from dataclasses import dataclass
from pathlib import Path
from typing import Final

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


def load_state(root: Path) -> State:
    """Treat a missing store as a first run rather than an error, so callers get
    a usable default instead of having to handle absence themselves."""
    state_file: Path = root / STATE_FILENAME
    if state_file.exists():
        raise NotImplementedError("reading an existing state store lands in a later PR")
    root.mkdir(parents=True, exist_ok=True)
    return default_state()
