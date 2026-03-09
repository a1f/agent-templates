"""Tests for multi_review.config."""

from pathlib import Path

import pytest

from multi_review.config import AppConfig, load_config, check_model_availability, generate_default_config
from multi_review.exceptions import ConfigError
from multi_review.types import TaskType


class TestLoadConfig:
    """Tests for config loading."""

    def test_defaults_when_no_file(self) -> None:
        cfg = load_config()
        assert len(cfg.models) == 2
        assert cfg.models[0].name == "claude"
        assert cfg.defaults.task == TaskType.CODE_REVIEW

    def test_load_from_file(self, tmp_path: Path) -> None:
        config_file = tmp_path / "config.yaml"
        config_file.write_text(
            "models:\n"
            "  - name: test-model\n"
            "    command: test-cli\n"
            "    timeout: 60\n"
            "defaults:\n"
            "  task: bug-hunting\n"
        )
        cfg = load_config(config_path=config_file)
        assert len(cfg.models) == 1
        assert cfg.models[0].name == "test-model"
        assert cfg.models[0].timeout == 60
        assert cfg.defaults.task == TaskType.BUG_HUNTING

    def test_missing_file_raises(self, tmp_path: Path) -> None:
        with pytest.raises(ConfigError, match="not found"):
            load_config(config_path=tmp_path / "nope.yaml")

    def test_invalid_yaml_raises(self, tmp_path: Path) -> None:
        config_file = tmp_path / "bad.yaml"
        config_file.write_text("just a string")
        with pytest.raises(ConfigError, match="YAML mapping"):
            load_config(config_path=config_file)


class TestCheckModelAvailability:
    """Tests for model availability checking."""

    def test_disabled_model_skipped(self) -> None:
        cfg = AppConfig(models=[
            {"name": "disabled", "command": "echo test", "enabled": False},  # type: ignore[list-item]
        ])
        result = check_model_availability(config=cfg)
        assert result == []

    def test_missing_binary_skipped(self) -> None:
        cfg = AppConfig(models=[
            {"name": "missing", "command": "nonexistent_binary_xyz", "enabled": True},  # type: ignore[list-item]
        ])
        result = check_model_availability(config=cfg)
        assert result == []

    def test_available_binary_included(self) -> None:
        cfg = AppConfig(models=[
            {"name": "echo", "command": "echo test", "enabled": True},  # type: ignore[list-item]
        ])
        result = check_model_availability(config=cfg)
        assert len(result) == 1
        assert result[0].name == "echo"


class TestGenerateDefaultConfig:
    """Tests for default config generation."""

    def test_generates_yaml(self) -> None:
        output = generate_default_config()
        assert "models:" in output
        assert "claude" in output
