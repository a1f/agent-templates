"""Tests for the prompt-vs-schema anti-drift checker.

The test that matters runs the checker over the real prompts. One more proves it
detects drift (a checker that always returned [] would pass the first too).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import check_prompt_schemas as cps


def test_real_prompts_match_their_schemas() -> None:
    prompts: list[Path] = sorted(cps._AGENTS.glob("*.md"))
    assert prompts, "expected real agent prompts to exist"
    drifting: dict[str, list[str]] = {
        p.name: d for p in prompts if (d := cps.drift(prompt=p))
    }
    assert not drifting, f"prompts drifted from their schemas: {drifting}"


def test_detects_drift_against_the_real_schema(tmp_path: Path) -> None:
    # A critic example with an out-of-band score must be flagged by the real schema.
    example: dict[str, Any] = {
        "schema_version": "v1",
        "role": "critic",
        "score": 10,
        "verdict": "achieved",
        "task_restated": "x",
        "covered": [],
        "gaps": [],
        "note": "",
    }
    prompt: Path = tmp_path / "critic.md"
    prompt.write_text(f"intro\n\n```json\n{json.dumps(example)}\n```\n")
    assert any("$.score" in line for line in cps.drift(prompt=prompt))
