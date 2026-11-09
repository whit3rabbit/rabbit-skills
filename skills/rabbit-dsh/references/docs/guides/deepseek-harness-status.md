# DeepSeek Harness status: source 0.1.5-alpha.1 vs npm

**In short**: official source is now `0.1.5-alpha.1`, while npm `latest` / `next` still resolve to `0.1.2-rc.1` and the `alpha` channel already publishes `0.1.5-alpha.1`. Default `npx` runs the `latest` release; new interfaces described here refer to the source build.

Checked **2026-09-09**. This is an independent community tutorial site, not an official DeepSeek site.

## Contents

- [Verified baseline](#verified-baseline)
- [Breaking changes (read before upgrading)](#breaking-changes-read-before-upgrading)
- [Source changes and updated tutorials](#source-changes-and-updated-tutorials)
- [Official documentation](#official-documentation)
- [Choose a distribution channel](#choose-a-distribution-channel)
- [Upgrade checks](#upgrade-checks)
- [Follow changes](#follow-changes)

---

## Verified baseline

| Item | Result |
| --- | --- |
| Repository | deepseek-ai/deepseek-harness |
| Source | master / 5dda764ed3aa172535a7967b06ff95d9cbfe536a |
| Commit time | 2026-09-08 23:25:45, UTC+8 |
| Source version / tag | 0.1.5-alpha.1 / dsh-v0.1.5-alpha.1 |
| npm channels | latest = next = 0.1.2-rc.1; alpha = 0.1.5-alpha.1 |
| Since the previous site baseline | 1863 commits after cd5ef8148158 |
| License / maturity | MIT; Developer Preview with breaking interface changes |
| Node requirement | ^22.19.0 || >=24.0.0 in root package.json#engines |
| Default Web address | http://127.0.0.1:3080; source builds require the printed token launch URL |

Version checks use official Git, root `package.json`, and the npm registry. Features were checked against the [0.1.5-alpha.1](https://github.com/deepseek-ai/deepseek-harness/releases/tag/dsh-v0.1.5-alpha.1), [0.1.3-alpha.2](https://github.com/deepseek-ai/deepseek-harness/releases/tag/dsh-v0.1.3-alpha.2), and [0.1.3-alpha.1](https://github.com/deepseek-ai/deepseek-harness/releases/tag/dsh-v0.1.3-alpha.1) release notes and the corresponding TypeScript implementation.

## Breaking changes (read before upgrading)

| Change | Impact | Tutorial |
| --- | --- | --- |
| Session format upgraded to V3 | Resuming a supported historical session writes new-format logs and keeps the original files; the system prompt becomes part of message history; legacy PTC events and code preset references migrate automatically. Custom log readers must adapt, and upgraded sessions cannot be read by older versions | Upgrade & migration, Sessions |
| Plugin Agent API | ctx.agent is removed; callers must pass the Agent explicitly. Subagents that can continue a conversation are no longer treated as root sessions for scheduling | Plugin anatomy, Subagents |
| Inbox API | Inbox becomes a type interface and no longer exports a constructible runtime class; plugins read and write pending messages through agent.inbox, and hasPending / claim leave the public API | Sessions, Event system |

## Source changes and updated tutorials

| Change | Migration / behavior | Tutorial |
| --- | --- | --- |
| Dynamic system prompt | System prompts can change without invalidating the KV cache when the configured model explicitly declares support | LLM routing |
| Experimental right Sidebar | Tabs, split panes, and fullscreen; chat file links and produced files open in the Sidebar, and the Detail panel is removed | Web UI, Client resources |
| Generic file upload | Any file type mixes with images in one preview area; background uploads support progress, cancel, and resume display across session switches, and the model reads saved paths with existing file tools | Attachments |
| Outbound proxy | All outbound requests honor HTTP_PROXY, HTTPS_PROXY, ALL_PROXY, and NO_PROXY from the launch environment | Environment variables |
| Workspace files API | New packages/api/workspace-files lets the Web UI and plugins read and write files per workspace | Workspace files |
| "Open in app" | The Web top bar opens the workspace in an installed editor, IDE, terminal, or file manager | Web UI |
| Subagent session controls | Continuable subagents support queueing, editing, deleting, single or bulk Steer, and stopping | Subagents |
| PTC output expansion | PTC mode can expand commands and their output | Tool execution |
| Model probing | Custom providers' models objects and Anthropic native model lists are supported, backfilling names, context windows, and max output tokens; pi-ai upgraded to 0.85.1 | LLM routing |
| Subagent plugin runtime | Built-in runtimes for optional subagent plugins upgraded to Codex 0.153.4 and Claude Code 2.1.263; explicit model settings are unchanged | Subagents |
| UI and stats | Composer menu layering, placeholder text, and spacing improved; session statistics split into two expandable summaries (turns and speed, exact token usage and cache hits); built-in slash command descriptions localized and updated live with the interface language | Web UI |
| Python SDK | New macOS x64 runtime wheel installs and runs the bundled runtime on Intel Macs | Drive the harness from a program |
| Fixes | Send button and Enter follow the same busy-session setting; the model can no longer resume a goal the user paused; POSIX absolute-path images in assistant messages render; empty messages and blank queue edits are rejected; project-root discovery reports permission/IO errors; fs-ext no longer needs local compilation on macOS/Linux | Related pages |

## Official documentation

- [Getting started](https://github.com/deepseek-ai/deepseek-harness/blob/master/docs/user/guide/index.md)

- [Providers](https://github.com/deepseek-ai/deepseek-harness/blob/master/docs/user/guide/providers.md)

- [Python SDK](https://github.com/deepseek-ai/deepseek-harness/blob/master/docs/user/guide/python-sdk.md)

- [Session scheduling](https://github.com/deepseek-ai/deepseek-harness/blob/master/docs/user/guide/schedule.md)

- [MCP memory examples](https://github.com/deepseek-ai/deepseek-harness/blob/master/docs/user/guide/mcp-memory.md)

- [GitHub review](https://github.com/deepseek-ai/deepseek-harness/blob/master/docs/user/guide/github-review.md)

- [Plugin development](https://github.com/deepseek-ai/deepseek-harness/tree/master/docs/user/develop)

- [Architecture](https://github.com/deepseek-ai/deepseek-harness/blob/master/docs/architecture.md) / [Development](https://github.com/deepseek-ai/deepseek-harness/blob/master/docs/development.md)

Chinese counterparts live alongside these files with the `.zh.md` suffix.

## Choose a distribution channel

For the published npm release (`latest` channel):

```sh
npx @deepseek-ai/dsh@0.1.2-rc.1 web

npm view @deepseek-ai/dsh dist-tags --json
```

For the source features described here, use a separate checkout:

```sh
git clone https://github.com/deepseek-ai/deepseek-harness.git

cd deepseek-harness

git checkout --detach dsh-v0.1.5-alpha.1

pnpm install

pnpm run build

pnpm dsh web
```

When upgrading an existing installation across versions, clear the previous build output first (`packages/*/*` directories without `package.json`, every `lib/`, every `*.tsbuildinfo`); otherwise `tsc -b` skips artifacts because of stale incremental state. A source tag does not imply npm publication. Query the registry before the next upgrade, and keep SDK clients and runtime versions aligned.

## Upgrade checks

Start with the [migration runbook](../guides/upgrade-migration.md) for backups, isolated validation, and rollback. Optional walkthroughs: [GitHub PR review](../guides/github-pr-review.md) and [MCP memory](../guides/mcp-memory.md).

- **Back up session data first**: the V3 migration keeps the original log files, but upgraded sessions cannot be read by older versions - rollback needs the old binaries plus a copy of the pre-upgrade session directory.

- Audit plugins for `ctx.agent`, `Inbox` constructors, and `hasPending` / `claim`, and adjust per the breaking-change table above.

- Migrate old `code` tool modes, API Proxy imports, and SDK `launch` options using the linked guides.

- Inspect `dsh web --dump-config`, especially telemetry, WebFetch, model selection, and third-party plugins.

- Upstream README / SECURITY state that the project has not been security-audited. Approval, permission presets, and sandbox mechanisms are not a containment guarantee. Start with a test directory without sensitive information and assess plugins and data egress separately.

## Follow changes

Use official [Releases](https://github.com/deepseek-ai/deepseek-harness/releases) for release changes and [Discussions](https://github.com/deepseek-ai/deepseek-harness/discussions) for feedback. Our [plugin ecosystem](../ecosystem.md) is a community directory, not an official endorsement.
