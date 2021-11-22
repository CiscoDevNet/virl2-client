#
# This file is part of CML 2
#
# Copyright 2021 Cisco Systems Inc.
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
import re
import requests
import uuid

from virl2_client import ClientLibrary
from virl2_client.models.cl_pyats import ClPyats

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
    lab = client_library.import_sample_lab("server-triangle.yaml")
    s0 = lab.get_node_by_label("server-0")
    assert lab.get_node_by_label("server-1") is not None
    assert lab.get_node_by_label("server-2") is not None

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

    assert [link for link in lab.links() if link.state is not None] == []


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
    assert exc.value.response.status_code == 400

    # need to stop and wipe to be able to remove node.
    s3.stop()
    s3.wipe()
    lab.remove_node(s3)


def test_import_yaml(client_library_session: ClientLibrary):
    lab = client_library_session.import_sample_lab("server-triangle.yaml")
    assert lab is not None
    lab.remove()


def test_import_virl(client_library_session: ClientLibrary):
    lab = client_library_session.import_sample_lab("dual-server.virl")
    assert lab is not None
    lab.remove()


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

    assert lab.is_active()

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
        "id",
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

    tags = sorted(node_3.tags())
    tag = tags[2]
    tagtag = tag + tag

    node_3.add_tag(tagtag)
    tags.insert(3, tagtag)
    lab.sync(topology_only=True)
    assert sorted(node_3.tags()) == tags

    node_3.add_tag(tag)
    lab.sync(topology_only=True)
    assert sorted(node_3.tags()) == tags

    node_3._tags.remove(tag)
    node_3.add_tag(tag)
    lab.sync(topology_only=True)
    assert sorted(node_3.tags()) == tags

    node_3.remove_tag(tag)
    tags.remove(tag)
    lab.sync(topology_only=True)
    assert sorted(node_3.tags()) == tags

    with pytest.raises(ValueError):
        node_3.remove_tag(tag)
    lab.sync(topology_only=True)
    assert sorted(node_3.tags()) == tags

    node_3._tags.append(tag)
    node_3.remove_tag(tag)
    lab.sync(topology_only=True)
    assert sorted(node_3.tags()) == tags


def test_node_with_unavailable_vnc(client_library_session: ClientLibrary):
    lab = client_library_session.create_lab("lab_111")
    node = lab.create_node("s1", "unmanaged_switch", 5, 100)
    lab.start()
    assert lab.state() == "STARTED"
    with pytest.raises(requests.exceptions.HTTPError) as err:
        node.vnc_key()
    assert err.value.response.status_code == 404
    lab.stop()
    lab.wipe()
    lab.remove()


@pytest.mark.nomock
def test_node_console_logs(client_library_session: ClientLibrary):
    lab = client_library_session.create_lab("lab_space")
    ext_conn = lab.create_node("ec", "external_connector", 100, 50, wait=False)
    server = lab.create_node("s1", "server", 100, 100)
    iosv = lab.create_node("n", "iosv", 50, 0)
    lab.start()
    assert lab.state() == "STARTED"
    # server has one serial console on id 0
    logs = server.console_logs(console_id=0)
    assert type(logs) == str

    # external connector - no serial console
    with pytest.raises(requests.exceptions.HTTPError) as err:
        ext_conn.console_logs(console_id=0)
    assert err.value.response.status_code == 400
    assert "Serial port does not exist on node" in err.value.response.text

    # test limited number of lines
    num_lines = 5
    logs = server.console_logs(console_id=0, lines=num_lines)
    assert type(logs) == str
    assert len(logs.split("\n")) == num_lines

    # assert 400 for non existent console id for server >0
    with pytest.raises(requests.exceptions.HTTPError) as err:
        server.console_logs(console_id=55)
    assert err.value.response.status_code == 400
    assert "Serial port does not exist on node" in err.value.response.text

    # iosv has 2 serial consoles
    logs = iosv.console_logs(console_id=0)
    assert type(logs) == str
    logs = iosv.console_logs(console_id=1)
    assert type(logs) == str
    with pytest.raises(requests.exceptions.HTTPError) as err:
        iosv.console_logs(console_id=2)
    assert err.value.response.status_code == 400
    assert "Serial port does not exist on node" in err.value.response.text

    lab.stop()
    lab.wipe()
    lab.remove()


def test_topology_owner(client_library_session: ClientLibrary):
    cml2_uid = client_library_session.user_management.user_id(
        client_library_session.username
    )
    lab = client_library_session.create_lab("owned_by_cml2")
    lab.sync(topology_only=True)
    assert lab.owner == cml2_uid
    lab.remove()


def test_start_stop_start_stop_cycle(client_library: ClientLibrary):
    """we need to test if the entire lifecycle works... e.g.
    - define
    - start
    - queued
    - booted
    - stopped
    - queued
    - start
    - stopped
    - ...
    """
    lab = client_library.import_sample_lab("server-triangle.yaml")

    lab.start()
    lab.stop()
    lab.start()
    lab.stop()
    lab.wipe()


