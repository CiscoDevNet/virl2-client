"""Lab-focused unit tests for lab properties and core lightweight behaviors."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from helpers import RESOURCE_POOL_MANAGER, make_lab
from respx import MockRouter

from virl2_client.exceptions import VirlException
from virl2_client.models import Lab
from virl2_client.models.authentication import make_session


def test_topology_create_stats() -> None:
    """create nodes/interfaces/links, assert statistics.

    NOTE: LLM-generated test -- verify for correctness.
    """
    lab = make_lab()
    node_a = lab._create_node_local("0", "node A", "nd")
    node_b = lab._create_node_local("1", "node B", "nd")
    node_c = lab._create_node_local("2", "node C", "nd")
    i1 = lab._create_interface_local("0", "iface A", node_a, 0)
    i2 = lab._create_interface_local("1", "iface B1", node_b, 1)
    i3 = lab._create_interface_local("2", "iface B2", node_b, 2)
    i4 = lab._create_interface_local("3", "iface C", node_c, 3)
    lab._create_link_local(i1, i2, "0")
    lab._create_link_local(i3, i4, "1")

    assert set(lab.nodes()) == {node_a, node_b, node_c}
    assert lab.statistics == {
        "annotations": 0,
        "nodes": 3,
        "links": 2,
        "interfaces": 4,
        "smart_annotations": 0,
    }


def test_topology_node_degree() -> None:
    """node degrees and links per node.

    NOTE: LLM-generated test -- verify for correctness.
    """
    lab = make_lab()
    node_a = lab._create_node_local("0", "node A", "nd")
    node_b = lab._create_node_local("1", "node B", "nd")
    node_c = lab._create_node_local("2", "node C", "nd")
    i1 = lab._create_interface_local("0", "iface A", node_a, 0)
    i2 = lab._create_interface_local("1", "iface B1", node_b, 1)
    i3 = lab._create_interface_local("2", "iface B2", node_b, 2)
    i4 = lab._create_interface_local("3", "iface C", node_c, 3)
    lnk1 = lab._create_link_local(i1, i2, "0")
    lnk2 = lab._create_link_local(i3, i4, "1")

    assert node_a.degree() == 1
    assert node_b.degree() == 2
    assert node_c.degree() == 1
    assert node_a.links() == [lnk1]
    assert node_c.links() == [lnk2]


def test_topology_peer_info() -> None:
    """peer interfaces and peer nodes.

    NOTE: LLM-generated test -- verify for correctness.
    """
    lab = make_lab()
    node_a = lab._create_node_local("0", "node A", "nd")
    node_b = lab._create_node_local("1", "node B", "nd")
    node_c = lab._create_node_local("2", "node C", "nd")
    i1 = lab._create_interface_local("0", "iface A", node_a, 0)
    i2 = lab._create_interface_local("1", "iface B1", node_b, 1)
    i3 = lab._create_interface_local("2", "iface B2", node_b, 2)
    i4 = lab._create_interface_local("3", "iface C", node_c, 3)
    lab._create_link_local(i1, i2, "0")
    lab._create_link_local(i3, i4, "1")

    assert i1.peer_interface is i2
    assert i2.peer_interface is i1
    assert i3.peer_interface is i4
    assert i4.peer_interface is i3
    assert i1.peer_node is node_b
    assert i2.peer_node is node_a
    assert i3.peer_node is node_c
    assert i4.peer_node is node_b


def test_topology_link_info() -> None:
    """link nodes and interfaces.

    NOTE: LLM-generated test -- verify for correctness.
    """
    lab = make_lab()
    node_a = lab._create_node_local("0", "node A", "nd")
    node_b = lab._create_node_local("1", "node B", "nd")
    node_c = lab._create_node_local("2", "node C", "nd")
    i1 = lab._create_interface_local("0", "iface A", node_a, 0)
    i2 = lab._create_interface_local("1", "iface B1", node_b, 1)
    i3 = lab._create_interface_local("2", "iface B2", node_b, 2)
    i4 = lab._create_interface_local("3", "iface C", node_c, 3)
    lnk1 = lab._create_link_local(i1, i2, "0")
    lnk2 = lab._create_link_local(i3, i4, "1")

    assert lnk1.nodes == (node_a, node_b)
    assert lnk1.interfaces == (i1, i2)
    assert lnk2.nodes == (node_b, node_c)
    assert lnk2.interfaces == (i3, i4)


def test_topology_removal() -> None:
    """remove elements, assert final stats.

    NOTE: LLM-generated test -- verify for correctness.
    """
    lab = make_lab()
    node_a = lab._create_node_local("0", "node A", "nd")
    node_b = lab._create_node_local("1", "node B", "nd")
    node_c = lab._create_node_local("2", "node C", "nd")
    i1 = lab._create_interface_local("0", "iface A", node_a, 0)
    i2 = lab._create_interface_local("1", "iface B1", node_b, 1)
    i3 = lab._create_interface_local("2", "iface B2", node_b, 2)
    i4 = lab._create_interface_local("3", "iface C", node_c, 3)
    lnk2 = lab._create_link_local(i3, i4, "1")
    lab._create_link_local(i1, i2, "0")

    lab.remove_link(lnk2)
    lab.remove_node(node_b)
    lab.remove_interface(i4)
    lab.remove_interface(i1)
    lab.remove_node(node_a)
    lab.remove_node(node_c)
    assert lab.statistics == {
        "annotations": 0,
        "nodes": 0,
        "links": 0,
        "interfaces": 0,
        "smart_annotations": 0,
    }


@pytest.mark.parametrize(
    ("lab_wait", "local_arg", "expected"),
    [
        (True, None, True),
        (True, False, False),
        (True, True, True),
        (False, None, False),
        (False, False, False),
        (False, True, True),
    ],
)
def test_need_to_wait(lab_wait: bool, local_arg: bool | None, expected: bool) -> None:
    """Resolve wait behavior from lab setting and local override.

    NOTE: LLM-generated test -- verify for correctness.
    """
    lab = make_lab(wait=lab_wait)
    assert lab.need_to_wait(local_arg) is expected


def test_need_to_wait_invalid_type_raises() -> None:
    """Raise ValueError for invalid local wait parameter types.

    NOTE: LLM-generated test -- verify for correctness.
    """
    lab = make_lab()
    with pytest.raises(ValueError):
        lab.need_to_wait("yes")  # type: ignore[arg-type]


def test_str_and_repr() -> None:
    """Return stable string and repr formats.

    NOTE: LLM-generated test -- verify for correctness.
    """
    session = make_session("http://dontcare")
    lab = Lab(
        "laboratory",
        "1",
        session,
        "test",
        "test",
        auto_sync=False,
        wait=False,
        resource_pool_manager=RESOURCE_POOL_MANAGER,
    )
    assert str(lab) == "Lab: laboratory"
    assert repr(lab) == "Lab('1', 'laboratory', '/')"


def test_lab_requires_resource_pool_manager() -> None:
    """Require a resource pool manager in lab constructor.

    NOTE: LLM-generated test -- verify for correctness.
    """
    with pytest.raises(VirlException, match="missing a resource pool manager"):
        Lab("test", "1", MagicMock(), "user", "pass", resource_pool_manager=None)


def test_sync_stats(respx_mock: MockRouter) -> None:
    """Call simulation statistics endpoint for lab statistics sync.

    NOTE: LLM-generated test -- verify for correctness.

    :param respx_mock: HTTPX mock router fixture.
    """
    respx_mock.get("mock://mock/labs/1/simulation_stats").respond(
        json={"nodes": {}, "links": {}}
    )
    session = make_session("mock://mock")
    session.lock = MagicMock()
    lab = Lab(
        "laboratory",
        "1",
        session,
        "test",
        "test",
        auto_sync=False,
        wait=False,
        resource_pool_manager=RESOURCE_POOL_MANAGER,
    )
    lab.sync_statistics()
    respx_mock.assert_all_called()


def test_sync_interfaces_operational(respx_mock: MockRouter) -> None:
    """Populate per-interface operational fields from bulk API response.

    NOTE: LLM-generated test -- verify for correctness.

    :param respx_mock: HTTPX mock router fixture.
    """
    respx_mock.get("mock://mock/labs/1/interfaces").respond(
        json=[{"id": "iface1", "operational": {"mac_address": "aa:bb:cc:dd:ee:ff"}}]
    )
    session = make_session("mock://mock")
    session.lock = MagicMock()
    lab = Lab(
        "test",
        "1",
        session,
        "user",
        "pass",
        auto_sync=False,
        resource_pool_manager=RESOURCE_POOL_MANAGER,
    )
    lab._interfaces = {"iface1": MagicMock()}
    lab.sync_interfaces_operational()
    assert lab._interfaces["iface1"]._operational == {
        "mac_address": "aa:bb:cc:dd:ee:ff"
    }


def test_lab_clear_discovered_addresses(respx_mock: MockRouter) -> None:
    """Clear discovered L3 addresses at lab level through API.

    NOTE: LLM-generated test -- verify for correctness.

    :param respx_mock: HTTPX mock router fixture.
    """
    respx_mock.delete("mock://mock/labs/1/layer3_addresses").respond(status_code=204)
    session = make_session("mock://mock")
    session.lock = MagicMock()
    lab = Lab(
        "test",
        "1",
        session,
        "user",
        "pass",
        auto_sync=False,
        resource_pool_manager=RESOURCE_POOL_MANAGER,
    )
    lab.clear_discovered_addresses()
    respx_mock.assert_all_called()


def test_lab_text_properties() -> None:
    """title, description, notes.

    NOTE: LLM-generated test -- verify for correctness.
    """
    lab = make_lab()
    lab.title = "new-title"
    lab.description = "new-description"
    lab.notes = "new-notes"
    assert lab.title == "new-title"
    assert lab.description == "new-description"
    assert lab.notes == "new-notes"


def test_lab_autostart_staging() -> None:
    """set_autostart and set_node_staging setters and accessors.

    NOTE: LLM-generated test -- verify for correctness.
    """
    lab = make_lab()
    lab.set_autostart(enabled=True, priority=10, delay=1)
    lab.set_node_staging(enabled=True, start_remaining=False, abort_on_failure=True)
    assert lab.autostart == {"enabled": True, "priority": 10, "delay": 1}
    assert lab.node_staging == {
        "enabled": True,
        "start_remaining": False,
        "abort_on_failure": True,
    }


def test_lab_collection_accessors() -> None:
    """nodes, links, interfaces, annotations, smart_annotations length.

    NOTE: LLM-generated test -- verify for correctness.
    """
    lab = make_lab()
    n1 = lab._create_node_local("n1", "n1", "iosv")
    i1 = lab._create_interface_local("i1", "eth0", n1, 0)
    i2 = lab._create_interface_local("i2", "eth1", n1, 1)
    _ = lab._create_link_local(i1, i2, "l1")
    _ = lab._create_annotation_local("a1", "rectangle")
    _ = lab._create_smart_annotation_local("s1", tag="core")

    assert len(lab) == 1
    assert len(lab.nodes()) == 1
    assert len(lab.interfaces()) == 2
    assert len(lab.links()) == 1
    assert len(lab.annotations()) == 1
    assert len(lab.smart_annotations()) == 1
