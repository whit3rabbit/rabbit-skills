# Dynamic Plugin Runtime: the Host/Client Halves

- 
- Concepts Course
- Plugin Development
- Dynamic Plugin Runtime: the Host/Client Halves
On this page

# Dynamic Plugin Runtime: the Host/Client Halves

**In short**: `@deepseek-ai/dsh-cordis-host-runner` keeps immutable Packages in process memory, runs Host halves in a `node:vm` sandbox, and routes browser calls through one handler table; `@deepseek-ai/dsh-cordis-client-runner` evaluates the closure in a page and mounts the plugin through the loader behind a whitelisting facade; `@deepseek-ai/dsh-client-ui-cordis` renders definitions, run state, and approval entry points as a panel, keyed cards, and `@pluginId` completion.

**Audit baseline 0.1.5-alpha.1 @ 5dda764ed3**: package names, ctx keys, event names, config keys, error codes, and sandbox symbols are all verified point-by-point against the official source.

[Runtime Inspection and Dynamic Cordis Plugins](../../learn/dev/runtime-tools.md) covers **what the model sees**: the seven `tool-cordis` tools, the `cordis_define` argument shape, and the `run/update/stop/undefine` semantics. This page goes one level down into **the machinery**: who stores a definition, where a Host half executes, how a Client half reaches the browser, and how the UI reports state. The seven-tool catalogue is not repeated here — read that page for it.

## Contents

