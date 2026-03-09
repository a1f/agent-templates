"""Tests for multi_review.cli."""

import logging
from pathlib import Path
from unittest.mock import patch

import structlog
from click.testing import CliRunner

from multi_review.cli import main

# Ensure structlog is configured for tests
structlog.configure(
    wrapper_class=structlog.make_filtering_bound_logger(logging.CRITICAL),
)


class TestConfigCommands:
    """Tests for config subcommands."""

    def test_config_show(self) -> None:
        runner = CliRunner()
        result = runner.invoke(main, ["config", "show"])
        assert result.exit_code == 0, result.output
        assert "claude" in result.output

    def test_config_init_creates_file(self, tmp_path: Path) -> None:
        runner = CliRunner()
        config_dir = tmp_path / ".config" / "multi-review"
        with patch("multi_review.cli.Path.home", return_value=tmp_path):
            result = runner.invoke(main, ["config", "init"])
        assert result.exit_code == 0, result.output
        assert (config_dir / "config.yaml").exists()

    def test_config_init_refuses_overwrite(self, tmp_path: Path) -> None:
        runner = CliRunner()
        config_dir = tmp_path / ".config" / "multi-review"
        config_dir.mkdir(parents=True)
        (config_dir / "config.yaml").write_text("existing: true")
        with patch("multi_review.cli.Path.home", return_value=tmp_path):
            result = runner.invoke(main, ["config", "init"])
        assert result.exit_code != 0
        assert "already exists" in result.output


class TestRunCommand:
    """Tests for the run subcommand."""

    def test_no_models_available(self) -> None:
        runner = CliRunner()
        with patch("multi_review.cli.check_model_availability", return_value=[]):
            result = runner.invoke(main, ["run", "--task", "bug-hunting"])
        assert result.exit_code != 0
        assert "No models available" in result.output

    def test_invalid_config_path(self) -> None:
        runner = CliRunner()
        result = runner.invoke(main, ["run", "--config", "/nonexistent/path.yaml"])
        assert result.exit_code != 0

    def test_custom_config_file(self, tmp_path: Path) -> None:
        config_file = tmp_path / "custom.yaml"
        config_file.write_text(
            "models:\n"
            "  - name: test\n"
            "    command: echo test\n"
            "    enabled: false\n"
        )
        runner = CliRunner()
        result = runner.invoke(main, ["run", "--config", str(config_file)])
        # Should fail because no models are enabled/available
        assert result.exit_code != 0
