#
# This file is part of VIRL 2
# Copyright (c) 2019-2026, Cisco Systems, Inc.
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
"""Unit tests for general-purpose helpers in virl2_client.utils."""

from __future__ import annotations

import pytest

from virl2_client.utils import sanitize_for_log


def test_sanitize_for_log_strips_cr_lf() -> None:
    """sanitize_for_log strips CR/LF to stop log-line injection/forging.

    NOTE: LLM-generated test -- verify for correctness.
    """
    text = "line one\r\nfake next log line\ninjected"
    result = sanitize_for_log(text)
    assert "\r" not in result
    assert "\n" not in result
    assert result == "line one  fake next log line injected"


def test_sanitize_for_log_caps_length() -> None:
    """sanitize_for_log truncates text longer than max_len.

    NOTE: LLM-generated test -- verify for correctness.
    """
    text = "a" * 500
    result = sanitize_for_log(text, max_len=50)
    assert result.startswith("a" * 50)
    assert result.endswith("...(truncated)")
    assert len(result) < len(text)


@pytest.mark.parametrize(
    "text",
    ["", "short text", "a" * 200],
)
def test_sanitize_for_log_leaves_short_text_unchanged(text: str) -> None:
    """sanitize_for_log returns text unchanged when within the length cap.

    NOTE: LLM-generated test -- verify for correctness.

    :param text: Input text at or below the default max_len.
    """
    assert sanitize_for_log(text) == text
