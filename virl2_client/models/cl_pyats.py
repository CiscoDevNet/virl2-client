#
# This file is part of VIRL 2
# Copyright (c) 2019-2023, Cisco Systems, Inc.
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

from __future__ import annotations

import io
from typing import TYPE_CHECKING

from ..exceptions import PyatsDeviceNotFound, PyatsNotInstalled

if TYPE_CHECKING:
    from .lab import Lab
    from genie.libs.conf.testbed import Testbed
    from genie.libs.conf.device import Device


class ClPyats:
    def __init__(self, lab: Lab, hostname: str | None = None) -> None:
        """
        Create a pyATS object that can be used to run commands
        against a device either in exec mode ``show version`` or in
        configuration mode ``interface gi0/0 \\n no shut``.

        :param lab: The lab object to be used with pyATS.
        :param hostname: Forced hostname or IP address and port of the console
            terminal server. (optional)
        :raises PyatsNotInstalled: If pyATS is not installed.
        :raises PyatsDeviceNotFound: If the device cannot be found.
        """
        self._pyats_installed = False
        self._lab = lab
        self._hostname = hostname
        try:
            import pyats  # noqa: F401
        except ImportError:
            return
        else:
            self._pyats_installed = True
        self._testbed: Testbed | None = None
        self._connections: set[Device] = set()

    @property
    def hostname(self) -> str | None:
        """Return the forced hostname/IP and port terminal server setting."""
        return self._hostname

    @hostname.setter
    def hostname(self, hostname: str | None = None) -> None:
        """
        Set the forced hostname/IP and port terminal server setting.

        :param hostname: The hostname or IP address and port of the console terminal
            server. (optional)
        """
        self._hostname = hostname

    def _check_pyats_installed(self) -> None:
        """
        Check if pyATS is installed and raise an exception if not.

        :raises PyatsNotInstalled: If pyATS is not installed.
        """
        if not self._pyats_installed:
            raise PyatsNotInstalled

    def sync_testbed(self, username: str, password: str) -> None:
        """
        Sync the testbed from the server.
        This fetches the latest topology data from the server.

        :param username: The username to be inserted into the testbed data.
        :param password: The password to be inserted into the testbed data.
        """
        self._check_pyats_installed()
        from pyats.topology import loader

        testbed_yaml = self._lab.get_pyats_testbed(self._hostname)
        data = loader.load(io.StringIO(testbed_yaml))
        data.devices.terminal_server.credentials.default.username = username
        data.devices.terminal_server.credentials.default.password = password
        self._testbed = data

    def _prepare_params(
        self,
        init_exec_commands: list[str] | None = None,
        init_config_commands: list[str] | None = None,
    ) -> dict:
        """
        Prepare a dictionary of optional parameters to be executed before a command.
        None means that default commands will be executed. If you want no commands
        to be executed, pass an empty list instead.

        :param init_exec_commands: A list of exec commands to be executed.
        :param init_config_commands: A list of config commands to be executed.
        :returns: A dictionary of optional parameters to be executed with a command.
        """
        params = {}
        if init_exec_commands:
            params["init_exec_commands"] = init_exec_commands
        if init_config_commands:
            params["init_config_commands"] = init_config_commands
        return params

    def _execute_command(
        self,
        node_label: str,
        command: str,
        configure_mode: bool = False,
        init_exec_commands: list[str] | None = None,
        init_config_commands: list[str] | None = None,
    ) -> str:
        """
        Execute a command on the device.

        :param node_label: The label/title of the device.
        :param command: The command to be executed.
        :param configure_mode: True if the command is to be run in configure mode,
            False for exec mode.
        :param init_exec_commands: A list of exec commands to be executed before the
            command. Optional; default commands will be run if omitted. Pass an empty
            list to run no commands.
        :param init_config_commands: A list of config commands to be executed before the
            command. Optional; default commands will be run if omitted. Pass an empty
            list to run no commands.
        :returns: The output from the device.
        :raises PyatsDeviceNotFound: If the device cannot be found.
        """
        self._check_pyats_installed()

        try:
            pyats_device: Device = self._testbed.devices[node_label]
        except KeyError:
            raise PyatsDeviceNotFound(node_label)

        if pyats_device not in self._connections or not pyats_device.is_connected():
            if pyats_device in self._connections:
                pyats_device.destroy()

            pyats_device.connect(log_stdout=False, learn_hostname=True)
            self._connections.add(pyats_device)
        params = self._prepare_params(init_exec_commands, init_config_commands)
        if configure_mode:
            return pyats_device.configure(command, log_stdout=False, **params)
        else:
            return pyats_device.execute(command, log_stdout=False, **params)

    def run_command(
        self,
        node_label: str,
        command: str,
        init_exec_commands: list[str] | None = None,
        init_config_commands: list[str] | None = None,
    ) -> str:
        """
        Run a command on the device in exec mode.

        :param node_label: The label/title of the device.
        :param command: The command to be run in exec mode.
        :param init_exec_commands: A list of exec commands to be executed before the
         command. Optional; default commands will be run if omitted. Pass an empty
            list to run no commands.
        :param init_config_commands: A list of config commands to be executed before the
            command. Optional; default commands will be run if omitted. Pass an empty
            list to run no commands.
        :returns: The output from the device.
        """
        return self._execute_command(
            node_label,
            command,
            configure_mode=False,
            init_exec_commands=init_exec_commands,
            init_config_commands=init_config_commands,
        )

    def run_config_command(
        self,
        node_label: str,
        command: str,
        init_exec_commands: list[str] | None = None,
        init_config_commands: list[str] | None = None,
    ) -> str:
        """
        Run a command on the device in configure mode. pyATS automatically handles the
        change into configure mode.

        :param node_label: The label/title of the device.
        :param command: The command to be run in configure mode.
        :param init_exec_commands: A list of exec commands to be executed before the
            command. Optional; default commands will be run if omitted. Pass an empty
            list to run no commands.
        :param init_config_commands: A list of config commands to be executed before the
            command. Optional; default commands will be run if omitted. Pass an empty
            list to run no commands.
        :returns: The output from the device.
        """
        return self._execute_command(
            node_label,
            command,
            configure_mode=True,
            init_exec_commands=init_exec_commands,
            init_config_commands=init_config_commands,
        )

    def cleanup(self) -> None:
        """Clean up the pyATS connections."""
        for pyats_device in self._connections:
            pyats_device.destroy()
        self._connections.clear()
