"""Spec: a make-pr session transcript yields a populated run record."""

import hashlib
import json
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
_BLOCKED_TRANSCRIPT: Final[Path] = (
    Path(__file__).parent / "fixtures" / "blocked_session.jsonl"
)
_FIX_LOOP_TRANSCRIPT: Final[Path] = (
    Path(__file__).parent / "fixtures" / "fix_loop_session.jsonl"
)
_ROLELESS_CRITIC_TRANSCRIPT: Final[Path] = (
    Path(__file__).parent / "fixtures" / "roleless_critic_session.jsonl"
)
_DISPATCH_TRANSCRIPT: Final[Path] = (
    Path(__file__).parent / "fixtures" / "dispatch_session.jsonl"
)

# Hand-counted from token_cost_session.jsonl: the msg_aaa pair is deduped to one,
# so only correct dedup (not naive per-line summing) yields these.
_EXPECTED_TOK_OUTPUT: Final[int] = 360
_EXPECTED_TOK_CACHE_READ: Final[int] = 2100
_EXPECTED_TOK_CACHE_CREATION: Final[int] = 1750
# Hand-priced from the same fixture: fable-5 msgs A (0.027) + B (0.015) + D (0.010);
# msg_ccc's claude-opus-9-9 is unknown so it bills $0 despite carrying tokens.
_EXPECTED_COST_USD: Final[float] = 0.052
# Hand-summed from clean_pass_session.jsonl consecutive gaps 30 s + 120 s + 10 s; the
# 3450 s gap (09:02:30 -> 10:00:00) exceeds the 300 s idle threshold and is excluded.
_EXPECTED_ACTIVE_SEC: Final[float] = 160.0

# A fixed 40-hex commit sha the installer stamps into state.json as "source_sha".
_SOURCE_SHA: Final[str] = "0123abcd4567ef890123abcd4567ef890123abcd"

# Hand-counted per-role breakdown of dispatch_session.jsonl and its subagents/
# sidechains. The main transcript carries no attributionAgent, so both main messages
# fall in "main"; each sidechain message's attributionAgent is its role, so agent-a2
# and agent-a3 (both "worker-coder") merge into one bucket. agent-a1 re-emits msg_s1
# on two lines with identical usage, so correct dedup by message.id counts it once.
# Costs bill cache_read at 0.1x and cache_creation at 1.25x the input rate (no
# cache_creation breakdown given), plus output at the output rate: fable-5 is 10/50
# and opus-4-8 is 5/25 USD per MTok. Summing any field across the three roles
# reproduces the record's total for that field.
_EXPECTED_ROLES: Final[dict[str, dict[str, object]]] = {
    "main": {
        "tok_output": 30,
        "tok_cache_read": 600,
        "tok_cache_creation": 300,
        "est_cost_usd": pytest.approx(0.0059),
    },
    "tdd-runner": {
        "tok_output": 8,
        "tok_cache_read": 100,
        "tok_cache_creation": 40,
        "est_cost_usd": pytest.approx(0.0015),
    },
    "worker-coder": {
        "tok_output": 18,
        "tok_cache_read": 180,
        "tok_cache_creation": 100,
        "est_cost_usd": pytest.approx(0.00207),
    },
}


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


def test_pr_link_taken_from_run_tail_over_earlier_mentions() -> None:
    record: RunRecord | None = extract_run(transcript_path=_CLEAN_PASS_TRANSCRIPT)

    assert record is not None
    assert record.pr_url == "https://github.com/a1f/agent-templates/pull/132"
    assert record.pr_number == 132


def test_blocked_run_reports_blocked_outcome_and_reason() -> None:
    record: RunRecord | None = extract_run(transcript_path=_BLOCKED_TRANSCRIPT)

    assert record is not None
    assert record.outcome == "blocked"
    assert record.blocked_reason == (
        "new dependency psycopg required but dependencies_allowed is false"
    )


def test_fix_mode_dispatches_counted_as_fix_loops() -> None:
    record: RunRecord | None = extract_run(transcript_path=_FIX_LOOP_TRANSCRIPT)

    assert record is not None
    assert record.n_fix_loops == 2
    assert record.outcome == "achieved"


def test_run_record_carries_installer_source_sha_as_skill_version(
    tmp_path: Path,
) -> None:
    state_dir: Path = tmp_path / "at"
    state_dir.mkdir()
    state: dict[str, object] = {
        "version": 1,
        "units": {},
        "source_sha": _SOURCE_SHA,
    }
    (state_dir / "state.json").write_text(json.dumps(state), encoding="utf-8")

    record: RunRecord | None = extract_run(
        transcript_path=_MAKE_PR_TRANSCRIPT, claude_root=tmp_path
    )

    assert record is not None
    assert record.skill_version == _SOURCE_SHA


