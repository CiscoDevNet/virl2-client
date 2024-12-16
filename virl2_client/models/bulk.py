#
# This file is part of VIRL 2
# Copyright (c) 2019-2024, Cisco Systems, Inc.
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

from typing import TYPE_CHECKING, Any

import httpx

from virl2_client.models.lab import Lab
from virl2_client.models.link import Link
from virl2_client.utils import get_url_from_template

if TYPE_CHECKING:
    from virl2_client.virl2_client import ClientLibrary

from .node import Node

# TODO: updated properties are not immediately reflected in the local objects
# e.g., when a lab is updated, _handle_lab_response doesn't update the local lab


class BulkManagement:
    _URL_TEMPLATES = {
        "import": "/import",
        "labs": "/labs",
        "links": "/links",
        "nodes": "/nodes",
    }

    def __init__(
        self, labs: dict[str, Lab], session: httpx.Client, client: ClientLibrary
    ) -> None:
        self._labs = labs
        self._session = session
        # needed only for lab creation
        self._client = client

    def _url_for(self, endpoint: str, **kwargs: dict):
        """
        Generate the URL for a given API endpoint.

        :param endpoint: The desired endpoint.
        :param **kwargs: Keyword arguments used to format the URL.
        :returns: The formatted URL.
        """
        return get_url_from_template(endpoint, self._URL_TEMPLATES, kwargs)

    # LABS

    def get_labs(self, lab_ids: list[str] | None = None) -> list[dict[str, Any]]:
        """
        Get details of the specified labs (get all by default).

        Warning: All selected labs must exist (support for partial results is not
            available yet).

        :param lab_ids: An optional list of lab IDs (none - get all labs).
        :returns: A list of dictionaries with lab properties.
        """
        url = self._url_for("labs")
        if lab_ids:
            # https://github.com/encode/httpx/discussions/1587
            return self._session.request("GET", url, json=lab_ids).json()
        else:
            return self._session.get(url).json()

    def fetch_labs(self, lab_ids: list[str] | None = None) -> list[Lab]:
        """
        Get details of the specified labs (get all by default).

        Warning: All selected labs must exist (support for partial results is not
            available yet).

        :param lab_ids: An optional list of lab IDs (none - get all labs).
        :returns: A list of labs objects.
        """
        response = self.get_labs(lab_ids=lab_ids)
        return self._handle_lab_response(response)

    def post_labs(self, lab_data: list[dict]) -> list[dict[str, Any]]:
        """
        Add the specified labs.

        Warning: All data must be valid (support for partial results is not available
            yet).

        :param lab_data: A list of dictionaries with lab properties.
        :returns: A list of dictionaries with lab properties.
        """
        url = self._url_for("labs")
        return self._session.post(url, json=lab_data).json()

    def create_labs(self, lab_data: list[dict]) -> list[Lab]:
        """
        Add the specified labs.

        Warning: All data must be valid (support for partial results is not available
            yet).

        :param lab_data: A list of dictionaries with lab properties.
        :returns: A list of labs objects.
        """
        response = self.post_labs(lab_data=lab_data)
        return self._handle_lab_response(response)

    def patch_labs(self, lab_data: list[dict]) -> list[dict[str, Any]]:
        """
        Update details for the specified labs.

        Warning: All data must be valid (support for partial results is not available
            yet).

        :param lab_data: A list of dictionaries with lab updatable properties.
        :returns: A list of dictionaries with lab properties.
        """
        url = self._url_for("labs")
        return self._session.patch(url, json=lab_data).json()

    def update_labs(self, lab_data: list[dict]) -> list[Lab]:
        """
        Update details for the specified labs.

        Warning: All updated labs must exist locally. Call ClientLibrary(...).all_labs()
            to fetch all labs.
        Warning: All data must be valid (support for partial results is not available
            yet).

        :param lab_data: A list of dictionaries with lab updatable properties.
        :returns: A list of labs objects.
        """
        response = self.patch_labs(lab_data)
        return self._handle_lab_response(response)

    def delete_labs(self, lab_ids: list[str]) -> None:
        """
        Delete the specified labs (from the server only).

        Warning: All selected labs must exist (support for partial results is not
            available yet).

        :param lab_ids: A list of lab IDs.
        :returns: None.
        """
        url = self._url_for("labs")
        # https://github.com/encode/httpx/discussions/1587
        self._session.request("DELETE", url, json=lab_ids)

    def remove_labs(self, lab_ids: list[str]) -> None:
        """
        Delete the specified labs (both from the server and locally).

        Warning: All selected labs must exist (support for partial results is not
            available yet).

        :param lab_ids: A list of lab IDs.
        :returns: None.
        """
        self.delete_labs(lab_ids)
        for lab_id in lab_ids:
            del self._labs[lab_id]

    def post_import(self, lab_data: list[dict]) -> list[dict[str, Any]]:
        """
        Add the specified labs.

        Warning: All data must be valid (support for partial results is not available
            yet).

        :param lab_data: A list of dictionaries with lab properties.
        :returns: A list of dictionaries with lab properties.
        """
        url = self._url_for("import")
        return self._session.post(url, json=lab_data).json()

    def import_labs(self, lab_data: list[dict]) -> list[Lab]:
        """
        Import the specified labs.

        Warning: All data must be valid (support for partial results is not available
            yet).

        :param lab_data: A list of dictionaries with lab properties.
        :returns: A list of labs objects.
        """
        response = self.post_import(lab_data)
        return self._handle_lab_response(response)

    def _handle_lab_response(self, response: list[dict[str, Any]]) -> list[Lab]:
        """
        Turn response into a list of Lab objects.

        :param response: A list of dictionaries with lab properties.
        :returns: A list of lab objects.
        """
        result = []
        for data in response:
            lab_id = data["id"]
            try:
                lab = self._labs[data["id"]]
            except KeyError:
                # lab is not fetched yet
                lab = Lab(
                    data["lab_title"],
                    lab_id,
                    self._session,
                    self._client.username,
                    self._client.password,
                    auto_sync=self._client.auto_sync,
                    auto_sync_interval=self._client.auto_sync_interval,
                    wait_max_iterations=self._client.convergence_wait_max_iter,
                    wait_time=self._client.convergence_wait_time,
                    resource_pool_manager=self._client.resource_pool_management,
                )
            result.append(lab)
        return result

    # LINKS

    def get_links(self, link_ids: list[str] | None = None) -> list[dict[str, Any]]:
        """
        Get details of the specified links (get all by default).

        Warning: All selected links must exist (support for partial results is not
            available yet).

        :param link_ids: An optional list of link IDs (none - get all links).
        :returns: A list of dictionaries with link properties.
        """
        url = self._url_for("links")
        if link_ids:
            # https://github.com/encode/httpx/discussions/1587
            return self._session.request("GET", url, json=link_ids).json()
        else:
            return self._session.get(url).json()

    def fetch_links(self, link_ids: list[str] | None = None) -> list[Link]:
        """
        Get details of the specified links (get all by default).

        Warning: All related labs must exist locally. Call ClientLibrary(...).all_labs()
            to fetch all labs.
        Warning: All selected links must exist (support for partial results is not
            available yet).

        :param link_ids: An optional list of link IDs (none - get all links).
        :returns: A list of links objects.
        """
        response = self.get_links(link_ids=link_ids)
        return self._handle_link_response(response)

    def post_links(self, link_data: list[dict]) -> list[dict[str, Any]]:
        """
        Add the specified links.

        Warning: All data must be valid (support for partial results is not available
            yet).

        :param link_data: A list of dictionaries with link properties.
        :returns: A list of dictionaries with link properties.
        """
        url = self._url_for("links")
        return self._session.post(url, json=link_data).json()

    def create_links(self, link_data: list[dict]) -> list[Link]:
        """
        Add the specified links.

        Warning: All updated labs must exist locally. Call ClientLibrary(...).all_labs()
            to fetch all labs.
        Warning: All data must be valid (support for partial results is not available
            yet).

        :param link_data: A list of dictionaries with link properties.
        :returns: A list of links objects.
        """
        response = self.post_links(link_data=link_data)
        return self._handle_link_response(response)

    def delete_links(self, link_ids: list[str]) -> None:
        """
        Delete the specified links (from the server only).

        Warning: All selected links must exist (support for partial results is not
            available yet).

        :param link_ids: A list of link IDs.
        :returns: None.
        """
        url = self._url_for("links")
        # https://github.com/encode/httpx/discussions/1587
        self._session.request("DELETE", url, json=link_ids)

    def remove_links(self, link_ids: list[str]) -> None:
        """
        Delete the specified links (both from the server and locally).

        Warning: All selected links must exist (support for partial results is not
            available yet).

        :param link_ids: A list of link IDs.
        :returns: None.
        """
        # this is performance-heavy and probably will be removed
        lab_links = [
            (lab, link)
            for lab in self._labs.values()
            for link_id, link in lab._links.items()
            if link_id in link_ids
        ]
        self.delete_links(link_ids)
        for lab, link in lab_links:
            lab._remove_link_local(link)

    def _handle_link_response(self, response: list[dict[str, Any]]) -> list[Link]:
        """
        Turn response into a list of Link objects.

        :param response: A list of dictionaries with link properties.
        :returns: A list of links objects.
        """
        result = []
        for data in response:
            # lab must exist (we may add support for local lab creation if needed)
            lab = self._labs[data["lab_id"]]
            link_id = data["id"]
            try:
                link = lab._links[link_id]
            except KeyError:
                # link is not fetched yet
                interface_a_id = data["interface_a"]
                interface_b_id = data["interface_b"]
                label = data.get("label")
                link = lab._create_link_local(
                    interface_a_id, interface_b_id, link_id, label=label
                )
            result.append(link)
        return result

    # NODES

    def get_nodes(
        self,
        node_ids: list[str] | None = None,
        operational: bool | None = None,
        exclude_configurations: bool | None = None,
    ) -> list[dict[str, Any]]:
        """
        Get details of the specified nodes (get all by default).

        Warning: All selected nodes must exist (support for partial results is not
            available yet).

        :param node_ids: An optional list of node IDs (none - get all nodes).
        :param operational: Whether to include operation data.
        :param exclude_configurations: Whether to exclude configurations.
        :returns: A list of dictionaries with node properties.
        """
        url = (
            f"{self._url_for('nodes')}?operational={operational}"
            f"&exclude_configurations={exclude_configurations}"
        )
        if node_ids:
            # https://github.com/encode/httpx/discussions/1587
            return self._session.request("GET", url, json=node_ids).json()
        else:
            return self._session.get(url).json()

    def fetch_nodes(
        self,
        node_ids: list[str] | None = None,
        operational: bool | None = None,
        exclude_configurations: bool | None = None,
    ) -> list[Node]:
        """
        Get details of the specified nodes (get all by default).

        Warning: All related labs must exist locally. Call ClientLibrary(...).all_labs()
            to fetch all labs.
        Warning: All selected nodes must exist (support for partial results is not
            available yet).

        :param node_ids: An optional list of node IDs (none - get all nodes).
        :param operational: Whether to include operation data.
        :param exclude_configurations: Whether to exclude configurations.
        :returns: A list of nodes objects.
        """
        response = self.get_nodes(
            node_ids=node_ids,
            operational=operational,
            exclude_configurations=exclude_configurations,
        )
        return self._handle_node_response(response)

    def post_nodes(
        self,
        node_data: list[dict],
        populate_interfaces=False,
    ) -> list[dict[str, Any]]:
        """
        Add the specified nodes.

        Warning: All data must be valid (support for partial results is not available
            yet).

        :param node_data: A list of dictionaries with node properties.
        :param populate_interfaces: Whether to automatically create node interfaces.
        :returns: A list of dictionaries with node properties.
        """
        url = f"{self._url_for('nodes')}?populate_interfaces={populate_interfaces}"
        return self._session.post(url, json=node_data).json()

    def create_nodes(
        self,
        node_data: list[dict],
        populate_interfaces=False,
    ) -> list[Node]:
        """
        Add the specified nodes.

        Warning: All updated labs must exist locally. Call ClientLibrary(...).all_labs()
            to fetch all labs.
        Warning: All data must be valid (support for partial results is not available
            yet).

        :param node_data: A list of dictionaries with node properties.
        :param populate_interfaces: Whether to automatically create node interfaces.
        :returns: A list of nodes objects.
        """
        response = self.post_nodes(
            node_data=node_data, populate_interfaces=populate_interfaces
        )
        return self._handle_node_response(response)

    def patch_nodes(self, node_data: list[dict]) -> list[dict[str, Any]]:
        """
        Update details for the specified nodes.

        Warning: All data must be valid (support for partial results is not available
            yet).

        :param node_data: A list of dictionaries with node updatable properties.
        :returns: A list of dictionaries with node properties.
        """
        url = self._url_for("nodes")
        return self._session.patch(url, json=node_data).json()

    def update_nodes(self, node_data: list[dict]) -> list[Node]:
        """
        Update details for the specified nodes.

        Warning: All updated labs must exist locally. Call ClientLibrary(...).all_labs()
            to fetch all labs.
        Warning: All data must be valid (support for partial results is not available
            yet).

        :param node_data: A list of dictionaries with node updatable properties.
        :returns: A list of nodes objects.
        """
        response = self.patch_nodes(node_data)
        # node.update() returns None
        return self._handle_node_response(response)

    def delete_nodes(self, node_ids: list[str]) -> None:
        """
        Delete the specified nodes (from the server only).

        Warning: All selected nodes must exist (support for partial results is not
            available yet).

        :param node_ids: A list of node IDs.
        :returns: None.
        """
        url = self._url_for("nodes")
        # https://github.com/encode/httpx/discussions/1587
        self._session.request("DELETE", url, json=node_ids)

    def remove_nodes(self, node_ids: list[str]) -> None:
        """
        Delete the specified nodes (both from the server and locally).

        Warning: All selected nodes must exist (support for partial results is not
            available yet).

        :param node_ids: A list of node IDs.
        :returns: None.
        """
        # this is performance-heavy and probably will be removed
        lab_nodes = [
            (lab, node)
            for lab in self._labs.values()
            for node_id, node in lab._nodes.items()
            if node_id in node_ids
        ]
        self.delete_nodes(node_ids)
        for lab, node in lab_nodes:
            lab._remove_node_local(node)

    def _handle_node_response(self, response: list[dict[str, Any]]) -> list[Node]:
        """
        Turn response into a list of Node objects.

        :param response: A list of dictionaries with node properties.
        :returns: A list of nodes objects.
        """
        result = []
        for data in response:
            # lab must exist (we may add support for local lab creation if needed)
            lab = self._labs[data.pop("lab_id")]
            node_id = data.pop("id")
            try:
                node = lab._nodes[node_id]
            except KeyError:
                # node is not fetched yet
                data["node_id"] = node_id
                # probably temporary until we unify responses
                data.pop("boot_progress")
                data.pop("state")
                node = lab._create_node_local(**data)
            result.append(node)
        return result
