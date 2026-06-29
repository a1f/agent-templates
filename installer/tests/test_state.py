import contextlib
import json
from pathlib import Path
from typing import NoReturn

import pytest

from state import STATE_FILENAME, STATE_VERSION, State, load_state, save_state


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


def test_save_then_load_round_trips_requesters_as_tuples(tmp_path: Path) -> None:
    saved: State = State(
        version=STATE_VERSION,
        units={"skill/make-pr": "deadbeef"},
        requesters={"skill/make-pr": ("@direct", "architect-pr")},
    )

    save_state(saved, tmp_path)
    loaded: State = load_state(tmp_path)

    assert loaded == saved


def test_save_then_load_round_trips_extra_hashes_and_omits_when_empty(
    tmp_path: Path,
) -> None:
    with_hashes: State = State(
        version=STATE_VERSION,
        units={"skill/make-pr": "deadbeef"},
        extra_hashes={"rules/python.md": "c0ffee"},
    )
    hashed_root: Path = tmp_path / "hashed"

    save_state(with_hashes, hashed_root)
    loaded: State = load_state(hashed_root)

    assert loaded == with_hashes

    without_hashes: State = State(
        version=STATE_VERSION, units={"skill/make-pr": "deadbeef"}
    )
    empty_root: Path = tmp_path / "empty"

    save_state(without_hashes, empty_root)
    with (empty_root / STATE_FILENAME).open(encoding="utf-8") as handle:
        payload: dict[str, object] = json.load(handle)

    assert "extra_hashes" not in payload


def test_save_is_atomic_failed_replace_keeps_prior_state(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    prior: State = State(version=STATE_VERSION, units={"skill/make-pr": "aaaa1111"})
    save_state(prior, tmp_path)

    def fail_replace(src: object, dst: object) -> NoReturn:
        raise OSError("replace interrupted before the swap")

    monkeypatch.setattr("os.replace", fail_replace)

    clobber: State = State(version=STATE_VERSION, units={"skill/make-pr": "bbbb2222"})
    with contextlib.suppress(OSError):
        save_state(clobber, tmp_path)

    survivor: State = load_state(tmp_path)
    assert survivor == prior


def test_failed_save_leaves_no_orphan_temp_file(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    prior: State = State(version=STATE_VERSION, units={"skill/make-pr": "aaaa1111"})
    save_state(prior, tmp_path)

    def fail_replace(src: object, dst: object) -> NoReturn:
        raise OSError("replace interrupted before the swap")

    monkeypatch.setattr("os.replace", fail_replace)

    clobber: State = State(version=STATE_VERSION, units={"skill/make-pr": "bbbb2222"})
    with pytest.raises(OSError):
        save_state(clobber, tmp_path)

    remaining: set[str] = {entry.name for entry in tmp_path.iterdir()}
    assert remaining == {STATE_FILENAME}
