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