def test_links_on_various_slots(client_library: ClientLibrary):
    """
    Create a link between two nodes on higher interfaces,
    then remove the link and re-add a link on lower interfaces.
    """
    lab = client_library.create_lab()

    s1 = lab.create_node("s1", "server", 50, 100)
    s2 = lab.create_node("s2", "server", 50, 200)

    assert s1.interfaces() == []
    assert s2.interfaces() == []

    # create a link between s1 and s2
    s1_i1 = s1.create_interface(slot=4)
    s2_i1 = s2.create_interface(slot=4)

    assert len(s1.interfaces()) == 5
    assert len(s2.interfaces()) == 5

    link = lab.create_link(s1_i1, s2_i1)

    assert link.interface_a.slot == 4
    assert link.interface_b.slot == 4

    lab.remove_link(link)

    # verify that removing the link doesn't delete interfaces:
    assert len(s1.interfaces()) == 5
    assert len(s2.interfaces()) == 5

    # create a link between s1 and s2 on lower slot than before
    s1_i1 = s1.create_interface(slot=0)
    s2_i1 = s2.create_interface(slot=0)
    link = lab.create_link(s1_i1, s2_i1)
    assert link.interface_a.slot == 0
    assert link.interface_b.slot == 0

    assert all(
        uuid.UUID(interface_id, version=4) for interface_id in lab._interfaces.keys()
    )
    assert [ifc.label for ifc in lab.interfaces()] == [
        "eth0",
        "eth1",
        "eth2",
        "eth3",
        "eth4",
        "eth0",
        "eth1",
        "eth2",
        "eth3",
        "eth4",
    ]
    # create a link between s1 and s2, again on the 4th slot
    s1_i1 = s1.create_interface(slot=4)
    s2_i1 = s2.create_interface(slot=4)
    link = lab.create_link(s1_i1, s2_i1)

    assert link.interface_a.slot == 4
    assert link.interface_b.slot == 4

    lab.remove_link(link)


@pytest.mark.nomock
def test_link_conditioning(client_library_keep_labs: ClientLibrary):
    response_packets = (
        r"(\d+) packets transmitted, (\d+) packets received, (\d+)% packet loss"
    )
    response_roundtrip = r"round-trip min/avg/max = [\d\.]+/([\d\.]+)/[\d\.]+ ms"

    lab = client_library_keep_labs.create_lab()

    alpine = lab.create_node("alpine-0", "alpine", 0, 0)
    ums = lab.create_node("unmanaged-switch-0", "unmanaged_switch", 100, 0)
    ext = lab.create_node("ext", "external_connector", 200, 0)

    lab.connect_two_nodes(alpine, ums)
    lab.connect_two_nodes(ums, ext)

    lab.start(wait=True)

    alpine = lab.get_node_by_label("alpine-0")
    ums = lab.get_node_by_label("unmanaged-switch-0")
    link = lab.get_link_by_nodes(alpine, ums)

    pylab = ClPyats(lab)
    pylab.sync_testbed("cml2", "cml2cml2")

    # ensure there's no link condition
    result = link.get_condition()
    assert result is None

    # remove, just to be sure
    link.remove_condition()

    def check_result(result_input, has_loss, min_avg, max_avg):
        print(result_input)
        rm = re.search(response_packets, result_input, re.MULTILINE)
        assert len(rm.groups()) == 3
        transmitted, received, loss = [int(a) for a in rm.groups()]
        # print(transmitted, received, loss)
        if has_loss:
            assert transmitted != received
            assert loss > 0
        else:
            assert transmitted == received
            assert loss == 0

        rm = re.search(response_roundtrip, result_input, re.MULTILINE)
        assert len(rm.groups()) == 1
        avg = float(rm.group(1))
        # print("avg:", avg)
        assert min_avg <= avg <= max_avg

    result = pylab.run_command("alpine-0", "time ping -Aqc100  192.168.255.1")
    check_result(result, False, 0.0, 10.0)

    # link.set_condition_by_name("dsl1")

    # 2mbps, 50ms delay, 0ms jitter, 5.1% loss)
    # 5.1 to ensure that the float is understood and returned
    link.set_condition(2000, 50, 0, 5.1)

    result = link.get_condition()
    assert result == {"bandwidth": 2000, "latency": 50, "loss": 5.1, "jitter": 0}

    result = pylab.run_command("alpine-0", "time ping -Aqc100 192.168.255.1")
    check_result(result, True, 90.0, 110.0)

    link.remove_condition()
    result = pylab.run_command("alpine-0", "time ping -Aqc100  192.168.255.1")
    check_result(result, False, 0.0, 10.0)

    lab.stop()
    lab.wipe()
    lab.remove()
