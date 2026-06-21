from settings import merge_hook_fragment, unmerge_hook_fragment


def test_merge_hook_fragment_stamps_fragment_into_settings_under_tracked_id() -> None:
    settings: dict[str, object] = {}
    fragment: dict[str, object] = {
        "PostToolUse": [
            {"matcher": "Edit", "hooks": [{"type": "command", "command": "x.sh"}]}
        ]
    }

    result: dict[str, object] = merge_hook_fragment(
        settings, hook_id="hook/demo", fragment=fragment
    )

    hooks_map: object = result["hooks"]
    assert isinstance(hooks_map, dict)
    groups: object = hooks_map["PostToolUse"]
    assert groups == [
        {
            "id": "hook/demo",
            "matcher": "Edit",
            "hooks": [{"type": "command", "command": "x.sh"}],
        }
    ]
    assert settings == {}


def test_merge_hook_fragment_preserves_other_settings_and_hook_groups() -> None:
    user_post_group: dict[str, object] = {
        "matcher": "Bash",
        "hooks": [{"type": "command", "command": "user.sh"}],
    }
    user_pre_group: dict[str, object] = {
        "matcher": "Read",
        "hooks": [{"type": "command", "command": "pre.sh"}],
    }
    settings: dict[str, object] = {
        "permissions": {"allow": ["Bash"]},
        "hooks": {
            "PostToolUse": [user_post_group],
            "PreToolUse": [user_pre_group],
        },
    }
    fragment: dict[str, object] = {
        "PostToolUse": [
            {"matcher": "Edit", "hooks": [{"type": "command", "command": "ours.sh"}]}
        ]
    }

    result: dict[str, object] = merge_hook_fragment(
        settings, hook_id="hook/demo", fragment=fragment
    )

    assert result["permissions"] == {"allow": ["Bash"]}

    hooks_map: object = result["hooks"]
    assert isinstance(hooks_map, dict)
    assert hooks_map["PreToolUse"] == [
        {"matcher": "Read", "hooks": [{"type": "command", "command": "pre.sh"}]}
    ]

    post_groups: object = hooks_map["PostToolUse"]
    assert isinstance(post_groups, list)
    assert len(post_groups) == 2
    assert {
        "matcher": "Bash",
        "hooks": [{"type": "command", "command": "user.sh"}],
    } in post_groups
    assert {
        "id": "hook/demo",
        "matcher": "Edit",
        "hooks": [{"type": "command", "command": "ours.sh"}],
    } in post_groups


def test_merge_hook_fragment_is_idempotent_for_repeated_same_hook_merge() -> None:
    fragment: dict[str, object] = {
        "PostToolUse": [
            {"matcher": "Edit", "hooks": [{"type": "command", "command": "ours.sh"}]}
        ]
    }

    once: dict[str, object] = merge_hook_fragment(
        {}, hook_id="hook/demo", fragment=fragment
    )
    twice: dict[str, object] = merge_hook_fragment(
        once, hook_id="hook/demo", fragment=fragment
    )

    assert twice == once

    hooks_map: object = twice["hooks"]
    assert isinstance(hooks_map, dict)
    post_groups: object = hooks_map["PostToolUse"]
    assert isinstance(post_groups, list)
    our_group_count: int = sum(
        1
        for group in post_groups
        if isinstance(group, dict) and group.get("id") == "hook/demo"
    )
    assert our_group_count == 1


def test_unmerge_hook_fragment_removes_tracked_groups_preserving_the_rest() -> None:
    user_post_group: dict[str, object] = {
        "matcher": "Bash",
        "hooks": [{"type": "command", "command": "user.sh"}],
    }
    demo_post_group: dict[str, object] = {
        "id": "hook/demo",
        "matcher": "Edit",
        "hooks": [{"type": "command", "command": "demo.sh"}],
    }
    other_pre_group: dict[str, object] = {
        "id": "hook/other",
        "matcher": "Read",
        "hooks": [{"type": "command", "command": "other.sh"}],
    }
    settings: dict[str, object] = {
        "permissions": {"allow": ["Bash"]},
        "hooks": {
            "PostToolUse": [user_post_group, demo_post_group],
            "PreToolUse": [other_pre_group],
        },
    }

    result: dict[str, object] = unmerge_hook_fragment(settings, hook_id="hook/demo")

    hooks_map: object = result["hooks"]
    assert isinstance(hooks_map, dict)
    remaining_ids: list[object] = [
        group.get("id")
        for event_groups in hooks_map.values()
        if isinstance(event_groups, list)
        for group in event_groups
        if isinstance(group, dict)
    ]
    assert "hook/demo" not in remaining_ids
    assert "hook/other" in remaining_ids

    post_groups: object = hooks_map["PostToolUse"]
    assert isinstance(post_groups, list)
    assert user_post_group in post_groups

    pre_groups: object = hooks_map["PreToolUse"]
    assert isinstance(pre_groups, list)
    assert other_pre_group in pre_groups

    assert result["permissions"] == {"allow": ["Bash"]}

    original_hooks: object = settings["hooks"]
    assert isinstance(original_hooks, dict)
    original_post_groups: object = original_hooks["PostToolUse"]
    assert isinstance(original_post_groups, list)
    assert demo_post_group in original_post_groups


def test_unmerge_hook_fragment_leaves_a_no_hooks_doc_unchanged() -> None:
    settings: dict[str, object] = {"model": "opus", "permissions": {"allow": ["Bash"]}}

    result: dict[str, object] = unmerge_hook_fragment(settings, hook_id="hook/demo")

    assert result == {"model": "opus", "permissions": {"allow": ["Bash"]}}
    assert "hooks" not in result


def test_merge_then_unmerge_round_trips_to_the_original_settings() -> None:
    original: dict[str, object] = {
        "model": "opus",
        "hooks": {
            "PreToolUse": [
                {"matcher": "Read", "hooks": [{"type": "command", "command": "pre.sh"}]}
            ]
        },
    }
    fragment: dict[str, object] = {
        "PostToolUse": [
            {"matcher": "Edit", "hooks": [{"type": "command", "command": "ours.sh"}]}
        ]
    }

    merged: dict[str, object] = merge_hook_fragment(
        original, hook_id="hook/demo", fragment=fragment
    )
    restored: dict[str, object] = unmerge_hook_fragment(merged, hook_id="hook/demo")

    assert restored == original
