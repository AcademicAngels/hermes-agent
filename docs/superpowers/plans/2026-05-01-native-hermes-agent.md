# Native Hermes Agent Runtime Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Run Hermes Agent natively on the host from `/home/hermes_runtime/venv` while Docker only runs Hindsight, PostgreSQL, and the cron memory ingestor.

**Architecture:** A host setup script creates `/home/hermes_runtime/venv`, installs the current checkout in editable mode, initializes `/home/hermes_data`, and writes a thin `/usr/local/bin/hermes` wrapper. `docker-compose.agent.yml` is reduced to service sidecars, and docs are updated so CLI usage is native instead of `docker exec`.

**Tech Stack:** Bash, Python stdlib, Docker Compose, uv/pip, YAML/JSON configuration, system Python virtualenv.

---

## File Map

- Create `scripts/setup-native-agent.sh`: host setup entrypoint. It owns `/home/hermes_runtime`, creates the venv, installs this checkout, writes the Hermes wrapper, and calls the config initializer.
- Create `scripts/native_agent_config_init.py`: idempotent host config initializer for `/home/hermes_data/config.yaml` and `/home/hermes_data/hindsight/config.json`.
- Modify `docker-compose.agent.yml`: remove `hermes-agent` and `hermes-config-init`; keep only sidecar services.
- Modify `.env.agent.example`: distinguish host CLI settings from Docker sidecar settings, add `HERMES_RUNTIME_DIR`, `HOST_HINDSIGHT_API_URL`, and `UV_CACHE_DIR`.
- Modify `docs/deploy/agent-first.md`: rename the operational model to native agent with Docker sidecars and replace `docker exec` CLI usage with `hermes`.
- Test with shell commands and targeted script execution because this is deployment glue, not a Python library path.

## Task 1: Host Config Initializer

**Files:**
- Create: `scripts/native_agent_config_init.py`
- Test: local command using temporary directories

- [ ] **Step 1: Create the failing smoke command**

Run this before the file exists:

```bash
python3 scripts/native_agent_config_init.py --hermes-home /tmp/hermes-native-test --hindsight-api-url http://localhost:18888
```

Expected: FAIL with a message like `can't open file` because the script does not exist.

- [ ] **Step 2: Add `scripts/native_agent_config_init.py`**

Create the file with this content:

```python
#!/usr/bin/env python3
"""Initialize host-native Hermes Agent config."""

from __future__ import annotations

import argparse
import json
import os
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


def _load_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle) or {}
    return data if isinstance(data, dict) else {}


def _write_yaml(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        yaml.safe_dump(data, handle, sort_keys=False, allow_unicode=True)


def initialize_config(
    hermes_home: Path,
    hindsight_api_url: str,
    bank_id: str,
    recall_budget: str,
    image_provider: str,
    image_model: str,
    memory_provider: str,
) -> None:
    hermes_home.mkdir(parents=True, exist_ok=True)
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
        (hermes_home / child).mkdir(parents=True, exist_ok=True)

    config_path = hermes_home / "config.yaml"
    config = _load_yaml(config_path)

    memory = config.setdefault("memory", {})
    if isinstance(memory, dict):
        memory["provider"] = memory_provider

    image_gen = config.setdefault("image_gen", {})
    if isinstance(image_gen, dict):
        image_gen["provider"] = image_provider
        image_gen["model"] = image_model
        provider_config = image_gen.setdefault(image_provider, {})
        if isinstance(provider_config, dict):
            provider_config["model"] = image_model

    _write_yaml(config_path, config)

    hindsight_dir = hermes_home / "hindsight"
    hindsight_dir.mkdir(parents=True, exist_ok=True)
    hindsight_config = {
        "mode": "local_external",
        "api_url": hindsight_api_url,
        "bank_id": bank_id,
        "recall_budget": recall_budget,
        "memory_mode": "hybrid",
    }
    with (hindsight_dir / "config.json").open("w", encoding="utf-8") as handle:
        json.dump(hindsight_config, handle, indent=2)
        handle.write("\n")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--hermes-home", default=os.environ.get("HERMES_HOME", DEFAULT_HERMES_HOME))
    parser.add_argument("--hindsight-api-url", default=os.environ.get("HOST_HINDSIGHT_API_URL", DEFAULT_HINDSIGHT_API_URL))
    parser.add_argument("--hindsight-bank-id", default=os.environ.get("HINDSIGHT_BANK_ID", DEFAULT_BANK_ID))
    parser.add_argument("--hindsight-budget", default=os.environ.get("HINDSIGHT_BUDGET", DEFAULT_RECALL_BUDGET))
    parser.add_argument("--image-provider", default=os.environ.get("HERMES_AGENT_IMAGE_PROVIDER", DEFAULT_IMAGE_PROVIDER))
    parser.add_argument("--image-model", default=os.environ.get("OPENAI_IMAGE_MODEL", DEFAULT_IMAGE_MODEL))
    parser.add_argument("--memory-provider", default=os.environ.get("HERMES_AGENT_MEMORY_PROVIDER", DEFAULT_MEMORY_PROVIDER))
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    initialize_config(
        hermes_home=Path(args.hermes_home),
        hindsight_api_url=args.hindsight_api_url,
        bank_id=args.hindsight_bank_id,
        recall_budget=args.hindsight_budget,
        image_provider=args.image_provider,
        image_model=args.image_model,
        memory_provider=args.memory_provider,
    )


if __name__ == "__main__":
    main()
```

