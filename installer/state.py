import json
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Final, cast

STATE_VERSION: Final[int] = 1

STATE_FILENAME: Final[str] = "state.json"


@dataclass(frozen=True)
class State:
    """Snapshot of which units the installer has placed, versioned so a future
    read can migrate older on-disk layouts."""

    version: int
    units: dict[str, str]
    # unit id -> the sorted tuple of tokens that requested it; declared last with a
    # default so existing State(version=..., units=...) call sites keep working.
    requesters: dict[str, tuple[str, ...]] = field(default_factory=dict)
    # extra source-relative path -> the sorted tuple of tokens that requested it,
    # the same refcount shape as requesters; declared last with a default so existing
    # State(version=..., units=..., requesters=...) call sites keep working.
    extras: dict[str, tuple[str, ...]] = field(default_factory=dict)
    # extra source-relative path -> the sha256 content hash recorded for it; declared
    # last with a default so existing State(version=..., units=..., requesters=...,
    # extras=...) call sites keep working.
    extra_hashes: dict[str, str] = field(default_factory=dict)


def default_state() -> State:
    """The starting point for a root that has never been installed into."""
    return State(version=STATE_VERSION, units={})


def save_state(state: State, root: Path) -> None:
    """Persist a snapshot so a later run can see what this one installed."""
    root.mkdir(parents=True, exist_ok=True)
    state_file: Path = root / STATE_FILENAME
    payload: dict[str, object] = {"version": state.version, "units": state.units}
    # Omit an empty requesters map so a no-requester store stays byte-identical to
    # what prior versions wrote; committed e2e golden snapshots pin that exact JSON.
    if state.requesters:
        payload["requesters"] = state.requesters
    # Omit an empty extras map for the same reason — committed e2e goldens pin the
    # exact JSON of stores that have no extras, so an empty map must not appear.
    if state.extras:
        payload["extras"] = state.extras
    # Omit an empty extra_hashes map for the same reason; values are plain strings,
    # so no tuple handling is needed unlike requesters/extras above.
    if state.extra_hashes:
        payload["extra_hashes"] = state.extra_hashes
    # Write a sibling temp file and atomically swap it in, so a failed write
    # leaves the prior store intact rather than a half-written file.
    with tempfile.NamedTemporaryFile(
        mode="w", encoding="utf-8", dir=root, suffix=".tmp", delete=False
    ) as handle:
        json.dump(payload, handle)
        tmp_path: Path = Path(handle.name)
    # A failed swap must not leave the sibling temp behind; the original error
    # still propagates so callers see the write failed.
    try:
        tmp_path.replace(state_file)
    except OSError:
        tmp_path.unlink(missing_ok=True)
        raise


def load_state(root: Path) -> State:
    """Treat a missing store as a first run rather than an error, so callers get
    a usable default instead of having to handle absence themselves."""
    state_file: Path = root / STATE_FILENAME
    if state_file.exists():
        with state_file.open(encoding="utf-8") as handle:
            raw: dict[str, object] = json.load(handle)
        version: int = cast("int", raw["version"])
        units: dict[str, str] = cast("dict[str, str]", raw["units"])
        # A store written before this field has no "requesters" key; default to {}.
        # JSON stores each token list as an array, so rebuild tuples on the way in.
        stored_requesters: dict[str, list[str]] = cast(
            "dict[str, list[str]]", raw.get("requesters", {})
        )
        requesters: dict[str, tuple[str, ...]] = {
            unit_id: tuple(tokens) for unit_id, tokens in stored_requesters.items()
        }
        # A store written before this field has no "extras" key; default to {} and
        # rebuild each token list as a tuple, mirroring the requesters rebuild above.
        stored_extras: dict[str, list[str]] = cast(
            "dict[str, list[str]]", raw.get("extras", {})
        )
        extras: dict[str, tuple[str, ...]] = {
            relpath: tuple(tokens) for relpath, tokens in stored_extras.items()
        }
        # A store written before this field has no "extra_hashes" key; default to {}.
        # Values are plain strings, so no tuple rebuild is needed unlike extras above.
        extra_hashes: dict[str, str] = cast(
            "dict[str, str]", raw.get("extra_hashes", {})
        )
        return State(
            version=version,
            units=units,
            requesters=requesters,
            extras=extras,
            extra_hashes=extra_hashes,
        )
    root.mkdir(parents=True, exist_ok=True)
    return default_state()
