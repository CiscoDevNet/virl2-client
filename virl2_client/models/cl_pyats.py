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
"""Deprecated pyATS/Unicon integration for running commands on lab devices.

.. deprecated::
    This module is deprecated and will be removed in a future release.
    ``pyats`` is no longer a dependency of ``virl2_client`` (optional or
    otherwise) -- it must be installed separately for this module to be
    functional. New code should use
    :meth:`~virl2_client.models.node.Node.run_cli_command` instead, which
    requires CML server >= 2.11.0 and runs commands server-side via Unicon
    without needing pyATS/Unicon installed locally.
"""

from __future__ import annotations

import io
import logging
import os
import warnings
from typing import TYPE_CHECKING, Any

try:
    from pyats.topology.loader.base import TestbedFileLoader as _PyatsTFLoader
    from pyats.topology.loader.markup import TestbedMarkupProcessor as _PyatsTMProcessor
    from pyats.utils.yaml.markup import Processor as _PyatsProcessor
    from unicon.core.errors import ConnectionError as _UConnectionError
    from unicon.core.errors import SubCommandFailure as _USubCommandFailure
except ImportError:
    _PyatsTFLoader = None
    _PyatsTMProcessor = None
    _UConnectionError = None
    _USubCommandFailure = None
else:
    # Ensure markup processor never uses the command line arguments as that's broken
    _PyatsProcessor.argv.clear()


from ..exceptions import PyatsDeviceNotFound, PyatsNotInstalled
from ..utils import Version

if TYPE_CHECKING:
    from pathlib import Path

    from genie.libs.conf.device import Device
    from genie.libs.conf.testbed import Testbed

    from .lab import Lab


_LOGGER = logging.getLogger(__name__)

# Do not use any identity keys and agents with the terminal server
# by default - the keys would be attempted before password, and may
# exhaust the number of allowed attempts at the server
# to use ssh keys, set the specific key path or set empty ssh_options
DEFAULT_SSH_OPTIONS = "-o IdentitiesOnly=yes -o IdentityAgent=none"

# CML 2.11.0 introduced POST /labs/{lab_id}/nodes/{node_id}/cli. Frozen for the
# pyATS deprecation stack — not advanced for later releases (2.12, 2.13, …).
# Any connected controller >= this version delegates to the server-side CLI API.
SERVER_CLI_API_MIN_VERSION = Version("2.11.0")
SERVER_CLI_API_MIN_VERSION_STR = "2.11.0"

_PYATS_DEPRECATION_MESSAGE = (
    "pyATS/Unicon integration (ClPyats, Lab.pyats, "
    "Node.run_pyats_command/run_pyats_config_command) is "
    "deprecated and will be removed in a future release. pyats "
    "is no longer bundled as a virl2_client dependency and must "
    "be installed separately if you still need this functionality."
)

_RUN_PYATS_USE_CLI_MESSAGE = (
    "Node.run_pyats_command() and Node.run_pyats_config_command() are "
    "deprecated; use Node.run_cli_command() instead."
)


def warn_pyats_deprecated(cl_pyats: ClPyats, stacklevel: int = 2) -> None:
    """Emit a DeprecationWarning once per :class:`ClPyats` instance (per lab)."""
    if cl_pyats._deprecation_warned:
        return
    cl_pyats._deprecation_warned = True
    warnings.warn(
        _PYATS_DEPRECATION_MESSAGE,
        DeprecationWarning,
        stacklevel=stacklevel,
    )


def warn_run_pyats_use_cli(cl_pyats: ClPyats, stacklevel: int = 2) -> None:
    """Advise :meth:`~virl2_client.models.node.Node.run_cli_command` on CML >= 2.11.

    Emitted once per :class:`ClPyats` instance when the deprecated node helpers
    are used against a controller that exposes the server-side CLI API.
    """
    if cl_pyats._run_pyats_cli_warned:
        return
    cl_pyats._run_pyats_cli_warned = True
    warnings.warn(
        _RUN_PYATS_USE_CLI_MESSAGE,
        DeprecationWarning,
        stacklevel=stacklevel,
    )


