"""Tests for the return-contract validator (a thin jsonschema wrapper).

We don't test jsonschema — we test that our schemas encode the contract and our wiring
resolves the cross-file $ref: real returns pass, a contract violation is rejected, the
CLI exits right.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Final

import pytest

from validate_return import main, validate

SCHEMAS: Final[Path] = Path(__file__).resolve().parents[2] / "schemas"

VALID: Final[dict[str, dict[str, Any]]] = {
    "critic": {
        "schema_version": "v1",
        "role": "critic",
        "score": 90,
        "verdict": "achieved",
        "task_restated": "x",
        "covered": [{"task_part": "a", "evidence": "b"}],
        "gaps": [],
        "note": "",
    },
    "reviewer": {
        "schema_version": "v1",
        "role": "reviewer",
        "summary": "s",
        "summary_score": 60,
        "has_critical": False,
        "findings": [],
    },
}


def errors_for(*, role: str, payload: dict[str, Any], tmp_path: Path) -> list[str]:
    instance: Path = tmp_path / "return.json"
    instance.write_text(json.dumps(payload))
    return validate(schema_path=SCHEMAS / f"{role}.schema.json", instance_path=instance)


@pytest.mark.parametrize("role", sorted(VALID))
def test_valid_returns_pass(role: str, tmp_path: Path) -> None:
    assert errors_for(role=role, payload=VALID[role], tmp_path=tmp_path) == []


def test_a_contract_violation_is_rejected(tmp_path: Path) -> None:
    # critic 'achieved' demands score >= 85 — the schema's band must reject 10.
    errors: list[str] = errors_for(
        role="critic", payload={**VALID["critic"], "score": 10}, tmp_path=tmp_path
    )
    assert any(message.startswith("$.score") for message in errors)


def test_cross_file_schema_version_ref_resolves(tmp_path: Path) -> None:
    # schema_version is a $ref into _defs.schema.json; a wrong value must be caught.
    errors: list[str] = errors_for(
        role="critic",
        payload={**VALID["critic"], "schema_version": "v2"},
        tmp_path=tmp_path,
    )
    assert any(message.startswith("$.schema_version") for message in errors)


def test_cli_reports_pass_and_fail(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    schema: str = str(SCHEMAS / "critic.schema.json")
    ok: Path = tmp_path / "ok.json"
    ok.write_text(json.dumps(VALID["critic"]))
    assert main(argv=["prog", schema, str(ok)]) == 0
    assert "OK:" in capsys.readouterr().out

    bad: Path = tmp_path / "bad.json"
    bad.write_text(json.dumps({**VALID["critic"], "score": 1}))
    assert main(argv=["prog", schema, str(bad)]) == 1
    assert "INVALID:" in capsys.readouterr().out
