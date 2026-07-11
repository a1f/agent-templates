import json
import stat
import subprocess
from pathlib import Path

from actions import (
    install_agent,
    install_hook,
    install_package,
    install_rule,
    install_skill,
    uninstall_agent,
    uninstall_hook,
    uninstall_package,
    uninstall_rule,
    uninstall_skill,
)
from catalog import Catalog, agent_unit_id, load_catalog, rule_unit_id, skill_unit_id
from constants import DIRECT_REQUESTER
from hashing import hash_unit
from state import STATE_FILENAME, State, default_state, load_state


def test_install_skill_stages_source_and_links_into_claude_skills(
    tmp_path: Path,
) -> None:
    skill_content: str = "# Demo Skill\n\nDemonstrates installation.\n"
    nested_content: str = '{"type": "object"}\n'
    source_root: Path = tmp_path / "repo"
    skill_source: Path = source_root / "skills" / "demo-skill"
    (skill_source / "schemas").mkdir(parents=True)
    (skill_source / "SKILL.md").write_text(skill_content, encoding="utf-8")
    (skill_source / "schemas" / "x.json").write_text(nested_content, encoding="utf-8")

    state_root: Path = tmp_path / "at"
    claude_root: Path = tmp_path / "claude"

    install_skill(
        name="demo-skill",
        source_root=source_root,
        state_root=state_root,
        claude_root=claude_root,
        state=State(version=1, units={}),
    )

    staged_path: Path = state_root / "staged" / "skill" / "demo-skill"
    assert staged_path.is_dir()
    assert (staged_path / "SKILL.md").read_text(encoding="utf-8") == skill_content
    assert (staged_path / "schemas" / "x.json").read_text(
        encoding="utf-8"
    ) == nested_content

    link_path: Path = claude_root / "skills" / "demo-skill"
    assert link_path.is_symlink()
    assert link_path.resolve() == staged_path.resolve()
    assert (link_path / "SKILL.md").read_text(encoding="utf-8") == skill_content


def test_install_skill_records_and_persists_installed_unit(tmp_path: Path) -> None:
    source_root: Path = tmp_path / "repo"
    skill_source: Path = source_root / "skills" / "demo-skill"
    skill_source.mkdir(parents=True)
    (skill_source / "SKILL.md").write_text("# Demo Skill\n", encoding="utf-8")

    state_root: Path = tmp_path / "at"
    claude_root: Path = tmp_path / "claude"
    initial_state: State = State(version=1, units={})

    result: State = install_skill(
        name="demo-skill",
        source_root=source_root,
        state_root=state_root,
        claude_root=claude_root,
        state=initial_state,
    )

    unit_id: str = skill_unit_id("demo-skill")
    assert unit_id in result.units
    assert unit_id in load_state(state_root).units
    assert initial_state.units == {}


def test_install_skill_records_staged_content_hash_as_unit_value(
    tmp_path: Path,
) -> None:
    source_root: Path = tmp_path / "repo"
    skill_source: Path = source_root / "skills" / "demo-skill"
    (skill_source / "schemas").mkdir(parents=True)
    (skill_source / "SKILL.md").write_text("# Demo Skill\n", encoding="utf-8")
    (skill_source / "schemas" / "x.json").write_text(
        '{"type": "object"}\n', encoding="utf-8"
    )

    state_root: Path = tmp_path / "at"
    claude_root: Path = tmp_path / "claude"

    result: State = install_skill(
        name="demo-skill",
        source_root=source_root,
        state_root=state_root,
        claude_root=claude_root,
        state=State(version=1, units={}),
    )

    recorded_hash: str = result.units[skill_unit_id("demo-skill")]
    assert recorded_hash == hash_unit(skill_source)
    assert recorded_hash != ""


def test_install_from_git_repo_source_stamps_head_sha_into_state(
    tmp_path: Path,
) -> None:
    source_root: Path = tmp_path / "repo"
    skill_source: Path = source_root / "skills" / "demo-skill"
    skill_source.mkdir(parents=True)
    (skill_source / "SKILL.md").write_text("# Demo Skill\n", encoding="utf-8")

    # Make the source root a real git repo and commit it, so install has a HEAD to
    # stamp. The -c config flags keep the commit independent of any global git config.
    subprocess.run(["git", "init"], cwd=source_root, check=True, capture_output=True)
    subprocess.run(
        ["git", "add", "-A"], cwd=source_root, check=True, capture_output=True
    )
    subprocess.run(
        ["git", "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-m", "x"],
        cwd=source_root,
        check=True,
        capture_output=True,
    )
    head: subprocess.CompletedProcess[str] = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=source_root,
        check=True,
        capture_output=True,
        text=True,
    )
    expected_sha: str = head.stdout.strip()

    state_root: Path = tmp_path / "at"
    claude_root: Path = tmp_path / "claude"

    install_skill(
        name="demo-skill",
        source_root=source_root,
        state_root=state_root,
        claude_root=claude_root,
        state=default_state(),
    )

    assert load_state(state_root).source_sha == expected_sha


