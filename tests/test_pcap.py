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
"""Tests for link packet-capture API (start, stop, status, download, packets)."""

from unittest.mock import Mock

import pytest

from virl2_client.models.link import Link


@pytest.fixture
def link() -> Link:
    """Create a Link with a mocked session for capture tests.

    :returns: A Link instance with mocked lab, interfaces, and session.
    """
    mock_session = Mock()
    mock_lab = Mock()
    mock_lab._url_for.return_value = "labs/test-lab"
    mock_interface_a = Mock()
    mock_interface_b = Mock()

    lnk = Link(mock_lab, "test-link", mock_interface_a, mock_interface_b)
    lnk._session = mock_session
    return lnk


@pytest.mark.parametrize(
    "template",
    ["capture_start", "capture_stop", "capture_status"],
)
def test_url_template_exists(template: str) -> None:
    """Required URL template is defined on Link.

    NOTE: LLM-generated test -- verify for correctness.
    """
    assert template in Link._URL_TEMPLATES
    assert "{lab}/links/{id}/capture/" in Link._URL_TEMPLATES[template]


@pytest.mark.parametrize(
    ("endpoint", "expected"),
    [
        ("pcap_file", "pcap/test-link"),
        ("pcap_packets", "pcap/test-link/packets"),
    ],
)
def test_pcap_url_is_relative_and_has_no_duplicate_api_prefix(
    link: Link, endpoint: str, expected: str
) -> None:
    """PCAP URLs are relative paths without a duplicate /api/v0/ segment.

    Regression guard for CMLDEV-1117: a previous implementation prepended
    session.base_url (which already ends in /api/v0/) plus "/api/v0/pcap",
    producing malformed URLs like .../api/v0//api/v0/pcap/<id>.
    """
    url = link._url_for(endpoint)

    assert url == expected
    assert "api/v0" not in url
    assert "//" not in url


def test_pcap_packet_url_has_packet_id(link: Link) -> None:
    """pcap_packet URL includes packet id and stays relative to base_url.

    Regression guard for CMLDEV-1117.
    """
    url = link._url_for("pcap_packet", packet_id="42")

    assert url == "pcap/test-link/packets/42"
    assert "api/v0" not in url
    assert "//" not in url


def test_start_capture_with_params(link: Link) -> None:
    """start_capture passes maxpackets, maxtime, and bpfilter to the server.

    NOTE: LLM-generated test -- verify for correctness.

    :param link: Link fixture with mocked session.
    """
    expected_response = {
        "config": {
            "link_capture_key": link.id,
            "maxpackets": 100,
            "maxtime": 300,
            "bpfilter": "tcp port 80",
            "encap": "ethernet",
        },
        "starttime": "2026-01-12T10:00:00Z",
        "packetscaptured": 0,
    }

    link._session.put.return_value.json.return_value = expected_response

    result = link.start_capture(maxpackets=100, maxtime=300, bpfilter="tcp port 80")

    assert result == expected_response
    link._session.put.assert_called_once()
    call_kwargs = link._session.put.call_args
    payload = call_kwargs.kwargs["json"]
    assert payload["maxpackets"] == 100
    assert payload["maxtime"] == 300
    assert payload["bpfilter"] == "tcp port 80"
    assert payload["encap"] == "ethernet"


def test_start_capture_defaults(link: Link) -> None:
    """start_capture without parameters uses server-side defaults.

    NOTE: LLM-generated test -- verify for correctness.

    :param link: Link fixture with mocked session.
    """
    expected_response = {
        "config": {
            "link_capture_key": link.id,
            "maxpackets": 1000000,
            "maxtime": 86400,
            "encap": "ethernet",
        },
        "starttime": "2026-01-12T10:00:00Z",
        "packetscaptured": 0,
    }

    link._session.put.return_value.json.return_value = expected_response

    result = link.start_capture()

    assert result == expected_response
    assert result["config"]["maxpackets"] == 1000000
    assert result["config"]["maxtime"] == 86400
    assert result["config"]["link_capture_key"] == link.id


def test_capture_status(link: Link) -> None:
    """capture_status returns the current capture state from the server.

    NOTE: LLM-generated test -- verify for correctness.

    :param link: Link fixture with mocked session.
    """
    expected_status = {
        "config": {
            "link_capture_key": link.id,
            "maxpackets": 200,
            "encap": "ethernet",
        },
        "starttime": "2026-01-12T09:30:00Z",
        "packetscaptured": 15,
    }

    link._session.get.return_value.json.return_value = expected_status

    result = link.capture_status()

    assert result == expected_status
    assert result["packetscaptured"] == 15
    assert result["config"]["link_capture_key"] == link.id


def test_stop_capture(link: Link) -> None:
    """stop_capture calls PUT once and returns None.

    NOTE: LLM-generated test -- verify for correctness.

    :param link: Link fixture with mocked session.
    """
    link._session.put.return_value = Mock()

    result = link.stop_capture()

    link._session.put.assert_called_once()
    assert result is None


def test_download_capture(link: Link) -> None:
    """download_capture returns the raw bytes of the PCAP file.

    NOTE: LLM-generated test -- verify for correctness.

    :param link: Link fixture with mocked session.
    """
    expected_content = b"PCAP file content"
    link._session.get.return_value.content = expected_content

    result = link.download_capture()

    link._session.get.assert_called_once()
    assert result == expected_content


def test_get_capture_packets(link: Link) -> None:
    """get_capture_packets returns the list of packet summaries.

    NOTE: LLM-generated test -- verify for correctness.

    :param link: Link fixture with mocked session.
    """
    expected_packets = [
        {"packet": {"timestamp": "2026-01-12T10:00:01Z", "size": 64}},
        {"packet": {"timestamp": "2026-01-12T10:00:02Z", "size": 128}},
    ]
    link._session.get.return_value.json.return_value = expected_packets

    result = link.get_capture_packets()

    assert result == expected_packets
    assert len(result) == 2


def test_get_capture_packet(link: Link) -> None:
    """get_capture_packet returns the PDML data for a single packet.

    NOTE: LLM-generated test -- verify for correctness.

    :param link: Link fixture with mocked session.
    """
    expected_packet_data = {"proto": []}
    link._session.get.return_value.json.return_value = expected_packet_data

    result = link.get_capture_packet(packet_id=5)

    assert result == expected_packet_data
