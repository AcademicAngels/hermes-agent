# Native Hermes Agent With Docker Sidecars

This deployment runs the Hermes CLI natively on the host and uses
`docker-compose.agent.yml` for the local Hindsight sidecars.

## Services

- Host `hermes` runs natively from `/home/hermes_runtime/venv`.
- `hindsight-postgres` stores Hindsight data with pgvectorscale/DiskANN.
- `hindsight` provides the local external Hindsight API and UI.
- `hermes-cron-memory-ingestor` retains cron output into Hindsight.

No `hermes-webui`, proxy, dashboard, Web UI token, Web UI port, Web UI volume,
or long-lived `hermes-agent` container is included.

## Start

```bash
cp .env.agent.example .env.agent
scripts/setup-native-agent.sh
hermes --version
docker compose --env-file .env.agent -f docker-compose.agent.yml pull hindsight hindsight-postgres
docker compose --env-file .env.agent -f docker-compose.agent.yml build hermes-cron-memory-ingestor
docker compose --env-file .env.agent -f docker-compose.agent.yml up -d --remove-orphans
```

For migrations from the old Docker CLI flow, verify `hermes --version` works
through the native `/usr/local/bin/hermes` wrapper and confirm
`/home/hermes_data/config.yaml` was generated before starting compose with
`--remove-orphans`.

`--remove-orphans` removes services left over from older deployments, including
the former `hermes-agent` service.

`hindsight` and `hindsight-postgres` use published images. The database image
defaults to
`timescale/timescaledb-ha:pg18-all-oss` because Z.ai `embedding-3` returns
2048-dimensional vectors, which exceed pgvector HNSW's 2000-dimensional index
limit. `hermes-cron-memory-ingestor` is built locally from the sibling
`/home/github/hermes-cron-memory-ingestor` project because it is our sidecar for
writing Hermes cron output into Hindsight memory.

## Native CLI

```bash
hermes
hermes --version
hermes model
```

`/usr/local/bin/hermes` is a host wrapper for
`/home/hermes_runtime/venv/bin/hermes`. It loads `.env.agent`, defaults
`HERMES_HOME=/home/hermes_data`, and runs the native CLI directly without
calling Docker.

The host data directory is `/home/hermes_data`.
Hindsight Postgres data is stored under
`/home/hermes_data/hindsight-postgres`, mounted at `/var/lib/postgresql` inside
the database container to match the PostgreSQL 18 image layout.

## Hermes Config

`scripts/setup-native-agent.sh` creates `/home/hermes_data/config.yaml` and
applies these native Hermes settings:

```yaml
memory:
  provider: hindsight

image_gen:
  provider: openai
  model: gpt-image-2-medium
  openai:
    model: gpt-image-2-medium
```

It also writes `/home/hermes_data/hindsight/config.json` for local external
Hindsight:

```json
{
  "mode": "local_external",
  "api_url": "http://localhost:18888",
  "bank_id": "hermes",
  "recall_budget": "mid",
  "memory_mode": "hybrid"
}
```

Host-native Hermes reaches Hindsight through `http://localhost:18888`. The
Dockerized cron memory ingestor reaches the same service through
`http://hindsight:8888` on the compose network.

The host-native Hindsight URL is written by `scripts/setup-native-agent.sh`
from `HOST_HINDSIGHT_API_URL`, which defaults to `http://localhost:18888`:

```env
HOST_HINDSIGHT_API_URL=http://localhost:18888
```

The OpenAI-compatible image endpoint is configured with environment variables
in `.env.agent`:

```env
OPENAI_API_KEY=...
OPENAI_BASE_URL=https://api.husanai.com/v1
OPENAI_IMAGE_MODEL=gpt-image-2-medium
```

The Dockerized cron memory ingestor uses `HINDSIGHT_URL`, which defaults to the
compose service URL:

```env
HINDSIGHT_URL=http://hindsight:8888
```

Hindsight itself also needs LLM credentials. Embeddings use Hindsight's
OpenAI-compatible provider with Z.ai `embedding-3`. If a database was previously
initialized with a different embedding dimension, back it up and reinitialize
or re-embed it before switching models.

```env
HINDSIGHT_LLM_API_KEY=...
HINDSIGHT_LLM_BASE_URL=...
HINDSIGHT_LLM_MODEL=...
HINDSIGHT_VECTOR_EXTENSION=pgvectorscale
HINDSIGHT_EMBEDDINGS_PROVIDER=openai
HINDSIGHT_EMBEDDINGS_OPENAI_BASE_URL=...
HINDSIGHT_EMBEDDINGS_OPENAI_API_KEY=...
HINDSIGHT_EMBEDDINGS_OPENAI_MODEL=...
```

## Operations Runbook

The current deployment is host-native Hermes plus Docker sidecars. Do not use
the old `hermes-web-ui` deployment path as the operational source of truth.

### Runtime Layout

- Repository: `/home/github/hermes-agent`
- Native runtime: `/home/hermes_runtime/venv`
- Host wrapper: `/usr/local/bin/hermes`
- Hermes data: `/home/hermes_data`
- Default `HERMES_HOME`: `/home/hermes_data`
- Environment file loaded by the wrapper: `/home/github/hermes-agent/.env.agent`
- Native gateway systemd unit: `/etc/systemd/system/hermes-gateway.service`

