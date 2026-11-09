# Building an Assistant with MCP + Sub Agents

End-to-end walkthrough: combine DSH's MCP integration with sub Agents to build an assistant that "can query external data and work in parallel". Mechanics are on the corresponding pages; here we just do it.

## Contents

- [1. Goal](#1-goal)
- [2. Connect an MCP Server](#2-connect-an-mcp-server)
- [3. How Tools Are Discovered and Named](#3-how-tools-are-discovered-and-named)
- [4. Configure a Resident Sub Agent](#4-configure-a-resident-sub-agent)
- [5. Dispatch Tasks and Get Reports](#5-dispatch-tasks-and-get-reports)
- [6. Combining: One Entry Point](#6-combining-one-entry-point)
- [7. Troubleshooting Common Failures](#7-troubleshooting-common-failures)
- [8. Verification and Permissions](#8-verification-and-permissions)
- [Summary](#summary)

---

## 1. Goal

What we're building:

```text
an assistant that can "query GitHub / databases" (via MCP)

  + a resident sub Agent that can "receive follow-up messages and keep researching" (via subagent)

  + an entry point that ties these together
```

## 2. Connect an MCP Server

See [MCP Integration](../features/mcp.md). Mount the MCP client into the profile:

```sh
# in your profile directory, add a github MCP server via a patch
```

`~/.dsh/profiles/web/cordis.patch.yml`:

```yaml
- insert:

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

Restart `dsh web`. Now the model can call the `mcp__github__*` tools (GitHub data).

If `@deepseek-ai/dsh-mcp-client` is in the core, mount it directly; otherwise first run `dsh plugin --profile web add`. One instance per server.

An HTTP-type server uses the `streamable-http` transport (remote/local HTTP endpoints):

```yaml
- insert:

    - id: mcp-web

      name: '@deepseek-ai/dsh-mcp-client'

      config:

        serverName: web

        transport: streamable-http

        url: http://localhost:3000/mcp

        headers:

          Authorization: !!js '`Bearer ${process.env.MCP_TOKEN}`'
```

Key fields for both transports:

| Field | Transport | Explanation |
| --- | --- | --- |
| transport | both | stdio (subprocess) or streamable-http (HTTP endpoint), required |
| serverName | both | tool namespace, [A-Za-z0-9_-]{1,32}, unique across instances |
| command / args / env / cwd | stdio | command, args, environment, working directory to spawn the subprocess |
| url / headers | http | server address and extra headers (e.g. auth tokens) |
| toolCallTimeoutMs | both | single callTool timeout, default 60000 |
| failOnStartupError | both | whether initial connect/sync failure makes the plugin activation fail, default false |
| reconnect.* | both | dropped-connection reconnect: exponential backoff (starting 500ms doubled, cap 30000ms), gives up after maxAttempts (default 10) |

## 3. How Tools Are Discovered and Named

At startup the mcp-client waits for `listTools()`, then registers each tool with `ctx.tools.register()` as `mcp__<serverName>__<rawName>` — the same naming as Claude Code / Codex. Key points:

- **Namespace isolation**: two servers each publishing a `search` don't collide; they hang under `mcp__github__search`, `mcp__web__search` respectively.

- **Duplicate `serverName` conflict**: if the same `serverName` appears twice, the later-loaded instance fails to load.

- **Hot-update sync**: when a server sends `notifications/tools/list_changed` it auto re-syncs; after a successful reconnect it also re-discovers, and the restored generation of tools replaces the previous one — no duplicates and no leaks.

- **Name normalization**: public names are limited to 64 chars, `[A-Za-z0-9_-]`; when replaced/truncated, a 12-hex-char hash (a deterministic function of `serverName`, `rawName`) is appended, so different tools won't collapse to the same name.

After changing a patch, HMR hot-switches: disconnect + reconnect; if `serverName` is unchanged, tool names stay unchanged.

## 4. Configure a Resident Sub Agent

See [Sub Agents](../features/subagent.md). We create a continuable child session so it can keep consuming messages and researching:

```text
Use subagent startContinuable to create a resident "research assistant",

label: research-assistant,

initialPrompt: You are a resident research assistant; accept my tasks at any time, and use the MCP git tools to query data.
```

Afterwards, feed new tasks any time with `followup(childId, 'check this repo's issues again')`. The sub Agent has its own scope and its own header, and does not pollute the main session.

## 5. Dispatch Tasks and Get Reports

A resident sub Agent is a three-phase "create, then feed, then collect":

- **Create**: `subagent startContinuable` returns `{ childId, messageId }`; the prompt is already in the child session's inbox, and it doesn't wait to start running.

- **Feed**: send follow-ups with `send_message` (the model-side tool) or `followup(childId, ...)` (the service API); each message becomes the sub Agent's **next FIFO turn**; while it is still running, messages queue until the current turn ends and cannot change the in-flight turn.

- **Report**: the sub Agent can use its child-session-specific `report` tool to return conclusions to the parent Agent (framed as `Background subagent <child-id> reported:`); even if it doesn't call `report`, on settle the parent session receives a `Background subagent <child-id> finished...` notice carrying the stop reason and last message, so results aren't silently lost.

- **View/stop**: `list_agents` lists resident sub Agents (with `running`/`idle`/`ready` states); `interrupt_agent` stops only the current turn, doesn't clear already-queued messages, and doesn't destroy the child session.

Sub Agents are independent sessions with independent scope; a `spawn` child session by default **cannot see the parent session's history**, so provide full context when dispatching rather than expecting it to remember prior context.

## 6. Combining: One Entry Point

Turn "ask one thing → sub agent queries/researches in parallel → aggregate" into a single call:

```text
Use research-assistant to find: among the recent 3 issues, which ones are related to build?

Query everything mcp__github__ can query, and give me a list with links.
```

The main agent hands the task to the sub Agent; the sub Agent calls MCP tools to query GitHub and reports the list back.

## 7. Troubleshooting Common Failures

| Symptom | Cause and Handling |
| --- | --- |
| No tools appear at all | Default failOnStartupError: false, so on an initial connect failure the plugin activates but carries no tools; check the startup log, and if needed set it to true to make the failure explicit |
| Tools still there after disconnect but calls keep failing | Reconnect uses exponential backoff; when maxAttempts (default 10) is exhausted, all of that server's tools are unregistered — needs an HMR reload or a Host restart |
| Duplicate serverName error | The later-loaded instance fails to load; give every instance a unique serverName |
| Tool name preempted by external registration | The whole generation rolls back (doesn't register only half), and the log reports the conflict |
| send_message sent with no reply | It only returns an "already queued" confirmation, not the sub Agent's reply; see the sub Agent's own transcript, or have the sub Agent report via report |
| interrupt_agent reports not authorized | Only an ancestor (including across generations) of the target sub Agent can stop it; self/sibling/expired calls are all rejected |
| HTTP server won't connect | streamable-http failures retry per request and don't trigger a supervisor restart; confirm the URL/headers are correct |
| report not received | Requires the parent Agent to still be a "live direct parent session"; if the parent has settled/unmounted, the report has no owner |

For the fuller field and behavior reference see [MCP Integration](../features/mcp.md) and [Sub Agents](../features/subagent.md).

## 8. Verification and Permissions

```sh
dsh web --dump-config | grep -E "mcp|subagent"   # check whether MCP + subagent are mounted

# look at mcp tool calls in the session

zstdcat ~/.dsh/sessions/*/*/session*.jsonl.zstd | grep -oE 'mcp__[a-z_]+' | sort -u
```

Sub Agents have their own scope; to restrict which tools one uses, pass `toolFilter` in `start`/`startContinuable`.

## Summary

You now have a workbench: external data (MCP) + parallel research (sub Agents). Add [Skills](../features/skills.md) to harden common flows, or automate with [Workflows](../features/workflow.md), and it can serve as a stable assistant.

To see the full mechanics: MCP → [MCP Integration](../features/mcp.md); sub Agent → [Sub Agents](../features/subagent.md); worker orchestration → [Workflows](../features/workflow.md).
