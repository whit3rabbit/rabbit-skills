# Plugin and Marketplace Linting: Quality Specifications and Check Catalog

A comprehensive static analysis and linting standard for Claude Code plugins, OpenAI Codex plugins, and Marketplace catalog repositories.

## Contents

- [Overview and Linting Architecture](#overview-and-linting-architecture)
- [Plugin Linter Check Catalog (`PL-01` through `PL-18`)](#plugin-linter-check-catalog-pl-01-through-pl-18)
- [Marketplace Linter Check Catalog (`MP-01` through `MP-15`)](#marketplace-linter-check-catalog-mp-01-through-mp-15)
- [CLI Tooling and Automated Execution](#cli-tooling-and-automated-execution)
- [CI/CD Integration and PR Gating](#cicd-integration-and-pr-gating)

---

## Overview and Linting Architecture

While `audit_static.py` validates individual procedural skills (`SKILL.md`), `audit_plugin.py` provides static validation for plugin packages and marketplace distribution catalogs.

```
                           [Target Directory]
                                   │
                  ┌────────────────┴────────────────┐
                  ▼                                 ▼
         [marketplace.json]                   [plugin.json]
                  │                                 │
                  ▼                                 ▼
       MARKETPLACE LINTER (MP)              PLUGIN LINTER (PL)
       - Catalog syntax & schema            - Manifest & semver
       - Owner declarations                 - Always-on token budget
       - Relative source existence          - Skill & command validation
       - Embedded plugin name sync          - Hooks & MCP definitions
       - Source object validation           - Evals suite presence
```

---

## Plugin Linter Check Catalog (`PL-01` through `PL-18`)

| Check ID | Severity | Check Name | Passing Condition & Fix |
|---|---|---|---|
| **PL-01** | Error | Manifest File Validity | `plugin.json` exists at root or in `.claude-plugin/` or `.codex-plugin/` and parses as valid JSON. |
| **PL-02** | Error | Identity and Naming | `name` is lowercase kebab-case matching `^[a-z0-9-]+$` and at most 64 characters. |
| **PL-03** | Warning | Semantic Versioning | `version` follows strict Semantic Versioning (`MAJOR.MINOR.PATCH`). |
| **PL-04** | Info | Description Brevity | `description` is concise (<160 characters) and explains core utility without promotional filler. |
| **PL-05** | Error | User Config Schema | `userConfig` properties declare valid types (`string`, `number`, `boolean`, `enum`). |
| **PL-06** | Info | License Declaration | Manifest declares a standard SPDX license identifier (e.g. `MIT`). |
| **PL-07** | Error | Skills Directory Existence | Declared skills path exists on disk. |
| **PL-08** | Warning | Skill File Compliance | Each skill in `skills/<name>/` contains a valid `SKILL.md` with frontmatter. |
| **PL-09** | Error | Lifecycle Hooks Syntax | Hook events must be valid (`SessionStart`, `UserPromptSubmit`, `PreToolUse`, `PostToolUse`, `SessionEnd`). |
| **PL-10** | Error | MCP Server Definition | Configured MCP servers in `.mcp.json` or `mcp.json` specify valid commands, arguments, or URLs. |
| **PL-11** | Error | Credential Safety | Configuration files must not contain hardcoded API keys or plaintext secrets. Use parameter substitution. |
| **PL-12** | Warning | Always-On Token Budget | Always-on context footprint (names + descriptions) must remain under **150 tokens** (error if >250 tokens). |
| **PL-13** | Info | Evaluation Suite Presence | Recommended minimum of 3 eval test cases under `evals/`. |
| **PL-14** | Warning | Eval Case Completeness | Each eval case directory must include `prompt.md` and at least one grader under `graders/`. |
| **PL-15** | Warning | Bounded Dependencies | Dependencies must declare explicit semver ranges (`^` or `~`), never unpinned wildcards (`*`). |
| **PL-16** | Warning | Codex Extension Validity | `onboardingSkill`, `apps`, and `assets` referenced in `extensions.com.openai` must exist. |
| **PL-17** | Warning | Local File Reference Integrity | Referenced commands, subagents, and scripts must resolve to valid files. |
| **PL-18** | Warning | Binary Permissions | Scripts placed in `bin/` must have executable permissions (`chmod +x`). |

---

## Marketplace Linter Check Catalog (`MP-01` through `MP-15`)

| Check ID | Severity | Check Name | Passing Condition & Fix |
|---|---|---|---|
| **MP-01** | Error | Marketplace Manifest Validity | `marketplace.json` exists at root or in `.claude-plugin/` and parses as valid JSON. |
| **MP-02** | Error | Marketplace Name Format | `name` contains only alphanumeric characters, hyphens, underscores, or dots, and no `..`. |
| **MP-03** | Error | Owner Declaration | Top-level `owner` object exists and includes a non-empty `name` field. |
| **MP-04** | Error | Plugins Array Existence | Top-level `plugins` array is defined. |
| **MP-05** | Warning | Non-Empty Catalog | `plugins` array contains at least one plugin entry. |
| **MP-06** | Error | Unique Plugin Identifiers | Every entry in the `plugins` catalog has a unique `name`. |
| **MP-07** | Error | Required Entry Fields | Each plugin entry defines both `name` and `source`. |
| **MP-08** | Warning | Relative Source Path Format | Relative path sources must start with `./` (or resolve under `metadata.pluginRoot`). |
| **MP-09** | Error | Embedded Plugin Directory | Target relative path must resolve to a directory containing a valid `plugin.json`. |
| **MP-10** | Error | Name Synchronization | Entry `name` in `marketplace.json` must exactly match the `name` declared in the target's `plugin.json`. |
| **MP-11** | Error | Object Source Type | Object source `source` field must be one of: `github`, `url`, `git-subdir`, `npm`, `archive`, `command`. |
| **MP-12** | Error | GitHub Source Format | GitHub sources require `repo: 'owner/repo'`. |
| **MP-13** | Error | Git-Subdir Source Format | Git-subdir sources require valid `url`, `path`, and `ref`. |
| **MP-14** | Error | Archive Source Integrity | Archive sources require HTTPS `url` and a 64-character hex `sha256` checksum. |
| **MP-15** | Error | Cross-Marketplace Dep List | `allowCrossMarketplaceDependenciesOn` must be a list of strings. |

---

## CLI Tooling and Automated Execution

Use `scripts/audit_plugin.py` to audit any local plugin or marketplace directory:

```bash
# Audit a plugin directory
python3 skills/rabbit-plugin-audit/scripts/audit_plugin.py /path/to/my-plugin

# Audit a marketplace catalog repository
python3 skills/rabbit-plugin-audit/scripts/audit_plugin.py /path/to/my-marketplace

# Output machine-readable JSON
python3 skills/rabbit-plugin-audit/scripts/audit_plugin.py /path/to/plugin --format json

# Strict mode: fail on warnings as well as errors (for CI gates)
python3 skills/rabbit-plugin-audit/scripts/audit_plugin.py /path/to/plugin --strict

# Run internal self-tests
python3 skills/rabbit-plugin-audit/scripts/audit_plugin.py --self-test
```

---

## CI/CD Integration and PR Gating

Add an automated linting step to your GitHub Actions workflow:

```yaml
name: Plugin & Marketplace Linter
on: [push, pull_request]

jobs:
  lint:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'
      - name: Lint Plugin and Marketplace Manifests
        run: |
          python3 skills/rabbit-plugin-audit/scripts/audit_plugin.py . --strict
```
