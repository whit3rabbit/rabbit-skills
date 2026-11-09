# DSH Artifact Checks (DA-01..DA-21)

Check catalog for `scripts/audit_dsh_artifacts.py`, the deep static linter for DeepSeek Harness (DSH) runtime artifacts. IDs are kept in exact 1-to-1 parity with `CHECK_INFO` in that script. When you add a check, add it here in the same commit.

Run it:

```sh
python3 scripts/audit_dsh_artifacts.py <artifact-path>          # text report
python3 scripts/audit_dsh_artifacts.py <artifact> --strict      # exit 1 on warnings
python3 scripts/audit_dsh_artifacts.py <artifact> --check DA-04,DA-06
python3 scripts/audit_dsh_artifacts.py --list-checks            # print this catalog
python3 scripts/audit_dsh_artifacts.py --self-test              # fixture regression suite
```

Artifact families and how they are recognized:

| Family | Files | Mounted by |
|---|---|---|
| Cordis patch / preset | `cordis.patch.yml`, `*.patch.yml`, `agent.cordis.yml` | profile/machine/`--patch` layers, agent presets |
| Workflow definition | `.json` / `.yaml` containing `meta` + `script` | `workflow` tool (`ctx.workflowEngine`) |
| Runtime settings | `settings.yaml` (or `settings.*.yaml`, `.json`) | `~/.dsh/settings.yaml`, hot-published |
| Skill manifest | `skill.json` (optional, DSH discovery ignores it) | other tooling, not DSH |
| Credentials | `.env`, `.credentials.yaml` | harness home (`~/.dsh/`) |
| Session log | `session*.jsonl` (`.jsonl.zstd` → decode first) | `→ ~/.dsh/sessions/` |

Two managed formats written by `rabbit_dsh.py` are recognized structurally: `# rabbit-dsh managed MCP patch` (JSON payload) and `# rabbit-dsh managed plugin patch` (YAML payload). Parsing uses a restricted line scanner, not a full YAML engine. Unrecognized shapes become notes, never errors.

## Contents

