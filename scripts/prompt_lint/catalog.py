"""The prompts on disk, checked against the inventory the installer places them from."""

from __future__ import annotations

import tomllib
from collections.abc import Iterator
from pathlib import Path

from .constants import (
    CATALOG_PATH,
    EXTRAS_KEY,
    MISSING_ROW,
    PACKAGES_TABLE,
    SKILL_FILE,
    SKILL_ID_PREFIX,
    SKILL_KIND,
    SKILL_ROOT,
    STAGED_ROOT,
    STALE_EXTRA,
    STALE_ROW,
    UNIT_PATHS,
    UNITS_TABLE,
    UNREADABLE,
    UNREADABLE_MESSAGE,
)
from .types import RegisteredUnit, StagedExtra


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


def _staged_extras(*, catalog: Path) -> Iterator[StagedExtra]:
    """Which staged directory each skill of a package must read its extras from."""
    for row in tomllib.loads(catalog.read_text()).get(PACKAGES_TABLE, ()):
        for relpath in row.get(EXTRAS_KEY, ()):
            for unit in row[UNITS_TABLE]:
                if unit.startswith(SKILL_ID_PREFIX):
                    yield StagedExtra(
                        skill=unit.removeprefix(SKILL_ID_PREFIX),
                        segment=relpath.split("/")[0],
                    )


def check_staged_extras(*, root: Path) -> Iterator[str]:
    """An installed skill no longer sits beside its package's extras, so naming one in
    its own directory reads nothing once installed."""
    catalog: Path = root / CATALOG_PATH
    if not catalog.is_file():
        return
    for extra in dict.fromkeys(_staged_extras(catalog=catalog)):  # segments can repeat
        skill_dir: str = UNIT_PATHS[SKILL_KIND].format(name=extra.skill)
        where: str = f"{skill_dir}/{SKILL_FILE}"
        try:
            body: str = (root / where).read_text()
        except UNREADABLE as exc:
            yield f"{where}:1: {UNREADABLE_MESSAGE}: {exc}"
            continue
        staged: str = f"{STAGED_ROOT}/{extra.segment}"
        in_dir: str = f"{skill_dir}/{extra.segment}"
        stale_root: str = f"{SKILL_ROOT}/{extra.segment}"
        if staged not in body or in_dir in body or stale_root in body:
            yield f"{where}:1: {STALE_EXTRA.format(staged=staged)}"
