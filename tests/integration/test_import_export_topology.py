#
# This file is part of VIRL 2
# Copyright (c) 2019-2022, Cisco Systems, Inc.
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

"""Tests for importing and exporting topology files."""
import copy
import requests
import pytest
import yaml

from virl2_client import ClientLibrary


pytestmark = [pytest.mark.integration, pytest.mark.nomock]

TEST_TOPOLOGIES_YAML = [
    "mixed-0.0.1.yaml",
    "mixed-0.0.4.yaml",
    "mixed-0.0.5.yaml",
    "mixed-0.1.0.yaml",
]

TEST_TOPOLOGIES_VIRL = [
    "mixed.virl",
]

TOPOLOGY_ID_KEYS = [
    "id",
    "lab_id",
    "node",
    "node_a",
    "node_b",
    "interface_a",
    "interface_b",
]


# TODO: also import .virl topology


def _import(topology: dict, client):
    with pytest.raises(requests.exceptions.HTTPError) as err:
        client.import_lab(topology=yaml.safe_dump(topology))
    assert err.value.response.status_code == 400


def test_import_validation(client_library_session: ClientLibrary):
    """Try requests with topology prohibited by schema"""
    cl = client_library_session
    # minimal working topology
    topology = {"version": "0.1.0", "nodes": [], "links": []}
    # version not allowed
    topo = copy.deepcopy(topology)
    topo["version"] = "0.1.1"
    _import(topo, cl)
    # missing version
    topo = copy.deepcopy(topology)
    del topo["version"]
    _import(topo, cl)
    # missing nodes
    topo = copy.deepcopy(topology)
    del topo["nodes"]
    _import(topo, cl)
    # missing links
    topo = copy.deepcopy(topology)
    del topo["links"]
    _import(topo, cl)
    # node missing x, y, label, node_definition
    topo = copy.deepcopy(topology)
    topo["nodes"] = [{"cpu": 2}]
    _import(topo, cl)
    # link missing interface_{a,b} attributes
    topo = copy.deepcopy(topology)
    topo["links"] = [{"id": "l1"}]
    _import(topo, cl)
    # interface missing node attribute
    topo = copy.deepcopy(topology)
    topo["nodes"] = [
        {
            "id": "n1",
            "x": 50,
            "y": 100,
            "label": "server1",
            "node_definition": "server",
            "interfaces": [{"id:": "i1"}],
        }
    ]
    _import(topo, cl)


@pytest.mark.parametrize(argnames="topology", argvalues=TEST_TOPOLOGIES_YAML)
def test_import_export_yaml(
    client_library_session: ClientLibrary,
    topology,
    change_test_dir,
    cleanup_test_labs,
    tmpdir,
):
    """Use the API to import a topology from YAML file, export it,
    then import it back and compare with the initial import.
    """

    imported_lab, reimported_lab = export_reimport_verify(
        client_library_session, topology, tmpdir
    )

    # YAML specific verification
    if "0.0.1" in topology:
        return

    for lab in [imported_lab, reimported_lab]:
        node = lab.get_node_by_label("iosv-0")
        assert node.node_definition == "iosv"
        assert sorted(node.tags()) == ["core", "test_tag"]
        assert node.cpu_limit == 50
        assert node.ram == 2048
        # node definition disallows setting these; here
        # they are 0 instead of None as in the backend
        assert node.cpus == 0
        assert node.boot_disk_size == 0
        assert node.data_volume == 0

        node = lab.get_node_by_label("lxc-0")
        assert node.node_definition == "alpine"
        assert sorted(node.tags()) == ["test_tag"]
        assert node.cpu_limit == 80
        assert node.ram == 3072
        assert node.cpus == 6
        assert node.boot_disk_size == 30
        assert node.data_volume == 10


@pytest.mark.parametrize(argnames="topology", argvalues=TEST_TOPOLOGIES_VIRL)
def test_import_export_virl(
    client_library_session: ClientLibrary,
    topology,
    change_test_dir,
    cleanup_test_labs,
    tmpdir,
):
    """Use the API to import a topology from .virl file, export it,
    then import it back and compare with the initial import.
    """

    _, _ = export_reimport_verify(client_library_session, topology, tmpdir)

    # VIRL specific verification
    # nothing for now


