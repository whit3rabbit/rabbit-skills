# Best Coding Harness for DeepSeek: Model-First Selection

This update rechecks DSH source only; competitor product descriptions retain the earlier comparison scope. npm `latest` / `next` resolve to `0.1.2-rc.1` and the `alpha` channel is `0.1.5-alpha.1`; see [status](../guides/deepseek-harness-status.md).

**The short answer**: if the model is already decided — DeepSeek — the selection simplifies a lot. **DeepSeek Harness (DSH) is the only coding agent that treats DeepSeek models as first-class**: the official `deepseek-official` provider works right after you paste an API key, it is MIT-licensed and fully auditable, and it runs locally. Claude Code and Codex can also point at third-party endpoints, but that is a side path, not the primary one — and they are closed.

This page differs from [DSH vs Claude Code vs Codex](../guides/dsh-vs-claude-code-vs-codex.md): that one compares the agents themselves; this one starts from **"I've decided to use DeepSeek models"** and works backwards to the least-friction harness. DSH facts are cross-checked against the official source (`0.1.5-alpha.1` @ `5dda764ed3`).

## Pick the model first, then the harness

Most selection articles start from the harness ("which agent is best"). For DeepSeek users that is the wrong order. The model dominates cost and results; the harness is the shell. Ask:

- **Is the model DeepSeek?** (cost / quality / data-locality considerations)

- Then: which harness has **native support** for DeepSeek models, not just "can be configured"?

In this order, the answer converges fast.

## The candidates

|  | DeepSeek Harness | Claude Code | Codex |
| --- | --- | --- | --- |
| DeepSeek model support | Native: official deepseek-official provider, paste key and go | Side path: custom OpenAI-compatible endpoint, not the official primary | Side path: custom endpoint, degraded experience |
| Default model route | deepseek-v4-flash (see Multi-model) | Claude models | OpenAI models |
| Open source / auditable | MIT, full source | Closed | Closed |
| Where it runs | Local process (127.0.0.1:3080) | Local CLI + remote | Cloud + local CLI |
| Cost | Model API only | Subscription / API | Subscription / API |
| Extension | Everything is a plugin (Cordis) | Hooks / MCP / plugins | Limited |

"Can point at a third-party endpoint" and "native support" are different things: DSH's `llm-pi-ai` makes model routing a plugin ([Multi-model](../features/multi-model.md)), and the DeepSeek official provider is a shipping default — docs, examples, and `settings.yaml` defaults revolve around it. Third-party endpoints in Claude Code / Codex have no official guarantee and can shift with any update.

## A decision rule

| Situation | Choose |
| --- | --- |
| Model decided (DeepSeek), want zero-config start | DSH: npx @deepseek-ai/dsh web, paste key, go (Quick Start) |
| Need open source, auditability, local data | DSH (MIT; 0600-managed credentials, Credentials) |
| Mixing models (DeepSeek + others) | DSH: multi-provider routing within one session |
| Must stay inside the Anthropic / OpenAI ecosystem | Claude Code / Codex (DeepSeek as a fallback) |
| Want vendor-backed stability | Claude Code / Codex (accept closed source + subscription) |
| Comfortable with rc breaking changes | DSH (Developer Preview; pin versions, read changelogs) |

## Frequently asked questions

### Which DeepSeek model does DSH use by default?

The official `deepseek-official` provider routes to `deepseek-v4-flash` by default; change it in Settings → Models or `settings.yaml` (see [Multi-model](../features/multi-model.md)).

### Do I have to use DSH to use DeepSeek models?

No. Claude Code and Codex can both point at DeepSeek via OpenAI-compatible endpoints, and each has a more mature ecosystem. The difference: that is a side-path configuration (no official guarantee, subject to change), while DSH is the native primary path. Choose DSH if "officially supported" matters; stay where you are if ecosystem maturity matters more.

### Is it really "model API costs only"? Does DSH itself cost money?

DSH itself is MIT-licensed and free (`deepseek-ai/deepseek-harness`). You pay only model API costs — or point it at a self-hosted gateway or local models ([Multi-model](../features/multi-model.md)).

### What should a team running DSH with DeepSeek watch out for?

Three things: pin the version (breaking changes during rc, see the [status page](../guides/deepseek-harness-status.md)); use the managed credential layer (`.credentials.yaml`, 0600, [Credentials](../user-guide/credentials.md)); keep the restricted sandbox until tool permissions are evaluated ([Sandbox & security](../learn/core/sandbox-security.md)).

## Conclusion

Model decided (DeepSeek) → harness of choice is DSH: native model support + open source + local + zero software cost, four hard advantages. Its weaknesses (rc instability, younger ecosystem) are offset by pinning versions and reading changelogs. If you cannot tolerate any instability, the side-path configuration of a closed product remains an option.
