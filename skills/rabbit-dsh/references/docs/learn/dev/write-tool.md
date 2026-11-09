# Write a Tool

- 
- Concepts Course
- Plugin Development
- Write a Tool
On this page

# Write a Tool

**In one sentence**: the core of tool definition is `parameters` (JSON-Schema) + `output.schema/render` + `execute(args, exec)`. Once registered, it automatically appears in the model's tool list. The standard entry point is `defineTool()` from `@deepseek-ai/dsh-tools`.

The second hands-on page. By the end you will be able to write a well-formed, safe tool for the model to call.

## Contents

- [1. A minimal tool (defineTool)](#1-a-minimal-tool-definetool)
- [2. What defineTool does for you](#2-what-definetool-does-for-you)
- [3. The output contract (must be well-formed)](#3-the-output-contract-must-be-well-formed)
- [4. execute(args, exec)](#4-executeargs-exec)
- [5. Registration rules (source conventions)](#5-registration-rules-source-conventions)
- [6. Scoped or not](#6-scoped-or-not)
- [7. Rendering to the model (mode)](#7-rendering-to-the-model-mode)
- [8. Where your tool gets wrapped (the pipeline)](#8-where-your-tool-gets-wrapped-the-pipeline)
- [9. The MCP tool bridge](#9-the-mcp-tool-bridge)
- [10. Best practices](#10-best-practices)
- [11. Verification](#11-verification)
- [Next steps](#next-steps)

---

## 1. A minimal tool (defineTool)

```ts
import { Context } from '@deepseek-ai/cordis'

import { defineTool } from '@deepseek-ai/dsh-tools'

export const name = 'tool-greet'

export const inject = ['tools']

export function apply(ctx: Context) {

  ctx.tools.register(defineTool({

    name: 'greet',

    description: 'Greet someone',

    parameters: {

      name: { type: 'string' },

      excited: { type: 'boolean' },

    },

    output: {

      schema: { type: 'string' },

      render(_args, value) {

        return [{ type: 'text', text: typeof value === 'string' ? value : 'ok' }]

      },

    },

    timeoutMs: 10_000,

    async execute({ name, excited }, exec) {

      return `${excited ? 'HELLO' : 'Hello'}, ${name}!`   // matches output.schema:{type:'string'}, returns a string

    },

  }))

}
```

`defineTool` only constructs a `ToolDefinition` (helping with type inference and field validation); **registration always goes through `ctx.tools.register()`**: MCP service-discovered tools and runtime dynamic tools are also registered by calling it.

## 2. What defineTool does for you

- **Typed parameters**: `parameters` is compiled into TS types, and `execute`'s `args` is precisely inferred

- **Automatic validation**: parameters are validated before execution; missing required / wrong type → `ToolArgsError` (`INVALID_ARGS`) follows the normal error path

- **Inferred output**: the return type and pure rendering are inferred from `output.schema`

The parameter DSL supports `string`/`number`/`integer`/`boolean`/`null`/`array`/`object`/`json`/`oneOf`; `additionalProperties: true|false` is explicit (raw JSON Schema keeps the open default).

## 3. The output contract (must be well-formed)

A tool **can only return** the single well-formed JSON value declared by `output.schema`; the registry validates, freezes, then renders.

| Field | Requirement |
| --- | --- |
| schema | Required, well-formed JSON-Schema, declares the "canonical form" of the return value |
| render(args, value) | Required, renders the canonical value into a ContentBlock |
| presentationMeta(args, value) | Optional, derives JSON metadata (persisted with tool/result) |

- **Missing/unsupported output → registration fails**; a missing render throws `TypeError`

- The canonical value returned by the executor is not given directly to the model: the model sees the `render` output + presentation

### Result shapes

```ts
// success

{ isError: false, value, content, meta?, additionalContexts? }

// failure (no value)

{ isError: true, error: { message }, content, meta?, additionalContexts? }
```

## 4. execute(args, exec)

`exec` (ToolRunContext) is the **only path** for a tool to access scope/session/ctx:

- **No** `exec.scope`/`exec.session`/`exec.ctx`: everything goes through **`exec.agent`** (`.id` / `.ctx` / `.session`), and the agent is injected by agent-loop

- `exec.signal`: AbortSignal, the cancellation contract (**must be forwarded/observed**; the registry has no hard kill)

- `exec.deferContext(UserMessage)` / result `additionalContexts(UserMessage[])`: returns context to the loop during execution

- `exec.concludeTurn()`: marks a successful result as terminating the current turn

## 5. Registration rules (source conventions)

| Rule | Description |
| --- | --- |
| output required | missing/unsupported → TypeError |
| Duplicate name | throws at the same level |
| timeoutMs | positive/finite; enforced by dsh-tool-call-timeout-policy (plugin id timeout-policy) wrapping tools/execute, not sent to the model |
| run_code | unconditionally reserved; cannot be registered/shadowed |
| Return value | register() returns () => void (an unload function) |
| isConcurrencySafe(args) | allows parallelism only if it returns exactly true; otherwise exclusive |

## 6. Scoped or not

| Registration location | Visibility |
| --- | --- |
| Ordinary plugin context | global registration |
| agent.ctx | that agent only; shadows a same-name global tool |

`ctx.tools.restrict(filter)` can add an allow/deny mask to inherited tools (does not affect your own registrations).

## 7. Rendering to the model (mode)

```yaml
tools:

  mode: native   # native (default) | ptc | both
```

Tool plugins need not care about rendering: the registry renders according to mode. `run_code` is the transport name for PTC mode, always reserved.

## 8. Where your tool gets wrapped (the pipeline)

```text
tools/pre-execute(gate) → guards → tools/execute(around) → your execute

 → tools/post-execute(rewrite) → finalizeContent → tools/result(observe)
```

See [Tool execution](../../learn/core/tools-execution.md).

## 9. The MCP tool bridge

`dsh-mcp-client` registers external MCP tools into `ctx.tools`, named `mcp__<server>__<raw>`, going through **the same pipeline**. Function names follow DeepSeek's constraints (≤64 characters, `[A-Za-z0-9_-]`). See [MCP](../../features/mcp.md).

## 10. Best practices

| Scenario | Use a tool / don't |
| --- | --- |
| Give the model a callable capability | use a tool |
| Several tools share logic | put the logic in a service, keep the tool a thin shell |
| Only in-process own-use is needed | a service/method suffices; a tool is unnecessary |
| Read a file | tool-fs may already be enough; don't reinvent it |

## 11. Verification

```sh
dsh web --dump-config | grep -A3 greet

# Call it once in a session, then look at the tool events (default zstd, two-level dirs, singular tool/ prefix)

zstdcat ~/.dsh/sessions/*/*/session*.jsonl.zstd \

  | jq -r 'select(.type | startswith("tool/"))' | tail -3
```

## Next steps

- [Write a service](../../learn/dev/write-service.md): not just a tool, a capability

- [Tool execution](../../learn/core/tools-execution.md): pipeline/cancellation/parallelism

- [Listen to events](../../learn/dev/listen-events.md): hook into the pipeline
