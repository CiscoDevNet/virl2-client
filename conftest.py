#
# Python bindings for the Cisco VIRL 2 Network Simulation Platform
#
# This file is part of VIRL 2
#
# Copyright 2020-2021 Cisco Systems Inc.
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

import os
import pytest
import time
import warnings

from requests import HTTPError
from urllib3.exceptions import InsecureRequestWarning

from virl2_client import ClientConfig, ClientLibrary


def pytest_addoption(parser):
    # only add these options if the test is run inside the
    # root virl2 repository itself and not from outside
    root_dir = parser.extra_info.get("rootdir", "")
    if not root_dir.endswith("virl2_client"):
        return

    parser.addoption(
        "--controller-url",
        default="https://127.0.0.1",
        metavar="VIRL2_URL",
        help="The URL of a CML2 controller",
    )

    parser.addoption(
        "--controller-username",
        default=None,
        metavar="VIRL2_USER",
        help="The user on CML2 controller",
    )

    parser.addoption(
        "--controller-password",
        default=None,
        metavar="VIRL2_PASS",
        help="The user's password on CML2 controller",
    )

    parser.addoption(
        "--controller-ssl-verify",
        default=False,
        nargs="?",
        const=True,
        metavar="CA_BUNDLE",
        help="Verify certificate of CML2 controller",
    )

    parser.addoption(
        "--controller-allow-http",
        default=False,
        action="store_true",
        help="Allow HTTP for CML2 controller URL",
    )

    parser.addoption(
        "--controller-pyats-hostname",
        default=None,
        help="Host:port for making PyATS termws connections",
    )


@pytest.fixture
def no_ssl_warnings():
    with warnings.catch_warnings():
        # We don't care about SSL connections to untrusted servers in tests:
        warnings.simplefilter("ignore", InsecureRequestWarning)
        yield


def stop_wipe_and_remove_all_labs(client_library: ClientLibrary):
    lab_list = client_library.get_lab_list()
    for lab_id in lab_list:
        lab = client_library.join_existing_lab(lab_id)
        lab.stop()
        lab.wipe()
        client_library.remove_lab(lab_id)


@pytest.fixture(scope="session")
def client_config(request) -> ClientConfig:
    return ClientConfig(
        url=request.config.getoption("--controller-url"),
        username=request.config.getoption("--controller-username"),
        password=request.config.getoption("--controller-password"),
        ssl_verify=request.config.getoption("--controller-ssl-verify"),
        allow_http=request.config.getoption("--controller-allow-http"),
        raise_for_auth_failure=True,
    )


@pytest.fixture(scope="session")
def pyats_hostname(request) -> str:
    return request.config.getoption("--controller-pyats-hostname")


def client_library_keep_labs_base(client_config: ClientConfig) -> ClientLibrary:
    client_library = client_config.make_client()
    for _ in range(5):
        try:
            client_library.is_system_ready()
        except HTTPError as err:
            if err.errno == 504:
                # system still initialising, wait longer
                time.sleep(2)

    return client_library


@pytest.fixture
def client_library_keep_labs(
    no_ssl_warnings, client_config: ClientConfig
) -> ClientLibrary:
    # for integration testing, the client library needs to connect to a mock simulator
    # running via HTTP on a non SSL servr / non-standard port. We therefore need to
    # set the allow_http to True. Otherwise the client library would enforce the HTTPS
    # scheme and the tests would fail. This should never be required in the wild.
    yield client_library_keep_labs_base(client_config)


@pytest.fixture(scope="session")
def client_library_session(client_config: ClientConfig) -> ClientLibrary:
    """This client library has session lifetime"""
    yield client_library_keep_labs_base(client_config)


@pytest.fixture
def client_library(client_library_keep_labs: ClientLibrary) -> ClientLibrary:
    client_library = client_library_keep_labs
    stop_wipe_and_remove_all_labs(client_library)
    # Reset "current" lab:
    client_library.lab = None
    yield client_library
    # tear down - delete labs from the tests
    # TODO: see if these need updating now remove_all_labs doesnt stop the lab
    stop_wipe_and_remove_all_labs(client_library)


@pytest.fixture(scope="function")
def change_test_dir(request):
    os.chdir(request.fspath.dirname)
    yield
    os.chdir(request.config.invocation_dir)
