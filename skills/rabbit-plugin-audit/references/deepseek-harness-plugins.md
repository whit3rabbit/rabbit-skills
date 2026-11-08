# DeepSeek Harness Plugin Architecture & Development Guide

Comprehensive technical guide for authoring, configuring, and packaging plugins for DeepSeek Harness (DSH) built on the Cordis composition runtime.

- **Framework:** Cordis / DeepSeek Harness
- **Documentation:**
  - Plugins User Guide: https://deepseekdocs.com/en/docs/user-guide/plugins
  - Plugin Anatomy: https://deepseekdocs.com/en/docs/learn/core/plugin-anatomy
  - Hello Plugin Guide: https://deepseekdocs.com/en/docs/learn/dev/hello-plugin
  - Basic Development: https://github.com/deepseek-ai/deepseek-harness/blob/master/docs/user/develop/basic/index.md
  - Tool Authoring: https://deepseekdocs.com/en/docs/learn/dev/write-tool
  - Event System: https://deepseekdocs.com/en/docs/learn/core/event-system
  - Persona & Agent Presets: https://deepseekdocs.com/en/docs/features/persona
  - Configuration & Publishing: https://deepseekdocs.com/en/docs/learn/dev/config-publish
  - Typert Contract Authoring: https://deepseekdocs.com/en/docs/learn/dev/typert-authoring

## Contents

