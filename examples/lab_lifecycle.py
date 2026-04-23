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

"""End-to-end walkthrough of the lab state machine.

Creates a two-node lab, starts it, waits for convergence, exercises a
stop / wipe / start cycle on one node, then tears everything back
down. Demonstrates the blocking ``wait=True`` convenience on
``start()`` / ``stop()`` / ``wipe()`` as well as explicit polling via
``Lab.wait_until_lab_converged()``.

Environment variables (all optional, prompted if unset):

* ``CML_URL`` / ``CML_USERNAME`` / ``CML_PASSWORD`` - controller
  credentials.
* ``CML_NODE_DEFINITION`` - node definition to use (defaults to
  ``alpine``; make sure it is available on the controller).
"""

from __future__ import annotations

import getpass
import os
import sys

from virl2_client import ClientLibrary


def _prompt(env_var: str, prompt: str, *, secret: bool = False) -> str:
    value = os.environ.get(env_var)
    if value is not None:
        return value
    reader = getpass.getpass if secret else input
    return reader(prompt)


def main() -> int:
    url = _prompt("CML_URL", "controller URL or hostname: ")
    username = _prompt("CML_USERNAME", "username: ")
    password = _prompt("CML_PASSWORD", "password: ", secret=True)
    node_def = os.environ.get("CML_NODE_DEFINITION", "alpine")

    client = ClientLibrary(url, username, password, ssl_verify=False)
    client.is_system_ready(wait=True)

    lab = client.create_lab(title="virl2_client lab_lifecycle demo")
    try:
        node_a = lab.create_node("a", node_def, 0, 0)
        node_b = lab.create_node("b", node_def, 200, 0)
        lab.connect_two_nodes(node_a, node_b)
        print(f"Created lab {lab.id!r} with nodes {node_a.label}, {node_b.label}.")

        # Blocking start -- returns when the whole lab is BOOTED.
        lab.start(wait=True)
        print(f"Lab state after start(): {lab.state()}")

        # Individual node operations. wait=True on the lab applies to
        # the whole lab; for a single node, poll via
        # wait_until_lab_converged() once the node-level call returns.
        node_a.stop()
        lab.wait_until_lab_converged()
        print(f"{node_a.label} state after stop(): {node_a.state}")

        node_a.wipe()
        lab.wait_until_lab_converged()
        print(f"{node_a.label} state after wipe(): {node_a.state}")

        node_a.start()
        lab.wait_until_lab_converged()
        print(f"{node_a.label} state after start(): {node_a.state}")

        # sync_states() flushes any pending state updates into the
        # local model without having to wait a full tick.
        lab.sync_states()
        for node in lab.nodes():
            print(f"  node={node.label}  state={node.state}")

    finally:
        # Always tear the lab down so this script is safe to run
        # repeatedly in a sandbox.
        lab.stop(wait=True)
        lab.wipe(wait=True)
        lab.remove()
        print(f"Removed lab {lab.id!r}.")

    return 0


if __name__ == "__main__":
    sys.exit(main())
