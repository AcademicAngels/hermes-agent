# Hindsight Memory Palace Design

## Goal

Hermes Agent should keep its official memory model intact while using
Hindsight as the durable, structured long-term memory layer for complex work.
The design must preserve upstream compatibility, avoid raw file mirroring, and
make memory retrieval useful for long-running coding, operations, cron, and
multi-agent tasks.

The target outcome is:

- `SOUL.md` stays agent identity only.
- `USER.md` and `MEMORY.md` stay small built-in prompt memory.
- Hindsight stores typed, tagged, structured long-term memories.
- Cron final outputs enter Hindsight through the external cron ingestor.
- Subagent results enter Hindsight through the official provider hook.
- Existing unstructured Hindsight entries are inventoried, cleaned, and
  rewritten or superseded.

## Current State

Hermes official docs define `SOUL.md` as the primary identity file loaded from
`HERMES_HOME` into the first system prompt slot. It is not a memory file and
should not be copied into Hindsight.

Hermes built-in memory consists of `MEMORY.md` and `USER.md` under
`$HERMES_HOME/memories`. They are bounded, curated files injected as a frozen
snapshot at session start. External memory providers run alongside this built-in
memory and do not replace it.

The Hindsight memory provider already supports the official provider lifecycle:
prompt block, prefetch, turn sync, provider tools, session switch, and optional
hooks. Hermes also exposes a parent-side `MemoryProvider.on_delegation(...)`
hook for completed subagent work. Subagents run with memory disabled, so the
parent provider is the correct place to retain a structured task/result
observation.

The external `hermes-cron-memory-ingestor` sidecar currently:

- scans `$HERMES_HOME/cron/output/**/*.md`
- extracts only the `## Response` section
- skips failed, empty, silent, and excluded-session outputs
- writes accepted responses to Hindsight
- updates deduplication state only after Hindsight accepts the write
- exposes a separate structured outfit event API

That sidecar is the correct place to structure cron-derived memories. It should
not become a general replacement for the Hermes memory provider.

## Non-Goals

Do not write raw `SOUL.md` into Hindsight.

Do not write raw `USER.md` or `MEMORY.md` into Hindsight as bulk text. Stable
facts distilled from those files may be retained as typed Hindsight memories
only after review.

Do not make Hindsight "take over" built-in memory. Built-in memory remains the
small always-in-context layer; Hindsight is deeper recall.

Do not store cron prompts, system prompts, hidden reasoning, chain-of-thought,
or unfiltered logs.

Do not hard-code a full memory palace taxonomy inside Hermes core. Schema and
tagging should be configuration-driven where possible and localized to the
Hindsight provider or external ingestors.

Do not implement a separate memory framework or MCP server before the Hindsight
schema, cleanup, and retrieval behavior prove insufficient.

## Memory Layers

### L0: Identity

`SOUL.md` is the durable Hermes identity and communication posture. It should be
short, stable, and focused on voice, directness, uncertainty handling, and
technical stance.

It should not contain project state, local paths, deployment facts, cron
results, task history, or user profile facts.

### L1: Built-In Prompt Memory

`USER.md` stores a compact stable user profile: durable preferences,
communication expectations, and workflow habits.

`MEMORY.md` stores a compact agent index card: critical environment facts and
how to use the long-term Hindsight layer. It may say that Hindsight is the
long-term memory palace and which tags or tools to query, but it should not
duplicate long task history.

This layer must remain small because it is injected into every session.

### L2: Hindsight Memory Palace

Hindsight stores structured long-term memory entries. It should hold durable
project facts, decisions, incidents, runbooks, subagent results, cron final
outputs, and distilled user preferences.

Retrieval should use type, source, project, component, scope, and session tags
so the agent can ask narrow questions instead of retrieving an undifferentiated
pile of memories.

### L3: Raw Archives

Raw cron output files, session logs, repository files, and other large artifacts
remain in their native locations. Hindsight entries may reference their source
path or session id, but should not embed raw archives unless the content has
been distilled.

## Memory Types

Use a small initial taxonomy. Each memory entry should have one primary
`memory_type`.

