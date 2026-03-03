---
name: python-coding-rules
description: Use when writing, editing, or reviewing Python code. Apply to all Python files, modules, and projects targeting Python 3.12+.
---

# Python Coding Rules (Python 3.12+)

These rules apply to all Python code. Follow them for every file you write or modify.

## Validation Checklist

Before outputting Python code, verify each item:

- [ ] Every function/method has typed parameters and return type
- [ ] Every variable has a type annotation at first assignment
- [ ] Constants are `Final[T]` and live in `constants.py`
- [ ] Types/enums/dataclasses live in `types.py`
- [ ] `__init__.py` files are empty
- [ ] No in-function imports, no `if TYPE_CHECKING:` guards
- [ ] No bare tuples for multi-value returns (use frozen dataclass)
- [ ] Stateless methods are `@staticmethod`
- [ ] `defaultdict` results converted to `dict` before returning
- [ ] Classes used only when stateful — prefer functions otherwise
- [ ] Using modern type syntax: `list[T]` not `List[T]`, `T | None` not `Optional[T]`
- [ ] All functions use keyword-only args (`*` as first param)
- [ ] No mutable default parameter values — use `None` sentinel
- [ ] Module docstrings only if they add info beyond the filename
- [ ] Docstrings are one sentence explaining WHY — no Args/Returns sections

## 1. Type Hints — Required Everywhere

Every function signature, method, and variable where the type is not obvious must have type annotations.

```python
def get_user(user_id: int) -> User | None: ...
```

Use modern built-in generics — no `typing.List`, `typing.Dict`, `typing.Optional`:

```python
# Yes
items: list[str]
mapping: dict[str, int]
value: str | None

# No
from typing import List, Dict, Optional
items: List[str]
mapping: Dict[str, int]
value: Optional[str]
```

Use the `type` statement for type aliases (Python 3.12+):

```python
type UserID = int
type Response = dict[str, Any]
```

### Modern Typing Additions

- **`TypeIs` over `TypeGuard`** — `TypeIs` (from `typing_extensions` on 3.12, stdlib in 3.13) narrows in both branches. Prefer it over `TypeGuard` unless you need asymmetric narrowing.
- **`Self`** — use `Self` for methods that return the instance type:
  ```python
  from typing import Self

  class Builder:
      def with_name(self, name: str) -> Self:
          self.name = name
          return self
  ```
- **`ParamSpec`** — use for decorators that preserve the wrapped function's signature:
  ```python
  from typing import ParamSpec, TypeVar

  P = ParamSpec("P")
  R = TypeVar("R")

  def retry(fn: Callable[P, R]) -> Callable[P, R]: ...
  ```
- **`@override`** — mark all overriding methods explicitly:
  ```python
  from typing import override

  class Child(Parent):
      @override
      def process(self) -> None: ...
  ```

## 2. Interfaces — Protocol Over ABC

Prefer `Protocol` for interfaces (structural subtyping) unless you need to share implementation via ABC.

```python
from typing import Protocol

class Repository(Protocol):
    def get(self, id: int) -> Model: ...
    def save(self, model: Model) -> None: ...
```

`Protocol` enables structural subtyping — implementors do not need to inherit. Use ABC only when sharing concrete method implementations across subclasses.

## 3. File Structure

Every Python package follows this structure:

| File | Contents |
|------|----------|
| `__init__.py` | Empty. Never put code here. |
| `types.py` | All custom types, TypedDicts, Enums, Protocols |
| `constants.py` | All constants using `Final[T]` |
| `exceptions.py` | Project exception hierarchy |
| Module files | One responsibility per file |

```python
# constants.py
from typing import Final

MAX_RETRIES: Final[int] = 3
DEFAULT_TIMEOUT: Final[float] = 30.0
API_VERSION: Final[str] = "v2"
```

## 4. Functions Over Classes

Use plain functions for stateless logic. Classes are for state or lifecycle management. If a method doesn't use `self`, make it a `@staticmethod`.

```python
# Yes — stateless, use a function
def calculate_score(data: list[float]) -> float: ...

# Yes — has state, use a class
class ConnectionPool:
    def __init__(self, max_size: int) -> None:
        self._connections: list[Connection] = []
        self._max_size = max_size

    @staticmethod
    def validate_config(config: dict[str, Any]) -> bool:
        return "host" in config
```

## 5. Dataclasses for Structured Data

Use `dataclasses` or Pydantic for all structured data. Use frozen dataclasses for immutable value objects and multi-value returns.

```python
from dataclasses import dataclass

@dataclass(frozen=True)
class SearchResult:
    items: tuple[Item, ...]
    total_count: int
    page: int
```

Use Pydantic for data that crosses trust boundaries (API input, config files, external data).

## 6. Imports

Always use **top-level imports**. Never import inside functions — it hides circular dependencies.

**Never use `if TYPE_CHECKING:`** — always import directly at the top level. If a type-only import causes a circular dependency, fix the architecture (split files).

## 7. Async by Default

Use `asyncio` for I/O-bound work. Never use threads for I/O.

