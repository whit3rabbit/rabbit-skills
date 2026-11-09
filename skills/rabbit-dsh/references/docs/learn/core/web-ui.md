# Web UI Architecture

- 
- Concepts Course
- Core Mechanisms
- Web UI Architecture
On this page

# Web UI Architecture

Audit baseline 0.1.5-alpha.1 @ 5dda764ed3; see [source/npm channels](../../guides/deepseek-harness-status.md).

**One-liner**: the Web UI is a "host process + browser side" **dual-process** architecture: the host (`host/`) holds agents and capabilities, the browser side (`client/`) is a React plugin shell, communicating through the connection layer (`client-connection`); client plugins are the browser halves of "dual-face" packages, hot-updated via HMR.

## Contents

- [1. Dual-process architecture](#1-dual-process-architecture)
- [2. Connection and browser authentication](#2-connection-and-browser-authentication)
- [3. Typed Remote API and controllers](#3-typed-remote-api-and-controllers)
- [4. Client plugins (dual-face)](#4-client-plugins-dual-face)
- [5. The slot system: third-party-extensible UI](#5-the-slot-system-third-party-extensible-ui)
- [6. Browser state and rendering](#6-browser-state-and-rendering)
- [7. Access-mode entry point](#7-access-mode-entry-point)
- [8. Workspace directory selection (directory-picker)](#8-workspace-directory-selection-directory-picker)
- [9. Workspace registry (workspace)](#9-workspace-registry-workspace)
- [10. Frontend static serving (host-frontend-static)](#10-frontend-static-serving-host-frontend-static)
- [11. Build artifacts](#11-build-artifacts)
- [12. Verification](#12-verification)
- [Next steps](#next-steps)

---

## 1. Dual-process architecture

**Why dual-process**: capabilities (agent loop, tools, sandbox) run in the host; the UI renders in the browser. The browser holds no real capability; it only subscribes to the event stream through the connection layer.

Dynamic Cordis plugins follow the same split: `tool-cordis` hands immutable Packages to the Host runner; Host halves run in the host, Client halves start asynchronously through the Client runner after browser approval, and `client-ui-cordis` owns the conversation cards. See [Runtime Inspection and Dynamic Plugins](../../learn/dev/runtime-tools.md) for the lifecycle.

## 2. Connection and browser authentication

`client-connection` owns transport, the shared `/api` handler, and browser sessions. Only the root `GET /` exchanges the launch URL token for a cookie; RPC and WebSocket requests check it even on loopback. The clean root URL alone is not a first-login credential.

Current source rejects `--host 0.0.0.0`. Use SSH forwarding for remote access, and keep launch URLs private. `trustedHosts` controls accepted Host authorities, not authentication.

## 3. Typed Remote API and controllers

`host/apiproxy` is removed. `api/gateway` dispatches generated Remote calls and streams; `api/remotes` assembles selected domain contributions.

- Session history, commands, cold reads, and ownership policy belong to `api/session-controller`.

- Settings and workspaces have separate `api/settings-controller` and `api/workspace-controller` owners.

- Workspace file reads, directory listing, and the Agent-write change feed belong to `api/workspace-files` (new in 0.1.5); the browser side wraps it as the `file` resource protocol — see [Workspace File Service](../../learn/core/workspace-files.md).

- History reads and explicit commands that restore an Agent are distinct operations.

- Session-log export remains a dedicated authenticated HTTP download surface, not a generic gateway configuration object.

- Unknown endpoints have no old API Proxy fallback. See [Remote API gateway](../../learn/core/remote-api-gateway.md).

## 4. Client plugins (dual-face)

One package can provide both a host half and a client half. The client half is a **lazy CJS module table**: the host scans the Loader entries to compose the `window.__DSH_BOOT__` boot map, serves `/plugins/<id>/client.js?rev=<rev>`, and the browser half's side effects **run only on first require** (`window.__ModuleLoader__.load({id, factory})`).

```json
{

  "exports": {

    ".": "./lib/index.js",               // host half

    "./client": "./lib/client.js"        // browser half

  },

  "dsh": {

    "client": {

      "inject": [                        // dependent client rows, named by package, not service short name

        "@deepseek-ai/dsh-api-session-controller",

        "@deepseek-ai/dsh-client-ui-renderer"

      ],

      "platform": "web"

    }

  }

}
```

The browser half registers UI (e.g. a settings-panel section):

```ts
export function apply(ctx: ClientContext): void {

  ctx.slots.inject('settings.section', () =>

    ctx.slots.register({

      name: 'settings.section', id: 'my-plugin', order: 100, label: () => 'My plugin',

    }, PluginPanel))

}
```

## 5. The slot system: third-party-extensible UI

| slot | Role |
| --- | --- |
| settings.section | settings-panel sections (plugins mount their own settings cards here) |
| settings.* | other settings positions |
| other named slots | provided by dsh-client-ui-slots, registered on demand by third-party plugins |

Third-party plugins **don't need to be hardcoded in the Web UI source**: mount into the right spot via a slot. Configurable items are discussed in [Agent Presets](../../features/persona.md).

## 6. Browser state and rendering

| Package | Responsibility |
| --- | --- |
| client/store | React-free observable stores and stable snapshots |
| api/session-controller client face | Session transport and lifecycle/control state |
| client/ui-session | React / Slot adapters, hooks, SessionProvider |
| client/ui-chat | Conversation rendering, details, history images, scroll state |
| client/ui-approval | Approval UI integration |
| client/resources | Unified resource model: dsh-resource:///… addresses + useResource, with protocol owners registering providers (new in 0.1.5) |
| client/file-upload | Blob / exact-byte / ReadableStream uploads returning an opaque receipt for a later prompt (new in 0.1.5) |
| client/ui-dockkit | Docking layout engine (split tree + tabbed panes); an internal package whose exports may change in any release (new in 0.1.5) |
| client/ui-sidebar-right | The right Sidebar: one docking surface per session, owning ctx.sidebarRight / ctx.sidebarRightTabs and the tab domain (new in 0.1.5) |
| client/ui-sidebar-files | Right-Sidebar workspace file-tree tab type, listing one level at a time over workspaceFiles (new in 0.1.5) |
| client/ui-sidebar-textpreview | Right-Sidebar plain-text viewer, the fallback type for file resource addresses (new in 0.1.5) |
| client/ui-schedule | Read-only catalog of active Schedule reminders; the shipped Web bundle mounts it as disabled: true (new in 0.1.5) |

The browser resource model and the four right-Sidebar packages are broken down in [Client Resources and Modules](../../learn/core/client-resources.md); the file service is in [Workspace File Service](../../learn/core/workspace-files.md).

The old `dsh-client-runtime` imports need migration to the relevant owner. Do not replace every old import mechanically with `client-store`: state primitives, Session lifecycle, and React rendering now have separate responsibilities.

Chat folds process content and System prompt rows by default. A completed turn exposes exact token usage only when the loaded window has complete valid accounting; partial totals are not presented as complete. Transcript width can be adjusted. Durable Session events, projected control state, and temporary submission echoes should remain distinct.

## 7. Access-mode entry point

The "Full access / Standard mode" selection in the UI = the **entry point of the permission preset** (see [Permissions](../../user-guide/permissions.md)), not the sandbox itself.

## 8. Workspace directory selection (directory-picker)

`directory-picker` is a capability seam: `ctx.directoryPicker` is its Service Definition, whose only method `capability()` returns a discriminated union describing "how the operator picks a directory". The difference among backends is user interaction, not just implementation:

| kind | Capability | Use case |
| --- | --- | --- |
| native | pick(signal): open a native OS picker | the operator sits in front of the host display |
| browse | list(path?) / createDirectory(path, name): in-app directory listing and creation | a remote client that can't reach the OS picker |

`directory-picker-auto` is the adaptive picker: it samples once at boot (loopback-only bind, non-SSH launch, an available display session; Linux needs `DISPLAY`/`WAYLAND_DISPLAY` + zenity/kdialog on `PATH`), and mounts the matching dual-face backend (native or browse) as a real Loader entry in the in-memory root tree (not persisted). Anything ambiguous falls back to browse.

The two backends:

- `directory-picker-native`: the `native` capability; `pick` opens a native picker each time and resolves an absolute path (cancel returns `null`); platform tools don't use a shell (macOS `osascript`, Linux Zenity→KDialog, Windows modern `IFileOpenDialog` in a spawned child); caller abort terminates the native process

- `directory-picker-browse`: the `browse` capability, one-level directory listing + subdirectory creation (via Node stdlib, with per-OS adaptation); lists only directories, name-sorted, follows symlink-to-directory, the host owns the `hidden` marker; `crumbs` is the root→target ancestor chain; `createDirectory` is non-recursive and validates the name is a single segment

browse primitive failures throw a typed `DirectoryPickerError` (`directory-unreadable`/`directory-exists`/`directory-create-failed`), which the gateway maps 1:1 to wire error codes.

**Mount status: auto is mounted by default** (the Web composition, id `directory-picker`); native/browse are mounted one-or-the-other at its boot, or you can mount one directly in an overlay to pin the interaction.

## 9. Workspace registry (workspace)

`ctx.workspaceRegistry` is a registry of workspace entities: durable workspace records, stable ordering, and a newest-first candidate session index, stored via the domain data form. Consumers see the `Workspace` interface; the entity implementation is package-private.

Registry (`ctx.workspaceRegistry`):

| API | Contract |
| --- | --- |
| create(path, title?) | normalize via fs.realpath, reject non-existent/non-directory, at most one record per canonical path, prepend to the durable order |
| get(id) / list() / resolveByPath(path) | cache-hit queries; list() synchronously in durable order; resolveByPath async (same realpath, rejects missing rather than creating) |
| delete(id) | deletes only the Workspace registration, ordering entry, and session account; directories/files/live Sessions/persisted logs are untouched, and those Sessions become Ungrouped |
| insertBefore(id, before?) | registry-level display-order reorder, DOM-insertBefore-style |
| archiveSession(id) / archivedSessionIds | a registry-global archive set; archiving removes from grouping surfaces but keeps the log and the sessionIds slot |

`Workspace` entity (returned by the registry):

| API | Contract |
| --- | --- |
| setTitle(title) | replace the display title |
| attachSession(id) | validates the header cwd against the workspace path, prepends the new id |
| insertSessionBefore(id, before?) | manual ordering of sessions inside the workspace; the workspace order is unchanged |
| detachSession(id) | deletes only the candidate-index entry |
| status() | an un-cached directory check, 'ok' | 'missing-dir' |

**Mount status: mounted by default** (the Web composition).

## 10. Frontend static serving (host-frontend-static)

`host-frontend-static` is the SPA dist server: a function plugin (config `{distIndex}`) occupying the webserver's **only fallback seat**, serving the built frontend directory with the shell's locking semantics — routes outside the dist root return 403, the dist root and the configured index path render `index.html` with HTTP 200, and any other absent or non-file target (missing file, directory, missing index) returns an empty 404 (**not** a catch-all SPA 200), unknown file extensions serve `application/octet-stream`, and non-GET/HEAD to unmatched named routes return 405. Every index response goes through the webserver's `renderIndex` (which applies the index taps internally), and the boot manifest reaches the page through it; the served index also injects `<base href="/">` so relative assets stay anchored at the site root on deep paths.

`distIndex` is an assembly fact of the composition: `dsh-web-app` resolves it via the frontend package's exports and mounts this plugin. The fallback seat has a single owner (a second claim throws), and is effect-scoped (once dispose frees it, an unclaimed webserver returns 404).

**Mount status: mounted by default** (mounted by the Web composition's web-runtime row).

## 11. Build artifacts

```sh
pnpm run build        # Build the matching source checkout first

pnpm dsh web          # Start the Web profile

pnpm run build:web    # build only the frontend
```

- development HMR runs `pnpm run dev:web` in the source directory (rebuilds `lib/client.js`); `dsh web`'s webserver polls for the rebuild and hot-updates automatically

## 12. Verification

```sh
# inspect the port the host process listens on

lsof -nP -iTCP:3080 -sTCP:LISTEN

# check whether a client plugin is loaded

dsh web --dump-config | grep -i client

# check whether the API gateway / directory picker / workspace / frontend hosting are mounted

dsh web --dump-config | grep -iE "api-gateway|controller|directory-picker|workspace|host-frontend-static"
```

## Next steps

- [Event System](../../learn/core/event-system.md): the event stream the frontend consumes

- [Scheduled Dispatch](../../learn/core/schedule.md): session-local scheduling while the process is running

- [Plugin Anatomy](../../learn/core/plugin-anatomy.md): dual-face is one plugin form

- [Write your first plugin](../../learn/dev/hello-plugin.md)
