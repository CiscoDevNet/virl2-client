#
# This file is part of VIRL 2
# Copyright (c) 2019, Cisco Systems, Inc.
# All rights reserved.
#
import pytest

from virl2_client import ClientLibrary


@pytest.mark.integration
def test_start_stop_start_stop_cycle(client_library: ClientLibrary):
    """we need to test if the entire lifecycle works... e.g.
    - define
    - start
    - queued
    - booted
    - stopped
    - queued
    - start
    - stopped
    - ...
    """
    lab = client_library.import_sample_lab("server-triangle.ng")

    lab.start()
    lab.stop()
    lab.start()
    lab.stop()
    lab.wipe()
