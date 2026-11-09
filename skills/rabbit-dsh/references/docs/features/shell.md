# The Shell Execution Seam (ctx.shell)

**In one sentence**: `ctx.shell` is DSH's **bash capability seam**: it defines what "run a foreground command" and "start a background process" should do, while leaving the how to lower-level providers. `run()` rejects only on infrastructure failures and otherwise settles with a descriptive `ShellRunResult`; `start()` returns a `ShellProcess` handle immediately with no foreground timeout; `readOutput()` reads incrementally, flags loss as `lossy`, and points at spill files. How processes run (subprocess) and how bash runs (the bash layer) thus sit on two separate levels.

The `bash` tool, the hooks bridges, and the sandboxed executor all build on this seam. This page explains "how DSH runs bash."

Relationship to [subprocesses](../features/subprocess.md): `ctx.subprocess` is the **process primitive** — executable lookup, managed spawn, collected stdio, tree-level termination; `ctx.shell` is the **bash capability seam** — command default semantics, deadlines, cause classification, and model-friendly output framing. Bash builds on subprocess; the two do not replace each other.

## Contents

- [1. What it is](#1-what-it-is)
- [2. Service API (ctx.shell)](#2-service-api-ctxshell)
- [3. run settling semantics (not rejecting)](#3-run-settling-semantics-not-rejecting)
- [4. start: the background handle](#4-start-the-background-handle)
- [5. Tool-layer capability advertisement (sandboxMode)](#5-tool-layer-capability-advertisement-sandboxmode)
- [6. Settings namespace and the environment overlay](#6-settings-namespace-and-the-environment-overlay)
- [7. parseExitStatus: the marker inverse](#7-parseexitstatus-the-marker-inverse)
- [8. Known limitations and deferred items](#8-known-limitations-and-deferred-items)
- [9. Verification](#9-verification)
- [Next steps](#next-steps)

---

## 1. What it is

`ctx.shell` is the `ShellExecutor` service-definition seam: the abstract class declares only `run()`, `start()`, `resolve()`, and the `sandboxMode` capability getter, and never touches process implementation itself. Job ids, ownership, collection, cancellation, and notices belong to the generic `ctx.jobs` runtime.

| Package | ctx key | Role |
| --- | --- | --- |
| shell | ctx.shell | service definition: the abstract ShellExecutor + vocabulary types (ShellExecRequest / ShellExecSpec / ShellRunResult / ShellProcess), exports SHELL_SETTINGS_NAMESPACE and parseExitStatus |
| bash-local | — (local ctx.shell provider) | local subprocess executor: bash -c, command defaulting, deadlines, cause classification, model-friendly environment |
| bash-sandbox | — (sandboxed ctx.shell provider) | reuses bash-local's mechanics but wraps the argv in a ctx.sandbox confine and reports denials / runner failures as result facts |
| tool-bash | — (model-facing bash tool) | the model-facing tool schema and rendering contract over ctx.shell |

`bash-sandbox` is a sandboxing executor that sits behind the **same service seam** as `bash-local`; `tool-bash` detects its `sandboxMode` capability to advertise the escalation fields without importing the provider. That is a standard capability-seam split, and containerized or remote executors can plug in the same way.

## 2. Service API (ctx.shell)

| Member | Semantics |
| --- | --- |
| resolve(request) | fills and caps a request into a fully-specified ShellExecSpec (workdir, timeoutMs, stdoutMaxBytes, …); run/start only ever receive a resolved spec |
| run(spec) | foreground execution; resolves on completion. Rejects only for infrastructure failures (unusable working directory, missing shell, signal already aborted before the call); nonzero exits, timeout kills, and abort kills resolve with a descriptive ShellRunResult |
| start(spec) | background execution; returns a ShellProcess handle immediately with no timeout applied. The caller can adapt it to ctx.jobs via kill()/readOutput()/done |
| get sandboxMode() | capability fact: a sandboxing executor's default mode (the base undefined means "this executor does not sandbox"); tool-bash reads it to advertise sandbox_permissions/justification only when escalation is supported |
| ShellProcess.kill() | kills the process group; returns false if the process already finished |
| ShellProcess.readOutput() | incremental reads: consecutive reads never re-deliver; reads that lose data to the buffer cap flag lossy and point at full-stream spill files |

Implementations subclass `ShellExecutor` and implement the abstract methods; dispose must terminate and await any still-running process.

**Foreground timeouts are always the executor's job**, and `start()` explicitly ignores `timeoutMs`: a background process is stopped only through `kill()` or the spec's `AbortSignal`.

## 3. run settling semantics (not rejecting)

```ts
// packages/shell/shell/src/index.ts

/**

 * Run a command in the foreground; resolves when it finishes.

 * @returns the outcome; nonzero exits, timeout kills, and abort kills

 *   resolve with a descriptive result rather than reject.

 */

abstract run(spec: ShellExecSpec): Promise<ShellRunResult>
```

`ShellRunResult` folds the exit facts and the first abort cause into one field pair:

```ts
// packages/shell/shell/src/types.ts

export interface ShellRunResult {

  exitCode: number | null   // null when the process died from a signal

  signal: NodeJS.Signals | null

  timedOut: boolean         // executor's own timeout was the first interrupt cause

  aborted: boolean          // caller's AbortSignal was the first interrupt cause

  timeoutMs: number         // the effective timeout for this run (after defaulting/capping)

  stdout: CollectedOutput

  stderr: CollectedOutput

  sandbox?: ShellSandboxInfo // present only for a sandboxing executor

}
```

`timedOut` and `aborted` are mutually exclusive: one fused deadline drives both the timeout and the caller's cancellation, and settlement reports the **first-abort** cause. In `bash-local` the adjudication is:

```ts
// packages/shell/bash-local/src/index.ts

using d = deadline(spec.signal, spec.timeoutMs, 'BASH_TIMEOUT')

const handle = this.ctx.subprocess.spawn(this.spawnSpec(spec, argv, spec.stdoutMaxBytes, d.signal))

const outcome = await handle.done

const timedOut = timeoutOf(d.signal, 'BASH_TIMEOUT') !== undefined

const aborted = d.signal.aborted && !timedOut
```

## 4. start: the background handle

`start()` is the background dual of `run()`: it returns a `ShellProcess` immediately and its `done` settles at process close **and never rejects** (a spawn failure settles as `killed`, with the error surfacing on stderr). A still-running background process is terminated and joined when its owning composition tears down, so even across an executor reload the process stays managed by the subprocess seam.

`readOutput()` returns the **delta since the previous read** (stderr in a marked `[stderr]` section) and merges stdout/stderr tail truncation into one `lossy` flag, with `stdoutSpillPath`/`stderrSpillPath` pointing at full-stream spill files:

```ts
// packages/shell/shell/src/types.ts

export interface ShellProcessRead {

  delta: string                    // output produced since the previous read

  lossy: boolean                   // truncation dropped bytes the delta cannot include

  stdoutSpillPath?: string

  stderrSpillPath?: string

}
```

## 5. Tool-layer capability advertisement (sandboxMode)

The `sandboxMode` abstract getter is a **composition capability fact**. The base returns `undefined` by default (= this executor does not sandbox); `bash-sandbox` overrides it to return `ctx.sandboxPolicy.defaultMode`:

```ts
// packages/shell/bash-sandbox/src/index.ts

override get sandboxMode(): SandboxMode {

  return this.mode   // taken from ctx.sandboxPolicy.defaultMode at construction

}
```

`tool-bash` reads it at registration:

```ts
// packages/shell/tool-bash/src/index.ts

const defaultMode = ctx.shell.sandboxMode

const escalationModes: readonly SandboxMode[] = defaultMode === undefined ? [] : ESCALATION_TARGETS

const sandboxPolicy = defaultMode === undefined ? undefined : ctx.get('sandboxPolicy')
```

- `defaultMode === undefined` → **does not advertise** `sandbox_permissions`/`justification` (no sandboxing executor mounted);

- `defaultMode !== undefined` → advertises the escalation fields = `ESCALATION_TARGETS`, and requires `ctx.sandboxPolicy` to be mounted (throws at tool-plugin load if missing);

- escalation runs `approveEscalation`, through `ctx.approval`, **before anything executes**, in a fail-closed sequence.

## 6. Settings namespace and the environment overlay

**`SHELL_SETTINGS_NAMESPACE` (`bash`)** is exported from the service definition, not from a provider — because it names the capability, not an implementation. A host composes exactly one `ctx.shell` provider:

```ts
// packages/shell/shell/src/index.ts

export const SHELL_SETTINGS_NAMESPACE = settingsNamespace('shell')
```

The win32 layer swaps the POSIX rows for the pwsh ones (`pwsh-local` invokes `pwsh -NoLogo -NoProfile -NonInteractive -Command …`); mounting both fails loud on a duplicate service registration. So each platform's provider registers this one namespace with its own schema and never collides, and a `settings.yaml` carried between platforms keeps resolving on both.

**The typed, trusted environment overlay.** Execution has **three** input channels (two ordinary plus one managed):

| Channel | Source | Semantics |
| --- | --- | --- |
| ordinary env | hooks bridges, native plugins (CLAUDE_PROJECT_DIR, CLAUDE_PLUGIN_ROOT) | merged after the credential scrub; the model-facing tool never exposes it as a parameter |
| dshEnv | the managed snapshot collected by ctx.shellEnv.collect() | typed as DshEnvironmentKey = `${'DSH_'}${string}`; merged after env, so managed DSH_* can never be displaced |
| ENV_OVERRIDES | bash-local constant | model-friendly entries (NO_COLOR=1, TERM=dumb, PAGER=cat, …) merged first, so a trusted caller's own entry still wins |

The explicit env handed to the spawn is layered; the subprocess service then applies its credential scrub on top:

```ts
// packages/shell/bash-local/src/index.ts

env: { ...ENV_OVERRIDES, ...spec.env, ...spec.dshEnv },
```

Because the managed keys merge last, **an absent current fact never falls back to a stale value**, and a caller `env` entry cannot displace a `DSH_*` one. `dshEnv` is still optional on the resolved spec; its absence means no overlay.

## 7. parseExitStatus: the marker inverse

`parseExitStatus` (with `ParsedExitStatus`) is the other half of the shell tools' **shared rendering contract**: both `dsh-tool-bash`'s `renderResult` and `dsh-tool-pwsh`'s `renderPwshResult` append the `[exit code: N]` / `[killed by signal: X]` markers. Putting the parse in the service definition means the two tools **never drift on the marker contract**.

```ts
// packages/shell/shell/src/render.ts

const signal = /\n\[killed by signal: ([^\]\n]+)\]$/.exec(text)

if (signal?.[1] !== undefined) return { body: text.slice(0, signal.index), signal: signal[1] }

const exit = /\n\[exit code: (\d+)\]$/.exec(text)

if (exit?.[1] !== undefined) return { body: text.slice(0, exit.index), exitCode: Number(exit[1]) }

return { body: text, exitCode: 0 }
```

Rules: a `[killed by signal: X]` marker yields `signal`; a nonzero `[exit code: N]` yields `exitCode`; neither matches means a clean exit 0. The consumed marker is removed from `body` because a terminal card renders the exit status as its own pill — leaving it in the body would render the exit twice. Requiring a **leading newline and the end of the string** keeps ordinary output that merely ends in marker-like text from matching.

## 8. Known limitations and deferred items

- **No interactive-input vocabulary**: `stdin` is written once at spawn and closed; the seam offers no channel for continued input to a running process, and there is no PTY session concept.

- **Foreground timeouts are always the executor's job**: a mode where the caller owns the deadline on the seam is explicitly deferred by the tool-call timeout policy Agent Note.

## 9. Verification

```sh
# see whether the bash executor/tool is mounted

dsh web --dump-config | grep -iE "shell|tool-bash"

# see bash subprocesses in the session (the pass-through ones)

zstdcat ~/.dsh/sessions/*/*/session*.jsonl.zstd | grep -E '"bash' | head
```

```sh
# run a command in a session and observe the exit marker and job semantics

# foreground: a nonzero exit returns a descriptive result, not a rejection

bash -c "exit 3"          # → [exit code: 3]

# background: returns a job id immediately; no foreground timeout applies

bash -c "sleep 30"        # run_in_background: true → get a jobId, job_output / job_kill
```

## Next steps

- [Built-in tools](../features/tools.md): the bash tool's schema and model experience

- [Subprocesses and Terminals](../features/subprocess.md): the process primitive beneath `ctx.shell`

- [Sandbox and security](../learn/core/sandbox-security.md): the boundary of `sandboxMode` and sandboxed execution
