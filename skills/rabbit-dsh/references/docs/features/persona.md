# Agent Presets and Personas

An Agent is more than "a model + a few default tools": it has a **fixed composition** — tools, system prompt sections, projection units — plus its personality. DSH carries this with two mechanisms: **Agent presets** (preset) and **Personas**.

| Mechanism | What it manages | Carrier |
| --- | --- | --- |
| Agent preset | the full capability composition of that agent | a directory + one agent.cordis.yml |
| Persona | that agent's personality / system prompt | one composable system-prompt line |

## Contents

- [1. Agent presets (agent-presets)](#1-agent-presets-agent-presets)
- [2. Persona](#2-persona)
- [3. Plan mode (plan-mode)](#3-plan-mode-plan-mode)
- [What a complete preset looks like](#what-a-complete-preset-looks-like)
- [Verification](#verification)
- [Next steps](#next-steps)

---

## 1. Agent presets (agent-presets)

A **preset** is a directory containing an `agent.cordis.yml`. `@deepseek-ai/dsh-agent-presets` **mounts it once** in-process (a standing mount); every session that names it joins it through the agent-scope parent chain.

- Each session keys its own state, but shares the same mount: "each preset's composition exists once, covering all agents that join it"

- Scope resolution chain: `agent → preset → global` (**nearest shadows farthest**)

- Mounted tools/prompt sections/projection units are visible to each agent beneath it; sibling presets stay deaf to it

```ts
ctx.agentPresets.defaultId          // preset id mounted when none is specified

await ctx.agentPresets.list()        // all current presets (including broken, with reasons)

await ctx.agentPresets.resolve(id?)  // by id, defaulting to defaultId

await ctx.agentPresets.mount(agentCtx, id?)   // compose an agent's preset

await ctx.agentPresets.composeFrom(agentCtx, parentCtx)  // join another agent's already-running standard composition

await ctx.agentPresets.read(id) / copy(...) / remove(id)  // read source / copy to create new / delete (local authority)
```

**Discovery is not cached**: `list()`/`resolve()` re-read the root every time, so a preset added at runtime is immediately visible. A corrupted directory is listed as `broken` (with a reason) rather than skipped.

## 2. Persona

`@deepseek-ai/dsh-persona` is a **composable personality line**. The deployment persona is registered unconditionally by `dsh-system-prompt` as its own config (process has exactly one); this package is the line that lets a single agent **shadow the deployment persona**.

```yaml
# in a preset's agent.cordis.yml

- id: persona

  name: '@deepseek-ai/dsh-persona'

  config:

    text: |

      You are an assistant focused on code review. Be direct and give actionable suggestions.

    complete: false   # false=shadow; true=become the only system prompt section

    includeRuntimeContext: true  # false=hides every dynamic context snapshot for this agent
```

- `text` is a template supporting `{{…}}` groups, strictly resolved against registered prompt variables at **render time** (not assembly time)

- With `complete: true`, assembly still resolves context/tools/variables/collaboration listeners, but afterwards **only this one persona section remains**: no other identity/tool guidance can be appended

- With `includeRuntimeContext: false`, context providers are not evaluated for this scope and listener-added contexts are discarded; the sandbox, approval, delegation, and other owning services stay active

**Can only mount in agent scope** (provided by a preset mount): mounting outside that scope conflicts with the `deployment:persona` registration and loud-fails. This is not meant to be bypassed: the deployment persona already has an owner, and this line's whole purpose is to shadow it for a single agent.

## 3. Plan mode (plan-mode)

`@deepseek-ai/dsh-plan-mode` is a **per-agent planning collaboration state + a deployment-wide guidance section**. It is, like a persona, a text section composable into the system prompt; the difference is that a persona is a persistent personality line, while the plan section **appears at prompt order 50 only when plan mode is active**, contributing zero tokens when inactive.

- **Entry/exit are commands**: `/plan [message]` selects plan mode (bare `/plan` enters directly; a non-empty argument pre-selects it, then submits as the next ordinary user message via `agent.steer()`); `/plan off` exits (the argument `off` is preserved exactly). The command and its terminal result never enter the model history.

- **`exit_plan_mode`** is the only exit tool: its schema is stably registered in both states, its execute is accepted only when plan is active, and it only leaves after the user **explicitly approves** via `ctx.userQuestions`. It declares a `plan-review` presentation intent, exposing `Approve` as the approval label — capable UIs present it as a decision rather than a generic question.

- **State writes to the log only**: the `plan/mode` event (`{ active: boolean }`) is log-only and whole-value-replacing; `foldPlanMode` restores directly from the session log, so resume, fork, and compaction all recover the state. A fork child inherits the recorded plan state; a fresh spawn starts inactive.

- `section` is a **required, non-empty** config; unknown keys fail at load. It does not accept arbitrary named modes, tool filters, sandbox settings, or approval policies.

**Consistent framing**: plan mode is **soft guidance, not model routing**. It **does not switch models and does no plan/execute dual routing** (see [multi-model](../features/multi-model.md) and [model routing](../learn/core/llm-routing.md)); sandbox modes and approval policies are **enforced independently**, neither reading nor writing plan state. To actually "restrict" execution, configure sandbox + approval separately. Mounted by default (base); under Web, plan-mode moves to the preset layer, where the standard preset's `planning` group carries it in an entry-local realm — plan state is per-agent by nature, which is the correct lifecycle.

## What a complete preset looks like

```text
~/.dsh/.agent-presets/reviewer/   # a user-authored preset root ($DSH_HOME/.agent-presets)

└── agent.cordis.yml
```

```yaml
# agent.cordis.yml —— the preset's standard composition

- id: persona

  name: '@deepseek-ai/dsh-persona'

  config:

    text: You are a code review assistant. Read-only refactoring suggestions, no implementation.

- insert:

    - id: tools

      name: '@deepseek-ai/dsh-tools'

    - id: lsp-tool

      name: '@deepseek-ai/dsh-tool-lsp'
```

A session selecting this preset → mounted once; the mounted composition applies to every joining agent.

## Verification

```sh
# see the user preset root

ls ~/.dsh/.agent-presets/

dsh web --dump-config | grep agentPresets

# see persona/system-prompt sections in the session

zstdcat ~/.dsh/sessions/*/*/session*.jsonl.zstd | grep -E 'persona|preset' | head
```

## Next steps

- [Plugin anatomy](../learn/core/plugin-anatomy.md): a preset is also a composition

- [Subagents and parallelism](../features/subagent.md): subagents can have their own preset/persona
