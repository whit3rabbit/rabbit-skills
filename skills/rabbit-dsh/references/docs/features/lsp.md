# LSP Code Intelligence

**In one sentence**: `ctx.lsp` is a **semantic code navigation** capability seam: jump-to-definition, find references, find implementations, hover — through language servers, and it **exposes exactly these four semantic operations** with no generic JSON-RPC escape hatch. `dsh-tool-lsp` is its model-visible tool.

Lets the agent do more than grep — actually "jump to the definition / find all references / inspect the implementation."

## Contents

- [1. Four semantic operations (no escape hatch)](#1-four-semantic-operations-no-escape-hatch)
- [2. Packages](#2-packages)
- [3. Service API](#3-service-api)
- [4. Vocabulary](#4-vocabulary)
- [5. Local backend (lsp-stdio)](#5-local-backend-lsp-stdio)
- [6. Configuration](#6-configuration)
- [7. Verification](#7-verification)
- [Next steps](#next-steps)

---

## 1. Four semantic operations (no escape hatch)

`ctx.lsp` exposes exactly four:

```text
goToDefinition    jump to definition

findReferences    find references (always includes the declaration)

goToImplementation find the implementation

hover            hover (content or null)
```

There is **no** generic JSON-RPC escape hatch: no un-reviewed command/mutation can reach the provider through `ctx.lsp`. This is a deliberate security boundary.

## 2. Packages

| Package | Role |
| --- | --- |
| dsh-lsp | Service definition: the service, a provider registry keyed by brand id + extension, on-demand selection, request/result vocabulary, LspError |
| dsh-lsp-stdio | Service provider: the generic stdio language-server backend |
| dsh-tool-lsp | Consumer: the model-facing lsp tool |

## 3. Service API

| Member | Semantics |
| --- | --- |
| registerProvider(provider) | Registers a backend, atomically reserving its brand id + each normalized file extension; invalid/conflicting input is not published and throws LspError (LSP_INVALID_PROVIDER/LSP_CONFLICT) |
| query(request, signal?) | Selects a provider by the file's final extension, derives a languageId, and runs one query; no match throws LSP_UNAVAILABLE |

Selection is **per-query and order-independent**: a provider exclusively owns a set of extensions, and registration/HMR order does not affect routing. Extensions are normalized to lowercase, leading-dot form; `languageId` only syncs transient documents and does not participate in selection. The first version has no glob / language-id / explicit routing selectors.

**Providers register capabilities, not tools.** `dsh-tool-lsp` is the sole owner of the model-visible name/description/prompt/schema/rendering.

## 4. Vocabulary

`LspQueryRequest`: `{ operation, filePath, position, workspaceRoot }` all required: no field needs an implementation default, no `resolve()` step. Positions/ranges are **zero-based UTF-16** (protocol-consistent); the tool's one-based cursor convention is converted from this.

`LspQueryResult` is a **closed discriminated union**:

- Navigation: `{ kind: 'locations', locations, resolvedWorkspaceUri }`

- hover: `{ kind: 'hover', hover }` (content or null)

`resolvedWorkspaceUri` is the provider's canonical workspace `file:` URI; callers relativize location URIs against it rather than imposing host-platform path rules (which may be symlinked).

## 5. Local backend (lsp-stdio)

`dsh-lsp-stdio` is a **generic stdio language-server backend**: one plugin instance accepts a named server table, each entry registering an isolated provider. It reads via `ctx.fs` and launches via `ctx.subprocess`: servers and source code always live in the mounted execution world. This is a generic host, **not a language-server catalog or installer**; presets go in a `cordis.yml` overlay.

Key behaviors:

- One server process is lazily single-flighted per `(server id, canonical workspace)`; live-server errors are not replayed, and a failed query is retried once on a fresh process

- **transient-open**: each query resolves and byte-bounds the source, `didOpen` (version 1 full text) → request → `didClose` in `finally`. Documents close after every query; the first version needs no didChange/content caching/LRU

- Each source-read/open/query/close is serialized through one **abortable per-workspace queue**; different workspaces run in parallel

- Protocol shutdown failure → terminates the server's descendant tree via subprocess (POSIX group / Windows taskkill)

- `ctx.fs` canonical containment, file URIs, and streaming text validation; but **no `fs/observed` is emitted**: only LSP results are visible to the model

## 6. Configuration

```yaml
- id: lsp

  name: '@deepseek-ai/dsh-lsp-stdio'

  config:

    servers:

      typescript:

        command: typescript-language-server   # required: the executable to spawn

        args: ['--stdio']

        extensionToLanguage:                  # required: lowercase dot-prefixed extensions → languageId

          '.ts': typescript

          '.tsx': typescript

      python:

        command: pyright-langserver

        extensionToLanguage:

          '.py': python
```

The keys of `servers` are stable provider ids reserved on `ctx.lsp`; `command` is required and is launched without a shell.

## 7. Verification

```sh
# check whether lsp is mounted and how many servers are configured

dsh web --dump-config | grep -iE "lsp"

# ask the agent to "goToDefinition some symbol", then see the result in the session

zstdcat ~/.dsh/sessions/*/*/session*.jsonl.zstd | grep -E '"tool/result"' | tail
```

## Next steps

- [Built-in tools](../features/tools.md): where `tool-lsp` sits in the tool list

- [Subprocess and terminals](../features/subprocess.md): lsp starts servers through subprocess
