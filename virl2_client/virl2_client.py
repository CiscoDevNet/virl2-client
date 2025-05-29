#
# This file is part of VIRL 2
# Copyright (c) 2019-2025, Cisco Systems, Inc.
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

import logging
import os
import re
import time
import warnings
from enum import Enum
from functools import lru_cache
from pathlib import Path
from threading import RLock
from typing import Any, NamedTuple
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
from .models.configuration import get_configuration
from .utils import _deprecated_argument, get_url_from_template, locked

_LOGGER = logging.getLogger(__name__)
cached = lru_cache(maxsize=None)  # cache results forever


class Version:
    __slots__ = ("version_str", "major", "minor", "patch")

    def __init__(self, version_str: str) -> None:
        self.version_str = version_str
        version_tuple = self.parse_version_str(version_str)
        self.major = int(version_tuple[0])
        self.minor = int(version_tuple[1])
        self.patch = int(version_tuple[2])

    @staticmethod
    def parse_version_str(version_str: str) -> str:
        regex = r"^(\d+)\.(\d+)\.(\d+)(.*)$"
        res = re.findall(regex, version_str)
        if not res:
            raise ValueError("Malformed version string.")
        return res[0]

    def __repr__(self):
        return self.version_str

    def __eq__(self, other):
        return (
            isinstance(other, self.__class__)
            and self.major == other.major
            and self.minor == other.minor
            and self.patch == other.patch
        )

    def __gt__(self, other):
        if isinstance(other, self.__class__):
            if self.major > other.major:
                return True
            elif self.major == other.major:
                if self.minor > other.minor:
                    return True
                elif self.minor == other.minor:
                    if self.patch > other.patch:
                        return True
        return False

    def __ge__(self, other):
        return self == other or self > other

    def __lt__(self, other):
        if isinstance(other, self.__class__):
            if self.major < other.major:
                return True
            elif self.major == other.major:
                if self.minor < other.minor:
                    return True
                elif self.minor == other.minor:
                    if self.patch < other.patch:
                        return True
        return False

    def __le__(self, other):
        return self == other or self < other

    def major_differs(self, other: Version) -> bool:
        return self.major != other.major

    def major_lt(self, other: Version) -> bool:
        return self.major < other.major

    def minor_differs(self, other: Version) -> bool:
        return self.minor != other.minor

    def minor_lt(self, other: Version) -> bool:
        return self.minor < other.minor

    def patch_differs(self, other: Version) -> bool:
        return self.patch != other.patch

    def minor_or_patch_differs(self, other: Version) -> bool:
        return self.minor_differs(other) or self.patch_differs(other)


class ClientConfig(NamedTuple):
    """Stores client library configuration, which can be used to create
    any number of identically configured instances of ClientLibrary."""

    url: str | None = None
    username: str | None = None
    password: str | None = None
    ssl_verify: bool | str = True
    allow_http: bool = False
    auto_sync: float = 1.0
    events: bool = False
    raise_for_auth_failure: bool = True
    convergence_wait_max_iter: int = 500
    convergence_wait_time: int | float = 5

    def make_client(self) -> ClientLibrary:
        client = ClientLibrary(
            url=self.url,
            username=self.username,
            password=self.password,
            ssl_verify=self.ssl_verify,
            raise_for_auth_failure=self.raise_for_auth_failure,
            allow_http=self.allow_http,
            convergence_wait_max_iter=self.convergence_wait_max_iter,
            convergence_wait_time=self.convergence_wait_time,
            events=self.events,
        )
        client.auto_sync_interval = self.auto_sync
        client.auto_sync = self.auto_sync >= 0.0 and not self.events
        return client