- [1. The four packages](#1-the-four-packages)
- [2. cordis-host-runner: definition registry and the Host-half sandbox](#2-cordis-host-runner-definition-registry-and-the-host-half-sandbox)
- [3. cordis-client-runner: the browser half](#3-cordis-client-runner-the-browser-half)
- [4. ui-cordis: the browser surfaces](#4-ui-cordis-the-browser-surfaces)
- [5. The dual-half contract: what a Package must export](#5-the-dual-half-contract-what-a-package-must-export)
- [Sources](#sources)
- [Verification](#verification)

---

## 1. The four packages

| Package | Face | ctx key / registration | Responsibility |
| --- | --- | --- | --- |
| @deepseek-ai/dsh-tool-cordis | Host | registers on ctx.tools | The seven model tools plus @pluginId reference injection (see Runtime inspection) |
| @deepseek-ai/dsh-cordis-host-runner | Host | ctx.dynamicCordisRunner, ctx.cordisInspect | Definition registry, vm sandbox, Host-half fiber lifecycle, invoke handler table |
| @deepseek-ai/dsh-cordis-client-runner | Client | browser ctx.dynamicCordisRunner | Evaluates and mounts/unmounts Client halves, answers run requests, guard facade |
| @deepseek-ai/dsh-client-ui-cordis | Client | registers slots and an input source | Frame-wide panel, four keyed tool cards, @pluginId completion |

The web bundle loads the first three from `packages/bundle/web-app/cordis.patch.yml` (the `cordis-host-runner` / `cordis-client-runner` / `ui-cordis` rows). `tool-cordis` is **not in any shipped composition** — it is an explicit opt-in, and the `tool-cordis` row in `packages/preset/agent-presets/presets/cordis/agent.cordis.yml` is how you enable it. Without the host runner, the tools never see `ctx.dynamicCordisRunner` and never activate.

## 2. cordis-host-runner: definition registry and the Host-half sandbox

The service is `DynamicCordisRunnerService` (`static inject = ['tools']`), exposed as `ctx.dynamicCordisRunner` through a `declare module '@deepseek-ai/cordis'` merge. It accepts exactly one config field:

| Config key | Default | Meaning |
| --- | --- | --- |
| vmTimeoutMs | 5000 | Milliseconds one synchronous vm evaluation may run (z.number().min(1).default(5000)) |

### The definition registry

`DynamicCordisRegistry` is a plain in-memory `Map` with no persistence: a DSH restart clears it. Four counters mint every identity, with predictable shapes that stay globally unique:

| Identity | Mint | Shape |
| --- | --- | --- |
| Plugin ID | mintPluginId(prefix) |

-, skipping used suffixes |
| Package ID | mintPackageId() | pkg- |
| Plugin Run ID | mintPluginRunId() | run- |
| Approval ID | mintApprovalRequestId() | approval- |

One `DynamicCordisPlugin` holds immutable `packages`, `currentPackageId` (the committed version), `nextPackageId` (the target), the live `run`, and the latest `latestRun` attempt record. Pending approvals live in a separate `pendingRequests` index managed by `armRequest` / `peekRequest` / `claimRequest` / `disarmRequest` / `pendingRequestFor` — **the first answer wins**.

### The Host-half sandbox

A Host half is not an ordinary `import`. `createSandbox(pluginId, { handle })` builds a fresh `node:vm` realm, and `evaluateHostCode(sandbox, code, id, vmTimeoutMs)` runs the source as an async function body. At define time, `precheckCode(code, 'code.host' | 'code.client')` compiles without running, surfacing syntax errors early.

The symbols exposed to the sandbox are the fixed `HOST_BUILTIN_INSPECTION` list:

| Symbol | Purpose |
| --- | --- |
| ctx | Restricted Cordis Context: ctx.get / ctx.on / ctx.provide / ctx.effect |
| harness | handle(method, fn), defineTool(definition), registerTool(ctx, tool) |
| console | Write-through logging tagged [cordis:] |
| btoa / atob | UTF-8 base64 encode/decode |
| TextEncoder / TextDecoder | Standard codec constructors |

Node globals are deliberately withheld, and calling one throws a teaching redirect (`NODE_API_REDIRECTS`): `require` → use the cordis services on `ctx`; `setTimeout` / `setInterval` / `setImmediate` / `clearTimeout` / `clearInterval` → declare `inject: ['timer']` and use `ctx.timeout` / `ctx.interval`; `fetch` → declare `inject: ['web']`. Separately, `DUAL_REALM_INSTANCEOF_PRELUDE` patches only the vm's `Object` / `Array` / `Error` constructors with `Symbol.hasInstance` so host values passed in as arguments, events, or service results still satisfy `instanceof`.

The sandbox **isolates globals but is not a security boundary**: Node globals are absent or redirected to Cordis services, and a Host half receives a facade without framework internals — but the services it declares reach the live runtime. As the README puts it, treat a dynamic package like bash access.

### The registration boundary (guard)

`guard.ts` is the only gate from "sandbox product" to "real runtime":

- `isPlugin(value)` / `pluginName(plugin)`: plugin-shape checks.

- `normalizeHandler(method, fn)`: normalizes a `harness.handle` argument into `{ method, handler }` and stores it in this run's handler table.

- `sandboxDefineTool` / `sandboxRegisterTool`: `harness.defineTool` runs the real schema DSL and stamps `DYNAMIC_TOOL`; `harness.registerTool` accepts only a stamped definition.

- `sandboxContext(ctx, reportFailure)`: the Host half's `ctx` facade — `CTX_VERBS` (`effect` / `on` / `once` / `provide` / timer family) pass through, `ctx.get(name)` is an optional lookup, and direct `ctx.serviceName` access requires the service in the fiber's `inject` (`declaredInjects` reads the keys of `ctx.fiber.inject`); otherwise it throws a guard error with the fix.

- `guardedPlugin(plugin, reportFailure)`: wraps registration so post-activation rejections travel the same reporting path.

### Fiber lifecycle

`startHostHalf(group, plugin, reportGuardFailure)` mounts the sandbox's plugin under the `cordis-dynamic` group fiber (lazily created by `requireGroup()` as `rootCtx.plugin({ name: 'cordis-dynamic', apply: () => {} })`), awaits `fiber.await()`, and returns. A startup failure disposes the fiber before rethrowing, so a failed run never lingers. `missingServices(ctx, fiber)` compares the fiber's `inject` keys against `ctx.get(name)` to produce the `waitingFor` list — a settled-but-inactive fiber is legal cordis semantics (it activates when the service appears), not an error.

Stopping needs no helper: everything a Host half registers is an effect on its own fiber, so `fiber.dispose()` unwinds it. `retract(plugin)` deletes `plugin.run`, runs every `handlerDisposers` entry, awaits `fiber.dispose()`, and finally emits `cordis/dynamic-retract`.

### The invoke handler table

Handlers registered with `harness.handle(method, fn)` live in `run.handlers: Map<string, DynamicCordisHandler>`, with `handlerDisposers` recording each undo. The browser's `host.call(method, args)` arrives over Typert Remote at `@Remote('invoke')`:

```ts
@Remote('invoke')

async invoke(pluginId, pluginRunId, method, args): Promise<DynamicCordisInvokeResult>
```

It answers with four failure codes (`DynamicCordisInvokeResult`):

| code | Meaning |
| --- | --- |
| plugin-not-running | The plugin has no active run |
| stale-run | The call belongs to a replaced activation |
| method-not-found | That method was never registered |
| handler-error | The handler threw (the owning Session is steered too) |

### Events and Remote verbs

Events a Host half emits (`interface Events` in `types.ts`):

| Event | When |
| --- | --- |
| cordis/request-run | A Client-bearing activation needs a page (and possibly a human decision) |
| cordis/request-run-resolved | A pending request left the answerable state |
| cordis/dynamic-package | One exact activation is now live in the Host |
| cordis/dynamic-retract | One exact activation was withdrawn |
| cordis/inspect-query | Request one read-only query from a browser-side Client inspect provider |
| cordis/inspect-query-resolved | A query settled or was cancelled |

The `@Remote` verbs exposed to the browser:

| Verb | Purpose |
| --- | --- |
| runHostHalf | Start the Host half after approval (or on a direct panel gesture) |
| getClientCode | Hand the page the Client source of one exact run |
| resolveRequestRun | Settle a model-driven Client activation (first answer wins) |
| settleUserRun | Settle a panel-driven run |
| stopFromPanel / undefineFromPanel | Stop/remove from the panel and inject the outcome into the owning Session |
| inventory | The frame-wide inventory (no source code) |
| syncInspectManifest | Replace the Host-side mirror of the Client provider directory |
| resolveInspectQuery | Settle one cross-plane inspect query with a page result |
| reportRenderFailure | Record a post-load render crash |
| reportClientGuardFailure | Record a post-activation guard rejection |
| invoke | Route a Client → Host handler call |

The tools call these non-Remote methods directly: `define`, `run`, `stop`, `undefine`, `snapshot`, `reference`, `listPlugins`, `inspectPlugin`, `inspectPackage`.

The Host-side inspect directory is `CordisInspectRegistryService`, exposed as `ctx.cordisInspect`: `register` takes Host providers, `syncClientManifest` mirrors the Client directory, `list` merges both planes, and `query` runs locally or turns into a `cordis/inspect-query`. **The first-party Host providers do not live here** — they are in `tool-cordis/src/providers.ts`, documented in [Runtime inspection](../../learn/dev/runtime-tools.md).

## 3. cordis-client-runner: the browser half

The plugin name is `cordis-client-runner`, with `inject = ['loader', 'modules', 'slots', 'remote', 'remote.dynamicCordisRunner']`. Declaring `remote.dynamicCordisRunner` keeps the plugin **parked until the Host namespace exists**, so a page never loads a browser half whose host half it could not reach.

It provides `ctx.dynamicCordisRunner: CordisRunnerFace` on the browser context:

| Member | Purpose |
| --- | --- |
| activeRuns | Per-plugin in-flight approval or activation, observable |
| lastRunError | This page's latest run failure |
| renderFailures | This page's latest render crash per package |
| reconcileApprovals(rows) | Align pending approval rows with the Host inventory |
| approve(requestId, approveFutureVersions) / decline(requestId) | Answer a model request |
| startUserRun(request) | Run directly from a user gesture (the gesture authorizes it) |
| subscribe / getSnapshot / isLoaded | Observe what this page has loaded |

### Event subscriptions

`apply` subscribes with `ctx.remote.$on(...)` (`$on` hands the listener the Host's own argument list):

| Event | Page action |
| --- | --- |
| cordis/request-run | orchestrator.open(request) records the pending activity |
| cordis/request-run-resolved | orchestrator.close(requestId) |
| cordis/dynamic-retract | runner.retract(pluginId, pluginRunId) unloads |
| cordis/inspect-query | Run the query on this page's provider and send the result back |
| cordis/inspect-query-resolved | Close the pending query |

### Closure evaluation

`evaluateClientHalf(pluginId, clientCode, env, styles)` runs the source as an async function body whose parameters are a fixed symbol surface:

| Parameter | Content |
| --- | --- |
| React | The React runtime (no JSX transform — build elements with React.createElement) |
| console | [cordis:]-tagged console; console.error is additionally copied into the load report |
| styles | DynamicCordisStyles; insert(css) returns a disposer, and unload cleans up automatically |
| host | { call(method, args = null) }, routed to this package's Host-half handler |
| harness | A teaching trap: harness.* belongs to the Host half |
| setTimeout / setInterval / clearTimeout / clearInterval | Teaching traps → declare inject: ['timer'] |
| fetch / require | Teaching traps → use a Host handler or a ctx service |
| process / Buffer | undefined (so typeof process probes stay safe) |

`DYNAMIC_CLIENT_REDIRECTS` is the single home of those redirect messages. The closure must `return` a plugin — either `(ctx) => {…}` or `{ name, inject, apply(ctx) }` — or it throws a teaching error; `isDynamicCordisPlugin` performs the host-side mirror of that shape check.

### Mounting: loader plus module table

`DynamicCordisPackageRunner` is the page-side load engine:

- Evaluate the closure; failure → `cause: 'evaluate'`.

- `moduleId = 'dyn/<pluginId>'` (also the loader entry name and fiber name).

- `modules.invalidate(moduleId)`, then write the factory into the `window.__ModuleLoader__` sink (a missing sink means the page booted outside the web shell).

- `loader.create({ name: moduleId })`; no resolvable fiber → `cause: 'module-import'`.

- `await fiber.await()`; a throw → `cause: 'activate'`.

- Record `waitingFor = Object.keys(fiber.inject).filter(name => ctx.get(name) === undefined)` — settled but waiting on services this page lacks counts as **success** (parked).

Teardown is `loader.remove(entryId)` + `modules.invalidate(moduleId)` + `styles.dispose()`: removing the entry cascades fiber disposal, so slot entries and facade effects go with it. Each package id has a serial queue (`enqueue`) so a slow load cannot be overtaken; loading the same revision twice is idempotent, a newer revision replaces the old one, and the same revision loads afresh after a retract.

### The guard facade

`dynamicCordisContext(ctx, env)` is the browser twin of the Host `sandboxContext`:

- `ctx.get(name)`: optional lookup returning the real service (Context returns are denied).

- `ctx.<service>`: allowed only when the fiber's `inject` declared it, otherwise a "declare it in inject" teaching error.

- `ctx.<verb>`: `CTX_VERBS` (`effect` / `on` / `once` / `provide` / timer family) pass; timer verbs additionally require `inject: ['timer']`.

- The `slots` seat: `register` assigns a page-local shadowing priority, records a ledger row, and registers component ownership (render-crash attribution depends on it).

- The `theme` seat: `overrideTokens`' source is **forced** to `<pluginId>.<packageId>`, so a dynamic package can never impersonate or evict another theme layer.

Render crashes are observed through `slots.onEntryError`: only components this runner seated count. The report carries the `slot`, `abdicated` (whether the crash retired the entry), and an author-facing message. One observation feeds two outlets — `reportRenderFailure` goes to the Host (for the model and `cordis_inspect_self`), while the page's `renderFailures` feeds the panel.

### Orchestration: Host first, then Client

`CordisRunOrchestrator.drive(plan)` has a fixed order:

Starting the Host half first means a host-half failure short-circuits before the browser moves; then the source is fetched, the Client half loads, and exactly one resolution is sent. Success carries the loaded `pluginRunId` and any parked service names; failure carries one reason — `rejected` (user refusal), `host-half-failed`, or `client-half-failed` — the latter two with the failing stage (`evaluate` / `module-import` / `activate`) and message. One plugin has at most one in-flight orchestration (`inFlight` deduplication).

## 4. ui-cordis: the browser surfaces

`inject = ['slots', 'locale', 'inputTriggers', 'remote', 'remote.dynamicCordisRunner', 'dynamicCordisRunner']`, registering five surfaces:

| Seat | Key | Content |
| --- | --- | --- |
| sidebar.footer.action | id cordis-panel | Frame-wide panel: badge count plus one row per definition |
| tool.call.toolview | cordis_define | Read-only definition card (Host/Client source tabs) |
| tool.call.toolview | cordis_run | Run card plus the tool.view.cordis child seat (kind: 'keyed', scope: 'session') |
| tool.call.toolview | cordis_stop / cordis_undefine | Compact action rows |
| inputTriggers source | trigger @, name cordis | @pluginId completion |

**The run/stop switch lives on the panel rows, not on the definition card.** `CordisDefineRow` is a pure record: the name, purpose, source, and current state the model wrote — no switch, no approval button, just a pointer to the panel. The panel row's `onRun` / `onStop` / `onRemove` / `onApprove` / `onDecline` are the lifecycle operations, reaching `stopFromPanel` / `undefineFromPanel` / `inventory` through `CordisDynamicPort`, while run and approval go through the browser runner.

Each row shows **two independent facts** — what the Host is running and what this page has loaded. `cordisVisibleStatus(row, packageId, loaded)` yields exactly three readings: `idle` (no active run for that package), `client-pending` (Host up, this page not loaded), and `running` (no Client half, or this page loaded that `pluginRunId`). A reloaded page therefore offers "load back into this page", while a host-only definition reads plainly running and offers the stop alone.

Panel data comes from `createCordisInventory`: one global `inventory` read, single-flight, re-read on announcements rather than patched in place. `cordis/dynamic-package` / `cordis/dynamic-retract` / `cordis/request-run` / `cordis/request-run-resolved` all trigger a refresh, and `connection/reset` calls `reset()` to discard an in-flight read so a reconnect never publishes the old host's rows. The card view models (`cordisDefineCard` / `cordisRunCard` / `cordisActionCard`) derive from frozen call/result slices, so replay renders the same card.

## 5. The dual-half contract: what a Package must export

**Host half (`code.host`)**

- A plain JavaScript async function body that must `return` a plugin: `(ctx) => {…}` or `{ name, inject, apply(ctx) {…} }`.

- Only the sandbox symbols are available: `ctx`, `harness`, `console`, `btoa`/`atob`, `TextEncoder`/`TextDecoder`.

- Expose a call surface with `harness.handle(method, fn)` for the Client half's `host.call`.

- For model-visible tools: `harness.defineTool(definition)` + `harness.registerTool(ctx, tool)`.

- For host capabilities: declare `inject: ['fs' | 'web' | 'bash' | 'timer' | …]` on the returned plugin, then use `ctx.get` / `ctx.<service>`; reading an undeclared service is rejected by the facade.

**Client half (`code.client`)**

- It must also `return` a plugin; the object form's `inject` is the **only declaration site** for services, so a plain function reaches none.

- The closure symbols are fixed: `React`, `console`, `styles`, `host`; `harness` / browser timers / `fetch` / `require` are teaching traps, and `process` / `Buffer` are `undefined`.

- Call the Host half with `host.call(method, args)`; when the argument is omitted the handler receives `null` (the wire carries JSON, and `undefined` is not JSON).

- Contribute UI by registering into slots; use `styles.insert(css)` for CSS and `theme.overrideTokens` for theme layers (whose source is forced).

**How this differs from a static cordis plugin**

|  | Static cordis plugin | Dynamic Package |
| --- | --- | --- |
| Code location | src/index.ts in a package, compiled into lib/ | A function body submitted by cordis_define, in process memory only |
| Mounting | A cordis.yml / patch row, mounted at startup | Activated per Package version by cordis_run |
| Lifecycle | Mounted/unmounted with the composition, restored on restart | stop ends the run, undefine removes it; a restart loses everything |
| Permission boundary | Full ctx, may import any module | Host half: vm sandbox + Node API redirects; Client half: closure + whitelisting facade |
| Scope | Process/composition scope | Owned by the Session that defined it; other sessions read it as absent |
| Versioning | npm package version | Immutable Packages plus currentPackageId / nextPackageId |
| Trust | Equal to the deployment | Treated like bash access |

Both forms **converge on the same Cordis lifecycle**: a static plugin goes through `ctx.plugin(...)`, a dynamic Host half through `group.ctx.plugin(guardedPlugin(...))` under the `cordis-dynamic` group, and a Client half through `loader.create` into the module table — so activation gating, fiber-effect cleanup, and status projection share one semantics. For plugin forms and patch application order see [Plugin Anatomy](../../learn/core/plugin-anatomy.md); for writing a static plugin see [Write your first plugin](../../learn/dev/hello-plugin.md); for the dual-face transport layer see [Web UI Architecture](../../learn/core/web-ui.md).

## Sources

| Location | Symbol / fact |
| --- | --- |
| packages/extensions/cordis-host-runner/src/index.ts | DynamicCordisRunnerService (static inject = ['tools']), Config.vmTimeoutMs default 5000, the ctx.dynamicCordisRunner merge, define / run / stop / undefine / snapshot / reference / listPlugins / inspectPlugin / inspectPackage, requireGroup()'s cordis-dynamic, and retract's handlerDisposers → fiber.dispose → cordis/dynamic-retract |
| packages/extensions/cordis-host-runner/src/index.ts:226,324,383,412,437,479,497,510,524,683,717,740 | The twelve @Remote verbs: undefineFromPanel, runHostHalf, getClientCode, resolveRequestRun, settleUserRun, stopFromPanel, syncInspectManifest, resolveInspectQuery, inventory, reportRenderFailure, reportClientGuardFailure, invoke |
| packages/extensions/cordis-host-runner/src/types.ts | CordisDynamicPluginId / CordisDynamicPackageId / CordisDynamicPluginRunId / ApprovalRequestId / CordisInspectRequestId, CordisDynamicRunMode, CordisRunStatus, the four DynamicCordisInvokeResult codes, and the six cordis/* events in interface Events |
| packages/extensions/cordis-host-runner/src/registry.ts | DynamicCordisRegistry, mintPluginId (-), mintPackageId (pkg-), mintPluginRunId (run-), mintApprovalRequestId (approval-), armRequest / peekRequest / claimRequest / disarmRequest / pendingRequestFor, DynamicCordisHandler |
| packages/extensions/cordis-host-runner/src/sandbox.ts | HOST_BUILTIN_INSPECTION (ctx / harness / console / btoa / atob / TextEncoder / TextDecoder), createSandbox, evaluateHostCode, precheckCode, NODE_API_REDIRECTS, DUAL_REALM_INSTANCEOF_PRELUDE |
| packages/extensions/cordis-host-runner/src/guard.ts | normalizeHandler, sandboxDefineTool, sandboxRegisterTool, sandboxContext, declaredInjects, guardedPlugin, isPlugin, pluginName, CTX_VERBS / TIMER_VERBS, DYNAMIC_TOOL |
| packages/extensions/cordis-host-runner/src/lifecycle.ts | startHostHalf (a guarded child under the group fiber, disposed before rethrow on failure) and missingServices |
| packages/extensions/cordis-host-runner/src/inspect-registry.ts | CordisInspectRegistryService, the ctx.cordisInspect merge, register / syncClientManifest / list / query / resolveClientQuery |
| packages/extensions/cordis-client-runner/src/client/index.ts | name = 'cordis-client-runner', inject = ['loader','modules','slots','remote','remote.dynamicCordisRunner'], CordisRunnerFace, the browser ctx.dynamicCordisRunner, and the five ctx.remote.$on('cordis/…') subscriptions |
| packages/extensions/cordis-client-runner/src/client/evaluator.ts | evaluateClientHalf, the closure parameters ['React','console','styles','host','harness', …traps, 'process','Buffer'], DYNAMIC_CLIENT_REDIRECTS, DynamicCordisStyles.insert, isDynamicCordisPlugin |
| packages/extensions/cordis-client-runner/src/client/runtime.ts | DynamicCordisPackageRunner, moduleIdOf → dyn/, ModuleLoaderSink.__ModuleLoader__, loader.create / loader.remove, modules.invalidate, DynamicCordisLoadErrorCause (evaluate / module-import / activate), waitingFor |
| packages/extensions/cordis-client-runner/src/client/guard.ts | dynamicCordisContext, CTX_VERBS / TIMER_VERBS, guardedSlots (priority + ledger + claim), guardedTheme (source forced to .) |
| packages/extensions/cordis-client-runner/src/client/orchestrator.ts | CordisRunOrchestrator, activeRuns / lastRunError, approve / decline / startUserRun / reconcileApprovals, and drive()'s Host → source → Client → single-resolution order |
| packages/extensions/cordis-client-runner/src/client/providers.ts | The five clientInspectProviders ids Service / Event / Builtin / Slots / Theme and CLIENT_BUILTIN_INSPECTION |
| packages/extensions/cordis-client-runner/src/client/timer.ts | ClientTimerService, provideClientTimer, timeout / interval / throttle / debounce / setTimeout / setInterval |
| packages/extensions/ui-cordis/src/client/index.ts | The six-entry inject, sidebar.footer.action id cordis-panel, the tool.call.toolview keys cordis_define / cordis_run / cordis_stop / cordis_undefine, children: { 'tool.view.cordis': { kind: 'keyed', scope: 'session' } }, and the @ input source |
| packages/extensions/ui-cordis/src/client/slots.ts | SlotMap['tool.view.cordis'], CordisPanelFace, CordisRunCardFace, CordisToolViewOwnerProps |
| packages/extensions/ui-cordis/src/client/CordisDefineRow.tsx | Read-only definition card, SourceTab = 'client' | 'host', no run switch |
| packages/extensions/ui-cordis/src/client/status.ts | cordisVisibleStatus → 'idle' | 'client-pending' | 'running', packageOf |
| packages/extensions/ui-cordis/src/client/dynamic-port.ts | CordisDynamicPort.stop / remove / inventory |
| packages/extensions/ui-cordis/src/client/inventory.ts | createCordisInventory, CordisInventorySnapshot, single-flight refresh, reset, retire |
| packages/extensions/ui-cordis/src/client/card-model.ts | cordisDefineCard / cordisRunCard / cordisActionCard, CordisToolState |
| packages/bundle/web-app/cordis.patch.yml:122,198,269 | The three rows loading @deepseek-ai/dsh-cordis-host-runner, @deepseek-ai/dsh-cordis-client-runner, and @deepseek-ai/dsh-client-ui-cordis |
| packages/preset/agent-presets/presets/cordis/agent.cordis.yml:246 | The explicit opt-in row for tool-cordis |

## Verification

```sh
# 1. Are the three runner/UI packages in the web composition? (tool-cordis is opt-in)

dsh web --dump-config | grep -E "cordis-(host|client)-runner|client-ui-cordis"

# 2. Host-side Remote verbs and event names

grep -n "@Remote(" packages/extensions/cordis-host-runner/src/index.ts

grep -rn "'cordis/" packages/extensions/cordis-host-runner/src

.md: the seven model tools and the `define → run/update/stop/undefine` semantics

- [Plugin Anatomy](../../learn/core/plugin-anatomy.md): static plugin forms, dual-face manifests, and patch application order

- [Write your first plugin](../../learn/dev/hello-plugin.md): hand-write a static cordis plugin

- [Web UI Architecture](../../learn/core/web-ui.md): the two processes, the slot system, and client plugin loading

- [Runtime invariants](../../learn/dev/runtime-invariants.md): add runtime health assertions to your plugin
