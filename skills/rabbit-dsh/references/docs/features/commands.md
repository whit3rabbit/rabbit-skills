# Custom Commands and User Interaction

Beyond tools (which the model calls itself), DSH supports two kinds of **human reach-outs**: **slash commands** (the user types `/xxx` in the UI) and **asking the user questions** (asking a human when the model is stuck).

## Contents

- [1. Custom commands (ctx.commands)](#1-custom-commands-ctxcommands)
- [2. Asking the user questions (ask_user_question)](#2-asking-the-user-questions-ask_user_question)
- [Commands vs tools vs questions](#commands-vs-tools-vs-questions)
- [Verification](#verification)
- [Next steps](#next-steps)

---

## 1. Custom commands (ctx.commands)

`@deepseek-ai/dsh-commands` is a plugin-owned **human command registry**, consumed by interactive UI adapters. A plugin registers a command, and users trigger it by typing `/command-name` in the Web UI.

```ts
import { Context } from '@deepseek-ai/cordis'

export const name = 'command-demo'

export const inject = ['commands']

export function apply(ctx: Context) {

  ctx.commands.register({

    name: 'deploy',                   // lowercase command name

    description: 'Deploy the current branch',

    input: { hint: 'optional freeform input hint' },

    recordInput: true,                // default true; set false when authoritative-domain events are held

    handler: async ({ agent, rawInput, signal }) => {

      // rawInput = exact text after the command name, including separator whitespace

      signal.throwIfAborted()

      return { kind: 'success', text: `Deploy triggered for ${agent.id}: ${rawInput.trim()}` }

    },

  })

}
```

Key points (source README):

- `parseCommand()` recognizes: byte 0 is `/`, the lowercase name contains `[a-z0-9_-]`, followed by end-of-line or whitespace; all bytes after the name are the `rawInput`

- Same-level duplicates → registration fails; registration under `agent.ctx` **shadows** a same-named global command (per agent scope)

- Lifecycle is recorded into the receiving agent's session log as a read-only **`command/run` → `command/done` event pair** (each is an independent append, not wrapped by a turn)

- The result is rendered directly by the adapter and **does not enter the model history**

- Registration/deregistration notifies `commands/change` observers so online adapters refresh

`dsh`'s base already mounts this service, and the Web client uses it too; custom interaction compositions and ACP automation do not provide a command adapter by default.

### Built-in slash commands

`dsh` ships several global commands (all registered via `ctx.commands`, human-triggered, not model turns):

| Command | Purpose | Details |
| --- | --- | --- |
| /goal | View / create / edit / pause / resume long-term goals | Goals, Jobs, and Todos |
| /plan [message] | Enter planning collaboration mode (does not switch model) | Agent Presets and Personas |
| /feedback | Append a feedback record | Feedback |
| /compact | Manually trigger a context compaction | Context system |
| /permission [preset] | Inspect or switch the permission preset | Permissions |
| /export | Download a ZIP of the current Web session and descendants; accepts no path argument | Web UI Architecture |

`/export` is mounted only by the Web composition. After a successful local acknowledgement, the submitting browser requests `GET /api/session.export?sessionId=<id>&includeDescendants=true` and delegates the destination to the browser download manager. The Header's **Session log** button uses the same controller.

The registry itself **submits nothing to the model**: command input, metadata, and direct output do not enter model requests and do not affect the cache; only work that command producers explicitly dispatch through the `Agent` scheduling counts toward tokens (such as the optional message of `/plan`).

## 2. Asking the user questions (ask_user_question)

`@deepseek-ai/dsh-tool-ask-user` lets the model ask a human a concise question when it needs **confirmation, a choice, or missing information**.

```text
ask_user_question

  questions  required, non-empty array

  id         required stable id per question (echoed in the answer)

  question   required question text

  header     optional short heading

  options    optional options, each { label, description }; recommended ones first with (Recommended)
```

The corresponding service seam is `ctx.userQuestions` (see `tool-ask-user` in [Built-in tools](../features/tools.md)).

```yaml
# shape of a typical question

questions:

  - id: confirm-deploy

    question: Confirm deploying the current branch to production?

    options:

      - { label: Deploy (Recommended), description: triggers the production release flow }

      - { label: Dry-run only, description: rehearses without actually releasing }
```

## Commands vs tools vs questions

|  | Who triggers | Typical use |
| --- | --- | --- |
| Tools | model | performing operations |
| Commands | user (typing /) | letting a human proactively trigger an operation |
| ask_user | model | model needs a human to confirm / choose / supply info |

The three are complementary: commands give a human a stable entry point to "jump in," and questions let the model pause and ask a human at critical points.

## Verification

```sh
# See command lifecycle in the session log

zstdcat ~/.dsh/sessions/*/*/session*.jsonl.zstd | grep -E '"command/' | head

# Confirm the command service is mounted

dsh web --dump-config | grep commands
```

## Next steps

- [Built-in tools](../features/tools.md): where ask_user_question sits in the tool list

- [Writing a tool](../learn/dev/write-tool.md): adding auto-executed tools for the model
