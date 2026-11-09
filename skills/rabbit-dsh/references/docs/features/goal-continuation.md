# Autonomous Long-Running Work: goal-round-driver vs Ralph

**One-liner**: DSH has two paths that keep a long-running objective moving forward with no one watching it. **goal-round-driver** appends a `<goal_round>` prompt into the *same* session over and over, reusing the prefix, KV cache, and tool results, with a durability checkpoint — a **same-session continuation** loop. **Ralph** spawns a **fresh Agent for every round**, carrying nothing across rounds but a shared workspace and one bounded report — a **fresh-agent** loop. Prefer goal-round-driver for most goals; reach for Ralph only when the human explicitly asks for fresh-agent iterative execution.

Both mechanisms answer the same question — "the objective is unfinished: who keeps working on it?" — but with a completely **different mental model**:

| Axis | goal-round-driver | Ralph |
| --- | --- | --- |
| Round carrier | The same session, appending a  user-role prompt | A fresh child Agent per round, no parent-conversation seed |
| Cross-round memory | Session history (KV cache / tool results / state) | Shared workspace + one bounded structured report |
| State ownership | ctx.goals, durable goal/change events | workflow + ctx.subagents (no standalone goal domain) |
| Cap | maxGoalRounds; auto-block (round-limit) on exhaustion | maxRounds; returns budget-limited on exhaustion |
| Completion / block | Autonomous complete/blocked via update_goal | Child reports status: continue/complete/blocked |
| Close-out | concludeTurn() + injected / | Parent receives a report; no close-out context injected |
| Authority | Driver-authorised goal round in one running agent | Child is just a plain subagent of the parent |

## Contents

