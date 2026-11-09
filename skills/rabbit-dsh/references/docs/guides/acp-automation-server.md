# ACP automation server

**In short**: `@deepseek-ai/dsh-acp` exposes a Harness runtime over ACP JSON-RPC stdio. Source `0.1.5-alpha.1` (`5dda764ed3`) expands the former automation-only surface with session navigation, model options, MCP, and richer updates.

See [source/npm channels](../guides/deepseek-harness-status.md): these are source-build capabilities, not a claim about the older default npm release.

## Launch and composition

```sh
# In a built official source checkout

pnpm dsh --profile acp --help

pnpm dsh --profile acp
```

The shipped profile is `packages/bundle/acp-app`, replacing the removed ACP demo bin. It supplies the application composition and a DeepSeek route; `packages/acp/acp` owns the protocol bridge. Keep stdout exclusively for protocol frames and send diagnostics to stderr.

## Negotiated capabilities

`initialize` advertises ACP v1, HTTP MCP, and session `list` / `resume` / `close`. Standard stdio MCP is also accepted. Image input is conditional on durable attachment support and the configured model route; audio and embedded context are not advertised. The returned `authMethods` list is empty; this does not make remote MCP credentials unnecessary.

Read the returned capability set instead of hard-coding every feature as available.

## Methods

| Method | Current contract |
| --- | --- |
| session/new | Absolute cwd; validate and connect stdio/HTTP MCP servers before publishing a new Agent |
| session/list | Newest-first resumable root sessions; optional cwd filter and pagination |
| session/resume | Restore an inactive persisted session after canonical cwd validation; no transcript replay |
| session/close | Cancel and drain the target and descendants, flush/dispose; preserve the persisted log |
| session/set_config_option | Select model or reasoning_effort, returning the complete option state |
| session/prompt | Ordered text/resource links and supported images; one in-flight prompt per session; model route pinned for that turn |
| session/cancel / $/cancel_request | Cancel active work; session cancellation also covers autonomous activity |
| session/update | Committed assistant/thought content, generic tool lifecycle, config and context-usage updates |
| session/request_permission | Client answers the bridge's one-time allow/reject request |

The `AcpConfig` provider/model fields are optional at the plugin seam; the shipped profile supplies its route. `sessionListPageSize` defaults to 100. Validate the selected model / reasoning option before starting work, not midway through a prompt.

## MCP and permissions

MCP servers supplied by the ACP client are trusted process configuration: stdio commands/environment and HTTP URLs/headers can start processes or send credentials. Failed discovery rolls back the unpublished Agent. SSE MCP and ACP-transport MCP are outside this implementation.

The permission bridge offers one-time allow/reject choices. A client should reply based on the request rather than treating all tool calls as implicitly approved. Filesystem/network policy still belongs to the composed Harness services.

## Updates and lifecycle

Updates are richer than the older committed-text-only bridge, but they are not raw uncommitted provider token deltas. Tool activity and thoughts have explicit update paths. Resume restores runtime state without replaying the transcript; a client needing history must account for that distinction.

Closing one session releases its owned tree without deleting logs. Disconnect or plugin disposal drains the connection-owned sessions and resources. An idle boundary can include injected work and descendants, so it is not an exclusive causal response to one prompt.

## Boundaries and verification

No `session/load`, session deletion/fork, extra directories, ACP modes/commands/plans/terminals, client filesystem, or elicitation surface is advertised here. Consult current source before assuming an editor feature is implemented.

Use an ACP client to exercise initialize → new → prompt → updates → permission response → close, then list/resume the persisted root. A help command checks only the entry point, not a real model round trip.

Source owners: `packages/acp/acp/src/index.ts`, its request/session helpers, and `packages/bundle/acp-app/cordis.patch.yml`.

## Next steps

- [Subagents](../features/subagent.md): the ACP backend as a delegation provider

- [SDK](../guides/drive-harness-from-program.md): DSH-specific stdio protocol

- [Permissions](../user-guide/permissions.md)
