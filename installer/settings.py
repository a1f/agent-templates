"""Own the hook<->settings.json round-trip: read a hook's fragment, merge it into
the user's settings.json tagging each contributed matcher-group with its hook id so
the membership stays reversible, and persist the result atomically."""

import json
import tempfile
from pathlib import Path
from typing import Final, cast

from catalog import hook_unit_id
from constants import HOOKS_DIRNAME

SETTINGS_FILENAME: Final[str] = "settings.json"


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
        # copies it, leaving the fragment's own dicts untouched. Drop any group
        # this hook stamped on a previous merge before re-appending, so merging
        # the same fragment twice replaces our groups rather than duplicating
        # them; user groups (no "id") and other hooks' groups (a different "id")
        # are kept, so they survive the merge.
        existing: list[dict[str, object]] = [
            group
            for group in cast("list[dict[str, object]]", hooks.get(event, []))
            if group.get("id") != hook_id
        ]
        hooks[event] = existing + [
            {"id": hook_id, **group}
            for group in cast("list[dict[str, object]]", groups)
        ]
    merged["hooks"] = hooks
    return merged


def unmerge_hook_fragment(
    settings: dict[str, object], *, hook_id: str
) -> dict[str, object]:
    """Strip back out exactly the matcher-groups a hook stamped with its id, so an
    uninstall reverses merge_hook_fragment — dropping that hook's groups while user
    groups (no "id") and other hooks' groups (a different "id") stay registered."""
    # Build a fresh settings dict (and a fresh "hooks" map) rather than mutating
    # the caller's: settings is the on-disk shape callers may still read, so the
    # unmerge stays a pure function of its inputs.
    merged: dict[str, object] = dict(settings)
    hooks: dict[str, object] = {}
    for event, groups in cast("dict[str, object]", merged.get("hooks", {})).items():
        # The settings are untrusted external shape, so cast each event's groups to
        # the matcher-group list at this boundary and keep only the groups this hook
        # did not stamp; user groups (no "id") and other hooks' groups (a different
        # "id") survive, so the unmerge removes exactly this hook's contributions.
        # Drop an event whose groups are now all gone rather than leaving an empty
        # "Event": [] behind, so a merge that introduced the event round-trips away.
        kept: list[dict[str, object]] = [
            group
            for group in cast("list[dict[str, object]]", groups)
            if group.get("id") != hook_id
        ]
        if kept:
            hooks[event] = kept
    # A settings doc that never had a "hooks" block should round-trip unchanged,
    # so only re-attach the map when it carries groups; otherwise drop the key
    # rather than leaving an empty "hooks": {} behind.
    if hooks:
        merged["hooks"] = hooks
    else:
        merged.pop("hooks", None)
    return merged


def load_settings(path: Path) -> dict[str, object]:
    """Treat a missing settings.json as a first install rather than an error, so a
    hook merges into an empty document instead of every caller handling absence."""
    if path.exists():
        with path.open(encoding="utf-8") as handle:
            return cast("dict[str, object]", json.load(handle))
    return {}


def save_settings(settings: dict[str, object], path: Path) -> None:
    """Persist the merged settings so a later run — and the user's own editor —
    sees what this install registered."""
    path.parent.mkdir(parents=True, exist_ok=True)
    # Write a sibling temp file and atomically swap it in, so a failed write leaves
    # the user's prior settings.json intact rather than a half-written file. Indent
    # and a trailing newline keep settings.json readable, since users hand-edit it.
    with tempfile.NamedTemporaryFile(
        mode="w", encoding="utf-8", dir=path.parent, suffix=".tmp", delete=False
    ) as handle:
        json.dump(settings, handle, indent=2)
        handle.write("\n")
        tmp_path: Path = Path(handle.name)
    # A failed swap must not leave the sibling temp behind; the original error
    # still propagates so callers see the write failed.
    try:
        tmp_path.replace(path)
    except OSError:
        tmp_path.unlink(missing_ok=True)
        raise


def read_hook_fragment(*, source_root: Path, name: str) -> dict[str, object] | None:
    """Treat a hook with no "<name>.settings.json" as contributing no settings, so
    the caller distinguishes "no fragment" from an empty one rather than guessing."""
    fragment_path: Path = source_root / HOOKS_DIRNAME / f"{name}.settings.json"
    if fragment_path.exists():
        with fragment_path.open(encoding="utf-8") as handle:
            return cast("dict[str, object]", json.load(handle))
    return None


def merge_hook_settings(*, name: str, source_root: Path, claude_root: Path) -> None:
    """Fold a hook's settings fragment into the user's settings.json under the
    hook's tracked id, so installing the hook also registers its matcher-groups;
    a hook without a fragment touches no settings, keeping plain-hook installs inert."""
    fragment: dict[str, object] | None = read_hook_fragment(
        source_root=source_root, name=name
    )
    if fragment is None:
        return
    settings_path: Path = claude_root / SETTINGS_FILENAME
    merged: dict[str, object] = merge_hook_fragment(
        load_settings(settings_path), hook_id=hook_unit_id(name), fragment=fragment
    )
    save_settings(merged, settings_path)


def unmerge_hook_settings(*, name: str, claude_root: Path) -> None:
    """Strip the hook's tracked matcher-groups back out of the user's settings.json
    by their id alone, so an uninstall reverses merge_hook_settings without depending
    on the repo source still existing or the hook's fragment being unchanged."""
    settings_path: Path = claude_root / SETTINGS_FILENAME
    unmerged: dict[str, object] = unmerge_hook_fragment(
        load_settings(settings_path), hook_id=hook_unit_id(name)
    )
    save_settings(unmerged, settings_path)
