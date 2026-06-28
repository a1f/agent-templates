"""The interactive installer menu: the whole TUI concern (tab rendering, the
checkbox/confirm reconcile loop, and Esc handling) lives here so at.py stays the
CLI/entry dispatcher."""

import sys
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Final, Protocol

import questionary
from prompt_toolkit.key_binding import (
    KeyBindings,
    KeyBindingsBase,
    KeyPressEvent,
    merge_key_bindings,
)
from prompt_toolkit.keys import Keys
from rich.console import Console
from rich.panel import Panel

from catalog import (
    Catalog,
    Package,
    agent_unit_id,
    hook_unit_id,
    list_agents,
    list_hooks,
    list_packages,
    list_rules,
    list_skills,
    load_catalog,
    resolve_package,
    rule_unit_id,
    skill_unit_id,
    unit_id,
)
from paths import CATALOG_PATH, CLAUDE_ROOT, REPO_ROOT, STATE_ROOT
from reconcile import (
    ReconcilePlan,
    apply_agent_reconcile,
    apply_hook_reconcile,
    apply_rule_reconcile,
    apply_skill_reconcile,
    package_installed,
    plan_agent_reconcile,
    plan_hook_reconcile,
    plan_rule_reconcile,
    plan_skill_reconcile,
)
from state import State, load_state

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

MARKER_INSTALLED: Final[str] = "✅"
MARKER_NOT_INSTALLED: Final[str] = "❌"

HEADER_TEXT: Final[str] = "Agent Templates Installer"
NON_TTY_NOTICE: Final[str] = (
    "The interactive menu needs a terminal; run 'at install' in one to use it."
)
TAB_PLACEHOLDER: Final[str] = "(empty — populated in a later PR)"
MENU_CHOICES: Final[tuple[str, ...]] = (
    "Bundles",
    "Skills",
    "Agents",
    "Rules",
    "Hooks",
    "Exit",
)


# ---------------------------------------------------------------------------
# Interfaces
# ---------------------------------------------------------------------------


class _PlanFn(Protocol):
    """One unit kind's planner: diff a ticked selection into a reconcile plan."""

    def __call__(
        self, *, ticked: frozenset[str], catalog: Catalog, state: State
    ) -> ReconcilePlan: ...


class _ApplyFn(Protocol):
    """One unit kind's applier: carry out a reconcile plan and return new state."""

    def __call__(
        self,
        *,
        plan: ReconcilePlan,
        source_root: Path,
        state_root: Path,
        claude_root: Path,
        state: State,
    ) -> State: ...


# ---------------------------------------------------------------------------
# Data shape
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class _UnitTab:
    """The per-kind pieces every installed-unit tab varies over, so one generic
    runner drives them all from data instead of parallel branches."""

    names: Callable[[Catalog], list[str]]
    unit_id_of: Callable[[str], str]
    plan: _PlanFn
    apply: _ApplyFn
    select_prompt: str
    confirm_prompt: str


# ---------------------------------------------------------------------------
# Rendering
# ---------------------------------------------------------------------------


def _unit_rows(
    *,
    names: Callable[[Catalog], list[str]],
    unit_id_of: Callable[[str], str],
    catalog: Catalog,
    state: State,
) -> list[str]:
    """Pair each catalog unit with its on-disk install marker, the one row-rendering
    every installed-unit tab shares, keying install state by the unit id catalog.py
    owns."""
    installed: frozenset[str] = frozenset(state.units)
    return [
        (MARKER_INSTALLED if unit_id_of(name) in installed else MARKER_NOT_INSTALLED)
        + f" {name}"
        for name in names(catalog)
    ]


def skill_rows(*, catalog: Catalog, state: State) -> list[str]:
    """Pair each catalog skill with its on-disk install marker so the Skills tab
    renders status, keying install state by the unit id catalog.py owns."""
    return _unit_rows(
        names=list_skills, unit_id_of=skill_unit_id, catalog=catalog, state=state
    )


def agent_rows(*, catalog: Catalog, state: State) -> list[str]:
    """Pair each catalog agent with its on-disk install marker so the Agents tab
    renders status, keying install state by the unit id catalog.py owns."""
    return _unit_rows(
        names=list_agents, unit_id_of=agent_unit_id, catalog=catalog, state=state
    )


def rule_rows(*, catalog: Catalog, state: State) -> list[str]:
    """Pair each catalog rule with its on-disk install marker so the Rules tab
    renders status, keying install state by the unit id catalog.py owns."""
    return _unit_rows(
        names=list_rules, unit_id_of=rule_unit_id, catalog=catalog, state=state
    )


def hook_rows(*, catalog: Catalog, state: State) -> list[str]:
    """Pair each catalog hook with its on-disk install marker so the Hooks tab
    renders status, keying install state by the unit id catalog.py owns."""
    return _unit_rows(
        names=list_hooks, unit_id_of=hook_unit_id, catalog=catalog, state=state
    )


def package_rows(*, catalog: Catalog, state: State) -> list[str]:
    """Pair each catalog package with its refcount-derived install marker (via
    package_installed) so the Packages tab renders status, and show the member
    units the package pulls in alongside it."""
    rows: list[str] = []
    for name in list_packages(catalog=catalog):
        package: Package = resolve_package(catalog, name)
        marker: str = (
            MARKER_INSTALLED
            if package_installed(catalog=catalog, name=name, state=state)
            else MARKER_NOT_INSTALLED
        )
        members: str = ", ".join(unit_id(unit) for unit in package.units)
        rows.append(f"{marker} {name}  ({members})")
    return rows


