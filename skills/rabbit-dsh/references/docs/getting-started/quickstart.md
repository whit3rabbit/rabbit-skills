# Quickstart

**Source / npm channels (2026-09-09)**: this guide tracks official `master` at `0.1.5-alpha.1` (`5dda764ed3`); npm `latest` / `next` resolve to `0.1.2-rc.1`, and the npm `alpha` channel is `0.1.5-alpha.1`. Default `npx` launches the npm `latest` release. Build from source for the new interfaces; see [Status](../guides/deepseek-harness-status.md).

This page follows the public repository's official run path and gets you running before diving into internals (leave those to the [concepts course](../learn/intro/what-is-dsh.md) and the [learning path](../getting-started/learning-path.md)).

DSH is currently in **Developer Preview**, so updates may include compatibility-breaking changes. Treat [deepseek-ai/deepseek-harness](https://github.com/deepseek-ai/deepseek-harness) as the source of truth.

## Contents

- [What you will get out of this walk](#what-you-will-get-out-of-this-walk)
- [0. Install and check requirements](#0-install-and-check-requirements)
- [1. Configure the API key](#1-configure-the-api-key)
- [2. Launch the Web UI](#2-launch-the-web-ui)
- [3. First conversation](#3-first-conversation)
- [4. Verify and observe](#4-verify-and-observe)
- [5. Common path shortcuts](#5-common-path-shortcuts)
- [6. Common issues](#6-common-issues)
- [Next steps](#next-steps)

---

## What you will get out of this walk

By the end you will have:

- Configured a model API key

- Opened the Web UI and completed a first conversation, and seen what the "composition tree" looks like

- Learned where your data is stored

## 0. Install and check requirements

Use Node.js `^22.19.0` or `>=24.0.0`. The zero-install entry point is:

```sh
npx @deepseek-ai/dsh web
```

It starts the Web UI at `http://127.0.0.1:3080` by default. For source development:

```sh
git clone https://github.com/deepseek-ai/deepseek-harness.git

cd deepseek-harness

pnpm install

pnpm run build

pnpm dsh web
```

The rest of the docs use `dsh` for an available CLI entry point. With the zero-install path, write `npx @deepseek-ai/dsh ...` instead.

## 1. Configure the API key

When DSH starts it reads credentials by priority: process environment → `~/.dsh/.credentials.yaml` (managed storage) → working-directory `.env` → `~/.dsh/.env` (fallback).

```sh
# Option 1: write into ~/.dsh/.env (as the fallback layer)

echo "DEEPSEEK_API_KEY=sk-xxx" >> ~/.dsh/.env

# Option 2: temporary environment variable

export DEEPSEEK_API_KEY=sk-xxx
```

- The official provider is `deepseek-official`; a model such as `deepseek-v4-flash` (see [Configuration](../user-guide/configuration.md) for the default routing).

- To use another provider / your own gateway, configure `llm-pi-ai.providers` (see [Multi-model](../features/multi-model.md)).

**Credential safety**: the managed `.credentials.yaml` is written atomically by DSH with 0600 permissions (0700 directory); `.env` is a plain environment layer whose permissions are your own responsibility. Finer details live in [Credentials](../user-guide/credentials.md) and [Data & privacy](../user-guide/privacy.md).

## 2. Launch the Web UI

```sh
npx @deepseek-ai/dsh web
```

The source build opens a URL such as `http://127.0.0.1:3080/?token=...` (pass `--no-open` to skip the automatic browser handoff); the root exchanges the launch token for a browser session and redirects to a clean URL. Keep this link private.

On first launch, a versioned notice and the model-credential step run in order. The workbench then shows:

- On the left, a collapsible **Workbench sidebar** (expanded column or 56px rail)

- In the middle, a workspace to pick: the first time it asks you to choose a working directory — all DSH activity happens inside the directory you pick

- On the top right, a **light / dark theme** toggle

Web UI defaults to loopback. Current source rejects `--host 0.0.0.0` at startup; use SSH port forwarding for remote work and open the launch URL printed by the CLI.

### Can't open it? Common causes

| Symptom | Troubleshooting |
| --- | --- |
| Port is taken | dsh web --port 8080 to change the port |
| Browser did not open | Open the complete launch URL printed by the CLI, including its token |
| Page broken / blank | dsh web --dump-config to check whether the plugin tree is healthy (below) |

## 3. First conversation

Once you have selected a working directory, your first message triggers the full pipeline: the agent picks a model → assembles context → calls the model → (maybe) calls tools → writes back to the session. Everything is recorded into the session logs under `~/.dsh/sessions/` (zstd-compressed by default).

Try a question that triggers a tool, such as "**list the first 10 files in the current directory**". In the message stream you will see:

- A `user/message` (what you sent)

- Several `assistant/message`s or tool calls (`tool/call` → `tool/result`)

- The agent summarizing into an answer

What that one message goes through is the whole topic of [Agent main loop](../learn/core/agent-loop.md). Don't dig into it now — just confirm it works.

## 4. Verify and observe

```sh
# Composition tree: see which plugins DSH stacked together (the authoritative tool for "which layer overrides what")

dsh web --dump-config | head -40

# Session log (zstd-compressed by default, two-level --<cwd>--/<id>/ dirs; the current format generation is session.v3.jsonl.zstd)

zstdcat ~/.dsh/sessions/*/*/session.v3.jsonl.zstd | tail -20
```

`--dump-config` groups contiguous rows by source and prefixes each group with a `# == <label>` comment (adding `patched by …` when applicable), so you can tell whether a config came from the base layer, the web-app layer, or your profile layer.

## 5. Common path shortcuts

| Path | Purpose |
| --- | --- |
| ~/.dsh/ | Harness home (config, sessions, plugins) |
| ~/.dsh/profiles/web/ | Web profile (plugin mounts, dependencies, cordis.patch.yml) |
| ~/.dsh/sessions/ | Session logs (zstd-compressed, two-level dirs; current generation session.v3.jsonl.zstd) |
| ~/.dsh/.env | Fallback environment layer (permissions are your own; managed credentials live in ~/.dsh/.credentials.yaml, 0600) |
| ~/.dsh/settings.yaml | Global runtime settings (default model routing, permission presets, etc.) |

## 6. Common issues

| Issue | Fix |
| --- | --- |
| --dump-config errors / breaks plugins | Usually a plugin failed to parse: fail-loud tells you which one; delete the suspicious patch line and retry |
| Model doesn't respond | Check the .env key is correct and the provider/model is fully configured (see Configuration) |
| Want to switch models | See Configure models |

## Next steps

You can run now. Pick a path based on your goal:

- **Just everyday use**: [Usage guide](../user-guide/cli.md) → [Capabilities](../features/tools.md) → configure permissions

- **Understand the internals**: [What is DSH](../learn/intro/what-is-dsh.md) → [Agent main loop](../learn/core/agent-loop.md)

- **Give the model new abilities**: [Write your first plugin](../learn/dev/hello-plugin.md)

For the full map see the [learning path](../getting-started/learning-path.md).
