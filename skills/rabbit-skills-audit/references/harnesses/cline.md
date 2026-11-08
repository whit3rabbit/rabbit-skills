# Cline Harness Reference

Official Documentation: https://docs.cline.bot/features/skills

## Contents

- [Identifier](#identifier)
- [Skill Paths](#skill-paths)
- [Settings & Configuration](#settings--configuration)
- [Discovery & Precedence](#discovery--precedence)
- [Feature Support](#feature-support)
- [Directory Layout](#directory-layout)
- [Invocation & Tool Integration](#invocation--tool-integration)
- [Concrete Example](#concrete-example)

---

## Identifier

- CLI / configuration flag: `--agent cline`
- Harness identifier: `cline`

---

## Skill Paths

Cline discovers skills from project-level and user-level directories.

### Project (Workspace)

- `.agents/skills/<skill-name>/` (cross-harness standard)
- `.cline/skills/<skill-name>/` (Cline standard)
- Alternate fallback paths: `.clinerules/skills/`, `.claude/skills/`

### Global (User)

- `~/.agents/skills/<skill-name>/` (cross-harness standard)
- `~/.cline/skills/<skill-name>/` (Linux and macOS)
- `%USERPROFILE%/.cline/skills/<skill-name>/` (Windows)

---

## Settings & Configuration

### Instructions and Rules

- **Workspace Rules**: Stored in `.clinerules` at the workspace root, or split across `.cline/rules/*.md`. Rules load on every turn.
- **Custom Modes**: Stored in `cline_custom_modes.json` within global storage, configuring role instructions and tool allowances.

### Configuration and Secret Storage

- **Extension Code**: `~/.vscode/extensions/saoudrizwan.claude-dev-*/`
- **Global Storage**:
  - macOS: `~/Library/Application Support/Code/User/globalStorage/saoudrizwan.claude-dev/settings/`
  - Linux: `~/.config/Code/User/globalStorage/saoudrizwan.claude-dev/settings/`
  - Windows: `%APPDATA%/Code/User/globalStorage/saoudrizwan.claude-dev/settings/`
- **MCP Configuration**: `cline_mcp_settings.json` in global storage defines MCP servers and tool configs.
- **API Keys**: Stored in the host OS credential vault via VS Code SecretStorage API.

---

## Discovery & Precedence

1. **Discovery**: On startup and task initialization, Cline scans project skill directories and global directories.
2. **Metadata Registration**: Extracts `name` and `description` from each skill's `SKILL.md` YAML frontmatter into an active capability index (~100 tokens per skill).
3. **Precedence**: Local workspace skills override global skills when skill names match. Project-specific definitions take precedence over user-level defaults.
4. **Toggling**: Skills can be toggled on or off via the Skills tab in the Cline UI panel without removing files from disk.

---

## Feature Support

| Feature | Supported | Description |
|---|---|---|
| Basic Skills | Yes | Requires `SKILL.md` with YAML frontmatter containing `name` and `description`. |
| `allowed-tools` | Yes | Supported for restricting available tools within execution contexts. |
| Context Forking (`context: fork`) | No | Context forking is unsupported; all skills execute within the primary task context. |
| Lifecycle Hooks | Yes | Pre-tool and post-tool execution hooks are supported via configuration. |
| Slash Command Invocation | Yes | Trigger explicit skills directly in chat input via `/<skill-name>`. |
| Supporting Resources | Yes | On-demand access to bundled `scripts/`, `templates/`, and `docs/`. |

---

## Directory Layout

```
workspace-root/
├── .clinerules
├── .cline/
│   ├── rules/
│   │   └── workflow-rules.md
│   └── skills/
│       └── db-migrate/
│           ├── SKILL.md
│           ├── scripts/
│           │   └── run_migration.py
│           └── templates/
│               └── migration.sql
└── .agents/
    └── skills/
        └── pr-checklist/
            └── SKILL.md
```

---

## Invocation & Tool Integration

### Progressive Disclosure

- **Metadata Tier**: Only `name` and `description` are loaded into system prompts at initialization.
- **Activation Tier**: `SKILL.md` instructions load only when the skill is activated by a task.
- **Resource Tier**: Additional files (`docs/`, `templates/`, `scripts/`) remain on disk until explicitly accessed.

### Invocation Triggers

- **Natural Language Triggering**: Semantic matching against skill descriptions. Cline invokes its internal skill activation tool to load instructions.
- **Slash Commands**: Explicit invocation via chat prompt `/<skill-name>` (e.g. `/db-migrate`).

### MCP Server Integration

Skills invoke tools exposed by Model Context Protocol (MCP) servers declared in `cline_mcp_settings.json`. MCP tool references follow the qualified format `ServerName:tool_name` (e.g. `PostgresDB:execute_query`).

---

## Concrete Example

### Skill Definition

File: `.cline/skills/db-migrate/SKILL.md`

```markdown
---
name: db-migrate
description: Executes database migrations and schema rollbacks. Use when applying SQL migrations, updating database schemas, or validating database status.
allowed-tools:
  - PostgresDB:execute_query
  - read_file
---

# Database Migration

Run schema migrations safely.

## Workflow

1. Check current schema migration version.
2. Apply pending migration scripts.
3. Validate schema integrity.
```

### Execution

**Input:**
```
User: /db-migrate Apply pending migration 2026_01_add_users.sql
```

**Output:**
```
1. Loaded skill instructions from .cline/skills/db-migrate/SKILL.md.
2. Verified pending migration file at templates/2026_01_add_users.sql.
3. Executed migration query via PostgresDB:execute_query.
4. Schema version updated successfully to 2026_01.
```
