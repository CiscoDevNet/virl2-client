#!/usr/bin/env python3
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

from virl2_client import ClientLibrary


CERT = """-----BEGIN CERTIFICATE-----
MIIDGzCCAgOgAwIBAgIBATANBgkqhkiG9w0BAQsFADAvMQ4wDAYDVQQKEwVDaXNj
WhcNMzMwNDI0MjE1NTQzWjAvMQ4wDAYDVQQKEwVDaXNjbzEdMBsGA1UEAxMUTGlj
ZW5zaW5nIFJvb3QgLSBERVYwggEiMA0GCSqGSIb3DQEBAQUAA4IBDwAwggEKAoIB
AQCcVnEB1h7fLrzDunrg27JBs7QyipsA64qA0Cqob17xrr/etnvWrX2te0P1gnU7
/8wcpaeEGgdpNNOvmQeO9heRlvpPs/LtOULHVr8coKnMmKen+eQ3JNnmHUeJ6eeS
3Z8ntFF8K97Q61uaeHughdm78APwVjvgpEUMjxJ7VYM+vBOFLZutmGjTrgdcJ5h8
HRMBAf8EBTADAQH/MB0GA1UdDgQWBBRDIUUhtfshehpNG7cCNuZky+yLZTANBgkq
hkiG9w0BAQsFAAOCAQEAhfGx8q6ufS+cqwNRwynj8a6YLfEfXjyQ9gCzze1aFJH7
3wfgbKoPQyWftMSuIID2dYw7esVOqqA+xbUKL2cK/4ftpkYvz8Q5Z8AkqzLuPM3P
oEudrhu6u9rI31WHz1HLHABaKC+LUYpajG+bPKq6NEYy7zp1wvRUUHqbz9MMi+VK
EYct4M8SANDRAY/ZrGhZaBZ+Qhybw5Ttm8hUY4OygUYHsr3t38FgW00WAHtocj4l
z1LPIlCn0j76n2sH+w9jhp3MO7xlJQaTOM9rpsuO/Q==
-----END CERTIFICATE-----"""

SSMS = "https://sch-alpha.cisco.com/its/service/oddce/services/DDCEService"

TOKEN = (
    "FFY4YzJjNjItMDUxNi00NjJhLWIzMzQtMzllMzEzN2NhYjk2"
    "6s8e1gr5res1g35ads1g651rg23rs1gs3rd5g1s2rd1g3s2r"
    "WhPV3MzWGJrT3U5VHVEL1NrWkNu%0AclBSST0%3D%0A"
)


# setup the connection and clean everything
cl = ClientLibrary("http://localhost:8001", "cml2", "cml2cml2", allow_http=True)
cl.is_system_ready(wait=True)

# set transport if needed - also proxy can be set if needed
# cl.licensing.licensing.set_transport(ssms=ssms, proxy_server="172.16.1.100", proxy_port=8888)
cl.licensing.set_transport(ssms=SSMS)
cl.licensing.install_certificate(cert=CERT)
# 'register_wait' method waits max 45s for registration status to become COMPLETED
# and another 45s for authorization status to become IN_COMPLIANCE
cl.licensing.register_wait(token=TOKEN)


lab_list = cl.get_lab_list()
for lab_id in lab_list:
    lab = cl.join_existing_lab(lab_id)
    lab.stop()
    lab.wipe()
    cl.remove_lab(lab_id)

lab = cl.create_lab()
lab = cl.join_existing_lab(lab_id="lab_1")

s1 = lab.create_node("s1", "server", 50, 100)
s2 = lab.create_node("s2", "server", 50, 200)
print(s1, s2)

# create a link between s1 and s2, equivalent to
#   s1_i1 = s1.create_interface()
#   s2_i1 = s2.create_interface()
#   lab.create_link(s1_i1, s2_i1)
lab.connect_two_nodes(s1, s2)

# this must remove the link between s1 and s2
lab.remove_node(s2)

lab.sync_states()
for node in lab.nodes():
    print(node, node.state)
    for iface in node.interfaces:
        print(iface, iface.state)

assert [link for link in lab.links() if link.state is not None] == []

# in case you's like to deregister after you're done
status = cl.licensing.deregister()
cl.licensing.remove_certificate()
# set licensing back to default transport
# default ssms is "https://tools.cisco.com/its/service/oddce/services/DDCEService"
cl.licensing.set_default_transport()
