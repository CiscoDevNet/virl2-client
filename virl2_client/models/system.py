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

import logging
import time
from typing import TYPE_CHECKING, Any, Optional

if TYPE_CHECKING:
    import httpx

_LOGGER = logging.getLogger(__name__)


class SystemManagement:
    def __init__(self, session: httpx.Client, auto_sync=True, auto_sync_interval=1.0):
        self._session = session
        self.auto_sync = auto_sync
        self.auto_sync_interval = auto_sync_interval
        self._last_sync_compute_host_time = 0.0
        self._last_sync_system_notice_time = 0.0
        self._compute_hosts: dict[str, ComputeHost] = {}
        self._system_notices: dict[str, SystemNotice] = {}
        self._maintenance_mode = False
        self._maintenance_notice: Optional[SystemNotice] = None

    @property
    def session(self) -> httpx.Client:
        return self._session

    @property
    def compute_hosts(self) -> dict[str, ComputeHost]:
        self.sync_compute_hosts_if_outdated()
        return self._compute_hosts

    @property
    def system_notices(self) -> dict[str, SystemNotice]:
        self.sync_system_notices_if_outdated()
        return self._system_notices

    @property
    def maintenance_mode(self) -> bool:
        self.sync_system_notices_if_outdated()
        return self._maintenance_mode

    @maintenance_mode.setter
    def maintenance_mode(self, value: bool) -> None:
        url = "system/maintenance_mode"
        self._session.patch(url, json={"maintenance_mode": value})
        self._maintenance_mode = value

    @property
    def maintenance_notice(self) -> Optional[SystemNotice]:
        self.sync_system_notices_if_outdated()
        return self._maintenance_notice

    @maintenance_notice.setter
    def maintenance_notice(self, notice: Optional[SystemNotice]) -> None:
        url = "system/maintenance_mode"
        notice_id = None if notice is None else notice.id
        result = self._session.patch(url, json={"notice": notice_id})
        resolved = result["resolved_notice"]
        if resolved is None:
            notice = None
        else:
            notice = self._system_notices.get(resolved["id"])
        if notice is not None and resolved is not None:
            notice.update(resolved)
        self._maintenance_notice = notice

    def sync_compute_hosts_if_outdated(self) -> None:
        timestamp = time.time()
        if (
            self.auto_sync
            and timestamp - self._last_sync_compute_host_time > self.auto_sync_interval
        ):
            self.sync_compute_hosts()

    def sync_system_notices_if_outdated(self) -> None:
        timestamp = time.time()
        if (
            self.auto_sync
            and timestamp - self._last_sync_system_notice_time > self.auto_sync_interval
        ):
            self.sync_system_notices()

    def sync_compute_hosts(self) -> None:
        url = "system/compute_hosts"
        compute_hosts = self._session.get(url).json()
        compute_host_ids = []

        for compute_host in compute_hosts:
            compute_id = compute_host.pop("id")
            compute_host["compute_id"] = compute_id
            if compute_id in self._compute_hosts:
                self._compute_hosts[compute_id].update(compute_host)
            else:
                self.add_compute_host_local(**compute_host)
            compute_host_ids.append(compute_id)

        for compute_id in list(self._compute_hosts):
            if compute_id not in compute_host_ids:
                self._compute_hosts.pop(compute_id)
        self._last_sync_compute_host_time = time.time()

    def sync_system_notices(self) -> None:
        url = "system/notices"
        system_notices = self._session.get(url).json()
        system_notice_ids = []

        for system_notice in system_notices:
            notice_id = system_notice.get("id")
            if notice_id in self._system_notices:
                self._system_notices[notice_id].update(system_notice)
            else:
                self.add_system_notice_local(**system_notice)
            system_notice_ids.append(notice_id)

        for notice_id in list(self._system_notices):
            if notice_id not in system_notice_ids:
                self._system_notices.pop(notice_id)

        url = "system/maintenance_mode"
        maintenance = self.session.get(url).json()
        self._maintenance_mode = maintenance["maintenance_mode"]
        notice_id = maintenance["notice"]
        if notice_id is None:
            self._maintenance_notice = None
        else:
            self._maintenance_notice = self._system_notices.get(notice_id)
        self._last_sync_system_notice_time = time.time()

    def get_external_connectors(self, sync: bool | None = None) -> list[dict[str, str]]:
        """
        Get the list of external connectors present on the controller.
        Admin users may enable sync to refresh the cached list from host state.
        If sync is False, the state is retrieved; if True, configuration is applied
        back into the controller host.

        Device names or tags are used as External Connector nodes' configuration.
        Returns a list of objects with the device name and label.
        """
        url = "/system/external_connectors"
        if sync is None:
            return self._session.get(url).json()
        else:
            data = {"push_configured_state": sync}
            return self._session.put(url, json=data).json()

    def update_external_connector(
        self, connector_id: str, data: dict[str, Any]
    ) -> dict[str, Any]:
        url = f"/system/external_connectors/{connector_id}"
        return self._session.patch(url, json=data).json()

    def delete_external_connector(self, connector_id: str):
        url = f"/system/external_connectors/{connector_id}"
        return self._session.delete(url)

    def get_web_session_timeout(self) -> int:
        """
        Get the web session timeout in seconds.

        :return: web session timeout
        """
        url = "/web_session_timeout"
        return self._session.get(url).json()

    def set_web_session_timeout(self, timeout: int) -> str:
        """
        Set the web session timeout in seconds.

        :return: 'OK'
        """

        url = "/web_session_timeout/{}".format(timeout)
        return self._session.patch(url).json()

    def get_mac_address_block(self) -> int:
        """
        Get mac address block.

        :return: mac address block
        """
        url = "/mac_address_block"
        return self._session.get(url).json()

    def _set_mac_address_block(self, block: int) -> str:
        url = "/mac_address_block/{}".format(block)
        return self._session.patch(url).json()

    def set_mac_address_block(self, block: int) -> str:
        """
        Set mac address block.

        :return: 'OK'
        """
        if block < 0 or block > 7:
            raise ValueError("MAC address block has to be in range 0-7.")
        return self._set_mac_address_block(block=block)

    def get_new_compute_host_state(self) -> str:
        url = "/system/compute_hosts/configuration"
        return self._session.get(url).json()["admission_state"]

    def set_new_compute_host_state(self, admission_state: str) -> str:
        url = "/system/compute_hosts/configuration"
        return self._session.patch(
            url, json={"admission_state": admission_state}
        ).json()["admission_state"]

    def add_compute_host_local(
        self,
        compute_id: str,
        hostname: str,
        server_address: str,
        is_connector: bool,
        is_simulator: bool,
        is_connected: bool,
        is_synced: bool,
        admission_state: str,
        nodes: Optional[list[str]] = None,
    ) -> ComputeHost:
        new_compute_host = ComputeHost(
            self,
            compute_id,
            hostname,
            server_address,
            is_connector,
            is_simulator,
            is_connected,
            is_synced,
            admission_state,
            nodes,
        )
        self._compute_hosts[compute_id] = new_compute_host
        return new_compute_host

    def add_system_notice_local(
        self,
        id: str,
        level: str,
        label: str,
        content: str,
        enabled: bool,
        acknowledged: dict[str, bool],
        groups: Optional[list[str]] = None,
    ) -> SystemNotice:
        new_system_notice = SystemNotice(
            self,
            id,
            level,
            label,
            content,
            enabled,
            acknowledged,
            groups,
        )
        self._system_notices[id] = new_system_notice
        return new_system_notice


