"""Tests for the prompt linter (a prompt tree -> the conventions its files violate).

The checker's contract is a CLI over whatever tree it is run in, so the test builds a
real fixture tree in tmp_path and runs the module as a subprocess — the way a gate
invokes it — rather than reaching for an internal entry point.
"""

from __future__ import annotations

import os
import re
import subprocess
import sys
from collections.abc import Mapping
from pathlib import Path
from typing import Final

SCRIPTS_DIR: Final[Path] = Path(__file__).resolve().parent.parent

# A diagnostic names the offending file and the line it was found on, so an editor or a
# CI annotation can jump straight there: `path:line: message`.
DIAGNOSTIC_LINE: Final[re.Pattern[str]] = re.compile(r"^\S+?:\d+: .+$")

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


# One skill per way the skill frontmatter rules can break, so each skill carries exactly
# one violation: no frontmatter at all (and so no name), no description, a name that
# disagrees with its directory, and a description that does not open with "Use when".
OFFENDING_SKILLS: Final[dict[str, str]] = {
    "skills/no-frontmatter/SKILL.md": "# no-frontmatter\n\nA skill that never opens.\n",
    "skills/no-description/SKILL.md": (
        "---\nname: no-description\n---\n\n# no-description\n\nA skill with no blurb.\n"
    ),
    "skills/wrong-name/SKILL.md": (
        "---\n"
        "name: mismatched\n"
        "description: Use when the name disagrees with the directory.\n"
        "---\n"
        "\n"
        "# wrong-name\n"
    ),
    "skills/vague-description/SKILL.md": (
        "---\n"
        "name: vague-description\n"
        "description: Lints prompt files, sometimes.\n"
        "---\n"
        "\n"
        "# vague-description\n"
    ),
}


# One agent per way the agent frontmatter rules can break, so each agent carries exactly
# one violation: a missing 'tools'/'model' pair, and a name that disagrees with the file
# stem — an agent is named after its file, not after the directory it sits in.
OFFENDING_AGENTS: Final[dict[str, str]] = {
    "agents/missing-keys.md": (
        "---\n"
        "name: missing-keys\n"
        "description: Runs without declaring its tools or its model.\n"
        "---\n"
        "\n"
        "# missing-keys\n"
    ),
    "agents/mismatched-stem.md": (
        "---\n"
        "name: renamed\n"
        "description: Answers to a name its own file does not carry.\n"
        "tools: Read\n"
        "model: opus\n"
        "---\n"
        "\n"
        "# mismatched-stem\n"
    ),
}


# One rule per way the sole rule convention can break, so each rule carries exactly one
# violation: no frontmatter at all, and frontmatter that opens without declaring the
# 'paths' it governs. A rule answers to nothing else — no 'name', no 'description'.
OFFENDING_RULES: Final[dict[str, str]] = {
    "rules/no-frontmatter.md": "# no-frontmatter\n\nA rule that never opens.\n",
    "rules/unscoped.md": (
        "---\n"
        "applies_to: everything\n"
        "---\n"
        "\n"
        "# unscoped\n"
        "\n"
        "A rule that never says which files it governs.\n"
    ),
}


# A skill that breaks nothing but its own length. The count sits far past the limit
# rather than one line over it, so a diagnostic quoting the file's length cannot be
# confused with one that merely points at the first line past the limit.
OVERSIZED_SKILL_PATH: Final[str] = "skills/sprawling/SKILL.md"
OVERSIZED_SKILL_LINES: Final[int] = 617
LINE_COUNT: Final[re.Pattern[str]] = re.compile(rf"\b{OVERSIZED_SKILL_LINES}\b")


def _write_prompts(*, root: Path, prompts: Mapping[str, str]) -> None:
    for relative_path, content in prompts.items():
        prompt: Path = root / relative_path
        prompt.parent.mkdir(parents=True, exist_ok=True)
        prompt.write_text(content)


def _write_conforming_tree(*, root: Path) -> None:
    _write_prompts(root=root, prompts=CONFORMING_TREE)


def _oversized_skill_prompt(*, lines: int) -> dict[str, str]:
    """A skill with clean frontmatter whose body runs it to exactly `lines` lines."""
    opening: list[str] = [
        "---",
        "name: sprawling",
        "description: Use when a skill outgrows what a reader will hold.",
        "---",
        "",
        "# sprawling",
        "",
    ]
    body: list[str] = [
        f"Paragraph {paragraph}, one more thing this skill also explains."
        for paragraph in range(lines - len(opening))
    ]
    return {OVERSIZED_SKILL_PATH: "\n".join([*opening, *body]) + "\n"}


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


