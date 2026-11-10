# Qoder Harness Reference

Reference guide for skill discovery, directory structure, configuration precedence, and feature support in Qoder and Qoder CN CLI.

- **Harness identifiers:** `qoder`, `qoder-cn` (CLI: `--agent qoder`, `--agent qoder-cn`)
- **Documentation:** https://docs.qoder.com/cli/Skills

## Contents

- [Harness Identifiers](#harness-identifiers)
- [Compatibility Matrix](#compatibility-matrix)
- [Skill Paths](#skill-paths)
- [Settings & Configuration](#settings--configuration)
- [Discovery & Precedence](#discovery--precedence)
- [Feature Support](#feature-support)
- [Directory Layout](#directory-layout)
- [Invocation & Execution](#invocation--execution)
- [Concrete Example](#concrete-example)

---

## Harness Identifiers

| Field | Value |
|---|---|
| CLI Identifiers | `--agent qoder`, `--agent qoder-cn` |
| Supported Surfaces | Qoder CLI, Qoder IDE, JetBrains Plugin |
| Specification URL | `https://docs.qoder.com/cli/Skills` |

---

## Compatibility Matrix

| Feature | Supported | Details |
|---|---|---|
| Basic Skills (`SKILL.md`) | Yes | Standard YAML frontmatter (`name`, `description`) and Markdown instructions. |
| `allowed-tools` Frontmatter | Yes | Filters and restricts tools available during skill execution. |
| `context: fork` | No | Context forking in skill frontmatter is not supported. |
| Frontmatter Hooks | No | Skill files do not declare lifecycle hooks; hooks use Qoder hook configurations. |
| Subagents | Yes | Autonomous subagent execution is supported in Qoder CLI. |
| MCP Tools | Yes | MCP servers configured via Qoder configuration and callable by skills. |

---

## Skill Paths

Qoder searches project-level and global user directories for skills.

### Project Skills (Workspace-Scoped)
- **Path**: `{workspace-root}/.qoder/skills/<skill-name>/SKILL.md`
- **Scope**: Current project only. Suitable for team workflows, project-specific knowledge, and version-controlled scripts.

### Global Skills (User-Scoped)
- **Qoder Global Path**: `~/.qoder/skills/<skill-name>/SKILL.md`
- **Qoder CN Global Path**: `~/.qoder-cn/skills/<skill-name>/SKILL.md`
- **Scope**: Available across all projects for the current user. Used for personal workflows and utility tools.

---

## Settings & Configuration

Qoder stores CLI settings and configurations across user-level and project-level configuration files:

| Scope | Path | Purpose |
|---|---|---|
| User Configuration | `~/.qoder/config.json` (or `~/.qoder-cn/config.json`) | Global settings, authentication, default models, and global tool configurations. |
| Project Configuration | `{workspace-root}/.qoder/config.json` | Project-specific overrides, workspace permissions, and local tool settings. |
| User Skills | `~/.qoder/skills/` (or `~/.qoder-cn/skills/`) | User-wide custom skill definitions. |
| Project Skills | `{workspace-root}/.qoder/skills/` | Workspace-level custom skill definitions. |

---

## Discovery & Precedence

At startup, Qoder CLI scans available skill directories and loads each skill's `name` and `description` into model memory:

1. **Discovery Order**:
   - Project directory: `{workspace-root}/.qoder/skills/`
   - User configuration: `~/.qoder/skills/` (or `~/.qoder-cn/skills/` for Qoder CN)

2. **Precedence**:
   - Configuration settings: Project directory (`.qoder/config.json`) takes precedence over user configuration (`~/.qoder/config.json`).
   - Skill collisions: When skills share identical names across scopes, project directory definitions take precedence over user configuration definitions within workspace execution context.

3. **Session Refreshing**:
   - Reload discovered skills without restarting the CLI session using `/skills reload`.
   - List active skills using `/skills` or prompting `"What Skills are available?"`.

---

## Feature Support

### Frontmatter Specifications
Skills require standard YAML frontmatter between `---` fences at the beginning of `SKILL.md`:

| Field | Required | Description | Constraints |
|---|---|---|---|
| `name` | Yes | Unique skill identifier | Lowercase letters, numbers, and hyphens; max 64 characters. |
| `description` | Yes | Functional explanation and trigger conditions | Concise purpose and scenario keywords; max 1024 characters. |
| `allowed-tools` | Optional | Whitelist of tools accessible to the skill | List of tool strings. |

### `allowed-tools` Restriction
Skills can restrict execution capabilities using `allowed-tools`. Only listed tools remain callable when the skill is active:

```yaml
---
name: schema-migrator
description: Generate and apply database schema migrations. Use when modifying database schemas or running Alembic migrations.
allowed-tools:
  - run_command
  - read_file
---
```

### Progressive Disclosure
Auxiliary documentation (`REFERENCE.md`, `EXAMPLES.md`), templates (`templates/`), and helper scripts (`scripts/`) reside alongside `SKILL.md`. Qoder loads the main `SKILL.md` first, retrieving auxiliary files only when referenced during execution.

---

## Directory Layout

A standard project workspace with Qoder skills adheres to the following tree structure:

```text
my-project/
├── .qoder/
│   ├── config.json                      # Project-level CLI configuration
│   └── skills/
│       ├── database-migrator/
│       │   ├── SKILL.md                 # Required skill entrypoint
│       │   ├── REFERENCE.md             # Optional detailed reference
│       │   └── scripts/
│       │       └── validate_schema.py   # Optional helper script
│       └── log-analyzer/
│           ├── SKILL.md
│           └── templates/
│               └── report_format.txt
├── package.json
└── src/
    └── index.ts
```

---

## Invocation & Execution

Qoder supports two primary invocation modes:

1. **Prompt Triggers (Automatic Invocation)**:
   - At startup, Qoder indexes skill `name` and `description` attributes.
   - When user prompts match trigger keywords, the model autonomously activates the skill, reads the full `SKILL.md`, and runs the outlined workflow.

2. **CLI Execution (Manual Invocation)**:
   - Run `/<skill-name>` as an interactive slash command (for example, `/database-migrator`).
   - The skill converts internally to an interactive command and executes immediately.

---

## Concrete Example

### Example Skill: `database-migrator`

#### File: `.qoder/skills/database-migrator/SKILL.md`

```markdown
---
name: database-migrator
description: Generate and manage database schema migrations. Use when creating database migrations, modifying schemas, or validating migration scripts.
allowed-tools:
  - read_file
  - run_command
---

# Database Migrator

Follow this workflow to create, validate, and apply database migrations safely.

## Workflow

1. **Inspect Schema Changes**:
   Compare desired model definitions with the target database schema:
   ```bash
   python3 scripts/validate_schema.py --target staging
   ```

2. **Generate Migration Script**:
   Create a timestamped migration file containing upgrade and downgrade functions.

3. **Validate Execution**:
   Run the migration in dry-run mode before applying to target databases.

## Output Format

Output:
- **Migration File**: `migrations/<timestamp>_change_summary.py`
- **Validation**: PASS | FAIL
- **Tables Modified**: List of affected database tables
- **Rollback Tested**: Yes | No
```

### Execution Example

**Input:**
```
Create a database migration to add an email_verified column to the accounts table.
```

**Output:**
```
Applying skill: database-migrator
Reading .qoder/skills/database-migrator/SKILL.md
Executed schema validation script.
Generated migration: migrations/20261108_add_email_verified.py
Validation: PASS
Tables Modified: accounts
Rollback Tested: Yes
```
