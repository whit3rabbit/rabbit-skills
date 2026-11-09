# The Workspace File Service

- 
- Concepts Course
- Core Mechanisms
- The Workspace File Service
On this page

# The Workspace File Service

Audit baseline 0.1.5-alpha.1 @ 5dda764ed3; see [source/npm channels](../../guides/deepseek-harness-status.md).

**One-liner**: `packages/api/workspace-files` turns "the files inside one session's workspace" into a typed Remote namespace, **`workspaceFiles`**: paged UTF-8 text reads, raw byte windows, `stat`, directory listing, and a stream of the **agent's own writes**; the same package's browser half wraps it as the `file` resource protocol, which the right Sidebar's file tree and text preview both consume.

This package is new in `0.1.5-alpha.1`. After reading it you can answer: how file content crosses the wire, why it cannot lean on the sandbox, which four gates the host applies, and how the browser turns one address into live metadata.

## Contents

- [1. Boundary: it sends content across the wire, not a path to the local opener](#1-boundary-it-sends-content-across-the-wire-not-a-path-to-the-local-opener)
- [2. The host / client halves](#2-the-host-client-halves)
- [3. The five host methods](#3-the-five-host-methods)
- [4. The four gates and the error codes](#4-the-four-gates-and-the-error-codes)
- [5. Configuration](#5-configuration)
- [6. The change feed: fs/observed → changes](#6-the-change-feed-fsobserved-changes)
- [7. The client half: the file resource protocol](#7-the-client-half-the-file-resource-protocol)
- [8. Source evidence](#8-source-evidence)
- [9. Verification](#9-verification)
- [Next steps](#next-steps)

---

## 1. Boundary: it sends content across the wire, not a path to the local opener

The header comment in `src/index.ts` is explicit: this service is **not** modelled on `session.openWorkspacePath`. That endpoint hands a path to the local opener and leaves the effect on the machine; this one sends **file content across the wire**, a different level of exposure.

More importantly, **reads through `ctx.fs` are deliberately unconfined**. The sandboxing backend fences writes and edits only (the `workspace-write` policy says files under the session workspace *may* be modified), so the service has to carry every constraint itself — which is what the four gates in section 4 are.

## 2. The host / client halves

One package, two compilation faces:

| Face | Entry | tsconfig | Export subpaths | Role |
| --- | --- | --- | --- | --- |
| Host | src/index.ts | tsconfig.host.json (files: index.ts / types.ts / changes.ts) | ., ./types, ./typert | the WorkspaceFiles service and the workspaceFiles Remote namespace |
| Client | src/client/index.ts | tsconfig.client.json (files: src/client/* plus src/types.ts) | ./client, ./remote | the file resource provider |

`package.json#dsh.client` declares `platform: "web"` and `inject: ["@deepseek-ai/dsh-api-gateway", "@deepseek-ai/dsh-api-session-controller", "@deepseek-ai/dsh-client-resources"]`; Typert generates the `./typert` (host) and `./remote` (client) artifacts. In the web composition it mounts as the `workspace-files` row right after `session-controller` (`packages/bundle/web-app/cordis.patch.yml`).

## 3. The five host methods

Every method takes the **session identity** on the wire first, which resolves the target agent — so a caller never names a root itself.

| Method | Arguments | Returns | Semantics |
| --- | --- | --- | --- |
| read(agent, path, range, signal) | range { offset?, limit? }, 1-based lines | WorkspaceFileText = stat + { offset, text, lines, eof } | paged text read; a page over the byte cap is refused, not shortened |
| readBytes(agent, path, range, signal) | range { offset?, length? }, 0-based bytes | WorkspaceFileBytes = stat + { offset, data(base64), eof } | raw bytes; nothing is decoded and nothing is refused as binary |
| stat(agent, path, signal) | — | WorkspaceFileStat { absolutePath, version, bytes? } | identity, version, and size without content |
| list(agent, path, signal) | — | WorkspaceDirectoryListing { path, entries, truncated } | direct children; the rest is dropped and reported cut |
| changes(agent, signal) | — | AsyncIterable (@Remote({ mode: 'stream' })) | agent observations only |

**Two path vocabularies, and each method uses exactly one** — the module comment in `src/types.ts` exists for this:

- `read` / `readBytes` / `stat` / `changes` report **`absolutePath`**: the absolute path in the execution world with symlinks resolved, because their consumer is the client resource system, whose addresses carry that same path.

- `list` reports a **workspace path**: relative to the workspace root, empty for the root, because its consumer is a tree rooted there; a child's path is that value joined with the entry name by `/`.

Page semantics: `text` joins its lines with `\n` and carries no terminator after the last; `lines` counts the page's lines (`0` when `offset` lies past the last line); `eof` says whether the page includes the file's last line. An empty page and a page holding one empty line are told apart by `lines` — which is exactly why `lines` travels separately.

## 4. The four gates and the error codes

Every read, stat, and listing passes four gates in order:

| # | Gate | Implementation | Failure code |
| --- | --- | --- | --- |
| 1 | the path's own type, before anything follows it | ctx.fs.lstat(path, { cwd: workspaceRoot }) | not-found / not-regular-file / not-directory |
| 2 | containment | ctx.fs.contains(root, target) — never a string-prefix comparison | outside-workspace |
| 3 | caps | Config's maxBytes / maxLines / maxEntries | too-large / gateway/bad-request |
| 4 | text | streamText decoding chunk by chunk plus a NUL scan of the page | not-text |

Gate 1 precedes containment on purpose: `lstat` is path-shaped and sees the link itself, while `resolve` follows it. The price is that an entry outside the workspace whose type already disqualifies it reports `not-regular-file` / `not-directory` rather than `outside-workspace`. Gate 2 must use `contains` rather than a prefix test because `resolve` realpaths — a prefix test cannot see a symlink that leaves the root.

The complete error map (`RemoteErrorDetailsMap` in `src/types.ts`):

| Code | Raised when | Details |
| --- | --- | --- |
| workspace-file/not-found | no entry at that path inside the workspace | path |
| workspace-file/outside-workspace | the path resolves outside the session's workspace root | path |
| workspace-file/too-large | a page or window exceeds the byte cap; nothing is returned | path, limit |
| workspace-file/not-text | not decodable UTF-8, or the page carries NUL bytes | path |
| workspace-file/not-regular-file | not a regular file | path, kind (directory / symlink / other) |
| workspace-file/not-directory | not a directory | path, kind (file / symlink / other) |

The workspace root comes from the policy, not from the filesystem backend's own cwd default:

```ts
this.ctx.sandboxPolicy.resolve({ session: agent.session }).workspaceRoot
```

The source comment gives the reason: the `minimal` preset shadows the host provider with a bare `fs-local` whose cwd differs, so resolving explicitly makes the answer the same whichever instance answers.

## 5. Configuration

| Key | Default | Meaning |
| --- | --- | --- |
| maxBytes | 2097152 (2 MiB) | inclusive byte cap on one page's text and on one byte window; a larger page or window is refused, never silently shortened (a silently cut page reads as the whole page) |
| maxLines | 5000 | default and largest page size in lines; a larger limit is refused |
| maxEntries | 2000 | cap on returned directory entries; the rest is dropped and truncated is set |

The file itself has **no size cap** — the caller pages through it. Pages are cut from `streamText`: lines before the page are counted and not kept, each in-window segment passes the byte gate before buffering, and the cutter returns at the first character past the page, so neither a huge file nor one giant line holds more than a page in memory.

## 6. The change feed: fs/observed → changes

| Frame | When |
| --- | --- |
| { kind: 'ready' } | the host observation queue is active and the workspace root is resolved; observations queued during that resolution follow as change frames |
| { kind: 'change', change } | { absolutePath, version } for an observed write, or { absolutePath, absent: true } for one observed gone |

Frames report **observations, not deltas**: a consumer already holding that `version` learns nothing new and can ignore the frame.

Two limits you must know (source comment and README agree):

- **Agent writes only**: the source is the `fs/observed` a tool emits after its own filesystem operation. A file changed by a subprocess, a shell command, or the user's editor produces **no** frame. The operating system is not watched.

- **Unbounded queue**: a generation buffers every contained observation until its consumer pulls; a stalled consumer grows host memory for the life of the stream.

## 7. The client half: the file resource protocol

The browser half does one thing — it wraps `workspaceFiles` as the resource model's `file` protocol:

| Item | Value |
| --- | --- |
| Registration | ctx.resources.register(provider), inject = ['resources', 'remote', 'remote.workspaceFiles', 'sessions'] |
| Address | dsh-resource://file/session//

 or dsh-resource://file/absolute/ |
| Value (metadata only) | { absolutePath, version, bytes?, changed } |
| Content | fetched separately, page by page: remote.workspaceFiles.read(sessionId, path, { offset }, signal) |
| Client-only errors | workspace-file/unsupported-address, workspace-file/unknown-workspace (the host never emits either) |

Addresses are built and parsed by `fileAddressFor` / `parseFileAddress` from `@deepseek-ai/dsh-util-workspace-path`; this package never splits the string itself.

The provider's open order: wait for the host's `ready` frame → first `stat` → queue changes during the read → bind the follower to `stat.absolutePath`. A new write version raises `changed` while retaining the last byte size; duplicate versions are ignored; an `absent` notice or a reload re-stats. One session has exactly **one** supervised `changes` stream, fanned out by absolute path to every followed file in that session (backslashes normalized to slashes); the last follower leaving disposes the stream.

## 8. Source evidence

| Location | Symbol / fact |
| --- | --- |
| packages/api/workspace-files/src/index.ts | WorkspaceFiles, Config, cutPage, inspect, confine, locateFile, workspaceRootOf, isNotTextRefusal |
| packages/api/workspace-files/src/changes.ts | WorkspaceChangeFeed, ChangeFollower, Observed |
| packages/api/workspace-files/src/types.ts | WorkspaceFileStat, WorkspaceFileRange, WorkspaceFileText, WorkspaceByteRange, WorkspaceFileBytes, WorkspaceDirectoryEntry, WorkspaceDirectoryListing, WorkspaceFileChange, WorkspaceFileWatchFrame, the six RemoteErrorDetailsMap codes |
| packages/api/workspace-files/src/client/index.ts | inject, apply, ChangeFeed wiring |
| packages/api/workspace-files/src/client/provider.ts | createFileResourceProvider, SessionLookup, metadataOf |
| packages/api/workspace-files/src/client/change-feed.ts | ChangeFeed, Follower, SessionFeed, editOf |
| packages/api/workspace-files/src/client/types.ts | ResourceProtocolMap.file, WorkspaceFileResource, WorkspaceFileParams, the two client error codes |
| packages/fs/fs/src/index.ts | lstat, resolve, contains, streamText, readByteRange, listDir, processPath, fileUrl |
| packages/sandbox/sandbox-policy/src/index.ts | resolve(...).workspaceRoot (session cwd → workspace root) |
| packages/bundle/web-app/cordis.patch.yml | the workspace-files row (right after session-controller) |

## 9. Verification

```sh
# 1. Mount: the web composition should carry a workspace-files row, grouped with the resource model

dsh web --dump-config | grep -iE "workspace-files|client-resources|ui-sidebar"

# 2. The caps and the four gates all live in these two files

grep -n "maxBytes\|maxLines\|maxEntries\|workspace-file/" \

  packages/api/workspace-files/src/index.ts packages/api/workspace-files/src/types.ts

# 3. In the browser: open a session's right Sidebar → Files tab → click a text file.

#    DevTools Network should show POST /api calls for workspaceFiles.stat / read,

#    plus the workspaceFiles.changes stream on /api/remote.mux.
```

A reproducible boundary observation: have the agent rewrite the file currently on screen; `changed` rises but the page text is **not** replaced — content is read by the viewer itself, and the metadata stream only says "it changed".

## Next steps

- [Sandbox & Security](../../learn/core/sandbox-security.md): why reads are outside the sandbox fence and the gates are the service's own

- [Remote API Gateway](../../learn/core/remote-api-gateway.md): how the `workspaceFiles` namespace crosses the gateway

- [Client Resources & Modules](../../learn/core/client-resources.md): the resource model behind the `file` protocol

- [Web UI Architecture](../../learn/core/web-ui.md): where the file tree and text preview mount
