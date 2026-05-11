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
"""Tests for LabRepository, LabRepositoryManagement, and system lab repository workflows."""

from unittest.mock import Mock, patch

import httpx
import pytest
import respx

from virl2_client.exceptions import ElementNotFound, LabRepositoryNotFound
from virl2_client.models import LabRepository, LabRepositoryManagement
from virl2_client.virl2_client import ClientLibrary

MOCK_LAB_REPOSITORY_1 = {
    "id": "repo-123",
    "url": "https://github.com/cisco/lab-templates.git",
    "name": "cisco-templates",
    "folder": "cisco_labs",
}

MOCK_LAB_REPOSITORY_2 = {
    "id": "repo-456",
    "url": "https://github.com/example/custom-labs.git",
    "name": "custom-labs",
    "folder": "custom_folder",
}

MOCK_LAB_REPOSITORIES_LIST = [MOCK_LAB_REPOSITORY_1, MOCK_LAB_REPOSITORY_2]


@pytest.fixture
def mock_lab_repository_management() -> LabRepositoryManagement:
    """Create a lab-repository management object backed by mocks.

    :returns: A local LabRepositoryManagement instance.
    """
    session_mock = Mock()
    system_mock = Mock()
    lab_repo_mgmt = LabRepositoryManagement(system_mock, session_mock, auto_sync=False)
    return lab_repo_mgmt


@pytest.fixture
def system_with_repos(
    mock_lab_repository_management: LabRepositoryManagement,
) -> LabRepositoryManagement:
    """Build a populated repository-management fixture.

    :param mock_lab_repository_management: Empty repository manager fixture.
    :returns: Repository manager preloaded with two repositories.
    """
    lab_repo_mgmt = mock_lab_repository_management
    for repo_data in MOCK_LAB_REPOSITORIES_LIST:
        data = dict(repo_data)
        lab_repo_mgmt.add_lab_repository_local(data.pop("id"), **data)
    return lab_repo_mgmt


def test_lab_repository_initialization(
    mock_lab_repository_management: LabRepositoryManagement,
) -> None:
    """Validate LabRepository initialization and identity fields.

    :param mock_lab_repository_management: Repository manager fixture.
    """
    data = dict(MOCK_LAB_REPOSITORY_1)
    repo = LabRepository(mock_lab_repository_management, data.pop("id"), **data)

    assert repo.id == MOCK_LAB_REPOSITORY_1["id"]
    assert repo._url == MOCK_LAB_REPOSITORY_1["url"]
    assert repo._name == MOCK_LAB_REPOSITORY_1["name"]
    assert repo._folder == MOCK_LAB_REPOSITORY_1["folder"]
    assert repo._manager is mock_lab_repository_management
    assert str(repo) == f"Lab repository: {MOCK_LAB_REPOSITORY_1['name']}"


def test_lab_repository_folder_defaults_to_none(
    mock_lab_repository_management: LabRepositoryManagement,
) -> None:
    """LabRepository.folder defaults to None when omitted."""
    repo = LabRepository(
        mock_lab_repository_management,
        repo_id="no-folder",
        url="https://example.com/repo.git",
        name="no-folder-repo",
    )
    assert repo._folder is None


def test_lab_repo_properties_sync(
    mock_lab_repository_management: LabRepositoryManagement,
) -> None:
    """Validate sync behavior for id vs mutable repository properties.

    :param mock_lab_repository_management: Repository manager fixture.
    """
    repo = LabRepository(
        manager=mock_lab_repository_management,
        repo_id="test-id",
        url="https://github.com/test/repo.git",
        name="test-repo",
        folder="test_folder",
    )

    mock_lab_repository_management.sync_lab_repositories_if_outdated = Mock()

    _ = repo.id
    mock_lab_repository_management.sync_lab_repositories_if_outdated.assert_not_called()

    _ = repo.url
    assert (
        mock_lab_repository_management.sync_lab_repositories_if_outdated.call_count == 1
    )

    _ = repo.name
    assert (
        mock_lab_repository_management.sync_lab_repositories_if_outdated.call_count == 2
    )

    _ = repo.folder
    assert (
        mock_lab_repository_management.sync_lab_repositories_if_outdated.call_count == 3
    )


def test_lab_repository_remove(
    mock_lab_repository_management: LabRepositoryManagement,
) -> None:
    """Ensure remove() calls DELETE and drops local repository state.

    :param mock_lab_repository_management: Repository manager fixture.
    """
    lab_repo_mgmt = mock_lab_repository_management
    repo = LabRepository(
        manager=lab_repo_mgmt,
        repo_id="test-id",
        url="https://github.com/test/repo.git",
        name="test-repo",
        folder="test_folder",
    )

    lab_repo_mgmt._lab_repositories["test-id"] = repo

    repo._url_for = Mock(return_value="lab_repos/test-id")
    repo.remove()
    lab_repo_mgmt._session.delete.assert_called_once_with("lab_repos/test-id")

    assert "test-id" not in lab_repo_mgmt._lab_repositories


