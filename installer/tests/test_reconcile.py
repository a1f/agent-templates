from pathlib import Path

from actions import install_agent, install_hook, install_rule, install_skill
from catalog import (
    Catalog,
    Package,
    Unit,
    agent_unit,
    agent_unit_id,
    hook_unit_id,
    rule_unit_id,
    skill_unit,
    skill_unit_id,
)
from reconcile import (
    ReconcilePlan,
    apply_agent_reconcile,
    apply_hook_reconcile,
    apply_rule_reconcile,
    apply_skill_reconcile,
    package_installed,
    plan_agent_reconcile,
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
        package_installed(catalog=catalog, name="pack", state=helper_uncredited) is False
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
