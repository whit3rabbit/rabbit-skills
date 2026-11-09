# DeepSeek Harness vs Claude Code vs Codex: What Actually Changes

This update rechecks DSH source only; competitor product descriptions retain the earlier comparison scope. npm `latest` / `next` resolve to `0.1.2-rc.1` and the `alpha` channel is `0.1.5-alpha.1`; see [status](../guides/deepseek-harness-status.md).

**The short answer**: all three can read code, run commands, call models, and edit files — the feature lists converge. The real dividers are **open source and auditability, model lock-in, cost model, and extension mechanism**. DeepSeek Harness is the only option that is fully open source (MIT), runs entirely on your machine, and works with any model endpoint — at the cost of a **Developer Preview** with breaking changes and a higher setup bar.

Facts on the DSH side are verified against the official source (`deepseek-ai/deepseek-harness`, baseline `0.1.5-alpha.1` @ `5dda764ed3`): commands, package names, and events are cross-checked against the TypeScript implementation. Claude Code / Codex are described from their public product status, not version-by-version.

## The short answer

|  | DeepSeek Harness | Claude Code | Codex |
| --- | --- | --- | --- |
| Origin | DeepSeek AI, open source (MIT) | Anthropic, commercial, closed | OpenAI, commercial (cloud + local CLI) |
| Model lock-in | None: any OpenAI-compatible endpoint | Defaults to Claude models | Defaults to OpenAI models |
| Where it runs | Local process (127.0.0.1:3080 by default) | Local CLI + remote sessions | Cloud workspaces + local CLI |
| Auditability | Full source available | Not available | Not available |
| Cost model | Model API costs only | Subscription or API billing | Subscription or API billing |
| Status | Developer Preview, breaking changes expected | Stable commercial product | Stable commercial product |

You don't need a feature checklist to decide — all three get work done. The questions that matter: **are you willing to treat the agent's implementation as a black box, and is a single model vendor acceptable?**

## Capabilities: convergent, not worth comparing line by line

| Capability | DeepSeek Harness | Claude Code | Codex |
| --- | --- | --- | --- |
| File / command tools | tool-fs / tool-bash | Built-in | Built-in |
| Session persistence | ~/.dsh/sessions/ (zstd, searchable) | Yes | Yes |
| Subagents | Yes | Yes | Yes |
| Skills / prompt packaging | skills system | Skills | Yes |
| MCP | Plugin-mounted | MCP client | Partial |
| Custom extension | Everything is a plugin (Cordis) | Hooks + plugins (preview) | Limited |
| Sandbox | Restricted by default (bwrap/Landlock) | Permission prompts | Cloud sandbox |
| Web UI | Yes (workspace-style) | No (terminal-first) | Cloud IDE |

Every DSH item links to a page: [Built-in tools](../features/tools.md), [Sessions](../learn/core/session.md), [Subagents](../features/subagent.md), [Skills](../features/skills.md), [MCP](../features/mcp.md), [Plugins](../user-guide/plugins.md), [Sandbox & security](../learn/core/sandbox-security.md), [Web UI](../learn/core/web-ui.md).

## The real dividers

### 1. Open source and auditability

The entire DSH runtime — agent loop, tool execution, sessions, sandbox, credential handling — lives in `deepseek-ai/deepseek-harness` under MIT. You can:

- audit what the model sees and what tools can touch ([Context](../learn/core/context.md), [Tool execution](../learn/core/tools-execution.md))

- fix bugs, patch, and re-compose ([Plugin anatomy](../learn/core/plugin-anatomy.md))

- run fully offline: endpoints, credentials, and sessions stay on your machine

Claude Code and Codex are closed products; behavior is observable only through docs and black-box testing. That matters little for individuals — it is a hard requirement for teams putting agents into production or compliance review.

### 2. Model lock-in

DSH's model routing is a plugin (`llm-pi-ai`, see [Multi-model](../features/multi-model.md)): any OpenAI-compatible endpoint works — DeepSeek, self-hosted gateways, other vendors, even multiple providers routed within one session. The official `deepseek-official` provider is the default, not a constraint.

Claude Code is built around Claude models (inside the paywall); Codex around OpenAI models. Third-party models are a side path in both.

### 3. Cost model

DSH: the software is free (MIT); you pay only model API costs. Local models work fine.

Claude Code / Codex: subscription or API billing that includes the product layer. For individuals, an all-in subscription is usually simpler; for high-volume teams, DSH's own routing can be cheaper.

### 4. Extension mechanism

DSH's architectural promise is **everything is a plugin** (Cordis): tools, services, events, and UI panels are all mountable via `dsh plugin add` (bundle) or repository manifests (`cordis.patch.yml`), see [Plugins](../user-guide/plugins.md).

Claude Code offers hooks / MCP / plugins (preview) as extension surfaces; Codex's surface is narrower. For deep customization, DSH's seam system (`ctx.llm`, `ctx.tools`, `ctx.sandbox`…) is the closest of the three to a framework.

## A decision rule

| Scenario | Choose | Why |
| --- | --- | --- |
| Audit the implementation, self-host, compliance | DSH | Full source, local run, 0600-managed credentials (Credentials) |
| Switch models / self-hosted gateway / local models | DSH | Plugin model routing, any OpenAI-compatible endpoint |
| Deep toolchain customization, plugin/skill distribution | DSH | Everything is a plugin; dsh-plugin ecosystem |
| Fastest start, fixed budget, vendor support | Claude Code / Codex | Zero config, stable, complete docs |
| Deep inside the OpenAI / Anthropic ecosystem | The matching vendor | Ecosystem integration > auditability |
| Comfortable with rc iteration and breaking changes | DSH | Developer Preview is the explicit trade |

## Frequently asked questions

### Is DeepSeek Harness an open-source replacement for Claude Code?

Positioning differs: Claude Code / Codex are products; DSH is an open-source framework plus a composable agent application. It can replace "getting work done with an agent," but you accept the rc cadence and wire up models yourself. To try it quickly, start with the [Quick Start](../getting-started/quickstart.md).

### Can DSH use Claude / GPT models?

Yes. `llm-pi-ai.providers` accepts any OpenAI-compatible endpoint; the official `deepseek-official` provider is just the default route (see [Multi-model](../features/multi-model.md)). Model names, endpoints, and keys are configured locally — no vendor lock.

### Can I migrate a Claude Code / Codex workflow to DSH directly?

Not seamlessly: the concept systems differ (plugins/Cordis composition vs hooks/MCP), and CLI and config formats differ. But the high-level capabilities (subagents, skills, MCP, session search) all have equivalents; migration cost is mostly re-configuration, not missing capabilities.

### Is DSH production-ready?

Depends on what "production" means: it listens on loopback by default (`127.0.0.1:3080`), writes credentials with 0600, and sandboxes tools by default ([Sandbox & security](../learn/core/sandbox-security.md)) — a solid privacy baseline. But the official status is Developer Preview: "there will be compatibility-breaking changes." Pin versions, read changelogs, and verify composition with `dsh web --dump-config` ([Boot config](../learn/core/boot-config.md)).

## Conclusion

Feature lists converge; they don't decide anything. The real variables: **open-source auditability, model freedom, transparent cost** (choose DSH) vs **out-of-the-box experience, vendor ecosystem, stable iteration** (choose Claude Code / Codex). DSH is in Developer Preview — the most freedom and the least stability. Pick it if you're comfortable following the source; pick a commercial product if you want zero-friction work today.
