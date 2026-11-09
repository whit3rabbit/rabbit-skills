# Tool Execution

- 
- Concepts Course
- Core Mechanisms
- Tool Execution
On this page

# Tool Execution

Audit baseline 0.1.5-alpha.1 @ 5dda764ed3.

The presentation-mode config value `native / ptc / both` supersedes the historical `code`; the v2→v3 session-format migration renamed the PTC dispatch events from `tool/code-dispatch*` to **`tool/ptc-dispatch*`** (old logs are migrated by `dsh-session-format-v2-to-v3`). In PTC-only mode direct named-tool calls return `UNKNOWN_TOOL`; SDK bindings through `run_code` still enter the complete tool pipeline.

**In one sentence**: a tool = a plugin registering `parameters` + `output` + `execute`. Each invocation goes through an extensible pipeline (`tools/pre-execute` gate → guard → `tools/execute` around → `tools/post-execute` → `finalizeContent` → `tools/result` notification), and `mode`/`presentAs` decides whether it is presented to the model as native/ptc/both. The registry lives in `core/tools`, exposed as `ctx.tools`.

This is the most direct demonstration of DSH's "capabilities are made by plugins". Understanding tools means understanding where the model's "what it can do" comes from.

## Contents

- [One — What a tool is](#one-what-a-tool-is)
- [Two — Three presentation modes: mode / presentAs](#two-three-presentation-modes-mode-presentas)
- [Three — The execution pipeline (each invocation goes through five stages)](#three-the-execution-pipeline-each-invocation-goes-through-five-stages)
- [Four — The guard family: timeout-policy and repeat-tool-reminder](#four-the-guard-family-timeout-policy-and-repeat-tool-reminder)
- [Five — Output contract and content/presentation separation](#five-output-contract-and-contentpresentation-separation)
- [Six — Cancellation semantics: cooperative and quiet](#six-cancellation-semantics-cooperative-and-quiet)
- [Seven — The typed parameter schema (defineTool's DSL)](#seven-the-typed-parameter-schema-definetools-dsl)
- [Eight — Scope and visibility](#eight-scope-and-visibility)
- [Nine — Parallelism and exclusivity (execution mode)](#nine-parallelism-and-exclusivity-execution-mode)
- [Ten — PTC mode (advanced but powerful)](#ten-ptc-mode-advanced-but-powerful)
- [Eleven — A tool's own UI rendering (presentCall/presentResult)](#eleven-a-tools-own-ui-rendering-presentcallpresentresult)
- [Twelve — MCP tools join the same system](#twelve-mcp-tools-join-the-same-system)
- [Verification](#verification)
- [Next steps](#next-steps)

---

## One — What a tool is

A tool = **schema (what the model sees) + executor (what actually runs) + output contract (what it returns)**.

A tool plugins hands its schema to system-prompt assembly through `ctx.tools` (`ctx.systemPrompt.tools()` feeds it automatically), and the executor runs when the model calls it. In a request, the model "sees" the tool's `parameters`; it does **not** see `execute` (the execute function never enters the model context).

### A minimal tool (the standard defineTool form)

```ts
import type { Context } from '@deepseek-ai/cordis'

import { defineTool } from '@deepseek-ai/dsh-tools'

declare const ctx: Context

ctx.tools.register(defineTool({

  name: 'read_file',

  description: 'Read a file from disk.',

  parameters: {

    path: { type: 'string', required: true, description: 'Absolute file path' },

    offset: { type: 'number' },

    limit: { type: 'number' },

  },

  output: {

    schema: { type: 'string' },

    render: (_args, value) => [{ type: 'text', text: value }],

  },

  async execute(args, exec) {

    // args is type-inferred: { path: string; offset?: number; limit?: number }

    return readFile(args.path, { encoding: 'utf8', signal: exec.signal })

  },

}))
```

`defineTool`'s three benefits:

- **Typed**: `parameters` compiles into TypeScript types, and `execute`'s `args` is inferred precisely

- **Automatic validation**: parameters are validated **before execution**; missing required / wrong type / invalid enum → `ToolArgsError` (`INVALID_ARGS`) goes down the normal error-result path

- **Output inference**: return type and pure rendering are inferred from `output.schema`

The lower-level `ctx.tools.register()` also works, but with the same fields (`parameters` + `output:{schema,render}` + `execute`), and you own validation yourself. **Prefer `defineTool`**.

The complete optional field set: `timeoutMs` (per-call budget, see Four), `isConcurrencySafe(args)` (parallel classification, see Nine), `finalizeContent(exec, result)` (the result-content boundary, see Three), `presentCall` / `presentResult` (tool-owned UI rendering, see Eleven), plus `presentationMeta(args, value)` nested under `output`.

## Two — Three presentation modes: mode / presentAs

A tool's `schema` stays the same, but **how it is presented to the model** has three forms:

```yaml
tools:

  mode: native   # native (default) | ptc | both
```

| mode | What the model sees | Notes |
| --- | --- | --- |
| native | function definitions | standard function calling |
| ptc | the reserved run_code transport + a generated tools:sdk section | lets the model call via "code + typed SDK" (see PTC mode) |
| both | both forms are provided |  |

- The config `mode` is the **default when an agent does not declare its own preference**; an individual agent shadows the default with `ctx.tools.presentAs(mode)` (call it in `agent.ctx`; ordinary contexts throw).

- `tools/execute` presentation is **decided by `core/agent-tool-presentation`** (`native`/`ptc`/`both`; see [Agent Presets](../../features/persona.md)).

- **Non-native modes require a `ctx.codeRuntime`** whose `language` has a registered SDK renderer (TypeScript goes through `dsh-code-runtime-worker-thread`; `python` is a known value but its backend is still experimental and unpublished).

### run_code is a reserved name

The `run_code` transport name is **unconditionally reserved regardless of the configured mode**: it cannot be registered/shadowed/restricted/removed, because any agent may switch itself to PTC mode. Want to register a tool named `run_code`? Not possible.

## Three — The execution pipeline (each invocation goes through five stages)

The source's own words:

The registry executes each invocation, passing it through `tools/pre-execute` (extensible allow/deny gate) → **monotonic guard** → `tools/execute` (around-dispatch wrappers: timeout/retry/metrics) → `tools/post-execute` (inspect/replace the result, attach context) → **the definition-owned `finalizeContent` boundary** → the observation-only `tools/result` notification.

Each stage is a plugin extension point:

| Stage | Type | What you can do |
| --- | --- | --- |
| tools/pre-execute | reorderable waterfall | allow / deny / ask (returns an allow, deny, or ask decision) |
| ctx.tools.guard() | synchronous guard | returning a reason rejects; monotonic: a later waterfall cannot flip a rejection back to allowed |
| tools/execute | around wrapper | add timeout/retry/metrics; can only replace signal, nothing else |
| tools/post-execute | waterfall | replace content / replace value / block / attach ordered contexts |
| finalizeContent | definition-owned | runs exactly once per normalized result (including failures that skipped post-policy); can only replace content, must be synchronous and total |
| tools/result | observation notification | only views the final result, cannot modify it |

Key point: `tools/result` is an **in-process live event**; the `tool/result` (singular) appended right after by agent-loop is the **persisted session event**. Don't mix them up (see [Event System](../../learn/core/event-system.md)).

## Four — The guard family: timeout-policy and repeat-tool-reminder

The `packages/guard` group is two **behavior-guard plugins** — watching for "no output" patterns in the agent loop and enforcing per-call budgets. They are self-contained consumers of the core services and extension points, not replaceable capabilities. Both are **mounted by default in the base bundle**.

| Package | Role | Attachment point |
| --- | --- | --- |
| dsh-tool-call-timeout-policy (plugin id stays timeout-policy) | lays out a per-call deadline per tool declaration, as a deployment policy | registers a tools/execute listener |
| dsh-repeat-tool-reminder | injects advisory reminders on repeated tool calls | listens to tool and agent events |

Don't confuse these with the `ctx.tools.guard()` synchronous guard in the pipeline (see Three above) — that is the registry's inline allow/deny mechanism; the two here are standalone behavior plugins in the `packages/guard` group.

### timeout-policy: turning timeoutMs into a cooperative deadline

`@deepseek-ai/dsh-tool-call-timeout-policy` is a **zero-config** `tools/execute` around listener: the budget comes from the tool's own declaration (`ToolDefinition.timeoutMs`, set by the tool plugin that owns the tool), so it only executes the deadline — it never sets the budget — and things like "misspelled tool name" simply cannot happen. It is the **reference implementation** of the `tools/execute` around wrapper.

For a tool that **declares `timeoutMs`**:

- Read the budget from the registry (`ctx.tools.get(exec.name)?.timeoutMs`), lay out a signal with `deadline(exec.signal, timeoutMs, 'TOOL_TIMEOUT')` — fusing the caller's own abort with this plugin's timer **into one** (`@deepseek-ai/dsh-timeout`).

- Swap this derived signal onto `exec` before handing it downstream for dispatch, then restore the caller's original signal afterwards (cordis's `next()` ignores arguments, so the wrapper **mutates the shared `exec` in place**; the restore is so that `tools/post-execute` sees the caller's signal).

- After dispatch, if `timeoutOf(d.signal, 'TOOL_TIMEOUT')` hits — i.e. **this plugin's own timer** fired — replace the result with the structured `TOOL_TIMEOUT`: `{ isError:true, error:{ message, info:{ name:'ToolTimeoutError', code:'TOOL_TIMEOUT' } }, content:'Error: tool call timed out after <ms>ms' }`.

**Tools that didn't declare a budget are delegated as-is (no deadline laid out)**.

**Cooperative, not a hard kill**: the derived signal is only a **notification**; the real power to terminate lies with the tool and whatever capability forwards its `exec.signal` (the `dsh-timeout` library itself owns no kill). So declaring `timeoutMs` is a **promise to cooperate with `exec.signal`** — a tool that ignores the signal won't stop on time, and only tools that forward the signal should declare it (`web_fetch`/`web_search` are the references). `TOOL_TIMEOUT` needs no extra session event to be reconstructable: it is already the final model-facing `tool/result`, and the loop has logged it.

About why the replacement checks the signal (`timeoutOf`) rather than the shape of the dispatch result: `tools/execute`'s underlying `next()` is the registry's "dispatch + normalize" thunk, so when a timeout signal first reaches a provider that throws an upstream abort error, dispatch turns it into an ordinary error result, and this wrapper then turns that ordinary result into `TOOL_TIMEOUT`.

### repeat-tool-reminder: advisory anti-repetition

`@deepseek-ai/dsh-repeat-tool-reminder` is an **advisory loop-breaker, not a model-facing tool**: it never enters the tool list and never vetoes or rewrites invocations — it does exactly one thing: watch each agent's tool-call stream, count the consecutive length of "call the same tool + byte-identical normalized arguments", and at configured consecutive lengths inject **escalating** reminders telling the model not to repeat, re-read the last result, and either change approach or wrap up. The decision (retry differently / gather more evidence / finish) is entirely the model's: legitimate repeated calls are neither delayed nor blocked.

```yaml
config:

  thresholds: [3, 5, 8]        # default; consecutive counts that trigger a reminder

  include: []                  # tool-name patterns to track; empty = all tools

  exclude: []                  # default empty; tool-name patterns transparent to the chain (e.g. [todo_write])

  argumentsPreviewChars: 500   # default; arg cap quoted in the detailed reminder
```

- **The chain's key is `(tool name, normalized arguments)`**: normalization = deep key-sort + `JSON.stringify`, so argument objects differing only in property order count as "the same". Same as the last tracked call → that agent's consecutive count +1; different → reset to 1.

- **Calls not tracked are transparent to the chain**: calls excluded by `include`/`exclude` neither increment nor reset, so `grep X → todo_write → grep X` still counts as two consecutive `grep X` when `todo_write` is excluded — the point of exclusion is exactly that a bookkeeping tool slipped into a loop cannot "launder" the loop.

- **Rejected calls count too**: detection attaches to `tools/post-execute`, and this event also runs for calls rejected by `tools/pre-execute` — a model hammering a rejected call is precisely the loop worth breaking.

- **Per-agent bookkeeping**: the registry is context-level and subagents interleave along the same waterfall, so a `WeakMap<Agent, Chain>` keys chains by the live agent object; one agent's repetition never triggers another's reminder. A user prompt (`agent/pre-step`) resets the submitting agent's chain.

- **In-memory only**: sessions restored from persistence start with an empty chain — it is a heuristic nudge, not a logged invariant.

**Reminder delivery**: reminders go through the post-execute decision's `additionalContexts` (source `{kind:'plugin', plugin:'repeat-tool-reminder', form:'notice', summary:'<tool> × <count>'}`), and **never** replace `content` — the `tool/result` event keeps the tool's own output for auditing. The loop buffers this context and appends it as an injected `user/message` after the step's tool results, rendered in the session as an ordinary synthetic user message. So a reminder is model-visible, provenance-annotated, and reconstructable from the session log, with no new session event.

The first threshold emits a short reminder; each subsequent threshold emits the detailed form (naming the tool, the consecutive count, the normalized arguments — head-truncated by `argumentsPreviewChars` with an ellipsis-count marker, so a loop's `write`/`edit` payloads never ride unbounded into the next request; the chain key always compares on the full normalized string, the cap constrains only the reminder, not detection).

| Effect | Notes |
| --- | --- |
| token | zero tokens before a threshold; each reminder preserves history, and argumentsPreviewChars constrains data-related text |
| KV cache | append-only; new visible content follows the reusable request prefix and does not invalidate existing entries |

## Five — Output contract and content/presentation separation

What a tool returns splits into two parts:

|  | content | value |
| --- | --- | --- |
| What it is | the UI/model-facing rendering | the canonical JSON value |
| Who can get it | the model context | programmatic consumers |
| Conversion | render(args, value) | returned by the executor |

A tool body can **only** return the one canonical JSON value declared by `output.schema`; the registry validates and freezes it, then materializes the presentation fields. Result shapes:

```ts
// success

{ isError: false, value: JsonValue, content, meta?, additionalContexts?, concludesTurn?: true }

// failure

{ isError: true, error: { message, info? }, content, meta?, additionalContexts? }   // no value
```

`ToolFailure.info` is optional and carries `HarnessError`'s internal `{ name, code }`. A tool can call `exec.concludeTurn()` to mark "this successful result is the current turn's end point" (`concludesTurn: true` appears only on success), and the loop stops after committing this result batch.

### additionalContexts: returning context to the loop during execution

`ToolRunContext.deferContext(context)` **defers** a piece of context until that tool's final result reaches agent-loop: even if the tool later throws or is cancelled, it is preserved and never injected immediately. `additionalContexts` keeps each deferred or post-execute-recognized `UserMessage` for the loop's post-result FIFO.

This is the channel from [Agent Main Loop](../../learn/core/agent-loop.md) by which "context is returned to the loop during execution".

## Six — Cancellation semantics: cooperative and quiet

Cancellation is **cooperative and quiescent**, not a hard kill:

- Each tool body receives the mandatory read-only `exec.signal` (an AbortSignal); **every asynchronous tool must observe or forward it, and settle only once its own owned work has stopped**

- Only the `tools/execute` wrapper layer can **temporarily replace** `signal`; the registry **re-fuses (merges) the caller's original signal before the body**, so a replacement never drops the caller's cancellation

- When cancellation happens decides the result:

cancelled **before the body's dispatch** → `ABORTED_BEFORE_DISPATCH`

- cancelled after the body's dispatch → can only replace a success result with `ABORTED`

- more specifically: denial / wrapper failure / tool failure / post-policy failure / timeout → `TOOL_TIMEOUT` stays more specific

- An **already pre-aborted** invocation: materialize and freeze the arguments, skip all policy/dispatch phases, publish a result

- **The registry has no hard-kill ability**: an in-process promise, once started, isn't let to race away

## Seven — The typed parameter schema (defineTool's DSL)

`defineTool`'s unified schema DSL supports:

```text
string / number / integer / boolean / null / array / object / json (author-only) / oneOf (exactly one)
```

- Explicit DSL objects all declare `additionalProperties: true|false`; the implicit parameter root and bare JSON Schema stay standard-open

- `enum`/`const` scalar types are correct

- **Defaults are not auto-applied** (types are right, but defaulting is up to you)

- Validation uses an explicit work stack, **bounded runtime memory on very deep schemas** (never blows the call stack); `InferValue` keeps exact types to 16 container levels, then falls back to `JsonValue`

- A bare `register`ed tool owns its input validation, but still declares and is subject to the registry's output validation

## Eight — Scope and visibility

A tool's visibility is decided by the **scope chain** (consistent with [Plugin Anatomy](../../learn/core/plugin-anatomy.md)'s scope):

| Registration location | Visibility |
| --- | --- |
| ordinary plugin context | global tool |
| agent.ctx | only that agent, shadows same-named global tools |
| restrict(filter) (agent.ctx only) | applies an allow/deny mask over inherited tools (global layer + ancestor scopes) |

Several key properties:

- `restrict` exempts the scope's **own registrations**, then merges: this is exactly the mechanism by which "when delegating to a subagent, its report/structured-output tools survive under a narrow filter"

- Multiple masks **intersect**; ancestor masks penetrate every nested scope

- a deny mask lets through unlisted inherited tools that appear after it; an allow mask excludes names that appear after it

- **This is live visibility composition, not a permission boundary** (scope security is explicitly a non-goal in the source; real restrictions are in [Sandbox](../../learn/core/sandbox-security.md))

Get the tools visible to a scope:

```ts
ctx.tools.get(name, scope)         // a single definition (both shadowing and restriction applied)

ctx.tools.schemas(scope)           // visible tools' schemas (no execute)
```

## Nine — Parallelism and exclusivity (execution mode)

agent-loop splits concurrent tool calls into two classes:

- **`exclusive`** (default): a queuing barrier, serial

- **`parallel`**: allowed into parallel only when `schema`'s `isConcurrencySafe(args)` returns **exactly `true`**; unknown/hidden/undeclared/invalid/throwing classifications all fall back to `exclusive`

```ts
ctx.tools.register(defineTool({

  // ...

  isConcurrencySafe(args) {

    // return true only if it's safe to run in parallel; an opt-in tool must not mutate parent-held state

    return args.kind === 'readOnly'

  },

}))
```

- agent-loop normalizes consecutive parallel calls into a **bounded rolling pool**; exclusive calls act as **sequential barriers**

- **Only dispatch/body overlap**; policy, persisted results, and result context keep model order

- `maxParallelToolCalls` (default 10) caps the pool

## Ten — PTC mode (advanced but powerful)

`ptc`/`both` modes let the model call tools with **program + a typed SDK** instead of one-by-one function calls. The SDK section (`tools:sdk`, order 5000) is **deterministically** regenerated on each assembly (lexicographic tool order, byte-identical → prefix-cache-friendly).

Key points:

- **`run_code` transport** + a deterministic SDK generated in the loaded runtime language

- **Only the program's outer logs and return value reach the model context**: sub-call detail doesn't pollute it

- **Bound calls** enter the full tool pipeline; concurrency-safe ones can overlap to `maxParallelSubCalls` (default 10; 1 = serial), with exclusive sub-calls as barriers

- Each bound call logs `tool/ptc-dispatch-start` at the pipeline entry, and a wave of `tool/ptc-dispatch` once settled (with full model-facing content/isError; named `tool/code-dispatch*` before the v2→v3 session-format migration)

- Rejection/failure → program-visible `ToolCallError(toolName, message)`; ordinary side effects are not rolled back; a run settling aborts and drains unfinished bound calls

- Run failure → `CodeRunFailedError` (`code:'CODE_RUN_FAILED'`), turned into a structured `isError` so the model can self-correct

- `run_code` returns `{ logs: string[], result?: JsonValue }`; the worker's `maxOutputBytes` defaults to 64 MiB; **image-bearing subtool results are attached after the run** (rc.7)

PTC mode folds "one complex operation" into a single program: the model writes code and calls tools bound one-by-one, instead of frequent back-and-forth function calls. This is DSH's bias toward "programmatic calls". Want to try it: `pnpm run demo:ptc`.

### The PTC runtime: the code-runtime service contract + the worker backend

The `packages/code-runtime` group is the capability seam for code execution, split into two layers:

| Package | Role | ctx key |
| --- | --- | --- |
| dsh-code-runtime | service definition + shared vocabulary, says "what to do" not "how" | ctx.codeRuntime |
| dsh-code-runtime-worker-thread | worker-thread backend, registers the service | (registers ctx.codeRuntime) |

The backend is mounted by default in both the headless and web mode bundles (id `code-runtime`); the base bundle itself does not mount it.

**The service contract (`ctx.codeRuntime`)** defines exactly three things:

| Member | Semantics |
| --- | --- |
| run(request) | executes a program against the request's bindings; every program result resolves with an error field — parse/transform failure, thrown exception, invalid completion, output over-limit, budget exhausted, abort, underlying death (CodeRunFailure's orthogonal kind taxonomy); only a caller violating the service contract (e.g. submitting after dispose) rejects. The program runs as an async function body: top-level await/return work, and lossless-JSON completion becomes result.value. |
| language | read-only description: the source language run expects. 'typescript' and 'python' are the known values (only 'typescript' has a released backend). Informational, not gating. |
| isolation | read-only description: the execution substrate ('worker-thread' / 'process' / 'container'). A label for deployment/diagnostics, not a security claim. |

Every implementation must honor: bound-call bridges use **lossless-JSON** arguments and results with **no byte cap at the seam layer**; the program is treated as a **hostile peer** (arbitrary binding names are own properties, malformed traffic never crashes the host); **no state survives between two runs**; dispose terminates in-flight runs **and waits for them to exit**.

**The worker backend (`WorkerThreadCodeRuntime`)** runs each program in a spanking-new `node:worker_threads.Worker`: TypeScript in, host-side type stripping, bindings bridged over the message port, `{ value, logs, error? }` out.

- **One fresh worker at a time, no pooling**: the program's world dies with the worker — no cross-run state to record, state leakage is inexpressible, and a run is reconstructable from the session log alone.

- **Host-side type stripping**: the program is wrapped in an async function shell, stripped with `node:module`'s `stripTypeScriptTypes` (erasable syntax only — `enum`/namespace are immediately judged a program `exception`, no worker is spawned), then spliced back by byte position and executed as an `AsyncFunction` body, so top-level `await`/`return` work.

- **The port assumes a hostile peer**: model code can grab `parentPort` and forge traffic, so each inbound message is **shape-checked before reconstruction** (null/primitives/garbage types/malformed payloads dropped, forged extra fields carried away with nothing), the host answers each call id at most once, binding names resolve only by own property (a forged `constructor`can't walk the prototype chain), replies after settling are discarded, and every binding parse and completion is lossless-JSON validated.

- **Two independent budgets (because the peer is hostile)**: `computeMs` charges the worker's **measured busytime** (polling `worker.performance.eventLoopUtilization()` — a hot loop can't hide inside a suspended decoy dispatch, and waiting on a slow tool doesn't bill); `maxWallMs` backstops the case busytime can't see (waiting on a promise nobody resolves). Both funnel into `worker.terminate()` (which can stop a hot synchronous loop); heap overflows surface as the worker's OOM exit.

- **Logs stream immediately into an outer ledger**: console/stdout/stderr text crosses the port in emission order, so a timed-out or killed program still sees what it printed. `maxOutputBytes` counts JSON-serialization bytes, and completion values and exception diagnostics are **pre-checked against the remaining budget** before being posted — a thrown million-byte stack becomes a fixed `output-limit` diagnostic at the worker boundary.

- **Empty environment**: the worker gets `env:{}` + `execArgv:[]` — no environment credentials, no inherited loader flags.

- **Dispose to silence**: teardown marks in-flight runs as `abort` and **waits for each worker to exit** before resolving.

| Config | Default | Meaning |
| --- | --- | --- |
| computeMs | 60000 | busy-time budget (measures event-loop active time) |
| maxWallMs | 600000 | wall-clock cap, never paused for anything |
| maxOutputBytes | 67108864 | serialized outer-output total cap (64 MiB) |
| maxOldGenerationSizeMb | 512 | worker heap cap (resourceLimits) |

**Containment, not a security boundary**: the worker backend is deliberately designed with the trust posture of "equivalent to bash" — it confers only what bash doesn't have (separate isolate, empty environment, heap cap, hard termination). Only the outer `run_code` result enters the model context and follows ordinary spill policy; bound traffic and intermediate values stay local to the execution.

## Eleven — A tool's own UI rendering (presentCall/presentResult)

A tool can return **pure render intent**, so the UI doesn't need a per-tool-name special case. Two cards:

```text
presentCall()    decides how the UI renders "the model is about to call this tool"

presentResult()  decides how the UI renders "this tool's result"
```

Card vocabulary has two groups: `presentCall` offers only `generic` / `terminal` / `diff`; `presentResult` additionally offers `search` (grep/glob completion-discovery search, with truncated/total) / `read` (file read with line numbers + optional highlighting) / `web` (search/fetch). Returning `undefined` = use the generic fallback.

- A renderer depends only on its **arguments + the persisted result** (the UI calls it for both the live stream and log replay)

- `output.presentationMeta(args, value)` derives JSON metadata, persisted with `tool/result`, and fed back into `presentResult` on replay

- `dsh-tool-bash` / `dsh-tool-fs` are reference implementations

**Meaning**: it makes "file reads show as code views, web searches show as source grids, diffs show as diffs" the tool's responsibility rather than each UI hardcoding tool names.

## Twelve — MCP tools join the same system

`dsh-mcp-client` (see [MCP Integration](../../features/mcp.md)) registers external MCP servers' tools into `ctx.tools` as `mcp__<server>__<raw>`. Names are **lossily normalized**: characters outside `[A-Za-z0-9_-]` become `_`, names longer than 64 characters are truncated, and both cases append a 12-hex-digit SHA-256 suffix; the raw name is wire-only and never parsed back. They **go through the same pipeline**: pre-execute gating, timeout, cancellation, and rendering all apply. Rules: one server per plugin; after `discover`ing the tools, `call ctx.tools.register()`.

## Verification

```sh
# See which tools the current profile has registered

dsh web --dump-config | grep -A2 "tool-"

# Inspect one tool invocation's pipeline in the session log (singular tool/ prefix, zstd-compressed by default, two-level directory; current format version v3)

zstdcat ~/.dsh/sessions/*/*/session.v3.jsonl.zstd | grep -E '"tool/call"|"tool/result"' | tail -6
```

## Next steps

- [Context](../../learn/core/context.md): how tool schemas enter system-prompt assembly

- [Sandbox & Security](../../learn/core/sandbox-security.md): the execution boundary behind tools

- [Write a Tool](../../learn/dev/write-tool.md): write one by hand

- [Built-in Tools](../../features/tools.md): what the 25 shipped tools can do
