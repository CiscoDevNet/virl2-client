#!/usr/bin/env python3
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

"""Register a controller with Smart Software Licensing.

Credentials are collected interactively so nothing sensitive is ever
written to disk. To automate, export ``CML_URL`` / ``CML_USERNAME`` /
``CML_PASSWORD`` / ``CML_SSMS_TOKEN`` before running. For controllers
with a self-signed certificate, also export ``CA_BUNDLE`` to the
controller CA PEM path.
"""

import getpass
import json
import os
import sys

from virl2_client import ClientLibrary


def _prompt(env_var: str, prompt: str, *, secret: bool = False) -> str:
    """Return the value of ``env_var`` or interactively prompt for it."""
    value = os.environ.get(env_var)
    if value is not None:
        return value
    reader = getpass.getpass if secret else input
    return reader(prompt)


def main() -> int:
    url = _prompt("CML_URL", "controller URL or hostname: ")
    username = _prompt("CML_USERNAME", "username: ")
    password = _prompt("CML_PASSWORD", "password: ", secret=True)
    token = _prompt("CML_SSMS_TOKEN", "Smart Licensing token: ", secret=True)

    client = ClientLibrary(url, username, password)
    licensing = client.licensing

    # Use the default SSMS transport (direct to the public Smart Licensing
    # server). Call licensing.set_transport(ssms=...) instead if you need
    # to point at an on-prem satellite.
    licensing.set_default_transport()

    try:
        # register_wait() returns the effective licensing status snapshot once
        # registration is COMPLETED and authorization is IN_COMPLIANCE, or
        # raises RuntimeError if the polling times out.
        status = licensing.register_wait(token)
    except RuntimeError as exc:
        print(f"ERROR: Smart Licensing registration timed out: {exc}", file=sys.stderr)
        return 1

    print(json.dumps(status, indent=4))
    return 0


if __name__ == "__main__":
    sys.exit(main())
