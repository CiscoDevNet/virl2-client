#
# This file is part of VIRL 2
# Copyright (c) 2019-2024, Cisco Systems, Inc.
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

import json
import logging
import re
import sys
from pathlib import Path
from unittest.mock import Mock, call, patch

import httpx
import pytest
import respx

from virl2_client.models import Lab
from virl2_client.virl2_client import (
    ClientConfig,
    ClientLibrary,
    InitializationError,
    Version,
)

CURRENT_VERSION = ClientLibrary.VERSION.version_str

python37_or_newer = pytest.mark.skipif(
    sys.version_info < (3, 7), reason="requires Python3.7"
)


# TODO: split into multiple test modules, by feature.
@pytest.fixture
def reset_env(monkeypatch):
    env_vars = [
        "VIRL2_URL",
        "VIRL_HOST",
        "VIRL2_USER",
        "VIRL_USERNAME",
        "VIRL2_PASS",
        "VIRL_PASSWORD",
    ]

    for key in env_vars:
        monkeypatch.delenv(key, raising=False)


@python37_or_newer
def test_import_lab_from_path_virl(
    client_library_server_current, mocked_session, tmp_path: Path
):
    cl = ClientLibrary(
        url="https://0.0.0.0/fake_url/", username="test", password="pa$$"
    )
    Lab.sync = Mock()

    (tmp_path / "topology.virl").write_text("<?xml version='1.0' encoding='UTF-8'?>")
    with patch.object(Lab, "sync", autospec=True) as sync_mock:
        lab = cl.import_lab_from_path(path=(tmp_path / "topology.virl").as_posix())

    assert lab.title is not None
    assert lab._url_for("lab").startswith("labs/")

    cl._session.post.assert_called_once_with(
        "import/virl-1x",
        content="<?xml version='1.0' encoding='UTF-8'?>",
    )
    cl._session.post.assert_called_once()
    sync_mock.assert_called_once_with()


@python37_or_newer
def test_import_lab_from_path_virl_title(
    client_library_server_current, mocked_session, tmp_path: Path
):
    cl = ClientLibrary(
        url="https://0.0.0.0/fake_url/", username="test", password="pa$$"
    )
    Lab.sync = Mock()
    new_title = "new_title"
    (tmp_path / "topology.virl").write_text("<?xml version='1.0' encoding='UTF-8'?>")
    with patch.object(Lab, "sync", autospec=True):
        lab = cl.import_lab_from_path(
            path=(tmp_path / "topology.virl").as_posix(), title=new_title
        )
    assert lab.title is not None
    assert lab._url_for("lab").startswith("labs/")

    cl._session.post.assert_called_once_with(
        "import/virl-1x",
        params={"title": new_title},
        content="<?xml version='1.0' encoding='UTF-8'?>",
    )


def test_ssl_certificate(client_library_server_current, mocked_session):
    cl = ClientLibrary(
        url="https://0.0.0.0/fake_url/",
        username="test",
        password="pa$$",
        ssl_verify="/home/user/cert.pem",
    )
    cl.is_system_ready(wait=True)

    assert cl._ssl_verify == "/home/user/cert.pem"
    assert cl._session.mock_calls[:4] == [call.get("authok")]


def test_ssl_certificate_from_env_variable(
    client_library_server_current, monkeypatch, mocked_session
):
    monkeypatch.setenv("CA_BUNDLE", "/home/user/cert.pem")
    cl = ClientLibrary(
        url="https://0.0.0.0/fake_url/", username="test", password="pa$$"
    )

    assert cl.is_system_ready()
    assert cl._ssl_verify == "/home/user/cert.pem"
    assert cl._session.mock_calls[:4] == [call.get("authok")]


@python37_or_newer
@respx.mock
def test_auth_and_reauth_token(client_library_server_current):
    def initial_different_response(initial, subsequent=httpx.Response(200)):
        yield initial
        while True:
            yield subsequent

    # mock failed and successful authentication:
    respx.post(
        "https://0.0.0.0/fake_url/api/v0/authenticate"
    ).side_effect = initial_different_response(
        httpx.Response(403), httpx.Response(200, json="7bbcan78a98bch7nh3cm7hao3nc7")
    )
    respx.get(
        "https://0.0.0.0/fake_url/api/v0/authok"
    ).side_effect = initial_different_response(httpx.Response(401))

    # mock get labs
    respx.get("https://0.0.0.0/fake_url/api/v0/labs").respond(json=[])

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

    # for idx, item in enumerate(respx.calls):
    #     print(idx, item.request.url)
    #
    # this is what we expect:
    # 0 https://0.0.0.0/fake_url/api/v0/authenticate
    # 1 https://0.0.0.0/fake_url/api/v0/authenticate
    # 2 https://0.0.0.0/fake_url/api/v0/authok
    # 3 https://0.0.0.0/fake_url/api/v0/authenticate
    # 4 https://0.0.0.0/fake_url/api/v0/authok
    # 5 https://0.0.0.0/fake_url/api/v0/labs

    assert respx.calls[0].request.url == "https://0.0.0.0/fake_url/api/v0/authenticate"
    assert json.loads(respx.calls[0].request.content) == {
        "username": "test",
        "password": "pa$$",
    }
    assert respx.calls[1].request.url == "https://0.0.0.0/fake_url/api/v0/authenticate"
    assert respx.calls[2].request.url == "https://0.0.0.0/fake_url/api/v0/authok"
    assert respx.calls[3].request.url == "https://0.0.0.0/fake_url/api/v0/authenticate"
    assert respx.calls[4].request.url == "https://0.0.0.0/fake_url/api/v0/authok"
    assert respx.calls[5].request.url == "https://0.0.0.0/fake_url/api/v0/labs"
    assert respx.calls.call_count == 6