- [Mental Model: Everything is a Plugin](#mental-model-everything-is-a-plugin)
- [Plugin Anatomy](#plugin-anatomy)
- [Bundle Manifest and Layout](#bundle-manifest-and-layout)
- [Configuration Patch Layer (`cordis.patch.yml`)](#configuration-patch-layer-cordispatchyml)
- [Authoring Tools (`defineTool`)](#authoring-tools-definetool)
- [Event System and Lifecycle](#event-system-and-lifecycle)
- [Authoring Typert RPC Contracts](#authoring-typert-rpc-contracts)
- [Personas and Agent Presets](#personas-and-agent-presets)
- [CLI Plugin Management](#cli-plugin-management)
- [DSH Pre-Publishing Checklist](#dsh-pre-publishing-checklist)
- [Best Practices and Quality Checklist](#best-practices-and-quality-checklist)

---

## Mental Model: Everything is a Plugin

DeepSeek Harness does not use a monolithic core with bolted-on extensions. Instead, it is built on **Cordis**, a spatio-temporal plugin composition framework:

- **No Base Classes:** You do not extend framework classes. Everything interacts through the `Context` (`ctx`) instance passed into your entry point.
- **Context Isolation and Scoping:** Services and hooks registered through `ctx` belong to that plugin's scope.
- **Automatic Teardown:** When a plugin is disabled or reloaded, Cordis automatically unbinds all event listeners, timers, tools, and injected services registered through `ctx`—preventing memory leaks or ghost handlers.
- **Dependency Tracking (`inject`):** Plugins declare required services (such as `tools`, `persona`, `database`) in an `inject` array. The framework loads plugins only after their dependencies become available.

---

## Plugin Anatomy

At minimum, a DeepSeek Harness plugin is a JavaScript or TypeScript module exporting:
1. `name`: Unique plugin identifier.
2. `apply(ctx, config)`: Lifecycle activation function.
3. `inject`: (Optional) List of service dependencies.
4. `Config`: (Optional) Schema validation for user-provided options.

```typescript
import type { Context } from '@deepseek-ai/cordis'

export const name = 'my-sample-plugin'
export const inject = ['tools']

export interface Config {
  prefix?: string
}

export function apply(ctx: Context, config: Config = {}) {
  const prefix = config.prefix || '[sample]'
  ctx.logger.info(`${prefix} Plugin initialized successfully`)
}
```

---

## Bundle Manifest and Layout

A publishable or locally linked DeepSeek Harness plugin is structured as an npm package bundle:

```text
my-dsh-plugin/
├── package.json          # Package manifest declaring the dsh.bundle configuration
├── cordis.patch.yml      # Configuration layer applied when loaded into a profile
├── tsconfig.json         # TypeScript compiler configuration
├── src/
│   ├── index.ts          # Main entrypoint exporting name and apply()
│   ├── tools.ts          # Custom tool registrations
│   └── events.ts         # Event listeners and handlers
└── README.md
```

### `package.json` Manifest Format

A DSH plugin declares its bundle patch in `package.json` using the `dsh` key:

```json
{
  "name": "dsh-plugin-code-tools",
  "version": "1.0.0",
  "description": "Code intelligence and analysis tools for DeepSeek Harness",
  "type": "module",
  "main": "dist/index.js",
  "types": "dist/index.d.ts",
  "files": [
    "dist",
    "cordis.patch.yml"
  ],
  "dsh": {
    "bundle": {
      "patch": "./cordis.patch.yml"
    }
  },
  "peerDependencies": {
    "@deepseek-ai/cordis": "^1.0.0",
    "@deepseek-ai/dsh-tools": "^1.0.0"
  }
}
```

> [!NOTE]
> Distributable extensions declare `"dsh": { "bundle": { "patch": "./cordis.patch.yml" } }`. In contrast, profile definitions in `~/.dsh/profiles/<profile>/package.json` declare `"dsh": { "profile": { "bundles": [...] } }`.

---

## Configuration Patch Layer (`cordis.patch.yml`)

The patch file describes how the plugin inserts itself into the composed Cordis runtime tree:

```yaml
- insert:
    - id: code-tools
      name: dsh-plugin-code-tools
      disabled: false
      config:
        enableLinting: true
        maxFileSizeKb: 512
```

- **`insert`**: Action adding new nodes to the plugin composition tree.
- **`id`**: Unique instance identifier within the configuration tree.
- **`name`**: Package or module name matching the entry in `package.json` or local path.
- **`disabled`**: (Optional) Boolean flag to toggle execution without removing the configuration.
- **`config`**: (Optional) Object holding configuration values passed to `apply(ctx, config)`.

---

## Authoring Tools (`defineTool`)

DeepSeek Harness provides native agent tool authoring via `@deepseek-ai/dsh-tools`.

### Tool Definition Structure

```typescript
import type { Context } from '@deepseek-ai/cordis'
import { defineTool } from '@deepseek-ai/dsh-tools'

export const name = 'code-inspector-tool'
export const inject = ['tools']

export function apply(ctx: Context) {
  ctx.tools.register(
    defineTool({
      name: 'inspect_symbol',
      description: 'Look up symbol references and definitions across the active workspace.',
      parameters: {
        symbol: {
          type: 'string',
          required: true,
          description: 'The identifier or symbol name to search.',
        },
        exact: {
          type: 'boolean',
          required: false,
          description: 'Whether to perform exact matching.',
        },
      },
      output: {
        schema: {
          type: 'object',
          properties: {
            matches: { type: 'array' },
            count: { type: 'number' },
          },
        },
        render: (_args, value) => [
          {
            type: 'text',
            text: `Found ${value.count} matches for symbol inspection.`,
          },
        ],
      },
      async execute(args) {
        const results = await ctx.tools.search(args.symbol, { exact: args.exact })
        return {
          matches: results,
          count: results.length,
        }
      },
    })
  )
}
```

### Key Tool Components

1. **Parameters:** Strict parameter typing using `type` (`string`, `number`, `boolean`, `array`, `object`), `required`, and descriptive comments.
2. **Output Schema & Render:** Declares structured output format and provides a `render()` callback producing human-readable text representations for chat interfaces.
3. **Async Execution:** `execute(args)` runs asynchronously in the harness runtime environment.

---

## Event System and Lifecycle

The event system connects decoupled plugins across lifecycle steps, tool invocations, and agent turns.

### Registering Listeners (`ctx.on`)

Listeners attached through `ctx.on` are strictly scoped to the plugin lifecycle:

```typescript
import type { Context } from '@deepseek-ai/cordis'

export const name = 'audit-listener'

export function apply(ctx: Context) {
  // Listen for tool execution results
  ctx.on('tools/result', (event) => {
    ctx.logger.info(`Tool ${event.name} finished in ${event.durationMs}ms`)
  })

  // Listen for agent turn completions
  ctx.on('turn/finish', (event) => {
    ctx.logger.info(`Turn ${event.turnId} completed with status ${event.status}`)
  })
}
```

### Event Interaction Modes

- **Broadcast (`ctx.emit`):** Listeners execute concurrently or sequentially without altering the payload.
- **Waterfall / Interception:** Core lifecycle hooks (e.g. `agent/pre-step`, `tools/before-call`) receive a `next()` continuation callback, allowing plugins to inspect, rewrite arguments, or abort operations safely.

### Type Safety via Module Augmentation

TypeScript plugins declare custom events by extending `@deepseek-ai/cordis`:

```typescript
declare module '@deepseek-ai/cordis' {
  interface Events {
    'audit/violation'(ruleId: string, message: string): void
  }
}
```

---

## Authoring Typert RPC Contracts

In DeepSeek Harness, **Typert** provides the type-safe Remote Procedure Call (RPC) and schema generation framework bridging the Node.js Host runtime with browser client interfaces.

### 1. Source Annotations & Service Definitions

Public capabilities are authored by subclassing `TypertRemoteService` and annotating methods with `@Remote`:

```typescript
import { TypertRemoteService, Remote } from '@deepseek-ai/dsh-typert-protocol'

export class WorkspaceGateway extends TypertRemoteService {
  @Remote('getWorkspaceImportContext')
  async getWorkspaceImportContext(
    query: string,
    signal: AbortSignal
  ): Promise<{ status: string; count: number }> {
    // Host execution and permission authorization
    return { status: 'ready', count: 1 }
  }
}
```

### 2. Generator Pipeline & Package Exports

Typert relies on build-time static analysis via `@deepseek-ai/dsh-typert-generator`:
- Analyzes TypeScript source code, validating that parameter types, returns, and projections map cleanly to Schemastery and Zod schema factories without runtime drift.
- Opt into generation by declaring `./typert` exports in `package.json`:

```json
{
  "exports": {
    ".": "./dist/index.js",
    "./typert": "./dist/typert/index.js"
  }
}
```

### 3. Runtime Integration & Atomic Registration

The consumer-side `dsh-typert-registry` loads lazy Zod schema factories and remote descriptors:
- **Queryable Reflection:** Capabilities are queried dynamically under stable namespaced keys.
- **Fiber-Scoped Effects:** Registrations are managed through Cordis effects—registering atomically at boot and unregistering cleanly when components unload.

---

## Personas and Agent Presets

DeepSeek Harness separates models from agent personas and presets through `@deepseek-ai/dsh-persona` and `@deepseek-ai/dsh-agent-presets`.

### Agent Presets (`agent.cordis.yml`)

An agent preset specifies fixed capability compositions—including prompt sections, bound tools, and personas:

```yaml
# ${DSH_HOME}/.agent-presets/code-reviewer/agent.cordis.yml
name: code-reviewer
description: Strict security and architectural code reviewer
persona:
  role: Senior Staff Security Architect
  tone: Direct, thorough, and evidence-driven
  instructions: |
    - Always verify bounds checks and input validation.
    - Emphasize zero-trust architecture and defensive programming.
tools:
  - inspect_symbol
  - run_linter
```

### Scope Resolution Hierarchy

When executing a prompt or tool call, DSH resolves settings along an inheritance chain:
1. **Agent Instance Scope:** Active session parameters and overrides.
2. **Preset Scope:** Settings declared in `agent.cordis.yml`.
3. **Global Scope:** Default runtime profile (`cordis.yml`).

---

## CLI Plugin Management

Manage plugins within DSH runtime profiles using the `dsh plugin` CLI command:

```bash
# Add a published npm plugin package to the web profile:
dsh plugin --profile web add dsh-plugin-code-tools

# Add a plugin from GitHub repository:
dsh plugin --profile web add github:owner/repo

# Link a local development plugin:
dsh plugin --profile tui add link:"/absolute/path/to/my-dsh-plugin"

# List active plugins in a profile:
dsh plugin --profile web ls

# Remove a plugin bundle from a profile:
dsh plugin --profile web remove dsh-plugin-code-tools
```

---

## DSH Pre-Publishing Checklist

Before distributing a DSH plugin bundle or submitting to a public or internal registry, verify each item against the official `config-publish` standard:

| Checklist Item | Validation Rule | Command / Inspection |
|---|---|---|
| **1. Build Artifacts** | `dist/` or `lib/` directory is compiled and declared in `files` of `package.json`. No raw TypeScript without build outputs. | `npm run build && ls dist/` |
| **2. Dependency Declarations** | All framework services (`@deepseek-ai/cordis`, `@deepseek-ai/dsh-tools`, etc.) declared under `peerDependencies` with bounded semver ranges. | Verify `package.json` |
| **3. Config Schema Validation** | Plugin exports a valid `Config` interface or Schemastery schema for options, properly handling patch overrides. | Inspect `apply(ctx, config)` |
| **4. Metadata & Provenance** | `name`, `version`, `description`, `license`, and `repository` fields are complete; `README.md` includes clear setup instructions. | `python3 audit_dsh.py . --publish-check` |
| **5. Runtime Settings & Typert** | Settings updates via `ctx.settings` stay synchronized with UI states; if `@Remote` is used, `./typert` export is present. | Inspect `exports` and `ctx.settings` |

---

## Best Practices and Quality Checklist

- [ ] **Export Standards:** Plugin module exports `name: string` and `apply(ctx: Context, config?: any)`.
- [ ] **Dependency Declaration:** All consumed services (e.g. `'tools'`, `'persona'`) are explicitly declared in `export const inject = [...]`.
- [ ] **No Memory Leaks:** Always attach event listeners and intervals via `ctx.on` and `ctx.setInterval` so Cordis can clean them up automatically on reload.
- [ ] **Safe Configuration:** Configuration defaults provided for all optional parameters.
- [ ] **No Raw Secrets:** Never hardcode API keys, passwords, or tokens in `cordis.patch.yml` or plugin code.
- [ ] **Patch Manifest Parity:** Ensure the `id` in `cordis.patch.yml` matches the intended module name and is referenced in `package.json` under `dsh.bundle.patch`.
