#
# This file is part of VIRL 2
# Copyright (c) 2019-2025, Cisco Systems, Inc.
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
"""
A collection of utility classes to make getting credentials and
configuration easier.
"""

from __future__ import annotations

import getpass
import os
from pathlib import Path

from ..exceptions import InitializationError

_CONFIG_FILE_NAME = ".virlrc"


def _get_from_file(virlrc_parent: Path, prop_name: str) -> str | None:
    """
    Retrieve a property value from a file.

    :param virlrc_parent: The parent directory of the file.
    :param prop_name: The name of the property to retrieve.
    :returns: The value of the property if found, otherwise None.
    """
    virlrc = virlrc_parent / _CONFIG_FILE_NAME
    if virlrc.is_file():
        with virlrc.open() as fh:
            config = fh.readlines()

        for line in config:
            if line.startswith(prop_name):
                prop = line.split("=")[1].strip()
                if prop.startswith('"') and prop.endswith('"'):
                    prop = prop[1:-1]
                return prop
    return None


def _get_prop(prop_name: str) -> str | None:
    """
    Get the value of a variable.

    The function follows the order:

    1. Check for .virlrc in the current directory
    2. Recurse up the directory tree for .virlrc
    3. Check environment variables
    4. Check ~/.virlrc

    :param prop_name: The name of the property to retrieve.
    :returns: The value of the property if found, otherwise None.
    """
    # check for .virlrc in current directory
    cwd = Path.cwd()
    if prop := _get_from_file(cwd, prop_name):
        return prop

    # search up directory tree for a .virlrc
    for path in cwd.parents:
        if prop := _get_from_file(path, prop_name):
            return prop

    # try environment next
    prop = os.getenv(prop_name, None)
    if prop:
        return prop

    # check for .virlrc in home directory
    prop = _get_from_file(Path.home(), prop_name)

    return prop or None


def get_configuration(
    host: str | None, username: str | None, password: str | None, ssl_verify: bool | str
) -> tuple[str, str, str, bool | str]:
    """
    Get the login configuration.

    The login configuration is retrieved in the following order:

    1. Retrieve from function arguments
    2. Check for .virlrc in the current directory
    3. Recurse up the directory tree for .virlrc
    4. Check environment variables
    5. Check ~/.virlrc
    6. Prompt the user (except for the cert path)

    :param host: The host address of the CML server.
    :param username: The username.
    :param password: The password.
    :param ssl_verify: The CA bundle path or boolean value indicating SSL verification.
    :returns: A tuple containing the host, username, password,
        and SSL verification information.
    """
    if not (
        host
        or (host := _get_prop("VIRL2_URL") or _get_prop("VIRL_HOST"))
        or (host := input("Please enter the IP / hostname of your virl server: "))
    ):
        message = "No URL provided."
        raise InitializationError(message)

    if not (
        username
        or (username := _get_prop("VIRL2_USER") or _get_prop("VIRL_USERNAME"))
        or (username := input("Please enter your VIRL username: "))
    ):
        message = "No username provided."
        raise InitializationError(message)

    if not (
        password
        or (password := _get_prop("VIRL2_PASS") or _get_prop("VIRL_PASSWORD"))
        or (password := getpass.getpass("Please enter your password: "))
    ):
        message = "No password provided."
        raise InitializationError(message)

    if ssl_verify is True:
        ssl_verify = _get_prop("CA_BUNDLE") or _get_prop("CML_VERIFY_CERT") or True
        # to match the behavior of virlutils, we allow to disable the SSL check via ENV
        if isinstance(ssl_verify, str) and ssl_verify.lower() == "false":
            ssl_verify = False

    return host, username, password, ssl_verify
