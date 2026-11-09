# Listen to Events

- 
- Concepts Course
- Plugin Development
- Listen to Events
On this page

# Listen to Events

**In one sentence**: `ctx.on(event, handler)` lets a plugin hook into the session/tool/agent lifecycle: the most common ones are the tool pipeline (`tools/pre-execute` gate, `tools/post-execute` rewrite). This is the entry point for the vast majority of "behavior extensions".

## Contents

- [1. Listening basics](#1-listening-basics)
- [2. Event hook patterns](#2-event-hook-patterns)
- [3. Five dispatch modes](#3-five-dispatch-modes)
- [4. The observable event catalog (excerpt)](#4-the-observable-event-catalog-excerpt)
- [5. Dual event planes (don't mix them up)](#5-dual-event-planes-dont-mix-them-up)
- [6. In practice: a "policy gate" plugin](#6-in-practice-a-policy-gate-plugin)
- [7. Verification](#7-verification)
- [Next steps](#next-steps)

---

## 1. Listening basics

```ts
import { Context } from '@deepseek-ai/cordis'

export const name = 'event-watcher'

export function apply(ctx: Context) {

  // session lifecycle

  ctx.on('session/created', (session) => {

    console.log('New session:', session.id)

  })

  // tool gate (can veto): signature (execution, next), returns a PreToolDecision

  ctx.on('tools/pre-execute', async (execution, next) => {

    if (execution.name === 'forbidden_tool') {

      return { kind: 'deny', reason: 'This tool is forbidden by policy' }

    }

    return next()   // allow through to subsequent listeners

  })

  // tool result rewrite

  ctx.on('tools/post-execute', async (execution, result, next) => {

    const decision = await next()

    // inspect the result, attach extra information, or change the decision

    return decision

  })

}
```

## 2. Event hook patterns

| Pattern | Purpose | Example |
| --- | --- | --- |
| Listen/notify | observe only | ctx.on('agent/error', ...) logging |
| Gate | intercept/allow | tools/pre-execute returns deny |
| Around | wrap a layer | tools/execute adds timeout/metrics |
| Rewrite | change the result | tools/post-execute appends context |

## 3. Five dispatch modes

| Mode | Semantics | Typical |
| --- | --- | --- |
| emit | sync trigger, no wait | agent/error |
| parallel | async in parallel, await all | session/flush |
| serial | serial in sequence | some agent/* |
| bail | stops at the first bail |  |
| waterfall | chained into a next() chain | tools/pre-execute, agent/request |

**waterfall must call `next()`**: skipping it short-circuits the whole chain. On the publish side use `ctx.emit()`/`ctx.parallel()`/`ctx.waterfall()`.

## 4. The observable event catalog (excerpt)

| Domain | Events |
| --- | --- |
| agent lifecycle | agent/created /disposed /status /session-start; waterfall's /pre-step /request /request-error; /turn-stopping, agent/inbox/* |
| session | session/created /disposed /event /flush |
| tool pipeline | tools/pre-execute execute post-execute (waterfall), tools/code-dispatch-log, tools/result (emit) |
| cross-domain | fs/edit-intent fs/write-intent, llm/stream, approval/request, goal/changed, settings/document-updated, credentials/reference-updated, commands/change |

The full matrix is in `$SRC/docs/event-producer-consumer.md` (including each event's dispatch mode).

## 5. Dual event planes (don't mix them up)

|  | Plane A: Cordis in-process | Plane B: SessionEvent persisted log |
| --- | --- | --- |
| When to use | transient signals, plugin communication | facts that need to be persisted/recoverable |
| Publish | ctx.emit('my/event', ...) | session.append('my/thing-happened', {...}) |
| Subscribe | ctx.on('my/event', handler) | only observable via session/event |

`tools/result` (host in-process notification) ≠ `tool/result` (session log event).

**Custom persisted events must first be declared** (augment into `SessionEventMap`), otherwise `session.append` rejects unknown types:

```ts
declare module '@deepseek-ai/dsh-session/types' {

  interface SessionEventMap {

    'my-plugin/thing-happened': { type: 'my-plugin/thing-happened'; detail: number }

  }

}
```

Downstream listening goes through `session/event`, and you **cannot** directly `ctx.on('my-plugin/thing-happened')`:

```ts
ctx.on('session/event', (session, event) => {

  if (event.type === 'my-plugin/thing-happened') {

    console.log('thing:', event.detail)

  }

})
```

## 6. In practice: a "policy gate" plugin

Scenario: an environment forbids the model from calling `web_fetch`, but allows `web_search`.

```ts
export function apply(ctx: Context) {

  ctx.on('tools/pre-execute', async (execution, next) => {

    if (execution.name === 'web_fetch') {

      return { kind: 'deny', reason: 'This environment\'s policy forbids web_fetch' }

    }

    return next()

  })

}
```

The `packages/guard` package is **not** this gate: it is a **loop-hygiene guard family** (repeat-tool-reminder / timeout-policy), with a different responsibility. allow/deny/ask is implemented through the `PreToolDecision` of `tools/pre-execute`.

## 7. Verification

```sh
# All event streams are in the session JSONL (default zstd, two-level directories)

zstdcat ~/.dsh/sessions/*/*/session*.jsonl.zstd | jq -r '.type' | sort | uniq -c
```

## Next steps

- [Configuration and publishing](../../learn/dev/config-publish.md): make plugins configurable and distributable

- [Event system](../../learn/core/event-system.md): event vocabulary and expansion surface
