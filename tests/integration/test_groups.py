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

"""Tests for Groups feature."""

import uuid
import pytest
import requests

from virl2_client import ClientConfig, ClientLibrary

pytestmark = [pytest.mark.integration]

# TODO: split into more granular test cases and document


def test_group_api_basic(
    cleanup_test_groups, register_licensing, client_library_session: ClientLibrary
):
    cl = client_library_session
    g0 = cl.group_management.create_group(name="g0")
    assert isinstance(g0, dict)
    assert "id" in g0 and uuid.UUID(g0["id"], version=4)
    assert g0["description"] == ""
    assert g0["members"] == [] and g0["labs"] == []

    # try to create group with same name
    with pytest.raises(requests.exceptions.HTTPError) as err:
        cl.group_management.create_group(name="g0")
    assert err.value.response.status_code == 422
    assert "Group already exists" in err.value.response.text

    # same object must be returned in get as upon create
    g0_a = cl.group_management.get_group(group_id=g0["id"])
    assert g0 == g0_a

    # get non-existent group
    with pytest.raises(requests.exceptions.HTTPError) as err:
        cl.group_management.get_group(group_id="8ee2051d-3adb-4e76-9e51-ae63238f15bc")
    assert err.value.response.status_code == 404
    assert "Group does not exist" in err.value.response.text

    # groups labs is empty list
    group_labs = cl.group_management.group_labs(group_id=g0["id"])
    assert group_labs == []

    with pytest.raises(requests.exceptions.HTTPError) as err:
        cl.group_management.group_labs(group_id="ef490485-f0a4-4455-afb6-b71c2b97bb6b")
    assert err.value.response.status_code == 404
    assert "Group does not exist" in err.value.response.text

    # groups members is empty list
    group_members = cl.group_management.group_members(group_id=g0["id"])
    assert group_members == []

    with pytest.raises(requests.exceptions.HTTPError) as err:
        cl.group_management.group_members(
            group_id="8a0aff6f-ed54-40b0-8246-081b0cb104db"
        )
    assert err.value.response.status_code == 404
    assert "Group does not exist" in err.value.response.text

    # update group
    new_description = "new_description"
    new_name = "g1"
    updated_g0 = cl.group_management.update_group(
        group_id=g0["id"], description=new_description, name=new_name
    )
    assert updated_g0["id"] == g0["id"]
    assert updated_g0["description"] == new_description
    assert updated_g0["name"] == new_name
    updated_g0_a = cl.group_management.get_group(group_id=updated_g0["id"])
    assert updated_g0 == updated_g0_a

    # make sure name cannot be set to empty string
    with pytest.raises(requests.exceptions.HTTPError) as err:
        cl.group_management.update_group(
            group_id=updated_g0["id"], description=new_description, name=""
        )
    assert err.value.response.status_code == 400

    # update non-existent group
    with pytest.raises(requests.exceptions.HTTPError) as err:
        cl.group_management.update_group(
            group_id="d393bb36-08a2-4f6b-a1b4-9acddc4ea364", description=new_description
        )
    assert err.value.response.status_code == 404
    assert "Group does not exist" in err.value.response.text

    # delete non existent group
    with pytest.raises(requests.exceptions.HTTPError) as err:
        cl.group_management.delete_group(
            group_id="ca789cac-a0e1-4233-bd92-336685c0eba2"
        )
    assert err.value.response.status_code == 404
    assert "Group does not exist" in err.value.response.text

    assert cl.group_management.delete_group(group_id=updated_g0["id"]) is None
    with pytest.raises(requests.exceptions.HTTPError) as err:
        cl.group_management.get_group(group_id=updated_g0["id"])
    assert err.value.response.status_code == 404
    assert "Group does not exist" in err.value.response.text


