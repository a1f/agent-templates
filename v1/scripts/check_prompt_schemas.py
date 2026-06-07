#!/usr/bin/env python3
"""Anti-drift check: each agent prompt's example return matches its schema.

Every v1 agent prompt ends with a ```json return block. This validates that block
against its schema in v1/schemas/ (via validate_return, as the architect does on real
returns) and flags any omitted field, so a prompt edit can't reshape it silently.
Run via uv:
    uv run --no-project --with jsonschema python check_prompt_schemas.py
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any, Final

from validate_return import errors_against

_V1: Final[Path] = Path(__file__).resolve().parent.parent
_AGENTS: Final[Path] = _V1 / "agents"
_SCHEMAS: Final[Path] = _V1 / "schemas"
_JSON_BLOCK: Final[re.Pattern[str]] = re.compile(r"```json\n(.*?)\n```", re.DOTALL)


def drift(*, prompt: Path) -> list[str]:
    """How a prompt's example diverges from its role's schema (empty = in sync)."""
    blocks: list[str] = _JSON_BLOCK.findall(prompt.read_text())
    if not blocks:
        return ["no ```json block found"]
    example: object = json.loads(blocks[-1])
    if not isinstance(example, dict):
        return ["last ```json block is not a JSON object"]
    role: object = example.get("role")
    schema_path: Path = _SCHEMAS / f"{role}.schema.json"
    if not schema_path.exists():
        return [f"role {role!r} has no schema in {_SCHEMAS.name}/"]
    errors: list[str] = errors_against(instance=example, schema_path=schema_path)
    schema: dict[str, Any] = json.loads(schema_path.read_text())
    properties: dict[str, Any] = schema.get("properties", {})
    omitted: list[str] = sorted(properties.keys() - example.keys())
    return errors + [f"example omits schema field {field!r}" for field in omitted]


def _report(*, prompt: Path) -> bool:
    """Print one prompt's verdict line(s); True if it drifted from its schema."""
    try:
        errors: list[str] = drift(prompt=prompt)
    except (OSError, json.JSONDecodeError) as exc:
        print(f"ERROR {prompt.name}: {exc}")
        return True
    if errors:
        print(f"DRIFT {prompt.name}:")
        for error in errors:
            print(f"  - {error}")
        return True
    print(f"ok    {prompt.name}")
    return False


def main() -> int:
    prompts: list[Path] = sorted(_AGENTS.glob("*.md"))
    if not prompts:
        print(f"no agent prompts found in {_AGENTS}", file=sys.stderr)
        return 2
    drifted: int = sum(_report(prompt=prompt) for prompt in prompts)
    if drifted:
        print(f"\n{drifted} prompt(s) drifted from their schema.")
        return 1
    print("\nAll agent prompts match their return schemas.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
