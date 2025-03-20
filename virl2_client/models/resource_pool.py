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
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Dict, Iterable

from ..exceptions import InvalidProperty
from ..utils import _deprecated_argument, get_url_from_template

if TYPE_CHECKING:
    import httpx

_LOGGER = logging.getLogger(__name__)


class ResourcePoolManagement:
    # The problem this is solving is that we need this list of all pools to be
    # updatable in both the client itself and its lab objects, as otherwise
    # the lab might receive the ID of a resource pool that doesn't exist yet
    # in the client, because the client wasn't updated recently
    _URL_TEMPLATES = {
        "resource_pools": "resource_pools",
        "resource_pools_data": "resource_pools?data=true",
    }

    def __init__(self, session: httpx.Client, auto_sync=True, auto_sync_interval=1.0):
        """
        Manage and synchronize resource pools.

        :param session: The httpx-based HTTP client for this session with the server.
        :param auto_sync: Whether to automatically synchronize resource pools.
        :param auto_sync_interval: How often to synchronize resource pools in seconds.
        """
        self._session = session
        self.auto_sync = auto_sync
        self.auto_sync_interval = auto_sync_interval
        self._last_sync_resource_pool_time = 0.0
        self._resource_pools: ResourcePools = {}

    def _url_for(self, endpoint, **kwargs):
        """
        Generate the URL for a given API endpoint.

        :param endpoint: The desired endpoint.
        :param **kwargs: Keyword arguments used to format the URL.
        :returns: The formatted URL.
        """
        return get_url_from_template(endpoint, self._URL_TEMPLATES, kwargs)

    @property
    def resource_pools(self) -> ResourcePools:
        """Return all resource pools."""
        self.sync_resource_pools_if_outdated()
        return self._resource_pools

    def sync_resource_pools_if_outdated(self) -> None:
        """Synchronize resource pools if they are outdated."""
        timestamp = time.time()
        if (
            self.auto_sync
            and timestamp - self._last_sync_resource_pool_time > self.auto_sync_interval
        ):
            self.sync_resource_pools()

    def sync_resource_pools(self) -> None:
        """Synchronize the resource pools with the server."""
        url = self._url_for("resource_pools_data")
        res_pools = self._session.get(url).json()
        res_pool_ids = []
        # update existing pools and add entries for new pools
        for res_pool in res_pools:
            pool_id = res_pool.pop("id")
            res_pool["pool_id"] = pool_id
            if pool_id in self._resource_pools:
                self._resource_pools[pool_id]._update(res_pool, push_to_server=False)
            else:
                self._add_resource_pool_local(**res_pool)
            res_pool_ids.append(pool_id)
        # remove all local pools that don't exist on remove
        for local_res_pool_id in list(self._resource_pools):
            if local_res_pool_id not in res_pool_ids:
                self._resource_pools.pop(local_res_pool_id)
        self._last_sync_resource_pool_time = time.time()

    def get_resource_pools_by_ids(
        self, resource_pool_ids: str | Iterable[str]
    ) -> ResourcePool | ResourcePools:
        """
        Get resource pools by their IDs.

        :param resource_pool_ids: A resource pool ID or an iterable of IDs.
        :returns: A ResourcePool object when one ID is passed, or a dictionary of IDs to
            either ResourcePools when a resource pool exists or None when it doesn't.
        :raises KeyError: When one ID is passed, and it doesn't exist.
        """
        self.sync_resource_pools_if_outdated()
        if isinstance(resource_pool_ids, str):
            return self._resource_pools[resource_pool_ids]

        resource_pools = {}
        for resource_pool_id in resource_pool_ids:
            resource_pools[resource_pool_id] = self._resource_pools.get(
                resource_pool_id
            )
        return resource_pools

    def create_resource_pool(
        self,
        label: str,
        **kwargs,
    ) -> ResourcePool:
        """
        Create a resource pool with the given parameters.

        :param label: The label for the resource pools.
        :param kwargs: Additional resource pool parameters as accepted by the
            ResourcePool object.
        :returns: The created ResourcePool object.
        """
        kwargs["label"] = label
        url = self._url_for("resource_pools")
        response: dict = self._session.post(url, json=kwargs).json()
        response["pool_id"] = response.pop("id")
        return self._add_resource_pool_local(**response)

    def create_resource_pools(
        self,
        label: str,
        users: list[str],
        **kwargs,
    ) -> list[ResourcePool]:
        """
        Create a list of resource pools with the given parameters.
        If no template is supplied, a new template pool is created with the specified
        parameters, and each user is assigned a new pool with no additional limits.
        If a template pool is supplied, then parameters are applied to each user pool.

        :param label: The label for the resource pools.
        :param users: The list of user IDs for which to create resource pools.
        :param kwargs: Additional resource pool parameters as accepted by the
            ResourcePool object.
        :returns: A list of created resource pool objects, with the template pool first
            if created.
        """
        kwargs["label"] = label
        kwargs["users"] = users
        kwargs["shared"] = False
        url = self._url_for("resource_pools")
        response: dict = self._session.post(url, json=kwargs).json()

        result = []
        for pool in response:
            pool["pool_id"] = pool.pop("id")
            result.append(self._add_resource_pool_local(**pool))
        return result

    def _add_resource_pool_local(
        self,
        pool_id: str,
        label: str,
        description: str | None = None,
        template: str | None = None,
        licenses: int | None = None,
        ram: int | None = None,
        cpus: int | None = None,
        disk_space: int | None = None,
        external_connectors: list[str] | None = None,
        users: list[str] | None = None,
        user_pools: list[str] | None = None,
    ) -> ResourcePool:
        """Helper method to add resource pool locally."""
        new_resource_pool = ResourcePool(
            self,
            pool_id,
            label,
            description,
            template,
            licenses,
            ram,
            cpus,
            disk_space,
            external_connectors,
            users,
            user_pools,
        )
        self._resource_pools[pool_id] = new_resource_pool
        return new_resource_pool