def test_offending_skill_frontmatter_is_reported_with_path_and_line(
    tmp_path: Path,
) -> None:
    _write_conforming_tree(root=tmp_path)
    _write_prompts(root=tmp_path, prompts=OFFENDING_SKILLS)

    result: subprocess.CompletedProcess[str] = _run_prompt_lint(root=tmp_path)

    assert result.returncode == 1, f"expected a failing lint, got: {result.stderr}"
    reported_lines: list[str] = result.stdout.splitlines()
    assert reported_lines, f"expected a diagnostic per violation: {result.stderr}"
    for reported_line in reported_lines:
        assert DIAGNOSTIC_LINE.match(reported_line) is not None, (
            f"not a `path:line: message` diagnostic: {reported_line!r}"
        )
    for offending_path in OFFENDING_SKILLS:
        assert any(offending_path in line for line in reported_lines), (
            f"{offending_path} broke a skill rule unreported: {result.stdout!r}"
        )
    for conforming_path in CONFORMING_TREE:
        assert conforming_path not in result.stdout, (
            f"{conforming_path} conforms but was reported: {result.stdout!r}"
        )


def test_offending_agent_frontmatter_is_reported_with_path_and_line(
    tmp_path: Path,
) -> None:
    _write_conforming_tree(root=tmp_path)
    _write_prompts(root=tmp_path, prompts=OFFENDING_AGENTS)

    result: subprocess.CompletedProcess[str] = _run_prompt_lint(root=tmp_path)

    assert result.returncode == 1, f"expected a failing lint, got: {result.stderr}"
    reported_lines: list[str] = result.stdout.splitlines()
    assert reported_lines, f"expected a diagnostic per violation: {result.stderr}"
    for reported_line in reported_lines:
        assert DIAGNOSTIC_LINE.match(reported_line) is not None, (
            f"not a `path:line: message` diagnostic: {reported_line!r}"
        )
    for offending_path in OFFENDING_AGENTS:
        assert any(offending_path in line for line in reported_lines), (
            f"{offending_path} broke an agent rule unreported: {result.stdout!r}"
        )
    for conforming_path in CONFORMING_TREE:
        assert conforming_path not in result.stdout, (
            f"{conforming_path} conforms but was reported: {result.stdout!r}"
        )


def test_rule_without_paths_frontmatter_is_reported_with_path_and_line(
    tmp_path: Path,
) -> None:
    _write_conforming_tree(root=tmp_path)
    _write_prompts(root=tmp_path, prompts=OFFENDING_RULES)

    result: subprocess.CompletedProcess[str] = _run_prompt_lint(root=tmp_path)

    assert result.returncode == 1, f"expected a failing lint, got: {result.stderr}"
    reported_lines: list[str] = result.stdout.splitlines()
    assert reported_lines, f"expected a diagnostic per violation: {result.stderr}"
    for reported_line in reported_lines:
        assert DIAGNOSTIC_LINE.match(reported_line) is not None, (
            f"not a `path:line: message` diagnostic: {reported_line!r}"
        )
    for offending_path in OFFENDING_RULES:
        assert any(offending_path in line for line in reported_lines), (
            f"{offending_path} declares no paths unreported: {result.stdout!r}"
        )
    for conforming_path in CONFORMING_TREE:
        assert conforming_path not in result.stdout, (
            f"{conforming_path} conforms but was reported: {result.stdout!r}"
        )


def test_overlong_skill_is_reported_with_its_line_count(tmp_path: Path) -> None:
    _write_conforming_tree(root=tmp_path)
    _write_prompts(
        root=tmp_path, prompts=_oversized_skill_prompt(lines=OVERSIZED_SKILL_LINES)
    )

    result: subprocess.CompletedProcess[str] = _run_prompt_lint(root=tmp_path)

    assert result.returncode == 1, f"expected a failing lint, got: {result.stderr}"
    reported_lines: list[str] = result.stdout.splitlines()
    assert reported_lines, f"expected a diagnostic per violation: {result.stderr}"
    for reported_line in reported_lines:
        assert DIAGNOSTIC_LINE.match(reported_line) is not None, (
            f"not a `path:line: message` diagnostic: {reported_line!r}"
        )
    about_the_skill: list[str] = [
        line for line in reported_lines if OVERSIZED_SKILL_PATH in line
    ]
    assert about_the_skill, (
        f"{OVERSIZED_SKILL_PATH} runs past the limit unreported: {result.stdout!r}"
    )
    assert any(LINE_COUNT.search(line) is not None for line in about_the_skill), (
        f"no diagnostic gives its {OVERSIZED_SKILL_LINES} lines: {about_the_skill!r}"
    )
    for conforming_path in CONFORMING_TREE:
        assert conforming_path not in result.stdout, (
            f"{conforming_path} conforms but was reported: {result.stdout!r}"
        )


