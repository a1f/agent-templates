from pathlib import Path

from actions import (
    install_agent,
    install_hook,
    install_package,
    install_rule,
    install_skill,
)
from catalog import (
    Bundle,
    Catalog,
    Package,
    Unit,
    agent_unit,
    agent_unit_id,
    hook_unit_id,
    load_catalog,
    rule_unit_id,
    skill_unit,
    skill_unit_id,
)
from reconcile import (
    ReconcilePlan,
    apply_agent_reconcile,
    apply_bundle_reconcile,
    apply_hook_reconcile,
    apply_package_reconcile,
    apply_rule_reconcile,
    apply_skill_reconcile,
    bundle_installed,
    package_installed,
    plan_agent_reconcile,
    plan_bundle_reconcile,
    plan_hook_reconcile,
    plan_package_reconcile,
    plan_rule_reconcile,
    plan_skill_reconcile,
)
from state import State, load_state


def test_package_installed_requires_every_declared_unit_to_credit_the_package() -> None:
    catalog: Catalog = Catalog(
        units=(skill_unit("alpha"), agent_unit("helper")),
        packages=(
            Package(name="pack", units=(skill_unit("alpha"), agent_unit("helper"))),
        ),
        bundles=(),
    )

    # Both declared units credit "pack" in the refcount map, and units stays empty so
    # the predicate can only be reading requesters bookkeeping, not loose unit presence.
    fully_credited: State = State(
        version=1,
        units={},
        requesters={
            skill_unit_id("alpha"): ("pack",),
            agent_unit_id("helper"): ("pack",),
        },
    )
    assert package_installed(catalog=catalog, name="pack", state=fully_credited) is True

    # Drop the helper's credit: one declared unit no longer names "pack", so the
    # package is not fully installed even though the other unit still credits it.
    helper_uncredited: State = State(
        version=1,
        units={},
        requesters={skill_unit_id("alpha"): ("pack",)},
    )
    assert (
        package_installed(catalog=catalog, name="pack", state=helper_uncredited)
        is False
    )


def test_bundle_installed_requires_every_declared_package_to_be_installed() -> None:
    catalog: Catalog = Catalog(
        units=(skill_unit("alpha"), agent_unit("helper")),
        packages=(
            Package(name="pack-a", units=(skill_unit("alpha"),)),
            Package(name="pack-b", units=(agent_unit("helper"),)),
        ),
        bundles=(
            Bundle(name="full", packages=("pack-a", "pack-b")),
            Bundle(name="empty", packages=()),
        ),
    )

    # Every unit of both member packages credits its package, so both packages read
    # installed and the bundle is installed. units stays empty so the predicate can
    # only be reading requesters bookkeeping, not loose unit presence.
    fully_installed: State = State(
        version=1,
        units={},
        requesters={
            skill_unit_id("alpha"): ("pack-a",),
            agent_unit_id("helper"): ("pack-b",),
        },
    )
    assert bundle_installed(catalog=catalog, name="full", state=fully_installed) is True

    # Drop pack-b's credit: one member package is no longer installed, so the bundle
    # is not fully installed even though pack-a still is.
    pack_b_uninstalled: State = State(
        version=1,
        units={},
        requesters={skill_unit_id("alpha"): ("pack-a",)},
    )
    assert (
        bundle_installed(catalog=catalog, name="full", state=pack_b_uninstalled)
        is False
    )

    # A bundle that declares no packages is never vacuously installed.
    assert (
        bundle_installed(catalog=catalog, name="empty", state=fully_installed) is False
    )


def test_plan_classifies_packages_by_refcount_install_not_unit_presence() -> None:
    catalog: Catalog = Catalog(
        units=(skill_unit("alpha"), skill_unit("beta")),
        packages=(
            Package(name="pack-a", units=(skill_unit("alpha"),)),
            Package(name="pack-b", units=(skill_unit("beta"),)),
        ),
        bundles=(),
    )

    # pack-a's only unit credits "pack-a", so the refcount predicate reads pack-a as
    # installed; pack-b stays uncredited and so is not installed. units is empty so the
    # diff can only be reading requesters bookkeeping, not loose unit presence.
    state: State = State(
        version=1,
        units={},
        requesters={skill_unit_id("alpha"): ("pack-a",)},
    )

    plan: ReconcilePlan = plan_package_reconcile(
        ticked=frozenset({"pack-b"}), catalog=catalog, state=state
    )

    assert plan.to_install == ("pack-b",)
    assert plan.to_remove == ("pack-a",)


