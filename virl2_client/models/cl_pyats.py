#
# Python bindings for the Cisco VIRL 2 Network Simulation Platform
#
# This file is part of VIRL 2
#
# Copyright 2020 Cisco Systems Inc.
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

import io
import logging

logger = logging.getLogger(__name__)


class PyatsNotInstalled(Exception):
    pass


class PyatsDeviceNotFound(Exception):
    pass


class ClPyats:
    """Creates a pyATS object that can be used to run commands
    against a device either in exec mode ``show version`` or in
    configuration mode ``interface gi0/0\\\\nno shut``.

    :param lab: The lab which should be used with pyATS
    :type lab: models.Lab
    :raises PyatsNotInstalled: when pyATS can not be found
    :raises PyatsDeviceNotFound: when the device can not be found
    """
    def __init__(self, lab):
        """Constructor method"""
        self._pyats_installed = False
        self._lab = lab
        try:
            import pyats    # noqa: F401
        except ImportError:
            return
        else:
            self._pyats_installed = True

        self._testbed = None
        self._connections = []

    def _check_pyats_installed(self):
        if not self._pyats_installed:
            raise PyatsNotInstalled

    def sync_testbed(self, username, password):
        """Syncs the the testbed from the server. Note that this
        will always fetch the latest topology data from the server.

        :param username: the username that will be inserted into
            the testbed data
        :type username: str
        :param password: the password that will be inserted into
            the testbed data
        :type password: str
        """
        self._check_pyats_installed()
        from pyats.topology import loader
        testbed_yaml = self._lab.get_pyats_testbed()
        data = loader.load(io.StringIO(testbed_yaml))
        data.devices.terminal_server.connections.cli.username = username
        data.devices.terminal_server.connections.cli.password = password
        self._testbed = data

    def run_command(self, node_label, command):
        """Run a command on the device in exec mode

        :param node_label: the label / title of the device
        :type node_label: str
        :param command: the command to be run in exec mode
        :type command: str
        :returns: The output from the device
        :rtype: str
        """
        self._check_pyats_installed()

        try:
            pyats_device = self._testbed.devices[node_label]
        except KeyError:
            raise PyatsDeviceNotFound(node_label)

        # TODO: later check if connected
        # TODO: later look at pooling connections
        pyats_device.connect(log_stdout=False)
        self._connections.append(pyats_device)
        return pyats_device.execute(command, log_stdout=False)

    def run_config_command(self, node_label, command):
        """Run a command on the device in configure mode. pyATS
        handles the change into configure mode automatically.

        :param node_label: the label / title of the device
        :type node_label: str
        :param command: the command to be run in exec mode
        :type command: str
        :returns: The output from the device
        :rtype: str
        """
        self._check_pyats_installed()

        try:
            pyats_device = self._testbed.devices[node_label]
        except KeyError:
            raise PyatsDeviceNotFound(node_label)

        # TODO: later check if connected
        # TODO: later look at pooling connections
        pyats_device.connect(log_stdout=False)
        self._connections.append(pyats_device)
        return pyats_device.configure(command, log_stdout=False)

    def cleanup(self):
        """cleans up the pyATS connections"""
        for pyats_device in self._connections:
            pyats_device.destroy()
