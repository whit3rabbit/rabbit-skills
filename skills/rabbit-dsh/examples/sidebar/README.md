# DSH Sidebar & Settings UI Template (`@rabbit-dsh/sidebar-template`)

Starter template and reference architecture for adding **sidebar tabs**, **file viewers**, **session header utility toggles**, and **settings pages** to DeepSeek Harness (`0.2.2-rc.1+`), extracted from `dsh-better-sidebar` and the native `@deepseek-ai/dsh-client-ui-*` packages.

## Contents

- [Template File Map](#template-file-map)
- [Build and Load](#build-and-load)
- [Quick Decision Matrix: Which Recipe to Use](#quick-decision-matrix-which-recipe-to-use)
- [How to Customize or Place UI Elements](#how-to-customize-or-place-ui-elements)
- [UI Components Kit Included in This Template](#ui-components-kit-included-in-this-template)
- [Critical Invariants for LLM Authors](#critical-invariants-for-llm-authors)

## Build and Load

The bundle ships prebuilt (`lib/index.js` Host half, `lib/client.js` browser
closure factory). Rebuild after editing `src/`:

```bash
cd examples/sidebar
pnpm install --config.auto-install-peers=false   # peers are runtime-injected; not all are on npm
pnpm build                                       # tsdown -> lib/
dsh plugin --profile web add link:"$PWD"         # then restart `dsh web`
```

`pnpm build` emits the two halves a `dsh.client` package publishes: the Node
half keeps `@deepseek-ai/*` specifiers as imports (resolved by DSH's loader),
and the browser half wraps in `window.__ModuleLoader__.load({id, factory})` with
the baseline module table (react, cordis, dsh-client-ui-slots,
dsh-client-ui-primitives, ...) as `require()` externals. A `*.module.css` import
compiles via lightningcss into a class-map export plus a style tag injected at
materialization.

## Template File Map

| File | Role |
| --- | --- |
| [package.json](package.json) | Declares dual Host + Client exports (`.` and `./client`), `dsh.bundle.patch`, `dsh.client` (`platform: 'web'`, `inject`), and optional `dsh-better-sidebar` peer dependency. |
| [cordis.patch.yml](cordis.patch.yml) | Mounts the plugin row with an environment-variable `!!js` disable guard. |
| [src/index.ts](src/index.ts) | **Host entry**: defines live `.volatile()` Schemastery config (`@deepseek-ai/schemastery`), resolves the dynamic profile Loader entry ID (`ownEntryId`), opts out of duplicate auto-settings cards (`ctx.settings.configure({ auto: false }, ctx.fiber)`), and mounts fenced `/sidebar-template/api/prefs` HTTP handlers. |
| [src/client/index.tsx](src/client/index.tsx) | **Client entry**: contains 4 modular placement recipes (`ctx.betterSidebar`, native `ctx.sidebarRightTabs` + `sidebar.right.pane.tab`, `conversation.session.header.utilities`, and `settings.section`). Delete the recipes your plugin does not need. |
| [src/client/ui-kit.tsx](src/client/ui-kit.tsx) | **Reusable UI Components**: `IconButton`, `Chip`, `SectionHeader`, `Notice`, `StatusBadge`, `Switch`, `ConfirmDialog`, `SelectMenu`, `FeatureCard`, and `ensureOpaqueSurface`. |
| [src/client/ui-kit.module.css](src/client/ui-kit.module.css) | **Token-pure CSS Module**: 12px/11px/28px sidebar scale, settings group cards, feature toggle grids, and `--dsw-alias-*` skin bindings with zero hardcoded hex colors. |

## Quick Decision Matrix: Which Recipe to Use

Open [src/client/index.tsx](src/client/index.tsx) and keep only the recipe(s) that match the user's request:

| User Goal | Recipe in `src/client/index.tsx` | Key API / Slot |
| --- | --- | --- |
| Add a tab, file viewer, or feature gear modal inside `dsh-better-sidebar` (right panel or bottom workbench) | **Recipe 1** | `ctx.betterSidebar.registerTab(...)` / `ctx.betterSidebar.registerFileViewer(...)` |
| Add a right-sidebar tab to stock DSH without requiring `dsh-better-sidebar` | **Recipe 2** | `ctx.sidebarRightTabs.register(...)` + `sidebar.right.pane.tab` + `sidebar.right.pane.tab.title` |
| Add a quick-toggle icon button in the top-right conversation session header | **Recipe 3** | `conversation.session.header.utilities` (`ctx.slots.inject`) |
| Add a dedicated top-level page in the DSH Settings shell | **Recipe 4** | `settings.section` + `settings.section.icon` + Host `ctx.settings.configure({ auto: false }, ctx.fiber)` |
| Add a simple auto-generated settings card in DSH Settings (no custom React settings page needed) | [src/index.ts](src/index.ts) only | Export `Config` from `@deepseek-ai/schemastery` with `.volatile()` fields and omit `ctx.settings.configure({ auto: false })` |

## How to Customize or Place UI Elements

1. **Rename the package and IDs**:
   - In [package.json](package.json) and [cordis.patch.yml](cordis.patch.yml), replace `@rabbit-dsh/sidebar-template` and `sidebar-template` with your plugin's package name and row ID.
   - In [src/client/index.tsx](src/client/index.tsx), update `BETTER_SIDEBAR_TAB_ID`, `NATIVE_TAB_KEY`, `NATIVE_TAB_KIND`, and `SETTINGS_SECTION_ID`.
2. **Place a tab in the Right Sidebar vs. Bottom Workbench**:
   - In **Recipe 1** (`ctx.betterSidebar.registerTab`), set `bottomOnly: false` to allow opening in both the right sidebar and bottom workbench, or `bottomOnly: true` to restrict the tab exclusively to the bottom workbench (like Terminal or Editor).
   - To open the tab programmatically, call `ctx.betterSidebar.openTab({ type: BETTER_SIDEBAR_TAB_ID, target: 'right' | 'bottom' | 'side', reveal: true })` or native `ctx.sidebarRight.openTab(NATIVE_TAB_KIND, { revealIfOpened: true })`.
3. **Add or update plugin settings**:
   - **Inside `dsh-better-sidebar` ("Side card" gear modal)**: Add entries to `settings.pluginToggles` (`switch | text | number | select | patterns`) inside `registerTab` or `registerFileViewer`. Values persist automatically under `prefs.pluginSettings[descriptor.id][key]`. For bespoke controls inside the gear modal, implement `settings.render`.
   - **Inside DSH's main Settings shell**: Either let DSH auto-render your Host `Config` schema from [src/index.ts](src/index.ts), or keep **Recipe 4** in [src/client/index.tsx](src/client/index.tsx) to render a custom page with `FeatureCard`, `Switch`, and `SelectMenu`.
4. **Register a custom file viewer**:
   - In **Recipe 1**, pass lowercase extension strings (without leading dots) in `exts: ['log', 'trace']` and choose a `fetchStrategy` (`'fsRead' | 'mediaUrl' | 'custom' | 'none' | 'binary-download'`).
   - Do not target host-owned document extensions (`xlsx, xls, csv, tsv, fods, pdf, png, jpg, jpeg, gif, webp, svg, bmp, ico, doc, docx, ppt, pptx`). `dsh-better-sidebar` yields those extensions to DSH's native `ui-sidebar-documentpreview` tab.

## UI Components Kit Included in This Template

Import ready-made sidebar and settings building blocks from [src/client/ui-kit.tsx](src/client/ui-kit.tsx) alongside `@deepseek-ai/dsh-client-ui-primitives`:

- `SectionHeader`: 28px sub-panel header band with uppercase label, tabular count pill, and right-aligned `IconButton` slot.
- `IconButton`: 28px (`md`) or 24px (`sm`) square icon button with `active` and `danger` states.
- `Chip`: 22px pill filter button with `active` highlight and optional `count` badge.
- `Notice`: Unified `empty | loading | error | warn | hint` callout in `page`, `well`, or `inline` layout tones.
- `StatusBadge`: Compact status pill with `data-tone="neutral | info | success | warn | error"`.
- `Switch`: Accessible checkbox switch styled with `--dsw-alias-button-primary-fill`.
- `ConfirmDialog`: Safe wrapper around Host `Modal` and `Button` (mounts `Modal` only when `open` is `true`).
- `SelectMenu`: Outline trigger `Button` wired to a portaled Host `Menu` dropdown.
- `FeatureCard`: Responsive grid card (`minmax(180px, 1fr)`) with toggle switch and bottom gear strip for Settings pages.
- `ensureOpaqueSurface`: Reads computed CSS variables and clamps translucent glass-skin values (`alpha < 0.9`) to an opaque fallback for canvas-based editors or terminals.

## Critical Invariants for LLM Authors

- **Client bundle purity gate**: Only runtime-import packages from `CLIENT_EXTERNALS` (`react`, `react/jsx-runtime`, `react-dom`, `react-dom/client`, `cordis`, `@deepseek-ai/dsh-client-ui-slots`, `@deepseek-ai/dsh-client-ui-primitives`). Always use `import type` for `@deepseek-ai/dsh-client-ui-sidebar-right`, `@deepseek-ai/dsh-client-ui-settings`, and `dsh-better-sidebar`.
- **Proxy-safe Host URLs**: Never call `fetch('/my-plugin/api/...')` with a leading slash. Leading slashes break reverse-proxy subpath deployments and `dsh-app://` desktop webviews. Resolve relative paths or call `ctx.betterSidebar.hostRouteUrl('my-plugin/api/...')`.
- **Root height layout**: Native `.paneBody` is a block scroll container (`overflow: auto`), not a flex container. Always apply `height: 100%; min-height: 0; display: flex; flex-direction: column;` on your tab root (`.tabRoot` in [src/client/ui-kit.module.css](src/client/ui-kit.module.css)).
- **Background polling gate**: Kept-mounted tabs stay in the DOM while hidden. Gate all `setInterval`, `fetch`, and WebSocket subscriptions on `visible === true`.
