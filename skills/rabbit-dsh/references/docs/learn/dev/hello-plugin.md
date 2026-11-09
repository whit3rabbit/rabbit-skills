# Your First Plugin

- 
- Concepts Course
- Plugin Development
- Your First Plugin
On this page

# Your First Plugin

**In one sentence**: a plugin = a module exporting `name`/`apply(ctx, config)` + the `dsh` manifest field in package.json + mounting it into a profile: from hello world to usable in ten minutes.

This is the hands-on companion to [Plugin anatomy](../../learn/core/plugin-anatomy.md). The practical loop mirrors the official tutorial [docs/user/develop/basic](https://github.com/deepseek-ai/deepseek-harness/blob/master/docs/user/develop/basic/index.md) (this lesson), `tool.md`, `config.md`, `publish.md`. By the end you will be able to write, mount, and verify a plugin.

## Contents

- [0. Prerequisites](#0-prerequisites)
- [1. The shape of a plugin](#1-the-shape-of-a-plugin)
- [2. A minimal plugin (listening to one event)](#2-a-minimal-plugin-listening-to-one-event)
- [3. The official scratch mount flow (--patch overlay)](#3-the-official-scratch-mount-flow-patch-overlay)
- [4. A more complete example (with config + a tool)](#4-a-more-complete-example-with-config-a-tool)
- [5. Automatic cleanup and ctx.effect](#5-automatic-cleanup-and-ctxeffect)
- [6. Three plugin forms](#6-three-plugin-forms)
- [7. The manifest declaration (package.json)](#7-the-manifest-declaration-packagejson)
- [8. Mount modes (choose one)](#8-mount-modes-choose-one)
- [9. Profile directories and closure resolution](#9-profile-directories-and-closure-resolution)
- [10. The dev loop](#10-the-dev-loop)
- [11. Common pitfalls](#11-common-pitfalls)
- [Next steps](#next-steps)
- [References](#references)

---

## 0. Prerequisites

- **Node**: `^22.19.0 || >=24.0.0` (official root `package.json#engines`, audit baseline 0.1.5-alpha.1 @ 5dda764ed3)

- **Source checkout**: the scratch mount flow requires completing the run-from-source path in the official README (clone + `pnpm install` + `pnpm run build`), then using `pnpm dsh …` from the checkout root; a CLI-only install runs via `npx @deepseek-ai/dsh web` (see [Quickstart](../../getting-started/quickstart.md))

- Package manager: pnpm (recommended)

## 1. The shape of a plugin

A DSH plugin is essentially a **cordis plugin**: a module exporting `name` and `apply(ctx, config)` (or a class extending `Service`), plus a `dsh` manifest field in package.json that tells the loader "how to mount it, and what it depends on".

```text
my-plugin/

├── package.json        # manifest (including the dsh declaration)

├── src/index.ts        # plugin body

└── (optional) cordis.patch.yml   # only needed for bundle-type: which rows to insert
```

## 2. A minimal plugin (listening to one event)

```ts
import { Context } from '@deepseek-ai/cordis'

export const name = 'hello-dsh'

export function apply(ctx: Context) {

  ctx.on('session/created', () => {

    console.log('[hello-dsh] New session!')

  })

}
```

- `name` is the plugin's unique id in the composition (also used for patch targeting)

- `apply(ctx, config)` is the entry point; registered listeners/tools are cleaned up automatically when the calling fiber unloads

## 3. The official scratch mount flow (--patch overlay)

The official "first plugin" tutorial's main path: write the plugin in a scratch directory, then insert it into the Web composition with a `--patch` overlay — **no packaging needed**:

```sh
# From the Harness repository root

mkdir -p scratch-plugin/src
```

Write `scratch-plugin/src/my-plugin.ts`:

```ts
import type { Context } from '@deepseek-ai/cordis'

export const name = 'hello-plugin'

export function apply(ctx: Context) {

  // Required dependencies are ready before apply runs.

  console.log('[hello-plugin] plugin loaded!')

}
```

Run `pwd` from the repository root and fill the printed absolute path into `scratch-plugin/cordis.yml`:

```yaml
- insert:

    - id: hello

      name: '/absolute/path/to/deepseek-harness/scratch-plugin/src/my-plugin.ts'
```

Start and verify:

```sh
pnpm dsh web --patch ./scratch-plugin/cordis.yml

# Open http://127.0.0.1:3080 — the terminal prints [hello-plugin] plugin loaded!
```

Two constraints (from the official text):

- The plugin path **must be absolute**

- A patch file contributes configuration but **does not change** the profile directory the loader uses to resolve module paths

This is the same YAML syntax bundle plugins ship on the patch layer (`- insert:` + `id`/`name`); the only difference is `name` holds a local source-file path instead of a package name. See [Plugin anatomy](../../learn/core/plugin-anatomy.md).

## 4. A more complete example (with config + a tool)

```ts
import { Context } from '@deepseek-ai/cordis'

import { defineTool } from '@deepseek-ai/dsh-tools'

export const name = 'greeter'

export const inject = ['tools']            // declare that you use tools

export function apply(ctx: Context, config: { greeting: string }) {

  ctx.tools.register(defineTool({

    name: 'say_hi',

    description: 'Greet according to the plugin-configured greeting',

    parameters: { to: { type: 'string' } },

    output: { schema: { type: 'string' }, render: (_a, v) => [{ type: 'text', text: String(v) }] },

    async execute({ to }) {

      return `${config.greeting}, ${to}!`   // matches output.schema:{type:'string'}, returns a string

    },

  }))

}
```

Once mounted, the model gains a `say_hi` tool whose return value carries your greeting. Real config validation and defaults use a Schemastery schema (see [Config & publish](../../learn/dev/config-publish.md)); the inline type here only serves the demo.

## 5. Automatic cleanup and ctx.effect

Anything registered through `ctx` — event listeners, tools, timers — is **cleaned up automatically** when the plugin unloads; you never need removeListener / clearInterval by hand. For resources that need manual release (network connections, file handles), hand `ctx.effect()` a disposer:

```ts
import type { Context } from '@deepseek-ai/cordis'

export function apply(ctx: Context) {

  ctx.effect(() => {

    const timer = setInterval(() => {

      console.log('heartbeat')

    }, 5000)

    // The returned function runs when the plugin unloads.

    return () => clearInterval(timer)

  })

}
```

## 6. Three plugin forms

The function form is sufficient in most cases; use the class form when the plugin provides a service to other plugins (see [Plugin anatomy](../../learn/core/plugin-anatomy.md) and [Write a service](../../learn/dev/write-service.md)). The object form sits between the two:

```ts
import type { Context } from '@deepseek-ai/cordis'

export default {

  name: 'my-plugin',

  inject: ['tools'],

  apply(ctx: Context) {

    // ...

  },

}
```

Class-form essentials: call `super(ctx, 'myService')` in the constructor, and initialization must be synchronous.

## 7. The manifest declaration (package.json)

```json
{

  "name": "@dsh-external/my-plugin",

  "main": "lib/index.js",

  "exports": { ".": "./lib/index.js" },

  "dsh": { "bundle": { "patch": "./cordis.patch.yml" } }

}
```

- `dsh.bundle.patch` = declares this is a **bundle-type plugin** + the patch file it carries (a single string path, not an array)

- Other forms (`dsh.client`, `dsh.profile.bundles`) are in [Plugin anatomy](../../learn/core/plugin-anatomy.md)

## 8. Mount modes (choose one)

```sh
# 1. Bundle type: one git-source line

dsh plugin --profile web add "github:dsh-external/my-plugin#main"

# 2. Local directory development

dsh plugin --profile web add link:/path/to/my-plugin

# 3. Manual mount on the patch layer (cordis.patch.yml) — same syntax as the scratch flow in section 3

- insert:

    - id: hello-dsh

      name: '@dsh-external/my-plugin'
```

## 9. Profile directories and closure resolution

`dsh plugin --profile <name> ...` essentially **forwards pnpm in the profile directory**:

- bundle names are **dual-anchor resolved** (install directory first, then profile)

- startup maintains a flat-closure fallback at `$DSH_HOME/profiles/node_modules`, so out-of-tree plugins resolve to the **same** cordis instance

- bundles listed in `dsh.profile.bundles` are activated automatically on reconcile

This is also why "bare-name dependencies fail to resolve": the framework closure only contains `@deepseek-ai/*`. See [Plugin anatomy](../../learn/core/plugin-anatomy.md).

## 10. The dev loop

```sh
# Build TS (tsdown/tsc)

pnpm build

# Verify the plugin appears in the composition

dsh web --dump-config | grep hello-dsh

# Restart to take effect (bundle-type needs a restart; --patch overlay changes do too)

dsh web
```

**Hot-update boundary** (verified against source): each boot, only the profile's own `cordis.patch.yml` is kept live by `watchUserPatches` — editing it unloads the old plugin instance and loads the composition with the new config (a failed read/parse keeps the last good tree and broadcasts `hmr/config-update-failed`). Changes to `--patch` overlays and bundle patch files need a restart.

## 11. Common pitfalls

| Pitfall | Fix |
| --- | --- |
| Bare-name cordis/schemastery fails to resolve | Use @deepseek-ai/cordis; if necessary, install the bare name into the plugin's own node_modules |
| Accessing a service without declaring inject | Proxy rejection: inject: ['tools'] first, then ctx.tools |
| Patch-layer name mismatch | Silently skipped, row doesn't take effect: check whether id/name matches the target row |
| config is full-row replacement | Fields missing from the patch take schema defaults; don't expect deep merge |
| Relative path in --patch | The official tutorial requires an absolute path: compose it from pwd |
| Exporting a Config interface without the same-named schema | No validation, no defaults; the official docs require exporting a Schemastery schema (see Config & publish) |

## Next steps

- [Write a tool](../../learn/dev/write-tool.md): give the model a callable capability

- [Config & publish](../../learn/dev/config-publish.md): the Config schema and bundle distribution

- [Plugin anatomy](../../learn/core/plugin-anatomy.md): forms and patch semantics

- [Event system](../../learn/core/event-system.md): how plugins communicate

## References

- Official tutorial: [docs/user/develop/basic](https://github.com/deepseek-ai/deepseek-harness/blob/master/docs/user/develop/basic/index.md) (this lesson is verified point-by-point against the 0.1.5-alpha.1 source)

- Community write-up: [How-DSH-Plugin-Made](https://github.com/yauntyour/skills/blob/main/How-DSH-Plugin-Made.md) (the scratch mount flow and structure of this lesson reference that document)
