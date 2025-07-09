#!/usr/bin/env python3
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

# This script demonstrates various functionalities of the client library.
# Each example is accompanied by comments explaining its purpose and usage.
import pathlib

from virl2_client import ClientLibrary

SSMS = "https://sch-alpha.cisco.com/its/service/oddce/services/DDCEService"

TOKEN = (
    "FFY4YzJjNjItMDUxNi00NjJhLWIzMzQtMzllMzEzN2NhYjk2"
    "6s8e1gr5res1g35ads1g651rg23rs1gs3rd5g1s2rd1g3s2r"
    "WhPV3MzWGJrT3U5VHVEL1NrWkNu%0AclBSST0%3D%0A"
)


# Set up the CML 2 connection
server_url = "http://localhost:8001"
username = "cml2"  # Default username if not changed in CML instance
password = pathlib.Path("/etc/machine-id").read_text().strip()
# Default password is equal to the contents of the CML instances /etc/machine-id file
# If you are running this script remotely, replace the password above
client_library = ClientLibrary(server_url, username, password, allow_http=True)

# Check if the CML 2 system is ready
client_library.is_system_ready(wait=True)

# Set up licensing configuration
client_library.licensing.set_transport(ssms=SSMS)
client_library.licensing.register_wait(token=TOKEN)

# Get a list of existing labs and print their details
lab_list = client_library.get_lab_list()
for lab_id in lab_list:
    lab = client_library.join_existing_lab(lab_id)
    print("Lab ID:", lab.id)
    print("Lab Title:", lab.title)
    print("Lab Description:", lab.description)
    print("Lab State:", lab.state)
    print("----")

# A simpler way to join all labs at once
labs = client_library.all_labs()

# Create a lab
lab = client_library.create_lab()

# Create two server nodes
server1 = lab.create_node("server1", "server", 50, 100)
server2 = lab.create_node("server2", "server", 50, 200)
print("Created nodes:", server1, server2)

# Create a link between server1 and server2
link = lab.connect_two_nodes(server1, server2)
print("Created link between server1 and server2")

# Remove the link between server1 and server2
link.remove()
print("Removed link between server1 and server2")

# Manually synchronize lab states - this happens automatically once per second
# by default, but we can skip the wait by calling this method
lab.sync_states()

# Print the state of each node and its interfaces
for node in lab.nodes():
    print(f"Node: {node.label} | State: {node.state}")
    for interface in node.interfaces():
        print(f"    Interface: {interface.label} | State: {interface.state}")

# Export a lab topology to a file
lab_data = lab.download()
with open("demo_lab_export.yaml", "w") as file:
    file.write(lab_data)
print("Lab exported successfully.")

# Clean up the lab
lab.stop()
lab.wipe()
lab.remove()  # or client_library.remove_lab(lab_id)

# Deregister (optional) and set licensing back to the default transport (optional)
# Default SSMS is "https://smartreceiver.cisco.com/licservice/license"
client_library.licensing.deregister()
client_library.licensing.set_default_transport()
