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

from virl2_client import ClientLibrary

# setup the connection and clean everything
cl = ClientLibrary("http://localhost:8001", "virl2", "virl2", allow_http=True)
cl.wait_for_lld_connected()

lab_list = cl.get_lab_list()
for lab_id in lab_list:
    lab = cl.join_existing_lab(lab_id)
    lab.stop()
    lab.wipe()
    cl.remove_lab(lab_id)

lab = cl.create_lab()
lab_id = "lab_1"
lab = cl.join_existing_lab(lab_id)

s1 = lab.create_node("s1", "server", 50, 100)
s2 = lab.create_node("s2", "server", 50, 200)
print(s1, s2)

# create a link between s1 and s2, equivalent to
#   s1_i1 = s1.create_interface()
#   s2_i1 = s2.create_interface()
#   lab.create_link(s1_i1, s2_i1)
lab.connect_two_nodes(s1, s2)

# this must remove the link between s1 and s2
lab.remove_node(s2)

lab.sync_states()
for node in lab.nodes():
    print(node, node.state)
    for iface in node.interfaces:
        print(iface, iface.state)

assert [link for link in lab.links() if link.state is not None] == []
