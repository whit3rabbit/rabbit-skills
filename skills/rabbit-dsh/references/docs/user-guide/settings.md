# Settings System

**Short version**: `ctx.settings` is the runtime user-config service: what a user changes in the UI/Settings is stored into `~/.dsh/settings.yaml` (hot-published by the `dsh-settings-file` file provider), and the `settings/document-updated` event keeps the UI and plugins in sync.

This section explains "that layer beyond patch's static configuration, changeable by the user at runtime".

## Contents

- [1. Which layer is this](#1-which-layer-is-this)
- [2. File provider: settings-file](#2-file-provider-settings-file)
- [3. Surface: how plugins use it](#3-surface-how-plugins-use-it)
- [4. Built-in namespace: agent-default-model](#4-built-in-namespace-agent-default-model)
- [5. Events](#5-events)
- [6. Verification](#6-verification)
- [Next steps](#next-steps)

---

## 1. Which layer is this

|  | patch layer | settings layer |
| --- | --- | --- |
| Who writes | Deployer (cordis.patch.yml) | User (UI / file) |
| Content | Static config / mounting | Runtime user settings |
| Carrier | cordis.patch.yml | ~/.dsh/settings.yaml |
| Change | Edit file, restart | Hot-published, settings/document-updated |

Patch and settings are **two configuration seams**, complementary (see [Configuration](../user-guide/configuration.md)).

## 2. File provider: settings-file

`dsh-settings-file` is the default implementation, carrying each namespace's section in a single YAML/JSON document:

| Field | Default | Description |
| --- | --- | --- |
| path | settings.yaml (under harness home) | Document path; the extension picks the format (.yaml/.yml/.json) |
| dshHome | $DSH_HOME or ~/.dsh | Harness home when path is omitted |
| watch | true | Watches the document, hot-publishing external edits |
| debounceMs | 100 | Write settle window (ms) |

Behavior notes:

- **fail-loud at startup, last-good on reload**: an existing invalid document → the plugin fails to load; an unreadable live edit → warns and keeps the last good section; a missing document → each namespace resolves from defaults+base

- **Every write is read-modify-write**: re-reads the document, publishes the diff, then writes: never revives a stale document or drops unobserved sibling sections

- **Writes hold a cross-process write lock** (`*.lock` sibling, `wx` creation, 2s acquisition cap)

- **Atomic, owner-only, symlink-resistant**: rendering uses a random-suffix temp (0600) then renames over

- **YAML edits are leaf-level diffs**: only change the altered values / remove dropped keys, preserving comment anchors and formatting

- **documentPath is a resolved absolute path**: `ctx.settings.documentPath` is the `resolveSpec()` filename; the browser only gets an availability flag, never rebuilds `$DSH_HOME`, never commits a filesystem destination

- **Its own writes are deduplicated by content**: the provider caches the last good text; when a watcher event's content equals the cache (including its own writes) it's a no-op

- **No indirection for values**: sections store literal values; `${env:VAR}`-style key references are a deferred seam-layer feature

## 3. Surface: how plugins use it

```ts
import { settingsNamespace } from '@deepseek-ai/dsh-settings'

import z from '@deepseek-ai/schemastery'

import { Context } from '@deepseek-ai/cordis'

const ns = settingsNamespace('my-plugin')

const schema = z.object({

  greeting: z.string().default('hello'),

  maxItems: z.number().step(1).min(1).default(10),

})

export function apply(ctx: Context) {

  const scope = ctx.settings.register(ns, schema, { /* base? */ })

  // resolution order: schema defaults → composition base → user layer

  // scope.get() / scope.update({...}) / scope.watch(...)

}
```

- `register(ns, schema, {base?})` returns the owner `SettingsScope` (`get`/`watch`/`update`)

- Registration is an effect: disposing the fiber removes the namespace and observers

- A stored section rejected by the schema → the registration fails; a duplicate namespace → fails loud

- A full example is in [Configuration & Publishing](../learn/dev/config-publish.md), "Runtime user config"

## 4. Built-in namespace: agent-default-model

`agent-default-model` is a settings section DSH ships, provided by the `dsh-agent-default-model` service (`ctx.agentDefaultModel`):

- `currentSelection()` returns a detached `{ provider, model, reasoningEffort? }` selection for newly-created agents

- `saveSelection(selection)` saves the full user selection; **it's a no-op when there's no settings provider**, so the deployment default in the composition stays in effect

- The deployment default is written into the **plugin config** (required `{ provider, model }`) as the base of the settings section; once a settings provider is mounted, the **user selection overrides on top**, taking effect on the next `currentSelection()` read

- `reasoningEffort` belongs **only to the settings section, never the plugin config**: a fully-saved selection can clear it when the next model has no effort, while a composition value would be inherited again

- The service **does not validate directory membership**: a provider route may serve an un-registered model; the consumer that actually opens the model request is responsible for availability diagnostics

```yaml
# ~/.dsh/settings.yaml

agent-default-model:

  provider: deepseek-official

  model: deepseek-v4-flash
```

Direct entry points (e.g. `dsh --profile headless`) and Host-side entry points (e.g. ApiProxy) read **the same service**, not maintaining separate provider/model defaults.

## 5. Events

- `settings/document-updated`: fired when `ctx.settings` values change

- Third-party plugins/UI listen to it to refresh. Credential changes are a **separate event stream** (`credentials/reference-updated` / `credentials/record-updated`, published by the credential provider), not derived from here — see [Credentials](../user-guide/credentials.md).

## 6. Verification

```sh
# Inspect the settings document (the layer a user can change)

cat ~/.dsh/settings.yaml

# Check the settings service in the composition

dsh web --dump-config | grep -i settings
```

## Next steps

- [Configuration](../user-guide/configuration.md): the full picture of settings.yaml

- [Configuration & Publishing](../learn/dev/config-publish.md): how plugins register their own settings

- [Credentials](../user-guide/credentials.md): reference keys, don't store values