def test_plan_classifies_bundles_by_installed_state_not_unit_presence() -> None:
    catalog: Catalog = Catalog(
        units=(skill_unit("alpha"), skill_unit("beta")),
        packages=(
            Package(name="pack-a", units=(skill_unit("alpha"),)),
            Package(name="pack-b", units=(skill_unit("beta"),)),
        ),
        bundles=(
            Bundle(name="bundle-a", packages=("pack-a",)),
            Bundle(name="bundle-b", packages=("pack-b",)),
        ),
    )

    # pack-a's unit credits "pack-a", so bundle-a reads installed via bundle_installed;
    # bundle-b's package stays uncredited and so is not installed. units is empty so the
    # diff can only be reading requesters bookkeeping, not loose unit presence.
    state: State = State(
        version=1,
        units={},
        requesters={skill_unit_id("alpha"): ("pack-a",)},
    )

    plan: ReconcilePlan = plan_bundle_reconcile(
        ticked=frozenset({"bundle-b"}), catalog=catalog, state=state
    )

    assert plan.to_install == ("bundle-b",)
    assert plan.to_remove == ("bundle-a",)


def test_plan_classifies_skills_by_tick_against_installed_state() -> None:
    catalog: Catalog = Catalog(
        units=(
            Unit(kind="skill", name="alpha"),
            Unit(kind="skill", name="beta"),
            Unit(kind="skill", name="gamma"),
        ),
        packages=(),
        bundles=(),
    )
    state: State = State(version=1, units={"skill/beta": "hash", "skill/gamma": "hash"})
    ticked: frozenset[str] = frozenset({"alpha", "gamma"})

    plan: ReconcilePlan = plan_skill_reconcile(
        ticked=ticked, catalog=catalog, state=state
    )

    assert plan.to_install == ("alpha",)
    assert plan.to_remove == ("beta",)


def test_plan_classifies_agents_by_tick_against_installed_state() -> None:
    catalog: Catalog = Catalog(
        units=(
            Unit(kind="agent", name="alpha"),
            Unit(kind="agent", name="beta"),
            Unit(kind="agent", name="gamma"),
        ),
        packages=(),
        bundles=(),
    )
    state: State = State(version=1, units={"agent/beta": "hash", "agent/gamma": "hash"})
    ticked: frozenset[str] = frozenset({"alpha", "gamma"})

    plan: ReconcilePlan = plan_agent_reconcile(
        ticked=ticked, catalog=catalog, state=state
    )

    assert plan.to_install == ("alpha",)
    assert plan.to_remove == ("beta",)


def test_plan_classifies_rules_by_tick_against_installed_state() -> None:
    catalog: Catalog = Catalog(
        units=(
            Unit(kind="rule", name="alpha"),
            Unit(kind="rule", name="beta"),
            Unit(kind="rule", name="gamma"),
        ),
        packages=(),
        bundles=(),
    )
    state: State = State(version=1, units={"rule/beta": "hash", "rule/gamma": "hash"})
    ticked: frozenset[str] = frozenset({"alpha", "gamma"})

    plan: ReconcilePlan = plan_rule_reconcile(
        ticked=ticked, catalog=catalog, state=state
    )

    assert plan.to_install == ("alpha",)
    assert plan.to_remove == ("beta",)


def test_plan_classifies_hooks_by_tick_against_installed_state() -> None:
    catalog: Catalog = Catalog(
        units=(
            Unit(kind="hook", name="alpha"),
            Unit(kind="hook", name="beta"),
            Unit(kind="hook", name="gamma"),
        ),
        packages=(),
        bundles=(),
    )
    state: State = State(version=1, units={"hook/beta": "hash", "hook/gamma": "hash"})
    ticked: frozenset[str] = frozenset({"alpha", "gamma"})

    plan: ReconcilePlan = plan_hook_reconcile(
        ticked=ticked, catalog=catalog, state=state
    )

    assert plan.to_install == ("alpha",)
    assert plan.to_remove == ("beta",)