def test_install_from_plain_source_root_writes_state_without_source_sha_key(
    tmp_path: Path,
) -> None:
    source_root: Path = tmp_path / "repo"
    skill_source: Path = source_root / "skills" / "demo-skill"
    skill_source.mkdir(parents=True)
    (skill_source / "SKILL.md").write_text("# Demo Skill\n", encoding="utf-8")

    # No `git init`: the source is a plain tree with no HEAD to stamp. The on-disk
    # store must stay byte-compatible with stores written before the stamp existed —
    # so the key is omitted entirely, never written as an empty "source_sha": "".
    state_root: Path = tmp_path / "at"
    claude_root: Path = tmp_path / "claude"

    install_skill(
        name="demo-skill",
        source_root=source_root,
        state_root=state_root,
        claude_root=claude_root,
        state=default_state(),
    )

    payload: dict[str, object] = json.loads(
        (state_root / STATE_FILENAME).read_text(encoding="utf-8")
    )
    assert "source_sha" not in payload


def test_source_sha_stamp_survives_uninstall_state_write(
    tmp_path: Path,
) -> None:
    source_root: Path = tmp_path / "repo"
    for skill_name in ("alpha", "beta"):
        skill_source: Path = source_root / "skills" / skill_name
        skill_source.mkdir(parents=True)
        (skill_source / "SKILL.md").write_text(
            f"# {skill_name} Skill\n", encoding="utf-8"
        )

    # Make the source root a real git repo and commit it, so install has a HEAD to
    # stamp. The -c config flags keep the commit independent of any global git config.
    subprocess.run(["git", "init"], cwd=source_root, check=True, capture_output=True)
    subprocess.run(
        ["git", "add", "-A"], cwd=source_root, check=True, capture_output=True
    )
    subprocess.run(
        ["git", "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-m", "x"],
        cwd=source_root,
        check=True,
        capture_output=True,
    )
    head: subprocess.CompletedProcess[str] = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=source_root,
        check=True,
        capture_output=True,
        text=True,
    )
    expected_sha: str = head.stdout.strip()

    state_root: Path = tmp_path / "at"
    claude_root: Path = tmp_path / "claude"

    # Install two skills so the store still holds a unit after one is removed; the
    # install stamps the source repo's HEAD sha into the persisted store.
    state_after_alpha: State = install_skill(
        name="alpha",
        source_root=source_root,
        state_root=state_root,
        claude_root=claude_root,
        state=default_state(),
    )
    state_after_beta: State = install_skill(
        name="beta",
        source_root=source_root,
        state_root=state_root,
        claude_root=claude_root,
        state=state_after_alpha,
    )

    uninstall_skill(
        name="beta",
        state_root=state_root,
        claude_root=claude_root,
        state=state_after_beta,
    )

    # Uninstalling one unit rewrites the store; that rewrite must carry the stamp
    # forward rather than silently dropping it.
    assert load_state(state_root).source_sha == expected_sha


def test_install_skill_preserves_existing_requesters_of_other_units(
    tmp_path: Path,
) -> None:
    source_root: Path = tmp_path / "repo"
    skill_source: Path = source_root / "skills" / "demo-skill"
    skill_source.mkdir(parents=True)
    (skill_source / "SKILL.md").write_text("# Demo Skill\n", encoding="utf-8")

    state_root: Path = tmp_path / "at"
    claude_root: Path = tmp_path / "claude"
    prior_state: State = State(
        version=1,
        units={"agent/reviewer": "somehash"},
        requesters={"agent/reviewer": ("architect-pr",)},
    )

    result: State = install_skill(
        name="demo-skill",
        source_root=source_root,
        state_root=state_root,
        claude_root=claude_root,
        state=prior_state,
    )

    # A direct install adds no requester token of its own, so the only requesters
    # entry that should survive is the unrelated unit's prior one.
    assert result.requesters == {"agent/reviewer": ("architect-pr",)}
    assert skill_unit_id("demo-skill") in result.units


def test_uninstall_skill_undoes_install_and_forgets_unit(tmp_path: Path) -> None:
    source_root: Path = tmp_path / "repo"
    skill_source: Path = source_root / "skills" / "demo-skill"
    skill_source.mkdir(parents=True)
    (skill_source / "SKILL.md").write_text("# Demo Skill\n", encoding="utf-8")

    state_root: Path = tmp_path / "at"
    claude_root: Path = tmp_path / "claude"
    installed_state: State = install_skill(
        name="demo-skill",
        source_root=source_root,
        state_root=state_root,
        claude_root=claude_root,
        state=State(version=1, units={}),
    )

    result: State = uninstall_skill(
        name="demo-skill",
        state_root=state_root,
        claude_root=claude_root,
        state=installed_state,
    )

    unit_id: str = skill_unit_id("demo-skill")
    assert not (claude_root / "skills" / "demo-skill").is_symlink()
    assert not (state_root / "staged" / "skill" / "demo-skill").exists()
    assert unit_id not in result.units
    assert unit_id not in load_state(state_root).units
    assert unit_id in installed_state.units