def test_lab_repos_property_sync(
    mock_lab_repository_management: LabRepositoryManagement,
) -> None:
    """Ensure lab_repositories property syncs and returns a copy.

    :param mock_lab_repository_management: Repository manager fixture.
    """
    lab_repo_mgmt = mock_lab_repository_management
    lab_repo_mgmt.sync_lab_repositories_if_outdated = Mock()

    lab_repo_mgmt._lab_repositories = {
        "repo-123": Mock(),
        "repo-456": Mock(),
    }

    result = lab_repo_mgmt.lab_repositories
    lab_repo_mgmt.sync_lab_repositories_if_outdated.assert_called_once()

    assert result is not lab_repo_mgmt._lab_repositories
    assert len(result) == 2


@patch("time.time")
@pytest.mark.parametrize(
    "auto_sync,interval,last_sync,now,expect_sync",
    [
        (False, 0, 0, 10, False),
        (True, 100, 5, 10, False),
        (True, 0, 0, 10, True),
    ],
)
def test_sync_lab_repos_conditions(
    mock_time: Mock,
    mock_lab_repository_management: LabRepositoryManagement,
    auto_sync: bool,
    interval: float,
    last_sync: float,
    now: float,
    expect_sync: bool,
) -> None:
    """Check conditional sync behavior for auto-sync and staleness."""
    mock_time.return_value = now
    lab_repo_mgmt = mock_lab_repository_management
    lab_repo_mgmt.sync_lab_repositories = Mock()
    lab_repo_mgmt.auto_sync = auto_sync
    lab_repo_mgmt.auto_sync_interval = interval
    lab_repo_mgmt._last_sync_lab_repository_time = last_sync
    lab_repo_mgmt.sync_lab_repositories_if_outdated()
    if expect_sync:
        lab_repo_mgmt.sync_lab_repositories.assert_called_once()
    else:
        lab_repo_mgmt.sync_lab_repositories.assert_not_called()


def test_add_lab_repository_local(
    mock_lab_repository_management: LabRepositoryManagement,
) -> None:
    """Ensure local-add helper creates and stores LabRepository.

    :param mock_lab_repository_management: Repository manager fixture.
    """
    lab_repo_mgmt = mock_lab_repository_management

    data = dict(MOCK_LAB_REPOSITORY_1)
    repo = lab_repo_mgmt.add_lab_repository_local(data.pop("id"), **data)

    assert isinstance(repo, LabRepository)
    assert repo.id == "repo-123"
    assert repo._url == "https://github.com/cisco/lab-templates.git"
    assert repo._name == "cisco-templates"
    assert repo._folder == "cisco_labs"

    assert "repo-123" in lab_repo_mgmt._lab_repositories
    assert lab_repo_mgmt._lab_repositories["repo-123"] is repo


def test_get_lab_repo_by_id(
    system_with_repos: LabRepositoryManagement,
) -> None:
    """get_lab_repository returns repo by id."""
    lab_repo_mgmt = system_with_repos
    lab_repo_mgmt.sync_lab_repositories_if_outdated = Mock()
    repo = lab_repo_mgmt.get_lab_repository("repo-123")
    assert repo.id == "repo-123"
    assert repo._name == "cisco-templates"


def test_get_lab_repo_by_id_missing(
    system_with_repos: LabRepositoryManagement,
) -> None:
    """get_lab_repository raises LabRepositoryNotFound for missing id.

    NOTE: LLM-generated test -- verify for correctness.
    """
    lab_repo_mgmt = system_with_repos
    lab_repo_mgmt.sync_lab_repositories_if_outdated = Mock()
    with pytest.raises(LabRepositoryNotFound) as exc_info:
        lab_repo_mgmt.get_lab_repository("nonexistent-repo")
    assert "nonexistent-repo" in str(exc_info.value)


def test_get_lab_repo_by_name(
    system_with_repos: LabRepositoryManagement,
) -> None:
    """get_lab_repository_by_name returns repo by name."""
    lab_repo_mgmt = system_with_repos
    lab_repo_mgmt.sync_lab_repositories_if_outdated = Mock()
    repo = lab_repo_mgmt.get_lab_repository_by_name("cisco-templates")
    assert repo.id == "repo-123"
    assert repo._name == "cisco-templates"


