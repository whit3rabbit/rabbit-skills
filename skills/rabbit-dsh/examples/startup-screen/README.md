# DSH Startup Screen Template (`startup-screen-template`)

A bare-bones, no-build template for **startup screens** (splash and boot widgets) in DeepSeek Harness. It was distilled from the real [`dsh-startup-screen` plugin](https://github.com/6shenhonghong9/dsh-startup-screen), with the branding, audio, voice, and glass effects stripped out. The result is a working widget: it takes over the first screen, plays, and releases the page. Copy it, rename it, and rebuild the look you want.

## What it demonstrates

- **Host half**: injecting a pre-mount overlay and scripts into `index.html` via `webServer.tapIndex`, serving plugin files over custom routes, persisting config to `$DSH_HOME/<plugin>.json`, and fencing routes with the host trust barrier (`connection.requestRejection`).
- **Widget half**: the safe overlay lifecycle. A boot layer covers the app before it mounts, a bootstrap guard decides whether to play at all, a 9-second watchdog guarantees the page can never stay locked, and a `finish()` contract always releases it.
- **Client half**: a handwritten `window.__ModuleLoader__.load` bundle (no bundler, no build step) registering a `settings.section` panel that edits config over HTTP.

## File map

| File | Role |
| --- | --- |
| [package.json](package.json) | `dsh.bundle.patch` + `dsh.client` (`platform: web`, `inject: ['react']`). `main` points at the Host entry. |
| [cordis.patch.yml](cordis.patch.yml) | Mounts the Host plugin row, with an environment-variable disable guard. |
| [lib/index.js](lib/index.js) | **Host entry**: defaults plus `normalize()`, config file I/O, four routes (`widget.css`, `screens.js`, `widget.js`, `config`), and the `tapIndex` injection (critical CSS, boot layer, config, bootstrap guard, deferred scripts). |
| [lib/widget.js](lib/widget.js) | **Widget runtime**: promotes the boot layer to the overlay, runs the chosen screen, handles skip keys, and owns `finish()` (fade out, remove root, unlock scroll, record shown marks). Exposes `__STARTUP_SCREEN_TEMPLATE_API__.replay()`. |
| [lib/screens.js](lib/screens.js) | **Screen pack**: the three built-in screens plus the screen contract (`mount(root, cfg, done)` returning a cleanup function). Add your own here. |
| [lib/widget.css](lib/widget.css) | Overlay and screen styles. Colors come from the `--sst-accent` variable, so nothing is brand-hardcoded. |
| [lib/client.js](lib/client.js) | **Client entry**: handwritten ModuleLoader bundle registering the `settings.section` panel (screen picker, title, subtitle, accent, play mode, duration, skip, Save, Reset, Preview). |
| [preview/index.html](preview/index.html) | Standalone preview. It reproduces the exact Host injection and adds a screen-switch and replay toolbar. Open it in any browser, no DSH needed. |

## The three screens

Pick one with the `screen` config key, the settings page, or the preview toolbar:

| Key | Look | Good starting point for |
| --- | --- | --- |
| `wordmark` | Centered uppercase title, subtitle, thin progress bar | A minimal brand flash |
| `boot-log` | Terminal-style `[ok]` lines appearing on a timer | Dev-tool boot sequences (edit the `lines` array) |
| `steps` | Checklist ticking pending to active to ok | Access and system-check sequences |

## How to make it yours

1. **Rename**: change `NS` and `name` in [lib/index.js](lib/index.js), the `id` in [lib/client.js](lib/client.js), the row `id` and `name` in [cordis.patch.yml](cordis.patch.yml), and the package `name` in [package.json](package.json). The config file name, route prefix, DOM ids, and storage keys follow from those strings.
2. **Restyle**: the look lives entirely in [lib/widget.css](lib/widget.css) and the `innerHTML` templates in [lib/screens.js](lib/screens.js). Keep text escaped with the `esc()` helper, because config values are untrusted.
3. **Add a fourth screen**: append a `yourScreen` object to the registry in [lib/screens.js](lib/screens.js) (`label` plus `mount`), add the key to `ENUMS.screen` in [lib/index.js](lib/index.js), and add an `<option>` in the panel and the preview. The `mount` function must build DOM inside `root`, respect `cfg.durationMs` scaling, call `done` exactly once, and return a cleanup function that clears timers.
4. **Add config keys**: add the key to `DEFAULTS` in both [lib/index.js](lib/index.js) (normalization and persistence) and [lib/widget.js](lib/widget.js) plus the preview (consumption), then wire a control in [lib/client.js](lib/client.js).

## Install

```bash
# From the marketplace/registry
dsh plugin --profile web add startup-screen-template

# Local development (path install; edit plus browser refresh to see changes)
dsh plugin --profile web add link:./skills/rabbit-dsh/examples/startup-screen
```

Then open DSH. The startup screen plays on the first load, and **Settings → Startup Screen** edits the title, subtitle, accent, screen, play mode (`always`, `session`, or `daily`), duration, and skip.

To preview without DSH, open [preview/index.html](preview/index.html) in a browser and use the toolbar to switch screens and replay.

## Invariants to keep when adapting

- **Never lock the page**: the inline bootstrap guard installs a 9-second watchdog that removes the overlay if the widget never starts. Every path in [lib/widget.js](lib/widget.js) ends in `finish()`. Keep both halves of this contract.
- **Idempotent injection**: the `tapIndex` hook checks for an existing marker before injecting, so reloading a profile must not double-inject scripts.
- **Escape inline JSON**: config reaching an inline `<script>` must pass through the `safeJson` escaping in [lib/index.js](lib/index.js). A literal `</script>` inside JSON breaks the page.
- **ModuleLoader id equals package name**: the handwritten client bundle registers under the loader entry name, and the loader rejects any other id.
- **Proxy-safe fetches**: client-side `fetch` uses a relative path without a leading slash (`startup-screen-template/config`), so reverse-proxy subpath and `dsh-app://` desktop deployments keep working.
- **No default export**: the Host entry exports named `name`, `inject`, and `apply` only. The loader unwraps `exports.default ?? exports`, so a default export would hide the others.

Verification steps for this example: [examples/verification.md](../verification.md).
