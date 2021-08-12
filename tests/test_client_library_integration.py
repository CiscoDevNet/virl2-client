#
# Python bindings for the Cisco VIRL 2 Network Simulation Platform
#
# This file is part of VIRL 2
#
# Copyright 2020 Cisco Systems Inc.
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
import pytest
import requests
import logging

from virl2_client import ClientLibrary

pytestmark = [pytest.mark.integration]


def test_sync_lab(register_licensing, client_library: ClientLibrary):
    lab = client_library.create_lab("my test lab name")
    lab = client_library.join_existing_lab(lab.id)

    r1 = lab.create_node("r1", "server", 5, 100)
    r2 = lab.create_node("r2", "server", 102, 201)
    r3 = lab.create_node("r3", "server", 200, 400)
    # print(r1, r2, r3)

    r1.x = 400
    r1.label = "abc"

    r1_i1 = r1.create_interface()
    r1_i2 = r1.create_interface()

    r2_i1 = r2.create_interface()
    r2_i2 = r2.create_interface()

    r3_i1 = r3.create_interface()
    r3_i2 = r3.create_interface()

    #
    lab.create_link(r1_i1, r2_i1)
    lab.create_link(r2_i2, r3_i1)
    lab.create_link(r3_i2, r1_i2)

    r1.start()
    r2.start()
    r3.start()

    # lab.stop()
    r1.stop()
    r2.stop()
    r3.stop()

    # lab.remove_link(link_1)
    # lab.remove_link(link_2)
    # lab.remove_link(link_3)
    # lab.remove_node(r1)
    # lab.remove_node(r2)
    # lab.remove_node(r3)

    # TODO: wait for convergence here
    lab.stop()

    # lab.clear()
    # lab.sync_events()


def test_import(client_library: ClientLibrary):
    lab = client_library.import_sample_lab("server-triangle.yaml")
    s0 = lab.get_node_by_label("server-0")
    assert lab.get_node_by_label("server-1") is not None
    assert lab.get_node_by_label("server-2") is not None

    lab.start()

    s0.stop()
    s0.wipe()

    i1 = s0.create_interface()

    s3 = lab.create_node("s3", "server", 100, 200)
    i2 = s3.create_interface()

    lab.create_link(i1, i2)

    lab.start()
    lab.stop()


def test_create_client_lab(client_library: ClientLibrary):
    lab = client_library.create_lab()
    lab.auto_sync = False

    print("Created lab {}".format(lab.id))
    # using server nodes, not IOSv nodes as they are not available
    # without a reference platform ISO attached
    r1 = lab.create_node("r1", "server", 5, 100)
    r2 = lab.create_node("r2", "server", 102, 201)
    r3 = lab.create_node("r3", "server", 200, 400)
    print(r1, r2, r3)

    r1_i1 = r1.create_interface()
    r1_i2 = r1.create_interface()
    print(r1_i1, r1_i2)

    r2_i1 = r2.create_interface()
    r2_i2 = r2.create_interface()

    r3_i1 = r3.create_interface()
    r3_i2 = r3.create_interface()

    link_1 = lab.create_link(r1_i1, r2_i1)
    link_2 = lab.create_link(r2_i2, r3_i1)
    link_3 = lab.create_link(r3_i2, r1_i2)

    # r1.config = "test"
    # r2.x = 50
    # r2.y = 200
    #

    # r1.start()
    # r2.start()
    # r3.start()

    # r1.stop()
    # r2.stop()
    # r3.stop()

    r1.label = "r1_test"

    # lab.remove_node(r1)
    lab.remove_link(link_1)
    lab.remove_link(link_2)
    lab.remove_link(link_3)
    lab.remove_node(r1)
    lab.remove_node(r2)
    lab.remove_node(r3)

    lab.sync_states()

    for node in lab.nodes():
        print(node, node.state)
        for iface in node.interfaces():
            print(iface, iface.state)

    for link in lab.links():
        print(link, link.state)

    # lab.remove()

    # print("clear lab")
    # lab.clear()
    # print("remove lab")
    # events = lab.sync_events()
    # for event in lab.events:
    #     print(event)
    # lab.wait_until_lab_converged()
    lab.remove()


def test_connect(client_library: ClientLibrary):
    lab = client_library.create_lab("my lab name")
    lab = client_library.join_existing_lab(lab.id)

    lab.auto_sync = False

    s1 = lab.create_node("s1", "server", 50, 100)
    s2 = lab.create_node("s2", "server", 50, 200)
    print(s1, s2)

    # create a link between s1 and s2
    s1_i1 = s1.create_interface()
    s2_i1 = s2.create_interface()
    lab.create_link(s1_i1, s2_i1)

    # this must remove the link between s1 and s2
    lab.remove_node(s2)

    lab.sync_states()
    for node in lab.nodes():
        print(node, node.state)
        for iface in node.interfaces():
            print(iface, iface.state)

    for link in lab.links():
        print(link, link.state)

    # self.assertEqual(0, len(links))


