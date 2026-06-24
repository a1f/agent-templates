import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Final, cast

# Packages name their units by a "<kind>/<name>" id so each unit is declared once
# under [[units]] and reused across packages; this is the join key load_catalog
# resolves against.
_REF_SEP: Final[str] = "/"


@dataclass(frozen=True)
class Unit:
    """An atom the installer can place: one skill, agent, rule, or hook."""

    kind: str
    name: str


@dataclass(frozen=True)
class Package:
    """A named group of units installed together; holds the resolved Unit
    objects, not raw id strings, so callers never re-join against the unit table.
    `extras` are source-relative paths (files or directories) to the runtime
    support files a skill reads — schemas, gates, helper scripts — staged
    alongside the units so an install is self-contained; default `()` keeps
    `Package(name=..., units=...)` construction working for packages with none."""

    name: str
    units: tuple[Unit, ...]
    extras: tuple[str, ...] = ()


@dataclass(frozen=True)
class Bundle:
    """An opinionated pick of packages (by name), the coarsest install choice.
    Package names are kept raw here; resolving and validating bundle->package
    refs is deferred to the slice that makes the bundle tier load-bearing."""

    name: str
    packages: tuple[str, ...]


@dataclass(frozen=True)
class Catalog:
    """The whole three-tier catalog parsed into trusted domain types, so the rest
    of the installer never touches raw toml."""

    units: tuple[Unit, ...]
    packages: tuple[Package, ...]
    bundles: tuple[Bundle, ...]


_SKILL_KIND: Final[str] = "skill"
_AGENT_KIND: Final[str] = "agent"
_RULE_KIND: Final[str] = "rule"
_HOOK_KIND: Final[str] = "hook"


def unit_id(unit: Unit) -> str:
    """Own the "<kind>/<name>" join key in one place, so callers key state and
    resolve packages without re-encoding the id format this module defines."""
    return f"{unit.kind}{_REF_SEP}{unit.name}"


def skill_unit(name: str) -> Unit:
    """Own the skill-kind decision here, so callers stage skills without
    re-encoding the "skill" kind token this module is the source of truth for."""
    return Unit(kind=_SKILL_KIND, name=name)


def skill_unit_id(name: str) -> str:
    """Expose the id a skill unit is keyed by, so callers render install status
    without re-encoding the "<kind>/<name>" join this module owns."""
    return unit_id(skill_unit(name))


def agent_unit(name: str) -> Unit:
    """Own the agent-kind decision here, so callers stage agents without
    re-encoding the "agent" kind token this module is the source of truth for."""
    return Unit(kind=_AGENT_KIND, name=name)


def agent_unit_id(name: str) -> str:
    """Expose the id an agent unit is keyed by, so callers render install status
    without re-encoding the "<kind>/<name>" join this module owns."""
    return unit_id(agent_unit(name))


def rule_unit(name: str) -> Unit:
    """Own the rule-kind decision here, so callers stage rules without
    re-encoding the "rule" kind token this module is the source of truth for."""
    return Unit(kind=_RULE_KIND, name=name)


def rule_unit_id(name: str) -> str:
    """Expose the id a rule unit is keyed by, so callers render install status
    without re-encoding the "<kind>/<name>" join this module owns."""
    return unit_id(rule_unit(name))


def hook_unit(name: str) -> Unit:
    """Own the hook-kind decision here, so callers stage hooks without
    re-encoding the "hook" kind token this module is the source of truth for."""
    return Unit(kind=_HOOK_KIND, name=name)


def hook_unit_id(name: str) -> str:
    """Expose the id a hook unit is keyed by, so callers render install status
    without re-encoding the "<kind>/<name>" join this module owns."""
    return unit_id(hook_unit(name))


def list_skills(catalog: Catalog) -> list[str]:
    """Surface the installable skills by name in a stable order, so a UI listing
    doesn't depend on declaration order in the toml."""
    return sorted(unit.name for unit in catalog.units if unit.kind == _SKILL_KIND)


def list_agents(catalog: Catalog) -> list[str]:
    """Surface the installable agents by name in a stable order, so a UI listing
    doesn't depend on declaration order in the toml."""
    return sorted(unit.name for unit in catalog.units if unit.kind == _AGENT_KIND)


def list_rules(catalog: Catalog) -> list[str]:
    """Surface the installable rules by name in a stable order, so a UI listing
    doesn't depend on declaration order in the toml."""
    return sorted(unit.name for unit in catalog.units if unit.kind == _RULE_KIND)


def list_hooks(catalog: Catalog) -> list[str]:
    """Surface the installable hooks by name in a stable order, so a UI listing
    doesn't depend on declaration order in the toml."""
    return sorted(unit.name for unit in catalog.units if unit.kind == _HOOK_KIND)


def _resolve(ref: str, by_id: dict[str, Unit], package: str) -> Unit:
    """Turn a package's unit id into the declared Unit, failing loudly at parse
    time with the dangling ref named rather than silently dropping it."""
    try:
        return by_id[ref]
    except KeyError as missing:
        raise ValueError(
            f"package {package!r} references undeclared unit {ref!r}"
        ) from missing


def _build_package(row: dict[str, object], by_id: dict[str, Unit]) -> Package:
    name: str = cast("str", row["name"])
    refs: list[str] = cast("list[str]", row["units"])
    extras: tuple[str, ...] = tuple(cast("list[str]", row.get("extras", [])))
    return Package(
        name=name,
        units=tuple(_resolve(ref, by_id, name) for ref in refs),
        extras=extras,
    )


def resolve_package(catalog: Catalog, name: str) -> Package:
    """Turn a package name into its declared Package — the unit set plus extras —
    in one place, so callers select a curated group without re-scanning the
    package table; an undeclared name fails loudly here rather than silently
    resolving to nothing downstream."""
    by_name: dict[str, Package] = {
        package.name: package for package in catalog.packages
    }
    try:
        return by_name[name]
    except KeyError as missing:
        raise ValueError(
            f"package {name!r} is not declared in the catalog"
        ) from missing


def load_catalog(path: Path) -> Catalog:
    """Parse the seed catalog at the boundary into frozen domain types, resolving
    each package's unit ids to the declared Unit so the interior never re-joins."""
    with path.open("rb") as handle:
        raw: dict[str, object] = tomllib.load(handle)

    units: tuple[Unit, ...] = tuple(
        Unit(kind=cast("str", row["kind"]), name=cast("str", row["name"]))
        for row in cast("list[dict[str, object]]", raw["units"])
    )
    by_id: dict[str, Unit] = {unit_id(unit): unit for unit in units}

    packages: tuple[Package, ...] = tuple(
        _build_package(row, by_id)
        for row in cast("list[dict[str, object]]", raw["packages"])
    )

    bundles: tuple[Bundle, ...] = tuple(
        Bundle(
            name=cast("str", row["name"]),
            packages=tuple(cast("list[str]", row["packages"])),
        )
        for row in cast("list[dict[str, object]]", raw["bundles"])
    )

    return Catalog(units=units, packages=packages, bundles=bundles)
