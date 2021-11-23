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

import json
import logging
import os
import sys

from pathlib import Path
from unittest.mock import Mock, call, patch
from urllib.parse import urlsplit

import pytest
import requests
import responses

from virl2_client.models import Lab
from virl2_client.virl2_client import (
    ClientConfig,
    ClientLibrary,
    Version,
    InitializationError,
)

CURRENT_VERSION = ClientLibrary.VERSION.version_str

python36_or_newer = pytest.mark.skipif(
    sys.version_info < (3, 6), reason="requires Python3.6"
)

# TODO: split into multiple test modules, by feature


@python36_or_newer
def test_import_lab_from_path_virl(
    client_library_server_2_0_0, mocked_session, tmp_path: Path
):
    cl = ClientLibrary(
        url="https://0.0.0.0/fake_url/", username="test", password="pa$$"
    )
    Lab.sync = Mock()

    (tmp_path / "topology.virl").write_text("<?xml version='1.0' encoding='UTF-8'?>")
    with patch.object(Lab, "sync", autospec=True) as sync_mock:
        lab = cl.import_lab_from_path(topology=(tmp_path / "topology.virl").as_posix())

    assert lab.title is not None
    assert lab.lab_base_url.startswith("https://0.0.0.0/fake_url/api/v0/labs/")

    cl.session.post.assert_called_once_with(
        "https://0.0.0.0/fake_url/api/v0/import/virl-1x?title=topology.virl",
        data="<?xml version='1.0' encoding='UTF-8'?>",
    )
    cl.session.post.assert_called_once()
    cl.session.post.return_value.raise_for_status.assert_called_once()
    sync_mock.assert_called_once_with()


def test_ssl_certificate(client_library_server_2_0_0, mocked_session):
    cl = ClientLibrary(
        url="https://0.0.0.0/fake_url/",
        username="test",
        password="pa$$",
        ssl_verify="/home/user/cert.pem",
    )
    cl.is_system_ready(wait=True)

    assert cl.session.verify == "/home/user/cert.pem"
    assert cl.session.mock_calls[:4] == [
        call.get("https://0.0.0.0/fake_url/api/v0/authok"),
        call.get().raise_for_status(),
    ]


def test_ssl_certificate_from_env_variable(
    client_library_server_2_0_0, monkeypatch, mocked_session
):
    monkeypatch.setitem(os.environ, "CA_BUNDLE", "/home/user/cert.pem")
    cl = ClientLibrary(
        url="https://0.0.0.0/fake_url/", username="test", password="pa$$"
    )

    assert cl.is_system_ready()
    assert cl.session.verify == "/home/user/cert.pem"
    assert cl.session.mock_calls[:4] == [
        call.get("https://0.0.0.0/fake_url/api/v0/authok"),
        call.get().raise_for_status(),
    ]