def test_group_api_invalid_request_data(
    cleanup_test_labs,
    cleanup_test_users,
    cleanup_test_groups,
    client_library_session: ClientLibrary,
):
    cl = client_library_session
    with pytest.raises(requests.exceptions.HTTPError) as err:
        cl.group_management.create_group(name="")
    assert err.value.response.status_code == 400
    with pytest.raises(requests.exceptions.HTTPError) as err:
        cl.group_management.create_group(name="xxx", description=[{}])
    assert err.value.response.status_code == 400
    with pytest.raises(requests.exceptions.HTTPError) as err:
        cl.group_management.create_group(name=458)
    assert err.value.response.status_code == 400
    with pytest.raises(requests.exceptions.HTTPError) as err:
        cl.group_management.create_group(name="xxx", members="incorrect type")
    assert err.value.response.status_code == 400
    with pytest.raises(requests.exceptions.HTTPError) as err:
        cl.group_management.create_group(name="xxx", labs=[{}])
    assert err.value.response.status_code == 400
    with pytest.raises(requests.exceptions.HTTPError) as err:
        cl.group_management.create_group(name="xxx", labs=["dsdsds"])
    assert err.value.response.status_code == 400
    with pytest.raises(requests.exceptions.HTTPError) as err:
        cl.group_management.create_group(name="xxx", labs=[{"id": "x"}])
    assert err.value.response.status_code == 400
    with pytest.raises(requests.exceptions.HTTPError) as err:
        cl.group_management.create_group(name="xxx", labs=[{"permission": "read_only"}])
    assert err.value.response.status_code == 400
    with pytest.raises(requests.exceptions.HTTPError) as err:
        cl.group_management.create_group(
            name="xxx", labs=[{"id": "dsd", "permission": "rw"}]
        )
    assert err.value.response.status_code == 400
    with pytest.raises(requests.exceptions.HTTPError) as err:
        cl.user_management.create_user("xxx", "hardpass", groups="pedro")
    assert err.value.response.status_code == 400
    lab = cl.create_lab()
    with pytest.raises(requests.exceptions.HTTPError) as err:
        lab.update_lab_groups(["x"])
    assert err.value.response.status_code == 400
    with pytest.raises(requests.exceptions.HTTPError) as err:
        lab.update_lab_groups([{"not_id": "x", "permission": "read_write"}])
    assert err.value.response.status_code == 400
    with pytest.raises(requests.exceptions.HTTPError) as err:
        lab.update_lab_groups([{"id": "x", "perm": "read_write"}])
    assert err.value.response.status_code == 400
    with pytest.raises(requests.exceptions.HTTPError) as err:
        lab.update_lab_groups([{"id": "x", "perm": "not_one_of_read_write_only"}])
    assert err.value.response.status_code == 400
    lab.remove()
    gg0 = cl.group_management.create_group("gg0")
    gg0_uid = gg0["id"]
    with pytest.raises(requests.exceptions.HTTPError) as err:
        cl.group_management.update_group(gg0_uid, labs=["labs"])
    assert err.value.response.status_code == 400
    with pytest.raises(requests.exceptions.HTTPError) as err:
        cl.group_management.update_group(gg0_uid, labs=[{"id": "dsdsd"}])
    assert err.value.response.status_code == 400
    with pytest.raises(requests.exceptions.HTTPError) as err:
        cl.group_management.update_group(gg0_uid, labs=[{"permission": "read_only"}])
    assert err.value.response.status_code == 400
    with pytest.raises(requests.exceptions.HTTPError) as err:
        cl.group_management.update_group(
            "gg0", labs=[{"id": "dsdsd", "permission": "xxx"}]
        )
    assert err.value.response.status_code == 400
    with pytest.raises(requests.exceptions.HTTPError) as err:
        cl.group_management.update_group(gg0_uid, name="")
    assert err.value.response.status_code == 400
    cl.group_management.delete_group(gg0_uid)


