# The Session System

- 
- Concepts Course
- Core Mechanisms
- The Session System
On this page

# The Session System

**One-liner**: a session is **event-sourced**: `Session` is the append-only **single source of truth** for the conversation history, and the model's LLM message history is **derived** from it; persistence, projection, and telemetry are all built around the same string of `SessionEvent`s. No parallel "persisted message" type exists.

**Audit baseline 0.1.5-alpha.1 @ 5dda764ed3**: package names, ctx keys, event names, config keys, and on-disk layout are all verified point-by-point against the official source.

This is the core of understanding "how a conversation is recorded, recovered, and displayed". After reading it you can answer: what exact shape a message is stored as in the log, what the relationship between surface and the raw log is, and how recovery after a crash works.

## Contents

- [1. Event sourcing: the log is the single source of truth](#1-event-sourcing-the-log-is-the-single-source-of-truth)
- [2. surface: the derived layer for messages](#2-surface-the-derived-layer-for-messages)
- [3. SessionStore: ctx.sessions](#3-sessionstore-ctxsessions)
- [4. The Session class](#4-the-session-class)
- [5. Request-header reconstruction (request/header)](#5-request-header-reconstruction-requestheader)
- [6. Event envelope fields (optional by event type)](#6-event-envelope-fields-optional-by-event-type)
- [7. Crash recovery and turn-end reasons](#7-crash-recovery-and-turn-end-reasons)
- [8. Event-sourced validation: snapshot and immutability](#8-event-sourced-validation-snapshot-and-immutability)
- [9. Persistence backend: JSONL](#9-persistence-backend-jsonl)
- [10. Persistence format and migration](#10-persistence-format-and-migration)
- [11. When to persist: checkpoint-policy](#11-when-to-persist-checkpoint-policy)
- [12. Projection persistence cache: projection-cache](#12-projection-persistence-cache-projection-cache)
- [13. Session title: the trio](#13-session-title-the-trio)
- [14. Telemetry: session-telemetry-otel](#14-telemetry-session-telemetry-otel)
- [15. Corruption and format policy](#15-corruption-and-format-policy)
- [16. Verification](#16-verification)
- [Next steps](#next-steps)

---

## 1. Event sourcing: the log is the single source of truth

The core mental model: a `Session` stores an **immutable event stream**, not a "list of messages".

```text
SessionEvent (append-only event stream)

  ├── session-persistence   store / reload / list (JSONL backend)

  ├── session-format-*      historical format migration (v0→v1→v2→v3)

  ├── session-projection    derived view (cached)

  ├── session-telemetry     telemetry export (OTel)

  └── session-title         title generation

the "LLM message history" the model sees = **derived** from this event stream (the surface layer)
```

From the source verbatim:

Event-sourcing model: the log is the single source of truth, therefore **no parallel 『persisted message』 type exists**.

This boundary is the foundation of everything: whatever you want to "add information" to a session, it's either a **new event type** (append) or a **derived view** (surface/projection) — not a separate message table.

## 2. surface: the derived layer for messages

The raw log doesn't only hold "messages"; it also has boundaries, attempts, usage, errors, and other lifecycle events. The model needs an **ordered message projection** — this is **surface**, an ordered projection layer over the raw log.

- **surface only projects "message-producing" events**: `system/message`, `user/message`, `assistant/message`, `tool/result` (this is `SurfaceEventType`)

- **`assistant/attempt`, lifecycle boundaries, errors**, etc. are excluded from surface (but stay in the log)

- **`surfaceOp`** marks how an event enters the surface and is only legal on those four event types: `'append'`, or `{ op:'replace', startSeq, endSeq }` (inclusive endpoints that must both be current surface nodes, with `sourceEventSeqs` covering every shadowed node)

Two reading conventions, don't mix them:

|  | who reads | which one |
| --- | --- | --- |
| model (request context) | deriveMessages() | surface (what it sees is the replaced face) |
| human transcript (debug/replay) | append-origin events | original events (a landed replacement has shadowed the old history) |

One rule of thumb: to make "the model see a summarized version", land a surface replace; to see "what actually happened", look at the raw log events.

## 3. SessionStore: ctx.sessions

`ctx.sessions` creates and holds the event-sourced `Session` instances. **Persistence is not what it implements**: plugins subscribe to `session/event`, flush at `session/flush`, and may mirror the `session/created`/`session/disposed` lifecycle.

| API | Contract |
| --- | --- |
| create(id?, { seed?, meta? }?) | validate and detach the persistent seed/header, fill version/id, createdAt defaults to now, publish and bind to the calling fiber |
| flush(session) | publish the awaited parallel persistence checkpoint; objects that weren't published / already detached / stale are rejected |
| fork(source, boundary?, childSessionId?) | resolve the session, select a seed (default: the current last event seq), require the prefix to end outside a turn, create a live child session with lineage metadata |
| get(id) | get it or undefined |
| list() | list them |

### The split lifecycle (only when teardown must be ordered against other resources)

For most cases `create()` is enough; but when teardown must be **ordered** with other resources, use the three-phase form:

```ts
prepare(id?, opts?)   // validate and construct, don't publish

enter(session)        // collision check + publish (no announce), returns entry-bound idempotent detach

                      // concurrent same-id may all prepare, but only one enter succeeds; stale detach can't delete the replacement

announce(session)     // emit the single creation edge; duplicate/reentrant announce rejected
```

`dsh-agent-loop` uses this split so the **last loop flush** happens **before** the session detach.

## 4. The Session class

Note: `Session` is a **plain class, not a Cordis Service**. Live sessions go through `ctx.sessions.create()`; `detached` replay/inspect sessions use `Session.create()` (the latter emits no lifecycle events and binds no fiber).

### Key methods

| Method | Contract |
| --- | --- |
| session.append(type, data, opts?) | snapshot and freeze the persisted data and surface metadata, validate the marker shape, referenced source-event seqs, complete-replace coverage, single-result tool/result rewrites; notify observers synchronously after commit (isolated failure). reentrant append to a session being attached is rejected |
| session.deriveMessages() | incrementally projects every new surface entry, returns a frozen message array |
| session.snapshotEvents(fromSeq?, toSeqExclusive?) | materializes a frozen half-open range; a full current snapshot is cached until the next append |
| session.eventAt(seq) | reads one accepted, deeply frozen event by seq |
| session.seq / session.id | current log length (the next event's seq) / readonly identifier |
| session.header | detached, deeply frozen creation metadata |
| session.surface | readonly surface view |
| session.inheritedEventCount / session.ownEvents() / session.isOwnSeq(seq) | fork-inherited prefix length / child-owned events / whether a position is child-owned |
| session.firstLiveSeq | seq of this process's first append (constructor seed length) |

### Header vs event separation

|  | content | replayable |
| --- | --- | --- |
| SessionHeader | version, id, createdAt, optional cwd/parentSession, isSeeded, optional origin/delegationDepth/agentPreset | creation metadata, detached + deeply frozen at write, immutable at runtime; the exact inherited prefix length is Session state (inheritedEventCount), not a header field |
| SessionEvent | replayable conversation state | replayable |

## 5. Request-header reconstruction (request/header)

`request/header` records a **complete canonical snapshot** of one request (not a historical request envelope), with a four-valued `reason`: `initial` / `resume` / `change` / `series` (`series` = the envelope was unchanged but an explicitly distinct message series starts, or it follows a surface replacement).

- An optional `adapterDefaults` map: marks the effective `reasoningEffort`/`maxTokens` as values **materialized by exact model resolution**, so a next request proposal can distinguish them from explicit session settings: this is the persistence landing point of the "adapter-default marker" in [Agent Main Loop](../../learn/core/agent-loop.md)

- `foldRequestHeader()` picks the most recent snapshot; legacy delta events and the removed `fallback` reason from historical formats are rejected at read time by the `session-format-v0-to-v1` migration package

`user/message` stores the full `UserMessage` (identity is created even before inbox routing / step entry); its `content` is rendered as-is, and `source` is the only channel distinguishing "human prompt / synthetic injection / an incoming goal round".

## 6. Event envelope fields (optional by event type)

| Field | Meaning |
| --- | --- |
| seq | the monotonically increasing persisted ordering key |
| time | Unix epoch milliseconds |
| sourceEventSeqs?: SessionSeq[] | referenced source-event seqs (e.g. the shadowed entries behind a compaction replacement). Present only on surface events; assistant/message forbids it (it embeds its own provider stream) |
| surfaceOp?: SurfaceOp | how the event enters the surface; absent on non-surface events (boundaries/attempts/errors) |
| ignorable?: true | an unrecognized type can be safely skipped when reading; absent = required, and unknown types reject session reconstruction |

### Event vocabulary and extension

- The full catalog lives in `known-event-types.ts` and the generated persistence catalog

- **`SessionEventMap` is declaratively merged**: plugins use `declare module` to add their own types (`compaction/*`, the hook bridge's `hook/*`, etc.), merging members into the same catalog

- For a plugin to have its own persisted facts: `session.append` then `await ctx.sessions.flush(session)` — don't fake an execution turn

## 7. Crash recovery and turn-end reasons

`turn/start` carries only the turn number; the `user/message` batches that follow record inputs, `llm/retry` records request recovery. `turn/end`'s `TurnEndReasonMap` is a `kind`-tagged union:

| kind | timing |
| --- | --- |
| completed | normal completion |
| aborted | a live turn was interrupted, reason: AgentCancelCause (keeps the typed cancel reason). Older formats import as { kind:'aborted', reason:{ kind:'legacy' } } |
| blocked | blocked by policy/guards |
| error | the turn failed, { kind:'error', error } |
| max-tokens | at least one step hit its output-token ceiling |
| interrupted | synthesized only for crash recovery (no other evidence found) |

**Crash recovery**: a cold load synthesizes closers through `interruptedTurnClosers()` — an unmatched tool call first gets an error `tool/result` (`TOOL_NOT_STARTED`/`TOOL_OUTCOME_UNKNOWN`), then an open `step/end`, then `turn/end { kind:'interrupted' }`; so a recovered session never has a "dangling turn".

## 8. Event-sourced validation: snapshot and immutability

Persisted values must be "accepted in one pass", not "check once then read again":

- `isJsonValue(value)`: boolean predicate

- `snapshotJsonValue(value)`: one-pass iterative validation and copy; rejects cycles, unsupported scalars, exotic prototypes, non-finite numbers, and `-0`; **no call-stack depth limit** (iterative implementation)

- `snapshotSessionEvent(event)` / `adoptSessionEvent(event)`: clone a borrowed one / take sole ownership of a mutable one in place (request-header)

## 9. Persistence backend: JSONL

`session-persistence-jsonl` is the only first-party `SessionPersistence` provider, with just two config fields:

| Config | Default | Effect |
| --- | --- | --- |
| root | none (required, no default) | session log root directory, usually $DSH_HOME/sessions |
| compression | zstd | zstd (checksummed frames) or none (plain-text JSONL) |

The write-coalescing window is no longer configuration: it is the seam's internal scheduling policy inside each write handle.

**On-disk layout** (current logical format V3 → filename carries `v3`):

```sh
~/.dsh/sessions/--<normalized-cwd>--/<encoded-id>/session.v3.jsonl.zstd   # current generation

~/.dsh/sessions/_no-cwd/<encoded-id>/session.v3.jsonl.zstd               # session without a cwd
```

- each session directory keeps immutable historical generations: `session.jsonl[.zstd]` = released v0, `session.v1.jsonl[.zstd]` = released v1, `session.v2.jsonl[.zstd]` = released v2, current is `session.v3.jsonl[.zstd]`; runtime selects the numerically highest generation

- zstd-compressed by default; to `head`/`jq` directly, configure `compression: 'none'` or `zstdcat` first

- two-level dirs: `--<cwd>--` (workspace, `_no-cwd` when absent) + `<encoded-id>` (the session id injectively escaped to one safe path segment)

- one live writer per session: an in-process claim plus a non-blocking `flock(2)` on `session.lock` (a named kernel semaphore on Windows); the first append publishes with `link()` without overwrite, which needs the prebuilt `node-addon-system` on POSIX

## 10. Persistence format and migration

Session logs have a **logical format version** (currently `SESSION_FORMAT_VERSION = 3`) and per-version **physical generations**. Historical logs are migrated to the current format by a set of pure libraries (not cordis plugins):

| Package | Role |
| --- | --- |
| session-format | pure library: adjacent-format planning, lossless JSON checks, header-only migration, and physical codec dispatch |
| session-format-v0-to-v1 | frozen released-v0 decoder + identity migration to v1 (rejects legacy delta events and the removed fallback reason) |
| session-format-v1-to-v2 | frozen released-v1 decoder + cardinality-changing migration: embeds top-level assistant/chunk into assistant/message and records an assistant/attempt for failed/retried/cancelled attempts |
| session-format-v2-to-v3 | new: promotes system prompts into system/message, remaps local event references, translates PTC and preset names, and canonicalizes envelopes |
| session-format-catalog | build-static catalog: verifies the gap-free v0→v3 chain at module init and exposes physical dispatch plus the current encoder |

Migration is triggered when a **historical generation is opened**: `open(id,'read')` decodes and migrates in memory without publishing a successor; `open(id,'write')` verifies and publishes the current `session.v3.jsonl[.zstd]` generation alongside it, leaving the source byte-identical. There is no CLI or config knob; a log the build cannot faithfully interpret is refused with `SessionFormatUnsupportedError` and the source is left untouched. Steps and rollback are in [Upgrade & Migration](../../guides/upgrade-migration.md).

## 11. When to persist: checkpoint-policy

`session-checkpoint-policy` is a zero-config **semantic persistence policy** that decides "when it must hit disk". It consumes `ctx.sessions`/`ctx.llm`/`ctx.tools` and takes effect when `ctx.sessionPersistence` exists (pairs with the JSONL backend).

It checkpoints at three boundaries:

| Boundary | Guarantee |
| --- | --- |
| before the model adapter receives a request | the request's buffered events are already durable |
| before a top-level tool body can have external side effects | the recorded calls are durable before the body runs |
| every agent/pre-step | the previous response and ordered tool results are durable before the next request |

Persistence and checkpoint scheduling are two deliberately separated plugins: the persistence backend runs bounded background batched appends and turns every `session/flush` into an immediate quiescence barrier; this policy only selects the request / tool-dispatch / next-step three barriers. Mounting only the backend without this policy is legal, but a crash can lose writes within the batching window or writes that haven't completed. A checkpoint rejection is **fail-closed**: if the model and tool boundaries reject, the adapter / tool body doesn't run; a step-boundary rejection fails the turn. Concurrent tool checkpoints share the session store's serial drain, so seqs are never duplicated.

**Mount status: mounted by default** (together with the JSONL backend).

## 12. Projection persistence cache: projection-cache

`session-projection-cache` provides `ctx.sessionProjectionCache`: a durable checkpoint of each registered projection unit's state, one per session, in the domain data form (the `session_projcache` domain, `per-record` layout; the shipped composition's json backend stores each record at `<root>/session_projcache/sessions/<id>.json`).

One stored row `(key → {ver, seq, val})` is a **fold shortcut, not authoritative**: it may be stale (`seq` states exactly how stale), but never wrong. The promises that follow:

- every background write is **fail-soft**: on failure it logs a warning and stays stale, self-healing on the next write or cold read; a crash only costs a tail replay, never a wrong value

- `ver` not matching the live unit's `stateVersion` → dropped at read, no migration, the key is re-folded from the log

- **whole-record write**: each write replaces the session's complete checkpoint, snapshotted across a lossless-JSON boundary; unit state that isn't plain-JSON fails loud

- record binds to the log's lifecycle (storing `formatVersion`/`createdAt`/`cwd`/`isSeeded`/`inheritedEventCount`), validated on every read; a deleted-and-recreated id or a swapped store discards irrelevant records rather than planting phantom values

- **log first, cache follows**: a live checkpoint flushes the buffered events durable before landing the cache row; a crash can only leave the cache behind the log, never ahead of it

The write policy is three forced points plus two configured throttles:

| Trigger | Nature |
| --- | --- |
| session creation (the seed-derived cut) | forced |
| turn/end | forced (a cold read wants the turn-final value) |
| session disposal (detach) | forced (the live→cold moment) |
| every writeEveryEvents committed events | configured throttle (count) |
| writeIntervalMs after the first dirty event | configured throttle (interval) |

Both `writeEveryEvents` / `writeIntervalMs` are required with no default. Read ladder: zero-I/O `cachedSnapshot(meta, inheritedEventCount, keys?)` (reads a stored record only on identity + version match) and `coldSnapshot(meta, inheritedEventCount, events)` (the caller passes the complete log in seq order; internally cache → `ctx.sessionProjections.restoreFloor` → `restore` → fail-soft write-back).

**Mount status: mounted by default** (in the Web composition `writeEveryEvents: 200`, `writeIntervalMs: 5000`; without it the projection system only runs live-only).

## 13. Session title: the trio

The session title comes from the `ctx.sessionTitle` seam; the model-backed title providers share one implementation strategy (the `session-title-llm` library), and what's actually optional are the two provider plugins:

| Package | Form | cadence | Mount |
| --- | --- | --- | --- |
| session-title-llm | library (not a cordis plugin) | shared implementation strategy; providers call registerSessionTitleLlmProvider() to register | — |
| session-title-first-prompt-llm | plugin | first-prompt: summarizes the first qualifying user prompt, runs automatically only on the initial fallback of a fresh non-forked session; an automatic failure keeps the fallback, only ctx.sessionTitle.refresh() retries | mounted by default |
| session-title-all-prompts-llm | plugin | all-prompts: a new revision starts after every new human prompt (including seeded history and child-session prompts); a new revision aborts and supersedes the old work | opt-in |

Shared config (all required except a route override; no library-level default):

| Key | Contract |
| --- | --- |
| targetWords | target word count for non-CJK titles |
| targetCjkCharacters | target character count for CJK titles |
| maxInputBytes | UTF-8 byte ceiling for the final JSON-framed user prompt |
| maxOutputTokens | auxiliary generation token ceiling |
| timeoutMs | end-to-end deadline |
| provider,model | optional explicit route; either both or neither |

The route and failure contract: with the `provider`/`model` pair unset it uses the exact route recorded in the current session's `request/header`; an explicit refresh when there's no route yet requires an override. The JSON-framed user prompt (with seq field, wrapping, escaping) is **validated before dispatch** against `maxInputBytes`, rejected rather than truncated on overflow; malformed/empty output, tool calls, and non-stop finish reasons are all rejected. Before dispatch it directly appends a log-only `session/title-llm-request` event through the `Session` (with provider id, exact source seqs, route, system prompt, message list, output-token cap), persisted via eager observation.

The title request is completely separate from the main conversation: the main agent request costs **zero extra tokens**; the title purpose maps to thinking-disabled (DeepSeek adapter), while the main conversation keeps its configured thinking mode.

## 14. Telemetry: session-telemetry-otel

`session-telemetry-otel` is the only mounting entry point of the telemetry seam (OpenTelemetry backend); `mode` has just two values, and `FULL` is **rejected**, not an alias:

| mode | behavior |
| --- | --- |
| FEEDBACK_ONLY (default) | Text feedback, rating creation/edit, note edit, and withdrawal each release the unhanded prefix through that canonical feedback event (context included); later records wait for the next feedback, staying local otherwise |
| DISABLED | no pipeline is constructed, no record leaves the process; live feedback warns locally, cold mutations stay silent |

It composes the OTel JS SDK as-is (`LoggerProvider` → `BatchLogRecordProcessor` → OTLP/HTTP log exporter), mapping every record to `logger.emit()` under the `@deepseek-ai/dsh-session-telemetry-otel` instrumentation scope. The resource identity carries `service.name`/`service.version` (from `dsh-llm`'s `APP_IDENTITY`) plus an anonymous `user.id` (`$DSH_HOME/.anonymous-user-id`, a random UUID).

Upload authorization is fail-closed: a missing/non-`http(s)` `exporter.url`, a non-positive-integer `processor.maxExportBatchSize`, or an invalid `shutdownTimeoutMillis` all fail at plugin load; direct `ctx.sessionTelemetry.emit()` is a no-op in **every** mode and cannot bypass feedback authorization; only new own `feedback/record`/`feedback/message-put`/`feedback/message-delete` events trigger live capture (inherited parent feedback does not authorize a child export). The seam discloses the mode through `ctx.sessionTelemetry.sharing` (`SessionTelemetrySharingStatus`; this backend only ever reports `feedback-only`/`disabled`).

**What leaves the machine**: in upload mode a record carries the full `event.data` (the telemetry seam's raw copy) — full user/assistant message text, tool arguments and results (command output, file content), system prompt, tool schemas, todo, compaction summary, hook `stderrSummary`, feedback text, session `cwd`. The seam has no redaction rules; a deployment crossing a trust boundary must mount its own `session-telemetry/record` redaction rules. See [Data & Privacy](../../user-guide/privacy.md).

**Mount status: mounted by default** (shipped composition mode defaults to `FEEDBACK_ONLY`; the endpoint comes from `exporter.url`, defaulting to `https://harness-telemetry.deepseeksvc.com/v1/logs`, overridable with `DSH_TELEMETRY_OTLP_URL`, switchable with `DSH_TELEMETRY_MODE`, disabled by any non-empty `DSH_TELEMETRY_DISABLED`).

## 15. Corruption and format policy

| Scenario | Policy |
| --- | --- |
| torn tail fragment | drop it |
| committed corrupted / misformatted | reject with SessionPersistenceCorruptionError |
| released historical format (v0/v1/v2) | migrated to current v3 by the format catalog |
| a format newer than current | reject with SessionFormatUnsupportedError, prompting a harness upgrade |
| unknown event type (non-ignorable) | reject with SessionFormatUnsupportedError |
| unknown event type (ignorable) | skip it |

## 16. Verification

```sh
# look at the session-related plugin mounts (mount status: persistence/checkpoint/projection-cache/title/telemetry)

dsh web --dump-config | grep -iE "persistence|checkpoint|projection-cache|session-title|telemetry-otel"

# session logs are compressed JSONL (zstd); decompress to read, one line per event (the current generation is session.v3.jsonl.zstd)

zstdcat ~/.dsh/sessions/*/*/session*.jsonl.zstd | head -3

# type distribution (see which events one session stores)

zstdcat ~/.dsh/sessions/*/*/session*.jsonl.zstd | jq -r .type | sort | uniq -c

# look at request-header reconstruction sources

zstdcat ~/.dsh/sessions/*/*/session*.jsonl.zstd | grep "request/header" | head -1

# look at turn-end reasons

zstdcat ~/.dsh/sessions/*/*/session*.jsonl.zstd | grep "turn/end" | tail
```

## Next steps

- [Agent Main Loop](../../learn/core/agent-loop.md): how the session is driven inside the loop

- [Event System](../../learn/core/event-system.md): the event vocabulary and extension points

- [Model Routing](../../learn/core/llm-routing.md): how a session picks a model

- [Web UI](../../learn/core/web-ui.md): how surface/projection is consumed by the frontend

- [Data & Privacy](../../user-guide/privacy.md): what telemetry leaves the machine and how to turn it off