@python36_or_newer
@responses.activate
def test_auth_and_reauth_token(client_library_server_2_0_0):
    # mock failed authentication:
    responses.add(
        responses.POST, "https://0.0.0.0/fake_url/api/v0/authenticate", status=403
    )
    responses.add(responses.GET, "https://0.0.0.0/fake_url/api/v0/authok", status=401)

    # mock successful authentication:
    responses.add(
        responses.POST,
        "https://0.0.0.0/fake_url/api/v0/authenticate",
        json="7bbcan78a98bch7nh3cm7hao3nc7",
    )
    responses.add(responses.GET, "https://0.0.0.0/fake_url/api/v0/authok")

    # mock get labs
    responses.add(responses.GET, "https://0.0.0.0/fake_url/api/v0/labs", json=[])

    with pytest.raises(InitializationError):
        # Test returns custom exception when instructed to raise on failure
        ClientLibrary(
            url="https://0.0.0.0/fake_url/",
            username="test",
            password="pa$$",
            raise_for_auth_failure=True,
        )

    cl = ClientLibrary(
        url="https://0.0.0.0/fake_url/", username="test", password="pa$$"
    )

    cl.all_labs()

    # for idx, item in enumerate(responses.calls):
    #     print(idx, item.request.url)
    #
    # this is what we expect:
    # 0 https://0.0.0.0/fake_url/api/v0/authenticate
    # 1 https://0.0.0.0/fake_url/api/v0/authenticate
    # 2 https://0.0.0.0/fake_url/api/v0/authok
    # 3 https://0.0.0.0/fake_url/api/v0/authenticate
    # 4 https://0.0.0.0/fake_url/api/v0/authok
    # 5 https://0.0.0.0/fake_url/api/v0/labs

    assert (
        responses.calls[0].request.url == "https://0.0.0.0/fake_url/api/v0/authenticate"
    )
    assert json.loads(responses.calls[0].request.body) == {
        "username": "test",
        "password": "pa$$",
    }
    assert (
        responses.calls[1].request.url == "https://0.0.0.0/fake_url/api/v0/authenticate"
    )
    assert responses.calls[2].request.url == "https://0.0.0.0/fake_url/api/v0/authok"
    assert (
        responses.calls[3].request.url == "https://0.0.0.0/fake_url/api/v0/authenticate"
    )
    assert responses.calls[4].request.url == "https://0.0.0.0/fake_url/api/v0/authok"
    assert responses.calls[5].request.url == "https://0.0.0.0/fake_url/api/v0/labs"
    assert len(responses.calls) == 6


def test_client_library_init_allow_http(client_library_server_2_0_0):
    cl = ClientLibrary("http://somehost", "virl2", "virl2", allow_http=True)
    url_parts = urlsplit(cl._context.base_url)
    assert url_parts.scheme == "http"
    assert url_parts.hostname == "somehost"
    assert url_parts.port is None
    assert cl._context.base_url.endswith("/api/v0/")
    assert cl.username == "virl2"
    assert cl.password == "virl2"


def test_client_library_init_disallow_http(client_library_server_2_0_0):
    with pytest.raises(InitializationError, match="must be https"):
        cl = ClientLibrary("http://somehost", "virl2", "virl2")
    with pytest.raises(InitializationError, match="must be https"):
        cl = ClientLibrary("http://somehost", "virl2", "virl2", allow_http=False)


@pytest.mark.parametrize("via", ["environment", "parameter"])
@pytest.mark.parametrize(
    "params",
    [
        (False, "somehost"),
        (False, "http://somehost"),
        (False, "https://somehost:443"),
        (True, "xyz://somehost:443"),
        (True, "https:@somehost:4:4:3"),
        (True, ""),
        (True, None),
    ],
)
def test_client_library_init_url(client_library_server_2_0_0, monkeypatch, via, params):
    (fail, url) = params
    expected_parts = None if fail else urlsplit(url)
    if via == "environment":
        env = url
        url = None
    else:
        env = "http://badhost" if url else None
    if env is None:
        monkeypatch.delenv("VIRL2_URL", raising=False)
    else:
        monkeypatch.setenv("VIRL2_URL", env)
    if fail:
        with pytest.raises((InitializationError, requests.exceptions.InvalidURL)):
            ClientLibrary(url=url, username="virl2", password="virl2", allow_http=True)
    else:
        cl = ClientLibrary(url, username="virl2", password="virl2", allow_http=True)
        url_parts = urlsplit(cl._context.base_url)
        assert url_parts.scheme == (expected_parts.scheme or "https")
        assert url_parts.hostname == (expected_parts.hostname or expected_parts.path)
        assert url_parts.port == expected_parts.port
        assert url_parts.path == "/api/v0/"
        assert cl._context.base_url.endswith("/api/v0/")
        assert cl.username == "virl2"
        assert cl.password == "virl2"


