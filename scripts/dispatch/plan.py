"""Parse the skill-written plan at the boundary, once, into trusted domain types."""

from __future__ import annotations

import json
import re

from .constants import (
    BASE_PATTERN,
    DEFAULT_BASE,
    PR_PATTERN,
    REF_PATTERN,
    SESSION_PATTERN,
    SLUG_PATTERN,
)
from .types import DispatchError, DispatchItem, DispatchPlan


def load_plan(*, text: str) -> DispatchPlan:
    """Parse the skill-written plan JSON into a validated DispatchPlan.

    Raises DispatchError on any malformed or unsafe field; a returned plan is safe to
    turn into shell commands without further checking.
    """
    raw: object = json.loads(text)
    if not isinstance(raw, dict):
        raise DispatchError("plan must be a JSON object")
    ref: str = _field(raw=raw, key="ref", pattern=REF_PATTERN)
    base: str = _field(raw=raw, key="base", pattern=BASE_PATTERN, default=DEFAULT_BASE)
    session: str | None = _optional_field(
        raw=raw, key="session", pattern=SESSION_PATTERN
    )
    raw_items: object = raw.get("items")
    if not isinstance(raw_items, list) or not raw_items:
        raise DispatchError("plan.items must be a non-empty list")
    items: tuple[DispatchItem, ...] = tuple(
        _item(raw=entry, plan_ref=ref) for entry in raw_items
    )
    _reject_duplicates(field="slug", values=[item.slug for item in items])
    _reject_duplicates(field="pr", values=[item.pr for item in items])
    return DispatchPlan(ref=ref, base=base, session=session, items=items)


def _item(*, raw: object, plan_ref: str) -> DispatchItem:
    if not isinstance(raw, dict):
        raise DispatchError("each item must be a JSON object")
    pr: str = _field(raw=raw, key="pr", pattern=PR_PATTERN)
    slug: str = _field(raw=raw, key="slug", pattern=SLUG_PATTERN)
    ref: str = _field(raw=raw, key="ref", pattern=REF_PATTERN, default=plan_ref)
    return DispatchItem(pr=pr, slug=slug, ref=ref)


def _field(
    *,
    raw: dict[str, object],
    key: str,
    pattern: re.Pattern[str],
    default: str | None = None,
) -> str:
    value: object = raw.get(key, default)
    if not isinstance(value, str):
        raise DispatchError(f"{key} must be a string")
    if not pattern.fullmatch(value):
        raise DispatchError(f"{key} {value!r} contains disallowed characters")
    return value


def _optional_field(
    *, raw: dict[str, object], key: str, pattern: re.Pattern[str]
) -> str | None:
    if raw.get(key) is None:
        return None
    return _field(raw=raw, key=key, pattern=pattern)


def _reject_duplicates(*, field: str, values: list[str]) -> None:
    seen: set[str] = set()
    for value in values:
        if value in seen:
            raise DispatchError(f"duplicate {field} {value!r} in plan")
        seen.add(value)
