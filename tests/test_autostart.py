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
"""Tests for lab autostart configuration."""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, Mock

import pytest

from virl2_client.models import Lab

RESOURCE_POOL_MANAGER = Mock()


def conditional_side_effect(*args: Any, **kwargs: Any) -> None:
    """Side-effect for session.patch that validates autostart fields in json payload.

    :param args: Unused positional args from patch call.
    :param kwargs: Keyword args; uses ``json`` to validate autostart.enabled, priority, delay.
    """
    _ = args
    resp = kwargs.get("json", {})
    if autostart := resp.get("autostart"):
        if not isinstance(autostart.get("enabled"), bool):
            raise ValueError("Invalid value for enabled")
        if priority := autostart.get("priority"):
            if not isinstance(priority, int) or not 0 <= priority <= 10000:
                raise ValueError("Invalid value for priority")
        if delay := autostart.get("delay"):
            if not isinstance(delay, int) or not 0 <= delay <= 86400:
                raise ValueError("Invalid value for delay")


def test_autostart_initial_values() -> None:
    """Test that new lab has correct initial autostart values."""
    session = MagicMock()
    lab = Lab(
        "test_lab",
        "1",
        session,
        "user",
        "pass",
        auto_sync=False,
        resource_pool_manager=RESOURCE_POOL_MANAGER,
    )
    assert lab._autostart == {"enabled": False, "priority": None, "delay": None}


def test_lab_autostart_setter() -> None:
    """Test setting the autostart parameter on a Lab instance."""
    session = MagicMock()
    lab = Lab(
        title="Test Lab",
        lab_id="lab-id",
        session=session,
        username="user",
        password="pass",
        auto_sync=False,
        resource_pool_manager=RESOURCE_POOL_MANAGER,
    )

    lab.set_autostart(enabled=True, priority=5, delay=10)
    assert lab.autostart == {"enabled": True, "priority": 5, "delay": 10}
    session.patch.assert_called_once_with(
        "labs/lab-id", json={"autostart": {"enabled": True, "priority": 5, "delay": 10}}
    )


def test_lab_autostart_setter_invalid() -> None:
    """Test setting invalid autostart parameters raises ValueError."""
    session = MagicMock()
    session.patch.side_effect = conditional_side_effect
    lab = Lab(
        title="Test Lab",
        lab_id="lab-id",
        session=session,
        username="user",
        password="pass",
        auto_sync=False,
        resource_pool_manager=RESOURCE_POOL_MANAGER,
    )

    with pytest.raises(ValueError):
        lab.set_autostart(enabled="yes", priority=5, delay=10)
    with pytest.raises(ValueError):
        lab.set_autostart(enabled=True, priority="yes", delay=10)
    with pytest.raises(ValueError):
        lab.set_autostart(enabled=True, priority=-1, delay=10)
    with pytest.raises(ValueError):
        lab.set_autostart(enabled=True, priority=10001, delay=10)
    with pytest.raises(ValueError):
        lab.set_autostart(enabled=True, priority=5, delay="yes")
    with pytest.raises(ValueError):
        lab.set_autostart(enabled=True, priority=5, delay=-10)
    with pytest.raises(ValueError):
        lab.set_autostart(enabled=True, priority=5, delay=86401)


def test_lab_autostart_setter_no_change() -> None:
    """Test that setting autostart to the same value does not trigger an API call."""
    session = MagicMock()
    lab = Lab(
        title="Test Lab",
        lab_id="lab-id",
        session=session,
        username="user",
        password="pass",
        auto_sync=False,
        resource_pool_manager=RESOURCE_POOL_MANAGER,
    )
    lab._autostart = {"enabled": True, "priority": 5, "delay": 10}

    lab.set_autostart()
    session.patch.assert_not_called()

    lab.set_autostart(enabled=True, priority=5, delay=10)
    session.patch.assert_called()


def test_lab_autostart_setter_partial_update() -> None:
    """Test that setting only some autostart parameters updates correctly."""
    session = MagicMock()
    lab = Lab(
        title="Test Lab",
        lab_id="lab-id",
        session=session,
        username="user",
        password="pass",
        auto_sync=False,
        resource_pool_manager=RESOURCE_POOL_MANAGER,
    )
    lab._autostart = {"enabled": False, "priority": None, "delay": None}

    lab.set_autostart(enabled=True)
    assert lab.autostart == {"enabled": True, "priority": None, "delay": None}
    session.patch.assert_called_with(
        "labs/lab-id",
        json={"autostart": {"enabled": True, "priority": None, "delay": None}},
    )

    lab.set_autostart(priority=7)
    assert lab.autostart == {"enabled": True, "priority": 7, "delay": None}
    session.patch.assert_called_with(
        "labs/lab-id",
        json={"autostart": {"enabled": True, "priority": 7, "delay": None}},
    )

    lab.set_autostart(delay=15)
    assert lab.autostart == {"enabled": True, "priority": 7, "delay": 15}
    session.patch.assert_called_with(
        "labs/lab-id", json={"autostart": {"enabled": True, "priority": 7, "delay": 15}}
    )
