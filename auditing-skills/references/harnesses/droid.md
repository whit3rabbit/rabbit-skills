# Droid (Factory AI) Harness Reference

Reference specification for skill discovery, directory layouts, configuration, and invocation in Factory AI's Droid harness.

- **Harness Identifier:** `--agent droid`
- **Documentation:** https://docs.factory.ai/cli/configuration/skills
- **Agent Registry Table:** `Droid | droid | .agents/skills/ | ~/.factory/skills/`

## Contents

- [Overview](#overview)
- [Skill Paths](#skill-paths)
- [Settings and Configuration](#settings-and-configuration)
- [Discovery and Precedence](#discovery-and-precedence)
- [Feature Support and Frontmatter](#feature-support-and-frontmatter)
- [Concrete Directory Layout](#concrete-directory-layout)
- [Invocation Patterns](#invocation-patterns)
- [CLI Tools and Management](#cli-tools-and-management)

---

## Overview

Droid executes agent skills formatted as directory bundles containing a `SKILL.md` entry point. Skills provide reusable workflows with explicit instructions, metadata, and optional support files.

Key properties:
- **Identifier:** `--agent droid`
- **Primary file:** `SKILL.md` (mandatory; files named `skill.mdx` are ignored)
- **Lifecycle:** 3-tier progressive disclosure (Discovery via metadata -> Intent selection -> Full execution)

---

## Skill Paths

Droid resolves skills across several hierarchical scopes, supporting both Factory-native directories and standard cross-agent directories:

| Scope | Filesystem Path | Scope Description |
|-------|-----------------|-------------------|
| **Project (Native)** | `<repo>/.factory/skills/<skill-name>/SKILL.md` | Team-shared workflows committed to the repository root. |
| **Project (Cross-agent)** | `<repo>/.agents/skills/<skill-name>/SKILL.md` | Standard multi-agent compatibility location. `<repo>/.agent/skills/` is also recognized. |
| **Folder-specific** | `<repo>/<subproject>/.factory/skills/<skill-name>/SKILL.md` | Nested skills discovered when Droid inspects a specific project area. |
| **Global / Personal (Native)** | `~/.factory/skills/<skill-name>/SKILL.md` | User-wide workflows available across all local workspaces. |
| **Global (Cross-agent)** | `~/.agents/skills/<skill-name>/SKILL.md` | Global multi-agent compatibility path (`~/.agent/skills/` also supported). |
| **Mission** | `{missionDir}/skills/**/SKILL.md` | Workflows scoped to a specific Factory mission session. |
| **Automation** | `~/.factory/automations/<name>/skills/**/SKILL.md` | Workflows scoped to automation runs. |
| **Plugin** | `${DROID_PLUGIN_ROOT}/skills/<skill-name>/SKILL.md` | Bundled skills distributed via plugins. |
| **Built-in** | Internal to Droid binary | System skills shipped with Droid. |

Droid traverses skill folders recursively; the first directory containing `SKILL.md` defines the skill bundle.

---

## Settings and Configuration

Droid stores persistent settings in JSON configuration files at both global and workspace levels.

### Configuration Files

- **Global configuration:** `~/.factory/config.json` and `~/.factory/settings.json`
- **Project configuration:** `<repo>/.factory/settings.json`

### Disabling Skills

Skills can be enabled or disabled without deleting files from disk. Configure `disabledSkills` in either project or user settings:

```json
{
  "disabledSkills": [
    "deploy-production",
    "summarize-diff"
  ]
}
```

Rules:
- User (`~/.factory/settings.json`) and project (`<repo>/.factory/settings.json`) lists merge together.
- A disable at either level disables the skill across the workspace.
- Removing a skill identifier re-enables it, provided neither frontmatter nor another settings scope disables it.

---

## Discovery and Precedence

### Discovery Workflow

1. **Discovery:** Droid scans registered skill paths and parses only YAML frontmatter (`name` and `description`).
2. **Selection:** Droid compares the user query against skill descriptions or matches an explicit slash command token.
3. **Invocation:** Droid loads the `SKILL.md` body and supporting files into context only when triggered.

### Precedence Hierarchy

When multiple skills share the same sanitized name, Droid selects one active version based on the following priority:

1. **Organization plugin skills** (overrides all scopes)
2. **Folder-specific and project skills** (`<repo>/.factory/skills/`, `<repo>/.agents/skills/`)
3. **Project plugin skills**
4. **Personal / Global skills** (`~/.factory/skills/`, `~/.agents/skills/`)
5. **User plugin skills**
6. **Built-in skills**

Session-specific overrides:
- In mission sessions, mission-scoped skills take priority over project skills.
- In automation sessions, automation-scoped skills override project and personal skills.
- Same-scope duplicates: If two skills within the same folder share a name, Droid ignores one duplicate and flags it in `/diagnostics`.

---

## Feature Support and Frontmatter

### Frontmatter Schema

`SKILL.md` requires YAML frontmatter delimited by `---`:

```yaml
---
name: summarize-diff
description: Summarizes staged git diffs with risk flags. Use when reviewing changes before commit.
allowed-tools:
  - Read
  - Grep
  - Glob
  - Bash
enabled: true
user-invocable: true
disable-model-invocation: false
license: MIT
compatibility: droid
version: 1.0.0
metadata:
  owner: core-platform
---
```

### Frontmatter Fields

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `name` | string | Yes | None | Skill identifier using lowercase letters, numbers, and hyphens (`[a-z0-9-]`). |
| `description` | string | Yes | None | Routing instruction defining what the skill does and when Droid must invoke it. |
| `allowed-tools` | list | No | All available | Intended tools (e.g. `Read`, `Grep`, `Glob`, `Bash`, `Edit`). Serves as review/UI metadata; does not sandbox runtime execution. (Note: deprecated legacy key is `tools`). |
| `enabled` | boolean | No | `true` | Set to `false` to keep files on disk while deactivating the skill. |
| `user-invocable` | boolean | No | `true` | Set to `false` to prevent direct `/skill-name` slash execution by users. |
| `disable-model-invocation` | boolean | No | `false` | Set to `true` to block Droid from invoking the skill automatically on prompt matching. |
| `license` | string | No | None | License identifier for shared or open-source skills. |
| `compatibility` | string | No | None | Environment compatibility tag (e.g. `droid`). |
| `version` | string | No | None | Semantic version string. |
| `metadata` | object | No | None | Arbitrary key-value metadata for developer tooling. |

### Tool Execution Boundaries

The `allowed-tools` list provides visibility in UI panels and code review. It does not enforce sandboxing or grant capabilities not already permitted in the active session. To enforce strict tool sandboxes, configure a custom droid profile with an execution policy.

---

## Concrete Directory Layout

Below is a standard project directory structure illustrating both cross-agent (`.agents/skills/`) and native (`.factory/skills/`) layouts with supporting files:

```text
my-project/
├── .agents/
│   └── skills/
│       └── review-api-change/
│           ├── SKILL.md
│           ├── checklists.md
│           └── schemas/
│               └── route-contract.json
├── .factory/
│   ├── settings.json
│   └── skills/
│       └── summarize-diff/
│           ├── SKILL.md
│           └── scripts/
│               └── format-summary.sh
├── src/
│   └── index.ts
└── package.json
```

### Supporting Files

- Keep secondary checklists, schemas, and helper scripts in the skill directory beside `SKILL.md`.
- Supporting files are not pre-loaded; reference them explicitly from `SKILL.md` (e.g., `Read checklists.md before evaluating changes`).
- Scripts can be executed via terminal commands (e.g., `bash scripts/format-summary.sh`).

---

## Invocation Patterns

### Natural Language Prompting

When `disable-model-invocation: false`, Droid matches the user's prompt against the skill's `description`:

- **Input:** `"What changes are ready to commit right now?"`
- **Behavior:** Droid matches `summarize-diff` via its description trigger, loads `SKILL.md`, and runs `git diff --staged`.

### Slash Commands in CLI

When `user-invocable: true`, the skill registers as `/skill-name`.

1. **Prefix execution:**
   ```text
   /summarize-diff focus on database migrations
   ```
2. **Inline multi-skill execution:**
   ```text
   inspect this branch with /review-api-change then run /summarize-diff
   ```
3. **Autocompletion:**
   Type `/` followed by space or characters to open the skill selection menu. Press `Tab` or `Enter` to insert.
4. **Name collisions:**
   If a custom slash command shares the skill name, the slash command takes precedence for CLI invocation; the skill remains available for natural language model matching.

### Invocation Permission Matrix

| Configuration | User `/skill-name` | Model Invocation | Typical Use Case |
|---------------|-------------------|------------------|------------------|
| **Default** (`enabled: true`) | Yes | Yes | Standard general-purpose workflows. |
| `disable-model-invocation: true` | Yes | No | Destructive or side-effect operations (e.g., deployments). |
| `user-invocable: false` | No | Yes | Internal procedures or guidelines not invoked directly. |
| `enabled: false` | No | No | Archived or draft workflows. |

---

## CLI Tools and Management

Factory AI provides built-in CLI commands to manage and author skills:

- `/skills`: Opens the interactive skills dashboard displaying discovered skills across tabs (`Effective`, `User`, `Project`, `Plugins`, `Built-in`). Press `Space` to toggle skill states, writing to `settings.json`.
- `/create-skill [prompt]`: Launches an interactive session in Spec mode to extract a skill from the recent conversation history and scaffold `SKILL.md`.
- `/diagnostics`: Analyzes loaded configuration, flags unreadable frontmatter, and reports duplicate or ignored skill paths.