def test_install_agent_stages_md_file_and_links_into_claude_agents(
    tmp_path: Path,
) -> None:
    agent_content: str = "# Demo Agent\n\nDemonstrates installation.\n"
    name: str = "demo-agent"
    source_root: Path = tmp_path / "repo"
    agent_source: Path = source_root / "agents" / f"{name}.md"
    agent_source.parent.mkdir(parents=True)
    agent_source.write_text(agent_content, encoding="utf-8")

    state_root: Path = tmp_path / "at"
    claude_root: Path = tmp_path / "claude"

    result: State = install_agent(
        name=name,
        source_root=source_root,
        state_root=state_root,
        claude_root=claude_root,
        state=State(version=1, units={}),
    )

    staged_path: Path = state_root / "staged" / "agent" / name
    assert staged_path.is_file()
    assert staged_path.read_text(encoding="utf-8") == agent_content

    link_path: Path = claude_root / "agents" / f"{name}.md"
    assert link_path.is_symlink()
    assert link_path.resolve() == staged_path.resolve()
    assert link_path.read_text(encoding="utf-8") == agent_content

    assert agent_unit_id(name) in result.units


def test_uninstall_agent_undoes_install_and_forgets_unit(tmp_path: Path) -> None:
    agent_content: str = "# Demo Agent\n\nDemonstrates installation.\n"
    name: str = "demo-agent"
    source_root: Path = tmp_path / "repo"
    agent_source: Path = source_root / "agents" / f"{name}.md"
    agent_source.parent.mkdir(parents=True)
    agent_source.write_text(agent_content, encoding="utf-8")

    state_root: Path = tmp_path / "at"
    claude_root: Path = tmp_path / "claude"
    installed_state: State = install_agent(
        name=name,
        source_root=source_root,
        state_root=state_root,
        claude_root=claude_root,
        state=State(version=1, units={}),
    )

    result: State = uninstall_agent(
        name=name,
        state_root=state_root,
        claude_root=claude_root,
        state=installed_state,
    )

    unit_id: str = agent_unit_id(name)
    assert not (claude_root / "agents" / f"{name}.md").is_symlink()
    assert not (state_root / "staged" / "agent" / name).exists()
    assert unit_id not in result.units
    assert unit_id not in load_state(state_root).units
    assert unit_id in installed_state.units


def test_install_rule_stages_md_file_and_links_into_claude_rules(
    tmp_path: Path,
) -> None:
    rule_content: str = "# Demo Rule\n\nDemonstrates installation.\n"
    name: str = "demo-rule"
    source_root: Path = tmp_path / "repo"
    rule_source: Path = source_root / "rules" / f"{name}.md"
    rule_source.parent.mkdir(parents=True)
    rule_source.write_text(rule_content, encoding="utf-8")

    state_root: Path = tmp_path / "at"
    claude_root: Path = tmp_path / "claude"

    result: State = install_rule(
        name=name,
        source_root=source_root,
        state_root=state_root,
        claude_root=claude_root,
        state=State(version=1, units={}),
    )

    staged_path: Path = state_root / "staged" / "rule" / name
    assert staged_path.is_file()
    assert staged_path.read_text(encoding="utf-8") == rule_content

    link_path: Path = claude_root / "rules" / f"{name}.md"
    assert link_path.is_symlink()
    assert link_path.resolve() == staged_path.resolve()
    assert link_path.read_text(encoding="utf-8") == rule_content

    assert rule_unit_id(name) in result.units


def test_install_hook_stages_executable_sh_and_links_into_claude_hooks(
    tmp_path: Path,
) -> None:
    hook_content: str = "#!/usr/bin/env bash\necho demo\n"
    name: str = "demo-hook"
    source_root: Path = tmp_path / "repo"
    hook_source: Path = source_root / "hooks" / f"{name}.sh"
    hook_source.parent.mkdir(parents=True)
    hook_source.write_text(hook_content, encoding="utf-8")
    hook_source.chmod(0o755)

    state_root: Path = tmp_path / "at"
    claude_root: Path = tmp_path / "claude"

    result: State = install_hook(
        name=name,
        source_root=source_root,
        state_root=state_root,
        claude_root=claude_root,
        state=State(version=1, units={}),
    )

    staged_path: Path = state_root / "staged" / "hook" / name
    assert staged_path.is_file()
    assert staged_path.read_text(encoding="utf-8") == hook_content
    assert staged_path.stat().st_mode & stat.S_IXUSR

    link_path: Path = claude_root / "hooks" / f"{name}.sh"
    assert link_path.is_symlink()
    assert link_path.resolve() == staged_path.resolve()
    assert link_path.read_text(encoding="utf-8") == hook_content

    assert f"hook/{name}" in result.units


