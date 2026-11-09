# Goals, Jobs, and Todos

DSH splits "things to do" into three levels, each serving progress at a different granularity:

| Level | Service | Audience | Where state lives |
| --- | --- | --- | --- |
| Goals | ctx.goals | Long-term goals spanning multiple turns/steps | Session log (goal/change events) |
| Jobs | ctx.jobs | Long-running background operations (shared ids, owner isolation) | In-process registry |
| Todos | tool-todo's todo_write | A checklist for one session | Event-sourced session log |

## Contents

- [1. Goals (goal)](#1-goals-goal)
- [2. Jobs (jobs)](#2-jobs-jobs)
- [3. Todos (todo)](#3-todos-todo)
- [How the three work together](#how-the-three-work-together)
- [Verification](#verification)
- [Next steps](#next-steps)

---

## 1. Goals (goal)

**Current completion goal**, stored in the agent's existing session, at most one at a time.

```ts
const ref = await ctx.goals.create({

  objective: 'Audit documentation consistency across the entire repository',

  maxGoalRounds,                    // can override deployment default defaultMaxGoalRounds: 256

})

// state machine: edit / pause / resume / complete / block / clear

await ctx.goals.edit(ref, {...})    // all changes carry a GoalRef{id,revision} compare-and-set fence

await ctx.goals.complete(ref)
```

Key points (source README):

- **create produces an active goal at revision 1 and arms it**; every change appends a durable `goal/change` event (with the full post-state snapshot), and clear uses a revisioned tombstone

- **block is the unified blocking state**: provider limits, config budgets, execution errors, and requests for human input all use this one durable phase, recording a policy-owned kebab-code + a normalized explanation

- `resume` only accepts when rounds remain under the cap (and clears the old blocker reason)

- `disarm()` is a lifecycle exception: it removes in-process continuation permission but writes no revision and emits no event

A goal is not a plain string: it carries completion conditions, a round cap, and blocking state — it is a mechanism that drives a long task continuously forward.

### The /goal human command

`command-goal` registers the global `/goal` command so a human can control goals directly (without a model round):

| Input | Result |
| --- | --- |
| /goal | Shows the current goal, durable phase, round count/cap, and valid follow-up commands (shows usage when no goal exists) |
| /goal  | Creates and arms a new goal; an unfinished goal is not replaced unless cleared first |
| /goal edit  | Changes the goal text without changing phase/activation |
| /goal pause / /goal resume | Pause and disarm / resume and rearm (bounded by the remaining round cap) |

### goal-round-driver: same-session continued progress

`goal-round-driver` is a **same-session continuation driver**: it turns an active + armed goal into consecutive **goal rounds**, pushed forward through the common `Agent` and session services:

```yaml
- id: goal

  name: '@deepseek-ai/dsh-goal'

- id: tool-goal

  name: '@deepseek-ai/dsh-tool-goal'

- id: goal-round-driver

  name: '@deepseek-ai/dsh-goal-round-driver'
```

Goal progress → goal round → model work → next round, until complete / block / round cap.

## 2. Jobs (jobs)

**Background job registry**: shared ids for long-lived producers, owner isolation, read, cancel, wait, notification, and cleanup, all unified under one `ctx.jobs` contract.

```ts
const id = await ctx.jobs.start({ owner, controller, spec })

await ctx.jobs.get(id)         // non-consuming snapshot

await ctx.jobs.read(id)        // streaming job consumption cursor; terminal-state idempotent read

await ctx.jobs.wait(id, 30_000) // wait for terminal state, timeout returns current snapshot

await ctx.jobs.kill(id, caller, 'no longer needed')

ctx.jobs.onJobDone(...)        // observes every terminal-state record (exact-owner only)

ctx.jobs.onJobsChanged(...)    // observes visible-set changes (owner granularity)
```

- **owner is a boundary**: ids like `bash-1` are predictable, and `get/list/read/kill/wait` all compare the caller's SessionId

- **unowned jobs** are open to any caller and live until the service unmounts

- The producer is `dsh-jobs-local`, extending the opaque id namespace via `TaskKindMap`

- Model-facing is `tool-jobs`: `job_output` / `job_list` / `job_kill`

### Completion notices and automatic wakeup

`tool-jobs` listens for every job's terminal state via `ctx.jobs.onJobDone(...)` and delivers a notice for an **unreported** completion, so it is never missed even if the model never read the output (source `packages/jobs/tool-jobs/src/index.ts`):

```txt
background job <id> (<kind>: <label>) finished [status: ...]. Read its output with job_output.
```

Routing depends on the owner's busy/idle state:

| Owner state | Delivery | Notes |
| --- | --- | --- |
| busy (running a step) | injected via owner.inject(message) | the notice lands in the owner's next-step inbox, readable within the current turn; several jobs settling together cost one step |
| idle | completionDelivery: 'wakeup' → owner.followup(message) | opens a new turn on the idle owner (automatic followup); with quiet it stays pending until something else wakes it |

```yaml
# tool-jobs configuration (composition example)

- id: tool-jobs

  name: '@deepseek-ai/dsh-tool-jobs'

  # completionDelivery: 'wakeup'  default; switch to 'quiet' so an idle owner is not turned

  # maxConsecutiveWakes: 3         default, bounds the self-exciting "a woken turn starts a job that wakes it again" chain
```

- **`maxConsecutiveWakes` defaults to 3**: it bounds how many turns completion wakes may open for one owner before it next consumes human input — capping the self-exciting chain where a woken turn starts the job whose completion wakes it again. The budget resets on each `agent/inbox/claimed` where the message comes from a user source (`message.source.kind === 'user'`); `quiet` delivery spends nothing (no turn is opened).

- **`completionDelivery: 'quiet'`**: the idle owner is not turned; the notice stays pending until some other input wakes it. A same-session replacement of the owner starts with a full budget.

- The system prompt steers the model (from `ctx.systemPrompt.section` in `packages/jobs/tool-jobs/src/index.ts`):

Track every background job id you start. You are notified in-session when a job finishes — do not busy-poll or sleep on one; keep working on independent steps and do not duplicate a running job's work. Before giving a final answer, collect every still-relevant job with job_output (set wait: true only when you are genuinely blocked on it), and job_kill jobs that stopped mattering.

- **`job_output(wait:true)` is a blocking read owned by `tool-jobs`**: `waitTimeoutMs` defaults to 30s (a single default wait), and `maxWaitTimeoutMs` defaults to `600_000` (10 min) as the **hard cap on any single wait** — a model-supplied `timeout_ms` is clamped down to it. **A timed-out wait returns the live job snapshot (`[status: running]`) rather than a TOOL_TIMEOUT error**; the job stays alive and can be read again. `onJobDone` also marks a terminal state `reported` when it still has waiters (the `settle` method in `packages/jobs/jobs-local/src/index.ts`).

### Concurrency limit

`dsh-jobs-local` caps active jobs per **exact owner** (source `packages/jobs/jobs-local/src/index.ts`):

- **`maxConcurrentJobsPerOwner` defaults to 10**; it counts `running` + `stopping` states (terminal completed/killed/failed do not occupy a slot).

- **unowned jobs are an independent bucket**: `activeTaskCount` counts `owner === undefined` separately and is not bound by any owner's quota.

- When the limit is reached, `start()` throws and supplies the **model's correct action**: "use job_kill to stop an unneeded job, wait for it to finish, then retry" — `job_kill` the unneeded job, wait for it to settle, then retry.

```yaml
- id: jobs-local

  name: '@deepseek-ai/dsh-jobs-local'

  maxConcurrentJobsPerOwner: 10   # default; running+stopping count, unowned is separate
```

```ts
// packages/jobs/jobs-local/src/index.ts

if (active >= this.maxConcurrentJobsPerOwner) {

  throw new Error(

    `background job limit reached for this owner (limit: ${this.maxConcurrentJobsPerOwner}); use job_kill to stop an unneeded job, wait for it to finish, then retry`,

  )

}
```

## 3. Todos (todo)

`tool-todo` provides the model-callable **`todo_write`**: it writes a checklist into the event-sourced session log. It suits the short-term list of "what I'll do in sequence this turn," with state persisted along with the session.

### todo_write deployment policy

`tool-todo`'s `Config.allowParallelInProgress` is **required** (`z.boolean().required()`, source `packages/todo/tool-todo/src/index.ts`) — a deployment must explicitly declare whether several todos may be active at once:

| allowParallelInProgress | Model guidance | Best for |
| --- | --- | --- |
| true | multiple in_progress allowed; instructs marking every actively worked task | fan-out: concurrent subagents, background commands, workflow fan-out |
| false | at most one in_progress; a call marking more is rejected (throws) | the single-active discipline of one step at a time |

```yaml
- id: tool-todo

  name: '@deepseek-ai/dsh-tool-todo'

  allowParallelInProgress: true    # required; true for fan-out, false for single-active discipline
```

```ts
// packages/todo/tool-todo/src/index.ts

if (!allowParallel && active > 1) {

  throw new Error(`invalid todos: at most one task may be in_progress (got ${active})`)

}
```

- **Single-owner boundary**: `todo_write` needs an owning agent session; `execute` throws when `exec.agent` is absent (a non-agent caller) rather than silently no-op'ing.

- **Whole-list replacement is the only operation**: "send the ENTIRE list every call — it REPLACES the previous list (there are no partial updates, no per-item edits)"; each call appends a `todo/write` snapshot, replay is last-write-wins, and there is no read-back. The projection (`todos` key) holds the latest whole list and clears to `null` on `turn/start`.

## How the three work together

Progress for a typical long task:

```text
create a goal "complete X"   → long-term direction

use todo_write to break the current round into todos  → short-term steps

slower/backgroundable operations go into jobs  → don't block the main loop, come back for results anytime

complete() when the goal is done  → wrap up
```

What the three share: **all hold state through event sourcing / a registry**, so none of them loses progress.

## Verification

```sh
zstdcat ~/.dsh/sessions/*/*/session*.jsonl.zstd | grep -E '"goal/|"todo/' | head

# jobs are in-process; use dsh web --dump-config | grep jobs to see whether it is mounted
```

## Next steps

- [Built-in tools](../features/tools.md): the model-facing side of `tool-goal` / `tool-jobs` / `tool-todo`

- [Subagents and parallelism](../features/subagent.md): dispatching work in parallel
