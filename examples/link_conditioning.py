#!/usr/bin/env python3
#
# Python bindings for the Cisco VIRL 2 Network Simulation Platform
#
# This file is part of VIRL 2
#
# Copyright 2020 Cisco Systems Inc.
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


import getpass
import re

from requests.exceptions import HTTPError

from virl2_client import ClientLibrary

VIRL_CONTROLLER = "virl2-controller"
VIRL_USERNAME = input("username: ")
VIRL_PASSWORD = getpass.getpass("password: ")
LAB_NAME = input("enter lab name: ")

client = ClientLibrary(VIRL_CONTROLLER, VIRL_USERNAME, VIRL_PASSWORD, ssl_verify=False)

# Find the lab by title and join it as long as it's the only
# lab with that title.
labs = client.find_labs_by_title(LAB_NAME)

if not labs or len(labs) != 1:
    print("ERROR: Unable to find a unique lab named {}".format(LAB_NAME))
    exit(1)

lobj = client.join_existing_lab(labs[0].id)

if not lobj:
    print("ERROR: Failed to join lab {}".format(LAB_NAME))
    exit(1)

# Print all links in the lab and ask which link to condition.
i = 1
liobjs = []
for link in lobj.links():
    print(
        "{}. {}[{}] <-> {}[{}]".format(
            i,
            link.interface_a.node.label,
            link.interface_a.label,
            link.interface_b.node.label,
            link.interface_b.label,
        )
    )
    liobjs.append(lobj.get_link_by_interfaces(link.interface_a, link.interface_b))
    i += 1

print()
lnum = 0
while lnum < 1 or lnum > i:
    lnum = input("Enter link number to condition (1-{}): ".format(i))
    try:
        lnum = int(lnum)
    except ValueError:
        lnum = 0

# Print the selected link's current conditioning (if any).
link = liobjs[lnum - 1]
print("Current condition is {}".format(link.get_condition()))
# Request the new conditoning for bandwidth, latency, jitter, and loss.
# Bandwidth is an integer between 0-10000000 kbps
# Bandwidth of 0 is "no bandwidth restriction"
# Latency is an integer between 0-10000 ms
# Jitter is an integer between 0-10000 ms
# Loss is a float between 0-100%
new_cond = input(
    "enter new condition in format 'BANDWIDTH, "
    "LATENCY, JITTER, LOSS' or 'None' to disable: "
)
# If "None" is provided disable any conditioning on the link.
if new_cond.lower() == "none":
    link.remove_condition()
    print("Link conditioning has been disabled.")
else:
    try:
        # Set the current conditioning based on the provided values.
        cond_list = re.split(r"\s*,\s*", new_cond)
        bw = int(cond_list[0])  # Bandwidth is an int
        latency = int(cond_list[1])  # Latency is an int
        jitter = int(cond_list[2])  # Jitter is an int
        loss = float(cond_list[3])  # Loss is a float
        link.set_condition(bw, latency, jitter, loss)
        print("Link conditioning set.")
    except HTTPError as exc:
        print("ERROR: Failed to set link conditioning: {}", format(exc))
        exit(1)
