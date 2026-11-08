# Replit Harness Reference

Reference guide for skill discovery, directory structure, configuration precedence, and feature support in Replit and Replit Agent.

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
| CLI Identifier | `--agent replit` |
| Fallback / Standard Identifier | `--agent universal` |
| Supported Surfaces | Replit Agent (Chat & Plan Mode), Replit Core IDE, Replit Mobile / Desktop App |
| Documentation URL | `https://docs.replit.com/features/agent/skills` |

---

## Compatibility Matrix

| Feature | Supported | Details |
|---|---|---|
| Basic Skills (`SKILL.md`) | Yes | Standard YAML frontmatter (`name`, `description`) with Markdown instructions. |
| Tool Restriction (`allowed-tools`) | Yes | Restricts active workspace tools available to the agent during execution. |
| Forked Context (`context: fork`) | No | Executes within the active Repl session; task isolation uses Replit Agent routines. |
| Skill Frontmatter Hooks | No | Lifecycle hooks in frontmatter are not supported; environment lifecycle uses `.replit`. |
| Workspace Tools | Yes | Direct agent integration with Shell, Console, Database, Secrets, and Deployments. |
| Universal Standard | Yes | Uses the standard `.agents/skills/` directory convention shared across agents. |

---

## Skill Paths

Replit discovers skills across project-level (Repl) and workspace-level (team/global) scopes.

### Project Skills (Repl Scope)
- **Primary Path**: `<repl-root>/.agents/skills/<skill-name>/SKILL.md`
- **Fallback / Legacy Path**: `<repl-root>/.replit/skills/<skill-name>/SKILL.md`
- **Behavior**: Scanned within the active Repl project. Stored alongside application files and committed to git or Repl Checkpoints, ensuring all project collaborators share identical skills.

### Workspace Skills (Team Library Scope)
- **Central Storage**: Managed in Workspace Settings (`Settings > Customization > Skills`).
- **Local / Machine Global Path**: `~/.config/agents/skills/<skill-name>/SKILL.md`
- **Member Access Policies**:
  - `Required`: Enforced workspace-wide; always active across all Repls and cannot be turned off.
  - `Available`: Optional, off by default; members enable the skill per Repl via the chat interface.
  - `No access`: Restricted to skill authors and workspace administrators.

### Pre-defined Platform Skills
- Bundled platform skills provided by Replit and partners; accessible across all Repls via the chat picker without manual installation.

---

## Settings & Configuration

Replit stores project configuration, environment variables, and agent guidelines in dedicated configuration files:

| Location | Path | Scope | Purpose |
|---|---|---|---|
| Agent Instructions | `replit.md` | Repl Project | High-priority project instructions and architectural guidelines loaded into agent prompt context. |
| Project Configuration | `.replit` | Repl Project | TOML configuration defining entrypoints, run commands, nix channels, workflows, and ports. |
| System Packages | `replit.nix` | Repl Project | Nix configuration declaring binary dependencies, runtime toolchains, and system packages. |
| Project Skills | `<repl-root>/.agents/skills/` | Repl Project | Project-specific skills versioned in repository files. |
| Modular Rules | `<repl-root>/.agents/rules/*.md` | Repl Project | Contextual coding rules and domain conventions. |
| Project Secrets | Replit Secrets Tool | Repl Project | Encrypted key-value credentials injected as environment variables without writing to disk. |
| Global Skills | `~/.config/agents/skills/` | Machine / User | User-wide skills shared across local environments and CLI runs. |

---

## Discovery & Precedence

When skills share identical `name` attributes, Replit Agent resolves collisions in strict priority order (highest to lowest):

1. **Repl Project Skills**: `.agents/skills/<skill-name>/` (and `.replit/skills/`). Project-level definitions override workspace-level or platform skills with the same name.
2. **Workspace Required Skills**: Centrally enforced skills marked `Required` by workspace administrators.
3. **Workspace Available Skills**: Team skills enabled for the active Repl session.
4. **Pre-defined Platform Skills**: Built-in skills bundled with Replit Agent.
5. **Global User Skills**: `~/.config/agents/skills/` from user configuration.

