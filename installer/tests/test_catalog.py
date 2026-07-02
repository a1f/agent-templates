from pathlib import Path
from typing import Final

import pytest

from catalog import (
    Bundle,
    Catalog,
    Package,
    Unit,
    list_agents,
    list_bundles,
    list_hooks,
    list_packages,
    list_rules,
    list_skills,
    load_catalog,
    resolve_bundle,
    resolve_package,
    skill_unit_id,
)

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


# Two agent units declared out of order (zeta before alpha) plus a skill and a
# rule, so a single catalog pins both the sort and the non-agent exclusion.
_AGENTS_FIXTURE: Final[str] = """
[[units]]
kind = "agent"
name = "zeta"

[[units]]
kind = "agent"
name = "alpha"

[[units]]
kind = "skill"
name = "beta"

[[units]]
kind = "rule"
name = "python"

[[packages]]
name = "pack"
units = ["agent/alpha"]

[[bundles]]
name = "everything"
packages = ["pack"]
"""


# Two rule units declared out of order (zeta before alpha) plus a skill and an
# agent, so a single catalog pins both the sort and the non-rule exclusion.
_RULES_FIXTURE: Final[str] = """
[[units]]
kind = "rule"
name = "zeta"

[[units]]
kind = "rule"
name = "alpha"

[[units]]
kind = "skill"
name = "beta"

[[units]]
kind = "agent"
name = "helper"

[[packages]]
name = "pack"
units = ["rule/alpha"]

[[bundles]]
name = "everything"
packages = ["pack"]
"""


# Two hook units declared out of order (zeta before alpha) plus a skill and an
# agent, so a single catalog pins both the sort and the non-hook exclusion.
_HOOKS_FIXTURE: Final[str] = """
[[units]]
kind = "hook"
name = "zeta"

[[units]]
kind = "hook"
name = "alpha"

[[units]]
kind = "skill"
name = "beta"

[[units]]
kind = "agent"
name = "helper"

[[packages]]
name = "pack"
units = ["hook/alpha"]

[[bundles]]
name = "everything"
packages = ["pack"]
"""


