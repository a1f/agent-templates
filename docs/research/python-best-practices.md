# Research: Python Best Practices (2025-2026)

## Target: Python 3.12+

Python 3.12 provides: `type` statement for aliases, new generics syntax, `@override` decorator.
Python 3.13 adds: `TypeIs`, type parameter defaults (available via `typing_extensions` for 3.12).

## Tooling Decisions

| Tool | Choice | Rationale |
|------|--------|-----------|
| Linter/Formatter | **ruff** | Industry standard. Used by FastAPI, Pydantic, httpx. 10-100x faster. |
| Type checker | **mypy strict** (or pyright) | Every major project uses one. ty (from Astral) is emerging but beta. |
| Package manager | **uv** | From Astral (ruff team). 10-100x faster than pip. Manages Python versions too. |
| Test framework | **pytest** | Universal. Add hypothesis for property-based, pytest-asyncio for async. |
| Logging | **structlog** | Structured JSON output, context binding, integrates with stdlib logging. |

### Recommended ruff rule set
```toml
[tool.ruff.lint]
select = ["E", "F", "I", "B", "C4", "UP", "SIM", "PIE", "RUF"]
```
Covers: pycodestyle, pyflakes, isort, bugbear, comprehensions, pyupgrade, simplify, pie, ruff-native.

## Rules: What Changed from Original Design

### KEEP (validated):
- Type hints required everywhere
- ruff for linting/formatting
- pytest with fixtures
- pathlib over os.path
- dataclasses/pydantic for structured data
- asyncio over threading
- keyword-only params (for >2-3 args)
- Modern type syntax (`list[T]`, `T | None`)
- `Final[T]` for constants
- Frozen dataclasses for multi-value returns

### CHANGED:
- ~~No default parameter values~~ → **Never use mutable defaults; use `None` sentinel for optional params**
  - No major project bans defaults. FastAPI, Pydantic, httpx all use them extensively.

### ADDED:
1. **Type checker**: mypy with `strict = true` or pyright strict mode. Run in CI.
2. **Package management**: uv for packages, virtual envs, Python version management.
3. **Structured logging**: structlog with JSON output. Log to stdout. Bind context at entry points.
4. **Error handling**: Project exception hierarchies. `raise X from Y`. `except*`/`ExceptionGroup` for concurrent errors.
5. **Protocol over ABC**: Prefer `Protocol` (structural subtyping) unless sharing implementation via ABC.
6. **Modern typing**: `TypeIs` over `TypeGuard`, `type` statement for aliases, `Self` for return-self, `ParamSpec` for decorators, `@override` on overriding methods.
7. **Testing**: hypothesis for property-based, pytest-asyncio for async, `filterwarnings = ["error"]`, branch coverage.
8. **Single config**: All tool config in `pyproject.toml` — no `setup.cfg`, `tox.ini`, `.flake8`.

## What Major Projects Use

| Project | Linter | Type checker | Line length | Ruff rules |
|---------|--------|-------------|-------------|-----------|
| FastAPI | ruff | mypy strict | 88 | E,W,F,I,B,C4,UP |
| Pydantic | ruff | pyright | 120 | F,E,I,D,UP,YTT,B,C4,PERF,PIE |
| httpx | ruff | mypy strict | 88 | E,F,I,B,PIE |
| Ruff | ruff | mypy | 88 | E,F,B,C4,SIM,I,UP,PIE,PGH,PYI,RUF |

## Sources

- [Ruff docs](https://docs.astral.sh/ruff/) | [uv docs](https://docs.astral.sh/uv/)
- [ty announcement](https://astral.sh/blog/ty) | [Pyrefly from Meta](https://engineering.fb.com/2025/05/15/developer-tools/introducing-pyrefly/)
- [PEP 742 - TypeIs](https://peps.python.org/pep-0742/) | [Python typing best practices](https://typing.python.org/en/latest/reference/best_practices.html)
- [PEP 654 - Exception Groups](https://peps.python.org/pep-0654/)
- [structlog docs](https://www.structlog.org/en/stable/why.html)