# ---------------------------------------------------------------------------
# Data instances
# ---------------------------------------------------------------------------

_SKILLS_TAB: Final[_UnitTab] = _UnitTab(
    names=list_skills,
    unit_id_of=skill_unit_id,
    plan=plan_skill_reconcile,
    apply=apply_skill_reconcile,
    select_prompt="Select installed skills",
    confirm_prompt="Apply skill changes?",
)

_AGENTS_TAB: Final[_UnitTab] = _UnitTab(
    names=list_agents,
    unit_id_of=agent_unit_id,
    plan=plan_agent_reconcile,
    apply=apply_agent_reconcile,
    select_prompt="Select installed agents",
    confirm_prompt="Apply agent changes?",
)

_RULES_TAB: Final[_UnitTab] = _UnitTab(
    names=list_rules,
    unit_id_of=rule_unit_id,
    plan=plan_rule_reconcile,
    apply=apply_rule_reconcile,
    select_prompt="Select installed rules",
    confirm_prompt="Apply rule changes?",
)

_HOOKS_TAB: Final[_UnitTab] = _UnitTab(
    names=list_hooks,
    unit_id_of=hook_unit_id,
    plan=plan_hook_reconcile,
    apply=apply_hook_reconcile,
    select_prompt="Select installed hooks",
    confirm_prompt="Apply hook changes?",
)

_UNIT_TABS: Final[dict[str, _UnitTab]] = {
    "Skills": _SKILLS_TAB,
    "Agents": _AGENTS_TAB,
    "Rules": _RULES_TAB,
    "Hooks": _HOOKS_TAB,
}


# ---------------------------------------------------------------------------
# Implementation
# ---------------------------------------------------------------------------


def abort_on_esc(question: questionary.Question) -> questionary.Question:
    """Let Esc abort a prompt exactly like Ctrl-C, so a user can back out with the
    key they reach for first; returns the question for chaining."""
    # Both real questionary Questions and the test doubles that stub only .ask() cross
    # this seam; a double carries no prompt_toolkit Application, so there is no binding
    # to register — hand it straight back rather than blow up on the missing attribute.
    if getattr(question, "application", None) is None:
        return question
    # A confirm's existing bindings are a _MergedKeyBindings with no .add, unlike a
    # checkbox/select's concrete KeyBindings — so register Escape on a fresh KeyBindings
    # and merge it ahead of whatever the prompt already had, leaving those intact.
    escape: KeyBindings = KeyBindings()

    @escape.add(Keys.Escape, eager=True)
    def _(event: KeyPressEvent) -> None:
        event.app.exit(exception=KeyboardInterrupt, style="class:aborting")

    existing: KeyBindingsBase | None = question.application.key_bindings
    merged: list[KeyBindingsBase] = [escape] if existing is None else [existing, escape]
    question.application.key_bindings = merge_key_bindings(merged)
    return question


def _run_unit_tab(*, tab: _UnitTab, console: Console) -> None:
    """Drive one installed-units tab end to end — render status, take the ticked
    selection, plan the diff, confirm, apply, then re-render — the body every
    installed-unit tab shares, differing only by the functions and prompts in `tab`."""
    catalog: Catalog = load_catalog(CATALOG_PATH)
    state: State = load_state(STATE_ROOT)
    for row in _unit_rows(
        names=tab.names, unit_id_of=tab.unit_id_of, catalog=catalog, state=state
    ):
        console.print(row, markup=False)
    installed: frozenset[str] = frozenset(state.units)
    choices: list[questionary.Choice] = [
        questionary.Choice(name, checked=tab.unit_id_of(name) in installed)
        for name in tab.names(catalog)
    ]
    ticked: list[str] | None = abort_on_esc(
        questionary.checkbox(tab.select_prompt, choices=choices)
    ).ask()
    if ticked is None:
        return
    plan: ReconcilePlan = tab.plan(
        ticked=frozenset(ticked), catalog=catalog, state=state
    )
    if plan.is_empty:
        return
    confirmed: bool | None = abort_on_esc(questionary.confirm(tab.confirm_prompt)).ask()
    if not confirmed:
        return
    state = tab.apply(
        plan=plan,
        source_root=REPO_ROOT,
        state_root=STATE_ROOT,
        claude_root=CLAUDE_ROOT,
        state=state,
    )
    for row in _unit_rows(
        names=tab.names, unit_id_of=tab.unit_id_of, catalog=catalog, state=state
    ):
        console.print(row, markup=False)


def launch_tui() -> int:
    """Bail out on non-interactive stdin: questionary's prompt would otherwise
    block forever waiting on input no CI session can supply."""
    console: Console = Console()
    console.print(Panel(HEADER_TEXT, expand=False))
    if not sys.stdin.isatty():
        console.print(NON_TTY_NOTICE)
        return 0
    try:
        while True:
            choice: str | None = abort_on_esc(
                questionary.select("Select a tab", choices=list(MENU_CHOICES))
            ).ask()
            if choice is None or choice == "Exit":
                return 0
            tab: _UnitTab | None = _UNIT_TABS.get(choice)
            if tab is not None:
                _run_unit_tab(tab=tab, console=console)
                continue
            console.print(TAB_PLACEHOLDER)
    except KeyboardInterrupt:
        return 0
