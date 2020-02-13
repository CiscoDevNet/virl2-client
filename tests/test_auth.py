#
# This file is part of VIRL 2
# Copyright (c) 2019, Cisco Systems, Inc.
# All rights reserved.
#
import pytest
import requests.exceptions

from virl2_client import ClientLibrary


@pytest.mark.integration
def test_sending_requests_without_auth_token(controller_url: str):
    client_library = ClientLibrary(controller_url, username="virl2", password="virl2", ssl_verify=False, allow_http=True)

    # it probably won't be a common case to override `auth` by ClientLibrary users
    # but missing auth token may happen when using API directly via HTTP:
    client_library.session.auth = None
    with pytest.raises(requests.exceptions.HTTPError) as exc:
        client_library.create_lab()
    exc.match('401 Client Error: Unauthorized for url')
