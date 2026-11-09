# DeepSeek Harness (DSH) — Master Environment Variables Guide

This guide is an exhaustive, source-audited reference of all environment variables recognized, read, or injected by **DeepSeek Harness (`dsh`)**, based on analysis of the official repository (`deepseek-ai/deepseek-harness`). It documents resolution precedence, the bootstrap security denylist, Chinese cloud provider settings, and configuration for developers setting up DSH.

---

## Contents

- [1. Resolution Precedence & Layering](#1-resolution-precedence--layering)
- [2. Bootstrap Security Denylist (Anti-Exfiltration Boundary)](#2-bootstrap-security-denylist-anti-exfiltration-boundary)
- [3. Master Environment Variable Reference](#3-master-environment-variable-reference)
- [4. Quick Setup Recommendations](#4-quick-setup-recommendations)

---

## 1. Resolution Precedence & Layering

DeepSeek Harness resolves configuration through a strict multi-tier hierarchy:

1. **Process Environment (`process.env`)**: Highest precedence. Overrides all file settings.
2. **Structured Credentials (`~/.dsh/.credentials.yaml`)**: Atomic `0600` permissions. Dynamically resolved via `ctx.credentials`; never materialized into `process.env`.
3. **Project Directory (`<project>/.env`)**: Project-level variables. Blocked from altering bootstrap, proxy, or model routes by the security denylist.
4. **Harness Home (`$DSH_HOME/.env` / `~/.dsh/.env`)**: Global user settings. The only `.env` file permitted to declare proxy variables (`HTTP_PROXY`, `HTTPS_PROXY`, `ALL_PROXY`, `NO_PROXY`).
5. **Cordis Patch Layer (`cordis.patch.yml`) & Profiles**: Profile and plugin defaults.

---

## 2. Bootstrap Security Denylist (Anti-Exfiltration Boundary)

To prevent untrusted or cloned repositories from hijacking execution or exfiltrating credentials, `packages/boot/app-boot/src/index.ts` enforces a strict bootstrap denylist on all discovered project `.env` files. If any of the following appear in a project `.env`, startup aborts with an error:

- **Process & Binary Paths**: `PATH`, `HOME`, `USERPROFILE`, `SHELL`, `LD_PRELOAD`, `LD_LIBRARY_PATH`, `LD_AUDIT`.
- **Runtime Interpreters**: `NODE_OPTIONS`, `NODE_PATH`, `NODE_EXTRA_CA_CERTS`, `NODE_TLS_REJECT_UNAUTHORIZED`, `PYTHONPATH`, `PYTHONSTARTUP`, `PYTHONHOME`, `PERL5OPT`, `PERL5LIB`, `RUBYOPT`, `RUBYLIB`, `JAVA_TOOL_OPTIONS`, `_JAVA_OPTIONS`, `JDK_JAVA_OPTIONS`.
- **Shell Startup Hooks**: `BASH_ENV`, `ENV`, `SHELLOPTS`, `BASHOPTS`.
- **VCS & Transport Controls**: `GIT_SSH`, `GIT_SSH_COMMAND`, `GIT_EXTERNAL_DIFF`, `GIT_PAGER`, `GIT_EDITOR`, `GIT_ASKPASS`, `SSH_ASKPASS`, `GIT_CONFIG_GLOBAL`, `GIT_CONFIG_SYSTEM`, `GIT_CONFIG_COUNT`.
- **Model Endpoints & Egress Redirects**: `DEEPSEEK_BASE_URL`, `DEEPSEEK_SEARCH_BASE_URL`, `SSL_CERT_FILE`, `SSL_CERT_DIR`, `REQUESTS_CA_BUNDLE`, `CURL_CA_BUNDLE`.
- **Proxy Configuration**: `HTTP_PROXY`, `HTTPS_PROXY`, `ALL_PROXY`, `NO_PROXY` (permitted in `$DSH_HOME/.env` only).
- **Reserved Prefixes**: Any variable starting with `DSH_*`, `XDG_*`, `DYLD_*`, or `BASH_FUNC_*`.

---

## 3. Master Environment Variable Reference

### 3.1 Paths & Filesystem Roots

| Variable | Default | Defined In | Purpose |
|---|---|---|---|
| `DSH_HOME` | `~/.dsh` | `@deepseek-ai/dsh-home-paths` | Harness home root for profiles, credentials, logs, and sessions |
| `DSH_AGENTS_HOME` | `~/.agents` | `@deepseek-ai/dsh-home-paths` | Shared home root for cross-harness skills and agent tools |
| `DSH_PROFILES_HOME` | `$DSH_HOME/profiles` | `@deepseek-ai/dsh-home-paths` | Profiles root (`web`, `headless`, `sdk`) |
| `DSH_STORAGE_HOME` | `$DSH_HOME/storage` | `@deepseek-ai/dsh-storage` | Persistent key-value and non-session storage root |
| `DSH_RUNTIMES_DIR` | `$DSH_HOME/runtimes` | `@deepseek-ai/dsh-runtime` | Bundled Python/Node language runtime cache directory |
| `DSH_BUNDLED_SKILL_DIR`| `<harness>/skills` | `@deepseek-ai/dsh-skill-filesystem` | Directory containing built-in skills |

### 3.2 Telemetry & Observability Controls

For complete telemetry details, see [TELEMETRY.md](TELEMETRY.md).

| Variable | Default | Defined In | Purpose |
|---|---|---|---|
| `DSH_TELEMETRY_DISABLED` | *unset* | `@deepseek-ai/dsh-app-boot` | **Hard disable switch**. Any non-empty value (e.g. `1`, `true`, `0`, `false`, `no`) disables the OTel telemetry plugin row at boot |
| `DSH_TELEMETRY_MODE` | `FEEDBACK_ONLY` | `@deepseek-ai/dsh-session-telemetry-otel` | Sets mode: `DISABLED`, `FEEDBACK_ONLY` (default), or `FULL` |
| `DSH_TELEMETRY_OTLP_URL`| `https://dsh-otel-collector.deepseeksvc.com/v1/logs` | `packages/bundle/base/cordis.patch.yml` | Overrides the OTLP/HTTP session and error logs collector endpoint |
| `DSH_APP_VERSION` | `<package.json version>` | `packages/host/product-telemetry-otel` | Application version reported in OTel resource attributes |
| `OTEL_EXPORTER_OTLP_ENDPOINT` | *unset* | `@opentelemetry/sdk-logs` | Fallback endpoint for standard OpenTelemetry collectors |
| `OTEL_EXPORTER_OTLP_HEADERS` | *unset* | `@opentelemetry/sdk-logs` | Custom HTTP headers sent to the OpenTelemetry collector |
| `OTEL_EXPORTER_OTLP_TIMEOUT` | `1000` | `@opentelemetry/sdk-logs` | OTLP HTTP export timeout in milliseconds |
| `OTEL_SERVICE_NAME` | `deepseek-harness` | `@opentelemetry/sdk-logs` | Service name attribute on the OpenTelemetry resource |
| `OTLP_TOKEN` | *unset* | `@deepseek-ai/dsh-session-telemetry-otel` | Bearer authentication token for custom OTLP telemetry collectors |

### 3.3 LLM Providers & API Credentials

| Variable | Default | Subsystem | Purpose |
|---|---|---|---|
| `DEEPSEEK_API_KEY` | *unset* | `@deepseek-ai/dsh-llm-deepseek` | Official API key for DeepSeek models (`deepseek-chat`, `deepseek-reasoner`) |
| `DEEPSEEK_BASE_URL` | `https://api.deepseek.com` | `@deepseek-ai/dsh-llm-deepseek` | Base URL for DeepSeek API requests |
| `DEEPSEEK_SEARCH_BASE_URL` | `https://api.deepseek.com` | `@deepseek-ai/dsh-web-search-deepseek` | Base URL for DeepSeek web search API |
| `DEEPSEEK_SEARCH_MODEL` | `deepseek-chat` | `@deepseek-ai/dsh-web-search-deepseek` | Model used for executing web search tasks |
| `ANTHROPIC_API_KEY` | *unset* | `@deepseek-ai/dsh-llm-pi-ai` | API key for Anthropic Claude models |
| `OPENAI_API_KEY` | *unset* | `@deepseek-ai/dsh-llm-pi-ai` | API key for OpenAI GPT models |
| `AZURE_OPENAI_API_KEY`| *unset* | `@deepseek-ai/dsh-llm-pi-ai` | API key for Azure OpenAI endpoints |
| `GEMINI_API_KEY` | *unset* | `@deepseek-ai/dsh-llm-pi-ai` | API key for Google Gemini models |
| `MISTRAL_API_KEY` | *unset* | `@deepseek-ai/dsh-llm-pi-ai` | API key for Mistral AI models |
| `GROQ_API_KEY` | *unset* | `@deepseek-ai/dsh-llm-pi-ai` | API key for Groq Cloud fast inference |
| `FIREWORKS_API_KEY` | *unset* | `@deepseek-ai/dsh-llm-pi-ai` | API key for Fireworks AI endpoints |
| `TOGETHER_API_KEY` | *unset* | `@deepseek-ai/dsh-llm-pi-ai` | API key for Together AI endpoints |
| `MOONSHOT_API_KEY` / `KIMI_API_KEY` | *unset* | `@deepseek-ai/dsh-llm-pi-ai` | API credential for Moonshot / Kimi models (`api.moonshot.ai` or `api.moonshot.cn`) |
| `MOONSHOTAI_CN_API_KEY` | *unset* | `@deepseek-ai/dsh-llm-pi-ai` | Domestic China API credential for Moonshot AI (`api.moonshot.cn`) |
| `MINIMAX_API_KEY` | *unset* | `@deepseek-ai/dsh-llm-pi-ai` | API credential for MiniMax models (`api.minimax.io`) |
| `MINIMAX_CN_API_KEY` | *unset* | `@deepseek-ai/dsh-llm-pi-ai` | Domestic China API credential for MiniMax models (`api.minimaxi.com`) |
| `XIAOMI_API_KEY` | *unset* | `@deepseek-ai/dsh-llm-pi-ai` | API credential for Xiaomi MiMo LLM service |
| `XIAOMI_TOKEN_PLAN_CN_API_KEY` | *unset* | `@deepseek-ai/dsh-llm-pi-ai` | Xiaomi Token Plan China gateway (`token-plan-cn.xiaomimimo.com`) |
| `XIAOMI_TOKEN_PLAN_AMS_API_KEY` | *unset* | `@deepseek-ai/dsh-llm-pi-ai` | Xiaomi Token Plan Amsterdam gateway (`token-plan-ams.xiaomimimo.com`) |
| `XIAOMI_TOKEN_PLAN_SGP_API_KEY` | *unset* | `@deepseek-ai/dsh-llm-pi-ai` | Xiaomi Token Plan Singapore gateway (`token-plan-sgp.xiaomimimo.com`) |
| `XAI_API_KEY` | *unset* | `@deepseek-ai/dsh-llm-pi-ai` | API credential for xAI Grok models |
| `CEREBRAS_API_KEY` | *unset* | `@deepseek-ai/dsh-llm-pi-ai` | API credential for Cerebras models |
| `HUGGINGFACE_API_KEY` | *unset* | `@deepseek-ai/dsh-llm-pi-ai` | API credential for Hugging Face Router |

### 3.4 Runtime & Execution Policy Switches

| Variable | Default | Subsystem | Purpose |
|---|---|---|---|
| `DSH_PERMISSION_MODE` | `workspace-write` | `@deepseek-ai/dsh-permissions` | Runtime permission preset: `workspace-write`, `danger-full-access`, or `read-only` |
| `DSH_TOOLS_MODE` | `native` | `@deepseek-ai/dsh-tools` | Tool presentation mode: `native`, `ptc` (Programmatic Tool Calling), or `both` |
| `DSH_WRAP` | *unset* | `@deepseek-ai/dsh-shell-sandbox` | Custom wrapper binary for sandbox subshell commands |
| `DSH_SNAPSHOT` | *unset* | `@deepseek-ai/dsh-app-boot` | Snapshot config override path used for immutable test reproducibility |
| `DSH_CONTEXT_WINDOW` | *model default* | `@deepseek-ai/dsh-llm` | Token context window upper limit override |

### 3.5 Injected Subprocess Variables (Read-Only)

These variables are injected automatically by the harness into spawned subprocesses and tool execution environments:

| Injected Variable | Injected Value | Source | Purpose |
|---|---|---|---|
| `DSH_SHELL` | `1` | Subprocess local runner | Identifies to child processes that they are executing under managed DSH supervision |
| `DSH_SESSION_ID` | UUID string | Session provider | Active session ID for correlation within tool and shell scripts |
| `DSH_SESSION_JSONL` | `/path/to/session.v3.jsonl` | Session persistence | Absolute path to the active session transaction journal on disk |
| `DSH_WEB_URL` | `http://127.0.0.1:3080` | Web host coordinator | Canonical local address of the running Web UI interface |

### 3.6 Web Server & UI Client Settings

| Variable | Default | Subsystem | Purpose |
|---|---|---|---|
| `HOST` / `DSH_WEB_HOST` | `127.0.0.1` | `apps/web` | Bind host interface. Rejects external network interfaces (`0.0.0.0`) unless explicitly permitted |
| `PORT` / `DSH_WEB_PORT` | `3080` | `apps/web` | HTTP port for the web user interface and API gateway |
| `DSH_WEB_SEARCH_PROVIDER` | `deepseek` | `packages/web/web` | Web search backend provider selector |
| `DSH_WEB_FETCH_PROVIDER` | `http` | `packages/web/web` | URL content fetcher backend provider |
| `DSH_CLIENT_TITLE` | `DeepSeek Harness` | `packages/client/ui-layout` | Document and titlebar title for Web/Desktop UI |
| `DSH_CLIENT_VERSION` | `<version>` | `packages/client/ui-sidebar` | Client build version reported in the UI sidebar footer |
| `DSH_CLIENT_COMMIT_HASH` | `<git commit>` | `packages/client/ui-sidebar` | Git commit hash displayed in UI diagnostic dialog |

### 3.7 Network & Proxy Configuration

| Variable | Default | Allowed Location | Purpose |
|---|---|---|---|
| `HTTP_PROXY` / `http_proxy` | *unset* | Shell env or `$DSH_HOME/.env` | Outbound proxy for HTTP requests |
| `HTTPS_PROXY` / `https_proxy` | *unset* | Shell env or `$DSH_HOME/.env` | Outbound proxy for HTTPS requests |
| `ALL_PROXY` / `all_proxy` | *unset* | Shell env or `$DSH_HOME/.env` | SOCKS / generic proxy for all outbound network traffic |
| `NO_PROXY` / `no_proxy` | `localhost,127.0.0.1` | Shell env or `$DSH_HOME/.env` | Comma-delimited list of hostnames/IPs to exempt from proxying |

### 3.8 Subagent & Experimental Features

| Variable | Default | Subsystem | Purpose |
|---|---|---|---|
| `DSH_BROWSER_EXECUTABLE` | *system default* | `browser-use-runtime` | Path to browser binary (Chrome/Chromium) for web browsing tools |
| `DSH_COMPUTER_USE_MCP_EXECUTABLE` | *unset* | `computer-use-cua-driver-mcp` | Path to CUA (Computer Use Agent) MCP driver executable |
| `DSH_COMPUTER_USE_MCP_ARGS` | *unset* | `computer-use-cua-driver-mcp` | Arguments passed to the CUA driver process |
| `DSH_TRANSLATION_LIVE` | *unset* | `translator` | Enables live translation services in the web client |

### 3.9 Desktop & Electron Host Flags (Including Tencent Cloud COS Distribution)

| Variable | Default | Subsystem | Purpose |
|---|---|---|---|
| `DSH_DESKTOP_OPEN_DEVTOOLS` | `0` | `apps/desktop` | Opens Chrome DevTools on startup when set to `1` |
| `DSH_DESKTOP_USER_DATA_DIR` | *platform default* | `apps/desktop` | Custom Electron userData directory path |
| `DSH_DESKTOP_UPDATE_CHANNEL` | `stable` | `apps/desktop` | Release update channel (`stable`, `beta`, `dev`) |
| `DSH_DESKTOP_DIAGNOSTIC_FILE` | *unset* | `apps/desktop` | File path where crash and diagnostic traces are dumped |
| `DESKTOP_COS_REGION` | `ap-beijing` | `apps/desktop` (`desktop-cos.ts`) | Tencent Cloud Object Storage (COS) region for release distribution buckets |
| `COS_SECRET_ID` / `COS_SECRET_KEY` | *unset* | `apps/desktop` (`upload-target.ts`) | Tencent Cloud API credentials for desktop package publishing |
| `COS_BUCKET` | *unset* | `apps/desktop` (`upload-target.ts`) | Target Tencent Cloud COS bucket for package distribution |
| `DOWNLOAD_PROD_COS_BUCKET` | *unset* | `apps/desktop` (packaging) | Production Tencent Cloud COS bucket for `download.deepseek.com` |
| `DOWNLOAD_PROD_COS_SECRET_ID` | *unset* | `apps/desktop` (publishing) | Production Tencent Cloud COS SecretId |
| `DOWNLOAD_PROD_COS_SECRET_KEY` | *unset* | `apps/desktop` (publishing) | Production Tencent Cloud COS SecretKey |
| `DOWNLOAD_TEST_COS_BUCKET` | *unset* | `apps/desktop` (packaging) | Test Tencent Cloud COS bucket for `download-test.deepseek.com` |
| `DOWNLOAD_TEST_COS_SECRET_ID` | *unset* | `apps/desktop` (publishing) | Test Tencent Cloud COS SecretId |
| `DOWNLOAD_TEST_COS_SECRET_KEY` | *unset* | `apps/desktop` (publishing) | Test Tencent Cloud COS SecretKey |

---

## 4. Quick Setup Recommendations

For initial setup of a clean, secure DSH workspace:

```bash
# 1. Initialize standard ~/.dsh structure:
python3 skills/rabbit-dsh/scripts/rabbit_dsh.py config init ~/.dsh

# 2. Add your DeepSeek API key to ~/.dsh/.env (chmod 0600):
echo "DEEPSEEK_API_KEY=sk-your-key-here" >> ~/.dsh/.env
chmod 0600 ~/.dsh/.env

# 3. Disable telemetry and reset tracking identity:
python3 skills/rabbit-dsh/scripts/rabbit_dsh.py config telemetry disable --reset-id

# 4. Export mandatory environment switches:
export DSH_TELEMETRY_DISABLED=1
export DSH_TELEMETRY_MODE=DISABLED
export DSH_PERMISSION_MODE=workspace-write
```
