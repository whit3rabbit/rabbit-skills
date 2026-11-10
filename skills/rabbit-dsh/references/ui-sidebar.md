# UI Components, Sidebar & Settings Reference

Build, place, and style Web UI extensions, right-sidebar tabs, bottom-workbench panels, file viewers, and settings pages for DeepSeek Harness (`0.2.2-rc.1+`). Start from the copyable template in [examples/sidebar/README.md](../examples/sidebar/README.md).

## Contents

- [Decision Matrix: Where to Place UI](#decision-matrix-where-to-place-ui)
- [Client Bundle Contract & Purity Gate](#client-bundle-contract--purity-gate)
- [Sidebar Extension Recipes](#sidebar-extension-recipes)
- [Settings Extension Recipes](#settings-extension-recipes)
- [Conversation & Header Slot Catalog](#conversation--header-slot-catalog)
- [UI Components & Primitives Catalog](#ui-components--primitives-catalog)
- [Skin Tokens & Layout Rules](#skin-tokens--layout-rules)

## Decision Matrix: Where to Place UI

| Surface | Target API / Slot | When to Choose |
| --- | --- | --- |
| **`dsh-better-sidebar` Tab** (Right Sidebar or Bottom Workbench) | `ctx.betterSidebar.registerTab(descriptor)` | You want multi-tab management, unread badges, split panes, bottom-workbench docking (`bottomOnly`), and built-in gear modal settings. |
| **`dsh-better-sidebar` File Viewer** | `ctx.betterSidebar.registerFileViewer(descriptor)` | You want custom rendering when a user opens files by extension or content sniff inside the sidebar file tree or chat links. |
| **Native DSH Right Sidebar Tab** | `ctx.sidebarRightTabs.register(...)` + `sidebar.right.pane.tab` | You want a zero-dependency right-sidebar tab in stock DSH (`@deepseek-ai/dsh-client-ui-sidebar-right`) without requiring `dsh-better-sidebar`. |
| **Session Header Quick Action** | `conversation.session.header.utilities` (list slot) | You need a persistent 24px/28px toggle button in the top-right conversation bar beside the Session Log capsule. |
| **Simple Plugin Settings Card** | Export `Config` from `@deepseek-ai/schemastery` on Host | Your settings are boolean switches, numbers, strings, or selects that DSH's `SettingsForms` can render automatically. |
| **Custom Settings Shell Section** | `settings.section` + `settings.section.icon` + `ctx.settings.configure({ auto: false }, ctx.fiber)` | You need a custom multi-card layout, feature toggle grid (`FeatureCard`), or custom dialogs in the DSH Settings navigation rail. |

## Client Bundle Contract & Purity Gate

A plugin that ships browser UI exports both a Host entry (`.`) and a Client entry (`./client`) in [examples/sidebar/package.json](../examples/sidebar/package.json):

```json
{
  "name": "@scope/my-ui-plugin",
  "type": "module",
  "main": "./dist/index.mjs",
  "exports": {
    ".": "./dist/index.mjs",
    "./client": "./dist/client.mjs"
  },
  "dsh": {
    "bundle": { "patch": "./cordis.patch.yml" },
    "client": {
      "platform": "web",
      "inject": ["slots", "settings", "sidebarRight", "sidebarRightTabs", "betterSidebar"]
    }
  }
}
```

### Shared Platform Externals (`CLIENT_EXTERNALS`)

The DSH browser shell resolves **only** these 7 module specifiers at runtime via `window.__ModuleLoader__.load`:

- `react`
- `react/jsx-runtime`
- `react-dom`
- `react-dom/client`
- `cordis`
- `@deepseek-ai/dsh-client-ui-slots`
- `@deepseek-ai/dsh-client-ui-primitives`

Any other `@deepseek-ai/*` package (`@deepseek-ai/dsh-client-ui-sidebar-right`, `@deepseek-ai/dsh-client-ui-settings`) or peer plugin (`dsh-better-sidebar`) must be imported with **`import type` only** in your client code so TypeScript merges their `cordis.Context` and `SlotRegistry` declarations without emitting a runtime `import` statement.

## Sidebar Extension Recipes

See [examples/sidebar/src/client/index.tsx](../examples/sidebar/src/client/index.tsx) for the complete copyable implementation of all recipes below.

### 1. `dsh-better-sidebar` Tab (`ctx.betterSidebar.registerTab`)

Inject `betterSidebar` (or guard with `ctx.inject(['betterSidebar'], ...)`) and wrap registrations in `ctx.effect`:

```tsx
import type {} from 'dsh-better-sidebar/client/service'
import type { Context } from 'cordis'

export const inject = ['betterSidebar']

export function apply(ctx: Context) {
  ctx.effect(() => {
    const dispose = ctx.betterSidebar.registerTab({
      id: 'my-plugin:inspector',
      title: 'Inspector',
      description: 'Live session diagnostics and event stream.',
      icon: <MyIcon size={16} />,
      order: 60,
      single: true,       // Focus existing tab instead of opening duplicates
      bottomOnly: false,  // Set true to dock exclusively in the bottom workbench
      component: ({ scope, tab, visible }) => (
        <MyInspectorPanel sessionId={scope} tab={tab} visible={visible} />
      ),
    })
    return () => dispose()
  })
}
```

Key `TabDescriptor` hooks and properties:

- `single?: boolean` / `dedupeKey?: (state) => string`: Prevents duplicate tabs for the same resource.
- `bottomOnly?: boolean`: When `true`, the tab opens only in the bottom workbench (like Terminal or Editor) and never mounts in the right sidebar.
- `available?: (ctx, scope, state) => boolean`: Conditionally hides the tab from the `+` launcher when unavailable for the active session.
- `badge?: (ctx, scope, state) => ReactNode`: Renders a counter or status indicator on the tab chip.
- `rightActions?: (ctx, scope, state, tab, paneId) => ReactNode`: Renders compact 24px `IconButton` controls on the right side of the tab bar when active.
- `urlTarget?: (url: string) => Record<string, unknown> | null`: Intercepts clicked links in chat and opens them inside this tab.

Programmatic navigation on `ctx.betterSidebar`:

- `ctx.betterSidebar.openTab({ type: 'my-plugin:inspector', target: 'right' | 'bottom' | 'side', reveal: true, state: { ... } }, scope?)`
- `ctx.betterSidebar.openFile(scope, filePath, title?, { line?, lineEnd? })`
- `ctx.betterSidebar.updateTab(tabId, patch, sessionId?)`
- `ctx.betterSidebar.hostRouteUrl('my-plugin/api/prefs')` — **Always** use `hostRouteUrl` (never a leading `/` like `fetch('/my-plugin/api/...')`) so reverse-proxy subpaths and `dsh-app://` desktop webviews resolve your Host HTTP handlers cleanly.

### 2. `dsh-better-sidebar` File Viewer (`ctx.betterSidebar.registerFileViewer`)

```tsx
const disposeViewer = ctx.betterSidebar.registerFileViewer({
  id: 'my-plugin:trace-viewer',
  title: 'Trace Viewer',
  icon: <MyIcon size={14} />,
  exts: ['log', 'trace'],        // Lowercase without leading dot; [] for catch-all
  priority: 10,                  // Higher wins; builtins use 0, code fallback uses -100
  fetchStrategy: 'fsRead',       // 'none' | 'fsRead' | 'mediaUrl' | 'custom' | 'binary-download'
  detect: (path, head) => head.startsWith('{"traceVersion":'),
  component: ({ path, content, scope, reload }) => (
    <MyTraceViewer path={path} content={content ?? ''} onReload={reload} />
  ),
})
```

- **Host-Owned Extensions Boundary (`HOST_OWNED_EXTS`)**: `dsh-better-sidebar` yields `xlsx, xls, csv, tsv, fods, pdf, png, jpg, jpeg, gif, webp, svg, bmp, ico, doc, docx, ppt, pptx` to DSH's native `ui-sidebar-documentpreview` tab in `canOpen`. Custom `registerFileViewer` plugins intercept `md/markdown`, `html/htm`, `jsonl/ndjson`, and text/code extensions routed through the `dsh-better-sidebar` tab.

### 3. Native DSH Right Sidebar Tab (`ctx.sidebarRightTabs` + `ctx.slots`)

When targeting stock DSH without `dsh-better-sidebar`, wait for `['sidebarRightTabs', 'sidebarRight']` via `ctx.inject` (because `sidebar.right.pane.tab` is declared before `sidebarRightTabs` is registered) and bind matching `id` and `key` values:

```tsx
const TAB_KEY = 'my-plugin:inspector'
const TAB_KIND = 'my-plugin-inspector'

ctx.inject(['sidebarRightTabs', 'sidebarRight'], (innerCtx) => {
  innerCtx.effect(() =>
    innerCtx.sidebarRightTabs.register({
      id: TAB_KEY,
      kind: TAB_KIND,
      keepMounted: true,
      priority: 'extension', // 'builtin' | 'extension' | 'fallback'
      title: () => 'Inspector',
      guide: [
        {
          id: TAB_KIND,
          order: 60,
          title: () => 'Inspector',
          description: () => 'Inspect live session events and metrics.',
          icon: ({ size = 16 }) => <MyIcon size={size} />,
        },
      ],
    }),
  )

  innerCtx.slots.inject('sidebar.right.pane.tab', () =>
    innerCtx.slots.register(
      { name: 'sidebar.right.pane.tab', key: TAB_KEY },
      ({ sessionId, tab }) => <MyInspectorPanel sessionId={sessionId} tabId={tab.id} />,
    ),
  )
})
```

- **New-Tab Guide Description Cap (`MAX_DESCRIBED_ENTRIES = 4`)**: DSH's native `+` New Tab guide renders each entry's `description` subtitle only when the total number of guide entries is 4 or fewer. Keep `title()` self-explanatory so the card remains clear when compact mode activates.
- **Opening Native Tabs Programmatically**: Call `ctx.sidebarRight.openTab(TAB_KIND, { revealIfOpened: true, preferNewPane: false, params: { ... } })` or `ctx.sidebarRight.openResource('dsh-resource://file/workspace/README.md')`.

## Settings Extension Recipes

### 1. Declarative & Modal Settings in `dsh-better-sidebar` (`settings.pluginToggles` & `settings.render`)

Every `TabDescriptor` and `FileViewerDescriptor` accepts a `settings` object that automatically wires a gear button onto its feature card in the "Side card" settings page:

- `pluginToggles`: Array of declarative controls persisted under `prefs.pluginSettings[descriptor.id][key]`:
  - `type: 'switch'` — Boolean toggle switch.
  - `type: 'text'` — Single-line text input (`placeholder`).
  - `type: 'number'` — Numeric input (`min`, `max`, `unit`).
  - `type: 'select'` — Option list (`options: [{ value, title, desc?, icon? }]`, `multi?: boolean`).
  - `type: 'patterns'` — Multi-line glob/pattern textarea (`patternsPlaceholder`).
- `render?: ({ store, service, prefs, pluginSettings, updatePluginSetting, close }) => ReactNode`: Custom React controls rendered inside the feature's gear modal.

### 2. Auto-Generated Host `Config` Card (`@deepseek-ai/schemastery` + `SettingsForms`)

In [examples/sidebar/src/index.ts](../examples/sidebar/src/index.ts), export `Config` using `@deepseek-ai/schemastery` (never public `schemastery`) and chain `.volatile()` on fields that should hot-update via `loader/volatile-update` without remounting the plugin:

```ts
import z, { type Volatile } from '@deepseek-ai/schemastery'

export interface RawConfig {
  refreshIntervalSec: number
}
export type Config = { [K in keyof RawConfig]: Volatile<RawConfig[K]> }

export const Config: z.Schema<RawConfig, Config> = z.object({
  refreshIntervalSec: z.number().min(1).max(300).default(10).description('Polling interval (s).').volatile(),
})
```

To read or persist settings from the Host via `ctx.settings` (`SettingsForms`), resolve the plugin's Loader entry ID dynamically (`ownEntryId(ctx)` in [examples/sidebar/src/index.ts](../examples/sidebar/src/index.ts)) rather than hardcoding a string ID.

### 3. Custom Settings Shell Section (`settings.section` + `settings.section.icon`)

When your plugin needs a dedicated navigation item and multi-card page inside DSH Settings:

1. **Host ([examples/sidebar/src/index.ts](../examples/sidebar/src/index.ts))**: Call `ctx.settings?.configure({ auto: false }, ctx.fiber)` inside `ctx.effect` so DSH does not generate a duplicate schema form page.
2. **Client ([examples/sidebar/src/client/index.tsx](../examples/sidebar/src/client/index.tsx))**: Register matching `id` and `order` values on `settings.section.icon` and `settings.section` via `ctx.slots.inject`.

## Conversation & Header Slot Catalog

| Slot Name | Kind | Purpose & Placement Rules |
| --- | --- | --- |
| `conversation.session.header.utilities` | `list` (`id`, `order`) | Top-right session header utility strip next to the Session Log capsule. Best home for sidebar or bottom-workbench toggles. |
| `conversation.session.header.corner` | `single` | Top-right corner slot **owned by the native right-sidebar toggle**. Do not overwrite unless replacing the entire right sidebar. |
| `conversation.session.header.actions` | `list` (`id`, `order`) | Secondary action strip in the session header. |
| `conversation.chat.turnTail` | `list` (`id`, `order`) | Renders below an assistant turn (citations, quick actions, surface cards). Keep contributions additive. |
| `conversation.input.activity` | `single` | Activity indicator bar between the model selector and the Send button. |
| `sidebar.right.pane.tab` | `keyed` (`key`) | Body renderer for a native right-sidebar tab (`key` matches `sidebarRightTabs.register({ id })`). |
| `sidebar.right.pane.tab.title` | `keyed` (`key`) | Custom chip title renderer in the native right-sidebar pane header. |
| `settings.section` | `list` (`id`, `order`, `label`) | Full page section in the DSH Settings shell. |
| `settings.section.icon` | `list` (`id`, `order`, `label`) | Navigation rail icon paired 1-to-1 with `settings.section` by `id`. |

## UI Components & Primitives Catalog

### 1. Host Primitives (`@deepseek-ai/dsh-client-ui-primitives`)

Always prefer DSH's shared primitives before writing custom widgets:

| Component | Key Props & Usage Notes |
| --- | --- |
| `Button` | `variant="primary" \| "outline"`. Standard action button for modals, footers, and dropdown triggers. |
| `Input` | `type="text" \| "number"`, `value`, `onChange`, `placeholder`. Token-styled text/number input. |
| `Menu` | `open`, `anchor`, `items` (`MenuItem[]`), `selectedId`, `selectedIds`, `onSelect`, `onClose`, `portal`. Dropdown menu. |
| `Modal` | `open`, `onClose`, `title`, `description`, `closeLabel`, `footer`. **Only render `<Modal>` when `open` is `true`** to avoid hook/portal mismatches. |
| `SegmentedControl` | `value`, `onChange`, `options` (`[{ value, label, disabled? }]`), `ariaLabel`. 36px mode switcher with arrow-key navigation. |
| `Tooltip` | `content`, `placement`, `delay`. Wrap icon-only buttons (`IconButton`) in `Tooltip` plus `aria-label`. |
| `StateDot` | `state="idle" \| "running" \| "success" \| "warn" \| "error"`. Status dot indicator. |
| `JsonTree` | Interactive collapsible JSON inspector tree. |
| `MarkdownText` | Host Markdown renderer (`MarkdownDelegateProvider` overrides link/code handling). |
| `FileTypeIcon` | Renders the host file/folder icon for a path or extension. |
| `Icon*OutlineRegular` / `Icon*FillRegular` | Shared icon family (`IconSettingsOutlineRegular`, `IconRefreshOutlineRegular`, `IconCloseOutlineRegular`, `IconPlusOutlineRegular`, `IconSearchOutlineRegular`, `IconCodeOutlineRegular`, `IconPanelLeftOutlineRegular`). Default `size={16}`; pass `size={14}` or `size={12}` inside compact 28px/24px sidebar headers. |

### 2. Extracted Sidebar UI Kit ([examples/sidebar/src/client/ui-kit.tsx](../examples/sidebar/src/client/ui-kit.tsx))

Copy [examples/sidebar/src/client/ui-kit.tsx](../examples/sidebar/src/client/ui-kit.tsx) and [examples/sidebar/src/client/ui-kit.module.css](../examples/sidebar/src/client/ui-kit.module.css) into your plugin for sidebar-scaled components (`12px` body, `11px` metadata, `28px` control height):

- `SectionHeader`: 28px sub-panel header band (`label`, `count`, right-aligned `action` slot) with a `1px solid var(--dsw-alias-border-l1)` divider.
- `IconButton`: 28px (`md`) or 24px (`sm`) icon button with hover, `active`, and `danger` states.
- `Chip`: 22px pill filter toggle with `active` accent state and tabular `count` badge.
- `Notice`: Unified `empty | loading | error | warn | hint` callout supporting `tone="page" | "well" | "inline"`.
- `StatusBadge`: Compact status pill with `data-tone="neutral | info | success | warn | error"`.
- `Switch`: Accessible checkbox switch bound to `--dsw-alias-button-primary-fill`.
- `ConfirmDialog`: Safe confirmation modal wrapping Host `Modal` and `Button`.
- `SelectMenu`: Outline `Button` + portaled Host `Menu` single-select dropdown.
- `FeatureCard`: Responsive card (`minmax(180px, 1fr)`) with toggle switch and bottom gear strip for Settings pages.

## Skin Tokens & Layout Rules

Never hardcode hex or RGB values in sidebar or settings CSS. Bind every rule to DSH's `--dsw-alias-*` CSS custom properties so light, dark, and glass skins recolor automatically:

| Category | CSS Variable | Usage |
| --- | --- | --- |
| **Panel Surface** | `var(--dsw-alias-bg-layer-1)` | Primary surface for right-sidebar and bottom-workbench panels. (**Never** use `--dsw-specific-sidebar-fill`; that token belongs exclusively to the left navigation rail.) |
| **Well / Chip Surface** | `var(--dsw-alias-bg-layer-2)` | Filter chips, inline notices, switch tracks, and feature cards. |
| **Settings Group Card** | `var(--dsw-alias-bg-layer-3)` | Elevated settings cards (`border-radius: 16px`) and modal surfaces. |
| **Canvas / Editor Base** | `var(--dsw-alias-bg-base)` | Base surface for editors/terminals. Wrap with `ensureOpaqueSurface('--dsw-alias-bg-base', fallback)` so translucent glass skins (`alpha < 0.9`) do not break canvas renderers. |
| **Typography / Ink** | `var(--dsw-alias-label-primary)` / `-secondary` / `-tertiary` / `-dimmed` | Primary copy, subheaders, descriptions, and disabled labels. |
| **Typography Scale** | `var(--dsw-font-xxs-12)` / `var(--dsw-font-xxxs-11)` | `12px` sidebar body copy and `11px` metadata/badges. |
| **Borders** | `var(--dsw-alias-border-l1)` / `-l2` / `-l4` | Row hairlines (`l1`), card/input borders (`l2`), and keyboard focus rings (`l4`). |
| **Interactive & Brand** | `var(--dsw-alias-button-primary-fill)` / `var(--dsw-alias-accent-soft)` / `var(--dsw-alias-interactive-bg-hover)` | Primary active controls, soft accent fills, and row hover states. |
| **Semantic States** | `var(--dsw-alias-state-business-primary)` / `-success-primary` / `-warn-primary` / `-error-primary` | Info, success, warning, and error badges/alerts. |

### Two Mandatory Layout & Runtime Invariants

1. **Root Height Contract (`.paneBody`)**: DSH's native `.paneBody` is a block scroll container (`overflow: auto`), not a flex column. Every root tab component must declare `height: 100%; min-height: 0; display: flex; flex-direction: column;` (see `.tabRoot` in [examples/sidebar/src/client/ui-kit.module.css](../examples/sidebar/src/client/ui-kit.module.css)) so inner scroll regions fill the pane without collapsing.
2. **Visibility Polling Gate (`visible`)**: Tabs with `keepMounted: true` remain mounted in the DOM when inactive or when the sidebar collapses. Always gate timers, polling loops, and streaming subscriptions on `visible === true`.
