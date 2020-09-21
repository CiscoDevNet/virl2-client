#
# Python bindings for the Cisco VIRL 2 Network Simulation Platform
#
# This file is part of VIRL 2
#
# Copyright 2020 Cisco Systems Inc.
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

# TODO: make this Python <3.5 compatible
import json
import logging
import os
import time
import urllib
import warnings
from functools import lru_cache
from pathlib import Path
from urllib.parse import urljoin, urlsplit, urlunsplit

import pkg_resources
import requests
import urllib3
from urllib3.exceptions import LocationParseError

from .exceptions import LabNotFound
from .models import Context, Lab, NodeImageDefinitions, TokenAuth, Licensing

logger = logging.getLogger(__name__)
cached = lru_cache(maxsize=None)  # cache results forever


class InitializationError(Exception):
    pass


class Version(object):

    __slots__ = ("version_str", "major", "minor", "patch")

    def __init__(self, version_str):
        self.version_str = version_str
        version_list = self.version_str.split(".")
        self.major = version_list[0]
        self.minor = version_list[1]
        self.patch = version_list[2]

    def __repr__(self):
        return "{}".format(self.version_str)

    def __eq__(self, other):
        return (
            self.major == other.major
            and self.minor == other.minor
            and self.patch == other.patch
        )

    def major_differs(self, other):
        return self.major != other.major

    def minor_differs(self, other):
        return self.minor != other.minor

    def patch_differs(self, other):
        return self.patch != other.patch

    def minor_or_patch_differs(self, other):
        return self.minor_differs(other) or self.patch_differs(other)


