"""Spec: a make-pr session transcript yields a populated run record."""

import random
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
_TOKEN_COST_TRANSCRIPT: Final[Path] = (
    Path(__file__).parent / "fixtures" / "token_cost_session.jsonl"
)
_CLEAN_PASS_TRANSCRIPT: Final[Path] = (
    Path(__file__).parent / "fixtures" / "clean_pass_session.jsonl"
)

# Hand-counted from token_cost_session.jsonl: the msg_aaa pair is deduped to one,
# so only correct dedup (not naive per-line summing) yields these.
_EXPECTED_TOK_OUTPUT: Final[int] = 360
_EXPECTED_TOK_CACHE_READ: Final[int] = 2100
_EXPECTED_TOK_CACHE_CREATION: Final[int] = 1750
# Hand-priced from the same fixture: fable-5 msgs A (0.027) + B (0.015) + D (0.010);
# msg_ccc's claude-opus-9-9 is unknown so it bills $0 despite carrying tokens.
_EXPECTED_COST_USD: Final[float] = 0.052


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


def test_token_sums_dedup_repeated_message_ids() -> None:
    record: RunRecord | None = extract_run(transcript_path=_TOKEN_COST_TRANSCRIPT)

    assert record is not None
    assert record.tok_output == _EXPECTED_TOK_OUTPUT
    assert record.tok_cache_read == _EXPECTED_TOK_CACHE_READ
    assert record.tok_cache_creation == _EXPECTED_TOK_CACHE_CREATION


def test_estimated_cost_priced_from_table() -> None:
    record: RunRecord | None = extract_run(transcript_path=_TOKEN_COST_TRANSCRIPT)

    assert record is not None
    assert record.est_cost_usd == pytest.approx(_EXPECTED_COST_USD)


def test_pricing_version_stamped_in_detail() -> None:
    record: RunRecord | None = extract_run(transcript_path=_TOKEN_COST_TRANSCRIPT)

    assert record is not None
    assert record.detail.get("pricing_version") == "2026-06-24"


def test_clean_pass_run_outcome_achieved_from_critic_verdict() -> None:
    record: RunRecord | None = extract_run(transcript_path=_CLEAN_PASS_TRANSCRIPT)

    assert record is not None
    assert record.outcome == "achieved"
    assert record.blocked_reason == ""
    assert record.n_fix_loops == 0


def test_token_sums_survive_line_shuffle(tmp_path: Path) -> None:
    lines: list[str] = _TOKEN_COST_TRANSCRIPT.read_text(encoding="utf-8").splitlines()
    random.Random(20260624).shuffle(lines)
    scrambled: Path = tmp_path / "scrambled.jsonl"
    scrambled.write_text("\n".join(lines) + "\n", encoding="utf-8")

    record: RunRecord | None = extract_run(transcript_path=scrambled)

    assert record is not None
    assert record.tok_output == _EXPECTED_TOK_OUTPUT
    assert record.tok_cache_read == _EXPECTED_TOK_CACHE_READ
    assert record.tok_cache_creation == _EXPECTED_TOK_CACHE_CREATION
