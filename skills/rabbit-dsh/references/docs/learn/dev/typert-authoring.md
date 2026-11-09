# Authoring and Publishing Typert Contracts

- 
- Concepts Course
- Plugin Development
- Authoring and Publishing Typert Contracts
On this page

# Authoring and Publishing Typert Contracts

**One sentence**: Declaring a plugin capability as a Typert Remote contract and publishing it is a five-step flow — ① mark the public surface with `@typert object` / `@typert service <key>` / the export JSDoc on declarations; ② register identity through `ctx.typert.lookups.register()` / `ctx.typert.contexts.*`; ③ let `WorkspaceTypertGenerator` generate `lib/typert.host.{js,d.ts}` and `lib/typert.remote-client.*` at build time (`check` mode fails loudly on invalid input, `write` mode backfills type annotations); ④ expose `./typert` and `./remote` under `package.json` `exports`; ⑤ the [Remote API gateway](../../learn/core/remote-api-gateway.md) consumes it with `ctx.remote.$mount()`. **Authors own the contract; consumers only read the artifacts.**

This is the **author side** — how a plugin author declares, generates, and publishes their capability as a Typert Remote contract. How consumers use the generated artifacts lives in [Remote API gateway](../../learn/core/remote-api-gateway.md). The dual-face boundary is covered by [Plugin anatomy](../../learn/core/plugin-anatomy.md).

## Contents

