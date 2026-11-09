# Environment Variables

On this page

# Environment Variables

## 1. Paths

| Variable | Default | Purpose |
| --- | --- | --- |
| DSH_HOME | ~/.dsh | Harness home directory (credentials, profiles, sessions, source) |

`DSH_HOME` is the resolution entry point for the single-root Harness home. Priority (high → low): explicitly configured path → `$DSH_HOME` → `~/.dsh`; every shell tool invocation also receives the resolved absolute `DSH_HOME`.

## 2. Behavior Control

| Variable | Default | Purpose |
| --- | --- | --- |
| DSH_TELEMETRY_DISABLED | unset | Any non-empty value (including 0/false) disables the telemetry line before startup |
| DSH_TELEMETRY_MODE | FEEDBACK_ONLY | Shipped base defaults to feedback-gated sharing; accepts FULL / FEEDBACK_ONLY / DISABLED; the disable switch wins |
| DSH_TELEMETRY_OTLP_URL | https://dsh-otel-collector.deepseeksvc.com/v1/logs | Overrides the telemetry OTLP reporting endpoint (for local development) |
| DSH_PERMISSION_MODE | workspace-write | Process-level fallback for the permission preset: rewrites both the sandbox mode and the approval policy (danger-full-access → never, otherwise → ask) |
| DSH_TOOLS_MODE | unset (= native) | Process-level switch for PTC mode; values native / ptc / both; any other value fails at startup |
| DSH_WEB_URL | — | Canonical Web GUI address (injected at runtime, not a user setting) |

`DSH_PERMISSION_MODE` and `DSH_TOOLS_MODE` are both **process-level temporary switches**: the former is a fallback to the composition default (see [Permissions](../user-guide/permissions.md)), the latter selects Web/headless tool presentation; migrate the old `code` value to `ptc`.

## 3. Provider Credentials

| Variable | Purpose |
| --- | --- |
| DEEPSEEK_API_KEY | Official provider credential (can also be stored in ~/.dsh/.env) |
| DEEPSEEK_BASE_URL | Official endpoint fallback (only effective for the trusted tier) |
| DEEPSEEK_SEARCH_BASE_URL | Web search endpoint override |
| Custom DP_* etc. | apiKeyEnv reference for custom providers |

The actual provider variables are governed by the `apiKeyEnv` you configure in `llm-pi-ai.providers` / `llm-deepseek` (see [Multi-model](../features/multi-model.md)).

## 4. Credential Files

| File | Content | Permissions |
| --- | --- | --- |
| ~/.dsh/.env | DEEPSEEK_API_KEY=... and so on (environment-tier fallback) | self-managed |
| ~/.dsh/.credentials.yaml | structured credentials | 0600 |

`ctx.credentials` resolves these per operation, referencing secrets rather than storing values (see [Credentials](../user-guide/credentials.md)). Resolution priority: process environment → `.credentials.yaml` → cwd `.env` → `$DSH_HOME/.env`; managed documents are never materialized into `process.env`, and both `.env` files are ordinary startup environment layers.

## 5. Runtime-Injected DSH_* (Not User Settings)

Each model shell invocation receives a set of trusted `DSH_*` environment variables collected by the host/registry — these are **not** variables you can set directly, but facts injected at runtime:

| Variable | Value | Injected by |
| --- | --- | --- |
| DSH_HOME | resolved absolute Harness home | registry built-in |
| DSH_SHELL | 1 | registry built-in, marks managed subprocesses |
| DSH_SESSION_ID | current agent session id | only invocations with an agent |
| DSH_SESSION_JSONL | absolute path of the current session JSONL | when the persistence seam is provided |

`DSH_WEB_URL` is also injected the same way by the Web host's shell-env contributor. The whole `DSH_*` namespace is type-restricted and is a trusted overlay for the shell tool, separate from ordinary `env`; `DSH_HOME`/`DSH_SHELL`/`DSH_SESSION_ID` are registry-reserved built-in keys that `list()` does not enumerate.

## 6. Notes

- **Telemetry anonymous identity**: exported records use `$DSH_HOME/.anonymous-user-id` (a random UUID) as the Resource anonymous user id; deleting this file resets the identity.

## Next Steps

- [Privacy](../user-guide/privacy.md): .env / .credentials.yaml

- [Configuration](../user-guide/configuration.md): provider/credential references

- [Command line](../user-guide/cli.md): common variables
