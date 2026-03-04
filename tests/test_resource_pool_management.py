"""Tests for ResourcePoolManagement synchronization and resource pool creation."""

from __future__ import annotations

from unittest.mock import MagicMock

from virl2_client.models.resource_pool import ResourcePoolManagement


def test_rp_management_sync() -> None:
    """sync_resource_pools loads pools from server.

    NOTE: LLM-generated test -- verify for correctness.
    """
    session = MagicMock()
    mgr = ResourcePoolManagement(session, auto_sync=False)

    session.get.return_value.json.return_value = [
        {
            "id": "p1",
            "label": "pool1",
            "description": "d",
            "template": None,
            "licenses": 1,
            "ram": 2,
            "cpus": 3,
            "disk_space": 4,
            "external_connectors": [],
            "users": [],
            "user_pools": [],
        }
    ]
    mgr.sync_resource_pools()
    assert "p1" in mgr.resource_pools


def test_rp_management_get_by_ids() -> None:
    """get_resource_pools_by_ids returns pool by id or dict with None for missing.

    NOTE: LLM-generated test -- verify for correctness.
    """
    session = MagicMock()
    mgr = ResourcePoolManagement(session, auto_sync=False)

    session.get.return_value.json.return_value = [
        {
            "id": "p1",
            "label": "pool1",
            "description": "d",
            "template": None,
            "licenses": 1,
            "ram": 2,
            "cpus": 3,
            "disk_space": 4,
            "external_connectors": [],
            "users": [],
            "user_pools": [],
        }
    ]
    mgr.sync_resource_pools()
    assert mgr.get_resource_pools_by_ids("p1").label == "pool1"
    assert mgr.get_resource_pools_by_ids(["p1", "missing"])["missing"] is None


def test_rp_management_create() -> None:
    """create_resource_pool creates a single pool.

    NOTE: LLM-generated test -- verify for correctness.
    """
    session = MagicMock()
    mgr = ResourcePoolManagement(session, auto_sync=False)

    session.get.return_value.json.return_value = []
    mgr.sync_resource_pools()

    session.post.return_value.json.return_value = {
        "id": "p2",
        "label": "pool2",
        "description": "x",
        "template": None,
        "licenses": 1,
        "ram": 2,
        "cpus": 3,
        "disk_space": 4,
        "external_connectors": [],
        "users": [],
        "user_pools": [],
    }
    created = mgr.create_resource_pool("pool2", description="x")
    assert created.id == "p2"


def test_rp_management_create_batch() -> None:
    """create_resource_pools creates template and user pools in batch.

    NOTE: LLM-generated test -- verify for correctness.
    """
    session = MagicMock()
    mgr = ResourcePoolManagement(session, auto_sync=False)

    session.post.return_value.json.return_value = [
        {
            "id": "template",
            "label": "tmpl",
            "description": "x",
            "template": None,
            "licenses": 1,
            "ram": 2,
            "cpus": 3,
            "disk_space": 4,
            "external_connectors": [],
            "users": [],
            "user_pools": ["u1"],
        },
        {
            "id": "upool-u1",
            "label": "u1",
            "description": "x",
            "template": "template",
            "licenses": 1,
            "ram": 2,
            "cpus": 3,
            "disk_space": 4,
            "external_connectors": [],
            "users": ["u1"],
            "user_pools": [],
        },
    ]
    pools = mgr.create_resource_pools("tmpl", ["u1"])
    assert len(pools) == 2