class DiagnosticsCategory(Enum):
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
    VERSION = Version("2.9.0")
    # list of Version objects
    INCOMPATIBLE_CONTROLLER_VERSIONS = [
        Version("2.0.0"),
        Version("2.0.1"),
        Version("2.1.0"),
        Version("2.1.1"),
        Version("2.1.2"),
        Version("2.2.1"),
        Version("2.2.2"),
        Version("2.2.3"),
        Version("2.3.0"),
        Version("2.3.1"),
        Version("2.4.0"),
        Version("2.4.1"),
        Version("2.5.0"),
        Version("2.5.1"),
        Version("2.6.0"),
        Version("2.6.1"),
    ]
    _URL_TEMPLATES = {
        "auth_test": "authok",
        "system_info": "system_information",
        "import": "import",
        "import_1x": "import/virl-1x",
        "sample_labs": "sample/labs",
        "sample_lab": "sample/labs/{lab_title}",
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
        ssl_verify: bool | str = True,
        raise_for_auth_failure: bool = False,
        allow_http: bool = False,
        convergence_wait_max_iter: int = 500,
        convergence_wait_time: int | float = 5,
        events: bool = False,
        client_type: str = None,
    ) -> None:
        """
        Initialize a ClientLibrary instance. Note that ssl_verify can
        also be a string that points to a cert (see class documentation).

        :param url: URL of controller. It's also possible to pass the
            URL via the ``VIRL2_URL`` or ``VIRL_HOST`` environment variable.
            If no protocol scheme is provided, "https:" is used.
        :param username: Username of the user to authenticate. It's also possible
            to pass the username via ``VIRL2_USER`` or ``VIRL_USERNAME`` variable.
        :param password: Password of the user to authenticate. It's also possible
            to pass the password via ``VIRL2_PASS`` or ``VIRL_PASSWORD`` variable.
        :param ssl_verify: Path of the SSL controller certificate, or True to load
            from ``CA_BUNDLE`` or ``CML_VERIFY_CERT`` environment variable,
            or False to disable.
        :param raise_for_auth_failure: Raise an exception if unable to connect to
            controller. (Use for scripting scenarios.)
        :param allow_http: If set, a https URL will not be enforced.
        :param convergence_wait_max_iter: Maximum number of iterations for convergence.
        :param convergence_wait_time: Time in seconds to sleep between convergence calls
            on the backend.
        :param events: A flag indicating whether to enable event-based data
            synchronization from the server. When enabled, utilizes a mechanism for
            receiving real-time updates from the server, instead of periodically
            requesting the data.
        :raises InitializationError: If no URL is provided, authentication fails or host
            can't be reached.
        """
        url, username, password, cert = get_configuration(
            url, username, password, ssl_verify
        )
        if cert is not None:
            ssl_verify = cert

        url, base_url = _prepare_url(url, allow_http)
        self.username: str = username
        self.password: str = password

        if ssl_verify is False:
            _LOGGER.warning("SSL Verification disabled")

        self._ssl_verify = ssl_verify
        try:
            self._session = make_session(base_url, ssl_verify, client_type)
        except httpx.InvalidURL as exc:
            raise InitializationError(exc) from None
        # checks version from system_info against self.VERSION
        controller_version = self.check_controller_version()

        self._session.auth = TokenAuth(self)
        # Note: session.auth is defined in the httpx module to be of type Auth,
        #  which has no logout function; this TokenAuth function will, therefore,
        #  not be visible to a type checker, causing warnings.

        self.auto_sync = True
        """`auto_sync` automatically syncs data with the backend after a specific
        time. The default expiry time is 1.0s. This time can be configured by
        setting the `auto_sync_interval`."""
        self.auto_sync_interval = 1.0  # seconds

        self.convergence_wait_max_iter = convergence_wait_max_iter
        self.convergence_wait_time = convergence_wait_time

        self.allow_http = allow_http
        self.definitions = NodeImageDefinitions(self._session)

        self.url: str = url
        self.raise_for_auth_failure = raise_for_auth_failure
        self._labs: dict[str, Lab] = {}

        self.licensing = Licensing(
            self._session, is_cert_deprecated=controller_version >= Version("2.7.0")
        )
        self.user_management = UserManagement(self._session)
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
            self._make_test_auth_call()
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

    def __repr__(self):
        return f"{self.__class__.__name__}({self.url!r})"

    def __str__(self):
        return f"{self.__class__.__name__} URL: {self._session.base_url}"

    def _url_for(self, endpoint, **kwargs):
        """
        Generate the URL for a given API endpoint.

        :param endpoint: The desired endpoint.
        :param **kwargs: Keyword arguments used to format the URL.
        :returns: The formatted URL.
        """
        return get_url_from_template(endpoint, self._URL_TEMPLATES, kwargs)

    def _make_test_auth_call(self) -> None:
        """
        Make a call to confirm that authentication works.

        :raises InitializationError: If authentication fails.
        """
        url = self._url_for("auth_test")
        try:
            self._session.get(url)
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

    @staticmethod
    def _environ_get(
        key: str, value: Any | None = None, default: Any | None = None
    ) -> Any | None:
        """
        If the value is not yet set, fetch it from the environment or return the default
        value.

        :param key: The key to fetch the value for.
        :param value: The value to use if it is already set.
        :param default: The default value to use if the key is not set
            and value is None.
        :returns: The fetched value or the default value.
        """
        if value is None:
            value = os.environ.get(key)
            if value:
                _LOGGER.info(f"Using value {key} from environment")
            else:
                value = default
        return value

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

    def check_controller_version(self) -> Version | None:
        """
        Check remote controller version against current client version
        (specified in `self.VERSION`) and against controller version
        blacklist (specified in `self.INCOMPATIBLE_CONTROLLER_VERSIONS`).
        Raise exception if versions are incompatible, or print warning
        if the client minor version is lower than the controller minor version.
        """
        controller_version = self.system_info().get("version", "")
        try:
            controller_version_obj = Version(controller_version)
        except (TypeError, ValueError):
            _LOGGER.warning(f"Invalid version detected: {controller_version}!")
            return None

        if controller_version_obj in self.INCOMPATIBLE_CONTROLLER_VERSIONS:
            raise InitializationError(
                f"Controller version {controller_version_obj} is marked incompatible! "
                f"List of versions marked explicitly as incompatible: "
                f"{self.INCOMPATIBLE_CONTROLLER_VERSIONS}."
            )
        if self.VERSION.major_lt(controller_version_obj):
            raise InitializationError(
                f"Major version mismatch. Client {self.VERSION}, "
                f"controller {controller_version_obj}."
            )
        if self.VERSION.minor_lt(controller_version_obj):
            _LOGGER.warning(
                f"Please ensure the client version is compatible with the controller "
                f"version. Client {self.VERSION}, controller {controller_version_obj}."
            )
        return controller_version_obj

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
        if path.suffix == ".virl":
            return True
        return False

    @locked
    def start_event_listening(self):
        """
        Start listening for and parsing websocket events.

        To replace the default event handling mechanism,
        subclass `event_handling.EventHandler` (or `EventHandlerBase` if necessary),
        then do::
        from .event_listening import EventListener
        custom_listener = EventListener()
        custom_listener._event_handler = CustomHandler(client_library)
        client_library.event_listener = custom_listener

        :returns:
        """
        from .event_listening import EventListener

        if self.event_listener is None:
            self.event_listener = EventListener(self)
        if not self.event_listener:
            self._session.lock = RLock()
            self.event_listener.start_listening()

    @locked
    def stop_event_listening(self):
        """Stop listening for and parsing websocket events."""
        if self.event_listener:
            self._session.lock = None
            self.event_listener.stop_listening()

    @locked
    def import_lab(
        self,
        topology: str,
        title: str | None = None,
        offline: bool | None = None,
        virl_1x: bool = False,
    ) -> Lab:
        """
        Import an existing topology from a string.

        :param topology: The topology representation as a string.
        :param title: The title of the lab.
        :param offline: DEPRECATED: Offline mode has been removed.
        :param virl_1x: Whether the topology format is the old, VIRL 1.x format.
        :returns: The imported Lab instance.
        :raises ValueError: If no lab ID is returned in the API response.
        :raises httpx.HTTPError: If there was a transport error.
        """
        _deprecated_argument(self.import_lab, offline, "offline")
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
    ):
        if virl_1x:
            url = self._url_for("import_1x")
        else:
            url = self._url_for("import")
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
    def import_sample_lab(self, title: str) -> Lab:
        """
        Import a built-in sample lab.

        :param title: The sample lab name.
        :returns: The imported Lab instance.
        """

        url = self._url_for("sample_lab", lab_title=title)
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
        for lab in list(self._labs.values()):
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
        :returns: A Lab instance representing the created lab.
        """
        url = self._url_for("labs")
        body = {"title": title, "description": description, "notes": notes}
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
        )
        lab._import_lab(result, created=True)
        self._labs[lab_id] = lab
        return lab

    @locked
    def remove_lab(self, lab_id: str | Lab) -> None:
        """
        Remove a lab identified by its ID or Lab object.

        Use this method with caution as it permanently deletes the specified lab.

        If you have the lab object, you can also do ``lab.remove()``.

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
        _LOGGER.debug(f"Removed lab: {response.text}")

    @locked
    def join_existing_lab(self, lab_id: str, sync_lab: bool = True) -> Lab:
        """
        Join a lab that exists on the server and make it accessible locally.

        If `sync_lab` is set to True, the current lab will be synchronized by applying
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
        )
        if sync_lab:
            lab.import_lab(topology)
            lab._initialized = True
        else:
            lab._owner = None
        self._labs[lab_id] = lab
        return lab

    def get_diagnostics(self, *categories: DiagnosticsCategory) -> dict:
        """
        Return selected diagnostics data as a JSON object.

        :param categories: List of diagnostics categories to fetch.
            DEPRECATED: If not provided, provide DiagnosticsCategory.ALL to fetch all
            diagnostics data.
        :returns: The diagnostics data.
        """
        if not categories:
            warnings.warn(
                "'ClientLibrary.get_diagnostics()' without arguments is deprecated. "
                "Use 'ClientLibrary.get_diagnostics(DiagnosticsCategory.ALL)' or "
                "'ClientLibrary.get_diagnostics(DiagnosticsCategory.COMPUTES, "
                "DiagnosticsCategory.LABS, ...)' with specific categories instead.",
                DeprecationWarning,
            )
            categories = [DiagnosticsCategory.ALL]
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
            owned by the admin (False).
        :returns: A list of lab IDs.
        """
        url: dict[str, str | dict] = {"url": self._url_for("labs")}
        if show_all:
            url["params"] = {"show_all": True}
        return self._session.get(**url).json()


def _prepare_url(url: str, allow_http: bool) -> tuple[str, str]:
    # prepare the URL
    try:
        url_parts = urlsplit(url, "https")
    except ValueError:
        message = "invalid URL / hostname"
        raise InitializationError(message)

    # https://docs.python.org/3/library/urllib.parse.html
    # Following the syntax specifications in RFC 1808, urlparse recognizes
    # a netloc only if it is properly introduced by ‘//’. Otherwise, the
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
