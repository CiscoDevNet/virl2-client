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

from __future__ import annotations

import io
from pathlib import Path
from typing import TYPE_CHECKING, Any

try:
    from pyats.topology.loader.base import TestbedFileLoader as _PyatsTFLoader
    from pyats.topology.loader.markup import TestbedMarkupProcessor as _PyatsTMProcessor
    from pyats.utils.yaml.markup import Processor as _PyatsProcessor
except ImportError:
    _PyatsTFLoader = None
    _PyatsTMProcessor = None
else:
    # Ensure markup processor never uses the command line arguments as that's broken
    _PyatsProcessor.argv.clear()


from ..exceptions import PyatsDeviceNotFound, PyatsNotInstalled

if TYPE_CHECKING:
    from genie.libs.conf.device import Device
    from genie.libs.conf.testbed import Testbed

    from .lab import Lab


class ClPyats:
    def __init__(self, lab: Lab, hostname: str | None = None) -> None:
        """
        Create a pyATS object that can be used to run commands
        against a device either in exec mode ``show version`` or in
        configuration mode ``interface gi0/0 \\n no shut``.

        :param lab: The lab object to be used with pyATS.
        :param hostname: Forced hostname or IP address and port of the console
            terminal server.
        :raises PyatsNotInstalled: If pyATS is not installed.
        :raises PyatsDeviceNotFound: If the device cannot be found.
        """
        self._lab = lab
        self._hostname = hostname
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
            server.
        """
        self._hostname = hostname

    def _check_pyats_installed(self) -> None:
        """
        Check if pyATS is installed and raise an exception if not.

        :raises PyatsNotInstalled: If pyATS is not installed.
        """
        if _PyatsTFLoader is None:
            raise PyatsNotInstalled

    def _load_pyats_testbed(self, testbed_yaml: str) -> Testbed:
        """
        Load a PyATS testbed instance from YAML representation.

        Disable all templating features of PyATS markup processor.
        Also disable extensions loading (which still uses all the templating)
        https://pubhub.devnetcloud.com/media/pyats/docs/utilities/yaml_markup.html
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

    def sync_testbed(self, username: str, password: str) -> None:
        """
        Sync the testbed (the latest topology data) from the server.

        :param username: The username to be inserted into the testbed data.
        :param password: The password to be inserted into the testbed data.
        """
        self._check_pyats_installed()
        testbed_yaml = self._lab.get_pyats_testbed(self._hostname)
        self._testbed = self._load_pyats_testbed(testbed_yaml)
        self.set_termserv_credentials(username, password)

    def set_termserv_credentials(
        self,
        username: str | None = None,
        password: str | None = None,
        key_path: Path | str | None = None,
    ) -> None:
        terminal = self._testbed.devices.terminal_server
        if username is not None:
            terminal.credentials.default.username = username
        if password is not None:
            terminal.credentials.default.password = password
        if key_path is not None:
            ssh_options = f"-o IdentitiesOnly=yes -o IdentityFile={key_path}"
            terminal.connections.cli.ssh_options = ssh_options

    def _prepare_params(
        self,
        init_exec_commands: list[str] | None = None,
        init_config_commands: list[str] | None = None,
        **params: str,
    ) -> dict:
        """
        Prepare a dictionary of optional parameters to be executed before a command.
        None means that default commands will be executed. If you want no commands
        to be executed, pass an empty list instead.

        :param init_exec_commands: A list of exec commands to be executed.
        :param init_config_commands: A list of config commands to be executed.
        :returns: A dictionary of optional parameters to be executed with a command.
        """
        if init_exec_commands is not None:
            params["init_exec_commands"] = init_exec_commands
        if init_config_commands is not None:
            params["init_config_commands"] = init_config_commands
        return params

    def _execute_command(
        self,
        node_label: str,
        command: str,
        configure_mode: bool = False,
        init_exec_commands: list[str] | None = None,
        init_config_commands: list[str] | None = None,
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
        :param pyats_params: Additional PyATS call parameters
        :returns: The output from the device.
        :raises PyatsDeviceNotFound: If the device cannot be found.
        """
        self._check_pyats_installed()

        try:
            pyats_device: Device = self._testbed.devices[node_label]
        except KeyError:
            raise PyatsDeviceNotFound(node_label)

        params = self._prepare_params(
            init_exec_commands, init_config_commands, **pyats_params
        )
        if pyats_device not in self._connections or not pyats_device.is_connected():
            if pyats_device in self._connections:
                pyats_device.destroy()

            pyats_device.connect(log_stdout=False, learn_hostname=True, **params)
            self._connections.add(pyats_device)
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
        :returns: The output from the device.
        """
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
        :returns: The output from the device.
        """
        return self._execute_command(
            node_label,
            command,
            configure_mode=True,
            init_exec_commands=init_exec_commands,
            init_config_commands=init_config_commands,
            **pyats_params,
        )

    def cleanup(self) -> None:
        """Clean up the pyATS connections."""
        for pyats_device in self._connections:
            pyats_device.destroy()
        self._connections.clear()
