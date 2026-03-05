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

from unittest.mock import Mock

import pytest
import respx

from virl2_client.models.link import Link


@pytest.fixture
def mock_link() -> Link:
    """Create a mock Link with mocked session for testing.

    :returns: A Link instance with mocked lab, interfaces, and session.
    """
    mock_session = Mock()
    mock_lab = Mock()
    mock_lab._url_for.return_value = "labs/test-lab"
    mock_interface_a = Mock()
    mock_interface_b = Mock()

    link = Link(mock_lab, "test-link", mock_interface_a, mock_interface_b)
    link._session = mock_session
    return link


def test_url_templates_exist() -> None:
    """Test that all required URL templates are defined."""
    required_templates = ["capture_start", "capture_stop", "capture_status"]

    for template in required_templates:
        assert template in Link._URL_TEMPLATES
        assert "{lab}/links/{id}/capture/" in Link._URL_TEMPLATES[template]


@respx.mock
def test_start_capture_with_params(mock_link: Link) -> None:
    """Test start_capture with explicit parameters.

    :param mock_link: Link fixture with mocked session.
    """
    expected_response = {
        "config": {
            "link_capture_key": mock_link.id,
            "maxpackets": 100,
            "encap": "ethernet",
        },
        "starttime": "2026-01-12T10:00:00Z",
        "packetscaptured": 0,
    }

    mock_link._session.put.return_value.json.return_value = expected_response

    result = mock_link.start_capture(maxpackets=100)

    assert result == expected_response
    assert result["config"]["maxpackets"] == 100
    assert result["config"]["link_capture_key"] == mock_link.id


@respx.mock
def test_start_capture_defaults(mock_link: Link) -> None:
    """Test start_capture without parameters uses server defaults.

    :param mock_link: Link fixture with mocked session.
    """
    expected_response = {
        "config": {
            "link_capture_key": mock_link.id,
            "maxpackets": 1000000,
            "maxtime": 86400,
            "encap": "ethernet",
        },
        "starttime": "2026-01-12T10:00:00Z",
        "packetscaptured": 0,
    }

    mock_link._session.put.return_value.json.return_value = expected_response

    result = mock_link.start_capture()

    assert result == expected_response
    assert result["config"]["maxpackets"] == 1000000
    assert result["config"]["maxtime"] == 86400
    assert result["config"]["link_capture_key"] == mock_link.id


@respx.mock
def test_capture_status(mock_link: Link) -> None:
    """Test capture_status with mocked HTTP call.

    :param mock_link: Link fixture with mocked session.
    """
    expected_status = {
        "config": {
            "link_capture_key": mock_link.id,
            "maxpackets": 200,
            "encap": "ethernet",
        },
        "starttime": "2026-01-12T09:30:00Z",
        "packetscaptured": 15,
    }

    mock_link._session.get.return_value.json.return_value = expected_status

    result = mock_link.capture_status()

    assert result == expected_status
    assert result["packetscaptured"] == 15
    assert result["config"]["link_capture_key"] == mock_link.id


@respx.mock
def test_stop_capture(mock_link: Link) -> None:
    """Test stop_capture with mocked HTTP call.

    :param mock_link: Link fixture with mocked session.
    """
    mock_link._session.put.return_value = Mock()

    result = mock_link.stop_capture()

    mock_link._session.put.assert_called_once()
    assert result is None


@respx.mock
def test_download_capture(mock_link: Link) -> None:
    """Test download_capture.

    :param mock_link: Link fixture with mocked session.
    """
    expected_content = b"PCAP file content"
    mock_link._session.get.return_value.content = expected_content

    result = mock_link.download_capture()

    mock_link._session.get.assert_called_once()
    assert result == expected_content


@respx.mock
def test_get_capture_packets(mock_link: Link) -> None:
    """Test get_capture_packets with mocked HTTP call.

    :param mock_link: Link fixture with mocked session.
    """
    expected_packets = [
        {"packet": {"timestamp": "2026-01-12T10:00:01Z", "size": 64}},
        {"packet": {"timestamp": "2026-01-12T10:00:02Z", "size": 128}},
    ]
    mock_link._session.get.return_value.json.return_value = expected_packets

    result = mock_link.get_capture_packets()

    assert result == expected_packets
    assert len(result) == 2


@respx.mock
def test_get_capture_packet(mock_link: Link) -> None:
    """Test download_capture_packet with mocked HTTP call.

    :param mock_link: Link fixture with mocked session.
    """
    # the actual PDML is rather large
    expected_packet_data = {"proto": []}
    mock_link._session.get.return_value.json.return_value = expected_packet_data

    result = mock_link.get_capture_packet(packet_id=5)

    assert result == expected_packet_data
