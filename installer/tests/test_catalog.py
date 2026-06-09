from pathlib import Path
from typing import Final

import pytest

from catalog import Bundle, Catalog, Package, Unit, list_skills, load_catalog

SEED: Final[Path] = Path(__file__).resolve().parent.parent / "catalog.toml"

# A small controlled catalog so the behavioral assertions pin parse/resolve/sort
# logic rather than the real seed's contents, which grow as units are added.
_FIXTURE: Final[str] = """
[[units]]
kind = "skill"
name = "beta"

[[units]]
kind = "skill"
name = "alpha"

[[units]]
kind = "agent"
name = "helper"

[[packages]]
name = "pack"
units = ["skill/alpha", "agent/helper"]

[[bundles]]
name = "everything"
packages = ["pack"]
"""


def _write(tmp_path: Path, body: str) -> Path:
    catalog: Path = tmp_path / "catalog.toml"
    catalog.write_text(body, encoding="utf-8")
    return catalog


def test_load_catalog_populates_all_three_tiers(tmp_path: Path) -> None:
    catalog: Catalog = load_catalog(_write(tmp_path, _FIXTURE))

    assert Unit(kind="agent", name="helper") in catalog.units
    # A package holds resolved Unit objects, not raw id strings: frozen-dataclass
    # equality compares units element-wise, so this fails if resolution didn't happen.
    assert (
        Package(
            name="pack",
            units=(
                Unit(kind="skill", name="alpha"),
                Unit(kind="agent", name="helper"),
            ),
        )
        in catalog.packages
    )
    assert Bundle(name="everything", packages=("pack",)) in catalog.bundles


def test_list_skills_returns_only_skill_names_sorted(tmp_path: Path) -> None:
    catalog: Catalog = load_catalog(_write(tmp_path, _FIXTURE))

    # Only skill-kind units, and sorted (declaration order is beta, alpha).
    assert list_skills(catalog) == ["alpha", "beta"]


def test_load_catalog_rejects_package_referencing_undeclared_unit(
    tmp_path: Path,
) -> None:
    broken: Path = _write(
        tmp_path,
        '[[units]]\nkind = "skill"\nname = "make-pr"\n\n'
        '[[packages]]\nname = "ghost"\nunits = ["skill/does-not-exist"]\n\n'
        "[[bundles]]\n",
    )

    with pytest.raises(ValueError, match="skill/does-not-exist"):
        load_catalog(broken)


def test_real_seed_loads_and_skills_are_sorted_skill_names() -> None:
    # Smoke check against the shipped seed without hard-coding its full, growing
    # contents: it parses, stays sorted, surfaces a known skill, and never leaks
    # a non-skill unit into the skills list.
    catalog: Catalog = load_catalog(SEED)
    skills: list[str] = list_skills(catalog)

    assert skills == sorted(skills)
    assert "make-pr" in skills  # a known skill unit is surfaced
    assert "reviewer" not in skills  # an agent unit must not leak in
    assert "python" not in skills  # a rule unit must not leak in
