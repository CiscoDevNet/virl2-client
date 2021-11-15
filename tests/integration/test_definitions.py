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

import json
from typing import List

import pytest
import requests

from virl2_client import ClientLibrary

pytestmark = [pytest.mark.integration]


def test_remove_non_existent_node_definition(client_library_session: ClientLibrary):
    def_id = "non_existent_node_definition"
    with pytest.raises(requests.exceptions.HTTPError) as err:
        client_library_session.definitions.remove_node_definition(definition_id=def_id)
    assert err.value.response.status_code == 404


def test_upload_node_definition_invalid_body(client_library_session: ClientLibrary):
    with pytest.raises(requests.exceptions.HTTPError) as err:
        client_library_session.definitions.upload_node_definition(body=json.dumps(None))
    assert err.value.response.status_code == 400

    with pytest.raises(requests.exceptions.HTTPError) as err:
        client_library_session.definitions.upload_node_definition(
            body=json.dumps({"id": "test1"})
        )
    assert err.value.response.status_code == 400

    with pytest.raises(requests.exceptions.HTTPError) as err:
        client_library_session.definitions.upload_node_definition(
            body=json.dumps({"general": {}})
        )
    assert err.value.response.status_code == 400


def test_add_image_definition(client_library_session: ClientLibrary, change_test_dir):
    img_id = "some_test_image"
    # Remove first, in case it does exist.
    try:
        client_library_session.definitions.remove_image_definition(img_id)
    except requests.exceptions.HTTPError:
        pass
    image_file = "dummy.qcow2"
    # Remove first, in case it does exist.
    try:
        client_library_session.definitions.remove_dropfolder_image(image_file)
    except requests.exceptions.HTTPError:
        pass
    # Unable to create an image definition with no image file.
    img_def = dict(
        id=img_id, node_definition_id="alpine", label="dummy", disk_image=image_file
    )
    with pytest.raises(requests.exceptions.HTTPError) as err:
        client_library_session.definitions.upload_image_definition(img_def, json=True)
    assert err.value.response.status_code == 404
    # Get a list of currently uploaded image files.
    images = client_library_session.definitions.download_image_file_list()
    new_images = images.copy()
    new_images.append(image_file)
    new_images.sort()
    # Upload an image file first.
    client_library_session.definitions.upload_image_file(f"test_data/{image_file}")
    assert client_library_session.definitions.download_image_file_list() == new_images
    number_of_alpine_defs = len(
        client_library_session.definitions.image_definitions_for_node_definition(
            "alpine"
        )
    )
    # Now it's possible to create an image definition.
    client_library_session.definitions.upload_image_definition(img_def, json=True)
    img_defs = client_library_session.definitions.image_definitions_for_node_definition(
        "alpine"
    )
    assert isinstance(img_defs, List)
    assert len(img_defs) == number_of_alpine_defs + 1
    assert next(img_def for img_def in img_defs if img_def.get("id") == img_id)
    # Image file is not in the dropfolder.
    assert client_library_session.definitions.download_image_file_list() == images
    client_library_session.definitions.remove_image_definition(img_id)
    # The image def was successfully removed.
    img_defs = client_library_session.definitions.image_definitions_for_node_definition(
        "alpine"
    )
    assert img_id not in img_defs
    assert len(img_defs) == number_of_alpine_defs
    # The image file was moved back to the dropfolder after the definition was removed.
    assert client_library_session.definitions.download_image_file_list() == new_images
    client_library_session.definitions.remove_dropfolder_image(image_file)
    # The image file was successfully removed.
    assert client_library_session.definitions.download_image_file_list() == images
    # It cannot be removed again.
    with pytest.raises(requests.exceptions.HTTPError) as err:
        client_library_session.definitions.remove_dropfolder_image(image_file)
    assert err.value.response.status_code == 404
