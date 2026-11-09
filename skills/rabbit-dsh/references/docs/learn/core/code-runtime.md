# The Code-Execution Seam and the Worker Sandbox

- 
- Concepts Course
- Core Mechanisms
- The Code-Execution Seam and the Worker Sandbox
On this page

# The Code-Execution Seam and the Worker Sandbox

**Audit baseline 0.1.5-alpha.1 @ 5dda764ed3**: package names, ctx keys, config keys, protocol messages, and the six failure kinds are all verified point-by-point against the official source; see [source/npm channels](../../guides/deepseek-harness-status.md).

**In short**: `ctx.codeRuntime` is the seam for "let the model write one program, hand it host-provided functions, and recover only what it printed and returned". `CodeRuntime.run()` **always reports a failed program as `result.error`** — a parse failure, a throw, a timeout, an abort, worker death, an invalid completion, and an output overflow are each a distinct `kind` — and rejects only when the caller violates the Service Definition contract. The shipped backend `dsh-code-runtime-worker-thread` puts each program in a **fresh** Node worker thread: host-side type stripping, bindings bridged over the message port, dual budgets, and hard termination. This is **containment, not a security boundary**.

The PTC-mode overview and the model-facing `run_code` contract live in [Tools Execution](../../learn/core/tools-execution.md) and [Tools](../../features/tools.md); this page goes deep on the seam's exact contract, the port protocol, the budgets and ledger, and what it isolates versus what [sandbox](../../learn/core/sandbox-security.md) isolates.

## Contents

