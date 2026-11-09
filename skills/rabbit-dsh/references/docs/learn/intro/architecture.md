# Architecture Overview

- 
- Concepts Course
- Basics
- Architecture Overview
On this page

# Architecture Overview

**In one sentence**: DSH is composed of dozens of `@deepseek-ai/*` packages: abstract capabilities (seams) live in `packages/core`, concrete implementations in the various capability packages, composition rules in `packages/bundle`, and everything is wired together through cordis's Context/plugin mechanism.

This is the page that explains "how DSH is actually assembled". We recommend reading [What Is DSH](../../learn/intro/what-is-dsh.md) first.

## 1. Package grouping map

| Grouping | Responsibility | Representative packages |
| --- | --- | --- |
| core/ | Abstract services and the core loop | agent, agent-loop, scope, session, system-prompt, tools |
| sandbox/ | Process sandbox | sandbox (convention), sandbox-local, sandbox-policy |
| session/ | Session system | session-persistence-jsonl/sqlite, session-projection, session-telemetry |
| llm/ | Model layer | llm, llm-deepseek, llm-pi-ai, llm-retry |
| context/ | Context injection sources (not assembly) | session-reference, time-context, agent-instructions |
| compaction/ | Context compression | compaction, compaction-basic, command-compact |
| shell/ fs/ terminal/ | Execution backends | bash-sandbox, fs-observation-policy, terminal-bash |
| web/ | Web tools/search | tool-web, web-search-deepseek/exa/perplexity |
| bundle/ | Composition layer | base, headless, web-app, sdk-app, sdk-minimal, acp-app |
| boot/ + apps/cli | Boot/commands | app-boot, cmdline |
| client/ host/ | Web UI dual process | browser side / host side |
| extensions/ | Dynamic Cordis extensions | tool-cordis, cordis-host-runner, cordis-client-runner, client-ui-cordis |
| Other | Capabilities | mcp, goal, guard, schedule, subagent, subprocess, jobs, workflow, settings, skill, storage, credentials, plan, preset, acp, lsp, code-runtime, etc. |

## 2. Layer structure

- The **application layer** decides "which mode to run" (web / headless) and "which plugins to load" (your profile)

- The **core service layer** is all the abstract capabilities (agent loop, sessions, models, tools, sandbox)

- The **composition layer** is cordis; it sums the two layers above, injects dependencies, and emits events

## 3. Key design: the Seam (capability seam)

Each capability seam = **an interface-definition package separated from an implementation package**. Take the sandbox as an example:

- `packages/sandbox/sandbox`: defines only the convention (`ctx.sandbox.confine` + vocabulary), with **zero dependency on a backend**

- `packages/sandbox/sandbox-local`: the implementation (Linux bwrap / macOS Seatbelt / Windows ACL)

**Swapping the implementation = changing the provider, and consumer code stays unchanged.** This runs through almost every capability — llm, session, storage, subagent, and so on. This is the structural foundation that makes "everything-is-a-plugin" viable.

## 4. Composition rules: Bundle → Profile

- A **bundle** is a "plugin package that carries its own patch", joining a profile as a layer

- A **profile** is the stacking of bundle layers + a user overlay layer (`$DSH_HOME/profiles/<name>`)

- The full application order and patch semantics are in [Plugin anatomy](../../learn/core/plugin-anatomy.md)

`sdk-minimal` is a standalone complete tree, not a base overlay; it intentionally omits most base services. The Web client uses `api/gateway` + domain controllers (`session-controller`, `settings-controller`, `workspace-controller`); browser stores (`client/store`) and React adapters (`ui-session`, `ui-chat`, `ui-approval`) have separate owners. See [Web UI](../../learn/core/web-ui.md) and [SDK](../../guides/drive-harness-from-program.md).

## 5. How a "make one tool call" request flows through each layer

```text
You send a message → application layer/UI

 → agent-loop (core service layer) assembles the request [system-prompt + tools + history]

 → ctx.llm picks a provider (model routing) → calls the model

 → the model wants to call → tools pipeline → (bash→sandbox / fs / web…)

 → the result is written back into the session log (event sourcing)

 → UI renders using the session/event
```

Every step happens on the seam of the corresponding layer — this is exactly the process described in [Agent loop](../../learn/core/agent-loop.md).

## 6. Viewing the current composition

```sh
dsh web --dump-config | head -50      # See the composition tree + source comment per row

dsh web --dump-default-config         # See only the bundle layers (no user layer)
```

`--dump-config` is the authoritative tool for "what a given layer is configured with" (see [Boot and configuration](../../learn/core/boot-config.md)).

## Next steps

- [Agent loop](../../learn/core/agent-loop.md): how the core loop drives things

- [Context](../../learn/core/context.md): how a request is assembled

- [Plugin anatomy](../../learn/core/plugin-anatomy.md): what a plugin is made of
