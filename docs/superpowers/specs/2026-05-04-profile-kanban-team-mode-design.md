# Profile / Kanban Team Mode Design

## Goal

Define a Hermes-native team mode for long-running, multi-step, multi-agent work
that stays aligned with upstream Hermes concepts:

- profiles provide identity, tools, memory, and workspace boundaries
- Kanban provides durable coordination, handoff, retry, and auditability
- the dispatcher turns ready tasks into running profile instances

The team mode should make it easy to run a small engineering or ops team with:

- one orchestrator profile that decomposes user intent
- one or more worker profiles that execute tasks
- an optional reviewer profile that validates and synthesizes results

The design must not introduce a new resident subagent runtime. It should be
expressed as a composition of existing Hermes profiles, skills, and the Kanban
dispatcher.

## Current State

Hermes already has the primitives needed for this pattern:

- **Profiles** are isolated Hermes homes with their own config, memory, skills,
  sessions, and `SOUL.md`.
- **Delegation** (`delegate_task`) is synchronous and useful for short-lived,
  in-turn reasoning, but it is not a durable work queue.
- **Kanban** is a durable board shared across profiles, with tasks, assignees,
  parent/child links, comments, runs, and a dispatcher.
- **Dispatcher** can claim tasks, spawn the right profile, and recover from
  crashes or spawn failures.

What is missing is a documented team workflow that says how these pieces should
be composed for real multi-agent work.

## Non-Goals

- Do not create a new always-on subagent process pool.
- Do not make `delegate_task` the main coordination primitive.
- Do not hard-code a fixed team roster into the runtime.
- Do not tie team mode to any memory provider.
- Do not require a new database or queue outside the existing Kanban store.

## Proposed Model

Team mode is a **workflow pattern**, not a new execution engine.

### Roles

The recommended team has three role classes:

- **Orchestrator**: receives the user goal, decomposes it, creates Kanban tasks,
  links dependencies, monitors progress, and produces the final synthesis.
- **Worker**: executes a bounded piece of work, then records a structured
  summary and metadata on completion.
- **Reviewer**: checks the worker result, blocks if needed, or completes with
  approval and follow-up notes.

Each role is still just a Hermes profile. Role behavior comes from profile
configuration, installed skills, and the Kanban task assigned to it.

### Coordination layer

Kanban is the source of truth for team execution:

- tasks carry the work description and assignee
- links express dependency order
- comments carry human and agent discussion
- runs preserve retry history and handoff payloads
- the dispatcher promotes and claims work without requiring the orchestrator to
  babysit every step

## Profile Layout

The smallest useful team is:

- `orchestrator` profile
- one specialist worker profile per domain, such as `backend`, `ops`,
  `research`, or `writer`
- one `reviewer` profile, or a reviewer skill attached to a worker profile

The initial implementation should prefer existing profile creation and cloning
mechanics rather than inventing a new runtime-specific profile format. A team is
assembled from ordinary Hermes profiles.

Recommended profile rules:

- the orchestrator profile gets the `kanban-orchestrator` skill
- worker profiles get `kanban-worker` plus domain skills
- reviewer profiles get review-focused skills and can reuse the worker toolset
- every profile keeps its own `SOUL.md`, memory, and workspace settings

## Kanban Contract

Team mode relies on a small Kanban contract:

- every non-trivial unit of work is a task
- every downstream task links to the task that produced its input
- every completion includes a concise summary
- every completion may include structured metadata when relevant
- every rejection or stall is represented as a blocked task with a reason

The handoff payload should stay structured and minimal. A worker should not dump
its entire scratchpad into the board.

Minimum useful run output:

- `summary`: what changed or what was learned
- `metadata`: files, commands, decisions, or metrics when applicable
- `blocked_reason`: why the task cannot proceed

## Data Flow

### 1. User intent enters the orchestrator

The user talks to the orchestrator profile. The orchestrator interprets the
request, decides whether it is a single-task or multi-task problem, and uses
Kanban when the work should survive across turns or across profiles.

### 2. Orchestrator decomposes work

The orchestrator creates tasks with:

- a clear title
- an assignee profile
- optional tenant / project namespace
- parent links for dependency ordering
- optional extra skills for the task

The orchestrator then steps back. It may continue to watch the board, but it
should not become the execution engine itself.

### 3. Dispatcher claims and spawns

The Kanban dispatcher sees ready tasks, claims them atomically, and spawns the
assigned profile with the task context. The worker profile reads:

- the task body
- prior runs
- parent summaries and metadata
- comments and handoff notes

### 4. Worker executes and records a handoff

The worker completes the task and writes a structured completion record back to
the board. If the task reveals a follow-up, the worker can create or unblock
child tasks instead of stuffing everything into one reply.

### 5. Reviewer validates or blocks

If a reviewer role is used, the reviewer opens the task or the child task,
checks the worker output, and either:

- completes it
- blocks it with a concrete fix request
- spawns a follow-up task if the work needs another pass

### 6. Orchestrator synthesizes

Once the dependency chain is complete, the orchestrator reads the board history
and writes the final response to the user. The final answer should reflect the
board state, not a private in-memory guess.

## Error Handling

Team mode should make failure visible and recoverable.

### Spawn failure

If the dispatcher cannot start the assigned profile, the task should be retried
according to the existing Kanban failure policy. After the retry limit is
reached, the task becomes blocked with the last error.

### Worker crash

If a running worker dies mid-task, the dispatcher reclaims the claim and
returns the task to the board so another attempt can resume from the stored
context.

### Review rejection

A reviewer should block the task with a specific reason, not silently discard
the result. The next worker attempt must see the rejection reason in context.

### Bad decomposition

If the orchestrator creates a task graph with missing dependencies, duplicate
work, or an invalid assignee, the board should reject it early rather than let a
broken workflow spread.

### Restart safety

Because the board is durable, a Hermes restart must not lose the current team
state. After restart, the dispatcher can resume from the persisted task table
and run history.

## Configuration

Team mode should stay configuration-driven where possible.

Recommended config surfaces:

- profile config for identity, model, memory, skills, and cwd
- Kanban config for dispatcher interval, retry policy, and tenant defaults
- task-level skill pinning for special cases

The design should not require hard-coded role names in the core runtime. A
team can be called anything as long as the profiles and task assignments line
up.

## Testing

Test coverage should prove the workflow, not just the syntax.

### Unit tests

- profile-to-assignee resolution
- task creation with parent links and pinned skills
- run summary and metadata persistence
- reviewer block/completion transitions

### Integration tests

- orchestrator creates a small dependency chain and the dispatcher promotes
  tasks in order
- worker completion exposes its summary to downstream tasks
- reviewer rejection causes a visible blocked state and preserves context
- dispatcher retry and reclaim behavior survives restart conditions

### End-to-end tests

- a simple orchestrator / worker / reviewer scenario runs from start to finish
- the final synthesis is generated from Kanban state after all tasks complete

## Acceptance Criteria

The design is complete when all of the following are true:

- a team can be expressed entirely with existing Hermes profiles and Kanban
- the orchestrator can decompose work without becoming a hidden runtime
- worker and reviewer results remain durable after restart
- retry, block, and recovery are visible in the board history
- the workflow remains upstream-compatible with Hermes profile and dispatcher
  semantics

## Implementation Boundary

This design intentionally stops at the workflow layer.

If a later implementation needs convenience scaffolding, it should stay thin:

- profile creation helpers
- team bootstrap config
- documentation and examples

The core runtime model should remain profiles + Kanban dispatcher, not a new
subagent framework.
