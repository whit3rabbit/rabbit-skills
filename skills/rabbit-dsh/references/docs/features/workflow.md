# Workflow and Ralph

DSH makes "multiple Agents collaborating" into two model-usable tools:

| Tool | Purpose |
| --- | --- |
| workflow | runs a JS orchestration script, fans out multiple subagents, returns the script's final value |
| ralph | for one immutable goal, starts an entirely fresh Agent each round to iterate |

The difference is a **mental model**: workflow is "you write a script, the script orchestrates a batch of agents"; Ralph is "the goal stays fixed, each round swaps in a brand-new agent to keep pushing forward."

## Contents

- [The workflow tool](#the-workflow-tool)
- [A minimal script](#a-minimal-script)
- [Lifecycle and errors](#lifecycle-and-errors)
- [The Ralph loop](#the-ralph-loop)
- [When to use which](#when-to-use-which)
- [Verification](#verification)
- [Next steps](#next-steps)

---

## The workflow tool

`@deepseek-ai/dsh-tool-workflow` runs a model-written JS orchestration script (fan out subagents); essentially the host hands the script to the `ctx.workflowEngine` seam, and the engine (`dsh-workflow-worker-thread`) decides how to isolate and execute it.

The three parameters the model sees:

```text
meta    required identity data: { name, description, phases? }

script  required pure-JS function body (top-level await; don't export const meta)

args    optional JSON, exposed to the script as the args global
```

The orchestration hooks available in the script (`agent`/`pipeline`/`parallel`/`phase`/`log`) all return JSON-serializable values. Rules:

- **Use only on explicit request**: use it only when the user explicitly asks for "workflow / large-scale multi-Agent orchestration"

- For one or two delegations, prefer ordinary subagent calls; don't reach for workflow

- `WorkflowStartRequest` = `{ meta, script, args, subagentProvider?, maxTotalAgents?, parent, signal? }`

- A `WorkflowResult` = `{ value, stopReason, error?, agentsStarted }`; `value` is pure JSON or `null`

- A run is holder-owned and must be `dispose()`d; the engine plugin unmounting only blocks new starts, it doesn't revoke already-accepted runs

## A minimal script

```js
// this is the tool's script parameter (Plain JS, top-level await)

async function main(args) {

  const items = await parallel([

    () => agent('Scrape site A', {label:'A'}),

    () => agent('Scrape site B', {label:'B'}),

    () => agent('Scrape site C', {label:'C'}),

  ])

  return items.filter(Boolean)

}
```

The script itself can be a top-level script body containing `return main(args)`. At runtime `agent()` returns the subagent's final text (or an object validated against `opts.schema`); a failed/errored subagent returns `null` (`.filter(Boolean)` drops the empties).

## Lifecycle and errors

- `start()` may be rejected synchronously for malformed meta / an unparseable script / an unavailable provider / an over-limit request: **before a run exists**

- `WorkflowRun.result` **never re-throws a rejection**: an execution failure resolves to `stopReason:'error'`, and a cancellation resolves to `cancelled` (within the engine's bounded grace window)

- `exec.signal` bridges to `run.cancel()` (including cases already aborted beforehand)

- any non-`completed` stop reason maps to `isError` (never falsely lumped in as success)

- a root transport (e.g. `exec.parent` missing) projects the run onto the calling agent's Session

## The Ralph loop

`@deepseek-ai/dsh-tool-ralph` is a model-facing **fresh-agent iterative loop**, built on the workflow + subagent seams: for one **immutable objective**, each round opens a brand-new subagent that **inherits no parent conversation context**, sharing the workspace as long-term memory, with only a bounded structured report crossing rounds. It suits long tasks with a stable goal that need iterative try-and-error progress.

Usage is basically "run a few rounds on a single goal, with each round a new agent pushing independently." It hands "what the next round learns from the previous one" to the **workspace + the structured report**, not the conversation context.

## When to use which

| Scenario | Use |
| --- | --- |
| a one-shot parallel split (scrape multiple sources, audit multiple files) | workflow |
| the user explicitly wants multi-agent orchestration / large fan-out | workflow |
| one stable goal, repeatedly swapping in fresh agents to push forward | ralph |
| one or two independent subtasks | ordinary subagent (don't reach for workflow) |

## Verification

```sh
# see workflow records in the session (run-start/members/run-end)

zstdcat ~/.dsh/sessions/*/*/session*.jsonl.zstd | grep -E 'workflow|"run/' | head
```

## Next steps

- [Subagents and parallelism](../features/subagent.md): what a workflow fans out

- [Built-in tools](../features/tools.md): where tool-workflow / tool-ralph sit in the tool list
