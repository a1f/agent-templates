from pathlib import Path

from actions import install_skill
from state import State


def update_skill(
    *,
    name: str,
    source_root: Path,
    state_root: Path,
    claude_root: Path,
    state: State,
) -> State:
    """Give refreshing an already-installed skill its own named entry point,
    distinct from a first install, so update-only behavior (skip-unchanged, drift
    handling) has one place to grow as it diverges from install — for now a
    re-stage of the current source is exactly what install already does."""
    return install_skill(
        name=name,
        source_root=source_root,
        state_root=state_root,
        claude_root=claude_root,
        state=state,
    )
