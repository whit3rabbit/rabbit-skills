# Multi-Model Routing

**In one sentence**: one session can use multiple models: different tasks go to different providers/models. The capability comes from **multi-provider configuration** (the `llm-pi-ai` gateway) plus routing selection, not from an "auto model-switching" plugin.

## Contents

- [1. Core: differentiating models by provider](#1-core-differentiating-models-by-provider)
- [2. Two provider shapes](#2-two-provider-shapes)
- [3. Routing selection: agent-level default](#3-routing-selection-agent-level-default)
- [4. Provider spectrum](#4-provider-spectrum)
- [5. Discovering models](#5-discovering-models)
- [6. Typical uses of multiple models](#6-typical-uses-of-multiple-models)
- [7. Verification](#7-verification)
- [Next steps](#next-steps)

---

## 1. Core: differentiating models by provider

The real mechanism is **differentiating models by provider**, not plan/execute auto-switching:

- Configure multiple providers in `~/.dsh/settings.yaml` under `llm-pi-ai.providers` (each with its own `apiKeyEnv`/`baseURL`/`models`)

- Use `agent-default-model` (deployment default, shared by web / headless / API entry points) to select the `provider`/`model`

- Within a session, select a model as needed in the Models settings page

**Don't be misled**: `@deepseek-ai/dsh-plan-mode` (the `/plan` command) only maintains planning collaboration state + a policy prompt section; it **does not switch models and does no plan/execute dual routing**. Multi-model = multi-provider config, not switching.

## 2. Two provider shapes

| Package | Shape | Used for |
| --- | --- | --- |
| llm-deepseek | flat top-level fields (single provider) | official chat-completions |
| llm-pi-ai | providers: dictionary (multi-provider gateway) | connecting multiple OpenAI-compatible endpoints |

**Use `llm-pi-ai` to configure multiple third parties**:

```yaml
llm-pi-ai:

  providers:

    cpa:

      apiKeyEnv: CPA_API_KEY

      api: openai-completions

      baseURL: http://example.gw:8317/v1

      models:

        - id: gpt-5.6-sol

    another:

      apiKeyEnv: ANOTHER_API_KEY

      baseURL: https://another.endpoint/v1

      models:

        - id: some-model
```

## 3. Routing selection: agent-level default

```yaml
# per-agent default model

agent-default-model:

  provider: deepseek-official

  model: deepseek-v4-flash
```

`agent-default-model` is each agent's default `provider`/`model` (`@deepseek-ai/dsh-agent-default-model` requires both), overridable by the in-session Models settings. (`api-gateway` is the host/client RPC gateway and is unrelated to model routing; don't mistake it for a default-model config.)

## 4. Provider spectrum

| Type | Description |
| --- | --- |
| Official provider | deepseek-official (api.deepseek.com, chat-completions) |
| OpenAI-compatible | any compatible endpoint (added via the settings panel / llm-pi-ai) |
| Custom gateway | private/proxy endpoints (mind the plain-HTTP risk) |
| Web search endpoint | a separate Anthropic endpoint reusing the main key (web-search-deepseek) |

Two authentication boundaries matter:

- **OAuth-only providers are withheld from the selectable directory**: `llm-pi-ai` has no credential store and runs no login or refresh flow, so a route with OAuth but no API key fails with `Provider is not configured` before the request. An existing settings row remains editable or removable.

- **Provider-native discovery reads process environment only**: a route without a credential reference lets the provider resolve variables such as `AZURE_OPENAI_API_KEY`, `AWS_PROFILE`, and `AWS_ACCESS_KEY_ID`. It cannot see Harness-managed credentials and does not select a profile from `~/.aws/credentials` alone.

## 5. Discovering models

DSH provides endpoint model discovery: `ctx.llm.listModels(provider)` / `discoverModels(...)` asks a provider for its currently advertised models (see [model routing](../learn/core/llm-routing.md)). The Models settings page uses it to prefill candidate models when adding a provider.

## 6. Typical uses of multiple models

| Scenario | How |
| --- | --- |
| Official model for heavy work, cheap model for light tasks | set different agent-default-model per agent |
| Connect a self-built gateway / private endpoint | add one under llm-pi-ai.providers |
| Web search via a separate endpoint | web-search-deepseek reuses the main key and goes through anthropic/v1 (not the main baseURL) |
| Temporarily switch models in a session | the Models settings page |

## 7. Verification

```sh
# see the registered providers

dsh web --dump-config | grep -iE "llm-|provider"

# see which path one request actually took (request/header)

zstdcat ~/.dsh/sessions/*/*/session*.jsonl.zstd | grep "request/header" | tail -1
```

## Next steps

- [Model routing](../learn/core/llm-routing.md): the `ctx.llm` / adapter / URL request mechanism

- [Configuration](../user-guide/configuration.md): how provider config is persisted
