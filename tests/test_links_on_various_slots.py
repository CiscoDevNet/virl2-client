#
# This file is part of VIRL 2
# Copyright (c) 2019, Cisco Systems, Inc.
# All rights reserved.
#
import pytest

from virl2_client import ClientLibrary


@pytest.mark.integration
def test_links_on_various_slots(client_library: ClientLibrary):
    """
    Creating a link between two nodes on higher interfaces,
    then removing the link and re-adding a link on lower interfaces.
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

    assert list(lab._interfaces.keys()) == ['i0', 'i1', 'i2', 'i3', 'i4', 'i5', 'i6', 'i7', 'i8', 'i9']
    assert [ifc.label for ifc in lab.interfaces()] == ['eth0', 'eth1', 'eth2', 'eth3', 'eth4', 'eth0', 'eth1', 'eth2', 'eth3', 'eth4']
    # create a link between s1 and s2, again on the 4th slot
    s1_i1 = s1.create_interface(slot=4)
    s2_i1 = s2.create_interface(slot=4)
    link = lab.create_link(s1_i1, s2_i1)

    assert link.interface_a.slot == 4
    assert link.interface_b.slot == 4

    lab.remove_link(link)
