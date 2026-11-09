# Model Routing

- 
- Concepts Course
- Core Mechanisms
- Model Routing
On this page

# Model Routing

**One-liner**: the model layer is a capability seam: `ctx.llm` defines the provider-agnostic abstraction and streaming-call API, while adapters like `llm-deepseek` / `llm-pi-ai` provide implementations; routing decides which provider/model serves which agent, errors are traceable, and retries are configurable.

**Audit baseline 0.1.5-alpha.1 @ 5dda764ed3**: package names, APIs, config keys, and error codes are all verified point-by-point against the official source.

This is the page on "how models are called, and how to choose when multiple models are configured". After reading it you'll be able to configure providers correctly and understand a request's routing and failure classification.

## Contents

- [1. LLM layer structure](#1-llm-layer-structure)
- [2. The abstract service ctx.llm](#2-the-abstract-service-ctxllm)
- [3. Provider configuration: two shapes](#3-provider-configuration-two-shapes)
- [4. Multi-provider routing (not "automatic model switching")](#4-multi-provider-routing-not-automatic-model-switching)
- [5. One request: from agent/request to stream](#5-one-request-from-agentrequest-to-stream)
- [6. Error classification (provider-neutral codes)](#6-error-classification-provider-neutral-codes)
- [7. Retry policy: llm-retry](#7-retry-policy-llm-retry)
- [8. Credentials and attribution](#8-credentials-and-attribution)
- [9. Verification](#9-verification)
- [Next steps](#next-steps)

---

## 1. LLM layer structure

| Package | Role |
| --- | --- |
| llm/llm | abstract service ctx.llm: adapter registration, streaming calls, model resolution |
| llm/llm-deepseek | chat-completions adapter for the deepseek-official route (direct fetch + SSE) |
| llm/llm-pi-ai | multi-provider gateway (pi-ai catalogs + OpenAI-compatible endpoints) |
| llm/llm-retry | exact-provider retry executor |
| web/web-search-deepseek | web search, via a separate Anthropic-compatible endpoint |

`LlmRuntime` = an adapter registry + a single streaming-call API, interceptable with the `llm/stream` waterfall.

## 2. The abstract service ctx.llm

Core API (source `llm/README`):

| API | Purpose |
| --- | --- |
| registerAdapter(providers, adapter) | register one adapter instance for provider routes (all-or-nothing) |
| listProviders() | list registered provider routes |
| stream(options) | stream one model call, returning raw chunks (block-start/text-delta/tool-call-delta/…/finish) |
| resolveModelInfo(provider, model, signal?) | resolve the exact model identity + capability metadata (context/output-default/reasoning) |
| resolveCallConfig(config, signal?) | validate and materialize the adapter config's call defaults |
| prepareCall(config, signal?) | one exact-model lookup, returns a cancellable one-shot call, carrying the adapter registration and an immutable retry policy |

**Failure normalization**: final-adapter selection / synchronous dispatch / iteration / construction failures all converge into the stream protocol's single terminal state `finish { kind:'error'|'aborted', failure }`. Errors from `llm/stream` middleware, nested calls, adapter cleanup, and downstream consumers are **thrown** (plugin/consumer failures, not model-request results).

### Messages and content blocks

- `Message` is a shared immutable value: it must carry `MessageId`, role, content, and typed sources

- content-block types (`ContentBlockMap`): `text` / `reasoning` / `image` / `file` / `tool-call` / `tool-result`; new block types can be added via declaration merging

- **the core block set holds types every shipping path honors**: images and files are core blocks, projected by a capable adapter into route-specific request forms; other modalities still need your own block plus supporting adapter/UI/compaction support

- the stream is a raw-chunk protocol (`block-start`,`text-delta`,`reasoning-delta`,`tool-call-delta`,`block-end`,`usage`,`finish`); `BlockAssembler` is the only shared implementation, assembling chunks into blocks/messages

## 3. Provider configuration: two shapes

**`llm-deepseek` uses flat top-level fields**, not a nested `providers`:

```yaml
llm-deepseek:

  apiKeyEnv: DEEPSEEK_API_KEY

  # baseURL optional: when omitted, falls back to $DEEPSEEK_BASE_URL, then the built-in default api.deepseek.com

  thinking: enabled                   # enabled | disabled (disabled allows only reasoningEffort: off)

  reasoningEffort: high               # off | low | high | max (default high)
```

**`llm-pi-ai` uses a `providers` dictionary** to host multiple OpenAI-compatible endpoints:

```yaml
llm-pi-ai:

  providers:

    <provider-id>:

      apiKeyEnv: <env>

      api: openai-completions

      baseURL: <endpoint>

      models:

        - id: <model-name>
```

Key points:

- keys are resolved per request via `ctx.credentials`, falling back to the environment

- `llm-deepseek` is only a chat-completions adapter; the Anthropic endpoint belongs to `web-search-deepseek`, not inside `llm-deepseek`

- each provider route can carry its own `retryPolicy` (see below)

## 4. Multi-provider routing (not "automatic model switching")

Real "multi-model" comes from multiple providers + routing config:

| Config | Purpose |
| --- | --- |
| agent-default-model | deployment-default provider/model (shared by the web / headless / API entry points) |
| Models settings page | pick a model as needed |

**Correcting a misconception**: `@deepseek-ai/dsh-plan-mode` (the `/plan` command + `exit_plan_mode`) only maintains **planning-collaboration state + policy prompt sections**; it does **not** switch models and does **no** plan/execute dual routing. The earlier-documented "plan→planning model / after-approval→execution model" is a misunderstanding.

The **provable part** of routing resolution: compaction-summary-type auxiliary requests **reuse the session's last route-request header** (aligned with prefix-cache); capability reads fall back to agent options on demand. How exactly to configure `agent-default-model` is in [Configuration](../../user-guide/configuration.md).

## 5. One request: from agent/request to stream

The chain of one normal model call (echoing [Context](../../learn/core/context.md) and [Agent Main Loop](../../learn/core/agent-loop.md)):

The key to `prepareCall()`: it **keeps the exact adapter registration**, binding the same registration across async resolution / header recording / terminal dispatch: **HMR never mixes one adapter's capability result into another request** (like agent-loop's adapter-default marker).

`LlmCallConfig` is per-conversation state (`provider`/`model`/`reasoningEffort`/`temperature`/`maxTokens`/`stop`), recorded in request/header, not a silently adjustable one-shot knob.

## 6. Error classification (provider-neutral codes)

`LlmError` carries a stable `code` string, decoupled from `message`:

| code | Meaning | Relationship to retry |
| --- | --- | --- |
| NO_ADAPTER / DUPLICATE_ADAPTER | no adapter / duplicate registration for the same provider route | not retried |
| AUTH / RATE_LIMIT | auth / rate-limited | rate limits are retryable |
| CONTEXT_WINDOW_EXCEEDED | model context window exceeded | not retried |
| QUOTA | quota/balance/budget exhausted (non-transient) | not retried |
| EMPTY_RESPONSE | terminal stop but no content blocks | retried by default (safe) |
| INVALID_CREDENTIAL | credentials given but invalid (fix the value) | excluded from the default retryable set |
| MISSING_CREDENTIAL | credentials missing (go provide them) | not retried |
| SERVER / TIMEOUT / TRANSPORT | 5xx / timeout / transport failure | retried by default |
| INVALID_MODEL_INFO | adapter returned invalid model capability metadata | not retried |

The first four constants are named `CONTEXT_WINDOW_EXCEEDED_CODE`, `QUOTA_EXCEEDED_CODE`, `EMPTY_RESPONSE_CODE`, and `INVALID_CREDENTIAL_CODE` in the source; the runtime `code` value is the string shown above.

`errorChain(value)` renders the full cause chain (`TypeError: fetch failed` → underlying `ECONNREFUSED`/DNS/TLS), for diagnostics but **route by code, don't parse text**.

## 7. Retry policy: llm-retry

`dsh-llm-retry` does **not** wrap `ctx.llm.stream()`: each adapter call is still a single provider attempt; a retry **re-runs the failed step inside the same open turn**, so the retried request is reconstructable from the session log exactly like the original. It works on the `agent/request-error` waterfall in the agent loop.

- each provider has its own `retryPolicy`, captured at route registration and carried with the call; if a route is unmounted/replaced mid-flight, **an in-flight failed call keeps its serving policy**

- **normal mode** (default): `EMPTY_RESPONSE`/`RATE_LIMIT`/`SERVER`/`TIMEOUT`/`TRANSPORT` retried up to **5 times** (`maxRetries` defaults to 5), bounded exponential backoff (500ms→10s, +10% jitter); `maxRetries`/`retryableCodes`/`backoff` are configurable

- **always mode**: first asks downstream for recovery, then retries every model-request failure without an attempt limit; success / cancel / plugin unmount stop it

- before waiting, it appends a non-surface `llm/retry` event (with `retryId`/provider/mode/policy key/failure/delay); after the wait a `llm/retry-started`, and only at the very moment does it return `{ kind:'retry' }`; a valid in-bounds provider `Retry-After` replaces local backoff

```yaml
# retryPolicy in llm-deepseek's flat config

- name: '@deepseek-ai/dsh-llm-deepseek'

  config:

    apiKeyEnv: DEEPSEEK_API_KEY

    retryPolicy:

      mode: always

      backoff: { initialDelayMs: 1000, maxDelayMs: 30000, jitterRatio: 0.2 }

- name: '@deepseek-ai/dsh-llm-retry'   # executor, no config
```

- a retry rebuilds **the same explicit provider/model request** on **the same persisted history**; failed chunks never enter derived messages

- multi-provider `llm-pi-ai` puts `retryPolicy` in **each provider profile**

## 8. Credentials and attribution

- `normalizeApiKey`: strips leading/trailing whitespace, accepts non-empty printable ASCII (excluding spaces), otherwise rejects with `ApiKeyRejection`

- every product adapter sends a `User-Agent` on provider HTTP requests (`attributionHeaders`); white-label deployments can replace but cannot suppress it

- `agent-default-model`'s provider/model live in [Configuration](../../user-guide/configuration.md)

## 9. Verification

```sh
# list registered providers

dsh web --dump-config | grep -B2 -A6 "llm-"

# inspect one request's actual routing (request/header; default zstd-compressed, two-level directories)

zstdcat ~/.dsh/sessions/*/*/session*.jsonl.zstd | grep "request/header" | tail -1

# inspect retries (llm/retry events)

zstdcat ~/.dsh/sessions/*/*/session*.jsonl.zstd | grep -E "llm/retry" | head
```

## Next steps

- [Agent Main Loop](../../learn/core/agent-loop.md): how the loop calls `prepareCall`/`stream`

- [Context](../../learn/core/context.md): request/header and adapter-default

- [Multi-model](../../features/multi-model.md): `llm-pi-ai` multi-provider in practice

- [Configuration](../../user-guide/configuration.md): how provider config is stored
