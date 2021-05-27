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
from unittest.mock import patch
from urllib3.exceptions import InsecureRequestWarning

from virl2_client import ClientLibrary


def pytest_addoption(parser):
    parser.addoption(
        "--controller-url",
        default="http://127.0.0.1:8001",
        help="The URL of simple controller server",
    )


@pytest.fixture(scope="session")
def controller_url(request):
    return request.config.getoption("--controller-url")


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


def client_library_keep_labs_base(
    url, usr="cml2", pwd="cml2cml2", ssl_verify=False, allow_http=True
):
    clientlibrary = ClientLibrary(
        url,
        username=usr,
        password=pwd,
        ssl_verify=ssl_verify,
        allow_http=allow_http,
    )
    for _ in range(5):
        try:
            clientlibrary.is_system_ready()
        except HTTPError as err:
            if err.errno == 504:
                # system still initialising, wait longer
                time.sleep(2)

    return clientlibrary


@pytest.fixture
def client_library_keep_labs(no_ssl_warnings, controller_url: str) -> ClientLibrary:
    # for integration testing, the client library needs to connect to a mock simulator
    # running via HTTP on a non SSL servr / non-standard port. We therefore need to
    # set the allow_http to True. Otherwise the client library would enforce the HTTPS
    # scheme and the tests would fail. This should never be required in the wild.
    yield client_library_keep_labs_base(url=controller_url)


@pytest.fixture(scope="session")
def client_library_session(controller_url: str) -> ClientLibrary:
    """This client library has session lifetime"""
    yield client_library_keep_labs_base(url=controller_url)


@pytest.fixture
def client_library(client_library_keep_labs: ClientLibrary) -> ClientLibrary:
    clientlibrary = client_library_keep_labs
    stop_wipe_and_remove_all_labs(clientlibrary)
    # Reset "current" lab:
    clientlibrary.lab = None
    yield clientlibrary
    # tear down - delete labs from the tests
    # TODO: see if these need updating now remove_all_labs doesnt stop the lab
    stop_wipe_and_remove_all_labs(clientlibrary)


@pytest.fixture(scope="function")
def change_test_dir(request):
    os.chdir(request.fspath.dirname)
    yield
    os.chdir(request.config.invocation_dir)