def test_get_lab_repo_by_name_missing(
    system_with_repos: LabRepositoryManagement,
) -> None:
    """get_lab_repository_by_name raises LabRepositoryNotFound for missing name.

    NOTE: LLM-generated test -- verify for correctness.
    """
    lab_repo_mgmt = system_with_repos
    lab_repo_mgmt.sync_lab_repositories_if_outdated = Mock()
    with pytest.raises(LabRepositoryNotFound) as exc_info:
        lab_repo_mgmt.get_lab_repository_by_name("non-existent-name")
    assert "non-existent-name" in str(exc_info.value)


def test_get_lab_repositories_api_call(
    mock_lab_repository_management: LabRepositoryManagement,
) -> None:
    """Verify repository list API call and returned JSON passthrough.

    :param mock_lab_repository_management: Repository manager fixture.
    """
    lab_repo_mgmt = mock_lab_repository_management

    mock_response = Mock()
    mock_response.json.return_value = MOCK_LAB_REPOSITORIES_LIST
    lab_repo_mgmt._session.get.return_value = mock_response

    lab_repo_mgmt._url_for = Mock(return_value="lab_repos")

    result = lab_repo_mgmt.get_lab_repositories()

    assert result == MOCK_LAB_REPOSITORIES_LIST
    lab_repo_mgmt._url_for.assert_called_once_with("lab_repos")
    lab_repo_mgmt._session.get.assert_called_once_with("lab_repos")


def test_add_lab_repository_api_call(
    mock_lab_repository_management: LabRepositoryManagement,
) -> None:
    """Verify add API call payload and local storage update invocation.

    :param mock_lab_repository_management: Repository manager fixture.
    """
    lab_repo_mgmt = mock_lab_repository_management

    mock_response = Mock()
    mock_response.json.return_value = dict(MOCK_LAB_REPOSITORY_1)
    lab_repo_mgmt._session.post.return_value = mock_response

    lab_repo_mgmt._url_for = Mock(return_value="lab_repos")
    lab_repo_mgmt.add_lab_repository_local = Mock(return_value=Mock())

    result = lab_repo_mgmt.add_lab_repository(
        url="https://github.com/cisco/lab-templates.git",
        name="cisco-templates",
        folder="cisco_labs",
    )

    expected_data = {
        "url": "https://github.com/cisco/lab-templates.git",
        "name": "cisco-templates",
        "folder": "cisco_labs",
    }
    assert result == expected_data
    lab_repo_mgmt._url_for.assert_called_once_with("lab_repos")
    lab_repo_mgmt._session.post.assert_called_once_with("lab_repos", json=expected_data)

    lab_repo_mgmt.add_lab_repository_local.assert_called_once_with(
        "repo-123",
        url="https://github.com/cisco/lab-templates.git",
        name="cisco-templates",
        folder="cisco_labs",
    )


def test_refresh_lab_repositories_api_call(
    mock_lab_repository_management: LabRepositoryManagement,
) -> None:
    """Verify refresh API call and refresh result handling.

    :param mock_lab_repository_management: Repository manager fixture.
    """
    lab_repo_mgmt = mock_lab_repository_management

    refresh_response = {
        "repo-123": {"status": "success", "message": "Updated successfully"},
        "repo-456": {"status": "error", "message": "Failed to pull"},
    }
    mock_response = Mock()
    mock_response.json.return_value = refresh_response
    lab_repo_mgmt._session.put.return_value = mock_response

    lab_repo_mgmt._url_for = Mock(return_value="lab_repos/refresh")
    result = lab_repo_mgmt.refresh_lab_repositories()

    assert result == refresh_response
    lab_repo_mgmt._url_for.assert_called_once_with("lab_repos_refresh")
    lab_repo_mgmt._session.put.assert_called_once_with("lab_repos/refresh")


@patch("time.time")
def test_sync_lab_repositories_behavior(
    mock_time: Mock,
    mock_lab_repository_management: LabRepositoryManagement,
) -> None:
    """Ensure sync preserves, adds, and removes repositories as expected.

    :param mock_time: Mocked time.time function.
    :param mock_lab_repository_management: Repository manager fixture.
    """
    mock_time.return_value = 1234567890.0
    lab_repo_mgmt = mock_lab_repository_management

    data1 = dict(MOCK_LAB_REPOSITORY_1)
    lab_repo_mgmt.add_lab_repository_local(data1.pop("id"), **data1)
    data2 = dict(MOCK_LAB_REPOSITORY_2)
    lab_repo_mgmt.add_lab_repository_local(data2.pop("id"), **data2)

    new_repo_data = {
        "id": "repo-789",
        "url": "https://github.com/new/repo.git",
        "name": "new-repo",
        "folder": "new_folder",
    }

    mock_response = Mock()
    mock_response.json.return_value = [dict(MOCK_LAB_REPOSITORY_1), new_repo_data]
    lab_repo_mgmt._session.get.return_value = mock_response
    lab_repo_mgmt._url_for = Mock(return_value="lab_repos")

    original_repo_123 = lab_repo_mgmt._lab_repositories["repo-123"]
    original_name = original_repo_123.name

    lab_repo_mgmt.sync_lab_repositories()

    assert lab_repo_mgmt._lab_repositories["repo-123"] is original_repo_123
    assert original_repo_123.name == original_name

    assert "repo-789" in lab_repo_mgmt._lab_repositories
    assert lab_repo_mgmt._lab_repositories["repo-789"].name == "new-repo"

    assert "repo-456" not in lab_repo_mgmt._lab_repositories

    assert len(lab_repo_mgmt._lab_repositories) == 2

    assert lab_repo_mgmt._last_sync_lab_repository_time == 1234567890.0