- [Patch layer & presets (DA-01..DA-08)](#patch-layer--presets-da-01da-08)
- [Workflow definitions (DA-09..DA-12)](#workflow-definitions-da-09da-12)
- [Runtime settings (DA-13..DA-16)](#runtime-settings-da-13da-16)
- [Bundle manifest & credentials (DA-17, DA-18)](#bundle-manifest--credentials-da-17-da-18)
- [Session logs (DA-19..DA-21)](#session-logs-da-19da-21)
- [Known version skew (read before trusting any single doc)](#known-version-skew-read-before-trusting-any-single-doc)

---

## Patch layer & presets (DA-01..DA-08)

Ground truth: `docs read learn/core/plugin-anatomy.md` (§6 patch semantics), `docs read features/mcp.md`, `docs read features/persona.md`.

A cordis patch is a **top-level YAML array**. Each entry is one of exactly two operations:

- `insert:` (an indented sub-list of rows appended to a target group, each row keyed by `id`)
- a bare row located by `id`, overriding `name` / `config` / `disabled` / `inject` / `group` / `isolate` / `intercept`

Constraints worth internalizing: `config` is a **whole-row replacement** (not a deep merge), a mismatched `name` warns then skips (silently ineffective), and there is **no** `replace`/`ignore` verb. Layers flatten in order: `profile.bundles` → profile patch → `$DSH_HOME/cordis.patch.yml` → `--patch` overlays → telemetry toggle.

### DA-01: Patch document shape / unknown verb (error)
Not a top-level array of `insert:`/`id:` entries, or uses a verb that does not exist.

```yaml
# Bad: `replace` is not a patch operation
- replace:
    - id: broken-row

# Good
- insert:
    - id: broken-row
      name: '@my/plugin'
- id: otel            # bare row override located by id
  disabled: true
```

### DA-02: Inserted row missing `id` or `name` (error)
Rows inside `insert:` blocks are keyed by `id`. Without it, later patches cannot target the row.

```yaml
# Bad
- insert:
    - name: '@my/plugin'

# Good
- insert:
    - id: docker-plugin
      name: '@my/docker-plugin'
```

### DA-03: Duplicate patch row id (error)
Later rows with the same id silently replace earlier ones within a layer.

### DA-04: `!!js` outside `config` / `disabled` (error)
The `!!js <expr>` JavaScript-expression tag is only interpreted inside `config` values and `disabled` fields. Anywhere else it stays a literal string.

```yaml
# Bad: inject is entry metadata, not a config value
- id: bad
  name: '@my/plugin'
  inject: !!js ['tools']

# Good
- id: good
  name: '@my/plugin'
  config:
    apiKey: !!js process.env.MY_API_KEY
  disabled: !!js process.platform === 'win32'
```

### DA-05: MCP `serverName` invalid or duplicate (error)
MCP rows mount `@deepseek-ai/dsh-mcp-client`. `serverName` must match `[A-Za-z0-9_-]{1,32}` and be unique across live instances. It becomes the `mcp__<serverName>__<tool>` prefix.

### DA-06: MCP transport/fields mismatch (error, `sse` warns)
`stdio` requires `command` (+ optional `args`/`env`/`cwd`). `streamable-http` requires `url` (+ optional `headers`). `sse` appears only in older docs and examples. Current documented transports are `stdio` and `streamable-http`.

```yaml
# Good
- id: mcp-github
  name: '@deepseek-ai/dsh-mcp-client'
  config:
    serverName: github
    transport: stdio
    command: npx
    args: ['-y', '@modelcontextprotocol/server-github']
    env:
      GITHUB_TOKEN: !!js process.env.GITHUB_TOKEN
```

### DA-07: Plaintext credential in patch (warning)
Inline secret literals leak through logs and backups. Reference environment variables instead (`!!js process.env.VAR`).

### DA-08: Persona preset row invalid (error)
In an agent preset (`agent.cordis.yml`), the `@deepseek-ai/dsh-persona` row needs a non-empty `config.text`. `complete` and `includeRuntimeContext` must be strict booleans.

```yaml
# Good
- id: persona
  name: '@deep-ai/dsh-persona'
  config:
    text: You are a code review assistant. Read-only suggestions, no implementation.
    complete: false            # false = shadow the deployment persona
    includeRuntimeContext: true
```

---

## Workflow definitions (DA-09..DA-12)

Ground truth: `docs read features/workflow.md`, `docs read official/reference/subsystems/workflow.md`.

The engine validates `meta` against its schema and **rejects loud BEFORE the script runs**. The official `WorkflowMeta` vocabulary is exactly `{name, description, whenToUse?, phases?}`. The script is a plain-JS function body (top-level await) ending in `return <json-value>`, and only `agent`, `parallel`, `pipeline`, `phase`, `log` are injected.

### DA-09: Workflow meta invalid (error)
Missing `name` (short kebab-case, also the persistence key) or `description`.

### DA-10: Unknown meta fields (warning)
Fields like `mode` or `maxIterations` were emitted by older scaffolders but are not in the engine schema. They can fail the start request.

```json
// Bad
{ "meta": { "name": "fix", "description": "...", "mode": "ralph", "maxIterations": "10" } }

// Good: iteration bounds live in the script body, not in meta
{ "meta": { "name": "fix", "description": "...", "whenToUse": "stable goal, repeated rounds" } }
```

### DA-11: `phase()` call not declared in `meta.phases` (warning)
`phases` is progress vocabulary only. `phase()` calls match declared titles for observers, and undeclared titles never appear in progress views.

### DA-12: Script violates the orchestration contract (error/warning)
Checked: `export` statements (error, scripts are bodies not modules), misspelled primitives (error, e.g. `parrallel(` or `pipelien(`), case-variants of primitives (warning, JS is case-sensitive), no `return` anywhere (warning), and Ralph-style loops with no visible iteration bound (warning).

```js
// Bad
export const meta = {};                       // modules are not scripts
const r = await parrallel([agent('a')]);      // misspelled primitive

// Good
async function main(args) {
  const r = await parallel([agent('a'), agent('b')]);
  return r.filter(Boolean);                   // ends with return <json-value>
}
```

---

## Runtime settings (DA-13..DA-16)

Ground truth: `docs read user-guide/settings.md`, `docs read user-guide/permissions.md`, `docs read user-guide/configuration.md`, `docs read reference/env-vars.md`.

Namespaces are **plugin-registered**, so unknown top-level sections are reported as notes (verify they belong to a mounted plugin), not errors. Behavior to remember: fail-loud at startup, last-good on hot reload, leaf-level YAML diffs.

### DA-13: Structural problem (error)
Non-mapping namespace values, or `agent-default-model` missing `provider`/`model` (string fields). Extra fields beyond `reasoningEffort` warn, since `reasoningEffort` is settings-only and never plugin config.

```yaml
# Good
agent-default-model:
  provider: deepseek-official
  model: deepseek-chat
```

### DA-14: Unknown permission preset (error)
`permission.defaultPreset` accepts `workspace-write`, `read-only`, or `danger-full-access` (approval `ask`/`never`). There is no `full-access` preset.

### DA-15: Invalid telemetry switch (error)
`telemetry.disabled` must be a strict boolean, and a mode value must be `FULL`, `FEEDBACK_ONLY`, or `DISABLED`.

### DA-16: Custom provider row incomplete (warning)
Provider rows under `llm-pi-ai.providers` reference credentials indirectly via `apiKeyEnv` (never inline keys) and declare the wire protocol via `api` (documented value: `openai-completions`).

---

## Bundle manifest & credentials (DA-17, DA-18)

### DA-17: skill.json inconsistent (error/warning + note)
DSH discovery reads `SKILL.md` frontmatter **only**. `skill.json` has no role in DSH discovery. If present for other tooling, keep it consistent: `name` matching the frontmatter/directory, semver-ish `version`, entry paths that resolve, strict booleans on `disableModelInvocation`/`userInvocable`.

### DA-18: Credential file permissions/placeholders (warning)
`.env` and `.credentials.yaml` should be owner-only (`chmod 600`, documented default 0600). Empty `DEEPSEEK_API_KEY=` placeholders fail model requests silently. Reserved `DSH_*` variables (`DSH_SHELL`, `DSH_SESSION_*`) are runtime-injected and must not be user-set (`DSH_HOME` is the documented exception).

---

## Session logs (DA-19..DA-21)

Ground truth: `docs read learn/core/event-system.md` (§5-6). On-disk logs are zstd-compressed (`session.v3.jsonl.zstd`). Decode with `zstdcat` first, since `.jsonl.zstd` inputs get a note instead of content checks.

Envelope: `{"type":"user/message","seq":1,"time":0,"data":{...},"surfaceOp":"append"}`. The first line is the header `{"type":"session","version":3,...}`.

### DA-19: Header or line malformed (error/warning)
First line must be a `type: session` header with an integer `version`, and every following line must parse as a JSON object. Versions above the catalog warn (community docs pin v3, official docs mention v4). A newer version makes older harnesses reject the whole log.

### DA-20: Ordering or surfaceOp violation (error)
`seq` is the monotonically increasing ordering key. `surfaceOp` (`append` or `{op:'replace',startSeq,endSeq}`) is valid **only** on the five surface event types: `system/message`, `developer/message`, `user/message`, `assistant/message`, and `tool/result`.

### DA-21: Unknown event type without `ignorable` (warning)
Unknown types reject session rebuild unless the envelope sets `ignorable: true`. The bundled type catalog is partial (format v3/v4 skew), so treat findings as review hints.

---

## Known version skew (read before trusting any single doc)

- **Session format version**: community docs pin `SESSION_FORMAT_VERSION = 3`, official docs mention a V4 that rejects the retired `{kind:'plugin'}` wrapper. This linter accepts v3 and v4 and warns above it.
- **Skill discovery ranks**: community tables list 5 roots (ranks 100-500), official docs add rank 600 (`bundled`).
- **Log filenames**: official naming is `session.vN.jsonl[.zstd]` from v1 (v0 uses `session.jsonl`), while community snippets glob `session*.jsonl.zstd`.
- **npm vs source**: npm `latest` is 0.1.2-rc.1 while docs describe source 0.1.5-alpha.1 (`guides/deepseek-harness-status.md` is the arbiter). Accept both generations of examples.
