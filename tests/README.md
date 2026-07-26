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

### Shared Fixtures and Constants (`conftest.py`)

`conftest.py` provides session-scoped and function-scoped fixtures available to
every test module.

| Name | Kind | Description |
|------|------|-------------|
| `FAKE_HOST` | constant | `"https://0.0.0.0"` — base URL for mocked controllers |
| `FAKE_HOST_API` | constant | `"https://0.0.0.0/api/v0/"` — base API endpoint |
| `CURRENT_VERSION` | constant | The `ClientLibrary.VERSION` string at import time |
| `reset_env` | fixture | Clears all `VIRL2_*` / `VIRL_*` env vars via `monkeypatch` |
| `client_library_server_current` | fixture | Patches `system_info` to return the current CML version |
| `client_library_server_2_0_0` | fixture | Patches `system_info` to return CML 2.0.0 |
| `client_library_server_2_9_0` | fixture | Patches `system_info` to return CML 2.9.0 |
| `client_library_server_2_19_0` | fixture | Patches `system_info` to return CML 2.19.0 |
| `mocked_session` | fixture | Patches `authentication.CustomClient` for tests needing a mock HTTP session |
| `test_data_dir` | fixture (session) | `Path` to the `test_data/` directory |
| `respx_mock_with_labs` | fixture | Pre-configures `respx` routes for lab listing and topology |
| `client_library` | fixture | A fully constructed `ClientLibrary` backed by `respx_mock_with_labs` |

Import constants directly when needed; fixtures are auto-discovered by pytest.
When a fixture is consumed only for its side-effects (e.g. `client_library_server_current`),
assign it to `_` to silence linter warnings:

```python
def test_something(client_library_server_current: MagicMock) -> None:
    _ = client_library_server_current
    ...
```

### Test Data Directory (`test_data/`)

The `test_data/` directory holds JSON fixtures and binary test assets.  Files
are accessed via the `test_data_dir` session fixture.

| Pattern | Purpose |
|---------|---------|
| `labs.json` | Lab listing payload |
| `populate_lab_tiles.json` | Lab tile/thumbnail payload |
| `topology-{lab_id}.json` | Per-lab topology snapshot |
| `simulation_stats-{lab_id}.json` | Per-lab simulation statistics |
| `layer3_addresses-{lab_id}.json` | Per-lab L3 address data |
| `sample_topology.json` | Standalone topology for import tests |
| `*.qcow`, `*.qcow2`, etc. | Stub image files for upload validation |

The `resp_body_from_file` helper in `conftest.py` maps `respx` request paths
to the corresponding JSON file automatically.  Add new fixture files here
instead of inlining large JSON blobs in test code.

---

## Core Rules

- Use `pytest` for all tests and keep tests unit-level (no real network/services).
- Start every `.py` file with the full Apache 2.0 license header (copyright +
  license text), followed by a one-line module docstring.
- Use `from __future__ import annotations` as the first application-level
  import in every test file.  This enables PEP 604 union syntax (`X | Y`)
  and deferred evaluation of type hints.
- Use reST docstrings in tests and helpers (`:param`, `:returns`, `:raises`).
  Omit `:returns: None` when the function return type is annotated as `-> None`
  (the annotation is sufficient).  Similarly, omit `:raises AssertionError:` on
  test functions — every test implicitly raises on failure, so the tag adds
  noise without information.
- Add type annotations for helpers, fixtures, and test function signatures.
- Capture expected warnings explicitly with `pytest.warns(...)` or
  `pytest.deprecated_call(...)`.
- Capture expected log output with `caplog`:
  ```python
  with caplog.at_level(logging.WARNING):
      do_something()
  assert "expected message" in caplog.text
  ```
- Prefer parametrization when scenarios share the same shape.  Use
  `pytest.param(..., id="descriptive-name")` or the `ids=` argument for
  readable test IDs in parametrized tests.

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

## Inline Topology Creation

When a test needs nodes, interfaces, or links but does not need a full `respx`
session, use the `Lab._create_*_local` family to build elements in-memory:

```python
lab = make_lab()
node = lab._create_node_local("n1", "n1", "iosv")
iface = lab._create_interface_local("i1", "eth0", node, 0)
link = lab._create_link_local(iface_a, iface_b, "l1")
annotation = lab._create_annotation_local("a1", "rectangle")
smart = lab._create_smart_annotation_local("sa1", tag="node_a")
```

Prefer `make_lab_with_topology()` from `helpers.py` when the standard
two-node-one-link shape is sufficient; use `_create_*_local` only when
the test requires a custom topology.

## Exception Assertions

Use `pytest.raises` with `match=` for message verification:

```python
with pytest.raises(NodeNotFound, match="node not in lab"):
    lab.get_node_by_id("missing")
```

When the exception object needs further inspection, combine `as` with
`match`:

```python
with pytest.raises(APIError, match="auth failed") as exc_info:
    client.authenticate()
assert exc_info.value.status == 403
```

## Optional Dependency Gating

