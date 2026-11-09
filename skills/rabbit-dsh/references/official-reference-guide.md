# Official DeepSeek Harness Reference Guide & Catalog

Use the published docs snapshot and the pinned authoring notes for offline development. Use the installed package and its inspection surface for version-specific behavior.

| Task | Read first |
| --- | --- |
| Write a skill | [Skill discovery and invocation](docs/official/reference/subsystems/skills.md) |
| Choose a Host, Client, or configuration extension | [Extension inspection and placement](docs/official/pinned/extensions.md) |
| Register a tool and define its model-facing schema | [Build a tool](docs/official/develop/basic/tool.md) |
| Install a package or edit a bundle patch | [Bundle packaging](docs/official/develop/basic/publish.md) |
| Prove an extension works | [Testing a DSH extension](docs/official/pinned/testing.md) |

---

## 1. Core Architecture & Catalogs

| Document | Path | What It Covers |
| --- | --- | --- |
| **Architecture Overview** | [`docs/official/reference/index.md`](docs/official/reference/index.md) | Cordis runtime, profile/bundle layering, application launch (`dsh --profile web`), HMR mechanics. |
| **Agent Lifecycle** | [`docs/official/reference/agent-lifecycle.md`](docs/official/reference/agent-lifecycle.md) | Turn, step, and execution lifecycle phases from prompt submission to tool output. |
| **Capability Seams** | [`docs/official/reference/capability-seams.md`](docs/official/reference/capability-seams.md) | Core services and abstraction boundaries (`ctx.tools`, `ctx.skills`, `ctx.shell`, etc.). |
| **Plugin Config Catalog** | [`docs/official/reference/config-catalog.md`](docs/official/reference/config-catalog.md) | Verbatim config definitions for all loadable harness packages and types. |
| **Tool Catalog** | [`docs/official/reference/tool-catalog.md`](docs/official/reference/tool-catalog.md) | Complete schema definitions and parameters for all built-in harness tools. |
| **Tool Execution Pipeline** | [`docs/official/reference/tool-execution-pipeline.md`](docs/official/reference/tool-execution-pipeline.md) | How tool calls are validated, approved, executed, and rendered for the model. |
| **Remote API Gateway** | [`docs/official/reference/api-gateway.md`](docs/official/reference/api-gateway.md) | Remote protocol bridge and JSON-RPC dispatch endpoints. |
| **Persistence Catalog** | [`docs/official/reference/persistence-catalog.md`](docs/official/reference/persistence-catalog.md) | Session log format, physical generation tracking, and event schema records. |
| **Experimental Persistence** | [`docs/official/reference/experimental-persistence-catalog.md`](docs/official/reference/experimental-persistence-catalog.md) | Experimental records and forward-compatibility specifications. |

---

## 2. Cordis Microkernel API

| Document | Path | What It Covers |
| --- | --- | --- |
| **Cordis Primer** | [`docs/official/reference/cordis-primer.md`](docs/official/reference/cordis-primer.md) | Context tree, plugins, lifecycle, services, and event mechanics. |
| **Context API** | [`docs/official/reference/cordis-api/context.md`](docs/official/reference/cordis-api/context.md) | `Context` creation, scoping, child forks, and disposal. |
| **Events API** | [`docs/official/reference/cordis-api/events.md`](docs/official/reference/cordis-api/events.md) | Event registration (`ctx.on`), emission (`ctx.emit`), waterfall pipelines (`ctx.waterfall`), and bail hooks. |
| **Service API** | [`docs/official/reference/cordis-api/service.md`](docs/official/reference/cordis-api/service.md) | `Service` base class, immediate vs deferred mounting, and dependency injection (`ctx.inject`). |
| **Fiber API** | [`docs/official/reference/cordis-api/fiber.md`](docs/official/reference/cordis-api/fiber.md) | Reactive execution units, context attachment, and effect tracking. |
| **Registry API** | [`docs/official/reference/cordis-api/registry.md`](docs/official/reference/cordis-api/registry.md) | Plugin registry, duplicate resolution, and runtime introspection. |
| **Inherited Cordis API** | [`docs/official/reference/cordis-api/inherited.md`](docs/official/reference/cordis-api/inherited.md) | Inherited upstream Cordis primitives and extensions. |

