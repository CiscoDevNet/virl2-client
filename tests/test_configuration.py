#
# This file is part of VIRL 2
# Copyright (c) 2019-2026, Cisco Systems, Inc.
# All rights reserved.
#
import os
from collections.abc import Iterator
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from virl2_client import ClientLibrary
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


def test_get_configuration_emits_deprecation_warning():
    with pytest.raises(OSError, match="reading from stdin"):
        with pytest.warns(DeprecationWarning):
            ClientConfig.get_configuration(
                url=None, username=None, password=None, jwtoken=None, ssl_verify=None
            )