def test_install_hook_merges_settings_fragment_preserving_user_settings(
    tmp_path: Path,
) -> None:
    name: str = "demo-hook"
    source_root: Path = tmp_path / "repo"
    hook_source: Path = source_root / "hooks" / f"{name}.sh"
    hook_source.parent.mkdir(parents=True)
    hook_source.write_text("#!/usr/bin/env bash\necho demo\n", encoding="utf-8")
    hook_source.chmod(0o755)

    fragment: dict[str, object] = {
        "PostToolUse": [
            {
                "matcher": "Edit|Write",
                "hooks": [
                    {"type": "command", "command": "~/.claude/hooks/demo-hook.sh"}
                ],
            }
        ]
    }
    (source_root / "hooks" / f"{name}.settings.json").write_text(
        json.dumps(fragment), encoding="utf-8"
    )

    claude_root: Path = tmp_path / "claude"
    claude_root.mkdir(parents=True)
    user_post_group: dict[str, object] = {
        "matcher": "Bash",
        "hooks": [{"type": "command", "command": "user.sh"}],
    }
    existing_settings: dict[str, object] = {
        "model": "opus",
        "hooks": {"PostToolUse": [user_post_group]},
    }
    settings_path: Path = claude_root / "settings.json"
    settings_path.write_text(json.dumps(existing_settings), encoding="utf-8")

    state_root: Path = tmp_path / "at"

    install_hook(
        name=name,
        source_root=source_root,
        state_root=state_root,
        claude_root=claude_root,
        state=State(version=1, units={}),
    )

    result: dict[str, object] = json.loads(settings_path.read_text(encoding="utf-8"))

    assert result["model"] == "opus"

    hooks_map: object = result["hooks"]
    assert isinstance(hooks_map, dict)
    post_groups: object = hooks_map["PostToolUse"]
    assert isinstance(post_groups, list)
    assert user_post_group in post_groups

    tracked_groups: list[dict[str, object]] = [
        group
        for group in post_groups
        if isinstance(group, dict) and group.get("id") == f"hook/{name}"
    ]
    assert len(tracked_groups) == 1

    tracked_hooks: object = tracked_groups[0]["hooks"]
    assert isinstance(tracked_hooks, list)
    first_hook: object = tracked_hooks[0]
    assert isinstance(first_hook, dict)
    command: object = first_hook["command"]
    assert isinstance(command, str)
    assert command.endswith("demo-hook.sh")


def test_uninstall_rule_undoes_install_and_forgets_unit(tmp_path: Path) -> None:
    rule_content: str = "# Demo Rule\n\nDemonstrates installation.\n"
    name: str = "demo-rule"
    source_root: Path = tmp_path / "repo"
    rule_source: Path = source_root / "rules" / f"{name}.md"
    rule_source.parent.mkdir(parents=True)
    rule_source.write_text(rule_content, encoding="utf-8")

    state_root: Path = tmp_path / "at"
    claude_root: Path = tmp_path / "claude"
    installed_state: State = install_rule(
        name=name,
        source_root=source_root,
        state_root=state_root,
        claude_root=claude_root,
        state=State(version=1, units={}),
    )

    result: State = uninstall_rule(
        name=name,
        state_root=state_root,
        claude_root=claude_root,
        state=installed_state,
    )

    unit_id: str = rule_unit_id(name)
    assert not (claude_root / "rules" / f"{name}.md").is_symlink()
    assert not (state_root / "staged" / "rule" / name).exists()
    assert unit_id not in result.units
    assert unit_id not in load_state(state_root).units
    assert unit_id in installed_state.units


def test_uninstall_hook_undoes_install_and_forgets_unit(tmp_path: Path) -> None:
    hook_content: str = "#!/usr/bin/env bash\necho demo\n"
    name: str = "demo-hook"
    source_root: Path = tmp_path / "repo"
    hook_source: Path = source_root / "hooks" / f"{name}.sh"
    hook_source.parent.mkdir(parents=True)
    hook_source.write_text(hook_content, encoding="utf-8")
    hook_source.chmod(0o755)

    state_root: Path = tmp_path / "at"
    claude_root: Path = tmp_path / "claude"
    installed_state: State = install_hook(
        name=name,
        source_root=source_root,
        state_root=state_root,
        claude_root=claude_root,
        state=State(version=1, units={}),
    )

    result: State = uninstall_hook(
        name=name,
        state_root=state_root,
        claude_root=claude_root,
        state=installed_state,
    )

    unit_id: str = f"hook/{name}"
    assert not (claude_root / "hooks" / f"{name}.sh").is_symlink()
    assert not (state_root / "staged" / "hook" / name).exists()
    assert unit_id not in result.units
    assert unit_id not in load_state(state_root).units
    assert unit_id in installed_state.units


def test_uninstall_hook_removes_its_settings_block_preserving_user_settings(
    tmp_path: Path,
) -> None:
    name: str = "demo-hook"
    source_root: Path = tmp_path / "repo"
    hook_source: Path = source_root / "hooks" / f"{name}.sh"
    hook_source.parent.mkdir(parents=True)
    hook_source.write_text("#!/usr/bin/env bash\necho demo\n", encoding="utf-8")
    hook_source.chmod(0o755)

    fragment: dict[str, object] = {
        "PostToolUse": [
            {
                "matcher": "Edit|Write",
                "hooks": [
                    {"type": "command", "command": "~/.claude/hooks/demo-hook.sh"}
                ],
            }
        ]
    }
    (source_root / "hooks" / f"{name}.settings.json").write_text(
        json.dumps(fragment), encoding="utf-8"
    )

    claude_root: Path = tmp_path / "claude"
    claude_root.mkdir(parents=True)
    user_post_group: dict[str, object] = {
        "matcher": "Bash",
        "hooks": [{"type": "command", "command": "user.sh"}],
    }
    existing_settings: dict[str, object] = {
        "model": "opus",
        "hooks": {"PostToolUse": [user_post_group]},
    }
    settings_path: Path = claude_root / "settings.json"
    settings_path.write_text(json.dumps(existing_settings), encoding="utf-8")

    state_root: Path = tmp_path / "at"

    installed_state: State = install_hook(
        name=name,
        source_root=source_root,
        state_root=state_root,
        claude_root=claude_root,
        state=State(version=1, units={}),
    )

    uninstall_hook(
        name=name,
        state_root=state_root,
        claude_root=claude_root,
        state=installed_state,
    )

    result: dict[str, object] = json.loads(settings_path.read_text(encoding="utf-8"))

    assert result["model"] == "opus"

    hooks_map: object = result["hooks"]
    assert isinstance(hooks_map, dict)
    post_groups: object = hooks_map["PostToolUse"]
    assert isinstance(post_groups, list)
    assert user_post_group in post_groups

    tracked_groups: list[dict[str, object]] = [
        group
        for groups in hooks_map.values()
        if isinstance(groups, list)
        for group in groups
        if isinstance(group, dict) and group.get("id") == f"hook/{name}"
    ]
    assert tracked_groups == []


