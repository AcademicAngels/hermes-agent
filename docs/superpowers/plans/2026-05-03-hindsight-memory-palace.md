# Hindsight Memory Palace Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add the first memory-palace implementation slice: config-driven Hindsight delegation retention in Hermes Agent and structured cron final-output ingestion in the external cron ingestor.

**Architecture:** Hermes Agent keeps the official memory provider architecture. The Hindsight provider handles parent-observed subagent results through `MemoryProvider.on_delegation(...)`, disabled by default and controlled by config. The cron ingestor handles only cron-source structure by adding schema-aware tags, context, and dedup policy versioning before posting final responses to Hindsight.

**Tech Stack:** Python, pytest/unittest, Hermes Agent memory provider plugin API, Hindsight retain API, external `hermes-cron-memory-ingestor` sidecar.

---

## File Structure

Hermes Agent repository: `/home/github/hermes-agent`

- Modify: `plugins/memory/hindsight/__init__.py`
  - Add default-off Hindsight delegation retention.
  - Parse config for `delegation_retain`, `delegation_context`, `delegation_tags`, `delegation_metadata`, and `delegation_content_template`.
  - Render placeholders without crashing on unknown fields.
- Modify: `plugins/memory/hindsight/README.md`
  - Document delegation retention config and example.
- Modify: `tests/plugins/memory/test_hindsight_provider.py`
  - Test disabled default.
  - Test configured retain content, tags, context, and metadata.
  - Test config schema includes the new fields.

Cron ingestor repository: `/home/github/hermes-cron-memory-ingestor`

- Modify: `src/hermes_cron_memory_ingestor/ingestor.py`
  - Add schema/policy fields to `IngestConfig`.
  - Include schema/policy in dedup hash so schema changes can re-retain old files.
- Modify: `src/hermes_cron_memory_ingestor/config.py`
  - Load `MEMORY_PALACE_SCHEMA_VERSION` and `INGESTOR_MEMORY_TYPE`.
- Modify: `src/hermes_cron_memory_ingestor/client.py`
  - Add structural tags for cron final output.
- Modify: `src/hermes_cron_memory_ingestor/parser.py`
  - Format cron context as stable key-value text with schema/source fields.
- Modify: `README.md`
  - Document structured memory tags and schema-aware dedup.
- Modify tests:
  - `tests/test_client.py`
  - `tests/test_ingestor.py`
  - `tests/test_parser.py`
  - Add config tests if needed in `tests/test_config.py`.

## Task 1: Verify Hermes Hindsight Delegation Retain

**Files:**
- Modify: `plugins/memory/hindsight/__init__.py`
- Modify: `plugins/memory/hindsight/README.md`
- Modify: `tests/plugins/memory/test_hindsight_provider.py`

- [ ] **Step 1: Review current diff**

Run:

```bash
git diff -- plugins/memory/hindsight/__init__.py plugins/memory/hindsight/README.md tests/plugins/memory/test_hindsight_provider.py
```

Expected: Only delegation-retain related changes are present.

- [ ] **Step 2: Run focused tests**

Run:

```bash
python -m pytest -o addopts= tests/plugins/memory/test_hindsight_provider.py -k "DelegationRetain or ConfigSchema"
```

Expected: `3 passed` with unrelated deselected tests. Do not run the full Hindsight test file.

- [ ] **Step 3: Fix only delegation-specific failures**

If tests fail, modify only the Hindsight provider, README, or focused tests. Do not change Hermes core delegation plumbing.

- [ ] **Step 4: Re-run focused tests**

Run:

```bash
python -m pytest -o addopts= tests/plugins/memory/test_hindsight_provider.py -k "DelegationRetain or ConfigSchema"
```

Expected: focused tests pass.

- [ ] **Step 5: Commit Hermes provider slice**

Run:

```bash
git add plugins/memory/hindsight/__init__.py plugins/memory/hindsight/README.md tests/plugins/memory/test_hindsight_provider.py
git commit -m "feat: retain hindsight delegation results"
```

Expected: commit contains only the Hindsight provider implementation, docs, and tests.

## Task 2: Add Cron Structural Tags And Context Tests

**Files:**
- Modify: `/home/github/hermes-cron-memory-ingestor/tests/test_client.py`
- Modify: `/home/github/hermes-cron-memory-ingestor/tests/test_parser.py`
- Modify: `/home/github/hermes-cron-memory-ingestor/src/hermes_cron_memory_ingestor/client.py`
- Modify: `/home/github/hermes-cron-memory-ingestor/src/hermes_cron_memory_ingestor/parser.py`

- [ ] **Step 1: Write failing client test for structural tags**

Add expectations that retained cron memories include:

```python
[
    "hermes",
    "cron",
    "source:cron_output",
    "type:cron_final_output",
    "scope:scheduled_task",
    "cron-job:job-123",
]
```

