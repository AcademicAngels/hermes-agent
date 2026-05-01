#!/usr/bin/env python3
"""Initialize host-side Hermes config for the native runtime."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

import yaml


DEFAULT_HERMES_HOME = "/home/hermes_data"
DEFAULT_HINDSIGHT_API_URL = "http://localhost:18888"
DEFAULT_BANK_ID = "hermes"
DEFAULT_RECALL_BUDGET = "mid"
DEFAULT_IMAGE_PROVIDER = "openai"
DEFAULT_IMAGE_MODEL = "gpt-image-2-medium"
DEFAULT_MEMORY_PROVIDER = "hindsight"

HERMES_CHILD_DIRS = (
    "cron",
    "sessions",
    "logs",
    "hooks",
    "memories",
    "skills",
    "skins",
    "plans",
    "workspace",
    "home",
)


class ConfigInitError(RuntimeError):
    """Raised when an existing config cannot be safely updated."""


def _env_default(name: str, fallback: str) -> str:
    return os.environ.get(name) or fallback


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Initialize host-side Hermes config for native deployments.",
    )
    parser.add_argument(
        "--hermes-home",
        default=_env_default("HERMES_HOME", DEFAULT_HERMES_HOME),
        help="Hermes home directory.",
    )
    parser.add_argument(
        "--hindsight-api-url",
        default=_env_default("HOST_HINDSIGHT_API_URL", DEFAULT_HINDSIGHT_API_URL),
        help="Host-accessible Hindsight API URL.",
    )
    parser.add_argument(
        "--hindsight-bank-id",
        default=_env_default("HINDSIGHT_BANK_ID", DEFAULT_BANK_ID),
        help="Hindsight bank id.",
    )
    parser.add_argument(
        "--hindsight-budget",
        default=_env_default("HINDSIGHT_BUDGET", DEFAULT_RECALL_BUDGET),
        help="Hindsight recall budget.",
    )
    parser.add_argument(
        "--image-provider",
        default=_env_default("HERMES_AGENT_IMAGE_PROVIDER", DEFAULT_IMAGE_PROVIDER),
        help="Image generation provider.",
    )
    parser.add_argument(
        "--image-model",
        default=_env_default("OPENAI_IMAGE_MODEL", DEFAULT_IMAGE_MODEL),
        help="Image generation model.",
    )
    parser.add_argument(
        "--memory-provider",
        default=_env_default("HERMES_AGENT_MEMORY_PROVIDER", DEFAULT_MEMORY_PROVIDER),
        help="Memory provider.",
    )
    return parser.parse_args()


def ensure_dirs(hermes_home: Path) -> None:
    hermes_home.mkdir(parents=True, exist_ok=True)
    for dirname in HERMES_CHILD_DIRS:
        (hermes_home / dirname).mkdir(parents=True, exist_ok=True)
    (hermes_home / "hindsight").mkdir(parents=True, exist_ok=True)


def load_config(config_path: Path) -> dict[str, Any]:
    if not config_path.exists():
        return {}

    try:
        loaded = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise ConfigInitError(f"could not read YAML config {config_path}: {exc}") from exc

    if loaded is None:
        return {}
    if isinstance(loaded, dict):
        return loaded
    raise ConfigInitError(f"YAML config {config_path} must be a mapping")


def update_config(
    config: dict[str, Any],
    *,
    memory_provider: str,
    image_provider: str,
    image_model: str,
) -> dict[str, Any]:
    memory_config = config.setdefault("memory", {})
    if not isinstance(memory_config, dict):
        memory_config = {}
        config["memory"] = memory_config
    memory_config["provider"] = memory_provider

    image_config = config.setdefault("image_gen", {})
    if not isinstance(image_config, dict):
        image_config = {}
        config["image_gen"] = image_config
    image_config["provider"] = image_provider
    image_config["model"] = image_model

    provider_config = image_config.setdefault(image_provider, {})
    if not isinstance(provider_config, dict):
        provider_config = {}
        image_config[image_provider] = provider_config
    provider_config["model"] = image_model

    return config


def write_config(config_path: Path, config: dict[str, Any]) -> None:
    config_path.write_text(
        yaml.safe_dump(config, sort_keys=False, allow_unicode=True),
        encoding="utf-8",
    )


def write_hindsight_config(
    config_path: Path,
    config: dict[str, Any],
    *,
    api_url: str,
    bank_id: str,
    recall_budget: str,
) -> None:
    config.update(
        {
            "mode": "local_external",
            "api_url": api_url,
            "bank_id": bank_id,
            "recall_budget": recall_budget,
            "memory_mode": "hybrid",
        }
    )
    config_path.write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")


def load_hindsight_config(config_path: Path) -> dict[str, Any]:
    if not config_path.exists():
        return {}

    try:
        loaded = json.loads(config_path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise ConfigInitError(f"could not read Hindsight config {config_path}: {exc}") from exc

    if not isinstance(loaded, dict):
        raise ConfigInitError(f"Hindsight config {config_path} must be a JSON object")
    return loaded


def main() -> int:
    args = parse_args()
    hermes_home = Path(args.hermes_home).expanduser()

    ensure_dirs(hermes_home)

    config_path = hermes_home / "config.yaml"
    config = load_config(config_path)
    hindsight_config_path = hermes_home / "hindsight" / "config.json"
    hindsight_config = load_hindsight_config(hindsight_config_path)

    update_config(
        config,
        memory_provider=args.memory_provider,
        image_provider=args.image_provider,
        image_model=args.image_model,
    )
    write_config(config_path, config)
    write_hindsight_config(
        hindsight_config_path,
        hindsight_config,
        api_url=args.hindsight_api_url,
        bank_id=args.hindsight_bank_id,
        recall_budget=args.hindsight_budget,
    )

    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except ConfigInitError as exc:
        print(f"error: {exc}", file=sys.stderr)
        raise SystemExit(1)