def test_uninstall_hook_leaves_settings_untouched_when_nothing_is_removed(
    tmp_path: Path,
) -> None:
    name: str = "demo-hook"
    source_root: Path = tmp_path / "repo"
    hook_source: Path = source_root / "hooks" / f"{name}.sh"
    hook_source.parent.mkdir(parents=True)
    hook_source.write_text("#!/usr/bin/env bash\necho demo\n", encoding="utf-8")
    hook_source.chmod(0o755)

    claude_root: Path = tmp_path / "claude"
    claude_root.mkdir(parents=True)
    user_doc: dict[str, object] = {
        "model": "opus",
        "hooks": {
            "PostToolUse": [
                {
                    "matcher": "Bash",
                    "hooks": [{"type": "command", "command": "user.sh"}],
                }
            ]
        },
    }
    settings_path: Path = claude_root / "settings.json"
    settings_path.write_text(
        json.dumps(user_doc, separators=(",", ":")), encoding="utf-8"
    )
    original_text: str = settings_path.read_text(encoding="utf-8")

    state_root: Path = tmp_path / "at"

    installed_state: State = install_hook(
        name=name,
        source_root=source_root,
        state_root=state_root,
        claude_root=claude_root,
        state=State(version=1, units={}),
    )

    uninstall_hook(
        name=name,
        state_root=state_root,
        claude_root=claude_root,
        state=installed_state,
    )

    assert settings_path.read_text(encoding="utf-8") == original_text


def test_uninstall_hook_tolerates_missing_settings_file(tmp_path: Path) -> None:
    hook_content: str = "#!/usr/bin/env bash\necho demo\n"
    name: str = "demo-hook"
    source_root: Path = tmp_path / "repo"
    hook_source: Path = source_root / "hooks" / f"{name}.sh"
    hook_source.parent.mkdir(parents=True)
    hook_source.write_text(hook_content, encoding="utf-8")
    hook_source.chmod(0o755)

    state_root: Path = tmp_path / "at"
    claude_root: Path = tmp_path / "claude"
    installed_state: State = install_hook(
        name=name,
        source_root=source_root,
        state_root=state_root,
        claude_root=claude_root,
        state=State(version=1, units={}),
    )

    uninstall_hook(
        name=name,
        state_root=state_root,
        claude_root=claude_root,
        state=installed_state,
    )

    assert not (claude_root / "hooks" / f"{name}.sh").is_symlink()
    assert not (claude_root / "settings.json").exists()


def test_install_package_installs_each_unit_and_records_package_requester(
    tmp_path: Path,
) -> None:
    source_root: Path = tmp_path / "repo"
    skill_source: Path = source_root / "skills" / "alpha"
    skill_source.mkdir(parents=True)
    (skill_source / "SKILL.md").write_text("# Alpha Skill\n", encoding="utf-8")
    agent_source: Path = source_root / "agents" / "helper.md"
    agent_source.parent.mkdir(parents=True)
    agent_source.write_text("# Helper Agent\n", encoding="utf-8")

    # A controlled catalog declaring the two units of different kinds and a package
    # grouping both, loaded through the real boundary so the package install
    # resolves its members exactly as production will.
    catalog_body: str = """
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
    catalog_path: Path = tmp_path / "catalog.toml"
    catalog_path.write_text(catalog_body, encoding="utf-8")
    catalog: Catalog = load_catalog(catalog_path)

    state_root: Path = tmp_path / "at"
    claude_root: Path = tmp_path / "claude"

    result: State = install_package(
        name="pack",
        catalog=catalog,
        source_root=source_root,
        state_root=state_root,
        claude_root=claude_root,
        state=State(version=1, units={}),
    )

    # Both members are physically placed: each kind's staged copy plus its live
    # symlink (a skill stages as a directory, an agent as a single file).
    assert (state_root / "staged" / "skill" / "alpha").is_dir()
    assert (state_root / "staged" / "agent" / "helper").is_file()
    assert (claude_root / "skills" / "alpha").is_symlink()
    assert (claude_root / "agents" / "helper.md").is_symlink()

    assert skill_unit_id("alpha") in result.units
    assert agent_unit_id("helper") in result.units

    # The package name is recorded as every installed unit's requester.
    assert result.requesters[skill_unit_id("alpha")] == ("pack",)
    assert result.requesters[agent_unit_id("helper")] == ("pack",)


def test_install_package_stages_extras_and_records_package_requester(
    tmp_path: Path,
) -> None:
    source_root: Path = tmp_path / "repo"
    skill_source: Path = source_root / "skills" / "alpha"
    skill_source.mkdir(parents=True)
    (skill_source / "SKILL.md").write_text("# Alpha Skill\n", encoding="utf-8")

    schemas_source: Path = source_root / "schemas"
    schemas_source.mkdir(parents=True)
    (schemas_source / "thing.json").write_text('{"type": "object"}\n', encoding="utf-8")

    tool_source: Path = source_root / "scripts" / "tool.py"
    tool_source.parent.mkdir(parents=True)
    tool_source.write_text("print('tool')\n", encoding="utf-8")

    # A controlled catalog declaring the one unit and a package that also carries
    # two extras — a whole directory ("schemas") and a single file nested in a
    # subdir ("scripts/tool.py") — loaded through the real boundary so the package
    # install resolves its members and extras exactly as production will.
    catalog_body: str = """