class ResourcePool:
    _URL_TEMPLATES = {
        "resource_pool": "resource_pools/{pool_id}",
        "resource_pool_usage": "resource_pool_usage/{pool_id}",
    }

    def __init__(
        self,
        resource_pools: ResourcePoolManagement,
        pool_id: str,
        label: str,
        description: str | None,
        template: str | None,
        licenses: int | None,
        ram: int | None,
        cpus: int | None,
        disk_space: int | None,
        external_connectors: list[str] | None,
        users: list[str] | None,
        user_pools: list[str] | None,
    ):
        """
        Initialize a resource pool.

        :param resource_pools: The parent ResourcePoolManagement object.
        :param pool_id: The ID of the resource pool.
        :param label: The label of the resource pool.
        :param description: The description of the resource pool.
        :param template: The template of the resource pool.
        :param licenses: The number of licenses in the resource pool.
        :param ram: The amount of RAM in the resource pool.
        :param cpus: The number of CPUs in the resource pool.
        :param disk_space: The amount of disk space in the resource pool.
        :param external_connectors: A list of external connectors in the resource pool.
        :param users: A list of users in the resource pool.
        :param user_pools: A list of user pools in the resource pool.
        """
        self._resource_pools = resource_pools
        self._session: httpx.Client = resource_pools._session
        self._id = pool_id
        self._label = label
        self._description = description
        self._template = template
        self._licenses = licenses
        self._ram = ram
        self._cpus = cpus
        self._disk_space = disk_space
        self._external_connectors = external_connectors
        self._users = users if users is not None else []
        self._user_pools = user_pools if user_pools is not None else []

    def __str__(self):
        return f"Resource pool: {self._label}"

    def __repr__(self):
        return (
            f"{self.__class__.__name__}("
            f"{self._id!r}, "
            f"{self._label!r}, "
            f"{self._template!r})"
        )

    def _url_for(self, endpoint, **kwargs):
        """
        Generate the URL for a given API endpoint.

        :param endpoint: The desired endpoint.
        :param **kwargs: Keyword arguments used to format the URL.
        :returns: The formatted URL.
        """
        kwargs["pool_id"] = self.id
        return get_url_from_template(endpoint, self._URL_TEMPLATES, kwargs)

    @property
    def id(self) -> str:
        """Return the ID of the resource pool."""
        return self._id

    @property
    def label(self) -> str:
        """Set the label of the resource pool."""
        self._resource_pools.sync_resource_pools_if_outdated()
        return self._label

    @label.setter
    def label(self, value: str):
        """Set the label of the resource pool."""
        self._set_resource_pool_property("label", value)
        self._label = value

    @property
    def description(self) -> str:
        """Return the description of the resource pool."""
        self._resource_pools.sync_resource_pools_if_outdated()
        return self._description

    @description.setter
    def description(self, value: str):
        """Set the description of the resource pool."""
        self._set_resource_pool_property("description", value)
        self._description = value

    @property
    def template(self) -> str:
        """Return the template of the resource pool."""
        return self._template

    @property
    def is_template(self) -> bool:
        """Return whether the resource pool is a template."""
        return self._template is None

    @property
    def licenses(self) -> int:
        """Return the number of licenses in the resource pool."""
        self._resource_pools.sync_resource_pools_if_outdated()
        return self._licenses

    @licenses.setter
    def licenses(self, value: int):
        """Set the number of licenses in the resource pool."""
        self._set_resource_pool_property("licenses", value)
        self._licenses = value

    @property
    def ram(self) -> int:
        """Return the amount of RAM in the resource pool."""
        self._resource_pools.sync_resource_pools_if_outdated()
        return self._ram

    @ram.setter
    def ram(self, value: int):
        """Set the amount of RAM in the resource pool."""
        self._set_resource_pool_property("ram", value)
        self._ram = value

    @property
    def cpus(self) -> int:
        """Return the number of CPUs in the resource pool."""
        self._resource_pools.sync_resource_pools_if_outdated()
        return self._cpus

    @cpus.setter
    def cpus(self, value: int):
        """Set the number of CPUs in the resource pool."""
        self._set_resource_pool_property("cpus", value)
        self._cpus = value

    @property
    def disk_space(self) -> int:
        """Return the amount of disk space in the resource pool."""
        self._resource_pools.sync_resource_pools_if_outdated()
        return self._disk_space

    @disk_space.setter
    def disk_space(self, value: int):
        """Set the amount of disk space in the resource pool."""
        self._set_resource_pool_property("disk_space", value)
        self._disk_space = value

    @property
    def external_connectors(self) -> list[str] | None:
        """Return a list of external connectors in the resource pool."""
        self._resource_pools.sync_resource_pools_if_outdated()
        return (
            self._external_connectors.copy()
            if self._external_connectors is not None
            else None
        )

    @external_connectors.setter
    def external_connectors(self, value: list[str] | None):
        """Set the external connectors in the resource pool."""
        self._set_resource_pool_property("external_connectors", value)
        self._external_connectors = value

    @property
    def users(self) -> list[str]:
        """Return the list of users in the resource pool."""
        if self.is_template:
            raise InvalidProperty("A template does not have the 'users' property.")
        self._resource_pools.sync_resource_pools_if_outdated()
        return self._users

    @property
    def user_pools(self) -> list[str]:
        """Return the list of user pools in the template."""
        if not self.is_template:
            raise InvalidProperty(
                "A resource pool does not have the 'user_pools' property."
            )
        self._resource_pools.sync_resource_pools_if_outdated()
        return self._user_pools

    def get_usage(self) -> ResourcePoolUsage:
        """Get the usage stats of the resource pool."""
        url = self._url_for("resource_pool_usage")
        result = self._session.get(url).json()
        limit = ResourcePoolUsageBase(**result["limit"])
        usage = ResourcePoolUsageBase(**result["usage"])
        return ResourcePoolUsage(limit, usage)

    def remove(self) -> None:
        """Remove the resource pool."""
        _LOGGER.info(f"Removing resource pool {self}")
        url = self._url_for("resource_pool")
        self._session.delete(url)

    def update(self, pool_data: dict[str, Any], push_to_server=None) -> None:
        """
        Update multiple properties of the pool at once.

        :param pool_data: A dictionary of the properties to update.
        :param push_to_server: DEPRECATED: Was only used by internal methods
            and should otherwise always be True.
        """
        _deprecated_argument(self.update, push_to_server, "push_to_server")
        self._update(pool_data, push_to_server=True)

    def _update(self, pool_data: dict[str, Any], push_to_server: bool = True) -> None:
        """
        Update multiple properties of the pool at once.

        :param pool_data: A dictionary of the properties to update.
        :param push_to_server: Whether to push the changes to the server.
        """
        if push_to_server:
            self._set_resource_pool_properties(pool_data)

        for key, value in pool_data.items():
            setattr(self, f"_{key}", value)

    def _set_resource_pool_property(self, key: str, val: Any) -> None:
        """Helper method to set a property on the server."""
        _LOGGER.debug(f"Setting resource pool property {self} {key}: {val}")
        self._set_resource_pool_properties({key: val})

    def _set_resource_pool_properties(self, resource_pool_data: dict[str, Any]) -> None:
        """Helper method to set multiple properties on the server."""
        # drop unmodifiable properties
        resource_pool_data_post = {
            key: resource_pool_data[key]
            for key in resource_pool_data
            if key not in ("id", "template", "users", "user_pools")
        }
        url = self._url_for("resource_pool")
        self._session.patch(url, json=resource_pool_data_post)


ResourcePools = Dict[str, ResourcePool]


@dataclass
class ResourcePoolUsage:
    limit: ResourcePoolUsageBase
    usage: ResourcePoolUsageBase


@dataclass
class ResourcePoolUsageBase:
    licenses: int
    cpus: int
    ram: int
    disk_space: int
    external_connectors: list