class ClPyats:
    """PyATS/Unicon integration for running commands against lab devices.

    .. deprecated::
        This module and class are deprecated and will be removed in a
        future release. ``pyats`` is no longer a dependency (optional or
        otherwise) of ``virl2_client`` -- install it separately in your
        own environment if you still need this functionality. New code
        should use :meth:`~virl2_client.models.node.Node.run_cli_command`
        instead, which requires CML server >= 2.11.0 and runs commands
        server-side via Unicon without needing pyATS/Unicon installed
        locally.
    """

    def __init__(self, lab: Lab, hostname: str | None = None) -> None:
        """
        Create a pyATS object that can be used to run commands
        against a device either in exec mode show version or in
        configuration mode interface gi0/0 \\n no shut.

        .. deprecated::
            Use :meth:`Node.run_cli_command` instead (requires CML server
            >= 2.11.0).

        :param lab: The lab object to be used with pyATS.
        :param hostname: Forced hostname or IP address and port of the console
            terminal server.
        """
        self._lab = lab
        self._hostname = hostname
        self._testbed: Testbed | None = None
        self._connections: set[Device] = set()
        self._deprecation_warned = False
        self._run_pyats_cli_warned = False
        self._serial_ports: dict[str, int] = {}

    @property
    def hostname(self) -> str | None:
        """Return the forced hostname/IP and port terminal server setting.

        :returns: Terminal server host override, or None when unset.
        """
        return self._hostname

    @hostname.setter
    def hostname(self, hostname: str | None = None) -> None:
        """
        Set the forced hostname/IP and port terminal server setting.

        :param hostname: The hostname or IP address and port of the console terminal
            server.
        """
        self._hostname = hostname

    def serial_port_for(self, node_label: str) -> int:
        """Return the serial console index selected for *node_label* (default 0)."""
        return self._serial_ports.get(node_label, 0)

    def _check_pyats_installed(self) -> None:
        """
        Check if pyATS is installed and raise an exception if not.

        :raises PyatsNotInstalled: If pyATS is not installed.
        """
        if _PyatsTFLoader is None:
            raise PyatsNotInstalled(
                "pyATS is not installed. pyats is no longer bundled as a "
                "virl2_client dependency; install it separately "
                "(e.g. `pip install pyats unicon`) if you still need this "
                "functionality, or switch to Node.run_cli_command() instead "
                "(requires CML server >= 2.11.0 and needs no local pyATS "
                "install)."
            )

    def _load_pyats_testbed(self, testbed_yaml: str) -> Testbed:
        """
        Load a PyATS testbed instance from YAML representation.

        Disable all templating features of PyATS markup processor.
        Also disable extensions loading (which still uses all the templating)
        https://pubhub.devnetcloud.com/media/pyats/docs/utilities/yaml_markup.html

        :param testbed_yaml: Testbed document in YAML format.
        :returns: Parsed pyATS testbed object.
        """
        processor = _PyatsTMProcessor(
            reference=True,
            callable=False,
            env_var=False,
            include_file=False,
            ask=False,
            encode=False,
            cli_var=False,
            extend_list=False,
        )
        loader = _PyatsTFLoader(markupprocessor=processor, enable_extensions=False)
        return loader.load(io.StringIO(testbed_yaml))

    def sync_testbed(self, username: str, password: str | None = None) -> None:
        """
        Sync the testbed (the latest topology data) from the server.

        :param username: The username to be inserted into the testbed data.
        :param password: The password or a JWT token to be inserted into
            the testbed data. Passing a JWT avoids creating a new token
            per SSH session and requires a CML 2.11.0 (or newer)
            controller that accepts JWTs as SSH passwords. When None
            (the default), the existing terminal-server password in the
            testbed YAML is left unchanged; call set_termserv_credentials
            to set credentials later.
        :raises PyatsNotInstalled: If pyATS is not installed.
        """
        self._check_pyats_installed()
        testbed_yaml = self._lab.get_pyats_testbed(self._hostname)
        self._testbed = self._load_pyats_testbed(testbed_yaml)
        self.set_termserv_credentials(username, password)

    def switch_serial_console(self, node_label: str, console_number: int | str) -> None:
        """
        Switch to different serial console that is used to execute PyAts commands
        should be executed after sync_testbed
        and re-executed after every sync_testbed call.

        On CML 2.11.0+ controllers the selection is recorded for
        :meth:`~virl2_client.models.node.Node.run_cli_command` delegation from
        the deprecated pyATS node helpers; no local pyATS testbed is required.

        :param node_label: The label/title of the device.
        :param console_number: The serial console number to be used for PyAts.
        :raises PyatsDeviceNotFound: If the device cannot be found.
        :raises PyatsNotInstalled: If pyATS is not installed.
        """
        self._serial_ports[node_label] = int(console_number)
        if self._lab._session.controller_version < SERVER_CLI_API_MIN_VERSION:
            warn_pyats_deprecated(self, stacklevel=2)
            self._check_pyats_installed()
            if self._testbed is None:
                raise RuntimeError("pyATS testbed is not initialized")

            try:
                pyats_device: Device = self._testbed.devices[node_label]
            except KeyError:
                raise PyatsDeviceNotFound(node_label) from None

            command = pyats_device.connections["a"]["command"]
            pyats_device.connections["a"]["command"] = command[:-1] + str(
                console_number
            )

    def set_termserv_credentials(
        self,
        username: str | None = None,
        password: str | None = None,
        key_path: Path | str | None = None,
        ssh_options: str = DEFAULT_SSH_OPTIONS,
    ) -> None:
        """
        Configure how to connect to the SSH terminal server after the testbed
        was synced with the server; the username must be known before making
        any connections. Then either set the password, or path to an identity
        file if SSH authentication with public keys is set up on the server.
        By default, this function disables authentication agents and identity
        files that would be loaded from the environment and running user ssh
        configuration, so that the passed password or key is attempted first.
        Pass empty string or custom SSH options to override this behavior.

        :param username: The username to be set.
        :param password: The password to be set.
        :param key_path: The SSH key path to be set.
        :param ssh_options: SSH options passed to terminal server connection.
        :raises PyatsNotInstalled: If pyATS is not installed.
        """
        self._check_pyats_installed()
        terminal = self._testbed.devices.terminal_server
        if username is not None:
            terminal.credentials.default.username = username
        if password is not None:
            terminal.credentials.default.password = password
            terminal.connections.cli.ssh_options = ssh_options
        if key_path is not None:
            ssh_options += f" -o IdentityFile={key_path}"
        terminal.connections.cli.ssh_options = ssh_options

    def _prepare_params(
        self,
        init_exec_commands: list[str] | None = None,
        init_config_commands: list[str] | None = None,
        **params: Any,
    ) -> dict[str, Any]:
        """
        Prepare a dictionary of optional parameters to be executed before a command.
        None means that default commands will be executed. If you want no commands
        to be executed, pass an empty list instead.

        :param init_exec_commands: A list of exec commands to be executed.
        :param init_config_commands: A list of config commands to be executed.
        :param params: Additional PyATS parameters to pass through.
        :returns: A dictionary of optional parameters to be executed with a command.
        """
        if init_exec_commands is not None:
            params["init_exec_commands"] = init_exec_commands
        if init_config_commands is not None:
            params["init_config_commands"] = init_config_commands
        return params

    def _is_connected(self, pyats_device: Device) -> bool:
        """Check whether a pyATS device is currently connected.

        :param pyats_device: Device instance to inspect.
        :returns: True when the device has an active CLI spawn handle.
        """
        if pyats_device not in self._connections or not pyats_device.is_connected():
            return False
        try:
            spawn = pyats_device.connectionmgr.connections.cli.spawn
            return bool(spawn.fd)
        except (TypeError, AttributeError):
            return False

    def _reconnect(self, pyats_device: Device, params: dict[str, Any]) -> None:
        """Reconnect a pyATS device with cleanup around connect calls.

        :param pyats_device: Device instance to reconnect.
        :param params: Connect/init command parameters.
        """
        if self._is_connected(pyats_device):
            return
        self._destroy_device(pyats_device, raise_exc=False)
        try:
            pyats_device.connect(
                logfile=os.devnull, log_stdout=False, learn_hostname=True, **params
            )
        finally:
            _remove_unicon_loggers(pyats_device)
        self._connections.add(pyats_device)

    def _execute_command(
        self,
        node_label: str,
        command: str,
        configure_mode: bool = False,
        init_exec_commands: list[str] | None = None,
        init_config_commands: list[str] | None = None,
        _retry_attempted: bool = False,
        **pyats_params: Any,
    ) -> str:
        """
        Execute a command on the device.

        :param node_label: The label/title of the device.
        :param command: The command to be executed.
        :param configure_mode: True if the command is to be run in configure mode,
            False for exec mode.
        :param init_exec_commands: A list of exec commands to be executed
            before the command. Default commands will be run if omitted.
            Pass an empty list to run no commands.
        :param init_config_commands: A list of config commands to be executed
            before the command. Default commands will be run if omitted.
            Pass an empty list to run no commands.
        :param _retry_attempted: Internal guard to avoid infinite reconnect retries.
        :param pyats_params: Additional PyATS call parameters.
        :returns: The output from the device.
        :raises PyatsDeviceNotFound: If the device cannot be found.
        :raises PyatsNotInstalled: If pyATS is not installed.
        :raises RuntimeError: If the pyATS testbed is not initialized.
        """
        self._check_pyats_installed()

        if self._testbed is None:
            raise RuntimeError("pyATS testbed is not initialized")

        try:
            pyats_device: Device = self._testbed.devices[node_label]
        except KeyError:
            raise PyatsDeviceNotFound(node_label) from None

        params = self._prepare_params(
            init_exec_commands, init_config_commands, **pyats_params
        )

        try:
            self._reconnect(pyats_device, params)
            if configure_mode:
                return pyats_device.configure(command, log_stdout=False, **params)
            return pyats_device.execute(command, log_stdout=False, **params)
        except Exception as exc:
            should_raise, retry_reason = _analyze_execute_failure(exc)

            if _retry_attempted or should_raise:
                raise

            _LOGGER.info(
                "PyATS command failed on node %s, retrying after reconnection. Reason: %s",
                node_label,
                retry_reason,
            )
            return self._execute_command(
                node_label,
                command,
                configure_mode,
                init_exec_commands,
                init_config_commands,
                _retry_attempted=True,
                **pyats_params,
            )

    def run_command(
        self,
        node_label: str,
        command: str,
        init_exec_commands: list[str] | None = None,
        init_config_commands: list[str] | None = None,
        **pyats_params: Any,
    ) -> str:
        """
        Run a command on the device in exec mode.

        :param node_label: The label/title of the device.
        :param command: The command to be run in exec mode.
        :param init_exec_commands: A list of exec commands to be executed
            before the command. Default commands will be run if omitted.
            Pass an empty list to run no commands.
        :param init_config_commands: A list of config commands to be executed
            before the command. Default commands will be run if omitted.
            Pass an empty list to run no commands.
        :param pyats_params: Additional PyATS call parameters
        :raises PyatsDeviceNotFound: If the device cannot be found.
        :raises PyatsNotInstalled: If pyATS is not installed.
        :returns: The output from the device.
        """
        warn_pyats_deprecated(self, stacklevel=2)
        return self._execute_command(
            node_label,
            command,
            configure_mode=False,
            init_exec_commands=init_exec_commands,
            init_config_commands=init_config_commands,
            **pyats_params,
        )

    def run_config_command(
        self,
        node_label: str,
        command: str,
        init_exec_commands: list[str] | None = None,
        init_config_commands: list[str] | None = None,
        **pyats_params: Any,
    ) -> str:
        """
        Run a command on the device in configure mode. pyATS automatically handles the
        change into configure mode.

        :param node_label: The label/title of the device.
        :param command: The command to be run in configure mode.
        :param init_exec_commands: A list of exec commands to be executed
            before the command. Default commands will be run if omitted.
            Pass an empty list to run no commands.
        :param init_config_commands: A list of config commands to be executed
            before the command. Default commands will be run if omitted.
            Pass an empty list to run no commands.
        :param pyats_params: Additional PyATS call parameters
        :raises PyatsDeviceNotFound: If the device cannot be found.
        :raises PyatsNotInstalled: If pyATS is not installed.
        :returns: The output from the device.
        """
        warn_pyats_deprecated(self, stacklevel=2)
        return self._execute_command(
            node_label,
            command,
            configure_mode=True,
            init_exec_commands=init_exec_commands,
            init_config_commands=init_config_commands,
            **pyats_params,
        )

    def cleanup(self, node_label: str | None = None) -> None:
        """
        Clean up pyATS connections.

        :param node_label: The label/title of a specific node to cleanup.
            If None, all connections will be cleaned up.
        """
        if node_label is None:
            for pyats_device in tuple(self._connections):
                self._destroy_device(pyats_device)
            return
        if self._testbed is None:
            return
        try:
            pyats_device: Device = self._testbed.devices[node_label]
        except KeyError:
            return
        if pyats_device in self._connections:
            self._destroy_device(pyats_device)

    def _destroy_device(self, pyats_device: Device, raise_exc: bool = True) -> None:
        """Destroy a device connection and forget local tracking state.

        :param pyats_device: Device instance to destroy.
        :param raise_exc: Re-raise destroy exceptions when True.
        """
        try:
            pyats_device.destroy()
        except Exception:
            if raise_exc:
                raise
        finally:
            self._connections.discard(pyats_device)


