# Subagents and Parallelism

## Contents

- [Child model selection (source build)](#child-model-selection-source-build)
- [Two kinds of subagent](#two-kinds-of-subagent)
- [One-shot delegation](#one-shot-delegation)
- [Continuable sub-sessions (continuable)](#continuable-sub-sessions-continuable)
- [The provider family](#the-provider-family)
- [When to use it](#when-to-use-it)
- [Verification](#verification)
- [Next steps](#next-steps)

---

## Child model selection (source build)

`tool-subagent` adds configured `agentOptions: { provider, model, reasoningEffort, maxTokens }` defaults. Backends must advertise `agentOptions` support; in-process spawn/fork and DSH SDK do. Claude Code / Codex backends accept their own configured model, but not the autonomous route-selection feature below.

The Web Plugins setting `subagent-model-selection` stores an explicit provider/model allowlist. With `modelSelectionSettings: true`, delegation samples it when a **new top-level Session** is composed and records it in the log. Children inherit the snapshot; later settings changes do not rewrite old Sessions. Enabled tools add `list_subagent_models` and optional `provider`, `model`, `reasoning_effort` arguments. Provider/model must be supplied together; route authorization and adapter capability are checked before creating the child. ACP, Claude Code, and Codex backends do not accept this switch.

Source: `packages/subagent/tool-subagent/src/{index,model-selection,model-selection-settings,list-models}.ts`.

An Agent can **delegate tasks to subagents**. DSH's `ctx.subagents` is a capability seam: the caller uses a single `ctx.subagents` API, and the **specific provider** decides whether a subagent runs in this process, another process, or through a future transport. This is the mechanism for "processing complex tasks in parallel": splitting a multi-step task across several isolated subagents that advance concurrently.

## Two kinds of subagent

DSH distinguishes two shapes with different responsibilities:

| Shape | Description | Key APIs |
| --- | --- | --- |
| one-shot | spawn a subagent to do work and get a final result | ctx.subagents.start(name, request) |
| continuable | build a persistent sub-session that can receive multiple messages, be interrupted, and cold-resume | startContinuable(spec) / followup / interrupt |

The model-facing side is `tool-subagent` (one-shot, `ctx.subagents.start`) and `tool-subagent-control` (`send_message` / `interrupt_agent` / `list_agents`), the latter being the control surface for the "continuable sub-sessions" covered in this page.

## One-shot delegation

```ts
// the request can: pick a model, ask for structured output, limit delegation depth, limit subagent tools, set a sub-persona

const run = await ctx.subagents.start('spawn', {

  prompt: 'Help me analyze the TODOs in this repo',

  outputSchema,          // optional: strongly constrains the final result structure

  depthLimit,            // optional: caps delegation depth

  toolFilter,            // optional: limits which tools the subagent sees

  signal,                // required: the cancellation channel before publication

})

const result = await run.result   // the one-shot subagent's final result
```

- `label` is an optional persistent display label

- `signal` is the **canonical cancellation channel** for a one-shot `start`: abort before publication → rejection rolled back; abort after publication → cancels remaining rounds but does not hide the returned `run`

- A provider advertises support through `provider.capabilities` (**outputSchema** / **depthLimit** / **toolFilter** / **agentOptions**), rejecting before creating a sub-session if unsupported

## Continuable sub-sessions (continuable)

```ts
const { childId, messageId } = await ctx.subagents.startContinuable({

  label: 'research-assistant',

  initialPrompt: 'This is a resident research assistant; reach me anytime',

})

// send a later message (only released after exact direct-parent authentication)

await ctx.subagents.followup(parent, childId, 'Check the latest MCP progress again')

// interrupt a continuable subagent's current round (keeps its inbox and descendants)

await ctx.subagents.interrupt(targetSessionId, authority)

// list direct session-level subagents / flatten the whole session tree

await ctx.subagents.listChildren(parentSessionId)

await ctx.subagents.listDescendants(rootSessionId)
```

Key properties (source README essentials):

- **follow-up authority** comes from the "exact direct parent" recorded in the subagent's persistent header: a parent deregistered/replaced during reassembly cannot authorize delivery

- **continuable sub-sessions require** `ctx.agents` + session persistence + a provider with a `prepareContinuable` capability

- Cold resume: when the parent agent is absent, rebuilds from the persisted Session (also requires session persistence)

- `reportFrom` delivers one of the subagent's messages back to its direct parent (quiet = injected into context; waking = triggers a new round for the parent)

## The provider family

Under `packages/subagent/` the same seam has multiple implementations. `subagent-in-process-driver` is the **shared run driver for the spawn / fork two in-process providers** (not a separately registered provider name), while the other six are providers that `getProvider(name)` can retrieve:

| provider | Where the subagent runs | Mount |
| --- | --- | --- |
| spawn | a brand-new Agent in the current process | mounted by default (base) |
| fork | current process, seeded with the parent's completed rounds | mounted by default (base) |
| acp | a fresh subprocess, via Agent Client Protocol | opt-in |
| claude-code | a fresh subprocess bridging the Claude Code CLI | provider mounted by default, delegation tool disabled by default |
| codex | a fresh subprocess bridging the Codex CLI | provider mounted by default, delegation tool disabled by default |
| dsh-sdk | a fresh subprocess with a full DSH runtime (JSON-RPC) | opt-in |

Multiple providers can **coexist** behind a single `ctx.subagents`; `getProvider(name)` fetches by name.

### in-process-driver: the shared run driver

`subagent-in-process-driver` is the **single implementation** for the spawn / fork two in-process providers — spawn passes no session seed, fork passes the parent's completed-round prefix, and everything else (depth validation, subagent creation, persona/tool-filter/structured-output installation, result reading, cancellation, dispose) lives in this one implementation:

- `startInProcessRun` only fulfills once the subagent is published on `ctx.agents`; when startup is rejected, the unpublished creation transaction has already quiesced, so the caller never gets a half-created handle

- **depth** reads the parent's `delegationDepth` (persistent header authoritative, runtime can only deepen, never lower), child depth = parent + 1 written into the child's header, so persistence + resume both preserve the budget; exceeding `maxDepth` reports a precise error

- **structured output** installs a whole contract: a `structured_output` tool + an order-190 system prompt section + an observer that only commits after that execution's final tool result succeeds + a single-call guard + `concludeTurn` wrapping up

- The same driver also installs a persona shadow and tool filtering for the subagent (removes global wire schemas / executable lookup / PTC mode SDK bindings, but keeps independently registered guidance sections), and applies the seam's delegation policy (parent's explicit sandbox override + `never` approval pin)

### spawn: same-process new Agent

`spawn` creates a brand-new subagent in the **current process**: it has its own session, can't see the parent's conversation history, and reuses the host's agent factory and LLM/tool services. It advertises `{ outputSchema, depthLimit, toolFilter, persona, agentOptions }` all true, because it can forcefully impose these capabilities within the subagent's creation window. The subagent inherits the parent's working directory/session lineage and model (unless overridden), but starts from an empty conversation.

### fork: same process + the parent's completed rounds

`fork` shares every run mechanism with spawn; the **only difference is the session seed**: it feeds the subagent the **contiguous prefix of the parent session before its last `turn/end`** — the parent's current in-flight round is excluded (otherwise the child would get an unbalanced session). It passes only the conversation history, inheriting neither the parent's tool limits nor authority. Capabilities advertised match spawn. Because a continuable child additionally carries a `report` tool and prompt section that would break the parent prefix cache fork wants to reuse, the delivery composition binds fork to `backgroundMode: one-shot`.

### acp: an ACP client in a subprocess

`acp` runs each subagent in a **fresh subprocess**, driven as an Agent Client Protocol client: it fulfills only after spawn → ACP `initialize` → `newSession` all succeed, meaning the remote session is ready and ownership is handed to the caller. It **advertises no start-time capabilities** (can't forcefully impose depth / toolFilter / persona / structured output in a remote process), `inheritsParentContext: false`, and the only thing carried over from the parent side is the working directory. `permission: reject|allow` auto-answers the sub-session's permission requests (no pop-up to a human). One fresh process per run, no process pool.

### claude-code / codex: bridging two CLIs

These two are **fixed providers**:

- `claude-code` calls the official Claude Agent SDK's `query()`, resolving the native `claude` executable in the parent-session workspace, submitting a self-contained text task, and returning only the strict final answer. The SDK reads the host's native Claude settings and auth, with `persistSession: false` and `AskUserQuestion` disabled (unattended).

- `codex` starts the official `codex app-server --stdio`, creates an ephemeral thread, and likewise returns only the final answer. Under unattended operation, command/file approvals pick cancel/decline, and permission requests get the empty set. `contextWindowExceeded` maps to `max-tokens`; other exceptions map to `error`.

Neither advertises optional capabilities, `inheritsParentContext: false`; the child's model/tools/permissions/auth all come from the original product install. **The provider rows mount by default on base's host plane (loaded but starting no product process), while the corresponding delegation tool rows are `disabled: true` in the standard preset** — copy the preset and remove `disabled` to expose `subagent_claude_code` / `subagent_codex` to agents composed from that copy.

### dsh-sdk: a full harness runtime in a subprocess

`dsh-sdk` runs each subagent as a **complete DeepSeek Harness runtime** in a fresh subprocess, communicating over stdio JSON-RPC through a TypeScript SDK client. The difference from `acp` is in the wire and child contract: the subprocess is a **full peer harness** — its own profile/patch composition, session persistence, model routing, and tools. It advertises `agentOptions` support, but not the other optional capabilities; `inheritsParentContext` is false; its delegation tool sets `maxDepth: provider-managed` (the child harness holds its own recursion budget). A full runtime starts the whole plugin tree per run, so a single spawn costs more than acp's typical subprocess.

## When to use it

- **Parallelism**: split an independent subtask (fetch + summarize + write a file) across three subagents running at once

- **Isolation**: a subagent has its own scope and tool limits and won't pollute the parent session

- **Continuable conversations**: resident assistants needing state held across multiple rounds (use continuable)

- Get a one-time result (use one-shot `start`)

## Verification

```sh
# see the available subagent providers in the composition tree

dsh web --dump-config | grep -iE "subagent"

# see subagent events in the session log

zstdcat ~/.dsh/sessions/*/*/session*.jsonl.zstd | grep -E "subagent/" | head
```

## Next steps

- [Workflow and Ralph](../features/workflow.md): orchestrating multiple agents in parallel with scripts

- [Writing a tool](../learn/dev/write-tool.md): sharing logic across subagents