- [ ] **Step 3: Run the initializer against a temp home**

```bash
rm -rf /tmp/hermes-native-test
python3 scripts/native_agent_config_init.py --hermes-home /tmp/hermes-native-test --hindsight-api-url http://localhost:18888
```

Expected: exit 0.

- [ ] **Step 4: Inspect generated config**

```bash
grep -nE 'provider: hindsight|image_gen:|provider: openai|gpt-image-2-medium' /tmp/hermes-native-test/config.yaml
cat /tmp/hermes-native-test/hindsight/config.json
```

Expected grep output includes `provider: hindsight`, `image_gen:`, `provider: openai`, and `gpt-image-2-medium`. Expected JSON contains `"api_url": "http://localhost:18888"`.

- [ ] **Step 5: Commit**

```bash
git add scripts/native_agent_config_init.py
git commit -m "feat(deploy): add native config initializer"
```

## Task 2: Host Setup Script and Wrapper

**Files:**
- Create: `scripts/setup-native-agent.sh`
- Modify: `.env.agent.example`
- Test: syntax check and dry-run path inspection

- [ ] **Step 1: Add runtime variables to `.env.agent.example`**

Add these lines near the top, after `HERMES_DATA_DIR=/home/hermes_data`:

```env
# Host-native Hermes runtime. Dependencies and uv cache stay under /home.
HERMES_RUNTIME_DIR=/home/hermes_runtime
HERMES_VENV_DIR=/home/hermes_runtime/venv
UV_CACHE_DIR=/home/hermes_runtime/uv-cache
HOST_HINDSIGHT_API_URL=http://localhost:18888
```

- [ ] **Step 2: Add `scripts/setup-native-agent.sh`**

Create the file with this content:

```bash
#!/usr/bin/env bash
set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE="${ENV_FILE:-$REPO_DIR/.env.agent}"

if [ -f "$ENV_FILE" ]; then
  set -a
  # shellcheck disable=SC1090
  . "$ENV_FILE"
  set +a
fi

HERMES_DATA_DIR="${HERMES_DATA_DIR:-/home/hermes_data}"
HERMES_RUNTIME_DIR="${HERMES_RUNTIME_DIR:-/home/hermes_runtime}"
HERMES_VENV_DIR="${HERMES_VENV_DIR:-$HERMES_RUNTIME_DIR/venv}"
UV_CACHE_DIR="${UV_CACHE_DIR:-$HERMES_RUNTIME_DIR/uv-cache}"
HOST_HINDSIGHT_API_URL="${HOST_HINDSIGHT_API_URL:-http://localhost:18888}"
HINDSIGHT_BANK_ID="${HINDSIGHT_BANK_ID:-hermes}"
HINDSIGHT_BUDGET="${HINDSIGHT_BUDGET:-mid}"
OPENAI_IMAGE_MODEL="${OPENAI_IMAGE_MODEL:-gpt-image-2-medium}"
WRAPPER_PATH="${WRAPPER_PATH:-/usr/local/bin/hermes}"
PYTHON_BIN="${PYTHON_BIN:-python3}"

export HERMES_HOME="$HERMES_DATA_DIR"
export UV_CACHE_DIR

install -d -m 755 "$HERMES_RUNTIME_DIR"
install -d -m 700 "$HERMES_DATA_DIR"

if ! command -v uv >/dev/null 2>&1; then
  echo "uv is required. Install uv first or provide it on PATH." >&2
  exit 1
fi

if [ ! -x "$HERMES_VENV_DIR/bin/python" ]; then
  uv venv "$HERMES_VENV_DIR" --python "$PYTHON_BIN"
fi

uv pip install --python "$HERMES_VENV_DIR/bin/python" -e "$REPO_DIR[all]"

"$HERMES_VENV_DIR/bin/python" "$REPO_DIR/scripts/native_agent_config_init.py" \
  --hermes-home "$HERMES_DATA_DIR" \
  --hindsight-api-url "$HOST_HINDSIGHT_API_URL" \
  --hindsight-bank-id "$HINDSIGHT_BANK_ID" \
  --hindsight-budget "$HINDSIGHT_BUDGET" \
  --image-model "$OPENAI_IMAGE_MODEL"

tmp_wrapper="$(mktemp)"
cat > "$tmp_wrapper" <<EOF
#!/usr/bin/env bash
set -euo pipefail

export HERMES_HOME="\${HERMES_HOME:-$HERMES_DATA_DIR}"

if [ -f "$ENV_FILE" ]; then
  set -a
  . "$ENV_FILE"
  set +a
fi

exec "$HERMES_VENV_DIR/bin/hermes" "\$@"
EOF

install -m 755 "$tmp_wrapper" "$WRAPPER_PATH"
rm -f "$tmp_wrapper"

echo "Hermes native runtime installed:"
echo "  repo:    $REPO_DIR"
echo "  venv:    $HERMES_VENV_DIR"
echo "  data:    $HERMES_DATA_DIR"
echo "  wrapper: $WRAPPER_PATH"
```

