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
"""Tests for pyATS integration: ClPyats model and node credential handling."""

from __future__ import annotations

import logging
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from tests.helpers import make_lab
from virl2_client.exceptions import PyatsDeviceNotFound, PyatsNotInstalled
from virl2_client.models import Node, cl_pyats
from virl2_client.models.cl_pyats import (
    ClPyats,
    _analyze_execute_failure,
    _remove_unicon_loggers,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _device() -> MagicMock:
    """Create a mocked pyATS device model with common nested attributes.

    :returns: Mocked pyATS device object.
    """
    dev = MagicMock()
    dev.connectionmgr.connections = SimpleNamespace(cli=MagicMock())
    dev.connectionmgr.connections.cli.spawn.fd = 1
    dev.connections = {
        "a": {"command": "telnet 10"},
        "cli": SimpleNamespace(ssh_options=""),
    }
    dev.is_connected.return_value = True
    return dev


# ---------------------------------------------------------------------------
# ClPyats model tests
# ---------------------------------------------------------------------------


def test_cl_pyats_importerror_branch() -> None:
    """Execute module import fallback path when pyATS dependencies are absent.

    NOTE: LLM-generated test -- verify for correctness.
    """
    module_path = Path(cl_pyats.__file__)
    source = module_path.read_text()
    source = source.replace(
        "from pyats.topology.loader.base", "from definitely_missing_pyats"
    )
    namespace: dict[str, object] = {
        "__name__": "virl2_client.models.tmp_cl_pyats",
        "__package__": "virl2_client.models",
        "__file__": str(module_path),
    }
    exec(compile(source, str(module_path), "exec"), namespace)
    assert namespace["_PyatsTFLoader"] is None
    assert namespace["_UConnectionError"] is None


def test_cl_pyats_hostname() -> None:
    """Get and set hostname.

    NOTE: LLM-generated test -- verify for correctness.
    """
    lab = MagicMock()
    pyats = ClPyats(lab, hostname="term:2222")
    assert pyats.hostname == "term:2222"
    pyats.hostname = "other:3000"
    assert pyats.hostname == "other:3000"


def test_cl_pyats_not_installed() -> None:
    """Raise PyatsNotInstalled when _PyatsTFLoader is None.

    NOTE: LLM-generated test -- verify for correctness.
    """
    pyats = ClPyats(MagicMock())
    with (
        patch("virl2_client.models.cl_pyats._PyatsTFLoader", None),
        pytest.raises(PyatsNotInstalled),
    ):
        pyats._check_pyats_installed()


def test_cl_pyats_load_testbed() -> None:
    """Load testbed from YAML.

    NOTE: LLM-generated test -- verify for correctness.
    """
    lab = MagicMock()
    pyats = ClPyats(lab)
    loader = MagicMock()
    loader.load.return_value = {"tb": "ok"}
    with (
        patch(
            "virl2_client.models.cl_pyats._PyatsTMProcessor", return_value=MagicMock()
        ),
        patch("virl2_client.models.cl_pyats._PyatsTFLoader", return_value=loader),
    ):
        assert pyats._load_pyats_testbed("devices: {}") == {"tb": "ok"}


@pytest.mark.parametrize(
    ("args", "expected"),
    [
        pytest.param(("u", "p"), ("u", "p"), id="password"),
        pytest.param(("u", None), ("u", None), id="password-none"),
        pytest.param(("u",), ("u", None), id="password-omitted"),
        pytest.param(
            ("u", "jwt-token-placeholder"),
            ("u", "jwt-token-placeholder"),
            id="password-jwt",
        ),
    ],
)
def test_cl_pyats_sync_testbed(args: tuple, expected: tuple) -> None:
    """Sync credentials into testbed.

    The password parameter is optional; None is forwarded to
    set_termserv_credentials so the testbed YAML default is preserved.
    A JWT string is forwarded verbatim (the SSH console server
    interprets it).

    NOTE: LLM-generated test -- verify for correctness.
    """
    lab = MagicMock()
    pyats = ClPyats(lab)
    with (
        patch.object(pyats, "_check_pyats_installed"),
        patch.object(pyats, "_load_pyats_testbed", return_value=MagicMock()) as load_tb,
        patch.object(pyats, "set_termserv_credentials") as set_creds,
    ):
        lab.get_pyats_testbed.return_value = "yaml-data"
        pyats.sync_testbed(*args)
        load_tb.assert_called_once_with("yaml-data")
        set_creds.assert_called_once_with(*expected)


def test_cl_pyats_switch_console() -> None:
    """Switch serial console updates connection command.

    NOTE: LLM-generated test -- verify for correctness.
    """
    lab = MagicMock()
    pyats = ClPyats(lab)
    dev = _device()
    devices = type("Devices", (dict,), {"terminal_server": MagicMock()})({"n1": dev})
    pyats._testbed = MagicMock(devices=devices)
    with patch.object(pyats, "_check_pyats_installed"):
        pyats.switch_serial_console("n1", 5)
        assert dev.connections["a"]["command"].endswith("5")


def test_cl_pyats_switch_missing() -> None:
    """Raise PyatsDeviceNotFound for missing device.

    NOTE: LLM-generated test -- verify for correctness.
    """
    lab = MagicMock()
    pyats = ClPyats(lab)
    devices = type("Devices", (dict,), {"terminal_server": MagicMock()})({})
    pyats._testbed = MagicMock(devices=devices)
    with (
        patch.object(pyats, "_check_pyats_installed"),
        pytest.raises(PyatsDeviceNotFound),
    ):
        pyats.switch_serial_console("missing", 1)


def test_cl_pyats_set_termserv_creds() -> None:
    """Set termserv credentials with key_path and ssh_options.

    NOTE: LLM-generated test -- verify for correctness.
    """
    lab = MagicMock()
    pyats = ClPyats(lab)
    terminal = MagicMock()
    terminal.connections = SimpleNamespace(cli=SimpleNamespace(ssh_options=""))
    devices = type("Devices", (dict,), {"terminal_server": terminal})()
    pyats._testbed = MagicMock(devices=devices)
    with patch.object(pyats, "_check_pyats_installed"):
        pyats.set_termserv_credentials(
            "u", "p", key_path="/tmp/key", ssh_options="-o X"
        )
        assert terminal.credentials.default.username == "u"
        assert terminal.credentials.default.password == "p"
        assert "IdentityFile=/tmp/key" in terminal.connections.cli.ssh_options


def test_cl_pyats_prepare_params() -> None:
    """_prepare_params returns init_exec_commands, init_config_commands, timeout.

    NOTE: LLM-generated test -- verify for correctness.
    """
    pyats = ClPyats(MagicMock())
    params = pyats._prepare_params(["term len 0"], [], timeout=5)
    assert params["init_exec_commands"] == ["term len 0"]
    assert params["init_config_commands"] == []
    assert params["timeout"] == 5


def test_cl_pyats_is_connected() -> None:
    """_is_connected branches: not in set, in set fd=1, fd=0, no cli.

    NOTE: LLM-generated test -- verify for correctness.
    """
    pyats = ClPyats(MagicMock())
    dev = _device()
    assert pyats._is_connected(dev) is False
    pyats._connections.add(dev)
    assert pyats._is_connected(dev) is True
    dev.connectionmgr.connections.cli.spawn.fd = 0
    assert pyats._is_connected(dev) is False
    dev.connectionmgr.connections = SimpleNamespace()
    assert pyats._is_connected(dev) is False


def test_cl_pyats_reconnect_noop() -> None:
    """_reconnect when connected does not call destroy.

    NOTE: LLM-generated test -- verify for correctness.
    """
    pyats = ClPyats(MagicMock())
    dev = _device()
    with (
        patch.object(pyats, "_is_connected", return_value=True),
        patch.object(pyats, "_destroy_device") as destroy,
    ):
        pyats._reconnect(dev, {})
        destroy.assert_not_called()


def test_cl_pyats_reconnect_acts() -> None:
    """_reconnect when disconnected calls destroy and clear_logs.

    NOTE: LLM-generated test -- verify for correctness.
    """
    pyats = ClPyats(MagicMock())
    dev = _device()
    with (
        patch.object(pyats, "_is_connected", return_value=False),
        patch.object(pyats, "_destroy_device") as destroy,
        patch("virl2_client.models.cl_pyats._remove_unicon_loggers") as clear_logs,
    ):
        pyats._reconnect(dev, {"timeout": 5})
        destroy.assert_called_once_with(dev, raise_exc=False)
        clear_logs.assert_called_once_with(dev)


def test_cl_pyats_execute_success() -> None:
    """Execute and configure-mode success.

    NOTE: LLM-generated test -- verify for correctness.
    """
    pyats = ClPyats(MagicMock())
    dev = _device()
    pyats._testbed = MagicMock(devices={"n1": dev})
    with (
        patch.object(pyats, "_check_pyats_installed"),
        patch.object(pyats, "_reconnect"),
        patch.object(pyats, "_prepare_params", return_value={"x": 1}),
    ):
        dev.execute.return_value = "ok"
        assert pyats._execute_command("n1", "show version") == "ok"
        dev.configure.return_value = "cfg-ok"
        assert (
            pyats._execute_command("n1", "hostname x", configure_mode=True) == "cfg-ok"
        )


def test_cl_pyats_execute_no_testbed() -> None:
    """Raise RuntimeError when testbed is None.

    NOTE: LLM-generated test -- verify for correctness.
    """
    pyats = ClPyats(MagicMock())
    pyats._testbed = None
    with patch.object(pyats, "_check_pyats_installed"), pytest.raises(RuntimeError):
        pyats._execute_command("n1", "x")


def test_cl_pyats_execute_missing_dev() -> None:
    """Raise PyatsDeviceNotFound for missing device.

    NOTE: LLM-generated test -- verify for correctness.
    """
    pyats = ClPyats(MagicMock())
    pyats._testbed = MagicMock(devices={})
    with (
        patch.object(pyats, "_check_pyats_installed"),
        pytest.raises(PyatsDeviceNotFound),
    ):
        pyats._execute_command("missing", "x")


def test_cl_pyats_reconnect_raises() -> None:
    """Raise ValueError when reconnect fails.

    NOTE: LLM-generated test -- verify for correctness.
    """
    pyats = ClPyats(MagicMock())
    dev = _device()
    pyats._testbed = MagicMock(devices={"n1": dev})
    with (
        patch.object(pyats, "_check_pyats_installed"),
        patch.object(pyats, "_reconnect", side_effect=ValueError("boom")),
        patch(
            "virl2_client.models.cl_pyats._analyze_execute_failure",
            return_value=(True, None),
        ),
        pytest.raises(ValueError),
    ):
        pyats._execute_command("n1", "x")


def test_cl_pyats_execute_retry_ok() -> None:
    """Transient failure then retry success.

    NOTE: LLM-generated test -- verify for correctness.
    """
    pyats = ClPyats(MagicMock())
    dev = _device()
    pyats._testbed = MagicMock(devices={"n1": dev})
    with (
        patch.object(pyats, "_check_pyats_installed"),
        patch.object(pyats, "_reconnect"),
        patch.object(pyats, "_prepare_params", return_value={}),
        patch(
            "virl2_client.models.cl_pyats._analyze_execute_failure",
            return_value=(False, "reconnect"),
        ),
    ):
        dev.execute.side_effect = [Exception("transient"), "ok-after-retry"]
        assert pyats._execute_command("n1", "x") == "ok-after-retry"


def test_cl_pyats_execute_retry_fail() -> None:
    """Retry still fails and raises.

    NOTE: LLM-generated test -- verify for correctness.
    """
    pyats = ClPyats(MagicMock())
    dev = _device()
    pyats._testbed = MagicMock(devices={"n1": dev})
    with (
        patch.object(pyats, "_check_pyats_installed"),
        patch.object(pyats, "_reconnect"),
        patch.object(pyats, "_prepare_params", return_value={}),
        patch(
            "virl2_client.models.cl_pyats._analyze_execute_failure",
            return_value=(False, "retry"),
        ),
    ):
        dev.execute.side_effect = Exception("still failing")
        with pytest.raises(Exception, match="still failing"):
            pyats._execute_command("n1", "x", _retry_attempted=True)


def test_cl_pyats_run_wrappers() -> None:
    """run_command and run_config_command delegate to _execute_command.

    NOTE: LLM-generated test -- verify for correctness.
    """
    pyats = ClPyats(MagicMock())
    with patch.object(pyats, "_execute_command", return_value="ok") as exec_cmd:
        assert pyats.run_command("n1", "show x") == "ok"
        assert pyats.run_config_command("n1", "hostname x") == "ok"
        assert exec_cmd.call_count == 2


def test_cl_pyats_cleanup_all() -> None:
    """Cleanup destroys all connected devices.

    NOTE: LLM-generated test -- verify for correctness.
    """
    pyats = ClPyats(MagicMock())
    dev1 = _device()
    dev2 = _device()
    pyats._connections = {dev1, dev2}
    with patch.object(pyats, "_destroy_device") as destroy:
        pyats.cleanup()
        assert destroy.call_count == 2


def test_cl_pyats_cleanup_no_testbed() -> None:
    """Cleanup when testbed is None does not raise.

    NOTE: LLM-generated test -- verify for correctness.
    """
    pyats = ClPyats(MagicMock())
    pyats._testbed = None
    pyats.cleanup("n1")


def test_cl_pyats_cleanup_missing_dev() -> None:
    """Cleanup for non-existent device does not raise.

    NOTE: LLM-generated test -- verify for correctness.
    """
    pyats = ClPyats(MagicMock())
    pyats._testbed = MagicMock(devices={})
    pyats.cleanup("missing")


def test_cl_pyats_cleanup_specific() -> None:
    """Cleanup specific device destroys only that device.

    NOTE: LLM-generated test -- verify for correctness.
    """
    pyats = ClPyats(MagicMock())
    dev1 = _device()
    pyats._testbed = MagicMock(devices={"n1": dev1})
    pyats._connections = {dev1}
    with patch.object(pyats, "_destroy_device") as destroy:
        pyats.cleanup("n1")
        destroy.assert_called_once_with(dev1)


def test_cl_pyats_destroy_device() -> None:
    """_destroy_device removes device from connections.

    NOTE: LLM-generated test -- verify for correctness.
    """
    pyats = ClPyats(MagicMock())
    dev1 = _device()
    pyats._connections = {dev1}
    pyats._destroy_device(dev1)
    assert dev1 not in pyats._connections


def test_cl_pyats_destroy_raises() -> None:
    """_destroy_device raise_exc=True propagates; raise_exc=False swallows.

    NOTE: LLM-generated test -- verify for correctness.
    """
    pyats = ClPyats(MagicMock())
    dev2 = _device()
    pyats._connections = {dev2}
    dev2.destroy.side_effect = RuntimeError("boom")
    with pytest.raises(RuntimeError):
        pyats._destroy_device(dev2, raise_exc=True)
    pyats._destroy_device(dev2, raise_exc=False)


@pytest.mark.parametrize(
    "case,should_raise,reason_substr",
    [
        ("connection_error", False, "ConnectionError"),
        ("timeout", False, "TimeoutError"),
        ("value_error", True, None),
    ],
)
def test_analyze_execute_failure(
    case: str, should_raise: bool, reason_substr: str | None
) -> None:
    """_analyze_execute_failure handles ConnectionError, SubCmdErr, ValueError.

    NOTE: LLM-generated test -- verify for correctness.
    """

    class ConnErr(Exception):
        pass

    class SubCmdErr(Exception):
        pass

    with (
        patch("virl2_client.models.cl_pyats._UConnectionError", ConnErr),
        patch("virl2_client.models.cl_pyats._USubCommandFailure", SubCmdErr),
    ):
        if case == "connection_error":
            got_raise, reason = _analyze_execute_failure(ConnErr("x"))
        elif case == "timeout":
            exc = SubCmdErr("x")
            exc.__cause__ = TimeoutError("t")
            got_raise, reason = _analyze_execute_failure(exc)
        else:
            got_raise, reason = _analyze_execute_failure(ValueError("x"))
        assert got_raise is should_raise
        if reason_substr is not None:
            assert reason_substr in reason
        else:
            assert reason is None


def test_remove_unicon_loggers() -> None:
    """_remove_unicon_loggers normal path and error path (no connectionmgr).

    NOTE: LLM-generated test -- verify for correctness.
    """
    dev = _device()
    dev.connectionmgr.connections = {
        "cli": SimpleNamespace(log=SimpleNamespace(name="unicon.terminal_server.conn"))
    }
    logging.root.manager.loggerDict["unicon.terminal_server.conn"] = MagicMock()
    _remove_unicon_loggers(dev)

    _remove_unicon_loggers(SimpleNamespace(connectionmgr=None))


# ---------------------------------------------------------------------------
# Node-level pyATS credential tests
# ---------------------------------------------------------------------------


@pytest.fixture
def pyats_session() -> MagicMock:
    """Return a mocked HTTP session used by Lab/Node instances.

    :returns: Mocked HTTP session object.
    """
    return MagicMock()


@pytest.fixture
def node(request: pytest.FixtureRequest, pyats_session: MagicMock) -> Node:
    """Create a Node (and Lab) for a given initial pyATS mapping.

    The parametrized value for this fixture (via indirect=["node"])
    is interpreted as the initial pyats dict or None.

    :param request: Fixture request object with optional parametrized payload.
    :param pyats_session: Mocked HTTP session fixture.
    :returns: Node instance bound to a synthetic lab.
    """
    initial_pyats: dict | None = getattr(request, "param", None)
    lab = make_lab(session=pyats_session)
    node_kwargs = {"pyats": initial_pyats} if initial_pyats is not None else {}
    return Node(
        lab,
        "node-id",
        "node1",
        "node-type",
        **node_kwargs,
    )


@pytest.mark.parametrize(
    "node, initial_pyats, expected_pyats",
    [
        (None, {}, {"username": None, "password": None, "enable_password": None}),
        (
            None,
            {"username": "pyuser"},
            {"username": "pyuser", "password": None, "enable_password": None},
        ),
        (
            None,
            {"password": "pypass"},
            {"username": None, "password": "pypass", "enable_password": None},
        ),
        (
            None,
            {"username": "pyuser", "password": "pypass"},
            {"username": "pyuser", "password": "pypass", "enable_password": None},
        ),
        (
            None,
            {"enable_password": "enpass"},
            {"username": None, "password": None, "enable_password": "enpass"},
        ),
        (
            {"username": "u", "password": "p"},
            {"username": None, "password": None},
            {"username": None, "password": None},
        ),
        (
            {"username": "old", "password": "p"},
            {"username": "new"},
            {"username": "new", "password": "p"},
        ),
        (
            {"username": "u", "password": "old"},
            {"password": "new"},
            {"username": "u", "password": "new"},
        ),
        (
            {"username": "u", "password": "p"},
            {"username": None},
            {"username": None, "password": "p"},
        ),
        (
            {"username": "u", "password": "p"},
            {"password": None},
            {"username": "u", "password": None},
        ),
        (
            {"username": "u", "password": "p", "enable_password": None},
            {"enable_password": "enpass"},
            {"username": "u", "password": "p", "enable_password": "enpass"},
        ),
        (
            {"username": "u", "password": "p", "enable_password": "enpass"},
            {"enable_password": None},
            {"username": "u", "password": "p", "enable_password": None},
        ),
    ],
    ids=[
        "default",
        "set_username_only",
        "set_password_only",
        "set_both",
        "set_enable_password_only",
        "clear_both",
        "change_username_only",
        "change_password_only",
        "set_username_none",
        "set_password_none",
        "set_enable_password_from_existing",
        "clear_enable_password",
    ],
    indirect=["node"],
)
def test_node_pyats_credentials(
    pyats_session: MagicMock,
    node: Node,
    initial_pyats: dict[str, str | None],
    expected_pyats: dict[str, str | None],
) -> None:
    """Verify pyATS credential updates, including None handling.

    NOTE: LLM-generated test -- verify for correctness.

    :param pyats_session: Mocked HTTP session fixture.
    :param node: Parametrized node fixture.
    :param initial_pyats: Input pyATS credential update mapping.
    :param expected_pyats: Expected node pyATS state after update.
    """
    if initial_pyats:
        node.set_pyats_credentials(**initial_pyats)

    assert node.pyats_credentials == expected_pyats

    if not initial_pyats:
        pyats_session.patch.assert_not_called()
        return

    pyats_session.patch.assert_called_once_with(
        "labs/l1/nodes/node-id?exclude_configurations=false",
        json={"pyats": expected_pyats},
    )
