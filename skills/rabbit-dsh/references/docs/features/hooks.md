# Hooks Bridge (Claude / Codex)

**In one sentence**: DSH's core extension surface is **typed interception points** (native plugins suffice); `hooks-claude-code`/`hooks-codex` are **bridge plugins**: they run your existing Claude Code / Codex `hooks.json` shell hooks verbatim on those same interception points, keeping compatibility with the legacy ecosystem.

If you used Claude Code / Codex to configure a bunch of shell hooks (pre-commit, gates, notifications…), and you do not want to rewrite them for DSH, `dsh-hooks-*` lets them keep running.

## Contents

- [1. Two concepts, don't conflate them](#1-two-concepts-dont-conflate-them)
- [2. Packages](#2-packages)
- [3. Configuration: connecting a Claude hooks.json](#3-configuration-connecting-a-claude-hooksjson)
- [4. Hook protocol shape](#4-hook-protocol-shape)
- [5. Interception point → decision mapping](#5-interception-point-decision-mapping)
- [6. Difference from tools gating](#6-difference-from-tools-gating)
- [7. When to use which](#7-when-to-use-which)
- [8. Verification](#8-verification)
- [Next steps](#next-steps)

---

## 1. Two concepts, don't conflate them

|  | Native plugin (recommended) | Hooks bridge (compatibility) |
| --- | --- | --- |
| What it is | An ordinary Cordis plugin mounted on DSH's typed interception points | A bridge translating the "external shell-hook protocol" to those same interception points |
| Experience | Typed returns, no serialization boundary | Goes through subprocess shell hooks |
| When to use | New extensions | Existing Claude/Codex hook configs you want to keep compatible |

Source quote: native plugins **can do everything the bridge does, more powerfully**. The bridge exists only as a **compatibility path**; anything you write fresh should be a native plugin.

## 2. Packages

| Package | Role |
| --- | --- |
| dsh-hook-protocol | Shared shell-hook wire protocol (matcher, stdlib codec, ctx.shell execution, hook/* events) |
| dsh-hooks-claude-code | Claude Code hook bridge (CC dialect: stdin payload, ${CLAUDE_PLUGIN_ROOT}/${CLAUDE_PROJECT_DIR} substitution) |
| dsh-hooks-codex | Codex hook bridge (Codex dialect) |

`hook-protocol` is **not a plugin**: it registers and injects nothing; it is just a library shared by both bridges.

## 3. Configuration: connecting a Claude hooks.json

```yaml
# cordis.yml / patch

- id: hooks-claude-code

  name: '@deepseek-ai/dsh-hooks-claude-code'

  config:

    configPath: ./.claude/hooks.json   # required: hooks.json or a settings with a hooks key

    pluginRoot: ./.claude/plugins/my   # optional: substitutes ${CLAUDE_PLUGIN_ROOT}

    projectDir: .                      # optional: substitutes ${CLAUDE_PROJECT_DIR}; default = session cwd

    defaultTimeoutMs: 600_000          # optional: the default when a hook sets no timeout (CC default)

    stderrSummaryMaxChars: 500         # optional: char cap for the stderr summary persisted in hook/result events
```

The Codex bridge config has the same shape, with one extra optional `model` (stamped on each stdin payload); `configPath` usually points to `./.codex/hooks.json`.

- Supports the command-hook **subset** that CC/Codex support; mapping: hook-neutral results → harness typed Decisions (allow/deny/ask, etc.); `hook/*` session events record hook executions

- Config parses **once** at mount time; `configPath` is **process-level** (relative paths resolve against the startup cwd, with no per-session discovery); read/parse failures are **isolated** (logged, zero hooks registered)

- Only `type: 'command'` shell hooks run; handlers like `http`/`mcp_tool`/`prompt`/`agent` are parsed then skipped with a warning

## 4. Hook protocol shape

The two bridges share one set of protocol primitives, each handling only its dialect differences:

| Concern | Shared library (dsh-hook-protocol) | Bridge (-claude / -codex) |
| --- | --- | --- |
| Matcher validation/matching | matcherDiagnostic / matchesMatcher | chooses mode: claude = literal or regex, codex = always regex |
| Running hooks | runHook: stdin payload + env via ctx.shell | builds each event's stdin payload + dialect env |
| Decoding/merging | parseHookOutput → HookOutput; mergeHookOutputs → most-restrictive result | maps neutral results to interception-point typed Decisions |
| Persistent recording | hook/invoked / hook/result session events | invokes them around each call |

Key semantics:

- **exit code 2 = blocking** (with stderr); other failures are non-blocking errors.

- **Merging takes the most restrictive**: `deny > ask > allow`; the first `continue:false` sticks; `additionalContext`/`systemMessages` accumulate in order.

- **matcher**: `claude` mode treats pure `[A-Za-z0-9_|]+` as literal (with `|` exact alternation), everything else as regex; `codex` mode is always unanchored regex.

- **`hook/*` events** are log-only (like `compaction/*`), not `SurfaceEventType`: the paired `hook/invoked` and `hook/result`, stderr summary truncated at `stderrSummaryMaxChars`.

## 5. Interception point → decision mapping

The Claude bridge maps CC hooks to DSH interception points:

| CC hook | DSH interception point | Mapping |
| --- | --- | --- |
| SessionStart | agent/session-start (emit) | additionalContext → agent.inject() into the new session |
| UserPromptSubmit | agent/pre-step (waterfall) | deny → reject; additionalContext only → next() delegation then appended context |
| PreToolUse | tools/pre-execute (waterfall) | deny → deny; ask → ask |
| PostToolUse | tools/post-execute (waterfall) | deny → block + feedback |
| Stop | agent/turn-stopping (serial) | a blocking Stop hard-pushes the next step via steer() |
| SubagentStart | subagent/start (emit) | additionalContext → injects into the live in-process subagent |
| SubagentStop | subagent/end (emit) | observe only |

The Codex bridge implements 5 of the 10 points (`PreToolUse`/`PostToolUse`/`SessionStart`/`UserPromptSubmit`/`Stop`), using `block` (exit 2) in place of `deny`, with no `allow`/`ask` for `PreToolUse`.

- Emit points (`SessionStart`/`SubagentStart`/`SubagentStop`) **run in isolation**; no interception point is waiting on them; the run chain is traced, and on dispose it first aborts still-running hook processes, then drains continuations.

- Matcher bodies: tool names (`PreToolUse`/`PostToolUse`), session source (`SessionStart`), the constant `agent_type=general-purpose` (`SubagentStart`/`SubagentStop`); `UserPromptSubmit`/`Stop` ignore the matcher.

- Multiple hooks on the same interception point execute **serially in config order** and fold to the most restrictive.

## 6. Difference from tools gating

The two ultimately land on the same interception points, but **don't conflate them** (consistent with [listening to events](../learn/dev/listen-events.md)):

|  | Native gating (recommended) | Hooks bridge |
| --- | --- | --- |
| Implementation | ctx.on('tools/pre-execute', ...) returns PreToolDecision | translates an external shell hook's stdout/exit code into the same decision |
| Type | typed return values, no serialization boundary | serialization through subprocess + stdin/stdout |
| When to use | configuring new gates/interceptions on DSH | existing Claude/Codex hooks.json you want to keep compatible |

## 7. When to use which

| Scenario | Use |
| --- | --- |
| You already have a large set of Claude/Codex hooks and want a seamless migration | hooks bridge |
| Configuring new gates/interceptions on DSH | native plugins (tools pipeline, agent events) |
| Wiring up @dsh-external community hooks | install as a plugin |

## 8. Verification

```sh
# check whether the hooks bridge is mounted

dsh web --dump-config | grep -iE "hook"

# see hook executions in the session

zstdcat ~/.dsh/sessions/*/*/session*.jsonl.zstd | grep -E '"hook/' | head
```

## Next steps

- [Plugin anatomy](../learn/core/plugin-anatomy.md): how native extensions are made

- [Listening to events](../learn/dev/listen-events.md): hooking interception points

- [Tool execution](../learn/core/tools-execution.md): the tools pipeline is the main interception point
