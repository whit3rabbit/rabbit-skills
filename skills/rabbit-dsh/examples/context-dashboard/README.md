# DSH Context Dashboard Template (`context-dashboard-template`)

A full-surface, no-build **working skeleton** for a DeepSeek Harness (`0.2.2-rc.1+`) context dashboard: a **Context tab**, a **Fleet tab**, a **`/context` command**, a **right-sidebar panel**, and a **settings page**, all fed by fenced Host routes. The architecture is distilled from the [`dsh-context`](https://github.com/bowenliang123/dsh-context) plugin (context insights and management for DSH). Every figure is served from a clearly-labeled demo fixture until you wire a real data source.

## Contents

- [Template File Map](#template-file-map)
- [Surface Matrix: What Gets Registered Where](#surface-matrix-what-gets-registered-where)
- [Data Model and Flow](#data-model-and-flow)
- [Quick Start](#quick-start)
- [Wire Real Data](#wire-real-data)
- [How to Customize](#how-to-customize)
- [Critical Invariants for LLM Authors](#critical-invariants-for-llm-authors)

## Template File Map

| File | Role |
| --- | --- |
| [package.json](package.json) | Declares dual Host + Client exports (`.` and `./client`), the `dsh.bundle.patch` row, and the `dsh.client` block (`platform: 'web'`, service `inject` list). |
| [cordis.patch.yml](cordis.patch.yml) | Mounts the plugin row with an environment-variable `!!js` disable guard. |
| [lib/index.js](lib/index.js) | **Host half**: fenced HTTP routes (`data.json`, `config`) guarded by `connection.requestRejection`, config persistence to `$DSH_HOME`, and the documented integration points (`sessionProjections`, session log, models.dev pricing) for replacing the demo feed. |
| [lib/demo-data.js](lib/demo-data.js) | **Demo dataset**: the skeleton data feed in the real shape (session, stats, 8-category composition, per-step trend, events, file ops, command runs, agent family) plus the category and color metadata. |
| [lib/client.js](lib/client.js) | **Client half** (handwritten ModuleLoader bundle, no build step): all five surfaces, the card components, the composition bar and trend chart, the `/context` modal, and the config gating. |
| [preview/index.html](preview/index.html) | **Static look preview**: the dashboard rendered with the demo figures, openable in any browser without DSH. A snapshot, not the live bundle. |

## Surface Matrix: What Gets Registered Where

dsh-context ships five surfaces, and so does this skeleton. Each one degrades silently when its service is missing, and each is gated by a config key.

| Surface | Registration | Config key | Default |
| --- | --- | --- | --- |
| **Context tab** (the dashboard) | `ctx.slots.inject('conversation.view', …)` + `ctx.slots.register({ name: 'conversation.view', id: …+':context', order: 20 })` | `enableTab` | on |
| **Fleet tab** (agent family) | Second `conversation.view` registration with `id: …+':fleet', order: 21` | `enableFleetTab` | on |
| **`/context` command** (centered modal) | `inputTriggers.registerSource({ trigger: '/', candidates, onPick, matchEnter })` | `enableCommand` | on |
| **Right-sidebar panel** | `ctx.sidebarRightTabs.register({ id, kind, priority: 'extension' })` + `sidebar.right.pane.tab` slot | `enableSidebarPanel` | off |
| **Settings page** | `ctx.slots.inject('settings.section', …)` | always registered, not gated | on |

Cards in the Context tab (each answers one question, the same rule dsh-context uses): **KPI band** (occupancy, turns, steps, tool calls, active time, est. cost, cache hit), **Current composition** (8-category stacked bar + legend), **Context trend** (per-step bars with a Total/Delta toggle), **Context events** (kind chips: Inject / Compact / Prune / Switch / Mode), **File activity** (read/written/searched + line deltas), and **Command executions** (program ranking). The Fleet tab adds agent cards with live occupancy and a skeleton slot for the collaboration timeline.

## Data Model and Flow

```
lib/demo-data.js ──import──▶ lib/index.js (Host) ──GET /context-dashboard/data.json──▶ lib/client.js (Client)
$DSH_HOME/dsh-context-dashboard-template.json ◀──GET/POST /context-dashboard/config──┘ (config + settings page)
```

The dataset shape is the contract between the halves:

| Field | Shape | Feeds |
| --- | --- | --- |
| `session` | `{ id, title, model, windowTokens, reservedTokens }` | header, occupancy |
| `stats` | `{ turns, steps, humanInputs, toolCalls, activeMs, costUsd, cacheHitRate }` | KPI band |
| `composition` | `[{ key, label, tokens }]` in draw order | composition card |
| `trend` | one row per step: `{ step, label, system, toolSchemas, user, injected, skills, reasoning, answers, toolResults }` (cumulative) | trend card (deltas derived client-side) |
| `events` | `[{ kind, producer, deltaTokens, turn, step, time, detail }]` | events card |
| `files` | `[{ path, reads, writes, searches, added, removed }]` | file activity card, line deltas |
| `commands` | `[{ program, runs, ok, failed, totalMs }]` | command executions card |
| `agents` | `[{ id, title, role, status, contextTokens, occupancy, steps, runtimeMs, parent }]` | Fleet tab |

`data.source` must stay honest: `'demo'` until a real source is wired (the dashboard shows a demo banner keyed on it), then `'session-log'` or `'projections'`.

## Quick Start

1. **Look at it first** (no DSH needed): open [preview/index.html](preview/index.html) in a browser.
2. **Install as-is** in a disposable profile:

   ```sh
   dsh plugin --profile web add link:./skills/rabbit-dsh/examples/context-dashboard
   dsh web
   ```

3. Open any conversation: the **Context** and **Fleet** tabs appear beside the chat, `/context` opens the centered modal, and **Settings → Context Dashboard** switches surfaces. Every card shows the demo banner until real data is wired.

## Wire Real Data

The demo fixture stands in for the real computation. In increasing fidelity, dsh-context builds its figures from:

1. **dsh's official token-meter projections** (`contextPressure` / `contextBreakdown`): the same numbers the chat composer's context ring shows, read through the `sessionProjections` Cordis service. Declare `inject: ['sessionProjections']` in the Host half and read the projections for the active session.
2. **The V4 session log** under `$DSH_HOME`: turns, tool calls, file ops, command runs, and agent events, folded per step. This is where events, file activity, and command rows come from.
3. **models.dev list prices** for cost estimates. DeepSeek's listed rates are the off-peak tier, and peak windows bill at 2×.

Replace `datasetFor()` in [lib/index.js](lib/index.js) (or serve your own object from the `data.json` route) while keeping the table above intact. Compute client-side instead when the data is already in the session store. dsh-context does most of its folding client-side and keeps the Host cache small.

## How to Customize

1. **Rename the plugin**: replace `context-dashboard-template` in `package.json` (`name`, exports, `dsh.client`), [cordis.patch.yml](cordis.patch.yml), the `NS` constant in [lib/client.js](lib/client.js) (it MUST equal the package name, the loader fails otherwise), and `NS` / `ROUTE_BASE` / `CONFIG_FILE` in [lib/index.js](lib/index.js).
2. **Add a card**: write a function that takes one dataset field and returns `Card` children, then add it to `DashboardView`. Keep one question per card. If it needs a new dataset field, extend [lib/demo-data.js](lib/demo-data.js) first so the contract stays executable.
3. **Move a surface**: the sidebar panel and `/context` command register inside the config callback in `apply()`. Move the call out of the gate (or add your own config key) to change when they mount. Conversation tabs self-gate on the config they fetch per mount, so toggling them never needs re-registration.
4. **Restyle**: layout and text bind to `--dsw-alias-*` skin tokens. The eight `--ctxd-c-*` chart hues are fixed data-encoding colors (dsh-context does the same), declared once on `.ctxd-root`. Category labels and colors live in one `CATEGORY_META` map in the client and `demoCategories` in the dataset, so change both together.
5. **Preview changes to the look**: mirror card changes in [preview/index.html](preview/index.html), the reviewable snapshot of the layout.

## Critical Invariants for LLM Authors

- **Client bundle identity**: the `window.__ModuleLoader__.load({ id })` in [lib/client.js](lib/client.js) must equal the package `name`. Export `apply` and `inject` as named exports only. No default export (the loader unwraps `exports.default ?? exports`), and no `Config` export from the Host (Cordis expects a Schemastery schema under that name).
- **Proxy-safe Host URLs**: never call `fetch('/context-dashboard/…')` with a leading slash. Leading slashes break reverse-proxy subpath deployments and `dsh-app://` desktop webviews. Use the relative paths already in the client.
- **Fenced routes**: every Host route must pass `connection.requestRejection` before answering, and the demo data and config endpoints are no exception. Malformed POST bodies answer 400 and leave the plugin loaded.
- **Token-pure theming**: bind layout, text, and background colors to `--dsw-alias-*` tokens. Only the eight chart hues are literal, and they are data encodings, not skin colors.
- **Hooks discipline**: each surface loads its own data with `useDashboardData()` inside its own component. Never share a hook result across components, because a store built in one component's render will not re-render another. All hooks run before any early return.
- **Unload must never throw**: every registration, listener, and route disposes through `ctx.effect` or an explicit disposer wrapped in try/catch.