---

## 3. Extension Cookbooks

| Document | Path | What It Covers |
| --- | --- | --- |
| **Adding a Tool** | [`docs/official/reference/cookbook/adding-a-tool.md`](docs/official/reference/cookbook/adding-a-tool.md) | Step-by-step tool authoring with `defineTool`, Schemastery schemas, UI cards, and execution hooks. |
| **Adding a Settings Card** | [`docs/official/reference/cookbook/adding-a-settings-card.md`](docs/official/reference/cookbook/adding-a-settings-card.md) | Live settings UI cards for the Web interface. |
| **Adding an LLM Adapter** | [`docs/official/reference/cookbook/adding-an-llm-adapter.md`](docs/official/reference/cookbook/adding-an-llm-adapter.md) | Creating custom model providers and streaming adapters. |
| **Adding a Workspace Package** | [`docs/official/reference/cookbook/adding-a-package.md`](docs/official/reference/cookbook/adding-a-package.md) | Adding in-tree packages to the pnpm monorepo. |
| **Extension Shapes** | [`docs/official/reference/cookbook/extension-cookbook.md`](docs/official/reference/cookbook/extension-cookbook.md) | Common extension patterns across services, listeners, tools, and UI slots. |

---

## 4. Subsystems Catalog (47 Deep-Dive Documents)

The official reference breaks down the Harness into 6 functional subsystem clusters:

### A. Core & Scopes
- [`subsystems/core.md`](docs/official/reference/subsystems/core.md): Host bootstrap, event loop, and service initialization.
- [`subsystems/scope.md`](docs/official/reference/subsystems/scope.md): Scoped contexts, isolation layers, and inheritance chains.

### B. Execution, Tools & Runtime
- [`subsystems/tools.md`](docs/official/reference/subsystems/tools.md): Tool registry, execution lifecycle, and invocation permissions.
- [`subsystems/skills.md`](docs/official/reference/subsystems/skills.md): Progressive disclosure skill provider (`ctx.skills`).
- [`subsystems/workflow.md`](docs/official/reference/subsystems/workflow.md): Multi-agent workflow scripts and Ralph iterative loops.
- [`subsystems/subagent.md`](docs/official/reference/subsystems/subagent.md): Subagent delegation, concurrent threads, and result bubbling.
- [`subsystems/shell.md`](docs/official/reference/subsystems/shell.md): Shell command execution seam (`ctx.shell`).
- [`subsystems/subprocess.md`](docs/official/reference/subsystems/subprocess.md): Managed background subprocesses.
- [`subsystems/terminal.md`](docs/official/reference/subsystems/terminal.md): PTY terminal sessions.
- [`subsystems/jobs.md`](docs/official/reference/subsystems/jobs.md): Long-running background jobs.
- [`subsystems/filesystem.md`](docs/official/reference/subsystems/filesystem.md): File reading, writing, and workspace indexing.
- [`subsystems/lsp.md`](docs/official/reference/subsystems/lsp.md): Language Server Protocol code intelligence.
- [`subsystems/ptc-runtime.md`](docs/official/reference/subsystems/ptc-runtime.md): Program-to-code runtime bridge.
- [`subsystems/web.md`](docs/official/reference/subsystems/web.md): Web scraping and external resource fetching.

### C. Sessions & Persistence
- [`subsystems/session.md`](docs/official/reference/subsystems/session.md): Session storage, log format, and history management.
- [`subsystems/session-query.md`](docs/official/reference/subsystems/session-query.md): Cross-session search across DSH, Codex, and Claude Code.
- [`subsystems/session-reference.md`](docs/official/reference/subsystems/session-reference.md): Inter-session linking and citation refs.
- [`subsystems/session-title.md`](docs/official/reference/subsystems/session-title.md): Automatic topic and title generation.
- [`subsystems/session-projection.md`](docs/official/reference/subsystems/session-projection.md): Session state projections.
- [`subsystems/session-telemetry.md`](docs/official/reference/subsystems/session-telemetry.md): Telemetry collection and anonymization.
- [`subsystems/persistence.md`](docs/official/reference/subsystems/persistence.md): Disk persistence engines and migration.
- [`subsystems/storage.md`](docs/official/reference/subsystems/storage.md): Non-session data storage and backends.
- [`subsystems/spill.md`](docs/official/reference/subsystems/spill.md): Large-payload spillover storage.

