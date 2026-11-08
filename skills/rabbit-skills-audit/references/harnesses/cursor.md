# Cursor Harness Reference

Reference for skill discovery, compatibility, configuration, and invocation in Cursor.

- **Harness Identifier:** `--agent cursor`
- **Official Documentation:** https://cursor.com/docs/context/skills

## Contents

- [Skill Paths](#skill-paths)
- [Settings & Configuration](#settings--configuration)
- [Discovery & Precedence](#discovery--precedence)
- [Feature Support](#feature-support)
- [Directory Layout](#directory-layout)
- [Invocation](#invocation)

## Skill Paths

Cursor discovers skills from both project-level and user-level (global) directories.

| Scope | Canonical Path | Supported Alternatives / Fallbacks |
|---|---|---|
| **Project** | `.agents/skills/<skill-name>/` | `.cursor/skills/<skill-name>/`, `.claude/skills/<skill-name>/`, `.codex/skills/<skill-name>/` |
| **User (Global)** | `~/.cursor/skills/<skill-name>/` | `~/.agents/skills/<skill-name>/`, `~/.claude/skills/<skill-name>/`, `~/.codex/skills/<skill-name>/` |

### Path Notes
- **Project skills:** Shared via version control in `.agents/skills/` (standard) or `.cursor/skills/` (legacy).
- **Global skills:** Local to machine in `~/.cursor/skills/`. To expose global skills to Cloud Agents, enable **Sync Skills for Cloud Agents** under Settings (`~/.cursor/skills/` only; `~/.agents/skills/` does not sync).
- **Monorepos:** Nested project directories can contain their own `.agents/skills/` or `.cursor/skills/` (e.g. `packages/backend/.agents/skills/`).

## Settings & Configuration

Cursor configuration files influencing agent and skill execution:

| Scope | Path | Purpose |
|---|---|---|
| **Project Rules (Legacy)** | `.cursorrules` | Single-file plain text system prompt additions. |
| **Project Rules (Modern)** | `.cursor/rules/*.mdc` | Modular markdown rules with glob and intelligent activation filters. |
| **Project Settings** | `.cursor/settings.json`, `.vscode/settings.json` | Project-specific workspace editor and agent parameters. |
| **Global Settings** | `~/.cursor/` | Global user configuration and caches (e.g., `~/.cursor/cli-config.json`). |
| **Plugin Manifest** | `.cursor-plugin/marketplace.json` | Plugin packaging to distribute skills, rules, and extensions across repositories. |

## Discovery & Precedence

Cursor scans for `SKILL.md` files at startup and when workspace context changes:

1. **Resolution Precedence:**
   - **Project-level skills override user-level skills.** When a skill in `.agents/skills/<name>` shares a name with a skill in `~/.cursor/skills/<name>`, the project-level skill is loaded.
   - For skills in monorepos, skills in a nested subfolder take priority for files inside that subfolder.
2. **Recursive Directory Traversal:**
   - Cursor traverses subdirectories within skill directories. A skill located at `.agents/skills/review/security/SKILL.md` is registered under its parent folder name (`security`).
3. **Context Filtering:**
   - When a skill defines `paths: [...]` frontmatter or resides in a sub-project directory, it is surfaced only when agent activity involves matching file paths.

## Feature Support

Compatibility with standard Agent Skills specifications:

| Feature | Supported | Notes |
|---|---|---|
| **Basic Skills (`SKILL.md`)** | **Yes** | Standard YAML frontmatter (`name`, `description`) and Markdown body. |
| **Tool Restriction (`allowed-tools`)** | **Yes** | Restricts active tools when the skill is applied. |
| **Forked Context (`context: fork`)** | **No** | Executes in the current agent session; does not spawn an isolated subagent fork. |
| **Skill Hooks** | **No** | Skill-level hooks are not supported. (Cursor provides separate lifecycle hooks via `hooks.json`). |

### Cursor-Specific Frontmatter Attributes

Cursor supports additional frontmatter fields beyond the base specification:

- `paths`: Glob patterns (list or comma-separated string) restricting when the skill is loaded based on open/modified files.
- `disable-model-invocation`: Set to `true` to disable automatic model activation; skill only loads when explicitly requested.
- `icon`: Icon name for Custom Mode UI display (e.g., `beaker`, `terminal`, `bug`).
- `color`: Accent color for Custom Mode UI badges (e.g., `green`, `blue`, `brand`).

## Directory Layout

Concrete layout for a standard project skill:

```
my-project/
├── .agents/
│   └── skills/
│       └── db-migrate/
│           ├── SKILL.md
│           ├── scripts/
│           │   └── run-migration.sh
│           └── references/
│               └── schema-rules.md
├── .cursor/
│   ├── rules/
│   │   └── database.mdc
│   └── settings.json
└── src/
    └── index.ts
```

### Example SKILL.md

```markdown
---
name: db-migrate
description: Runs database schema migrations and validates migration integrity. Use when creating or applying database migrations.
allowed-tools:
  - run_command
  - read_file
paths:
  - "migrations/**"
  - "prisma/**"
---

# Database Migration

Run and verify schema migrations.

## Workflow

1. Validate existing migration status:
   ```bash
   scripts/run-migration.sh --status
   ```
2. Apply pending migrations and verify output against "`references/schema-rules.md`".
```

## Invocation

Skills are activated through automatic model selection or manual user invocation:

### 1. Automatic Semantic Triggering
When a user prompt aligns with the skill's `description`, Cursor includes the skill in the agent's context window.

- **Input Prompt:** `"Check whether our pending prisma migrations are valid and apply them"`
- **Agent Behavior:** Matches `description` keywords and opens `SKILL.md` instructions.

### 2. Explicit Mention / Slash Command
Users can invoke skills directly in Agent chat:
- `@db-migrate` or `/db-migrate` attached to a single chat prompt.

### 3. Session Custom Mode
A skill can back an ongoing session mode using `Option+Enter` (macOS) or `Alt+Enter` (Windows/Linux) in chat, pinning the skill instructions into context across all follow-up turns.
