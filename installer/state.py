import json
from dataclasses import dataclass
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


def default_state() -> State:
    """The starting point for a root that has never been installed into."""
    return State(version=STATE_VERSION, units={})


def save_state(state: State, root: Path) -> None:
    """Persist a snapshot so a later run can see what this one installed."""
    root.mkdir(parents=True, exist_ok=True)
    state_file: Path = root / STATE_FILENAME
    payload: dict[str, object] = {"version": state.version, "units": state.units}
    with state_file.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle)


def load_state(root: Path) -> State:
    """Treat a missing store as a first run rather than an error, so callers get
    a usable default instead of having to handle absence themselves."""
    state_file: Path = root / STATE_FILENAME
    if state_file.exists():
        with state_file.open(encoding="utf-8") as handle:
            raw: dict[str, object] = json.load(handle)
        version: int = cast("int", raw["version"])
        units: dict[str, str] = cast("dict[str, str]", raw["units"])
        return State(version=version, units=units)
    root.mkdir(parents=True, exist_ok=True)
    return default_state()
