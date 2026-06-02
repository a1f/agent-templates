#!/usr/bin/env python3
"""Anti-drift check: every agent prompt's example return matches its schema's shape.

Each v1 agent prompt ends with an illustrative ```json block. That block is a
human-facing example — enum fields show "a | b" choices, so it is NOT a valid data
instance — but its KEY STRUCTURE must stay in lockstep with the authoritative schema
in v1/schemas/. This check extracts the block, reads its "role" to find the matching
schema, and asserts the key sets are identical at every object level. A prompt edit
that adds, renames, or drops a field is caught here before it can drift from the
schema the architect validates real returns against.

Usage:
    python3 check_prompt_schemas.py        # checks every prompt in v1/agents/

Exits 0 if every prompt matches its schema, 1 on drift, 2 on bad input.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

V1 = Path(__file__).resolve().parent.parent
AGENTS = V1 / "agents"
SCHEMAS = V1 / "schemas"

_JSON_BLOCK = re.compile(r"```json\n(.*?)\n```", re.DOTALL)


def _example_object(prompt_path: Path) -> dict:
    blocks = _JSON_BLOCK.findall(prompt_path.read_text())
    if not blocks:
        raise ValueError("no ```json block found")
    return json.loads(blocks[-1])  # the Return block is the last json fence


def _resolve(schema: dict, *, schema_dir: Path, root: dict) -> dict:
    if "$ref" not in schema:
        return schema
    file_part, _, pointer = schema["$ref"].partition("#")
    doc = root if not file_part else json.loads((schema_dir / file_part).read_text())
    node: object = doc
    for token in pointer.split("/"):
        if token:
            node = node[token]
    return node  # type: ignore[return-value]


def _check(
    example: object,
    schema: dict,
    *,
    schema_dir: Path,
    root: dict,
    path: str,
    errors: list[str],
) -> None:
    schema = _resolve(schema, schema_dir=schema_dir, root=root)

    if schema.get("type") == "object" or "properties" in schema:
        if not isinstance(example, dict):
            errors.append(f"{path}: schema expects an object, example is {type(example).__name__}")
            return
        props: dict = schema.get("properties", {})
        expected, actual = set(props), set(example)
        for missing in sorted(expected - actual):
            errors.append(f"{path}: example is missing key '{missing}' (present in schema)")
        for extra in sorted(actual - expected):
            errors.append(f"{path}: example has key '{extra}' (not in schema)")
        for key in sorted(expected & actual):
            _check(example[key], props[key], schema_dir=schema_dir, root=root,
                   path=f"{path}.{key}", errors=errors)
    elif schema.get("type") == "array":
        if not isinstance(example, list):
            errors.append(f"{path}: schema expects an array, example is {type(example).__name__}")
            return
        item_schema = schema.get("items")
        if item_schema and example:
            _check(example[0], item_schema, schema_dir=schema_dir, root=root,
                   path=f"{path}[0]", errors=errors)


def check_agent(prompt_path: Path) -> list[str]:
    example = _example_object(prompt_path)
    role = example.get("role")
    schema_path = SCHEMAS / f"{role}.schema.json"
    if not schema_path.exists():
        return [f"role {role!r} has no schema at {schema_path.relative_to(V1.parent)}"]
    schema = json.loads(schema_path.read_text())
    errors: list[str] = []
    _check(example, schema, schema_dir=SCHEMAS, root=schema, path=str(role), errors=errors)
    return errors


def main() -> int:
    prompts = sorted(AGENTS.glob("*.md"))
    if not prompts:
        print(f"no agent prompts found in {AGENTS}", file=sys.stderr)
        return 2
    failures = 0
    for prompt_path in prompts:
        try:
            errors = check_agent(prompt_path)
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            print(f"ERROR {prompt_path.name}: {exc}")
            failures += 1
            continue
        if errors:
            failures += 1
            print(f"DRIFT {prompt_path.name}:")
            for err in errors:
                print(f"  - {err}")
        else:
            print(f"ok    {prompt_path.name}")
    if failures:
        print(f"\n{failures} prompt(s) drifted from their schema.")
        return 1
    print("\nAll agent prompts match their return schemas.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