def test_server_node_deletion(client_library: ClientLibrary):
    lab = client_library.create_lab("lab_1")

    lab.auto_sync = False

    s1 = lab.create_node("s1", "server", 5, 100)
    s2 = lab.create_node("s2", "server", 102, 201)

    s1_iface = lab.create_interface(s1, 2)
    s2_iface = lab.create_interface(s2, 2)
    lab.create_link(s1_iface, s2_iface)

    lab.start()

    s3 = lab.create_node("s3", "server", 200, 400)
    s3_iface = lab.create_interface(s3)

    s2.stop()

    lab.create_link(s2.interfaces()[0], s3_iface)

    lab.start()

    # can't remove node while running
    with pytest.raises(requests.exceptions.HTTPError) as exc:
        lab.remove_node(s3)
    assert exc.value.response.status_code == 400

    # need to stop and wipe to be able to remove node.
    s3.stop()
    s3.wipe()
    lab.remove_node(s3)


def test_user_management(client_library: ClientLibrary):
    test_user = "test_user"
    test_password = "test_password"

    res = client_library.user_management.create_user(
        username=test_user, pwd=test_password
    )
    assert isinstance(res, dict)
    assert res["username"] == test_user
    assert res["fullname"] == ""
    assert res["description"] == ""
    test_user_id = res["id"]

    # changing only fullname
    res = client_library.user_management.update_user(
        user_id=test_user_id, fullname=test_user
    )
    assert res["fullname"] == test_user
    assert res["description"] == ""

    # changing only description; already changed fullname must be kept
    res = client_library.user_management.update_user(
        user_id=test_user_id, description=test_user
    )
    assert res["fullname"] == test_user
    assert res["description"] == test_user

    # changing both fullname and description
    res = client_library.user_management.update_user(
        user_id=test_user_id,
        description=test_user + test_user,
        fullname=test_user + test_user,
    )
    assert res["fullname"] == test_user + test_user
    assert res["description"] == test_user + test_user

    user = client_library.user_management.get_user(test_user_id)
    assert isinstance(user, dict)
    assert user["username"] == test_user
    assert "admin" in user and "groups" in user
    assert res["fullname"] == test_user + test_user
    assert res["description"] == test_user + test_user

    users = client_library.user_management.users()
    assert isinstance(users, list)
    assert test_user in [user["username"] for user in users]

    res = client_library.user_management.update_user(
        user_id=test_user_id,
        password_dict=dict(
            old_password=test_password, new_password="new_test_password"
        ),
    )
    assert isinstance(res, dict)
    assert test_user_id == res["id"]
    res = client_library.user_management.delete_user(user_id=test_user_id)
    assert res is None

    users = client_library.user_management.users()
    assert isinstance(users, list)
    assert test_user not in [user["username"] for user in users]

    with pytest.raises(requests.exceptions.HTTPError):
        client_library.user_management.get_user(test_user_id)

    # non existent role should return 400 - Bad request
    with pytest.raises(requests.exceptions.HTTPError) as err:
        client_library.user_management.create_user(
            username="user569", pwd=test_password, admin=["non-existent-role"]
        )
    assert err.value.response.status_code == 400
    assert "not of type 'boolean'" in err.value.response.text

    # delete non-existent user
    with pytest.raises(requests.exceptions.HTTPError) as err:
        client_library.user_management.delete_user(
            user_id="8ee2051d-3adb-4e76-9e51-ae63238f15bc"
        )
    assert err.value.response.status_code == 404
    assert "User does not exist" in err.value.response.text


def test_password_word_list(client_library: ClientLibrary):
    test_user = "another-test-user"
    restricted_password = "password"
    # try to create user with restricted password - must fail
    with pytest.raises(requests.exceptions.HTTPError) as err:
        client_library.user_management.create_user(
            username=test_user, pwd=restricted_password
        )
    assert err.value.response.status_code == 403
    assert "password in common word list" in err.value.response.text

    good_pwd = restricted_password + "dfsjdf"
    res = client_library.user_management.create_user(username=test_user, pwd=good_pwd)
    assert isinstance(res, dict)
    assert res["username"] == test_user
    test_user_id = res["id"]

    # try to change password to restricted password - must fail
    with pytest.raises(requests.exceptions.HTTPError) as err:
        client_library.user_management.update_user(
            user_id=test_user_id,
            password_dict=dict(old_password=good_pwd, new_password=restricted_password),
        )
    assert err.value.response.status_code == 403
    assert "password in common word list" in err.value.response.text

    res = client_library.user_management.delete_user(user_id=test_user_id)
    assert res is None

    with pytest.raises(requests.exceptions.HTTPError):
        client_library.user_management.get_user(test_user_id)


