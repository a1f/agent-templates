"""Tests for multi_review.parser."""

import json

import pytest

from multi_review.exceptions import ParseError
from multi_review.parser import parse_findings
from multi_review.types import Severity


class TestParseFindings:
    """Tests for the 3-tier JSON extraction strategy."""

    def test_direct_json_array(self) -> None:
        raw = json.dumps([
            {"file": "a.py", "line": 1, "issue": "bug", "severity": "CRITICAL", "category": "correctness"},
        ])
        result = parse_findings(raw_output=raw, model_name="test")
        assert len(result) == 1
        assert result[0].file == "a.py"
        assert result[0].severity == Severity.CRITICAL

    def test_code_fence_extraction(self) -> None:
        raw = """Here are the findings:

```json
[{"file": "b.py", "line": 10, "issue": "xss", "severity": "MAJOR", "category": "security"}]
```

That's all."""
        result = parse_findings(raw_output=raw, model_name="test")
        assert len(result) == 1
        assert result[0].issue == "xss"

    def test_code_fence_no_language_tag(self) -> None:
        raw = """Findings:

```
[{"file": "c.py", "line": 5, "issue": "leak", "severity": "MINOR", "category": "performance"}]
```
"""
        result = parse_findings(raw_output=raw, model_name="test")
        assert len(result) == 1
        assert result[0].severity == Severity.MINOR

    def test_line_scan_fallback(self) -> None:
        raw = """Some preamble text...
The issues are: [{"file": "d.py", "line": 3, "issue": "err", "severity": "LOW", "category": "maintainability"}] end of output"""
        result = parse_findings(raw_output=raw, model_name="test")
        assert len(result) == 1
        assert result[0].category == "maintainability"

    def test_empty_array(self) -> None:
        raw = "[]"
        result = parse_findings(raw_output=raw, model_name="test")
        assert result == []

    def test_no_json_raises_parse_error(self) -> None:
        raw = "No issues found in this code."
        with pytest.raises(ParseError, match="Could not extract JSON"):
            parse_findings(raw_output=raw, model_name="test")

    def test_malformed_entries_skipped(self) -> None:
        raw = json.dumps([
            {"file": "a.py", "line": 1, "issue": "good", "severity": "MAJOR", "category": "correctness"},
            {"file": "b.py", "missing_line": True},
            {"file": "c.py", "line": 3, "issue": "ok", "severity": "INVALID_SEV"},
        ])
        result = parse_findings(raw_output=raw, model_name="test")
        assert len(result) == 1
        assert result[0].issue == "good"

    def test_severity_case_insensitive(self) -> None:
        raw = json.dumps([
            {"file": "a.py", "line": 1, "issue": "bug", "severity": "critical", "category": "correctness"},
        ])
        result = parse_findings(raw_output=raw, model_name="test")
        assert result[0].severity == Severity.CRITICAL

    def test_model_name_attached(self) -> None:
        raw = json.dumps([
            {"file": "a.py", "line": 1, "issue": "bug", "severity": "LOW", "category": "correctness"},
        ])
        result = parse_findings(raw_output=raw, model_name="my-model")
        assert result[0].model_name == "my-model"

    def test_missing_category_defaults_to_unknown(self) -> None:
        raw = json.dumps([
            {"file": "a.py", "line": 1, "issue": "bug", "severity": "LOW"},
        ])
        result = parse_findings(raw_output=raw, model_name="test")
        assert result[0].category == "unknown"