Some modules (e.g. `event_listening`, `pyATS`) require optional packages.
Gate the entire test module with `pytest.importorskip` at the top:

```python
aiohttp = pytest.importorskip("aiohttp")
```

If the dependency is not importable the module is skipped with a clear
message.  Do not use bare `try/except ImportError` for this purpose.

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
- **Patch at the import site**, not the definition site.  Python's `patch`
  replaces the name in the namespace where it was imported, so
  `patch("virl2_client.models.node.time.sleep")` is correct when `node.py`
  does `import time`; `patch("time.sleep")` would miss the reference.
- **`respx` patterns** — three valid ways, choose by scope:
  - *Fixture*: accept `respx_mock: MockRouter`, configure routes, call
    `respx_mock.assert_all_called()` at the end.
  - *Decorator*: apply `@respx.mock` and configure routes in the body.
  - *Context manager*: `with respx.mock(base_url=...) as respx_mock:`.
- **Module-local helpers** — when several tests in one file share setup logic,
  extract a private helper (e.g. `_make_node()`, `_new_event()`).  Move to
  `helpers.py` or `conftest.py` only when the helper is needed across modules.

## Determinism and Stability

- Patch time/sleep in polling or stale-check paths (`time.time`, `time.sleep`).
- For async/threaded code, test with controlled mocks and explicit stop conditions.
- Avoid broad exception swallowing; assert concrete exception types/messages.

## Test Module Reference

The `_runtime` suffix denotes a file that tests runtime/integration-level
behaviour of the same domain as the base file (e.g. `test_system_runtime.py`
complements `test_system.py`).

### ClientLibrary

| Module | Scope |
|--------|-------|
| `test_client_init.py` | Constructor, URL parsing, and repr |
| `test_client_library.py` | Authentication, lab management, and diagnostics |
| `test_client_library_labs.py` | Lab operations (join, list, find, import) |
| `test_client_library_runtime.py` | Runtime branches: readiness, events, and lab management |
| `test_configuration.py` | Configuration, SSL options, and credential loading |
| `test_version.py` | Version class: comparisons, parsing, and diff helpers |

### Lab

| Module | Scope |
|--------|-------|
| `test_labs.py` | Lab properties and core lightweight behaviours |
| `test_lab_lifecycle.py` | Lifecycle, element removal, and convergence |
| `test_lab_sync.py` | Topology sync, import handlers, and L3 address sync |
| `test_lab_topology_and_runtime.py` | Sync/associations, topology and management helpers |

### Topology Elements

| Module | Scope |
|--------|-------|
| `test_annotations.py` | Annotation subclasses (rectangle, ellipse, line, text) and server sync |
| `test_smart_annotations.py` | SmartAnnotation properties, server sync, and identity helpers |
| `test_interfaces.py` | Interface operations and properties |
| `test_links.py` | Link creation paths |
| `test_link_runtime.py` | Link runtime: properties, conditions, and packet capture APIs |
| `test_nodes.py` | Node behaviours and properties |
| `test_node_staging.py` | Lab node staging and node priority |
| `test_pcap.py` | Link packet-capture API (start, stop, status, download, packets) |
| `test_wireless_pcap.py` | Wireless node packet-capture API (start, stop, status, download) |

### Authentication and Users

| Module | Scope |
|--------|-------|
| `test_authentication.py` | Authentication helpers and auth objects |
| `test_auth_management.py` | AuthManagement, LDAPManager, and RADIUSManager settings and auth flows |
| `test_user_group_management.py` | User and group CRUD, associations, and ID lookups |

### System

| Module | Scope |
|--------|-------|
| `test_system.py` | SystemManagement, ComputeHost, and SystemNotice mutations and syncs |
| `test_system_runtime.py` | SystemManagement runtime: compute hosts, connectors, timeout, telemetry |
| `test_system_lab_repositories.py` | LabRepository, LabRepositoryManagement, and system lab repository workflows |

### Other Models

| Module | Scope |
|--------|-------|
| `test_licensing.py` | Licensing API wrappers |
| `test_node_image_definitions.py` | NodeImageDefinitions CRUD, upload validation, image file handling, and definitions |
| `test_pyats.py` | pyATS integration: ClPyats model and node credential handling |
| `test_resource_pool.py` | ResourcePool property setters, usage payloads, and sync |
| `test_resource_pool_management.py` | ResourcePoolManagement synchronisation and resource pool creation |

### Utilities and Optional Dependencies

| Module | Scope |
|--------|-------|
| `test_autostart.py` | Lab autostart configuration |
| `test_deprecated_alias_modules.py` | Deprecated alias modules and emitted warning categories |
| `test_event_handling.py` | Optional event-handling module |
| `test_event_listening.py` | Optional websocket event listener |
| `test_utils_stale.py` | Stale-checking utilities and related helpers |

## Coverage and Validation

- Add direct tests for every new/changed branch.
- For optional dependency paths, use explicit dependency gating and isolated mocks.
- Run in parallel by default:
  - `pytest -n auto --cov=virl2_client --cov-report=term-missing`