def test_lab_repository_not_found_exception() -> None:
    """Verify LabRepositoryNotFound inheritance and message formatting."""
    exc = LabRepositoryNotFound("test-repo-id")
    assert "test-repo-id" in str(exc)
    assert isinstance(exc, ElementNotFound)
    assert isinstance(exc, KeyError)


@respx.mock
def test_lab_repository_end_to_end_workflow() -> None:
    """Run an end-to-end repository workflow via mocked REST endpoints.

    :raises LabRepositoryNotFound: On post-delete lookup.
    """
    respx.post("https://localhost/api/v0/authenticate").respond(json="fake_token")
    respx.get("https://localhost/api/v0/authentication").respond(
        200,
        json={
            "username": "username",
            "id": "6c7dd461-1cbe-428f-bdd5-545a0d766ed7",
            "token": "BOGUS_TOKEN",
            "admin": True,
            "error": None,
        },
    )

    respx.get("https://localhost/api/v0/system_information").respond(
        json={"version": "2.10.0"}
    )

    deleted = [False]

    def get_lab_repos_response(request: httpx.Request) -> httpx.Response:
        """Return dynamic repository list based on mock workflow state.

        :param request: Incoming mocked request object.
        :returns: Mocked HTTP response with repository payload.
        """
        _ = request
        if deleted[0]:
            return httpx.Response(200, json=[])
        elif len(respx.calls) >= 4:
            return httpx.Response(200, json=[MOCK_LAB_REPOSITORY_1])
        else:
            return httpx.Response(200, json=[])

    def delete_lab_repo_response(request: httpx.Request) -> httpx.Response:
        """Mark repository as deleted in mocked backend state.

        :param request: Incoming mocked request object.
        :returns: Successful delete response.
        """
        _ = request
        deleted[0] = True
        return httpx.Response(200)

    respx.get("https://localhost/api/v0/lab_repos").mock(
        side_effect=get_lab_repos_response
    )
    respx.post("https://localhost/api/v0/lab_repos").respond(json=MOCK_LAB_REPOSITORY_1)
    respx.delete("https://localhost/api/v0/lab_repos/repo-123").mock(
        side_effect=delete_lab_repo_response
    )

    client = ClientLibrary("https://localhost", "admin", "admin")

    lab_repo_mgmt = LabRepositoryManagement(
        system=client.system_management,
        session=client._session,
        auto_sync=True,
        auto_sync_interval=0.001,
    )

    repos = lab_repo_mgmt.lab_repositories
    assert len(repos) == 0

    result = lab_repo_mgmt.add_lab_repository(
        url="https://github.com/cisco/lab-templates.git",
        name="cisco-templates",
        folder="cisco_labs",
    )
    expected = {k: v for k, v in MOCK_LAB_REPOSITORY_1.items() if k != "id"}
    assert result == expected

    repo = lab_repo_mgmt.get_lab_repository("repo-123")
    assert repo.id == "repo-123"
    assert repo.name == "cisco-templates"

    repo_by_name = lab_repo_mgmt.get_lab_repository_by_name("cisco-templates")
    assert repo_by_name.id == "repo-123"

    repo.remove()

    lab_repo_mgmt.sync_lab_repositories()

    with pytest.raises(LabRepositoryNotFound):
        lab_repo_mgmt.get_lab_repository("repo-123")


def test_lab_repo_management_len() -> None:
    """__len__ syncs and returns count.

    NOTE: LLM-generated test -- verify for correctness.
    """
    mgr = LabRepositoryManagement(system=Mock(), session=Mock(), auto_sync=False)
    mgr.sync_lab_repositories_if_outdated = Mock()
    mgr._lab_repositories = {"a": Mock(), "b": Mock()}
    assert len(mgr) == 2
    mgr.sync_lab_repositories_if_outdated.assert_called_once()
