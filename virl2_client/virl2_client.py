#
# This file is part of VIRL 2
# Copyright (c) 2019-2026, Cisco Systems, Inc.
# All rights reserved.
#
# Python bindings for the Cisco VIRL 2 Network Simulation Platform
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#

from __future__ import annotations

import getpass
import logging
import os
import sys
import time
import warnings
from enum import Enum
from pathlib import Path
from threading import RLock
from typing import Any, ClassVar, NamedTuple
from urllib.parse import urljoin, urlsplit, urlunsplit

import httpx

from .exceptions import InitializationError, LabNotFound
from .models import (
    AuthManagement,
    GroupManagement,
    Lab,
    Licensing,
    NodeImageDefinitions,
    ResourcePoolManagement,
    SystemManagement,
    TokenAuth,
    UserManagement,
)
from .models.authentication import make_session
from .utils import Version, get_url_from_template, locked

_LOGGER = logging.getLogger(__name__)


class ClientConfig(NamedTuple):
    """Stores client library configuration, which can be used to create
    any number of identically configured instances of ClientLibrary."""

    _CONFIG_FILE_NAME = ".virlrc"
    _CONFIG_SOURCES = {  # noqa: RUF012
        "url": ["VIRL2_URL", "VIRL_HOST"],
        "username": ["VIRL2_USER", "VIRL_USERNAME"],
        "password": ["VIRL2_PASS", "VIRL_PASSWORD"],
        "jwtoken": ["VIRL2_JWT"],
        "ssl_verify": ["CA_BUNDLE", "CML_VERIFY_CERT"],
    }

    url: str | None = None
    username: str | None = None
    password: str | None = None
    jwtoken: str | None = None
    ssl_verify: bool | str = True
    allow_http: bool = False
    auto_sync: float = 1.0
    events: bool = False
    raise_for_auth_failure: bool = True
    convergence_wait_max_iter: int = 500
    convergence_wait_time: int | float = 5
    check_version: bool = True

    def make_client(self) -> ClientLibrary:
        client = ClientLibrary(
            url=self.url,
            username=self.username,
            password=self.password,
            jwtoken=self.jwtoken,
            ssl_verify=self.ssl_verify,
            raise_for_auth_failure=self.raise_for_auth_failure,
            allow_http=self.allow_http,
            convergence_wait_max_iter=self.convergence_wait_max_iter,
            convergence_wait_time=self.convergence_wait_time,
            check_version=self.check_version,
            events=self.events,
        )
        client.auto_sync_interval = self.auto_sync
        client.auto_sync = self.auto_sync >= 0.0 and not self.events
        return client

    @classmethod
    def _get_from_file(cls, virlrc_parent: Path, prop_name: str) -> str | None:
        virlrc = virlrc_parent / cls._CONFIG_FILE_NAME
        if virlrc.is_file():
            with virlrc.open() as fh:
                config = fh.readlines()

            for line in config:
                if line.startswith(prop_name):
                    prop = line.split("=")[1].strip()
                    if prop.startswith('"') and prop.endswith('"'):
                        prop = prop[1:-1]
                    return prop
        return None

    @classmethod
    def _get_prop(cls, prop_name: str) -> str | None:
        cwd = Path.cwd()
        if prop := cls._get_from_file(cwd, prop_name):
            return prop

        for path in cwd.parents:
            if prop := cls._get_from_file(path, prop_name):
                return prop

        return cls._get_from_file(Path.home(), prop_name) or None

    @classmethod
    def _populate_from_env(cls, config: dict):
        for key, env_vars in cls._CONFIG_SOURCES.items():
            if config[key] is not None:
                continue
            for env_var in env_vars:
                if value := os.getenv(env_var):
                    config[key] = value
                    break

    @classmethod
    def _populate_from_rc_files(cls, config: dict):
        for key, env_vars in cls._CONFIG_SOURCES.items():
            if config[key] is None:
                config[key] = cls._get_prop(env_vars[0])

    @classmethod
    def _populate_from_inputs(cls, config: dict):
        if config["url"] is None:
            config["url"] = input("Please enter the IP / hostname of your CML server: ")

        if config["username"] is None and config["jwtoken"] is None:
            auth_input = input("Please enter your username or JWT (if using a token): ")
            if len(auth_input) > 32:
                config["jwtoken"] = auth_input
            else:
                config["username"] = auth_input

        if config["username"] is not None and config["password"] is None:
            config["password"] = getpass.getpass("Please enter your password: ")

    @classmethod
    def _validate(cls, config: dict[str, Any], final: bool = False) -> bool:
        errors: list[str] = []
        if not config["url"]:
            errors.append("No URL provided.")
        if not (config["jwtoken"] or (config["username"] and config["password"])):
            errors.append("Incomplete authentication configuration.")
        ssl_verify_pending = config["ssl_verify"] is None
        if final:
            if errors:
                raise InitializationError(" ".join(errors))
            if ssl_verify_pending:
                config["ssl_verify"] = True
            return True
        return not ssl_verify_pending and not errors

    @classmethod
    def get_configuration(
        cls,
        url: str | None,
        username: str | None,
        password: str | None,
        jwtoken: str | None,
        ssl_verify: bool | str | None,
        allow_inputs: bool | None = None,
    ) -> ClientConfig:
        config = {
            "url": url,
            "username": username,
            "password": password,
            "jwtoken": jwtoken,
            "ssl_verify": ssl_verify,
        }

        cls._populate_from_env(config)
        if cls._validate(config):
            return cls(**config)

        cls._populate_from_rc_files(config)
        if cls._validate(config):
            return cls(**config)

        if allow_inputs is None and not sys.stdin.isatty():
            warnings.warn(
                "Interactive inputs are deprecated when stdin is not a TTY. "
                "In the future, allow_inputs will default to False in such cases.",
                DeprecationWarning,
                stacklevel=2,
            )
        if allow_inputs is not False:
            cls._populate_from_inputs(config)
        if cls._validate(config, final=True):
            return cls(**config)


