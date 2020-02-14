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

import io
import logging


class TextFsmNotInstalled(Exception):
    pass


logger = logging.getLogger(__name__)


class TextFsmTemplateHelper():
    def __init__(self):
        self._tokens = []
        self._lines = []

    def clear(self):
        self._tokens = []
        self._lines = []

    def add_token(self, name, pattern):
        # TODO: warn if not raw string
        entry = f"Value {name} ({pattern})"
        self._tokens.append(entry)

    def add_numeric_token(self, name):
        # TODO: warn if not raw string
        entry = f"Value {name}" + r" (\d+)"
        self._tokens.append(entry)

    def add_line(self, line):
        # TODO: warn if unescaped brackets in line
        self._lines.append(line)

    def render(self):
        result = ""
        for token in self._tokens:
            result += token + "\n"

        result += "\n"
        result += "Start\n"
        for line in self._lines:
            result += fr"  ^{line} -> Record"

        return result


def splice_interface_ip_into_config(config, remote, ip_address, netmask):
    search_string = f"description to {remote}\n    no ip address"
    replace_string = f"description to {remote}\n    ip address {ip_address} {netmask}"
    return config.replace(search_string, replace_string)


def parse_with_textfsm_template(template, cli_result):
    try:
        import textfsm
    except ImportError:
        logger.warning("TextFSM not installed")
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


def parse_ping(result):
    import re
    match = re.search(r'Success rate is (?P<rate>\d+) percent', result)
    success_rate = int(match.group('rate'))
    return {"success": success_rate}


def parse_interfaces(get_offsets_for_keywords, parse_line, result):
    interfaces = {}
    lines = result.splitlines()

    title = lines[0]
    body = lines[1:]
    offsets = get_offsets_for_keywords(title)
    keys = ["Interface", "Status", "Protocol"]

    result = {}

    for line in body:
        data = parse_line(line, keys, offsets)
        label = data["Interface"]
        result[label] = {"Status": data["Status"],
                         "Protocol": data["Protocol"]}

    return result


def parse_line(line, keys, offsets):
    result = {}
    for key in keys:
        start = offsets[key]["start"]
        end = offsets[key]["end"]
        value = line[start:end]
        # strip off whitespace as could be right padded if short entry relative to others in the column
        result[key] = value.rstrip()
    return result


def get_offsets_for_keywords(title):
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