class ComputeHost:
    def __init__(
        self,
        system: SystemManagement,
        compute_id: str,
        hostname: str,
        server_address: str,
        is_connector: bool,
        is_simulator: bool,
        is_connected: bool,
        is_synced: bool,
        admission_state: str,
        nodes: Optional[list[str]] = None,
    ):
        self._system = system
        self._session: httpx.Client = system.session
        self._compute_id = compute_id
        self._hostname = hostname
        self._server_address = server_address
        self._is_connector = is_connector
        self._is_simulator = is_simulator
        self._is_connected = is_connected
        self._is_synced = is_synced
        self._admission_state = admission_state
        self._nodes = nodes if nodes is not None else []
        self._base_url = f"{self._session.base_url}/system/compute_hosts/{compute_id}"

    def __str__(self):
        return f"Compute host: {self._hostname}"

    @property
    def compute_id(self) -> str:
        return self._compute_id

    @property
    def hostname(self) -> str:
        self._system.sync_compute_hosts_if_outdated()
        return self._hostname

    @property
    def server_address(self) -> str:
        self._system.sync_compute_hosts_if_outdated()
        return self._server_address

    @property
    def is_connector(self) -> bool:
        return self._is_connector

    @property
    def is_simulator(self) -> bool:
        return self._is_simulator

    @property
    def is_connected(self) -> bool:
        self._system.sync_compute_hosts_if_outdated()
        return self._is_connected

    @property
    def is_synced(self) -> bool:
        self._system.sync_compute_hosts_if_outdated()
        return self._is_synced

    @property
    def nodes(self) -> list[str]:
        self._system.sync_compute_hosts_if_outdated()
        return self._nodes

    @property
    def admission_state(self) -> str:
        self._system.sync_compute_hosts_if_outdated()
        return self._admission_state

    @admission_state.setter
    def admission_state(self, value: str):
        self._set_compute_host_property("admission_state", value)
        self._admission_state = value

    def remove(self) -> None:
        _LOGGER.info("Removing compute host %s", self)
        self._session.delete(self._base_url)

    def update(self, host_data: dict[str, Any], push_to_server: bool = False):
        if push_to_server:
            self._set_compute_host_properties(host_data)
            return

        for key, value in host_data.items():
            setattr(self, f"_{key}", value)

    def _set_compute_host_property(self, key: str, val: Any) -> None:
        _LOGGER.debug("Setting compute host property %s %s: %s", self, key, val)
        self._set_compute_host_properties({key: val})

    def _set_compute_host_properties(self, host_data: dict[str, Any]) -> None:
        new_data = self._session.patch(url=self._base_url, json=host_data).json()
        self.update(new_data)


