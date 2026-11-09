# Driving Harness from a Program: the SDK

**In short**: the SDK starts a `dsh` profile as a subprocess, drives it over newline JSON-RPC on stdio, and owns shutdown. Source baseline: `0.1.5-alpha.1` / `5dda764ed3`; npm `latest` / `next` resolve to `0.1.2-rc.1` and the `alpha` channel is `0.1.5-alpha.1` ([status](../guides/deepseek-harness-status.md)).

The TypeScript client resolves a matching `@deepseek-ai/dsh` dependency unless `dshBin` is supplied. Select composition with `profile` (default `sdk`) and ordered `patches`, not the old `launch: { command, args }` contract or a complete external `cordis.yml`. The application being developed remains a separate workspace.

## Contents

- [Components and roles](#components-and-roles)
- [The server: the sdk-jsonrpc-server plugin and the app boundary](#the-server-the-sdk-jsonrpc-server-plugin-and-the-app-boundary)
- [Transport: JsonRpcLineTransport](#transport-jsonrpclinetransport)
- [Wire methods](#wire-methods)
- [Client: two layers](#client-two-layers)
- [Python SDK](#python-sdk)
- [Why this satisfies "drive DSH as an embedded runtime"](#why-this-satisfies-drive-dsh-as-an-embedded-runtime)
- [Verify / try it](#verify-try-it)
- [Next steps](#next-steps)

---

## Components and roles

| Package | Role |
| --- | --- |
| @deepseek-ai/dsh-sdk-protocol | Defines the SDK runtime wire protocol: one newline-delimited JSON-RPC transport class plus the named request/result/notification types both ends speak |
| @deepseek-ai/dsh-sdk-client | TypeScript client, with the high-level DeepSeekHarness and the low-level HarnessClient |
| @deepseek-ai/dsh-sdk-jsonrpc-server | Server plugin: serves out-of-process SDK clients over newline JSON-RPC on stdio |
| deepseek-harness-sdk | Python edition (deepseek_harness), mirroring the same protocol and layering without importing the TS types |

## The server: the sdk-jsonrpc-server plugin and the app boundary

The runtime side is handled by a plugin named `sdk-jsonrpc-server`. It declares `inject: ['agents']` (`packages/sdk/server/src/index.ts`):

```ts
export const name = 'sdk-jsonrpc-server'

// Only the agent factory is required; initialize reads the optional LLM seam with ctx.get().

export const inject = ['agents']
```

Its core is `HarnessSdkJsonRpcServer`: on construction it subscribes to session, agent, and subagent lifecycle events and sends notifications; `initialize` configures the route and, when needed, mounts the DeepSeek adapter fallback; `session/prompt` gets-or-creates one session per sessionId, queues one user message, and immediately returns the `{ messageId }` enqueue receipt; `shutdown` disposes all SDK-owned agents, adapter, and subscriptions to quiescence, then the plugin flushes the response, disposes the root context, and exits `0`. `handleRequest` is the method dispatcher (`packages/sdk/server/src/server.ts`):

```ts
async handleRequest(method: string, params: Record<string, unknown> | undefined): Promise<unknown> {

  switch (method) {

    case 'initialize':          return this.initialize(params as unknown as InitializeParams)

    case 'session/prompt':      return this.prompt(params as unknown as SessionPromptParams)

    case 'shutdown':            return this.shutdown()

    default:                    throw new Error(`unknown DeepSeek Harness SDK runtime method: ${method}`)

  }

}
```

**Stdout is the protocol.** The selected SDK profile reserves stdout for JSON-RPC frames; diagnostics go to stderr. Custom plugins and patches must preserve this separation. See `packages/bundle/sdk-app` and `packages/sdk/server`.

## Transport: JsonRpcLineTransport

The protocol uses a single transport class, `JsonRpcLineTransport`, to carry JSON-RPC 2.0 frames over **caller-owned byte streams**, one compact JSON frame per `\n`-terminated line (`packages/sdk/protocol/src/transport.ts`):

- A frame with `id` plus `method` is a request; `id` alone is a response; `method` alone is a notification; **malformed JSON lines are ignored**.

- `start()` attaches stream listeners; `close()` detaches them and rejects pending requests without destroying the streams.

- A missing request handler answers `-32601`; a handler rejection answers `-32603` with the message. An error response rejects the pending `request()` with `JsonRpcResponseError`, which preserves the wire `code` and optional `data`.

```ts
private write(message: Record<string, unknown>): void {

  this.output.write(`${JSON.stringify(message)}\n`)

}
```

## Wire methods

The protocol names every payload (`HarnessSdkRequestMap` / `HarnessSdkNotificationMap` in `packages/sdk/protocol/src/types.ts`):

| Direction | Method | Payload | Notes |
| --- | --- | --- | --- |
| client→server | initialize | InitializeParams → InitializeResult | Process-wide handshake: cwd + provider/model route + optional positive maxTokens |
| client→server | session/prompt | SessionPromptParams → SessionPromptResult | Queues one user message and immediately returns the durable { messageId } receipt |
| client→server | shutdown | no params → {} | Disposes SDK-owned agents/adapter/subscriptions to quiescence, then exits |
| server→client | session.event | SessionEventNotification | The full session-log event for every session in the runtime (unfiltered), streamed as recorded |
| server→client | session.status | SessionStatusNotification | Whole-agent running / idle transition |
| server→client | subagent.started | SubagentStartedNotification | An in-runtime child session was created |
| server→client | subagent.finished | SubagentFinishedNotification | An in-process subagent run ended (local runs only; remote runs are not reported) |

Key semantics, from the protocol README / type JSDoc:

- `SessionPromptResult.messageId` identifies the queued `UserMessage` only; it does **not** denote a later assistant message, a turn ending, or a prompt result.

- Clients combine the open-ended `session.event` stream with whole-agent `session.status` to own their activity interval.

- `SubagentFinishedNotification.lastAssistantMessage` carries the child's last non-empty assistant message; the field is absent when it produced neither.

- `InitializeParams.maxTokens` is an optional positive safe integer capping each conversation-model output for SDK-created agents (and in-process descendants).

- `serverInfo.name` stays the wire-stable `deepseek-harness-sdk-runtime` (current version `0.0.1`, unvalidated).

The protocol README also states honest limits: **no protocol-version negotiation** (`serverInfo.version` unvalidated), **no cancel or session-close methods** (abandon a turn by closing the runtime process), and server→client requests are a "dead capability" (the transport supports them but the server never sends one — reserved for future approval flows).

## Client: two layers

### High-level DeepSeekHarness (owns the run lifecycle)

```ts
import { DeepSeekHarness } from '@deepseek-ai/dsh-sdk-client'

await using harness = new DeepSeekHarness({

  profile: 'sdk',

  dshHome: '/absolute/path/to/isolated-dsh-home',

  cwd: '/absolute/path/to/workspace',

  provider: 'deepseek-official',

  model: 'deepseek-v4-flash',

  maxTokens: 49_152,

})

const result = await harness.run('say hi')

console.log(result.finalResponse)
```

(`packages/sdk/client/README.md` and `src/api.ts`) Key points:

- The subprocess starts **lazily on first use** and stays owned by this instance across `run()` calls; `close()` (or `await using`) is **required** so the child is always reaped.

- `start()` memoizes the `initialize` handshake; a failed handshake reaps the runtime and swaps in a fresh client so a later call retries with a new subprocess (until `close()` is terminal).

- `run(input, { sessionId?, onNotification? })` owns one activity interval: queue the prompt → wait until its `MessageId` appears in the durable `agent/inbox/spliced` receipt → collect through the next **whole-agent idle**. Returns `RunResult { sessionId, finalResponse, events, notifications }`.

- `finalResponse` is the last committed root-session assistant text in the interval, not a response causally assigned to the prompt — steering, injected context, and other queued work may contribute before idle. `events` contains only root-session events, while `notifications` also includes descendants discovered from `subagent.started`, all in wire order.

- `session(id?)` opens a named or fresh session handle.

`HarnessSession.run` in `src/api.ts` is that "receipt → idle" collection loop:

```ts
const messageId = await client.prompt(this.id, contentBlocks)

let received = false

while (true) {

  const notification = await subscription.next()

  if (!received) {

    if (notification.method !== 'session.event'

      || notification.params.sessionId !== this.id

      || !isInboxReceipt(notification.params.event, messageId)) continue

    received = true

  }

  collect(notification)

  if (notification.method === 'session.status'

    && notification.params.sessionId === this.id

    && notification.params.status === 'idle') break

}
```

### Low-level HarnessClient (fine-grained control)

The protocol client (`src/client.ts`): explicit `start()` / `initialize()` / `prompt()` / `request()` / `close()`, plus notification subscriptions.

- `prompt(sessionId, contentBlocks)` returns the queued message id as soon as the runtime accepts it; it **never waits** for agent activity.

- `subscribe(filter?)` returns a `NotificationSubscription` (awaitable `next()`, non-blocking `tryNext()`, async iteration); `subscribeSessionTree(id)` scopes to one session and the descendants discovered from `subagent.started` lineage edges — the runtime notifies for every session in its context, and scoping is **client-side**, exactly like the Python SDK.

- Typed errors (`src/client.ts`): `JsonRpcResponseError` (wire error response, code/data preserved), `RequestTimeoutError` (a bound elapsed), `SdkProtocolError` (a response outside the documented protocol), `TransportClosedError` (the runtime is gone — message carries the exit code and a bounded stderr tail).

- `close()` requests protocol `shutdown` (bounded by `shutdownTimeoutMs`, default 1000ms), then walks the stdin-EOF → SIGTERM → SIGKILL ladder (`disposeEofGraceMs` default 6000, `disposeGraceMs` default 3000) until the process has actually exited. The ladder runs outside any harness context, so it does not go through the `dsh-subprocess` service — the seam's documented exception. It is idempotent, and a closed client refuses reuse.

- `HarnessClientOptions.env` replaces the child environment entirely when given (`undefined` inherits the parent's); callers own credential policy (`scrubbedParentEnv` from `dsh-subprocess` is the shared base for isolation-minded launches).

Both clients are pure libraries: they register nothing on a Cordis context. The runtime process they spawn is a **complete harness** whose composition is selected by its profile and patches.

## Python SDK

Install a matching SDK/runtime pair; the source contract below is not a promise that the alpha wheel is already published.

```python
from deepseek_harness import DeepSeekHarness

with DeepSeekHarness(

    dsh_home="/absolute/path/to/isolated-dsh-home",

    cwd="/absolute/path/to/workspace",

    profile="sdk",

    provider="deepseek-official",

    model="deepseek-v4-flash",

    max_tokens=49_152,

) as harness:

    result = harness.run("Summarize the project.")

    print(result.final_response)
```

- The package depends on the exact same-version `deepseek-harness-runtime-bin` wheel. It launches bundled `dsh --profile sdk`; it is not the old `dsh-jsonrpc-agent` entry point.

- Supply `dsh_home` or a non-empty child `DSH_HOME`; the Python SDK deliberately does not discover `~/.dsh`.

- `cwd` is the Agent workspace; `runtime_cwd` is the subprocess directory. `patches` are ordered overlays; `dsh_bin` overrides the CLI executable while retaining profile grammar.

- Python initialization defaults to 30 seconds (`initialize_timeout_seconds`); ordinary turns are unbounded unless `request_timeout_seconds` is set. TypeScript's initialization default is 10 seconds.

- Source runtime-wheel targets include Windows x64, Linux x64/arm64, and macOS 14+ arm64 and x64 (macOS x64 added in 0.1.3-alpha.1). Check availability for the chosen release rather than inferring publication from source.

- `run()` owns the durable inbox-receipt-to-idle activity interval. `final_response` and `finish_reason` describe the last root response / turn end in that interval, not a response exclusively caused by the prompt.

- Use the context manager or `close()` to reap the child.

### Full vs minimal profiles

`sdk` inherits the base composition. `sdk-minimal` is a standalone tree, with a platform-selected persistent shell, `str_replace_editor`, one DeepSeek adapter, and uncompressed JSONL sessions. It omits settings, managed credentials, telemetry, Web tools, compaction, workspace instructions, skills, jobs, and subagents.

**Minimal does not mean restricted**: `sdk-minimal` pins `danger-full-access`; shell/editor operations can reach every path available to the process. Use a disposable environment, not merely a different working directory.

## Why this satisfies "drive DSH as an embedded runtime"

- **The seam is a pure process boundary** — the runtime is a subprocess and stdio is a factory protocol; no UI, network port, or global install is required, so it embeds in CI, batch jobs, and orchestrators.

- **Stdout purity** — protocol frames own stdout, diagnostics go to stderr, and no logging can pollute programmatic parsing.

- **Well-defined activity intervals** — `run()` (or your own combination of `session.event` + `session.status`) abstracts "send a prompt → wait until the whole agent is idle" into a single awaitable call, returning `finalResponse` plus the full event/notification stream.

- **Complete lifecycle** — `await using` / the context manager guarantees the child is reaped; `close()` walks the protocol `shutdown` + EOF/SIGTERM/SIGKILL ladder to an idempotent terminal state.

- **Symmetric, two languages** — TS and Python speak the same wire; pick either. The cross-process subagent backend (`dsh-sdk` subagent provider) is exactly what runs each subagent as a full peer harness through this TS client.

## Verify / try it

After building the matching official source:

```sh
pnpm dsh --profile sdk --help

pnpm dsh --profile sdk-minimal --help

pnpm dsh --profile sdk --dump-config
```

A real session additionally requires a configured model route and credentials. Use the TypeScript example above or the Python source example:

```sh
python python/sdk/examples/minimal.py "Say hi" \

  --workspace /absolute/path/to/disposable-workspace \

  --dsh-home /absolute/path/to/isolated-dsh-home
```

The Python example explicitly selects `sdk-minimal`; see its access policy above. Observe `session.event` / `session.status` through subscriptions or `run(input, { onNotification })`. Old `demo:jsonrpc` and complete-config launch examples have been replaced by profiles.

## Next steps

- To see this API used as a subagent backend inside the harness, see [Subagents and Parallelism](../features/subagent.md).

- The full property and limitation references live in the source: `packages/sdk/{protocol,client,server}/README{.zh}.md` and `python/sdk/README{.zh}.md`.