def test_group_api_user_associations(
    cleanup_test_users, cleanup_test_groups, client_library_session: ClientLibrary
):
    cl = client_library_session
    # create non admin users
    satoshi = cl.user_management.create_user(username="satoshi", pwd="super-secret-pwd")
    satoshi_uid = satoshi["id"]
    assert uuid.UUID(satoshi_uid, version=4)
    nick_szabo = cl.user_management.create_user(
        username="nick_szabo", pwd="super-secret-pwd"
    )
    nick_szabo_uid = nick_szabo["id"]
    assert uuid.UUID(nick_szabo_uid, version=4)
    # create teachers group and immediately add teacher user to it
    teachers_group = cl.group_management.create_group(
        name="teachers", description="teachers group", members=[satoshi_uid]
    )
    assert "id" in teachers_group and uuid.UUID(teachers_group["id"], version=4)
    assert teachers_group["members"] == [satoshi_uid]
    assert (
        cl.group_management.group_members(group_id=teachers_group["id"])
        == teachers_group["members"]
    )
    assert cl.user_management.user_groups(user_id=satoshi_uid) == [teachers_group["id"]]
    assert (
        cl.group_management.get_group(group_id=teachers_group["id"]) == teachers_group
    )

    # create students group
    students_group = cl.group_management.create_group(
        name="students",
        description="students group",
    )
    # add user to group subsequently
    students_group = cl.group_management.update_group(
        group_id=students_group["id"], members=[nick_szabo_uid]
    )
    assert "id" in students_group and uuid.UUID(students_group["id"], version=4)
    assert students_group["members"] == [nick_szabo_uid]
    assert (
        cl.group_management.group_members(group_id=students_group["id"])
        == students_group["members"]
    )
    assert cl.user_management.user_groups(user_id=nick_szabo_uid) == [
        students_group["id"]
    ]
    assert (
        cl.group_management.get_group(group_id=students_group["id"]) == students_group
    )

    # add group to user during user creation
    nocoiners = cl.group_management.create_group(
        name="nocoiners", description="group for nocoiners"
    )
    mario_draghi = cl.user_management.create_user(
        username="mario_draghi", pwd="super-secret-pwd", groups=[nocoiners["id"]]
    )
    mario_draghi_uid = mario_draghi["id"]
    assert cl.user_management.user_groups(user_id=mario_draghi_uid) == [nocoiners["id"]]
    assert cl.group_management.group_members(group_id=nocoiners["id"]) == [
        mario_draghi_uid
    ]

    # try add non-existent user to group
    with pytest.raises(requests.exceptions.HTTPError) as err:
        cl.group_management.update_group(
            group_id=teachers_group["id"],
            members=["b78a563b-d4a9-45fb-9aed-d8b5de4c3a2b"],
        )
    assert err.value.response.status_code == 404
    assert "User does not exist" in err.value.response.text

    # try add non-existent group to user
    with pytest.raises(requests.exceptions.HTTPError) as err:
        cl.user_management.create_user(
            username="xxx",
            pwd="super-secret-pwd",
            groups=["fcd86c8b-a04f-4d1b-9a2d-81ce4dfae1b2"],
        )
    assert err.value.response.status_code == 404
    assert "Group does not exist" in err.value.response.text
    # above should not create user
    assert "xxx" not in [
        user_obj["username"] for user_obj in cl.user_management.users()
    ]

    # TODO: let pytest fixture clean this up, create separate test case for deletes
    # CLEAN UP
    # remove nocoiner group and draghi user
    assert cl.user_management.delete_user(user_id=mario_draghi_uid) is None
    assert cl.group_management.delete_group(group_id=nocoiners["id"]) is None
    # remove teachers group - check if not in user_groups
    assert cl.group_management.delete_group(group_id=teachers_group["id"]) is None
    assert cl.user_management.user_groups(user_id=satoshi_uid) == []
    assert cl.user_management.delete_user(user_id=satoshi_uid) is None
    # remove user first - check if not part of the group
    assert cl.user_management.delete_user(user_id=nick_szabo_uid) is None
    assert cl.group_management.group_members(group_id=students_group["id"]) == []
    assert cl.group_management.delete_group(group_id=students_group["id"]) is None
    # check if clean
    for group_id in (nocoiners["id"], teachers_group["id"], students_group["id"]):
        with pytest.raises(requests.exceptions.HTTPError) as err:
            cl.group_management.get_group(group_id=group_id)
        assert err.value.response.status_code == 404
    for user_id in (mario_draghi_uid, satoshi_uid, nick_szabo_uid):
        with pytest.raises(requests.exceptions.HTTPError) as err:
            cl.user_management.get_user(user_id=user_id)
        assert err.value.response.status_code == 404


