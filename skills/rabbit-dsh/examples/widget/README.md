# DSH Floating Widget Template (`@rabbit-dsh/widget-template`)

Bare-bones starter for **floating overlay widgets**: small fixed-position elements (badges, tickers, mini-panels) that live directly on the chat page. It is a static DSH bundle plugin that serves a vanilla-JS widget over Host routes and injects a `<script defer>` tag into every rendered `index.html`. No build step, no React client bundle, no client module graph changes. Pattern proven in production by `dsh-whale-widget` (MeteorNOX/DeepSeek-Balance-Whale-Widget).

## Contents

- [When to Use This Template](#when-to-use-this-template)
- [Template File Map](#template-file-map)
- [How to Customize](#how-to-customize)
- [Install and Verify](#install-and-verify)
- [Critical Invariants for LLM Authors](#critical-invariants-for-llm-authors)

## When to Use This Template

| Goal | Use |
| --- | --- |
| A small always-visible overlay on the chat page (balance badge, status dot, token ticker) | This template. A floating widget. |
| A panel docked inside the right sidebar, bottom workbench, or Settings shell | The [sidebar UI template](../sidebar/README.md). A React client bundle. |
| One-off debugging markup for a single session | A dynamic `cordis_define` snippet. No package needed. |

Floating widgets are the right shape when the element must survive page reloads, mount before the user does anything, and stay out of the client module graph. Dynamic (`cordis_define`/`cordis_run`) plugins cannot do this: their definitions live in process memory and die on reload.

## Template File Map

| File | Role |
| --- | --- |
| [package.json](package.json) | Bundle manifest. `dsh.bundle.patch` points at the mount declaration. No client exports, everything is served over routes. |
| [cordis.patch.yml](cordis.patch.yml) | Inserts the plugin row into the web profile composition, with an environment-variable `!!js` disable guard. |
| [index.js](index.js) | **Host entry** (ESM, named exports `name` + `apply`). Registers three routes (`widget.js`, `data.json`, `config.json`), the web `tapIndex` injection, and the desktop `webserver/index-inject` row. `collectData()` is the single function to replace with a real data source. |
| [widget.js](widget.js) | **Page-side client**: vanilla-JS IIFE that mounts a draggable pill plus detail bubble, polls `data.json`, and persists drag position to `localStorage`. |

## How to Customize

1. **Rename the package and IDs**: replace `@rabbit-dsh/widget-template` and `widget-template` in [package.json](package.json) and [cordis.patch.yml](cordis.patch.yml), then `ROUTE_PREFIX` in [index.js](index.js), `ROUTE` in [widget.js](widget.js), and the `window.__dshWidgetTemplate` guard. Every route path must be unique. The web server throws on duplicate `(kind, path)` registrations.
2. **Feed it real data**: replace `collectData()` in [index.js](index.js). Return `{ label, value, detail, updatedAt }`. Fetch APIs with a timeout (`AbortSignal.timeout(...)`), cache in memory, and fall back to the last good value on transient failure. The whale widget shows the full robustness pattern.
3. **Shape the widget**: edit `buildDom()` and the style block in [widget.js](widget.js). Keep data rendering on `textContent`. The default surface is one pill with one bubble. Add menus or lists as needed.
4. **Add settings**: extend `DEFAULT_CONFIG` in [index.js](index.js) and `readConfig()` validation, then honor the new keys in [widget.js](widget.js). The GET/PUT `config.json` round-trip is already wired. Change settings with `curl -X PUT` or build a small menu.
5. **Add session awareness**: listen to Host events inside `apply()` (for example `ctx.on('session/event', ...)`) and fold the results into what `collectData()` returns. Collect every disposer into the existing `ctx.effect` cleanup.

## Install and Verify

```bash
# Static checks
node --check index.js && node --check widget.js
python3 "$rabbit_dsh_dir/scripts/rabbit_dsh.py" audit /path/to/widget
python3 "$rabbit_dsh_dir/scripts/audit_dsh_artifacts.py" /path/to/widget/cordis.patch.yml --strict

# Load into a disposable web profile (run from the package root), then restart `dsh web`
dsh plugin --profile web add link:.

# Verify the routes (port 3080 is the default `dsh web` listener)
curl -f http://127.0.0.1:3080/ | grep widget-template/widget.js   # index carries the script tag
curl -f http://127.0.0.1:3080/widget-template/data.json           # { ok: true, data: ... }
curl -f http://127.0.0.1:3080/widget-template/config.json         # { ok: true, config: ... }
```

The pill appears bottom-right after a browser reload of the chat page. Drag it anywhere, click it for the detail bubble, and click the bubble to close.

## Critical Invariants for LLM Authors

- **Static bundle plugin, not dynamic**: the widget must self-start on every page load. Only a package-mounted bundle patch does that. `cordis_define` definitions die with the process.
- **Register the desktop row before waiting on services**: the desktop shell collects the `webserver/index-inject` table once at host startup. A top-level `export const inject = ['webServer']` would delay `apply()` past that collection, so the widget would never appear on desktop. That is why [index.js](index.js) pushes the row first and waits for `webServer` inside `root.inject(...)`.
- **Inline script row, never `script-src`, on desktop**: the desktop interpreter rejects the entire boot when a `script-src` row fails to load. The inline row in [index.js](index.js) creates its own `<script>` element and swallows `onerror`, so a missing route can never take the app down.
- **Both injection channels dedupe independently**: `tapIndex` (web `renderIndex`) checks for the script tag before inserting. The desktop row scans the table. Keep both, they cover different shells.
- **Handlers must always answer**: wrap every route handler and end every path with a response. A thrown async handler surfaces as an empty 400, and a hanging handler stalls the widget's poll loop.
- **Idempotency at both ends**: the client guard (`window.__dshWidgetTemplate`) plus the server-side dedupe checks prevent double injection across HMR reloads and shell restarts.
- **Gate on the chat root**: check for composer markers (`[data-composer-input]`, `textarea`, ...) before touching the DOM. The script is injected into every SPA view, including the plugin marketplace, where global DOM changes break React.
- **Position with `left`/`top` pixels**: `right: 0` or `auto` values cannot be interpolated by CSS transitions, so anchored moves jump. Clamp to the viewport and persist to `localStorage`, not to a server file.
- **Render data with `textContent`**: route payloads are data, not markup. Never build HTML strings from them.
- **Fence write routes when they touch anything sensitive**: the shipped Connection plugin authenticates Host API routes, but a widget that reads credentials or accepts writes should add its own loopback/Origin check. Copy `selfRejection()` from the whale widget.
