#
# This file is part of VIRL 2
# Copyright (c) 2019-2022, Cisco Systems, Inc.
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

"""Tests for labs, nodes interfaces, links, etc."""

import inspect
import re
import uuid
from time import sleep

import requests
import pytest
from unicon.core.errors import SubCommandFailure

from virl2_client import ClientLibrary
from virl2_client.models.cl_pyats import ClPyats


pytestmark = [pytest.mark.integration]

# TODO: reduce code duplication
# TODO: split into more granular test cases and document


def create_lab(client_library_session: ClientLibrary, node_types: list, sync: bool = False):
    lab = client_library_session.create_lab(inspect.stack()[1].function)
    lab = client_library_session.join_existing_lab(lab.id)
    lab.auto_sync = sync

    for idx in range(len(node_types)):
        _ = lab.create_node("r{}".format(idx), node_types[idx], idx * 100, 0)

    nodes = lab.nodes()
    for idx in range(len(node_types) - 1):
        _ = lab.connect_two_nodes(nodes[idx], nodes[idx+1])
    return lab


@pytest.mark.parametrize("sync", [True, False])
def test_sync_lab(cleanup_test_labs, client_library_session: ClientLibrary, sync: bool):
    # TODO: figure out what this is, add asserts and document
    lab = create_lab(client_library_session, ["server"] * 3)

    for node in lab.nodes():
        node.start()
    for node in lab.nodes():
        node.stop()
        node.wipe()

    for link in lab.links():
        lab.remove_link(link)
    for node in lab.nodes():
        lab.remove_node(node)

    assert not lab.nodes()
    assert not lab.interfaces()
    assert not lab.links()

    lab.remove()


def test_import(register_licensing, cleanup_test_labs, client_library_session: ClientLibrary):
    # TODO: split into multiple cases - import lab, start/stop/wipe, add/remove nodes/interfaces/links
    lab = client_library_session.import_sample_lab("server-triangle.yaml")
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


def test_link_removal(cleanup_test_labs, client_library_session: ClientLibrary):
    lab = create_lab(client_library_session, ["server"] * 3)

    lab.remove_node(lab.nodes()[0])
    assert len(lab.nodes()) == 2
    assert len(lab.interfaces()) == 3
    assert len(lab.links()) == 1

    lab.remove_node(lab.nodes()[0])
    assert len(lab.nodes()) == 1
    assert len(lab.interfaces()) == 1
    assert not lab.links()


def test_server_node_deletion(cleanup_test_labs, client_library_session: ClientLibrary):
    lab = create_lab(client_library_session, ["server"] * 3)
    s3 = lab.nodes()[2]
    lab.start()

    # can't remove node while running
    with pytest.raises(requests.exceptions.HTTPError) as exc:
        lab.remove_node(s3)
    assert exc.value.response.status_code == 400

    # need to stop and wipe to be able to remove node.
    s3.stop()
    s3.wipe()
    lab.remove_node(s3)


def test_import_sample_lab_yaml(
    cleanup_test_labs, client_library_session: ClientLibrary
):
    lab = client_library_session.import_sample_lab("server-triangle.yaml")
    assert lab is not None
    lab.remove()


def test_import_sample_lab_virl(
    cleanup_test_labs, client_library_session: ClientLibrary
):
    lab = client_library_session.import_sample_lab("dual-server.virl")
    assert lab is not None
    lab.remove()


def test_lab_state(cleanup_test_labs, client_library_session: ClientLibrary):
    lab = create_lab(client_library_session, ["server"] * 2, sync=True)

    assert lab.state() == "DEFINED_ON_CORE"

    lab.start()
    assert lab.state() == "STARTED"

    lab.stop()
    assert lab.state() == "STOPPED"

    lab.wipe()
    assert lab.state() == "DEFINED_ON_CORE"


def test_lab_details(cleanup_test_labs, client_library_session: ClientLibrary):
    lab = create_lab(client_library_session, ["server"] * 2, sync=True)

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


def test_labels_and_tags(cleanup_test_labs, client_library_session: ClientLibrary):
    lab = client_library_session.import_sample_lab("server-triangle.yaml")

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


def test_node_with_unavailable_vnc(
    cleanup_test_labs, client_library_session: ClientLibrary
):
    lab = create_lab(client_library_session, ["unmanaged_switch"], sync=True)
    node = lab.nodes()[0]
    lab.start()
    assert lab.state() == "STARTED"
    with pytest.raises(requests.exceptions.HTTPError) as err:
        node.vnc_key()
    assert err.value.response.status_code == 404
    lab.stop()
    lab.wipe()
    lab.remove()


