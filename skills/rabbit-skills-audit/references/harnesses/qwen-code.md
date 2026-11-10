# Qwen Code Harness Reference

Reference for skill discovery, directory structure, configuration, feature support, and invocation in Qwen Code.

- **Harness Identifier:** `--agent qwen-code`
- **Specification Documentation:** https://qwenlm.github.io/qwen-code-docs/en/users/features/skills/

## Contents

- [Harness Identifiers](#harness-identifiers)
- [Compatibility Matrix](#compatibility-matrix)
- [Skill Paths](#skill-paths)
- [Settings & Configuration](#settings--configuration)
- [Discovery & Precedence](#discovery--precedence)
- [Feature Support](#feature-support)
- [Concrete Directory Layout](#concrete-directory-layout)
- [Invocation](#invocation)
- [Concrete Example](#concrete-example)

---

## Harness Identifiers

| Field | Value |
|---|---|
| CLI Identifier | `--agent qwen-code` |
| Supported Surfaces | Qwen Code CLI, IDE Extensions (VS Code, JetBrains, Zed), Daemon Mode |
| Documentation URL | `https://qwenlm.github.io/qwen-code-docs/en/users/features/skills/` |

---

## Compatibility Matrix

| Feature | Supported | Details |
|---|---|---|
| Basic Skills (`SKILL.md`) | Yes | Standard YAML frontmatter (`name`, `description`, optional `priority`) and Markdown body. |
| Tool Restriction (`allowedTools`) | Yes | Restricts active tools via camelCase `allowedTools`. (Hyphenated `allowed-tools` is ignored). |
| Multi-Lingual & Unicode | Yes | Skill names support `^[\p{L}\p{N}_:.-]+$` (CJK, Cyrillic, accented Latin). Descriptions and prompts support multi-lingual text. |
| Deterministic Hooks (`hooks:`) | Yes | Frontmatter lifecycle hooks (e.g., `PreToolUse`) executed through shell via `$QWEN_SKILL_ROOT`. |
| Path Gating (`paths:`) | Yes | Glob filters matched via `picomatch` relative to project root; skill remains inactive until a matching file is touched. |
| Invocation Visibility Controls | Yes | `user-invocable: false` hides from `/` picker; `disable-model-invocation: true` hides from autonomous model use. |
| Auto-Skill Maintenance | Yes | `/learn` distills sources into project skills; `/curator` tracks stale (30d) and archived (90d) transitions. |
| Forked Context (`context: fork`) | No | Context forking in frontmatter is not supported; executions occur in the active session. |

---

## Skill Paths

Qwen Code discovers skills across workspace, user, extension, and bundled scopes:

| Scope | Canonical Path | Fallback / Alternative Paths | Description |
|---|---|---|---|
| **Project (Workspace)** | `.qwen/skills/<skill-name>/` | `.agents/skills/<skill-name>/` | Project-specific skills committed to version control. `.qwen/skills/` wins on collision. |
| **Learned / Auto-Skills** | `.qwen/skills/learned-skill-*/` | `.qwen/skills/auto-skill-*/` | Distilled via `/learn` or Auto Skill generator. Archived to `.qwen/archived-skills/`. |
| **User (Global)** | `~/.qwen/skills/<skill-name>/` | `~/.agents/skills/<skill-name>/` | Personal skills available across all projects. `~/.qwen/skills/` wins on collision. |
| **Custom Directories** | Configured in `skills.directories` | None | Additional filesystem paths loaded as personal skills (e.g., `["~/.claude/skills"]`). |
| **Extension Skills** | `{extension-root}/skills/` | None | Skills packaged in installed extensions, registered as `<extensionName>:<skill-name>`. |
| **Bundled Skills** | Internal binary assets | None | Built-in skills packaged with Qwen Code. |

---

## Settings & Configuration

Qwen Code configuration files and directories:

| Scope | Path | Purpose |
|---|---|---|
| **Project Workspace** | `.qwen/` | Workspace root holding project skills, learned skills, and archived skills. |
| **Project Settings** | `.qwen/settings.json`, `.qwen/config.json` | Project-level settings, folder trust overrides, and workspace skill toggles. |
| **Global User Configuration** | `~/.qwen/config.json`, `~/.qwen/settings.json` | Global settings, model provider keys, trusted folders, and skill directories. |
| **Archived Skills** | `.qwen/archived-skills/` | Storage for auto-skills moved out of active library after inactivity. |

### Skill Configuration Keys

Configured under `~/.qwen/config.json` or project settings:

- `skills.directories`: Array of absolute or `~`-prefixed paths to scan for additional personal skills.
- `skills.enabled`: Array of skill names explicitly enabled. For extension skills, use the qualified registered name (`<extensionName>:<name>`).
- `skills.disabled`: Array of skill names disabled across model and user invocation surfaces.
- `skills.defaultDisabled`: Array of skill names disabled by default until toggled on in the `/skills` panel.
- `security.folderTrust.enabled`: Enables folder trust validation. Project-level `hooks:` and `allowedTools` side effects require explicit folder trust.

---

## Discovery & Precedence

When skills share identical registered names, Qwen Code resolves collisions in strict hierarchical order:

```
Project (.qwen/skills > .agents/skills)
  └── User (~/.qwen/skills > ~/.agents/skills > skills.directories)
        └── Extension (<extensionName>:<skill-name>)
              └── Bundled Built-in Skills
```

### Precedence Rules

1. **Workspace Overrides Global**: A project skill in `.qwen/skills/<name>` shadows a personal skill in `~/.qwen/skills/<name>`.
2. **Canonical Over Generic**: Inside the same scope, `.qwen/skills/` overrides `.agents/skills/`.
3. **Extension Namespacing**: Extension skills register as `<extensionName>:<skill-name>` (for example, `rust:pdf`), preventing collisions with un-prefixed user skills. An explicitly authored user or project skill named `rust:pdf` outranks the extension skill.
4. **Custom Command Collision**: Custom slash commands load after skills. If a custom command shares a name with a skill, typing `/<name>` triggers the custom command on the slash surface, while the skill remains accessible to autonomous model selection.
5. **Live Directory Watching**: Qwen Code watches personal and project skill directories during active sessions. Changes to `SKILL.md` reload automatically without restarting the CLI.

---

## Feature Support

### Multi-Lingual & Unicode Skill Names
Qwen Code validates skill names against Unicode letters and digits: `/^[\p{L}\p{N}_:.-]+$/u`. Non-Latin characters (Chinese, Japanese, Korean, Cyrillic) are valid in names, descriptions, and prompt instructions.

### Tool Restrictions (`allowedTools`)
Skills can constrain accessible tools while running by specifying `allowedTools` in camelCase:

```yaml
---
name: schema-lint
description: Lint SQL database schema files for syntax and index conventions.
allowedTools:
  - run_shell_command
  - read_file
---
```

### Path-Gated Activation (`paths:`)
Skills targeting specific repository locations remain hidden from the model's catalog until matching files are touched by a tool call:

```yaml
---
name: tsx-helper
description: React TSX component helper for UI rendering.
paths:
  - 'src/**/*.tsx'
  - 'packages/*/src/**/*.tsx'
---
```

### Deterministic Lifecycle Hooks (`hooks:`)
Frontmatter hooks enforce programmatic constraints independent of model compliance. The `$QWEN_SKILL_ROOT` environment variable resolves to the directory containing `SKILL.md`:

```yaml
---
name: release-gate
description: Validates CI status before triggering deployment.
hooks:
  PreToolUse:
    - matcher: run_shell_command
      hooks:
        - type: command
          command: '"$QWEN_SKILL_ROOT/scripts/verify-ci.sh"'
---
```

Project hook execution requires a trusted workspace (`security.folderTrust.enabled: true`). Exit code `2` blocks the tool call and feeds standard error back to the model.

---

## Concrete Directory Layout

Standard repository structure for a project utilizing Qwen Code skills:

```
my-repo/
├── .qwen/
│   ├── settings.json
│   ├── archived-skills/
│   └── skills/
│       ├── learned-skill-auth/
│       │   └── SKILL.md
│       └── sql-reviewer/
│           ├── SKILL.md
│           ├── scripts/
│           │   └── check-queries.py
│           └── references/
│               └── query-rules.md
├── .agents/
│   └── skills/
│       └── cross-tool-lint/
│           └── SKILL.md
├── src/
│   └── db/
│       └── queries.sql
└── package.json
```

---

## Invocation

Qwen Code supports dual invocation pathways:

### 1. Autonomous Model Invocation (Progressive Disclosure)
- Skill metadata (`name` and `description`) is exposed in prompt context (`<available_skills>`).
- When user prompts match keywords or intent described in `description`, the model autonomously invokes the skill tool: `Skill { skill: "<name>" }`.
- Setting `disable-model-invocation: true` in frontmatter hides the skill from autonomous model selection.

### 2. Manual Slash Command Invocation
- Any discovered skill is directly runnable via `/<skill-name>` (or `/<extensionName>:<skill-name>`).
- Typing `/skills` opens the interactive management panel to browse, search, and toggle skills.
- Setting `user-invocable: false` in frontmatter hides the skill from slash autocomplete and the `/skills` panel while retaining autonomous model invocation.

---

## Concrete Example

### Example Skill: `sql-reviewer`

#### File: `.qwen/skills/sql-reviewer/SKILL.md`

```markdown
---
name: sql-reviewer
description: Reviews SQL migration scripts for indexing conventions, locking hazards, and syntax issues. Use when writing or modifying database migrations.
allowedTools:
  - run_shell_command
  - read_file
paths:
  - "migrations/**/*.sql"
  - "src/db/**/*.sql"
---

# SQL Reviewer Workflow

Evaluate SQL queries and migration files against repository conventions:

## Steps

1. Run the migration validator:
   ```bash
   python3 "$QWEN_SKILL_ROOT/scripts/check-queries.py" "$TARGET_FILE"
   ```

2. Review table alteration statements for safety:
   - Ensure new columns on large tables are nullable or have constant defaults.
   - Verify index creation uses `CONCURRENTLY`.

3. Format output adhering strictly to the template below.

## Output Format

Output:
- Status: PASS | FAIL
- File Reviewed: <path>
- Violations:
  - Line <line>: <description of issue>
- Remediation: <exact SQL fix>
```

### Execution Example

**User Input:**
```
Check the migration in migrations/20261108_create_users.sql for indexing hazards.
```

**Agent Action:**
1. Matches request intent with `sql-reviewer` description and active path pattern `migrations/**/*.sql`.
2. Model issues tool call: `Skill { skill: "sql-reviewer" }`.
3. Reads `.qwen/skills/sql-reviewer/SKILL.md`.
4. Executes `python3 "$QWEN_SKILL_ROOT/scripts/check-queries.py" "migrations/20261108_create_users.sql"`.
5. Emits review report matching the Output Format template:

**Output:**
```
- Status: FAIL
- File Reviewed: migrations/20261108_create_users.sql
- Violations:
  - Line 14: CREATE INDEX idx_users_email lacks CONCURRENTLY keyword
- Remediation: CREATE INDEX CONCURRENTLY idx_users_email ON users(email);
```
