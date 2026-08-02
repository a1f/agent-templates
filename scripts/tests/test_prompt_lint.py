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
# with a name matching its file stem and closes with an example return still in step
# with the schema its role names, and the rule declares the paths it governs.
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
        "A conforming agent. It returns:\n"
        "\n"
        "```json\n"
        '{"role": "helper", "status": "done"}\n'
        "```\n"
    ),
    "schemas/helper.schema.json": (
        "{\n"
        '  "$schema": "https://json-schema.org/draft/2020-12/schema",\n'
        '  "type": "object",\n'
        '  "required": ["role", "status"],\n'
        '  "properties": {\n'
        '    "role": {"const": "helper"},\n'
        '    "status": {"type": "string"}\n'
        "  }\n"
        "}\n"
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


# A package whose extras the installer stages into ~/.claude/at, plus the one skill of
# that package that reads both of them from there. The two extras cover both shapes an
# extra path takes — a file nested under a directory, and a bare directory — and the
# package also carries a non-skill unit, which reads no extra and so answers to nothing
# here.
CONFORMING_EXTRAS_SKILL: Final[str] = "skills/staged-reader/SKILL.md"

EXTRAS_PACKAGE_TREE: Final[dict[str, str]] = {
    "installer/catalog.toml": (
        "[[units]]\n"
        'kind = "skill"\n'
        'name = "staged-reader"\n'
        "\n"
        "[[units]]\n"
        'kind = "skill"\n'
        'name = "bundled-reader"\n'
        "\n"
        "[[units]]\n"
        'kind = "skill"\n'
        'name = "silent-reader"\n'
        "\n"
        "[[units]]\n"
        'kind = "rule"\n'
        'name = "python"\n'
        "\n"
        "[[packages]]\n"
        'name = "extras-package"\n'
        "units = [\n"
        '  "skill/staged-reader",\n'
        '  "skill/bundled-reader",\n'
        '  "skill/silent-reader",\n'
        '  "rule/python",\n'
        "]\n"
        'extras = ["scripts/validate_return.py", "rules"]\n'
    ),
    CONFORMING_EXTRAS_SKILL: (
        "---\n"
        "name: staged-reader\n"
        "description: Use when a skill reads its extras where they are staged.\n"
        "---\n"
        "\n"
        "# staged-reader\n"
        "\n"
        "Validate the return with `~/.claude/at/scripts/validate_return.py`, then\n"
        "hold the code to `~/.claude/at/rules/python.md`.\n"
    ),
}


# One skill per way the staged-extras convention breaks, so each skill carries exactly
# one violation: one still points at the copy bundled beside it in its own directory,
# and one never names the staged root for the 'scripts' extra at all.
OFFENDING_EXTRAS_SKILLS: Final[dict[str, str]] = {
    "skills/bundled-reader/SKILL.md": (
        "---\n"
        "name: bundled-reader\n"
        "description: Use when a skill still reads the copy bundled beside it.\n"
        "---\n"
        "\n"
        "# bundled-reader\n"
        "\n"
        "Validate the return with `~/.claude/at/scripts/validate_return.py`, or\n"
        "with `skills/bundled-reader/scripts/validate_return.py` when that is\n"
        "missing, then hold the code to `~/.claude/at/rules/python.md`.\n"
    ),
    "skills/silent-reader/SKILL.md": (
        "---\n"
        "name: silent-reader\n"
        "description: Use when a skill never says where its extras are staged.\n"
        "---\n"
        "\n"
        "# silent-reader\n"
        "\n"
        "Validate the return, then hold the code to `~/.claude/at/rules/python.md`.\n"
    ),
}


# A skill of the same package that names the staged root for every extra the package
# declares AND keeps a `<skill_root>/` path to one of them beside it — the half-done
# cutover `installer/tests/test_skill_extras_paths.py` bans as `stale_root`, since an
# installed skill has no `<skill_root>` left to read. Its frontmatter is clean and its
# catalog re-cuts the package around only the skills this needs, so the stale path is
# the one violation left in the tree.
STALE_ROOT_EXTRAS_SKILL: Final[str] = "skills/stale-root-reader/SKILL.md"

STALE_ROOT_EXTRAS_TREE: Final[dict[str, str]] = {
    "installer/catalog.toml": (
        "[[units]]\n"
        'kind = "skill"\n'
        'name = "staged-reader"\n'
        "\n"
        "[[units]]\n"
        'kind = "skill"\n'
        'name = "stale-root-reader"\n'
        "\n"
        "[[packages]]\n"
        'name = "extras-package"\n'
        "units = [\n"
        '  "skill/staged-reader",\n'
        '  "skill/stale-root-reader",\n'
        "]\n"
        'extras = ["scripts/validate_return.py", "rules"]\n'
    ),
    STALE_ROOT_EXTRAS_SKILL: (
        "---\n"
        "name: stale-root-reader\n"
        "description: Use when a skill keeps a bundled path beside the staged one.\n"
        "---\n"
        "\n"
        "# stale-root-reader\n"
        "\n"
        "Validate the return with `~/.claude/at/scripts/validate_return.py`, then\n"
        "hold the code to `~/.claude/at/rules/python.md`, falling back to\n"
        "`<skill_root>/rules/python.md` when the package ships its own copy.\n"
    ),
}


# An agent whose closing example return no longer carries every field the schema for
# its role declares — the drift a prompt edit introduces silently. Its frontmatter is
# clean, so the stale example is the only thing left to report. The schema requires
# 'role' alone, so the dropped 'notes' is drift the schema itself would not reject.
DRIFTED_AGENT_PATH: Final[str] = "agents/drifted.md"

DRIFTED_AGENT_TREE: Final[dict[str, str]] = {
    DRIFTED_AGENT_PATH: (
        "---\n"
        "name: drifted\n"
        "description: Returns less than the schema it answers to declares.\n"
        "tools: Read\n"
        "model: opus\n"
        "---\n"
        "\n"
        "# drifted\n"
        "\n"
        "An agent whose example return fell behind its schema:\n"
        "\n"
        "```json\n"
        '{"role": "drifted"}\n'
        "```\n"
    ),
    "schemas/drifted.schema.json": (
        "{\n"
        '  "$schema": "https://json-schema.org/draft/2020-12/schema",\n'
        '  "type": "object",\n'
        '  "required": ["role"],\n'
        '  "properties": {\n'
        '    "role": {"const": "drifted"},\n'
        '    "notes": {"type": "string"}\n'
        "  }\n"
        "}\n"
    ),
}


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


def test_skill_not_reading_extras_from_state_root_is_reported_with_path_and_line(
    tmp_path: Path,
) -> None:
    _write_conforming_tree(root=tmp_path)
    _write_prompts(root=tmp_path, prompts=EXTRAS_PACKAGE_TREE)
    _write_prompts(root=tmp_path, prompts=OFFENDING_EXTRAS_SKILLS)

    result: subprocess.CompletedProcess[str] = _run_prompt_lint(root=tmp_path)

    assert result.returncode == 1, f"expected a failing lint, got: {result.stderr}"
    reported_lines: list[str] = result.stdout.splitlines()
    assert reported_lines, f"expected a diagnostic per violation: {result.stderr}"
    for reported_line in reported_lines:
        assert DIAGNOSTIC_LINE.match(reported_line) is not None, (
            f"not a `path:line: message` diagnostic: {reported_line!r}"
        )
    for offending_path in OFFENDING_EXTRAS_SKILLS:
        assert any(offending_path in line for line in reported_lines), (
            f"{offending_path} reads an extra off the staged root unreported: "
            f"{result.stdout!r}"
        )
    assert CONFORMING_EXTRAS_SKILL not in result.stdout, (
        f"{CONFORMING_EXTRAS_SKILL} names every staged extra but was reported: "
        f"{result.stdout!r}"
    )
    for conforming_path in CONFORMING_TREE:
        assert conforming_path not in result.stdout, (
            f"{conforming_path} conforms but was reported: {result.stdout!r}"
        )


def test_skill_keeping_a_skill_root_extra_path_is_reported_with_path_and_line(
    tmp_path: Path,
) -> None:
    _write_conforming_tree(root=tmp_path)
    _write_prompts(root=tmp_path, prompts=EXTRAS_PACKAGE_TREE | STALE_ROOT_EXTRAS_TREE)

    result: subprocess.CompletedProcess[str] = _run_prompt_lint(root=tmp_path)

    assert result.returncode == 1, f"expected a failing lint, got: {result.stderr}"
    reported_lines: list[str] = result.stdout.splitlines()
    assert reported_lines, f"expected a diagnostic per violation: {result.stderr}"
    for reported_line in reported_lines:
        assert DIAGNOSTIC_LINE.match(reported_line) is not None, (
            f"not a `path:line: message` diagnostic: {reported_line!r}"
        )
    assert any(STALE_ROOT_EXTRAS_SKILL in line for line in reported_lines), (
        f"{STALE_ROOT_EXTRAS_SKILL} kept a <skill_root> extra path unreported: "
        f"{result.stdout!r}"
    )
    assert CONFORMING_EXTRAS_SKILL not in result.stdout, (
        f"{CONFORMING_EXTRAS_SKILL} names every staged extra but was reported: "
        f"{result.stdout!r}"
    )
    for conforming_path in CONFORMING_TREE:
        assert conforming_path not in result.stdout, (
            f"{conforming_path} conforms but was reported: {result.stdout!r}"
        )


def test_agent_example_drifting_from_its_schema_is_reported_with_path_and_line(
    tmp_path: Path,
) -> None:
    _write_conforming_tree(root=tmp_path)
    _write_prompts(root=tmp_path, prompts=DRIFTED_AGENT_TREE)

    result: subprocess.CompletedProcess[str] = _run_prompt_lint(root=tmp_path)

    assert result.returncode == 1, f"expected a failing lint, got: {result.stderr}"
    reported_lines: list[str] = result.stdout.splitlines()
    assert reported_lines, f"expected a diagnostic per violation: {result.stderr}"
    for reported_line in reported_lines:
        assert DIAGNOSTIC_LINE.match(reported_line) is not None, (
            f"not a `path:line: message` diagnostic: {reported_line!r}"
        )
    assert any(DRIFTED_AGENT_PATH in line for line in reported_lines), (
        f"{DRIFTED_AGENT_PATH} dropped a schema field unreported: {result.stdout!r}"
    )
    for conforming_path in CONFORMING_TREE:
        assert conforming_path not in result.stdout, (
            f"{conforming_path} conforms but was reported: {result.stdout!r}"
        )
