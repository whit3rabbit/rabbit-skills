# FAQ

On this page

# FAQ

Quick reference for common questions. For detailed mechanisms see the corresponding pages (links in each section).

## Contents

- [1. Startup](#1-startup)
- [2. Configuration](#2-configuration)
- [3. Plugins](#3-plugins)
- [4. Data / Privacy](#4-data-privacy)
- [5. Error Troubleshooting](#5-error-troubleshooting)
- [6. Execution and Terminal](#6-execution-and-terminal)
- [7. Choosing a harness](#7-choosing-a-harness)
- [Still have questions?](#still-have-questions)

---

## 1. Startup

### Browser won't open after dsh web starts

- It listens on `127.0.0.1:3080`; confirm the process: `ps aux | grep "bin.js web"`

- Port occupied: `dsh web --port 8080`

- Bad configuration: `dsh web --dump-config` to inspect the composition tree

### First run of --dump-config errors

Usually some plugin fails to parse; errors with the `dsh:` prefix name it. Delete the offending patch line and retry (see [Startup](../learn/core/boot-config.md)).

## 2. Configuration

### How do I switch models?

Settings → Models, add a provider (any OpenAI-compatible endpoint), then pick it in the session; or change `agent-default-model` in `settings.yaml` (see [Multi-model](../features/multi-model.md)).

### How do I change the default model?

The default model is decided by the `agent-default-model` service (requires `{ provider, model }`), shared by web / headless / API entry points. Change `agent-default-model` in `settings.yaml` (or the Models settings page) to override the deployment default; it takes effect for the next created Agent; `/plan` does not switch models (see [Multi-model](../features/multi-model.md)).

### cordis.patch.yml changes don't take effect?

Patches are composed at startup: **restart `dsh web`**. Check whether id/name match (see [Plugins](../user-guide/plugins.md)).

### Where do I set environment variables / credentials?

`~/.dsh/.env` (secrets), shell environment variables (`DSH_HOME` and so on), and `settings.yaml` (structured config). See [Environment Variables](../reference/env-vars.md).

### How do I change the DSH home directory?

The `DSH_HOME` environment variable overrides the default `~/.dsh` (holds profiles, sessions, credentials, source); restart after changing it. See [Environment Variables](../reference/env-vars.md).

### How is credential priority ordered?

`dsh-credentials-local` has four tiers: process environment (read-only, always wins) > `$DSH_HOME/.credentials.yaml` (managed 0600) > working directory `.env` > `$DSH_HOME/.env`. See [Credential Management](../user-guide/credentials.md).

### Can I use Claude / GPT models?

Yes. `llm-pi-ai.providers` accepts any OpenAI-compatible endpoint; the official `deepseek-official` provider is just the default route. Model names, endpoints, and keys are configured locally — no vendor lock (see [Multi-model](../features/multi-model.md) and [the comparison](../guides/dsh-vs-claude-code-vs-codex.md).

## 3. Plugins

### Errors after uninstalling?

`dsh plugin remove` only removes dependencies and does **not** rewrite the manually mounted manifest: check `profile/web/cordis.patch.yml` and manually delete the corresponding insert lines.

### Plugin panel not visible?

Confirm the bundle has plugin-console:

```sh
dsh web --dump-config | grep plugin-console

# if absent, go through the repository source; the plugin panel's repository mechanism adds a subpath

# (github:dsh-external/plugin-registry#main&path:/packages/plugin/console)
```

### Bundle plugin installed but not effective?

**Restart `dsh web`**. Bundles require a restart; repository changes take effect immediately.

### How do I choose between bundle and repository plugins?

Bundles go through `dsh plugin add` (pnpm source) and take effect on restarting `dsh web` — suited to kernel packages and packages needing a restart; repository goes through the panel plus `cordis.patch.yml` lines and takes effect immediately — suited to monorepo subpackages and frequent iteration. See [Plugins](../user-guide/plugins.md).

### Why is session_search not mounted by default?

`tool-session-query` is **opt-in** (not mounted by the factory composition by default): it exposes "search past sessions" to the model, cross-session access requires the cwd to match exactly, and the deployer weighs the tradeoffs before explicitly mounting it. The underlying `session-query-sqlite` is mounted by default (`:memory:`). See [Session Query](../features/session-query.md).

### How do I enable e2b?

e2b is an experimental POC, opt-in: no factory composition mounts it by default. Explicitly declare the three rows `e2b`, `subprocess-e2b`, `fs-e2b` in the profile's cordis config, with the last two loading after `e2b`; `apiKey` defaults to reading `E2B_API_KEY`. See [E2B Cloud Sandbox](../features/e2b.md).

## 4. Data / Privacy

### How do I turn off telemetry?

`export DSH_TELEMETRY_DISABLED=1` then restart. Any non-empty value (including 0/false) counts as off (see [Privacy](../user-guide/privacy.md)).

### What telemetry modes are there?

The OTel backend (`session-telemetry-otel`) has three modes: `FULL` (explicit continuous sharing) / `FEEDBACK_ONLY` (shipped default, feedback-gated) / `DISABLED`; you can also use `DSH_TELEMETRY_DISABLED` to turn it off directly. See [Privacy](../user-guide/privacy.md).

### Where are attachments stored?

Image bytes live in `<DSH_HOME>/attachments/v1/objects/<sha256-prefix>/<sha256>`, owner-only; session logs store only the `sha256:` reference and validated metadata, without the host path. See [Attachments](../features/attachments.md).

### Which formats do attachments support?

The first version accepts only PNG, JPEG, WebP, GIF; generic files, audio, and video need a separate lifecycle (see [Attachments](../features/attachments.md)).

### When does spill trigger?

When the UTF-8 byte count of a tool's final plaintext result exceeds `maxInlineBytes` (default 50000), `spill-policy` writes the full text to a session-scoped file, and the model side gets a bounded head/tail preview plus a locator; `read` results, nested results, and results containing non-text blocks do not spill. See [Spill Storage](../features/spill.md).

### Where do spill files land? How do I clean them up?

By default they land in a private 0700 temporary directory (per process); configuring `root` for `spill-local` places them in a known retained location. Local spill files persist until externally cleaned; there is no age-based retention policy (see [Spill Storage](../features/spill.md)).

### Difference between /feedback and message feedback?

Two contracts: the command `/feedback <text>` appends a read-only `feedback/record` event to the session log (log-only); message feedback (`ctx.messageFeedback`) is an editable rating/note sidecar bound to a single assistant message, stored in the storage realm. Neither enters the model context. See [Feedback](../features/feedback.md).

### What is .anonymous-user-id?

The anonymous user ID (a random UUID), used for telemetry statistics; deleting the file resets the identity.

### Where are sessions recorded?

`~/.dsh/sessions/` (zstd-compressed by default, filename follows the format version: `session.vN.jsonl.zstd`, two-level directory); deleting the directory clears them (see [Sessions](../learn/core/session.md)).

## 5. Error Troubleshooting

| Error / Symptom | Solution |
| --- | --- |
| SANDBOX_UNAVAILABLE: ... refusing to run the command unconfined | Backend unavailable; install bwrap/Landlock or switch to danger-full-access (see Sandbox) |
| rewind summary (...) is not smaller than the folded region (...) | Third-party tool-rewind SHRINK; enlarge the region / switch summary model / uninstall |
| Plugin panel / settings not fully shown | Check the browser console + compare --dump-config; missing client package = bundle not fully installed |
| Model not responding | Check .env key, whether provider/model are configured |

## 6. Execution and Terminal

### Difference between terminal and bash?

`bash` is a one-shot command wrapper (each call runs a managed subprocess, no cross-call state); PTY (`ctx.terminals` + `terminal-bash` + `tool-terminal`) is a persistent, owner-scoped interactive terminal session whose state persists across tool calls and supports interactive stdin. PTY is not mounted by default. See [Subprocess and Terminal](../features/subprocess.md).

### How often are sessions flushed to disk? What is lost on a crash?

`session-checkpoint-policy` forces a flush at three boundaries: before model requests, before tool external side effects, and at each step boundary; eager background write-behind plus the `session/flush` barrier back it up. Mounting only a persistence backend without this policy may lose writes within the batching window on a crash (see [Session System](../learn/core/session.md)).

## 7. Choosing a harness

### How do I choose between DSH and Claude Code / Codex?

Look at four variables: open-source auditability, model lock-in, cost model, and extension mechanism. DSH is the only one of the three that is open source (MIT), runs locally, and accepts any OpenAI-compatible model endpoint — at the cost of breaking changes during the Developer Preview. Claude Code / Codex are out-of-the-box and stable, but closed and bound to their vendor's models by default. The feature lists converge; there is no point comparing them line by line. Full analysis: [DeepSeek Harness vs Claude Code vs Codex](../guides/dsh-vs-claude-code-vs-codex.md).

### Is DSH an official DeepSeek project?

Yes. The repository lives in the `deepseek-ai` org, the README credits DeepSeek AI, and it is MIT-licensed; source is `0.1.5-alpha.1` (`5dda764ed3`), while npm `latest` / `next` remain `0.1.2-rc.1` (`alpha` channel: `0.1.5-alpha.1`) as of 2026-09-09; it remains Developer Preview with breaking changes. This site is a community tutorial site with no affiliation (see the [status page](../guides/deepseek-harness-status.md)).

### Is DSH production-ready?

The official status is Developer Preview (breaking changes expected), but the privacy baseline is solid: loopback-only listener, 0600-managed credentials, restricted sandbox by default. Three disciplines for production: pin versions, read changelogs before upgrading, and verify the composition tree with `dsh web --dump-config` (see the [status page](../guides/deepseek-harness-status.md) and [Sandbox & security](../learn/core/sandbox-security.md)).

## Still have questions?

- Visit the [Learning Path](../getting-started/learning-path.md) to find the page at the matching depth

- Report issues to the [Issues Board](https://github.com/dsh-external/issues)
