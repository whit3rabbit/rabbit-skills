# Learning Path

This tutorial site has a lot of content; rather than reading top to bottom, choose a path by your **experience level**. Each level spells out "what to read, and what you'll achieve".

## 🟢 New users: first get it running

Goal: set up your key, open a dialog box, and know what's going on.

- [Quickstart](../getting-started/quickstart.md): configure your key, open the Web UI, first conversation

- [Command Line](../user-guide/cli.md): `dsh web` / `--profile headless` / `--dump-config`

- [Configuration](../user-guide/configuration.md): profiles, the patch layer, API keys

- [What is DSH](../learn/intro/what-is-dsh.md): what exactly it is

✅ Afterwards you can: configure a key, open the Web UI, and view `--dump-config`.

## 🟡 Everyday use: make it convenient

Goal: know how much it can do, and how to manage permissions and privacy.

- [Built-in Tools](../features/tools.md): what the 21 factory tools can do

- [Permissions](../user-guide/permissions.md): presets, `ask`/`never`, `DSH_PERMISSION_MODE`

- [Data and Privacy](../user-guide/privacy.md): telemetry, `.anonymous-user-id`, session storage

- [Multi-Model Routing](../features/multi-model.md): how to configure providers

- [Subagents and Parallelism](../features/subagent.md): handing work out

- [Goals, Jobs and Todos](../features/goals-tasks.md): pushing long-running matters forward

- [Settings and Credentials](../user-guide/settings.md): runtime configuration and key management

- [Session Search](../features/session-query.md) / [Attachments](../features/attachments.md): search past sessions, attach images into a session

✅ Afterwards you can: manage permissions, multiple providers, spin up subagents, and use goals to advance long-running tasks.

## 🔵 Developers: add capabilities to the model

Goal: write your own plugins, tools, services, listen to events, and publish configuration.

- [Plugin Anatomy](../learn/core/plugin-anatomy.md): what a plugin is, patch-layer semantics

- [First Plugin](../learn/dev/hello-plugin.md): hello world

- [Write a Tool](../learn/dev/write-tool.md): add a tool to the model

- [Write a Service](../learn/dev/write-service.md): shared logic

- [Listen to Events](../learn/dev/listen-events.md): dispatch modes, event catalog

- [Configuration & Publishing](../learn/dev/config-publish.md): `ctx.settings` + publishing

- [Skills System](../features/skills.md) / [MCP Integration](../features/mcp.md): extend capabilities further

- [Feedback](../features/feedback.md) / [Spill Storage](../features/spill.md) / [E2B Cloud Sandbox](../features/e2b.md): advanced capabilities mounted on demand

✅ Afterwards you can: write plugins, add tools, register commands, connect MCP, and publish configuration.

## 🟣 Architects: dig into the principles

Goal: understand how DSH assembles all of this.

- [Architecture Overview](../learn/intro/architecture.md): the package-grouping map

- All 11 core-mechanics chapters: `boot-config` → `context` → `agent-loop` → `tools-execution` → `sandbox-security` → `session` → `llm-routing` → `plugin-anatomy` → `event-system` → `web-ui` → `schedule`

- [Workflows and Ralph](../features/workflow.md): multi-agent orchestration

- [Agent Presets and Persona](../features/persona.md): identity and composition

- [Built-in Tools](../features/tools.md): full picture

✅ Afterwards you can: explain an agent's complete path from startup to running a tool, and pinpoint "which layer to extend at".

## Choose a practical workflow

- [Upgrade and migration](../guides/upgrade-migration.md): channels, backup, configuration changes, verification, and rollback.

- [Automatic GitHub PR review](../guides/github-pr-review.md): turn a matching webhook into a read-only review Session.

- [Persistent MCP memory](../guides/mcp-memory.md): connect a backend and verify recall in a fresh Session.

💡 **Tip**: all doc links have no numeric prefixes and can be jumped back; use the right-hand directory for quick navigation; the "Principles Course" works well as a reference manual to query, not something to read in one sitting.
