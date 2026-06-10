from pathlib import Path

from actions import install_skill
from catalog import Catalog, Unit, skill_unit_id
from reconcile import ReconcilePlan, apply_skill_reconcile, plan_skill_reconcile
from state import State, load_state


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