def test_client_library_init_allow_http(client_library_server_current):
    cl = ClientLibrary("http://somehost", "virl2", "virl2", allow_http=True)
    assert cl._session.base_url.scheme == "http"
    assert cl._session.base_url.host == "somehost"
    assert cl._session.base_url.port is None
    assert cl._session.base_url.path.endswith("/api/v0/")
    assert cl.username == "virl2"
    assert cl.password == "virl2"


def test_client_library_init_disallow_http(client_library_server_current):
    with pytest.raises(InitializationError, match="must be https"):
        ClientLibrary("http://somehost", "virl2", "virl2")
    with pytest.raises(InitializationError, match="must be https"):
        ClientLibrary("http://somehost", "virl2", "virl2", allow_http=False)


# the test fails if you have variables set in env
@pytest.mark.parametrize("via", ["environment", "parameter"])
@pytest.mark.parametrize("env_var", ["VIRL2_URL", "VIRL_HOST"])
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
def test_client_library_init_url(
    client_library_server_current, reset_env, monkeypatch, via, env_var, params
):
    monkeypatch.setattr("getpass.getpass", input)
    (fail, url) = params
    expected_parts = None if fail else httpx.URL(url)
    if via == "environment":
        env = url
        url = None
    else:
        env = "http://badhost" if url else None
    if env is None:
        monkeypatch.delenv(env_var, raising=False)
    else:
        monkeypatch.setenv(env_var, env)
    if fail:
        with pytest.raises((InitializationError, OSError)) as err:
            ClientLibrary(
                url=url,
                username="virl2",
                password="virl2",
                allow_http=True,
                raise_for_auth_failure=True,
            )
        if isinstance(err, OSError):
            pattern = "(reading from stdin)"
            assert re.match(pattern, str(err.value))
    else:
        cl = ClientLibrary(url, username="virl2", password="virl2", allow_http=True)
        url_parts = cl._session.base_url
        assert url_parts.scheme == (expected_parts.scheme or "https")
        assert url_parts.host == (expected_parts.host or expected_parts.path)
        assert url_parts.port == expected_parts.port
        assert url_parts.path == "/api/v0/"
        assert cl._session.base_url.path.endswith("/api/v0/")
        assert cl.username == "virl2"
        assert cl.password == "virl2"


# the test fails if you have variables set in env
@pytest.mark.parametrize("via", ["environment", "parameter"])
@pytest.mark.parametrize("env_var", ["VIRL2_USER", "VIRL_USERNAME"])
@pytest.mark.parametrize("params", [(False, "johndoe"), (True, ""), (True, None)])
def test_client_library_init_user(
    client_library_server_current, reset_env, monkeypatch, via, env_var, params
):
    monkeypatch.setattr("getpass.getpass", input)
    url = "validhostname"
    (fail, user) = params
    if via == "environment":
        # can't set a None value for an environment variable
        env = user or ""
        user = None
    else:
        env = "baduser" if user else None
    if env is None:
        monkeypatch.delenv(env_var, raising=False)
    else:
        monkeypatch.setenv(env_var, env)
    if fail:
        with pytest.raises((OSError, InitializationError)) as err:
            ClientLibrary(url=url, username=user, password="virl2")
        if isinstance(err, OSError):
            pattern = "(reading from stdin)"
            assert re.match(pattern, str(err.value))
    else:
        cl = ClientLibrary(url, username=user, password="virl2")
        assert cl.username == params[1]
        assert cl.password == "virl2"
        assert cl._session.base_url == "https://validhostname/api/v0/"


