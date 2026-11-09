# Plugin Anatomy

- 
- Concepts Course
- Core Mechanisms
- Plugin Anatomy
On this page

# Plugin Anatomy

**One-liner**: a DSH plugin = a cordis plugin (`apply(ctx, config)` or a class) + a `dsh`-field manifest in package.json: it declares capabilities (`inject`), what it contributes, and which layer it mounts on. Almost every DSH capability is stacked out of plugins.

**Audit baseline 0.1.5-alpha.1 @ 5dda764ed3**: manifest fields, patch semantics, and resolution order are all verified point-by-point against the official source.

Read this page and you'll understand "what a plugin really is, what forms exist, how the patch layer works, and how dependencies resolve". For hands-on writing see the [dev series](../../learn/dev/hello-plugin.md).

## Contents

- [1. What a plugin means in DSH](#1-what-a-plugin-means-in-dsh)
- [2. Plugin forms](#2-plugin-forms)
- [3. Minimal plugin](#3-minimal-plugin)
- [4. Two plugin forms: function vs class](#4-two-plugin-forms-function-vs-class)
- [5. inject and capability safety](#5-inject-and-capability-safety)
- [6. Patch-layer semantics (getting these right matters)](#6-patch-layer-semantics-getting-these-right-matters)
- [7. Mounting and reconcile: dsh plugin](#7-mounting-and-reconcile-dsh-plugin)
- [8. Dependency resolution (rescope)](#8-dependency-resolution-rescope)
- [9. Verification](#9-verification)
- [Next steps](#next-steps)

---

## 1. What a plugin means in DSH

DSH's philosophy is "**everything is a plugin**": tools, services, event listeners, UI panels are all plugins. A plugin is essentially two things:

```text
① a cordis plugin (function apply(ctx, config)   or  class extends Service)

② a manifest declaration (the dsh field in package.json) — tells the loader how it mounts and what it depends on
```

The framework (`@deepseek-ai/cordis`, a vendored composition framework) handles: dependency injection, plugin loading, lifecycle, and scoping.

## 2. Plugin forms

| Form | Declaration | Role |
| --- | --- | --- |
| Bundle plugin | dsh.bundle.patch | carries its own patch layer, joined into the profile as one layer |
| Client / dual-face | dsh.client + exports["./client"] | has both a node half and a browser half |
| Profile dependency | dsh.profile.bundles | declares which bundles a profile depends on |

**There's no `dsh.plugin.json` file**: the only real manifest is the `dsh` field in package.json. The repository plugins' `.dsh-plugin` directory format belongs to the external plugin-registry mechanism, not DSH core; see [Plugins](../../user-guide/plugins.md).

### Client / dual-face plugins

One package can provide both a host half and a client half (browser):

- host half (node): scans the host Loader entries to compose the `window.__DSH_BOOT__` boot map and serves `/plugins/<id>/client.js`

- client half (browser): **a lazy CJS module table**: side effects run only on **first require**

- declaration: `exports["./client"]` + `dsh.client`

See [Web UI Architecture](../../learn/core/web-ui.md) for details.

## 3. Minimal plugin

```ts
import { Context } from '@deepseek-ai/cordis'

export const name = 'my-plugin'

export const inject = ['tools']          // declare dependencies: undeclared access is denied

export function apply(ctx: Context, config: {greeting: string}) {

  const dispose = ctx.tools.register({

    name: 'say_hello',

    description: 'Greet someone by name.',

    parameters: { text: { type: 'string', required: true } },

    output: {

      schema: { type: 'string' },

      render(_args, value) {

        return [{ type: 'text', text: typeof value === 'string' ? value : 'ok' }]

      },

    },

    async execute({ text }) {

      return { content: `${config.greeting} ${text}` }

    },

  })

  // ctx.plugin(...) / return cleanup ...

}
```

## 4. Two plugin forms: function vs class

| Form | Style | Dependency declaration | Typical |
| --- | --- | --- | --- |
| function | export function apply(ctx, config) | export const inject = [...] | mount tools / listen to events, stateless |
| class | class extends Service | static inject + @Inject | provide a service capability (see Writing a Service) |

- a class plugin's dependencies are read from `static inject` and normalized through `Inject.resolve`, a **different source** from `apply`'s `inject`

- the `@Inject` decorator declares on class properties/methods; it can also add `config` to `inject` on functions

## 5. inject and capability safety

- plugins **statically declare** the services to inject at load time (array or object)

- access to undeclared services is denied by the context proxy (Proxy): **capability-based**

- dependencies are declared **statically**, so the loader can examine and approve them at load time

- injection is "declare first, then use"; dynamically-but-injected services can be fetched asynchronously with `ctx.inject(['x'], cb)`

This relates to, but is not the same as, the security boundary: `inject` governs "whether you can reach this service at all"; permissions/sandbox govern "whether what you do is allowed". See [Sandbox & Security](../../learn/core/sandbox-security.md).

## 6. Patch-layer semantics (getting these right matters)

`cordis.patch.yml` is a **top-level YAML array**; each entry has only two operations:

- **`insert`** (indented sub-list): append 1+ rows to a target group, keyed by id

- **override an entire row by id**: without `insert`, `id` locates an existing row and can change `name`/`config`/`disabled`/`inject`/`group`/`isolate`/`intercept`

Three constraints that are easy to trip on:

| Constraint | Explanation |
| --- | --- |
| config is a whole-row replacement, not a deep merge | the fields the patch gives are exactly what the plugin receives (missing ones use schema defaults) |
| name mismatch → warn, then skip | if the patch has a name that doesn't match the target row, the loader only warns and the entry becomes ineffective; an id that matches no row also only warns |
| there's no replace/ignore verb | rows inserted by insert can later be configured/disabled by id via a later patch |

### Complete application order

```text
profile.bundles (bundle patches in order; the base's win32 shell rows are platform-gated here too)

 → the profile's own cordis.patch.yml

 → $DSH_HOME/cordis.patch.yml (machine-level, overrides every profile)

 → --patch overlays

 → telemetry toggle
```

All layers are **flattened into one list** and applied once (`applyEntryPatches`), later layers overriding earlier ones. The root `cordis.yml` is rewritten to an empty entry list `[]` on every startup: the real config tree is **100% composed from the patch layers**.

## 7. Mounting and reconcile: dsh plugin

`dsh plugin --profile <name> <args>` is a **very thin pnpm forwarder**:

```text
first use → initProfile (directory + package.json + empty patch + pnpm-workspace.yaml)

   → run pnpm <args> in the profile directory

   → reconcile the dsh.profile.bundles layer list against the installed state

      (dependencies resolving to packages that declare dsh.bundle → join the layer stack; dependencies removed / without a bundle → leave)
```

It reconciles **by installed state, not by dependency diff**: so an `update` can activate a package that "only gained a `dsh.bundle` declaration in the new version".

## 8. Dependency resolution (rescope)

- the framework is vendored and **published only as `@deepseek-ai/*` scoped packages** (`vendor/cordis`'s package name is `@deepseek-ai/cordis`)

- plugins should `import ... from '@deepseek-ai/cordis'`, `z from '@deepseek-ai/schemastery'`

- the new loader's load closure contains only `@deepseek-ai/*` packages; a plugin using the bare names `cordis`/`schemastery` without its own dependency cannot resolve them

- workaround: install the missing bare-name dependency in the plugin's own directory

- the profile directory: `bundle name dual-anchor resolution` (install directory first, then profile) + the `$DSH_HOME/profiles/node_modules` flat-closure fallback, so out-of-tree plugins resolve to the same cordis instance

## 9. Verification

```sh
# inspect plugin mounting and layer-source comments in the composition tree

dsh web --dump-config | grep -B1 -A2 "my-plugin"

# inspect a profile's bundle layer list

node -e "console.log(require('./profiles/web/package.json').dsh?.profile?.bundles)"
```

## Next steps

- [Write your first plugin](../../learn/dev/hello-plugin.md): get hands-on

- [Event System](../../learn/core/event-system.md): how plugins communicate

- [Agent Presets](../../features/persona.md): compose a set of plugins for an agent with a preset
