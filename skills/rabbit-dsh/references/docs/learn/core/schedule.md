# Scheduled Dispatch

- 
- Concepts Course
- Core Mechanisms
- Scheduled Dispatch
On this page

# Scheduled Dispatch

Audit baseline 0.1.5-alpha.1 @ 5dda764ed3; see [source/npm channels](../../guides/deepseek-harness-status.md).

**Opt-in**: from the official checkout run `pnpm dsh web --patch apps/cli/config/examples/schedule/cordis.yml`. This enables the three tools plus the read-only reminder catalog for that process without changing the default Web composition. Delivery is session-local; closing the process or leaving the Session cold pauses its timer. Reactivating the same Session handles overdue reminders; reading cold history does not wake them. This is not an OS notification service or persistent cross-session cron.

Repeats stay aligned to their creation time. Missed intervals coalesce to the latest occurrence; repeats due at one idle decision share one follow-up, after due one-shots. Browser time zones help natural-language interpretation, but `at` still requires an explicit zone. Official usage: [schedule.md](https://github.com/deepseek-ai/deepseek-harness/blob/master/docs/user/guide/schedule.md).

**One-liner**: `@deepseek-ai/dsh-schedule` gives live agents 3 in-session tools (`schedule_create` / `schedule_list` / `schedule_delete`) to manage **persistent reminders**: **the session event log owns reminder state**, and the timer and model follow-up are only discardable projections of the log.

The ability to make an agent do something on a schedule. Core insight: reminder state lives not in "an in-memory timer" but in the **session event log**; so fold/recover reads only the log, and a crashed timer doesn't matter.

## Contents

- [1. Three tools](#1-three-tools)
- [2. State model (a key design)](#2-state-model-a-key-design)
- [3. Time semantics (strict)](#3-time-semantics-strict)
- [4. Runtime delivery: how a reminder becomes a real turn](#4-runtime-delivery-how-a-reminder-becomes-a-real-turn)
- [5. Composition requirements](#5-composition-requirements)
- [6. Verification](#6-verification)
- [Next steps](#next-steps)

---

## 1. Three tools

| Tool | Input | Behavior |
| --- | --- | --- |
| schedule_create | after_seconds (positive integer) / at (absolute time) / every_seconds (≥5 minutes) | create a reminder |
| schedule_list | — | list active reminders (incl. scheduled / overdue state) |
| schedule_delete | id | delete a reminder |

`schedule_dispatch` is **not a tool**: dispatch is an internal operation in the `schedule/change` event. On-time delivery is done by the runtime (see below).

## 2. State model (a key design)

```text
session event log (single source of truth)

  ├── schedule/change events (create/delete/dispatch union, version 1)

  ├── timer (discardable projection)

  └── model follow-up (discardable projection)
```

Important properties:

- **session fold = the full log**; a fork folds only `session.ownEvents()` (the inherited cut is `inheritedEventCount`): a **child session does not inherit the parent session's reminders**

- before every read, first `ctx.sessions.flush(session)`; persistence unavailable → `persistence_uncertain`, and **never treat un-confirmed state as a result**

- replay rejects: unknown versions, duplicate ids, shape-mismatched dispatches, and transitions on inactive records

- after each successful preflight, and after a real barrier succeeds, callback `onDurableChange` drives the owner to recompute

### Client projection (optional)

When `ctx.sessionProjections` exists, the plugin registers the strict `schedule` projection unit (source `packages/schedule/schedule/src/projection.ts`): the checkpoint shape is `{ inheritedEventCount, active, seenIds }`, and the wire publishes only the complete `active` array. The projection carries **durable records only** — scheduled/overdue status, local time, ordering, popover state, and delivery receipts are derived by the browser from the array and its own clock. A headless composition without the registry keeps the same tools and runtime.

The browser-safe vocabulary comes from the type-only export **`@deepseek-ai/dsh-schedule/client`** (source `packages/schedule/schedule/src/client.ts`, which re-exports types only). The shipped Web bundle mounts the `ui-schedule` row as `disabled: true`; only the explicit Schedule overlay enables it together with the Host Schedule services.

## 3. Time semantics (strict)

`at` supports two forms:

| Form | Example |
| --- | --- |
| RFC 3339 string | 2026-08-12T10:00:00Z or with an offset |
| local form | { date, time, time_zone }: must be explicit UTC or an IANA time zone |

Rejections: missing time zone, offset-less strings, times inside a DST gap (overlap takes the earlier one), and targets that aren't in the future. **After creation only the normalized UTC is kept**: a Schedule never reads the browser/session/model-context time zone.

Minimum interval: `every_seconds` can't be smaller than `MIN_EVERY_INTERVAL_SECONDS = 300` (5 minutes).

## 4. Runtime delivery: how a reminder becomes a real turn

An on-time reminder isn't "just a state change" — it's delivered to the agent as **one real user message**:

```text
one ScheduleRuntime per root agent maintains the loop

 → a timer uses whenIdle() + MAX_TIMER_DELAY_MS(2147483647) to wait for an idle phase

 → on time, uses agent.runMaintenance(...) to claim an idle phase

 → builds a user message; agent.followup(message) injects one "follow-up turn"

 → this is precisely the next-turn input the model actually receives and processes
```

Tool calls also carry a **cancellable transaction** (`runCancellableScheduleTransaction` / `exec.signal`) to prevent duplicate delivery.

The delivered text is a stable user-role framing with JSON-escaped dynamic values (source `src/domain.ts` / `src/runtime.ts`):

- one-shot reminder: `[SCHEDULE REMINDER]` + `schedule_id_json` / `occurrence_at` / `reminder_prompt_json`

- fixed-rate batch: `[SCHEDULE REMINDER BATCH]` + `reminders_json` (an array in target and creation order, each entry carrying `schedule_id`, the latest `occurrence_at`, and the `reminder_prompt` supplied at creation)

## 5. Composition requirements

- load order: **after** `ctx.sessions`, `ctx.agents`, `ctx.tools`, `ctx.sessionPersistence` + the flush-persistence listener; a failed static injection = the composition fails outright

- **only listens to future `agent/created`**: agents and subagents that already exist at load time will **not** get a Schedule

- `schedule/change`'s durably-commit delivery barrier and the `onDurableChange` observer drive recomputation after create/delete

- `ctx.sessionProjections` is an **optional** dependency (registers the `schedule` projection unit when present), not an inject entry; the official overlay also inserts `@deepseek-ai/dsh-time-context` and flips `ui-schedule` from `disabled: true`

## 6. Verification

```sh
# find schedule/change events in the session log (default zstd, two-level directories)

zstdcat ~/.dsh/sessions/*/*/session*.jsonl.zstd | jq -r 'select(.type == "schedule/change")'

# inspect what turn it gets delivered into

zstdcat ~/.dsh/sessions/*/*/session*.jsonl.zstd | grep -E "user/message|schedule/" | tail
```

## Next steps

- [Agent Main Loop](../../learn/core/agent-loop.md): how a follow-up gets driven

- [Event System](../../learn/core/event-system.md): which plane `schedule/change` lives on
