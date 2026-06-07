#!/usr/bin/env python3
"""Validate an agent return against its v1 JSON-Schema contract.

A thin wrapper over jsonschema (the reference validator) so the architect can reject a
malformed return (exit 0/1/2). Run under uv so the dependency is present:
    uv run --no-project --with jsonschema python validate_return.py <schema> <instance>
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from jsonschema import Draft202012Validator
from referencing import Registry, Resource


def _validator(*, schema_path: Path) -> Draft202012Validator:
    """A validator registered with the sibling schemas, so cross-file $refs resolve."""
    registry: Registry = Registry().with_resources(
        (path.name, Resource.from_contents(json.loads(path.read_text())))
        for path in schema_path.parent.glob("*.schema.json")
    )
    return Draft202012Validator(json.loads(schema_path.read_text()), registry=registry)


def errors_against(*, instance: object, schema_path: Path) -> list[str]:
    """Every way an in-memory instance violates the schema (empty list = valid)."""
    validator: Draft202012Validator = _validator(schema_path=schema_path)
    messages: list[str] = [
        f"{error.json_path}: {error.message}"
        for error in validator.iter_errors(instance)
    ]
    return sorted(messages)


def validate(*, schema_path: Path, instance_path: Path) -> list[str]:
    """Every way the instance file violates the schema file (empty list means valid)."""
    instance: object = json.loads(instance_path.read_text())
    return errors_against(instance=instance, schema_path=schema_path)


def main(*, argv: list[str]) -> int:
    if len(argv) != 3:
        print(
            "usage: validate_return.py <schema.json> <instance.json>", file=sys.stderr
        )
        return 2
    schema_path: Path = Path(argv[1])
    instance_path: Path = Path(argv[2])
    try:
        errors: list[str] = validate(
            schema_path=schema_path, instance_path=instance_path
        )
    except (OSError, json.JSONDecodeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    if errors:
        print(f"INVALID: {instance_path.name} does not match {schema_path.name}")
        for error in errors:
            print(f"  - {error}")
        return 1
    print(f"OK: {instance_path.name} matches {schema_path.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(argv=sys.argv))