def test_webtoken_config(client_library_session: ClientLibrary):
    orig = client_library_session.system_management.get_web_session_timeout()

    client_library_session.system_management.set_web_session_timeout(3600)
    res = client_library_session.system_management.get_web_session_timeout()
    assert res == 3600
    client_library_session.system_management.set_web_session_timeout(orig)
    res = client_library_session.system_management.get_web_session_timeout()
    assert res == orig


def test_mac_addr_block_config(client_library_session: ClientLibrary):
    orig = client_library_session.system_management.get_mac_address_block()

    client_library_session.system_management.set_mac_address_block(7)
    res = client_library_session.system_management.get_mac_address_block()
    assert res == 7

    client_library_session.system_management.set_mac_address_block(orig)
    res = client_library_session.system_management.get_mac_address_block()
    assert res == orig

    # client validation
    with pytest.raises(ValueError):
        client_library_session.system_management.set_mac_address_block(8)

    with pytest.raises(ValueError):
        client_library_session.system_management.set_mac_address_block(-1)

    # server validation
    with pytest.raises(requests.exceptions.HTTPError) as err:
        client_library_session.system_management._set_mac_address_block(8)
    assert err.value.response.status_code == 400

    with pytest.raises(requests.exceptions.HTTPError) as err:
        client_library_session.system_management._set_mac_address_block(-1)
    assert err.value.response.status_code == 400


def test_import_yaml(client_library_session: ClientLibrary):
    lab = client_library_session.import_sample_lab("server-triangle.yaml")
    assert lab is not None
    lab.remove()


def test_import_virl(client_library_session: ClientLibrary):
    lab = client_library_session.import_sample_lab("dual-server.virl")
    assert lab is not None
    lab.remove()


def test_lab_state(client_library: ClientLibrary):
    lab = client_library.create_lab("lab_1")

    s1 = lab.create_node("s1", "server", 5, 100)
    s2 = lab.create_node("s2", "server", 102, 201)

    s1_iface = lab.create_interface(s1, 2)
    s2_iface = lab.create_interface(s2, 2)
    lab.create_link(s1_iface, s2_iface)

    state = lab.state()
    assert state == "DEFINED_ON_CORE"

    lab.start()
    state = lab.state()
    assert state == "STARTED"

    assert lab.is_active()

    lab.stop()
    state = lab.state()
    assert state == "STOPPED"

    lab.wipe()
    state = lab.state()
    assert state == "DEFINED_ON_CORE"


def test_lab_details(client_library: ClientLibrary):
    lab = client_library.create_lab("lab_1")

    s1 = lab.create_node("s1", "server", 5, 100)
    s2 = lab.create_node("s2", "server", 102, 201)

    s1_iface = lab.create_interface(s1, 2)
    s2_iface = lab.create_interface(s2, 2)
    lab.create_link(s1_iface, s2_iface)

    expected_keys = (
        "state",
        "created",
        "lab_title",
        "lab_description",
        "node_count",
        "link_count",
        "id",
    )

    details = lab.details()
    assert all(k in details.keys() for k in expected_keys)
    assert details["node_count"] == 2
    assert details["link_count"] == 1
    assert details["state"] == "DEFINED_ON_CORE"


def test_labels_and_tags(client_library: ClientLibrary):
    lab = client_library.import_sample_lab("server-triangle.yaml")

    lab.sync(topology_only=True)

    node_1 = lab.get_node_by_label("server-0")
    assert node_1.label == "server-0"
    assert len(node_1.tags()) == 2

    node_2 = lab.get_node_by_label("server-1")
    assert node_2.label == "server-1"
    assert len(node_2.tags()) == 2

    node_3 = lab.get_node_by_label("server-2")
    assert node_3.label == "server-2"
    assert len(node_3.tags()) == 5


def test_remove_non_existent_node_definition(client_library_session: ClientLibrary):
    def_id = "non_existent_node_definition"
    with pytest.raises(requests.exceptions.HTTPError) as err:
        client_library_session.definitions.remove_node_definition(definition_id=def_id)
    assert err.value.response.status_code == 404


def test_remove_non_existent_dropfolder_image(client_library_session: ClientLibrary):
    filename = "non_existent_file"
    with pytest.raises(requests.exceptions.HTTPError) as err:
        client_library_session.definitions.remove_dropfolder_image(filename=filename)
    assert err.value.response.status_code == 404


