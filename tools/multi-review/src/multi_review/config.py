"""YAML config loading and validation."""

import shutil
from pathlib import Path

import structlog
import yaml
from pydantic import BaseModel, Field

from multi_review.constants import (
    CONFIG_DIR_NAME,
    CONFIG_FILENAMES,
    DEFAULT_CONTEXT_TYPE,
    DEFAULT_OUTPUT_FORMAT,
    DEFAULT_TASK,
    DEFAULT_TIMEOUT,
)
from multi_review.exceptions import ConfigError
from multi_review.types import ContextType, OutputFormat, TaskType

logger = structlog.get_logger()


class ModelConfig(BaseModel):
    """Configuration for a single AI model CLI."""

    name: str
    command: str
    enabled: bool = True
    timeout: int = DEFAULT_TIMEOUT


class DefaultsConfig(BaseModel):
    """Default settings for review runs."""

    task: TaskType = DEFAULT_TASK
    context_type: ContextType = DEFAULT_CONTEXT_TYPE


class OutputConfig(BaseModel):
    """Output formatting settings."""

    format: OutputFormat = DEFAULT_OUTPUT_FORMAT
    color: bool = True


class AppConfig(BaseModel):
    """Top-level application configuration."""

    models: list[ModelConfig] = Field(default_factory=lambda: [
        ModelConfig(name="claude", command="claude -p"),
        ModelConfig(name="codex", command="codex -q"),
    ])
    defaults: DefaultsConfig = Field(default_factory=DefaultsConfig)
    output: OutputConfig = Field(default_factory=OutputConfig)


def _find_config_file(*, explicit_path: Path | None = None) -> Path | None:
    """Search config chain: explicit > cwd > ~/.config > built-in defaults."""
    if explicit_path is not None:
        if not explicit_path.is_file():
            raise ConfigError(f"Config file not found: {explicit_path}")
        return explicit_path

    cwd = Path.cwd()
    for filename in CONFIG_FILENAMES:
        candidate = cwd / filename
        if candidate.is_file():
            return candidate

    config_home = Path.home() / ".config" / CONFIG_DIR_NAME
    for filename in CONFIG_FILENAMES:
        candidate = config_home / filename
        if candidate.is_file():
            return candidate

    return None


def load_config(*, config_path: Path | None = None) -> AppConfig:
    """Load and validate configuration from YAML or defaults."""
    path = _find_config_file(explicit_path=config_path)
    if path is None:
        logger.info("no_config_file_found", using="built-in defaults")
        return AppConfig()

    logger.info("loading_config", path=str(path))
    raw = path.read_text(encoding="utf-8")
    data = yaml.safe_load(raw)
    if not isinstance(data, dict):
        raise ConfigError(f"Config file must be a YAML mapping: {path}")

    return AppConfig.model_validate(data)


def check_model_availability(*, config: AppConfig) -> list[ModelConfig]:
    """Return enabled models whose CLI command is found on PATH."""
    available: list[ModelConfig] = []
    for model in config.models:
        if not model.enabled:
            logger.info("model_disabled", model=model.name)
            continue
        binary = model.command.split()[0]
        if shutil.which(binary) is not None:
            available.append(model)
            logger.info("model_available", model=model.name, command=model.command)
        else:
            logger.warning("model_not_found", model=model.name, binary=binary)
    return available


def generate_default_config() -> str:
    """Return default config as YAML string for `config init`."""
    default = AppConfig()
    data = default.model_dump(mode="json")
    return yaml.dump(data, default_flow_style=False, sort_keys=False)