@pytest.mark.parametrize("via", ["environment", "parameter"])
@pytest.mark.parametrize("params", [(False, "johndoe"), (True, ""), (True, None)])
def test_client_library_init_user(
    client_library_server_2_0_0, monkeypatch, via, params
):
    url = "validhostname"
    (fail, user) = params
    if via == "environment":
        # can't set a None value for an environment variable
        env = user or ""
        user = None
    else:
        env = "baduser" if user else None
    if env is None:
        monkeypatch.delenv("VIRL2_USER", raising=False)
    else:
        monkeypatch.setenv("VIRL2_USER", env)
    if fail:
        with pytest.raises((InitializationError, requests.exceptions.InvalidURL)):
            ClientLibrary(url=url, username=user, password="virl2")
    else:
        cl = ClientLibrary(url, username=user, password="virl2")
        assert cl.username == params[1]
        assert cl.password == "virl2"
        assert cl._context.base_url == "https://validhostname/api/v0/"


@pytest.mark.parametrize("via", ["environment", "parameter"])
@pytest.mark.parametrize("params", [(False, "validPa$$w!2"), (True, ""), (True, None)])
def test_client_library_init_password(
    client_library_server_2_0_0, monkeypatch, via, params
):
    url = "validhostname"
    (fail, password) = params
    if via == "environment":
        # can't set a None value for an environment variable
        env = password or ""
        password = None
    else:
        env = "badpass" if password else None
    if env is None:
        monkeypatch.delenv("VIRL2_PASS", raising=False)
    else:
        monkeypatch.setenv("VIRL2_PASS", env)
    if fail:
        with pytest.raises((InitializationError, requests.exceptions.InvalidURL)):
            ClientLibrary(url=url, username="virl2", password=password)
    else:
        cl = ClientLibrary(url, username="virl2", password=password)
        assert cl.username == "virl2"
        assert cl.password == params[1]
        assert cl._context.base_url == "https://validhostname/api/v0/"


@pytest.mark.parametrize(
    "config",
    [
        ClientConfig("http://somehost", "virl2", "pa$$", allow_http=True),
        ClientConfig("https://somehost:443", "virl4", "somepass", ssl_verify=False),
        ClientConfig("https://somehost", "virl4", "somepass", ssl_verify="/path.pem"),
        ClientConfig("https://somehost", "virl4", "somepass", auto_sync=-1),
        ClientConfig("https://somehost", "virl4", "somepass", auto_sync=0.0),
        ClientConfig("https://somehost", "virl4", "somepass", auto_sync=2.3),
    ],
)
def test_client_library_config(client_library_server_2_0_0, mocked_session, config):
    client_library = config.make_client()
    assert client_library._base_url.startswith(config.url)
    assert client_library.username == config.username
    assert client_library.password == config.password
    assert client_library.allow_http == config.allow_http
    assert client_library.session.verify == config.ssl_verify
    assert client_library.auto_sync == (config.auto_sync >= 0.0)
    assert client_library.auto_sync_interval == config.auto_sync
    assert client_library.session.mock_calls[:4] == [
        call.get(client_library._base_url + "authok"),
        call.get().raise_for_status(),
    ]


def test_client_library_str_and_repr(client_library_server_2_0_0):
    client_library = ClientLibrary("somehost", "virl2", password="virl2")
    assert (
        repr(client_library)
        == "ClientLibrary('https://somehost', 'virl2', 'virl2', True, False, False)"
    )
    assert str(client_library) == "ClientLibrary URL: https://somehost/api/v0/"


def test_major_version_mismatch(client_library_server_1_0_0):
    with pytest.raises(InitializationError) as err:
        ClientLibrary("somehost", "virl2", password="virl2")
    assert str(
        err.value
    ) == "Major version mismatch. Client {}, controller 1.0.0.".format(CURRENT_VERSION)


