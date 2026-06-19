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