[[units]]
kind = "skill"
name = "alpha"

[[packages]]
name = "pack"
units = ["skill/alpha"]
extras = ["schemas", "scripts/tool.py"]

[[bundles]]
name = "everything"
packages = ["pack"]
"""
    catalog_path: Path = tmp_path / "catalog.toml"
    catalog_path.write_text(catalog_body, encoding="utf-8")
    catalog: Catalog = load_catalog(catalog_path)

    state_root: Path = tmp_path / "at"
    claude_root: Path = tmp_path / "claude"

    result: State = install_package(
        name="pack",
        catalog=catalog,
        source_root=source_root,
        state_root=state_root,
        claude_root=claude_root,
        state=State(version=1, units={}),
    )

    # The directory extra is staged whole under the state root, preserving its
    # source-relative path, so a skill finds its schemas where it expects them.
    assert (state_root / "schemas" / "thing.json").is_file()
    # The file extra nested in a subdir lands at the same relative path too.
    assert (state_root / "scripts" / "tool.py").is_file()

    # Each extra records the package name as its requester, keyed by the extra's
    # source-relative path string.
    assert result.extras["schemas"] == ("pack",)
    assert result.extras["scripts/tool.py"] == ("pack",)


def test_install_package_records_each_extra_content_hash(
    tmp_path: Path,
) -> None:
    source_root: Path = tmp_path / "repo"
    skill_source: Path = source_root / "skills" / "alpha"
    skill_source.mkdir(parents=True)
    (skill_source / "SKILL.md").write_text("# Alpha Skill\n", encoding="utf-8")

    schemas_source: Path = source_root / "schemas"
    schemas_source.mkdir(parents=True)
    (schemas_source / "thing.json").write_text('{"type": "object"}\n', encoding="utf-8")

    tool_source: Path = source_root / "scripts" / "tool.py"
    tool_source.parent.mkdir(parents=True)
    tool_source.write_text("print('tool')\n", encoding="utf-8")

    # A controlled catalog declaring the one unit and a package that carries two
    # extras — a whole directory ("schemas") and a single file nested in a subdir
    # ("scripts/tool.py") — loaded through the real boundary. Two extras of
    # different shapes are deliberate: recording one extra's hash must carry the
    # other's forward rather than overwrite it.
    catalog_body: str = """
[[units]]
kind = "skill"
name = "alpha"

[[packages]]
name = "pack"
units = ["skill/alpha"]
extras = ["schemas", "scripts/tool.py"]

[[bundles]]
name = "everything"
packages = ["pack"]
"""
    catalog_path: Path = tmp_path / "catalog.toml"
    catalog_path.write_text(catalog_body, encoding="utf-8")
    catalog: Catalog = load_catalog(catalog_path)

    state_root: Path = tmp_path / "at"
    claude_root: Path = tmp_path / "claude"

    result: State = install_package(
        name="pack",
        catalog=catalog,
        source_root=source_root,
        state_root=state_root,
        claude_root=claude_root,
        state=State(version=1, units={}),
    )

    # Each staged extra's content hash is recorded under its source-relative path,
    # equal to hashing the staged copy under the state root: the directory extra and
    # the nested file extra each carry their own hash forward.
    assert result.extra_hashes["schemas"] == hash_unit(state_root / "schemas")
    assert result.extra_hashes["scripts/tool.py"] == hash_unit(
        state_root / "scripts" / "tool.py"
    )


def test_uninstall_package_keeps_unit_still_required_by_another_package(
    tmp_path: Path,
) -> None:
    source_root: Path = tmp_path / "repo"
    for skill_name in ("shared", "only-one", "only-two"):
        skill_source: Path = source_root / "skills" / skill_name
        skill_source.mkdir(parents=True)
        (skill_source / "SKILL.md").write_text(
            f"# {skill_name} Skill\n", encoding="utf-8"
        )

    # Two packages that share one unit (skill/shared) and each own one private unit,
    # loaded through the real boundary so the uninstall resolves members exactly as
    # production will.
    catalog_body: str = """
[[units]]
kind = "skill"
name = "shared"

[[units]]
kind = "skill"
name = "only-one"

[[units]]
kind = "skill"
name = "only-two"

[[packages]]
name = "pack-one"
units = ["skill/shared", "skill/only-one"]

[[packages]]
name = "pack-two"
units = ["skill/shared", "skill/only-two"]

