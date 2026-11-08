# OpenHands Harness Reference

Harness configuration, skill discovery paths, and execution characteristics for OpenHands.

## Contents

- [Overview](#overview)
- [Harness Identifier](#harness-identifier)
- [Skill Discovery Paths](#skill-discovery-paths)
- [Settings and Configuration](#settings-and-configuration)
- [Discovery and Precedence](#discovery-and-precedence)
- [Feature Support Matrix](#feature-support-matrix)
- [Directory Layout](#directory-layout)
- [Invocation and Triggering](#invocation-and-triggering)

## Overview

OpenHands supports agent skills defined via `SKILL.md` specifications, loaded either automatically through context-aware keyword matching or manually via chat commands.

## Harness Identifier

When executing harness-targeted audits or compatibility checks:

```bash
--agent openhands
```

## Skill Discovery Paths

OpenHands resolves skills across project-scoped and user-scoped locations:

| Scope | Primary Path | Fallback / Standard Path |
|-------|--------------|--------------------------|
| **Project** | `.openhands/skills/` | `.agents/skills/` |
| **Global (User)** | `~/.openhands/skills/` | `~/.agents/skills/` |

- **Project Skills**: Committed directly inside the target repository. Applicable to all sessions working in the repository.
- **Global Skills**: Stored in the user home directory. Available across all workspaces and projects for the local user.

## Settings and Configuration

OpenHands stores environment settings, agent parameters, and instruction overrides across configuration files:

- **`config.toml`**: Main configuration file placed at repository root or `~/.openhands/config.toml`. Configures runtime options, model choices, and security sandboxing.
- **`AGENTS.md`**: Repository-level instruction and guidance file at project root. Defines repo context, development workflows, and constraints provided to agents.
- **Microagent Definitions**: Custom microagents and domain-specific rules can reside in `.openhands/microagents/` (e.g., `repo.md` for repository knowledge).

## Discovery and Precedence

When identical skill names or triggers collide, OpenHands resolves them in descending order of precedence:

1. **Project Skills**: `.openhands/skills/<skill-name>` and `.agents/skills/<skill-name>` take highest priority.
2. **User Skills**: `~/.openhands/skills/<skill-name>` and `~/.agents/skills/<skill-name>` take secondary priority.
3. **Built-in Extensions**: Default system microagents and built-in extensions load only when not overridden by project or user skills.

## Feature Support Matrix

| Feature | Supported | Notes |
|---------|-----------|-------|
| **Basic Skills (`SKILL.md`)** | Yes | Full YAML frontmatter (`name`, `description`) and markdown body support. |
| **`allowed-tools` Restriction** | Yes | Restricts agent tool calls to specified list when declared in skill metadata. |
| **`context: fork` Isolation** | No | Forked subagent execution contexts are not supported via skill frontmatter. |
| **Lifecycle Hooks** | No | Pre-execution and post-execution shell hooks are ignored. |
| **Chat Command `/add-skill`** | Yes | Supports manual explicit injection into conversation context. |

## Directory Layout

Example structure of a project incorporating OpenHands skills:

```text
my-project/
├── .openhands/
│   ├── skills/
│   │   └── code-auditor/
│   │       ├── SKILL.md
│   │       ├── references/
│   │       │   └── audit-rules.md
│   │       └── scripts/
│   │           └── lint.py
│   └── microagents/
│       └── repo.md
├── AGENTS.md
├── config.toml
└── src/
```

### Concrete Skill Example

```markdown
---
name: code-auditor
description: Audits code quality and static checks. Use when reviewing code or running linter checks.
allowed-tools:
  - bash
  - read_file
---

# Code Auditor

Audit instructions and execution procedures:

1. Run static lint:
   ```bash
   python3 scripts/lint.py
   ```
2. Verify output and report findings.
```

## Invocation and Triggering

OpenHands supports two invocation mechanisms:

1. **Prompt Keyword Matching**:
   OpenHands matches prompt intent and keywords against skill `description` fields and metadata to load relevant skills automatically during agent execution.

2. **Explicit Chat Command**:
   Users load a skill manually in the chat interface:
   ```text
   /add-skill code-auditor
   ```
