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

import pytest

from virl2_client import ClientLibrary


@pytest.mark.integration
def test_connect(client_library: ClientLibrary):
    lab = client_library.create_lab("my lab name")
    lab = client_library.join_existing_lab(lab.id)

    lab.auto_sync = False

    s1 = lab.create_node("s1", "server", 50, 100)
    s2 = lab.create_node("s2", "server", 50, 200)
    print(s1, s2)

    # create a link between s1 and s2
    s1_i1 = s1.create_interface()
    s2_i1 = s2.create_interface()
    lab.create_link(s1_i1, s2_i1)

    # this must remove the link between s1 and s2
    lab.remove_node(s2)

    lab.sync_states()
    for node in lab.nodes():
        print(node, node.state)
        for iface in node.interfaces():
            print(iface, iface.state)

    assert [link for link in lab.links() if link.state is not None] == []
