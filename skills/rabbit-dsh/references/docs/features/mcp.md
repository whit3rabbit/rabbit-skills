# MCP Integration

[MCP (Model Context Protocol)](https://modelcontextprotocol.io/) is the open standard for AI applications to connect external data sources and tools. DSH bridges it through `@deepseek-ai/dsh-mcp-client`: connect to an external MCP server, register its tools into `ctx.tools`, and the model can call them just like local tools, named `mcp__<serverName>__<rawName>`.

## Contents

- [In one sentence](#in-one-sentence)
- [Configuration](#configuration)
- [Merging tools into the registry](#merging-tools-into-the-registry)
- [Connection, reconnect, and failure semantics](#connection-reconnect-and-failure-semantics)
- [Difference from custom tools](#difference-from-custom-tools)
- [When to use](#when-to-use)
- [Current boundaries](#current-boundaries)
- [Verification](#verification)
- [Next steps](#next-steps)
- [Optional memory servers](#optional-memory-servers)

---

## In one sentence

"One plugin instance = one MCP server," mounted in `cordis.yml`/patch.

## Configuration

The most common is `stdio`: launching a local subprocess as the server.

```yaml
- id: mcp-github

  name: '@deepseek-ai/dsh-mcp-client'

  config:

    serverName: github

    transport: stdio

    command: npx

    args: ['-y', '@modelcontextprotocol/server-github']

    env:

      GITHUB_TOKEN: !!js process.env.GITHUB_TOKEN
```

You can also connect a **remote** server (`streamable-http`):

```yaml
- id: mcp-web

  name: '@deepseek-ai/dsh-mcp-client'

  config:

    serverName: web

    transport: streamable-http

    url: http://localhost:3000/mcp

    headers:

      Authorization: !!js '`Bearer ${process.env.MCP_TOKEN}`'
```

Full field list:

| Field | Transport | Required | Effect |
| --- | --- | --- | --- |
| transport | both | yes | "stdio" or "streamable-http" |
| serverName | both | yes | Tool-name namespace, [A-Za-z0-9_-]{1,32}, unique across live instances |
| command | stdio | yes | The executable to launch |
| args | stdio | no | Arguments passed to the command |
| env | stdio | no | Extra environment variables, merged on top of the scrubbed host environment |
| cwd | stdio | no | Subprocess working directory |
| url | http | yes | MCP server address |
| headers | http | no | Extra request headers (e.g. auth token) |
| toolCallTimeoutMs | both | no | Per-callTool timeout (default 60000) |
| failOnStartupError | both | no | Reject activation when initial connection/sync fails (default false) |
| reconnect.enabled | both | no | Auto-reconnect after a drop (default true) |
| reconnect.initialDelayMs | both | no | First reconnect delay, doubled on consecutive failures (default 500) |
| reconnect.maxDelayMs | both | no | Backoff cap, also the uptime needed to reset the reconnect budget (default 30000) |
| reconnect.maxAttempts | both | no | Consecutive-failure cap per disconnect (default 10) |

## Merging tools into the registry

Once connected, external MCP tools become ordinary tools on `ctx.tools`. Each tool has **two names**: the raw name (what `tools/call` sends to the server) and a public name `mcp__<serverName>__<rawName>` (what the model sees/calls). For example, `github`'s `create_issue` becomes `mcp__github__create_issue`. The public name normalizes to the DeepSeek function-name contract (≤64 chars, `[A-Za-z0-9_-]`), appending a 12-digit hex hash derived from `(serverName, rawName)` on renaming to prevent name collapses; the name is a pure function of `(serverName, rawName)`, unchanged by connection order or resync.

Name conflicts are deterministic: two servers emitting the same raw name coexist within their own namespaces; two live instances with the same `serverName` cause the later-mounted one to fail; a server listing the same tool name twice is an invalid list; an external registration squatting the namespace rolls back the whole generation with a loud error.

Once merged, they go through the **same tool pipeline** (see [tool execution](../learn/core/tools-execution.md)): `tools/pre-execute` gating, timeouts, and result rewriting all apply, so policies like allow/deny lists uniformly govern external tools.

## Connection, reconnect, and failure semantics

- **Discovery**: `await listTools()` on activation, then `ctx.tools.register()` one by one before the first round; failures are logged, and only `failOnStartupError: true` rejects activation.

- **Hot updates**: listens for `notifications/tools/list_changed` to resync; a failed fetch keeps the previous generation of tools, and registration conflicts roll back the attempted generation.

- **Execution**: `client.callTool({ name: rawName, arguments }, { signal })` with timeout and cancellation; the public name is never sent to the server; `isError` goes through the registry error path.

- **Drop reconnect**: the supervisor restarts per the original config with exponential backoff, rerunning discovery on success; recovery replaces the previous generation without duplicating or leaking, and the last good generation stays registered during a disconnect. After `maxAttempts` consecutive failures for the same disconnect, tools are deregistered and reconnecting stops until an HMR reload or Host restart.

## Difference from custom tools

|  | Local tools | MCP tools |
| --- | --- | --- |
| Implementation | plugin ctx.tools / defineTool | external MCP server |
| Naming | snake_case names | mcp____ |
| Lifecycle | in-process | bridged process/remote |
| Both | go through the same pipeline | go through the same pipeline |

## When to use

- You already have a bunch of MCP servers (filesystem, GitHub, database, in-house tools) and don't want to write a dedicated integration for each

- You want to bring external tools under DSH's **tool governance** (gating/timeout/cancellation)

- Typical: connect a GitHub server to let the model open issues / query PRs; connect a database server to expose read-only queries; connect an in-house API gateway so dozens of operations are wired in at once, all governed uniformly under `tools/pre-execute`

## Current boundaries

- **Only tools are bridged**: Resources and Prompts have no harness consumer.

- **Startup timeout inherits the MCP SDK** (60-second default); an unresponsive server slows activation and cleanup; `streamable HTTP` failures surface per request, with unreachability being a per-call retry rather than a restart.

- **Image is the only durable rich-result bridge (rc.7)**: PNG/JPEG/WebP/GIF become durable core image blocks in the model context when `ctx.attachments` is mounted and the calling model route explicitly declares image input; the whole batch is decoded and admitted before any member is saved, and malformed or unsupported batches become diagnostic text. Audio and embedded-resource payloads stay out of model context (the canonical value keeps the JSON block), and resource links keep only their name and URI as text.

- **Unsupported output schemas are not enforced**: `structuredContent` falls back to `JsonValue`.

## Verification

```sh
# see the mcp client in the composition tree

dsh web --dump-config | grep -A3 mcp

# see tool calls in the session log (mcp__ prefix naming)

zstdcat ~/.dsh/sessions/*/*/session*.jsonl.zstd | grep -E '"mcp__' | head
```

## Next steps

- [Built-in tools](../features/tools.md): the shipping tool list

- [Writing a tool](../learn/dev/write-tool.md): how local tools are defined

## Optional memory servers

Current official source includes three external MCP memory examples (Engram, reference memory, Memorix) under `apps/cli/config/examples/mcp-memory/`. These are opt-in overlays, not built-in durable memory. Follow the [official guide](https://github.com/deepseek-ai/deepseek-harness/blob/master/docs/user/guide/mcp-memory.md) for dependencies, data directories, and process setup.

For installation, storage scoping, and a write → fresh-session recall → use checklist, see [Persistent MCP memory](../guides/mcp-memory.md).
