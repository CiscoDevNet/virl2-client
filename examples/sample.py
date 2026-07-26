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

"""Walk-through of the most common virl2_client operations.

Set at least ``CML_URL``, ``CML_USERNAME`` and ``CML_PASSWORD`` in the
environment before running this script. Optional variables:

* ``CML_SSMS_URL``  -- override the default SSMS endpoint.
* ``CML_SSMS_TOKEN`` -- Smart Licensing registration token. When unset
  the licensing block is skipped, which lets the script be used on a
  controller that is already licensed.
"""

import os
import pathlib
import sys

from virl2_client import ClientLibrary

DEFAULT_SSMS_URL = "https://smartreceiver.cisco.com/licservice/license"


def _read_default_password() -> str:
    """Return the controller's default password or an empty string.

    On a locally-provisioned CML instance the default admin password is the
    contents of ``/etc/machine-id``. That file only exists on the
    controller itself, so callers running remotely should export
    ``CML_PASSWORD`` instead.
    """
    try:
        return pathlib.Path("/etc/machine-id").read_text().strip()
    except OSError:
        return ""


def main() -> int:
    url = os.environ.get("CML_URL", "http://localhost:8001")
    username = os.environ.get("CML_USERNAME", "cml2")
    password = os.environ.get("CML_PASSWORD") or _read_default_password()
    if not password:
        print(
            "ERROR: set CML_PASSWORD (or run on the controller so "
            "/etc/machine-id is readable).",
            file=sys.stderr,
        )
        return 1

    client = ClientLibrary(url, username, password, allow_http=True)
    client.is_system_ready(wait=True)

    token = os.environ.get("CML_SSMS_TOKEN")
    if token:
        ssms = os.environ.get("CML_SSMS_URL", DEFAULT_SSMS_URL)
        client.licensing.set_transport(ssms=ssms)
        client.licensing.register_wait(token=token)

    for lab_id in client.get_lab_list():
        lab = client.join_existing_lab(lab_id)
        print(f"Lab {lab.id!r}: title={lab.title!r}, state={lab.state}")

    # A simpler way to join all labs at once.
    client.all_labs()

    lab = client.create_lab()
    server1 = lab.create_node("server1", "server", 50, 100)
    server2 = lab.create_node("server2", "server", 50, 200)
    print("Created nodes:", server1, server2)

    link = lab.connect_two_nodes(server1, server2)
    print("Created link between server1 and server2")

    link.remove()
    print("Removed link between server1 and server2")

    # sync_states() skips the next auto-sync tick so subsequent reads
    # are guaranteed to reflect the latest server state.
    lab.sync_states()
    for node in lab.nodes():
        print(f"Node: {node.label} | State: {node.state}")
        for interface in node.interfaces():
            print(f"    Interface: {interface.label} | State: {interface.state}")

    export_path = pathlib.Path("demo_lab_export.yaml")
    export_path.write_text(lab.download())
    print(f"Lab exported to {export_path}.")

    lab.stop()
    lab.wipe()
    lab.remove()

    if token:
        # Optional cleanup -- deregister and fall back to default transport.
        client.licensing.deregister()
        client.licensing.set_default_transport()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
