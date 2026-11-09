# Spill Storage

**In one sentence**: `ctx.spillStore` is a tool-output **overflow capability seam**: an over-long tool result decided by `spill-policy` has its **full text** persisted, while the model side only keeps a **bounded preview + a locator**. `spill-local` stores the spilled text as **session-scoped local files**, the locator is a file path, and a retrieval hint tells the model to use `read`/`grep`.

Tool output is sometimes huge (web scraping, command logs). Stuffing the full text into the model context is both expensive and pointless — spill stores the full text and gives the model only a "where to look" locator.

## Contents

- [1. The responsibilities of the three packages](#1-the-responsibilities-of-the-three-packages)
- [2. Service definition (spill)](#2-service-definition-spill)
- [3. Local backend (spill-local)](#3-local-backend-spill-local)
- [4. Spill policy (spill-policy)](#4-spill-policy-spill-policy)
- [5. Mount status](#5-mount-status)
- [6. Model visibility](#6-model-visibility)
- [7. Known limitations](#7-known-limitations)
- [Verification](#verification)
- [Next steps](#next-steps)

---

## 1. The responsibilities of the three packages

| Package | Role | ctx key |
| --- | --- | --- |
| spill | defines the spill-storage seam (service + vocabulary types) | ctx.spillStore |
| spill-local | stores spilled text into session-scoped local files | registered on ctx.spillStore |
| spill-policy | applies the overflow policy after tool execution | listens on ctx.tools |

The three split by concern and can evolve/replace independently: the storage seam says **what to do** (WHAT), the local backend says **how** (HOW), and the policy decides **when to spill** and assembles the notice.

## 2. Service definition (spill)

`SpillStore` (`ctx.spillStore`) defines **what a spill backend does** — persist a tool's over-large text, return a model-facing locator + retrieval guidance — without saying **how**.

| Member | Semantics |
| --- | --- |
| saveText(input) | persists input.content verbatim; resolves a SpillRef (opaque locator, exact bytes written, retrieval hint). Rejects on real storage failures (permissions, ENOSPC, backend unavailable); the caller decides how to degrade |

Storage groups into a namespace by the requesting `owner` session **at save time**; the backend chooses its own private representation and may derive a name from the caller's `suggestedName`, but **never trusts it as a path**. This seam **only owns storage**: no retention policy (that belongs to `@deepseek-ai/dsh-output-retention`), no tool-result replacement (that belongs to `spill-policy`), and no retrieval/search API (the backend's `retrievalHint` tells the model how to use the locator).

**Vocabulary**:

- `SaveTextSpill` (owner, source, suggestedName, content) is the request; `SpillRef` (locator, bytes, retrievalHint) is the result

- `SpillLocator` is a branded, model-rendered **opaque string** — a local path for `spill-local`; future backends may return a URI, a key, or a command token without changing the policy/tool consumers

- `SpillOwner.sessionId` is the storage namespace at save time: a forked session inherits existing locators from the seed log, **neither copying nor re-attributing them**; new spills after a fork use the child session's id

- `SpillSource` records the producing `toolName`, `callId`, and `label`, used for backend naming and inspection, **not access control**

## 3. Local backend (spill-local)

The **local filesystem** implementation of `SpillStore`. Registered as `ctx.spillStore`, it persists a tool's over-large text into **private, session-scoped** files; the locator is a file path, and the retrieval hint tells the model to use `read` or `grep` on it.

**Storage layout**: files land at `<root>/session-<hash>/<random>-<safeName>`

| Segment | Meaning |
| --- | --- |
| root | the configured root (resolved to an absolute path); when omitted, a lazily created private (0700) per-process directory under the OS temp directory. A predictable, readable root lets other local users read spilled output or plant symlinks |
| session- | a short prefix of sha256(sessionId), grouping one session's spill files together for future per-session cleanup |
| - | an unpredictable hex prefix (guarding against symlink planting under a shared root) + the caller's suggestedName sanitized into a single safe path segment (guarding against path traversal; mirrors encodeSegment on the JSONL persistence backend). Writes are exclusive + owner-only (open(path, 'wx', 0o600)): any pre-existing path — symlink or not — fails, so a planted target cannot redirect it |

**Configuration**:

| Key | Default | Meaning |
| --- | --- | --- |
| root | private 0700 temp directory | the root for spill files; set a known location to keep them |

`saveText` rejects on real storage failures (permissions, ENOSPC); the spill policy treats a rejection as best-effort and keeps the inlined result.

## 4. Spill policy (spill-policy)

**Tool-result overflow policy**: a `tools/post-execute` transformer that keeps over-large plaintext tool results out of the model context. When a final result exceeds `maxInlineBytes`, it saves the **full text** via `ctx.spillStore` and replaces the model-side result with a **bounded head/tail preview + a backend locator + a retrieval hint**.

This plugin **registers no service**, and owns neither the storage nor the preview mechanism: the preview is `@deepseek-ai/dsh-output-retention` (`TextRetainer`), and the storage is `ctx.spillStore`. It only decides **when to spill** and assembles the notice.

**Configuration**:

| Key | Default | Meaning |
| --- | --- | --- |
| maxInlineBytes | (omitted) | the model-side context cap for plaintext results, in UTF-8 bytes (non-negative integer, validated at load). Omitting it disables the policy entirely (the plugin registers nothing). Once set, larger results are spilled and replaced with a preview derived under the same budget (head/tail split) |

**Behavior**:

-

Let the tool finish (delegated through `next()`, so it constrains whatever downstream hooks accept)

-

Skip: nested executions (`exec.parent` exists, its durable copy bounded by the dispatch-log arm below), accepted value replacements (the registry must re-validate and re-render them), `read` (avoiding a `read → spill → re-read` loop), and any non-`accept` decision (`block`'s corrective feedback passes through)

-

Flatten only when the content is **plain text** (all `text` blocks); results containing any non-text block pass through untouched

-

UTF-8 size `≤ maxInlineBytes` → unchanged

-

Otherwise save the full text and replace the result with a preview + notice, sized so the whole replacement (preview + blank line + notice) stays within `maxInlineBytes` — the notice's byte cost is reserved from the budget, so the preview shrinks to fit, and the **model-side result never exceeds the cap**:

```text
<retained head/tail preview>

(Omitted N bytes. Full formatted result stored at: /…/session-…/…-web_fetch.txt. Use read with offset/limit, or grep this path to search within it.)
```

When the notice alone fills the budget (a tiny cap or a very long locator), the preview is empty and only the notice is returned. If even this "notice-only" replacement would exceed `maxInlineBytes`, the policy keeps the inline result — **it never emits an over-cap replacement** (and a compliant replacement is always smaller than the original, so spill never adds bytes).

**Best-effort**: no session owner, no `ctx.spillStore` backend, or a `saveText` rejection ⇒ the policy logs a warning and returns the original result. A spill failure **never** turns a successful call into an `isError` or hides the inline result. A successful replacement only changes `content`; the canonical programmatic value is preserved.

**The dispatch-log arm**: a second listener on `tools/code-dispatch-log` applies the same cap, replacement pipeline, and best-effort fallback to the **durable copies** of each `run_code` subcall result (artifact label `dispatch`, keyed by subcall id). Program values are untouched (they already crossed the worker boundary wholesale), and `read` subcalls are also exempt: the log copy isn't model context, so the `read → spill → re-read` loop can't occur — and `read` is precisely the tool that produces enormous logs.

**Scope**: the policy only sees the **final formatted model-side result** — not a tool's internal resources or canonical value. If the provider already truncated (e.g. `web-fetch-http.maxBodyChars`), the spill artifact saves **the full formatted result the tool returns**, not the full original source. Provider/resource caps stay enforced and independent. `glob`/`grep` own their entry-level rendering overflow (their full fetched values still exist before rendering); bash streams own their collection-time overflow. The generic policy prefixed its waterfall listener and then delegated, so an ordinary tool's own async projection completes first, followed by the generic byte constraint, independent of plugin load order.

## 5. Mount status

| Package | Default mount | Default config |
| --- | --- | --- |
| spill-local | base mounted by default | none (root omitted → private 0700 temp directory) |
| spill-policy | base mounted by default | maxInlineBytes: 50000 |

## 6. Model visibility

**Over-large plaintext results**: results `≤ maxInlineBytes`, nested results, `read` results, `block`-ed decisions, and results containing non-text blocks are unchanged. An over-large plaintext model-side result becomes a **bounded head/tail preview + `(Omitted <bytes> bytes. Full formatted result stored at: <locator>. <retrievalHint>)`**; on a storage or ownership failure the original result stays visible.

- **Token effect**: a successful replacement is at most `maxInlineBytes` UTF-8 bytes and stays in history until compaction; the full spilled text is **not re-sent** to the model

- **KV cache effect**: append-only; new visible content follows a reusable request prefix and does not invalidate existing KV cache entries

## 7. Known limitations

- Only the **final plaintext result** can spill — mixed-content results, `block`-ed feedback, and `read` pass through; provider truncation or a tool's own retention that happened earlier cannot be recovered here

- A notice that won't fit **disables replacement for that call** — a tiny cap or a long locator can keep an over-large original inline even though the backend saved an unreferenced spill

- Local spill files **persist until something external cleans them up** — the backend has no session-lifecycle deletion or age-based retention (because persisted/recovered/forked sessions may still reference a path)

- Locators **require a consumer on the same filesystem** — remote or virtual deployments need another `SpillStore` backend whose locators and retrieval hints make sense there

## Verification

```sh
# spill-local / spill-policy mounted by default (base)

dsh web --dump-config | grep -iE "spill"

# see spilled tool results in the session (model side is a preview + (Omitted ...) notice)

zstdcat ~/.dsh/sessions/*/*/session*.jsonl.zstd | grep -E '"Omitted ' | tail
```

## Next steps

- [Subprocess and terminals](../features/subprocess.md): collection-time overflow of bash streams (subprocess collect spill files)

- [Built-in tools](../features/tools.md): which tools produce over-long results

- [Event system](../learn/core/event-system.md): where tools/post-execute sits in the pipeline
