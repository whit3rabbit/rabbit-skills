# Feedback

**In one sentence**: the feedback family has **two deliberately separated contracts** — the `/feedback` command appends a **read-only `feedback/record` event** to the session log (log-only, not sent to the model), while **message feedback** (`ctx.messageFeedback`) is an **editable rating/note sidecar** bound to a **single assistant message**, stored in the storage domain and accessible via `list`/`put`/`delete`. **Neither enters the model conversation**.

Feedback lets "humans" leave opinions to the system without polluting the model context: command feedback is an immutable note in the session log; message feedback is a host-owned, editable, deletable per-message rating.

## Contents

- [1. Two contracts](#1-two-contracts)
- [2. Command feedback (command-feedback)](#2-command-feedback-command-feedback)
- [3. The /feedback command contract](#3-the-feedback-command-contract)
- [4. Session-sharing disclosure](#4-session-sharing-disclosure)
- [5. Message feedback sidecar (message-feedback)](#5-message-feedback-sidecar-message-feedback)
- [6. Data, lifecycle, and durability](#6-data-lifecycle-and-durability)
- [7. Compare-and-set and idempotency](#7-compare-and-set-and-idempotency)
- [8. Service / Host Remote contract](#8-service-host-remote-contract)
- [9. Mount status](#9-mount-status)
- [10. Model visibility](#10-model-visibility)
- [11. Known limitations](#11-known-limitations)
- [Verification](#verification)
- [Next steps](#next-steps)

---

## 1. Two contracts

| Package | Role | ctx key |
| --- | --- | --- |
| command-feedback | Trigger-agnostic feedback/record event + human-facing /feedback producer | — |
| message-feedback | Lifecycle-bound per-message rating/note sidecar + Host messageFeedback.list/put/delete Remote contract | messageFeedback |

Command feedback is **log-only**: it never enters the model context or derived history. When `dsh-session-telemetry-otel` is mounted, it observes `feedback/record` to release a pending telemetry prefix, or warns that "with telemetry off, feedback stays local only"; capture itself is independent of this policy.

Message feedback is **not** a Session event or projection: it lives in a storage-domain sidecar and does not trigger a telemetry handoff. The Host Remote contract publishes with the service; the client Remote aggregation and UI consumers are held separately.

## 2. Command feedback (command-feedback)

The package exports `recordFeedback(session, text)`, appending a log-only `feedback/record` event. Its plugin registers a global command via `ctx.commands`, so every composition's command adapter can discover it; the published Web client can execute it without a model round.

**What it does and does not do**:

- `recordFeedback` is a **command-agnostic** write path: it rejects empty (normalized) text and appends `feedback/record { text }`. Other UIs, hooks, or host integrations can call it directly without constructing a slash command

- The `/feedback` handler uses this producer and **starts no model work**

- The optional `dsh-session-telemetry-otel` consumer observes that event and **does not alter** its capture contract

- Feedback text appears only in the **single persistent payload** `feedback/record`. `dsh-commands` still appends the generic `command/run`/`command/done` event pair, but this definition sets `recordInput: false`, so `command/run` omits `args` and `command/done` carries only the result. All three events are log-only; they do not appear in ordered surfaces, `deriveMessages()`, or model requests

- Appending starts the usual eager drain of persistence, but the producer does **not** force `session/flush`: so confirmation only means the feedback entered the log, not that it has been written to disk

- The event is the authoritative source rather than the command record: feedback may arrive through a trigger other than `/feedback`; keeping the payload out of `command/run` avoids two records carrying the same text

## 3. The /feedback command contract

| Input | Result |
| --- | --- |
| /feedback  | Appends feedback/record; the confirmation carries Feedback recorded for session {sessionId}, User: {userId}, and a session-sharing disclosure |
| /feedback | Returns a usage error directly; pure-whitespace input counts as empty |

- Leading/trailing whitespace is stripped, and nothing beyond that is **parsed**: no truncation, case folding, or control words

- Text that looks like another command (e.g. `/feedback /plan felt slow`) is just feedback content

- Repeated commands each produce their own event; no replacement or merging

## 4. Session-sharing disclosure

The confirmation names the receiving session id and reports how that session is shared, taken from the mounted `telemetry` service (via plugin context `ctx.get('telemetry')`, **not** a declared injection). The disclosure is a sentence decided by the backend `TelemetrySharingStatus`:

| Disclosure status | Confirmation sentence |
| --- | --- |
| full | Session sharing is enabled. |
| feedback-only | Session sharing is feedback-gated; recording feedback releases the session prefix for sharing. |
| disabled | Session sharing is disabled. |
| no service | Session sharing is not configured. |

The disclosure only states the deployment's **current** sharing policy and never promises delivery or retention. Under `full`/`feedback-only`, recording hands off to the backend's non-blocking enqueue, and the SDK handles batching, retry, and loss policies, so the sentence does not claim anything reached the collector. The disclosure appends no event and does not enter the model surface.

## 5. Message feedback sidecar (message-feedback)

Host-owned, editable feedback on a **single finalized assistant message**. The plugin registers `ctx.messageFeedback`, persists **one lifecycle-bound sidecar row** in the storage domain per Session, and publishes Host's unary `messageFeedback.list` / `messageFeedback.put` / `messageFeedback.delete` Remote contracts. It is independent of the immutable Session-level `feedback/record` event and produces no telemetry handoff.

**Configuration**:

| key | Meaning |
| --- | --- |
| maxNoteBytes | Required positive safe integer: max UTF-8 byte length of a single optional note |

A note must contain at least one non-whitespace character, but accepted text is **stored verbatim, not trimmed**. Omitting `note` means "no note for the expected value," so a version-matching substantive `put` clears an existing note. Note validation **precedes** Session lookup, so a missing Session can still return `note-blank` / `note-too-large` without touching persistence.

```yaml
- id: message-feedback

  name: '@deepseek-ai/dsh-message-feedback'

  config:

    maxNoteBytes: 8192
```

The service injects `storageDomain`, `sessionPersistence`, and `sessions`. The persistence domain is `message_feedback`, with one `sessions`-table record row per `SessionId`.

## 6. Data, lifecycle, and durability

`MessageFeedbackItem` contains `messageId`, `rating: 'positive' | 'negative'`, an optional `note`, an opaque `version` used only for equality comparison, and host-assigned `createdAt`/`updatedAt` Unix-millisecond timestamps. Substantive updates preserve `createdAt`, replace `version`, and guarantee `updatedAt` never moves backward. `list` returns a fresh immutable snapshot in first-creation order; updating an item preserves its position, while delete-then-recreate appends it as a new item.

Each row carries the inspected Session's header identity `{createdAt, cwd}`. A mismatch counts as absent: `list` returns empty `items`, `delete` returns an absent postcondition, and `put` may replace a stale row with one bound to the current identity. This guards against `SessionId` reuse with a different header identity; a fork uses a different Session identity and does not inherit feedback rows.

`put` accepts only non-empty, **append-source** `assistant/message` records; replacement-source messages, empty usage-only assistant records, and non-assistant records all return `target-not-found`.

After initial validation, `put` establishes a durability barrier before writing the sidecar: a matching live Session is check-pointed via the canonical `ctx.sessions.flush`, then both the live and cold paths physically read from sequence zero via `SessionPersistence.readFrom`. A missing flush participant, an identity change, a vanished target, or a physical read failure all block the sidecar commit — so **durable feedback never precedes its durable target message**.

## 7. Compare-and-set and idempotency

- `ifVersion: null` requests creation only; every request on an existing item requires its **exact current version**, including no-ops where "the expected value is already the same"

- Checks are per **message**, not per Session: changing one item does not conflict with another

- Every substantive create/update allocates a new opaque UUID token, preventing stale writes from crossing an ABA value cycle

- A version-matching no-op returns the stored item with version and timestamps unchanged; after a lost success response, retrying with the old token receives `version-conflict.current`, letting the caller compare the authoritative item without an extra read

- `delete` ignores `ifVersion` when the item is already absent and always returns stable `{ absent: true }` on success

- A per-Session promise queue serializes inspection, durability validation, sidecar reads, comparison, and whole-row writes; the storage domain itself has **no cross-process conditional writes**

- Plugin dispose closes mutation admission, drains accepted operations in each Session's queue, then closes the storage domain; mutations submitted after dispose begins are rejected as lifecycle failures

## 8. Service / Host Remote contract

`GatewayService` and `@Remote` publish the same set of `MessageFeedbackService` methods, with Host endpoint names `messageFeedback.list` / `messageFeedback.put` / `messageFeedback.delete`. Each method returns a discriminated business union: `{ ok: true, value }` or `{ ok: false, error }`; operational-level failures of storage, corruption, or a missing durability listener are rejected rather than mislabeled as business errors.

| Method | Request | Success value | Rejection error.code |
| --- | --- | --- | --- |
| list | { sessionId } | { items } | session-not-found |
| put | { sessionId, messageId, rating, note?, ifVersion } | committed MessageFeedbackItem | session-not-found, target-not-found, version-conflict, note-blank, note-too-large |
| delete | { sessionId, messageId, ifVersion } | { absent: true } | session-not-found, version-conflict |

`MessageFeedbackVersionConflict` returns the authoritative `current` item (`null` when none exists), letting the caller reconcile the current rating/note/version without a second `list`. `MessageFeedbackNoteTooLarge` returns both `maxBytes` and `actualBytes`. The client Remote aggregation is not yet mounted as a generated client contribution; host callers can use the service/Remote contract without that client assembly.

## 9. Mount status

| Package | Default mount | Default config |
| --- | --- | --- |
| command-feedback | base mounted by default (unconditional, no config) | none |
| message-feedback | web-app mounted by default | maxNoteBytes: 8192 |

`/feedback` is only exposed on the Web client (via the command adapter); headless, ACP automation, and JSON-RPC provide no command adapter, so it is unavailable there. Message feedback's Host Remote contract publishes with the service, but the client Remote aggregation and UI consumers are held separately and not yet present.

## 10. Model visibility

**Command feedback**: the model sees nothing — slash input, `feedback/record`, and confirmation messages do not enter model requests (none has `surfaceOp`, none enters the ordered surface / `deriveMessages()` / system prompt). Recording feedback does not change the rest of that turn's requests. Token effect is zero; the KV cache is independent and does not affect prefix reuse.

**Message feedback**: `ctx.messageFeedback` registers no tool, prompt section, model context, or Session event; feedback stays in the host-side sidecar unless another consumer explicitly exposes it. Token effect is zero; the KV cache is independent.

## 11. Known limitations

- Command feedback: no retrieval/management surface, no structured fields (one free-form text), no amend/withdraw (log is append-only), no durability barrier (confirmation ≠ written to disk), no visible confirmation row on brand-new sessions, exposed only on the Web

- Message feedback: client aggregation and UI are not yet present; CAS is single-process (multiple host processes can still lose updates); no persistent Session-delete cascade; `session-not-found` is possible within the detach/catalog adoption window; header identity is not a content fingerprint; no authenticated-caller boundary; item count and total per-Session row bytes are unbounded

## Verification

```sh
# command feedback is mounted by default (base)

dsh web --dump-config | grep -iE "command-feedback"

# message feedback is mounted by default (web-app)

dsh web --dump-config | grep -iE "message-feedback"

# see feedback/record events in the session log

zstdcat ~/.dsh/sessions/*/*/session*.jsonl.zstd | grep -E '"feedback/record"' | tail
```

## Next steps

- [Custom commands and user interaction](../features/commands.md): the command registry and the command/run event pair

- [Event system](../learn/core/event-system.md): where feedback/record sits in the session log vocabulary

- [Storage](../features/storage.md): where the message feedback sidecar lives (storage domain)