def test_node_with_unavailable_vnc(client_library_session: ClientLibrary):
    lab = client_library_session.create_lab("lab_111")
    node = lab.create_node("s1", "unmanaged_switch", 5, 100)
    lab.start()
    assert lab.state() == "STARTED"
    with pytest.raises(requests.exceptions.HTTPError) as err:
        node.vnc_key()
    assert err.value.response.status_code == 404
    lab.stop()
    lab.wipe()
    lab.remove()


@pytest.mark.nomock
def test_node_console_logs(client_library_session: ClientLibrary):
    lab = client_library_session.create_lab("lab_space")
    ext_conn = lab.create_node("ec", "external_connector", 100, 50, wait=False)
    server = lab.create_node("s1", "server", 100, 100)
    iosv = lab.create_node("n", "iosv", 50, 0)
    lab.start()
    assert lab.state() == "STARTED"
    # server has one serial console on id 0
    logs = server.console_logs(console_id=0)
    assert type(logs) == str

    # external connector - no serial console
    with pytest.raises(requests.exceptions.HTTPError) as err:
        ext_conn.console_logs(console_id=0)
    assert err.value.response.status_code == 400
    assert "Serial port does not exist on node" in err.value.response.text

    # test limited number of lines
    num_lines = 5
    logs = server.console_logs(console_id=0, lines=num_lines)
    assert type(logs) == str
    assert len(logs.split("\n")) == num_lines

    # assert 400 for non existent console id for server >0
    with pytest.raises(requests.exceptions.HTTPError) as err:
        server.console_logs(console_id=55)
    assert err.value.response.status_code == 400
    assert "Serial port does not exist on node" in err.value.response.text

    # iosv has 2 serial consoles
    logs = iosv.console_logs(console_id=0)
    assert type(logs) == str
    logs = iosv.console_logs(console_id=1)
    assert type(logs) == str
    with pytest.raises(requests.exceptions.HTTPError) as err:
        iosv.console_logs(console_id=2)
    assert err.value.response.status_code == 400
    assert "Serial port does not exist on node" in err.value.response.text

    lab.stop()
    lab.wipe()
    lab.remove()


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


def test_topology_owner(client_library_session: ClientLibrary):
    cml2_uid = client_library_session.user_management.user_id("cml2")
    lab = client_library_session.create_lab("owned_by_cml2")
    lab.sync(topology_only=True)
    assert lab.owner == cml2_uid
    lab.remove()


@pytest.mark.nomock
def test_server_tokens_off(controller_url):
    resp = requests.get(controller_url, verify=False)
    headers = resp.headers
    # has to equal to 'nginx' without version
    assert headers["Server"] == "nginx"


def test_user_role_change(controller_url, client_library_session: ClientLibrary):
    cl_admin = client_library_session
    cl_admin_uid = client_library_session.user_management.user_id(cl_admin.username)
    # create non admin users
    cl_user1, cl_user2 = "cl_user1", "cl_user2"
    password = "super-secret"
    res = cl_admin.user_management.create_user(username=cl_user1, pwd=password)
    cl_user1_uid = res["id"]
    res = cl_admin.user_management.create_user(username=cl_user2, pwd=password)
    cl_user2_uid = res["id"]

    cl_user1 = ClientLibrary(
        controller_url,
        username=cl_user1,
        password=password,
        ssl_verify=False,
        allow_http=True,
    )
    cl_user2 = ClientLibrary(
        controller_url,
        username=cl_user2,
        password=password,
        ssl_verify=False,
        allow_http=True,
    )

    cl_user1.create_lab("lab1-cl_user1")
    cl_user1.create_lab("lab2-cl_user1")

    assert cl_user2.all_labs(show_all=True) == []
    # promote cl_user2 to admin
    cl_admin.user_management.update_user(user_id=cl_user2_uid, admin=True)
    # check if cl_user2 can see all the labs as admin
    all_labs = cl_user2.all_labs(show_all=True)
    assert len(all_labs) == 2
    assert all_labs[0].owner == cl_user1_uid

    # check if cl_user2 can create user and delete users
    res = cl_user2.user_management.create_user(username="TestUser", pwd=password)
    assert cl_user2.user_management.get_user(user_id=res["id"])

    cl_user2.user_management.delete_user(user_id=res["id"])
    with pytest.raises(requests.exceptions.HTTPError) as err:
        cl_user2.user_management.get_user(user_id=res["id"])
    assert err.value.response.status_code == 404

    # check cl_user2 can see licensing
    assert cl_user2.licensing.status()

    for lab in all_labs:
        cl_user2.remove_lab(lab.id)
    assert cl_user2.all_labs(show_all=True) == []

    # promote cl_user1 to admin
    cl_admin.user_management.update_user(user_id=cl_user1_uid, admin=True)

    # check if cl_user1 can remove admin cl_user2
    cl_user1.user_management.delete_user(user_id=cl_user2_uid)
    with pytest.raises(requests.exceptions.HTTPError) as err:
        cl_user1.user_management.get_user(user_id=cl_user2_uid)
    assert err.value.response.status_code == 404

    # remove admin rights from cl_user1
    cl_admin.user_management.update_user(user_id=cl_user1_uid, admin=False)
    lab = cl_admin.create_lab("origin-lab")
    assert cl_user1.all_labs(show_all=True) == []

    with pytest.raises(requests.exceptions.HTTPError) as err:
        cl_user1.user_management.create_user(username="TestUser", pwd=password)
    assert err.value.response.status_code == 403

    with pytest.raises(requests.exceptions.HTTPError) as err:
        cl_user1.licensing.status()
    assert err.value.response.status_code == 403

    cl_admin.user_management.delete_user(user_id=cl_user1_uid)

    # check that user cannot update its own user role
    with pytest.raises(requests.exceptions.HTTPError) as err:
        cl_admin.user_management.update_user(user_id=cl_admin_uid, admin=False)
    assert err.value.response.status_code == 400

    # cleanup
    cl_admin.remove_lab(lab.id)


