#
# This file is part of CML 2
#
# Copyright 2021 Cisco Systems Inc.
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

"""Tests for Node and Image definitions."""

import json

import pytest
import requests

from virl2_client import ClientLibrary

pytestmark = [pytest.mark.integration]

node_def_id = "integration_test_node_definition"
image_def_id = "integration_test_image_definition"
image_file_name = "integration_test_dummy.qcow2"
image_def = {
    "id": image_def_id,
    "node_definition_id": "alpine",
    "label": "Integration Test Dummy",
    "disk_image": image_file_name,
}
node_def = json.dumps(
    {
        "id": node_def_id,
        "general": {"nature": "server", "read_only": False},
        "device": {
            "interfaces": {
                "has_loopback_zero": True,
                "physical": ["eth0"],
                "serial_ports": 1,
                "loopback": ["l0"],
            }
        },
        "ui": {"visible": True, "label_prefix": "-b", "icon": "server", "label": "a"},
        "sim": {"linux_native": {"libvirt_domain_driver": "none", "driver": "server"}},
        "boot": {"timeout": 1},
        "inherited": {
            "image": {
                "ram": True,
                "cpus": True,
                "cpu_limit": True,
                "data_volume": True,
                "boot_disk_size": True,
            },
            "node": {
                "ram": True,
                "cpus": True,
                "cpu_limit": True,
                "data_volume": True,
                "boot_disk_size": True,
            },
        },
        "configuration": {"generator": {"driver": None}},
    }
)


@pytest.fixture(params=["empty", "basic_string", "only_id", "missing_id"])
def invalid_node_def(request) -> str:
    definitions = {
        "empty": json.dumps(None),
        "basic_string": "abc",
        "only_id": json.dumps({"id": node_def_id}),
        "missing_id": json.dumps({"general": {}}),
        # TODO: anything else?
    }
    return definitions[request.param]


@pytest.fixture
def cleanup_node_def(client_library_session: ClientLibrary):
    """Remove the test node def before test, if they exist.
    Remove them again after the test."""
    try:
        client_library_session.definitions.remove_node_definition(node_def_id)
    except requests.exceptions.HTTPError:
        pass

    yield

    try:
        client_library_session.definitions.remove_node_definition(node_def_id)
    except requests.exceptions.HTTPError:
        pass


@pytest.fixture
def cleanup_image_def(client_library_session: ClientLibrary):
    """Remove the test image def and image file before test, if they exists.
    Remove them again after the test."""
    try:
        client_library_session.definitions.remove_image_definition(image_def_id)
    except requests.exceptions.HTTPError:
        pass
    try:
        client_library_session.definitions.remove_dropfolder_image(image_file_name)
    except requests.exceptions.HTTPError:
        pass

    yield

    try:
        client_library_session.definitions.remove_image_definition(image_def_id)
    except requests.exceptions.HTTPError:
        pass
    try:
        client_library_session.definitions.remove_dropfolder_image(image_file_name)
    except requests.exceptions.HTTPError:
        pass


def test_upload_node_definition(
    cleanup_node_def, client_library_session: ClientLibrary
):
    """Add a valid Node definition, verify it was added."""

    client_library_session.definitions.upload_node_definition(body=node_def)

    node_defs = client_library_session.definitions.node_definitions()
    assert node_def_id in [definition["id"] for definition in node_defs]


def test_remove_non_existent_node_definition(
    cleanup_node_def, client_library_session: ClientLibrary
):
    """Try to remove an Node Definition that does not exist, expect a 404."""
    with pytest.raises(requests.exceptions.HTTPError) as err:
        client_library_session.definitions.remove_node_definition(
            definition_id=node_def_id
        )
    assert err.value.response.status_code == 404


def test_upload_node_definition_invalid_body(
    cleanup_node_def, invalid_node_def, client_library_session: ClientLibrary
):
    """Try adding an invalid Node Definition, expect a 400."""
    with pytest.raises(requests.exceptions.HTTPError) as err:
        client_library_session.definitions.upload_node_definition(body=invalid_node_def)
    assert err.value.response.status_code == 400


def test_create_image_definition_with_no_image_file(
    cleanup_image_def, client_library_session: ClientLibrary, change_test_dir
):
    """Try creating an Image Definition with a non-existent image file. Expect a 404."""

    with pytest.raises(requests.exceptions.HTTPError) as err:
        client_library_session.definitions.upload_image_definition(image_def, json=True)
    assert err.value.response.status_code == 404


def test_upload_image_file(
    cleanup_image_def, client_library_session: ClientLibrary, change_test_dir
):
    """Upload an image file, check that it was uploaded and that other images are still there."""
    images = client_library_session.definitions.download_image_file_list()
    assert image_file_name not in images

    client_library_session.definitions.upload_image_file(f"test_data/{image_file_name}")

    new_images = client_library_session.definitions.download_image_file_list()
    for image in images:
        assert image in new_images
    assert image_file_name in new_images


def test_add_image_definition(
    cleanup_image_def, client_library_session: ClientLibrary, change_test_dir
):
    """Upload an image file, use it to add a new image definition for the Alpine node and verify."""
    alpine_defs = (
        client_library_session.definitions.image_definitions_for_node_definition(
            "alpine"
        )
    )

    client_library_session.definitions.upload_image_file(f"test_data/{image_file_name}")
    client_library_session.definitions.upload_image_definition(image_def, json=True)

    new_alpine_defs = (
        client_library_session.definitions.image_definitions_for_node_definition(
            "alpine"
        )
    )
    # Make sure all previous definitions are still there
    for definition in alpine_defs:
        assert definition in new_alpine_defs
    # Check that the definition was added
    assert image_def_id in [definition["id"] for definition in new_alpine_defs]
    # Check that nothing else was added
    assert len(new_alpine_defs) == len(alpine_defs) + 1

    # Image file should be moved out of dropfolder when in use.
    assert (
        image_file_name
        not in client_library_session.definitions.download_image_file_list()
    )


def test_remove_image_definition(
    cleanup_image_def, client_library_session: ClientLibrary, change_test_dir
):
    """Remove a created image definition, and its respective image file."""

    alpine_defs = (
        client_library_session.definitions.image_definitions_for_node_definition(
            "alpine"
        )
    )

    client_library_session.definitions.upload_image_file(f"test_data/{image_file_name}")
    client_library_session.definitions.upload_image_definition(image_def, json=True)

    client_library_session.definitions.remove_image_definition(image_def_id)

    new_alpine_defs = (
        client_library_session.definitions.image_definitions_for_node_definition(
            "alpine"
        )
    )
    # Check that the definition was removed
    assert image_def_id not in [definition["id"] for definition in new_alpine_defs]
    # Check that nothing else was changed or removed
    for definition in alpine_defs:
        if definition["id"] == image_def_id:
            pass
        else:
            assert definition in new_alpine_defs

    # Check that the image file was moved back to dropfolder
    assert (
        image_file_name in client_library_session.definitions.download_image_file_list()
    )

    # Remove the image and check
    client_library_session.definitions.remove_dropfolder_image(image_file_name)

    assert (
        image_file_name
        not in client_library_session.definitions.download_image_file_list()
    )
