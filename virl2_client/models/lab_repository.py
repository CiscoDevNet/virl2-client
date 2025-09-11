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
from typing import TYPE_CHECKING, Any

from ..exceptions import LabRepositoryNotFound
from ..utils import get_url_from_template

if TYPE_CHECKING:
    import httpx

_LOGGER = logging.getLogger(__name__)


class LabRepository:
    _URL_TEMPLATES = {"lab_repo": "lab_repos/{repo_id}"}

    def __init__(
        self,
        system,
        id: str,
        url: str,
        name: str,
        folder: str,
    ):
        """
        A lab repository, which provides access to lab templates and resources.

        :param system: The SystemManagement instance.
        :param id: The ID of the lab repository.
        :param url: The URL of the lab repository.
        :param name: The name of the lab repository.
        :param folder: The folder name for the lab repository.
        """
        self._system = system
        self._session: httpx.Client = system._session
        self._id = id
        self._url = url
        self._name = name
        self._folder = folder

    def __str__(self):
        return f"Lab repository: {self._name}"

    def _url_for(self, endpoint, **kwargs) -> str:
        """
        Generate the URL for a given API endpoint.

        :param endpoint: The desired endpoint.
        :param **kwargs: Keyword arguments used to format the URL.
        :returns: The formatted URL.
        """
        kwargs["repo_id"] = self._id
        return get_url_from_template(endpoint, self._URL_TEMPLATES, kwargs)

    @property
    def id(self) -> str:
        """Return the ID of the lab repository."""
        return self._id

    @property
    def url(self) -> str:
        """Return the URL of the lab repository."""
        if hasattr(self._system, "sync_lab_repositories_if_outdated"):
            self._system.sync_lab_repositories_if_outdated()
        elif hasattr(self._system, "lab_repository_management"):
            self._system.lab_repository_management.sync_lab_repositories_if_outdated()
        return self._url

    @property
    def name(self) -> str:
        """Return the name of the lab repository."""
        if hasattr(self._system, "sync_lab_repositories_if_outdated"):
            self._system.sync_lab_repositories_if_outdated()
        elif hasattr(self._system, "lab_repository_management"):
            self._system.lab_repository_management.sync_lab_repositories_if_outdated()
        return self._name

    @property
    def folder(self) -> str:
        """Return the folder name of the lab repository."""
        if hasattr(self._system, "sync_lab_repositories_if_outdated"):
            self._system.sync_lab_repositories_if_outdated()
        elif hasattr(self._system, "lab_repository_management"):
            self._system.lab_repository_management.sync_lab_repositories_if_outdated()
        return self._folder

    def remove(self) -> None:
        """Remove the lab repository."""
        _LOGGER.info(f"Removing lab repository {self}")
        url = self._url_for("lab_repo")
        self._session.delete(url)

        if hasattr(self._system, "_lab_repositories"):
            if self._id in self._system._lab_repositories:
                del self._system._lab_repositories[self._id]
        elif hasattr(self._system, "lab_repository_management"):
            if self._id in self._system.lab_repository_management._lab_repositories:
                del self._system.lab_repository_management._lab_repositories[self._id]


