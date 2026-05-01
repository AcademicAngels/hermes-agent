# Native Hermes Agent With Docker Sidecars Design

## Goal

Hermes Agent must run natively on the host so the CLI has normal access to the
host terminal, filesystem, shell, git checkout, editor, and permissions. Docker
should remain only for services that benefit from containerization:
Hindsight, PostgreSQL with pgvectorscale, and the cron memory ingestor sidecar.

The deployment must keep large runtime state under `/home` and avoid adding new
Python environments or dependency caches under the root filesystem.

## Current State

The current `docker-compose.agent.yml` starts a long-lived `hermes-agent`
container from `nousresearch/hermes-agent:latest`. The CLI can be used with:

```bash
docker compose --env-file .env.agent -f docker-compose.agent.yml \
  exec hermes-agent hermes
```

That proves the image works, but it does not satisfy the native CLI requirement.
The `hermes` process still runs inside Docker.

The Hindsight side is working with:

- `timescale/timescaledb-ha:pg18-all-oss`
- PostgreSQL data under `/home/hermes_data/hindsight-postgres`
- `HINDSIGHT_API_VECTOR_EXTENSION=pgvectorscale`
- Z.ai `embedding-3`, which uses 2048-dimensional embeddings
- DiskANN indexes created by Hindsight for 2048-dimensional vectors

Root filesystem inspection found no standard venv to remove. There is no
`/usr/local/lib/hermes-agent`, no `/opt/hermes`, and no root-level `pyvenv.cfg`.
The relevant root filesystem pressure points are:

- `/usr/local/lib/python3.12/dist-packages` at about 1.6 GB, from previous
  system Python package installs
- `/var/lib/containerd` at about 29 GB

The Python package directory is not a venv. It should only be cleaned after the
new native Hermes runtime is verified, because `/usr/local/bin` currently has
commands that depend on that global Python package set.

## Chosen Architecture

Use a host-native Hermes runtime with Docker sidecars.

```text
/home/github/hermes-agent
  Source checkout on personal-dev.

/home/hermes_runtime/venv
  Host Python virtual environment for Hermes Agent.

/home/hermes_data
  Hermes data, config, sessions, logs, cron output, skills, and Hindsight client config.

/usr/local/bin/hermes
  Thin wrapper that executes /home/hermes_runtime/venv/bin/hermes.

Docker Compose services:
  hindsight-postgres
  hindsight
  hermes-cron-memory-ingestor
```

The host command:

```bash
hermes
```

must execute a host process, equivalent to:

```bash
HERMES_HOME=/home/hermes_data \
  /home/hermes_runtime/venv/bin/hermes "$@"
```

It must not call `docker exec`.

## Runtime Layout

The Hermes Python environment lives outside the repository:

```text
/home/hermes_runtime/venv
```

This avoids polluting the git working tree and keeps dependencies on the
`/home` filesystem. The venv should install the current checkout in editable
mode so branch changes in `/home/github/hermes-agent` are reflected without
copying source code:

```bash
/home/hermes_runtime/venv/bin/python -m pip install -e /home/github/hermes-agent
```

If `uv` is used, its cache should also be redirected under `/home`, for example:

```bash
UV_CACHE_DIR=/home/hermes_runtime/uv-cache
```

The wrapper at `/usr/local/bin/hermes` should be small and stable. It should:

- set `HERMES_HOME=/home/hermes_data` if the caller did not provide it
- load non-Docker runtime environment from `/home/github/hermes-agent/.env.agent`
  when present
- execute `/home/hermes_runtime/venv/bin/hermes "$@"`
- not contain secrets directly

## Docker Services

`docker-compose.agent.yml` should stop running the `hermes-agent` service.

The compose stack should retain:

- `hindsight-postgres`
- `hindsight`
- `hermes-cron-memory-ingestor`

The compose stack should remove:

- `hermes-agent`
- `hermes-config-init` if its only purpose is initializing the Hermes container

Hermes config initialization should move to the host setup script so
`/home/hermes_data/config.yaml` and `/home/hermes_data/hindsight/config.json`
are created without pulling or running the Hermes Agent Docker image.

`hindsight-postgres` must keep:

```yaml
image: timescale/timescaledb-ha:pg18-all-oss
volumes:
  - ${HERMES_DATA_DIR:-/home/hermes_data}/hindsight-postgres:/var/lib/postgresql
```

`hindsight` must keep:

```env
HINDSIGHT_API_VECTOR_EXTENSION=pgvectorscale
HINDSIGHT_API_EMBEDDINGS_PROVIDER=openai
HINDSIGHT_API_EMBEDDINGS_OPENAI_BASE_URL=https://open.bigmodel.cn/api/paas/v4
HINDSIGHT_API_EMBEDDINGS_OPENAI_MODEL=embedding-3
```

Secrets stay in the local `.env.agent`, which remains ignored by git.

## Configuration

The setup should ensure `/home/hermes_data/config.yaml` contains:

```yaml
memory:
  provider: hindsight

image_gen:
  provider: openai
  model: gpt-image-2-medium
  openai:
    model: gpt-image-2-medium
```

The setup should ensure `/home/hermes_data/hindsight/config.json` contains:

```json
{
  "mode": "local_external",
  "api_url": "http://localhost:18888",
  "bank_id": "hermes",
  "recall_budget": "mid",
  "memory_mode": "hybrid"
}
```

Host-native Hermes should use the host-published Hindsight port
`http://localhost:18888`, not the Docker-internal service name
`http://hindsight:8888`.

The cron memory ingestor remains inside Docker, so it should continue to use
Docker-internal `HINDSIGHT_URL=http://hindsight:8888`.

## Cleanup Strategy

Cleanup must happen after the new native runtime is verified.

First verify:

```bash
/usr/local/bin/hermes --version
HERMES_HOME=/home/hermes_data /usr/local/bin/hermes --version
docker compose --env-file .env.agent -f docker-compose.agent.yml ps
```

Then clean old root filesystem Python packages only if they are confirmed to be
from the previous global install and no longer needed. The main candidate is:

```text
/usr/local/lib/python3.12/dist-packages
```

This is not a venv and should not be removed blindly. It currently backs
commands under `/usr/local/bin`, such as `openai`, `pytest`, `playwright`,
`hermes-worker`, and `copaw-worker`.

The larger root filesystem pressure point is:

```text
/var/lib/containerd
```

That should be handled separately from the Hermes native install. It may contain
containerd image layers or snapshot state and needs containerd-aware cleanup, not
Python cleanup.

## Testing

The implementation should verify:

- `hermes --version` runs on the host and does not call Docker
- `which hermes` resolves to `/usr/local/bin/hermes`
- the process path or wrapper output confirms `/home/hermes_runtime/venv`
- `/home/hermes_data/config.yaml` uses Hindsight and OpenAI image generation
- `/home/hermes_data/hindsight/config.json` points host Hermes to
  `http://localhost:18888`
- `docker compose ps` shows Hindsight, Postgres, and cron ingestor running
- Hindsight logs still show `pgvectorscale` and 2048-dimensional indexes
- `.env.agent` remains ignored by git and is not committed

## Risks

Installing `.[all]` can be large. The setup must use `/home/hermes_runtime` for
venv and cache locations to avoid increasing root filesystem pressure.

Cleaning `/usr/local/lib/python3.12/dist-packages` can break unrelated global
Python commands. It should be treated as a post-verification cleanup with a
specific file list or a deliberate whole-directory removal decision.

Host-native Hermes and Dockerized ingestor use different Hindsight URLs. The
host CLI must use `localhost:18888`; the Docker sidecar must use
`hindsight:8888`.
