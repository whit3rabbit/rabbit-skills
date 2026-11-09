# Built-in Tools

Tools are the model's entry point for performing operations. DSH ships multiple `@deepseek-ai/dsh-tool-*` packages out of the box, grouped by capability domain below. They register through `ctx.tools` and automatically appear in the model's tool list.

Want to **add** a tool for the model? See [writing a tool](../learn/dev/write-tool.md). This page only covers the built-in, out-of-the-box capabilities.

## Contents

- [At a glance](#at-a-glance)
- [Terminal domain](#terminal-domain)
- [File domain](#file-domain)
- [Delegation and parallelism](#delegation-and-parallelism)
- [Goals / jobs / todos](#goals-jobs-todos)
- [Search / query / questions](#search-query-questions)
- [Network](#network)
- [Code](#code)
- [Introspection and orchestration](#introspection-and-orchestration)
- [Common combinations (how to chain them to get work done)](#common-combinations-how-to-chain-them-to-get-work-done)
- [Verify which tools are currently installed](#verify-which-tools-are-currently-installed)
- [Tool configurability](#tool-configurability)

---

## At a glance

| Capability domain | Tool packages | In one sentence |
| --- | --- | --- |
| Terminal | tool-bash / tool-bash-persistent / tool-pwsh / tool-pwsh-persistent / tool-terminal | run commands, long-lived sessions |
| Files | tool-fs / tool-fs-search / tool-str-replace-editor | read/write, search, precise editing |
| Network | tool-web | web_search / web_fetch |
| Code | tool-lsp | jump-to-definition, find references, hover |
| Delegation | tool-subagent / tool-subagent-control | hand work to subagents |
| Scheduling | schedule | timed reminders |
| Goals | tool-goal | session-level goals |
| Jobs | tool-jobs | background job output/list/terminate |
| Todos | tool-todo | todo_write |
| Skills | tool-skill | load skills |
| Session query | tool-session-query | history search/traces |
| Questions | tool-ask-user | ask the user |
| Introspection | tool-cordis | query Host/Client contracts and manage versioned dynamic plugins |
| Orchestration | tool-workflow / tool-ralph | JS orchestration, Ralph iteration |
| Model-carrying | decided by each seam | presentation and scheduling |

## Terminal domain

| Tool | Key usage | Description |
| --- | --- | --- |
| bash | run shell commands, optional background jobs, sandbox escalation | general command execution |
| bash (tool-bash-persistent) | long-lived shell sessions (same name as tool-bash) | owner-isolated persistent Bash (PTY-based) |
| terminal | six persistent terminal tools | interactive terminals, owner-isolated, connected to background jobs |
| pwsh | execute PowerShell | the shell layer for Windows scenarios |
| pwsh (tool-pwsh-persistent) | long-lived PowerShell sessions (same name as tool-pwsh) | owner-isolated persistent PowerShell (PTY-based) |
| Terminal tools all pass through ctx.sandbox.confine (see sandbox and security). The execution environment is uniformly provided by shell-env (ctx.shellEnv): every foreground/background shell call receives a freshly collected managed DSH_* environment snapshot, with built-in DSH_HOME, DSH_SHELL=1, DSH_SESSION_ID; other plugins can register effect-scoped contributors to append facts; duplicate attribution or undeclared runtime keys fail loud. shell-env is mounted by default, and process.env is never rewritten. |  |  |

## File domain

| Tool | Key usage | Description |
| --- | --- | --- |
| fs | read / read_image / write / edit | goes through the ctx.fs capability seam |
| fs_search | glob / grep | bundled ripgrep, fast discovery |
| str_replace_editor | view/create/literal replace/insert lines | precise editing, small diffs, easy to review |

`read_image` registers only when the durable `ctx.attachments` service is mounted, and at execution it rejects model routes that do not declare image input; it accepts PNG/JPEG/WebP/GIF (including extension-less paths recognized by file signature) and returns the image as a native image block recorded in the session log with its durable reference.

## Delegation and parallelism

| Tool | Key usage | Description |
| --- | --- | --- |
| subagent | dispatch one-shot subagents | goes through the ctx.subagents seam |
| subagent_control | send_message / interrupt_agent / list_agents | global control of continuable sub-sessions |

The full delegation model is in [Subagents and parallelism](../features/subagent.md). Parent and continuable child Agents exchange follow-up messages through `send_message` (since 0.1.2-rc.1, replacing the one-way `report` tool; `tool-subagent-report` is gone).

## Goals / jobs / todos

| Tool | Key usage | Description |
| --- | --- | --- |
| get_goal / create_goal / update_goal | same-session long-term goals | execution-time permission checks |
| jobs | job_output / job_list / job_kill | background job registry |
| todo | todo_write | writes into the event-sourced session log |

See [Goals, Jobs, and Todos](../features/goals-tasks.md). A goal the user paused can only be resumed by the user: `update_goal` cannot move `paused` back to `active` (0.1.5).

## Search / query / questions

| Tool | Key usage | Description |
| --- | --- | --- |
| session_search (et al.) | history session search / traces / event reads | queries DSH's own sessions, opt-in (not mounted by default) |
| ask_user_question | ask the user a question | goes through ctx.userQuestions |

`dsh-tool-session-query` registers `session_search`/`session_trace`/`session_event_read` and so on to query DSH's own history sessions; the package is opt-in and not mounted by default.

## Network

What the model sees is the `web` tool (`web_search` / `web_fetch`), both going through the same `ctx.web` capability seam. **The actual retrieval/forward-fetch is done by the provider backends registered into `ctx.web`**; `tool-web` only handles presentation (tool name, schema, result format, HTML→markdown):

| Backend | Type | Description | Mount |
| --- | --- | --- | --- |
| web-search-deepseek | search provider | Anthropic-compatible Messages API + native web_search tool, parses structured result blocks, reuses DEEPSEEK_API_KEY | mounted by default (searchProvider: deepseek-official) |
| web-fetch-http | fetch provider | Public HTTP(S), address/DNS/redirect checks and output limits | Base mounts the provider with tool-web at fetch: true; the Web app disables that base row and standard/cordis/ptc presets compose their own (also fetch: true) |
| web-search-exa | search provider | Exa POST /search, auto/keyword/neural; no generated answer, content omitted | opt-in (requires EXA_API_KEY) |
| web-search-perplexity | search provider | OpenAI-compatible chat/completions, generated answer content + citations sources[] | opt-in (requires PERPLEXITY_API_KEY) |

Providers register **capabilities, not tools**; `tool-web`'s registration follows the product switch (base already sets `fetch: true`; the Web app disables that base row and standard/cordis/ptc presets compose their own at `true`, while the minimal preset has no web tool), not backend availability — when a provider is missing/unavailable/ambiguous, the tool schema stays and a structured `WebError` is thrown at execution. Provider selection resolves within the seam at execution time (an explicit `searchProvider`/`fetchProvider` or automatic selection of the single available provider).

Outbound network calls uniformly follow the proxy policy resolved from the startup environment (0.1.3-alpha.1): `HTTP_PROXY` / `HTTPS_PROXY` / `ALL_PROXY` / `NO_PROXY` cover LLM, web search, and HTTP MCP traffic; loopback stays direct, and an unsupported proxy URL is reported and skipped for that protocol.

## Code

| Tool | Key usage | Description |
| --- | --- | --- |
| lsp | goToDefinition / findReferences / goToImplementation / hover | read-only, based on ctx.lsp |

## Introspection and orchestration

| Tool | Key usage | Description |
| --- | --- | --- |
| cordis | cordis_inspect_list/query/self + cordis_define/run/stop/undefine | versioned dynamic Cordis toolset |
| workflow | run JS orchestration scripts | goes through ctx.workflowEngine |
| ralph | Ralph iteration loop with fresh Agents | combines workflow + subagent |

See [Workflow and Ralph](../features/workflow.md).

## Common combinations (how to chain them to get work done)

| You want | Combination |
| --- | --- |
| search + read a file + change code | session_search to find history → fs/str_replace_editor to change |
| terminal running + background jobs | bash resident + jobs to collect background output |
| split a large task for parallel | subagent to dispatch + subagent_control to collect |
| scheduled progress | schedule_create to set reminders + update_goal/todo_write to record progress |
| stuck, ask a human | ask_user_question to confirm before continuing |

Tools are atomic capabilities; fixing common sequences into reusable form is what [skills](../features/skills.md) or [workflows](../features/workflow.md) are for.

## Verify which tools are currently installed

```sh
dsh web --dump-config | grep -E "tool-"

# each tool-* plugin and whether it's enabled is visible in the composition tree
```

## Tool configurability

Every tool package can override `config` at the profile layer via a patch (e.g. whether it's off by default, timeouts, workspace authorization). A tool's **presentation** (native/ptc/both) is decided by `ctx.tools.presentAs`, not something a tool cares about itself. In PTC mode, supported `bash` / `pwsh` / `terminal_send` subcalls dispatched through `run_code` render as expandable terminal cards in the Web tool card exactly like root calls, with both command and output expandable (0.1.3-alpha.2); background calls and tool errors keep the generic fallback. `read_image` renders the image directly for top-level and PTC-nested calls instead of showing the raw attachment object (0.1.3-alpha.1).

Source baseline: `0.1.5-alpha.1` (`5dda764ed3`). Public fetching has an SSRF policy rather than the old deferred protection; ordinary permitted public fetches do not request per-call network approval. Check the effective preset, not only base. Owners: `packages/web/web-fetch-http`, `packages/util/http-proxy`, `packages/bundle/base/cordis.patch.yml`, and `packages/preset/agent-presets/presets/`.
