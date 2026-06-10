from catalog import Catalog, Unit
from reconcile import ReconcilePlan, plan_skill_reconcile
from state import State


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
