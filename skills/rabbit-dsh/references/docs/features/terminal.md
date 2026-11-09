# Interactive Terminal Model Workflow

**In one sentence:** `terminal` is six model-facing persistent terminal tools (`terminal_open` / `terminal_send` / `terminal_read` / `terminal_signal` / `terminal_close` / `terminal_list`) that expose an owner-isolated interactive shell/REPL on top of DSH's `ctx.terminals` seam — foreground sends wait on your prompt, background sends hand you a job id through `ctx.jobs`, and a real process-group signal interrupts it.

The [subprocess page](../features/subprocess.md) section 7 explains how DSH allocates a PTY and how the `ctx.terminals` service seam routes to the `terminal-bash` backend. This page stands on the **model side**: what the six tools actually look like to a model, and how to choreograph one complete interactive session.

## Contents

- [1. Positioning: the model presentation of the mechanism layer](#1-positioning-the-model-presentation-of-the-mechanism-layer)
- [2. The six tools, unpacked](#2-the-six-tools-unpacked)
- [3. Core usage conventions](#3-core-usage-conventions)
- [4. One complete interactive session](#4-one-complete-interactive-session)
- [5. The division of labor with the subprocess page](#5-the-division-of-labor-with-the-subprocess-page)
- [Next steps](#next-steps)

---

## 1. Positioning: the model presentation of the mechanism layer

When you mount the `terminal` row, the `packages/terminal/tool-terminal` package maps that managed-terminal machinery into **six model-visible tools**. The layering is clear:

| Layer | Package / ctx | What it owns | Covered here |
| --- | --- | --- | --- |
| Terminal machinery | terminal | ctx.terminals seam: opaque session ids, owner gating, routing by backend name, waiting for quiescence on dispose | Background |
| Backend | terminal-bash | a persistent shell over ctx.subprocess.spawnTerminal (type: shell) | Background |
| Model tools | tool-terminal (on top of ctx.terminals) | the six tool schemas, owner auth, the result cap, the system prompt, and backgrounding via ctx.jobs | This page |

`tool-terminal` injects only three services — `['terminals', 'tools', 'systemPrompt']` — it does not touch `node-pty`, the sandbox, or task scheduling; it only exposes machinery as a model workflow.

## 2. The six tools, unpacked

Below is the full lifecycle from `terminal_open` to `terminal_close`. Every parameter and return value comes from the schemas in `packages/terminal/tool-terminal/src/index.ts`.

### 1. terminal_open — create a session

```text
terminal_open(type?, name?, cwd?) → { sessionId, name?, type, pid?, status, motd }
```

- `type` (required): a registered terminal backend type, usually `"shell"`.

- `name` (optional): an owner-local display name such as `"main"` or `"gdb"`.

- `cwd` (optional): the initial working directory; defaults to the deployment workspace root.

- Returns a session snapshot with `motd` — a hint about what the session is for.

Source `execute` (`packages/terminal/tool-terminal/src/index.ts`):

```ts
const result = await ctx.terminals.spawn(requireAgent(exec.agent), {

  type: args.type,

  ...args.name !== undefined ? { name: args.name } : {},

  ...args.cwd !== undefined ? { cwd: args.cwd } : {},

}, exec.signal)

return result
```

### 2. terminal_send — write input (foreground / background)

```text
terminal_send(sessionId, text, submit?, run_in_background?) →

  foreground: { kind:'foreground', viewport, waitReason, sessionStatus, truncated }

  background: { kind:'background', jobId }
```

- `submit` defaults to `true` (sends Enter); set `false` for control characters or incomplete REPL input.

- A foreground send by default **waits** — until one of four things happens, and `waitReason` tells you exactly which:

| waitReason | Meaning |
| --- | --- |
| stdin_read | the program read more input again (it wants further input) |
| inferred_idle | an idle inference — output is considered done for now |
| timeout | the wait timed out |
| session_exit | this session has exited |

⚠️ Per the system prompt, verbatim: **an `inferred_idle` or `timeout` result does not prove the foreground command exited** — silence ≠ finished, timeout ≠ exited. Check `sessionStatus` to confirm.

- **Background mode** (`run_in_background: true`) does not block the model: preflight and this session's exclusive in-flight-send reservation both complete before the job id is returned, then it hands you `{ kind:'background', jobId }` into the generic `ctx.jobs` registry. Collect with `job_output`, stop with `job_kill` — and for a `pty-send` job, `job_kill` forwards a **real `SIGINT` to the current foreground process group**.

Source background branch (`packages/terminal/tool-terminal/src/index.ts`):

```ts
const jobId = jobs.start({

  kind: 'pty-send',

  label: `${id}: ${args.text || '(input)'}`,

  owner,

  outputLimitBytes: maxResultBytes,

  run: () => {

    const operation = ctx.terminals.startSend(owner, id, request)

    return {

      cancel: () => { cancelRequested = true; operation.cancel() },

      done: operation.done.then(

        result => ({ status: cancelRequested ? 'killed' : 'completed', detail: sendDetail(result) }),

        (error) => ({ status: 'failed', detail: String(error) }),

      ),

      readOutput: () => renderSendRead(operation.readOutput()),

    }

  },

})

return { kind: 'background', jobId }
```

`kind: 'pty-send'` is this package's declaration on `@deepseek-ai/dsh-jobs`'s `JobKindMap`:

```ts
declare module '@deepseek-ai/dsh-jobs' {

  interface JobKindMap { 'pty-send': 'pty-send' }

}
```

Foreground sends render with the terminal call/result card; background sends use the generic execution card.

### 3. terminal_read — a bounded page, no input

```text
terminal_read(sessionId, offset?, count?) → { text, totalLines, lineBegin, lineEnd, truncated }
```

- `offset` defaults to `0` (newest-relative); `count` defaults to `500` (backend caps apply).

- Returns a page of retained output with pagination markers, sending no input: use it to review earlier output without disturbing a program that is waiting on stdin.

- `truncated` means this page was cut; combine it with `lineBegin`/`lineEnd`/`totalLines` to decide whether to page further back.

### 4. terminal_signal — deliver a signal

```text
terminal_signal(sessionId, signal) → { delivered:true, targetPgid }
```

- `signal` is an enum: `SIGINT` / `SIGTERM` / `SIGKILL` / `SIGTSTP` / `SIGHUP`, delivered to the current foreground process group (`targetPgid`).

- **Shell-targeted `SIGKILL` is rejected** — to tear everything down use `terminal_close`; do not `SIGKILL` the shell process itself.

### 5. terminal_close — close and wait for the process tree to vanish

```text
terminal_close(sessionId) → { sessionId, outcome:'closed'|'already-closing' }
```

- Closes one persistent session and **waits until its captured owned process tree is fully gone** before returning.

- `outcome: 'closed'` means you closed it this time; `'already-closing'` means it was already shutting down — an idempotent acknowledgement.

Source `execute`:

```ts
const closed = await ctx.terminals.kill(requireAgent(exec.agent), id)

return { sessionId: id, outcome: closed ? 'closed' : 'already-closing' }
```

### 6. terminal_list — inventory the current agent's sessions

```text
terminal_list() → [ { sessionId, name?, type, pid?, status } ... ]
```

- Lists fresh snapshots of the **persistent sessions owned by the current initiating agent**, one snapshot per session.

### Tool quick-reference

| Tool | Purpose | Key returns |
| --- | --- | --- |
| terminal_open | create a persistent session | sessionId + motd |
| terminal_send | write input; foreground waits, background gives a job id | waitReason/sessionStatus/viewport or {kind:'background', jobId} |
| terminal_read | read a bounded page of retained output, no input | totalLines/lineBegin/lineEnd/truncated |
| terminal_signal | signal SIGINT/SIGTERM/SIGKILL/SIGTSTP/SIGHUP to the foreground pgroup | targetPgid |
| terminal_close | close a session, wait for full process-tree teardown | closed/already-closing |
| terminal_list | list all sessions of the current agent | array |

## 3. Core usage conventions

### Owner isolation (every step goes through requireAgent)

A hard precondition in the source: all six tools call `requireAgent(exec.agent)`:

```ts
function requireAgent(agent: Agent | undefined): Agent {

  if (agent === undefined) throw new Error('terminal tools require an initiating agent')

  return agent

}
```

**Owner identity comes from the exact Agent that initiated that tool execution.** So even if a model learns another agent's session id, it cannot pry into that agent's terminal — every `spawn`/`send`/`read`/`signal`/`kill`/`list` is precisely fenced to the same owner.

### The system prompt section (order: 106)

The plugin contributes a fixed guidance section about when to use a terminal:

```ts
ctx.systemPrompt.section({

  name: 'tool:pty',

  order: 106,

  text: 'Use a terminal session only when work needs persistent terminal state or interactive stdin; prefer shell/read/write/edit for bounded one-shot operations. Track every terminal session id and close sessions that no longer matter. An inferred_idle or timeout result does not prove the foreground command exited.',

})
```

The points (they speak to the model, and are worth keeping in mind when writing a prompt):

- **Use a terminal only when work needs persistent terminal state or interactive stdin**; for bounded one-shot operations prefer `shell` / `read` / `write` / `edit`.

- **Track every session id and close sessions that no longer matter** — do not leak `terminal_close`.

- **`inferred_idle` or `timeout` does not prove the foreground command exited**.

### Configuration

| Key | Default | Minimum | Meaning |
| --- | --- | --- | --- |
| enableRunInBackground | true | — | expose and accept run_in_background; when false the schema omits the field and a forced undeclared parameter is rejected |
| maxResultBytes | 262144 | 64 | the UTF-8 cap for one complete terminal/task-output result; computed after wait, session, pagination, truncation, and task-status metadata are all included |

- Both values are validated at load: `maxResultBytes` must be a **safe integer ≥ 64** (`MIN_MAX_RESULT_BYTES`).

- The 64-byte minimum is deliberate: **it guarantees every registry-issued session id / job id appears fully in its creation acknowledgement**.

- Rendering reserves room for control metadata and the truncation marker (`[output truncated]`, cut at UTF-8 boundaries in the render layer), then trims the body.

## 4. One complete interactive session

The typical long-running flow — open, send commands, read into silence or when the program asks for more input, signal if needed, then close:

Verification / try-it (in an environment where you can run DSH), with a real REPL:

```sh
# 1) start a session that calls the terminal

dsh run --agent-terminal-demo

# 2) watch the order of terminal_* tool events in the session log

zstdcat ~/.dsh/sessions/*/*/session*.jsonl.zstd | grep -E '"terminal_' | head

# 3) confirm the tool-terminal row is mounted in the composition tree

dsh web --dump-config | grep -iE "tool-terminal|terminal-bash"
```

To experience it model-side: ask the agent to `terminal_open` a `shell`, send `python3`, then `print(2+2)`, keep feeding while `waitReason` is `stdin_read`, watch `waitReason` flip to `inferred_idle` or `session_exit`, and finally `terminal_close` to tear down.

## 5. The division of labor with the subprocess page

Do not confuse this with [subprocess and terminal](../features/subprocess.md):

- The **subprocess page** is the mechanism layer: the `ctx.terminals` service seam + the `terminal-bash` backend, and the `spawnTerminal` primitive beneath them — they own "how a PTY is allocated/routed/cleaned up".

- **This page** is the model layer: what the six tools are named, how their parameters are filled, how their returns are read, how to choreograph an interactive session, and how the background path plugs into `ctx.jobs`.

- A full tool overview is in [built-in tools](../features/tools.md), "Terminal domain".

|  | mechanism layer (subprocess page) | model layer (this page) |
| --- | --- | --- |
| Who | terminal / terminal-bash | tool-terminal |
| Deliverable | ctx.terminals seam, backend | six tool schemas + owner auth + prompt + result cap |
| For whom | other plugins / backends | the model |

## Next steps

- [Subprocess and terminal](../features/subprocess.md): the `ctx.terminals` seam and the `terminal-bash` backend

- [Built-in tools](../features/tools.md): the terminal domain and background jobs

- [Goals, jobs, and todos](../features/goals-tasks.md): `ctx.jobs` and `job_kill`
