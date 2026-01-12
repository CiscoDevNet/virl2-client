#
# This file is part of VIRL 2
# Copyright (c) 2019-2025, Cisco Systems, Inc.
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
def mock_link():
    """Create a mock link with mocked session for testing."""
    mock_session = Mock()
    mock_lab = Mock()
    mock_lab._url_for.return_value = "labs/test-lab"
    mock_interface_a = Mock()
    mock_interface_b = Mock()

    link = Link(mock_lab, "test-link", mock_interface_a, mock_interface_b)
    link._session = mock_session
    return link


def test_url_templates_exist():
    """Test that all required URL templates are defined."""
    required_templates = [
        "capture_start",
        "capture_stop",
        "capture_status",
        "capture_key",
    ]

    for template in required_templates:
        assert template in Link._URL_TEMPLATES
        assert "{lab}/links/{id}/capture/" in Link._URL_TEMPLATES[template]


@respx.mock
def test_start_capture_with_params(mock_link):
    """Test start_capture with explicit parameters."""
    expected_response = {
        "config": {
            "link_capture_key": "test-key-123",
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
    assert "link_capture_key" in result["config"]


@respx.mock
def test_start_capture_defaults(mock_link):
    """Test start_capture without parameters uses server defaults."""
    expected_response = {
        "config": {
            "link_capture_key": "default-key-456",
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


@respx.mock
def test_capture_status(mock_link):
    """Test capture_status with mocked HTTP call."""
    expected_status = {
        "config": {
            "link_capture_key": "status-key-456",
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


@respx.mock
def test_capture_key(mock_link):
    """Test capture_key with mocked HTTP call."""
    expected_key = "capture-key-789"
    mock_link._session.get.return_value.json.return_value = expected_key

    result = mock_link.capture_key()

    assert result == expected_key


@respx.mock
def test_stop_capture(mock_link):
    """Test stop_capture with mocked HTTP call."""
    mock_link._session.put.return_value = Mock()

    result = mock_link.stop_capture()

    mock_link._session.put.assert_called_once()
    assert result is None


@respx.mock
def test_download_capture_auto_key(mock_link):
    """Test download_capture with automatic key retrieval."""

    def mock_get_side_effect(url):
        mock_response = Mock()
        if "capture/key" in url:
            mock_response.json.return_value = "auto-retrieved-key"
        else:
            mock_response.content = b"PCAP file content"
        return mock_response

    mock_link._session.get.side_effect = mock_get_side_effect

    result = mock_link.download_capture()

    assert result == b"PCAP file content"
    assert mock_link._session.get.call_count == 2


@respx.mock
def test_get_capture_packets(mock_link):
    """Test get_capture_packets with mocked HTTP call."""
    expected_packets = [
        {"packet": {"timestamp": "2026-01-12T10:00:01Z", "size": 64}},
        {"packet": {"timestamp": "2026-01-12T10:00:02Z", "size": 128}},
    ]

    def mock_get_side_effect(url):
        mock_response = Mock()
        if "capture/key" in url:
            mock_response.json.return_value = "packet-key-123"
        else:
            mock_response.json.return_value = expected_packets
        return mock_response

    mock_link._session.get.side_effect = mock_get_side_effect

    result = mock_link.get_capture_packets()

    assert result == expected_packets
    assert len(result) == 2


@respx.mock
def test_download_capture_packet(mock_link):
    """Test download_capture_packet with mocked HTTP call."""
    expected_packet_data = {
        "packet": {"timestamp": "2026-01-12T10:00:05Z", "size": 256}
    }

    def mock_get_side_effect(url):
        mock_response = Mock()
        if "capture/key" in url:
            mock_response.json.return_value = "packet-download-key"
        else:
            mock_response.json.return_value = expected_packet_data
        return mock_response

    mock_link._session.get.side_effect = mock_get_side_effect

    result = mock_link.download_capture_packet(packet_id=5)

    assert result == expected_packet_data
