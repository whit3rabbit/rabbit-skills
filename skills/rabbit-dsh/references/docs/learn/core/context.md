# The Context System

- 
- Concepts Course
- Core Mechanisms
- The Context System
On this page

# The Context System

Audit baseline 0.1.5-alpha.1 @ 5dda764ed3.

**In one sentence**: what the model sees = the object returned by `agent-loop` assembling **system prompt + tool schemas + derived session history** into a controlled context just before a request; when overlong, it goes through **compaction** rather than truncation. The `context/` packages only provide additional context-injection sources; they are not the assembly layer.

This is the second core lesson after [Agent Main Loop](../../learn/core/agent-loop.md). It is what lets you understand "what exactly is sent in each model request, and why it is sometimes slow / spends tokens".

## Contents

- [One — Who assembles the context (correcting a common misconception)](#one-who-assembles-the-context-correcting-a-common-misconception)
- [Two — System prompt: the ctx.systemPrompt registry](#two-system-prompt-the-ctxsystemprompt-registry)
- [Three — Tool schemas into the assembly](#three-tool-schemas-into-the-assembly)
- [Four — Request header: the "business card" of a request](#four-request-header-the-business-card-of-a-request)
- [Five — Context injection sources: context/*](#five-context-injection-sources-context)
- [Six — Token metering (token-meter): the basis for the compaction decision](#six-token-metering-token-meter-the-basis-for-the-compaction-decision)
- [Seven — Context compaction (compact): don't truncate, fold](#seven-context-compaction-compact-dont-truncate-fold)
- [Eight — Three perspectives: model / token / KV cache](#eight-three-perspectives-model-token-kv-cache)
- [Nine — Source evidence (event layer)](#nine-source-evidence-event-layer)
- [Ten — Verification](#ten-verification)
- [Next steps](#next-steps)

---

## One — Who assembles the context (correcting a common misconception)

Many believe "the context is assembled by the `context` package": **not true**. The real division of labor:

| Layer | Responsibility | Owner |
| --- | --- | --- |
| Assembly subject | Each step assembles system prompt + tool schemas + derived messages into a request | agent-loop (private buildRequest + agent/request assembly waterfall); the assembly context is built by dsh-agent's assembleContextFor(agent, signal) |
| System-prompt registration | Plugins contribute ordered prompt sections, tool schemas, and named variables, and render them | core/system-prompt (ctx.systemPrompt) |
| Tool-list presentation | Decides whether to present tools to the model as native/ptc/both | core/tools + core/agent-tool-presentation |
| Session history | Event-sourced log → surface-message projection | core/session |
| Extra injection sources | Inject additional model-visible context into the request (do not define tools) | context/* |
| Compaction | Collapses history when over a limit | compaction/* |

Remember in one sentence: **assembly is agent-loop's job; `context/*` is merely "optional extra words fed to the model", and `system-prompt` is the registration registry for prompt sections**.

## Two — System prompt: the ctx.systemPrompt registry

`@deepseek-ai/dsh-system-prompt` is the **system-prompt assembly registry**. Plugins contribute ordered sections, tool schemas, and named variables; agent-loop assembles once per step and renders them into the full model prompt.

### The 6 core entry points

| Entry | Purpose |
| --- | --- |
| ctx.systemPrompt.section({ name, order, text, complete? }) | Contributes a prompt section, sorted ascending by order |
| ctx.systemPrompt.context({ name, order, text }) | Contributes ordered dynamic context, evaluated per eligible assembly into a sourced user-role snapshot |
| ctx.systemPrompt.suppressRuntimeContext() | Suppresses all dynamic context for the current scope; disposal restores it |
| ctx.systemPrompt.tools(provider) | Contributes tool schemas (evaluated with the current context on each assembly) |
| ctx.systemPrompt.variable(name, provider) | Contributes a prompt variable, referenced in section text with {{name}} |
| ctx.systemPrompt.assemble(context?) | Runs a full assembly (global layer + scope layer, through a waterfall) |

### order: how sections are placed

Sections are concatenated in **ascending** `order`. The order conventions in the source:

```text
-1000   harness identity (fixed "You are an AI agent powered by DeepSeek Harness.")

    0   deployment persona prefix (deployment:persona-prefix)

  500   plan-policy section / 600 team-policy section / 800 ptc-only collapse section

1000–2900 tool guidance (tool:bash / tool:read …)

 5000   tools:sdk (code-mode SDK section)

 9900   structured output

10200   deployment persona suffix (deployment:persona-suffix)
```

- `includeHarnessIdentity: true` (default) injects the fixed `You are an AI agent powered by DeepSeek Harness.`

- `includeRuntimeContext: true` (default) evaluates dynamic context providers; false drops provider and waterfall-added contexts while sandbox, approval, delegation, and other owning services remain active

- **The deployment persona is two config sections**: `personaPrefix` (order 0) and `personaSuffix` (order 10200); an agent-scoped `deployment:persona-prefix` / `deployment:persona-suffix` section can **shadow** the matching slot

- A section with `complete: true` becomes "the only prompt section" after the assembly waterfall; more than one effective `complete` at the same layer → assembly fails

### Scope layering

Like tools, `systemPrompt` is layered by the **scope of the calling context**:

- Sections/variables/tools registered inside `agent.ctx` → effective only for that agent, and **shadow** same-named global items

- Global registration → visible to everyone

This is what makes "give a specific agent its own persona/toolset" possible (see [Agent Presets & Persona](../../features/persona.md)).

### Variable rendering: strict, not stretchy

`renderPrompt(assembly)` performs strict `{{variable}}` interpolation, then **drops empty sections and joins with blank lines**. Fail-loud:

- References to unregistered variables, references registered but without a value, and broken `{{…}}` groups → **throw** (better to fail than to send a malformed prompt)

- An orphan `{{` (with no following `}}`) passes through as-is

- Replaced values are **not rescanned**

Strictness is for stability: **byte-for-byte identical system prompts are the prerequisite for KV-cache reuse** (see below).

Assembly goes through the `system-prompt/assemble` **waterfall**: listeners can cooperatively modify or replace the assembly (filtered by scope), after which the `complete`-section constraint and runtime-context suppressor are applied. Dynamic contexts are separate from system-prompt sections and become sourced user-role snapshots only when present.

Want to give an agent a dynamic fact like "today's date"? Register a `variable` provider and reference `{{date}}` from any section: much cleaner than hardcoding it into a persona. The agent loop already registers the three variables `provider`, `model`, `cwd`.

## Three — Tool schemas into the assembly

Tool schemas are **part of the assembly**: the README's own words are "what the model is told it can do is one coherent thing": even though the adapter transmits the schema online as a standalone wire field, at the assembly level it is one whole with the prompt.

- `ToolRuntime` **automatically** registers itself as a tool provider, handing the visible tool schemas into `systemPrompt`

- The `toolOrder` config can explicitly order how tools are presented (list `name`s, use `'<unlisted-tools>'` to placeholder the rest); misconfiguration fails loud

- The presentation mode (native / ptc / both) is decided by `ctx.tools.presentAs` + `core/agent-tool-presentation`; see [Tool Execution](../../learn/core/tools-execution.md)

## Four — Request header: the "business card" of a request

Every model request carries a request header recording that request's **call config and tool list**:

```text
{ config: { provider, model, reasoningEffort, maxTokens },

  adapterDefaults?: { reasoningEffort?: true, maxTokens?: true },

  tools?: <the tool list presented to the model> }
```

**The system prompt is not in the header**: it is part of derived history, recorded in the session log as a `system/message` surface event (node 0).

`request/header` has several semantics worth understanding:

- **`reason`**: `initial` / `resume` / `change` / `series`. `change` is appended only when the canonical header differs (equality = `config` + `adapterDefaults` + `tools`; the prompt does not participate); `series` means the header is unchanged but an explicitly new message series begins or a surface replacement just happened: this is the switch that **does not invalidate the prefix cache**

- The compaction summary call reuses the session's current request header (aligning the KV cache); but "auxiliary calls (subagents, etc.) reuse the same header" has **no source basis**: subagents have their own header

- Paired **`request/context`** event, carrying provider/model/contextWindow and whether the route supports `systemPromptUpdate: 'in-history'`

- `request/header` is recorded in the session log: you can always look in the JSONL to see which model a given message actually used; to see how the system prompt was assembled, read the adjacent `system/message`

This is where the "adapter-default marking" from [Agent Main Loop](../../learn/core/agent-loop.md) lands: `adapterDefaults` records which fields the adapter materialized, and the next waterfall removes them so the current route re-materializes defaults, keeping HMR from cross-contaminating.

## Five — Context injection sources: context/*

The `context/` group's product plugins add **extra model-visible context** to requests, but do not define tools:

| Package | ctx key | Role |
| --- | --- | --- |
| session-reference | ctx.sessionReferenceResolver | Bounded snapshots of other sessions |
| file-reference / file-reference-local | ctx.fileReferences | File references (definition + local search backend) |
| time-context | none | Current time / elapsed time (opt-in) |
| tmux-context | none | tmux location context (opt-in) |
| agent-instructions | none | Workspace-instruction context |

`agent-instructions` is mounted by the base bundle; `session-reference` and `file-reference-local` are mounted by web-app; `time-context` / `tmux-context` are opt-in. All of them inject model-visible messages at `agent/pre-step` and do **not participate in the system prompt's order-based assembly**.

## Six — Token metering (token-meter): the basis for the compaction decision

How does `compact` know "when to compact, and how much"? Through the `ctx.tokenMeter` service mounted by `@deepseek-ai/dsh-token-meter` (mounted by default in the base bundle). It is a **replay-aware** metering singleton: each measurement is based on the latest consumed-log revision of the persisted log, so compaction and other pressure-sensitive plugins share the same ledger without depending on `CompactionEngine`.

### Estimation is a "fixed heuristic", not an exact tokenizer

The meter has **no configuration items**, deliberately using only a single fixed heuristic: **≈1 token per 4 characters**, plus structural overhead for role / block / request-envelope fields. Any config key is rejected — model capacity belongs to the adapter that owns the precise provider/model route, obtained via `ctx.llm.resolveModelInfo().context`.

### Two entry points

| Operation | Returns | Notes |
| --- | --- | --- |
| ctx.tokenMeter.measure(session, requestHeader?) | { totalTokens, surfaceTokens, nodes[], … } | Synchronizes once at one consumed revision, returns a deeply immutable detached snapshot |
| ctx.tokenMeter.estimateMessage(message) | Estimate for a single message | Prices one message with the same fixed heuristic |

- `totalTokens` = the **pressure** of request + response; `surfaceTokens` = the heuristic total counting only the surface, exactly equal to the sum of `nodes[].tokens`.

- A `requestHeader` override affects only the pressure fields; the surface fields still describe the current session.

- Each call clones the located nodes, so measurement complexity is O(surface).

### The reuse rule for provider usage

Provider-reported real usage can be reused only when the **canonical request envelope (provider / model / tools / prefix / call config) of the latest successful call is byte-for-byte identical to the current measurement's envelope**, and its total is not below the full heuristic anchor of that call; later successful calls supersede earlier anchors. Otherwise it falls back to a full heuristic estimate over "the whole envelope + surface". Surface changes (including the shrink-replacements after compaction) are accumulated **with sign** relative to the anchor, so negative deltas also count correctly.

### Session projections: three quantities for the UI

When the composition layer provides `ctx.sessionProjections`, the meter registers three units through an optional child fiber:

| Projection | Contents |
| --- | --- |
| tokenUsage | uncachedInputTokens / outputTokens / cacheReadTokens / cacheWriteTokens of the full persisted log (the four buckets — input/cache-read/cache-write/output — are disjoint; reasoning is no longer double-counted) |
| contextPressure | optional pressureTokens (latest provider-reported prompt size), optional projectedTokens, optional contextWindow (route capacity from the latest request/context) |
| contextBreakdown | heuristic systemTokens / toolsTokens / messageTokens — the composition of the context, not the provider-billed size |

The key is `projectedTokens`: how many tokens **the next** request's prompt will cost = the provider-sampled baseline + heuristic re-pricing of surface deltas since the sample (clamped at 0). Only deltas are estimated, so it is both anchored to the provider and reactive the moment content lands (or is compacted into shadow). That is exactly why it exists: the compaction summary calls `ctx.llm.stream()` directly and **does not itself report any usage**, so `pressureTokens` still reports the pre-compaction prompt right after compaction, until the next full turn completes — the occupancy display reads `projectedTokens`.

**The approximation is deliberate.** The occupancy fields are independent last-wins records, not an atomic observation of a single request; switching models pairs the new capacity with the previous route's stale sample. The occupancy percentage is a human-facing reference, not a billing record nor a gate input — nothing in the harness uses it for decisions; compaction reads `measure()`. CJK text and JSON schemas are severely underestimated under "4 chars / token", so the three parts of `contextBreakdown` never add up to `projectedTokens`.

## Seven — Context compaction (compact): don't truncate, fold

Long sessions aren't handled by "chopping off the beginning", but by **folding**:

```text
folding = "shadowing" a section of history

  → replace the model-visible surface with a summary/report

  → the full log still stays in the persistence layer (event sourcing: the log is the only source of truth)

  → what the model sees is the surface after a surfaceOp: replace
```

Mechanism highlights:

- **`CompactionEngine` three entry points**: `compactIfNeeded` / `compactNow` / `compactRegion`

- Event sequence: `compaction/start` → `compaction/summary` → `compaction/end`; a model-free prune additionally logs `compaction/prune`; the seed/orphan boundary is marked by `session/end-seed` (not a `compaction/*` event)

- **Surface constraint**: `surfaceOp` (`append`/`replace`) is only legal on `system/message`, `user/message`, `assistant/message`, `tool/result`; the compaction events themselves are **log-only and never enter the surface**

- Compaction pressure is attached to **`agent/pre-step`**; the canonical overflow repair is attached to **`agent/request-error`** (see [Event System](../../learn/core/event-system.md) and [Agent Main Loop](../../learn/core/agent-loop.md))

### Result pruning (compaction-tool-result-pruner): cut the feed before summarizing

`@deepseek-ai/dsh-compaction-tool-result-pruner` provides `ctx.toolResultPruner`, an **optional companion** to compaction-basic (mounted by default in the base bundle; explicitly disabled in the web-mode bundle). It is not a compaction backend nor a model-facing tool, but a **model-free, replayable** prune: it rewrites over-budget `tool/result` surface nodes into "bounded head + fixed omission marker + bounded tail", while the full raw events remain in the append-only session log.

- **Trigger timing**: after compaction-basic's pressure or canonical overflow is triggered **but before it selects a region**, it reads it (`ctx.get('toolResultPruner')`); steps below pressure **never** prune.

- **Rewrite shape**: each over-budget result first logs a log-only `compaction/prune` (with the `shadowedRange` / `shadowedSeqs` / `shadowedTokenCount` shadow price), then synchronously appends a replacement `tool/result` carrying `{ surfaceOp: { op:'replace', startSeq: originalSeq, endSeq: originalSeq }, sourceEventSeqs:[originalSeq] }`; the replacement only changes `content`, preserving `turn`/`step`/`callId`/error fields/`meta`.

- **Pruned remeasure**: compaction-basic re-measures through `ctx.tokenMeter`; if pressure drops below the safety line it **skips the summary**; otherwise it summarizes the pruned surface.

| Config | Default | Meaning |
| --- | --- | --- |
| thresholdChars | 8192 | Prune only when text totals exceed this many Unicode code points |
| headChars | 4096 | Head code points retained |
| tailChars | 1024 | Tail code points retained |

- `measureContent(blocks)` counts the Unicode code points of `text` blocks; `pruneContent(blocks)` returns a bounded replacement, or `null` if the content is already within threshold. Non-text blocks keep their relative positions; slicing never splits a UTF-16 surrogate pair (but may split a multi-code-point grapheme cluster).

- Each output is exactly "head + marker + tail" and **strictly smaller than the triggering input**, so a second pass never re-produces a replacement.

Third-party `tool-rewind`'s SHRINK "the summary must be shorter than the folded region" belongs to a repository-external plugin whose semantics **cannot be verified from the current source**: treat it as an ecosystem reference, not a DSH built-in.

## Eight — Three perspectives: model / token / KV cache

| One assembly | What the model sees | Token effect | KV-cache effect |
| --- | --- | --- | --- |
| System prompt | identity + persona prefix/suffix + each plugin section (after strict interpolation), committed as a system/message node | identity costs tokens fixed; persona/section text is re-paid per request | repeated only when identity/persona/sections/order are byte-for-byte unchanged; on an in-history route an appended change keeps the prefix reusable |
| Tool schema | visible tools (via toolOrder/restriction) | schema is re-paid per step | schema invalidation starts at the first changed token |
| Session history | surface messages (without raw chunks/boundaries) | grows with surface messages; cumulative re-send per step across multi-tool turns | plain growth is append-only; surface replacement/compaction invalidates the prefix |

**Practical takeaway**: to save tokens and preserve the cache, keep the system prompt and tool schemas stable; any "dynamically assembled persona" invalidates the prefix cache from the change point onward, costing a full recompute.

## Nine — Source evidence (event layer)

```jsonl
{ "type": "system/message", "seq": 8,  "data": { "turn": 1, "step": 1, "message": { "content": [{ "type": "text", "text": "You are an AI agent powered by DeepSeek Harness.\n…" }] } } }

{ "type": "user/message",   "seq": 9,  "data": {...} }

{ "type": "request/header", "seq": 11, "data": { "header": { "config": {...}, "adapterDefaults": { "reasoningEffort": true }, "tools": [...] }, "reason": "initial" } }

{ "type": "request/context","seq": 12, "data": { "provider": "deepseek-official", "model": "deepseek-v4-flash", "contextWindow": ..., "systemPromptUpdate": "in-history" } }
```

## Ten — Verification

```sh
# Inspect one session's request header (zstd-compressed by default, two-level directory; current format version v3)

zstdcat ~/.dsh/sessions/*/*/session.v3.jsonl.zstd | grep "request/header" | head -1

# Inspect the assembled system prompt (the surface's system/message node, including identity + persona + each section)

zstdcat ~/.dsh/sessions/*/*/session.v3.jsonl.zstd | grep '"system/message"' | head -1

# Check whether variable rendering took effect (strict interpolation, malformed fails)

zstdcat ~/.dsh/sessions/*/*/session.v3.jsonl.zstd | grep -i "model\|cwd" | head
```

## Next steps

- [Agent Main Loop](../../learn/core/agent-loop.md): how the context is consumed by the loop (assembly is part of it)

- [Tool Execution](../../learn/core/tools-execution.md): the execution pipeline behind tool schemas

- [Agent Presets & Persona](../../features/persona.md): take full control of an agent's prompt with a `complete:true` persona

- [Write a Service](../../learn/dev/write-service.md): inject dynamic facts into an agent with `variable()`