class SystemNotice:
    def __init__(
        self,
        system: SystemManagement,
        id: str,
        level: str,
        label: str,
        content: bool,
        enabled: bool,
        acknowledged: dict[str, bool],
        groups: Optional[list[str]] = None,
    ):
        self._system = system
        self._session: httpx.Client = system.session
        self._id = id
        self._level = level
        self._label = label
        self._content = content
        self._enabled = enabled
        self._acknowledged = acknowledged
        self._groups = groups
        self._base_url = f"{self._session.base_url}/system/notices/{id}"

    @property
    def id(self) -> str:
        return self._id

    @property
    def level(self) -> str:
        self._system.sync_system_notices_if_outdated()
        return self._level

    @property
    def label(self) -> str:
        self._system.sync_system_notices_if_outdated()
        return self._label

    @property
    def content(self) -> str:
        self._system.sync_system_notices_if_outdated()
        return self._content

    @property
    def enabled(self) -> bool:
        self._system.sync_system_notices_if_outdated()
        return self._enabled

    @property
    def acknowledged(self) -> dict[str, bool]:
        self._system.sync_system_notices_if_outdated()
        return self._acknowledged

    @property
    def groups(self) -> Optional[list[str]]:
        self._system.sync_system_notices_if_outdated()
        return self._groups

    def remove(self) -> None:
        _LOGGER.info("Removing system notice %s", self)
        self._session.delete(self._base_url)

    def update(self, notice_data: dict[str, Any], push_to_server: bool = False):
        if push_to_server:
            self._set_notice_properties(notice_data)
            return

        for key, value in notice_data.items():
            setattr(self, f"_{key}", value)

    def _set_notice_property(self, key: str, val: Any) -> None:
        _LOGGER.debug("Setting system notice property %s %s: %s", self, key, val)
        self._set_notice_properties({key: val})

    def _set_notice_properties(self, notice_data: dict[str, Any]) -> None:
        new_data = self._session.patch(url=self._base_url, json=notice_data).json()
        self.update(new_data)
