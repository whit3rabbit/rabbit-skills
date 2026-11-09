# The user-questions Seam and Its Identity Boundary

- 
- Concepts Course
- Core Mechanisms
- The user-questions Seam and Its Identity Boundary
On this page

# The user-questions Seam and Its Identity Boundary

Audit baseline 0.1.5-alpha.1 @ 5dda764ed3; see [source/npm channels](../../guides/deepseek-harness-status.md).

**One-liner**: `ctx.userQuestions` is the seam for "pause a tool call and ask the human a question". `ask()` runs five checks, then dispatches the **Agent-scoped Cordis waterfall `user-questions/request`**: the first answerer to return an answer claims the request, and if every listener calls `next()` it throws `NO_PROVIDER` (fail closed). When an `agent` is supplied it **admits only the exact live instance in the AgentRegistry** — identity is decided by *runtime root ownership*, not durable session lineage. To plug in, a plugin/UI developer just registers an answerer on `user-questions/request`.

This is a core foundational lesson in the "interaction and advancement" mechanisms. After reading you will know: how the model pauses to wait for a human answer, which error codes correspond to what, why a child owned by another live agent must **never** ask the human, and how to write your own answerer.

## Contents

- [1. Where the seam sits](#1-where-the-seam-sits)
- [2. Public API and types](#2-public-api-and-types)
- [3. ask() validation order and dispatch](#3-ask-validation-order-and-dispatch)
- [4. The identity boundary: CALLER_NOT_LIVE / DELEGATED_CALLER](#4-the-identity-boundary-caller_not_live-delegated_caller)
- [5. BAD_INTENT: two assertions the types can't carry](#5-bad_intent-two-assertions-the-types-cant-carry)
- [6. How an answerer plugs in: the Agent-scoped waterfall](#6-how-an-answerer-plugs-in-the-agent-scoped-waterfall)
- [7. How to implement an answerer](#7-how-to-implement-an-answerer)
- [8. The model-facing side: tool-ask-user](#8-the-model-facing-side-tool-ask-user)
- [9. Verify](#9-verify)
- [Next steps](#next-steps)

---

## 1. Where the seam sits

`@deepseek-ai/dsh-user-questions` is the **Service Definition** package for this seam. It renders no UI itself; it owns:

- `ctx.userQuestions` — the `UserQuestionService`

- a set of wire-safe types (`AskUserQuestionRequest` / `AskUserQuestionAnswer`, …)

- a stable error taxonomy (`UserQuestionError`, a `HarnessError` subclass)

The consumer is the model-facing tool `@deepseek-ai/dsh-tool-ask-user` (`ask_user_question`); the **UI-side implementation** is an answerer composed onto the `user-questions/request` waterfall (the shipped Web answerer lives in the browser half and is forwarded in through Remote Events). The loop stays unchanged: a tool call `await`s a promise, and the human's answer feeds back into the agent loop as an ordinary tool result.

## 2. Public API and types

```ts
// packages/interaction/user-questions/src/types.ts (excerpt)

export interface AskUserQuestionRequestEvent {

  questions: AskUserQuestionItem[]

  agent?: Agent

  signal?: AbortSignal

}

// packages/interaction/user-questions/src/index.ts (excerpt)

export interface AskUserQuestionRequest extends AskUserQuestionRequestEvent {}

// Cordis waterfall declaration: returning an answer claims the request;

// calling next() delegates to the next answerer.

'user-questions/request'(

  this: Scoped<Agent>,

  request: AskUserQuestionRequestEvent,

  next: () => Promise<AskUserQuestionAnswer>,

): Promise<AskUserQuestionAnswer>
```

| API | Behavior |
| --- | --- |
| ask(request) | After validation, dispatches the user-questions/request waterfall and waits for the first accepted answer; when an agent is supplied, authenticates it first. |
| ctx.on('user-questions/request', (request, next) => …) | How an answerer plugs in: returning an answer claims the request, return next() delegates to the next answerer. |

Key types (`user-questions/src/types.ts`):

- **`AskUserQuestionItem`**: `{ id, question, detail?, header?, options?, multiSelect?, intent? }`. `detail` is supporting text rendered with the question but **kept out of option labels**.

- **`AskUserQuestionOption`**: `{ label, description? }` (recommended options go first, with `"(Recommended)"` appended).

- **`AskUserQuestionIntent`**: `{ kind: 'plan-review', approve }`, a declared presentation intent for UIs that recognise the tag.

- **`AskUserQuestionAnswer`**: `{ answers: [{ id, selected, custom? }] }`. Single-select: `custom` overrides the selected choice and `selected` is empty; multi-select: `custom` may supplement the labels in `selected`.

### Single / multi select and skipped items

From the source README: for a single-select question, `custom` overrides the selected choice and `selected` is empty; for a multi-select question, `custom` may supplement the labels in `selected`. A UI may preserve a skipped item as `{ id, selected: [] }`, keeping the existing answer shape while retaining the other answers in the batch.

### Presentation intent

`intent` asserts that the question **is** a known kind of decision, so a UI that recognises the tag may present it accordingly, otherwise it renders the generic option list — **presentation only, the protocol never changes**, and callers read identical answer fields either way. `approve` names the label that approves rather than relying on option order. `dsh-plan-mode` sets `plan-review` on the `exit_plan_mode` question.

## 3. ask() validation order and dispatch

`ask()` runs these checks **before dispatching the waterfall**, throwing `UserQuestionError`:

| Order | Trigger | Code |
| --- | --- | --- |
| 1 | signal is already aborted | ASK_ABORTED |
| 2 | questions.length === 0 | EMPTY_QUESTIONS |
| 3 | an agent is supplied but it is not the registry's exact live instance | CALLER_NOT_LIVE |
| 4 | it is the live instance but owned by another live agent (not a root) | DELEGATED_CALLER |
| 5 | a question's intent assertion breaks (approve names none of its options, or a plan-review has no detail) | BAD_INTENT |
| 6 | no answerer on the waterfall claims the request | NO_PROVIDER |

The head of `ask()` in the source (`user-questions/src/index.ts`):

```ts
async ask(request: AskUserQuestionRequest): Promise<AskUserQuestionAnswer> {

  if (request.signal?.aborted) {

    throw new UserQuestionError('ask_user_question was aborted before the user answered', 'ASK_ABORTED')

  }

  if (request.questions.length === 0) {

    throw new UserQuestionError('ask_user_question requires at least one question', 'EMPTY_QUESTIONS')

  }

  const agent = request.agent

  if (agent !== undefined) {

    const agents = this.ctx.get('agents')

    if (agents === undefined || agents.get(agent.id) !== agent) {

      throw new UserQuestionError(

        'human interaction requires the exact live calling agent when an agent is supplied',

        'CALLER_NOT_LIVE')

    }

    if (!agents.roots().includes(agent)) {

      throw new UserQuestionError(

        'human interaction is unavailable while the calling agent is owned by another live agent; …',

        'DELEGATED_CALLER')

    }

  }

  // … BAD_INTENT validation (section 5) follows, then:

  const noAnswerer = () => Promise.reject(new UserQuestionError(

    'no user-questions answerer accepted the request',

    'NO_PROVIDER',

  ))

  return await (agent === undefined

    ? this.ctx.waterfall('user-questions/request', request, noAnswerer)

    : this.ctx.waterfall(

      scopeTarget(agent, agent),

      'user-questions/request',

      { ...request, agent },

      noAnswerer,

    ))

}
```

## 4. The identity boundary: CALLER_NOT_LIVE / DELEGATED_CALLER

This is the heart of the lesson. **"Who may ask the human" is decided by runtime root ownership, not durable session lineage.**

- **`CALLER_NOT_LIVE`**: `agents.get(agent.id) !== agent` — you are not the exact live instance registered under that id. E.g. a replaced or disposed Agent handle. Identity is stricter than `agents.get(id)`; it also requires `===` the same instance.

- **`DELEGATED_CALLER`**: you are the live instance in the registry, but `!agents.roots().includes(agent)` — you are owned by another live agent. An owned child **has no human answerer** and would block forever, so it is mechanically rejected.

Why runtime root ownership rather than lineage? The `ask()` JSDoc says it plainly:

```ts
/**

 * When a caller supplies an agent, human interaction is valid only for the

 * exact live runtime root. Runtime ownership, not durable session lineage,

 * decides this boundary: an owned child has no human answerer and would

 * block forever, while a lineage-bearing session resumed as a new runtime

 * root may ask normally.

 */
```

- A session with historical delegation depth **may ask after it is resumed as a new runtime root** (deep lineage ≠ barred).

- A live child, even with `delegationDepth` 0, is **rejected** as long as it is still owned by another agent.

**When a child is rejected, what next?** The error message points the way: include the unresolved question or decision **in the child's final result**, so the parent relays it to the human. This is the "child hands unresolved questions back to parent" convention.

## 5. BAD_INTENT: two assertions the types can't carry

`intent` asserts two facts no type can encode:

- the `approve` label must be one **of this question's own options** — otherwise a UI would put a choice the asker never offered in front of the user.

- a `plan-review` must carry `detail` (that is "the plan under review") — otherwise a UI would approve something invisible.

```ts
// packages/interaction/user-questions/src/index.ts (excerpt)

for (const question of request.questions) {

  const intent = question.intent

  if (intent === undefined) continue

  if (!(question.options ?? []).some(option => option.label === intent.approve)) {

    throw new UserQuestionError(

      `question ${question.id} declares intent ${intent.kind} whose approve label …`,

      'BAD_INTENT')

  }

  if (question.detail === undefined) {

    throw new UserQuestionError(

      `question ${question.id} declares intent ${intent.kind} without the detail it reviews`,

      'BAD_INTENT')

  }

}
```

The source comment stresses catching the mistake **at the asker**, where the bug lives, rather than in every UI.

## 6. How an answerer plugs in: the Agent-scoped waterfall

The service has **no provider registry**. `ask()` dispatches the Cordis waterfall `user-questions/request` (the `Events` declaration in `packages/interaction/user-questions/src/types.ts`):

```ts
declare module '@deepseek-ai/cordis' {

  interface Events {

    /**

     * Ask composed answerers for structured user input. Return an answer to

     * claim the request or call `next()` to delegate. Scope-filtered dispatch

     * (`@deepseek-ai/dsh-scope`): agent-scoped listeners receive only that agent.

     * @mode waterfall

     */

    'user-questions/request'(

      this: Scoped<Agent>,

      request: AskUserQuestionRequestEvent,

      next: () => Promise<AskUserQuestionAnswer>,

    ): Promise<AskUserQuestionAnswer>

  }

}
```

- **Returning an answer claims it**: the first listener to return an `AskUserQuestionAnswer` ends the waterfall; `return next()` means "I won't handle it, pass it on".

- **Scope filtering**: a request with an `agent` is dispatched through `scopeTarget(agent, agent)`, so only that agent's scoped listeners receive it. An **agentless request never reaches the Web answerer** (it handles Agent-scoped requests only) and needs an unscoped local listener.

- **No listener claims it**: the fallback `noAnswerer` throws `NO_PROVIDER` **rather than degrading** — fail closed, not swallowed.

- Listeners are ordinary `ctx.on(...)` registrations that unregister with their plugin fiber; several answerers can stack on one waterfall, so there is no "duplicate registration" error.

The shipped Web answerer is one browser-half `ctx.remote.$on('user-questions/request', (request, next) => …)`: on the Host, `packages/api/remotes/src/remote-events.ts` forwards it to the browser as `{ event: 'user-questions/request', mode: 'waterfall' }`, and the browser's answer travels back to the Host (source `packages/client/ui-user-questions/src/client/index.ts`).

The README's Known Limitations also note that the interaction vocabulary is currently only the *question-form shape* (selectable options + optional custom text) — file pickers, diff-preview confirmations, and richer shapes have no seam vocabulary yet.

## 7. How to implement an answerer

A plugin/UI developer plugs into this seam in two steps:

```ts
import type { Context } from '@deepseek-ai/cordis'   // has ctx.userQuestions

import type {

  AskUserQuestionAnswer,

  AskUserQuestionRequestEvent,

} from '@deepseek-ai/dsh-user-questions'

export function apply(ctx: Context): void {

  // Returning an answer claims the request; return next() delegates.

  ctx.on('user-questions/request', async (request, next) => {

    if (!canHandle(request)) return next()

    return renderAndCollect(request)   // your UI/CLI/email… any presentation; resolves to AskUserQuestionAnswer

  })

}
```

Things to watch:

- **Claiming is exclusive**: the waterfall ends at the first returned value, so when you are unsure whether to handle a request you must call `next()`.

- Your answerer may `await` any endpoint — the loop does not care where you render or how you collect answers, as long as you resolve to an `AskUserQuestionAnswer`.

- A custom visual / terminal / Web UI, email, or a "headless" auto-responder is just **a different answerer on the same waterfall**.

- To accept **agentless** programmatic requests you must register an unscoped listener; the shipped Web answerer handles Agent-scoped requests only.

## 8. The model-facing side: tool-ask-user

`@deepseek-ai/dsh-tool-ask-user` exposes `ask_user_question` to the model. It composes no answerer itself; it only depends on the `userQuestions` service, and all validation / identity checks live in `ctx.userQuestions.ask()`. In `execute`, `exec.agent` is passed as `agent` (only when one exists) and `exec.signal` is the cancellation channel:

```ts
// packages/interaction/tool-ask-user/src/index.ts (excerpt)

async execute(args, exec) {

  const result = await ctx.userQuestions.ask({

    questions: args.questions.map(question => ({

      id: question.id,

      question: question.question,

      ...question.header !== undefined ? { header: question.header } : {},

      ...question.options !== undefined ? { options: question.options } : {},

      ...question.multi_select !== undefined ? { multiSelect: question.multi_select } : {},

    })),

    ...exec.agent !== undefined ? { agent: exec.agent } : {},

    signal: exec.signal,

  })

  return {

    answers: result.answers.map(answer => ({

      id: answer.id,

      selected: [...answer.selected],

      ...answer.custom !== undefined ? { custom: answer.custom } : {},

    })),

  }

}
```

On success the model gets a compact JSON answer; on failure one of the following (README / index.ts source):

```text
Error: ask_user_question was aborted before the user answered

Error: ask_user_question requires at least one question

Error: human interaction requires the exact live calling agent when an agent is supplied

Error: human interaction is unavailable while the calling agent is owned by another live

       agent; include the unresolved question or decision in the child agent's final result

Error: no user-questions answerer accepted the request

Error: <message>
```

## 9. Verify

```sh
# Composition tree: tool-ask-user / user-questions both loaded

dsh web --dump-config | grep -iE "ask-user|user-questions" | head

# Session log: ask_user_question calls and results

zstdcat ~/.dsh/sessions/*/*/session*.jsonl.zstd | grep -E '"tool/call"|ask_user_question' | head

# From an "owned child" agent, call ask_user_question and observe DELEGATED_CALLER

zstdcat ~/.dsh/sessions/*/*/session*.jsonl.zstd | grep -E 'DELEGATED_CALLER|CALLER_NOT_LIVE' | head
```

To actually see a question in a UI, start the Web UI and have the model call `ask_user_question` in a session (e.g. "I need your confirmation before continuing"), and watch the browser-side answerer render the question and feed the answer back.

## Next steps

- [Tool Execution](../../learn/core/tools-execution.md): how a tool call awaits and resumes the main loop on its result

- [Writing a Service](../../learn/dev/write-service.md): how to provide your own seam with `ctx.provide`

- [Writing a Tool](../../learn/dev/write-tool.md): how a consumer like `tool-ask-user` is built
