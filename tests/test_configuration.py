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
"""Tests for ClientLibrary configuration, SSL options, and credential loading."""

import warnings
from collections.abc import Iterator
from pathlib import Path
from unittest.mock import MagicMock, call

import pytest

from virl2_client import ClientLibrary
from virl2_client.exceptions import InitializationError
from virl2_client.virl2_client import ClientConfig

FAKE_URL = "https://0.0.0.0/fake_url/"

_TEST_ENV = {
    "VIRL2_URL": "0.0.0.0",
    "VIRL_HOST": "0.0.0.0",
    "VIRL2_USER": "test_admin",
    "VIRL_USERNAME": "test_admin",
    "VIRL2_PASS": "test_test123",
    "VIRL_PASSWORD": "test_test123",
    "VIRL2_JWT": "test_jwt_token",
    "CA_BUNDLE": "/path/to/ca-bundle.pem",
    "CML_VERIFY_CERT": "1",
}


@pytest.fixture
def cwd_virlrc(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[Path]:
    """Create a .virlrc in tmp_path and chdir there for the test.

    Uses monkeypatch.chdir so the working directory is restored automatically
    even if the test fails.

    :param tmp_path: Pytest tmp_path fixture providing a temporary directory.
    :param monkeypatch: Pytest monkeypatch fixture for safe state mutation.
    :yields: Path to the created .virlrc file.
    """
    path = tmp_path / ClientConfig._CONFIG_FILE_NAME
    with path.open("w") as f:
        for name, value in _TEST_ENV.items():
            f.write(f"{name}={value}\n")

    monkeypatch.chdir(path.parent)
    yield path


@pytest.fixture
def home_virlrc(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[Path]:
    """Create a .virlrc in tmp_path and set HOME to that directory.

    Uses monkeypatch.setenv so the environment variable is restored
    automatically even if the test fails.

    :param tmp_path: Pytest tmp_path fixture providing a temporary directory.
    :param monkeypatch: Pytest monkeypatch fixture for safe state mutation.
    :yields: Path to the created .virlrc file.
    """
    path = tmp_path / ClientConfig._CONFIG_FILE_NAME
    with path.open("w") as f:
        for name, value in _TEST_ENV.items():
            f.write(f"{name}={value}\n")

    monkeypatch.setenv("HOME", str(path.parent))
    yield path


def test_local_virlrc(
    client_library_server_current: MagicMock, cwd_virlrc: Path
) -> None:
    """ClientLibrary loads credentials from .virlrc in current working directory.

    :param client_library_server_current: Patched system_info fixture.
    :param cwd_virlrc: Fixture providing .virlrc in cwd.
    """
    _ = client_library_server_current, cwd_virlrc
    cl = ClientLibrary(ssl_verify=False)
    assert cl.is_system_ready()
    assert cl.url == f"https://{_TEST_ENV['VIRL2_URL']}"
    assert cl.username == _TEST_ENV["VIRL2_USER"]
    assert cl.password == _TEST_ENV["VIRL2_PASS"]
    assert cl.jwtoken == _TEST_ENV["VIRL2_JWT"]


def test_export_credentials(
    client_library_server_current: MagicMock, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Load credentials from VIRL2_* environment variables.

    :param client_library_server_current: Patched system-info fixture.
    :param monkeypatch: Fixture for temporary environment mutation.
    """
    _ = client_library_server_current
    for name, value in _TEST_ENV.items():
        monkeypatch.setenv(name, value)

    cl = ClientLibrary(ssl_verify=False)
    assert cl.is_system_ready()
    assert cl.url == f"https://{_TEST_ENV['VIRL2_URL']}"
    assert cl.username == _TEST_ENV["VIRL2_USER"]
    assert cl.password == _TEST_ENV["VIRL2_PASS"]
    assert cl.jwtoken == _TEST_ENV["VIRL2_JWT"]


def test_home_directory_virlrc(
    client_library_server_current: MagicMock, home_virlrc: Path
) -> None:
    """Load credentials from ~/.virlrc when present.

    :param client_library_server_current: Patched system-info fixture.
    :param home_virlrc: Temporary user-home .virlrc fixture path.
    """
    _ = client_library_server_current, home_virlrc
    cl = ClientLibrary(ssl_verify=False)
    assert cl.is_system_ready()
    assert cl.url == f"https://{_TEST_ENV['VIRL2_URL']}"
    assert cl.username == _TEST_ENV["VIRL2_USER"]
    assert cl.password == _TEST_ENV["VIRL2_PASS"]
    assert cl.jwtoken == _TEST_ENV["VIRL2_JWT"]


def test_read_from_stdin(client_library_server_current: MagicMock) -> None:
    """ClientLibrary raises OSError when reading from stdin in non-TTY context.

    :param client_library_server_current: Patched system_info fixture.
    """
    _ = client_library_server_current
    with pytest.raises(OSError, match="reading from stdin"):
        _ = ClientLibrary(ssl_verify=False)


def test_config_jwt_from_env(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Use VIRL2_JWT from environment when provided.

    :param monkeypatch: Fixture for temporary environment mutation.
    """
    monkeypatch.setenv("VIRL2_URL", _TEST_ENV["VIRL2_URL"])
    monkeypatch.setenv("VIRL2_JWT", _TEST_ENV["VIRL2_JWT"])

    config = ClientConfig.get_configuration(
        url=None, username=None, password=None, jwtoken=None, ssl_verify=None
    )

    assert config.url == _TEST_ENV["VIRL2_URL"]
    assert config.jwtoken == _TEST_ENV["VIRL2_JWT"]
    assert config.username is None
    assert config.password is None


def test_config_ca_bundle_ssl_verify(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """ClientConfig uses CA_BUNDLE for ssl_verify when set in environment.

    NOTE: LLM-generated test -- verify for correctness.

    :param monkeypatch: Pytest monkeypatch fixture.
    """
    monkeypatch.setenv("VIRL2_URL", _TEST_ENV["VIRL2_URL"])
    monkeypatch.setenv("VIRL2_USER", _TEST_ENV["VIRL2_USER"])
    monkeypatch.setenv("VIRL2_PASS", _TEST_ENV["VIRL2_PASS"])
    monkeypatch.setenv("CA_BUNDLE", _TEST_ENV["CA_BUNDLE"])

    config = ClientConfig.get_configuration(
        url=None, username=None, password=None, jwtoken=None, ssl_verify=None
    )

    assert config.ssl_verify == _TEST_ENV["CA_BUNDLE"]


def test_config_cml_verify_cert_ssl_verify(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Use CML_VERIFY_CERT env var for ssl_verify when present.

    NOTE: LLM-generated test -- verify for correctness.

    :param monkeypatch: Fixture for temporary environment mutation.
    """
    monkeypatch.setenv("VIRL2_URL", _TEST_ENV["VIRL2_URL"])
    monkeypatch.setenv("VIRL2_USER", _TEST_ENV["VIRL2_USER"])
    monkeypatch.setenv("VIRL2_PASS", _TEST_ENV["VIRL2_PASS"])
    monkeypatch.setenv("CML_VERIFY_CERT", _TEST_ENV["CML_VERIFY_CERT"])

    config = ClientConfig.get_configuration(
        url=None, username=None, password=None, jwtoken=None, ssl_verify=None
    )

    assert config.ssl_verify == _TEST_ENV["CML_VERIFY_CERT"]


@pytest.mark.parametrize(
    "config",
    [
        ClientConfig(
            url="http://somehost", username="virl2", password="pa$$", allow_http=True
        ),
        ClientConfig(
            url="https://somehost:443",
            username="virl4",
            password="somepass",
            ssl_verify=False,
        ),
        ClientConfig(
            url="https://somehost",
            username="virl4",
            password="somepass",
            ssl_verify="/path.pem",
        ),
        ClientConfig(
            url="https://somehost", username="virl4", password="somepass", auto_sync=-1
        ),
        ClientConfig(
            url="https://somehost", username="virl4", password="somepass", auto_sync=0.0
        ),
        ClientConfig(
            url="https://somehost", username="virl4", password="somepass", auto_sync=2.3
        ),
        ClientConfig(
            url="https://somehost", jwtoken="JWT_TOKEN", ssl_verify="/path.pem"
        ),
    ],
)
def test_client_library_config(
    client_library_server_current: MagicMock,
    mocked_session: MagicMock,
    config: ClientConfig,
) -> None:
    """ClientLibrary respects ClientConfig options when make_client() is called.

    :param client_library_server_current: Patched system_info fixture.
    :param mocked_session: Mocked HTTP session fixture.
    :param config: ClientConfig instance to test.
    """
    _ = client_library_server_current
    mock_client = mocked_session.return_value
    mock_client.get.return_value.json.return_value = {
        "admin": False,
        "username": config.username or "username",
        "id": "6c7dd461-1cbe-428f-bdd5-545a0d766ed7",
        "token": "BOGUS_TOKEN",
        "error": None,
    }
    client_library = config.make_client()
    assert client_library._session.base_url.path.startswith(config.url)
    if config.username is not None:
        assert client_library.username == config.username
    else:
        assert client_library.username == "username"
    assert client_library.password == config.password
    assert client_library.jwtoken == config.jwtoken
    assert client_library.allow_http == config.allow_http
    assert client_library._ssl_verify == config.ssl_verify
    assert client_library.auto_sync == (config.auto_sync >= 0.0)
    assert client_library.auto_sync_interval == config.auto_sync
    assert client_library._session.mock_calls == [
        call.get("authentication"),
        call.get().json(),
        call.base_url.path.startswith(config.url),
        call.base_url.path.startswith().__bool__(),
    ]


_DEPRECATION_CONFIG_KWARGS = [
    {
        "url": None,
        "username": "user",
        "password": "pass",
        "jwtoken": None,
        "ssl_verify": False,
    },
    {
        "url": "https://somehost",
        "username": None,
        "password": None,
        "jwtoken": None,
        "ssl_verify": False,
    },
    {
        "url": "https://somehost",
        "username": "user",
        "password": None,
        "jwtoken": None,
        "ssl_verify": False,
    },
]


def _setup_deprecation_mocks(
    monkeypatch: pytest.MonkeyPatch,
    config_kwargs: dict,
) -> dict[str, int]:
    """Setup stdin/input/getpass mocks for deprecation tests.

    :param monkeypatch: Pytest monkeypatch fixture.
    :param config_kwargs: Config dict for mock return values.
    :returns: Mutable call counter dict.
    """
    monkeypatch.setattr("sys.stdin.isatty", lambda: False)
    calls: dict[str, int] = {"input": 0, "getpass": 0}

    def _fake_input(prompt: str) -> str:
        calls["input"] += 1
        if "IP / hostname" in prompt:
            return config_kwargs.get("url") or ""
        return config_kwargs.get("username") or ""

    def _fake_getpass(_: str) -> str:
        calls["getpass"] += 1
        return config_kwargs.get("password") or ""

    monkeypatch.setattr("builtins.input", _fake_input)
    monkeypatch.setattr("getpass.getpass", _fake_getpass)
    return calls


@pytest.mark.parametrize("config_kwargs", _DEPRECATION_CONFIG_KWARGS)
@pytest.mark.parametrize("allow_inputs", [True, False, None])
def test_get_config_deprecation(
    monkeypatch: pytest.MonkeyPatch, config_kwargs: dict, allow_inputs: bool | None
) -> None:
    """get_configuration with allow_inputs emits deprecation when None.

    NOTE: LLM-generated test -- verify for correctness.

    :param monkeypatch: Pytest monkeypatch fixture.
    :param config_kwargs: Incomplete config dict that triggers InitializationError.
    :param allow_inputs: Whether to allow interactive credential prompts.
    """
    calls = _setup_deprecation_mocks(monkeypatch, config_kwargs)
    with warnings.catch_warnings(record=True) as caught:
        with pytest.raises(InitializationError):
            ClientConfig.get_configuration(**config_kwargs, allow_inputs=allow_inputs)
    got_deprecation = any(issubclass(w.category, DeprecationWarning) for w in caught)
    assert got_deprecation == (allow_inputs is None)
    if allow_inputs is False:
        assert calls["input"] == 0
        assert calls["getpass"] == 0
    else:
        assert calls["input"] + calls["getpass"] > 0


@pytest.mark.parametrize("config_kwargs", _DEPRECATION_CONFIG_KWARGS)
@pytest.mark.parametrize("allow_inputs", [True, False, None])
def test_make_client_deprecation(
    monkeypatch: pytest.MonkeyPatch, config_kwargs: dict, allow_inputs: bool | None
) -> None:
    """make_client with allow_inputs emits deprecation when None.

    NOTE: LLM-generated test -- verify for correctness.

    :param monkeypatch: Pytest monkeypatch fixture.
    :param config_kwargs: Incomplete config dict that triggers InitializationError.
    :param allow_inputs: Whether to allow interactive credential prompts.
    """
    calls = _setup_deprecation_mocks(monkeypatch, config_kwargs)
    orig_get_configuration = ClientConfig.get_configuration.__func__

    def patched_get_configuration(*args: object) -> ClientConfig:
        return orig_get_configuration(
            ClientConfig, **config_kwargs, allow_inputs=allow_inputs
        )

    monkeypatch.setattr(
        ClientConfig,
        "get_configuration",
        classmethod(patched_get_configuration),
    )
    config = ClientConfig(**config_kwargs)
    with warnings.catch_warnings(record=True) as caught:
        with pytest.raises(InitializationError):
            config.make_client()
    got_deprecation = any(issubclass(w.category, DeprecationWarning) for w in caught)
    assert got_deprecation == (allow_inputs is None)
    if allow_inputs is False:
        assert calls["input"] == 0
        assert calls["getpass"] == 0
    else:
        assert calls["input"] + calls["getpass"] > 0


def test_ssl_certificate(
    client_library_server_current: MagicMock, mocked_session: MagicMock
) -> None:
    """Use constructor-provided SSL CA bundle path for requests.

    :param client_library_server_current: Patched current-version fixture.
    :param mocked_session: Mocked HTTP session fixture.
    """
    _ = client_library_server_current, mocked_session
    cl = ClientLibrary(
        url=FAKE_URL,
        username="test",
        password="pa$$",
        ssl_verify="/home/user/cert.pem",
    )
    cl.is_system_ready(wait=True)

    assert cl._ssl_verify == "/home/user/cert.pem"
    assert cl._session.mock_calls[0] == call.get("authentication")


def test_ssl_certificate_from_env_variable(
    client_library_server_current: MagicMock,
    monkeypatch: pytest.MonkeyPatch,
    mocked_session: MagicMock,
) -> None:
    """Use CA_BUNDLE environment variable for SSL verification.

    :param client_library_server_current: Patched current-version fixture.
    :param monkeypatch: Fixture for temporary environment mutation.
    :param mocked_session: Mocked HTTP session fixture.
    """
    _ = client_library_server_current, mocked_session
    monkeypatch.setenv("CA_BUNDLE", "/home/user/cert.pem")
    cl = ClientLibrary(url=FAKE_URL, username="test", password="pa$$")

    assert cl.is_system_ready()
    assert cl._ssl_verify == "/home/user/cert.pem"
    assert cl._session.mock_calls[0] == call.get("authentication")


def test_config_get_from_file(tmp_path: Path) -> None:
    """ClientConfig._get_from_file reads property from .virlrc.

    NOTE: LLM-generated test -- verify for correctness.

    :param tmp_path: Temporary directory fixture.
    """
    config_file = tmp_path / ".virlrc"
    config_file.write_text('VIRL2_URL="https://from-file"\n')
    assert ClientConfig._get_from_file(tmp_path, "VIRL2_URL") == "https://from-file"


def test_config_get_prop(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """ClientConfig._get_prop walks directory tree to find .virlrc.

    NOTE: LLM-generated test -- verify for correctness.

    :param tmp_path: Temporary directory fixture.
    :param monkeypatch: Pytest monkeypatch fixture.
    """
    config_file = tmp_path / ".virlrc"
    config_file.write_text('VIRL2_URL="https://from-file"\n')
    nested = tmp_path / "a" / "b"
    nested.mkdir(parents=True)
    monkeypatch.chdir(nested)
    assert ClientConfig._get_prop("VIRL2_URL") == "https://from-file"


def test_config_populate_inputs(monkeypatch: pytest.MonkeyPatch) -> None:
    """ClientConfig._populate_from_inputs stores JWT from interactive input.

    NOTE: LLM-generated test -- verify for correctness.

    :param monkeypatch: Pytest monkeypatch fixture.
    """
    conf = {
        "url": None,
        "username": None,
        "password": None,
        "jwtoken": None,
        "ssl_verify": True,
    }
    monkeypatch.setattr(
        "builtins.input",
        MagicMock(side_effect=["https://server.local", "x" * 40]),
    )
    ClientConfig._populate_from_inputs(conf)
    assert conf["jwtoken"] == "x" * 40
