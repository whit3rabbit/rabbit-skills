# DeepSeek Harness (DSH) — Telemetry & Tracking Analysis Guide

This guide provides an in-depth security analysis of telemetry, identity correlation, and background network traffic in **DeepSeek Harness (`dsh`)**. It includes a full breakdown of all telemetry-related calls, the exact source files where they are defined, what data leaves your machine, and step-by-step instructions on how to disable and block them.

---

## Contents

- [1. Executive Summary & Security Model](#1-executive-summary--security-model)
- [2. Complete Breakdown of Telemetry & Network Calls](#2-complete-breakdown-of-telemetry--network-calls)
- [3. How to Turn Off and Block All Telemetry (5-Layer Defense)](#3-how-to-turn-off-and-block-all-telemetry-5-layer-defense)
- [4. Setup Checklist for Secure Operation](#4-setup-checklist-for-secure-operation)

---

## 1. Executive Summary & Security Model

Independent code audits (including Magnus Hedemark's security review at [magnus919.com](https://magnus919.com/2026/08/deepseek-harness-what-i-found-before-i-let-it-run/)) and our source inspection of `deepseek-ai/deepseek-harness` establish the following facts:

- **No Malicious Code**: There is no spyware, malware, cryptomining, hidden backdoor, or obfuscated beacon in the source code.
- **Telemetry Is Decoupled from Chat**: Telemetry export is separated from ordinary model calls and defaults to `FEEDBACK_ONLY` in base profile patches.
- **Identity Correlation Exists on Model Requests**: Normal API requests through `@deepseek-ai/dsh-llm-deepseek` attach a pseudonymous user UUID (`x-deepseek-harness-user-id`), even when custom endpoint base URLs are supplied.
- **Local Sandbox Has No Network Isolation**: The default `workspace-write` sandbox limits filesystem **writes** outside the project root, but allows filesystem **reads** across any file readable by the operating system user and places **no restrictions on outbound network egress**.

---

## 2. Complete Breakdown of Telemetry & Network Calls

Below is the exhaustive catalog of every telemetry, logging, and identity-tracking call in DeepSeek Harness, mapped to source files and trigger conditions:

### Call 1: OpenTelemetry Session Log Export (`session-telemetry-otel`)

- **Subsystem**: `@deepseek-ai/dsh-session-telemetry-otel`
- **Source Files**:
  - `packages/session/session-telemetry-otel/src/index.ts`
  - `packages/bundle/base/cordis.patch.yml` (lines 205–233)
- **Destination**: `https://dsh-otel-collector.deepseeksvc.com/v1/logs` (or `$DSH_TELEMETRY_OTLP_URL`)
- **Protocol**: OTLP HTTP / JSON with gzip compression
- **Trigger**:
  - In `FEEDBACK_ONLY` mode (shipped default): Triggered **only when the user submits feedback** (e.g. `/feedback` command or feedback UI dialog).
  - In `FULL` mode: Triggered **continuously** across every session event.
  - In `DISABLED` mode: No pipeline is instantiated; zero events leave the process.
- **What Leaves the Machine**:
  - Full prompt text and user messages
  - Model responses and internal reasoning traces
  - Invoked tool names, tool input arguments, and raw execution outputs (shell command outputs, file content)
  - Active workspace directory path (`session.cwd`)
  - Session errors, user feedback ratings, and approval decisions
  - Anonymous User ID on the OTel Resource (`user.id`)

### Call 2: Host Product Telemetry (`product-telemetry-otel`)

- **Subsystem**: `@deepseek-ai/dsh-host-product-telemetry-otel`
- **Source Files**:
  - `packages/host/product-telemetry-otel/src/index.ts`
  - `packages/host/product-telemetry-otel/README.md`
- **Destination**: `https://dsh-otel-collector.deepseeksvc.com/v1/logs`
- **Protocol**: OTLP HTTP / JSON (`x-channel: dsh_otel_report`)
- **Trigger**: Application boot, periodic watchdog flush (`scheduledDelayMillis: 30000`), and clean process shutdown.
- **What Leaves the Machine**:
  - Application version (`DSH_APP_VERSION`)
  - Operating system platform and architecture
  - Process lifecycle status and crash diagnostics

### Call 3: Anonymous User ID Request Header (`x-deepseek-harness-user-id`)

- **Subsystem**: `@deepseek-ai/dsh-anonymous-user-id` & `@deepseek-ai/dsh-llm-deepseek`
- **Source Files**:
  - `packages/identity/anonymous-user-id/src/index.ts`
  - `packages/llm/llm-deepseek/src/adapter.ts` (line 150)
  - `packages/llm/llm-deepseek/src/host.ts` (lines 48–55)
- **Local Storage**: Persisted as a raw UUID line in `$DSH_HOME/.anonymous-user-id` (`~/.dsh/.anonymous-user-id`).
- **Destination**: Sent directly to the model endpoint (default `https://api.deepseek.com`, or whatever custom `DEEPSEEK_BASE_URL` is configured).
- **Trigger**: Attached to **every single DeepSeek API request**:
  ```typescript
  // packages/llm/llm-deepseek/src/adapter.ts
  headers: {
    ...attributionHeaders(),
    'content-type': 'application/json',
    'x-deepseek-harness-user-id': this.dependencies.resolveUserId(),
    ...
  }
  ```
- **What Leaves the Machine**: The persistent UUID v4 string. Disabling OTel telemetry does **not** stop this header from being sent on LLM requests.

### Call 4: Plugin Package Inventory Header (`dsh_plugin_packages`)

- **Subsystem**: `@deepseek-ai/dsh-plugin-package-inventory-deepseek`
- **Source Files**:
  - `packages/llm/plugin-package-inventory-deepseek/src/index.ts`
- **Destination**: Model endpoint on official DeepSeek requests.
- **Trigger**: Appended to model request metadata by default.
- **What Leaves the Machine**: Names and version numbers of all currently active Cordis plugin packages.

### Call 5: Session Log Suffix API Channel (`dsh_session_log`)

- **Subsystem**: `@deepseek-ai/dsh-session-log-deepseek`
- **Source Files**:
  - `packages/session/session-log-deepseek/src/index.ts`
- **Trigger**: Opt-in feature (disabled by default in base configuration).
- **What Leaves the Machine**: Sends canonical session log suffixes directly over the model API channel.

### Call 6: First-Prompt Title Synthesis Request

- **Subsystem**: `@deepseek-ai/dsh-session-title` & `@deepseek-ai/dsh-session-title-llm`
- **Source Files**:
  - `packages/session/session-title/src/index.ts` (lines 461–499)
  - `packages/session/session-title-llm/src/index.ts` (lines 229–275)
- **Destination**: Model API endpoint.
- **Trigger**: Automatically dispatched in the background after the user sends their first message in a new session.
- **What Leaves the Machine**: Dispatches an additional model completion request containing the first prompt's content to generate a 3–6 word session title.

### Call 7: Desktop Updater Inquiries & Tencent Cloud COS

- **Subsystem**: `apps/desktop` updater & publication scripts
- **Source Files**:
  - `apps/desktop/scripts/desktop-cos.ts`
  - `apps/desktop/scripts/upload-target.ts`
  - `apps/desktop/src/update-coordinator.ts`
- **Destination**: `https://download.deepseek.com` and Tencent Cloud COS in region `ap-beijing`.
- **Trigger**: Desktop application launches and periodic update checks.
- **What Leaves the Machine**: Application version, platform query, and download requests for binary updates.

### Call 8: Embedded Feishu Contact Forms

- **Subsystem**: `@deepseek-ai/dsh-ui-settings-account`
- **Source Files**:
  - `packages/client/ui-settings-account/src/contact-config.ts`
- **Destination**: `https://trtgsjkv6r.feishu.cn`
- **Trigger**: User manually clicks the contact/feedback link in the Desktop or Web UI account panel.
- **What Leaves the Machine**: User-entered feedback submitted into a ByteDance Feishu web questionnaire.

---

## 3. How to Turn Off and Block All Telemetry (5-Layer Defense)

Follow this multi-layer procedure to achieve complete isolation:

### Layer 1: Shell Environment Hard Switch (Process Level)

DeepSeek Harness includes an explicit opt-out switch in `packages/boot/app-boot/src/profile-context.ts`: **ANY non-empty value** (including `'0'`, `'false'`, `'no'`) completely unmounts the telemetry row.

Add these lines to your `~/.zshrc`, `~/.bashrc`, or launch environment:

```bash
# 1. Hard disable OTel session telemetry at startup (cannot be overridden by config)
export DSH_TELEMETRY_DISABLED=1

# 2. Force telemetry mode to DISABLED
export DSH_TELEMETRY_MODE=DISABLED

# 3. Sink OTLP collector endpoint to loopback null-route
export DSH_TELEMETRY_OTLP_URL=http://127.0.0.1:9/sink
```

### Layer 2: Automated CLI Hardening via `rabbit-dsh`

The `rabbit-dsh` companion script provides automated hardening:

```bash
# Automatically patch cordis.patch.yml, settings.yaml, and remove .anonymous-user-id:
python3 skills/rabbit-dsh/scripts/rabbit_dsh.py config telemetry disable --root ~/.dsh --reset-id

# Verify current telemetry and correlation status:
python3 skills/rabbit-dsh/scripts/rabbit_dsh.py config telemetry status --root ~/.dsh
```

### Layer 3: Cordis Profile Patch Overrides

In `~/.dsh/profiles/web/cordis.patch.yml` (and any project `.dsh/cordis.patch.yml`), add explicit disable rows:

```yaml
# Disable OpenTelemetry collector and session logging
- id: session-telemetry-otel
  disabled: true

- id: otel
  disabled: true

# Disable sending plugin package inventory in API headers
- id: plugin-package-inventory-deepseek
  config:
    enabled: false

# Disable session log API metadata reporting
- id: session-log-deepseek
  config:
    enabled: false
```

### Layer 4: Tracking Identity Reset & Ephemeral Workspaces

The anonymous user UUID is stored on disk in `$DSH_HOME/.anonymous-user-id`. To prevent cross-session tracking:

```bash
# Reset the UUID (a new random ID is created on next launch):
rm -f ~/.dsh/.anonymous-user-id

# Or run DSH inside an ephemeral temporary directory:
export DSH_HOME=$(mktemp -d /tmp/dsh-session.XXXXXX)
dsh web
```

### Layer 5: Operating System DNS Blackholing (`/etc/hosts`)

Prevent any connection attempts from leaving the machine at the network socket layer:

```text
# Add to /etc/hosts:
127.0.0.1 dsh-otel-collector.deepseeksvc.com
127.0.0.1 harness-telemetry.deepseeksvc.com
::1       dsh-otel-collector.deepseeksvc.com
::1       harness-telemetry.deepseeksvc.com
```

---

## 4. Setup Checklist for Secure Operation

Before using DeepSeek Harness on confidential codebases:

- [ ] Export `DSH_TELEMETRY_DISABLED=1` in your shell profile.
- [ ] Run `python3 skills/rabbit-dsh/scripts/rabbit_dsh.py config telemetry disable --reset-id`.
- [ ] Verify `settings.yaml` contains `telemetry.disabled: true`.
- [ ] Add collector blackhole entries to `/etc/hosts`.
- [ ] If working with high-security repositories, run DSH inside an isolated container, VM, or dedicated user account without access to sensitive host files or credentials.