| Type | Purpose |
| --- | --- |
| `cron_final_output` | Final result of a scheduled Hermes cron job |
| `subagent_result` | Parent-observed result from delegated subagent work |
| `project_fact` | Stable fact about a repo, service, deployment, or workflow |
| `decision` | A decision with rationale and date |
| `incident` | Failure, symptom, root cause, and resolution |
| `runbook` | Reusable operational procedure |
| `task_timeline` | Compact milestone summary for a longer task chain |
| `user_preference` | Distilled durable user preference |
| `skill_summary` | Summary of reusable skill or technique learned by Hermes |

The first implementation should only create the types that have clear sources:
`cron_final_output`, `subagent_result`, `project_fact`, `decision`, `incident`,
`runbook`, and `user_preference`.

## Common Tags

Tags are the most portable structure because both the Hermes Hindsight provider
and the cron ingestor already support them.

Recommended tags:

- `source:<source>`, for example `source:cron_output`, `source:delegation`,
  `source:curated_migration`
- `type:<memory_type>`, for example `type:cron_final_output`
- `project:<project_name>` when known
- `component:<component_name>` when known
- `scope:<scope>`, for example `scope:scheduled_task`, `scope:repo`,
  `scope:deployment`, `scope:user_profile`
- `session:<session_id>` when known
- `child_session:<session_id>` for delegation results when supported
- `cron-job:<job_id>` for cron results

Tags should be low-cardinality except for session and job lineage tags. Avoid
inventing many near-duplicate labels.

## Common Metadata

When the Hindsight client path supports metadata, include:

```json
{
  "memory_type": "cron_final_output",
  "source": "cron_output",
  "scope": "scheduled_task",
  "project": "",
  "component": "",
  "session_id": "",
  "child_session_id": "",
  "job_id": "",
  "source_path": "",
  "created_at": "",
  "schema_version": "memory-palace-v1",
  "confidence": "observed"
}
```

If a write path only supports `content`, `context`, `tags`, and `timestamp`,
encode the stable fields in tags and a compact context string. Do not block the
initial design on metadata availability.

## Content Templates

Content should be concise and retrieval-oriented. Avoid transcripts when a
summary is enough.

### Cron Final Output

```text
Cron final output

Job: <job_name>
Run time: <run_time>
Schedule: <schedule>

Result:
<response>
```

The ingestor should continue to exclude the cron prompt.

### Subagent Result

```text
Subagent result

Task:
<delegated_task>

Result:
<final_result>
```

This should be retained by the parent Hindsight provider through
`on_delegation(...)`. The default must remain disabled unless configured.

### Curated Decision

```text
Decision: <short title>

Context:
<why the decision was needed>

Decision:
<what was chosen>

Rationale:
<why>

Implications:
<how future agents should use it>
```

## Hermes Agent Changes

Keep Hermes-agent changes small and upstream-friendly.

The only runtime provider change currently justified is Hindsight support for
configuration-driven `on_delegation(...)` retention:

- default disabled
- no hard-coded memory palace taxonomy
- content template configurable
- context configurable
- tags configurable
- metadata configurable when supported
- no changes to delegation core logic
- no subagent direct provider session

Do not add startup scanning of `SOUL.md`, `USER.md`, or `MEMORY.md`.

Do not use `on_memory_write(...)` as the primary future direction. It may be
useful later for mirroring carefully curated built-in memory writes, but the
memory palace should be based on typed entries rather than blind mirroring.

## Cron Ingestor Changes

Extend `/home/github/hermes-cron-memory-ingestor` for cron-source structure.

Recommended changes:

- add `MEMORY_PALACE_SCHEMA_VERSION`, default `memory-palace-v1`
- add `INGESTOR_MEMORY_TYPE`, default `cron_final_output`
- add base structural tags:
  - `source:cron_output`
  - `type:cron_final_output`
  - `scope:scheduled_task`
- keep `cron-job:<job_id>` lineage tags
- format context as stable key-value text:
  `schema_version=memory-palace-v1 memory_type=cron_final_output source=cron_output job_id=... run_time=... source_path=...`
- optionally include metadata if confirmed accepted by the Hindsight HTTP API
- keep extracting only `## Response`
- keep updating state only after Hindsight accepts the write