```python
async def fetch_user(client: HttpClient, user_id: int) -> User: ...
```

## 8. defaultdict Pattern

Use `defaultdict` for aggregation. Convert to plain `dict` before returning.

```python
from collections import defaultdict

def count_items(items: list[str]) -> dict[str, int]:
    result: defaultdict[str, int] = defaultdict(int)
    for item in items:
        result[item] += 1
    return dict(result)
```

## 9. Parameters — Safe Defaults

Never use mutable defaults (lists, dicts, sets). Use `None` sentinel for optional mutable params. Allow sensible immutable defaults (bool, int, str, tuples).

```python
# Yes — immutable defaults are fine
def connect(host: str, port: int = 5432, use_ssl: bool = True) -> Connection: ...

# Yes — None sentinel for mutable default
def process(items: list[str] | None = None) -> list[str]:
    items = items if items is not None else []
    return items

# No — mutable default
def process(items: list[str] = []) -> list[str]: ...
```

## 10. Keyword-Only Arguments

Always use keyword-only args (`*` as first param) for all functions. No runtime overhead — CPython stores this as a simple integer in the code object. Benefits: prevents argument-order bugs, makes APIs evolvable, and self-documents call sites.

```python
# All functions use keyword-only args
def get_user(*, user_id: int, include_deleted: bool = False) -> User: ...

def create_user(*, name: str, email: str, role: str = "viewer") -> User: ...
```

## 11. Docstrings — Explain Why

Single sentence explaining WHY the function exists, not what it does (the signature shows that). No `Args:` / `Returns:` sections — type hints serve that purpose.

```python
def calculate_priority(task: Task) -> int:
    """Business rule: overdue tasks get 2x priority boost."""
    ...
```

Only write a module-level docstring if it communicates something the filename does not. Never restate the filename:

```python
# WRONG — constants.py doesn't need to say it contains constants
"""Constants for the translation module."""

# CORRECT — omit entirely, or write only if non-obvious
"""Retry budget and model selection defaults shared across translation entrypoints."""
```

## 12. Code Health and Tooling

### Formatter and Linter — ruff

Use ruff for both formatting and linting. Recommended rule set:

```toml
[tool.ruff.lint]
select = ["E", "F", "I", "B", "C4", "UP", "SIM", "PIE", "RUF"]
```

Covers: pycodestyle, pyflakes, isort, bugbear, comprehensions, pyupgrade, simplify, pie, ruff-native.

### Type Checker — mypy or pyright

Run mypy with `strict = true` or pyright strict mode. Run in CI on every commit.

### Package Management — uv

Use uv for package management, virtual environments, and Python version management.

### Logging — structlog

Use structlog with JSON output for structured logging. Log to stdout. Bind context at entry points.

```python
import structlog

logger = structlog.get_logger()

def process_order(order_id: str) -> None:
    log = logger.bind(order_id=order_id)
    log.info("processing_order")
```

### Testing — pytest

- **pytest** as the test framework with fixtures for setup
- **hypothesis** for property-based testing
- **pytest-asyncio** for async test functions
- **`filterwarnings = ["error"]`** in pytest config — treat warnings as errors
- **Branch coverage** — measure and enforce branch coverage, not just line coverage

### Configuration — pyproject.toml

All tool config in `pyproject.toml`. No `setup.cfg`, `tox.ini`, or `.flake8`.

### pathlib Over os.path

```python
from pathlib import Path

config_path = Path("config") / "settings.toml"
```

## 13. Error Handling

Define project exception hierarchies. All custom exceptions inherit from a single project base.

```python
class AppError(Exception):
    """Base exception for this project."""

class NotFoundError(AppError): ...
class ValidationError(AppError): ...
```

Chain exceptions with `raise X from Y` — never swallow the original cause:

```python
try:
    result = parse_config(raw)
except json.JSONDecodeError as e:
    raise ConfigError(f"Invalid config format: {path}") from e
```

Use `except*` / `ExceptionGroup` for concurrent errors (Python 3.11+):

```python
try:
    async with asyncio.TaskGroup() as tg:
        tg.create_task(fetch_users())
        tg.create_task(fetch_orders())
except* ConnectionError as eg:
    for exc in eg.exceptions:
        logger.error("connection_failed", error=str(exc))
```

## 14. Testing

Write tests for all business logic. Follow the Arrange-Act-Assert pattern.

```python
def test_priority_boost_for_overdue_tasks() -> None:
    # Arrange
    task = Task(due_date=date(2024, 1, 1), base_priority=5)

    # Act
    priority = calculate_priority(task)

    # Assert
    assert priority == 10
```

Use hypothesis for property-based testing to catch edge cases:

```python
from hypothesis import given, strategies as st

@given(st.lists(st.integers()))
def test_sort_is_idempotent(items: list[int]) -> None:
    assert sorted(sorted(items)) == sorted(items)
```

Use pytest-asyncio for async tests:

```python
import pytest

@pytest.mark.asyncio
async def test_fetch_user() -> None:
    user = await fetch_user(client, user_id=1)
    assert user.name == "Alice"
```
