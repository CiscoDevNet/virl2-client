#!/usr/bin/env python3
#
# This file is part of VIRL 2
# Copyright (c) 2019-2025, Cisco Systems, Inc.
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

import getpass
import json

from virl2_client import ClientLibrary

VIRL_CONTROLLER = "virl2-controller"
VIRL_USERNAME = input("username: ")
VIRL_PASSWORD = getpass.getpass("password: ")
SL_TOKEN = input("Smart License token: ")

client = ClientLibrary(VIRL_CONTROLLER, VIRL_USERNAME, VIRL_PASSWORD, ssl_verify=False)

# Get the licensing handle from the client as a property
licensing = client.licensing

# Setup default license transport (i.e., directly connected to the external
# Smart License server)
licensing.set_default_transport()

# Register with the Smart License server.
# Wait for registration and authorization to complete.
result = licensing.register_wait(SL_TOKEN)
if not result:
    result = licensing.get_reservation_return_code()
    print(f"ERROR: Failed to register with Smart License server: {result}!")
    exit(1)

# Get the current registration status. This returns a JSON blob with license
# status and authorization details.
status = licensing.status()

# Get the current list of licensed features. This returns a JSON blob with
# licensed features.
features = licensing.features()

print(json.dumps(status, indent=4))

"""
Prints:

{
    "udi": "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx",
    "registration": {
        "status": "COMPLETED",
        "expires": "2021-06-10 20:17:39",
        "smart_account": "Foo",
        "virtual_account": "Bar",
        "instance_name": "cml-controller.cml.lab",
        "register_time": {
            "succeeded": null,
            "attempted": "2020-06-10 20:22:33",
            "scheduled": null,
            "status": null,
            "failure": "OK",
            "success": "SUCCESS"
        },
        "renew_time": {
            "succeeded": null,
            "attempted": null,
            "scheduled": "2020-12-07 20:22:40",
            "status": null,
            "failure": null,
            "success": "FAILED"
        }
    },
    "authorization": {
        "status": "IN_COMPLIANCE",
        "renew_time": {
            "succeeded": null,
            "attempted": "2020-07-25 16:44:09",
            "scheduled": "2020-08-24 16:44:08",
            "status": "SUCCEEDED",
            "failure": null,
            "success": "SUCCESS"
        },
        "expires": "2020-10-23 16:39:07"
    },
    "reservation_mode": false,
    "transport": {
        "ssms": "https://smartreceiver.cisco.com/licservice/license",
        "proxy": {
            "server": null,
            "port": null
        },
        "default_ssms": "https://smartreceiver.cisco.com/licservice/license"
    },
    "features": [
        {
            "name": "CML - Enterprise License",
            "description": "Cisco Modeling Labs - Enterprise License with 20 nodes \
                capacity included",
            "in_use": 1,
            "status": "IN_COMPLIANCE",
            "version": "1.0"
        },
        {
            "name": "CML \u2013 Expansion Nodes",
            "description": "Cisco Modeling Labs - Expansion node capacity for CML \
                Enterprise Servers",
            "in_use": 50,
            "status": "IN_COMPLIANCE",
            "version": "1.0"
        }
    ]
}
"""

print(json.dumps(features, indent=4))
"""
Prints:

[
    {
        "id": "regid.2019-10.com.cisco.CML_ENT_BASE,\
            1.0_xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxx",
        "name": "CML - Enterprise License",
        "description": "Cisco Modeling Labs - Enterprise License with 20 nodes \
            capacity included",
        "in_use": 1,
        "status": "IN_COMPLIANCE",
        "version": "1.0",
        "min": 0,
        "max": 1
    },
    {
        "id": "regid.2019-10.com.cisco.CML_NODE_COUNT,\
            1.0_xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxx",
        "name": "CML \u2013 Expansion Nodes",
        "description": "Cisco Modeling Labs - Expansion node capacity for \
            CML Enterprise Servers",
        "in_use": 50,
        "status": "IN_COMPLIANCE",
        "version": "1.0",
        "min": 0,
        "max": 300
    }
]
"""