class DiagnosticsCategory(Enum):
    """Categories of diagnostics data that can be retrieved from the controller."""

    ALL = "all"
    COMPUTES = "computes"
    LABS = "labs"
    LAB_EVENTS = "lab_events"
    NODE_LAUNCH_QUEUE = "node_launch_queue"
    SERVICES = "services"
    NODE_DEFINITIONS = "node_definitions"
    USER_LIST = "user_list"
    LICENSING = "licensing"
    STARTUP_SCHEDULER = "startup_scheduler"


class ClientLibrary:
    """Python bindings for the REST API of a CML controller."""

    # current client version
    VERSION = Version("2.11.0")

    _URL_TEMPLATES: ClassVar[dict[str, str]] = {
        "auth": "authentication",
        "old_auth": "authok",
        "system_info": "system_information",
        "import": "import",
        "import_1x": "import/virl-1x",
        "sample_labs": "sample/labs",
        "sample_lab": "sample/labs/{sample_lab_id}",
        "labs": "labs",
        "lab": "labs/{lab_id}",
        "lab_topology": "labs/{lab_id}/topology",
        "diagnostics": "diagnostics/{category}",
        "system_health": "system_health",
        "system_stats": "system_stats",
        "populate_lab_tiles": "populate_lab_tiles",
    }

    def __init__(
        self,
        url: str | None = None,
        username: str | None = None,
        password: str | None = None,
        jwtoken: str | None = None,
        ssl_verify: bool | str | None = None,
        raise_for_auth_failure: bool = False,
        allow_http: bool = False,
        convergence_wait_max_iter: int = 500,
        convergence_wait_time: int | float = 5,
        events: bool = False,
        client_type: str | None = None,
        check_version: bool = True,
    ) -> None:
        client_config = ClientConfig.get_configuration(
            url, username, password, jwtoken, ssl_verify
        )
        self.allow_http = allow_http
        url, base_url = _prepare_url(client_config.url, allow_http)
        self.username: str | None = client_config.username
        self.password: str | None = client_config.password
        self.jwtoken: str | None = client_config.jwtoken
        self.url: str = url
        self.raise_for_auth_failure = raise_for_auth_failure
        self.check_version = check_version

        self._ssl_verify = client_config.ssl_verify
        if client_config.ssl_verify is False and not allow_http:
            _LOGGER.warning("SSL Verification disabled")

        self.auto_sync = True
        """auto_sync automatically syncs data with the backend after a specific
        time. The default expiry time is 1.0s. This time can be configured by
        setting the auto_sync_interval."""
        self.auto_sync_interval = 1.0  # seconds

        self.convergence_wait_max_iter = convergence_wait_max_iter
        self.convergence_wait_time = convergence_wait_time

        self._labs: dict[str, Lab] = {}

        try:
            self._session = make_session(base_url, ssl_verify, client_type)
        except httpx.InvalidURL as exc:
            raise InitializationError(exc) from None
        self._session.controller_version = self.check_controller_version()

        self._session.auth = TokenAuth(self)
        # Note: session.auth is defined in the httpx module to be of type Auth,
        #  which has no logout function; this TokenAuth function will, therefore,
        #  not be visible to a type checker, causing warnings.

        self.definitions = NodeImageDefinitions(self._session)
        self.licensing = Licensing(self._session)
        self.user_management = UserManagement(
            self._session,
            auto_sync=self.auto_sync,
            auto_sync_interval=self.auto_sync_interval,
        )
        self.group_management = GroupManagement(self._session)
        self.system_management = SystemManagement(
            self._session,
            auto_sync=self.auto_sync,
            auto_sync_interval=self.auto_sync_interval,
        )
        self.resource_pool_management = ResourcePoolManagement(
            self._session,
            auto_sync=self.auto_sync,
            auto_sync_interval=self.auto_sync_interval,
        )
        self.auth_management = AuthManagement(
            self._session,
            auto_sync=self.auto_sync,
            auto_sync_interval=self.auto_sync_interval,
        )

        try:
            self._make_test_auth_call(
                self._session.controller_version >= Version("2.10.0")
            )
        except InitializationError as exc:
            if raise_for_auth_failure:
                raise
            else:
                _LOGGER.warning(exc)
                return

        self.event_listener = None
        self._session.lock = None
        if events:
            # http-based auto sync should be off by default when using events
            self.auto_sync = False
            self.start_event_listening()

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}({self.url!r})"

    def __str__(self) -> str:
        return f"{self.__class__.__name__} URL: {self._session.base_url}"

    def _url_for(self, endpoint: str, **kwargs: str) -> str:
        """
        Generate the URL for a given API endpoint.

        :param endpoint: The desired endpoint.
        :param **kwargs: Keyword arguments used to format the URL.
        :returns: The formatted URL.
        """
        return get_url_from_template(endpoint, self._URL_TEMPLATES, kwargs)

    def _make_test_auth_call(self, new_auth: bool) -> None:
        """
        Make a call to confirm that authentication works.

        :raises InitializationError: If authentication fails.
        """
        url = self._url_for("auth" if new_auth else "old_auth")
        try:
            response = self._session.get(url)
        except httpx.HTTPStatusError as exc:
            status_code = exc.response.status_code
            if status_code == httpx.codes.FORBIDDEN:
                message = (
                    "Unable to authenticate, please check your username and password"
                )
                raise InitializationError(message)
            raise
        except httpx.HTTPError as exc:
            raise InitializationError(exc)
        if new_auth:
            user_info: dict = response.json()
            self.user_id = user_info["id"]
            self.admin = user_info.get("admin", False)
            self.username = user_info["username"]

    @property
    def uuid(self) -> str:
        """Return the UUID4 that identifies this client to the server."""
        return self._session.headers["X-Client-UUID"]

    def logout(self, clear_all_sessions: bool = False) -> bool:
        """
        Invalidate the current token.

        :param clear_all_sessions: Whether to clear all user sessions as well.
        """
        return self._session.auth.logout(clear_all_sessions=clear_all_sessions)

    def get_host(self) -> str:
        """
        Return the hostname of the session to the controller.

        :returns: The hostname.
        """
        return self._session.base_url.host

    def system_info(self) -> dict:
        """
        Get information about the system where the application runs.
        Can be called without authentication.

        :returns: The system information as a JSON object.
        """
        url = self._url_for("system_info")
        return self._session.get(url).json()

    def check_controller_version(self) -> Version:
        """
        Check remote controller version against current client version
        (specified in self.VERSION and support last 3 minor versions).
        Raise exception if versions are incompatible, or print warning
        if the client minor version is lower than the controller minor version.
        Compatibility validation is disabled if `self.check_version` attribute
        is set to False, but the version is always parsed and returned.

        :raises InitializationError: If the controller version is unparseable
            or incompatible.
        :returns: The controller version.
        """
        controller_version_str = self.system_info().get("version", "")
        try:
            controller_version = Version(controller_version_str)
        except (TypeError, ValueError):
            raise InitializationError(
                f"Controller returned invalid version: {controller_version_str}"
            )

        if not self.check_version:
            return controller_version

        if self.VERSION.major_lt(controller_version):
            raise InitializationError(
                "Major version mismatch. "
                f"Client {self.VERSION}, controller {controller_version}."
            )
        if self.VERSION.minor - 3 >= controller_version.minor:
            raise InitializationError(
                "Unsupported minor version (only last 3 minor versions are supported). "
                f"Client {self.VERSION}, controller {controller_version}."
            )
        if self.VERSION.minor_lt(controller_version):
            _LOGGER.warning(
                "Please ensure the client version is compatible with the controller "
                "version. Client %s, controller %s.",
                self.VERSION,
                controller_version,
            )
        return controller_version

    def is_system_ready(
        self, wait: bool = False, max_wait: int = 60, sleep: int = 5
    ) -> bool:
        """
        Report whether the system is ready or not.

        :param wait: Whether to block until the system is ready.
        :param max_wait: The maximum time to wait in seconds.
        :param sleep: The time to wait between tries in seconds.
        :returns: The ready state of the system.
        """
        loops = 1
        if wait:
            loops = int(max_wait / sleep)
        ready = False
        while not ready and loops > 0:
            try:
                result = self.system_info()
                ready = bool(result.get("ready"))
            except httpx.HTTPStatusError as exc:
                if exc.response.status_code == httpx.codes.BAD_GATEWAY:
                    # 502 Bad Gateway is expected and hints
                    # that system is not ready - no need to
                    # raise - just wait
                    ready = False
                else:
                    raise
            if not ready and loops > 0:
                time.sleep(sleep)
            loops -= 1
        return ready

    @staticmethod
    def is_virl_1x(path: Path) -> bool:
        """
        Check if the given file is of VIRL version 1.x.

        :param path: The path to check.
        :returns: Whether the file is of VIRL version 1.x.
        """
        return path.suffix == ".virl"

    @locked
    def start_event_listening(self) -> None:
        """
        Start listening for and parsing websocket events.

        To replace the default event handling mechanism,
        subclass EventHandler (or EventHandlerBase if necessary),
        then do::
            custom_listener = EventListener()
            custom_listener._event_handler = CustomHandler(client_library)
            client_library.event_listener = custom_listener
        """
        from .event_listening import EventListener  # noqa: PLC0415

        if self.event_listener is None:
            self.event_listener = EventListener(self)
        if not self.event_listener:
            self._session.lock = RLock()
            self.event_listener.start_listening()

    @locked
    def stop_event_listening(self) -> None:
        """Stop listening for and parsing websocket events."""
        if self.event_listener:
            self._session.lock = None
            self.event_listener.stop_listening()

    @locked
    def import_lab(
        self,
        topology: str,
        title: str | None = None,
        virl_1x: bool = False,
    ) -> Lab:
        """
        Import an existing topology from a string.

        :param topology: The topology representation as a string.
        :param title: The title of the lab.
        :param virl_1x: Whether the topology format is the old, VIRL 1.x format.
        :returns: The imported Lab instance.
        :raises ValueError: If no lab ID is returned in the API response.
        :raises httpx.HTTPError: If there was a transport error.
        """
        lab = self._create_imported_lab(topology, title, virl_1x)
        lab.sync()
        self._labs[lab.id] = lab
        return lab

    @locked
    def _create_imported_lab(
        self,
        topology: str,
        title: str | None = None,
        virl_1x: bool = False,
    ) -> Lab:
        url = self._url_for("import_1x" if virl_1x else "import")
        params = {"title": title} if title else None
        result = self._session.post(url, params=params, content=topology).json()
        lab_id = result.get("id")
        if lab_id is None:
            raise ValueError("No lab ID returned!")

        return Lab(
            title,
            lab_id,
            self._session,
            self.username,
            self.password,
            auto_sync=self.auto_sync,
            auto_sync_interval=self.auto_sync_interval,
            resource_pool_manager=self.resource_pool_management,
            user_management=self.user_management,
        )

    @locked
    def import_lab_from_path(self, path: Path | str, title: str | None = None) -> Lab:
        """
        Import an existing topology from a file or path.

        :param path: The topology filename or path.
        :param title: The title of the lab.
        :returns: The imported Lab instance.
        :raises FileNotFoundError: If the specified path does not exist.
        """
        topology_path = Path(path)
        if not topology_path.exists():
            raise FileNotFoundError(path)

        topology = topology_path.read_text()
        return self.import_lab(
            topology, title=title, virl_1x=self.is_virl_1x(topology_path)
        )

    def get_sample_labs(self) -> dict[str, dict]:
        """
        Return a dictionary with information about all sample labs
        available on the host.

        :returns: A dictionary of sample lab information where the keys are the titles.
        """
        url = self._url_for("sample_labs")
        return self._session.get(url).json()

    @locked
    def import_sample_lab(self, sample_lab_id: str) -> Lab:
        """
        Import a built-in sample lab.

        :param sample_lab_id: The sample lab ID.
        :returns: The imported Lab instance.
        """

        url = self._url_for("sample_lab", sample_lab_id=sample_lab_id)
        lab_id = self._session.put(url).json()
        return self.join_existing_lab(lab_id)

    @locked
    def all_labs(self, show_all: bool = False) -> list[Lab]:
        """
        Join all labs owned by this user (or all labs) and return their list.

        :param show_all: Whether to get only labs owned by the admin or all user labs.
        :returns: A list of Lab objects.
        """
        lab_ids = self.get_lab_list(show_all=show_all)
        result = []
        for lab_id in lab_ids:
            lab = self.join_existing_lab(lab_id)
            result.append(lab)
        return result

    @locked
    def _remove_stale_labs(self):
        """Remove stale labs from the client library."""
        for lab in tuple(self._labs.values()):
            if lab._stale:
                self._remove_lab_local(lab)

    @locked
    def local_labs(self) -> list[Lab]:
        """
        Return a list of local labs.

        :returns: A list of local labs.
        """
        self._remove_stale_labs()
        return list(self._labs.values())

    @locked
    def get_local_lab(self, lab_id: str) -> Lab:
        """
        Get a local lab by its ID.

        :param lab_id: The ID of the lab.
        :returns: The Lab object with the specified ID.
        :raises LabNotFound: If the lab with the given ID does not exist.
        """
        self._remove_stale_labs()
        try:
            return self._labs[lab_id]
        except KeyError:
            raise LabNotFound(lab_id)

    @locked
    def create_lab(
        self,
        title: str | None = None,
        description: str | None = None,
        notes: str | None = None,
        autostart: dict | None = None,
        node_staging: dict | None = None,
    ) -> Lab:
        """
        Create a new lab with optional title, description, and notes.

        If no title, description, or notes are provided, the server will generate a
        default title in the format "Lab at Mon 13:30 PM" and leave the description
        and notes blank.

        The lab will automatically sync based on the Client Library's auto-sync setting
        when created, but this behavior can be overridden on a per-lab basis.

        Example::

            lab = client_library.create_lab()
            print(lab.id)
            lab.create_node("r1", "iosv", 50, 100)

        :param title: The title of the lab.
        :param description: The description of the lab.
        :param notes: The notes of the lab.
        :param autostart: Parameter for autostart (enabled, priority, delay).
        :param node_staging: Parameter for node staging (enabled, abort_on_failure, start_remaining).
        :returns: A Lab instance representing the created lab.
        """
        url = self._url_for("labs")
        body: dict[str, str | dict | None] = {
            "title": title,
            "description": description,
            "notes": notes,
        }
        if autostart:
            body["autostart"] = autostart
        if node_staging:
            body["node_staging"] = node_staging

        # exclude values left at None
        body = {k: v for k, v in body.items() if v is not None}
        result = self._session.post(url, json=body).json()
        lab_id = result["id"]
        lab = Lab(
            result["lab_title"],
            lab_id,
            self._session,
            self.username,
            self.password,
            auto_sync=self.auto_sync,
            auto_sync_interval=self.auto_sync_interval,
            wait_max_iterations=self.convergence_wait_max_iter,
            wait_time=self.convergence_wait_time,
            resource_pool_manager=self.resource_pool_management,
            user_management=self.user_management,
        )
        lab._import_lab(result, created=True)
        self._labs[lab_id] = lab
        return lab

    @locked
    def remove_lab(self, lab_id: str | Lab) -> None:
        """
        Remove a lab identified by its ID or Lab object.

        Use this method with caution as it permanently deletes the specified lab.

        If you have the lab object, you can also do lab.remove().

        :param lab_id: The ID or Lab object representing the lab to be removed.
        """
        self._remove_stale_labs()
        if isinstance(lab_id, Lab):
            lab_id.remove()
            self._remove_lab_local(lab_id)
        elif lab_id in self._labs:
            self._labs[lab_id].remove()
            self._remove_lab_local(self._labs[lab_id])
        else:
            self._remove_unjoined_lab(lab_id)

    @locked
    def _remove_lab_local(self, lab: Lab) -> None:
        """Helper function to remove a lab from the client library."""
        try:
            del self._labs[lab._id]
            lab._stale = True
        except KeyError:
            # element may already have been deleted on server,
            # and removed locally due to auto-sync
            pass

    def _remove_unjoined_lab(self, lab_id: str):
        """Helper function to remove an unjoined lab from the server."""
        url = self._url_for("lab", lab_id=lab_id)
        response = self._session.delete(url)
        _LOGGER.debug("Removed lab: %s", response.text)

    @locked
    def join_existing_lab(self, lab_id: str, sync_lab: bool = True) -> Lab:
        """
        Join a lab that exists on the server and make it accessible locally.

        If sync_lab is set to True, the current lab will be synchronized by applying
        any changes that were made in the UI or in another ClientLibrary session.

        Example::
            lab = client_library.join_existing_lab("2e6a18")

        :param lab_id: The ID of the lab to be joined.
        :param sync_lab: Whether to synchronize the lab.
        :returns: A Lab instance representing the joined lab.
        :raises LabNotFound: If no lab with the given ID exists on the host.
        """
        self._remove_stale_labs()
        if lab_id in self._labs:
            return self._labs[lab_id]
        topology = {}
        if sync_lab:
            try:
                # check if lab exists through REST call
                url = self._url_for("lab_topology", lab_id=lab_id)
                topology = self._session.get(url).json()
            except httpx.HTTPStatusError as exc:
                if exc.response.status_code == 404:
                    raise LabNotFound(lab_id)
                raise
            title = topology.get("lab", {}).get("title")
        else:
            title = None

        lab = Lab(
            title,
            lab_id,
            self._session,
            self.username,
            self.password,
            auto_sync=self.auto_sync,
            auto_sync_interval=self.auto_sync_interval,
            wait_max_iterations=self.convergence_wait_max_iter,
            wait_time=self.convergence_wait_time,
            resource_pool_manager=self.resource_pool_management,
            user_management=self.user_management,
        )
        if sync_lab:
            lab.import_lab(topology)
            lab._initialized = True
            lab._last_sync_topology_time = time.time()
        else:
            lab._owner = None
        self._labs[lab_id] = lab
        return lab

    def get_diagnostics(self, *categories: DiagnosticsCategory) -> dict:
        """
        Return selected diagnostics data as a JSON object.

        :param categories: List of diagnostics categories to fetch.
        :returns: The diagnostics data.
        """
        if not categories:
            raise ValueError(
                "No diagnostics category provided. Use "
                "ClientLibrary.get_diagnostics(DiagnosticsCategory.ALL) "
                "or provide one or more explicit categories."
            )
        if DiagnosticsCategory.USER_LIST in categories:
            warnings.warn(
                "'DiagnosticsCategory.USER_LIST' is deprecated. "
                "Use UserManagement.users() instead.",
                DeprecationWarning,
                stacklevel=2,
            )
        if DiagnosticsCategory.ALL in categories:
            categories = list(DiagnosticsCategory)[1:]

        diagnostics_data = {}
        for category in set(categories):
            value = category.value
            url = self._url_for("diagnostics", category=value)
            try:
                response = self._session.get(url)
                response.raise_for_status()
                diagnostics_data[value] = response.json()
            except httpx.HTTPStatusError:
                diagnostics_data[value] = {
                    "error": f"Failed to fetch {value} diagnostics"
                }
        return diagnostics_data

    def get_system_health(self) -> dict:
        """
        Return the controller system health data as a JSON object.

        :returns: The system health data.
        """
        url = self._url_for("system_health")
        return self._session.get(url).json()

    def get_system_stats(self) -> dict:
        """
        Return the controller resource statistics as a JSON object.

        :returns: The system resource statistics.
        """
        url = self._url_for("system_stats")
        return self._session.get(url).json()

    @locked
    def find_labs_by_title(self, title: str) -> list[Lab]:
        """
        Return a list of labs which match the given title.

        :param title: The title to search for.
        :returns: A list of Lab objects matching the specified title.
        """
        url = self._url_for("populate_lab_tiles")
        resp = self._session.get(url).json()

        # populate_lab_tiles response has been changed in 2.1
        # if it doesn't have a key "lab_tiles" then it's <2.1
        labs = resp.get("lab_tiles")
        if labs is None:
            labs = resp

        matched_lab_ids = []

        for lab_id, lab_data in labs.items():
            if lab_data["lab_title"] == title:
                matched_lab_ids.append(lab_id)

        matched_labs = []
        for lab_id in matched_lab_ids:
            lab = self.join_existing_lab(lab_id)
            matched_labs.append(lab)

        return matched_labs

    def get_lab_list(self, show_all: bool = False) -> list[str]:
        """
        Get the list of all lab IDs.

        :param show_all: Whether to include labs owned by all users (True) or only labs
            owned by the authenticated user (False).
        :returns: A list of lab IDs.
        """
        params = {"show_all": True} if show_all else None
        return self._session.get(self._url_for("labs"), params=params).json()


def _prepare_url(url: str, allow_http: bool) -> tuple[str, str]:
    # prepare the URL
    try:
        url_parts = urlsplit(url, "https")
    except ValueError:
        message = "invalid URL / hostname"
        raise InitializationError(message)

    # https://docs.python.org/3/library/urllib.parse.html
    # Following the syntax specifications in RFC 1808, urlparse recognizes
    # a netloc only if it is properly introduced by `//`. Otherwise, the
    # input is presumed to be a relative URL and thus to start with
    # a path component.
    if len(url_parts.netloc) == 0:
        try:
            url_parts = urlsplit("//" + url, "https")
        except ValueError:
            message = "invalid URL / hostname"
            raise InitializationError(message)

    if not allow_http and url_parts.scheme == "http":
        message = "invalid URL scheme (must be https)"
        raise InitializationError(message)
    if url_parts.scheme not in ("http", "https"):
        message = "invalid URL scheme (should be https)"
        raise InitializationError(message)
    url = urlunsplit(url_parts)
    base_url = urljoin(url, "api/v0/")
    return url, base_url