- [ ] **Step 3: Run shell syntax checks**

```bash
bash -n scripts/setup-native-agent.sh
python3 -m py_compile scripts/native_agent_config_init.py
```

Expected: exit 0.

- [ ] **Step 4: Verify `.env.agent` is still ignored**

```bash
git check-ignore -v .env.agent
```

Expected: output shows `.gitignore` matching `.env.agent`.

- [ ] **Step 5: Commit**

```bash
git add .env.agent.example scripts/setup-native-agent.sh
git commit -m "feat(deploy): add native hermes setup script"
```

## Task 3: Reduce Docker Compose to Sidecars

**Files:**
- Modify: `docker-compose.agent.yml`
- Test: `docker compose config --quiet`

- [ ] **Step 1: Edit `docker-compose.agent.yml`**

Remove the entire `hermes-config-init` service and the entire `hermes-agent` service.

In `hermes-cron-memory-ingestor`, remove the `depends_on` entry for `hermes-config-init`, leaving only Hindsight:

```yaml
    depends_on:
      hindsight:
        condition: service_started
```

Keep this environment value for the Dockerized ingestor:

```yaml
      HINDSIGHT_URL: ${HINDSIGHT_URL:-http://hindsight:8888}
```

Keep the bind mount:

```yaml
      - ${HERMES_DATA_DIR:-/home/hermes_data}:/home/agent/.hermes
```

- [ ] **Step 2: Update the quick-start comments at the top of `docker-compose.agent.yml`**

Replace the current CLI comment with:

```yaml
# Native Hermes CLI:
#   scripts/setup-native-agent.sh
#   hermes
```

Replace the pull comment so it no longer mentions `hermes-agent` or `hermes-config-init`:

```yaml
#   docker compose --env-file .env.agent -f docker-compose.agent.yml \
#     pull hindsight hindsight-postgres
```

- [ ] **Step 3: Validate compose syntax**

```bash
docker compose --env-file .env.agent -f docker-compose.agent.yml config --quiet
```

Expected: exit 0.

- [ ] **Step 4: Verify removed services are absent**

```bash
docker compose --env-file .env.agent -f docker-compose.agent.yml config --services
```

Expected output exactly lists:

```text
hindsight-postgres
hindsight
hermes-cron-memory-ingestor
```

- [ ] **Step 5: Commit**

```bash
git add docker-compose.agent.yml
git commit -m "feat(deploy): run only sidecars in agent compose"
```

## Task 4: Documentation Update

**Files:**
- Modify: `docs/deploy/agent-first.md`
- Test: text inspection

- [ ] **Step 1: Rewrite the document title and service list**

Change the title to:

```markdown
# Native Hermes Agent With Docker Sidecars
```

Replace the services section with:

```markdown
## Services

- Host `hermes` runs natively from `/home/hermes_runtime/venv`.
- `hindsight-postgres` stores Hindsight data with pgvectorscale/DiskANN.
- `hindsight` provides the local external Hindsight API and UI.
- `hermes-cron-memory-ingestor` retains cron output into Hindsight.

No `hermes-webui`, proxy, dashboard, Web UI token, Web UI port, Web UI volume,
or long-lived `hermes-agent` container is included.
```

- [ ] **Step 2: Replace the start section**

Use this start section:

```markdown
## Start

```bash
cp .env.agent.example .env.agent
scripts/setup-native-agent.sh
docker compose --env-file .env.agent -f docker-compose.agent.yml \
  pull hindsight hindsight-postgres
