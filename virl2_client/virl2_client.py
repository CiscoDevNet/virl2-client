#
# This file is part of VIRL 2
# Copyright (c) 2019-2022, Cisco Systems, Inc.
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

import json
import logging
import os
import re
import time
import urllib
from functools import lru_cache
from pathlib import Path
from urllib.parse import urljoin, urlsplit, urlunsplit

from typing import NamedTuple, Optional, Any

import requests
import urllib3

from .exceptions import LabNotFound, InitializationError
from .models import (
    Context,
    Lab,
    NodeImageDefinitions,
    TokenAuth,
    Licensing,
    UserManagement,
    SystemManagement,
    GroupManagement,
)

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
        return "{}".format(self.version_str)

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

    url: Optional[str] = None
    username: Optional[str] = None
    password: Optional[str] = None
    ssl_verify: bool = True
    allow_http: bool = False
    auto_sync: float = 1.0
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
        )
        client.auto_sync = self.auto_sync >= 0.0
        client.auto_sync_interval = self.auto_sync
        return client


class ClientLibrary:
    """Python bindings for the REST API of a CML controller."""

    # current client version
    VERSION = Version("2.5.0")
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
    ]

    def __init__(
        self,
        url: Optional[str] = None,
        username: Optional[str] = None,
        password: Optional[str] = None,
        ssl_verify: bool | str = True,
        raise_for_auth_failure: bool = False,
        allow_http: bool = False,
        convergence_wait_max_iter: int = 500,
        convergence_wait_time: int | float = 5,
    ) -> None:
        """
        Initializes a ClientLibrary instance. Note that ssl_verify can
        also be a string that points to a cert (see class documentation).

        :param url: URL of controller. It's also possible to pass the
            URL via the ``VIRL2_URL`` environment variable. If no protocol
            scheme is provided, "https:" is used.
        :param username: Username of the user to authenticate
        :param password: Password of the user to authenticate
        :param ssl_verify: Path SSL controller certificate, or True to load
            from ``CA_BUNDLE`` environment variable, or False to disable
        :param raise_for_auth_failure: Raise an exception if unable
            to connect to controller (use for scripting scenarios)
        :param allow_http: If set, a https URL will not be enforced
        :param convergence_wait_max_iter: maximum number of iterations to wait for
            lab to converge
        :param convergence_wait_time: wait interval in seconds to wait during one
            iteration during lab convergence wait
        :raises InitializationError: If no URL is provided,
            authentication fails or host can't be reached
        """

        url = self._environ_get("VIRL2_URL", url)
        if url is None or len(url) == 0:
            message = "no URL provided"
            raise InitializationError(message)

        url, base_url = self._prepare_url(url, allow_http)

        # check environment for username
        username = self._environ_get("VIRL2_USER", username)
        if username is None or len(username) == 0:
            message = "no username provided"
            raise InitializationError(message)
        self.username = username

        # check environment for password
        password = self._environ_get("VIRL2_PASS", password)
        if password is None or len(password) == 0:
            message = "no password provided"
            raise InitializationError(message)
        self.password = password

        self._context = Context(base_url)
        """
        Within the Client Library context:
        `requests.Session()` instance that can be used to send requests
        to the controller.
        `uuid.uuid4()` instance to uniquely identify this client library session.
        `base_url` stores the base URL.
        """

        # http://docs.python-requests.org/en/master/user/advanced/#ssl-cert-verification

        if ssl_verify is True:
            ssl_verify_parsed = self._environ_get("CA_BUNDLE", default=True)
        else:
            ssl_verify_parsed = False
        self.session.verify = ssl_verify_parsed

        if ssl_verify_parsed is False:
            _LOGGER.warning("SSL Verification disabled")
            urllib3.disable_warnings()

        # checks version from system_info against self.VERSION
        self.check_controller_version()

        self.session.auth = TokenAuth(self)
        # Note: session.auth is defined in the requests module to be of type AuthBase,
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
        self.definitions = NodeImageDefinitions(self._context)

        self.url: str = url
        self.raise_for_auth_failure = raise_for_auth_failure
        self._labs: dict[str, Lab] = {}

        self.licensing = Licensing(context=self._context)
        self.user_management = UserManagement(context=self._context)
        self.group_management = GroupManagement(context=self._context)
        self.system_management = SystemManagement(context=self._context)

        try:
            self._make_test_auth_call()
        except InitializationError as exc:
            if raise_for_auth_failure:
                raise
            else:
                _LOGGER.warning(exc)
                return

    def __repr__(self):
        return "{}({!r}, {!r}, {!r}, {!r}, {!r}, {!r})".format(
            self.__class__.__name__,
            self.url,
            self.username,
            self.password,
            self._context.session.verify,
            self.raise_for_auth_failure,
            self.allow_http,
        )

    def __str__(self):
        return "{} URL: {}".format(self.__class__.__name__, self._context.base_url)

    def _prepare_url(self, url: str, allow_http: bool) -> tuple[str, str]:
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

    def _make_test_auth_call(self) -> None:
        """Make a call to confirm auth works by using the "authok" endpoint."""
        try:
            url = self._base_url + "authok"
            response = self.session.get(url)
            response.raise_for_status()
        except requests.HTTPError as exc:
            response = exc.response
            status_code = response.status_code
            if status_code == requests.codes.forbidden:  # pylint: disable=E1101
                message = (
                    "Unable to authenticate, please check your username and password"
                )
                raise InitializationError(message)
            raise
        except requests.exceptions.ConnectionError as exc:
            # TODO: subclass InitializationError
            raise InitializationError(exc)

    @staticmethod
    def _environ_get(
        key: str, value: Optional[Any] = None, default: Optional[Any] = None
    ) -> Optional[Any]:
        """If the value is not set yet, fetch it from environment or return default."""
        if value is None:
            value = os.environ.get(key)
            if value:
                _LOGGER.info("Using value %s from environment", key)
            else:
                value = default
        return value

    @property
    def session(self) -> requests.Session:
        """
        Returns the used Requests session object.

        :returns: The Requests session object
        """
        return self._context.session

    @property
    def _base_url(self) -> str:
        """
        Returns the base URL to access the controller.

        :returns: The base URL
        """
        return self._context.base_url

    def logout(self, clear_all_sessions: bool = False) -> None:
        """
        Invalidate current token.
        """
        return self.session.auth.logout(  # type: ignore
            clear_all_sessions=clear_all_sessions
        )
        # See session.auth assignment in __init__ for ignore reasoning.

    def get_host(self) -> str:
        """
        Returns the hostname of the session to the controller.

        :returns: A hostname
        """
        split_url = urllib.parse.urlsplit(self._base_url)
        return split_url.hostname or ""

    def system_info(self) -> dict:
        """
        Get information about the system where the application runs.
        Can be called without authentication.

        :returns: system information json
        """
        response = self.session.get(urljoin(self._base_url, "system_information"))
        response.raise_for_status()
        return response.json()

    def check_controller_version(
        self, controller_version: Optional[str] = None
    ) -> None:
        """
        Checks remote controller version against current client version
        (specified in self.VERSION) and against controller version
        blacklist (specified in self.INCOMPATIBLE_CONTROLLER_VERSIONS) and
        raises exception if versions are incompatible or prints warning
        if client minor version is lower than controller minor version.
        """
        controller_version = (
            controller_version or self.system_info().get("version", "").split("-")[0]
        )

        # are we running against a test version?
        if controller_version == "testing":
            _LOGGER.warning("testing version detected!")
            return

        controller_version_obj = Version(controller_version)
        if controller_version_obj in self.INCOMPATIBLE_CONTROLLER_VERSIONS:
            raise InitializationError(
                "Controller version {} is marked incompatible! "
                "List of versions marked explicitly as incompatible: {}.".format(
                    controller_version_obj, self.INCOMPATIBLE_CONTROLLER_VERSIONS
                )
            )
        if self.VERSION.major_differs(controller_version_obj):
            raise InitializationError(
                "Major version mismatch. Client {}, controller {}.".format(
                    self.VERSION, controller_version_obj
                )
            )
        if self.VERSION.minor_differs(controller_version_obj) and self.VERSION.minor_lt(
            controller_version_obj
        ):
            _LOGGER.warning(
                "Please ensure the client version is compatible with the controller"
                " version. Client %s, controller %s.",
                self.VERSION,
                controller_version_obj,
            )

    def is_system_ready(
        self, wait: bool = False, max_wait: int = 60, sleep: int = 5
    ) -> bool:
        """
        Reports whether the system is ready or not.

        :param wait: if this is true, the call will block until it's ready
        :param max_wait: maximum time to wait, in seconds
        :param sleep: time to wait between tries, in seconds
        :returns: ready state
        """
        loops = 1
        if wait:
            loops = int(max_wait / sleep)
        ready = False
        while not ready and loops > 0:
            try:
                result = self.system_info()
                ready = bool(result.get("ready"))
            except requests.HTTPError:
                # 502 Bad Gateway is expected and hints
                # that system is not ready - no need to
                # raise - just wait
                ready = False
            if not ready and loops > 0:
                time.sleep(sleep)
            loops -= 1
        return ready

    @staticmethod
    def is_virl_1x(path: Path) -> bool:
        if path.suffix == ".virl":
            return True
        return False

    def import_lab(
        self,
        topology: str,
        title: Optional[str] = None,
        offline: bool = False,
        virl_1x: bool = False,
    ) -> Lab:
        """
        Imports an existing topology from a string.

        :param topology: Topology representation as a string
        :param title: Title of the lab (optional)
        :param offline: whether the ClientLibrary should import the
            lab locally.  The topology parameter has to be a JSON string
            in this case.  This can not be XML or YAML representation of
            the lab.  Compatible JSON from `GET /labs/{lab_id}/topology`.
        :param virl_1x: Is this old virl-1x topology format (default=False)
        :returns: A Lab instance
        :raises ValueError: if there's no lab ID in the API response
        :raises requests.exceptions.HTTPError: if there was a transport error
        """
        # TODO: refactor to return the local lab, and sync it,
        #  if already exists in self._labs
        if offline:
            lab_id = "offline_lab"
        else:
            if virl_1x:
                url = "{}import/virl-1x".format(self._base_url)
            else:
                url = "{}import".format(self._base_url)
            if title is not None:
                url = "{}?title={}".format(url, title)
            response = self.session.post(url, data=topology)
            response.raise_for_status()
            result = response.json()
            lab_id = result.get("id")
            if lab_id is None:
                raise ValueError("No lab ID returned!")

        lab = Lab(
            title,
            lab_id,
            self._context,
            self.username,
            self.password,
            auto_sync=self.auto_sync,
            auto_sync_interval=self.auto_sync_interval,
        )

        if offline:
            topology_dict = json.loads(topology)
            # ensure the lab owner is not properly set
            # how does below get to offline? user_id is calling controller
            topology_dict["lab"]["owner"] = self.user_management.user_id(self.username)
            lab.import_lab(topology_dict)
        else:
            lab.sync()
        self._labs[lab_id] = lab
        return lab

    def import_lab_from_path(self, path: str, title: Optional[str] = None) -> Lab:
        """
        Imports an existing topology from a file / path.

        :param path: Topology filename / path
        :param title: Title of the lab
        :returns: A Lab instance
        """
        topology_path = Path(path)
        if not topology_path.exists():
            message = "{} can not be found".format(path)
            raise FileNotFoundError(message)

        topology = topology_path.read_text()
        return self.import_lab(
            topology, title=title, virl_1x=self.is_virl_1x(topology_path)
        )

    def get_sample_labs(self) -> dict[str, dict]:
        """
        Returns a dictionary with information about all sample labs available on host.

        :returns: A dictionary of sample lab information, where keys are titles
        """
        url = urljoin(self._base_url, "sample/labs")
        response = self.session.get(url)
        response.raise_for_status()
        return response.json()

    def import_sample_lab(self, title: str) -> Lab:
        """
        Imports a built-in sample lab.

        :param title: sample lab name, as returned by get_sample_labs
        :returns: a Lab instance
        """

        url = urljoin(self._base_url, "sample/labs/" + title)
        response = self.session.put(url)
        response.raise_for_status()
        lab_id = response.json()
        return self.join_existing_lab(lab_id)

    def all_labs(self, show_all: bool = False) -> list[Lab]:
        """
        Retrieves a list of all defined labs.

        :param show_all: Whether to get only labs owned by the admin or all user labs
        :returns: A list of lab objects
        :rtype: list[models.Lab]
        """
        # TODO: integrate this further with local labs - check if already exist
        url = "labs"
        if show_all:
            url += "?show_all=true"
        url = urljoin(self._base_url, url)
        response = self.session.get(url)
        response.raise_for_status()
        lab_ids = response.json()
        result = []
        for lab_id in lab_ids:
            lab = self.join_existing_lab(lab_id)
            result.append(lab)

        return result

    def local_labs(self) -> list[Lab]:
        # TODO: first sync with controller to pull all possible labs
        return [lab for lab in self._labs.values()]

    def get_local_lab(self, lab_id: str) -> Lab:
        try:
            return self._labs[lab_id]
        except KeyError:
            raise LabNotFound(lab_id)

    def create_lab(self, title: Optional[str] = None) -> Lab:
        """
        Creates an empty lab with the given name. If no name is given, then
        the created lab ID is set as the name.

        Note that the lab will be auto-syncing according to the Client Library's
        auto-sync setting when created. The lab has a property to override this
        on a per-lab basis.

        Example::

            lab = client_library.create_lab()
            print(lab.id)
            lab.create_node("r1", "iosv", 50, 100)

        :param title: The Lab name (or title)
        :returns: A Lab instance
        """
        url = self._base_url + "labs"
        params = {"title": title}
        response = self.session.post(url, params=params)
        response.raise_for_status()
        result = response.json()
        # TODO: server generated title not loaded
        lab_id = result["id"]
        lab = Lab(
            title or lab_id,
            lab_id,
            self._context,
            self.username,
            self.password,
            auto_sync=self.auto_sync,
            auto_sync_interval=self.auto_sync_interval,
            wait_max_iterations=self.convergence_wait_max_iter,
            wait_time=self.convergence_wait_time,
        )
        self._labs[lab_id] = lab
        return lab

    def remove_lab(self, lab_id: str) -> None:
        """
        Use carefully, it removes a given lab::

            client_library.remove_lab("1f6cd7")

        :param lab_id: The lab ID to be removed.
        :type lab_id: str
        """
        url = self._base_url + "labs/{}".format(lab_id)
        response = self.session.delete(url)
        response.raise_for_status()
        self._labs.pop(lab_id, None)

    def join_existing_lab(self, lab_id: str, sync_lab: bool = True) -> Lab:
        """
        Creates a new ClientLibrary lab instance that is retrieved
        from the controller.

        If `sync_lab` is set to true, then synchronize current lab
        by applying the changes that were done in UI or in another
        ClientLibrary session.

        Join preexisting lab::

            lab = client_library.join_existing_lab("2e6a18")

        :param lab_id: The lab ID to be joined.
        :param sync_lab: Synchronize changes.
        :returns: A Lab instance
        """
        # TODO: check if lab exists through REST call
        title = None
        # TODO: sync lab name
        lab = Lab(
            title,
            lab_id,
            self._context,
            self.username,
            self.password,
            auto_sync=self.auto_sync,
            auto_sync_interval=self.auto_sync_interval,
        )
        if sync_lab:
            lab.sync()

        self._labs[lab_id] = lab
        return lab

    def get_diagnostics(self) -> dict:
        """
        Returns the controller diagnostic data as JSON

        :returns: diagnostic data
        :rtype: dict
        """
        url = self._base_url + "diagnostics"
        response = self.session.get(url)
        response.raise_for_status()
        return response.json()

    def get_system_health(self) -> dict:
        """
        Returns the controller system health data as JSON

        :returns: system health data
        """
        url = self._base_url + "system_health"
        response = self.session.get(url)
        response.raise_for_status()
        return response.json()

    def get_system_stats(self) -> dict:
        """
        Returns the controller resource statistics as JSON

        :returns: system resource statistics
        """
        url = self._base_url + "system_stats"
        response = self.session.get(url)
        response.raise_for_status()
        return response.json()

    def find_labs_by_title(self, title: str) -> list[Lab]:
        """
        Return a list of labs which match the given title.

        :param title: The title to search for
        :returns: A list of lab objects which match the title specified
        """
        url = self._base_url + "populate_lab_tiles"
        response = self.session.get(url)
        response.raise_for_status()

        resp = response.json()

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
        Returns list of all lab IDs.

        :param show_all: Whether to get only labs owned by the admin or all user labs
        :type show_all: bool
        :returns: a list of Lab IDs
        :rtype: list[str]
        """
        url = "labs"
        if show_all:
            url += "?show_all=true"
        url = urljoin(self._base_url, url)
        response = self.session.get(url)
        response.raise_for_status()
        return response.json()
