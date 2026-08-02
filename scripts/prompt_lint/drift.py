"""The example return an agent prompt closes with, held to the schema it names."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

from check_prompt_schemas import drift

from .constants import AGENTS_GLOB, SCHEMAS_DIR, UNREADABLE, UNREADABLE_MESSAGE


def check_schema_drift(*, root: Path) -> Iterator[str]:
    """An agent's example return is the shape callers rely on, so it has to keep
    answering to the schema the architect validates the real return against."""
    for prompt in sorted(root.glob(AGENTS_GLOB)):
        where: Path = prompt.relative_to(root)
        try:
            messages: list[str] = drift(prompt=prompt, schemas=root / SCHEMAS_DIR)
        except UNREADABLE as exc:
            yield f"{where}:1: {UNREADABLE_MESSAGE}: {exc}"
            continue
        for message in messages:
            yield f"{where}:1: {message}"
