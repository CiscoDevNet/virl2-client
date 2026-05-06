#
# This file is part of VIRL 2
# Copyright (c) 2019-2026, Cisco Systems, Inc.
# All rights reserved.
#
import os
import warnings
from collections.abc import Iterator
from pathlib import Path
from unittest.mock import MagicMock, call

import pytest

from virl2_client import ClientLibrary
from virl2_client.exceptions import InitializationError
from virl2_client.virl2_client import ClientConfig

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
def cwd_virlrc(tmp_path: Path) -> Iterator[Path]:
    path = tmp_path / ClientConfig._CONFIG_FILE_NAME
    with path.open("w") as f:
        for name, value in _TEST_ENV.items():
            f.write(f"{name}={value}\n")

    os.chdir(path.parent)

    yield path

    os.remove(path)


@pytest.fixture
def home_virlrc(tmp_path: Path) -> Iterator[Path]:
    path = tmp_path / ClientConfig._CONFIG_FILE_NAME
    with path.open("w") as f:
        for name, value in _TEST_ENV.items():
            f.write(f"{name}={value}\n")

    HOME = "HOME"
    home = os.environ.get(HOME)
    os.environ[HOME] = str(path.parent)

    yield path

    os.environ[HOME] = home
    os.remove(path)


def test_local_virlrc(client_library_server_current: MagicMock, cwd_virlrc: Path):
    _ = client_library_server_current, cwd_virlrc
    cl = ClientLibrary(ssl_verify=False)
    assert cl.is_system_ready()
    assert cl.url == f"https://{_TEST_ENV['VIRL2_URL']}"
    assert cl.username == _TEST_ENV["VIRL2_USER"]
    assert cl.password == _TEST_ENV["VIRL2_PASS"]
    assert cl.jwtoken == _TEST_ENV["VIRL2_JWT"]


def test_export_credentials(
    client_library_server_current: MagicMock, monkeypatch: pytest.MonkeyPatch
):
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
):
    _ = client_library_server_current, home_virlrc
    cl = ClientLibrary(ssl_verify=False)
    assert cl.is_system_ready()
    assert cl.url == f"https://{_TEST_ENV['VIRL2_URL']}"
    assert cl.username == _TEST_ENV["VIRL2_USER"]
    assert cl.password == _TEST_ENV["VIRL2_PASS"]
    assert cl.jwtoken == _TEST_ENV["VIRL2_JWT"]


def test_read_from_stdin(client_library_server_current: MagicMock):
    _ = client_library_server_current
    with pytest.raises(OSError, match="reading from stdin"):
        _ = ClientLibrary(ssl_verify=False)


def test_get_configuration_uses_jwt_from_env(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("VIRL2_URL", _TEST_ENV["VIRL2_URL"])
    monkeypatch.setenv("VIRL2_JWT", _TEST_ENV["VIRL2_JWT"])

    config = ClientConfig.get_configuration(
        url=None, username=None, password=None, jwtoken=None, ssl_verify=None
    )

    assert config.url == _TEST_ENV["VIRL2_URL"]
    assert config.jwtoken == _TEST_ENV["VIRL2_JWT"]
    assert config.username is None
    assert config.password is None


def test_get_configuration_uses_ca_bundle_for_ssl_verify(
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setenv("VIRL2_URL", _TEST_ENV["VIRL2_URL"])
    monkeypatch.setenv("VIRL2_USER", _TEST_ENV["VIRL2_USER"])
    monkeypatch.setenv("VIRL2_PASS", _TEST_ENV["VIRL2_PASS"])
    monkeypatch.setenv("CA_BUNDLE", _TEST_ENV["CA_BUNDLE"])

    config = ClientConfig.get_configuration(
        url=None, username=None, password=None, jwtoken=None, ssl_verify=None
    )

    assert config.ssl_verify == _TEST_ENV["CA_BUNDLE"]


def test_get_configuration_uses_cml_verify_cert_for_ssl_verify(
    monkeypatch: pytest.MonkeyPatch,
):
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
):
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


@pytest.mark.parametrize(
    "config_kwargs",
    [
        # Missing URL
        {
            "url": None,
            "username": "user",
            "password": "pass",
            "jwtoken": None,
            "ssl_verify": False,
        },
        # Missing authentication (no username/password and no JWT)
        {
            "url": "https://somehost",
            "username": None,
            "password": None,
            "jwtoken": None,
            "ssl_verify": False,
        },
        # Username without password and no JWT
        {
            "url": "https://somehost",
            "username": "user",
            "password": None,
            "jwtoken": None,
            "ssl_verify": False,
        },
    ],
)
@pytest.mark.parametrize("allow_inputs", [True, False, None])
def test_deprecation_warning(
    monkeypatch: pytest.MonkeyPatch, config_kwargs: dict, allow_inputs: bool | None
):
    """Verify deprecation warning and interactive input behavior for allow_inputs.

    - When allow_inputs is None and stdin is not a TTY, a DeprecationWarning
      should be emitted and interactive prompts should be used.
    - When allow_inputs is False, no warning should be emitted and no
      interactive prompts should be used.
    - When allow_inputs is True, no warning should be emitted but interactive
      prompts should be used.
    """
    # Treat stdin as non-interactive to exercise the deprecation path when
    # allow_inputs is None.
    monkeypatch.setattr("sys.stdin.isatty", lambda: False)

    # Mock input() and getpass.getpass() so we don't actually read from stdin
    # under pytest, while still tracking whether they were called.
    calls: dict[str, int] = {"input": 0, "getpass": 0}

    def _fake_input(prompt: str) -> str:
        calls["input"] += 1
        if "IP / hostname" in prompt:
            return config_kwargs["url"] or ""
        return config_kwargs["username"] or ""

    def _fake_getpass(_: str) -> str:
        calls["getpass"] += 1
        return config_kwargs["password"] or ""

    monkeypatch.setattr("builtins.input", _fake_input)
    monkeypatch.setattr("getpass.getpass", _fake_getpass)

    # Capture warnings while invoking get_configuration with the given
    # allow_inputs setting. Some combinations still result in an
    # InitializationError; that's fine for this test.
    with warnings.catch_warnings(record=True) as caught:
        with pytest.raises(InitializationError):
            ClientConfig.get_configuration(**config_kwargs, allow_inputs=allow_inputs)

    got_deprecation = any(issubclass(w.category, DeprecationWarning) for w in caught)
    assert got_deprecation == (allow_inputs is None)

    # Interactive prompts should only be used when allow_inputs is not False.
    if allow_inputs is False:
        assert calls["input"] == 0
        assert calls["getpass"] == 0
    else:
        assert calls["input"] + calls["getpass"] > 0

    orig_get_configuration = ClientConfig.get_configuration.__func__

    def patched_get_configuration(*_):
        # Always forward the parametrized allow_inputs from this test,
        # regardless of what the caller passes (or omits).
        return orig_get_configuration(
            ClientConfig, **config_kwargs, allow_inputs=allow_inputs
        )

    monkeypatch.setattr(
        ClientConfig,
        "get_configuration",
        classmethod(patched_get_configuration),
    )

    calls = {"input": 0, "getpass": 0}

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