class ClientLibrary:
    """
    Initializes a ClientLibrary instance. Note that ssl_verify can
    also be a string that points to a cert (see class documentation).

    :param url: URL of controller. It's also possible to pass the
        URL via the ``VIRL2_URL`` environment variable. If no protocol
        scheme is provided, "https:" is used.
    :type url: str
    :param username: Username of the user to authenticate
    :type username: str
    :param password: Password of the user to authenticate
    :type password: str
    :param ssl_verify: SSL controller certificate verification
    :type ssl_verify: bool
    :param raise_for_auth_failure: Raise an exception if unable
        to connect to server (use for scripting scenarios)
    :type allow_http: bool
    :param allow_http: If set, a https URL will not be enforced
    :type raise_for_auth_failure: bool
    :raises InitializationError: If no URL is provided or
        authentication fails or host can't be reasched
    """

    # current client version
    VERSION = Version(version_str="2.1.0")
    # list of Version objects
    INCOMPATIBLE_CONTROLLER_VERSIONS = []

    def __init__(
        self,
        url=None,
        username=None,
        password=None,
        ssl_verify=True,
        raise_for_auth_failure=False,
        allow_http=False,
    ):
        """Constructor method"""

        # check environment for host URL
        env_url = os.environ.get("VIRL2_URL")
        if env_url:
            logger.info("using URL from environment: %s", env_url)
            url = env_url
        if url is None or len(url) == 0:
            message = "no URL provided"
            raise InitializationError(message)

        # prepare the URL
        try:
            url_parts = urlsplit(url, "https")
        except LocationParseError:
            message = "invalid URL / hostname"
            raise InitializationError(message)

        # https://docs.python.org/3/library/urllib.parse.html
        # Following the syntax specifications in RFC 1808, urlparse recognizes
        # a netloc only if it is properly introduced by ‘//’. Otherwise the
        # input is presumed to be a relative URL and thus to start with
        # a path component.
        if len(url_parts.netloc) == 0:
            url_parts = urlsplit("//" + url, "https")
        url_parts_list = list(url_parts)
        if not allow_http and url_parts.scheme == "http":
            url_parts_list[0] = "https"
        if url_parts_list[0] not in ("http", "https"):
            message = "invalid URL scheme (should be https)"
            raise InitializationError(message)
        new_url = urlunsplit(url_parts_list)
        base_url = urljoin(new_url, "api/v0/")

        # check environment for username
        env_user = os.environ.get("VIRL2_USER")
        if env_user:
            logger.info("using username from environment")
            username = env_user
        if username is None or len(username) == 0:
            message = "no username provided"
            raise InitializationError(message)
        self.username = username

        # check environment for password
        env_pass = os.environ.get("VIRL2_PASS")
        if env_pass:
            logger.info("using password from environment")
            password = env_pass
        if password is None or len(password) == 0:
            message = "no password provided"
            raise InitializationError(message)
        self.password = password

        self._context = Context(base_url)
        """
        Within the Client Library context:
        `requests.Session()` instance that can be used to send requests to the controller.
        `uuid.uuid4()` instance to uniquely identify this client library session.
        `base_url` stores the base URL."""

        # http://docs.python-requests.org/en/master/user/advanced/#ssl-cert-verification

        ENV_CA_BUNDLE = os.environ.get("CA_BUNDLE")
        if ssl_verify is True and ENV_CA_BUNDLE:
            self.session.verify = ENV_CA_BUNDLE
        else:
            self.session.verify = ssl_verify

        if ssl_verify is False:
            logger.warning("SSL Verification disabled")
            urllib3.disable_warnings()

        # checks version from system_info against self.VERSION
        self.check_controller_version()

        self.session.auth = TokenAuth(self)
        """
        `auto_sync` automatically syncs data with the backend after a specific
        time. The default expiry time is 1.0s. This time can be configured by
        setting the `auto_sync_interval`."""

        self.auto_sync = True
        self.auto_sync_interval = 1.0  # seconds

        self.allow_http = allow_http
        self.definitions = NodeImageDefinitions(self._context)

        self.url = url
        self.raise_for_auth_failure = raise_for_auth_failure
        self._labs = {}

        self.licensing = Licensing(context=self._context)

        try:
            self._make_test_auth_call()
        except InitializationError as exc:
            if raise_for_auth_failure:
                raise
            else:
                logger.warning(exc)
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

    def _make_test_auth_call(self):
        # make a call to confirm auth works by using the "authok" endpoint
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

    @property
    def session(self):
        """
        Returns the used Requests session object

        :returns: The Requests session object
        :rtype: Requests.Session
        """
        return self._context.session

    @property
    def _base_url(self):
        """
        Returns the base URL to access the controller

        :returns: The base URL
        :rtype: str
        """
        return self._context.base_url

    def get_host(self):
        """
        Returns the hostname of the session to the controller.

        :returns: A hostname
        :rtype: str
        """
        split_url = urllib.parse.urlsplit(self._base_url)
        return split_url.hostname

    def system_info(self):
        """
        Get information about the system where the application runs.
        Can be called without authentication.

        :returns: system information json
        :rtype: dict
        """
        response = self.session.get(urljoin(self._base_url, "system_information"))
        response.raise_for_status()
        return response.json()

    def check_controller_version(self, controller_version=None):
        """
        Checks remote controller version against current client version
        (specified in self.VERSION) and against controller version
        blacklist (specified in self.INCOMPATIBLE_CONTROLLER_VERSIONST) and
        raises exception if version are incompatible or prints warning
        if version are not in exact match.

        :rtype: None
        """
        controller_version = (
            controller_version or self.system_info().get("version", "").split("-")[0]
        )

        # are we running against a test version?
        if controller_version == "testing":
            logger.warning("testing version detected!")
            return

        controller_version = Version(controller_version)
        if controller_version in self.INCOMPATIBLE_CONTROLLER_VERSIONS:
            raise InitializationError(
                "Controller version {} is marked incompatible! "
                "List of versions marked expclicitly as incompatible: {}".format(
                    controller_version, self.INCOMPATIBLE_CONTROLLER_VERSIONS
                )
            )
        if self.VERSION.major_differs(controller_version):
            raise InitializationError(
                "Major version mismatch. server {}, client {}".format(
                    controller_version, self.VERSION
                )
            )
        if self.VERSION.minor_or_patch_differs(controller_version):
            logger.warning(
                "Please ensure the client version is compatible with the server"
                " version. client %s, server %s",
                self.VERSION,
                controller_version,
            )

    def is_system_ready(self, wait=False, max_wait=60, sleep=5):
        """
        is_system_ready reports whether the system is ready or not.

        :param wait: if this is true, the call will block until it's ready
        :type wait: bool
        :param max_wait: wait for a maximum of 'max_wait' seconds
        :type wait: int
        :param sleep: wait for 'sleep' seconds between tries
        :type wait: int
        :returns: ready state
        :rtype: bool
        """
        loops = 1
        if wait:
            loops = int(max_wait / sleep)
        ready = False
        while not ready and loops > 0:
            result = self.system_info()
            ready = result.get("ready")
            if not ready and loops > 0:
                time.sleep(int(sleep))
        return ready

    def wait_for_lld_connected(self):
        """
        Waits until the controller has a compute node connected.
        (Deprecated)
        """
        raise Exception("this is deprecated, use is_system_ready(wait=True), if needed")

    def import_lab(self, topology, title, offline=False):
        """
        Imports an existing topology from a string.

        :param topology: Topology representation as a string
        :type topology: str
        :param title: Title of the lab
        :type title: str
        :param offline: whether the ClientLibrary should import the
            lab locally.  The topology parameter has to be a JSON string
            in this case.  This can not be XML or YAML representation of
            the lab.  Compatible JSON from `GET /labs/{lab_id}/topology`.
        :type offline: bool
        :returns: A Lab instance
        :rtype: models.Lab
        :raises ValueError: if there's no lab ID in the API response
        :raises requests.exceptions.HTTPError: if there was a transport error
        """
        # TODO: refactor to return the local lab, and sync it, if already exists in self._labs
        if offline:
            lab_id = "offline_lab"
        else:
            # TODO: reformat with params=params not string formatting
            if title.endswith(".virl"):
                url = "{}import/virl-1x?title={}".format(self._base_url, title)
            elif title.endswith(".ng"):
                url = "{}import?is_json=true&title={}".format(self._base_url, title)
            else:
                url = "{}import?title={}".format(self._base_url, title)
            response = self.session.post(url, data=topology)
            response.raise_for_status()
            result = response.json()
            lab_id = result.get("id")
            if lab_id is None:
                raise ValueError("no lab ID returned!")

        # remove the extension (.ng, .yaml) to name the lab
        lab_title = title.replace(Path(title).suffix, "")
        lab = Lab(
            lab_title,
            lab_id,
            self._context,
            self.username,
            self.password,
            auto_sync=self.auto_sync,
            auto_sync_interval=self.auto_sync_interval,
        )

        if offline:
            topology_json = json.loads(topology)
            lab.import_lab(topology_json)
        else:
            lab.sync()
        self._labs[lab_id] = lab
        return lab

    def import_lab_from_path(self, topology, title=None):
        """
        Imports an existing topology from a file / path.

        :param topology: Topology filename / path
        :type topology: str
        :param title: Title of the lab
        :type title: str
        :returns: A Lab instance
        :rtype: models.Lab
        """
        topology_path = Path(topology)
        if not topology_path.exists():
            message = "{} can not be found".format(topology)
            raise Exception(message)

        topology = topology_path.read_text()
        title = title or topology_path.name
        return self.import_lab(topology, title)

    def import_sample_lab(self, title):
        """
        Imports a built-in sample lab (this will be going away in the future).

        :param title: Sample lab name with extension
        :type title: str
        :returns: A Lab instance
        :rtype: models.Lab
        """
        warnings.warn("deprecated", DeprecationWarning)
        topology_file_path = Path("import_export") / "SampleData" / title
        topology = pkg_resources.resource_string(
            "simple_common", topology_file_path.as_posix()
        )
        return self.import_lab(topology=topology.decode(), title=title)

    def all_labs(self, show_all=False):
        """
        Retrieves a list of all defined labs.

        :param show_all: Whether to get only labs owned by the admin or all user labs
        :type show_all: bool
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

    def local_labs(self):
        # TODO: first sync with server to pull all possible labs
        return [lab for lab in self._labs.values()]

    def get_local_lab(self, lab_id):
        try:
            return self._labs[lab_id]
        except KeyError:
            raise LabNotFound(lab_id)

    def create_lab(self, title=None):
        """
        Creates an empty lab with the given name. If no name is given, then
        the created lab ID is set as the name.

        Note that the lab will be auto-syncing according to the Client Librarie's
        auto-sync setting when created. The lab has a property to override this
        on a per-lab basis.

        Example::

            lab = client_library.create_lab()
            print(lab.id)
            lab.create_node("r1", "iosv", 50, 100)

        :param title: The Lab name (or title)
        :type title: str
        :returns: A Lab instance
        :rtype: models.Lab
        """
        url = self._base_url + "labs"
        params = {"title": title}
        response = self.session.post(url, params=params)
        response.raise_for_status()
        result = response.json()
        lab_id = result["id"]
        lab = Lab(
            title or lab_id,
            lab_id,
            self._context,
            self.username,
            self.password,
            auto_sync=self.auto_sync,
            auto_sync_interval=self.auto_sync_interval,
        )
        self._labs[lab_id] = lab
        return lab

    def remove_lab(self, lab_id):
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

    def join_existing_lab(self, lab_id, sync_lab=True):
        """
        Creates a new ClientLibrary lab instance that is retrieved
        from the controller.

        If `sync_lab` is set to true, then synchronize current lab
        by applying the changes that were done in UI or in another
        ClientLibrary session.

        Join preexisting lab::

            lab = client_library.join_existing_lab("2e6a18")

        :param lab_id: The lab ID to be removed.
        :type lab_id: str
        :param sync_lab: Syncronize changes.
        :type sync_lab: bool
        :returns: A Lab instance
        :rtype: models.Lab
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

    def get_diagnostics(self):
        """Returns the controller diagnostic data as JSON

        :returns: diagnostic data
        :rtype: str
        """
        url = self._base_url + "diagnostics"
        response = self.session.get(url)
        response.raise_for_status()
        return response.json()

    def find_labs_by_title(self, title):
        """
        Return a list of labs which match the given title

        :param title: The title to search for
        :type title: str
        :returns: A list of lab objects which match the title specified
        :rtype: list[models.Lab]
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

    def get_lab_list(self, show_all=False):
        """Returns list of all lab IDs.

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