def test_skill_version_falls_back_to_installed_skill_content_hash(
    tmp_path: Path,
) -> None:
    skill_bytes: bytes = b"# make-pr\n\nInstalled skill body under test.\n"
    skill_dir: Path = tmp_path / "skills" / "make-pr"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_bytes(skill_bytes)

    record: RunRecord | None = extract_run(
        transcript_path=_MAKE_PR_TRANSCRIPT, claude_root=tmp_path
    )

    expected: str = "installed:" + hashlib.sha256(skill_bytes).hexdigest()[:8]
    assert record is not None
    assert record.skill_version == expected


def test_corrupt_state_json_degrades_to_installed_hash_instead_of_raising(
    tmp_path: Path,
) -> None:
    state_dir: Path = tmp_path / "at"
    state_dir.mkdir()
    (state_dir / "state.json").write_bytes(b'\xff\xfe{"version": 1}')
    skill_bytes: bytes = b"# make-pr\n\nInstalled skill body under test.\n"
    skill_dir: Path = tmp_path / "skills" / "make-pr"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_bytes(skill_bytes)

    record: RunRecord | None = extract_run(
        transcript_path=_MAKE_PR_TRANSCRIPT, claude_root=tmp_path
    )

    expected: str = "installed:" + hashlib.sha256(skill_bytes).hexdigest()[:8]
    assert record is not None
    assert record.skill_version == expected


def test_skill_version_is_unknown_when_no_stamp_and_no_installed_skill(
    tmp_path: Path,
) -> None:
    record: RunRecord | None = extract_run(
        transcript_path=_MAKE_PR_TRANSCRIPT, claude_root=tmp_path
    )

    assert record is not None
    assert record.skill_version == "unknown"


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


def test_active_sec_sums_gaps_excluding_idle(tmp_path: Path) -> None:
    lines: list[str] = _CLEAN_PASS_TRANSCRIPT.read_text(encoding="utf-8").splitlines()
    random.Random(20260711).shuffle(lines)
    scrambled: Path = tmp_path / "scrambled.jsonl"
    scrambled.write_text("\n".join(lines) + "\n", encoding="utf-8")

    record: RunRecord | None = extract_run(transcript_path=_CLEAN_PASS_TRANSCRIPT)
    shuffled_record: RunRecord | None = extract_run(transcript_path=scrambled)

    assert record is not None
    assert shuffled_record is not None
    assert record.active_sec == pytest.approx(_EXPECTED_ACTIVE_SEC)
    assert shuffled_record.active_sec == pytest.approx(_EXPECTED_ACTIVE_SEC)


def test_roleless_critic_verdict_sets_outcome() -> None:
    record: RunRecord | None = extract_run(transcript_path=_ROLELESS_CRITIC_TRANSCRIPT)

    assert record is not None
    assert record.outcome == "achieved"


def test_malformed_outcome_signals_degrade_to_unknown(tmp_path: Path) -> None:
    truncated_return: str = '{"schema_version": "v1", "role": "critic", "verdi'
    out_of_enum_return: str = '{"role": "critic", "verdict": "maybe"}'
    coder_done_return: str = (
        '{"schema_version": "v1", "role": "coder", "mode": "green", '
        '"status": "done", "blocked_reason": ""}'
    )
    entries: list[dict[str, object]] = [
        {
            "type": "assistant",
            "uuid": "mf-l1",
            "timestamp": "2026-07-11T08:00:00.000Z",
            "sessionId": "99999999-8888-4777-8666-555555555555",
            "session_id": "99999999-8888-4777-8666-555555555555",
            "attributionSkill": "make-pr",
            "message": {
                "id": "msg_mf_01",
                "type": "message",
                "role": "assistant",
                "model": "claude-fable-5",
                "content": [{"type": "text", "text": "Intake: starting the run."}],
                "usage": {
                    "input_tokens": 10,
                    "output_tokens": 50,
                    "cache_read_input_tokens": 100,
                    "cache_creation_input_tokens": 20,
                },
            },
        },
        {
            "type": "assistant",
            "uuid": "mf-l2",
            "timestamp": "not-a-timestamp",
            "sessionId": "99999999-8888-4777-8666-555555555555",
            "message": {
                "role": "assistant",
                "content": [
                    {"type": "text", "text": "no structured return here, just prose"}
                ],
            },
        },
        {
            "type": "user",
            "uuid": "mf-l3",
            "timestamp": "2026-07-11T08:01:00.000Z",
            "message": {
                "role": "user",
                "content": [
                    {
                        "type": "tool_result",
                        "tool_use_id": "toolu_mf_01",
                        "content": [{"type": "text", "text": truncated_return}],
                    }
                ],
            },
        },
        {
            "type": "user",
            "uuid": "mf-l4",
            "timestamp": "2026-07-11T08:02:00.000Z",
            "message": {
                "role": "user",
                "content": [
                    {
                        "type": "tool_result",
                        "tool_use_id": "toolu_mf_02",
                        "content": [{"type": "text", "text": out_of_enum_return}],
                    }
                ],
            },
        },
        {
            "type": "user",
            "uuid": "mf-l5",
            "timestamp": "2026-07-11T08:03:00.000Z",
            "message": {
                "role": "user",
                "content": [
                    {
                        "type": "tool_result",
                        "tool_use_id": "toolu_mf_03",
                        "content": [{"type": "text", "text": coder_done_return}],
                    }
                ],
            },
        },
    ]
    transcript: Path = tmp_path / "malformed_session.jsonl"
    transcript.write_text(
        "".join(json.dumps(entry) + "\n" for entry in entries), encoding="utf-8"
    )

    record: RunRecord | None = extract_run(transcript_path=transcript)

    assert record is not None
    assert record.outcome == "unknown"
    assert record.blocked_reason == ""


