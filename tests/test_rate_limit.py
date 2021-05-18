import pytest
import requests


LIMITED_ENDPOINTS = ["/api/v0/authenticate", "/api/v0/auth_extended"]


@pytest.mark.integration
@pytest.mark.nomock
def test_rate_limit(controller_url):
    for endpoint in LIMITED_ENDPOINTS:
        for i in range(30):
            r = requests.post(
                controller_url + endpoint,
                json={"username": "admin", "password": "incorrect_pwd"},
                verify=False,
            )
            assert r.status_code != 429
