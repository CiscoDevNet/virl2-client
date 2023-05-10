"""
https://github.com/CiscoDevNet/virlutils/blob/master/virl/api/credentials.py

Collection of utility classes to make getting credentials and
configuration easier.
"""
from __future__ import annotations

import getpass
import os
from pathlib import Path

_CONFIG_FILE_NAME = ".virlrc"


def _get_from_file(virlrc_parent: Path, prop_name: str) -> str | None:
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


def get_prop(prop_name: str) -> str:
    """
    Gets a variable using the following order:
    * Check for .virlrc in current directory
    * Recurse up directory tree for .virlrc
    * Check environment variables
    * Check ~/.virlrc
    * Prompt user

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
    host: str, username: str, password: str, ssl_verify: bool | str
) -> tuple[str, str, str, str]:
    """
    Used to get login configuration
    The login configuration is taken in the following order:
    * Check for .virlrc in the current directory
    * Check environment variables
    * Check ~/.virlrc
    * Prompt user
    """
    if not host:
        host = get_prop("VIRL2_URL")
        if not host:
            host = input("Please enter the IP / hostname of your virl server: ")

    if not username:
        username = get_prop("VIRL2_USER")
        if not username:
            username = input("Please enter your VIRL username: ")

    if not password:
        password = get_prop("VIRL2_PASS")
        if not password:
            password = getpass.getpass("Please enter your password: ")

    if ssl_verify is True:
        ssl_verify = get_prop("CA_BUNDLE")

    if all([host, username, password]):
        return host, username, password, ssl_verify
    print("Unable to determine CML/VIRL credentials, please see docs")
    exit(1)
