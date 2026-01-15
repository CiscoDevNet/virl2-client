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
    assert all([cl.url, cl.username, cl.password])


def test_export_credentials(
    client_library_server_current: MagicMock, monkeypatch: pytest.MonkeyPatch
):
    _ = client_library_server_current
    for name, value in _TEST_ENV.items():
        monkeypatch.setenv(name, value)

    cl = ClientLibrary(ssl_verify=False)
    assert cl.is_system_ready()
    assert all([cl.url, cl.username, cl.password])


def test_home_directory_virlrc(
    client_library_server_current: MagicMock, home_virlrc: Path
):
    _ = client_library_server_current, home_virlrc
    cl = ClientLibrary(ssl_verify=False)
    assert cl.is_system_ready()
    assert all([cl.url, cl.username, cl.password])


def test_read_from_stdin(client_library_server_current: MagicMock):
    _ = client_library_server_current
    with pytest.raises(OSError, match="reading from stdin"):
        _ = ClientLibrary(ssl_verify=False)
