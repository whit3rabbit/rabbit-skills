# Agent Turn And Step Lifecycle

This sequence is the visual companion to [architecture.md](./index.md#turn-flow). It keeps durable replay facts on `session/event` and live control/status on `agent/*`.

The `assistant/message` event records every successful provider call, including content-less and `max-tokens` finishes, and embeds the exact compact timed stream. Empty content stays out of derived history. A failed, retried, cancelled, or stream-error attempt that reaches settlement without a surface message records its stream as `assistant/attempt`. Live `agent/assistant-stream` chunk frames are transient; replay reads either durable settlement, and a hard process loss before settlement leaves no durable attempt stream.

`dsh-compaction-basic` uses `agent/pre-step` for pressure before request derivation and `agent/request-error` only for canonical context overflow. Once either trigger qualifies, optional tool-result pruning runs before summary selection. Recovery runs within the open step and retries only when pruning or summarization advances the surface replacement generation; otherwise the original request error remains authoritative. Each retry prepares its call and reconciles the retained rendered assembly before request derivation, without repeating assembly, pre-step, or user admission.

The returned `agent/pre-step` decision is authoritative; listeners wrapping `next()` preserve downstream messages and `startsRequestSeries` unless replacement is intentional. Steering and injected context pass through the same waterfall after a later claim operation takes their next-step batch.

SDK users that need replayable transcript data should consume `session/event`; `agent/*` is the live coordination API for queue/status, prompt interception, request construction, steering, continuation, and errors.

Maintenance mode: curated Mermaid sequence; exact event signatures live in the generated Cordis catalog.