def test_group_api_lab_associations(
    cleanup_test_labs, cleanup_test_groups, client_library_session: ClientLibrary
):
    cl = client_library_session
    # create lab
    lab0 = cl.create_lab(title="lab0")
    # create group and add lab into it with rw
    lab0_rw = [{"id": lab0.id, "permission": "read_write"}]
    teachers_group = cl.group_management.create_group(
        name="teachers", description="teachers group", labs=lab0_rw
    )
    assert teachers_group["labs"] == lab0_rw
    teachers_group_labs = cl.group_management.group_labs(group_id=teachers_group["id"])
    assert teachers_group_labs == [lab0.id]
    assert lab0.groups == [{"id": teachers_group["id"], "permission": "read_write"}]
    # remove association between group and lab using lab endpoint
    assert lab0.update_lab_groups(group_list=[]) == []
    assert lab0.groups == []
    assert cl.group_management.get_group(group_id=teachers_group["id"])["labs"] == []
    # reinstantiate association via group update - change to read_only
    lab0_ro = [{"id": lab0.id, "permission": "read_only"}]
    teachers_group = cl.group_management.update_group(
        group_id=teachers_group["id"], labs=lab0_ro
    )
    assert teachers_group["labs"] == lab0_ro
    assert lab0.groups == [{"id": teachers_group["id"], "permission": "read_only"}]
    teachers_group_labs = cl.group_management.group_labs(group_id=teachers_group["id"])
    assert teachers_group_labs == [lab0.id]
    # remove association via group update endpoint
    teachers_group = cl.group_management.update_group(
        group_id=teachers_group["id"], labs=[]
    )
    assert lab0.groups == []
    assert cl.group_management.get_group(group_id=teachers_group["id"])["labs"] == []
    teachers_group_labs = cl.group_management.group_labs(group_id=teachers_group["id"])
    assert teachers_group_labs == []

    # create on emore lab and group and create an association between them
    # so that we can test both 1. lab removal 2. group removal
    lab1 = cl.create_lab(title="lab1")
    lab1_rw = [{"id": lab1.id, "permission": "read_write"}]
    students_group = cl.group_management.create_group(
        name="students", description="students group", labs=lab1_rw
    )
    assert lab1.groups == [{"id": students_group["id"], "permission": "read_write"}]
    students_group_labs = cl.group_management.group_labs(group_id=students_group["id"])

    assert students_group_labs == [lab1.id]

    # add non-existent lab to group (create)
    non_existent_id = str(uuid.uuid4())
    with pytest.raises(requests.exceptions.HTTPError) as err:
        cl.group_management.create_group(
            name="xxx", labs=[{"id": non_existent_id, "permission": "read_only"}]
        )
    assert err.value.response.status_code == 404
    assert "Lab not found" in err.value.response.text
    assert "xxx" not in [group["name"] for group in cl.group_management.groups()]

    # add non-existent lab to group (update)
    with pytest.raises(requests.exceptions.HTTPError) as err:
        cl.group_management.update_group(
            group_id=teachers_group["id"],
            labs=[{"id": non_existent_id, "permission": "read_only"}],
        )
    assert err.value.response.status_code == 404
    assert "Lab not found" in err.value.response.text
    assert "non-existent" not in cl.group_management.group_labs(
        group_id=teachers_group["id"]
    )

    # add non-existent group to lab
    with pytest.raises(requests.exceptions.HTTPError) as err:
        lab0.update_lab_groups(
            group_list=[{"id": non_existent_id, "permission": "read_only"}]
        )
    assert err.value.response.status_code == 404
    assert "Group does not exist" in err.value.response.text
    assert "non-existent" not in [obj["id"] for obj in lab0.groups]

    # CLEAN UP
    # remove lab first
    lab1.remove()
    assert cl.find_labs_by_title(title="lab1") == []
    # assert association is removed also
    students_group_labs = cl.group_management.group_labs(group_id=students_group["id"])
    assert students_group_labs == []
    assert cl.group_management.get_group(group_id=students_group["id"])["labs"] == []
    assert cl.group_management.delete_group(group_id=students_group["id"]) is None
    # remove group first
    assert cl.group_management.delete_group(group_id=teachers_group["id"]) is None
    with pytest.raises(requests.exceptions.HTTPError) as err:
        cl.group_management.group_labs(group_id=teachers_group["id"])
    assert err.value.response.status_code == 404
    assert "Group does not exist" in err.value.response.text
    assert lab0.groups == []
    lab0.remove()


