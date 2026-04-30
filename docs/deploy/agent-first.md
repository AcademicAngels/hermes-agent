# Agent-First Docker Deployment

This deployment keeps `docker-compose.yml` aligned with upstream and uses
`docker-compose.agent.yml` for the local agent-first stack.

## Services

- `hermes-agent` runs the native Hermes Agent image and stays alive for CLI use.
- `hermes-config-init` initializes `/home/agent/.hermes` with agent-first
  defaults before the long-lived services start.
- `hindsight-postgres` stores Hindsight data with pgvectorscale/DiskANN.
- `hindsight` provides the local external Hindsight API and UI.
- `hermes-cron-memory-ingestor` retains cron output into Hindsight.

No `hermes-webui`, proxy, dashboard, Web UI token, Web UI port, or Web UI volume
is included.

## Start

```bash
cp .env.agent.example .env.agent
install -d -m 700 /home/hermes_data
docker compose --env-file .env.agent -f docker-compose.agent.yml \
  pull hermes-agent hermes-config-init hindsight hindsight-postgres
docker compose --env-file .env.agent -f docker-compose.agent.yml \
  build hermes-cron-memory-ingestor
docker compose --env-file .env.agent -f docker-compose.agent.yml up -d
```

`hermes-agent`, `hermes-config-init`, `hindsight`, and `hindsight-postgres` use
published images. The database image defaults to
`timescale/timescaledb-ha:pg18-all-oss` because Z.ai `embedding-3` returns
2048-dimensional vectors, which exceed pgvector HNSW's 2000-dimensional index
limit. `hermes-cron-memory-ingestor` is built locally from the sibling
`/home/github/hermes-cron-memory-ingestor` project because it is our sidecar for
writing Hermes cron output into Hindsight memory.

## Native CLI

```bash
docker compose --env-file .env.agent -f docker-compose.agent.yml \
  exec hermes-agent hermes
```

The host data directory is `/home/hermes_data`. Inside containers it is mounted
at `/home/agent/.hermes` and exposed to Hermes as `HERMES_HOME`.
Hindsight Postgres data is stored under
`/home/hermes_data/hindsight-postgres`, mounted at `/var/lib/postgresql` inside
the database container to match the PostgreSQL 18 image layout.

The `hermes` executable still comes from the image installation under
`/opt/hermes/.venv/bin`; the compose file adds that directory to `PATH` so the
CLI command can stay short. `/home/hermes_data` remains data-only.

## Hermes Config

The stack creates `/home/hermes_data/config.yaml` on first start and applies
these native Hermes settings:

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
  "api_url": "http://hindsight:8888",
  "bank_id": "hermes",
  "recall_budget": "mid",
  "memory_mode": "hybrid"
}
```

The OpenAI-compatible image endpoint is configured with environment variables
in `.env.agent`:

```env
OPENAI_API_KEY=...
OPENAI_BASE_URL=https://api.husanai.com/v1
OPENAI_IMAGE_MODEL=gpt-image-2-medium
```

Hindsight local external mode is configured through the compose environment:

```env
HINDSIGHT_MODE=local_external
HINDSIGHT_API_URL=http://hindsight:8888
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