@pytest.mark.nomock
def test_node_console_logs(cleanup_test_labs, client_library_session: ClientLibrary):
    lab = create_lab(client_library_session, ["external_connector", "server", "iosv"], sync=True)
    ext_conn, server, iosv = lab.nodes()

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


def test_topology_owner(cleanup_test_labs, client_library_session: ClientLibrary):
    lab = client_library_session.create_lab("owned_by_cml2")
    lab.sync(topology_only=True)
    assert lab.owner
    lab.remove()


def test_start_stop_start_stop_cycle(
    cleanup_test_labs, client_library_session: ClientLibrary
):
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
    lab = client_library_session.import_sample_lab("server-triangle.yaml")

    lab.start()
    lab.stop()
    lab.start()
    lab.stop()
    lab.wipe()


def test_links_on_various_slots(
    cleanup_test_labs, client_library_session: ClientLibrary
):
    """
    Create a link between two nodes on higher interfaces,
    then remove the link and re-add a link on lower interfaces.
    """
    lab = create_lab(client_library_session, ["server"] * 2, sync=True)

    # create a link between s1 and s2
    s1, s2 = lab.nodes()
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
    s1_i1, s2_i1 = s1.interfaces()[1], s2.interfaces()[1]
    link = lab.create_link(s1_i1, s2_i1)
    assert link.interface_a.slot == 1
    assert link.interface_b.slot == 1

    # both nodes should have 5 interfaces and all of them must match UUIDv4
    expected_int_list = ["eth0", "eth1", "eth2", "eth3", "eth4"] * 2
    for interface in lab.interfaces():
        assert uuid.UUID(interface.id, version=4)
        expected_int_list.remove(interface.label)

    # create a link between s1 and s2, again on the 4th slot
    s1_i1, s2_i1 = s1.interfaces()[4], s2.interfaces()[4]
    link = lab.create_link(s1_i1, s2_i1)

    assert link.interface_a.slot == 4
    assert link.interface_b.slot == 4

    lab.remove_link(link)


@pytest.mark.xfail(reason="expected failure")
@pytest.mark.nomock
def test_link_conditioning(
    cleanup_test_labs, client_library_session: ClientLibrary, pyats_hostname: str
):
    response_packets = (
        r"(\d+) packets transmitted, (\d+) packets received, (\d+)% packet loss"
    )
    response_roundtrip = r"round-trip min/avg/max = [\d\.]+/([\d\.]+)/[\d\.]+ ms"

    lab = create_lab(client_library_session, ["alpine", "unmanaged_switch", "external_connector"], sync=True)
    lab.start(wait=True)

    alpine, ums = lab.nodes()[:2]
    link = lab.get_link_by_nodes(alpine, ums)

    pylab = ClPyats(lab, hostname=pyats_hostname)
    pylab.sync_testbed(lab.username, lab.password)

    # ensure there's no link condition
    result = link.get_condition()
    assert result is None

    # remove, just to be sure
    link.remove_condition()

    def check_result(result_input, has_loss, min_avg, max_avg):
        rm = re.search(response_packets, result_input, re.MULTILINE)
        assert len(rm.groups()) == 3
        transmitted, received, loss = [int(a) for a in rm.groups()]
        if has_loss:
            assert transmitted != received
            assert loss > 0
        else:
            assert transmitted == received
            assert loss == 0

        rm = re.search(response_roundtrip, result_input, re.MULTILINE)
        assert len(rm.groups()) == 1
        avg = float(rm.group(1))
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


@pytest.mark.nomock
def test_node_shutdown(
    cleanup_test_labs, client_library_session: ClientLibrary, pyats_hostname: str
):
    """Start a lab with one ubuntu node, have the node shut itself down
    then verify the lab is stopped and can be deleted."""

    lab = create_lab(client_library_session, ["ubuntu"], sync=True)
    node1 = lab.nodes()[0]
    lab_id = lab.id

    lab.start(wait=True)

    pyats_instance = ClPyats(lab=lab, hostname=pyats_hostname)
    pyats_instance.sync_testbed(lab.username, lab.password)
    try:
        pyats_instance.run_command(node1.label, "sudo shutdown -h now")
    except SubCommandFailure as e:
        if "TimeoutError" in str(e):
            pass
        else:
            raise

    # May take a few seconds to power off and enter STOPPED state, wait
    for i in range(20):
        if node1.state == "STOPPED" and lab.has_converged():
            break
        else:
            sleep(1)

    # Make sure both the node and lab are in STOPPED state
    assert node1.state == "STOPPED"
    assert lab.state() == "STOPPED"

    # Make sure the lab is not stuck, can be wiped and deleted
    lab.wipe()
    lab.remove()
    assert lab_id not in client_library_session.get_lab_list(show_all=True)