# the test fails if you have variables set in env
@pytest.mark.parametrize("via", ["environment", "parameter"])
@pytest.mark.parametrize("env_var", ["VIRL2_PASS", "VIRL_PASSWORD"])
@pytest.mark.parametrize("params", [(False, "validPa$$w!2"), (True, ""), (True, None)])
def test_client_library_init_password(
    client_library_server_current, reset_env, monkeypatch, via, env_var, params
):
    monkeypatch.setattr("getpass.getpass", input)
    url = "validhostname"
    (fail, password) = params
    if via == "environment":
        # can't set a None value for an environment variable
        env = password or ""
        password = None
    else:
        env = "badpass" if password else None
    if env is None:
        monkeypatch.delenv(env_var, raising=False)
    else:
        monkeypatch.setenv(env_var, env)
    if fail:
        with pytest.raises((OSError, InitializationError)) as err:
            ClientLibrary(url=url, username="virl2", password=password)
        if isinstance(err, OSError):
            pattern = "(reading from stdin)"
            assert re.match(pattern, str(err.value))
    else:
        cl = ClientLibrary(url, username="virl2", password=password)
        assert cl.username == "virl2"
        assert cl.password == params[1]
        assert cl._session.base_url == "https://validhostname/api/v0/"


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
def test_client_library_config(client_library_server_current, mocked_session, config):
    client_library = config.make_client()
    assert client_library._session.base_url.path.startswith(config.url)
    assert client_library.username == config.username
    assert client_library.password == config.password
    assert client_library.allow_http == config.allow_http
    assert client_library._ssl_verify == config.ssl_verify
    assert client_library.auto_sync == (config.auto_sync >= 0.0)
    assert client_library.auto_sync_interval == config.auto_sync
    assert client_library._session.mock_calls == [
        call.get("authok"),
        call.base_url.path.startswith(config.url),
        call.base_url.path.startswith().__bool__(),
    ]


def test_client_library_str_and_repr(client_library_server_current):
    client_library = ClientLibrary("somehost", "virl2", password="virl2")
    assert (
        repr(client_library)
        == "ClientLibrary('https://somehost', 'virl2', 'virl2', True, False, False)"
    )
    assert str(client_library) == "ClientLibrary URL: https://somehost/api/v0/"


def test_major_version_mismatch(client_library_server_1_0_0):
    with pytest.raises(InitializationError) as err:
        ClientLibrary("somehost", "virl2", password="virl2")
    assert (
        str(err.value)
        == f"Major version mismatch. Client {CURRENT_VERSION}, controller 1.0.0."
    )


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


def test_client_minor_version_gt_nowarn(client_library_server_current, caplog):
    with caplog.at_level(logging.WARNING):
        client_library = ClientLibrary("somehost", "virl2", password="virl2")
    assert client_library is not None
    assert (
        f"Please ensure the client version is compatible with the controller version. "
        f"Client {CURRENT_VERSION}, controller 2.0.0." not in caplog.text
    )


def test_client_minor_version_lt_warn(client_library_server_2_9_0, caplog):
    with caplog.at_level(logging.WARNING):
        client_library = ClientLibrary("somehost", "virl2", password="virl2")
    assert client_library is not None
    assert (
        f"Please ensure the client version is compatible with the controller version. "
        f"Client {CURRENT_VERSION}, controller 2.9.0." in caplog.text
    )


def test_client_minor_version_lt_warn_1(client_library_server_2_19_0, caplog):
    with caplog.at_level(logging.WARNING):
        client_library = ClientLibrary("somehost", "virl2", password="virl2")
    assert client_library is not None
    assert (
        f"Please ensure the client version is compatible with the controller version. "
        f"Client {CURRENT_VERSION}, controller 2.19.0." in caplog.text
    )


def test_exact_version_no_warn(client_library_server_current, caplog):
    with caplog.at_level(logging.WARNING):
        client_library = ClientLibrary("somehost", "virl2", password="virl2")
    assert client_library is not None
    assert (
        f"Please ensure the client version is compatible with the controller version. "
        f"Client {CURRENT_VERSION}, controller 2.0.0." not in caplog.text
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
    client_library_server_current, mocked_session, tmp_path: Path, test_dir
):
    client_library = ClientLibrary(
        url="https://0.0.0.0/fake_url/", username="test", password="pa$$"
    )
    topology_file_path = test_dir / "test_data/sample_topology.json"
    with open(topology_file_path) as fh:
        topology_file = fh.read()
        with pytest.deprecated_call():
            client_library.import_lab(topology_file, "topology-v0_0_4", offline=True)


def test_convergence_parametrization(client_library_server_current, mocked_session):
    max_iter = 2
    max_time = 1
    cl = ClientLibrary(
        url="https://0.0.0.0/fake_url/",
        username="test",
        password="pa$$",
        convergence_wait_max_iter=max_iter,
        convergence_wait_time=max_time,
    )
    # check that passing of value from client to lab is working
    lab = cl.create_lab()
    assert lab.wait_max_iterations == max_iter
    assert lab.wait_time == max_time
    with patch.object(Lab, "has_converged", return_value=False):
        with pytest.raises(RuntimeError) as err:
            lab.wait_until_lab_converged()
        assert (
            "has not converged, maximum tries %s exceeded" % max_iter
        ) in err.value.args[0]

        # try to override values on function
        with pytest.raises(RuntimeError) as err:
            lab.wait_until_lab_converged(max_iterations=1)
        assert ("has not converged, maximum tries %s exceeded" % 1) in err.value.args[0]
