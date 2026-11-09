# What Is DSH

- 
- Concepts Course
- Basics
- What Is DSH
On this page

# What Is DSH

**In one sentence**: DeepSeek Harness(`dsh`) is an open-source **coding / automation agent**: an independent process with its own configuration, session, and permission system, built on an **everything-is-a-plugin** architecture: the core keeps only the loop and the abstraction seams, while every capability comes from composing plugins.

DSH is open-sourced by DeepSeek AI and is currently in **Developer Preview**. See [deepseek-ai/deepseek-harness](https://github.com/deepseek-ai/deepseek-harness) for the official source, install command, and current behavior. This site is community-maintained.

This page answers "what exactly is this thing, and is it worth using". By the end you will have a judgment, and know where to start.

## Contents

- [1. What it is](#1-what-it-is)
- [2. What it is not (avoiding misconceptions)](#2-what-it-is-not-avoiding-misconceptions)
- [3. Core concepts](#3-core-concepts)
- [4. What it can do (capability overview)](#4-what-it-can-do-capability-overview)
- [5. Three ways to start](#5-three-ways-to-start)
- [6. The everything-is-a-plugin philosophy](#6-the-everything-is-a-plugin-philosophy)
- [7. Quick verification](#7-quick-verification)
- [Where to start](#where-to-start)

---

## 1. What it is

`dsh` is an **agent that can run tasks on its own** — not a "chat box", and not an "IDE completion plugin". It:

- is an **independent process** with its own configuration (`~/.dsh/`), sessions (`~/.dsh/sessions/`), permission, and sandbox system

- can **read files, run commands, search, and call tools**, and also supports multi-model routing and multi-agent collaboration

- extends almost everything (tools, services, events, UI panels) through **plugins**

- provides a Hermes-style Web workbench via `dsh web`, and also supports one-shot command-line tasks

To put it in one sentence: it is "a workbench you start with a single `dsh web`, plus a composable set of agent capabilities".

## 2. What it is not (avoiding misconceptions)

| Not | It actually is |
| --- | --- |
| IDE plugin | Independent process that manages its own configuration/sessions/permissions |
| Single-model chat box | Can route across multiple providers/models (llm-pi-ai) |
| Fixed-function tool | You can change not just settings, but the composition itself |

Common misconception: "plan/execute automatically switches models": no such thing. `/plan` only maintains planning/coordination state, and does not switch models (see [Model routing](../../learn/core/llm-routing.md)).

## 3. Core concepts

| Concept | Description | Location |
| --- | --- | --- |
| SDK | The runtime stack that drives the Harness from another process (JSON-RPC wire protocol / client / server) | packages/sdk |
| Cordis base | The composition framework providing Context/service injection/plugin loading (everything-is-a-plugin) | @deepseek-ai/cordis |
| Harness | The complete composed agent application: loop, tools, sessions, sandbox | whole-repo composition |
| Profile | The composed configuration of plugins: bundle patch layers stacked with a user overlay layer | $DSH_HOME/profiles/ |
| Bundle | A plugin package that carries its own patch and joins a profile as a layer | packages/bundle/base |
| Seam (capability seam) | Abstract capability interfaces (ctx.llm, ctx.tools, ctx.sandbox…), whose implementations are swappable | individual capability packages |

## 4. What it can do (capability overview)

| Scenario | How |
| --- | --- |
| Modify code / read files / run commands | tool-fs / tool-bash (see Built-in tools) |
| Search DSH's own past sessions | tool session_search (dsh-tool-session-query) |
| Split a task across multiple agents in parallel | Subagent / Workflow |
| Scheduled reminders | Scheduling |
| Connect external tools | MCP |
| Teach the model processes | Skills |
| Long-term goal progression | Goals and tasks |

## 5. Three ways to start

```sh
npx @deepseek-ai/dsh web                    # Official zero-install entry point

dsh web                                    # Web workbench (default 127.0.0.1:3080)

dsh --profile headless "run the tests"     # One-shot task; exits after it finishes

dsh --profile web                          # Explicitly specify a profile
```

- `web` and `headless` are **built-in profile templates**

- `--profile headless <task>` is the one-shot task entry point (`dsh run` has been removed)

## 6. The everything-is-a-plugin philosophy

The top-level README says it verbatim: "it adopts an 'everything-is-a-plugin' architecture":

- **Add a capability** = write a plugin (tools, services, events, UI)

- **Change behavior** = swap plugins / stack patch layers, **without touching the core**

- **The core keeps only one concrete `AgentLoop`**: "new behavior should go into a plugin, not here"

That is why later you will see [Plugin anatomy](../../learn/core/plugin-anatomy.md) repeatedly stress "extension points first".

## 7. Quick verification

```sh
dsh web --dump-config         # See the current composed plugin tree (the layering at a glance)

dsh web --dump-default-config # See the default bundle's composition
```

## Where to start

Pick your entry point by your goal (the full navigation is in [Learning path](../../getting-started/learning-path.md)):

- Get it running first → [Quick start](../../getting-started/quickstart.md)

- Understand the architecture → [Architecture overview](../../learn/intro/architecture.md)

- Understand the main loop → [Agent loop](../../learn/core/agent-loop.md)

- Write a plugin hands-on → [Your first plugin](../../learn/dev/hello-plugin.md)