# Where the installer keeps the inventory of units it can place; a catalog diagnostic
# names it, since that is the file the reader has to edit to fix the finding.
CATALOG: Final[str] = "installer/catalog.toml"

# A skill is registered under the directory that names it, so the path a catalog row
# stands for is the directory rather than the SKILL.md inside it.
SKILL_FILE: Final[str] = "SKILL.md"

# One prompt per kind that the catalog below does carry a row for. Every fixture in
# this pair conforms to the frontmatter conventions, so the only finding either can
# provoke is a catalog one.
REGISTERED_PROMPTS: Final[dict[str, str]] = {
    "skills/registered/SKILL.md": (
        "---\n"
        "name: registered\n"
        "description: Use when the catalog already carries a row for a skill.\n"
        "---\n"
        "\n"
        "# registered\n"
        "\n"
        "A skill the installer can place.\n"
    ),
    "agents/registered.md": (
        "---\n"
        "name: registered\n"
        "description: Runs errands for a test fixture the catalog knows about.\n"
        "tools: Read\n"
        "model: opus\n"
        "---\n"
        "\n"
        "# registered\n"
    ),
    "rules/registered.md": (
        '---\npaths: "**/*.py"\n---\n\n# registered\n\nA rule with a row.\n'
    ),
}


# The same three kinds with no row in the catalog — a skill directory, an agent file
# and a rule file. All three reach the catalog by the same path, so one fixture spanning
# the kinds pins the behaviour without a test per kind.
UNREGISTERED_PROMPTS: Final[dict[str, str]] = {
    "skills/orphan/SKILL.md": (
        "---\n"
        "name: orphan\n"
        "description: Use when a skill exists on disk but nowhere in the catalog.\n"
        "---\n"
        "\n"
        "# orphan\n"
        "\n"
        "A skill the installer cannot place.\n"
    ),
    "agents/orphan.md": (
        "---\n"
        "name: orphan\n"
        "description: Answers to a name the installer's inventory never lists.\n"
        "tools: Read\n"
        "model: opus\n"
        "---\n"
        "\n"
        "# orphan\n"
    ),
    "rules/orphan.md": (
        '---\npaths: "**/*.md"\n---\n\n# orphan\n\nA rule the installer cannot place.\n'
    ),
}


# A catalog whose [[units]] rows cover REGISTERED_PROMPTS and stop there, so the tree
# holds both halves of the cross-check: three prompts with a row, three without.
PARTIAL_CATALOG: Final[dict[str, str]] = {
    CATALOG: (
        "[[units]]\n"
        'kind = "skill"\n'
        'name = "registered"\n'
        "\n"
        "[[units]]\n"
        'kind = "agent"\n'
        'name = "registered"\n'
        "\n"
        "[[units]]\n"
        'kind = "rule"\n'
        'name = "registered"\n'
    ),
}


def _unit_paths(*, prompts: Mapping[str, str]) -> list[str]:
    """The path each prompt is registered under, which for a skill is its directory."""
    return [
        str(Path(prompt_path).parent)
        if Path(prompt_path).name == SKILL_FILE
        else prompt_path
        for prompt_path in prompts
    ]


def test_prompt_without_a_units_row_is_reported_with_the_catalog(
    tmp_path: Path,
) -> None:
    _write_prompts(root=tmp_path, prompts=REGISTERED_PROMPTS)
    _write_prompts(root=tmp_path, prompts=UNREGISTERED_PROMPTS)
    _write_prompts(root=tmp_path, prompts=PARTIAL_CATALOG)

    result: subprocess.CompletedProcess[str] = _run_prompt_lint(root=tmp_path)

    assert result.returncode == 1, (
        f"expected a failing lint for the uncatalogued prompts: {result.stdout!r}"
    )
    reported_lines: list[str] = result.stdout.splitlines()
    for unit_path in _unit_paths(prompts=UNREGISTERED_PROMPTS):
        assert any(unit_path in line and CATALOG in line for line in reported_lines), (
            f"{unit_path} has no [[units]] row unreported: {result.stdout!r}"
        )
    for unit_path in _unit_paths(prompts=REGISTERED_PROMPTS):
        assert unit_path not in result.stdout, (
            f"{unit_path} has a [[units]] row but was reported: {result.stdout!r}"
        )
