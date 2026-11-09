# Subprocesses and Terminals

**In one sentence**: `ctx.subprocess` is DSH's process foundation: it takes care of **executable lookup, managed process trees, raw or collected stdio, and a deep terminal primitive** (PTY, foreground group, session cleanup) for any child process. Command default semantics, shells, timeouts, and framing belong to consumers.

The session's `bash` tool, LSP, PTY, and ACP all build on it. This page explains "how DSH runs processes."

## Contents

- [1. What it is](#1-what-it-is)
- [2. Ordinary managed spawn](#2-ordinary-managed-spawn)
- [3. Collecting output (collect)](#3-collecting-output-collect)
- [4. Termination and cleanup (tree-level)](#4-termination-and-cleanup-tree-level)
- [5. Terminal primitive (spawnTerminal)](#5-terminal-primitive-spawnterminal)
- [6. Environment scrubbing](#6-environment-scrubbing)
- [7. Terminal sessions (ctx.terminals and terminal-bash)](#7-terminal-sessions-ctxterminals-and-terminal-bash)
- [8. Verification](#8-verification)
- [Next steps](#next-steps)

---

## 1. What it is

`ctx.subprocess` is the **execution world on the process half**: the abstract `SubprocessRuntime` exposes executable lookup, ordinary managed `spawn`, and a terminal process primitive. Its vocabulary covers raw/collected stdio, process and terminal handles, exit facts, tree/session cleanup, and the managed `DSH_*` environment namespace.

| Package | ctx key | Role |
| --- | --- | --- |
| subprocess | ctx.subprocess | service definition (executable lookup, managed spawn, terminal primitive, handle lifecycle) |
| subprocess-local | — | local provider (detached process trees, bounded collect/spill, node-pty, tree signals, terminate-and-join) |

Its consumers are the shell executor, the LSP host, the terminal backend, and the ACP backend. `ctx.subprocess` **does not replace** `ctx.shell`: bash is a higher-level, model-facing wrapper.

## 2. Ordinary managed spawn

`spawn(spec)` immediately returns a live handle; `done` resolves to exit facts when the process closes (`SubprocessOutcome` has no output and no reason classification, only reporting spawn-level failures).

- **spec is fully explicit**: argv, cwd, per-stream stdio, grace: deployment-related defaults belong to the caller's config, not hidden in subprocess's defaults

- **argv is never interpreted by a shell**; for a shell, pass `['bash','-c',command]` yourself

- stdio Node shapes: `'pipe'` gives you a raw stream to frame yourself (e.g. LSP JSON-RPC, ACP ndjson); `'inherit'` passes through the parent descriptors; collect mode (`{maxBytes, spill?}`) buffers a bounded tail + an optional full-stream spill file

## 3. Collecting output (collect)

- collect readers take **rectified byte offsets** and never consume: independent readers don't steal each other's deltas

- when the read offset slides out of the in-memory tail → `lossy`, pointing at the spill file if one exists

- collected output stays readable after settle

## 4. Termination and cleanup (tree-level)

- **Tree-scoped** termination on all platforms (POSIX detached group + direct-child fallback; Windows `taskkill /T`)

- `terminate()` is the single termination verb: escalates SIGTERM → grace → SIGKILL (idempotent; also driven by the spec's abort signal; no tree is a no-op)

- `waitForExit(signal?)` observes the whole tree's liveness so a caller's teardown ladder can wait for real quiescence at every level

- **the manager only reacts, it doesn't classify reasons**: deadlines, teardown ladders, and reason classification belong to the caller

## 5. Terminal primitive (spawnTerminal)

`spawnTerminal(spec)` is the **only non-pipe primitive**, and its handle owns a real PTY:

- UTF-8 text I/O, foreground group inspection/signaling, a single awaited `terminate()`

- `terminate` reaches quiescence for every session member the provider can still observe, and settles in-flight handle calls

- the spec signal only cancels allocation; a published handle holds its own lifecycle

- output streams end after draining queues once the top process exits; a live transport failure rejects `done`

An ordinary pipe can't allocate a controlling terminal or clean up terminal session members, so this is a separate substrate primitive.

## 6. Environment scrubbing

`scrubbedParentEnv()` / `SENSITIVE_ENV_PATTERN`: drops environment with **credential shapes and `DSH_*` names**, then merges explicit `env` after the scrub. Both local ordinary and terminal spawns apply it; SDK-managed transports can import it directly.

## 7. Terminal sessions (ctx.terminals and terminal-bash)

`spawnTerminal` is the low-level "allocate a PTY" primitive; what actually gives the model a **persistent interactive shell** is the `ctx.terminals` service seam + its `terminal-bash` backend:

| Package | ctx key | Role |
| --- | --- | --- |
| terminal | ctx.terminals | owner-scoped persistent terminal service seam: mints opaque session ids, routes creation through named backends, fences every operation to the exact live Agent, waits for backend quiescence on dispose |
| terminal-bash | —(backend type: shell) | persistent shell backend on ctx.subprocess.spawnTerminal |

- **`ctx.terminals` itself contains no `node-pty`/sandbox/tool schema/prompt/task/terminal-rendering policy**: implementations handle terminal mechanics, consumers handle model presentation

- `terminal-bash` starts the interactive shell under a shared `ctx.sandboxPolicy`: `danger-full-access` starts directly; restrictive modes require a same-world `ctx.sandbox`, wrapping the shell argv in a confine and failing before spawn if none is mounted

- **readiness** is composite evidence: foreground-verified bash private-prompt marker + the provider's reported foreground stdin-wait fact + a silent fallback + an absolute timeout; echoed input or an earlier prompt must not be mistaken for this send being ready

- **send cancellation** marks queued input canceled, then sends a real `SIGINT` to the current foreground process group; wind-down rides on `terminal_close`

- Sessions are **process-local**, not recovered on harness restart; the same backend composition pairs with local or remote execution-world providers

Mount: `terminal` / `terminal-bash` are **not mounted by default** in base; the `minimal` preset mounts them in an entry-local realm together with `tool-bash-persistent` (the persistent shell is one of the two tools this lean composition deliberately keeps).

## 8. Verification

```sh
# see whether subprocess is mounted

dsh web --dump-config | grep -iE "subprocess"

# see bash/lsp subprocesses in the session (the pass-through ones)

zstdcat ~/.dsh/sessions/*/*/session*.jsonl.zstd | grep -E '"bash|"tool/' | head
```

## Next steps

- [Built-in tools](../features/tools.md): bash/pty both build on subprocess

- [Sandbox and security](../learn/core/sandbox-security.md): the boundary of subprocess execution

- [MCP integration](../features/mcp.md): the stdio transport is also a subprocess
