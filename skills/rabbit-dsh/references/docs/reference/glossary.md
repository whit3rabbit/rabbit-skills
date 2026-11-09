# Glossary

On this page

# Glossary

To go from zero to understanding DSH, skim these terms first. Each entry gives a "one-liner" and a source link.

## Contents

- [A–Z](#az)
- [The Easily Confused Pairs](#the-easily-confused-pairs)
- [Read Deeper as Needed](#read-deeper-as-needed)

---

## A–Z

### ACP (Agent Client Protocol)

An automation transport (not a human-interaction layer) that exposes a harness agent to programmatic clients; the cross-process sub Agent provider `acp` uses it. → [Sub Agents](../features/subagent.md)

### Agent-default-model

The default model selection (`ctx.agentDefaultModel`) shared by every Agent entry point, requiring `{ provider, model }`; used by web / headless / API entry points and can be overridden by in-session Models settings. → [Multi-model](../features/multi-model.md)

### Attachment

The persistent binary attachment seam behind `ctx.attachments`: validates and atomically commits immutable image bytes, while the session log stores only the `sha256:` reference and validated metadata. → [Attachments](../features/attachments.md)

### Bundle

A plugin bundle carrying its own patch, added to a profile as **one layer**. Declared by `dsh.bundle.patch`. → [Plugin Anatomy](../learn/core/plugin-anatomy.md)

### Checkpoint (semantic checkpoint)

`session-checkpoint-policy` forces a flush before model requests, before tool external side effects, and at each step boundary; on refusal it fails closed. → [Session System](../learn/core/session.md)

### Compaction

The compaction capability family: `ctx.compaction` seam plus the `compaction-basic` backend, which folds the oldest surface into a summary under token pressure, reusing the KV cache. → [Context and Tokens](../learn/core/context.md)

### Cordis

DSH's composition framework (vendored, published only as `@deepseek-ai/cordis`), providing `Context`, dependency injection, plugin mounting, and events. → [Architecture](../learn/intro/architecture.md)

### Credentials (credential references)

The `ctx.credentials` seam: config stores only references, not secrets, resolved per operation; priority is process environment > `.credentials.yaml` > working directory `.env` > `$DSH_HOME/.env`. → [Credential Management](../user-guide/credentials.md)

### Dual-face (client dual-face)

A package that has both a node half and a browser half (`dsh.client`). → [Web UI](../learn/core/web-ui.md)

### E2B

An experimental cloud sandbox POC: moves the filesystem + subprocess execution world into an E2B Linux sandbox; opt-in, not mounted by default. → [E2B Cloud Sandbox](../features/e2b.md)

### Feedback

Two contracts: `/feedback` appends a log-only `feedback/record` event; message feedback is an editable rating sidecar bound to a single assistant message; neither enters the model. → [Feedback](../features/feedback.md)

### Guard (behavior guard)

`packages/guard`, two self-contained behavior plugins (repeat-tool-reminder / timeout-policy), watching for no-output patterns and per-call budgets; a non-replaceable capability. → [Tool Execution](../learn/core/tools-execution.md)

### Patch

Stacking entries in `cordis.patch.yml` (insert / override by id) that decide "which layer overrides which". → [Plugin Anatomy](../learn/core/plugin-anatomy.md)

### Persona

Composable persona rows, shadowing deployment personas. → [Agent Presets](../features/persona.md)

### Plan-mode (planning mode)

Per-agent planning collaboration state plus a policy prompt section (soft guidance); entered via `/plan`, exited with `exit_plan_mode` approval; **does not switch models**. → [Multi-model](../features/multi-model.md)

### Preset (permission preset)

An operating-mode profile (`workspace-write` / `danger-full-access`) plus approval. → [Permissions](../user-guide/permissions.md)

### Preset (agent-presets)

The per-session fixed composition (`agent.cordis.yml`). → [Agent Presets](../features/persona.md)

### Profile

The `$DSH_HOME/profiles/<name>` directory, holding bundle layers plus user patch layers. → [Configuration](../user-guide/configuration.md)

### Projection (session projection)

`ctx.sessionProjections`, whole-log derived views for clients (current surface / title / token ledger); fold shortcuts, non-authoritative. → [Session System](../learn/core/session.md)

### Scope

Context layering (global / agent) that determines visibility and masking. → [Plugin Anatomy](../learn/core/plugin-anatomy.md)

### Seam (capability seam)

Abstract capability interfaces (`ctx.llm` / `ctx.tools` / `ctx.sandbox`...), with swappable implementations. → [Architecture](../learn/intro/architecture.md)

### Session / Turn / Step

The three-level lifecycle of session / turn / step. → [First Session](../learn/intro/first-session.md)

### Session query

The `ctx.sessionQuery` session-retrieval seam: authorized reads of live/durable logs, relationship traces, SQLite FTS5 search; the `session_search` tool is not mounted by default. → [Session Query](../features/session-query.md)

### Spill

The `ctx.spillStore` tool-output overflow seam: overly long plaintext is written to a session-scoped file, while the model side gets a bounded preview plus a locator. → [Spill Storage](../features/spill.md)

### Surface

The derived message layer on top of the session log that the model sees. → [Sessions](../learn/core/session.md)

### Token-meter

The replayable metering singleton `ctx.tokenMeter`, estimating with a fixed heuristic (4 chars/token plus structural overhead); the basis for compaction decisions. → [Context and Tokens](../learn/core/context.md)

### Tool

A model-callable capability (schema + output + execute). → [Tool Execution](../learn/core/tools-execution.md)

## The Easily Confused Pairs

| Pair | Explanation |
| --- | --- |
| tools/* vs tool/* | Cordis in-process notifications (plural) vs session log events (singular). → Event System |
| patch layer vs settings layer | static deployer configuration vs user runtime settings. → Configuration |
| permission vs sandbox | operating-mode profiles vs command execution boundaries. → Permissions |
| plan-mode vs multi-model | /plan does not change the model; multi-model relies on multiple providers. → Models |
| surface vs projection | the derived message layer the model sees vs log-derived views for clients. → Sessions |
| shell vs terminal | one-shot command wrapper vs persistent owner-scoped interactive terminal session. → Subprocess and Terminal |

## Read Deeper as Needed

Each term is expanded in detail on its corresponding page; to follow a knowledge-level path, start from the [Learning Path](../getting-started/learning-path.md).
