# Plugin Inventory

Take a live look at **which plugins are installed and what state they are in**. DSH exposes a read-only `pluginInventory` service that projects the current Cordis Loader tree to clients via a Remote; the Web Settings "Plugins" tab is its visual surface.

## Contents

- [Read-only projection:ctx.pluginInventory](#read-only-projectionctxplugininventory)
- [The "Plugins" tab in Web Settings](#the-plugins-tab-in-web-settings)
- [How it differs from related capabilities](#how-it-differs-from-related-capabilities)
- [Verify](#verify)
- [Next steps](#next-steps)

---

## Read-only projection:ctx.pluginInventory

The `PluginInventoryGateway` in `packages/host/plugin-inventory` (package `@deepseek-ai/dsh-host-plugin-inventory`) registers the `pluginInventory` service and publishes **one** Typert-generated direct Remote: `pluginInventory/list`.

**Every call** reads `ctx.loader.entries()` directly, skips structural group rows, and returns the remaining entries in Loader order — with only four fields:

| field | meaning |
| --- | --- |
| entryId | stable Loader-tree entry identity (branded PluginEntryId) |
| moduleName | the exact module specifier the entry imports |
| enabled | effective enablement (including disabled ancestor groups) |
| fiberPhase | current root Fiber phase, null when there is no live root Fiber |

```ts
// packages/host/plugin-inventory/src/index.ts —— read the Loader directly, no second cache

@Remote('list')

list(): PluginInventorySnapshot {

  const entries: PluginInventoryEntry[] = []

  for (const entry of this.ctx.loader.entries()) {

    if (entry.options.group) continue

    entries.push({

      entryId: pluginEntryId(entry.id),

      moduleName: entry.options.name,

      enabled: !entry.disabled,

      fiberPhase: entry.fiber === undefined ? null : FIBER_PHASE[entry.fiber.state],

    })

  }

  return { entries }

}
```

### fiberPhase values

| value | Cordis Fiber state | meaning |
| --- | --- | --- |
| pending | PENDING | not yet started loading |
| loading | LOADING | loading the module |
| active | ACTIVE | running / activated |
| failed | FAILED | load/activation failed |
| unloading | UNLOADING | unloading |
| null | DISPOSED | no live root Fiber |

The snapshot is **point-in-time**: the Loader remains the sole lifecycle authority, and this package owns no cache, history, provenance model, event stream, or mutation path. The service is **Remote-only** and deliberately declares no same-process Cordis `Context` merge — Client packages consume it through the `api-remotes` assembly.

```ts
// packages/host/plugin-inventory/src/types.ts —— the phase projection

export type PluginFiberPhase =

  | 'pending' | 'loading' | 'active' | 'failed' | 'unloading' | null
```

## The "Plugins" tab in Web Settings

`packages/client/ui-settings-plugin-inventory` (`@deepseek-ai/dsh-client-ui-settings-plugin-inventory`) is a browser plugin that registers a localized `settings.plugins.tab` contribution with id `all`. The Plugins section owns the navigation entry and tab chrome.

- **Lazy**: the component is only mounted on first selecting the tab, which then **lazily calls** `ctx.remote.pluginInventory.list()` through `api-remotes`

- renders a **searchable two-column card catalog**; each collapsed card = a short module-name title + an effective-enablement tag + (when enabled) a colored root-Fiber status dot

- expanding a card shows: the Loader-tree entry id, the effective configuration, and for enabled entries the Cordis status; disabled entries omit the redundant "not mounted" runtime state

- search matches the module name and entry id; loading/empty/no-match/failure states stay local to the mounted component, and a failed read can be retried without exposing transport details

```tsx
// ui-settings-plugin-inventory/src/client/index.ts —— registered via slots, without importing the section owner

ctx.slots.inject('settings.plugins.tab', () => ctx.slots.register({

  name: 'settings.plugins.tab', id: 'all', order: 10,

  label: () => t('tab'), locale: NS, inject: injected,

}, PluginInventorySettingsTab))
```

The status dot is colored via `data-phase` (see `.statusDot[data-phase='…']` in `PluginInventorySettingsTab.module.css`): enabled + `active` → success green, `failed` → error color, `loading` → a progress color, everything else gray.

## How it differs from related capabilities

| capability | relationship |
| --- | --- |
| plugin install management and plugins.md | the management surface (enable/disable/install); this capability is a read-only projection with no mutation path |
| tool-cordis | the model-facing tools; this capability is a deployment/host-side Loader-tree view with no tool or prompt registration |
| ctx.loader | the sole lifecycle authority; pluginInventory is just its read-only mirror |

This capability registers **no** prompt, tool, message, or provider request (README **Model Experience: None**).

## Verify

```sh
# confirm the service and Remote contribution in the composition tree

dsh web --dump-config | grep -iE "plugin-inventory|pluginInventory"

# open Web Settings → "Plugins" tab and look at the searchable card catalog with its colored status dots
```

## Next steps

- [Remote API Gateway](../learn/core/remote-api-gateway.md): the gateway and `$mount()` mechanism `pluginInventory/list` travels through

- [Web UI Architecture](../learn/core/web-ui.md): the dual-process and slot-system background

- [Plugin Anatomy](../learn/core/plugin-anatomy.md): the dual-face plugin shape
