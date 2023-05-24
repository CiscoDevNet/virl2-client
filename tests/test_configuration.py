import os
from pathlib import Path

import pytest

from virl2_client import ClientLibrary
from virl2_client.models.configuration import _CONFIG_FILE_NAME


@pytest.fixture
def cwd_virlrc():
    return Path(_CONFIG_FILE_NAME)


@pytest.fixture
def home_virlrc():
    return Path.home() / _CONFIG_FILE_NAME


@pytest.fixture
def files_to_store(cwd_virlrc, home_virlrc):
    return [cwd_virlrc, home_virlrc]


@pytest.fixture(autouse=True)
def store_original_file(files_to_store):
    # store file if exists
    holder = {}
    for file_path in files_to_store:
        if file_path.is_file():
            with file_path.open("r") as f:
                holder[file_path] = f.read()
            file_path.unlink()

    yield holder

    # teardown
    for file_path in files_to_store:
        if file_path.is_file():
            file_path.unlink()

    # restore original home file
    for file_path, content in holder.items():
        with file_path.open("w") as f:
            f.write(content)


@pytest.fixture
def tested_credentials(files_to_store):
    configuration = {
        "VIRL2_URL": "0.0.0.0",
        "VIRL_HOST": "0.0.0.0",
        "VIRL2_USER": "test_admin",
        "VIRL_USERNAME": "test_admin",
        "VIRL2_PASS": "test_test123",
        "VIRL_PASSWORD": "test_test123",
    }
    virlrc_test = Path(".virlrc_test")
    if not virlrc_test.is_file():
        return configuration

    with virlrc_test.open("r") as f:
        for line in f.readlines():
            try:
                name, value = line.split("=", 1)
                if name in configuration:
                    configuration[name] = value
            except ValueError:
                continue

    return configuration


@pytest.fixture(autouse=True)
def store_original_exports(tested_credentials):
    store = {}

    # export test credentials
    for name in tested_credentials:
        if name in os.environ:
            store[name] = os.environ[name]
            del os.environ[name]

    yield store

    # teardown
    for name in tested_credentials:
        if name in os.environ:
            del os.environ[name]

    # restore exports
    for name in store:
        os.environ[name] = store[name]


def test_local_virlrc(
    tested_credentials, client_library_server_current, mocked_session, cwd_virlrc
):
    # load test data into file
    with cwd_virlrc.open("w") as f:
        for name, value in tested_credentials.items():
            f.write(f"{name}={value}\n")

    assert cwd_virlrc.is_file()
    cl = ClientLibrary(ssl_verify=False)

    assert cl.is_system_ready()
    assert all([cl.url, cl.username, cl.password])


def test_export_credentials(
    tested_credentials, client_library_server_current, mocked_session, cwd_virlrc
):
    for name, value in tested_credentials.items():
        assert os.environ.get(name, None) is None
        os.environ[name] = value
        assert os.environ.get(name, None) is not None

    assert not cwd_virlrc.is_file()
    cl = ClientLibrary(ssl_verify=False)

    assert cl.is_system_ready()
    assert all([cl.url, cl.username, cl.password])


def test_home_directory_virlrc(
    tested_credentials,
    client_library_server_current,
    mocked_session,
    home_virlrc,
    cwd_virlrc,
):
    assert not home_virlrc.is_file()

    with home_virlrc.open("w") as f:
        for name, value in tested_credentials.items():
            f.write(f"{name}={value}\n")

            assert os.environ.get(name, None) is None

    assert not cwd_virlrc.is_file()
    cl = ClientLibrary(ssl_verify=False)

    assert cl.is_system_ready()
    assert all([cl.url, cl.username, cl.password])


def test_read_from_stdin(
    tested_credentials,
    client_library_server_current,
    mocked_session,
    home_virlrc,
    cwd_virlrc,
):
    assert not home_virlrc.is_file()
    assert not cwd_virlrc.is_file()
    for name in tested_credentials:
        assert name not in os.environ

    with pytest.raises(OSError, match="reading from stdin"):
        _ = ClientLibrary(ssl_verify=False)