def test_token_invalidation(
    caplog, controller_url, client_library_session: ClientLibrary
):
    cl_admin = client_library_session

    res = cl_admin.user_management.create_user(username="test_user", pwd="moremore")
    test_user_uid = res["id"]

    cl_test_user = ClientLibrary(
        controller_url,
        username="test_user",
        password="moremore",
        ssl_verify=False,
        allow_http=True,
    )
    # make sure user token works
    res = cl_test_user.user_management.users()
    assert isinstance(res, list)
    for obj in res:
        assert "username" in obj and "id" in obj

    # CHANGE PASSWORD
    new_pwd = "moremoreevenmore"
    res = cl_test_user.user_management.update_user(
        user_id=test_user_uid,
        password_dict=dict(old_password="moremore", new_password=new_pwd),
    )
    assert isinstance(res, dict)
    cl_test_user.password = new_pwd
    with caplog.at_level(logging.WARNING):
        res = cl_test_user.user_management.users()
        assert isinstance(res, list)
    assert "re-auth called on 401 unauthorized" in caplog.text

    # CHANGE ROLE
    res = cl_admin.user_management.update_user(user_id=test_user_uid, admin=True)
    assert isinstance(res, dict)
    assert res["admin"] is True
    with caplog.at_level(logging.WARNING):
        res = cl_test_user.user_management.users()
        assert isinstance(res, list)
    assert "re-auth called on 401 unauthorized" in caplog.text

    # LOGOUT
    res = cl_test_user.logout()
    assert res is True
    with caplog.at_level(logging.WARNING):
        res = cl_test_user.user_management.users()
        assert isinstance(res, list)
    assert "re-auth called on 401 unauthorized" in caplog.text

    # CLEAR SESSION
    # create another client library object (this generates new token)
    cl_test_user1 = ClientLibrary(
        controller_url,
        username="test_user",
        password=new_pwd,
        ssl_verify=False,
        allow_http=True,
    )
    # clear whole test_user session (remove all tokens)
    res = cl_test_user.logout(clear_all_sessions=True)
    assert res is True
    # cl_test_user
    with caplog.at_level(logging.WARNING):
        res = cl_test_user.user_management.users()
        assert isinstance(res, list)
    assert "re-auth called on 401 unauthorized" in caplog.text
    # cl_test_user1
    with caplog.at_level(logging.WARNING):
        res = cl_test_user1.user_management.users()
        assert isinstance(res, list)
    assert "re-auth called on 401 unauthorized" in caplog.text

    # DELETE USER
    res = cl_admin.user_management.delete_user(user_id=test_user_uid)
    # test that user token works no more
    with pytest.raises(requests.exceptions.HTTPError) as err:
        with caplog.at_level(logging.WARNING):
            cl_test_user.user_management.users()
            assert isinstance(res, list)
        assert "re-auth called on 401 unauthorized" in caplog.text
    # normally you would expect 401 here, it was returned, however
    # response hook that catches 401 TokenAuth.handle_401_unauthorized
    # tried to authenticate and user no longer exists - so 403 Forbidden
    assert err.value.response.status_code == 403
