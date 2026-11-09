# Client Resources and Modules

- 
- Concepts Course
- Core Mechanisms
- Client Resources and Modules
On this page

# Client Resources and Modules

Audit baseline 0.1.5-alpha.1 @ 5dda764ed3; see [source/npm channels](../../guides/deepseek-harness-status.md).

**One-liner**: live data in the browser is expressed uniformly as a **resource address** — one `dsh-resource://<type>/…` address is one resource, the protocol's owning package registers exactly one provider through `ctx.resources.register`, and any slot component reads it with `useResource<P>(address)`; the right Sidebar is then `ui-dockkit` (a host-agnostic engine) + `ui-sidebar-right` (the product host) + two tab-type packages (`files` / `text`).

All four packages are new in `0.1.5-alpha.1`. After reading this you can answer: how one address becomes a self-updating value, how a plugin contributes its own protocol, why dockkit is not a plugin, and what actually happens after you click a file in the tree.

## Contents

- [1. The resource model: one address, one provider](#1-the-resource-model-one-address-one-provider)
- [2. ctx.resources: register, pin, subscribe](#2-ctxresources-register-pin-subscribe)
- [3. useResource: four states](#3-useresource-four-states)
- [4. The client module system: dsh.client → browser bundle](#4-the-client-module-system-dshclient-browser-bundle)
- [5. How the right Sidebar composes](#5-how-the-right-sidebar-composes)
- [6. Two-stage tab-type registration](#6-two-stage-tab-type-registration)
- [7. Worked example: the life of one dsh-resource://file/… address](#7-worked-example-the-life-of-one-dsh-resourcefile-address)
- [8. Source evidence](#8-source-evidence)
- [9. Verification](#9-verification)
- [Next steps](#next-steps)

---

## 1. The resource model: one address, one provider

- A resource address is a `dsh-resource://<type>/…` URL whose **host is the protocol name** (`RESOURCE_SCHEME = 'dsh-resource'`, and `protocolOf(address)` takes the host).

- A protocol that needs a scope encodes it in the path, as `dsh-resource://file/session/<sessionId>/<path relative to the workspace root>` and `dsh-resource://file/absolute/<absolute path>` do. The model itself knows only addresses.

- Addresses under any other scheme (`sidebar://guide`) are **navigation addresses** and name no resource.

- `ResourceProtocolMap` (declared in `packages/client/ui-slots/src/index.ts`) is the declaration-merged protocol → value-type roster: a consumer names the protocol as a type argument and receives the owner's value type **without importing the owner's runtime**.

## 2. ctx.resources: register, pin, subscribe

| Member | Contract |
| --- | --- |
| register(provider) | registers the one provider for a protocol; a second registration throws. Returns an idempotent disposer (the caller holds it in its own ctx.effect) |
| pin(address, signal) | keeps a resource open without subscribing, until the signal aborts; an already-aborted signal pins nothing |
| source(address) | the bare observable behind the hook; getSnapshot() reads without holding the resource |

The provider contract (`src/client/contract.ts`):

```ts
interface ResourceProvider<P> {

  readonly protocol: P

  open(address: string, ctx: { signal: AbortSignal }): AsyncIterable<RemoteResult<Value>>

  reload?(address: string): void

}
```

Three hard rules:

- `open`'s **first frame is the current content**, and every later frame is one change;

- **a failure is a frame, not a throw** — `{ ok: false, error }` turns the resource `failed` while keeping the last value; a throw inside the stream is a programming error and is not caught;

- it must honour `signal`: the stream is aborted when the last holder releases.

Lifecycle: one record per address, kept for the **page lifetime and never dropped** (only its state is discarded). The holder count is subscribers plus pins; the first holder opens the provider's stream, later holders share it, and the last release aborts the stream and resets the snapshot to idle. Keeping the record is what makes `source()` reference-stable across React's render-then-subscribe window and a StrictMode remount.

## 3. useResource: four states

The browser half of `@deepseek-ai/dsh-client-resources` builds the registry at apply's top level, then:

```ts
ctx.slots.provideRoot({ keyedHooks: { resource: address => resources.source(address) } })
```

so **every** slot component receives `useResource` in its props, whatever its scope.

| status | Meaning |
| --- | --- |
| none | no provider is registered for that protocol, or the address is not a dsh-resource:// URL |
| loading | a provider is open and has not yielded yet |
| live | value is the latest ok frame's value |
| failed | the latest frame reported a failure; value keeps the last one and failure is this one |

`reload()` asks the provider for a fresh frame; it is a no-op when the protocol has no provider or no `reload`.

## 4. The client module system: dsh.client → browser bundle

Browser plugins are not imported by the host; they are **declared and lazily loaded**:

| Declaration | Purpose |
| --- | --- |
| package.json#dsh.client.platform: "web" | declares a browser plugin |
| exports["./client"] | the browser half's entry bundle |
| dsh.client.inject[] | module-graph dependencies (bundle load order) — not the same thing as cordis inject service dependencies |
| dsh.client.external[] | extra module requests beyond the platform seed table |

The host half of `@deepseek-ai/dsh-client-modules` scans the enabled Loader entries, composes the boot graph (injected as `window.__DSH_BOOT__`), and serves each bundle under `/plugins`; the browser half loads them **lazily**: executing a bundle only registers a factory, and module bodies (CSS injection included) run at materialization.

**`ui-dockkit` is not a plugin**: it declares no `dsh.client` and is statically linked into its consumer's bundle through tsdown's `staticLinked` preset (`packages/client/tsdown.client.ts`). It is a library, not a loadable browser plugin — which is also why its README calls it an internal engine with no stable API promise.

## 5. How the right Sidebar composes

`ui-sidebar-right` (`inject = ['slots', 'layout', 'locale', 'resources']`) provides two services and one domain:

| Name | Role |
| --- | --- |
| ctx.sidebarRight | the navigation and layout controller: openResource / openTab / close / active / isExpanded / toggleExpanded / focus / split / float / dock |
| ctx.sidebarRightTabs | the tab-type registry: register(definition) / candidates(address) / claim(address, kind?) |
| the Tab domain | per (Session, tab id) it retains navigation, an abort signal, and bound actions; only record removal or plugin unload aborts the signal |

It is also what binds dockkit to the product: every open tab pins its resource through `ctx.resources.pin(address, signal)`, so switching away and back reads the latest value instead of reopening the stream.

The seats, all declared at runtime by `ui-sidebar-right`:

| Seat | Kind | Purpose |
| --- | --- | --- |
| rightbar | component | the panel itself; it declares the child seats sidebar.right.pane.tab (keyed), .title (keyed), and sidebar.right.tab.menu.item (list) |
| conversation.session.header.corner | component | the expand button shown while the panel is collapsed |
| sidebar.right.pane.tab | keyed | a tab's body, keyed by the type definition's id |
| sidebar.right.tab.guide | chain | replace the guide page's contents without replacing the tab |
| sidebar.right.tab.menu.item | list | append content-level menu items (layout gestures belong to dockkit) |

## 6. Two-stage tab-type registration

- **The type**: `ctx.sidebarRightTabs.register({ id, kind, patterns?, priority?, canOpen?, title, guide? })` — a static declaration returning a disposer; `id` is this implementation's identity in the tab system, and a second registration of an `id` throws.

- **The body**: `ctx.slots.register({ name: 'sidebar.right.pane.tab', key: definition.id }, Body)`, where the body reads `{ sidebar, panel, tab }` through `useTabInfo()`.

Routing rules (the editor-resolver convention):

| Dimension | Rule |
| --- | --- |
| band | extension (default, highest) > builtin > fallback |
| pattern | one containing : matches the whole address (dsh-resource://file/**); one without matches the URI's path at any depth (*.md, ignoring case) |
| ordering within a band | the longer matched pattern wins, then registration order |
| veto | canOpen(address) returning false removes a candidate |

The two shipped types:

| Package | kind | priority | patterns | Role |
| --- | --- | --- | --- | --- |
| ui-sidebar-files | files | builtin | none (a page, it claims no address) | the workspace file tree; guide entry at order 10 |
| ui-sidebar-textpreview | text | fallback | dsh-resource://file/** | the plain-text viewer; any more specific type can take those addresses |

`ui-sidebar-files` is a page: it claims no address, offers one entry box in the guide, and a file row opens through `tab.actions.openResource` for the `file` viewers to claim.

## 7. Worked example: the life of one dsh-resource://file/… address

The division of labour is the point: **metadata rides the resource stream, content rides paged calls**. A `file` resource's value is only `{ absolutePath, version, bytes?, changed }`; the viewer reads the text itself one page at a time, so when the host reports a write the text on screen is never silently replaced — a reloadable notice bar appears instead.

## 8. Source evidence

| Location | Symbol / fact |
| --- | --- |
| packages/client/resources/src/client/contract.ts | ResourceProvider, Resources, ResourceSnapshot, UseResource, ResourceStatus, ResourceOpenContext, the ctx.resources declaration merge |
| packages/client/resources/src/client/resources.ts | RESOURCE_SCHEME, protocolOf, ResourceRegistry, ResourceRecord |
| packages/client/resources/src/client/index.ts | inject = ['slots'], provideRoot({ keyedHooks: { resource } }) |
| packages/client/resources/src/index.ts | the host half is empty (apply(): void {}) — the resource model lives in the browser only |
| packages/client/ui-slots/src/index.ts | interface ResourceProtocolMap {} (the declaration-merge host) |
| packages/client/modules/README.md | the dsh.client declaration, platform: 'web', exports["./client"], dsh.client.external, window.__DSH_BOOT__, /plugins |
| packages/client/tsdown.client.ts | staticLinked, isStaticLinkedConfig, clientBundle |
| packages/client/ui-dockkit/src/contract/types.ts | LayoutState, LayoutOp, PaneId/SplitId/TabId, TabRecord, DockMode, DockZone |
| packages/client/ui-dockkit/src/contract/adapter.ts | DockLabels, TabRenderer, TabMenuExtras, DockIntents |
| packages/client/ui-sidebar-right/src/client/index.ts | inject, ctx.reflect.provide('sidebarRight' / 'sidebarRightTabs'), the rightbar and conversation.session.header.corner seats |
| packages/client/ui-sidebar-right/src/client/service.ts | the ten ISidebarRight methods |
| packages/client/ui-sidebar-right/src/client/tab-registry.ts | SidebarRightTabPriority (extension/builtin/fallback), register, candidates, claim, coexists |
| packages/client/ui-sidebar-right/src/client/contract/params.ts | SidebarRightResourceParamsMap, SidebarRightTabParamsMap, SidebarRightNavigationParams |
| packages/client/ui-sidebar-files/src/client/definition.ts | FILES_KIND = 'files', FILES_ID, priority: 'builtin', guide order 10 |
| packages/client/ui-sidebar-textpreview/src/client/definition.ts | TEXTPREVIEW_KIND = 'text', patterns: ['dsh-resource://file/**'], priority: 'fallback', canOpen |
| packages/client/ui-sidebar-textpreview/src/client/rpc.ts | hostFileOf, createReadPage, WorkspaceFilesReadRemote |
| packages/bundle/web-app/cordis.patch.yml | the resources / ui-sidebar-right / ui-sidebar-textpreview / ui-sidebar-files rows |

## 9. Verification

```sh
# 1. The browser plugin roster and load order (resources before ui-sidebar-right)

dsh web --dump-config | grep -iE "modules|connection|resources|ui-sidebar|ui-dockkit"

# 2. dockkit declares no dsh.client: a static-linked library, not a plugin

grep -n '"dsh"' packages/client/ui-dockkit/package.json || echo "no dsh.client: static-linked library"

grep -n "staticLinked" packages/client/ui-dockkit/tsdown.config.ts

# 3. The scheme and the address grammar

grep -n "dsh-resource" packages/client/resources/src/client/resources.ts \

  packages/api/workspace-files/src/client/types.ts

# 4. In the browser: open a session's right Sidebar → Files tab → click a text file.

#    DevTools should show POST /api calls for workspaceFiles.stat / read,

#    plus the per-session workspaceFiles.changes stream on /api/remote.mux.
```

One observable behaviour: the same file opened in two different sessions is **two tabs** (different addresses), while opening the same address again only focuses the existing tab and delivers new `navigation.params` — the content identity is the whole address.

## Next steps

- [The Workspace File Service](../../learn/core/workspace-files.md): the host endpoint behind the `file` protocol

- [Web UI Architecture](../../learn/core/web-ui.md): the dual-process split, the slot system, and client plugins

- [Remote API Gateway](../../learn/core/remote-api-gateway.md): the transport and auth under the resource streams

- [Plugin Anatomy](../../learn/core/plugin-anatomy.md): the shape and manifest of a dual-face package
