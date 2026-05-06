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
  provider: openai-compatible
  model: gpt-image-2-medium
  openai_compatible:
    endpoint: custom:ttp
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

Local Hermes extensions are kept outside this repository in the plugin pack:

```text
/home/github/hermes-atomic-arsenal
https://github.com/AcademicAngels/hermes-atomic-arsenal
```

The current OpenAI-compatible image generation path is provided by the
`openai-compatible` user plugin from that plugin pack. It uses
`custom_providers` as a multi-capability endpoint registry; `custom:ttp`
remains the TTP aggregation endpoint and is not treated as an image-only
backend.

Expected image plugin config:

```yaml
plugins:
  enabled:
    - openai-compatible

image_gen:
  provider: openai-compatible
  model: gpt-image-2-medium
  openai_compatible:
    endpoint: custom:ttp
    model: gpt-image-2-medium
```

Install or refresh the plugin pack locally with:

```bash
cd /home/github/hermes-atomic-arsenal
python3 scripts/install.py openai-compatible --home /home/hermes_data --force --enable
env HERMES_HOME=/home/hermes_data /usr/local/bin/hermes config set image_gen.provider openai-compatible
env HERMES_HOME=/home/hermes_data /usr/local/bin/hermes config set image_gen.openai_compatible.endpoint custom:ttp
env HERMES_HOME=/home/hermes_data /usr/local/bin/hermes config set image_gen.openai_compatible.model gpt-image-2-medium
```

The Dockerized cron memory ingestor uses `HINDSIGHT_URL`, which defaults to the
compose service URL:

```env
HINDSIGHT_URL=http://hindsight:8888
```

The ingestor's structured outfit event endpoint listens on container port
`8787`. Docker-internal callers can use:

```text
http://hermes-cron-memory-ingestor:8787/v1/outfit/events
```

Host-native Hermes processes, including ordinary Weixin conversations, cannot
resolve the Docker service DNS name. They must use the published host port
instead:

```text
http://127.0.0.1:18787/v1/outfit/events
http://64.83.43.72:18787/v1/outfit/events
```

The published port is configured by:

```env
CRON_MEMORY_EVENT_PUBLIC_HOST=0.0.0.0
CRON_MEMORY_EVENT_PUBLIC_PORT=18787
```

If the public endpoint is exposed beyond the host, restrict it at the firewall
or network layer. The endpoint is intended for trusted local/runtime callers,
not anonymous internet traffic.

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

Local feature code must not be added to this `hermes-agent` checkout. This
repository follows upstream Hermes Agent updates; site-specific capabilities
belong in `/home/github/hermes-atomic-arsenal` as user plugins. If a capability
cannot be implemented through existing plugin/tool hooks, document the
limitation and consider an upstream issue or PR instead of maintaining a local
source fork.

### Runtime Layout

- Repository: `/home/github/hermes-agent`
- Local plugin pack: `/home/github/hermes-atomic-arsenal`
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

### Local Plugin Operations

The local plugin pack is the deployment-owned extension point:

```bash
cd /home/github/hermes-atomic-arsenal
git pull --ff-only
python3 scripts/install.py --home /home/hermes_data --force --enable
```

After installing or updating plugins, restart the native gateway so the plugin
manager reloads user plugins:

```bash
env HERMES_HOME=/home/hermes_data /usr/local/bin/hermes gateway restart --system
```

Verify the active image provider:

```bash
env HERMES_HOME=/home/hermes_data python - <<'PY'
from hermes_cli import plugins as plugins_module
from agent import image_gen_registry
plugins_module._ensure_plugins_discovered(force=True)
active = image_gen_registry.get_active_provider()
print({"active": active.name if active else None, "available": active.is_available() if active else None})
PY
```

Expected output:

```text
{'active': 'openai-compatible', 'available': True}
```

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
- Delivery: `weixin`
- Workdir: unset

This job is treated as daily outfit memory generation with Weixin delivery.
`deliver=weixin` means:

- the cron job still runs through Hermes
- output is saved to `/home/hermes_data/cron/output/dfc99065dc6e/`
- `hermes-cron-memory-ingestor` can retain the output into Hindsight
- the final response may include one or more `MEDIA:<path>` lines, and the
  gateway will forward the generated images to Weixin as native attachments

Do not use `deliver=origin` for this job unless it is created from a live
gateway conversation with a valid stored origin. In the host-native deployment,
this job has no origin, so `deliver=origin` cannot resolve a visible delivery
target.

The runtime prompt currently instructs the job to preserve Hindsight anchors for
`daily-outfit`, `weixin-visible`, `replaceable-outfit`, and `multi-image`, so
ordinary Weixin replies like “换一套” can be resolved from memory instead of
from cron context.

The runtime persona file `/home/hermes_data/SOUL.md` also contains global
Outfit System rules for ordinary Weixin follow-ups:

- short replies such as “换一套” and “不满意这套” refer to the most recent daily
  outfit by default
- the agent should recall Hindsight before generating the replacement
- user feedback and replacement outfits should be stored as outfit memory
  events through `http://64.83.43.72:18787/v1/outfit/events`
- if that endpoint is unavailable, the agent should fall back to
  `hindsight_retain`
- final responses must not expose tool calls, Hindsight results, ingestor
  errors, or internal execution notes

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
