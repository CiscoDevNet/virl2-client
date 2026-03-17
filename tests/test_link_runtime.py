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
"""Link runtime tests for properties, conditions and packet capture APIs."""

from __future__ import annotations

from unittest.mock import patch

import pytest
from helpers import make_lab_with_topology

from virl2_client.models.link import Link


def _new_link() -> Link:
    """Create a local link object with two nodes/interfaces.

    :returns: Local link instance connected between two synthetic nodes.
    """
    return make_lab_with_topology().link


def test_link_state_stats() -> None:
    """state, readbytes, readpackets, writebytes, writepackets.

    NOTE: LLM-generated test -- verify for correctness.
    """
    link = _new_link()
    link.statistics = {
        "readbytes": 1,
        "readpackets": 2,
        "writebytes": 3,
        "writepackets": 4,
    }
    link._session.get.return_value.json.return_value = {"state": "started"}
    assert link.state == "started"
    assert link.readbytes == 1
    assert link.readpackets == 2
    assert link.writebytes == 3
    assert link.writepackets == 4


def test_link_nodes_and_interfaces() -> None:
    """nodes[0].id, interfaces[0].id.

    NOTE: LLM-generated test -- verify for correctness.
    """
    link = _new_link()
    assert link.nodes[0].id == "n1"
    assert link.interfaces[0].id == "i1"


def test_link_as_dict() -> None:
    """as_dict returns id and interface ids.

    NOTE: LLM-generated test -- verify for correctness.
    """
    link = _new_link()
    assert link.as_dict() == {"id": "l1", "interface_a": "i1", "interface_b": "i2"}


@pytest.mark.parametrize("method", ["start", "stop"])
def test_link_method_waits(method: str) -> None:
    """start/stop with wait=True call wait_until_converged.

    NOTE: LLM-generated test -- verify for correctness.
    """
    link = _new_link()
    with patch.object(link, "wait_until_converged") as wait:
        getattr(link, method)(wait=True)
        wait.assert_called_once()


def test_link_remove() -> None:
    """_remove_on_server and remove.

    NOTE: LLM-generated test -- verify for correctness.
    """
    link = _new_link()
    link._remove_on_server()
    link.remove()


def test_link_set_condition() -> None:
    """set_condition filters unknown, sets known params.

    NOTE: LLM-generated test -- verify for correctness.
    """
    link = _new_link()
    link.set_condition(
        bandwidth=1000,
        latency=50,
        jitter=1,
        loss=0.1,
        enabled=True,
        delay_corr=10,
        unknown_param=123,
    )
    payload = link._session.patch.call_args.kwargs["json"]
    assert "unknown_param" not in payload
    assert payload["bandwidth"] == 1000


def test_link_get_condition() -> None:
    """get_condition returns session JSON.

    NOTE: LLM-generated test -- verify for correctness.
    """
    link = _new_link()
    link._session.get.return_value.json.return_value = {"enabled": True}
    assert link.get_condition() == {"enabled": True}


def test_link_remove_condition() -> None:
    """remove_condition calls session delete.

    NOTE: LLM-generated test -- verify for correctness.
    """
    link = _new_link()
    link.remove_condition()
    link._session.delete.assert_called_once()


def test_link_eq_other_type() -> None:
    """Link eq with non-Link returns False.

    NOTE: LLM-generated test -- verify for correctness.
    """
    link = _new_link()
    assert (link == object()) is False


def test_link_lab_accessor() -> None:
    """Link lab.id returns lab id.

    NOTE: LLM-generated test -- verify for correctness.
    """
    link = _new_link()
    assert link.lab.id == "l1"


def test_link_repr() -> None:
    """repr includes Link class name.

    NOTE: LLM-generated test -- verify for correctness.
    """
    link = _new_link()
    assert "Link(" in repr(link)


def test_link_label_none() -> None:
    """Link label is None when unset.

    NOTE: LLM-generated test -- verify for correctness.
    """
    link = _new_link()
    assert link.label is None


def test_link_has_converged() -> None:
    """has_converged returns server response.

    NOTE: LLM-generated test -- verify for correctness.
    """
    link = _new_link()
    link._session.get.return_value.json.return_value = True
    assert link.has_converged() is True


def test_link_wait_converged() -> None:
    """wait_until_converged when converged.

    NOTE: LLM-generated test -- verify for correctness.
    """
    link = _new_link()
    with patch.object(link, "has_converged", return_value=True):
        link.wait_until_converged(max_iterations=1, wait_time=0)


def test_link_set_condition_by_name() -> None:
    """set_condition_by_name delegates to set_condition.

    NOTE: LLM-generated test -- verify for correctness.
    """
    link = _new_link()
    with patch.object(link, "set_condition") as set_condition:
        link.set_condition_by_name("dsl2")
        set_condition.assert_called_with(bandwidth=8000, latency=40, loss=0.5)