The gateway process is expected to look like:

```bash
/home/hermes_runtime/venv/bin/python -m hermes_cli.main gateway run --replace
```

### Managed Services

Hermes runs as a native systemd system service:

```bash
env HERMES_HOME=/home/hermes_data /usr/local/bin/hermes gateway status --system
systemctl status hermes-gateway.service --no-pager
```

The service is responsible for:

- gateway platform adapters
- the local API server
- the embedded cron ticker
- the embedded kanban dispatcher

The Docker compose sidecars are responsible for Hindsight and cron-output
ingestion only:

```bash
docker compose --env-file .env.agent -f docker-compose.agent.yml ps
docker ps --format 'table {{.Names}}\t{{.Status}}\t{{.Image}}'
```

Expected sidecars:

- `hindsight-postgres`
- `hindsight`
- `hermes-cron-memory-ingestor`

`docker-compose.agent.yml` intentionally does not manage a Hermes gateway
container. The cron memory ingestor does not trigger Hermes cron jobs; it only
scans completed cron output and retains it into Hindsight.

### Gateway Service Operations

Install or repair the native gateway service:

```bash
env HERMES_HOME=/home/hermes_data /usr/local/bin/hermes gateway install --system --run-as-user root --force
```

Start, restart, and check the gateway:

```bash
env HERMES_HOME=/home/hermes_data /usr/local/bin/hermes gateway start --system
env HERMES_HOME=/home/hermes_data /usr/local/bin/hermes gateway restart --system
env HERMES_HOME=/home/hermes_data /usr/local/bin/hermes gateway status --system
systemctl status hermes-gateway.service --no-pager
```

The system service currently runs as `root` because the host deployment is
managed by root and `/home/hermes_data` contains files from the earlier
container UID mapping. If this is changed later, update ownership and the
systemd `User=` consistently.

### Cron Execution Model

Hermes cron jobs fire from the gateway's embedded cron ticker. A normal CLI
chat session does not fire cron jobs automatically.

Check cron health:

```bash
env HERMES_HOME=/home/hermes_data /usr/local/bin/hermes cron status
env HERMES_HOME=/home/hermes_data /usr/local/bin/hermes cron list
```

Expected healthy status:

```text
Gateway is running - cron jobs will fire automatically
```

Cron output is written under:

```bash
/home/hermes_data/cron/output/{job_id}/*.md
```

The ingestor scans that output and writes retained memories into Hindsight.

### Daily Outfit Cron

Current daily outfit job:

- ID: `dfc99065dc6e`
- Name: `夏尔每日穿搭结果推送`
- Schedule: `0 8 * * *`
- Skill: `charlotte-outfit-system`
- Delivery: `local`
- Workdir: unset

This job is treated as daily outfit memory generation, not external platform
push. `deliver=local` means:

- the cron job still runs through Hermes
- output is saved to `/home/hermes_data/cron/output/dfc99065dc6e/`
- `hermes-cron-memory-ingestor` can retain the output into Hindsight
- no external chat/platform delivery is attempted

Do not use `deliver=origin` for this job unless it is created from a live
gateway conversation with a valid stored origin. In the host-native deployment,
this job has no origin, so `deliver=origin` cannot resolve a visible delivery
target.

Useful checks:

```bash
env HERMES_HOME=/home/hermes_data /usr/local/bin/hermes cron list
find /home/hermes_data/cron/output/dfc99065dc6e -maxdepth 1 -type f -printf '%TY-%Tm-%Td %TH:%TM:%TS %s %p\n' | sort
docker logs --tail 200 hermes-cron-memory-ingestor
```

Known validated run:

- `last_run_at`: `2026-05-05T08:02:08+08:00`
- output: `/home/hermes_data/cron/output/dfc99065dc6e/2026-05-05_08-02-08.md`
- ingestor log: `Retained cron output memory: output/dfc99065dc6e/2026-05-05_08-02-08.md`

### Historical Fixes

The daily outfit job previously had `deliver=origin`. Because the old origin
was absent in the native deployment, Hermes recorded:

```text
no delivery target resolved for deliver=origin
```

The job was corrected to `deliver=local`, and the stale
`last_delivery_error` was cleared.

The job also previously had `workdir=/home/agent`, which came from the old
container runtime. The host-native machine does not have `/home/agent`, so
Hermes logged:

```text
configured workdir '/home/agent' no longer exists - running without it
```

The job workdir was cleared. It should remain unset unless the cron task needs
project-specific context files or a specific tool working directory.

### Logs

Gateway and cron scheduler logs:

```bash
tail -120 /home/hermes_data/logs/gateway.log
tail -120 /home/hermes_data/logs/agent.log
rg -n 'Cron ticker|cron.scheduler|dfc99065dc6e|workdir|delivery' /home/hermes_data/logs/agent.log /home/hermes_data/logs/gateway.log
```

Ingestor logs:

```bash
docker logs --tail 200 hermes-cron-memory-ingestor
```

Systemd logs:

```bash
journalctl -u hermes-gateway.service -n 200 --no-pager
```
