"""The prompts on disk, checked against the inventory the installer places them from."""

from __future__ import annotations

import tomllib
from collections.abc import Iterator
from pathlib import Path

from .constants import CATALOG_PATH, MISSING_ROW, STALE_ROW, UNIT_PATHS, UNITS_TABLE
from .types import RegisteredUnit


def _registered_units(*, catalog: Path) -> tuple[RegisteredUnit, ...]:
    """Every [[units]] row that stands for a prompt, so parsed rows go no further."""
    rows: list[dict[str, str]] = tomllib.loads(catalog.read_text()).get(UNITS_TABLE, [])
    return tuple(
        RegisteredUnit(
            kind=row["kind"], name=row["name"], path=template.format(name=row["name"])
        )
        for row in rows
        # A row of a kind that lives outside the prompt tree registers no prompt.
        if (template := UNIT_PATHS.get(row["kind"])) is not None
    )


def cross_check_catalog(*, root: Path) -> Iterator[str]:
    """Every prompt the catalog has no row for, and every row with no prompt on disk.

    A tree with no catalog is not a tree that lost its rows, so it reports nothing, and
    neither diagnostic carries a line number — neither finding sits on a line.
    """
    catalog: Path = root / CATALOG_PATH
    if not catalog.is_file():
        return
    registered: tuple[RegisteredUnit, ...] = _registered_units(catalog=catalog)
    known: frozenset[str] = frozenset(unit.path for unit in registered)
    for path_template in UNIT_PATHS.values():
        for prompt in sorted(root.glob(path_template.format(name="*"))):
            if (where := str(prompt.relative_to(root))) not in known:
                yield f"{where}: {MISSING_ROW}"
    for unit in registered:
        if not (root / unit.path).exists():
            yield STALE_ROW.format(unit=f"{unit.kind}/{unit.name}", path=unit.path)
