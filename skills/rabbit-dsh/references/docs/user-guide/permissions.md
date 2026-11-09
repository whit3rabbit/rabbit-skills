# Permissions

**Short version**: DSH's permission system controls what an agent can execute and whether approval is required: a set of "presets" picks an operation mode profile, and a set of "approval policies" decides whether to ask the user. It is **not a sandbox**; the real file-access boundary lives in the [Sandbox](../learn/core/sandbox-security.md).

## Contents

- [1. Permission presets](#1-permission-presets)
- [2. Approval policies](#2-approval-policies)
- [3. Configuration](#3-configuration)
- [4. Approval decision chain (what ask actually goes through)](#4-approval-decision-chain-what-ask-actually-goes-through)
- [5. Ask-the-user tool (ask_user_question)](#5-ask-the-user-tool-ask_user_question)
- [6. Permissions vs sandbox (easy to confuse)](#6-permissions-vs-sandbox-easy-to-confuse)
- [7. Best practices](#7-best-practices)
- [Next steps](#next-steps)

---

## 1. Permission presets

| Preset | Sandbox mode | Approval policy | Behavior |
| --- | --- | --- | --- |
| workspace-write | workspace-write | ask | Writes only to the current workspace; write operations need approval |
| read-only | read-only | ask | Read-only sandbox; operations still require confirmation |
| danger-full-access | danger-full-access | never | All operations run directly, no approval gate |

A preset bundles the two dials of `sandbox/mode` and `approval/policy` into one table:

- `workspace-write` (+ `ask`) is the **factory default**; `read-only` and `danger-full-access` require an explicit switch or configuration

- Switch with **`/permission`** during a session (the bare command reports the current value; with arguments it switches); a switch only logs an event, and only lands when the effective value actually changes

- When the two dials match no table entry, the current state shows as `custom` — **display-only, not selectable** (a derived state, not an optional preset)

## 2. Approval policies

The real enum is only **`ask` and `never`** (there is no `full-access`):

| Policy | Behavior |
| --- | --- |
| ask | Asks the user before executing the operation |
| never | Does not ask; executes directly (dangerous) |

The effective policy is the last `approval/policy` event (with config fallback); `never` rejects **before** entering interactive dispatch.

## 3. Configuration

```yaml
# ~/.dsh/settings.yaml

permission:

  defaultPreset: danger-full-access
```

Factory default is `workspace-write` (+ask); `danger-full-access` overrides here explicitly.

Environment-variable override (takes effect at startup):

```sh
export DSH_PERMISSION_MODE=workspace-write
```

**Override precedence** (high → low):

| Layer | Description |
| --- | --- |
| DSH_PERMISSION_MODE | Process-level fallback, rewrites the sandbox mode and derives the approval policy (danger-full-access → never, otherwise ask) |
| permission.defaultPreset | Default for future sessions; when omitted, back-derived from the composed sandbox/approval defaults |
| Factory default | workspace-write (+ ask) |

Key semantics: the default is **read only when a session is created**; creation **pins** `permission/preset`, `sandbox/mode`, and `approval/policy` into that session, and later changes never alter an existing session; a resumed seed session keeps its existing permissions. The preset table is **process-level**; adding or removing presets requires reloading the plugin.

## 4. Approval decision chain (what ask actually goes through)

Operations that need approval route the decision to `ctx.approval.request(req)`, a **one-shot authorization seam**:

| Return | Meaning |
| --- | --- |
| allowed-once | Approved this time, valid only for that request's action, forming no remembered rule |
| rejected | Rejected |
| cancelled | The request was aborted |
| unavailable | No answerer available; fails closed (treated as rejected) |

- **fail-closed**: when an answerer is missing or fails, it is treated as a rejection and nothing is allowed; the `ask` semantics is "ask only if there's an answerer, reject otherwise".

- Authorization is **one-shot**: the vocabulary is only `allowed-once`; there is no `allow-always`, no revocation, and no authorization store; the policy has only two levels, `ask`/`never`.

- The answerer is a cascade listener on `approval/request`; each deployment **composes exactly one terminal answerer**; the ACP automation bridge provides one-shot machine decisions for the sessions it owns.

- Audit events `approval/asked` + `approval/decided` **only write logs**; the model sees only the asking side's final tool result; the sandbox bash tool also goes through this seam on **escalation retries**.

## 5. Ask-the-user tool (ask_user_question)

Beyond "should this be approved", the model can also **proactively ask a person**: `ask_user_question` is a model-visible tool mounted on `ctx.userQuestions`, used to confirm, choose between two options, or fill in missing information.

- Parameters: `questions` (a non-empty array; each item requires `id` and `question`, with optional `header`, `options`, `multi_select`); put the recommended item first and append `(Recommended)` to its label.

- Return: `{ answers: [{ id, selected, custom? }] }` — `selected` is the chosen option label, `custom` is free text — multi-select as a supplement, single-select as an override.

- Constraints: pending questions **block** the tool call until a person answers; **subagents owned by other agents at runtime cannot ask a person** (`DELEGATED_CALLER`), so unresolved questions must be written into their own final result.

## 6. Permissions vs sandbox (easy to confuse)

|  | Permission | Sandbox |
| --- | --- | --- |
| What it governs | The operation's "mode profile" + approval | File boundary at command execution time |
| Layer | preset + approval policy | ctx.sandbox.confine |
| Example | Whether writing a file needs approval | Whether a command runs read-only |

**The preset selects the mode; the sandbox enforces the boundary.** Setting a preset to danger does not bypass the sandbox: commands still pass through `confine`. See [Sandbox and Security](../learn/core/sandbox-security.md).

## 7. Best practices

| Scenario | Suggestion |
| --- | --- |
| Daily use | workspace-write (write operations get confirmation, preventing mistakes) |
| Fully-automated batches / CI | Temporarily switch to danger-full-access |
| Sensitive projects | Keep a safe preset + combine with sandbox read-only |
| headless / unattended | Compose one terminal answerer or ACP machine decisions; otherwise ask always fails closed |

Permissions are the "preset", not the "sandbox". To actually restrict filesystem access, pair with sandbox configuration.

## Next steps

- [Sandbox and Security](../learn/core/sandbox-security.md): the real execution boundary

- [Configuration](../user-guide/configuration.md): where permissions are stored

- [Privacy](../user-guide/privacy.md): the data plane
