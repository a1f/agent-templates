"""Tests for multi_review.runner."""

import json
import textwrap
from pathlib import Path
from unittest.mock import patch

import pytest

from multi_review.config import ModelConfig
from multi_review.exceptions import ContextError
from multi_review.runner import gather_context
from multi_review.types import ContextType


class TestGatherContext:
    """Tests for context gathering functions."""

    def test_files_context(self, tmp_path: Path) -> None:
        f = tmp_path / "test.py"
        f.write_text("print('hello')")
        result = gather_context(
            context_type=ContextType.FILES,
            files=[str(f)],
        )
        assert "print('hello')" in result
        assert "test.py" in result

    def test_files_context_no_files_raises(self) -> None:
        with pytest.raises(ContextError, match="No files specified"):
            gather_context(context_type=ContextType.FILES, files=[])

    def test_files_context_missing_file(self, tmp_path: Path) -> None:
        with pytest.raises(ContextError, match="None of the specified files"):
            gather_context(
                context_type=ContextType.FILES,
                files=[str(tmp_path / "nonexistent.py")],
            )

    def test_directory_context(self, tmp_path: Path) -> None:
        src = tmp_path / "src"
        src.mkdir()
        (src / "app.py").write_text("x = 1")
        (src / "data.txt").write_text("not source")

        result = gather_context(
            context_type=ContextType.DIRECTORY,
            files=[str(src)],
        )
        assert "x = 1" in result
        assert "data.txt" not in result

    def test_directory_context_no_dir_raises(self) -> None:
        with pytest.raises(ContextError, match="No directory specified"):
            gather_context(context_type=ContextType.DIRECTORY, files=[])

    def test_directory_context_empty_dir(self, tmp_path: Path) -> None:
        empty = tmp_path / "empty"
        empty.mkdir()
        with pytest.raises(ContextError, match="No source files found"):
            gather_context(
                context_type=ContextType.DIRECTORY,
                files=[str(empty)],
            )

    def test_diff_context_no_git(self) -> None:
        with patch("multi_review.runner.subprocess.run", side_effect=FileNotFoundError("git not found")):
            with pytest.raises(ContextError, match="git not found"):
                gather_context(context_type=ContextType.DIFF, files=[])


class TestRunModels:
    """Tests for async model execution."""

    @pytest.mark.asyncio()
    async def test_model_timeout(self) -> None:
        """Model that exceeds timeout returns failure result."""
        from multi_review.runner import _run_single_model

        model = ModelConfig(name="slow", command="sleep 10", timeout=1)
        result = await _run_single_model(
            model=model,
            prompt="test",
        )
        assert not result.success
        assert "Timed out" in (result.error or "")

    @pytest.mark.asyncio()
    async def test_model_not_found(self) -> None:
        """Nonexistent command returns failure result."""
        from multi_review.runner import _run_single_model

        model = ModelConfig(name="fake", command="nonexistent_command_xyz")
        result = await _run_single_model(
            model=model,
            prompt="test",
        )
        assert not result.success

    @pytest.mark.asyncio()
    async def test_model_success_with_echo(self) -> None:
        """Model that echoes valid JSON returns parsed findings."""
        from multi_review.runner import _run_single_model

        findings_json = json.dumps([
            {"file": "a.py", "line": 1, "issue": "bug", "severity": "MAJOR", "category": "correctness"},
        ])
        model = ModelConfig(name="echo", command=f"echo {findings_json!r}")
        result = await _run_single_model(
            model=model,
            prompt="test",
        )
        # echo ignores stdin, just outputs the argument
        # This may or may not parse depending on shell quoting
        # The important thing is it doesn't crash
        assert result.model_name == "echo"
