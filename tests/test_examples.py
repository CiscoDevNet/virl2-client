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

"""Static checks that the examples/ scripts stay healthy.

These tests deliberately do not execute the example main()
functions -- that requires a live controller. Instead they enforce
contracts that are cheap to verify and that catch the bug classes the
examples have historically regressed on:

* syntactically valid Python that parses cleanly;
* importing the module has *no* side effects (no input(), no network,
  no credentials read at import time);
* nothing credential-shaped is committed into the source.
"""

from __future__ import annotations

import ast
import importlib.util
import json
import re
import sys
from pathlib import Path

import pytest

EXAMPLES_DIR = Path(__file__).resolve().parent.parent / "examples"

#: Python example files we verify. The notebook is scanned separately.
PY_EXAMPLES: list[Path] = sorted(EXAMPLES_DIR.glob("*.py"))

#: (label, regex) pairs for obvious credential shapes that must never
#: be committed. We keep the list deliberately narrow -- false
#: positives here would block unrelated example changes.
SECRET_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    (
        "AWS access key",
        re.compile(r"\bA(?:KIA|GPA|IDA|ROA|IPA|NPA|NVA|SIA)[0-9A-Z]{16}\b"),
    ),
    ("Stripe live key", re.compile(r"\b(?:sk|pk)_live_[0-9A-Za-z]{10,}\b")),
    ("GitHub token", re.compile(r"\bgh[posur]_[0-9A-Za-z]{20,}\b")),
    (
        "PEM private key",
        re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----"),
    ),
    (
        "JWT-looking literal",
        re.compile(r'"eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}"'),
    ),
]

#: Import-time modules that some examples use but that are optional
#: dependencies of virl2_client. Missing them should skip the import
#: assertion, not fail the test.
OPTIONAL_DEPS = {"aiohttp"}


@pytest.mark.parametrize("path", PY_EXAMPLES, ids=lambda p: p.name)
def test_example_parses(path: Path) -> None:
    """Each example file is valid Python."""
    ast.parse(path.read_text(), filename=str(path))


@pytest.mark.parametrize("path", PY_EXAMPLES, ids=lambda p: p.name)
def test_example_has_main_guard(path: Path) -> None:
    """Each example wraps its entry point behind if __name__ == '__main__':.

    The guard is what makes the module safe to import for the other
    static checks; regressing it would re-introduce the "runs input()
    at import time" bug class we fixed.
    """
    tree = ast.parse(path.read_text(), filename=str(path))
    has_guard = False
    for node in ast.iter_child_nodes(tree):
        if not isinstance(node, ast.If):
            continue
        test = node.test
        if (
            isinstance(test, ast.Compare)
            and isinstance(test.left, ast.Name)
            and test.left.id == "__name__"
            and len(test.ops) == 1
            and isinstance(test.ops[0], ast.Eq)
            and len(test.comparators) == 1
            and isinstance(test.comparators[0], ast.Constant)
            and test.comparators[0].value == "__main__"
        ):
            has_guard = True
            break
    assert has_guard, f"{path.name} is missing an `if __name__ == '__main__':` guard"


@pytest.mark.parametrize("path", PY_EXAMPLES, ids=lambda p: p.name)
def test_example_imports_without_side_effects(path: Path) -> None:
    """Importing an example must not prompt, hit the network, or raise.

    The if __name__ == "__main__": guard enforced by
    test_example_has_main_guard is what keeps input() /
    getpass() / network calls out of import time; this test
    verifies the guard is actually effective end-to-end.
    """
    rel = path.relative_to(EXAMPLES_DIR.parent).with_suffix("")
    module_name = "_example_" + "_".join(rel.parts)
    spec = importlib.util.spec_from_file_location(module_name, path)
    assert spec is not None, path
    assert spec.loader is not None, path

    module = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(module)
    except ModuleNotFoundError as exc:
        if exc.name in OPTIONAL_DEPS:
            pytest.skip(f"optional dependency {exc.name!r} not installed")
        raise
    finally:
        sys.modules.pop(module_name, None)


@pytest.mark.parametrize("path", PY_EXAMPLES, ids=lambda p: p.name)
def test_example_has_no_secret_literals(path: Path) -> None:
    """No obvious credential/token shapes appear in the source."""
    text = path.read_text()
    hits = [label for label, pattern in SECRET_PATTERNS if pattern.search(text)]
    assert not hits, f"{path.name} contains suspected secrets: {hits}"


def test_demo_notebook_is_clean() -> None:
    """The bundled notebook has cleared outputs and no obvious secrets."""
    notebook_path = EXAMPLES_DIR / "demo.ipynb"
    nb = json.loads(notebook_path.read_text())

    source_blob_parts: list[str] = []
    for idx, cell in enumerate(nb["cells"]):
        source_blob_parts.append("".join(cell["source"]))
        if cell["cell_type"] != "code":
            continue
        assert cell.get("execution_count") is None, (
            f"cell {idx} has a non-null execution_count; clear outputs before commit"
        )
        assert not cell.get("outputs"), (
            f"cell {idx} has captured outputs; clear outputs before commit"
        )

    source_blob = "\n".join(source_blob_parts)
    hits = [label for label, pattern in SECRET_PATTERNS if pattern.search(source_blob)]
    assert not hits, f"demo.ipynb contains suspected secrets: {hits}"
