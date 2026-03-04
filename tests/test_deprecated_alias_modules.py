"""Tests for deprecated alias modules and emitted warning categories."""

from __future__ import annotations

import importlib
import sys
import warnings

import pytest


@pytest.mark.parametrize(
    "module_name",
    [
        "virl2_client.models.groups",
        "virl2_client.models.users",
        "virl2_client.models.node_image_definitions",
        "virl2_client.models.resource_pools",
    ],
)
def test_deprecated_alias_warns(module_name: str) -> None:
    """Verify importing alias modules emits UserWarning (not DeprecationWarning).

    NOTE: LLM-generated test -- verify for correctness.

    :param module_name: Deprecated alias module path to import.
    """
    sys.modules.pop(module_name, None)
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        importlib.import_module(module_name)
    assert caught, "Expected warning when importing deprecated alias module."
    assert all(issubclass(w.category, UserWarning) for w in caught)
    assert all(not issubclass(w.category, DeprecationWarning) for w in caught)
