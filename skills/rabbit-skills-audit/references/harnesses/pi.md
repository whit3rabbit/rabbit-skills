# Pi Coding Agent Harness Reference

Reference guide for skill discovery, layout, configuration, and execution in Pi Coding Agent (`pi`).

- **Harness Identifier:** `--agent pi`
- **Documentation:** https://pi.dev/docs/latest/skills and https://pi.dev/docs/latest/configuration (verified 8 November 2026)
- **Specification:** [Agent Skills Specification](https://agentskills.io/specification)

## Contents

- [Skill Paths](#skill-paths)
- [Directory Layout](#directory-layout)
- [Settings and Configuration](#settings-and-configuration)
- [Discovery and Precedence](#discovery-and-precedence)
- [Feature Support Matrix](#feature-support-matrix)
- [Frontmatter Specification](#frontmatter-specification)
- [Invocation and Execution](#invocation-and-execution)
- [Distribution](#distribution)

## Skill Paths

Pi searches for skills across project and global user locations:

| Scope | Path | Source |
|---|---|---|
| Project | `.agents/skills/` | Agent Skills standard location; discovered from the working directory through its ancestors, stopping at the repository root. |
| Project | `.pi/skills/` | Pi project resources directory (configuration docs). |
| User / Global | `~/.agents/skills/` | Agent Skills standard global location (skills docs). |
| User / Global | `~/.pi/agent/skills/` | Pi agent-directory resources. The agent directory defaults to `~/.pi/agent` and can be moved via `PI_CODING_AGENT_DIR` (configuration docs). |

## Directory Layout

A skill consists of a directory containing a `SKILL.md` entrypoint and supporting subdirectories:

```text
my-project/
├── .agents/
│   └── skills/
│       └── pdf-tools/
│           ├── SKILL.md
│           ├── scripts/
│           │   └── extract.py
│           ├── references/
│           │   └── formats.md
│           └── assets/
│               └── template.json
├── .pi/
│   └── settings.json
└── src/
```

- `SKILL.md`: Required entrypoint containing YAML frontmatter and operational instructions.
- Supporting files (`scripts/`, `references/`, `assets/`): Referenced from `SKILL.md` via relative paths. Pi provides the skill root directory to the model to resolve relative paths during execution.

## Settings and Configuration

Pi configuration files reside in global user directories and project-level directories:

| Configuration Scope | Path | Purpose |
|---|---|---|
| User Configuration Root (agent directory) | `~/.pi/agent/` | Global settings, keybindings, MCP, models, auth, and resource directories (`extensions/`, `skills/`, `prompts/`, `themes/`). Movable via `PI_CODING_AGENT_DIR`. |
| User Settings File | `~/.pi/agent/settings.json` | Global flags (e.g., `enableSkillCommands`) and resource lists. |
| Project Configuration Root | `.pi/` | Project-scoped overrides for settings and resources. |
| Project Settings File | `.pi/settings.json` | Project-level configuration overrides. |

The `skills` settings key (a string array) adds skill files or directories on top of the documented locations. Resource paths in user settings resolve from the agent directory, and paths in project settings resolve from the project `.pi` directory.

### Skill Configuration Options

- `enableSkillCommands`: Boolean setting in `settings.json` controlling whether `/skill:name` commands are exposed during interactive command discovery. Manual invocation via `/skill:name` functions regardless of this setting.

## Discovery and Precedence

Pi implements progressive disclosure to minimize context window usage:

1. **Startup Discovery**: Pi scans the documented skill roots (`.agents/skills/` ancestor-walked to the repository root, `.pi/skills/`, `~/.agents/skills/`, and the agent-directory `skills/`) recursively.
2. **System Prompt Registration**: Only the `name`, `description`, and file system path of each discovered skill are injected into the system prompt at startup (~100 tokens per skill). Full instructions are omitted.
3. **Ancestor Search**: Project skills in `.agents/skills/` are discovered from the current working directory walking up through ancestor directories, halting at the repository root.
4. **Collision Precedence**: When two skills share identical `name` values, Pi retains the first discovered skill and outputs a diagnostic warning. Project-level skills discovered earlier in the ancestor chain take precedence over global user-level skills.
5. **Instruction Loading**: The full body of `SKILL.md` loads into context only when triggered by model routing or explicit user command.

## Feature Support Matrix

| Feature | Supported | Notes |
|---|---|---|
| Basic Skills (`SKILL.md`) | Yes | Implements Agent Skills specification; directories with `SKILL.md` preferred. |
| `allowed-tools` | Yes | Experimental pre-approved tool allowlist in frontmatter. |
| `disable-model-invocation` | Yes | Excludes skill from automatic model selection; requires manual `/skill:name`. |
| Context Forking (`context: fork`) | No | Skills execute within the active conversation session. |
| Skill Hooks | No | Lifecycle hooks (pre/post execution triggers) are not supported. |
| Interactive Coding CLI | Yes | Interactive command execution, slash commands, and hot reload. |
| Standalone Markdown Files | Partial | Standalone `.md` files recognized, but directory structure with `SKILL.md` is standard. |

## Frontmatter Specification

`SKILL.md` requires valid YAML frontmatter at the top of the file:

```markdown
# Example: SKILL.md
---
name: pdf-tools
description: Extract text and tabular data from PDF files. Use when reading, converting, or inspecting PDFs.
license: MIT
compatibility: python3, pypdf
allowed-tools:
  - bash
  - read_file
disable-model-invocation: false
metadata:
  version: 1.0.0
---

# PDF Tools

Read `references/formats.md` before converting documents. Execute scripts relative to this skill directory.
```

### Supported Frontmatter Fields

| Field | Type | Description |
|---|---|---|
| `name` | string | Display name and command handle. Lowercase letters, digits, and hyphens (`[a-z0-9-]`); max 64 characters; no leading/trailing/consecutive hyphens. |
| `description` | string | Routing description shown to the model in the system prompt. Max 1024 characters. Must state what the skill does and specific triggers for when to apply it. |
| `license` | string | License identifier or bundled license file reference. |
| `compatibility` | string | Environment and runtime prerequisites. |
| `allowed-tools` | list | Experimental pre-approved tool list for the skill. |
| `disable-model-invocation` | boolean | Set `true` to restrict skill to explicit manual `/skill:name` invocation. |
| `metadata` | map | Arbitrary key-value metadata pairs. |

## Invocation and Execution

### 1. Automatic Model Routing

When a user request matches a skill's `description`, the model reads `SKILL.md` and applies its instructions:

- **Input Prompt:** `"Extract the balance sheet table from quarterly_report.pdf"`
- **Routing:** Model matches description keywords in `pdf-tools` and loads `SKILL.md`.

### 2. Explicit Command Invocation

Users can directly trigger skills using slash commands in the interactive CLI. Any text following the command is passed to the loaded instructions as the user request:

```text
/skill:pdf-tools extract quarterly_report.pdf --tables-only
```

### 3. Session Reload

When editing skills during an active session, reload the skill cache without restarting Pi:

```text
/reload
```

## Distribution

Pi skills can be distributed individually or bundled inside Pi Packages:

- **Directory Sharing:** Check `.agents/skills/<skill-name>/` into version control.
- **Pi Packages:** Package skills using npm packages or git repositories as defined in Pi package configurations. Runtime environment setup should remain self-contained within the skill.
