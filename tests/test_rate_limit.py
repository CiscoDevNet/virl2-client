import pytest
import requests

from virl2_client import ClientConfig


LIMITED_ENDPOINTS = ["/api/v0/authenticate", "/api/v0/auth_extended"]


@pytest.mark.integration
@pytest.mark.nomock
def test_rate_limit(client_config: ClientConfig):
    for endpoint in LIMITED_ENDPOINTS:
        for i in range(30):
            r = requests.post(
                client_config.url + endpoint,
                json={"username": client_config.username, "password": "incorrect_pwd"},
                verify=False,
            )
            assert r.status_code != 429