[[bundles]]
name = "everything"
packages = ["pack-one", "pack-two"]
"""
    catalog_path: Path = tmp_path / "catalog.toml"
    catalog_path.write_text(catalog_body, encoding="utf-8")
    catalog: Catalog = load_catalog(catalog_path)

    state_root: Path = tmp_path / "at"
    claude_root: Path = tmp_path / "claude"

    # Install both packages, threading state, so skill/shared ends up credited to
    # both pack-one and pack-two while each private unit has a single requester.
    state_after_pack_one: State = install_package(
        name="pack-one",
        catalog=catalog,
        source_root=source_root,
        state_root=state_root,
        claude_root=claude_root,
        state=State(version=1, units={}),
    )
    state_after_both: State = install_package(
        name="pack-two",
        catalog=catalog,
        source_root=source_root,
        state_root=state_root,
        claude_root=claude_root,
        state=state_after_pack_one,
    )

    result: State = uninstall_package(
        name="pack-one",
        catalog=catalog,
        state_root=state_root,
        claude_root=claude_root,
        state=state_after_both,
    )

    # skill/shared survives: pack-two still requires it, so it stays fully installed
    # and only loses pack-one from its requester set.
    assert (state_root / "staged" / "skill" / "shared").is_dir()
    assert (claude_root / "skills" / "shared").is_symlink()
    assert skill_unit_id("shared") in result.units
    assert result.requesters[skill_unit_id("shared")] == ("pack-two",)

    # skill/only-one was pack-one's alone: its last requester is gone, so it is
    # physically removed and forgotten entirely.
    assert not (state_root / "staged" / "skill" / "only-one").exists()
    assert not (claude_root / "skills" / "only-one").is_symlink()
    assert skill_unit_id("only-one") not in result.units
    assert skill_unit_id("only-one") not in result.requesters

    # skill/only-two belongs only to pack-two and is left untouched.
    assert skill_unit_id("only-two") in result.units
    assert result.requesters[skill_unit_id("only-two")] == ("pack-two",)


def test_uninstall_package_keeps_a_directly_installed_unit(tmp_path: Path) -> None:
    source_root: Path = tmp_path / "repo"
    skill_source: Path = source_root / "skills" / "alpha"
    skill_source.mkdir(parents=True)
    (skill_source / "SKILL.md").write_text("# Alpha Skill\n", encoding="utf-8")

    # A controlled catalog declaring the one unit and a package that also contains
    # it, loaded through the real boundary so the package install/uninstall resolve
    # its members exactly as production will.
    catalog_body: str = """
[[units]]
kind = "skill"
name = "alpha"

[[packages]]
name = "pack"
units = ["skill/alpha"]

[[bundles]]
name = "everything"
packages = ["pack"]
"""
    catalog_path: Path = tmp_path / "catalog.toml"
    catalog_path.write_text(catalog_body, encoding="utf-8")
    catalog: Catalog = load_catalog(catalog_path)

    state_root: Path = tmp_path / "at"
    claude_root: Path = tmp_path / "claude"

    # The user installs alpha directly first (a bare direct install records no
    # requester token of its own), then a package containing alpha is layered over
    # the already-present unit, then that package is dropped again.
    state_after_direct: State = install_skill(
        name="alpha",
        source_root=source_root,
        state_root=state_root,
        claude_root=claude_root,
        state=State(version=1, units={}),
    )
    state_after_pack: State = install_package(
        name="pack",
        catalog=catalog,
        source_root=source_root,
        state_root=state_root,
        claude_root=claude_root,
        state=state_after_direct,
    )
    result: State = uninstall_package(
        name="pack",
        catalog=catalog,
        state_root=state_root,
        claude_root=claude_root,
        state=state_after_pack,
    )

    # The user still wants alpha, so dropping the package must leave it fully
    # installed: a direct-install marker outlives the package's requester rather
    # than letting the package uninstall reclaim the directly-installed unit.
    assert skill_unit_id("alpha") in result.units
    assert (state_root / "staged" / "skill" / "alpha").is_dir()
    assert (claude_root / "skills" / "alpha").is_symlink()
    assert result.requesters[skill_unit_id("alpha")] == (DIRECT_REQUESTER,)


def test_uninstall_package_refcounts_extras_keeping_shared_removing_sole(
    tmp_path: Path,
) -> None:
    source_root: Path = tmp_path / "repo"
    for skill_name in ("alpha", "beta"):
        skill_source: Path = source_root / "skills" / skill_name
        skill_source.mkdir(parents=True)
        (skill_source / "SKILL.md").write_text(
            f"# {skill_name} Skill\n", encoding="utf-8"
        )

    # A shared extra directory both packages declare, plus one private extra file
    # per package nested in its own subdir, so refcounting an extra mirrors how the
    # units test exercises a shared-vs-private unit. The units are incidental here.
    shared_extra: Path = source_root / "shared"
    shared_extra.mkdir(parents=True)
    (shared_extra / "keep.txt").write_text("shared\n", encoding="utf-8")

    one_private: Path = source_root / "one" / "private.txt"
    one_private.parent.mkdir(parents=True)
    one_private.write_text("one\n", encoding="utf-8")

    two_private: Path = source_root / "two" / "private.txt"
    two_private.parent.mkdir(parents=True)
    two_private.write_text("two\n", encoding="utf-8")

    # Two packages that share one extra ("shared") and each own one private extra,
    # loaded through the real boundary so the uninstall resolves the package's
    # extras exactly as production will.
    catalog_body: str = """
[[units]]
kind = "skill"
name = "alpha"

[[units]]
kind = "skill"
name = "beta"

