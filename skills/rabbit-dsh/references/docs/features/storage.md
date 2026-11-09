# Storage Layer

**In one sentence**: `ctx.storage` is where DSH stores **non-session data**: a named backend registry + mounted data-shape facilities. Backends manage media, data shapes manage semantics, and `kv` is currently the only data shape (JSON / SQLite backends).

Session history lives in the [session system](../learn/core/session.md) (event sourcing). What about "other data" (plugin state, key-values, persistent data beyond config)? Store it here.

## Contents

- [1. The hub idea](#1-the-hub-idea)
- [2. JSON backend (readability first)](#2-json-backend-readability-first)
- [3. SQLite backend (scale)](#3-sqlite-backend-scale)
- [4. Domain layer: typed KV domains](#4-domain-layer-typed-kv-domains)
- [5. JSON vs SQLite: how to choose](#5-json-vs-sqlite-how-to-choose)
- [6. Example composition config](#6-example-composition-config)
- [7. Model visibility](#7-model-visibility)
- [8. Known limitations](#8-known-limitations)
- [9. Verification](#9-verification)
- [Next steps](#next-steps)

---

## 1. The hub idea

`ctx.storage` is a **hub that does no IO**:

- Multiple backends run **in parallel**: `json`, `sqlite` mounted together, chosen by the consumer's config (the domain's routing table), **not one globally picked by the hub**

- `register()` returns a disposer; duplicate names / unknown lookups fail loud

- Data shapes `StorageForms` can be declared and merged; the domain layer merges them and they are accessed as `ctx.storage.domain`

## 2. JSON backend (readability first)

`dsh-storage-json` registers as backend `json`: **one unit, one `<unit>.json` file** (under the configured root).

- Writes: in-memory unit state is authoritative; each write re-publishes the whole file via temp-write + fsync + atomic `rename()`; unit files are **always the full clean state** (readability is why this backend exists; for scale, use sqlite)

- A missing file = an empty unit, materialized on first write; a foreign/unparseable file rejects `malformed-medium`; a version mismatch rejects `version-mismatch`

- Each single call is atomic and durable; cross-call write ordering belongs to the caller (the domain write chain)

```yaml
# configuration

- id: storage-json

  name: '@deepseek-ai/dsh-storage-json'

  config:

    root: $DSH_HOME/storages   # required, no default; created 0o700 as needed
```

## 3. SQLite backend (scale)

`dsh-storage-sqlite` registers as backend `sqlite`, providing a kv facet on **one** `node:sqlite` database file (or `:memory:`). For scale and multi-unit concurrency, replace json with it.

The storage model is **one row per record**: each unit table materializes as a STRICT table `"u_<unit>_<table>"` (`key TEXT PRIMARY KEY, value TEXT`), with `value` being the record's JSON text, so **one key update touches exactly one row** (which is why you route high-write-frequency domains here instead of json). Unit identity lives in two metadata tables: `units` stamps a format version on every unit at first open (a mismatch rejects `version-mismatch`), and `unit_globals` stores each unit's single global row; the physical layout version sits in `PRAGMA user_version`. Unit/table names pass the hub's `UNIT_NAME_RE` validation before entering DDL — **externally supplied input is never concatenated into SQL identifiers**.

Each write primitive is a **single prepared statement** — SQLite's per-statement atomicity satisfies the KV contract without explicit transactions; cross-call write ordering still belongs to the caller (the domain write chain). Missing directories and library files are created owner-only (`0o700` / `0o600`).

```yaml
# configuration

- id: storage-sqlite

  name: '@deepseek-ai/dsh-storage-sqlite'

  config:

    path: $DSH_HOME/storage.sqlite   # library file path, or ':memory:' for an in-process library

    journalMode: wal                 # journal_mode pragma; default 'wal'
```

| Field | Default | Description |
| --- | --- | --- |
| path | required | SQLite library file path, or :memory: (in-process) |
| journalMode | wal | journal_mode pragma: wal / delete / truncate / persist |

## 4. Domain layer: typed KV domains

The domain shape is a "schema-validated, event-emitting KV domain": a plugin mounts its own domain, and `ctx.storage.domain` gives a typed KV interface. This keeps "shove in an arbitrary value" from becoming unconstrained state.

`dsh-storage-domain` provides the injectable `ctx.storageDomain` service and exposes a matching `ctx.storage.domain` projection after all backends register. A domain:

- **Declares once**: `defineDomain` defines records with a **zod record schema**, types derived via `z.infer`; opened through `DomainFacility.open`

- **Memory is authoritative**: reads are **synchronous**, returned directly from in-process state

- **Writes go through a chain**: each write first **reaches the routed backend's persistent layer**, then updates memory and emits a `domain/changed` event; each domain's writes serialize on one per-domain chain

- **Lifecycle belongs to the consumer**: `Domain.close()` idempotently releases the handle (usually its own `ctx.effect` disposer); on plugin unmount the facility closes any still-open domains

```yaml
# domain backend routing

- id: storage-domain

  name: '@deepseek-ai/dsh-storage-domain'

  config:

    backend: json          # default backend for all domains (required: no one-size-fits-all medium exists)

    routes:

      workspace: sqlite    # per-domain override: workspace goes through sqlite
```

| Field | Description |
| --- | --- |
| backend | default backend name for every domain (required) |
| routes | per-domain overrides: domain name → backend name |

`domain/changed` is an **in-process event**: it's only visible to the model when some consumer renders it into its own surface; this package itself registers no tool, injects no prompt, and appends no session event.

## 5. JSON vs SQLite: how to choose

|  | json | sqlite |
| --- | --- | --- |
| Readability | one unit, one full clean-state file, cat/jq-able | library file, needs SQL queries |
| Write cost | each write re-publishes the whole file (temp-write + fsync + rename) | one key update writes one row |
| Concurrency | no cross-process write lock (two processes on the same root overwrite the whole file, last-write-wins) | synchronous writes, no busy-wait/retry; another connection holding a write transaction is rejected immediately |
| Fits | small, low-frequency, human-inspected state | high-write-frequency domains, multi-unit concurrency |

Rules of thumb:

- **Want scale and frequent updates** → route to `sqlite` (one-row-per-write write cost is its reason to exist)

- **Want human-readable, easy to debug** → use `json` (the file is always the full clean state, its reason to exist)

- Both can **sit mounted side by side**, split per domain by `routes`, not a global either/or

## 6. Example composition config

Mount json and sqlite together, with high-frequency domains going through sqlite and the rest through json:

```yaml
# ~/.dsh/profiles/web/cordis.patch.yml

- id: storage-json

  name: '@deepseek-ai/dsh-storage-json'

  config:

    root: $DSH_HOME/storages        # required, no default; created 0o700 as needed

- id: storage-sqlite

  name: '@deepseek-ai/dsh-storage-sqlite'

  config:

    path: $DSH_HOME/storage.sqlite

    journalMode: wal

- id: storage-domain

  name: '@deepseek-ai/dsh-storage-domain'

  config:

    backend: json

    routes:

      workspace: sqlite
```

## 7. Model visibility

`ctx.storage` **registers no tool, injects no prompt, and writes no session event**: it is a pure host-side registry.

- **Token effect**: zero direct tokens per request

- **KV cache effect**: never touches the request prefix, does not affect provider cache reuse

## 8. Known limitations

- `kv` is the only data shape (backends currently need to implement a single facet)

- Data shapes are **lazily resolved**: reading `ctx.storage.domain` before the domain plugin mounts throws `form-not-mounted`; assembly is ordered, and misconfiguration fail-louds rather than failing silently

- `domain/changed` is an **in-process event**: a second process or a reconnected GUI doesn't see changes until the cross-process revision lands

- No cross-table transactions, secondary indexes, or multi-segment keys: each write touches a single record

- The json backend has **no cross-process write lock** (two processes on the same root overwrite the whole file); sqlite's synchronous writes block the event loop (for the duration of a single statement)

## 9. Verification

```sh
# see whether the storage backends are mounted (json/sqlite)

dsh web --dump-config | grep -iE "storage"

# see the storage directory (0o700)

ls -la ~/.dsh/storages/
```

## Next steps

- [Settings and credentials](../user-guide/settings.md): runtime user settings (another kind of non-session data)

- [Session system](../learn/core/session.md): session history lives here, not through storage