def test_apply_installs_planned_skills_and_uninstalls_removed_ones(
    tmp_path: Path,
) -> None:
    source_root: Path = tmp_path / "repo"
    for name in ("old-skill", "new-skill"):
        skill_source: Path = source_root / "skills" / name
        skill_source.mkdir(parents=True)
        (skill_source / "SKILL.md").write_text(f"# {name}\n", encoding="utf-8")

    state_root: Path = tmp_path / "at"
    claude_root: Path = tmp_path / "claude"
    installed_state: State = install_skill(
        name="old-skill",
        source_root=source_root,
        state_root=state_root,
        claude_root=claude_root,
        state=State(version=1, units={}),
    )

    plan: ReconcilePlan = ReconcilePlan(
        to_install=("new-skill",), to_remove=("old-skill",)
    )
    result: State = apply_skill_reconcile(
        plan=plan,
        source_root=source_root,
        state_root=state_root,
        claude_root=claude_root,
        state=installed_state,
    )

    persisted: State = load_state(state_root)
    new_id: str = skill_unit_id("new-skill")
    old_id: str = skill_unit_id("old-skill")

    assert (claude_root / "skills" / "new-skill").is_symlink()
    assert (state_root / "staged" / "skill" / "new-skill").is_dir()
    assert new_id in result.units
    assert new_id in persisted.units

    assert not (claude_root / "skills" / "old-skill").is_symlink()
    assert not (state_root / "staged" / "skill" / "old-skill").exists()
    assert old_id not in result.units
    assert old_id not in persisted.units


def test_apply_installs_planned_agents_and_uninstalls_removed_ones(
    tmp_path: Path,
) -> None:
    source_root: Path = tmp_path / "repo"
    agents_source: Path = source_root / "agents"
    agents_source.mkdir(parents=True)
    for name in ("old-agent", "new-agent"):
        (agents_source / f"{name}.md").write_text(f"# {name}\n", encoding="utf-8")

    state_root: Path = tmp_path / "at"
    claude_root: Path = tmp_path / "claude"
    installed_state: State = install_agent(
        name="old-agent",
        source_root=source_root,
        state_root=state_root,
        claude_root=claude_root,
        state=State(version=1, units={}),
    )

    plan: ReconcilePlan = ReconcilePlan(
        to_install=("new-agent",), to_remove=("old-agent",)
    )
    result: State = apply_agent_reconcile(
        plan=plan,
        source_root=source_root,
        state_root=state_root,
        claude_root=claude_root,
        state=installed_state,
    )

    persisted: State = load_state(state_root)
    new_id: str = agent_unit_id("new-agent")
    old_id: str = agent_unit_id("old-agent")

    assert (claude_root / "agents" / "new-agent.md").is_symlink()
    assert (state_root / "staged" / "agent" / "new-agent").is_file()
    assert new_id in result.units
    assert new_id in persisted.units

    assert not (claude_root / "agents" / "old-agent.md").is_symlink()
    assert not (state_root / "staged" / "agent" / "old-agent").exists()
    assert old_id not in result.units
    assert old_id not in persisted.units


def test_apply_installs_planned_rules_and_uninstalls_removed_ones(
    tmp_path: Path,
) -> None:
    source_root: Path = tmp_path / "repo"
    rules_source: Path = source_root / "rules"
    rules_source.mkdir(parents=True)
    for name in ("old-rule", "new-rule"):
        (rules_source / f"{name}.md").write_text(f"# {name}\n", encoding="utf-8")

    state_root: Path = tmp_path / "at"
    claude_root: Path = tmp_path / "claude"
    installed_state: State = install_rule(
        name="old-rule",
        source_root=source_root,
        state_root=state_root,
        claude_root=claude_root,
        state=State(version=1, units={}),
    )

    plan: ReconcilePlan = ReconcilePlan(
        to_install=("new-rule",), to_remove=("old-rule",)
    )
    result: State = apply_rule_reconcile(
        plan=plan,
        source_root=source_root,
        state_root=state_root,
        claude_root=claude_root,
        state=installed_state,
    )

    persisted: State = load_state(state_root)
    new_id: str = rule_unit_id("new-rule")
    old_id: str = rule_unit_id("old-rule")

    assert (claude_root / "rules" / "new-rule.md").is_symlink()
    assert (state_root / "staged" / "rule" / "new-rule").is_file()
    assert new_id in result.units
    assert new_id in persisted.units

    assert not (claude_root / "rules" / "old-rule.md").is_symlink()
    assert not (state_root / "staged" / "rule" / "old-rule").exists()
    assert old_id not in result.units
    assert old_id not in persisted.units