- [0. What each package contributes](#0-what-each-package-contributes)
- [1. Source annotations: marking the public surface](#1-source-annotations-marking-the-public-surface)
- [2. Check mode: four failure classes & write-mode backfill](#2-check-mode-four-failure-classes-write-mode-backfill)
- [3. Identity registration: ctx.typert.lookups / contexts](#3-identity-registration-ctxtypertlookups-contexts)
- [4. Build: Host artifacts + Remote projection & the dual face](#4-build-host-artifacts-remote-projection-the-dual-face)
- [5. Publish: exposing ./typert and ./remote in package.json](#5-publish-exposing-typert-and-remote-in-packagejson)
- [6. End-to-end minimal change checklist](#6-end-to-end-minimal-change-checklist)
- [7. Verification](#7-verification)
- [Next steps](#next-steps)

---

## 0. What each package contributes

Typert splits source analysis, runtime storage, and artifact generation across three packages (`packages/typert/README.md`):

| Package | Responsibility | Cordis key | Role here |
| --- | --- | --- | --- |
| packages/typert/protocol | Compiler-independent protocol declarations (@Remote, @RemoteScope, InvocationDescriptor, TypertLookupMap, the typertRemote binding) | None (types + decorators) | The annotation vocabulary authors write against |
| packages/typert/registry | Runtime registry for generated reflection and Zod schemas | ctx.typert | Where authors/hosts register identity and contracts at runtime |
| packages/typert/generator | Build-time library that generates runtime artifacts from source types | None (tsdown plugin) | The generate and validate step during the build |

Plus `packages/typert/loader`: inside a Loader composition it discovers each package's `./typert` export and calls `ctx.typert.register()`, feeding the generated artifacts into the registry automatically (see `packages/typert/loader/README.md`). As an author you only need to get the artifacts **and their export declarations** in the right place — the Loader performs runtime registration for you.

The full loop:

The "consumer gateway / client" half of the diagram is fully covered in [Remote API gateway](../../learn/core/remote-api-gateway.md). This page stops at the **author side**: exactly what to write in each step, where to find the artifacts, and how to verify.

## 1. Source annotations: marking the public surface

Typert analyzes **package public exports** (the source graph reachable through `package.json#exports`), not arbitrary internals. `typertMode()` and `typertServiceTag()` in `packages/typert/generator/src/analyzer.ts` read the JSDoc tags:

- `@typert object` — marks an exported object (e.g. a class) as a **reflection object** (ObjectModel): only **public instance members** are exposed; constructors, static members, and non-public members are excluded (generator `README.md`).

- `@typert schema` / `@typert type` (`@typert` followed by nothing, `schema`, or `type`) — marks it as a **data schema**, producing a runnable Zod projection.

- `@typert service <key>` — marks an exported **class** as a **service**, where `<key>` is its Cordis key. It must be exactly one non-empty segment without `/`, and the declaration must be an exported class (otherwise `collectExplicitServices` in `analyzer.ts` fails).

- A source `declare module '@deepseek-ai/cordis' { interface Context { … } interface Events { … } }` — Context augmentations yield **services** and Events augmentations yield **events**, both collected into the package's reflection surface.

A real example — the `Session` class in `packages/core/session/src/index.ts`:

```ts
// packages/core/session/src/index.ts

declare module '@deepseek-ai/cordis' {

  interface Context { sessions: SessionStore }

  interface Events {

    'session/created'(this: Scoped<Session>, session: Session): void

    'session/disposed'(this: Scoped<Session>, session: Session): void

    /* ... */

  }

}

/**

 * An event-sourced session: an append-only log of {@link SessionEvent}s.

 * @typert object

 */

export class Session {

  /** The session identity, derived from its durable header's single copy. */

  get id(): SessionId { return this.header.id }

  /* ... */

}
```

The `@typert object` tag marks the `Session` **class**; `sessions: SessionStore` lives in the `Context` augmentation — the former enters the reflected objects, the latter enters as a service in the package model. Both are discovered by the generator.

On the Zod side of `@typert object`, note that `FaceModelEmitter` only supports the subset of TypeScript projections it implements (keywords/literals/arrays/tuples/unions/intersections/interfaces/`Record`/`Date`, etc.); it **fails** on functions, `Map`/`Set`/`Date` instances, generic schema roots, conditional/mapped schema roots, and so on (`emitter.ts` fails rather than flattening or weakening the source type). Visibility is a hard rule: services and objects keep only `public`, non-static instance members.

## 2. Check mode: four failure classes & write-mode backfill

`WorkspaceAnalyzer` **defaults to `check` mode** (`packages/typert/generator/src/analyzer.ts:282`, `mode: options.mode ?? 'check'`). It fails directly on any of four conditions (throwing `TypertAnalysisError` with source-oriented line/column diagnostics):

| Failure source | Source action / location | Fix |
| --- | --- | --- |
| TypeScript syntax/semantic diagnostics | checkProject() collects each package's getSyntacticDiagnostics() + getSemanticDiagnostics() | Fix the type error |
| A reachable public declaration is missing an explicit type annotation | requiredType() in check mode fails 'public … is missing an explicit type annotation' | Add an explicit annotation (or run write mode to backfill) |
| Private cross-package references | The model only follows the public-export graph; references poking into another package's private boundary are rejected | Go through @typert / public exports; do not leak privates |
| Declaration merges the model cannot keep losslessly | Lossless merges (e.g. TypertLookupMap) are supported; non-lossless ones (e.g. cross-face namespace re-exports, merged … is not supported) fail | Use named exports / concrete export targets |

**`write` mode** is the automatic backfill: when `mode: 'write'`, `requiredType()` no longer fails but derives the type via the checker (`checker.typeToTypeNode()`), queues a source edit that inserts `: <rendered>` at the right position, then **re-compiles** and returns a clean **`check`-mode model** (`analyzer.ts` re-runs `analyze()` in `check` mode at the end). `WorkspaceTypertGenerator` (`packages/typert/generator/src/workspace.ts`) is driven by the tsdown plugin and runs `generate()` (the check face) by default; you only opt into `write` when you want annotations backfilled.

## 3. Identity registration: ctx.typert.lookups / contexts

The runtime registry `TypertRegistry` (default plugin providing `ctx.typert`) lives in `packages/typert/registry/src/service.ts`. An author package registers, at runtime, how a "host object / scoped Context ←→ wire identity" mapping resolves so that a generated `InvocationDescriptor` can replace a wire value with a host object.

`ctx.typert` has four sub-tables (`packages/typert/registry/README.md` + `service.ts`):

| Sub-table | Methods | Registers what |
| --- | --- | --- |
| lookups | register(key, provider) / configure(key, resolver) | Host-object↔wire identity resolution (incl. the default resolver) |
| contexts | registerHost / configureHost / registerClient | Scoped-Context↔wire identity (Host resolver provider / Client binder) |
| local | get / list / hasSeen / subscribe | InvocationDescriptors of the current environment (filled by register()) |
| remotes | register(contribution) / get / list | Consumer-selected, mounted Remote contributions |

`lookups.register(key, provider)`'s `provider` fields (`protocol/src/types.ts` `TypertLookupProvider`): `parameter` (source parameter name), `wire` (wire field name), `hostTypeSymbol` / `wireTypeSymbol` (canonical type symbols used by strict generation), and `resolve(id)` (resolves a wire identity to a Host object, synchronously or asynchronously). `register` validates malformed identities and duplicate keys before committing anything, and returns an **exact Cordis effect disposer** (automatically withdrawn when the registering fiber unloads).

The canonical `session` lookup in the repository is `core/session` (`packages/core/session/src/index.ts:798-806`):

```ts
// packages/core/session/src/index.ts

export class SessionStore extends Service {

  constructor(ctx: Context) {

    super(ctx, 'sessions')

    ctx.inject(['typert'], (typeCtx) => {

      typeCtx.typert.lookups.register('session', {

        parameter: 'session',

        wire: 'sessionId',

        hostTypeSymbol: '@deepseek-ai/dsh-session#Session',

        wireTypeSymbol: '@deepseek-ai/dsh-session/types#SessionId',

        resolve: sessionId => this.get(sessionId),

      })

    })

  }

  /* ... */

}
```

Its matching **static declaration merge** lives in the same file's `declare module '@deepseek-ai/dsh-typert-protocol'` (lines 89-93): `interface TypertLookupMap { session: TypertLookup<Session, SessionId> }`. **The protocol package owns both sides of its contract** (`protocol/README.md`): declaration merging supplies the static association, while the runtime provider registers identity resolution with `ctx.typert`. The protocol package supplies the stable declaration and default resolver; Host composition can `configure()` a synchronous or asynchronous resolver, and configuration may precede the provider; policy rejections may use `TypertLookupFailure` to carry a failure value owned by the boundary adapter.

`ctx.typert` query API at a glance (registry `README.md`): `register(contribution)`, `get(key)`, `resolve(key)`, `list(filter?)`, `getPackage(packageName, face='host')`, `listPackages(filter?)`, `toJSONSchema(key, params?)` (projects with `z.toJSONSchema()` on demand, uncached), and `typertKey()` / `typertPackageKey()`. Schemas are keyed `<package>#<name>` and package reflection `<package>#<face>`.

## 4. Build: Host artifacts + Remote projection & the dual face

Artifacts are produced by `WorkspaceTypertGenerator` + `FaceModelEmitter` (`packages/typert/generator/src/workspace.ts` + `emitter.ts`). The Host tsdown runs generation with `tsconfig.host.json` as its **only program seed**, producing both:

- **Host reflection artifacts** `lib/typert.host.js` + `lib/typert.host.d.ts` (a `TYPERT` contribution with the Zod schemas it supports; `TYPERT` is declared as `unknown` in the d.ts so contributing business packages need not depend on the runtime registry).

- **Host-for-Client Remote projection** `lib/typert.remote-client.js` + `.d.ts` (+ `.d.ts.map`): it projects the Host's Remote contracts for the Client so that a Client import exposes only the **selected Remote methods**.

The root `package.json` build scripts (the repository containing `packages/typert/generator`) confirm the split:

```jsonc
// package.json (scripts)

"build:lib:host":   "tsc -b tsconfig.host.json && tsdown --env.DSH_BUILD_FACE host",

"build:lib:client": "tsc -b tsconfig.client.json && tsdown --env.DSH_BUILD_FACE client",
```

And in root `tsdown.config.ts` the Host pass mounts `typertPlugin({ mode: 'workspace', faces: ['host'] })`, while the **Client pass's plugins is an empty array** (`client ? [] : [typertPlugin(...)]`) — the Client stage neither starts Typert nor analyzes `tsconfig.client.json`, exactly as the generator `README.md` describes.

**Dual-face (Host/Client) boundary**: an ordinary single-project package that declares `dsh.client` in `package.json` (e.g. `packages/api/gateway/package.json`'s `dsh.client`) can contribute both Host and Client runtime models; only a split project explicitly referenced through `tsconfig.host.json` or `tsconfig.client.json` is restricted to that corresponding face. `package.json#exports` defines every **cross-package public boundary**, and source imports or re-exports are the only allowed cross-face edges; cross-face edges that poke at another package's privates fail. The dual-face assembly on the gateway/client side is covered in [Remote API gateway](../../learn/core/remote-api-gateway.md); the plugin dual-face shape is in [Plugin anatomy](../../learn/core/plugin-anatomy.md).

## 5. Publish: exposing ./typert and ./remote in package.json

The generator validates the export declarations before publishing (`validateExport()` in `workspace.ts`): it requires the package's `files` to include the emitted artifacts. Your `package.json#exports` should expose the artifacts as follows (this is the **author-side declaration you must add**; `hasTypertExport()` also relies on it to decide whether the package participates in generation):

| Subpath | Points to | Purpose |
| --- | --- | --- |
| ./typert | ./lib/typert.host.d.ts + ./lib/typert.host.js | Host reflection artifacts (Loader / host) |
| ./remote | ./lib/typert.remote-client.d.ts + ./lib/typert.remote-client.js | Host-for-Client Remote projection (imported by consumers) |

The real examples in `packages/feedback/message-feedback/package.json` and `packages/host/plugin-inventory/package.json`:

```jsonc
// packages/host/plugin-inventory/package.json

"exports": {

  ".":       { "types": "./lib/types/index.d.ts",       "default": "./lib/index.js" },

  "./types": { "types": "./lib/types/types.d.ts",       "default": "./lib/types/types.js" },

  "./typert": {"types": "./lib/typert.host.d.ts",       "default": "./lib/typert.host.js" },

  "./remote": {"types": "./lib/typert.remote-client.d.ts", "default": "./lib/typert.remote-client.js" },

  "./package.json": "./package.json"

},

"files": [ "lib/index.js", "lib/typert.host.js", "lib/typert.host.d.ts",

           "lib/typert.remote-client.js", "lib/typert.remote-client.d.ts", /* ... */ ]
```

Publication is **opt-in** per package: business packages without these public entries need no Typert artifacts, and the generator simply skips them. The Remote methods in `packages/feedback/message-feedback/src/index.ts` show exactly how an author marks them — those signatures are what the consumer side sees:

```ts
// packages/feedback/message-feedback/src/index.ts

export class MessageFeedbackService extends TypertRemoteService {

  @Remote('list')   async list(request: MessageFeedbackListRequest): Promise<MessageFeedbackListResult> { /* ... */ }

  @Remote('put')    put(  request: MessageFeedbackPutRequest): Promise<MessageFeedbackPutResult> { /* ... */ }

  @Remote('delete') delete(request: MessageFeedbackDeleteRequest): Promise<MessageFeedbackDeleteResult> { /* ... */ }

}
```

A service that extends `TypertRemoteService` binds the Cordis key passed to `super(ctx, serviceKey)` to the same default wire namespace; one that cannot inherit calls `bindTypertRemote(this, serviceKey)` to get the same **read-only, frozen** `typertRemote` binding (`protocol/src/index.ts`). `@Remote()` also accepts an explicit export name, and `@RemoteScope(key)` marks a method whose receiver is selected from a scoped Context.

## 6. End-to-end minimal change checklist

| Step | What you edit / do | Result |
| --- | --- | --- |
| 1 Annotate | @typert object before an exported class/object, @typert service  before a service, @Remote on Remote methods | The public surface enters the model |
| 2 Register | At runtime ctx.typert.lookups.register('session', {parameter, wire, hostTypeSymbol, wireTypeSymbol, resolve}); for scoped contexts contexts.registerHost/registerClient; same-name protocol declare module | wire↔object resolution works |
| 3 Build | Host tsdown runs typertPlugin({mode:'workspace',faces:['host']}) (already wired in the repo) | lib/typert.host.* + lib/typert.remote-client.* |
| 4 Publish | Expose ./typert and ./remote in package.json, and list them in files | Consumers can import |
| 5 Consume | Consumers ctx.remote.$mount() via the gateway (see below) | Author-to-consumer loop closed |

## 7. Verification

```sh
# 1) The Host build runs Typert; artifacts should appear in the declared packages

npm run build:lib:host

ls packages/host/plugin-inventory/lib/typert.host.{js,d.ts} \

   packages/host/plugin-inventory/lib/typert.remote-client.*
```

```sh
# 2) Publish declarations must match the artifacts, or validateExport fails

node -e "const m=require('./packages/host/plugin-inventory/package.json');

console.log('typert->', m.exports['./typert'], '\nremote->', m.exports['./remote'])"
```

```sh
# 3) Registry is observable at runtime (after starting dsh):

#    lookups.get('session') should return a provider (parameter/wire/hostTypeSymbol/wireTypeSymbol)

#    local.list() / listPackages() surface keys like <package>#<host>
```

```sh
# 4) Run pure source analysis without a runtime:

#    call WorkspaceAnalyzer directly; check mode exits with diagnostics on failure,

#    write mode backfills annotations and returns a clean model
```

## Next steps

- [Remote API gateway](../../learn/core/remote-api-gateway.md): the **consumer side** — how `ctx.typertGateway.invoke()` and `ctx.remote.$mount()/$on()/$dispatch()` consume these artifacts

- [Plugin anatomy](../../learn/core/plugin-anatomy.md): the dual-face (Host/Client) plugin shape and the `dsh` manifest

- [Write a service](../../learn/dev/write-service.md): a service is the basic container for capability