### Progressive Disclosure
To preserve the context window:
- **Startup / Turn Zero**: Replit Agent loads only the `name` and `description` frontmatter from each installed skill (~100 tokens per skill).
- **Execution**: The complete Markdown body of `SKILL.md` is loaded into the prompt context only when the user query matches the skill's declared scope.

---

## Feature Support

### Workspace Tool Integration
Skills can instruct Replit Agent to operate across native Repl workspace tools:
- **Shell**: Execute CLI commands, run migration scripts, and install dependencies.
- **Console**: Monitor application runtime logs and debugging output.
- **Database**: Query and update PostgreSQL databases configured within the Repl.
- **Secrets**: Access environment variables configured securely in the Secrets tool.
- **Deployments**: Verify deployment configurations and production health checks.

### `allowed-tools` Restriction
Skills can whitelist permitted tools in YAML frontmatter to prevent unintended tool calls:

```yaml
---
name: db-migrate
description: Runs database schema migrations and checks schema consistency.
allowed-tools:
  - run_command
  - read_file
---
```

### GitHub Skill Import
Replit Agent supports importing skills from public GitHub repositories directly via the Workspace Skills interface (`+ > Use a skill > Preview skills > Import`). Imports are limited to 50 skills, 3,500 files, or 200 MiB per repository.

---

## Directory Layout

A standard Replit project with local skills and workspace configuration follows this directory tree:

```
my-repl/
├── .agents/
│   ├── rules/
│   │   └── code-style.md
│   └── skills/
│       └── db-migrate/
│           ├── SKILL.md
│           ├── scripts/
│           │   └── run_migration.py
│           └── references/
│               └── migration-guide.md
├── .replit
├── replit.nix
├── replit.md
├── package.json
└── src/
    └── index.ts
```

---

## Invocation

Replit Agent supports three skill invocation models:

1. **Autonomous Semantic Triggering**: Replit Agent matches the incoming user prompt against skill descriptions declared in frontmatter. When a prompt aligns with the declared intent, the agent loads `SKILL.md` automatically.
2. **Interactive Chat Picker**: Users can select skills manually by clicking `+` > `Use a skill` in the agent chat input.
3. **Explicit Chat Command**: Users can trigger a skill by name directly in the chat prompt (e.g., "Use db-migrate to apply pending database changes").

---

## Concrete Example

### Example Skill: `db-migrate`

#### File: `.agents/skills/db-migrate/SKILL.md`

```markdown
---
name: db-migrate
description: Runs database schema migrations and verifies database integrity. Use when applying database changes or checking schema status.
allowed-tools:
  - run_command
  - read_file
---

# Database Migration Workflow

Apply and verify database schema migrations in the Repl environment.

## Execution Steps

1. Check current migration status:
   ```bash
   python3 scripts/run_migration.py --status
   ```

2. Apply pending migrations:
   ```bash
   python3 scripts/run_migration.py --apply
   ```

3. Verify schema state and format the output using the template below.

## Output Format

Output:
- **Status**: SUCCESS | FAILURE
- **Applied Migrations**: Number of migration files applied
- **Database Version**: Current schema version hash
- **Notes**: Operational observations or error details
```

### Execution Example

**User Input:**
```
Input: Apply the latest database migration and verify the schema version.
```

**Agent Execution:**
1. Evaluates user request against skill descriptions and selects `db-migrate`.
2. Loads `.agents/skills/db-migrate/SKILL.md` into active context.
3. Executes `python3 scripts/run_migration.py --status` in the Repl Shell.
4. Executes `python3 scripts/run_migration.py --apply`.
5. Emits the final status report matching the Output Format template:

**Skill Output:**
```
Output:
- **Status**: SUCCESS
- **Applied Migrations**: 2
- **Database Version**: a1f89c2
- **Notes**: Successfully applied migrations 003_add_users and 004_create_sessions.
```