class LabRepositoryManagement:
    """Manage lab repositories."""

    _URL_TEMPLATES = {
        "lab_repos": "lab_repos",
        "lab_repos_refresh": "lab_repos/refresh",
    }

    def __init__(
        self,
        system,
        session: httpx.Client,
        auto_sync: bool = True,
        auto_sync_interval: float = 1.0,
    ) -> None:
        """
        Manage lab repositories.

        :param system: The SystemManagement instance.
        :param session: The httpx-based HTTP client for this session with the server.
        :param auto_sync: A boolean indicating whether auto synchronization is enabled.
        :param auto_sync_interval: The interval in seconds between auto synchronizations.
        """
        self._system = system
        self._session = session
        self.auto_sync = auto_sync
        self.auto_sync_interval = auto_sync_interval
        self._last_sync_lab_repository_time = 0.0
        self._lab_repositories: dict[str, LabRepository] = {}

    def __len__(self) -> int:
        """Return the number of lab repositories."""
        self.sync_lab_repositories_if_outdated()
        return len(self._lab_repositories)

    def _url_for(self, endpoint, **kwargs):
        """
        Generate the URL for a given API endpoint.

        :param endpoint: The desired endpoint.
        :param **kwargs: Keyword arguments used to format the URL.
        :returns: The formatted URL.
        """
        return get_url_from_template(endpoint, self._URL_TEMPLATES, kwargs)

    @property
    def lab_repositories(self) -> dict[str, LabRepository]:
        """Return a dictionary of lab repositories."""
        self.sync_lab_repositories_if_outdated()
        return self._lab_repositories.copy()

    def sync_lab_repositories_if_outdated(self) -> None:
        """Synchronize lab repositories if they are outdated."""
        timestamp = time.time()
        if (
            self.auto_sync
            and timestamp - self._last_sync_lab_repository_time
            > self.auto_sync_interval
        ):
            self.sync_lab_repositories()

    def sync_lab_repositories(self) -> None:
        """Synchronize lab repositories from the server."""
        url = self._url_for("lab_repos")
        lab_repositories = self._session.get(url).json()
        lab_repository_ids = []

        for lab_repository in lab_repositories:
            repo_id = lab_repository.get("id")
            if repo_id not in self._lab_repositories:
                self.add_lab_repository_local(**lab_repository)
            lab_repository_ids.append(repo_id)

        for repo_id in tuple(self._lab_repositories):
            if repo_id not in lab_repository_ids:
                self._lab_repositories.pop(repo_id)
        self._last_sync_lab_repository_time = time.time()

    def get_lab_repositories(self) -> list[dict[str, Any]]:
        """
        Get the list of configured lab repositories.

        :returns: A list of lab repository objects.
        """
        url = self._url_for("lab_repos")
        return self._session.get(url).json()

    def add_lab_repository(self, url: str, name: str, folder: str) -> dict[str, Any]:
        """
        Add a lab repository.

        :param url: The URL of the lab repository.
        :param name: The name of the lab repository.
        :param folder: The folder name for the lab repository.
        :returns: The created lab repository data.
        """
        repo_url = self._url_for("lab_repos")
        data = {"url": url, "name": name, "folder": folder}
        result = self._session.post(repo_url, json=data).json()

        self.add_lab_repository_local(**result)
        return result

    def refresh_lab_repositories(self) -> dict[str, dict[str, Any]]:
        """
        Performs a git pull on each configured lab repository and returns the result.

        :returns: A dictionary containing the refresh status for each repository.
        """
        url = self._url_for("lab_repos_refresh")
        return self._session.put(url).json()

    def add_lab_repository_local(
        self,
        id: str,
        url: str,
        name: str,
        folder: str,
    ) -> LabRepository:
        """
        Add a lab repository locally.

        :param id: The unique identifier of the lab repository.
        :param url: The URL of the lab repository.
        :param name: The name of the lab repository.
        :param folder: The folder name for the lab repository.
        :returns: The newly created lab repository object.
        """
        new_lab_repository = LabRepository(self._system, id, url, name, folder)
        self._lab_repositories[id] = new_lab_repository
        return new_lab_repository

    def get_lab_repository(self, repo_id: str) -> LabRepository:
        """
        Get a lab repository by its ID.

        :param repo_id: The ID of the lab repository.
        :returns: The lab repository with the specified ID.
        :raises LabRepositoryNotFound: If no lab repository with the specified ID is found.
        """
        self.sync_lab_repositories_if_outdated()
        if repo_id not in self._lab_repositories:
            raise LabRepositoryNotFound(repo_id)
        return self._lab_repositories[repo_id]

    def get_lab_repository_by_name(self, name: str) -> LabRepository:
        """
        Get a lab repository by its name.

        :param name: The name of the lab repository.
        :returns: The lab repository with the specified name.
        :raises LabRepositoryNotFound: If no lab repository with the specified name is found.
        """
        self.sync_lab_repositories_if_outdated()
        for repo in self._lab_repositories.values():
            if repo.name == name:
                return repo
        raise LabRepositoryNotFound(name)
