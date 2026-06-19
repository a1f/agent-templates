"""Own how a hook unit's fragment merges into the user's settings.json, tagging
each contributed matcher-group with its hook id so the membership stays reversible."""

from typing import cast


def merge_hook_fragment(
    settings: dict[str, object], *, hook_id: str, fragment: dict[str, object]
) -> dict[str, object]:
    """Stamp a hook unit's id onto every matcher-group it contributes, so the
    merged settings carry which hook owns each group and a later uninstall can
    strip exactly that hook's groups back out without disturbing the rest."""
    # Build a fresh settings dict (and a fresh "hooks" map) rather than mutating
    # the caller's: settings is the on-disk shape callers may still read, so the
    # merge stays a pure function of its inputs.
    merged: dict[str, object] = dict(settings)
    hooks: dict[str, object] = dict(cast("dict[str, object]", merged.get("hooks", {})))
    for event, groups in fragment.items():
        # The fragment is untrusted external shape, so cast to the matcher-group
        # list at this boundary; stamping each group as {"id": ..., **group}
        # copies it, leaving the fragment's own dicts untouched.
        hooks[event] = [
            {"id": hook_id, **group}
            for group in cast("list[dict[str, object]]", groups)
        ]
    merged["hooks"] = hooks
    return merged