def test_incompatible_version(client_library_server_2_0_0):
    with pytest.raises(InitializationError) as err:
        with patch.object(
            ClientLibrary, "INCOMPATIBLE_CONTROLLER_VERSIONS", new=[Version("2.0.0")]
        ):
            ClientLibrary("somehost", "virl2", password="virl2")
    assert (
        str(err.value) == "Controller version 2.0.0 is marked incompatible! "
        "List of versions marked explicitly as incompatible: [2.0.0]."
    )


def test_client_minor_version_gt_nowarn(client_library_server_2_0_0, caplog):
    with caplog.at_level(logging.WARNING):
        client_library = ClientLibrary("somehost", "virl2", password="virl2")
    assert client_library is not None
    assert (
        "Please ensure the client version is compatible with the controller version. "
        "Client {}, controller 2.0.0.".format(CURRENT_VERSION) not in caplog.text
    )


def test_client_minor_version_lt_warn(client_library_server_2_9_0, caplog):
    with caplog.at_level(logging.WARNING):
        client_library = ClientLibrary("somehost", "virl2", password="virl2")
    assert client_library is not None
    assert (
        "Please ensure the client version is compatible with the controller version. "
        "Client {}, controller 2.9.0.".format(CURRENT_VERSION) in caplog.text
    )


def test_client_minor_version_lt_warn_1(client_library_server_2_19_0, caplog):
    with caplog.at_level(logging.WARNING):
        client_library = ClientLibrary("somehost", "virl2", password="virl2")
    assert client_library is not None
    assert (
        "Please ensure the client version is compatible with the controller version. "
        "Client {}, controller 2.19.0.".format(CURRENT_VERSION) in caplog.text
    )


def test_exact_version_no_warn(client_library_server_current, caplog):
    with caplog.at_level(logging.WARNING):
        client_library = ClientLibrary("somehost", "virl2", password="virl2")
    assert client_library is not None
    assert (
        "Please ensure the client version is compatible with the controller version. "
        "Client {}, controller 2.0.0.".format(CURRENT_VERSION) not in caplog.text
    )


@pytest.mark.parametrize(
    "greater, lesser, expected",
    [
        pytest.param(
            Version("2.0.1"), Version("2.0.0"), True, id="Patch is greater than"
        ),
        pytest.param(
            Version("2.0.10"), Version("2.0.0"), True, id="Patch is much greater than"
        ),
        pytest.param(
            Version("2.1.0"), Version("2.0.0"), True, id="Minor is greater than"
        ),
        pytest.param(
            Version("2.10.0"), Version("2.0.0"), True, id="Minor is much greater than"
        ),
        pytest.param(
            Version("3.0.0"), Version("2.0.0"), True, id="Major is greater than"
        ),
        pytest.param(
            Version("10.0.0"), Version("2.0.0"), True, id="Major is much greater than"
        ),
        pytest.param(
            Version("2.0.0"), Version("2.0.1"), False, id="Patch is lesser than"
        ),
        pytest.param(
            Version("2.0.0"), Version("2.0.10"), False, id="Patch is much lesser than"
        ),
        pytest.param(
            Version("2.0.0"), Version("2.1.0"), False, id="Minor is lesser than"
        ),
        pytest.param(
            Version("2.0.0"), Version("2.10.0"), False, id="Minor is much lesser than"
        ),
        pytest.param(
            Version("2.0.0"), Version("3.0.0"), False, id="Major is lesser than"
        ),
        pytest.param(
            Version("2.0.0"), Version("10.0.0"), False, id="Major is much lesser than"
        ),
        pytest.param(
            Version("2.0.0"),
            "random string",
            False,
            id="Other object is string and not a Version object",
        ),
        pytest.param(
            Version("2.0.0"),
            12345,
            False,
            id="Other object is int and not a Version object",
        ),
    ],
)
def test_version_comparison_greater_than(greater, lesser, expected):
    assert (greater > lesser) == expected


