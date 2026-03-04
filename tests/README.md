# Test Authoring Guide

Unit tests in this project should be deterministic, explicit, and domain-scoped.
This document explains the *why* behind each rule and documents the shared test
infrastructure.  For a terse checklist aimed at code generators see
[AGENTS.md](AGENTS.md).

---

## Shared Test Infrastructure (`helpers.py`)

The following helpers live in `helpers.py` and should be imported directly
rather than re-implemented per module.

### `make_lab(session=None, wait=False, resource_pool_manager=None) -> Lab`

Creates a `Lab` backed by a fresh `MagicMock` session (or a caller-supplied
one) and the shared `RESOURCE_POOL_MANAGER`.  Use this instead of writing an
inline `Lab(...)` constructor whenever the test does not need to assert on a
specific lab id or title — it prevents the drift that caused subtle URL
assertion failures in the past when different modules used different dummy ids.

```python
# preferred
lab = make_lab()
lab_with_session = make_lab(session=my_session)
lab_with_custom_rpm = make_lab(resource_pool_manager=Mock())
```

Tests that **must** use a specific lab id (e.g., they assert on URL paths such
as `labs/1/nodes/...`) should still construct `Lab(...)` inline; import
`RESOURCE_POOL_MANAGER` from `helpers` for the constructor argument.

### `make_lab_with_topology(session=None) -> Topology`

Creates a lab with two nodes connected by a single link
(`node_a(eth0) --link-- node_b(eth0)`).  Returns a `Topology` named tuple
with `lab`, `nodes`, `interfaces`, and `link` fields.  This covers the most
common test-setup pattern and avoids duplicating the same boilerplate across
domain files.

```python
topo = make_lab_with_topology()
topo.lab, topo.nodes, topo.interfaces, topo.link
```

### `RESOURCE_POOL_MANAGER: Mock`

A module-level `Mock()` shared across the suite.  Pass it as the
`resource_pool_manager=` argument when constructing `Lab` objects inline.
Tests that need to assert on calls to the resource-pool manager should pass
their own `Mock()` to `make_lab(resource_pool_manager=...)` so the shared
instance is not polluted.

---

## Core Rules

- Use `pytest` for all tests and keep tests unit-level (no real network/services).
- Use reST docstrings in tests and helpers (`:param`, `:returns`, `:raises`).
  Omit `:returns: None` when the function return type is annotated as `-> None`
  (the annotation is sufficient).  Similarly, omit `:raises AssertionError:` on
  test functions — every test implicitly raises on failure, so the tag adds
  noise without information.
- Add type annotations for helpers, fixtures, and test function signatures.
- Capture expected warnings explicitly with `pytest.warns(...)` or
  `pytest.deprecated_call(...)`.
- Prefer parametrization when scenarios share the same shape.

## LLM-Generated Tests

Tests written or substantially modified by an LLM **must** include the following
note in their docstring, on its own line after the summary:

```
NOTE: LLM-generated test -- verify for correctness.
```

This signals to reviewers that the test should be inspected for correctness
rather than trusted at face value.  Remove the note only after a human has
verified the test logic.

## Naming and Layout

- Use module names in the form `test_<domain>.py`.
- Keep tests in the closest domain file (do not keep mixed "misc/additional" buckets).
- Do not use `_feature` or `_optional` suffixes in filenames.
- Add a one-line module docstring to every test file even when a licence header is
  present (static analysis and LLMs use it to understand file purpose).
- Keep test names concise and behavior-oriented:
  - prefer `< 30` chars when clear,
  - hard cap `< 50` chars.
- Each test should exercise one logical behavior.  If a test has more than
  roughly three arrange/act/assert cycles, split it into focused tests.
- Use full names in test code for clarity: `interface` (not `iface`),
  `annotation` (not `ann`), `smart_annotation` (not `smart` or `smart_ann`).
  The production code uses `iface` in some places but tests should prefer
  the unabbreviated form for readability.

## No Duplicate Tests

Before adding a new test, search for existing coverage.  A test that merely
re-exercises an already-covered path adds maintenance cost without coverage
benefit.  If the same setup is needed in multiple domain files, extract a shared
fixture or helper in `conftest.py`; do not copy test bodies across modules.

## Fixture Hygiene and Environment Safety

Never mutate global or process state directly in a fixture body.  Two common
mistakes and their fixes:

| Wrong | Why it breaks | Fix |
|-------|--------------|-----|
| `os.chdir(...)` | working directory is not restored on failure | `monkeypatch.chdir(...)` |
| `os.environ[key] = value` | env leaks into subsequent tests | `monkeypatch.setenv(key, value)` |

Do not place `import` statements inside test function or fixture bodies.
Module-level imports let static analysis tools (mypy, ruff) see the dependency
and make the file easier to scan.

## Mock and Decorator Hygiene

- Do not apply `@respx.mock` (or any mock-router decorator) unless the test body
  actually registers at least one route on it.  A stray decorator looks like
  there is network isolation when there is none.
- Do not patch class attributes directly without cleanup (e.g. `Lab.sync = Mock()`).
  Use `patch.object(Lab, "sync")` as a context manager so the original is
  restored automatically; unrestored patches bleed into later tests.
- `assert_called_once_with(...)` already verifies call count — do not follow it
  with a redundant `assert_called_once()`.

## Determinism and Stability

- Patch time/sleep in polling or stale-check paths (`time.time`, `time.sleep`).
- For async/threaded code, test with controlled mocks and explicit stop conditions.
- Avoid broad exception swallowing; assert concrete exception types/messages.

## Coverage and Validation

- Add direct tests for every new/changed branch.
- For optional dependency paths, use explicit dependency gating and isolated mocks.
- Run in parallel by default:
  - `pytest -n auto --cov=virl2_client --cov-report=term-missing`