def test_fix_loops_deduped_by_dispatch_identity(tmp_path: Path) -> None:
    usage: dict[str, object] = {
        "input_tokens": 5,
        "output_tokens": 35,
        "cache_read_input_tokens": 0,
        "cache_creation_input_tokens": 0,
    }
    # L2 and its L3 re-emission are byte-identical: same message id and same
    # tool_use `id`, so dedup by dispatch identity must count this dispatch once.
    dispatch_line: dict[str, object] = {
        "type": "assistant",
        "uuid": "dd-l2",
        "timestamp": "2026-07-08T12:01:00.000Z",
        "attributionSkill": "make-pr-lite",
        "message": {
            "id": "msg_dd_02",
            "type": "message",
            "role": "assistant",
            "model": "claude-fable-5",
            "content": [
                {
                    "type": "tool_use",
                    "id": "toolu_dd_A",
                    "name": "Agent",
                    "input": {
                        "description": "Fix round 1",
                        "subagent_type": "coder-lite",
                        "prompt": "mode: fix\n\nApply blocker 1.",
                    },
                }
            ],
            "usage": usage,
        },
    }
    entries: list[dict[str, object]] = [
        {
            "type": "assistant",
            "uuid": "dd-l1",
            "timestamp": "2026-07-08T12:00:00.000Z",
            "session_id": "44444444-5555-4666-8777-888888888888",
            "attributionSkill": "make-pr-lite",
            "message": {
                "id": "msg_dd_01",
                "type": "message",
                "role": "assistant",
                "model": "claude-fable-5",
                "content": [{"type": "text", "text": "Intake: starting the run."}],
                "usage": usage,
            },
        },
        dispatch_line,
        dispatch_line,
        {
            "type": "assistant",
            "uuid": "dd-l4",
            "timestamp": "2026-07-08T12:02:00.000Z",
            "attributionSkill": "make-pr-lite",
            "message": {
                "id": "msg_dd_03",
                "type": "message",
                "role": "assistant",
                "model": "claude-fable-5",
                "content": [{"type": "text", "text": "Dispatching the follow-up fix."}],
                "usage": usage,
            },
        },
        {
            # A second content part of message id msg_dd_03, already seen on L4, still
            # carries a distinct dispatch (toolu_dd_B) that must count.
            "type": "assistant",
            "uuid": "dd-l5",
            "timestamp": "2026-07-08T12:02:01.000Z",
            "attributionSkill": "make-pr-lite",
            "message": {
                "id": "msg_dd_03",
                "type": "message",
                "role": "assistant",
                "model": "claude-fable-5",
                "content": [
                    {
                        "type": "tool_use",
                        "id": "toolu_dd_B",
                        "name": "Agent",
                        "input": {
                            "description": "Fix round 2",
                            "subagent_type": "coder-lite",
                            "prompt": "mode: fix\n\nApply blocker 2.",
                        },
                    }
                ],
                "usage": usage,
            },
        },
    ]
    transcript: Path = tmp_path / "dispatch_dedup_session.jsonl"
    transcript.write_text(
        "".join(json.dumps(entry) + "\n" for entry in entries), encoding="utf-8"
    )

    record: RunRecord | None = extract_run(transcript_path=transcript)

    assert record is not None
    assert record.n_fix_loops == 2


def test_tokens_partition_by_role_across_sidechains_with_nothing_dropped() -> None:
    record: RunRecord | None = extract_run(transcript_path=_DISPATCH_TRANSCRIPT)

    assert record is not None
    roles: object = record.detail.get("roles")
    assert roles == _EXPECTED_ROLES
    assert isinstance(roles, dict)
    assert record.tok_output == sum(bucket["tok_output"] for bucket in roles.values())
    assert record.tok_cache_read == sum(
        bucket["tok_cache_read"] for bucket in roles.values()
    )
    assert record.tok_cache_creation == sum(
        bucket["tok_cache_creation"] for bucket in roles.values()
    )
    assert record.est_cost_usd == pytest.approx(
        sum(bucket["est_cost_usd"] for bucket in roles.values())
    )
