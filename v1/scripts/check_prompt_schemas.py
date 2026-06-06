#!/usr/bin/env python3
"""Anti-drift check: each agent prompt's example return stays in sync with its schema.

Every v1 agent prompt ends with a JSON return block. This checks that block against the
authoritative schema in v1/schemas/ two ways: identical key sets at every object level
(so an added, renamed, or dropped field is caught — stricter than the schema, which lets
optional keys be absent), and — via the same validator the architect runs on real
returns — the enum values and numeric ranges the key walk alone cannot see.

Usage: python3 check_prompt_schemas.py    # every prompt in v1/agents/  (exit 0/1/2).
"""

from __future__ import annotations

import json
import re
import sys
from collections.abc import Iterator
from pathlib import Path
from typing import Any, Final, cast

sys.path.insert(0, str(Path(__file__).resolve().parent))
from validate_return import (
    Ctx,
    Schema,
    deref,
    iter_errors,
)

_V1: Final = Path(__file__).resolve().parent.parent
_AGENTS: Final = _V1 / "agents"
_SCHEMAS: Final = _V1 / "schemas"
_JSON_BLOCK: Final = re.compile(r"```json\n(.*?)\n```", re.DOTALL)


def _example(prompt: Path) -> dict[str, Any]:
    """The last ```json block in a prompt — the Return shape the agent is shown."""
    blocks = _JSON_BLOCK.findall(prompt.read_text())
    if not blocks:
        raise ValueError("no ```json block found")
    return cast("dict[str, Any]", json.loads(blocks[-1]))


def _key_drift(example: object, schema: Schema, ctx: Ctx, path: str) -> Iterator[str]:
    """Yield every place the example's keys diverge from the schema's properties."""
    schema = deref(schema, ctx)
    if schema.get("type") == "object" or "properties" in schema:
        if not isinstance(example, dict):
            yield f"{path}: expected an object, example is {type(example).__name__}"
            return
        props: Schema = schema.get("properties", {})
        for missing in sorted(props.keys() - example.keys()):
            yield f"{path}: example is missing key {missing!r} (present in schema)"
        for extra in sorted(example.keys() - props.keys()):
            yield f"{path}: example has key {extra!r} (not in schema)"
        for key in sorted(props.keys() & example.keys()):
            yield from _key_drift(example[key], props[key], ctx, f"{path}.{key}")
    elif schema.get("type") == "array" and (item_schema := schema.get("items")):
        if not isinstance(example, list):
            yield f"{path}: expected an array, example is {type(example).__name__}"
        elif example:
            yield from _key_drift(example[0], item_schema, ctx, f"{path}[0]")


def drift(prompt: Path) -> list[str]:
    """How a prompt's example diverges from its role's schema (empty = in sync)."""
    example = _example(prompt)
    role = example.get("role")
    schema_path = _SCHEMAS / f"{role}.schema.json"
    if not schema_path.exists():
        return [f"role {role!r} has no schema at {schema_path.relative_to(_V1.parent)}"]
    schema: Schema = json.loads(schema_path.read_text())
    ctx = Ctx(_SCHEMAS, schema)
    # Key-set parity catches structural drift; iter_errors catches the enum/range drift
    # the key walk cannot — together they hold the example to the full return contract.
    return [
        *_key_drift(example, schema, ctx, str(role)),
        *iter_errors(example, schema, ctx, str(role)),
    ]


def main() -> int:
    prompts = sorted(_AGENTS.glob("*.md"))
    if not prompts:
        print(f"no agent prompts found in {_AGENTS}", file=sys.stderr)
        return 2
    drifted = 0
    for prompt in prompts:
        try:
            errors = drift(prompt)
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            print(f"ERROR {prompt.name}: {exc}")
            drifted += 1
            continue
        if errors:
            drifted += 1
            print(f"DRIFT {prompt.name}:")
            for error in errors:
                print(f"  - {error}")
        else:
            print(f"ok    {prompt.name}")
    if drifted:
        print(f"\n{drifted} prompt(s) drifted from their schema.")
        return 1
    print("\nAll agent prompts match their return schemas.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
