#
# This file is part of VIRL 2
# Copyright (c) 2019, Cisco Systems, Inc.
# All rights reserved.
#
import json
import os
from pathlib import Path
from unittest.mock import Mock, call, patch
from urllib.parse import urlsplit

import pytest
import requests
import responses

from virl2_client.models import Lab
from virl2_client.virl2_client import ClientLibrary, InitializationError


@pytest.fixture
def mocked_session():
    with patch.object(requests, "Session", autospec=True) as session:
        yield session


def test_import_lab_from_path_ng(mocked_session, tmp_path: Path):
    client_library = ClientLibrary(url="http://0.0.0.0/fake_url/", username="test", password="pa$$")
    Lab.sync = Mock()

    topology_data = '{"nodes": [], "links": [], "interfaces": []}'
    (tmp_path / "topology.ng").write_text(topology_data)
    with patch.object(Lab, "sync", autospec=True) as sync_mock:
        lab = client_library.import_lab_from_path(topology=(tmp_path / "topology.ng").as_posix())

    assert lab.title is not None
    assert lab.lab_base_url.startswith("https://0.0.0.0/fake_url/api/v0/labs/")

    client_library.session.post.assert_called_once_with(
            'https://0.0.0.0/fake_url/api/v0/import?is_json=true&title=topology.ng',
            data=topology_data)
    client_library.session.post.assert_called_once()
    client_library.session.post.return_value.raise_for_status.assert_called_once()
    sync_mock.assert_called_once_with()


def test_import_lab_from_path_virl(mocked_session, tmp_path: Path):
    client_library = ClientLibrary(url="http://0.0.0.0/fake_url/", username="test", password="pa$$")
    Lab.sync = Mock()

    (tmp_path / "topology.virl").write_text("<?xml version='1.0' encoding='UTF-8'?>")
    with patch.object(Lab, "sync", autospec=True) as sync_mock:
        lab = client_library.import_lab_from_path(topology=(tmp_path / "topology.virl").as_posix())

    assert lab.title is not None
    assert lab.lab_base_url.startswith("https://0.0.0.0/fake_url/api/v0/labs/")

    client_library.session.post.assert_called_once_with(
            'https://0.0.0.0/fake_url/api/v0/import/virl-1x?title=topology.virl',
            data="<?xml version='1.0' encoding='UTF-8'?>")
    client_library.session.post.assert_called_once()
    client_library.session.post.return_value.raise_for_status.assert_called_once()
    sync_mock.assert_called_once_with()


def test_ssl_certificate(mocked_session):
    client_library = ClientLibrary(url="http://0.0.0.0/fake_url/",
                                   username="test",
                                   password="pa$$",
                                   ssl_verify="/home/user/cert.pem")
    client_library.wait_for_lld_connected()

    assert client_library.session.verify == "/home/user/cert.pem"
    assert client_library.session.mock_calls == [
        call.get('https://0.0.0.0/fake_url/api/v0/labs'),
        call.get().raise_for_status(),
        call.get('https://0.0.0.0/fake_url/api/v0/wait_for_lld_connected'),
        call.get().raise_for_status()
    ]


def test_ssl_certificate_from_env_variable(monkeypatch, mocked_session):
    monkeypatch.setitem(os.environ, "CA_BUNDLE", "/home/user/cert.pem")
    client_library = ClientLibrary(url="http://0.0.0.0/fake_url/", username="test", password="pa$$")
    client_library.wait_for_lld_connected()

    assert client_library.session.verify == "/home/user/cert.pem"
    assert client_library.session.mock_calls == [
        call.get('https://0.0.0.0/fake_url/api/v0/labs'),
        call.get().raise_for_status(),
        call.get('https://0.0.0.0/fake_url/api/v0/wait_for_lld_connected'),
        call.get().raise_for_status()
    ]