# One package declares extras (three paths, order significant) and another omits
# the key entirely, so a single catalog pins both extras-order preservation and
# the empty-tuple default.
_EXTRAS_FIXTURE: Final[str] = """
[[units]]
kind = "skill"
name = "alpha"

[[units]]
kind = "agent"
name = "helper"

[[packages]]
name = "withextras"
units = ["skill/alpha"]
extras = ["schemas", "gates", "scripts/run.py"]

[[packages]]
name = "bare"
units = ["agent/helper"]

[[bundles]]
name = "everything"
packages = ["withextras", "bare"]
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


def test_load_catalog_parses_package_extras_in_declared_order(tmp_path: Path) -> None:
    catalog: Catalog = load_catalog(_write(tmp_path, _EXTRAS_FIXTURE))

    # extras parse into Package.extras as a tuple in declaration order; tuple
    # equality is ordered, so a reorder would fail this.
    assert (
        Package(
            name="withextras",
            units=(Unit(kind="skill", name="alpha"),),
            extras=("schemas", "gates", "scripts/run.py"),
        )
        in catalog.packages
    )
    # A package row with no extras key defaults to an empty tuple.
    assert (
        Package(name="bare", units=(Unit(kind="agent", name="helper"),))
        in catalog.packages
    )


def test_resolve_package_returns_the_named_package(tmp_path: Path) -> None:
    catalog: Catalog = load_catalog(_write(tmp_path, _EXTRAS_FIXTURE))

    package: Package = resolve_package(catalog, "withextras")

    assert package.name == "withextras"
    assert package.extras == ("schemas", "gates", "scripts/run.py")
    assert package.units == (Unit(kind="skill", name="alpha"),)


def test_resolve_package_raises_naming_an_undeclared_package(tmp_path: Path) -> None:
    catalog: Catalog = load_catalog(_write(tmp_path, _EXTRAS_FIXTURE))

    # A name with no matching package fails loudly, naming the missing package.
    with pytest.raises(ValueError, match="ghost"):
        resolve_package(catalog, "ghost")


def test_resolve_bundle_returns_the_named_bundle(tmp_path: Path) -> None:
    catalog: Catalog = load_catalog(_write(tmp_path, _FIXTURE))

    bundle: Bundle = resolve_bundle(catalog=catalog, name="everything")

    assert bundle == Bundle(name="everything", packages=("pack",))


def test_resolve_bundle_raises_naming_an_undeclared_bundle(tmp_path: Path) -> None:
    catalog: Catalog = load_catalog(_write(tmp_path, _FIXTURE))

    # A name with no matching bundle fails loudly, naming the missing bundle.
    with pytest.raises(ValueError, match="ghost"):
        resolve_bundle(catalog=catalog, name="ghost")


def test_list_skills_returns_only_skill_names_sorted(tmp_path: Path) -> None:
    catalog: Catalog = load_catalog(_write(tmp_path, _FIXTURE))

    # Only skill-kind units, and sorted (declaration order is beta, alpha).
    assert list_skills(catalog) == ["alpha", "beta"]


def test_list_agents_returns_only_agent_names_sorted(tmp_path: Path) -> None:
    catalog: Catalog = load_catalog(_write(tmp_path, _AGENTS_FIXTURE))

    # Only agent-kind units, and sorted (declaration order is zeta, alpha); the
    # skill and rule units must not leak into the agent listing.
    assert list_agents(catalog) == ["alpha", "zeta"]


def test_list_rules_returns_only_rule_names_sorted(tmp_path: Path) -> None:
    catalog: Catalog = load_catalog(_write(tmp_path, _RULES_FIXTURE))

    # Only rule-kind units, and sorted (declaration order is zeta, alpha); the
    # skill and agent units must not leak into the rule listing.
    assert list_rules(catalog) == ["alpha", "zeta"]


def test_list_hooks_returns_only_hook_names_sorted(tmp_path: Path) -> None:
    catalog: Catalog = load_catalog(_write(tmp_path, _HOOKS_FIXTURE))

    # Only hook-kind units, and sorted (declaration order is zeta, alpha); the
    # skill and agent units must not leak into the hook listing.
    assert list_hooks(catalog) == ["alpha", "zeta"]


def test_list_packages_returns_package_names_sorted() -> None:
    # Packages are listed by name in a stable sorted order, independent of their
    # declaration order in the catalog (here zeta is declared before alpha).
    shared: Unit = Unit(kind="skill", name="alpha")
    catalog: Catalog = Catalog(
        units=(shared,),
        packages=(
            Package(name="zeta", units=(shared,)),
            Package(name="alpha", units=(shared,)),
        ),
        bundles=(),
    )

    assert list_packages(catalog=catalog) == ["alpha", "zeta"]


def test_list_bundles_returns_bundle_names_sorted() -> None:
    # Bundles are listed by name in a stable sorted order, independent of their
    # declaration order in the catalog (here zeta is declared before alpha).
    shared: Unit = Unit(kind="skill", name="alpha")
    catalog: Catalog = Catalog(
        units=(shared,),
        packages=(Package(name="pack", units=(shared,)),),
        bundles=(
            Bundle(name="zeta", packages=("pack",)),
            Bundle(name="alpha", packages=("pack",)),
        ),
    )

    assert list_bundles(catalog=catalog) == ["alpha", "zeta"]


def test_skill_unit_id_joins_kind_and_name() -> None:
    # The skill-unit id is the join key install status is keyed by; pin it here
    # so the "<kind>/<name>" format lives in exactly one module.
    assert skill_unit_id("make-pr") == "skill/make-pr"


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


def test_load_catalog_rejects_bundle_referencing_undeclared_package(
    tmp_path: Path,
) -> None:
    broken: Path = _write(
        tmp_path,
        '[[units]]\nkind = "skill"\nname = "make-pr"\n\n'
        '[[packages]]\nname = "real"\nunits = ["skill/make-pr"]\n\n'
        '[[bundles]]\nname = "wide"\npackages = ["ghost-package"]\n',
    )

    with pytest.raises(ValueError, match="ghost-package"):
        load_catalog(broken)


def test_real_seed_resolve_package_carries_declared_extras_and_units() -> None:
    # Smoke check against the shipped seed without hard-coding its full, growing
    # extras list (the seed curation is provisional): membership checks confirm a
    # named package resolves to its declared extras (the runtime support files
    # staged with it) and still carries its units, so resolution didn't drop
    # either tier. Exact extras order is pinned by the controlled-fixture test
    # test_load_catalog_parses_package_extras_in_declared_order, so this smoke
    # test does not re-pin it.
    catalog: Catalog = load_catalog(SEED)
    package: Package = resolve_package(catalog, "architect-pr")

    assert "schemas" in package.extras  # a known declared extra is carried
    assert "gates" in package.extras  # a second known extra is carried too
    assert Unit(kind="skill", name="make-pr") in package.units


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
