# Interaction Seams: Approval, Permission Presets, and Commands

- 
- Concepts Course
- Core Mechanisms
- Interaction Seams: Approval, Permission Presets, and Commands
On this page

# Interaction Seams: Approval, Permission Presets, and Commands

**In short**: `packages/interaction` splits "how a person guides a running agent" into several **independent seams** — `ctx.approval` asks once whether an action may proceed (`ApprovalOutcome`, a closed four-value set; a missing answerer fails closed), `ctx.permissionPresets` bundles sandbox mode with approval policy into one user-facing preset selector, and `ctx.commands` lets plugins register human slash commands that never enter a model round trip; the fourth seam, `ctx.userQuestions` (the model asking a person), has its own [dedicated page](../../learn/core/user-question-seam.md), so this page only maps it and cross-links.

**Audit baseline 0.1.5-alpha.1 @ 5dda764ed3**: package names, ctx keys, event names, methods, types, and config keys are all verified point-by-point against the official source.

This is the core lesson on the interaction plane. After reading you can answer: which stages an approval passes from a tool request to a grant, why the answer vocabulary has only four values, how to write and compose an answerer, how a preset switch "writes through" to the approval policy, and how a slash command is registered, addressed, logged, and where its result goes.

## Contents

- [1. How the four seams divide the work (a map)](#1-how-the-four-seams-divide-the-work-a-map)
- [2. ctx.approval: API and decision vocabulary](#2-ctxapproval-api-and-decision-vocabulary)
- [3. request()'s sequence and fail-closed rules](#3-requests-sequence-and-fail-closed-rules)
- [4. Composing answerers: the approval/request waterfall](#4-composing-answerers-the-approvalrequest-waterfall)
- [5. Policy and audit events](#5-policy-and-audit-events)
- [6. ctx.permissionPresets: how a preset writes through to approval](#6-ctxpermissionpresets-how-a-preset-writes-through-to-approval)
- [7. ctx.commands: the plugin command registry contract](#7-ctxcommands-the-plugin-command-registry-contract)
- [Sources](#sources)
- [Verification](#verification)
- [Next steps](#next-steps)

---

## 1. How the four seams divide the work (a map)

| Seam | ctx key | Package | Who initiates | Answer / result shape | Here |
| --- | --- | --- | --- | --- | --- |
| Approval | ctx.approval | packages/interaction/user-approval | Tool pipeline, sandbox escalation retry | ApprovalOutcome, a closed four-value set | §2–5 |
| Permission presets | ctx.permissionPresets | packages/interaction/permission-presets | The user (/permission) | Preset name + two knob events | §6 |
| Human commands | ctx.commands | packages/interaction/commands | The user (typing /xxx in a UI) | CommandResult, rendered directly | §7 |
| Asking a person | ctx.userQuestions | packages/interaction/user-questions | The model (ask_user_question) | AskUserQuestionAnswer | Dedicated page |

Three relationships matter:

- **Presets write through to approval; approval does not depend on presets.** `permissionPresets`'s `set()` calls `setApprovalPolicy()` exported by `user-approval`; conversely, `ApprovalService` has no idea presets exist — it only folds `approval/policy` events. Removing the preset package therefore leaves the last knob values in effect.

- **The command registry is not a model surface.** Command metadata, input, and direct output never enter a model request; only work a command producer explicitly schedules through an `Agent` costs tokens.

- **Approval and asking are two different paths.** Approval is "I want to act, please authorize" (raised by a tool or the sandbox; the person gives a one-shot grant). Asking is "I need information" (raised by the model; the person gives a structured answer). Both use an Agent-scoped waterfall, but the service, event names, and answer types are entirely different.

For the user-facing configuration, environment variables, and `/permission` operations see [Permissions](../../user-guide/permissions.md); for the enforcement boundary itself see [Sandbox and Security](../../learn/core/sandbox-security.md).

## 2. ctx.approval: API and decision vocabulary

`ApprovalService` (service name `'approval'`) is this seam's service definition (`user-approval/src/index.ts:142`). Its public surface:

| Member | Signature | Meaning |
| --- | --- | --- |
| request | request(req: ApprovalRequest): Promise | Ask once; requires an open turn; the audit pair lands in the log |
| setPolicy | setPolicy(agent: Agent, policy: ApprovalPolicy): void | Switch a live agent's policy and inject a "policy changed" user message for the model |
| overrideOf | overrideOf(session: Session): ApprovalPolicy | undefined | Read the last approval/policy event in the log; undefined without an override |
| setApprovalPolicy | module-level setApprovalPolicy(session, policy): void | The single durable write path (session initialization uses it directly); an invalid value throws before the log changes |
| APPROVAL_POLICIES | readonly ApprovalPolicy[] | ['ask', 'never'], used for option advertisement and runtime validation |

**The effective policy** comes from a private fold: `overrideOf(session) ?? config.policy ?? 'ask'` (`user-approval/src/index.ts:235`). There is exactly one config field:

```yaml
- name: '@deepseek-ai/dsh-user-approval'

  config:

    policy: ask     # ask | never, defaults to ask
```

**The decision vocabulary is closed** (`user-approval/src/types.ts:32`):

| Return value | Meaning | What a caller should do |
| --- | --- | --- |
| allowed-once | The only grant value: valid for this requested action only, never a remembered rule | Proceed this once |
| rejected | Explicit refusal | Deny |
| cancelled | The request was withdrawn (signal abort) | Deny |
| unavailable | No answerer, a throwing answerer, or a value outside the closed set | Fail closed: treat as denial |

`ApprovalRequest` (`user-approval/src/index.ts:103`) deliberately **carries no tool arguments**: an answerer attaches the prompt to the already-streamed tool call through `callId` instead of rendering a second copy that could drift.

| Field | Required | Meaning |
| --- | --- | --- |
| agent | yes | On whose behalf the question is asked; decides scope routing and which session receives the audit |
| toolName | yes | The tool the question is about (presentation + audit) |
| callId | no | The exact tool-call id, so a UI can attach the prompt to the call it already streamed |
| reason | no | The asker's human-readable explanation |
| signal | no | Aborting withdraws the question: the request settles cancelled immediately and a late answer is discarded |

## 3. request()'s sequence and fail-closed rules

The order inside `request()` (`user-approval/src/index.ts:207`) is fixed:

- **The open-turn precondition.** The session log must sit inside a `turn/start` not yet closed by `turn/end`; otherwise it throws immediately and **appends nothing**. The audit pair must be turn-enclosed because the turn is the durable log's commit/replay boundary — a bare event between turns is indistinguishable from a crash tail on reload.

- Mint a fresh `ApprovalRequestId(randomUUID())` and append `approval/asked`.

- `decide()` produces one outcome:

`signal` already aborted → `cancelled`;

- effective policy is `never` → `rejected`, **before any answerer dispatch**;

- otherwise enter `ctx.waterfall(scopeTarget(req.agent, req.agent), 'approval/request', req, () => 'unavailable')`; a return value outside the closed set → `unavailable`, a throw → `unavailable` (a synchronous throw lands in the same containment);

- with a `signal`, the answer races the abort: an abort that wins returns `cancelled`, and a later answerer answer is discarded.

- Append `approval/decided` and return the outcome.

**Three fail-closed rules** (`decide()`, `user-approval/src/index.ts:258`): no answerer claims it → `unavailable`; an answerer throws → `unavailable`; a non-vocabulary return → `unavailable`. Separately, if an audit append fails before the commit point the request **rejects** — returning an unlogged decision would break the audit pair.

A consumer example: the tools pipeline opportunistically takes the service with `ctx.get('approval')` and maps an `ask` decision to allow/deny (`packages/core/tools/src/index.ts:1696`); sandbox escalation retries ride the same seam (`approveEscalation`, `packages/sandbox/sandbox/src/escalation.ts`; see [Sandbox and Security](../../learn/core/sandbox-security.md) for the details).

## 4. Composing answerers: the approval/request waterfall

The service itself has **no provider registry**; the entry point is the Cordis waterfall `approval/request` (`user-approval/src/types.ts:85`):

```ts
declare module '@deepseek-ai/cordis' {

  interface Events {

    /**

     * Ask composed answerers for one decision. Return an outcome to claim the

     * request or call `next()` to delegate. Scope-filtered dispatch

     * (`@deepseek-ai/dsh-scope`): agent-scoped listeners receive only that agent.

     * @mode waterfall

     */

    'approval/request'(

      this: Scoped<Agent>,

      req: ApprovalRequestEvent,

      next: () => Promise<ApprovalOutcome>,

    ): Promise<ApprovalOutcome>

  }

}
```

- **Returning an outcome claims the request**; the first returned value ends the waterfall, and `return next()` means "I won't handle it".

- **Scope filtering**: the request is dispatched through `scopeTarget(req.agent, req.agent)`, so only that agent's scoped listeners receive it; the scope layer takes the key from `args[0].agent` (`packages/core/scope/src/scoped-events.generated.ts:24`).

- **The terminal default is `unavailable`**, so a deployment should compose **exactly one terminal answerer**; sibling listener order is not a policy-priority mechanism.

- Listeners are ordinary `ctx.on(...)` registrations that unregister with their plugin fiber.

Two real answerers in the shipped composition:

| Implementation | Location | Behavior |
| --- | --- | --- |
| Browser UI | packages/client/ui-approval/src/client/index.ts | ctx.remote.$on('approval/request', …): renders the request as a pending-interaction panel; the Host side forwards it to the browser as { event: 'approval/request', mode: 'waterfall' } (packages/api/remotes/src/remote-events.ts:18) |
| ACP machine decision | packages/acp/acp/src/index.ts:155 | Answers only for sessions it owns, and only when the request carries a callId, else next(); it offers the client just allow-once / reject-once and never infers a durable grant from an unknown response |

**`never` cannot be bypassed**: the policy is enforced on the service's own `request()` path before any waterfall dispatch, so even a later-registered `prepend: true` listener cannot make a `never` session ask.

## 5. Policy and audit events

`user-approval` declares four events:

| Event | Mode | Payload | Purpose |
| --- | --- | --- | --- |
| approval/request | waterfall | ApprovalRequestEvent | The answerer entry point |
| approval/asked | log-only | { id, toolName, callId?, reason? } | First half of the audit pair; id pairs it with the second |
| approval/decided | log-only | { id, outcome } | Second half; exactly one per ask |
| approval/policy | log-only | { policy, source?: 'delegation' } | Session policy override; the last one wins; source: 'delegation' marks an override seeded into a child |

The two audit events **never enter the model transcript**: what the model sees is the consumer's eventual tool result plus the policy sentence in the runtime-context snapshot.

Policy semantics (`ApprovalPolicy`, `user-approval/src/index.ts:63`):

- `ask` (the default) — delegate to the composed answerers; with none composed the chain falls through to the fail-closed `unavailable`.

- `never` — prompt nobody, and every ask resolves deterministically to `rejected`; the strict stance for CI and unattended runs. The model is told that approval prompts are disabled and not to request sandbox escalation (not to set `sandbox_permissions`).

The model-visible surface comes from the systemPrompt contribution `approval:policy` (`user-approval/src/index.ts:155`): each policy contributes one sentence stating its **complete current meaning**, appended after retained history, so switching policy never rewrites the stable system-prompt prefix. `setPolicy()` additionally injects a sourced user message announcing the change.

**Audit invariants** (`user-approval/src/invariant.ts`) validate both loaded and newly appended events: `approval/asked` / `approval/decided` must be inside an open turn, pair one-to-one by `id`, and keep `outcome` and `policy` inside their closed sets. Failure messages look like:

```text
approval/asked appended outside any open turn

approval/asked toolName must be non-empty

approval/asked repeated open id "<id>"

approval/decided has no matching approval/asked for id "<id>"

approval/decided carries unknown outcome "<value>"

approval/policy carries unknown policy "<value>"
```

**Error shape**: this seam has **no error-code enum** (unlike `user-questions`' `UserQuestionError` with stable codes). Its failure taxonomy is the closed outcome set; only programming errors throw:

| Trigger | Thrown |
| --- | --- |
| Calling request() with no open turn | Error: approval.request() outside an open turn: … |
| Passing an invalid policy to setApprovalPolicy() | TypeError: approval policy must be one of "ask" or "never" |

## 6. ctx.permissionPresets: how a preset writes through to approval

`PermissionPresetService` (service name `'permissionPresets'`, `permission-presets/src/index.ts:162`) bundles two **independent** enforcement knobs — sandbox mode `sandbox/mode` and approval policy `approval/policy` — into named presets a client offers as one selector. It performs **no enforcement itself**: execution, narration, and replay keep reading each knob's own fold.

A preset is one table entry (`PresetSpec`, `permission-presets/src/index.ts:58`):

| Field | Meaning |
| --- | --- |
| sandbox | The sandbox/mode value this preset writes |
| approval | The approval/policy value this preset writes |
| name | Display label a client shows; the table key when omitted |
| description | One user-facing sentence; omitted when not configured |

The **default table in the plugin source has only two entries**: `workspace-write` (`workspace-write` + `ask`) and `danger-full-access` (`danger-full-access` + `never`). The shipped base bundle overrides it with three at `packages/bundle/base/cordis.patch.yml:229`, adding `read-only` (`read-only` + `ask`) — that is the table you see in `dsh web --dump-config`. `custom` is a **reserved name**: a table entry named `custom` throws at plugin load, because it exists only for the derived "matches no preset" state.

**The write-through path** (`set()` → `apply()`, `permission-presets/src/index.ts:379`, `:384`):

- `resolve(name)` looks up the entry; an unknown name throws;

- if the effective preset differs from the target name, append `permission/preset` (log-only user intent);

- compare each knob's **effective value** and call only the changed one's canonical setter — `setSandboxMode` (from `dsh-sandbox-policy`) or `setApprovalPolicy` (from `dsh-user-approval`). A net-zero selection writes nothing.

`current(session)` derives in this order (`permission-presets/src/index.ts:308`): the **last recorded selection** while it still matches the knobs (so user intent survives when two presets share a bundle) → the first matching entry in table order → otherwise the derived `CUSTOM_PRESET` (`'custom'`, display-only, never a switch target).

**The read side** is the `permissions` session projection (`permission-presets/src/index.ts:237`): key `permissions`, `stateVersion: 2`, folding `permission/preset` / `sandbox/mode` / `approval/policy` / `session/end-seed`, with a `PermissionSelect` wire view (every switchable preset in table order, `custom` appended exactly while current, plus `currentValue`). A missing projection key means no permission service is composed and clients hide the control.

**Defaults and session pinning**: the `permission` settings namespace's `defaultPreset` affects **future sessions only**; `session/created` and every existing session run `pinInitialPermission()` — a genuinely fresh session gains the default preset plus both knob facts, while a seeded or partially initialized session keeps its effective knob values and gains only the missing durable facts.

**The `/permission` command** is the one write path a web client uses (`permission-presets/src/index.ts:256`; the service-level write path is `set()`): a bare invocation reports the current value and the available table, and an argument calls `apply(..., policy => ctx.approval.setPolicy(agent, policy))`. Note the difference — calling `setApprovalPolicy()` directly only writes the log, whereas `/permission` goes through `setPolicy()`, so it **also injects the policy-change notice for the model**.

**How a preset resolves into approval behavior**: the preset's `approval` knob ultimately lands as an `approval/policy` event; `ApprovalService` folds it into the effective policy; `never` short-circuits before answerer dispatch and `ask` enters the waterfall. There is **no second channel** between presets and approval.

Misconfiguration fails at load time (`permission-presets/src/index.ts:192`):

```text
permission: "custom" is reserved for the derived not-a-preset state and cannot name a table entry

permission: the mounted bash executor does not confine (no sandboxMode) — presets bundle a sandbox mode, so composing this plugin over an unconfined executor is a misconfiguration

permission: composed sandbox and approval defaults match no preset; configure defaultPreset explicitly

permission: unknown preset "<name>" (known: <names>)

permission: permissions session projection is not registered
```

The service declares `static inject = ['shell', 'approval', 'sessions', 'sessionProjections']` (`permission-presets/src/index.ts:183`): without a confining `ctx.shell` executor there is no `sandboxMode` fact to bundle, so composition fails instead of degrading silently.

## 7. ctx.commands: the plugin command registry contract

`CommandRuntime` (service name `'commands'`, `commands/src/index.ts:258`) is the **plugin-owned human command registry** consumed by interactive UI adapters. The usage-level tutorial is [Custom Commands and User Interaction](../../features/commands.md); this section covers only the registry contract.

### Registration contract

```ts
export interface CommandDefinition {

  readonly name: string                              // lowercase, ^[a-z][a-z0-9_-]*$

  readonly description: string                       // discovery-UI summary, non-empty

  readonly input?: CommandInputDescriptor            // { hint: string; attachments?: boolean }

  readonly recordInput?: boolean                     // defaults to true

  readonly handler: (invocation: CommandInvocation) => CommandResult | Promise<CommandResult>

}
```

`register(definition)` (`commands/src/index.ts:280`) **validates and then freezes** a detached copy (`normalizeDefinition`, `:176`): the name must match `/^[a-z][a-z0-9_-]*$/u`, `description` must be a non-empty string, `handler` must be a function, `input.hint` must be a non-empty string, and `input.attachments`, when present, must be a boolean. It returns the **exact disposer** that unregisters the definition; a duplicate name in the same layer throws at registration.

### Ownership and scope

- A registration on a plain context is **global**; a command-producing plugin mounted under an agent context that declares its `commands` injection registers an **agent-scoped** command that **shadows** a same-named global for that agent only.

- Layers merge through `ScopedLayers`: `list(agent)` returns handler-free `CommandDescriptor`s sorted by name, and `find(agent, name)` returns the effective definition after scoped shadowing.

- Registration and removal emit `commands/change` (`:87`, emit mode). Observer failures are contained one by one: they can neither veto the registry mutation nor starve later observers.

### Addressing and arguments

- `CommandId` is a brand (`commands/src/brand.ts:20`); each execution mints `cmd-<instanceToken>-<seq>`, and the instance-token prefix keeps ids unique across a restart over one resumed log.

- `parseCommand(line)` (`commands/src/index.ts:122`) splits with `/^\/([a-z][a-z0-9_-]*)(?=$|[\t\n\r ])/u`: everything after the name — separator whitespace included — becomes the verbatim `rawInput`, and the command owns its own grammar.

- Attachments: only a command declaring `input.attachments: true` accepts them; admission happens inside `execute()` — images go through `admitEncodedImages`, files are resolved from their receipt by the single `registerFileReceiptResolver` provider, and the original mixed order is restored. Anything non-conforming (undeclared, no attachment store, unknown receipt, over limit) settles as an error before the handler runs.

### Invocation path and lifecycle

An adapter calls the Host-side `execute(agent, line, attachments, signal)` (`commands/src/index.ts:356`):

- `parseCommand` or name resolution fails → return `undefined` and **log nothing** (it never entered a handler);

- mint a `commandId` and append `command/run` before the handler (`args` is omitted when `recordInput: false`);

- admit attachments;

- call the handler and validate its return shape with `normalizeResult`;

- append `command/done` and return `{ commandId, result }`.

Both lifecycle events are **standalone, log-only** appends: no turn wraps them, and persistence drains them at ordinary checkpoints; a thrown or aborted handler settles as `kind: 'error'`. A `command/run` append failure fails the execution **loud**; a `command/done` append failure on the handler-failure path is contained so the handler's own error stays the reported failure.

`CommandResult` has exactly two shapes — `{ kind: 'success', text?, sourceEventSeq? }` and `{ kind: 'error', text }` — rendered directly by the dispatching UI and **never entering model history**; `sourceEventSeq` (success only) names an earlier authoritative domain event so a client can combine the command lifecycle with that projection without parsing `text`.

The browser-half Remote facade addresses by `sessionId` (`packages/client/ui-commands/src/client/service.ts:365`), while the Host-side method's first parameter is `agent`.

Registration and result validation errors are all `TypeError`s (`commands/src/index.ts:176`, `:223`):

```text
command name "<name>" must match /^[a-z][a-z0-9_-]*$/u

command "<name>" description must be a string

command "<name>" description must not be empty

command "<name>" handler must be a function

command "<name>" input hint must be a string

command "<name>" input hint must not be empty

command "<name>" input attachments flag must be a boolean

command "<name>" handler must return a CommandResult

command "<name>" success text must be a string when supplied

command "<name>" success sourceEventSeq must be a non-negative safe integer when supplied

command "<name>" error text must be a non-empty string

command "<name>" returned unknown result kind "<kind>"
```

Also: a second `registerFileReceiptResolver` throws `Error: commands: a file receipt resolver is already registered`, and an unknown file receipt throws `AttachmentError('File upload receipt is unknown for this session.', 'ATTACHMENT_NOT_FOUND')`. The command invariant (`commands/src/invariant.ts`) requires every `command/done` to pair a prior `command/run` in the same session log and every `sourceEventSeq` to point at an earlier non-command event.

Registrants visible in the source: `/permission` (`permission-presets/src/index.ts:256`), `/plan` (`packages/plan/plan-mode/src/index.ts:225`), `/compact` (`packages/compaction/command-compact/src/index.ts:100`), `/feedback` (`packages/feedback/command-feedback/src/index.ts:61`), `/goal` (`packages/goal/command-goal/src/index.ts:190`), and `/export` (`packages/session-query/session-log-export/src/index.ts:78`).

## Sources

| File | Symbol / line |
| --- | --- |
| packages/interaction/user-approval/src/index.ts | ApprovalService :142; request() :207; setPolicy() :176; overrideOf() :244; setApprovalPolicy() :92; effectivePolicy() fold :235; decide() :258; never short-circuit :266; OUTCOMES :48; APPROVAL_POLICIES :63; approval/policy event declaration :33; approval:policy context contribution :155 |
| packages/interaction/user-approval/src/types.ts | ApprovalRequestId :17; ApprovalOutcome :32; approval/asked :44; approval/decided :55; ApprovalRequestEvent :63; approval/request waterfall :85 |
| packages/interaction/user-approval/src/invariant.ts | validateApprovalEvent() :28 (turn enclosure, id pairing, closed vocabulary) |
| packages/interaction/permission-presets/src/index.ts | PresetSpec :58; CUSTOM_PRESET :73; PERMISSION_SETTINGS_NAMESPACE :76; Config :143; PermissionPresetService :162; static inject :183; permissions projection registration :237; /permission command :256; current() :308; selectFor() :333; resolve() :350; optionOf() :365; set() :379; apply() :384; pinInitialPermission() :404 |
| packages/interaction/permission-presets/src/types.ts | PresetOption :13; PermissionSelect :27; SessionProjectionMap.permissions declaration |
| packages/interaction/commands/src/index.ts | COMMAND_NAME :31; CommandInvocation :40; CommandDefinition :60; parseCommand() :122; normalizeDefinition() :176; normalizeResult() :223; CommandRuntime :258; register() :280; registerFileReceiptResolver() :294; list() :310; find() :323; execute() :356; command/run append :368; command/done append :375; mintCommandId() :441; notifyChange() :470 |
| packages/interaction/commands/src/types.ts | CommandResult :34; CommandExecution :49; CommandDescriptor :57; commands/change :87; command/run :103; command/done :110 |
| packages/interaction/commands/src/brand.ts | CommandId :20 |
| packages/interaction/commands/src/invariant.ts | run/done pairing and sourceEventSeq validation |
| packages/bundle/base/cordis.patch.yml | approval config :225; three-entry preset table :229 |
| packages/core/tools/src/index.ts | serviceAsk() consuming ctx.approval :1696 |
| packages/sandbox/sandbox/src/escalation.ts | EscalationOutcome / approveEscalation: escalation retries share the same seam |
| packages/acp/acp/src/index.ts | machine answerer :155 |
| packages/client/ui-approval/src/client/index.ts | browser answerer (ctx.remote.$on('approval/request', …)) |
| packages/api/remotes/src/remote-events.ts | approval/request remote forwarding :18 |
| packages/core/scope/src/scoped-events.generated.ts | scope key taken from args[0].agent :24 |

## Verification

```sh
SRC=~/.dsh/source/official

# 1) Composition tree: all three services are in the web profile (with the base-overridden preset table)

dsh web --dump-config | grep -nE "dsh-user-approval|dsh-permission-presets|dsh-commands"

# 2) Approval: closed outcome set, waterfall declaration, policy write path

grep -n "allowed-once\|approval/request\|setApprovalPolicy" \

  $SRC/packages/interaction/user-approval/src/types.ts \

  $SRC/packages/interaction/user-approval/src/index.ts

# 3) Presets: reserved custom name, permission/preset event, the two write-through setters

grep -n "CUSTOM_PRESET\|permission/preset\|setSandboxMode\|setApprovalPolicy" \

  $SRC/packages/interaction/permission-presets/src/index.ts

# 4) Commands: name regex, parser, lifecycle events

grep -n "COMMAND_NAME\|parseCommand\|command/run\|command/done" \

  $SRC/packages/interaction/commands/src/index.ts \

  $SRC/packages/interaction/commands/src/types.ts

# 5) Runtime: audit pairs, command lifecycles, and preset switches all land in the session log (read-only)

zstdcat ~/.dsh/sessions/*/*/session.jsonl.zstd 2>/dev/null \

  | grep -E '"approval/(asked|decided|policy)"|"command/(run|done)"|"permission/preset"' | head
```

On this machine's `0.1.5-alpha.1`, command 1 prints the `dsh-user-approval`, `dsh-permission-presets`, and `dsh-commands` plugin entries, plus the `read-only` / `workspace-write` / `danger-full-access` preset table.

## Next steps

- [The user-questions Seam and Its Identity Boundary](../../learn/core/user-question-seam.md): the model-asks-a-person seam, contrasted with approval

- [Permissions](../../user-guide/permissions.md): presets, `/permission`, environment variables, and configuration

- [Sandbox and Security](../../learn/core/sandbox-security.md): `ctx.sandbox.confine` and escalation retries

- [Custom Commands and User Interaction](../../features/commands.md): using commands and `ask_user_question`

- [Writing a Service](../../learn/dev/write-service.md): providing a capability seam of your own