Deduplication should account for schema changes. A response previously retained
under an older schema should be eligible for re-retention after the memory
palace schema changes. The state key or state value should include the schema
version or policy hash.

## Cleanup And Rewrite

Cleaning current Hindsight data should be a separate one-time operation, not a
runtime behavior in Hermes-agent or cron ingestor.

Process:

1. Inventory current Hindsight memories by source, tags, timestamp, and content
   shape.
2. Identify entries that are cron final outputs imported by the old ingestor.
3. Classify each entry into the new schema.
4. Reinsert cleaned entries with `source:curated_migration` plus original source
   tags such as `source:cron_output`.
5. Delete old entries only if the Hindsight API supports safe targeted
   deletion. Otherwise mark superseded entries with a replacement memory that
   says the old unstructured import should be ignored.
6. Record migration time, schema version, and counts.

This migration must run against a test bank or backup first.

## SOUL.md And USER.md Distillation

Distill, do not ingest raw files.

`SOUL.md` output should be a shorter identity file. It remains only in
`$HERMES_HOME/SOUL.md`.

`USER.md` output should be a compact set of stable user facts and preferences.
Only durable preferences that help future work should remain.

Potential Hindsight entries derived from `USER.md` should be manually curated as
`type:user_preference` with `source:curated_migration`, not bulk imported.

`MEMORY.md` should become a small index card that tells Hermes where deeper
memory lives and how to query it.

## Retrieval Policy

Hindsight recall should prefer structured filtering:

- task history: `type:task_timeline` or `type:subagent_result`
- cron results: `source:cron_output` and `type:cron_final_output`
- operational fixes: `type:incident` or `type:runbook`
- project knowledge: `type:project_fact` and `project:<name>`
- user preferences: `type:user_preference`

Automatic recall should be conservative. If broad auto-recall injects too much
unrelated memory, prefer tool-driven recall with explicit tags or lower recall
budget.

## External References

Relevant GitHub projects support the direction but should not be copied as
architecture:

- `adshaa/mempalacejs`: spatial labels such as wings, rooms, and drawers;
  local-first structured search; agent-to-system memory writes.
- `z1one0415/z1-matrix-memory-palace`: raw layer, palace layer, watchdog,
  archivist, and context-budget discipline.
- `dcostenco/prism-coder`: session ledger, semantic knowledge, causal links,
  multi-agent handoff, and confidence-aware retrieval.

For Hermes, the practical adaptation is tags, typed entries, distillation, and
budgeted recall on top of Hindsight.

## Testing

Hermes-agent tests:

- Hindsight provider does not retain delegation by default.
- With delegation retention enabled, it writes configured content, context,
  tags, and metadata.
- Placeholder rendering covers task, result, child session, parent session,
  platform, and agent identity.
- Existing retain, recall, and sync behavior remains unchanged.

Cron ingestor tests:

- parser still extracts only `## Response`.
- retained cron entries include memory palace tags.
- context includes schema version and source fields.
- state dedup changes when schema version or policy hash changes.
- state is written only after retain succeeds.
- prompts and hidden reasoning fields are not retained.

Migration tests:

- dry run produces inventory and planned actions without writing.
- migration can target a test bank.
- migrated entries include old-source provenance and new schema tags.
- failed writes do not delete or mark old entries as migrated.

Manual verification:

- Hindsight UI or API shows structured cron entries.
- Hindsight recall by `source:cron_output` returns cron results.
- Hindsight recall by `type:subagent_result` returns delegation summaries when
  configured.
- `SOUL.md` content is not present as a Hindsight memory.

## Risks

Over-retention can pollute Hindsight. Defaults should be conservative, and
structured writes should be explicit.

Hindsight metadata support may differ between client and HTTP API paths. Tags
and context must be sufficient for the first version.

Auto-recall can inject unrelated long-term memories into current tasks. Use
tags, recall budgets, and tool-driven queries to reduce noise.

Schema churn can create duplicate memories. Include schema version in state and
migration provenance.

Cleaning production Hindsight data is destructive if deletes are used. Prefer
backup, test bank migration, and supersede markers unless targeted deletion is
verified.

Background self-review or skill-learning sessions may write conversation
summaries if Hindsight auto-retain is enabled. Evaluate provider configuration
before enabling broad auto-retain in production.