- [1. goal-round-driver: same-session continuation](#1-goal-round-driver-same-session-continuation)
- [2. tool-goal wrap-up: autonomous close-out](#2-tool-goal-wrap-up-autonomous-close-out)
- [3. Ralph: a fresh Agent every round](#3-ralph-a-fresh-agent-every-round)
- [4. Which do you use when](#4-which-do-you-use-when)
- [5. Verify](#5-verify)
- [Next steps](#next-steps)

---

## 1. goal-round-driver: same-session continuation

`@deepseek-ai/dsh-goal-round-driver` is a Cordis plugin sitting on top of the public `agents` / `goals` / `sessions` services. It turns a **active + armed** goal in `ctx.goals` into sequential **goal rounds**. It does **not** rely on a private agent-loop: it drives through the public `Agent` interface and session events.

### Composition

```yaml
- id: goal

  name: '@deepseek-ai/dsh-goal'

- id: tool-goal

  name: '@deepseek-ai/dsh-tool-goal'

- id: goal-round-driver

  name: '@deepseek-ai/dsh-goal-round-driver'
```

The driver has no tunable config of its own: the round cap `maxGoalRounds` belongs to the goal definition (`tool-goal`'s `create_goal` / the deployment `defaultMaxGoalRounds`), and the model self-blocking threshold belongs to `tool-goal`'s `blockedAfterConsecutiveRounds`. The source README states that duplicating either value into the driver would produce divergent policy.

### Round contract

When an exact **live agent** is idle, the goal is active + armed, and there is remaining capacity, the driver first checkpoints pending goal mutations, then reserves round `roundsStarted + 1` for the current `{ goalId, revision }`. It queues a `<goal_round>` prompt carrying `GoalMessageSource` (`kind: 'goal'`) via `Agent.followup()`. Only an **admitted** `user/message` advances `roundsStarted`; a reservation rejected as stale does **not** consume the round number.

```ts
// packages/goal/goal-round-driver/src/prompt.ts (excerpt)

export function renderGoalRoundPrompt(goal: GoalView, round: number): ContentBlock[] {

  return [{

    type: 'text',

    text: '<goal_round>\n'

      + `Objective: ${JSON.stringify(goal.objective)}\n`

      + `Round: ${round}/${goal.maxGoalRounds}\n\n`

      + 'Continue working toward the objective in this same session. Treat the current workspace, '

      + 'tool results, and durable session state as authoritative; inspect them instead of assuming '

      + 'earlier narration is still current. …',

  }]

}
```

Once admitted, earlier human messages, goal-state snapshots, assistant output, and tool records all remain in that same session history. This is **appended growth**: each round extends the existing conversation from a reusable prefix — it never copies a conversation prefix or creates derived history.

### Await sessions.flush() before each round

A `goal/changed` event creates a durability obligation. Before queuing work, the driver runs `await ctx.sessions.flush(agent.session)`, and **re-checks** the goal revision and any competing input after the await returns:

```ts
// packages/goal/goal-round-driver/src/index.ts (excerpt)

if (state.needsCheckpoint) {

  state.needsCheckpoint = false

  try {

    await ctx.sessions.flush(agent.session)

  } catch (error) {

    ctx.logger.warn(`…durability checkpoint failed for agent "${agent.id}"…`)

    disarm(state)   // checkpoint failure → disarm continuation, never push forward sick

    return

  }

  if (!readyAfterCheckpoint(state)) return   // a mutation or message may have arrived during flush

}
```

- A flush failure arriving through `agent/error` disarms continuation before another round can start

- The flush is a **checkpoint**, not per-step: `ctx.sessions.flush()` persists pending events to the durable log

- If an ordinary human message or a mutation arrives while the checkpoint settles, the driver yields and gives that input its own checkpoint / turn before reserving again

### Round-cap: auto-block on exhaustion

```ts
// packages/goal/goal-round-driver/src/index.ts (excerpt)

if (goal.roundsStarted >= goal.maxGoalRounds) {

  ctx.goals.block(agent, goalRef(goal), {

    code: 'round-limit',

    message: `Goal reached its configured limit of ${goal.maxGoalRounds} rounds.`,

  })

  return

}
```

On exhaustion the goal enters `block` (a durable phase) with code `round-limit`. `maxGoalRounds` counts only **admitted** goal-sourced rounds; human messages do not consume the cap.

### No fresh agent, no session-prefix fork

The README calls this out explicitly as a design boundary:

**Same-session execution only** — this package deliberately does not spawn a fresh agent, fork a session prefix, or implement Ralph-style independent attempts.

Each admitted round adds just one fixed instruction block plus the objective. KV cache is **append-only within an epoch**: every round extends the existing conversation after its reusable prefix; compaction may move that boundary. This is the core reason it is cheaper than Ralph in tokens and KV.

### Race fences (in brief)

The driver carefully handles the reservation vs queued vs admitted race. The `agent/pre-step` listener verifies the full claimed record and the current goal both **before and after** downstream listeners; only an entered `user/message` increments `roundsStarted`; a pending automatic prompt that lands in a mixed batch with human messages is rejected and re-reserved only after that checkpoint.

## 2. tool-goal wrap-up: autonomous close-out

`@deepseek-ai/dsh-tool-goal` exposes `get_goal` / `create_goal` / `update_goal`. When, during an **autonomous goal round**, the model calls `update_goal` with `complete` or `blocked` successfully, `tool-goal` injects a `<goal_complete>` / `<goal_blocked>` close-out context via `exec.deferContext()` and marks that tool execution with `concludeTurn()`, so **that physical turn stops after the step** — but the model still writes the user one closing message first (the README says this "replac[es] the former hard turn stop").

```ts
// packages/goal/tool-goal/src/index.ts (excerpt)

if (authority.kind === 'goal-round') {

  exec.deferContext(createUserMessage({

    content: args.action === 'complete'

      ? renderWrapupContext(goal.objective)

      : renderWrapupContext(goal.objective, args.blocked_reason as string),

    source: { kind: 'plugin', plugin: 'tool-goal', form: 'notice', … },

  }))

}
```

The close-out context requires grounding (report only what earlier rounds and tool results in this session actually establish), addresses the user directly, and forbids calling further tools in that run.

`update_goal` with `blocked` is constrained by a hard lower bound when authority is the goal round:

```ts
// packages/goal/tool-goal/src/index.ts (excerpt)

if (args.action === 'blocked' && authority.kind === 'goal-round'

  && authority.goal.roundsStarted < resolved.blockedAfterConsecutiveRounds) {

  throw new HarnessError(

    `blocked requires at least ${resolved.blockedAfterConsecutiveRounds} consecutive goal rounds; …`,

    'GOAL_TOOL_BLOCK_THRESHOLD')

}
```

- `blockedAfterConsecutiveRounds` defaults to `3` (`z.number().step(1).min(1).default(3)`)

- It is the **hard lower bound** on model self-blocking: self-blocking before 3 admitted rounds is mechanically rejected

- Whether the *same condition actually persisted* remains model judgment — the runtime only verifies the distinct admitted-round count, and persists `code: 'model-reported'`

## 3. Ralph: a fresh Agent every round

`@deepseek-ai/dsh-tool-ralph` is the model-facing **fresh-agent iterative loop**. It adds no Ralph mode to `agent-loop`; it is an ordinary plugin over `ctx.workflowEngine` and `ctx.subagents`:

```markdown
Use the ralph tool ONLY when the direct human explicitly asks for a Ralph loop or fresh-agent

iterative execution. Each Ralph round starts a fresh child with no conversation seed and uses

the shared workspace as durable memory. Completion and blockers are worker reports, not

independent evaluation. Use same-session goal tools for ordinary long-running objectives…
```

Every Ralph round starts, through `subagentProvider`, a **fresh child Agent with no parent-conversation seed**; neither the parent conversation nor prior child sessions are seeded. The only cross-round memory is a **shared workspace** + one **bounded structured report** (`status: continue | complete | blocked` with summary / evidence / next steps / blocker text).

- An oversized / missing / invalid report **fails the workflow** rather than being truncated or mistaken for cap exhaustion

- An ordinary child failure yields an error naming the failed round and retains the last successful handoff; **Ralph does not retry that round**

- Ordinary child failures and provider/transport failures are all errors; partial output is **never success**

- Completion is **worker self-declaration**: the child reports `complete`, the parent only relays it, with no independent evaluator certifying it

## 4. Which do you use when

| Scenario | Use |
| --- | --- |
| The user sets a long-run objective and wants it advanced within the same session | goal-round-driver (create_goal) |
| You want to reuse accumulated tool results, KV cache, and session state | goal-round-driver |
| You need a durability checkpoint: resume after an interruption | goal-round-driver (sessions.flush checkpoint) |
| The user explicitly asks for a "Ralph loop / fresh-agent iterative execution" | ralph |
| A stable objective needing repeated trial-and-error, each round from a clean context | ralph |
| A couple of independent delegations / large fan-out | plain subagent / workflow (not goal / ralph) |

The model-facing guidance in the source draws the same line: Ralph is for the explicit fresh-agent iterative request; the goal tools are for ordinary same-session long-running objectives.

## 5. Verify

```sh
# Assert "same session": a goal round is a user/message whose source.kind is 'goal'

zstdcat ~/.dsh/sessions/*/*/session*.jsonl.zstd \

  | grep -E '"source":\{"kind":"goal"' | head

# See goal changes and the round-limit block

zstdcat ~/.dsh/sessions/*/*/session*.jsonl.zstd | grep -E 'goal/|"round-limit"' | head

# All three goal plugins loaded in the composition tree

dsh web --dump-config | grep -iE "goal-round-driver|tool-goal|'goal'" | head

# Ralph goes through workflow run events (run-start/members/run-end)

zstdcat ~/.dsh/sessions/*/*/session*.jsonl.zstd | grep -E 'workflow|"run/' | head
```

Compare the two paths: `goal/change` + `user/message(source.kind=goal)` is the fingerprint of same-session continuation; **`workflow/run*` events and child sessions** are the fingerprint of fresh-agent advancement.

## Next steps

- [Goals, Jobs, and Todos](../features/goals-tasks.md): the `ctx.goals` state machine and the `/goal` command

- [Workflows and Ralph](../features/workflow.md): the workflow / subagent seam under Ralph

- [Subagents and Parallelism](../features/subagent.md): the `ctx.subagents` Ralph uses each round
