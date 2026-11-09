# Data and Privacy

**Short version**: source builds default to `FEEDBACK_ONLY` sharing when the user submits feedback. Official DeepSeek requests include plugin package names/versions by default; additional Session-log upload is off. These three controls are independent.

## Contents

- [Session telemetry (feedback-gated by default)](#session-telemetry-feedback-gated-by-default)
- [Two additional DeepSeek request metadata controls](#two-additional-deepseek-request-metadata-controls)
- [2. Anonymous user ID (.anonymous-user-id)](#2-anonymous-user-id-anonymous-user-id)
- [3. Session data](#3-session-data)
- [4. Credentials](#4-credentials)
- [5. Network egress list](#5-network-egress-list)
- [6. Best practices](#6-best-practices)
- [Next steps](#next-steps)

---

## Session telemetry (feedback-gated by default)

Official source `packages/bundle/base/cordis.patch.yml` defaults to `FEEDBACK_ONLY`, overridable with `DSH_TELEMETRY_MODE`. Ordinary chat does not continuously export OTel logs; `/feedback` shares the relevant log suffix:

- **Content**: a raw copy of the session log: full user/assistant messages, tool arguments and results, system prompts, and the local `session.cwd` path

- **Cadence**: batched export (configured by `scheduledDelayMillis` etc. in the OTel SDK processor, adjustable)

- **Endpoint**: the deployer-level default is `https://dsh-otel-collector.deepseeksvc.com/v1/logs` (also aliases `https://harness-telemetry.deepseeksvc.com/v1/logs`; overridable with `DSH_TELEMETRY_OTLP_URL`; in OTel `exporter.url` is required with no default)

- **Identity**: the anonymous `user.id` (see below)

### Three modes

`session-telemetry-otel`'s `mode` decides whether the telemetry seam follows session events, only replays at recording feedback, or stays local:

| mode | What gets reported |
| --- | --- |
| FULL | When explicitly selected, every projected record (including lifecycle ops) is handed to the OTel SDK immediately |
| FEEDBACK_ONLY | Shipped composition default. On each feedback/record, replays, projects, and redacts the log suffix before that event; later records wait for the next feedback, or stay local if none comes |
| DISABLED | No pipeline is constructed, no record leaves the process; feedback stays in the local session log |

The upload modes (`FULL` / `FEEDBACK_ONLY`) both require `exporter.url` (no default; must resolve to http(s)); under `DISABLED` the exporter can be omitted and is ignored. All three modes share one `sharing` disclosure (`full` / `feedback-only` / `disabled`), and `/feedback` confirmation reports how the session is shared accordingly.

### Exporter configuration

```yaml
# Override by id in the deployer-level composition (see Configuration)

- id: session-telemetry-otel

  name: '@deepseek-ai/dsh-session-telemetry-otel'

  config:

    mode: FULL

    shutdownTimeoutMillis: 3000     # optional, outer DSH shutdown deadline, default 3000ms

    exporter:                       # passed verbatim to the OTLP/HTTP log exporter

      url: https://collector.example.com/v1/logs

      headers:

        authorization: !!js `Bearer ${process.env.OTLP_TOKEN}`

    processor: {}                   # optional, passed verbatim to BatchLogRecordProcessor
```

Both `exporter` and `processor` are **passed through wholesale** to the SDK: `headers`, `timeoutMillis`, `compression`, `keepAlive`, etc. reach the exporter; batching, export cadence (`scheduledDelayMillis`), retries, queue limits, and the drop-policy under sustained failure are all SDK behavior, tuned via `processor`. Field mapping: `time` → `timestamp`/`observedTimestamp`, `severity` → `severityNumber`/`severityText` (INFO 9 / WARN 13 / ERROR 17), `body` → the structured log body, `attributes` passed through as-is; the receiver deduplicates by `(session.id, event.seq)` and can alert by severity.

The seam **carries no redaction rules**: with no `session-telemetry/record` listener, the raw captured copy is what's uploaded. Deployments crossing trust boundaries must mount their own redaction rules (see [Session System](../learn/core/session.md)). `FULL` redacts at append time; `FEEDBACK_ONLY` keeps no telemetry copy and redacts with the currently-mounted rules when recording feedback.

### Disabling telemetry

```sh
export DSH_TELEMETRY_DISABLED=1   # any non-empty value, including 0 / false
```

Restart `dsh` for it to take effect; disabling affects no functionality. You can also use OTel's `mode: DISABLED`.

## Two additional DeepSeek request metadata controls

| Plugin / setting | Default | Effect |
| --- | --- | --- |
| plugin-package-inventory-deepseek.enabled | true | dsh_plugin_packages carries active plugin package names and versions on official DeepSeek requests |
| session-log-deepseek.enabled | false | Opting in sends canonical Session-log suffixes through dsh_session_log |

These are API metadata, separate from OTel, and add no model-input tokens. Disabling OTel does not remove them. Disable both shipped rows with:

```yaml
- id: plugin-package-inventory-deepseek

  config:

    enabled: false

- id: session-log-deepseek

  config:

    enabled: false
```

Load with `dsh web --patch ./privacy.yml` and inspect the effective composition with `--dump-config`. Source: the `Config` declarations in `packages/llm/plugin-package-inventory-deepseek/src/index.ts` and `packages/session/session-log-deepseek/src/index.ts`.

## 2. Anonymous user ID (.anonymous-user-id)

- File: `~/.dsh/.anonymous-user-id`, whose content is a random UUID

- Generation rule: **not** derived from any identifiable source such as hostname, NIC, or git remote: **purely random**

- **Deleting the file resets the identity** (a new UUID is generated at the next startup)

The same id appears in three places, letting the receiver correlate without building its own identity:

| Use | Form |
| --- | --- |
| Telemetry | user.id on the OTel Resource, used for aggregate statistics and issue triage |
| Feedback confirmation | the /feedback confirmation text carries the same value |
| DeepSeek requests | dsh-llm-deepseek sends it in the x-deepseek-harness-user-id header |

Two easily-misunderstood points:

- `DSH_TELEMETRY_DISABLED` **only stops telemetry export**, not the feedback confirmation or the DeepSeek request header — disabling telemetry is not disabling identity correlation

- The id reaches DeepSeek only as **HTTP transport metadata**; it never enters the request body, prompts, or any model-visible content

In-process it is memoized by file path for the process lifetime; the first write uses exclusive creation and concurrent losers adopt the persisted winner; if the write fails (e.g. home not writable), it falls back to a process-local UUID without blocking telemetry or feedback.

## 3. Session data

- All session logs live locally in `~/.dsh/sessions/` (zstd-compressed by default; the current generation is `session.v3.jsonl.zstd` while older sessions keep `session.jsonl.zstd`, in the two-level `--<cwd>--/<id>/` directories), including conversations, tool calls, and working-directory paths

- Sessions persist locally; deleting the directory clears them

Want to `head`/`jq` the plaintext directly? Configure `compression: 'none'` or `zstdcat` first (see [Session System](../learn/core/session.md)).

## 4. Credentials

| File | Content | Permissions |
| --- | --- | --- |
| ~/.dsh/.credentials.yaml | Managed structured credentials | 0600 (0700 directory) |
| ~/.dsh/.env | Env-layer fallback | Permissions self-managed |

Don't commit credentials into a repository; the managed `.credentials.yaml` is written atomically at 0600 by DSH, while `.env` is an ordinary env layer whose permissions are your own responsibility.

## 5. Network egress list

| Destination | Use | Can be disabled |
| --- | --- | --- |
| api.deepseek.com | LLM calls (chat-completions + anthropic/v1) | Bypassable by switching provider |
| dsh-otel-collector.deepseeksvc.com / harness-telemetry.deepseeksvc.com | Session and host telemetry | DSH_TELEMETRY_DISABLED=1 |
| Custom provider endpoints | The model gateways you configure | Controlled at the configuration level |

## 6. Best practices

- Before using on sensitive projects, evaluate the telemetry policy (or just disable it)

- Watch out for the network behavior of third-party plugins (telegram/zotero etc. have outbound capability)

- Deleting `.anonymous-user-id` resets anonymity but **does not affect** the telemetry switch

- Session logs are zstd-compressed by default; redact before backup/sharing

## Next steps

- [Session System](../learn/core/session.md): how sessions are stored

- [Environment Variables](../reference/env-vars.md): telemetry-related variables

- [Permissions](../user-guide/permissions.md): the permissions side
