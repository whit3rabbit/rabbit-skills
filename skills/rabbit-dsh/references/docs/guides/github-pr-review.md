# Automatic GitHub PR review

**In short**: a dedicated GitHub webhook endpoint feeds a rule that creates a DSH review Session. Results stay in that Session by default; the example does not post PR comments.

**Source baseline: `0.1.5-alpha.1` / `5dda764ed3`, checked 2026-09-09.** npm `latest` / `next` resolve to `0.1.2-rc.1` (the `alpha` channel is `0.1.5-alpha.1`); prepare a matching source build using the [migration guide](../guides/upgrade-migration.md). For manually initiated review, see [Code review](../guides/code-review.md).

## Contents

- [1. Expected workflow](#1-expected-workflow)
- [2. Prerequisites](#2-prerequisites)
- [3. Copy the example and select a repository](#3-copy-the-example-and-select-a-repository)
- [4. Expose only the webhook endpoint](#4-expose-only-the-webhook-endpoint)
- [5. Verify two separate layers](#5-verify-two-separate-layers)
- [6. Delivery semantics and troubleshooting](#6-delivery-semantics-and-troubleshooting)
- [7. Constraints to retain when extending](#7-constraints-to-retain-when-extending)
- [Sources](#sources)

---

## 1. Expected workflow

The ingress sends `202` before rule completion. It does not certify that the model started or that the review passed.

## 2. Prerequisites

- Built official source and a working model route with available quota.

- A local checkout of a dedicated test repository and permission to configure its webhook.

- A new DSH home for verification.

- An HTTPS ingress that forwards GitHub requests to the dedicated webhook port. Keep the Web UI local.

The example binds `127.0.0.1:3081`, serves `/github`, and limits request bodies to `1048576` bytes. Its isolated WebServer realm is separate from the Web UI / RPC on port `3080`.

## 3. Copy the example and select a repository

These shell commands target macOS / Linux. Substitute your source checkout and test repository; use a new demo home.

```sh
export DSH_SOURCE="/absolute/path/to/deepseek-harness"

export DSH_HOME="$HOME/.dsh-github-review-demo"

export DSH_GITHUB_REVIEW_WORKSPACE="/absolute/path/to/test-repo"

export DSH_GITHUB_WEBHOOK_PORT=3081

umask 077

cd "$DSH_SOURCE"

pnpm dsh web --dump-default-config >/dev/null

PROFILE_DIR="$DSH_HOME/profiles/web"

mkdir -p "$PROFILE_DIR"

cp apps/cli/config/examples/github-review/github-ready-review-rule.mjs \

  "$PROFILE_DIR/github-ready-review-rule.mjs"

cp apps/cli/config/examples/github-review/cordis.yml \

  "$PROFILE_DIR/github-review.patch.yml"
```

Edit the rule's `config.repository` in the copied `github-review.patch.yml` to your exact `OWNER/REPO`. The upstream example says `deepseek-harness/deepseek-harness`; replace it rather than inheriting that example target. Keep the `.mjs` file beside the patch so its relative plugin path resolves.

Relevant fragment below; this is not the complete overlay:

```yaml
- id: github-ready-review-rule

  name: './github-ready-review-rule.mjs'

  config:

    source: primary-github

    repository: OWNER/REPO

    workspacePath: !!js process.env.DSH_GITHUB_REVIEW_WORKSPACE ?? process.cwd()

    agentPreset: standard

    permissionPreset: read-only
```

Both the rule and adapter must use source `primary-github`. Generate a high-entropy secret once, retain it for later restarts, and use the same value in GitHub:

```sh
export DSH_GITHUB_WEBHOOK_SECRET="$(openssl rand -hex 32)"

pnpm dsh web --patch "$PROFILE_DIR/github-review.patch.yml"
```

Configure model credentials in the Web UI. Store the webhook secret privately, outside repository files, logs, and URLs. Generating another value on restart invalidates signatures from the old GitHub configuration.

## 4. Expose only the webhook endpoint

Forward HTTPS `/github` to the dedicated local port, preserving the raw body and GitHub signature headers. Do not forward the complete Web UI port alongside it.

Configure the test repository's webhook:

| Setting | Value |
| --- | --- |
| Payload URL | https://HOOK_HOST/github |
| Content type | application/json |
| Secret | Same value as runtime DSH_GITHUB_WEBHOOK_SECRET |
| Events | Pull requests |

The secret authenticates inbound events only. It does not grant the Agent permission to read private repositories or post comments. Configure necessary outbound credentials separately for private PR reads. The default output destination is the DSH Session, not GitHub comments.

## 5. Verify two separate layers

### A. Local ingress check without model execution

In another terminal, set the same secret and port as the server, then send a correctly signed `ping`. Do not type these commands into the terminal occupied by the running server.

```sh
node --input-type=module <<'JS'

import { createHmac, randomUUID } from 'node:crypto';

const secret = process.env.DSH_GITHUB_WEBHOOK_SECRET;

if (!secret) throw new Error('Set DSH_GITHUB_WEBHOOK_SECRET first');

const body = JSON.stringify({ zen: 'local ingress check' });

const signature = createHmac('sha256', secret).update(body).digest('hex');

const port = process.env.DSH_GITHUB_WEBHOOK_PORT || '3081';

const response = await fetch('http://127.0.0.1:' + port + '/github', {

  method: 'POST',

  headers: {

    'content-type': 'application/json',

    'x-hub-signature-256': 'sha256=' + signature,

    'x-github-delivery': randomUUID(),

    'x-github-event': 'ping',

  },

  body,

});

console.log('HTTP', response.status);

if (response.status !== 202) process.exitCode = 1;

JS
```

Expect `HTTP 202` and no review Session: `ping` does not match the rule. This checks the local port, signature, and acceptance only—not public forwarding or model execution.

### B. Real PR to Session

- Create a **draft PR** in the configured test repository, then mark it **ready for review**.

- Inspect the delivery status and ID in GitHub.

- Find the `Review OWNER/REPO#number` Session in the DSH Workspace.

- Check that its prompt carries the event's head SHA. Review should refresh live PR metadata and examine an explicit revision.

- Wait for an actual model result and confirm that files, branches, and PR state remain unchanged.

The default filter is `pull_request` + `ready_for_review`. An ordinary `opened` event, `synchronize` after another commit, or an event from another repository can receive `202` without triggering this rule.

## 6. Delivery semantics and troubleshooting

| Symptom | First checks |
| --- | --- |
| 401 | Matching secrets, unchanged raw body, complete signature header |
| 415 / 405 | JSON content type and POST method |
| 503 | Secret reference resolution and webhook runtime readiness |
| 202 without a Session | Source, repository full name, event and action filters; then rule logs |
| Session exists but review fails | Model route, quota, repository access, and read-only policy—not the webhook secret |
| Duplicate review Sessions | The runtime has no persistent delivery deduplication; redelivery runs the rule again |

The runtime stores no durable delivery/execution queue. A crash loses rule calls that have not admitted their prompt. After admission, ordinary Session persistence and Agent lifecycle own the work.

If reliable deduplication or retries are required, implement them explicitly in an upstream delivery layer or your rule's persistent state. The presence of `deliveryId` is not built-in deduplication. A browser launch token is not a GitHub webhook secret.

## 7. Constraints to retain when extending

The official rule treats PR titles/authors and other metadata as untrusted, asks for read-only checks, and reports inside the Session. Preserve these boundaries. Broadening action filters or adding automatic comments introduces behavior that needs separate permission, duplicate-execution, and failure-recovery checks.

This example is enabled by `--patch`; plain `dsh web` does not discover this file automatically. For persistent activation, merge the original overlay rows into the sibling `cordis.patch.yml`. Mount them once: do not both merge them and pass the same overlay again.

## Sources

- [Official GitHub review guide](https://github.com/deepseek-ai/deepseek-harness/blob/5dda764ed3aa172535a7967b06ff95d9cbfe536a/docs/user/guide/github-review.md)

- [Overlay and rule](https://github.com/deepseek-ai/deepseek-harness/tree/5dda764ed3aa172535a7967b06ff95d9cbfe536a/apps/cli/config/examples/github-review)

- [Signature validation and HTTP responses](https://github.com/deepseek-ai/deepseek-harness/blob/5dda764ed3aa172535a7967b06ff95d9cbfe536a/packages/webhook/webhook-github/src/handler.ts)
