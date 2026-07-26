#
# This file is part of VIRL 2
# Copyright (c) 2019-2026, Cisco Systems, Inc.
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
"""Tests for ClientLibrary lab operations (join, list, find, import)."""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import MagicMock

import pytest

from tests.helpers import RESOURCE_POOL_MANAGER, USER_MANAGEMENT, make_lab
from virl2_client.exceptions import (
    ElementAlreadyExists,
    InvalidTopologySchema,
    LabNotFound,
)
from virl2_client.models import Lab
from virl2_client.models.authentication import make_session

if TYPE_CHECKING:
    from respx import MockRouter

    from virl2_client.virl2_client import ClientLibrary


def test_join_existing_lab(client_library: ClientLibrary) -> None:
    """Join existing lab and validate imported baseline statistics.

    NOTE: LLM-generated test -- verify for correctness.

    :param client_library: Prepared client fixture.
    :raises AssertionError: If imported data is inconsistent.
    """
    lab = client_library.join_existing_lab("444a78d1-575c-4746-8469-696e580f17b6")
    assert lab.title == "IOSv Feature Tests"
    assert lab.statistics == {
        "annotations": 0,
        "nodes": 7,
        "links": 8,
        "interfaces": 24,
        "smart_annotations": 0,
    }


def test_all_labs_listing(client_library: ClientLibrary) -> None:
    """List all labs returns expected count.

    NOTE: LLM-generated test -- verify for correctness.
    """
    all_labs = client_library.all_labs()
    assert len(all_labs) == 4


def test_find_labs_by_title(client_library: ClientLibrary) -> None:
    """find_labs_by_title filters labs by title.

    NOTE: LLM-generated test -- verify for correctness.
    """
    iosv_labs = client_library.find_labs_by_title("IOSv Feature Tests")
    assert len(iosv_labs) == 1


def test_joined_lab_compute_id(client_library: ClientLibrary) -> None:
    """Joined lab node has compute_id after join.

    NOTE: LLM-generated test -- verify for correctness.
    """
    iosv_labs = client_library.find_labs_by_title("IOSv Feature Tests")
    assert len(iosv_labs) == 1
    assert iosv_labs[0].get_node_by_label("csr1000v-0").compute_id is not None


def test_sync_topology_404_marks_stale_raises(
    respx_mock: MockRouter,
) -> None:
    """Mark lab stale and raise LabNotFound on topology 404.

    NOTE: LLM-generated test -- verify for correctness.

    :param respx_mock: HTTPX mock router fixture.
    :raises AssertionError: If stale flag is not set.
    """
    respx_mock.get("mock://mock/labs/deadbeef/topology").respond(
        status_code=404, text="Lab not found: deadbeef"
    )
    session = make_session("mock://mock")
    lab = Lab(
        "test",
        "deadbeef",
        session,
        "user",
        "pass",
        auto_sync=False,
        resource_pool_manager=RESOURCE_POOL_MANAGER,
        user_management=USER_MANAGEMENT,
    )

    with pytest.raises(LabNotFound):
        lab._sync_topology()
    assert lab._stale is True


def test_import_lab_invalid_schema_raises() -> None:
    """Raise InvalidTopologySchema for incomplete topology payloads.

    NOTE: LLM-generated test -- verify for correctness.

    :raises AssertionError: If expected exception is not raised.
    """
    with pytest.raises(InvalidTopologySchema):
        make_lab()._import_lab({})


@pytest.mark.parametrize(
    ("handler_name", "topology", "existing_attr", "existing_id"),
    [
        ("_handle_import_nodes", {"nodes": [{"id": "n1"}]}, "_nodes", "n1"),
        (
            "_handle_import_interfaces",
            {"interfaces": [{"id": "i1", "node": "n1"}]},
            "_interfaces",
            "i1",
        ),
        (
            "_handle_import_links",
            {"links": [{"id": "l1", "interface_a": "i1", "interface_b": "i2"}]},
            "_links",
            "l1",
        ),
        (
            "_handle_import_annotations",
            {"annotations": [{"id": "a1"}]},
            "_annotations",
            "a1",
        ),
        (
            "_handle_import_annotations",
            {"annotations": [], "smart_annotations": [{"id": "s1"}]},
            "_smart_annotations",
            "s1",
        ),
    ],
)
def test_import_handlers_raise_duplicates(
    handler_name: str, topology: dict, existing_attr: str, existing_id: str
) -> None:
    """Raise ElementAlreadyExists for duplicate import IDs.

    NOTE: LLM-generated test -- verify for correctness.

    :param handler_name: Name of handler method to call.
    :param topology: Topology payload for the handler.
    :param existing_attr: Local lab container attribute to pre-populate.
    :param existing_id: Existing object id to duplicate.
    :raises AssertionError: If duplicate detection does not raise.
    """
    lab = make_lab()
    setattr(lab, existing_attr, {existing_id: MagicMock()})
    if "interfaces" in topology or "links" in topology:
        lab._nodes = {"n1": MagicMock(id="n1")}
        lab._interfaces = {"i1": MagicMock(id="i1"), "i2": MagicMock(id="i2")}
    with pytest.raises(ElementAlreadyExists):
        getattr(lab, handler_name)(topology)
