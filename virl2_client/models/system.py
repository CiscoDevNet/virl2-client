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

import logging
import time
import warnings
from typing import TYPE_CHECKING, Any

from virl2_client.exceptions import ControllerNotFound

from ..utils import _deprecated_argument, get_url_from_template

if TYPE_CHECKING:
    import httpx

_LOGGER = logging.getLogger(__name__)


class SystemManagement:
    _URL_TEMPLATES = {
        "maintenance_mode": "system/maintenance_mode",
        "compute_hosts": "system/compute_hosts",
        "notices": "system/notices",
        "external_connectors": "system/external_connectors",
        "external_connector": "system/external_connectors",
        "web_session_timeout": "web_session_timeout",
        "host_configuration": "system/compute_hosts/configuration",
    }

    def __init__(
        self,
        session: httpx.Client,
        auto_sync: bool = True,
        auto_sync_interval: float = 1.0,
    ):
        """
        Manage the underlying controller software and the host system where it runs.

        :param session: The httpx-based HTTP client for this session with the server.
        :param auto_sync: A boolean indicating whether auto synchronization is enabled.
        :param auto_sync_interval: The interval in seconds between auto
            synchronizations.
        """
        self._session = session
        self.auto_sync = auto_sync
        self.auto_sync_interval = auto_sync_interval
        self._last_sync_compute_host_time = 0.0
        self._last_sync_system_notice_time = 0.0
        self._compute_hosts: dict[str, ComputeHost] = {}
        self._system_notices: dict[str, SystemNotice] = {}
        self._maintenance_mode = False
        self._maintenance_notice: SystemNotice | None = None

    def _url_for(self, endpoint, **kwargs):
        """
        Generate the URL for a given API endpoint.

        :param endpoint: The desired endpoint.
        :param **kwargs: Keyword arguments used to format the URL.
        :returns: The formatted URL.
        """
        return get_url_from_template(endpoint, self._URL_TEMPLATES, kwargs)

    @property
    def compute_hosts(self) -> dict[str, ComputeHost]:
        """Return a dictionary of compute hosts."""
        self.sync_compute_hosts_if_outdated()
        return self._compute_hosts.copy()

    @property
    def controller(self) -> ComputeHost:
        """Return the controller

        :raises ControllerNotFound: If no controller has been found
            (should never be the case).
        :returns: The controller object.
        """
        for compute_host in self._compute_hosts.values():
            if compute_host.is_connector:
                return compute_host
        raise ControllerNotFound

    @property
    def system_notices(self) -> dict[str, SystemNotice]:
        """Return a dictionary of system notices."""
        self.sync_system_notices_if_outdated()
        return self._system_notices.copy()

    @property
    def maintenance_mode(self) -> bool:
        """Return the maintenance mode status."""
        self.sync_system_notices_if_outdated()
        return self._maintenance_mode

    @maintenance_mode.setter
    def maintenance_mode(self, value: bool) -> None:
        """Set the maintenance mode status."""
        url = self._url_for("maintenance_mode")
        self._session.patch(url, json={"maintenance_mode": value})
        self._maintenance_mode = value

    @property
    def maintenance_notice(self) -> SystemNotice | None:
        """Return the current maintenance notice."""
        self.sync_system_notices_if_outdated()
        return self._maintenance_notice

    @maintenance_notice.setter
    def maintenance_notice(self, notice: SystemNotice | None) -> None:
        """Set the maintenance notice."""
        url = self._url_for("maintenance_mode")
        notice_id = None if notice is None else notice.id
        result: dict = self._session.patch(url, json={"notice": notice_id}).json()
        resolved = result["resolved_notice"]
        if resolved is None:
            notice = None
        else:
            notice = self._system_notices.get(resolved["id"])
        if notice is not None and resolved is not None:
            notice._update(resolved, push_to_server=False)
        self._maintenance_notice = notice

    def sync_compute_hosts_if_outdated(self) -> None:
        """Synchronize compute hosts if they are outdated."""
        timestamp = time.time()
        if (
            self.auto_sync
            and timestamp - self._last_sync_compute_host_time > self.auto_sync_interval
        ):
            self.sync_compute_hosts()

    def sync_system_notices_if_outdated(self) -> None:
        """Synchronize system notices if they are outdated."""
        timestamp = time.time()
        if (
            self.auto_sync
            and timestamp - self._last_sync_system_notice_time > self.auto_sync_interval
        ):
            self.sync_system_notices()

    def sync_compute_hosts(self) -> None:
        """Synchronize compute hosts from the server."""
        url = self._url_for("compute_hosts")
        compute_hosts = self._session.get(url).json()
        compute_host_ids = []

        for compute_host in compute_hosts:
            compute_id = compute_host.pop("id")
            compute_host["compute_id"] = compute_id
            if compute_id in self._compute_hosts:
                self._compute_hosts[compute_id]._update(
                    compute_host, push_to_server=False
                )
            else:
                compute_host["node_counts"] = compute_host.get("node_counts", {})
                self.add_compute_host_local(**compute_host)
            compute_host_ids.append(compute_id)

        for compute_id in list(self._compute_hosts):
            if compute_id not in compute_host_ids:
                self._compute_hosts.pop(compute_id)
        self._last_sync_compute_host_time = time.time()

    def sync_system_notices(self) -> None:
        """Synchronize system notices from the server."""
        url = self._url_for("notices")
        system_notices = self._session.get(url).json()
        system_notice_ids = []

        for system_notice in system_notices:
            notice_id = system_notice.get("id")
            if notice_id in self._system_notices:
                self._system_notices[notice_id]._update(
                    system_notice, push_to_server=False
                )
            else:
                self.add_system_notice_local(**system_notice)
            system_notice_ids.append(notice_id)

        for notice_id in list(self._system_notices):
            if notice_id not in system_notice_ids:
                self._system_notices.pop(notice_id)

        url = self._url_for("maintenance_mode")
        maintenance = self._session.get(url).json()
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
        Device names or tags are used as External Connector nodes' configuration.

        :param sync: Admin only. A boolean indicating whether to refresh the cached list
            from host state. If sync is False, the state is retrieved;
            if True, configuration is applied back into the controller host.
        :returns: A list of objects with the device name and label.
        """
        url = self._url_for("external_connectors")
        if sync is None:
            return self._session.get(url).json()
        else:
            data = {"push_configured_state": sync}
            return self._session.put(url, json=data).json()

    def update_external_connector(
        self, connector_id: str, data: dict[str, Any]
    ) -> dict[str, Any]:
        """
        Update an external connector.

        :param connector_id: The ID of the connector to update.
        :param data: The data to update.
        :returns: The updated data.
        """
        url = f"{self._url_for('external_connector')}/{connector_id}"
        return self._session.patch(url, json=data).json()

    def delete_external_connector(self, connector_id: str) -> None:
        """
        Delete an external connector.

        :param connector_id: The ID of the connector to delete.
        """
        url = f"{self._url_for('external_connector')}/{connector_id}"
        self._session.delete(url)

    def get_web_session_timeout(self) -> int:
        """
        Get the web session timeout in seconds.

        :returns: The web session timeout.
        """
        url = self._url_for("web_session_timeout")
        return self._session.get(url).json()

    def set_web_session_timeout(self, timeout: int) -> str:
        """
        Set the web session timeout in seconds.

        :param timeout: The timeout value in seconds.
        :returns: 'OK'
        """
        url = f"{self._url_for('web_session_timeout')}/{timeout}"
        return self._session.patch(url).json()

    def get_new_compute_host_state(self) -> str:
        """
        Get the admission state of the new compute host.

        :returns: The admission state of the new compute host.
        """
        url = self._url_for("host_configuration")
        return self._session.get(url).json()["admission_state"]

    def set_new_compute_host_state(self, admission_state: str) -> str:
        """
        Set the admission state of the new compute host.

        :param admission_state: The admission state to set.
        :returns: The updated admission state.
        """
        url = self._url_for("host_configuration")
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
        node_counts: dict[str, int],
        nodes: list[str] | None = None,
    ) -> ComputeHost:
        """
        Add a compute host locally.

        :param compute_id: The ID of the compute host.
        :param hostname: The hostname of the compute host.
        :param server_address: The server address of the compute host.
        :param is_connector: A boolean indicating if the compute host is a connector.
        :param is_simulator: A boolean indicating if the compute host is a simulator.
        :param is_connected: A boolean indicating if the compute host is connected.
        :param is_synced: A boolean indicating if the compute host is synced.
        :param admission_state: The admission state of the compute host.
        :param node_counts: Count of deployed and running nodes and orphans.
        :param nodes: A list of node IDs associated with the compute host.
        :returns: The added compute host.
        """
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
            node_counts,
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
        groups: list[str] | None = None,
    ) -> SystemNotice:
        """
        Add a system notice locally.

        :param id: The unique identifier of the system notice.
        :param level: The level of the system notice.
        :param label: The label or title of the system notice.
        :param content: The content or description of the system notice.
        :param enabled: A flag indicating whether the system notice is enabled or not.
        :param acknowledged: A dictionary mapping user IDs to their acknowledgment
            status.
        :param groups: A list of group names to associate with the system notice.
            (Optional)
        :returns: The newly created system notice object.
        """
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
    _URL_TEMPLATES = {"compute_host": "system/compute_hosts/{compute_id}"}

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
        node_counts: dict[str, int],
        nodes: list[str] | None = None,
    ):
        """
        A compute host, which hosts some of the nodes of the simulation.

        :param system: The SystemManagement instance.
        :param compute_id: The ID of the compute host.
        :param hostname: The hostname of the compute host.
        :param server_address: The server address of the compute host.
        :param is_connector: Whether the compute host is a connector.
        :param is_simulator: Whether the compute host is a simulator.
        :param is_connected: Whether the compute host is connected.
        :param is_synced: Whether the compute host is synced.
        :param admission_state: The admission state of the compute host.
        :param node_counts: The counts of deployed and running nodes and orphans.
        :param nodes: DEPRECATED: replaced by node_counts.
            The list of node IDs associated with the compute host.
        """
        self._system = system
        self._session: httpx.Client = system._session
        self._compute_id = compute_id
        self._hostname = hostname
        self._server_address = server_address
        self._is_connector = is_connector
        self._is_simulator = is_simulator
        self._is_connected = is_connected
        self._is_synced = is_synced
        self._admission_state = admission_state
        self._node_counts = node_counts
        self._nodes = nodes if nodes is not None else []

    def __str__(self):
        return f"Compute host: {self._hostname}"

    def _url_for(self, endpoint, **kwargs) -> str:
        """
        Generate the URL for a given API endpoint.

        :param endpoint: The desired endpoint.
        :param **kwargs: Keyword arguments used to format the URL.
        :returns: The formatted URL.
        """
        kwargs["compute_id"] = self._compute_id
        return get_url_from_template(endpoint, self._URL_TEMPLATES, kwargs)

    @property
    def compute_id(self) -> str:
        """Return the ID of the compute host."""
        return self._compute_id

    @property
    def hostname(self) -> str:
        """Return the hostname of the compute host."""
        self._system.sync_compute_hosts_if_outdated()
        return self._hostname

    @property
    def server_address(self) -> str:
        """Return the server address of the compute host."""
        self._system.sync_compute_hosts_if_outdated()
        return self._server_address

    @property
    def is_connector(self) -> bool:
        """Return whether the compute host is a connector."""
        return self._is_connector

    @property
    def is_simulator(self) -> bool:
        """Return whether the compute host is a simulator."""
        return self._is_simulator

    @property
    def is_connected(self) -> bool:
        """Return whether the compute host is connected."""
        self._system.sync_compute_hosts_if_outdated()
        return self._is_connected

    @property
    def is_synced(self) -> bool:
        """Return whether the compute host is synced."""
        self._system.sync_compute_hosts_if_outdated()
        return self._is_synced

    @property
    def node_counts(self) -> dict[str, int]:
        """Return the counts of deployed and running nodes and orphans."""
        self._system.sync_compute_hosts_if_outdated()
        return self._node_counts

    @property
    def nodes(self) -> list[str]:
        """Return the list of nodes associated with the compute host."""
        warnings.warn(
            "'ComputeHost.nodes' is deprecated. Use 'ComputeHost.node_counts' or "
            "'ClientLibrary.get_diagnostics(DiagnosticsCategory.COMPUTES)' instead.",
        )
        self._system.sync_compute_hosts_if_outdated()
        return self._nodes

    @property
    def admission_state(self) -> str:
        """Return the admission state of the compute host."""
        self._system.sync_compute_hosts_if_outdated()
        return self._admission_state

    @admission_state.setter
    def admission_state(self, value: str) -> None:
        """Set the admission state of the compute host."""
        self._set_compute_host_property("admission_state", value)
        self._admission_state = value

    def remove(self) -> None:
        """Remove the compute host."""
        _LOGGER.info(f"Removing compute host {self}")
        url = self._url_for("compute_host")
        self._session.delete(url)

    def update(self, host_data: dict[str, Any], push_to_server=None) -> None:
        """
        Update the compute host with the given data.

        :param host_data: The data to update the compute host.
        :param push_to_server: DEPRECATED: Was only used by internal methods
            and should otherwise always be True.
        """
        _deprecated_argument(self.update, push_to_server, "push_to_server")
        self._update(host_data, push_to_server=True)

    def _update(self, host_data: dict[str, Any], push_to_server: bool = True) -> None:
        """
        Update the compute host with the given data.

        :param host_data: The data to update the compute host.
        :param push_to_server: Whether to push the changes to the server.
        """
        if push_to_server:
            self._set_compute_host_properties(host_data)
            return

        for key, value in host_data.items():
            setattr(self, f"_{key}", value)

    def _set_compute_host_property(self, key: str, val: Any) -> None:
        """
        Set a specific property of the compute host.

        :param key: The property key.
        :param val: The new value for the property.
        """
        _LOGGER.debug(f"Setting compute host property {self} {key}: {val}")
        self._set_compute_host_properties({key: val})

    def _set_compute_host_properties(self, host_data: dict[str, Any]) -> None:
        """
        Set multiple properties of the compute host.

        :param host_data: The data to set as properties of the compute host.
        """
        url = self._url_for("compute_host")
        new_data = self._session.patch(url, json=host_data).json()
        self._update(new_data, push_to_server=False)


class SystemNotice:
    _URL_TEMPLATES = {"notice": "system/notices/{notice_id}"}

    def __init__(
        self,
        system: SystemManagement,
        id: str,
        level: str,
        label: str,
        content: str,
        enabled: bool,
        acknowledged: dict[str, bool],
        groups: list[str] | None = None,
    ):
        """
        A system notice, which notifies users of maintenance or other events.

        :param system: The SystemManagement instance.
        :param id: The ID of the system notice.
        :param level: The level of the system notice.
        :param label: The label of the system notice.
        :param content: The content of the system notice.
        :param enabled: Whether the system notice is enabled.
        :param acknowledged: The acknowledgement status of the system notice.
        :param groups: The groups associated with the system notice.
        """
        self._system = system
        self._session: httpx.Client = system._session
        self._id = id
        self._level = level
        self._label = label
        self._content = content
        self._enabled = enabled
        self._acknowledged = acknowledged
        self._groups = groups

    def _url_for(self, endpoint, **kwargs) -> str:
        """
        Generate the URL for a given API endpoint.

        :param endpoint: The desired endpoint.
        :param **kwargs: Keyword arguments used to format the URL.
        :returns: The formatted URL.
        """
        kwargs["notice_id"] = self._id
        return get_url_from_template(endpoint, self._URL_TEMPLATES, kwargs)

    @property
    def id(self) -> str:
        """Return the ID of the system notice."""
        return self._id

    @property
    def level(self) -> str:
        """Return the level of the system notice."""
        self._system.sync_system_notices_if_outdated()
        return self._level

    @property
    def label(self) -> str:
        """Return the label of the system notice."""
        self._system.sync_system_notices_if_outdated()
        return self._label

    @property
    def content(self) -> str:
        """Return the content of the system notice."""
        self._system.sync_system_notices_if_outdated()
        return self._content

    @property
    def enabled(self) -> bool:
        """Return whether the system notice is enabled."""
        self._system.sync_system_notices_if_outdated()
        return self._enabled

    @property
    def acknowledged(self) -> dict[str, bool]:
        """Return the acknowledgement status of the system notice."""
        self._system.sync_system_notices_if_outdated()
        return self._acknowledged

    @property
    def groups(self) -> list[str] | None:
        """Return the groups associated with the system notice."""
        self._system.sync_system_notices_if_outdated()
        return self._groups

    def remove(self) -> None:
        """Remove the system notice."""
        _LOGGER.info(f"Removing system notice {self}")
        url = self._url_for("notice")
        self._session.delete(url)

    def update(self, notice_data: dict[str, Any], push_to_server=None) -> None:
        """
        Update the system notice with the given data.

        :param notice_data: The data to update the system notice with.
        :param push_to_server: DEPRECATED: Was only used by internal methods
            and should otherwise always be True.
        """
        _deprecated_argument(self.update, push_to_server, "push_to_server")
        self._update(notice_data, push_to_server=True)

    def _update(self, notice_data: dict[str, Any], push_to_server: bool = True) -> None:
        """
        Update the system notice with the given data.

        :param notice_data: The data to update the system notice with.
        :param push_to_server: Whether to push the changes to the server.
        """
        if push_to_server:
            self._set_notice_properties(notice_data)
            return

        for key, value in notice_data.items():
            setattr(self, f"_{key}", value)

    def _set_notice_property(self, key: str, val: Any) -> None:
        """
        Set a specific property of the system notice.

        :param key: The property key.
        :param val: The new value for the property.
        """
        _LOGGER.debug(f"Setting system notice property {self} {key}: {val}")
        self._set_notice_properties({key: val})

    def _set_notice_properties(self, notice_data: dict[str, Any]) -> None:
        """
        Set multiple properties of the system notice.

        :param notice_data: The data to set as properties of the system notice.
        """
        url = self._url_for("notice")
        new_data = self._session.patch(url, json=notice_data).json()
        self._update(new_data, push_to_server=False)
