# Configuration and Publishing

- 
- Concepts Course
- Plugin Development
- Configuration and Publishing
On this page

# Configuration and Publishing

**In one sentence**: plugin configuration = a schemastery-defined `Config` schema (patch layer overrides by id)**, plus runtime user config through `ctx.settings`;** publishing = the `dsh` field in package.json + a mount mode, so a user installs with one line.

This is the wrap-up of the plugin development series: make your plugin configurable, distributable, and maintainable.

## Contents

- [1. The static config schema](#1-the-static-config-schema)
- [2. How users override (the patch layer)](#2-how-users-override-the-patch-layer)
- [3. Runtime user config (ctx.settings)](#3-runtime-user-config-ctxsettings)
- [4. Publishing to an org](#4-publishing-to-an-org)
- [5. bundle vs repository](#5-bundle-vs-repository)
- [6. Release checklist](#6-release-checklist)
- [7. Verifying a release](#7-verifying-a-release)
- [Course complete 🎉](#course-complete)

---

## 1. The static config schema

```ts
import z from '@deepseek-ai/schemastery'

import { Context } from '@deepseek-ai/cordis'

export const name = 'my-plugin'

export const Config = z.object({

  greeting: z.string().default('Hello'),

  maxItems: z.number().step(1).min(1).default(10),

})
```

What `apply(ctx, config)` receives is the **validated** config (`plugin.Config` is copied to runtime for `~standard` validation).

Use `@deepseek-ai/schemastery`, not the bare name `schemastery` (rescope; see [Plugin anatomy](../../learn/core/plugin-anatomy.md)).

## 2. How users override (the patch layer)

```yaml
# the profile's cordis.patch.yml

- id: my-plugin

  name: '@dsh-external/my-plugin'

  config:

    greeting: Hi

    maxItems: 5
```

Processing: the patch **is located by entry id** (not required to equal the registered name); `config` is **full-row replacement, not deep merge**;

The full application order: `profile.bundles → win32 shell → profile cordis.patch.yml → $DSH_HOME/cordis.patch.yml → --patch override` (see [Plugin anatomy](../../learn/core/plugin-anatomy.md)).

## 3. Runtime user config (ctx.settings)

The patch is the **static** layer. To let **end users change things in UI/Settings**, use `ctx.settings`:

```ts
import { settingsNamespace } from '@deepseek-ai/dsh-settings'

import z from '@deepseek-ai/schemastery'

import { Context } from '@deepseek-ai/cordis'

const ns = settingsNamespace('my-plugin')

const schema = z.object({

  greeting: z.string().default('Hello'),

  maxItems: z.number().step(1).min(1).default(10),

})

export async function apply(ctx: Context) {

  const scope = ctx.settings.register(ns, schema, { /* base? */ })

  const s = await ctx.settings.get(ns)   // resolved: schema default → composition base → user layer

  // user update: const updated = await scope.update({ greeting: 'Hi' })

}
```

- The file provider `dsh-settings-file`, default `$DSH_HOME/settings.yaml`, hot-releases external edits

- Optimistic concurrency via `revision`; the `settings/document-updated` event keeps UI and plugins in sync

- This is the real channel for "what parts of my plugin users can change", complementary to the patch

## 4. Publishing to an org

### 1. Repository manifest (the dsh field in package.json; there is no dsh.plugin.json)

```json
{

  "name": "@dsh-external/my-plugin",

  "version": "0.1.0",

  "exports": { ".": "./lib/index.js" },

  "dsh": { "bundle": { "patch": "./cordis.patch.yml" } }

}
```

### 2. Commit to the dsh-external org

```sh
git push origin main

# create a new repository under the dsh-external org (or commit to an existing org)
```

### 3. The user installs with one line

```sh
dsh plugin --profile web add "github:dsh-external/my-plugin#main"
```

## 5. bundle vs repository

|  | Bundle plugin | repository plugin |
| --- | --- | --- |
| Carrier | one git-source line (github:...#main) | .dsh-plugin directory (external plugin-registry mechanism) |
| Takes effect | restart dsh web | takes effect immediately |
| Belongs to | DSH standard | third-party plugin-console + home layer |

## 6. Release checklist

| Item | Check |
| --- | --- |
| Build artifact | lib/ checked in, or a build script available |
| Dependencies complete | watch out for bare-name deps: if necessary, install the bare name into the plugin's own node_modules |
| Composition healthy | dsh web --dump-config shows no anomalies |
| Documentation | bilingual README (org convention README.md + README.zh.md) |
| Schema | both the Config/ctx.settings schemas declare defaults |

## 7. Verifying a release

```sh
# Simulate a user install in a clean environment

dsh plugin --profile web add "github:dsh-external/my-plugin#main"

dsh web --dump-config | grep my-plugin
```

## Course complete 🎉

At this point, the plugin development loop is closed:

```text
what a plugin is (anatomy) → how to write it (hello → tool → service → events) → how to configure it → how to release it
```

New capabilities, new behaviors, new UI: you can all add them yourself. Keep going: the full [learning path](../../getting-started/learning-path.md) has more capability essentials and advanced material.
