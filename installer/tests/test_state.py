from pathlib import Path

from state import STATE_VERSION, State, load_state, save_state


def test_load_state_on_first_run_creates_dir_and_returns_default(
    tmp_path: Path,
) -> None:
    root: Path = tmp_path / "at"

    state: State = load_state(root)

    assert state.version == STATE_VERSION
    assert len(state.units) == 0
    assert root.is_dir()


def test_save_then_load_round_trips_recorded_state(tmp_path: Path) -> None:
    saved: State = State(version=STATE_VERSION, units={"skill/make-pr": "deadbeef"})

    save_state(saved, tmp_path)
    loaded: State = load_state(tmp_path)

    assert loaded == saved
