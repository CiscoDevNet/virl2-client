# LLM Test Writing Notes

When generating/editing tests in this directory:

- Write unit tests only; no external services or mutable environment assumptions.
- Keep module names as `test_<domain>.py`; avoid mixed catch-all files.
- Place behavior in the closest module-specific file.
- Add a one-line module docstring to every test file even when a licence header is present.
- Use reST docstrings and explicit type annotations in tests/helpers.
  Omit `:returns: None` when the return type is `-> None`.
  Omit `:raises AssertionError:` on test functions (every test raises on failure).
- **Every LLM-generated or LLM-modified test must include** the following note in
  its docstring, on its own line after the summary:
  `NOTE: LLM-generated test -- verify for correctness.`
  Remove the note only after a human has verified the test logic.
- Keep test names behavior-focused; prefer short names (`<30`, hard cap `<50`).
- Each test should exercise one logical behavior; split tests with more than ~3
  arrange/act/assert cycles.
- Capture expected warnings explicitly (`pytest.warns` / `pytest.deprecated_call`).
- Prefer parametrization for repeated patterns; avoid copy-paste duplication.
- Do not duplicate tests that already exist in a domain-specific module; search for
  existing coverage before adding a new test.
- Never place `import` statements inside test function or fixture bodies; put them at
  module level.
- Do not use mocking decorators (e.g. `@respx.mock`) unless the test body configures
  at least one route; unused decorators are noise.
- `assert_called_once_with(...)` already verifies call count — do not follow it with a
  redundant `assert_called_once()`.
- Fixtures must not call `os.chdir` or directly mutate `os.environ`; use
  `monkeypatch.chdir` / `monkeypatch.setenv` instead so teardown is guaranteed.
- For flaky paths (time/async/threading), patch clocks/sleeps and use controlled mocks.
- Assert concrete behavior (exact calls, exact exception types/messages).
- Keep coverage complete for touched branches and verify with:
  - `pytest -n auto --cov=virl2_client --cov-report=term-missing`

> For full explanations and examples, see [README.md](README.md).
