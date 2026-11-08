# ZCode Harness Reference

Reference guide for skill discovery, layout conventions, precedence rules, and execution in ZCode.

- **Harness identifier:** `zcode` (CLI: `--agent zcode`)
- **Specification:** Anthropic Agent Skills (`SKILL.md`)

## Contents

- [Harness Identifiers](#harness-identifiers)
- [Compatibility Matrix](#compatibility-matrix)
- [Skill Paths](#skill-paths)
- [Settings & Configuration](#settings--configuration)
- [Discovery & Precedence](#discovery--precedence)
- [Feature Support](#feature-support)
- [Directory Layout](#directory-layout)
- [Invocation](#invocation)
- [Concrete Example](#concrete-example)

---

## Harness Identifiers

| Field | Value |
|---|---|
| CLI Identifier | `--agent zcode` |
| Supported Surfaces | ZCode CLI, ZCode IDE / Editor extension, Agent Tooling |
| Skill Specification | Anthropic Agent Skills standard (`SKILL.md`) |

---

## Compatibility Matrix

| Feature | Supported | Details |
|---|---|---|
| Basic Skills (`SKILL.md`) | Yes | Standard YAML frontmatter (`name`, `description`) and Markdown instructions. |
| `allowed-tools` Frontmatter | Yes | Restricts available agent tools when the skill activates. |
| `context: fork` | No | Sub-task isolation is handled via agent delegation rather than frontmatter context forking. |
| Agent Tooling | Yes | Native shell command execution, file system operations, and code inspection. |
| Model Context Protocol (MCP) | Yes | Configured via project or user configuration files. |
| CLI Integration | Yes | Non-interactive and interactive command-line skill execution. |

---

## Skill Paths

ZCode scans project-local and user-global paths for skill definitions.

### Project Skills (Workspace-Level)

- **Override Path**: `<workspace-root>/.zcode/skills/<skill-name>/SKILL.md`
- **Standard Path**: `<workspace-root>/.agents/skills/<skill-name>/SKILL.md`

Project skills are version-controlled alongside repository code. When a skill exists in both project locations with the same `name`, `.zcode/skills/` takes precedence over `.agents/skills/`.

### User Skills (Global)

- **Harness Path**: `~/.zcode/skills/<skill-name>/SKILL.md`
- **Standard Path**: `~/.agents/skills/<skill-name>/SKILL.md`

Global skills apply to all repositories and sessions on the host machine. ZCode-specific user skills in `~/.zcode/skills/` take precedence over generic `~/.agents/skills/`.

---

## Settings & Configuration

ZCode stores agent configuration, environment settings, and rules across dedicated scopes:

| Location | Path | Scope | Purpose |
|---|---|---|---|
| Project Rules | `<workspace-root>/AGENTS.md` | Workspace | High-priority project instructions loaded into agent context. |
| Project Settings | `<workspace-root>/.zcode/settings.json` | Workspace | Workspace-specific agent configurations, model selections, and tool overrides. |
| Workspace Skills | `<workspace-root>/.zcode/skills/` | Workspace | Repository-specific skill overrides. |
| Global Settings | `~/.zcode/settings.json` | Global / User | Machine-wide preferences, telemetry toggles, and default model flags. |
| Global Skills | `~/.zcode/skills/` | Global / User | Personal workflows available across all projects. |
| MCP Servers | `<workspace-root>/.zcode/mcp.json` or `~/.zcode/mcp.json` | Workspace / Global | Configuration for Model Context Protocol servers and connected tools. |

---

## Discovery & Precedence

When multiple skills share the same `name` property in their frontmatter, ZCode resolves collisions in strict priority order (highest to lowest):

1. **Project Override**: `<workspace-root>/.zcode/skills/<skill-name>/`
2. **Project Standard**: `<workspace-root>/.agents/skills/<skill-name>/`
3. **User Override**: `~/.zcode/skills/<skill-name>/`
4. **User Standard**: `~/.agents/skills/<skill-name>/`

Project-scoped skills always override global skills, ensuring team repository workflows take precedence over individual machine configurations.

---

## Feature Support

### Basic Skills
Skills require a `SKILL.md` file with valid YAML frontmatter containing `name` and `description` fields:

```yaml
---
name: db-migrate
description: Runs and validates database migrations. Use when applying database schema changes or verifying pending migrations.
---
```

### `allowed-tools` Restriction
Skills can restrict executable tools to a safe subset. Tools omitted from the list cannot be invoked while the skill is active:

```yaml
---
name: db-migrate
description: Runs and validates database migrations. Use when applying database schema changes or verifying pending migrations.
allowed-tools:
  - run_command
  - read_file
---
```

### Agent Tooling and CLI Integration
ZCode integrates skill workflows directly into its CLI tool loop:
- Shell execution: Skills can trigger scripts or CLI utilities using non-interactive command execution.
- File manipulation: Standard file reading and targeted edits are available for guided workflows.
- MCP Tools: External services and databases exposed via MCP servers can be called directly by skills.

---

## Directory Layout

A standard repository configured for ZCode with local skills and instructions:

```text
my-project/
├── .zcode/
│   ├── settings.json                    # Workspace settings
│   ├── mcp.json                         # Workspace MCP server configuration
│   └── skills/
│       └── db-migrate/
│           ├── SKILL.md                 # ZCode-specific skill override
│           ├── scripts/
│           │   └── run_migration.py     # Supporting migration runner
│           └── references/
│               └── rollback_guide.md    # Reference documentation
├── .agents/
│   └── skills/
│       └── code-review/
│           └── SKILL.md                 # Standard cross-agent skill
├── AGENTS.md                            # Project-wide agent rules
├── package.json
└── src/
    └── index.ts
```

---

## Invocation

ZCode provides three invocation methods for skills:

1. **Contextual Natural Language Triggering**: The skill metadata (`name` and `description`) is evaluated against user prompts. When a prompt matches the skill purpose, ZCode loads `SKILL.md` into the agent context.
2. **Interactive CLI Prompting**: Passing instructions to the interactive ZCode shell:
   ```bash
   zcode "Check pending database migrations and apply them"
   ```
3. **Targeted Agent Execution**: Specifying the ZCode harness identifier in automated or scripted runs:
   ```bash
   zcode --agent zcode "Execute db-migrate for staging environment"
   ```

---

## Concrete Example

### Example Skill: `db-migrate`

#### File: `.zcode/skills/db-migrate/SKILL.md`

````markdown
---
name: db-migrate
description: Runs and validates database migrations. Use when applying database schema changes or verifying pending migrations.
allowed-tools:
  - run_command
  - read_file
---

# Database Migration Workflow

Follow this procedure to inspect and apply database schema changes:

## Verification Steps

1. **Status Inspection**:
   Check for pending migration scripts:
   ```bash
   python3 scripts/run_migration.py --status
   ```

2. **Schema Application**:
   Apply pending migrations within a transaction:
   ```bash
   python3 scripts/run_migration.py --apply
   ```

3. **Integrity Validation**:
   Confirm all schema updates applied without errors:
   ```bash
   python3 scripts/run_migration.py --verify
   ```

## Output Format

Return migration results:
- **Status**: SUCCESS | FAILURE
- **Applied Migrations**: List of migration version numbers applied
- **Verification Result**: Schema check output
- **Next Steps**: Instructions for rollback or deployment
````

### Execution Example

**User Input:**
```
Check if there are any pending database migrations and apply them to the dev database.
```

**Agent Action:**
1. Evaluates user request against registered skill descriptions and matches `db-migrate`.
2. Reads `.zcode/skills/db-migrate/SKILL.md`.
3. Executes `python3 scripts/run_migration.py --status` to inspect pending migrations.
4. Executes `python3 scripts/run_migration.py --apply` to perform updates.
5. Executes `python3 scripts/run_migration.py --verify` to validate table states.
6. Returns formatted summary confirming status, applied migrations, and schema verification.
