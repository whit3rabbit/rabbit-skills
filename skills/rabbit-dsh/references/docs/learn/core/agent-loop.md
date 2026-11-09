# The Agent Main Loop

- 
- Concepts Course
- Core Mechanisms
- The Agent Main Loop
On this page

# The Agent Main Loop

Audit baseline 0.1.5-alpha.1 @ 5dda764ed3.

**One-liner**: `@deepseek-ai/dsh-agent-loop` is the **only concrete loop** in the harness: it drives the session/turn/step lifecycle, and everything else is either an abstract service or a plugin; **write new behavior as a plugin — don't change this**.

This is the piece of the whole site you should read most thoroughly. Understand agent-loop and you'll understand "what path a single user message actually travels".

## Contents

- [1. Why it is the "only concrete loop"](#1-why-it-is-the-only-concrete-loop)
- [2. The three-level lifecycle: session / turn / step](#2-the-three-level-lifecycle-session-turn-step)
- [3. Two creation paths: declarative vs programmatic](#3-two-creation-paths-declarative-vs-programmatic)
- [4. Transactional lifecycle: create and reload are the same thing](#4-transactional-lifecycle-create-and-reload-are-the-same-thing)
- [5. Resumability: the boundary of resume](#5-resumability-the-boundary-of-resume)
- [6. send primitives and the inbox: how messages get into the loop](#6-send-primitives-and-the-inbox-how-messages-get-into-the-loop)
- [7. Driving the loop and request assembly: what happens in one step](#7-driving-the-loop-and-request-assembly-what-happens-in-one-step)
- [8. Failure, recovery, and cancellation](#8-failure-recovery-and-cancellation)
- [9. What belongs in plugins (the extension surface)](#9-what-belongs-in-plugins-the-extension-surface)
- [10. Model Experience: the model / token / KV-cache three perspectives](#10-model-experience-the-model-token-kv-cache-three-perspectives)
- [11. Source structure at a glance](#11-source-structure-at-a-glance)
- [12. Config quick reference](#12-config-quick-reference)
- [13. Verification](#13-verification)
- [Next steps](#next-steps)

---

## 1. Why it is the "only concrete loop"

One sentence in the source README defines the architectural boundary of the entire harness:

This is the only package in the harness that contains concrete loop logic. Everything else is either an abstract service or a plugin against the extension points: **new behavior should go into a plugin, not here**.

What this means:

- **The core is extremely thin**: `agent-loop` does exactly one thing — "call the model, run tools, loop". It doesn't decide for you whether to search, to compact, or to ask the user.

- **Everything is an extension point**: search (web), compaction (compact), recovery (llm-retry), sandbox/permissions (guard), subagents (subagent), UI rendering — all of it hangs off **events** as plugins.

- **This boundary is intentional**: before adding something "inside the loop", ask yourself — can it be done with the existing event/tool pipeline? 99% yes. The genuinely rare need is to change the loop itself.

Remember it in one sentence: DSH's philosophy = **`agent-loop` handles "driving", everything else comes from plugin composition**.

## 2. The three-level lifecycle: session / turn / step

Let's establish the basic vocabulary first; we'll use it everywhere below:

- A **session** holds one persistent conversation and can be `resume`d (rebuilt from the log after a crash) or `fork`ed (derives a new session).

- A **turn** starts when you send a message and ends when the agent fully responds; turns are numbered consecutively.

- A **step** is the smallest unit of progress inside a turn: either one model inference or one tool execution. A multi-tool turn = model step → tool step → model step → tool step… until the agent decides it's done.

The agent-loop README says it verbatim: it "drives the session/turn/step lifecycle". **These three levels are the most fundamental structure in the event-sourced log** (see [Event System](../../learn/core/event-system.md)).

## 3. Two creation paths: declarative vs programmatic

An agent is not "an object you `new`". It has two entirely different birth paths, and understanding this determines how you use it.

### 3.1 Declarative (config-driven)

Declared in the `config.agents` of the `agent-loop` plugin:

```yaml
- id: agent-loop

  name: '@deepseek-ai/dsh-agent-loop'

  config:

    maxParallelToolCalls: 10     # default 10; 1 = serial

    agents:

      - id: main

        provider: deepseek-official

        model: deepseek-v4-flash

        reasoningEffort: high     # initial reasoning effort; agent/request may override

        maxTokens: 65536          # per-request output token ceiling

        cwd: /path/to/workspace

      - id: exact

        sessionId: <stable-session-id>   # first use creates it; a remount resumes that id's history

      - id: resume-me

        resumeSessionId: <existing-session-id>   # reload this persisted session (mutually exclusive with sessionId)
```

- Declared agents **start automatically** when the service starts (created internally by `ctx.agentLoop.create()`).

- **Ownership**: the agent belongs to the loop fiber; the handle is discarded.

- **No per-agent persona / setup hook**: declarative agents use the deployment persona; to customize persona/tools per agent, you must go programmatic.

### 3.2 Programmatic (ctx.agents)

Via the factory interface `ctx.agents` (`agent-loop` registers itself as `ctx.agents.setFactory(this)`):

```ts
// programmatic create

const handle = await ctx.agents.create({

  sessionId,             // globally unique; can be prepared in parallel with a concurrent op, enter() adjudicates

  parentAgent?,          // live parent Agent (runtime ownership); omit for a root Agent

  meta?,                 // cwd / parentSession / isSeeded / origin / delegationDepth / agentPreset

  inheritedEventCount?,  // exact inherited prefix length when isSeeded

  seed?,                 // prefix for a forked child session (used to rebuild history)

  agentOptions?,         // per-agent provider/model/reasoningEffort/maxTokens

  setup?,                // trusted in-process composition code (can shadow persona); may return commit() to validate before publish

  signal?,               // only affects the load/setup/publish phase

})

// reload a persisted session

const resumed = await ctx.agents.resume({

  resumeSessionId,       // required: an existing persisted session id

  parentAgent?,

  agentOptions?,

  setup?,

  signal?,

})
```

- The programmatic `AgentHandle` is the **only consumer-side teardown capability**: whoever holds it is responsible for ending this agent's lifecycle.

- `signal` **only applies until the promise settles** (publish/load phase); it does not keep cancelling after the handle becomes visible.

### Ownership comparison

|  | Declarative | Programmatic |
| --- | --- | --- |
| Entry point | config agents: section | ctx.agents.create/resume |
| Start | automatic at service start | when you call it |
| Ownership | loop fiber | the caller holding the AgentHandle |
| persona | fixed by deployment persona | shadowable via setup/agentOptions |
| Typical use | stable main agent | subagents, runtime on-demand |

## 4. Transactional lifecycle: create and reload are the same thing

**The single most important fact**: `create` and `resume` belong to **the same rollback-protected transaction**. It is not "create a session, then request" in two steps, but one indivisible commit.

```text
create / resume (the same rollback-protected transaction)

  ├── construct private session + concrete agent + scoped context

  ├── await setup (optional trusted in-process composition code; must not drive an unpublished agent)

  ├── enter the two registries (agents / sessions)

  ├── publish order: session/created → agent/created → agent/session-start

  └── only at this point does driving the loop begin

teardown (the symmetric sequence at the end)

  stop and drain → revoke scope → close the session write path (drain first) → detach agent → detach session
```

The key concurrency and rollback invariants (key points from the source):

- **`sessionId` is globally unique**: two concurrent operations may prepare with the same id, but the final `enter()` call **adjudicates publication**: each loser fully rolls back its own private resources.

- **`resumeSessionId` and `sessionId` are mutually exclusive**: a session is either created new or reloaded by an existing id.

- **detach is bound to the exact object entered**: a stale disposer cannot accidentally kill a later replacement with the same id: this guarantees "unload one, recreate one" never tramples each other.

- Requesting detach during a synchronous notification within creation **waits for that dispatch to unwind**, keeping `agent/created` ↔ `agent/disposed` pairing complete.

- Plain identity/options passed through are borrowed under a readonly contract; but **seed events and session metadata are validated and snapshotted**, because they cross the durable session boundary.

Common misconception: thinking "resume re-reads the history and then runs a new turn". Actually: load the persisted session → await setup on a **brand-new unpublished agent scope** → then the rollback-protected publish. So a resumed agent and a new one go through **the exact same safe path**.

## 5. Resumability: the boundary of resume

```ts
ctx.agents.resume({ resumeSessionId, ... })
```

- It loads the persisted session via `ctx.sessionPersistence`, registers the agent under the same id, rebuilds history, then awaits setup, then the rollback-protected publish.

- Turn numbers and derived history **continue from the loaded log** (not from 0).

- **Hard dependency**: `resume` needs a session-persistence backend. But it is **not hard-injected**: a demo without persistence still runs, only `resume` will explicitly reject (reporting "persistence absent"). This lets you write pure in-memory demos while enabling resume seamlessly when you need it.

**Practical value**: after a crash / restart, a single `resume` continues the conversation from the persisted log instead of losing it. (Related skills in the out-of-repo ecosystem such as `dsh-harness-ops` cannot be verified against this source; please check on your own.)

## 6. send primitives and the inbox: how messages get into the loop

Content reaching an agent is not handed directly to the model; it goes through a **send primitive based on an inbox (FIFO)**. The source funnels all of this into one unified `send()` primitive, routed by `target × wakeup`, with `followup`/`steer`/`inject` as its three fixed aliases:

| Primitive | target | wakeup | semantics |
| --- | --- | --- | --- |
| followup() | next-turn FIFO | yes | append a "next-turn" input and wake the driver |
| steer() | next-step inbox | yes | append and wake (driver moves to the next step) |
| inject() | next-step inbox | no | append but don't wake; waited on together with a follow-up/steer |

Claim rules **at the turn boundary**:

- At the turn boundary, the driver opens the durable turn and then **atomically** claims pending next-step inputs plus one queued prompt.

- Between two steps, it claims only next-step inputs (never touches the next turn).

**Event-izing the inbox**: every mutation first emits the standardized transition events, then mutates the live projection:

| Event | Timing |
| --- | --- |
| agent/inbox/inserted { message } | every insertion |
| agent/inbox/claimed { message, turn } | each time a message is claimed into a step |
| agent/inbox/discarded { message } | ordinary removal (with outcome:'canceled') |
| agent/inbox/spliced | unified pre-announcement before every mutation (insert/edit/remove/claim/cancel all use the same splice coordinates) |

`MessageId` is **globally unique** across the two pending lists (next-turn / next-step); sync durable-event observers can rebuild removed values from the pre-splice projection.

## 7. Driving the loop and request assembly: what happens in one step

When a batch of inputs in the inbox is claimed into a step, the driver starts assembling **this one model request**.

### 7.1 What kind of request gets assembled

For each step, the loop sends:

```text
per-agent system prompt     (rendered by systemPrompt.assemble())

visible tool schemas        (presented via tools, native/ptc/both)

session-derived messages    (surface messages; turn/step basis below)
```

The loop only fills in the `provider`/`model`/`cwd` variables; **it adds no extra fixed prose**. The full assembly waterfall (`agent/request` + `systemPrompt.assemble()`) is in [Context System](../../learn/core/context.md).

**The system prompt is a surface event, not a request-header field**: `SystemPromptProjection` commits the result of `renderPrompt(assembly)` as `system/message` (surface node 0, before the step's first `user/message`). When the prepared route declares `systemPromptUpdate: 'in-history'`, a non-empty prompt change inside the same request series is **appended** after the cached history (the prefix cache stays valid); a route without that capability or a new series instead **normalizes** the text onto the first system node (logging a per-node replacement) and clears every active system node on an empty rendering.

### 7.2 The adapter-default marker: keeping HMR from mixing flavors

A subtle but critical mechanism that's easy to overlook. After an `agent/request` returns the provider/model call config, the loop calls `ctx.llm.prepareCall()` to:

- validate adapter-specific fields

- materialize the configured reasoning-effort and output-token defaults (under the active-turn signal)

Then `request/header` records the **canonical effective header** `{ config, adapterDefaults?, tools? }`; `adapterDefaults` marks only the fields the adapter materialized (`reasoningEffort` / `maxTokens`). Before the next waterfall, the loop **removes these marked fields** so the current exact route re-materializes its own defaults: while unmarked explicit settings persist across steps / across routes.

`request/header` is appended in only four cases: `initial` (the conversation's first header) / `resume` (a loop instance's first header after a restart) / `change` (the header changed, optionally with `startsSeries: true` for a coincident new series) / `series` (the header is unchanged but an explicitly new message series begins or a surface replacement just happened). Equality uses `headerEquals` (config + adapterDefaults + tools; the prompt is not part of the header).

During that one async resolution, HMR (hot reload) also can't mix one adapter's capability results into another adapter's request. Without this, hot-changing config could pick up "the previous provider's defaults".

### 7.3 Completion anchor

Every **provider call that successfully reaches finish** appends exactly one `assistant/message` completion anchor: including calls with no content and calls that hit the `max-tokens` ceiling. The anchor carries the step's `stream` (the exact timed model stream, compacted without joining delta boundaries) and its usage when reported (there is no separate usage record); a turn cancelled mid-stream finalizes its delivered text/reasoning prefix as the same event with `interrupted: true`; empty content does not enter the derived history.

**A model attempt that committed no surface message** lands as `assistant/attempt` (carrying only `stream`), preserving failed / retried / cancelled / stream-error attempts without fabricating model-visible history.

## 8. Failure, recovery, and cancellation

agent-loop's core principle for failures: **a plugin's failure ends "the current turn", not the whole loop**.

### 8.1 Two kinds of failures, two paths

| Failure source | Outcome |
| --- | --- |
| final adapter selection / dispatch / iteration failure | goes to agent/request-error as a terminal error or an aborted finish |
| middleware / result handling / tools / other extensions | throw closes directly, never enters agent/request-error |

Recovery from `agent/request-error`: a handling listener can return `{ kind: 'retry' }` (wait for the exact-provider to succeed or back off unboundedly, implemented by `dsh-llm-retry`, which emits non-surface `llm/retry` status); **no listener handling it = terminal failure**.

### 8.2 Cancellation semantics

```ts
agent.cancel(cause, { keepInbox })
```

- An effective cancel **clears pending work** (unless `keepInbox`) and cooperatively aborts the current signal

- **Cancelling while idle is a no-op**

- Wake inputs that land after the abort but before activity converges to idle are **locked (wakeRequested)** and replayed at the driver's own convergence boundary: no need to wake again

- A `disposed` cancel **never locks**

- Submitting a wake again while already idle always opens a turn boundary (the state will show a transient `idle → running → idle`)

- Durable `turn/end`'s `aborted` event carries the cancellation cause (`user` / `parent` / `hook` / `disposed`; imported older logs may be `legacy`)

- `whenIdle()` resolves once the whole agent's activity reaches quiescence; `runMaintenance(task)` runs one non-turn maintenance task from the true idle phase (throws synchronously when a turn or another maintenance task already owns the agent)

- **Undispatched model tool calls** receive a synthesized `tool/call` + `ABORTED_BEFORE_DISPATCH` result pair: so the model won't be confused about the "vanished call" in later steps

### 8.3 The two kinds of parallel execution

Within a step, tool calls divide into two kinds:

- **exclusive**: forms a barrier, strictly serial around it

- **parallel-safe**: run in parallel via a bounded rolling pool; reclassified before execution

Only dispatch/body runs in parallel; policy, durable result, and result context keep model order. **This is where `isConcurrencySafe(args)` semantics live** (see [Tool Execution](../../learn/core/tools-execution.md)).

Known limits: **unary classification** — calls whose safety depends on "comparing with siblings" must stay exclusive. There is no built-in turn budget: to cap runaway turns you cancel from existing extension points like `agent/turn-stopping`.

## 9. What belongs in plugins (the extension surface)

The loop is explicitly "only call-model-run-tools-loop". Everything else **must** hang on events. This is DSH's most important programming convention:

| What you want to do | Where to hang it |
| --- | --- |
| hooks / policies | agent/* checkpoints + tools/pre-execute → tools/execute → tools/post-execute → finalizeContent → tools/result pipeline |
| context compaction | pressure in agent/pre-step; the canonical fix for spill in agent/request-error |
| model request recovery | dsh-llm-retry records and waits with backoff in agent/request-error |
| sandbox / permissions / plan | tools/pre-execute (deny/ask), tools.guard(), tools/post-execute, tools/result |
| subagents | ctx.subagents provider (in-process via ctx.agents.create() + owned handle); background via ctx.jobs + dsh-tool-subagent |
| persistence | writes follow the committed session/event via observers; dsh-session-checkpoint-policy owns the per-request durability checkpoint; session.flush() is the explicit observation barrier (consumers flush before reading storage) |
| UI | session/event (boundaries/tool activity) + agent/assistant-stream (in-process live frames start/chunk/end) + agent/* control events (agent/status, created/disposed); the turnBoundary projection supplies turn/step boundaries |

**Test whether you understand**: to give an agent a "retrieve memory before answering every message" feature: don't change agent-loop — hang a plugin on `agent/request` (the assembly waterfall) or `agent/pre-step` to inject the retrieval results. That's exactly what [Context System](../../learn/core/context.md) is about.

## 10. Model Experience: the model / token / KV-cache three perspectives

Understanding these effects tells you "why certain configs burn tokens, why changing schemas invalidates the prefix cache wholesale".

| Dimension | What the model sees | token effect | KV cache effect |
| --- | --- | --- | --- |
| Full request | the surface's system/message node (per-agent prompt) + visible tool schemas + session-derived messages | system text and schemas are repaid every step | only system text/schema/history that is byte-for-byte unchanged (same provider+model route) is reused append-only; on a route declaring systemPromptUpdate: 'in-history', prompt changes are appended after the cached history, keeping the prefix reusable |
| Retained history | accepted user/assistant messages, tool calls and results, injected context, steering | every surface message grows the input; multi-tool turns re-send accumulated history each step | ordinary history growth is append-only reusable; surface replacement or compaction invalidates the prefix |
| Cancelled undispatched calls | ABORTED_BEFORE_DISPATCH error code + fixed text | one fixed error result left per skipped call until compaction | append-only, doesn't invalidate existing entries |

Use this to understand the "compaction summary reuses the request head to align the prefix-cache" point in [Context System](../../learn/core/context.md): the goal is to **keep system text/schema/history byte-for-byte unchanged**, so the provider's KV cache never invalidates.

## 11. Source structure at a glance

The kernel of the `agent-loop` package (`ReactLoopAgent`, its inbox, run controls) is **package-internal**; the package root only exports plugin/service/config contracts, and the exports map has **no `./src/*` escape hatch**. Lifecycle owners are created at the `ctx.agents` layer, not by naming/constructing/starting the driving kernel. This means:

- you always interact with the loop through `ctx.agents` / config

- one prepared session can only be claimed by one concrete driver

- everything observable is exposed through session events and `agent/*` events (you're never given access to internal state)

## 12. Config quick reference

```yaml
agentLoop:

  maxParallelToolCalls: 10    # rolling-pool ceiling of parallel-safe calls per agent; 1=serial

  agents:

    - id: main

      provider: deepseek-official

      model: deepseek-v4-flash

      reasoningEffort: <optional, initial reasoning effort; agent/request may override>

      maxTokens: <positive integer, optional>   # per-request output token ceiling, recorded in request/header

      cwd: <optional, only affects new sessions>

      sessionId: <optional, exact identity: first use creates it, a remount resumes its history>

      resumeSessionId: <optional, mutually exclusive with sessionId>
```

Config points (from the source):

- **`agents` is deliberately not in the Settings section**: it is consumed once at service start, and changing the stored value only "looks" effective. `maxParallelToolCalls` is all of agent-loop's Settings section; hot-editing it caps the next tool group (and invalid values are rejected **at write time**).

- A configured agent's `provider`/`model`/`cwd` are provided as prompt variables; harness identity and deployment persona belong to `dsh-system-prompt`.

- One model call **requires both provider + model**; `agent/request` can complete a missing pair before dispatch.

- `sessionId` and `resumeSessionId` are mutually exclusive; duplicate exact session identities in one config are rejected before startup. A launcher may also `ctx.provide('configuredAgentIdentities', …)` before the Loader mounts to override both keys.

## 13. Verification

```sh
# 1. look at the session event stream (zstd-compressed by default, two-level --<cwd>--/<id>/ dirs; current format version v3)

zstdcat ~/.dsh/sessions/*/*/session.v3.jsonl.zstd | tail -30

# 2. see the session/turn/step three-level structure in one turn of conversation

zstdcat ~/.dsh/sessions/*/*/session.v3.jsonl.zstd \

  | jq -r 'select(.type | test("turn/|step/|assistant/message|assistant/attempt|tool/call|tool/result")) | [.type, (.seq|tostring)] | @tsv'

# 3. look at agent events that reach the log (agent/assistant-stream is in-process only)

zstdcat ~/.dsh/sessions/*/*/session.v3.jsonl.zstd | grep -E "agent/" | head
```

## Next steps

- [Tool Execution](../../learn/core/tools-execution.md): how tools are invoked inside the loop (pipeline + parallelism/cancellation)

- [Context](../../learn/core/context.md): what the model sees on each request (assembly waterfall + KV cache)

- [Events](../../learn/core/event-system.md): the two sets of `agent/*` and `tool/*` events

- [Subagents](../../features/subagent.md): delegating with `ctx.agents.create()` (real use of the programmatic entry point)
