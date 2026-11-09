# Session Query

**In one sentence**: `ctx.sessionQuery` is a **session-retrieval capability seam**: authorized reads, relationship traces, and search over live and durable session logs, independent of compaction. `session-query` is the service definition, `session-query-sqlite` implements it with SQLite FTS5, and `tool-session-query` exposes workspace-authorized retrieval to the model.

## Contents

- [1. What it is](#1-what-it-is)
- [2. Read API (session-query)](#2-read-api-session-query)
- [3. Filtering and text extraction](#3-filtering-and-text-extraction)
- [4. Full-text search (session-query-sqlite)](#4-full-text-search-session-query-sqlite)
- [5. Model tool (tool-session-query)](#5-model-tool-tool-session-query)
- [6. Configuration](#6-configuration)
- [7. Mount status](#7-mount-status)
- [8. Known limitations](#8-known-limitations)
- [9. Verification](#9-verification)
- [Next steps](#next-steps)

---

## 1. What it is

Session query lets DSH retrieve its own history **without relying on compaction** — precisely reading history, tracing relationships, and full-text searching. The abstract service composes precise session-history retrieval, relationship tracking, and provider-agnostic filtering, operating on live `ctx.sessions` plus an optional dynamically mounted `ctx.sessionPersistence`.

| Package | ctx key | Role |
| --- | --- | --- |
| session-query | ctx.sessionQuery | Defines trusted read, relationship-query, and search operations |
| session-query-sqlite | ctx.sessionQuery | Implements session queries with SQLite full-text search |
| tool-session-query | (registered on ctx.tools) | Exposes workspace-authorized session queries to the model |

Matching the same id yields a single record: live events win, and `live`/`persisted` report both sides' source availability; conflicting immutable headers fail with `SESSION_QUERY_SOURCE_CONFLICT`.

## 2. Read API (session-query)

`SessionQueryEngine` is the composable abstract `ctx.sessionQuery` contract:

| Member | Semantics |
| --- | --- |
| listSessions(signal?) | Reads current persisted metadata, live-first merged, returning deterministic newest-first sorted cloned records |
| readSession(sessionId) | Returns a complete, detached original log (through the same core replay validation as resume), without placing the session in the live store |
| filterSessions(filters, signal?) | Applies provider-agnostic session metadata and availability predicates over the same cloned logical corpus |
| filterEvents(sessionId, filters) | Extracts a one-sided semantic document, applying metadata and literal-text predicates by ascending seq |
| listEvents(sessionId) | Classifies each event as current / shadowed / log-only |
| readSurface(sessionId) | Returns the cloned header, raw-log capture bounds, and the fully folded current surface (model-history order) |
| readEvent(request, signal?) | Returns the cloned header, the full target event, and a bounded raw seq window (before/after default 0, no more than readWindowMax) |
| traceSession(sessionId, signal?) | Reads the corpus once, returning outward ancestors + a deterministic recursive descendant tree; complete: false marks the first missing parent node |
| traceEvent(request, signal?) | Returns the cloned source, direct position replacement, and the direct-reference source event chain (replacementChain follows position replacement to the final replacement) |

Persistence is optional and dynamically mountable/unmountable. When mounted persistence is unreadable, cross-corpus listing and relationship tracing fail with `SESSION_QUERY_PERSISTENCE_FAILED`; a durable record read successfully but failing Session validation reports `SESSION_QUERY_CORRUPT_SESSION`. Header reads, event traces, and event reads aimed at known live sessions **do not consult persistence**, so a durable backend's health does not affect current in-memory state.

## 3. Filtering and text extraction

- `SessionResultFilter`: id, nullable cwd, created-at range, nullable parent, source availability

- `SessionEventResultFilter`: seq/time range, event type, surface, semantic text

Filter arrays AND; values within a single list clause OR; empty list values match nothing; ranges are endpoint-inclusive. Text clauses are **independent of the FTS provider**: the caller's text is escaped into a Unicode, case-insensitive regex where each whitespace string matches one or more whitespace characters — this is a literal semantic-text scan, not a full-text query.

`extractSessionEventText()` / `buildSessionEventSearchDocuments()` define the shared one-sided document projection; reasoning blocks, structural boundaries, stream chunks, request headers, and unknown declaration-merged variants produce no documents.

## 4. Full-text search (session-query-sqlite)

`SqliteSessionQueryEngine` inherits precise reads/traces/provider-agnostic filtering and implements the two full-text methods with SQLite FTS5.

- `searchSessions(request, exec?)` returns `SessionSearchHit` pages grouped by the strongest-matching event across the corpus; `searchEvents(request, exec?)` searches a single logical session

- The query is required, a whitespace-normalized literal phrase after trimming; FTS5 syntax (quotes, `OR`, `NEAR`, `*`) is treated as **data**, not as executable MATCH syntax

- Relevance is comparable across persistent and TEMP tables: FTS5 highlighted matching-span count descending, then stored code-point length ascending; event time / session id / seq break ties

- Cursors are opaque branded values bound to the normalized request and service instance, failing when the relevance generation changes; in-session cursors are not invalidated by unrelated-session changes

- The index uses FTS5 `unicode61`: token/phrase recall, not arbitrary substring recall (`AI` won't match the token `BRAID`); use `filterEvents()`'s `text` clause for literal substrings

- All three surfaces (`current` / `shadowed` / `log-only`) are searchable by default; a surface filter narrows the result

## 5. Model tool (tool-session-query)

`tool-session-query` registers `session_search`, `session_event_search`, `session_trace`, `session_event_trace`, and `session_event_read`, **opt-in** (not mounted in shipping compositions by default).

- Callers come only from `ToolExecution.exec.agent`; cross-session access requires the target and caller session `cwd`s to match exactly, and callers without a `cwd` can only inspect themselves

- Search never exposes provider cursors, offsets, page sizes, or model-controllable limits; the two search tools execute **mutually exclusively** with other tool calls, while the three precise trace/read tools can run in parallel

- `session_search` always omits the caller's own session; requested parent ids are deduplicated and checked against workspace authorization before entering FTS

- The system prompt injects a fixed prior-history guidance, telling the model to "use `session_search` to find history, `session_event_search` to search a single session, and after a hit use `session_trace`/`session_event_trace`/`session_event_read` to fetch relationships or precise data"

- Every `ctx.sessionQuery` call passes through a model-boundary sanitizer, preserving cancellation reasons exactly

## 6. Configuration

`session-query` service definition:

| Key | Default | Contract |
| --- | --- | --- |
| readWindowMax | 50 | cap on before/after raw event counts |
| persistedInspectConcurrency | 4 | max persisted logs inspected concurrently in a single batch read (positive integer) |

`session-query-sqlite`:

| Key | Default | Contract |
| --- | --- | --- |
| path | required | dedicated derived-index SQLite path; :memory: is allowed |
| openAt | startup | startup opens before activation; first-search defers to first search; never disables full-text search while exact reads/filters/traces remain |
| journalMode | wal | wal / delete / truncate / persist |
| defaultLimit | 20 | page size when a request omits limit |
| maxLimit | 100 | maximum accepted request page size |
| snippetChars | 240 | max snippet length (Unicode code points) |

`tool-session-query`:

| Key | Default | Meaning |
| --- | --- | --- |
| maxSearchResults | 100 | max authorized non-self hits collected across providers per page |
| searchTimeoutMs | 30000 | cooperative deadline applied to the two full-text search tools |

## 7. Mount status

- `session-query-sqlite` **mounted by default** (base composition), with neutral defaults `path: ':memory:'`, `openAt: first-search` — process-local, opened only when used

- `tool-session-query` is **opt-in**, not mounted in shipping compositions by default

- `session-query` is an abstract service definition with no separate concrete plugin

## 8. Known limitations

- **No caller authorization**: `session-query`/`session-query-sqlite` are trusted full-context infrastructure; model tools or UIs must constrain which sessions are inspectable themselves

- **Synchronous query execution**: `DatabaseSync` blocks the JS thread during MATCH execution and cannot interrupt an already-running statement

- **`openAt: never` is a deployment switch**: both full-text entry points return `SESSION_QUERY_SEARCH_DISABLED` before request normalization; `node:sqlite`, source observation, and reconciliation never start, while inherited exact reads, filters, and traces stay available

- **Token recall, not arbitrary substring**: `unicode61` won't match substrings inside larger tokens

- **Single-owner derived index**: one index path belongs to one service in one process; external writes and multi-process sharing are unsupported

## 9. Verification

```sh
# check whether session-query-sqlite is mounted (default)

dsh web --dump-config | grep -iE "session-query"

# tool-session-query is opt-in; it shouldn't be mounted by default, so it should be absent

dsh web --dump-config | grep -iE "tool-session-query"
```

## Next steps

- [Built-in tools](../features/tools.md): where `tool-session-query` sits in the tool list

- [Session system](../learn/core/session.md): the event-sourced session log being queried

- [Storage](../features/storage.md): session query goes through `ctx.sessionPersistence`, not through storage
