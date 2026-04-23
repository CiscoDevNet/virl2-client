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

"""Interactively adjust link conditioning on a lab.

Bandwidth is 0-10_000_000 kbps (0 = unlimited), latency and jitter are
0-10_000 ms, loss is a percentage (0-100). Environment: ``CML_URL``,
``CML_USERNAME``, ``CML_PASSWORD``, ``CML_LAB_NAME`` override the
interactive prompts when set.
"""

import getpass
import os
import sys

from httpx import HTTPStatusError

from virl2_client import ClientLibrary


def _prompt(env_var: str, prompt: str, *, secret: bool = False) -> str:
    value = os.environ.get(env_var)
    if value is not None:
        return value
    reader = getpass.getpass if secret else input
    return reader(prompt)


def _parse_condition(raw: str) -> tuple[int, int, int, float]:
    """Parse ``BANDWIDTH, LATENCY, JITTER, LOSS`` into typed values.

    :raises ValueError: if the string does not contain exactly four
        comma-separated numeric values.
    """
    parts = [p.strip() for p in raw.split(",")]
    if len(parts) != 4:
        raise ValueError(f"expected 4 comma-separated values, got {len(parts)}")
    bandwidth = int(parts[0])
    latency = int(parts[1])
    jitter = int(parts[2])
    loss = float(parts[3])
    return bandwidth, latency, jitter, loss


def main() -> int:
    url = _prompt("CML_URL", "controller URL or hostname: ")
    username = _prompt("CML_USERNAME", "username: ")
    password = _prompt("CML_PASSWORD", "password: ", secret=True)
    lab_name = _prompt("CML_LAB_NAME", "lab name: ")

    client = ClientLibrary(url, username, password, ssl_verify=False)

    labs = client.find_labs_by_title(lab_name)
    if not labs or len(labs) != 1:
        print(f"ERROR: no unique lab named {lab_name!r}", file=sys.stderr)
        return 1

    lab = client.join_existing_lab(labs[0].id)
    if not lab:
        print(f"ERROR: failed to join lab {lab_name!r}", file=sys.stderr)
        return 1

    # Show the links with a 1-based index that matches the prompt.
    links = list(lab.links())
    if not links:
        print("No links in this lab -- nothing to condition.")
        return 0
    for idx, link in enumerate(links, start=1):
        print(
            f"{idx}. {link.interface_a.node.label}[{link.interface_a.label}] "
            f"<-> {link.interface_b.node.label}[{link.interface_b.label}]"
        )

    link_number = 0
    while not 1 <= link_number <= len(links):
        try:
            link_number = int(input(f"Enter link number to condition (1-{len(links)}): "))
        except ValueError:
            link_number = 0

    link = links[link_number - 1]
    print(f"Current condition is {link.get_condition()}")

    raw = input(
        "Enter new condition 'BANDWIDTH, LATENCY, JITTER, LOSS' "
        "or 'None' to disable: "
    ).strip()
    if raw.lower() == "none":
        link.remove_condition()
        print("Link conditioning has been disabled.")
        return 0

    try:
        bandwidth, latency, jitter, loss = _parse_condition(raw)
    except ValueError as exc:
        print(f"ERROR: invalid condition {raw!r}: {exc}", file=sys.stderr)
        return 1

    try:
        link.set_condition(bandwidth, latency, jitter, loss)
    except HTTPStatusError as exc:
        print(f"ERROR: failed to set link conditioning: {exc}", file=sys.stderr)
        return 1

    print("Link conditioning set.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