docker compose --env-file .env.agent -f docker-compose.agent.yml \
  build hermes-cron-memory-ingestor
docker compose --env-file .env.agent -f docker-compose.agent.yml up -d
```
```

- [ ] **Step 3: Replace the CLI section**

Use this CLI section:

```markdown
## Native CLI

```bash
hermes
hermes --version
hermes model
```

`/usr/local/bin/hermes` is a thin wrapper around
`/home/hermes_runtime/venv/bin/hermes`. The wrapper runs on the host, loads
`.env.agent` when present, and sets `HERMES_HOME=/home/hermes_data` by default.
It does not call `docker exec`.
```
```

- [ ] **Step 4: Update Hindsight URL explanation**

Add this paragraph:

```markdown
Host-native Hermes reaches Hindsight through the published host port:
`http://localhost:18888`. The Dockerized cron memory ingestor stays on the
Compose network and uses `http://hindsight:8888`.
```

- [ ] **Step 5: Remove stale Docker CLI text**

Run:

```bash
grep -nE 'docker compose .*exec hermes-agent|/opt/hermes/.venv|hermes-agent container' docs/deploy/agent-first.md
```

Expected: no output.

- [ ] **Step 6: Commit**

```bash
git add docs/deploy/agent-first.md
git commit -m "docs(deploy): document native hermes sidecar deployment"
```

## Task 5: Runtime Verification and Root Cleanup Decision

**Files:**
- No committed files unless cleanup notes are added later.
- Runtime paths: `/home/hermes_runtime`, `/home/hermes_data`, `/usr/local/bin/hermes`

- [ ] **Step 1: Run native setup**

```bash
scripts/setup-native-agent.sh
```

Expected: exits 0 and prints repo, venv, data, and wrapper paths. If writing `/usr/local/bin/hermes` requires elevated permissions, rerun with the approved escalation path.

- [ ] **Step 2: Verify native CLI**

```bash
which hermes
hermes --version
```

Expected:

```text
/usr/local/bin/hermes
Hermes Agent v0.11.0
```

The exact version suffix may include the current release date.

- [ ] **Step 3: Verify wrapper does not call Docker**

```bash
grep -n 'docker' /usr/local/bin/hermes
```

Expected: no output.

- [ ] **Step 4: Start sidecars**

```bash
docker compose --env-file .env.agent -f docker-compose.agent.yml up -d
```

Expected: exit 0.

- [ ] **Step 5: Verify sidecar services**

```bash
docker compose --env-file .env.agent -f docker-compose.agent.yml ps
```

Expected services are up:

```text
hindsight-postgres
hindsight-app
hermes-cron-memory-ingestor
```

- [ ] **Step 6: Verify host config**

```bash
grep -nE 'provider: hindsight|image_gen:|provider: openai|gpt-image-2-medium' /home/hermes_data/config.yaml
cat /home/hermes_data/hindsight/config.json
```

Expected: config uses Hindsight and OpenAI image generation; Hindsight JSON uses `"api_url": "http://localhost:18888"`.

- [ ] **Step 7: Verify Hindsight vector mode**

```bash
docker logs --tail 120 hindsight-app
```

Expected: logs include `pgvectorscale` and `2048-dimensional embeddings` or existing startup confirmation for the already-initialized database.

- [ ] **Step 8: Recheck root filesystem pressure**

```bash
df -h / /home
du -sh /usr/local/lib/python3.12/dist-packages /var/lib/containerd 2>/dev/null
```

Expected: output identifies current root pressure. Do not delete anything in this step.

- [ ] **Step 9: Decide cleanup scope**

If native Hermes works, decide whether to clean:

```text
/usr/local/lib/python3.12/dist-packages
/usr/local/bin commands that depend on those packages
/var/lib/containerd
```

Expected: cleanup is a separate explicit action because `dist-packages` is not a venv and `/var/lib/containerd` needs containerd-aware cleanup.

## Final Verification

- [ ] Run `git status -sb`
- [ ] Run `bash -n scripts/setup-native-agent.sh`
- [ ] Run `python3 -m py_compile scripts/native_agent_config_init.py`
- [ ] Run `docker compose --env-file .env.agent -f docker-compose.agent.yml config --quiet`
- [ ] Run `docker compose --env-file .env.agent -f docker-compose.agent.yml config --services`
- [ ] Confirm `.env.agent` is ignored with `git check-ignore -v .env.agent`
- [ ] Confirm no real secrets are staged with `git diff --cached`
- [ ] Push `personal-dev` after all commits if requested
