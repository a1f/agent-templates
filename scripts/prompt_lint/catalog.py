"""The prompts on disk, checked against the inventory the installer places them from."""

from __future__ import annotations

import tomllib
from collections.abc import Iterator
from pathlib import Path

from .constants import CATALOG_PATH, MISSING_ROW, UNIT_PATHS, UNITS_TABLE


def _registered_units(*, catalog: Path) -> frozenset[str]:
    """The path every [[units]] row stands for, so parsed rows go no further."""
    rows: list[dict[str, str]] = tomllib.loads(catalog.read_text()).get(UNITS_TABLE, [])
    return frozenset(
        path_template.format(name=row["name"])
        for row in rows
        # A row of a kind that lives outside the prompt tree registers no prompt.
        if (path_template := UNIT_PATHS.get(row["kind"])) is not None
    )


def cross_check_catalog(*, root: Path) -> Iterator[str]:
    """Every prompt under root the installer has no [[units]] row to place, one each.

    A tree with no catalog is not a tree that lost its rows, so it reports nothing.
    The diagnostic carries no line number — the missing row has no line to point at.
    """
    catalog: Path = root / CATALOG_PATH
    if not catalog.is_file():
        return
    registered: frozenset[str] = _registered_units(catalog=catalog)
    for path_template in UNIT_PATHS.values():
        for unit in sorted(root.glob(path_template.format(name="*"))):
            where: str = str(unit.relative_to(root))
            if where not in registered:
                yield f"{where}: {MISSING_ROW}"
