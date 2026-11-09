# Your First Session

- 
- Concepts Course
- Basics
- Your First Session
On this page

# Your First Session

**In one sentence**: a user message in DSH runs through the **session → turn → step** three-level lifecycle: the agent loop drives model inference + tool execution, and every step is recorded, rollback-able, and recoverable.

After [Quick start](../../getting-started/quickstart.md) you can already run it. Now follow what exactly happened with your first message.

## Contents

- [1. Lifecycle levels](#1-lifecycle-levels)
- [2. The journey of a message](#2-the-journey-of-a-message)
- [3. Source evidence (agent-loop)](#3-source-evidence-agent-loop)
- [4. Configuring an agent](#4-configuring-an-agent)
- [5. End to end: you send a message, what happens](#5-end-to-end-you-send-a-message-what-happens)
- [6. Observability (extension points)](#6-observability-extension-points)
- [7. Verification](#7-verification)
- [Next steps](#next-steps)

---

## 1. Lifecycle levels

```text
Session    persistence boundary, recoverable / forkable

  └── Turn    one user message + the agent's full response

        └── Step    one model call or one tool execution
```

In short: a **session** holds a long-running conversation; a **turn** goes from you sending one message to the agent finishing its reply; a **step** is every advance inside a turn (model inference or tool execution). The agent-loop README puts it verbatim: it "drives the session/turn/step lifecycle".

## 2. The journey of a message

- **Create/recover a session**: `ctx.agents.create({ sessionId })` or `resume({ resumeSessionId })`: resuming rebuilds history from the persisted log and the turn numbering continues

- **Setup transaction**: constructs the private session, agent, and scoped context: **protected by rollback**; a failure rolls back

- **Publish**: `session/created` → `agent/created` → `agent/session-start` announced in sequence

- **Drive the loop**: model inference → tool calls → result backfill → next round (see [Agent loop](../../learn/core/agent-loop.md))

- **Teardown**: stop and drain → revoke scope → detach agent → detach session

Key characteristics:

- **Creating and resuming belong to the same rollback-protected transaction**

- `sessionId` is globally unique; two concurrent operations can prepare simultaneously, and the final `enter()` arbitrates publication

- `resumeSessionId` and `sessionId` are **mutually exclusive**

- Declarative config treats `agents[].id` as a stable label, usually generating `${label}-session-<uuid>`

## 3. Source evidence (agent-loop)

```ts
// Config-driven creation: the loop fiber owns the agent

ctx.agentLoop.create(id, options, meta)

// Programmatic creation: returns an AgentHandle (the only teardown capability)

ctx.agents.create({ sessionId, agentOptions, setup, signal })

// Recover a persisted session: rebuild history from the log

ctx.agents.resume({ resumeSessionId, agentOptions, setup })
```

`signal` (AbortSignal) only applies to the creation/loading period, and detaches before the handle becomes visible; `resume` depends on a persistence backend and errors out clearly when there is none.

## 4. Configuring an agent

`agents` hangs under the `config` of the `agent-loop` plugin (**not a top-level section**):

```yaml
- id: agent-loop

  name: '@deepseek-ai/dsh-agent-loop'

  config:

    agents:

      - id: main

        provider: deepseek-official

        model: deepseek-v4-flash

        maxTokens: 65536

        cwd: /path/to/workspace

      - id: resume-demo

        resumeSessionId: <existing session id>
```

At the same level there is also `maxParallelToolCalls` (loop-level parallelism, default 10; 1 = serial).

## 5. End to end: you send a message, what happens

Suppose you ask "how many lines of code are in this repository":

The persisted record of all this (default zstd, two-level directories):

```sh
zstdcat ~/.dsh/sessions/*/*/session*.jsonl.zstd | tail -30
```

Note: the content is the **session log (surface)**; `agent/*` are **control-plane events** (state, errors, requests). See [Event system](../../learn/core/event-system.md) for both.

## 6. Observability (extension points)

Each request/response publishes a series of `agent/*` events (control plane); persistence truly lands on `session/event`:

- `agent/status`, `agent/created`, `agent/disposed`, `agent/request-error`, `agent/pre-step`

- Combined with `ctx.tools`/`session` events, you can attach policies, compaction, retries, and UI rendering

## 7. Verification

```sh
# After running one session, look at the session file (default zstd-compressed, two-level directories)

ls ~/.dsh/sessions/*/*/session*.jsonl.zstd

# Decompress and inspect the event stream (the 3-level structure at a glance)

zstdcat ~/.dsh/sessions/*/*/session*.jsonl.zstd \

  | jq -r 'select(.type | test("turn/|step/|user/message|assistant/message|tool/call|tool/result")) | [.seq, .type] | @tsv'
```

## Next steps

- [Agent loop](../../learn/core/agent-loop.md): how the loop is driven (the most core thing on the site)

- [Boot and configuration](../../learn/core/boot-config.md): how the process is assembled

- [Architecture overview](../../learn/intro/architecture.md): how this whole thing is put together
