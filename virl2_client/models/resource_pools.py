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
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Dict, Iterable, Optional

from virl2_client.exceptions import InvalidProperty

if TYPE_CHECKING:
    import httpx

_LOGGER = logging.getLogger(__name__)


class ResourcePoolManagement:
    # The problem this is solving is that we need this list of all pools to be
    # updatable in both the client itself and its lab objects, as otherwise
    # the lab might receive the ID of a resource pool that doesn't exist yet
    # in the client, because the client wasn't updated recently
    def __init__(self, session: httpx.Client, auto_sync=True, auto_sync_interval=1.0):
        """
        Sync and modify resource pools.

        :param session: parent client's httpx.Client object
        :param auto_sync: whether to automatically synchronize resource pools
        :param auto_sync_interval: how often to synchronize resource pools in seconds
        """
        self._session = session
        self.auto_sync = auto_sync
        self.auto_sync_interval = auto_sync_interval
        self._last_sync_resource_pool_time = 0.0
        self._resource_pools: ResourcePools = {}

    @property
    def session(self) -> httpx.Client:
        return self._session

    @property
    def resource_pools(self) -> ResourcePools:
        self.sync_resource_pools_if_outdated()
        return self._resource_pools

    def sync_resource_pools_if_outdated(self) -> None:
        timestamp = time.time()
        if (
            self.auto_sync
            and timestamp - self._last_sync_resource_pool_time > self.auto_sync_interval
        ):
            self.sync_resource_pools()

    def sync_resource_pools(self) -> None:
        url = "resource_pools?data=true"
        res_pools = self._session.get(url).json()
        res_pool_ids = []
        # update existing pools and add entries for new pools
        for res_pool in res_pools:
            pool_id = res_pool.pop("id")
            res_pool["pool_id"] = pool_id
            if pool_id in self._resource_pools:
                self._resource_pools[pool_id].update(res_pool)
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
        Converts either one resource pool ID into a `ResourcePool` object
        or multiple IDs in an iterable into a dict of IDs and `ResourcePool` objects.

        :param resource_pool_ids: a resource pool ID or an iterable of IDs
        :returns: a `ResourcePool` when one ID is passed or, when an iterable of pools
            is passed, a dictionary of IDs to `ResourcePool`s or `None`s when
            resource pool doesn't exist
        :raises KeyError: when one ID is passed and it doesn't exist
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
        Creates a resource pool with the given parameters.

        :param label: required pool label
        :param kwargs: other resource pool parameters as accepted by ResourcePool object
        :returns: resource pool object
        """
        kwargs["label"] = label
        url = "resource_pools"
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
        Creates a list of resource pools with the given parameters.
        If no template is supplied, a new template pool is created with the specified
        parameters, and each user is assigned a new pool with no additional limits.
        If a template pool is supplied, then parameters are applied to each user pool.

        :param label: pool label
        :param users: list of user IDs for which to create resource pools
        :param kwargs: other resource pool parameters as accepted by ResourcePool object
        :returns: resource pool objects, with template pool first if created
        """
        kwargs["label"] = label
        kwargs["users"] = users
        kwargs["shared"] = False
        url = "resource_pools"
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
        description: Optional[str] = None,
        template: Optional[str] = None,
        licenses: Optional[int] = None,
        ram: Optional[int] = None,
        cpus: Optional[int] = None,
        disk_space: Optional[int] = None,
        external_connectors: Optional[list[str]] = None,
        users: Optional[list[str]] = None,
        user_pools: Optional[list[str]] = None,
    ) -> ResourcePool:
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
    def __init__(
        self,
        resource_pools: ResourcePoolManagement,
        pool_id: str,
        label: str,
        description: Optional[str],
        template: Optional[str],
        licenses: Optional[int],
        ram: Optional[int],
        cpus: Optional[int],
        disk_space: Optional[int],
        external_connectors: Optional[list[str]],
        users: Optional[list[str]],
        user_pools: Optional[list[str]],
    ):
        self._resource_pools = resource_pools
        self._session: httpx.Client = resource_pools.session
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
        self._base_url = f"{self._session.base_url}/resource_pools/{pool_id}"
        self._usage_base_url = f"{self._session.base_url}/resource_pool_usage/{pool_id}"

    def __str__(self):
        return f"Resource pool: {self._label}"

    def __repr__(self):
        return "{}({!r}, {!r}, {!r}, {!r})".format(
            self.__class__.__name__,
            self._id,
            self._label,
            self._description,
            self._template,
        )

    @property
    def id(self) -> str:
        return self._id

    @property
    def label(self) -> str:
        self._resource_pools.sync_resource_pools_if_outdated()
        return self._label

    @label.setter
    def label(self, value: str):
        self._set_resource_pool_property("label", value)
        self._label = value

    @property
    def description(self) -> str:
        self._resource_pools.sync_resource_pools_if_outdated()
        return self._description

    @description.setter
    def description(self, value: str):
        self._set_resource_pool_property("description", value)
        self._description = value

    @property
    def template(self) -> str:
        return self._template

    @property
    def is_template(self) -> bool:
        return self._template is None

    @property
    def licenses(self) -> int:
        self._resource_pools.sync_resource_pools_if_outdated()
        return self._licenses

    @licenses.setter
    def licenses(self, value: int):
        self._set_resource_pool_property("licenses", value)
        self._licenses = value

    @property
    def ram(self) -> int:
        self._resource_pools.sync_resource_pools_if_outdated()
        return self._ram

    @ram.setter
    def ram(self, value: int):
        self._set_resource_pool_property("ram", value)
        self._ram = value

    @property
    def cpus(self) -> int:
        self._resource_pools.sync_resource_pools_if_outdated()
        return self._cpus

    @cpus.setter
    def cpus(self, value: int):
        self._set_resource_pool_property("cpus", value)
        self._cpus = value

    @property
    def disk_space(self) -> int:
        self._resource_pools.sync_resource_pools_if_outdated()
        return self._disk_space

    @disk_space.setter
    def disk_space(self, value: int):
        self._set_resource_pool_property("disk_space", value)
        self._disk_space = value

    @property
    def external_connectors(self) -> Optional[list[str]]:
        self._resource_pools.sync_resource_pools_if_outdated()
        return self._external_connectors

    @external_connectors.setter
    def external_connectors(self, value: Optional[list[str]]):
        self._set_resource_pool_property("external_connectors", value)
        self._external_connectors = value

    @property
    def users(self) -> list[str]:
        if self.is_template:
            raise InvalidProperty("A template does not have 'users' property")
        self._resource_pools.sync_resource_pools_if_outdated()
        return self._users

    @property
    def user_pools(self) -> list[str]:
        if not self.is_template:
            raise InvalidProperty("A resource pool does not have 'user_pools' property")
        self._resource_pools.sync_resource_pools_if_outdated()
        return self._user_pools

    def get_usage(self) -> ResourcePoolUsage:
        result = self._session.get(self._usage_base_url).json()
        limit = ResourcePoolUsageBase(**result["limit"])
        usage = ResourcePoolUsageBase(**result["usage"])
        return ResourcePoolUsage(limit, usage)

    def remove(self) -> None:
        _LOGGER.info("Removing resource pool %s", self)
        self._session.delete(self._base_url)

    def update(self, pool_data: dict[str, Any], push_to_server: bool = False):
        if push_to_server:
            self._set_resource_pool_properties(pool_data)

        for key, value in pool_data.items():
            setattr(self, f"_{key}", value)

    def _set_resource_pool_property(self, key: str, val: Any) -> None:
        _LOGGER.debug("Setting resource pool property %s %s: %s", self, key, val)
        self._set_resource_pool_properties({key: val})

    def _set_resource_pool_properties(self, resource_pool_data: dict[str, Any]) -> None:
        for key in list(resource_pool_data):
            # drop unmodifiable properties
            if key in ("id", "template", "users", "user_pools"):
                resource_pool_data.pop(key)
        self._session.patch(url=self._base_url, json=resource_pool_data)


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
