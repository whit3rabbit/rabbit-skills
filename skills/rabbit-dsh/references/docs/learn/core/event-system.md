# Event System

- 
- Concepts Course
- Core Mechanisms
- Event System
On this page

# Event System

**One-liner**: DSH has **two event families**. Cordis in-process events (`ctx.on`, a hook chain for inter-plugin communication) and SessionEvent session logs (persistent, event-sourced). They are **not the same thing**: don't conflate "listening" with "persisting".

**Audit baseline 0.1.5-alpha.1 @ 5dda764ed3**: event names, dispatch modes, and envelope fields are all verified point-by-point against the official source.

This page is the master overview of "how plugins communicate, and how sessions are recorded". After reading it you'll know: when to use `ctx.on`, when to use `session.append`, what events exist, and the difference between `(plural tools/)` and `(singular tool/)`.

## Contents

- [1. Two event planes](#1-two-event-planes)
- [2. Five dispatch modes (ctx.emit/*)](#2-five-dispatch-modes-ctxemit)
- [3. agent/*: agent lifecycle and control plane](#3-agent-agent-lifecycle-and-control-plane)
- [4. The tools pipeline (Cordis, plural tools/)](#4-the-tools-pipeline-cordis-plural-tools)
- [5. SessionEvent session-log vocabulary](#5-sessionevent-session-log-vocabulary)
- [6. Event-type conventions and the format gate](#6-event-type-conventions-and-the-format-gate)
- [7. The two ways a plugin participates](#7-the-two-ways-a-plugin-participates)
- [8. Several seams consuming the same stream](#8-several-seams-consuming-the-same-stream)
- [9. Verification](#9-verification)
- [Next steps](#next-steps)

---

## 1. Two event planes

|  | Cordis in-process events | SessionEvent session logs |
| --- | --- | --- |
| Carrier | memory, ctx.on/ctx.emit | session append-only log (default zstd-compressed) |
| Semantics | transient notifications, hook chains | event sourcing, recoverable session facts |
| Lifetime | auto-unregistered on plugin unmount | persisted, survives restarts |
| Examples | agent/status, tools/pre-execute, session/created | user/message, request/header, tool/call, tool/result |

**Key**: the session log ("single source of truth") carries telemetry, projections, and recovery; Cordis events are **in-process reactive extension**. Don't think mounting `ctx.on` persists anything: for persistence use `session.append`.

## 2. Five dispatch modes (ctx.emit/*)

Cordis event dispatch modes determine how listeners get composed:

| Mode | Semantics | Typical |
| --- | --- | --- |
| emit | fire synchronously, don't wait for listeners | agent/error |
| parallel | async in parallel, await all | session/flush |
| serial | serially, one by one | some agent/* |
| bail | stop at the first bail result | — |
| waterfall | listeners form a next() chain; next()'s return value flows to the next | tools/pre-execute, agent/request |

**waterfall must call `next()`**: missing it short-circuits the entire chain. Publishing side uses `ctx.emit()` / `ctx.parallel()` / `ctx.waterfall()`.

## 3. agent/*: agent lifecycle and control plane

| Event | Timing / dispatch |
| --- | --- |
| agent/created / agent/disposed | created / destroyed (paired) |
| agent/status | running-state transitions |
| agent/pre-step | per-step assembly (waterfall) |
| agent/request | request-assembly replacement (waterfall) |
| agent/request-error | model-request failure recovery (waterfall; dsh-llm-retry hangs here) |
| agent/turn-stopping | a turn begins stopping (serial) |
| agent/error / agent/session-start | error / session start |
| agent/inbox/* | inserted / claimed / discarded (see the main loop) |

agent/* is the **control plane**; the actual conversation content flows through the session log.

## 4. The tools pipeline (Cordis, plural tools/)

The extension points of each tool call, extending from [Agent Main Loop](../../learn/core/agent-loop.md):

**`tools/result` (plural, a Cordis notification) ≠ `tool/result` (singular, a session-log event)**: the former is an in-process notification, the latter a persisted session event. This is the pair that's easiest to confuse.

## 5. SessionEvent session-log vocabulary

**Singular `tool/`, persisted**. One session log:

```jsonl
{"type":"session","version":3,"id":"...","createdAt":0,"isSeeded":false,"delegationDepth":0}

{"type":"user/message","seq":1,"time":0,"data":{...},"surfaceOp":"append"}

{"type":"request/header","seq":2,"time":0,"data":{...}}

{"type":"tool/call","seq":3,"time":0,"data":{...}}

{"type":"tool/result","seq":4,"time":0,"data":{...},"surfaceOp":"append"}
```

Common types: `system/message`, `user/message`, `assistant/message`, `assistant/attempt`, `request/header`, `request/context`, `tool/call`, `tool/result`, `step/start`, `step/end`, `turn/start`, `turn/end`, `session/end-seed`, `compaction/*`, `permission/preset`, `feedback/record`, `todo/write`, `goal/change`, `llm/retry`, `llm/retry-started`. For the full catalog see `$SRC/packages/core/session/src/known-event-types.ts`.

**Event-envelope fields** (optional by event type):

| Field | Meaning |
| --- | --- |
| seq | the monotonically increasing persisted ordering key |
| time | Unix epoch milliseconds |
| sourceEventSeqs | seqs of the source events referenced (compaction replacement→shadowed entries); present only on surface events |
| surfaceOp | append or { op:'replace', startSeq, endSeq }, only valid for system/message/user/message/assistant/message/tool/result |
| ignorable | unknown types with this set can be skipped; absent = required, unknown types reject rebuild |

## 6. Event-type conventions and the format gate

- **`seq` is monotonically increasing** (the ordering key)

- **format-version gate**: when the log's first-line `version` is newer than the current `SESSION_FORMAT_VERSION` (=3), loading rejects outright and prompts upgrading the harness; released v0/v1/v2 are migrated to v3 by the format catalog

- unknown types: no `ignorable` → reject; with `ignorable` → skip

- telemetry / projection / recovery **consume the same event stream** (that's what "the log is the single source of truth" means)

## 7. The two ways a plugin participates

| What you want | How to do it |
| --- | --- |
| listen for reactive extension | ctx.on('tools/result', handler) (Cordis) |
| publish a persisted fact | session.append(type, data), then await ctx.sessions.flush(session) |
| custom persisted events | first declare module '@deepseek-ai/dsh-session/types' to augment SessionEventMap, otherwise append rejects unknown types |
| custom Cordis events | ctx.emit, auto-cleaned on plugin unmount |

Details on the two event planes + code in [Listening to Events](../../learn/dev/listen-events.md).

## 8. Several seams consuming the same stream

| Seam | What it does with the event stream |
| --- | --- |
| session-persistence | storage/reload (eager write-behind) |
| session-projection | derived views (cache) |
| session-telemetry | OTel export |
| session-title | title generation |
| UI | session/event + agent/* control events render the conversation |

## 9. Verification

```sh
# the event stream = the full session log (default zstd-compressed, two-level directories)

zstdcat ~/.dsh/sessions/*/*/session*.jsonl.zstd | jq -r '.type' | sort | uniq -c | sort -rn | head -12

# inspect agent control events

zstdcat ~/.dsh/sessions/*/*/session*.jsonl.zstd | grep -E '"agent/' | head
```

## Next steps

- [Session System](../../learn/core/session.md): how events get persisted (surface/log)

- [Listening to Events](../../learn/dev/listen-events.md): listen/publish hands-on

- [Agent Main Loop](../../learn/core/agent-loop.md): where agent/* and inbox events come from