[[packages]]
name = "pack-one"
units = ["skill/alpha"]
extras = ["shared", "one/private.txt"]

[[packages]]
name = "pack-two"
units = ["skill/beta"]
extras = ["shared", "two/private.txt"]

[[bundles]]
name = "everything"
packages = ["pack-one", "pack-two"]
"""
    catalog_path: Path = tmp_path / "catalog.toml"
    catalog_path.write_text(catalog_body, encoding="utf-8")
    catalog: Catalog = load_catalog(catalog_path)

    state_root: Path = tmp_path / "at"
    claude_root: Path = tmp_path / "claude"

    # Install both packages, threading state, so the shared extra ends up credited
    # to both pack-one and pack-two while each private extra has a single requester.
    state_after_pack_one: State = install_package(
        name="pack-one",
        catalog=catalog,
        source_root=source_root,
        state_root=state_root,
        claude_root=claude_root,
        state=State(version=1, units={}),
    )
    state_after_both: State = install_package(
        name="pack-two",
        catalog=catalog,
        source_root=source_root,
        state_root=state_root,
        claude_root=claude_root,
        state=state_after_pack_one,
    )

    result: State = uninstall_package(
        name="pack-one",
        catalog=catalog,
        state_root=state_root,
        claude_root=claude_root,
        state=state_after_both,
    )

    # pack-one's private extra had pack-one as its sole requester: its last
    # requester is gone, so it is physically removed and forgotten entirely.
    assert not (state_root / "one" / "private.txt").exists()
    assert "one/private.txt" not in result.extras

    # The shared extra survives: pack-two still requires it, so it stays on disk and
    # only loses pack-one from its requester set.
    assert (state_root / "shared" / "keep.txt").is_file()
    assert result.extras["shared"] == ("pack-two",)

    # pack-two's private extra belongs only to pack-two and is left untouched.
    assert (state_root / "two" / "private.txt").is_file()
    assert result.extras["two/private.txt"] == ("pack-two",)


def test_uninstall_package_drops_forgotten_extra_hash_keeping_shared(
    tmp_path: Path,
) -> None:
    source_root: Path = tmp_path / "repo"
    for skill_name in ("alpha", "beta"):
        skill_source: Path = source_root / "skills" / skill_name
        skill_source.mkdir(parents=True)
        (skill_source / "SKILL.md").write_text(
            f"# {skill_name} Skill\n", encoding="utf-8"
        )

    # A shared extra directory both packages declare, plus one private extra file
    # per package nested in its own subdir, so refcounting an extra's hash mirrors how
    # the extras test exercises a shared-vs-private extra. The units are incidental.
    shared_extra: Path = source_root / "shared"
    shared_extra.mkdir(parents=True)
    (shared_extra / "keep.txt").write_text("shared\n", encoding="utf-8")

    one_private: Path = source_root / "one" / "private.txt"
    one_private.parent.mkdir(parents=True)
    one_private.write_text("one\n", encoding="utf-8")

    two_private: Path = source_root / "two" / "private.txt"
    two_private.parent.mkdir(parents=True)
    two_private.write_text("two\n", encoding="utf-8")

    # Two packages that share one extra ("shared") and each own one private extra,
    # loaded through the real boundary so the uninstall resolves the package's
    # extras exactly as production will.
    catalog_body: str = """
[[units]]
kind = "skill"
name = "alpha"

[[units]]
kind = "skill"
name = "beta"

[[packages]]
name = "pack-one"
units = ["skill/alpha"]
extras = ["shared", "one/private.txt"]

[[packages]]
name = "pack-two"
units = ["skill/beta"]
extras = ["shared", "two/private.txt"]

[[bundles]]
name = "everything"
packages = ["pack-one", "pack-two"]
"""
    catalog_path: Path = tmp_path / "catalog.toml"
    catalog_path.write_text(catalog_body, encoding="utf-8")
    catalog: Catalog = load_catalog(catalog_path)

    state_root: Path = tmp_path / "at"
    claude_root: Path = tmp_path / "claude"

    # Install both packages, threading state, so the shared extra ends up credited
    # to both pack-one and pack-two while each private extra has a single requester.
    state_after_pack_one: State = install_package(
        name="pack-one",
        catalog=catalog,
        source_root=source_root,
        state_root=state_root,
        claude_root=claude_root,
        state=State(version=1, units={}),
    )
    state_after_both: State = install_package(
        name="pack-two",
        catalog=catalog,
        source_root=source_root,
        state_root=state_root,
        claude_root=claude_root,
        state=state_after_pack_one,
    )

    result: State = uninstall_package(
        name="pack-one",
        catalog=catalog,
        state_root=state_root,
        claude_root=claude_root,
        state=state_after_both,
    )

    # pack-one's private extra had pack-one as its sole requester: its last requester
    # is gone, so the extra is forgotten — and its recorded hash is dropped too.
    assert "one/private.txt" not in result.extra_hashes

    # The shared extra survives: pack-two still requires it, so its recorded hash is
    # kept and still equals hashing the surviving staged copy under the state root.
    assert "shared" in result.extra_hashes
    assert result.extra_hashes["shared"] == hash_unit(state_root / "shared")

    # pack-two's private extra belongs only to pack-two, so its hash is untouched.
    assert "two/private.txt" in result.extra_hashes
