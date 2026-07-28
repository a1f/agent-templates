"""Tests for the prompt linter (a prompt tree -> the conventions its files violate).

The checker's contract is a CLI over whatever tree it is run in, so the test builds a
real fixture tree in tmp_path and runs the module as a subprocess — the way a gate
invokes it — rather than reaching for an internal entry point.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from typing import Final

SCRIPTS_DIR: Final[Path] = Path(__file__).resolve().parent.parent

# A tree that satisfies every convention the checker knows: the skill's name matches its
# directory and its description opens with "Use when", the agent carries all four keys
# with a name matching its file stem, and the rule declares the paths it governs.
CONFORMING_TREE: Final[dict[str, str]] = {
    "skills/demo/SKILL.md": (
        "---\n"
        "name: demo\n"
        "description: Use when testing the prompt linter.\n"
        "---\n"
        "\n"
        "# demo\n"
        "\n"
        "A conforming skill.\n"
    ),
    "agents/helper.md": (
        "---\n"
        "name: helper\n"
        "description: Helps with one step of a test fixture.\n"
        "tools: Read\n"
        "model: opus\n"
        "---\n"
        "\n"
        "# helper\n"
        "\n"
        "A conforming agent.\n"
    ),
    "rules/python.md": (
        '---\npaths: "**/*.py"\n---\n\n# Python Rules\n\nA conforming rule.\n'
    ),
}


def _write_conforming_tree(*, root: Path) -> None:
    for relative_path, content in CONFORMING_TREE.items():
        prompt: Path = root / relative_path
        prompt.parent.mkdir(parents=True, exist_ok=True)
        prompt.write_text(content)


def _run_prompt_lint(*, root: Path) -> subprocess.CompletedProcess[str]:
    """Runs the CLI the way a gate does: cwd is the tree, scripts/ is on the path."""
    environment: dict[str, str] = {**os.environ, "PYTHONPATH": str(SCRIPTS_DIR)}
    return subprocess.run(
        [sys.executable, "-m", "prompt_lint"],
        cwd=root,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )


def test_conforming_tree_exits_zero_with_no_output(tmp_path: Path) -> None:
    _write_conforming_tree(root=tmp_path)

    result: subprocess.CompletedProcess[str] = _run_prompt_lint(root=tmp_path)

    assert result.returncode == 0, f"prompt_lint failed: {result.stderr}"
    assert result.stdout == ""
