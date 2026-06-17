#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = ["click", "questionary", "rich"]
# ///
import os
import subprocess
import sys
from pathlib import Path
from typing import Final

import click

from catalog import Catalog, list_skills, load_catalog, skill_unit_id
from paths import CATALOG_PATH, CLAUDE_ROOT, REPO_ROOT, STATE_ROOT
from reconcile import ReconcilePlan, apply_skill_reconcile, plan_skill_reconcile
from state import State, load_state
from tui import launch_tui
from update import update_installed_skills

AT_VERSION: Final[str] = "0.2.0"


def _env_path(var: str, default: Path) -> Path:
    """One env-override rule shared by the source-root and catalog seams so they
    cannot drift: read var, else fall back to default. The e2e harness sets these
    vars to point the installer at a fixture tree."""
    override: str | None = os.environ.get(var)
    return Path(override) if override else default


def _source_root() -> Path:
    """Where skill sources are read from: AT_SOURCE_ROOT points a subprocess at a
    fixture tree, else the repo root. Reading REPO_ROOT here at call time keeps the
    seam monkeypatchable by tests."""
    return _env_path("AT_SOURCE_ROOT", REPO_ROOT)


def _catalog_path() -> Path:
    """Which catalog the non-interactive CLI loads: AT_CATALOG points a subprocess
    at a fixture catalog, else the repo's. Reading CATALOG_PATH here at call time
    keeps the seam monkeypatchable by tests."""
    return _env_path("AT_CATALOG", CATALOG_PATH)


def _run_update() -> int:
    """Fast-forward the repo when sourcing from the real checkout, then refresh only
    the installed skills whose upstream content changed, so `at update` is a single
    non-interactive sync."""
    source_root: Path = _source_root()
    # Only pull against the real repo checkout: an AT_SOURCE_ROOT override points the
    # update at a fixture tree that has no upstream remote to fast-forward.
    if source_root == REPO_ROOT:
        subprocess.run(["git", "pull", "--ff-only"], cwd=REPO_ROOT, check=True)
    catalog: Catalog = load_catalog(_catalog_path())
    state: State = load_state(STATE_ROOT)
    update_installed_skills(
        source_root=source_root,
        state_root=STATE_ROOT,
        claude_root=CLAUDE_ROOT,
        catalog=catalog,
        state=state,
    )
    return 0


def _reject_unknown_skills(names: list[str], catalog: Catalog) -> int | None:
    """Reject a --skill the catalog doesn't list before any reconcile runs, so a typo
    fails atomically instead of silently no-opping; names the unknowns on stderr and
    returns exit code 2, or None when every name is known."""
    known: frozenset[str] = frozenset(list_skills(catalog))
    unknown: list[str] = [name for name in names if name not in known]
    if not unknown:
        return None
    for name in unknown:
        print(f"error: unknown skill '{name}'", file=sys.stderr)
    print("Try 'at --help' for usage.", file=sys.stderr)
    return 2


def _reconcile_to(ticked: frozenset[str], *, catalog: Catalog, state: State) -> int:
    """The one apply path every scriptable install/uninstall shares, so reconcile
    wiring lives in one place."""
    plan: ReconcilePlan = plan_skill_reconcile(
        ticked=ticked, catalog=catalog, state=state
    )
    apply_skill_reconcile(
        plan=plan,
        source_root=_source_root(),
        state_root=STATE_ROOT,
        claude_root=CLAUDE_ROOT,
        state=state,
    )
    return 0


def _install_named_skills(names: list[str]) -> int:
    """Install every named skill without the TUI, so `at install --skill <name> ...`
    is a scriptable path that drives the same declarative reconcile the menu does.
    Install is additive: the named skills join whatever is already installed."""
    catalog: Catalog = load_catalog(_catalog_path())
    rejection: int | None = _reject_unknown_skills(names, catalog)
    if rejection is not None:
        return rejection
    state: State = load_state(STATE_ROOT)
    installed: set[str] = {
        name for name in list_skills(catalog) if skill_unit_id(name) in state.units
    }
    ticked: frozenset[str] = frozenset(installed | set(names))
    return _reconcile_to(ticked, catalog=catalog, state=state)


def _uninstall_named_skills(names: list[str]) -> int:
    """Remove every named skill without the TUI, so `at uninstall --skill <name> ...`
    is a scriptable path that drives the same declarative reconcile the menu does.
    Uninstall is subtractive: the named skills drop out of whatever is installed,
    and every other installed skill stays ticked and thus untouched."""
    catalog: Catalog = load_catalog(_catalog_path())
    rejection: int | None = _reject_unknown_skills(names, catalog)
    if rejection is not None:
        return rejection
    state: State = load_state(STATE_ROOT)
    installed: set[str] = {
        name for name in list_skills(catalog) if skill_unit_id(name) in state.units
    }
    ticked: frozenset[str] = frozenset(installed - set(names))
    return _reconcile_to(ticked, catalog=catalog, state=state)


@click.group(context_settings={"help_option_names": ["-h", "--help"]})
@click.version_option(
    AT_VERSION, "--version", prog_name="at", message="%(prog)s %(version)s"
)
def cli() -> None:
    """Manage agent-template skills from the CLI or an interactive menu."""


@cli.command()
@click.option("--skill", "skills", multiple=True, metavar="<name>")
@click.option("--all", "install_all", is_flag=True)
# Accepted so a scripted `install --all` can pass it, but it changes nothing: the
# --all path never opens the menu, so the flag never needs to reach the callback.
@click.option("--non-interactive", is_flag=True, expose_value=False)
def install(skills: tuple[str, ...], install_all: bool) -> int:
    """Install named skills (--skill/--all) without the menu, else open it."""
    if skills:
        return _install_named_skills(list(skills))
    if install_all:
        catalog_skills: list[str] = list_skills(load_catalog(_catalog_path()))
        return _install_named_skills(catalog_skills)
    return launch_tui()


@cli.command()
@click.option("--skill", "skills", multiple=True, metavar="<name>")
def uninstall(skills: tuple[str, ...]) -> int:
    """Uninstall the named skills; at least one --skill is required."""
    if not skills:
        raise click.UsageError("uninstall requires at least one --skill <name>")
    return _uninstall_named_skills(list(skills))


@cli.command()
def update() -> int:
    """Pull the repo, then refresh every installed skill from its updated source."""
    return _run_update()


def main(argv: list[str]) -> int:
    """The stable int-returning entry every test and the `at` wrapper call: run the
    click group without its process-exiting shell and translate the outcome to an exit
    code, so click owns parsing while callers keep a plain function boundary."""
    try:
        outcome: int | None = cli.main(args=argv, prog_name="at", standalone_mode=False)
    except click.exceptions.ClickException as click_error:
        # Non-standalone click re-raises usage/parse errors instead of exiting; show
        # the message on stderr ourselves and surface its code (2 for usage errors).
        click_error.show()
        return click_error.exit_code
    except click.exceptions.Exit as click_exit:
        return click_exit.exit_code
    except SystemExit as system_exit:
        return system_exit.code if isinstance(system_exit.code, int) else 0
    return outcome if isinstance(outcome, int) else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
