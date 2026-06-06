#!/usr/bin/env python3
"""Validate an agent return against the v1 JSON-Schema subset — no third-party deps.

Covers only the keywords the v1 return schemas use: type, const, enum, required,
properties, additionalProperties, items, minimum/maximum, minLength, allOf,
if/then/else, contains, and $ref (same-doc "#/..." or sibling "file.json#/...").
This lets a return contract be enforced in any project without installing jsonschema.

Usage: python3 validate_return.py <schema.json> <instance.json>  (exit 0/1/2).
"""

from __future__ import annotations

import json
import sys
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final, cast

type Schema = dict[str, Any]

# JSON type name -> the Python type(s) that satisfy it. bool is handled in _typed,
# since it subclasses int and must not satisfy "integer"/"number".
_PYTYPES: Final[dict[str, type | tuple[type, ...]]] = {
    "object": dict,
    "array": list,
    "string": str,
    "integer": int,
    "number": (int, float),
    "boolean": bool,
}


@dataclass(frozen=True)
class Ctx:
    """The $ref-resolution context — constant for one validation, so it rides along
    instead of being threaded as separate schema_dir / root arguments."""

    schema_dir: Path
    root: Schema


def deref(schema: Schema, ctx: Ctx) -> Schema:
    """Resolve a $ref to the schema it points at; unchanged if there is no $ref."""
    ref = schema.get("$ref")
    if ref is None:
        return schema
    file, _, pointer = ref.partition("#")
    doc: Any = json.loads((ctx.schema_dir / file).read_text()) if file else ctx.root
    for token in filter(None, pointer.split("/")):
        doc = doc[token.replace("~1", "/").replace("~0", "~")]
    return cast("Schema", doc)  # a $ref resolves to a schema object by contract


def _typed(instance: object, name: str) -> bool:
    # bool subclasses int, so it must satisfy only "boolean", never "integer"/"number".
    if isinstance(instance, bool):
        return name == "boolean"
    return isinstance(instance, _PYTYPES[name])


def _ok(instance: object, schema: Schema, ctx: Ctx) -> bool:
    """Whether instance validates cleanly — drives if/then/else and contains checks."""
    return next(iter_errors(instance, schema, ctx), None) is None


def iter_errors(
    instance: object, schema: Schema, ctx: Ctx, path: str = "$"
) -> Iterator[str]:
    """Yield one message per way instance violates schema; empty when it is valid."""
    schema = deref(schema, ctx)

    for branch in schema.get("allOf", []):
        yield from iter_errors(instance, branch, ctx, path)
    if "if" in schema:
        taken = "then" if _ok(instance, schema["if"], ctx) else "else"
        yield from iter_errors(instance, schema.get(taken, {}), ctx, path)

    if "const" in schema and instance != schema["const"]:
        yield f"{path}: expected const {schema['const']!r}, got {instance!r}"
    if "enum" in schema and instance not in schema["enum"]:
        yield f"{path}: {instance!r} not in enum {schema['enum']}"

    wanted = schema.get("type")
    if wanted and not _typed(instance, wanted):
        yield f"{path}: expected type {wanted}, got {type(instance).__name__}"
        return  # wrong shape — deeper checks would only add noise

    if isinstance(instance, str) and len(instance) < schema.get("minLength", 0):
        yield f"{path}: shorter than minLength {schema['minLength']}"
    if _typed(instance, "number"):  # excludes bool by construction
        if (low := schema.get("minimum")) is not None and instance < low:
            yield f"{path}: {instance} below minimum {low}"
        if (high := schema.get("maximum")) is not None and instance > high:
            yield f"{path}: {instance} above maximum {high}"
    if isinstance(instance, dict):
        yield from _object_errors(instance, schema, ctx, path)
    elif isinstance(instance, list):
        yield from _array_errors(instance, schema, ctx, path)


def _object_errors(
    obj: dict[str, Any], schema: Schema, ctx: Ctx, path: str
) -> Iterator[str]:
    props: Schema = schema.get("properties", {})
    for key in schema.get("required", []):
        if key not in obj:
            yield f"{path}: missing required key {key!r}"
    if schema.get("additionalProperties") is False:
        for key in obj:
            if key not in props:
                yield f"{path}: unexpected key {key!r}"
    for key, value in obj.items():
        if key in props:
            yield from iter_errors(value, props[key], ctx, f"{path}.{key}")


def _array_errors(
    items: list[Any], schema: Schema, ctx: Ctx, path: str
) -> Iterator[str]:
    if item_schema := schema.get("items"):
        for index, item in enumerate(items):
            yield from iter_errors(item, item_schema, ctx, f"{path}[{index}]")
    if (contains := schema.get("contains")) and not any(
        _ok(item, contains, ctx) for item in items
    ):
        yield f"{path}: no array item matches the 'contains' schema"


def validate(schema_path: Path, instance_path: Path) -> list[str]:
    """Every way the instance file violates the schema file (empty list means valid)."""
    schema: Schema = json.loads(schema_path.read_text())
    instance = json.loads(instance_path.read_text())
    return list(iter_errors(instance, schema, Ctx(schema_path.parent, schema)))


def main(argv: list[str]) -> int:
    if len(argv) != 3:
        print(
            "usage: validate_return.py <schema.json> <instance.json>", file=sys.stderr
        )
        return 2
    schema_path, instance_path = Path(argv[1]), Path(argv[2])
    try:
        errors = validate(schema_path, instance_path)
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
    raise SystemExit(main(sys.argv))
