# coding: utf-8
#
#  This file is part of VIRL2
#  Cisco (c) 2020
#

import logging
import re
import pytest

from virl2_client import ClientLibrary
from virl2_client.models.cl_pyats import ClPyats

logger = logging.getLogger("__main__")
logging.basicConfig(level=logging.INFO)

# pytestmark = [pytest.mark.integration]

RE1 = r"(\d+) packets transmitted, (\d+) packets received, (\d+)% packet loss"
RE2 = r"round-trip min/avg/max = [\d\.]+/([\d\.]+)/[\d\.]+ ms"


def check_result(result, has_loss, min_avg, max_avg):
    print(result)
    rm = re.search(RE1, result, re.MULTILINE)
    assert len(rm.groups()) == 3
    transmitted, received, loss = [int(a) for a in rm.groups()]
    # print(transmitted, received, loss)
    if has_loss:
        assert transmitted != received
        assert loss > 0
    else:
        assert transmitted == received
        assert loss == 0

    rm = re.search(RE2, result, re.MULTILINE)
    assert len(rm.groups()) == 1
    avg = float(rm.group(1))
    # print("avg:", avg)
    assert min_avg <= avg <= max_avg


@pytest.mark.integration
@pytest.mark.nomock
def test_link_conditioning(register_licensing, client_library_keep_labs: ClientLibrary):
    lab = client_library_keep_labs.create_lab()

    alpine = lab.create_node("alpine-0", "alpine", 0, 0)
    ums = lab.create_node("unmanaged-switch-0", "unmanaged_switch", 100, 0)
    ext = lab.create_node("ext", "external_connector", 200, 0)

    lab.connect_two_nodes(alpine, ums)
    lab.connect_two_nodes(ums, ext)

    lab.start(wait=True)

    alpine = lab.get_node_by_label("alpine-0")
    ums = lab.get_node_by_label("unmanaged-switch-0")
    link = lab.get_link_by_nodes(alpine, ums)

    pylab = ClPyats(lab)
    pylab.sync_testbed("cml2", "cml2cml2")

    # ensure there's no link condition
    result = link.get_condition()
    assert result is None

    # remove, just to be sure
    link.remove_condition()
    result = pylab.run_command("alpine-0", "time ping -Aqc100  192.168.255.1")
    check_result(result, False, 0.0, 10.0)

    # link.set_condition_by_name("dsl1")

    # 2mbps, 50ms delay, 0ms jitter, 5.1% loss)
    # 5.1 to ensure that the float is understood and returned
    link.set_condition(2000, 50, 0, 5.1)

    result = link.get_condition()
    assert result == {"bandwidth": 2000, "latency": 50, "loss": 5.1, "jitter": 0}

    result = pylab.run_command("alpine-0", "time ping -Aqc100 192.168.255.1")
    check_result(result, True, 90.0, 110.0)

    link.remove_condition()
    result = pylab.run_command("alpine-0", "time ping -Aqc100  192.168.255.1")
    check_result(result, False, 0.0, 10.0)

    lab.stop()
    lab.wipe()
    lab.remove()
