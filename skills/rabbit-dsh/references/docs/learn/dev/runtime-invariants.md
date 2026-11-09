# Runtime Invariants

- 
- Concepts Course
- Plugin Development
- Runtime Invariants
On this page

# Runtime Invariants

**In one sentence**: `@deepseek-ai/dsh-invariants` provides the `ctx.invariants` registry service; every workspace package uses a `./invariant` companion to register runtime checks on **its own npm package contract**, throwing an `InvariantError` with stable `code:'INVARIANT'` and `packageName` on violation. This is the mechanism DSH uses to continuously self-check contracts for session/agent/hook/compaction/goal/jobs and more.

This is the companion to [Runtime Inspection and Dynamic Plugins](../../learn/dev/runtime-tools.md): the latter lets a model inspect contracts and manage versioned dynamic Packages; here **packages themselves** declare "my runtime contract must not break." By the end you will be able to add runtime health assertions to your own plugin and understand DSH's continuous self-checking.

## Contents

- [1. The overall model](#1-the-overall-model)
- [2. The service: ctx.invariants](#2-the-service-ctxinvariants)
- [3. InvariantError and its contract](#3-invarianterror-and-its-contract)
- [4. The companion: the ./invariant file](#4-the-companion-the-invariant-file)
- [5. How DSH continuously self-checks itself](#5-how-dsh-continuously-self-checks-itself)
- [6. Mounting and composition](#6-mounting-and-composition)
- [7. Verification and try it](#7-verification-and-try-it)
- [Next steps](#next-steps)

---

## 1. The overall model

- **Service layer**: `InvariantRegistry` (`ctx.invariants`) is a configurable registry that **contains no product checks and imports no product packages**.

- **Companion layer**: every workspace package publishes a `./invariant` companion that registers its **exact npm package name**.

- **Check policy**: the README is explicit — publication and registration are exhaustive, but **runtime assertions are deliberately not synthetic**. A companion installs a check only when its package owns an observable event relationship or a relevant mutable-data relationship.

## 2. The service: ctx.invariants

```ts
// packages/runtime-diagnostics/invariants/src/index.ts

interface Config {

  /** Global switch; defaults to `true`. */

  readonly enabled?: boolean

  /** Case-sensitive JavaScript regex sources that admit package names; empty admits all. */

  readonly package_allowlist?: string[]

  /** Case-sensitive JavaScript regex sources that exclude package names after allowlist matching. */

  readonly package_blocklist?: string[]

}
```

| Config | Default | Meaning |
| --- | --- | --- |
| enabled | true | Service-level master switch; false selects no package |
| package_allowlist | [] | Regex sources compiled one by one with new RegExp(pattern); empty admits all |
| package_blocklist | [] | The same regex sources; blocklist matches override allowlist matches |

```ts
// packages/runtime-diagnostics/invariants/src/index.ts

private selected(packageName: string): boolean {

  if (!this.enabled) return false

  if (this.packageAllowlist.length > 0

    && !this.packageAllowlist.some(pattern => pattern.test(packageName))) return false

  return !this.packageBlocklist.some(pattern => pattern.test(packageName))

}
```

All three conditions must hold for a package to be selected: enabled ∧ (allowlist empty ∨ at least one pattern matches the full npm name) ∧ no blocklist pattern matches.

### The regex-filter conventions

- Matching is over **case-sensitive** JavaScript regex sources compiled with `new RegExp(pattern)`; `/pattern/flags` syntax is not parsed.

- Unless the source supplies `^`/`$`, matching is **unanchored** (substring).

- Blank, whitespace-padded, invalid, or duplicate entries within one list fail service startup (`compilePatterns` in `index.ts`).

- A valid pattern may match no currently loaded package, so later loading and HMR stay **deterministic**.

### register(packageName, installer)

```ts
// packages/runtime-diagnostics/invariants/src/index.ts (excerpt)

register(packageName: string, installer: InvariantInstaller): () => void {

  // validates the name is non-blank, whitespace-free, and not already registered

  // const ctx = this.ownerCtx

  return ctx.effect(async () => {

    if (!this.selected(packageName)) {

      return () => { registrations.delete(packageName) }

    }

    const child = ctx.plugin(installer.inject === undefined

      ? installInvariant

      : Object.assign(installInvariant, { inject: installer.inject }))

    try { await child } catch (error) { await child.dispose(); throw error }

    return async () => { try { await child.dispose() } finally { registrations.delete(packageName) } }

  }, `invariants.register(${JSON.stringify(packageName)})`)

}
```

Key points:

- **Reserves one active registration**: even when filters keep its installer inactive, the package name is reserved as a placeholder.

- **Dedicated child fiber**: an enabled contribution runs in a **dedicated child Cordis fiber**, and can declare its required services through `installer.inject`.

- **`fail(message)` injection**: the installer receives `fail`; calling it **throws an `InvariantError` bound to the registering package** (it never returns).

- **Startup join**: synchronous or asynchronous installer completion is joined before registration succeeds; failure disposes the child fiber and releases ownership atomically — no half-registration is ever left.

- **Disposer ownership**: the service owns every registration fiber; the returned disposer also belongs to the companion fiber. Unloading either side removes listeners, trace state, and the reservation, so a companion can reload and re-register the same package name without retaining old state.

- **Reload semantics**: session-backed companions rebuild their baseline from durable events; live-only companions observe operations that begin after reload.

## 3. InvariantError and its contract

```ts
// packages/runtime-diagnostics/invariants/src/index.ts

export class InvariantError extends Error {

  readonly code = 'INVARIANT' as const

  readonly packageName: string

  constructor(packageName: string, message: string) {

    super(`invariant violated by "${packageName}": ${message}`)

    this.name = 'InvariantError'

    this.packageName = packageName

  }

}
```

`InvariantError` extends `Error`, carries a **stable `code: 'INVARIANT'`** (machine-readable), and exposes the **owning `packageName`**, without adding a product dependency to the service itself.

## 4. The companion: the ./invariant file

Each package's companion is a standard cordis plugin that nevertheless registers during the install phase. Here is `dsh-invariants`'s own companion:

```ts
// packages/runtime-diagnostics/invariants/src/invariant.ts

const PACKAGE_NAME = '@deepseek-ai/dsh-invariants'

export const name = 'invariants-invariant'

export const inject = ['invariants']

/* Empty installer: registration ownership and child lifecycle are the service's

 * mutation boundary itself; observing them from the same registry duplicates it. */

const install: InvariantInstaller = () => {}

export const apply = (ctx: Context): Promise<() => void> =>

  Promise.resolve(ctx.invariants.register(PACKAGE_NAME, install))
```

Companion conventions:

- `export const name` = `<package>-invariant`; `export const inject = ['invariants']` (it waits if the service is absent).

- `apply` calls `ctx.invariants.register(PACKAGE_NAME, install)` and returns the disposer.

- **Empty installer**: when no plausible runtime relationship exists, use an empty installer plus a package-specific leading `No runtime invariant: ...` comment explaining why (pure utilities, thin implementations whose behavior is already observed through their interface package, composition-only packages, binaries, persistence adapters, and test-support packages are common). **The explanation must be revisited when the owner gains mutable state or an event protocol.**

### A companion with a real check

To add runtime health assertions to your own plugin, add a `src/invariant.ts` in the package directory, declare the services the installer needs via `installer.inject`, and report violations with `fail()`:

```ts
// my-plugin/src/invariant.ts

import type { Context } from '@deepseek-ai/cordis'

import type { InvariantInstaller } from '@deepseek-ai/dsh-invariants'

const PACKAGE_NAME = '@scope/my-plugin'          // must be the exact npm package name

export const name = 'my-plugin-invariant'

export const inject = ['invariants']

const install: InvariantInstaller = {

  inject: ['tools'],                            // services the installer declares

  (ctx, fail) => {

    ctx.on('tool/call', () => { /* observe events; on a violation */ fail('trace invariant broken') })

  },

}

export const apply = (ctx: Context): Promise<() => void> =>

  Promise.resolve(ctx.invariants.register(PACKAGE_NAME, install))
```

The key judgment: **confirming a required method, plugin name, injection, effect, or fixed pure-function result is a type, load, or unit-test concern, not a runtime invariant.** Install a runtime check only when there is an **observable event relationship or a relevant mutable-data relationship**.

## 5. How DSH continuously self-checks itself

DSH anchors its runtime-contract self-checks on these packages' companions (the companion table in `README.md`):

| Companion | Checks |
| --- | --- |
| dsh-session、dsh-agent、dsh-scope、dsh-agent-loop | Session enclosure, call/result trace, agent-status transitions, inbox FIFO conservation, scoped subjects, model-request reconstruction |
| dsh-llm、dsh-llm-retry、dsh-tools、dsh-system-prompt | Stream grammar, durable retry position and bounds, tool-pipeline stages and frozen results, authoritative prompt-assembly data |
| dsh-compaction、dsh-hook-protocol、dsh-sandbox-policy | Durable compaction and hook pairing, compaction metadata, sandbox-mode vocabulary |
| dsh-fs、dsh-subagent、dsh-workflow | Filesystem event identity, provider/child pairing, workflow and agent lifecycle identity |
| dsh-goal、dsh-goal-round-driver | Durable goal source/content agreement, revision and lifecycle transitions, timestamps, sequential admitted rounds, reconstructed continuation prompts |
| dsh-permission-presets、dsh-user-approval | Active-preset references, approval asked/decided audit pairing |
| dsh-jobs、dsh-tool-todo | Task snapshot lifecycle/ownership fields, durable whole-list todo structure |
| dsh-time-context | Durable clock readings agree with the session's open turn and next pre-step position and elapsed baseline; rendered time parses and does not postdate its event |

The key distinction: **Session itself** owns immutable, surface-valid log storage (one lossless JSON snapshot per candidate, full cited source-event coverage and positional replacement, `tool/result` replacement restricted to one current result's `content`, deep-freezing, exposing the log through immutable array snapshots); the `dsh-session` companion checks the **remaining cross-record rules** that Session does not own. This fits the positioning that each package owns its npm contract and the service is only a registry.

## 6. Mounting and composition

The standard agent composition mounts the service and four core stateful companions; custom compositions **explicitly** add companions for other loaded packages whose contracts they want checked. Filters can disable or select registrations without changing package entrypoints.

```ts
// packages/runtime-diagnostics/invariants/README.md (composition example)

import type { Context } from '@deepseek-ai/cordis'

import InvariantRegistry from '@deepseek-ai/dsh-invariants'

import * as SessionInvariant from '@deepseek-ai/dsh-session/invariant'

declare const ctx: Context

ctx.plugin(InvariantRegistry, {

  enabled: true,

  package_allowlist: ['^@deepseek-ai/dsh-'],

  package_blocklist: ['^@deepseek-ai/dsh-agent-loop$'],

})

ctx.plugin(SessionInvariant)
```

Each owner's **root entrypoint is independent of diagnostics**: loading the service alone installs no product checks; loading a companion without the service waits on its declared `invariants` injection. The ordinary/Vitest topology mounts an explicitly enabled service plus the current test package's companion; focused suites cover valid and invalid observations for executable companions, while one exhaustive topology mounts all companions to prove registration and disposal wiring.

## 7. Verification and try it

```sh
# Repo-wide minimum ownership check: discovers all workspace packages and rejects

# generated markers, unexplained empty installers, non-empty installers that omit or

# ignore the reporter, incorrect registration names, and incomplete export/publication/

# dependency/TS-reference/bundle wiring

cd ~/.dsh/source/current && pnpm run verify-package-invariants

# Confirm a package's root entrypoint is independent of diagnostics

# (should load without installing product checks)

grep -rn "invariants" packages/runtime-diagnostics/invariants/package.json
```

## Next steps

- [Runtime Inspection and Dynamic Plugins](../../learn/dev/runtime-tools.md): Inspect first, define immutable Packages, then manage them with `run/update/stop/undefine`

- [Write a Service](../../learn/dev/write-service.md): a capability, not just a tool

- [Listen to events](../../learn/dev/listen-events.md): hook into events
