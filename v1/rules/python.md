---
paths: ["**/*.py", "**/pyproject.toml"]
---

# Python Rules

Target Python 3.12+. Use modern syntax and tooling throughout.

## Tooling

- **Linter/Formatter:** ruff (`select = ["E", "F", "I", "B", "C4", "UP", "SIM", "PIE", "RUF", "DTZ", "PTH", "ASYNC"]` — `DTZ`/`PTH`/`ASYNC` enforce the tz-aware-datetime, pathlib, and async rules below)
- **Type checker:** mypy with `strict = true`
- **Package manager:** uv (manages packages, virtual envs, and Python versions)
- **Tests:** pytest + hypothesis (property-based) + pytest-asyncio + pytest-cov (branch coverage)
- **Logging:** structlog with JSON output
- **Config:** All tool configuration in `pyproject.toml` only. No `setup.cfg`, `tox.ini`, or `.flake8`.
  The gate runs config-backed commands; put Ruff selection, mypy strictness, warnings-as-errors,
  and coverage policy in `pyproject.toml`.

## Type Hints

Type hints required on all function signatures and module-level variables.

- Use modern syntax: `list[T]`, `dict[K, V]`, `T | None` (not `Optional[T]`)
- Use the `type` statement for type aliases: `type Vector = list[float]`
- Use `TypeIs` over `TypeGuard` for type narrowing — it narrows the `else` branch too (import
  from `typing_extensions` on 3.12): `def is_str(x: object) -> TypeIs[str]: return isinstance(x, str)`
- Use `Self` for methods that return `self`
- Use `Protocol` for structural subtyping; prefer over ABC unless sharing implementation
- Use `ParamSpec` for decorators that wrap callables
- Use `@override` on every method that overrides a parent
- Use `Final[T]` for constants

## Naming

- snake_case for functions, variables, and modules; PascalCase for classes; `UPPER_SNAKE` for
  constants; a single leading underscore for private names (Ruff's `N` rules are off by default)

## Function and Parameter Design

Prefer functions over classes unless state is needed. If a method doesn't use `self`, prefer a module-level function; use `@staticmethod` only when it must conceptually live on the class.

- Use keyword-only arguments for public functions and helpers when named arguments improve
  call-site clarity. Exceptions: `self`/`cls`, dunder methods, protocol/callback signatures,
  pytest fixture injection, framework-required signatures, and tiny private helpers where
  positional use is clearer.
- Never use mutable defaults (`list`, `dict`, `set`). Use `None` sentinel with `if arg is None: arg = []`
- Sensible immutable defaults (strings, numbers, booleans, `None`, tuples) are fine
- Return frozen dataclasses for multi-value returns, never bare tuples — return a
  `@dataclass(frozen=True)` result with named fields instead of `-> tuple[int, str]`
- `@property` for cheap computed access only — no side effects, no I/O. Never `@cache`/`@lru_cache`
  a method: it pins `self` for the process lifetime and leaks memory

## Control Flow and Idioms

- Use `is None` / `is not None` for identity; only fall back to a truthiness check when `None`
  and empty should behave identically
- Use `with` for every resource (files, locks, sessions, connections), not just files
- Never mutate a collection while iterating it; build a new one with a comprehension
- Timezone-aware datetimes always: `datetime.now(tz=UTC)`, never naive `now()`/`utcnow()`
- Comprehension over a manual append loop; switch to a generator (`yield` or `(...)`) when the
  data is large or consumed once
- `set`/`frozenset` for membership tests; `dict.get(key, default)` over `in`-then-index
- Prefer EAFP over LBYL; keep the one statement that can raise as the entire `try` body
- Watch the aliasing footgun: `[[]] * n` shares one inner list — use `[[] for _ in range(n)]`

## Project Structure

- Keep `__init__.py` files empty (they are namespace markers, not code)
- Place shared types in `types.py` modules
- Place constants in `constants.py` using `Final[T]`
- Use `pathlib.Path` over `os.path`
- Use `asyncio` over threading for concurrent I/O
- Always use top-level imports. Never import inside functions.
- Avoid `if TYPE_CHECKING:` for ordinary imports — a circular import usually means the architecture
  is wrong, so fix that first. Use it only for a genuinely unavoidable type-only cycle (or to keep a
  heavy/optional dependency out of the runtime import graph); pair it with `from __future__ import
  annotations`, since 3.12 still evaluates annotations eagerly without it
- Convert `defaultdict` to plain `dict` before returning from functions
- Executable modules define `main()` and call it under `if __name__ == "__main__":`; no work at import time
- No mutable module-level state; module-level values are `Final`
- Lift magic literals into named `Final` constants (in `constants.py`)

## Data Modeling

- Use `dataclasses` or Pydantic models for structured data
- Prefer frozen dataclasses (`frozen=True`) when mutability is not needed
- Model closed sets of values with `enum.Enum` (`StrEnum`/`IntEnum` when serialized). This
  intentionally diverges from `typescript.md`'s enum ban — Python enums carry no runtime-emit cost

## Error Handling

- Define project-specific exception hierarchies inheriting from a base project exception
- Catch the narrowest exception type; never `except Exception` unless you log and re-raise
- Re-raise with bare `raise`, never `raise e` — it preserves the original traceback
- Use built-in exceptions for precondition violations (`ValueError`, `TypeError`)
- Always chain exceptions: `raise ProjectError("msg") from original_error`
- Use `except*` and `ExceptionGroup` for concurrent error handling

## Logging

- Use structlog with JSON output to stdout
- Bind context (request ID, user ID, operation) at entry points
- Never log to files directly; let the runtime collect stdout

## Docstrings

Single sentence explaining WHY the function exists, not WHAT it does. Do not include `Args:`, `Returns:`, or `Raises:` sections -- type hints and names should be self-documenting. Only write a module-level docstring if it adds info beyond the filename. Non-obvious preconditions, error modes, and side effects belong in a prose interface comment (see `design-principles.md`), not in structured docstring sections.

## Testing

Test discipline (pytest, hypothesis, pytest-asyncio) lives in `tdd.md`. Python-specific config:
- Set `filterwarnings = ["error"]` to catch deprecation warnings (the default gate also runs
  pytest with `-W error`).
- Measure **branch** coverage, not just line coverage. Configure the package path and threshold
  in `pyproject.toml`; do not hardcode repository layout in the shared gate.