def export_reimport_verify(client_library_session: ClientLibrary, topology, tmpdir):
    """Core of the import_export tests, compatible with both .yaml and .virl topologies."""

    # Import lab from test data file
    reimported_lab_title = "export_import_test.yaml"
    topology_file_path = f"test_data/{topology}"

    imported_lab = client_library_session.import_lab_from_path(topology_file_path)

    # Export the lab we just imported, save to YAML file
    exported_lab_yaml = imported_lab.download()

    exported_file_path = tmpdir.mkdir("yaml").join(reimported_lab_title)
    exported_file_path.write(exported_lab_yaml)

    # Import the lab from the exported YAML file
    reimported_lab = client_library_session.import_lab_from_path(exported_file_path)

    # Get the topology data for each lab
    url = (
        client_library_session._context.base_url
        + f"labs/{imported_lab._lab_id}/topology"
    )
    response = client_library_session._context.session.get(url)
    response.raise_for_status()
    imported_lab_data = response.json()

    url = (
        client_library_session._context.base_url
        + f"labs/{reimported_lab._lab_id}/topology"
    )
    response = client_library_session._context.session.get(url)
    response.raise_for_status()
    reimported_lab_data = response.json()

    # Compare the initial import with the reimport
    for item in ["description"]:
        assert imported_lab_data["lab"][item] == reimported_lab_data["lab"][item]

    lab_notes = imported_lab_data["lab"]["notes"]
    if not lab_notes:
        # If the lab had no notes, the reimport should be empty as well.
        assert lab_notes == reimported_lab_data["lab"]["notes"]
    else:
        # Import warnings are appended to lab notes, if there are any the re-import should have them twice
        # We don't know if they're import warnings or actual notes, so do nothing
        pass

    compare_structures(imported_lab_data, reimported_lab_data)

    return imported_lab, reimported_lab


def compare_structures(original: dict, compared: dict):
    # Match all IDs for consistency, they are autogenerated on import
    id_map = {}

    def extract_interfaces_from_nodes(nodes_list: list):
        interfaces = []
        for node in nodes_list:
            for interface in node["interfaces"]:
                interfaces.append(interface)
        return interfaces

    def compare_items(original_item, compared_item):
        for key in original_item:
            if key in TOPOLOGY_ID_KEYS:
                if original_item[key] in id_map:
                    assert id_map[original_item[key]] == compared_item[key]
                else:
                    id_map[original_item[key]] = compared_item[key]
            elif key == "configuration":
                # config gets stripped at some point
                assert original_item[key].strip() == compared_item[key].strip()
            elif key == "version":
                pass
            elif key == "interfaces":
                # ignore interfaces on node
                pass
            else:
                assert original_item[key] == compared_item[key]

    # Compare individual topology items
    original_nodes = original.pop("nodes", [])
    compared_nodes = compared.pop("nodes", [])
    original_links = original.pop("links", [])
    compared_links = compared.pop("links", [])
    original_interfaces = extract_interfaces_from_nodes(original_nodes)
    compared_interfaces = extract_interfaces_from_nodes(compared_nodes)

    # original and compared now only contains top namespace lab related keys
    for org, cmp in zip(original_nodes, compared_nodes):
        compare_items(org, cmp)
    for org, cmp in zip(original_links, compared_links):
        compare_items(org, cmp)
    for org, cmp in zip(original_interfaces, compared_interfaces):
        compare_items(org, cmp)

    # assert original["lab"]["compute_id"] == compared["lab"]["compute_id"]
    assert original["lab"]["description"] == compared["lab"]["description"]
    assert original["lab"]["notes"] == compared["lab"]["notes"]
    # assert original["lab"]["owner"] == compared["lab"]["owner"]
    assert original["lab"]["version"] == compared["lab"]["version"]
    # do not compare timestamp and lab_title
    #  title is changed on export/import
