# Remote API gateway

- 
- Concepts Course
- Core Mechanisms
- Remote API gateway
On this page

# Remote API gateway

Audit baseline 0.1.5-alpha.1 @ 5dda764ed3; see [source/npm channels](../../guides/deepseek-harness-status.md).

**In short**: `Connection` owns transport and browser authentication; `typertGateway` validates and dispatches typed Remote calls/streams; domain controllers own business policy. The legacy API Proxy is removed in source.

These interfaces describe the source build. See [source vs npm](../../guides/deepseek-harness-status.md) before using them with an installed release.

## 1. Request and stream paths

- `packages/client/connection` owns the single `/api` fetch handler and exact HTTP route registration. POST carries unary RPC; explicit GET/HEAD routes serve surfaces such as downloads.

- `packages/api/gateway` owns the `/api/remote.mux` WebSocket carrier, multiplexing logical streams. Its heartbeat interval `websocketHeartbeatIntervalMs` defaults to **2 seconds** (changed from 30 seconds in 0.1.2), and that interval is also the Pong deadline — a peer that does not answer before the next tick is terminated by the Host.

- An unclaimed endpoint returns 404; there is no legacy API Proxy fallback.

- Session history/control streams and forwarded Host events are different contracts. Do not treat the persistent `session/event` log as a raw browser token stream.

- `packages/api/session-controller` additionally mounts `GET|HEAD /api/file?path=<absolute path>` (`SessionMediaReferences`) on the authenticated `connection.fetch` channel, reading ordinary files (including temporary paths outside registered workspaces) with no directory or MIME-category restriction.

## 2. Host Remote invocation

`ctx.typertGateway.invoke()` and `.stream()` consume generated descriptors. The gateway checks named arguments, resolves receiver / lookup identities, validates service binding, and applies codecs at the boundary. Cancellation is descriptor metadata: the Host receives an `AbortSignal`, rather than trusting a wire-supplied signal.

| Layer | Owner |
| --- | --- |
| @Remote, @RemoteScope, TypertRemoteService | packages/typert/protocol |
| Descriptor validation and invocation | packages/api/gateway/src/index.ts |
| Client method installation | packages/api/gateway/src/client/index.ts |
| Business errors and session ownership policy | Respective domain controllers |

Plugin authors should use generated Remote contracts and their client-safe types, rather than copying the removed API Proxy schemas. `@RemoteScope` selects a scoped receiver through a registered Host context provider; it does not itself define session admission policy.

## 3. Domain controllers replace the monolithic proxy

| Package | Responsibility |
| --- | --- |
| api/session-controller | Session listing/history, model selection, prompt/queue/cancel, live control and follow streams, file references and /api/file media reads |
| api/settings-controller | Settings operations and client-safe contracts |
| api/workspace-controller | Workspace operations and directory-picker integration |
| api/workspace-files | Paginated reads, byte windows, stat, directory listing, and the Agent-write change feed inside a session workspace (new in 0.1.5) |
| api/remotes | Application-selected Remote contributions and forwarded-event assembly |

Session Agent resolution lives in `packages/api/session-controller/src/agent.ts` and owns live reuse, cold restoration, concurrent-resume deduplication, and subagent ownership fences. Read-only cold history and an explicit command that resumes an Agent remain distinct paths: `list` reads only stored headers and projection-cache rows — it never stats per session or opens a cold Session body.

The only remaining session knob is `nativeOpen` (platform-detected: whether workspace paths can be handed to a native desktop opener). Export policy belongs to the Session-log export owner, not a restored all-purpose gateway config.

## 4. Client service and contributions

`ctx.remote` mounts generated contributions through `$mount()`, subscribes to selected Host events with `$on()`, opens logical streams with `$stream()`, and reads fixed Host facts through `$host`; decoded frames are delivered inside the carrier, and `ctx.remote` has **no** `$dispatch`. Contribution lifetime controls mounted methods and in-flight work.

At this baseline, `packages/api/remotes/src/client/index.ts` explicitly mounts **14** contributions:

```text
agentPresetsRemote · commandsRemote · settingsControllerRemote

goalsRemote · llmRemote · dynamicRemote · pluginInventoryRemote

messageFeedbackRemote · fileUploadsRemote · sessionReferencesRemote

subagentsRemote · sessionRemote · workspaceRemote · workspaceFilesRemote
```

The browser imports the application facade and client-safe types. It does not discover arbitrary active Host services at runtime. Event selection remains declared in `packages/api/remotes/src/remote-events.ts`; a forwarded event is not automatically a replayable Session subscription.

## 5. Authentication is separate from Host trust

The CLI prints a launch URL containing `?token=...`. Only `GET /` exchanges it for an authority-bound browser session cookie and redirects to the clean root. RPC and WebSocket requests then authenticate with the cookie, including loopback requests.

`trustedHosts` permits Host authorities; it is not a credential. Missing/invalid browser sessions produce 401, while Host/Origin failures produce 403. Public static assets do not grant API access. Current startup rejects `--host 0.0.0.0`; use an SSH tunnel and the printed launch URL for remote work.

## Verify

```sh
# Use the matching source build.

pnpm dsh web --dump-config | grep -iE "connection|api-gateway|api-remotes|controller"
```

In browser developer tools, check authenticated POST requests to `/api` and the `/api/remote.mux` connection. A bare curl without the browser cookie returning 401 is expected, not proof that RPC is broken.

## Next steps

- [Web UI architecture](../../learn/core/web-ui.md)

- [Plugin inventory](../../features/plugin-inventory.md)

- [Event system](../../learn/core/event-system.md)

- [Plugin anatomy](../../learn/core/plugin-anatomy.md)
