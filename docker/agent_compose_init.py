"""Initialize profile config for docker-compose.agent.yml.

The stock Docker entrypoint copies the full upstream config template into the
mounted HERMES_HOME on first start. This helper keeps that behavior, then applies
the few agent-first defaults this compose file depends on.
"""

from __future__ import annotations

import json
import os
import shutil
from pathlib import Path

import yaml


HERMES_HOME = Path(os.environ.get("HERMES_HOME", "/home/agent/.hermes"))
INSTALL_DIR = Path("/opt/hermes")


def _copy_if_missing(src: Path, dst: Path) -> None:
    if not dst.exists() and src.exists():
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(src, dst)


def _load_yaml(path: Path) -> dict:
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle) or {}
    return data if isinstance(data, dict) else {}


def _write_yaml(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        yaml.safe_dump(data, handle, sort_keys=False, allow_unicode=True)


def main() -> None:
    HERMES_HOME.mkdir(parents=True, exist_ok=True)
    for child in (
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
    ):
        (HERMES_HOME / child).mkdir(parents=True, exist_ok=True)

    _copy_if_missing(INSTALL_DIR / ".env.example", HERMES_HOME / ".env")
    _copy_if_missing(INSTALL_DIR / "cli-config.yaml.example", HERMES_HOME / "config.yaml")
    _copy_if_missing(INSTALL_DIR / "docker" / "SOUL.md", HERMES_HOME / "SOUL.md")

    config_path = HERMES_HOME / "config.yaml"
    config = _load_yaml(config_path)

    memory = config.setdefault("memory", {})
    if isinstance(memory, dict):
        memory["provider"] = os.environ.get("HERMES_AGENT_MEMORY_PROVIDER", "hindsight")

    image_gen = config.setdefault("image_gen", {})
    if isinstance(image_gen, dict):
        image_provider = os.environ.get("HERMES_AGENT_IMAGE_PROVIDER", "openai")
        image_model = os.environ.get("OPENAI_IMAGE_MODEL", "gpt-image-2-medium")
        image_gen["provider"] = image_provider
        image_gen["model"] = image_model
        provider_config = image_gen.setdefault(image_provider, {})
        if isinstance(provider_config, dict):
            provider_config["model"] = image_model

    _write_yaml(config_path, config)

    hindsight_dir = HERMES_HOME / "hindsight"
    hindsight_dir.mkdir(parents=True, exist_ok=True)
    hindsight_config = {
        "mode": os.environ.get("HINDSIGHT_MODE", "local_external"),
        "api_url": os.environ.get("HINDSIGHT_API_URL", "http://hindsight:8888"),
        "bank_id": os.environ.get("HINDSIGHT_BANK_ID", "hermes"),
        "recall_budget": os.environ.get("HINDSIGHT_BUDGET", "mid"),
        "memory_mode": "hybrid",
    }
    with (hindsight_dir / "config.json").open("w", encoding="utf-8") as handle:
        json.dump(hindsight_config, handle, indent=2)
        handle.write("\n")


if __name__ == "__main__":
    main()
