from settings import merge_hook_fragment


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
