"""Spec: a make-pr session transcript yields a populated run record."""

from datetime import UTC, datetime
from pathlib import Path
from typing import Final

import pytest

from extractor import RunRecord, extract_run

_MAKE_PR_TRANSCRIPT: Final[Path] = (
    Path(__file__).parent / "fixtures" / "make_pr_session.jsonl"
)
_MAKE_PR_LITE_TRANSCRIPT: Final[Path] = (
    Path(__file__).parent / "fixtures" / "make_pr_lite_session.jsonl"
)
_PLAIN_TRANSCRIPT: Final[Path] = (
    Path(__file__).parent / "fixtures" / "plain_session.jsonl"
)
_OTHER_SKILL_TRANSCRIPT: Final[Path] = (
    Path(__file__).parent / "fixtures" / "other_skill_session.jsonl"
)


def test_make_pr_transcript_yields_populated_run_record() -> None:
    record: RunRecord | None = extract_run(transcript_path=_MAKE_PR_TRANSCRIPT)

    assert record is not None
    assert record.variant == "make-pr"
    assert record.session_id == "ba155846-a890-4755-aec2-5f89b8150e7f"
    assert record.started_at == datetime(2026, 7, 10, 5, 20, 39, 9000, tzinfo=UTC)


def test_make_pr_lite_transcript_yields_lite_variant_record() -> None:
    record: RunRecord | None = extract_run(transcript_path=_MAKE_PR_LITE_TRANSCRIPT)

    assert record is not None
    assert record.variant == "make-pr-lite"
    assert record.session_id == "da2c4f72-df7e-4343-9153-11396aec9251"
    assert record.started_at == datetime(2026, 7, 9, 15, 37, 46, 236000, tzinfo=UTC)


@pytest.mark.parametrize(
    "transcript_path",
    [_PLAIN_TRANSCRIPT, _OTHER_SKILL_TRANSCRIPT],
)
def test_non_make_pr_session_yields_none(transcript_path: Path) -> None:
    assert extract_run(transcript_path=transcript_path) is None