def _analyze_execute_failure(exc: Exception) -> tuple[bool, str | None]:
    """Classify command failures to decide whether retry is safe.

    :param exc: Exception raised during command execution.
    :returns: Tuple (should_raise, retry_reason).
    """
    should_raise = True
    retry_reason = None

    if _UConnectionError and isinstance(exc, _UConnectionError):
        should_raise = False
        retry_reason = f"ConnectionError: {exc}"
    elif _USubCommandFailure and isinstance(exc, _USubCommandFailure):
        cause = getattr(exc, "__cause__", None)
        if isinstance(cause, TimeoutError):
            should_raise = False
            retry_reason = f"SubCommandFailure with TimeoutError cause: {cause}"
    return should_raise, retry_reason


def _remove_unicon_loggers(pyats_device: Device) -> None:
    """Prevent unicon logger instances and placeholders from accumulating.

    :param pyats_device: Device with active/previous unicon connections.
    """
    loggers = logging.root.manager.loggerDict
    try:
        names = {
            con.log.name for con in pyats_device.connectionmgr.connections.values()
        }
        names.update(
            name for name in loggers if name.startswith("unicon.terminal_server.")
        )
    except (AttributeError, TypeError, KeyError):
        return
    for name in names:
        current_name = name
        while current_name.startswith("unicon."):
            loggers.pop(current_name, None)
            current_name = current_name.rsplit(".", 1)[0]