def test_apply_installs_planned_hooks_and_uninstalls_removed_ones(
    tmp_path: Path,
) -> None:
    source_root: Path = tmp_path / "repo"
    hooks_source: Path = source_root / "hooks"
    hooks_source.mkdir(parents=True)
    for name in ("old-hook", "new-hook"):
        (hooks_source / f"{name}.sh").write_text(
            f"#!/usr/bin/env bash\necho {name}\n", encoding="utf-8"
        )

    state_root: Path = tmp_path / "at"
    claude_root: Path = tmp_path / "claude"
    installed_state: State = install_hook(
        name="old-hook",
        source_root=source_root,
        state_root=state_root,
        claude_root=claude_root,
        state=State(version=1, units={}),
    )

    plan: ReconcilePlan = ReconcilePlan(
        to_install=("new-hook",), to_remove=("old-hook",)
    )
    result: State = apply_hook_reconcile(
        plan=plan,
        source_root=source_root,
        state_root=state_root,
        claude_root=claude_root,
        state=installed_state,
    )

    persisted: State = load_state(state_root)
    new_id: str = hook_unit_id("new-hook")
    old_id: str = hook_unit_id("old-hook")

    assert (claude_root / "hooks" / "new-hook.sh").is_symlink()
    assert (state_root / "staged" / "hook" / "new-hook").is_file()
    assert new_id in result.units
    assert new_id in persisted.units

    assert not (claude_root / "hooks" / "old-hook.sh").is_symlink()
    assert not (state_root / "staged" / "hook" / "old-hook").exists()
    assert old_id not in result.units
    assert old_id not in persisted.units


def test_apply_package_reconcile_installs_added_and_removes_dropped_packages(
    tmp_path: Path,
) -> None:
    source_root: Path = tmp_path / "repo"
    for skill_name in ("alpha", "beta"):
        skill_source: Path = source_root / "skills" / skill_name
        skill_source.mkdir(parents=True)
        (skill_source / "SKILL.md").write_text(
            f"# {skill_name} Skill\n", encoding="utf-8"
        )

    # Two single-unit packages, loaded through the real boundary so the package
    # reconcile resolves each package's member unit exactly as production will.
    catalog_body: str = """
[[units]]
kind = "skill"
name = "alpha"

[[units]]
kind = "skill"
name = "beta"

[[packages]]
name = "pack-a"
units = ["skill/alpha"]

[[packages]]
name = "pack-b"
units = ["skill/beta"]

[[bundles]]
name = "everything"
packages = ["pack-a", "pack-b"]
"""
    catalog_path: Path = tmp_path / "catalog.toml"
    catalog_path.write_text(catalog_body, encoding="utf-8")
    catalog: Catalog = load_catalog(catalog_path)

    state_root: Path = tmp_path / "at"
    claude_root: Path = tmp_path / "claude"

    # Pre-install pack-a so the plan has a real package to drop while it adds pack-b.
    installed_state: State = install_package(
        name="pack-a",
        catalog=catalog,
        source_root=source_root,
        state_root=state_root,
        claude_root=claude_root,
        state=State(version=1, units={}),
    )

    plan: ReconcilePlan = ReconcilePlan(to_install=("pack-b",), to_remove=("pack-a",))
    result: State = apply_package_reconcile(
        plan=plan,
        catalog=catalog,
        source_root=source_root,
        state_root=state_root,
        claude_root=claude_root,
        state=installed_state,
    )

    # pack-b is now installed: its unit is recorded, credits pack-b, and is live.
    assert skill_unit_id("beta") in result.units
    assert result.requesters[skill_unit_id("beta")] == ("pack-b",)
    assert (claude_root / "skills" / "beta").is_symlink()

    # pack-a is now removed: its unit is gone from state and from disk.
    assert skill_unit_id("alpha") not in result.units
    assert not (claude_root / "skills" / "alpha").exists()


