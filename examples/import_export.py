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

"""Round-trip a lab topology through export / import.

Builds a small lab, downloads its YAML topology, imports it back under
a new title, asserts the imported lab has the same nodes/links, and
cleans up both labs. Useful as a starting point for backup tooling,
CI fixtures, or migrating a lab between controllers.

``Lab.download()`` returns the YAML topology as a string; the client
exposes two import paths:

* ``ClientLibrary.import_lab(topology_str, title=...)`` -- import
  from an in-memory string (used here).
* ``ClientLibrary.import_lab_from_path(path, title=...)`` -- import
  directly from a ``.yaml`` / ``.virl`` file on disk.
"""

from __future__ import annotations

import getpass
import os
import pathlib
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
    output_dir = pathlib.Path(
        os.environ.get("CML_EXPORT_DIR", os.getcwd())
    ).expanduser()
    output_dir.mkdir(parents=True, exist_ok=True)

    client = ClientLibrary(url, username, password, ssl_verify=False)
    client.is_system_ready(wait=True)

    source = client.create_lab(title="virl2_client import/export source")
    try:
        server1 = source.create_node("server1", "server", 50, 100)
        server2 = source.create_node("server2", "server", 250, 100)
        source.connect_two_nodes(server1, server2)

        # Download returns a YAML topology (str). Writing to disk is
        # optional; doing so here keeps the script useful for backup
        # scenarios.
        topology_yaml = source.download()
        export_path = output_dir / f"{source.id}.yaml"
        export_path.write_text(topology_yaml)
        print(f"Exported source lab {source.id!r} to {export_path}")

        restored = client.import_lab(
            topology=topology_yaml,
            title="virl2_client import/export restored",
        )
        try:
            # sync() was called by import_lab(), but nodes/interfaces
            # on the restored lab are not real object refs from the
            # source lab, so compare by label/count.
            src_nodes = sorted(n.label for n in source.nodes())
            dst_nodes = sorted(n.label for n in restored.nodes())
            assert src_nodes == dst_nodes, (src_nodes, dst_nodes)
            src_links = len(source.links())
            dst_links = len(restored.links())
            assert src_links == dst_links, (src_links, dst_links)
            print(
                f"Restored lab {restored.id!r} matches source: "
                f"{len(dst_nodes)} nodes, {dst_links} links."
            )
        finally:
            restored.remove()
    finally:
        source.remove()

    return 0


if __name__ == "__main__":
    sys.exit(main())