Run:

```bash
PYTHONPATH=src python -m unittest tests.test_client.HindsightClientTests.test_posts_content_context_tags_and_timestamp
```

Expected before implementation: FAIL because structural tags are missing.

- [ ] **Step 2: Write failing parser test for stable context**

Assert `memory.context` includes:

```text
schema_version=memory-palace-v1
memory_type=cron_final_output
source=cron_output
scope=scheduled_task
job_id=job-123
```

Run:

```bash
PYTHONPATH=src python -m unittest tests.test_parser.ParseCronOutputTests.test_extracts_only_final_response_and_metadata
```

Expected before implementation: FAIL because context still uses the older prose format.

- [ ] **Step 3: Implement structural tags and context**

Update `CronMemory.context` and `HindsightClient.retain(...)` so the tests pass. Keep the parser extracting only `## Response`.

- [ ] **Step 4: Run focused tests**

Run:

```bash
PYTHONPATH=src python -m unittest tests.test_client.HindsightClientTests.test_posts_content_context_tags_and_timestamp tests.test_parser.ParseCronOutputTests.test_extracts_only_final_response_and_metadata
```

Expected: both tests pass.

## Task 3: Add Schema-Aware Cron Dedup

**Files:**
- Modify: `/home/github/hermes-cron-memory-ingestor/src/hermes_cron_memory_ingestor/ingestor.py`
- Modify: `/home/github/hermes-cron-memory-ingestor/src/hermes_cron_memory_ingestor/config.py`
- Modify: `/home/github/hermes-cron-memory-ingestor/tests/test_ingestor.py`
- Create if useful: `/home/github/hermes-cron-memory-ingestor/tests/test_config.py`

- [ ] **Step 1: Write failing ingestor test**

Add a test proving that the same file content is retained again when `schema_version` changes.

Expected setup:

```python
first_config = IngestConfig(..., schema_version="memory-palace-v1", memory_type="cron_final_output")
second_config = IngestConfig(..., schema_version="memory-palace-v2", memory_type="cron_final_output")
```

Run:

```bash
PYTHONPATH=src python -m unittest tests.test_ingestor.IngestorTests
```

Expected before implementation: FAIL because state only keys by raw content hash.

- [ ] **Step 2: Implement policy hash**

Update `scan_once(...)` to hash a stable policy prefix together with file bytes:

```text
schema_version=<schema_version>
memory_type=<memory_type>
```

Use the policy-aware hash for state checks and state writes.

- [ ] **Step 3: Load config env vars**

Update `load_config()` so:

```python
schema_version = os.getenv("MEMORY_PALACE_SCHEMA_VERSION", "memory-palace-v1")
memory_type = os.getenv("INGESTOR_MEMORY_TYPE", "cron_final_output")
```

These values should be passed into `IngestConfig`.

- [ ] **Step 4: Run ingestor tests**

Run:

```bash
PYTHONPATH=src python -m unittest tests.test_ingestor tests.test_state
```

Expected: pass.

## Task 4: Update Cron README And Full Cron Test Suite

**Files:**
- Modify: `/home/github/hermes-cron-memory-ingestor/README.md`

- [ ] **Step 1: Document structural memory behavior**

Add README notes for:

- `source:cron_output`
- `type:cron_final_output`
- `scope:scheduled_task`
- `MEMORY_PALACE_SCHEMA_VERSION`
- `INGESTOR_MEMORY_TYPE`
- schema-aware dedup behavior

- [ ] **Step 2: Run full cron ingestor tests**

Run:

```bash
PYTHONPATH=src python -m unittest discover -s tests
PYTHONPATH=src python -m compileall src
```

Expected: all tests pass and compile succeeds.

- [ ] **Step 3: Commit cron ingestor slice**

Run in `/home/github/hermes-cron-memory-ingestor`:

```bash
git add README.md src tests
git commit -m "feat: structure cron memories for hindsight"
```

Expected: commit contains only cron ingestor implementation, docs, and tests.

## Task 5: Final Verification

**Files:**
- Check both repositories.

- [ ] **Step 1: Confirm no full Hindsight pytest is running**

Run:

```bash
pgrep -af pytest
```

Expected: no `test_hindsight_provider.py` process remains.

- [ ] **Step 2: Confirm Hermes Agent status**

Run in `/home/github/hermes-agent`:

```bash
git status --short --branch
git log -2 --oneline
```

Expected: clean or only explicitly unrelated changes; latest commits include design/plan/provider work.

- [ ] **Step 3: Confirm cron ingestor status**

Run in `/home/github/hermes-cron-memory-ingestor`:

```bash
git status --short --branch
git log -1 --oneline
```

Expected: clean; latest commit is the cron structure commit.
