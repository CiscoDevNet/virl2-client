# LLM Test Writing Notes

When generating/editing tests in this directory:

## File Structure

- Start every `.py` file with the full Apache 2.0 license header, then a one-line
  module docstring.
- Use `from __future__ import annotations` as the first application-level import.
- Keep module names as `test_<domain>.py`; avoid mixed catch-all files.
- Place behavior in the closest module-specific file.

## Docstrings and Types

- Use reST docstrings and explicit type annotations in tests/helpers.
  Omit `:returns: None` when the return type is `-> None`.
  Omit `:raises AssertionError:` on test functions (every test raises on failure).
- **Every LLM-generated or LLM-modified test must include** the following note in
  its docstring, on its own line after the summary:
  `NOTE: LLM-generated test -- verify for correctness.`
  Remove the note only after a human has verified the test logic.

## Test Design

- Write unit tests only; no external services or mutable environment assumptions.
- Keep test names behavior-focused; prefer short names (`<30`, hard cap `<50`).
- Each test should exercise one logical behavior; split tests with more than ~3
  arrange/act/assert cycles.
- Prefer parametrization for repeated patterns; use `pytest.param(..., id="...")`
  for readable test IDs. Avoid copy-paste duplication.
- Do not duplicate tests that already exist in a domain-specific module; search for
  existing coverage before adding a new test.

## Shared Infrastructure

- Use `make_lab()` / `make_lab_with_topology()` from `helpers.py` for lab setup.
- Use `lab._create_node_local()`, `_create_interface_local()`, `_create_link_local()`,
  `_create_annotation_local()`, `_create_smart_annotation_local()` for custom
  topologies. Prefer `make_lab_with_topology()` when the standard shape suffices.
- Use conftest fixtures: `FAKE_HOST`, `FAKE_HOST_API`, `CURRENT_VERSION`,
  `reset_env`, `client_library_server_*`, `mocked_session`, `test_data_dir`,
  `respx_mock_with_labs`, `client_library`.
- Place JSON fixtures in `test_data/`; access via the `test_data_dir` fixture.
- Assign side-effect-only fixtures to `_`: `_ = client_library_server_current`.

## Assertions and Exceptions

- Assert concrete behavior (exact calls, exact exception types/messages).
- Use `pytest.raises(ExcType, match="regex")` for exception assertions.
- Capture expected warnings with `pytest.warns` / `pytest.deprecated_call`.
- Capture log output with `caplog.at_level(...)` and assert on `caplog.text`.

## Mocking

- Do not use `@respx.mock` unless the test body configures at least one route.
- Three valid `respx` patterns: fixture (`respx_mock: MockRouter`), decorator
  (`@respx.mock`), or context manager (`with respx.mock(...)`).
- Patch at the import site, not the definition site
  (e.g. `patch("virl2_client.models.node.time.sleep")`, not `patch("time.sleep")`).
- Use `patch.object(Cls, "attr")` as a context manager; never assign directly
  (e.g. `Lab.sync = Mock()`) without cleanup.
- `assert_called_once_with(...)` already verifies call count — do not follow it with a
  redundant `assert_called_once()`.
- Extract module-local helpers (`_make_node()`, `_new_event()`) for repeated setup;
  promote to `helpers.py`/`conftest.py` only when shared across modules.

## Environment and Imports

- Never place `import` statements inside test function or fixture bodies; put them at
  module level.
- Fixtures must not call `os.chdir` or directly mutate `os.environ`; use
  `monkeypatch.chdir` / `monkeypatch.setenv` instead so teardown is guaranteed.
- For flaky paths (time/async/threading), patch clocks/sleeps and use controlled mocks.

## Optional Dependencies

- Gate modules requiring optional packages with `pytest.importorskip("pkg")` at
  module level.

## Coverage

- Keep coverage complete for touched branches and verify with:
  - `pytest -n auto --cov=virl2_client --cov-report=term-missing`

## File Placement

Place new tests in the closest domain-specific `test_<domain>.py` file.
The `_runtime` suffix marks runtime/integration-level tests for the same domain.
See [Test Module Reference](README.md#test-module-reference) for the full
module-to-scope mapping.

> For full explanations and examples, see [README.md](README.md).
