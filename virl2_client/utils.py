#
# This file is part of VIRL 2
# Copyright (c) 2019-2022, Cisco Systems, Inc.
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

from __future__ import annotations

import io
import logging
from typing import Callable


class TextFsmNotInstalled(Exception):
    pass


_LOGGER = logging.getLogger(__name__)


class TextFsmTemplateHelper:
    def __init__(self) -> None:
        self._tokens: list[str] = []
        self._lines: list[str] = []

    def clear(self) -> None:
        self._tokens = []
        self._lines = []

    def add_token(self, name: str, pattern: str) -> None:
        # TODO: warn if not raw string
        entry = "Value {} ({})".format(name, pattern)
        self._tokens.append(entry)

    def add_numeric_token(self, name: str) -> None:
        # TODO: warn if not raw string
        entry = "Value {} (\\d+)".format(name)
        self._tokens.append(entry)

    def add_line(self, line: str) -> None:
        # TODO: warn if unescaped brackets in line
        self._lines.append(line)

    def render(self) -> str:
        result = ""
        for token in self._tokens:
            result += token + "\n"

        result += "\n"
        result += "Start\n"
        for line in self._lines:
            result += r"  ^{} -> Record".format(line)

        return result


def splice_interface_ip_into_config(
    config: str, remote: str, ip_address: str, netmask: str
) -> str:
    search_string = "description to {}\n    no ip address".format(remote)
    replace_string = "description to {}\n    ip address {} {}".format(
        remote, ip_address, netmask
    )
    return config.replace(search_string, replace_string)


def parse_with_textfsm_template(template: str, cli_result: str) -> list:
    try:
        import textfsm
    except ImportError:
        _LOGGER.warning("TextFSM not installed")
        raise TextFsmNotInstalled

    string_fh = io.StringIO(template)
    fsm = textfsm.TextFSM(string_fh)
    fsm_result = fsm.ParseText(cli_result)
    result = []
    for entry in fsm_result:
        data = {}
        for index, heading in enumerate(fsm.header):
            data[heading] = entry[index]
        result.append(data)

    return result


def parse_ping(result: str) -> dict:
    import re

    match = re.search(r"Success rate is (?P<rate>\d+) percent", result)
    success_rate = int(match.group("rate"))
    return {"success": success_rate}


def parse_interfaces(
    get_offsets_for_keywords: Callable[[str], dict],
    parse_line: Callable[[str, list, dict], dict],
    result: str,
) -> dict:
    lines = result.splitlines()

    title = lines[0]
    body = lines[1:]
    offsets = get_offsets_for_keywords(title)
    keys = ["Interface", "Status", "Protocol"]

    result = {}

    for line in body:
        data = parse_line(line, keys, offsets)
        label = data["Interface"]
        result[label] = {"Status": data["Status"], "Protocol": data["Protocol"]}

    return result


def parse_line(line: str, keys: list, offsets: dict) -> dict:
    result = {}
    for key in keys:
        start = offsets[key]["start"]
        end = offsets[key]["end"]
        value = line[start:end]
        # strip off whitespace as could be right padded if short entry relative
        # to others in the column
        result[key] = value.rstrip()
    return result


def get_offsets_for_keywords(title: str) -> dict:
    offsets = {}
    start_index_for_keyword = None
    keyword = None
    previous_keyword = None

    for index, element in enumerate(title):
        if element == " ":
            if start_index_for_keyword is not None:
                offsets[keyword] = {}
                offsets[keyword]["start"] = start_index_for_keyword

                if previous_keyword:
                    offsets[previous_keyword]["end"] = start_index_for_keyword - 1

                start_index_for_keyword = None
                previous_keyword = keyword
                keyword = ""
        else:
            if start_index_for_keyword is None:
                start_index_for_keyword = index
                keyword = element
            else:
                keyword += element
    # and store final item (as don't transition char->whitespace)
    if start_index_for_keyword:
        offsets[keyword] = {}
        offsets[previous_keyword]["end"] = start_index_for_keyword - 1
        offsets[keyword]["start"] = start_index_for_keyword
        offsets[keyword]["end"] = index
    return offsets