### D. Model & Context
- [`subsystems/llm-streaming.md`](docs/official/reference/subsystems/llm-streaming.md): Token streaming, chunk parsers, and tool call reassembly.
- [`subsystems/token-meter.md`](docs/official/reference/subsystems/token-meter.md): Cost tracking, token limits, and quota controls.
- [`subsystems/system-prompt.md`](docs/official/reference/subsystems/system-prompt.md): Dynamic system prompt composition layers.
- [`subsystems/compaction.md`](docs/official/reference/subsystems/compaction.md): Context window truncation, summarization, and compaction.

### E. Policy, Safety & Interaction
- [`subsystems/approval.md`](docs/official/reference/subsystems/approval.md): Human-in-the-loop tool approval prompts.
- [`subsystems/permission-presets.md`](docs/official/reference/subsystems/permission-presets.md): Read-only, trusted, and developer mode presets.
- [`subsystems/sandbox.md`](docs/official/reference/subsystems/sandbox.md): OS process sandboxing and network isolation.
- [`subsystems/plan.md`](docs/official/reference/subsystems/plan.md): Plan mode vs execution mode.
- [`subsystems/user-questions.md`](docs/official/reference/subsystems/user-questions.md): Structured multi-choice question prompts to the user.
- [`subsystems/commands.md`](docs/official/reference/subsystems/commands.md): User slash-commands (`/help`, `/compact`, etc.).
- [`subsystems/goal.md`](docs/official/reference/subsystems/goal.md): Long-running persistent goals and continuation.
- [`subsystems/schedule.md`](docs/official/reference/subsystems/schedule.md): Cron schedules, timers, and background wakeups.

### F. Platform, Web UI & Clients
- [`subsystems/web-server.md`](docs/official/reference/subsystems/web-server.md): HTTP / WebSocket server for the Web interface.
- [`subsystems/web-client.md`](docs/official/reference/subsystems/web-client.md): Vue / Vite browser client architecture.
- [`subsystems/client-modules.md`](docs/official/reference/subsystems/client-modules.md): Extensible frontend client modules.
- [`subsystems/slots.md`](docs/official/reference/subsystems/slots.md): Frontend UI injection slots.
- [`subsystems/client-resources.md`](docs/official/reference/subsystems/client-resources.md): Static client asset serving.
- [`subsystems/sidebar-right.md`](docs/official/reference/subsystems/sidebar-right.md): Right inspector side pane panels.
- [`subsystems/conversation.md`](docs/official/reference/subsystems/conversation.md): Conversation assembly and message rendering.
- [`subsystems/typert.md`](docs/official/reference/subsystems/typert.md): Rich message rendering and typing indicators.
- [`subsystems/workspace.md`](docs/official/reference/subsystems/workspace.md): Workspace directory tracking and file change events.
- [`subsystems/settings.md`](docs/official/reference/subsystems/settings.md): Runtime user settings persistence.
- [`subsystems/credentials.md`](docs/official/reference/subsystems/credentials.md): Secure API key and secret storage.

---

## 5. Offline Lookup Commands

You can search and read any of these reference documents instantly using `rabbit-dsh`:

```bash
# Search official reference docs by subsystem or concept:
python3 skills/rabbit-dsh/scripts/rabbit_dsh.py docs search "subsystems approval"
python3 skills/rabbit-dsh/scripts/rabbit_dsh.py docs search "cookbook adding a tool"
python3 skills/rabbit-dsh/scripts/rabbit_dsh.py docs search "cordis-api fiber"

# Read specific reference guides directly:
python3 skills/rabbit-dsh/scripts/rabbit_dsh.py docs read official/reference/index.md
python3 skills/rabbit-dsh/scripts/rabbit_dsh.py docs read official/reference/cookbook/adding-a-tool.md
python3 skills/rabbit-dsh/scripts/rabbit_dsh.py docs read official/reference/subsystems/skills.md
python3 skills/rabbit-dsh/scripts/rabbit_dsh.py docs read official/reference/tool-catalog.md
```
