"""Spec: a make-pr session transcript yields a populated run record."""

from datetime import UTC, datetime
from pathlib import Path
from typing import Final

from extractor import RunRecord, extract_run

_MAKE_PR_TRANSCRIPT: Final[Path] = Path(__file__).parent / "fixtures" / "make_pr_session.jsonl"


def test_make_pr_transcript_yields_populated_run_record() -> None:
    record: RunRecord | None = extract_run(transcript_path=_MAKE_PR_TRANSCRIPT)

    assert record is not None
    assert record.variant == "make-pr"
    assert record.session_id == "ba155846-a890-4755-aec2-5f89b8150e7f"
    assert record.started_at == datetime(2026, 7, 10, 5, 20, 39, 9000, tzinfo=UTC)