def test_apply_bundle_reconcile_installs_a_newly_ticked_bundles_packages(
    tmp_path: Path,
) -> None:
    source_root: Path = tmp_path / "repo"
    skill_source: Path = source_root / "skills" / "alpha"
    skill_source.mkdir(parents=True)
    (skill_source / "SKILL.md").write_text("# alpha Skill\n", encoding="utf-8")

    # A bundle over one package over one skill, loaded through the real boundary so the
    # bundle reconcile resolves the member package and its unit exactly as production.
    catalog_body: str = """
[[units]]
kind = "skill"
name = "alpha"

[[packages]]
name = "pack-a"
units = ["skill/alpha"]

[[bundles]]
name = "bundle-a"
packages = ["pack-a"]
"""
    catalog_path: Path = tmp_path / "catalog.toml"
    catalog_path.write_text(catalog_body, encoding="utf-8")
    catalog: Catalog = load_catalog(catalog_path)

    state_root: Path = tmp_path / "at"
    claude_root: Path = tmp_path / "claude"

    plan: ReconcilePlan = ReconcilePlan(to_install=("bundle-a",), to_remove=())
    result: State = apply_bundle_reconcile(
        plan=plan,
        ticked=frozenset({"bundle-a"}),
        catalog=catalog,
        source_root=source_root,
        state_root=state_root,
        claude_root=claude_root,
        state=State(version=1, units={}),
    )

    persisted: State = load_state(state_root)
    alpha_id: str = skill_unit_id("alpha")

    # Installing bundle-a places its member package's unit: recorded in state (and
    # persisted), credited to the package that pulled it in, and linked live — so the
    # bundle tier delegates to the tested package engine rather than reimplementing it.
    assert alpha_id in result.units
    assert alpha_id in persisted.units
    assert result.requesters[alpha_id] == ("pack-a",)
    assert (claude_root / "skills" / "alpha").is_symlink()


def test_apply_bundle_reconcile_keeps_a_package_shared_by_a_still_ticked_bundle(
    tmp_path: Path,
) -> None:
    source_root: Path = tmp_path / "repo"
    for skill_name in ("shared", "only-a", "only-b"):
        skill_source: Path = source_root / "skills" / skill_name
        skill_source.mkdir(parents=True)
        (skill_source / "SKILL.md").write_text(f"# {skill_name}\n", encoding="utf-8")

    # Two bundles overlapping on pkg-shared; each also carries its own exclusive
    # package. Loaded through the real boundary so the bundle reconcile resolves the
    # bundle->package->unit chain exactly as production will.
    catalog_body: str = """
[[units]]
kind = "skill"
name = "shared"

[[units]]
kind = "skill"
name = "only-a"

[[units]]
kind = "skill"
name = "only-b"

[[packages]]
name = "pkg-shared"
units = ["skill/shared"]

[[packages]]
name = "pkg-a"
units = ["skill/only-a"]

[[packages]]
name = "pkg-b"
units = ["skill/only-b"]

[[bundles]]
name = "bundle-x"
packages = ["pkg-shared", "pkg-a"]

[[bundles]]
name = "bundle-y"
packages = ["pkg-shared", "pkg-b"]
"""
    catalog_path: Path = tmp_path / "catalog.toml"
    catalog_path.write_text(catalog_body, encoding="utf-8")
    catalog: Catalog = load_catalog(catalog_path)

    state_root: Path = tmp_path / "at"
    claude_root: Path = tmp_path / "claude"

    # Pre-install every member package so both bundles read installed before the diff.
    state: State = State(version=1, units={})
    for package_name in ("pkg-shared", "pkg-a", "pkg-b"):
        state = install_package(
            name=package_name,
            catalog=catalog,
            source_root=source_root,
            state_root=state_root,
            claude_root=claude_root,
            state=state,
        )

    # Untick bundle-y while bundle-x stays ticked: bundle-y's packages are
    # {pkg-shared, pkg-b}, but pkg-shared is kept by still-ticked bundle-x, so only
    # pkg-b is reclaimed.
    plan: ReconcilePlan = ReconcilePlan(to_install=(), to_remove=("bundle-y",))
    result: State = apply_bundle_reconcile(
        plan=plan,
        ticked=frozenset({"bundle-x"}),
        catalog=catalog,
        source_root=source_root,
        state_root=state_root,
        claude_root=claude_root,
        state=state,
    )

    shared_id: str = skill_unit_id("shared")
    only_b_id: str = skill_unit_id("only-b")

    # pkg-shared survives on bundle-x's claim: its unit stays recorded, credited, live.
    assert shared_id in result.units
    assert result.requesters[shared_id] == ("pkg-shared",)
    assert (claude_root / "skills" / "shared").is_symlink()

    # pkg-b is reclaimed: its exclusive unit is gone from state and from disk.
    assert only_b_id not in result.units
    assert not (claude_root / "skills" / "only-b").exists()
