# Credential Management

**Short version**: three iron rules govern DSH's credential system `ctx.credentials`: **configuration only stores references, never the keys themselves**; resolution happens per operation; an empty stored value equals "not configured". Where the key actually lives is decided by the provider (under `~/.dsh` by default).

This section explains "where keys live, how they are read, and how to rotate them".

## Contents

- [1. Three principles (source README)](#1-three-principles-source-readme)
- [2. Public API](#2-public-api)
- [3. Resolution flow and priority](#3-resolution-flow-and-priority)
- [4. Masking rules (fail-loud)](#4-masking-rules-fail-loud)
- [5. Provider](#5-provider)
- [6. Security boundaries and known limitations](#6-security-boundaries-and-known-limitations)
- [7. Rotation walkthrough](#7-rotation-walkthrough)
- [8. Impact on the model](#8-impact-on-the-model)
- [9. Verification](#9-verification)
- [Next steps](#next-steps)

---

## 1. Three principles (source README)

- **Configuration carries references to keys, never the keys themselves**. `apiKeyEnv: DEEPSEEK_API_KEY` is a reference; the value lives in the credential provider. So settings/cordis documents can be safely synced and rendered, and `describe()` can answer "configured or not, where it comes from, whether it can be written" — all while never holding the value; rotating a key touches no configuration file.

- **Consumers resolve per operation**. `resolve(ref)` is called at the start of each operation (the LLM adapter resolves once per model request), and **is not cached across operations**: this makes `a changed key take effect on the next request immediately, without restarting the plugin`.

- **An empty stored value = missing**. `resolve` skips it and `describe` reports it as not configured. An empty string can never masquerade as a configured key.

## 2. Public API

```ts
import type { Context } from '@deepseek-ai/cordis'

import { credentialRef } from '@deepseek-ai/dsh-credentials'

declare const ctx: Context

const ref = credentialRef('DEEPSEEK_API_KEY')   // POSIX shell identifier, branded

const hit = await ctx.credentials.resolve(ref)  // { value, source } | undefined

const info = await ctx.credentials.describe(ref)// { configured, source?, writable } — never the value

await ctx.credentials.set(ref, 'sk-…')          // rejected when masked by a read-only source

await ctx.credentials.unset(ref)                // missing is a no-op; same masking rule as above
```

Credential records (new in 0.1.1, `CredentialKey = <scope>/<id>`) are a second key space: `describeRecord(key)` / `modifyRecord(key, record)` / `deleteRecord(key)`, with records shaped `{ kind: 'api-key', key?/env? }` or `{ kind: 'grant', payload }`. The two key spaces are grammatically disjoint, which is also why the events are separate (`credentials/reference-updated` vs `credentials/record-updated`).

`credentials/reference-updated (ref)` fires after a committed change (used by the config UI to refresh the "configured" badge). Consumers don't need it, because they re-resolve per operation. The credential-record key space (the `modifyRecord` family above) publishes `credentials/record-updated`.

## 3. Resolution flow and priority

The local provider (`dsh-credentials-local`) stacks the four layers following **one honest priority**:

| Layer | Source id | Writable | Who wins |
| --- | --- | --- | --- |
| Inherited process env | env | no | always |
| $DSH_HOME/.credentials.yaml document | file | yes (set/unset) | overrides both .env layers |
| /.env | project-env | not writable here | overrides the user .env |
| $DSH_HOME/.env | user-env | not writable here | fallback |

Reading it line by line:

- **The startup environment always wins**: `DEEPSEEK_API_KEY=… dsh`, CI secrets, container `-e` are the operator's intent for this run; and because it **cannot be rewritten from inside**, it must be **visibly read-only** — `describe()` reports `source: 'env', writable: false`, and `set`/`unset` are rejected outright.

- **Managed storage overrides the `.env` fallback**: a key written on the Models page takes effect immediately, even if an old key still sits in `.env`; the two `.env` layers resolve only when "nothing is stored" — storing a key replaces them as the actually-effective source.

- **A snapshot, not `process.env`**: under the product CLI, resolution reads a snapshot of the environment frozen by the launcher; only it can say whether a value came from the startup shell or from a file.

## 4. Masking rules (fail-loud)

`set`/`unset` have **deliberately fail-loud behavior**: when a read-only source (the active process env for the local provider) currently supplies this ref, a write would "appear to succeed" yet resolution still returns the masked value: **the seam rejects outright**; `describe().writable` lets the UI render this ref as read-only in advance.

| Scenario | Result |
| --- | --- |
| DEEPSEEK_API_KEY present in the process env, then code calls set on it | Rejected; resolution still returns the old value from the env |
| An old key in .env, set writes it into the store | Succeeds; the store immediately overrides .env as the effective source |
| set(ref, '') (empty string) | Rejected; an empty stored value = missing, unset is what removes a key |

## 5. Provider

`dsh-credentials-local` stacks the inherited process env **on top of** the `$DSH_HOME/.credentials.yaml` document it manages, with the launcher's project/user `.env` layers as fallback.

`llm-pi-ai` provider-native discovery is a separate path: a provider without a credential reference reads the **process environment** directly and cannot see the Harness-managed store. For AWS, explicitly export `AWS_PROFILE` or access-key variables; `~/.aws/credentials` alone is insufficient.

| Config option | Default | Meaning |
| --- | --- | --- |
| path | /.credentials.yaml | Location of the credential document |
| dshHome | $DSH_HOME or ~/.dsh | Harness home used when path is omitted |
| watch | true | Hot-publish external edits |
| debounceMs | 100 | Watcher write settle window |

The document is a **versioned YAML** (`version: 1`) with one section per key space: `refs:` maps credential-reference → value, `records:` maps `<scope>/<id>` → credential record (`kind: api-key | grant`, for provider-native authorization and similar), and nothing more; a non-map root, an unknown top-level key, a key that isn't addressable in its space, a wrong-typed value, an empty string, an unknown record tag/field, a duplicate key, and broken YAML are all **rejected in full** (a loud failure at startup; on hot reload it warns and keeps the last good snapshot). Writes **modify patch-style**: they re-read and merge the resolved document (preserving comments and untouched-item formatting), then atomically commit under the cross-process write lock of `dsh-atomic-write`, at `0600` (directory `0700`). **The pre-release flat mapping migrates in place at boot**: a document of addressable names over non-empty string scalars, with no directives, is upgraded under the writer lock (its original lines nest verbatim under `refs:`, so values, comments, and spellings survive byte for byte); any other flat shape is refused by name with a repair hint, never read as an empty store. External edits publish `credentials/reference-updated` per changed ref after a **whole-document replacement** (record changes publish `credentials/record-updated`), and entries deleted on disk never linger in memory.

The seam leaves room for a keyring / helper-command / KMS-backed provider; a remote settings provider never needs to carry keys.

## 6. Security boundaries and known limitations

**The boundary stops at "other OS users" and does not block the model**: `0600` + `0700` keeps out other users; tool processes (bash, filesystem tools) run as the same user, and the `workspace-write` file policy constrains **writes, not reads**. What the harness actually guards is narrower: it **never** hands the document path to the model, and it **never** loads `process.env` into it (`$DSH_HOME/.env` is the ordinary env layer) — this is restraint, not a boundary.

| Limitation | Description |
| --- | --- |
| Concurrent writes to the same ref | last-write-wins: the write lock + read-modify-write prevent lost entries, but when two writers change the same ref the later one still wins |
| Readable by same-UID processes | the file-effect sandbox doesn't refuse reads; true isolation needs an OS-keychain provider (storage the model process can't read, deferred) |
| Env changes not visible | the snapshot is frozen at startup; variables exported at runtime don't enter resolution; changing an env-sourced credential requires a restart |
| Atomic, not crash-durable | inherits dsh-atomic-write; the store re-reads at startup |

## 7. Rotation walkthrough

Rotating a key never requires editing any configuration file — because configuration only stores references. Three paths, depending on "where it comes from now":

| Current source (describe().source) | Rotation steps |
| --- | --- |
| env | Change the startup environment (new shell / CI secret / container -e), restart to take effect |
| file | set(ref, newValue) writes 0600 atomically and takes effect immediately; or edit the file directly and the watcher hot-publishes it |
| project-env / user-env | Write directly into the store with set to override .env; or clear the old value in .env first, then set |

When done, check with `describe(ref)` that `configured: true` and `source` points at the expected layer; it's fine if the old value still sits in `.env` — as long as the store has a value, `.env` drops back to being a fallback.

## 8. Impact on the model

Indirect, via the LLM adapter that consumes them: the resolved value authorizes provider requests, and the adapter owns the model-visible surface.

## 9. Verification

```sh
# Inspect the credential file (0600)

ls -la ~/.dsh/.credentials.yaml

# Check whether credentials are mounted in the composition

dsh web --dump-config | grep -i credential
```

## Next steps

- [Data and Privacy](../user-guide/privacy.md): `.env` / `.credentials.yaml` permissions

- [Configuration](../user-guide/configuration.md): the `apiKeyEnv` reference

- [Model Routing](../learn/core/llm-routing.md): how adapters use credentials