@pytest.mark.parametrize(
    "first, second, expected",
    [
        pytest.param(
            Version("2.0.1"), Version("2.0.0"), True, id="Patch is greater than"
        ),
        pytest.param(
            Version("2.0.10"), Version("2.0.0"), True, id="Patch is much greater than"
        ),
        pytest.param(
            Version("2.1.0"), Version("2.0.0"), True, id="Minor is greater than"
        ),
        pytest.param(
            Version("2.10.0"), Version("2.0.0"), True, id="Minor is much greater than"
        ),
        pytest.param(
            Version("3.0.0"), Version("2.0.0"), True, id="Major is greater than"
        ),
        pytest.param(
            Version("10.0.0"), Version("2.0.0"), True, id="Major is much greater than"
        ),
        pytest.param(
            Version("2.0.0"), Version("2.0.1"), False, id="Patch is lesser than"
        ),
        pytest.param(
            Version("2.0.0"), Version("2.0.10"), False, id="Patch is much lesser than"
        ),
        pytest.param(
            Version("2.0.0"), Version("2.1.0"), False, id="Minor is lesser than"
        ),
        pytest.param(
            Version("2.0.0"), Version("2.10.0"), False, id="Minor is much lesser than"
        ),
        pytest.param(
            Version("2.0.0"), Version("3.0.0"), False, id="Major is lesser than"
        ),
        pytest.param(
            Version("2.0.0"), Version("10.0.0"), False, id="Major is much lesser than"
        ),
        pytest.param(
            Version("2.0.0"),
            Version("2.0.0"),
            True,
            id="Equal versions no minor no patch",
        ),
        pytest.param(
            Version("2.0.1"),
            Version("2.0.1"),
            True,
            id="Equal versions patch increment",
        ),
        pytest.param(
            Version("2.1.0"),
            Version("2.1.0"),
            True,
            id="Equal versions minor increment",
        ),
        pytest.param(
            Version("3.0.0"),
            Version("3.0.0"),
            True,
            id="Equal versions major increment",
        ),
        pytest.param(
            Version("2.0.0"),
            "random string",
            False,
            id="Other object is string and not a Version object",
        ),
        pytest.param(
            Version("2.0.0"),
            12345,
            False,
            id="Other object is int and not a Version object",
        ),
    ],
)
def test_version_comparison_greater_than_or_equal_to(first, second, expected):
    assert (first >= second) == expected


@pytest.mark.parametrize(
    "lesser, greater, expected",
    [
        pytest.param(Version("2.0.0"), Version("2.0.1"), True, id="Patch is less than"),
        pytest.param(
            Version("2.0.0"), Version("2.0.10"), True, id="Patch is much less than"
        ),
        pytest.param(Version("2.0.0"), Version("2.1.0"), True, id="Minor is less than"),
        pytest.param(
            Version("2.0.0"), Version("2.10.0"), True, id="Minor is much less than"
        ),
        pytest.param(Version("2.0.0"), Version("3.0.0"), True, id="Major is less than"),
        pytest.param(
            Version("2.0.0"), Version("10.0.0"), True, id="Major is much less than"
        ),
        pytest.param(
            Version("2.0.1"), Version("2.0.0"), False, id="Patch is greater than"
        ),
        pytest.param(
            Version("2.0.10"), Version("2.0.0"), False, id="Patch is much greater than"
        ),
        pytest.param(
            Version("2.1.0"), Version("2.0.0"), False, id="Minor is greater than"
        ),
        pytest.param(
            Version("2.10.0"), Version("2.0.0"), False, id="Minor is much greater than"
        ),
        pytest.param(
            Version("3.0.0"), Version("2.0.0"), False, id="Major is greater than"
        ),
        pytest.param(
            Version("10.0.0"), Version("2.0.0"), False, id="Major is much greater than"
        ),
        pytest.param(
            Version("2.0.0"),
            "random string",
            False,
            id="Other object is string and not a Version object",
        ),
        pytest.param(
            Version("2.0.0"),
            12345,
            False,
            id="Other object is int and not a Version object",
        ),
    ],
)
def test_version_comparison_less_than(lesser, greater, expected):
    assert (lesser < greater) == expected