- [1. Two packages, three roles](#1-two-packages-three-roles)
- [2. The seam's vocabulary: request, result, failure taxonomy](#2-the-seams-vocabulary-request-result-failure-taxonomy)
- [3. The portability contract: one binding list, valid on every backend](#3-the-portability-contract-one-binding-list-valid-on-every-backend)
- [4. The lifecycle of one run](#4-the-lifecycle-of-one-run)
- [5. The host↔worker protocol: a port treated as hostile](#5-the-hostworker-protocol-a-port-treated-as-hostile)
- [6. Budgets, the output ledger, and termination](#6-budgets-the-output-ledger-and-termination)
- [7. The config surface and the failure modes](#7-the-config-surface-and-the-failure-modes)
- [8. How PTC routes through this seam](#8-how-ptc-routes-through-this-seam)
- [9. Division of labor with sandbox: who isolates what](#9-division-of-labor-with-sandbox-who-isolates-what)
- [10. Sources](#10-sources)
- [11. Verification](#11-verification)
- [Next steps](#next-steps)

---

## 1. Two packages, three roles

`packages/code-runtime/` is one instance of the capability-seam split: definition and implementation are separate, and consumers depend only on the definition.

| Package | Role | Key symbols |
| --- | --- | --- |
| @deepseek-ai/dsh-code-runtime | Service Definition: states what happens, carries no execution code | CodeRuntime (ctx.codeRuntime), CodeRunRequest/CodeRunResult/CodeRunFailure, the four reserved-name sets |
| @deepseek-ai/dsh-code-runtime-worker-thread | Service Provider (shipped): language: 'typescript', isolation: 'worker-thread' | WorkerThreadCodeRuntime, Config, src/protocol.ts |
| @deepseek-ai/dsh-experimental-code-runtime-python | Experimental, unpublished Python backend (isolation runs a subprocess) | Not on npm; never appears in a composition |

The definition package draws its own line: **"Runtimes know nothing about tools or sessions; consumers own those concerns."** (`src/index.ts` module doc). It does one thing — bridge the host functions in `CodeBindingNamespace` into the program, and collect the program's artifacts back out.

Two consumers depend on it:

- PTC mode in `dsh-tools`: at assembly, non-`native` modes call `requireCodeRuntime(mode)`, which must find `ctx.codeRuntime` whose `language` has a registered SDK renderer, or **assembly fails** (`packages/core/tools/src/index.ts`).

- `dsh-tool-presentation`: `native` returns immediately; non-`native` waits with `ctx.inject(['codeRuntime'], …)`, and an entry left pending is what `dsh-agent-presets` reports as an unusable row (`packages/core/agent-tool-presentation/src/index.ts`).

## 2. The seam's vocabulary: request, result, failure taxonomy

```ts
// packages/code-runtime/code-runtime/src/types.ts (excerpt)

export interface CodeRunRequest {

  program: string

  bindings: CodeBindingNamespace[]

  signal?: AbortSignal

}

export interface CodeRunResult {

  value?: CodeJsonValue

  logs: string[]

  error?: CodeRunFailure

}

export interface CodeRunFailure {

  kind: 'exception' | 'timeout' | 'abort' | 'worker-exit' | 'invalid-output' | 'output-limit'

  message: string

}
```

| Field | Meaning (per the source JSDoc) |
| --- | --- |
| program | The program source. It runs as the body of an async function: top-level await/return work, and the completion value becomes value |
| bindings | Each CodeBindingNamespace becomes one global object in the program |
| signal | Abort: the runtime hard-stops the program (even mid-loop) and resolves with kind 'abort'; in-flight binding calls are the caller's to settle — the runtime only stops asking |
| value? | The program's completion value (its top-level return), which must cross the lossless-JSON boundary; an invalid or over-limit value fails the run instead of being replaced by a rendered string |
| logs | Captured text. Order is preserved within one source; interleaving across sources is backend-dependent; bounded only as part of the outer result |
| error? | Present iff the run failed |

`CodeBindingNamespace` is a three-piece shape: `global` (the identifier the program sees), `functions` (keyed by the exact name the program calls), and an optional `errorClass`. `CodeBindingErrorClass` is `{ name, memberNameProperty }`: the runtime injects a **real error constructor**, rejected member calls become its instances, and the exact member name is exposed through `memberNameProperty` — PTC's `ToolCallError` + `toolName` is exactly this (section 8).

The failure kinds are **orthogonal**; the source JSDoc says it plainly: "a budget expiry is not an exception, an abort is not a timeout, and a substrate death is neither."

| kind | Trigger |
| --- | --- |
| exception | The program threw, or failed to parse/transform (including non-erasable TypeScript) |
| timeout | An implementation-owned budget expired; message says which one |
| abort | CodeRunRequest.signal fired |
| worker-exit | The execution substrate died without settling (e.g. OOM) |
| invalid-output | The completion value was not lossless JSON |
| output-limit | Serialized outer logs/value/diagnostic exceeded the configured cap |

**Two contract points that are easy to misread:**

- **There is no streaming or event API at the seam.** One run is one `Promise<CodeRunResult>`, and `logs` is a settled ordered array. The worker backend does stream log text back to the host **eagerly** (so a killed program still shows what it printed), but that is a backend implementation detail, not the public seam — the seam deliberately exposes no `ctx.on('code-run/…')`-style events.

- **A request carries no optional tuning knobs.** Defaulting (time budgets, output caps) belongs to the implementation's **validated config**; a request carries no field for a hidden `??` to fill in — explicit over implicit.

## 3. The portability contract: one binding list, valid on every backend

The seam treats portability as a hard constraint: a `bindings` list valid on the worker backend must also be valid on the Python backend. Four tables are owned exclusively by the definition package, and every backend enforces them identically.

| Constant | Contents | Why |
| --- | --- | --- |
| Identifier rule | [A-Za-z_][A-Za-z0-9_]* | The language-portable subset; a JS-only spelling like $tools is rejected by design, not just by the Python backend |
| RESERVED_BINDING_GLOBALS | console, __dsh_main__, __builtins__, __name__, __debug__ | Each is owned by some backend (the worker's log-capture slot, Python's bootstrap wrapper and seeded globals). __debug__ is special: CPython compiles a bare reference to the constant True and rejects any assignment to the name at compile time, so an injected global under it is unreachable from the program |
| PORTABLE_RESERVED_WORDS | ECMAScript ∪ Python reserved words (including strict-mode names such as let/static/implements, plus the soft keywords match/type/_) | Otherwise lambda passes the TS backend and fails the Python one; extending the seam with a language means widening this union (a breaking review, by design) |
| RESERVED_ERROR_MEMBERS + DUNDER_MEMBER | name/message/stack (JS Error exclusions), args/with_traceback/add_note (Python exception-protocol members), and every __x__ form | Some CPython descriptors raise on setattr while constructing the rejection, and the exact set is an interpreter-version detail, so dunder forms are refused wholesale |

The worker backend enforces these in `validateBindings()`, and **violations throw** (caller misuse, not a program failure): `binding global … is not a usable identifier`, `reserved binding global …`, `duplicate binding global …`, `binding error class … is not a usable identifier`, `duplicate injected global …`, `binding error member property … is not usable`. All of these throw synchronously on the host and **never spawn a worker**.

## 4. The lifecycle of one run

The order inside `WorkerThreadCodeRuntime.run()` (`src/index.ts`):

- `disposed` check → `run() after disposal` throws.

- `validateBindings(request)` → the contract checks above.

- `request.signal?.aborted` already set → `failureBeforeWorker({ kind: 'abort', … })`, **no spawn**.

- **Host-side type stripping**: `stripTypeScriptTypes(STRIP_WRAP.prefix + program + STRIP_WRAP.suffix)`, then the body is sliced back out by byte position. `STRIP_WRAP` wraps the program as `async function __dsh_program__() { … }` because a bare module parse would reject the top-level `return`; strip mode is **position-preserving** (removed syntax becomes whitespace), so the wrapper survives byte-identical. Non-erasable syntax such as `enum`/namespaces fails here → `kind: 'exception'`, and **no worker spawns**.

- `execute()`: `new Worker(WORKER_PATH, …)` with `WorkerBootData` (stripped code, namespace declarations, `maxOutputBytes`).

- The worker bootstrap materializes the namespaces, runs the program, and posts `done`; the host settles, then `worker.terminate()`s and **awaits exit**.

Every worker option has a stated intent:

| Option | Value | Purpose |
| --- | --- | --- |
| env | {} | Model code gets no ambient environment — stronger than a scrubbed env for a spawned command |
| execArgv | [] | Does not inherit the host's loader flags (a test runner's or tsx's hooks cannot be satisfied by a bare isolate) |
| resourceLimits.maxOldGenerationSizeMb | config (default 512) | Heap cap; overflow kills the worker → kind: 'worker-exit' |
| stdout / stderr | true | Backstop capture: the bootstrap already patches JS-level writes into its own ordered buffer, so the pipes normally stay silent; anything that still arrives (native-level writes) is appended after the done logs |

**One fresh worker per run, never pooled.** A program's world dies with its worker: there is no cross-run state to leak, and the run is reconstructable from the session log alone. `teardown()` marks the service unusable, settles every in-flight run as `{ kind: 'abort', message: 'runtime disposed' }`, and **awaits each worker's exit** before resolving.

## 5. The host↔worker protocol: a port treated as hostile

`src/protocol.ts` is a **versionless, structured-clone** vocabulary. Model code can reach `parentPort` and forge traffic, so trust is asymmetric: **the host does not trust the worker; the worker trusts the host.**

| Direction | Message | Payload |
| --- | --- | --- |
| worker→host | call | { id, global, name, args } — id is a worker-issued correlation id |
| worker→host | log | { text } — streamed eagerly, so a killed program still leaves its output |
| worker→host | output-limit | worker-side capture or completion measurement crossed the cap |
| worker→host | done | { value?, error? }, where error.kind is only 'exception' | 'invalid-output' | 'output-limit' (budgets, aborts, and substrate death are observed host-side) |
| host→worker | reply | { id, ok: true, value } or { id, ok: false, message }; each id is answered at most once |

The host's hostile-peer rules (`parseWorkerMessage` + `onCall`):

- **Shape-validate, then rebuild field by field**: the compile-time `WorkerToHost` type means **nothing** here; the peer can post anything. A forged extra field never rides along, a non-number call id can never be echoed into a reply, and junk returns `undefined` and is dropped silently (a throw in the `message` listener would **crash the host process**).

- **Each call id is answered at most once**: duplicates are ignored.

- **Binding names resolve as own properties only**: `Object.hasOwn(record, name)`, so a forged `constructor`/`hasOwnProperty` cannot walk the prototype chain.

- **Arguments and results both pass lossless-JSON validation**: invalid args → `ok: false`; an invalid binding resolution → `ok: false, message: 'binding resolution must be lossless JSON'`; a binding throw/reject → `ok: false`, surfacing inside the program as the namespace's **typed rejection** and **never crashing the host**.

The worker side defends itself symmetrically: namespace objects are built with `Object.create(null)` + `Object.defineProperty`, so names like `__proto__`/`constructor` are **ordinary own keys** rather than prototype collisions; every function snapshots its args with `snapshotCodeJsonValue` before posting a `call`.

**Cross-boundary JSON travels as a flat token stream.** `WorkerJsonWire` is a pre-order array of tokens (container markers and scalar leaves in one list), and `encodeWorkerJson`/`decodeWorkerJson` traverse iteratively, so `worker_threads` structured clone **never has to recurse over the application's nesting depth**. Both sides' `snapshotCodeJsonValue` accept lossless JSON only: `NaN`/`Infinity`/`-0`, sparse arrays, prototype-bearing or accessor objects, symbol keys, and cycles all yield `undefined` (`src/worker-json.ts`).

## 6. Budgets, the output ledger, and termination

Two **independent** budgets exist because the peer is hostile:

| Budget | Mechanism | Why it is this |
| --- | --- | --- |
| computeMs | The host polls worker.performance.eventLoopUtilization() every 25 ms; elu.active > computeMs settles the run as timeout | It meters measured busy time: a hot loop cannot hide behind a suspended decoy dispatch, while a program awaiting a slow tool accrues nothing (fair and ungameable). The cost is that expiry can overshoot by up to one poll interval (25 ms is an internal constant, deliberately not configurable) |
| maxWallMs | A single setTimeout backstop | Covers what busy time cannot see — awaiting a promise nobody will resolve. Validated at load to ≤ MAX_TIMER_DELAY_MS (2_147_483_647), because setTimeout clamps a longer delay to 1 ms |

Both funnel into `worker.terminate()`, which **also stops a hot synchronous loop** — something an ordinary "stop waiting after a timeout" cannot do.

The **output ledger** (`OutputLedger`) counts JSON-serialized bytes only: the outer `logs` array plus the completion value or failure diagnostic; **fixed envelope syntax (the `CodeRunResult` field names) is excluded**. The rules:

- Each log is `admit`ted in order; the first overflow stops admission and marks the ledger.

- The completion value is measured against the remaining budget first: invalid → `invalid-output`; valid but too large → `output-limit` (**never** a substituted `inspect` string).

- Failure diagnostics are pre-checked the same way — a million-byte stack becomes a **fixed** `output-limit` diagnostic at the worker boundary.

- Either way, the result keeps a **fitting prefix of the logs** (measured: with a 4096-byte cap, 4058 bytes were retained).

The default 64 MiB is a **rejection boundary, not recoverable storage**: bytes rejected beyond the runtime cap never reach the [spill](../../features/spill.md) layer, which can only save the bounded logs and diagnostic returned after `output-limit`.

## 7. The config surface and the failure modes

`WorkerThreadCodeRuntime.Config` is a schemastery schema; every cap is changeable from the composition YAML, with **no hardcoded tunables**:

| Config | Default | Validation |
| --- | --- | --- |
| computeMs | 60_000 | Finite positive number |
| maxWallMs | 600_000 | Finite positive number and ≤ 2_147_483_647 |
| maxOutputBytes | 67_108_864 (64 MiB) | Safe integer and ≥ 4 (the smallest representable empty logs array plus empty failure message) |
| maxOldGenerationSizeMb | 512 | Finite positive number |

The Loader fills defaults from the schema; **direct construction** (bypassing the Loader) must supply every field, and the constructor re-checks positivity/bounds, failing with messages like `config.maxWallMs must be at most 2147483647 (Node clamps a longer setTimeout delay to 1ms), got 2147483648`.

The failure modes keep **program outcomes and caller errors strictly apart**:

- Program outcomes → `result.error` (the six `kind`s).

- Caller contract misuse → throw: `run() after disposal`, binding-name validation, `config.*` validation.

The README's current limitations (package constraints, not a task backlog):

- **OS processes a program spawns survive `terminate()`** — the thread dies, weaker than bash-local's process-group kill; orphan cleanup is a deployment concern until a container backend exists.

- **Type stripping rides the experimental `stripTypeScriptTypes` API**; amaro / sucrase are the named drop-in replacements if its behavior shifts.

- **`console` has exactly five methods** (`log`/`info`/`warn`/`error`/`debug`), rendering arguments with `inspect` (`depth: 4`, `maxArrayLength: 100`, `maxStringLength: 10_000`) — deliberately not Node's full console.

- **Intermediate binding values have no byte cap** — a program can exhaust process or worker memory with a value that never becomes outer output.

## 8. How PTC routes through this seam

For details and the PTC tables see [Tools Execution](../../learn/core/tools-execution.md) (the `run_code` transport, the SDK section, sub-call concurrency, and `tool/ptc-dispatch*` events) and [Tools](../../features/tools.md) (the tool surface and per-profile config). At the **seam boundary** there are only four moves (`packages/core/tools/src/ptc.ts`):

- **Resolve the runtime**: `requireRuntime()` = `ctx.get('codeRuntime')`, throwing `dsh-tools: mode "ptc" requires a code runtime …` when absent, and also when `language` has no SDK renderer. The `run_code` schema text is resolved **at emission time** from `runtime.language`, so the model's description and the SDK section share a language.

- **Build exactly one namespace**: `global: 'tools'`, with `functions` being the **calling agent's visible** tool set (`registry.schemas(exec.agent)`, skipping `run_code` itself), materialized with null-prototype + `defineProperty`, isomorphic to the worker side.

- **Declare the typed rejection**: `errorClass: { name: 'ToolCallError', memberNameProperty: 'toolName' }`, so `catch (e) { e.toolName }` inside the program yields the **exact tool name** (measured: `e.name === 'ToolCallError'`).

- **Call and map**:

```ts
// packages/core/tools/src/ptc.ts (excerpt)

result = await runtime.run({

  program: args.code,

  bindings: [{ global: 'tools', functions,

    errorClass: { name: 'ToolCallError', memberNameProperty: 'toolName' } }],

  signal: runController.signal,   // follows the outer signal and always fires when the run settles

})

if (result.error) {

  throw new CodeRunFailedError(`code run failed (${result.error.kind}): ${result.error.message}…`)

}

return { logs: result.logs, ...result.value !== undefined ? { result: result.value } : {} }
```

`CodeRunFailedError` is a `HarnessError` (`code: 'CODE_RUN_FAILED'`), which the registry turns into a structured `isError` for the model to self-correct. Note the seam boundary: **runtimes know nothing about tools, sessions, or model context**; binding traffic and intermediate values stay execution-local, and only the outer `{ logs, result? }` enters model context.

## 9. Division of labor with sandbox: who isolates what

Both names sound like "isolation", but they sit at completely different layers:

|  | ctx.codeRuntime (this page) | ctx.sandbox |
| --- | --- | --- |
| What is isolated | One program execution (a thread inside a JS isolate) | The process and all its descendants wrapped by confine |
| Mechanism | node:worker_threads + empty env + execArgv: [] + heap cap + hard termination | OS-level: Linux bwrap/Landlock, macOS Seatbelt, Windows restricted-token runner |
| What is bounded | Resources and terminability (time, heap, output), not capabilities | File effects (read-only/workspace-write/danger-full-access); the vocabulary has no network/process/syscall limits |
| Failure posture | Program failure = a result field; contract misuse = throw | Fail closed: no available backend throws SANDBOX_UNAVAILABLE, never a bare run |
| Trust posture | Source doc: "bash-equivalent trust"; the isolation field is a diagnostic label, not a security claim | Distrust by default; the caller chooses a policy per call |

**One sentence**: code-runtime provides **containment** — a separate isolate, an empty environment, a heap cap, and hard termination that stops a hot loop; it does **not** restrict which files or network a program touches, nor the processes it spawns. A program can still `import` Node APIs and start subprocesses, and those subprocesses **survive `terminate()`** and are **not constrained by the worker**. To get a file fence, the program must go through a **binding call** (for example the bash tool) that rides `ctx.sandbox` — or wait for a container-class backend to provide a real boundary.

## 10. Sources

| Location | Symbol / fact |
| --- | --- |
| packages/code-runtime/code-runtime/src/index.ts | CodeRuntime, run/language/isolation, RESERVED_BINDING_GLOBALS, RESERVED_ERROR_MEMBERS, DUNDER_MEMBER, PORTABLE_RESERVED_WORDS, the codeRuntime key in declare module '@deepseek-ai/cordis' |
| packages/code-runtime/code-runtime/src/types.ts | CodeBindingFunction, CodeJsonValue, CodeBindingErrorClass, CodeBindingNamespace, CodeRunRequest, CodeRunFailure, CodeRunResult, the six kinds |
| packages/code-runtime/code-runtime-worker-thread/src/index.ts | WorkerThreadCodeRuntime, Config, ELU_POLL_INTERVAL_MS, MIN_OUTPUT_BYTES, IDENTIFIER, STRIP_WRAP, WORKER_PATH, LiveRun, OutputLedger, parseWorkerMessage, validateBindings, execute, teardown |
| packages/code-runtime/code-runtime-worker-thread/src/protocol.ts | WorkerBootData, CallMessage, LogMessage, OutputLimitMessage, DoneMessage, WorkerToHost, ReplyMessage |
| packages/code-runtime/code-runtime-worker-thread/src/bootstrap.ts | runWorkerMain, makeNamespaces, makeConsoleShim, captureStreamWrites, LogBuffer, makeBindingErrorClass, wireReplies, PendingCall, INSPECT_OPTIONS |
| packages/code-runtime/code-runtime-worker-thread/src/worker.ts | The runWorkerMain(parentPort, workerData, …) entry |
| packages/code-runtime/code-runtime-worker-thread/src/worker-json.ts | WorkerJsonWire, encodeWorkerJson, decodeWorkerJson, snapshotCodeJsonValue |
| packages/code-runtime/code-runtime-worker-thread/src/output-json.ts | jsonStringBytesUpTo, jsonValueBytesUpTo, truncateJsonStringBytes |
| packages/core/tools/src/ptc.ts | RUN_CODE_NAME, createRunCodeTool, CodeRunFailedError (CODE_RUN_FAILED), global: 'tools', ToolCallError/toolName, runtime.run({…}) |
| packages/core/tools/src/index.ts | requireCodeRuntime, peekRuntime, SDK_RENDERERS, maxParallelSubCalls |
| packages/core/agent-tool-presentation/src/index.ts | inject = ['tools'] and the non-native ctx.inject(['codeRuntime'], …) wait |
| packages/bundle/headless/cordis.patch.yml, packages/bundle/web-app/cordis.patch.yml | The two id: code-runtime / name: '@deepseek-ai/dsh-code-runtime-worker-thread' mounts |
| packages/util/timeout/src/index.ts | MAX_TIMER_DELAY_MS = 2_147_483_647 |

## 11. Verification

```sh
# 1. Composition: web / headless should each carry a code-runtime row, and the tools mode can be overridden by DSH_TOOLS_MODE

dsh web --dump-config | grep -iE "code-runtime|tool-presentation|maxOutputBytes"

grep -n "code-runtime" packages/bundle/*/cordis.patch.yml

# 2. The seam vocabulary and the six failure kinds live in two files

grep -n "kind: 'exception'\|RESERVED_BINDING_GLOBALS\|PORTABLE_RESERVED_WORDS" \

  packages/code-runtime/code-runtime/src/types.ts packages/code-runtime/code-runtime/src/index.ts

grep -n "type: 'call'\|type: 'reply'\|type: 'done'\|type: 'output-limit'" \

  packages/code-runtime/code-runtime-worker-thread/src/protocol.ts

# 3. Budgets, ledger, and the hostile-port rules

grep -n "eventLoopUtilization\|MAX_TIMER_DELAY_MS\|Object.hasOwn\|MIN_OUTPUT_BYTES\|STRIP_WRAP" \

  packages/code-runtime/code-runtime-worker-thread/src/index.ts

# 4. The consumer's seam

grep -n "runtime.run({\|errorClass\|requireCodeRuntime" packages/core/tools/src/ptc.ts packages/core/tools/src/index.ts
```

To see the six failure kinds yourself, construct `WorkerThreadCodeRuntime` directly and run a few programs — no full `dsh` boot required. Measured output (Node v24.15.0 locally, `maxOutputBytes: 4096`, `computeMs: 400`):

```text
success            {"value":{"ok":true,"r":{"n":42}},"logs":["hello { a: 1 }","r=42"]}

exception          {"logs":[],"error":{"kind":"exception","message":"Error: program blew up\n    at …"}}

invalid-output     {"logs":[],"error":{"kind":"invalid-output","message":"program completion must be lossless JSON"}}

binding-rejection  {"value":{"name":"ToolCallError","toolName":"boom","message":"host says no"}}

timeout            {"logs":[],"error":{"kind":"timeout","message":"compute budget exhausted (400ms busy)"}}

abort              {"logs":[],"error":{"kind":"abort","message":"caller gave up"}}

output-limit       {"logCount":1,"logLen":4058,"error":{"kind":"output-limit","message":"outer output exceeded 4096 bytes"}}

enum               {"logs":[],"error":{"kind":"exception","message":"TypeScript enum is not supported in strip-only mode"}}

run() after disposal  → throw: dsh-code-runtime-worker-thread: run() after disposal

reserved global console → throw: dsh-code-runtime-worker-thread: reserved binding global "console"
```

## Next steps

- [Tools Execution](../../learn/core/tools-execution.md): PTC mode, the SDK section, and `tool/ptc-dispatch*` events (deliberately not repeated here)

- [Sandbox & Security](../../learn/core/sandbox-security.md): `ctx.sandbox.confine`'s file fence and fail-closed posture

- [Writing a Service](../../learn/dev/write-service.md): how to provide your own capability seam with `ctx.provide`

- [Spill](../../features/spill.md): the overflow policy for an outer `run_code` result once it enters model context

- [Tools](../../features/tools.md): which tools are mounted and how to configure them per profile