@responses.activate
def test_auth_and_reauth_token():
    # TODO: need to check what the purpose of this test is, and how it works with the automatic auth check on CL init
    # if there's environ vars for username and password set
    # then delete them b/c we rely on specific usernames
    # and passwords for this test!
    try:
        del os.environ['SIMPLE_PASS']
        del os.environ['SIMPLE_USER']
    except KeyError:
        pass

    # mock always successful authentication:
    responses.add(responses.POST, 'https://0.0.0.0/fake_url/api/v0/authenticate',
                  json="7bbcan78a98bch7nh3cm7hao3nc7")
    responses.add(responses.GET, 'https://0.0.0.0/fake_url/api/v0/wait_for_lld_connected')
    responses.add(responses.GET, 'https://0.0.0.0/fake_url/api/v0/wait_for_lld_connected', status=401)
    responses.add(responses.GET, 'https://0.0.0.0/fake_url/api/v0/wait_for_lld_connected')
    responses.add(responses.GET, 'https://0.0.0.0/fake_url/api/v0/wait_for_lld_connected', status=401)

    with pytest.raises(InitializationError):
        # Test returns custom exception when instructed to raise on check
        client_library = ClientLibrary(url="http://0.0.0.0/fake_url/", username="test", password="pa$$",
                                       raise_for_auth_failure=True)

    client_library = ClientLibrary(url="http://0.0.0.0/fake_url/", username="test", password="pa$$")
    client_library.wait_for_lld_connected()

    # last request fails as after reauthentication status code of response is still 401:
    # with pytest.raises(requests.exceptions.HTTPError) as exc:
    #     client_library.wait_for_lld_connected()
    #     assert exc.value.response.status_code == 401

    assert responses.calls[0].request.url == "https://0.0.0.0/fake_url/api/v0/authenticate"
    assert json.loads(responses.calls[0].request.body) == {'username': 'test', 'password': 'pa$$'}
    assert responses.calls[1].request.url == "https://0.0.0.0/fake_url/api/v0/labs"
    assert responses.calls[1].request.method == "GET"
    assert responses.calls[2].request.url == "https://0.0.0.0/fake_url/api/v0/authenticate"
    assert responses.calls[3].request.url == "https://0.0.0.0/fake_url/api/v0/labs"
    assert responses.calls[4].request.url == "https://0.0.0.0/fake_url/api/v0/wait_for_lld_connected"

    assert len(responses.calls) == 5


def test_client_library_init_allow_http():
    client_library = ClientLibrary("http://somehost", "virl2", "virl2", allow_http=True)
    url_parts = urlsplit(client_library._context.base_url)
    assert url_parts.scheme == "http"
    assert url_parts.hostname == "somehost"
    assert url_parts.port == None
    assert client_library._context.base_url.endswith("/api/v0/")
    assert client_library.username == "virl2"
    assert client_library.password == "virl2"


@pytest.mark.parametrize("via", ["environment", "parameter"])
@pytest.mark.parametrize("parms", [
        (False, "somehost"),
        (False, "http://somehost"),
        (False, "https://somehost:443"),
        (True, "xyz://somehost:443"),
        (True, "https:@somehost:4:4:3"),
    ]
)
def test_client_library_init_url(monkeypatch, via, parms):
    (fail, url) = parms
    if via == "environment":
        monkeypatch.setenv("VIRL2_URL", url)
        url = None
    if fail:
        with pytest.raises((InitializationError, requests.exceptions.InvalidURL)) as exc:
            client_library = ClientLibrary(url=url, username="virl2", password="virl2")
    else:
        client_library = ClientLibrary(url, username="virl2", password="virl2")
        url_parts = urlsplit(client_library._context.base_url)
        assert url_parts.scheme == "https"
        assert url_parts.hostname == "somehost"
        assert url_parts.port == 443 or url_parts.port == None
        assert client_library._context.base_url.endswith("/api/v0/")
        assert client_library.username == "virl2"
        assert client_library.password == "virl2"


@pytest.mark.parametrize("via", ["environment", "parameter"])
@pytest.mark.parametrize("parms", [
        (False, "johndoe"),
        (True, ""),
        (True, None),
    ]
)
def test_client_library_init_user(monkeypatch, via, parms):
    url = "validhostname"
    (fail, user) = parms
    if via == "environment":
        # can't set a None value for an environment variable
        monkeypatch.setenv("VIRL2_USER", user or "")
        user = None
    if fail:
        with pytest.raises((InitializationError, requests.exceptions.InvalidURL)) as exc:
            client_library = ClientLibrary(url=url, username=user, password="virl2")
    else:
        client_library = ClientLibrary(url, username=user, password="virl2")
        assert client_library.username == parms[1]
        assert client_library.password == "virl2"
        assert client_library._context.base_url == "https://validhostname/api/v0/"


@pytest.mark.parametrize("via", ["environment", "parameter"])
@pytest.mark.parametrize("parms", [
        (False, "validPa$$w!2"),
        (True, ""),
        (True, None),
    ]
)
def test_client_library_init_password(monkeypatch, via, parms):
    url = "validhostname"
    (fail, password) = parms
    if via == "environment":
        # can't set a None value for an environment variable
        monkeypatch.setenv("VIRL2_PASS", password or "")
        password = None
    if fail:
        with pytest.raises((InitializationError, requests.exceptions.InvalidURL)) as exc:
            client_library = ClientLibrary(url=url, username="virl2", password=password)
    else:
        client_library = ClientLibrary(url, username="virl2", password=password)
        assert client_library.username == "virl2"
        assert client_library.password == parms[1]
        assert client_library._context.base_url == "https://validhostname/api/v0/"

def test_client_library_str_and_repr():
    client_library = ClientLibrary("somehost", "virl2", password="virl2")

    assert repr(client_library) == "ClientLibrary('somehost', 'virl2', 'virl2', True, False, False)"
    assert str(client_library) == "ClientLibrary URL: https://somehost/api/v0/"
