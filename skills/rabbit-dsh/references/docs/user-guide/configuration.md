# Configuration

**Short version**: DSH configuration is **stacked in layers**: bundle layer → profile layer → user patch layer, where the latter overrides the former; what a user can change at runtime lives in `settings.yaml`.

This section explains "where to change, which layer takes effect, and how to diagnose".

## Contents

- [1. Profile](#1-profile)
- [2. What to write in the patch layer](#2-what-to-write-in-the-patch-layer)
- [3. Global settings ~/.dsh/settings.yaml](#3-global-settings-dshsettingsyaml)
- [4. Credentials](#4-credentials)
- [5. LLM provider configuration](#5-llm-provider-configuration)
- [6. How to diagnose "my change didn't take effect"](#6-how-to-diagnose-my-change-didnt-take-effect)
- [7. Common configuration targets quick reference](#7-common-configuration-targets-quick-reference)
- [Next steps](#next-steps)

---

## 1. Profile

Each profile (`web` / `headless` / a custom `tui`) is its own directory:

```text
~/.dsh/profiles/web/

├── cordis.yml          # Entry file (empty list; do not edit; rewritten as an empty base on every start)

├── cordis.patch.yml    # User mounting layer: plugin inserts/overrides go here

├── package.json        # Dependencies + dsh.profile.bundles (the bundle-layer list)

├── pnpm-lock.yaml

├── pnpm-workspace.yaml # Needed for out-of-tree plugins

└── node_modules/
```

**Composition order**:

- The bundles listed in `dsh.profile.bundles` (each with its own patch)

- `cordis.patch.yml` (manually mounted plugins)

- `--patch` command-line overrides

The root `cordis.yml` serves only as an empty base; the real config tree is **100% composed from patch layers** (see [Plugin Anatomy](../learn/core/plugin-anatomy.md)).

## 2. What to write in the patch layer

```yaml
# ~/.dsh/profiles/web/cordis.patch.yml

- insert:                       # Manually mount a DSH kernel tool

    - id: schedule

      name: '@deepseek-ai/dsh-schedule'

- id: session-telemetry-otel      # Override a plugin's config by id

  name: '@deepseek-ai/dsh-session-telemetry-otel'

  config:

    mode: FULL                  # Enum uppercase: FULL / FEEDBACK_ONLY / DISABLED
```

Three constraints (getting these right matters; see [Plugin Anatomy](../learn/core/plugin-anatomy.md)):

- `config` is a **full-line replacement**, not a deep merge

- A mismatched `name` → **silently skipped**

- A patch is located by **entry id**, not required to equal the registered name

## 3. Global settings ~/.dsh/settings.yaml

A patch is a static layer written by the deployer; **what a user can change at runtime** lives in `settings.yaml` (hot-published by `dsh-settings-file`, editable by the user in the UI):

# Default route (deployment default: shared by the web / headless / API entry points)

agent-default-model:
provider: deepseek-official
model: deepseek-v4-flash

# Custom provider (llm-pi-ai gateway)

llm-pi-ai:
providers:
cpa:
apiKeyEnv: CPA_API_KEY
api: openai-completions
baseURL: [http://example.gw:8317/v1](http://example.gw:8317/v1)
models:

- id: gpt-5.6-sol

# Permission preset

permission:
defaultPreset: danger-full-access

```text
**Difference between patch and settings**:

| | patch layer | settings.yaml |

|---|---|---|

| Who writes | Deployer (cordis.patch.yml) | User at runtime |

| How changed | Edit file, restart | UI / hot-published file |

| Semantics | Static config/mounting | Dynamic user settings |

## 4. Credentials

| File | Content | Permissions |

|---|---|---|

| `~/.dsh/.credentials.yaml` | Managed structured credentials | 0600 (0700 directory) |

| `~/.dsh/.env` | Env-layer fallback | Permissions self-managed |

Managed credentials go into `.credentials.yaml` (DSH writes it atomically at 0600); `.env` is an ordinary env layer (process env > working-dir `.env` > `~/.dsh/.env`), where secrets can also be placed at your own risk. See [Credential Management](./credentials.md) and [Data and Privacy](./privacy.md).

## 5. LLM provider configuration

Providers are managed on the Models settings page. Two shapes:

- **`llm-deepseek`**: flat top level (official chat-completions)

- **`llm-pi-ai`**: a `providers` dictionary (multiple OpenAI-compatible endpoints)

```yaml

llm-pi-ai:

  providers:

    <provider-id>:

      apiKeyEnv: <env>

      api: openai-completions

      baseURL: <endpoint>

      models:

        - id: <model name>
```

Built-in providers: `deepseek-official` (api.deepseek.com), a standalone Anthropic endpoint for web search (`web-search-deepseek`), and any OpenAI-compatible endpoint (custom gateway; watch out for plaintext-HTTP risk). See [Multi-Model](../features/multi-model.md).

## 6. How to diagnose "my change didn't take effect"

```sh
dsh web --dump-config              # Inspect the composition tree + per-line source comments (which layer overrides which)

dsh web --dump-default-config      # Bundle layer only
```

`--dump-config` is the authoritative diagnostic tool (see [Command Line](../user-guide/cli.md)).

## 7. Common configuration targets quick reference

| What to change | Where to write |
| --- | --- |
| Default model / route | agent-default-model in settings.yaml |
| Add a provider | llm-pi-ai.providers in settings.yaml |
| Permission preset | permission.defaultPreset in settings.yaml |
| Mount/unmount plugins | cordis.patch.yml |
| provider keys | ~/.dsh/.credentials.yaml (managed) or environment variables |

## Next steps

- [Command Line](../user-guide/cli.md): how to view/change configuration with commands

- [Multi-Model](../features/multi-model.md): provider configuration

- [Plugins](../user-guide/plugins.md): patch layer specifics
