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
"""Tests for the wireless node packet-capture API (start, stop, status, download).

Wireless PCAP is implemented on :class:`~virl2_client.models.node.Node` and
requires CML server >= 2.10.0. REST endpoints:

* start:    ``POST   /wireless/pcap``            (node ID carried in the body)
* stop:     ``DELETE /wireless/pcap/{node_id}``
* status:   ``GET    /wireless/pcap/{node_id}``
* download: ``GET    /wireless/pcap/{node_id}/download``
"""

from unittest.mock import Mock

import httpx
import pytest

from virl2_client.models import Node
from virl2_client.virl2_client import Version


@pytest.fixture
def node() -> Node:
    """Create a Node with a mocked session for capture tests.

    :returns: A Node instance with a mocked lab and session.
    """
    mock_session = Mock()
    mock_session.controller_version = Version("2.10.0")
    mock_lab = Mock()
    mock_lab._url_for.return_value = "labs/test-lab"
    mock_lab._session = mock_session

    nd = Node(mock_lab, "test-node", "wireless-node", "wireless_node")
    nd._session = mock_session
    return nd


@pytest.mark.parametrize(
    ("endpoint", "expected"),
    [
        ("capture_start", "wireless/pcap"),
        ("capture_stop", "wireless/pcap/test-node"),
        ("capture_status", "wireless/pcap/test-node"),
        ("pcap_file", "wireless/pcap/test-node/download"),
    ],
)
def test_wireless_pcap_url_relative_no_dup_prefix(
    node: Node, endpoint: str, expected: str
) -> None:
    """Wireless PCAP URLs are node-keyed relative paths without /api/v0/.

    They are siblings of /api/v0/labs/... so they must not carry the lab prefix
    nor a duplicate /api/v0/ segment.

    NOTE: LLM-generated test -- verify for correctness.
    """
    url = node._url_for(endpoint)

    assert url == expected
    assert "api/v0" not in url
    assert "//" not in url
    assert "labs/" not in url


def test_start_capture_posts_with_node_id(node: Node) -> None:
    """start_capture POSTs the parameters plus the node ID as the session key.

    NOTE: LLM-generated test -- verify for correctness.
    """
    expected_response = "PCAP started for node test-node"
    node._session.post.return_value.json.return_value = expected_response

    result = node.start_capture(maxpackets=100, maxtime=300, bpfilter="tcp port 80")

    assert result == expected_response
    node._session.post.assert_called_once()
    call = node._session.post.call_args
    assert call.args[0] == "wireless/pcap"
    payload = call.kwargs["json"]
    assert payload["node_id"] == node.id
    assert payload["maxpackets"] == 100
    assert payload["maxtime"] == 300
    assert payload["bpfilter"] == "tcp port 80"
    assert payload["encap"] == "ethernet"


def test_start_capture_defaults(node: Node) -> None:
    """start_capture omits unset optional params but always sends node_id and encap.

    NOTE: LLM-generated test -- verify for correctness.
    """
    node._session.post.return_value.json.return_value = "ok"

    node.start_capture(maxpackets=100)

    payload = node._session.post.call_args.kwargs["json"]
    assert payload == {"encap": "ethernet", "node_id": node.id, "maxpackets": 100}


def test_capture_status(node: Node) -> None:
    """capture_status GETs the node-keyed status endpoint.

    NOTE: LLM-generated test -- verify for correctness.
    """
    expected_status = {
        "config": {"node_id": node.id, "maxpackets": 200, "encap": "ethernet"},
        "starttime": "2026-01-12T09:30:00Z",
        "packetscaptured": 15,
    }
    node._session.get.return_value.json.return_value = expected_status

    result = node.capture_status()

    assert result == expected_status
    node._session.get.assert_called_once_with("wireless/pcap/test-node")


def test_stop_capture_uses_delete(node: Node) -> None:
    """stop_capture issues a DELETE on the node-keyed endpoint and returns None.

    NOTE: LLM-generated test -- verify for correctness.
    """
    result = node.stop_capture()

    node._session.delete.assert_called_once_with("wireless/pcap/test-node")
    node._session.put.assert_not_called()
    assert result is None


def test_stop_capture_ignores_404(node: Node) -> None:
    """stop_capture treats a 404 as success when no capture session is active.

    NOTE: LLM-generated test -- verify for correctness.
    """
    response = Mock(status_code=httpx.codes.NOT_FOUND)
    node._session.delete.side_effect = httpx.HTTPStatusError(
        "not found",
        request=Mock(),
        response=response,
    )

    assert node.stop_capture() is None


def test_download_capture(node: Node) -> None:
    """download_capture returns the raw bytes from the node download endpoint.

    NOTE: LLM-generated test -- verify for correctness.
    """
    expected_content = b"PCAP file content"
    node._session.get.return_value.content = expected_content

    result = node.download_capture()

    node._session.get.assert_called_once_with("wireless/pcap/test-node/download")
    assert result == expected_content
