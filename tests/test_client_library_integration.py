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
import requests

from virl2_client import ClientLibrary

pytestmark = [pytest.mark.integration]


def test_sync_lab(client_library: ClientLibrary):
    lab = client_library.create_lab("my test lab name")
    lab = client_library.join_existing_lab(lab.id)

    r1 = lab.create_node("r1", "server", 5, 100)
    r2 = lab.create_node("r2", "server", 102, 201)
    r3 = lab.create_node("r3", "server", 200, 400)
    # print(r1, r2, r3)

    r1.x = 400
    r1.label = "abc"

    r1_i1 = r1.create_interface()
    r1_i2 = r1.create_interface()

    r2_i1 = r2.create_interface()
    r2_i2 = r2.create_interface()

    r3_i1 = r3.create_interface()
    r3_i2 = r3.create_interface()

    #
    lab.create_link(r1_i1, r2_i1)
    lab.create_link(r2_i2, r3_i1)
    lab.create_link(r3_i2, r1_i2)

    r1.start()
    r2.start()
    r3.start()

    # lab.stop()
    r1.stop()
    r2.stop()
    r3.stop()

    # lab.remove_link(link_1)
    # lab.remove_link(link_2)
    # lab.remove_link(link_3)
    # lab.remove_node(r1)
    # lab.remove_node(r2)
    # lab.remove_node(r3)

    # TODO: wait for convergence here
    lab.stop()

    # lab.clear()
    # lab.sync_events()


def test_import(client_library: ClientLibrary):
    lab = client_library.import_sample_lab("server-triangle.ng")
    s0 = lab.get_node_by_id("n0")
    assert lab.get_node_by_id("n1") is not None
    assert lab.get_node_by_id("n2") is not None

    lab.start()

    s0.stop()
    s0.wipe()

    i1 = s0.create_interface()

    s3 = lab.create_node("s3", "server", 100, 200)
    i2 = s3.create_interface()

    lab.create_link(i1, i2)

    lab.start()
    lab.stop()


def test_create_client_lab(client_library: ClientLibrary):
    lab = client_library.create_lab()
    lab.auto_sync = False

    print("Created lab {}".format(lab.id))
    # using server nodes, not IOSv nodes as they are not available
    # without a reference platform ISO attached
    r1 = lab.create_node("r1", "server", 5, 100)
    r2 = lab.create_node("r2", "server", 102, 201)
    r3 = lab.create_node("r3", "server", 200, 400)
    print(r1, r2, r3)

    r1_i1 = r1.create_interface()
    r1_i2 = r1.create_interface()
    print(r1_i1, r1_i2)

    r2_i1 = r2.create_interface()
    r2_i2 = r2.create_interface()

    r3_i1 = r3.create_interface()
    r3_i2 = r3.create_interface()

    link_1 = lab.create_link(r1_i1, r2_i1)
    link_2 = lab.create_link(r2_i2, r3_i1)
    link_3 = lab.create_link(r3_i2, r1_i2)

    # r1.config = "test"
    # r2.x = 50
    # r2.y = 200
    #

    # r1.start()
    # r2.start()
    # r3.start()

    # r1.stop()
    # r2.stop()
    # r3.stop()

    r1.label = "r1_test"

    # lab.remove_node(r1)
    lab.remove_link(link_1)
    lab.remove_link(link_2)
    lab.remove_link(link_3)
    lab.remove_node(r1)
    lab.remove_node(r2)
    lab.remove_node(r3)

    lab.sync_states()

    for node in lab.nodes():
        print(node, node.state)
        for iface in node.interfaces():
            print(iface, iface.state)

    for link in lab.links():
        print(link, link.state)

    # lab.remove()

    # print("clear lab")
    # lab.clear()
    # print("remove lab")
    # events = lab.sync_events()
    # for event in lab.events:
    #     print(event)
    # lab.wait_until_lab_converged()
    lab.remove()


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

    for link in lab.links():
        print(link, link.state)

    # self.assertEqual(0, len(links))


def test_server_node_deletion(client_library: ClientLibrary):
    lab = client_library.create_lab("lab_1")

    lab.auto_sync = False

    s1 = lab.create_node("s1", "server", 5, 100)
    s2 = lab.create_node("s2", "server", 102, 201)

    s1_iface = lab.create_interface(s1, 2)
    s2_iface = lab.create_interface(s2, 2)
    lab.create_link(s1_iface, s2_iface)

    lab.start()

    s3 = lab.create_node("s3", "server", 200, 400)
    s3_iface = lab.create_interface(s3)

    s2.stop()

    lab.create_link(s2.interfaces()[0], s3_iface)

    lab.start()

    # can't remove node while running
    with pytest.raises(requests.exceptions.HTTPError) as exc:
        lab.remove_node(s3)
    assert exc.value.response.status_code == 403

    # need to stop and wipe to be able to remove node.
    s3.stop()
    s3.wipe()
    lab.remove_node(s3)


def test_import_json(client_library: ClientLibrary):
    lab = client_library.import_sample_lab("server-triangle.ng")
    assert lab is not None


def test_import_yaml(client_library: ClientLibrary):
    lab = client_library.import_sample_lab("server-triangle.yaml")
    assert lab is not None


def test_import_virl(client_library: ClientLibrary):
    lab = client_library.import_sample_lab("dual-server.virl")
    assert lab is not None


def test_lab_state(client_library: ClientLibrary):
    lab = client_library.create_lab("lab_1")

    s1 = lab.create_node("s1", "server", 5, 100)
    s2 = lab.create_node("s2", "server", 102, 201)

    s1_iface = lab.create_interface(s1, 2)
    s2_iface = lab.create_interface(s2, 2)
    lab.create_link(s1_iface, s2_iface)

    state = lab.state()
    assert state == "DEFINED_ON_CORE"

    lab.start()
    state = lab.state()
    assert state == "STARTED"

    lab.stop()
    state = lab.state()
    assert state == "STOPPED"

    lab.wipe()
    state = lab.state()
    assert state == "DEFINED_ON_CORE"


def test_lab_details(client_library: ClientLibrary):
    lab = client_library.create_lab("lab_1")

    s1 = lab.create_node("s1", "server", 5, 100)
    s2 = lab.create_node("s2", "server", 102, 201)

    s1_iface = lab.create_interface(s1, 2)
    s2_iface = lab.create_interface(s2, 2)
    lab.create_link(s1_iface, s2_iface)

    expected_keys = (
        "state",
        "created",
        "lab_title",
        "lab_description",
        "node_count",
        "link_count",
        "id"
    )

    details = lab.details()
    assert all(k in details.keys() for k in expected_keys)
    assert details["node_count"] == 2
    assert details["link_count"] == 1
    assert details["state"] == "DEFINED_ON_CORE"


def test_labels_and_tags(client_library: ClientLibrary):
    lab = client_library.import_sample_lab("server-triangle.yaml")

    lab.sync(topology_only=True)

    node_1 = lab.get_node_by_label("server-0")
    assert node_1.label == "server-0"
    assert len(node_1.tags()) == 2

    node_2 = lab.get_node_by_label("server-1")
    assert node_2.label == "server-1"
    assert len(node_2.tags()) == 2

    node_3 = lab.get_node_by_label("server-2")
    assert node_3.label == "server-2"
    assert len(node_3.tags()) == 5