def test_group_api_permissions(
    cleanup_test_labs,
    cleanup_test_users,
    cleanup_test_groups,
    client_config: ClientConfig,
    client_library_session: ClientLibrary,
):
    cl_admin = client_library_session
    # create non-admin user
    username = "satoshi"
    satoshi_pwd = "super-secret-pwd"
    satoshi = cl_admin.user_management.create_user(username=username, pwd=satoshi_pwd)
    halfinn = cl_admin.user_management.create_user(
        username="halfinney", pwd=satoshi_pwd
    )
    satoshi_uid = satoshi["id"]
    cml2_uid = client_library_session.user_management.user_id(
        username=client_config.username
    )
    halfinn_uid = halfinn["id"]
    # create lab
    lab0 = cl_admin.create_lab(title="lab0")
    lab1 = cl_admin.create_lab(title="lab1")
    # create students group
    lab0_ro = [{"id": lab0.id, "permission": "read_only"}]
    lab0_1_rw = [
        {"id": lab0.id, "permission": "read_write"},
        {"id": lab1.id, "permission": "read_write"},
    ]
    students_group = cl_admin.group_management.create_group(
        name="students",
        description="students group",
        members=[satoshi_uid],
        labs=lab0_ro,
    )
    teachers_group = cl_admin.group_management.create_group(
        name="teachers", description="teachers group", members=[], labs=lab0_1_rw
    )
    all_groups = cl_admin.group_management.groups()
    all_groups_names = [group["id"] for group in all_groups]
    assert students_group["id"] in all_groups_names
    assert teachers_group["id"] in all_groups_names

    # log in as non-admin satoshi user
    cl_satoshi = ClientLibrary(
        client_config.url,
        username=username,
        password=satoshi_pwd,
        ssl_verify=client_config.ssl_verify,
        allow_http=client_config.allow_http,
    )
    # satoshi must only see groups that he is part of
    satoshi_groups = cl_satoshi.group_management.groups()
    assert len(satoshi_groups) == 1
    assert satoshi_groups[0]["name"] == "students"
    assert cl_satoshi.user_management.user_groups(user_id=satoshi_uid) == [
        students_group["id"]
    ]

    # cannot check other user info
    with pytest.raises(requests.exceptions.HTTPError) as err:
        cl_satoshi.user_management.user_groups(user_id=cml2_uid)
    assert err.value.response.status_code == 403
    assert "User does not have required access" in err.value.response.text

    # user cannot see groups he is not part of
    with pytest.raises(requests.exceptions.HTTPError) as err:
        cl_satoshi.group_management.get_group(group_id=teachers_group["id"])
    assert err.value.response.status_code == 403
    assert "User does not have required access" in err.value.response.text
    # can see those where he is member
    students_group = cl_satoshi.group_management.get_group(
        group_id=students_group["id"]
    )
    assert students_group["members"] == [satoshi_uid]
    # only admin can create, delete and modify group
    # create
    with pytest.raises(requests.exceptions.HTTPError) as err:
        cl_satoshi.group_management.create_group(name="xxx")
    assert err.value.response.status_code == 403
    assert "User does not have required access" in err.value.response.text
    # update
    with pytest.raises(requests.exceptions.HTTPError) as err:
        cl_satoshi.group_management.update_group(
            group_id=teachers_group["id"], description="new"
        )
    assert err.value.response.status_code == 403
    assert "User does not have required access" in err.value.response.text
    # delete
    with pytest.raises(requests.exceptions.HTTPError) as err:
        cl_satoshi.group_management.delete_group(group_id=teachers_group["id"])
    assert err.value.response.status_code == 403
    assert "User does not have required access" in err.value.response.text
    # user cannot see members of group that he is not part of
    with pytest.raises(requests.exceptions.HTTPError) as err:
        cl_satoshi.group_management.group_members(group_id=teachers_group["id"])
    assert err.value.response.status_code == 403
    assert "User does not have required access" in err.value.response.text
    # can see those where he is member
    students_group_members = cl_satoshi.group_management.group_members(
        group_id=students_group["id"]
    )
    assert students_group_members == [satoshi_uid]
    # user cannot see labs of group that he is not part of
    with pytest.raises(requests.exceptions.HTTPError) as err:
        cl_satoshi.group_management.group_labs(group_id=teachers_group["id"])
    assert err.value.response.status_code == 403
    assert "User does not have required access" in err.value.response.text
    # can see those where he is member
    students_group_labs = cl_satoshi.group_management.group_labs(
        group_id=students_group["id"]
    )
    assert students_group_labs == [lab0.id]

    # we need to get lab objects again so that they are bound to satoshi user
    lab0 = cl_satoshi.find_labs_by_title(title="lab0")[0]
    # satishi can only see groups where he is a member - in this case students
    assert lab0.groups == [
        {"id": students_group["id"], "permission": "read_only"},
    ]
    # we cannot modify groups associations as satoshi is not owner or admin
    with pytest.raises(requests.exceptions.HTTPError) as err:
        lab0.update_lab_groups(group_list=[])
    assert err.value.response.status_code == 403
    assert "User does not have required access" in err.value.response.text

    # we cannot modify notes
    with pytest.raises(requests.exceptions.HTTPError) as err:
        lab0.notes = "new note"
    assert err.value.response.status_code == 403
    assert "User does not have write permission to lab" in err.value.response.text

    # we cannot modify description
    with pytest.raises(requests.exceptions.HTTPError) as err:
        lab0.description = "new description"
    assert err.value.response.status_code == 403
    assert "User does not have write permission to lab" in err.value.response.text

    # change students association to lab0 to read_write
    assert cl_admin.group_management.update_group(
        group_id=students_group["id"],
        labs=[{"id": lab0.id, "permission": "read_write"}],
    )
    # now user can perform writes to associated lab
    lab0.notes = "new note"
    assert lab0.notes == "new note"
    lab0.description = "new description"
    assert lab0.description == "new description"
    # get students groups association to lab0 back to read only
    # satoshi cannot - he is not admin or owner
    with pytest.raises(requests.exceptions.HTTPError) as err:
        lab0.update_lab_groups(
            group_list=[
                {"id": students_group["id"], "permission": "read_only"},
            ]
        )
    assert err.value.response.status_code == 403
    assert "User does not have required access" in err.value.response.text
    # admin can
    lab0 = cl_admin.find_labs_by_title(title="lab0")[0]
    lab0.update_lab_groups(
        group_list=[
            {"id": students_group["id"], "permission": "read_only"},
        ]
    )
    lab0 = cl_satoshi.find_labs_by_title(title="lab0")[0]
    assert lab0.groups == [
        {"id": students_group["id"], "permission": "read_only"},
    ]
    # add teachers group rw association to lab0 (admin action)
    teachers_group = cl_admin.group_management.update_group(
        group_id=teachers_group["id"], labs=lab0_1_rw
    )
    assert len(teachers_group["labs"]) == 2
    # we cannot modify groups associations as satoshi is not admin or owner
    with pytest.raises(requests.exceptions.HTTPError) as err:
        lab0.update_lab_groups(group_list=[])
    assert err.value.response.status_code == 403
    assert "User does not have required access" in err.value.response.text

    # we cannot modify notes
    with pytest.raises(requests.exceptions.HTTPError) as err:
        lab0.notes = "new note"
    assert err.value.response.status_code == 403
    assert "User does not have write permission to lab" in err.value.response.text

    # we cannot modify description
    with pytest.raises(requests.exceptions.HTTPError) as err:
        lab0.description = "new description"
    assert err.value.response.status_code == 403
    assert "User does not have write permission to lab" in err.value.response.text

    # as satoshi has no access to lab1 - below list is empty
    assert cl_satoshi.find_labs_by_title(title="lab1") == []
    # add satoshi to teachers group - by doing this now he gains read write
    # access to both lab0 and lab1
    teachers_group = cl_admin.group_management.update_group(
        group_id=teachers_group["id"], members=[satoshi_uid]
    )
    # now we can access teachers group and related data
    assert cl_satoshi.group_management.get_group(group_id=teachers_group["id"])
    assert cl_satoshi.group_management.group_members(group_id=teachers_group["id"]) == [
        satoshi_uid
    ]
    assert (
        len(cl_satoshi.group_management.group_labs(group_id=teachers_group["id"])) == 2
    )
    user_groups = cl_satoshi.user_management.user_groups(user_id=satoshi_uid)
    assert students_group["id"] in user_groups and teachers_group["id"] in user_groups
    associated_groups_names = [
        group["name"] for group in cl_satoshi.group_management.groups()
    ]
    assert (
        "students" in associated_groups_names and "teachers" in associated_groups_names
    )
    # test adjusting lab groups (only owner and admin can change lab group associations)
    # admin must see all associations
    # owner and non-admin users can only see those associations where they are members of group
    # log in as non-admin satoshi user
    cl_halfinn = ClientLibrary(
        client_config.url,
        username="halfinney",
        password=satoshi_pwd,
        ssl_verify=client_config.ssl_verify,
        allow_http=client_config.allow_http,
    )
    # create lab owned by halfin
    lab2 = cl_halfinn.create_lab(title="lab2")
    # only satoshi in students group + add lab2 association
    cl_admin.group_management.update_group(
        group_id=students_group["id"],
        members=[satoshi_uid],
        labs=[{"id": lab2.id, "permission": "read_only"}],
    )
    # only halfinney in teachers group + add lab2 association
    cl_admin.group_management.update_group(
        group_id=teachers_group["id"],
        members=[halfinn_uid],
        labs=[{"id": lab2.id, "permission": "read_only"}],
    )
    halfinn_lab2 = cl_halfinn.find_labs_by_title(title="lab2")[0]
    # get lab owned by halfinney with satoshi (who is not owner)
    satoshi_lab2 = cl_satoshi.find_labs_by_title(title="lab2")[0]
    # get lab owned by halfinney with admin
    admin_lab2 = cl_admin.find_labs_by_title(title="lab2")[0]

    # admin must see both groups associated with lab2
    assert admin_lab2.groups == [
        {"id": students_group["id"], "permission": "read_only"},
        {"id": teachers_group["id"], "permission": "read_only"},
    ]
    # halfinney only sees group that he is member of (teachers)
    assert halfinn_lab2.groups == [
        {"id": teachers_group["id"], "permission": "read_only"},
    ]
    # satoshi only sees group that he is member of (students)
    assert satoshi_lab2.groups == [
        {"id": students_group["id"], "permission": "read_only"},
    ]
    # satoshi cannot update lab groups associations for lab2 -> 403 (not owner or admin)
    with pytest.raises(requests.exceptions.HTTPError) as err:
        satoshi_lab2.update_lab_groups(group_list=[])
    assert err.value.response.status_code == 403
    assert "User does not have required access" in err.value.response.text
    # associations mus still be present after above failure
    assert admin_lab2.groups == [
        {"id": students_group["id"], "permission": "read_only"},
        {"id": teachers_group["id"], "permission": "read_only"},
    ]
    # halfinney cannot add/remove students association to lab2 as he is not member of students
    halfinn_lab2.update_lab_groups(group_list=[])
    # above only removed the group teachers as halfinn is owner and also member of teachers
    assert halfinn_lab2.groups == []  # sees nothing
    assert satoshi_lab2.groups == [
        {"id": students_group["id"], "permission": "read_only"},
    ]  # sees students
    assert admin_lab2.groups == [
        {"id": students_group["id"], "permission": "read_only"},
    ]  # admin too sees only students as that is now only associtation
    # halfinney cannot add students group as he is not member
    with pytest.raises(requests.exceptions.HTTPError) as err:
        halfinn_lab2.update_lab_groups(
            group_list=[{"id": students_group["id"], "permission": "read_only"}]
        )
    assert err.value.response.status_code == 403
    assert "User does not have required access" in err.value.response.text
    # halfinney can add teachers as he is a member
    halfinn_lab2.update_lab_groups(
        group_list=[{"id": teachers_group["id"], "permission": "read_only"}]
    )
    # halfinney only sees group that he is member of (teachers)
    assert halfinn_lab2.groups == [
        {"id": teachers_group["id"], "permission": "read_only"},
    ]
    # add halfinney to students group
    cl_admin.group_management.update_group(
        group_id=students_group["id"],
        members=[satoshi_uid, halfinn_uid],
    )
    # halfinney now sees both students and teachers
    # associations mus still be present after above failure
    assert halfinn_lab2.groups == [
        {"id": students_group["id"], "permission": "read_only"},
        {"id": teachers_group["id"], "permission": "read_only"},
    ]
    # he can now also remove both associations
    halfinn_lab2.update_lab_groups(group_list=[])
    assert admin_lab2.groups == []
    assert halfinn_lab2.groups == []
    # satoshi lost access --> 404
    with pytest.raises(requests.exceptions.HTTPError) as err:
        assert satoshi_lab2.groups == []
    assert err.value.response.status_code == 404
    assert "Lab not found" in err.value.response.text
    # add also possible
    halfinn_lab2.update_lab_groups(
        group_list=[
            {"id": students_group["id"], "permission": "read_only"},
            {"id": teachers_group["id"], "permission": "read_only"},
        ]
    )
    assert halfinn_lab2.groups == [
        {"id": students_group["id"], "permission": "read_only"},
        {"id": teachers_group["id"], "permission": "read_only"},
    ]
    assert satoshi_lab2.groups == [
        {"id": students_group["id"], "permission": "read_only"},
    ]  # sees students as he is only part of students not teachers
    assert admin_lab2.groups == [
        {"id": students_group["id"], "permission": "read_only"},
        {"id": teachers_group["id"], "permission": "read_only"},
    ]
    # admin can do whatever he pleases
    admin_lab2.update_lab_groups(group_list=[])
    assert admin_lab2.groups == []
    assert halfinn_lab2.groups == []
    # satoshi lost access --> 404
    with pytest.raises(requests.exceptions.HTTPError) as err:
        assert satoshi_lab2.groups == []
    assert err.value.response.status_code == 404
    assert "Lab not found" in err.value.response.text

    # CLEAN UP
    # again need to get lab0 from admin account
    lab0 = cl_admin.find_labs_by_title(title="lab0")[0]
    lab0.remove()
    lab1.remove()
    lab2.remove()
    cl_admin.user_management.delete_user(user_id=satoshi_uid)
    cl_admin.user_management.delete_user(user_id=halfinn_uid)
    assert cl_admin.group_management.delete_group(group_id=students_group["id"]) is None
    assert cl_admin.group_management.delete_group(group_id=teachers_group["id"]) is None
