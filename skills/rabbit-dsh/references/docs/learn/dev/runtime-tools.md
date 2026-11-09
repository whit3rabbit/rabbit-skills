# Runtime Inspection and Dynamic Cordis Plugins

- 
- Concepts Course
- Plugin Development
- Runtime Inspection and Dynamic Cordis Plugins
On this page

# Runtime Inspection and Dynamic Cordis Plugins

**In one sentence**: `@deepseek-ai/dsh-tool-cordis` lets the model query the real Host/Client surface, define an immutable Package, and run, update, inspect, stop, or permanently remove a dynamic Cordis plugin under a stable `pluginId`.

Four packages compose the feature:

| Package | Responsibility |
| --- | --- |
| @deepseek-ai/dsh-tool-cordis | Registers seven model tools and injects @pluginId references |
| @deepseek-ai/dsh-cordis-host-runner | Owns dynamic plugins, Packages, version pointers, and Host state |
| @deepseek-ai/dsh-cordis-client-runner | Approves and runs Client halves in the browser |
| @deepseek-ai/dsh-client-ui-cordis | Renders definition, start, and state cards in the conversation |

The source entry point is `packages/extensions/tool-cordis/src/index.ts`. Treat the TypeScript registration table as authoritative.

## Contents

- [1. The seven tools](#1-the-seven-tools)
- [2. Inspect before writing code](#2-inspect-before-writing-code)
- [3. cordis_define: create an immutable Package](#3-cordis_define-create-an-immutable-package)
- [4. cordis_run: run, update, and roll back](#4-cordis_run-run-update-and-roll-back)
- [5. cordis_inspect_self: inspect versions and failures](#5-cordis_inspect_self-inspect-versions-and-failures)
- [6. Stop versus permanent removal](#6-stop-versus-permanent-removal)
- [7. Host/Client flow](#7-hostclient-flow)
- [8. Verify](#8-verify)
- [Next](#next)

---

## 1. The seven tools

| Tool | Purpose | Mutates state |
| --- | --- | --- |
| cordis_inspect_list | List Host and Client Inspect Providers, methods, and schemas | No |
| cordis_inspect_query | Run a read-only query declared by a Provider | No |
| cordis_inspect_self | Inspect this Session's plugins, Packages, versions, and diagnostics | No |
| cordis_define | Record a new immutable Package; validate but do not run it | Yes |
| cordis_run | First run, restart, rollback, or update to an exact Package | Yes |
| cordis_stop | Stop the current run while retaining versions, grants, and pointers | Yes |
| cordis_undefine | Permanently remove the plugin, all Packages, grants, and pointers | Yes |

This versioned lifecycle replaces `cordis_inspect`, `cordis_mount`, and `cordis_unmount`.

## 2. Inspect before writing code

Call `cordis_inspect_list` first. Every result declares a `host` or `client` platform, Provider id, purpose, read-only methods, and input/output schemas.

Then query exact names from that result:

```yaml
platform: host

provider: Service

method: listService

input: {}
```

Host queries run locally; Client queries wait for a browser response. Inspect reads contracts, services, events, Builtins, Slots, tokens, and live trees. It neither invokes business Service methods nor mutates the runtime.

Recommended order:

- `cordis_inspect_list`

- Navigate to an exact service, event, or slot

- Query its full contract

- Only then call `cordis_define`

## 3. cordis_define: create an immutable Package

For a new plugin, submit only a 3–6 letter lowercase semantic prefix; the Host mints the unique id:

```yaml
plugin:

  kind: new

  idPrefix: echo

name: Echo tool

purpose: Register a small echo capability

code:

  host: |

    return {

      name: 'echo-package',

      inject: [],

      apply(ctx) {

        // Use the exact Cordis APIs returned by Inspect.

      }

    }
```

To update an existing plugin:

```yaml
plugin:

  kind: existing

  pluginId: echo-1

name: Echo tool v2

purpose: Add the second behavior

code:

  host: "return { name: 'echo-v2', inject: [], apply(ctx) {} }"
```

Rules:

- Supply at least one of `code.host` and `code.client`

- Each value is a plain JavaScript function body returning a Cordis Plugin

- There is no TypeScript, JSX, or `import` transformation

- Packages are immutable; an update appends one rather than overwriting history

- `define` validates and records source only: it requests no approval, runs no `apply`, and moves no current pointer

Success returns a stable `pluginId` and exact `packageId`; explicitly call `cordis_run` next.

## 4. cordis_run: run, update, and roll back

```yaml
pluginId: echo-1

packageId: pkg-2

mode: update
```

Modes:

- `run`: first activation, restart current, or rollback

- `update`: switch from current to another Package

An unauthorized Client Package may return `awaiting-approval`; an authorized one may return `starting` and continue asynchronously in the browser. Tool completion does not imply Client completion.

Version-pointer rules:

- `currentPackageId` changes only after complete Host/Client success

- The activation target is `nextPackageId` while starting

- Technical failure preserves the old current and target next for inspection and retry

- After a user rejects approval, do not repeat the same approval request

## 5. cordis_inspect_self: inspect versions and failures

```text
cordis_inspect_self

cordis_inspect_self pluginId:"echo-1"

cordis_inspect_self pluginId:"echo-1" packageId:"pkg-2"
```

The exact Package form returns Host/Client source and runtime diagnostics. A `packageId` cannot be queried without its `pluginId`.

When a message contains `@echo-1`, `agent/pre-step` injects the current plugin reference. Inspect the exact Package before handling a reference, repairing an asynchronous failure, or appending a version.

## 6. Stop versus permanent removal

`cordis_stop` cancels unfinished approval or activation and stops the current run, but retains every Package, Client grant, version pointer, and restart/update/rollback path. Repeating it on a stopped plugin succeeds idempotently.

`cordis_undefine` stops active work and permanently removes the plugin, Packages, grants, and pointers. Its ids and `@pluginId` reference become invalid.

## 7. Host/Client flow

Dynamic objects belong to the current Session rather than the old process-wide temporary-mount table. Browser halves still depend on page connectivity, approval, and an asynchronous lifecycle.

## 8. Verify

```sh
rg -n "name: 'cordis_" packages/extensions/tool-cordis/src/index.ts

dsh web --dump-config | grep -E "cordis-(host|client)-runner|client-ui-cordis|tool-cordis"
```

## Next

- [Launch Environment](../../learn/dev/launch-environment.md)

- [Runtime Invariants](../../learn/dev/runtime-invariants.md)

- [Web UI Architecture](../../learn/core/web-ui.md)
