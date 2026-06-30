from pathlib import Path
from typing import Final

from catalog import Catalog, load_catalog

# installer/tests/ -> installer/ -> repo root, holding skills/<name>/, the catalog, and
# the single canonical rules/ the in-skill bundles used to copy.
_REPO_ROOT: Final[Path] = Path(__file__).resolve().parent.parent.parent
_CATALOG_PATH: Final[Path] = _REPO_ROOT / "installer" / "catalog.toml"
_SKILLS_ROOT: Final[Path] = _REPO_ROOT / "skills"

# Skills that historically bundled COPIES of repo assets inside their own dir so the
# assets shipped on install; slice 7.6 retires the copies and composes the deps from the
# single canonical source via the package `extras` mechanism.
_CLONE_DEPENDENT_SKILLS: Final[tuple[str, ...]] = (
    "make-pr",
    "make-pr-lite",
    "improve-architecture",
)

# Asset dirs that are canonical-root-only: a skill holding any of these is duplicating
# files that already live once at the repo root.
_FORBIDDEN_ASSET_DIRS: Final[frozenset[str]] = frozenset(
    {"rules", "gates", "schemas", "scripts"}
)

# The extra each clone-dependent skill's package must declare so its rule deps are
# composed from the canonical rules/ at install time instead of a bundled in-skill copy.
_COMPOSED_RULES_EXTRA: Final[str] = "rules"
_SKILL_KIND: Final[str] = "skill"

# The single canonical rule source that must survive the retirement of the copies.
_CANONICAL_RULES_DIR: Final[Path] = _REPO_ROOT / "rules"
_CANONICAL_RULE_FILES: Final[tuple[str, ...]] = ("design-principles.md", "tdd.md")


def _composes_rules_for_skill(*, catalog: Catalog, skill: str) -> bool:
    """A skill's rule deps are composed from canonical when some catalog package both
    lists the skill as a skill-kind unit and declares "rules" among its extras."""
    return any(
        _COMPOSED_RULES_EXTRA in package.extras
        and any(
            unit.kind == _SKILL_KIND and unit.name == skill for unit in package.units
        )
        for package in catalog.packages
    )


def test_clone_dependent_skills_compose_deps_from_canonical_not_bundled() -> None:
    """Clone-dependent skills must compose their rule/gate deps from the single
    canonical source: no in-skill duplicate asset dir survives, every such skill is
    declared as a skill-kind unit of a package whose extras include "rules", and the
    canonical rules/ source it composes from stays intact (we retire the copies, not
    the source)."""
    catalog: Catalog = load_catalog(_CATALOG_PATH)

    for skill in _CLONE_DEPENDENT_SKILLS:
        skill_root: Path = _SKILLS_ROOT / skill
        bundled_dirs: list[str] = sorted(
            name for name in _FORBIDDEN_ASSET_DIRS if (skill_root / name).is_dir()
        )
        assert not bundled_dirs, (
            f"skill {skill!r} still bundles canonical asset dir(s) {bundled_dirs} "
            f"under skills/{skill}/ — retire the in-skill copies and compose the deps "
            f"from the single canonical source"
        )
        assert _composes_rules_for_skill(catalog=catalog, skill=skill), (
            f"skill {skill!r} is not composed from canonical rules: no catalog package "
            f"lists it as a {_SKILL_KIND!r} unit with {_COMPOSED_RULES_EXTRA!r} in its "
            f"extras"
        )

    assert _CANONICAL_RULES_DIR.is_dir(), (
        f"canonical {_CANONICAL_RULES_DIR.name}/ is gone — retire the COPIES, not the "
        f"single canonical source"
    )
    for rule_file in _CANONICAL_RULE_FILES:
        assert (_CANONICAL_RULES_DIR / rule_file).is_file(), (
            f"canonical rules/{rule_file} is missing — the single source must survive "
            f"the retirement of the in-skill copies"
        )