@pytest.mark.parametrize(
    "first, second, expected",
    [
        pytest.param(Version("2.0.0"), Version("2.0.1"), True, id="Patch is less than"),
        pytest.param(
            Version("2.0.0"), Version("2.0.10"), True, id="Patch is much less than"
        ),
        pytest.param(Version("2.0.0"), Version("2.1.0"), True, id="Minor is less than"),
        pytest.param(
            Version("2.0.0"), Version("2.10.0"), True, id="Minor is much less than"
        ),
        pytest.param(Version("2.0.0"), Version("3.0.0"), True, id="Major is less than"),
        pytest.param(
            Version("2.0.0"), Version("10.0.0"), True, id="Major is much less than"
        ),
        pytest.param(
            Version("2.0.1"), Version("2.0.0"), False, id="Patch is greater than"
        ),
        pytest.param(
            Version("2.0.10"), Version("2.0.0"), False, id="Patch is much greater than"
        ),
        pytest.param(
            Version("2.1.0"), Version("2.0.0"), False, id="Minor is greater than"
        ),
        pytest.param(
            Version("2.10.0"), Version("2.0.0"), False, id="Minor is much greater than"
        ),
        pytest.param(
            Version("3.0.0"), Version("2.0.0"), False, id="Major is greater than"
        ),
        pytest.param(
            Version("10.0.0"), Version("2.0.0"), False, id="Major is much greater than"
        ),
        pytest.param(
            Version("2.0.0"),
            Version("2.0.0"),
            True,
            id="Equal versions no minor no patch",
        ),
        pytest.param(
            Version("2.0.1"),
            Version("2.0.1"),
            True,
            id="Equal versions patch increment",
        ),
        pytest.param(
            Version("2.1.0"),
            Version("2.1.0"),
            True,
            id="Equal versions minor increment",
        ),
        pytest.param(
            Version("3.0.0"),
            Version("3.0.0"),
            True,
            id="Equal versions major increment",
        ),
        pytest.param(
            Version("2.0.0"),
            "random string",
            False,
            id="Other object is string and not a Version object",
        ),
        pytest.param(
            Version("2.0.0"),
            12345,
            False,
            id="Other object is int and not a Version object",
        ),
    ],
)
def test_version_comparison_less_than_or_equal_to(first, second, expected):
    assert (first <= second) == expected


def test_different_version_strings():
    v = Version("2.1.0-dev0+build8.7ee86bf8")
    assert v.major == 2 and v.minor == 1 and v.patch == 0
    v = Version("2.1.0dev0+build8.7ee86bf8")
    assert v.major == 2 and v.minor == 1 and v.patch == 0
    v = Version("2.1.0--dev0+build8.7ee86bf8")
    assert v.major == 2 and v.minor == 1 and v.patch == 0
    v = Version("2.1.0_dev0+build8.7ee86bf8")
    assert v.major == 2 and v.minor == 1 and v.patch == 0
    v = Version("2.1.0")
    assert v.major == 2 and v.minor == 1 and v.patch == 0
    v = Version("2.1.0-")
    assert v.major == 2 and v.minor == 1 and v.patch == 0

    with pytest.raises(ValueError):
        Version("2.1-dev0+build8.7ee86bf8")
    with pytest.raises(ValueError):
        Version("2-dev0+build8.7ee86bf8")
    with pytest.raises(ValueError):
        Version("54dev0+build8.7ee86bf8")


def test_import_lab_offline(
    change_test_dir, client_library_server_2_0_0, mocked_session, tmp_path: Path
):
    client_library = ClientLibrary(
        url="https://0.0.0.0/fake_url/", username="test", password="pa$$"
    )
    topology_file_path = "test_data/sample_topology.json"
    with open(topology_file_path) as fh:
        topology_file = fh.read()
        client_library.import_lab(topology_file, "topology-v0_0_4", offline=True)
