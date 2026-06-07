---
paths: "**/*.py", "**/pyproject.toml"
---

# Python Rules

Target Python 3.12+. Use modern syntax and tooling throughout.

## Tooling

- **Linter/Formatter:** ruff (`select = ["E", "F", "I", "B", "C4", "UP", "SIM", "PIE", "RUF"]`)
- **Type checker:** mypy with `strict = true`
- **Package manager:** uv (manages packages, virtual envs, and Python versions)
- **Tests:** pytest + hypothesis (property-based) + pytest-asyncio
- **Logging:** structlog with JSON output
- **Config:** All tool configuration in `pyproject.toml` only. No `setup.cfg`, `tox.ini`, or `.flake8`.

## Type Hints

Type hints required on all function signatures and on **every variable binding** —
module-level, class-level, and **local** — wherever the syntax allows an annotation. Annotate
each `x = ...` assignment, including locals inside functions (this also pins the `Any` that
`json.loads`/`re`/external calls leak, forcing a deliberate narrowing). The only exempt targets
are those that *cannot* carry an annotation — `for`/comprehension loop variables, walrus (`:=`)
targets, exception-handler (`except … as`) bindings, and tuple-unpacking targets; split a tuple
unpack into single annotated assignments when the types matter.

- Use modern syntax: `list[T]`, `dict[K, V]`, `T | None` (not `Optional[T]`)
- Use the `type` statement for type aliases: `type Vector = list[float]`
- Use `TypeIs` over `TypeGuard` for type narrowing (import from `typing_extensions` on Python 3.12)
- Use `Self` for methods that return `self`
- Use `Protocol` for structural subtyping; prefer over ABC unless sharing implementation
- Use `ParamSpec` for decorators that wrap callables
- Use `@override` on every method that overrides a parent
- Use `Final[T]` for constants

## Function and Parameter Design

Prefer functions over classes unless state is needed. If a method doesn't use `self`, make it a `@staticmethod`.

- Always use keyword-only args (`*` as first param) for all functions
- Never use mutable defaults (`list`, `dict`, `set`). Use `None` sentinel with `if arg is None: arg = []`
- Sensible immutable defaults (strings, numbers, booleans, `None`, tuples) are fine
- Return frozen dataclasses for multi-value returns (never bare tuples)

## Project Structure

- Keep `__init__.py` files empty (they are namespace markers, not code)
- Place shared types in `types.py` modules
- Place constants in `constants.py` using `Final[T]`
- Use `pathlib.Path` over `os.path`
- Use `asyncio` over threading for concurrent I/O
- Always use top-level imports. Never import inside functions.
- Never use `if TYPE_CHECKING:` — if it causes a circular import, fix the architecture
- Convert `defaultdict` to plain `dict` before returning from functions

## Data Modeling

- Use `dataclasses` or Pydantic models for structured data
- Prefer frozen dataclasses (`frozen=True`) when mutability is not needed

## Error Handling

- Define project-specific exception hierarchies inheriting from a base project exception
- Always chain exceptions: `raise ProjectError("msg") from original_error`
- Use `except*` and `ExceptionGroup` for concurrent error handling

## Logging

- Use structlog with JSON output to stdout
- Bind context (request ID, user ID, operation) at entry points
- Never log to files directly; let the runtime collect stdout

## Docstrings

Single sentence explaining WHY the function exists, not WHAT it does. Do not include `Args:`, `Returns:`, or `Raises:` sections -- type hints and names should be self-documenting. Only write a module-level docstring if it adds info beyond the filename.

## Testing

- Use pytest with fixtures for setup/teardown
- Use hypothesis for property-based testing of pure functions
- Use pytest-asyncio for async test functions
- Set `filterwarnings = ["error"]` in pytest config to catch deprecation warnings
- Measure branch coverage as a **diagnostic** to find untested paths — never as a gate target. Do not set a `--cov-fail-under` mandate; a coverage number counts lines touched, not behavior asserted, and a 100% target just manufactures tests that color branches green
- Write the **fewest** tests that pin the behavior; never add a test solely to cover a line, and never test a dormant or unreachable path
