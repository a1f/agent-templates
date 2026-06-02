#!/usr/bin/env python3
"""Validate an agent return JSON against its v1 schema.

A stdlib-only structural validator for the subset of JSON Schema the v1 return
schemas use: ``type``, ``const``, ``enum``, ``required``, ``properties``,
``additionalProperties: false``, ``items``, ``minimum``/``maximum``, and ``$ref``
(same-document ``#/...`` or sibling-file ``name.json#/...``). It is deliberately
not a general JSON Schema implementation — just enough to enforce the v1 return
contracts without adding a dependency the user's project may not have.

Usage:
    python3 validate_return.py <schema.json> <instance.json>

Exits 0 if the instance is valid, 1 if it violates the schema, 2 on bad input.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

_TYPES: dict[str, type | tuple[type, ...]] = {
    "object": dict,
    "array": list,
    "string": str,
    "integer": int,
    "number": (int, float),
    "boolean": bool,
}


def _resolve_ref(ref: str, *, schema_dir: Path, root: dict) -> dict:
    file_part, _, pointer = ref.partition("#")
    doc = root if not file_part else json.loads((schema_dir / file_part).read_text())
    node: object = doc
    for token in pointer.split("/"):
        if token:
            node = node[token.replace("~1", "/").replace("~0", "~")]
    return node  # type: ignore[return-value]


def _is_number(value: object) -> bool:
    # bool is a subclass of int — exclude it from numeric checks.
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _validate(
    instance: object,
    schema: dict,
    *,
    schema_dir: Path,
    root: dict,
    path: str,
    errors: list[str],
) -> None:
    if "$ref" in schema:
        schema = _resolve_ref(schema["$ref"], schema_dir=schema_dir, root=root)

    if "const" in schema and instance != schema["const"]:
        errors.append(f"{path}: expected const {schema['const']!r}, got {instance!r}")
    if "enum" in schema and instance not in schema["enum"]:
        errors.append(f"{path}: {instance!r} not in enum {schema['enum']}")

    expected = schema.get("type")
    if expected:
        py_type = _TYPES[expected]
        ok = isinstance(instance, py_type) and not (
            expected in ("integer", "number") and isinstance(instance, bool)
        )
        if not ok:
            errors.append(f"{path}: expected type {expected}, got {type(instance).__name__}")
            return  # wrong container type — recursing would be noise

    if isinstance(instance, dict):
        props: dict = schema.get("properties", {})
        for key in schema.get("required", []):
            if key not in instance:
                errors.append(f"{path}: missing required key '{key}'")
        if schema.get("additionalProperties") is False:
            for key in instance:
                if key not in props:
                    errors.append(f"{path}: unexpected key '{key}'")
        for key, value in instance.items():
            if key in props:
                _validate(value, props[key], schema_dir=schema_dir, root=root,
                          path=f"{path}.{key}", errors=errors)
    elif isinstance(instance, list):
        item_schema = schema.get("items")
        if item_schema:
            for index, item in enumerate(instance):
                _validate(item, item_schema, schema_dir=schema_dir, root=root,
                          path=f"{path}[{index}]", errors=errors)

    if _is_number(instance):
        if "minimum" in schema and instance < schema["minimum"]:
            errors.append(f"{path}: {instance} below minimum {schema['minimum']}")
        if "maximum" in schema and instance > schema["maximum"]:
            errors.append(f"{path}: {instance} above maximum {schema['maximum']}")


def validate(schema_path: Path, instance_path: Path) -> list[str]:
    schema = json.loads(schema_path.read_text())
    instance = json.loads(instance_path.read_text())
    errors: list[str] = []
    _validate(instance, schema, schema_dir=schema_path.parent, root=schema,
              path="$", errors=errors)
    return errors


def main(argv: list[str]) -> int:
    if len(argv) != 3:
        print("usage: validate_return.py <schema.json> <instance.json>", file=sys.stderr)
        return 2
    schema_path, instance_path = Path(argv[1]), Path(argv[2])
    try:
        errors = validate(schema_path, instance_path)
    except (OSError, json.JSONDecodeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    if errors:
        print(f"INVALID: {instance_path.name} does not match {schema_path.name}")
        for err in errors:
            print(f"  - {err}")
        return 1
    print(f"OK: {instance_path.name} matches {schema_path.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
