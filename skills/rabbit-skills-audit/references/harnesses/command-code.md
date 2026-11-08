# Command Code Harness Reference

Reference for skill discovery, compatibility, configuration, directory layout, and invocation in Command Code.

- **Harness Identifier:** `--agent command-code`
- **Official Documentation:** https://commandcode.ai/docs/skills

## Contents

- [Compatibility Matrix](#compatibility-matrix)
- [Skill Paths](#skill-paths)
- [Settings & Configuration](#settings--configuration)
- [Discovery & Precedence](#discovery--precedence)
- [Feature Support](#feature-support)
- [Directory Layout](#directory-layout)
- [Invocation](#invocation)
- [Concrete Example](#concrete-example)

---

## Compatibility Matrix

| Feature | Supported | Notes |
|---|---|---|
| **Basic Skills (`SKILL.md`)** | **Yes** | Standard YAML frontmatter (`name`, `description`) and Markdown body. |
| **Tool Restriction (`allowed-tools`)** | **Yes** | Space-delimited string or YAML list of permitted tools. `disallowed-tools` is also supported. |
| **Forked Context (`context: fork`)** | **No** | Executes within active conversation context; forked execution sub-sessions are not supported. |
| **Skill Frontmatter Hooks** | **No** | Skill frontmatter does not define hooks. Lifecycle hooks are configured separately. |
| **Dynamic Context Injection** | **Yes** | Shell injection via inline `` !`command` `` and fenced ````! ... ```` blocks (disable with `disableSkillShellExecution`). |
| **Argument Substitution** | **Yes** | Supports `$ARGUMENTS`, `$ARGUMENTS[N]`, `${N}`, and named variables declared via `arguments`. |

---

## Skill Paths

Command Code resolves skills across project-level, global user-level, and cross-compatibility locations.

| Scope | Canonical Path | Compatibility / Fallback Paths |
|---|---|---|
| **Project (Local)** | `.commandcode/skills/<skill-name>/` | `.agents/skills/<skill-name>/` |
| **User (Global)** | `~/.commandcode/skills/<skill-name>/` | `~/.agents/skills/<skill-name>/` |
| **Extra Locations** | Pinned in `settings.json` under `skills: [...]` | CLI runtime flag `--skill <path>` (repeatable) |

### Path Behavior
- **Project skills:** Stored in `.commandcode/skills/` at the repository root and committed to version control for team workflows.
- **User skills:** Stored in `~/.commandcode/skills/` for personal workflows shared across all repositories on the local system.
- **Cross-tool compatibility:** Discovers skills in `.agents/skills/` (project) and `~/.agents/skills/` (user) automatically, displaying a `[.agents]` badge in the `/skills` menu.
- **Nested directories:** Intermediate grouping directories are traversed recursively (e.g. `.commandcode/skills/review/security/SKILL.md`). The skill name must match its immediate containing directory (`security`).

---

## Settings & Configuration

Command Code manages settings, tool policies, and skill toggles using JSON configuration files:

| Scope | Path | Purpose |
|---|---|---|
| **Workspace Settings** | `.commandcode/settings.json` | Project-wide settings, team tool authorizations, and external skills folders. |
| **Local Workspace Settings** | `.commandcode/settings.local.json` | Local developer workspace overrides; excluded from version control. |
| **Workspace Legacy / Config** | `.commandcode/config.json` | Project-level configuration and agent settings. |
| **Global User Settings** | `~/.commandcode/settings.json` | Machine-wide preferences, global disabled skills, and global telemetry options. |
| **Global Config Directory** | `~/.commandcode/` | Global config state, credentials, auth tokens, and session history. |
| **Custom Commands** | `.commandcode/commands/` | Project-specific slash command scripts taking precedence over skills. |

### Disabling Skills
Skills can be temporarily toggled off without deleting files by adding their names to `disabledSkills` in `settings.json`:

```json
{
  "disabledSkills": [
    "pdf-processing",
    "legacy-deploy"
  ]
}
```

---

## Discovery & Precedence

Command Code checks skill sources at startup and context initialization using strict precedence order:

1. **Project Canonical:** `.commandcode/skills/` (ascends up to 10 parent levels to repository root).
2. **Project Compatibility:** `.agents/skills/` (ascends to repository root, stops before home directory).
3. **User Canonical:** `~/.commandcode/skills/`.
4. **User Compatibility:** `~/.agents/skills/`.
5. **Configured Locations:** Paths supplied via `--skill <path>` flags, followed by entries in `settings.json` (`skills: [...]`).
6. **Bundled Skills:** Built-in skills packaged with Command Code (e.g., `/skill-builder`, `/design`, `/loop`).

### Collision Resolution
- **Project overrides Global:** When a skill in `.commandcode/skills/` shares a name with a skill in `~/.commandcode/skills/`, the project version executes.
- **Canonical overrides Compatibility:** `.commandcode/skills/` takes precedence over `.agents/skills/` at the same scope level.
- **Command collisions:** Built-in commands (`/help`, `/clear`) and custom commands in `.commandcode/commands/` override identical skill names when invoked with `/<name>`. To bypass command collision and force skill execution, invoke using the namespaced form: `/skill:<name>`.

---

## Feature Support

### Frontmatter Validation
Every skill requires a valid `SKILL.md` file with YAML frontmatter:

- `name`: Required. Maximum 64 characters. Lowercase letters, numbers, and hyphens (`-`). Must match the skill's containing folder name.
- `description`: Required. Maximum 1024 characters. Clear task description and trigger context.
- `allowed-tools`: Optional. Space-delimited string or YAML sequence of permitted tools (e.g. `Read Bash(git:*)`).
- `disallowed-tools`: Optional. Space-delimited string or YAML sequence of forbidden tools.
- `argument-hint`: Optional. Argument syntax displayed in the `/` interactive menu.
- `disable-model-invocation`: Optional boolean. When `true`, hides the skill from model semantic matching; invocation requires an explicit slash command.

### Dynamic Context Injection
Command Code can evaluate shell commands before feeding the skill body to the model:
- Inline: `` !`git status --short` ``
- Fenced block:
  ````markdown
  ```!
  git branch --show-current
  git status -s
  ```
  ````
Dynamic shell execution can be disabled globally or per project by setting `"disableSkillShellExecution": true` in `settings.json`.

### Terminal Agent Execution
Command Code runs as an interactive terminal coding agent (`cmd`). Skills integrate with terminal workflows through:
- **Interactive TUI:** Launching `/skills` opens an interactive list to browse, filter, toggle, or edit installed skills.
- **CLI Skill Management:**
  ```bash
  cmd skills list                # List all installed skills and locations
  cmd skills list --debug        # Inspect load errors or skipped skills
  cmd skills add owner/repo      # Install skill from GitHub repository
  cmd skills remove <skill-name> # Remove skill from current project
  ```
- **Session Flags:**
  ```bash
  cmd --skill ./custom-skill     # Load specific skill for current session
  cmd --no-skills                # Disable all skill discovery for current session
  ```

---

## Directory Layout

Recommended project directory layout for Command Code skills:

```
my-project/
├── .commandcode/
│   ├── config.json                      # Workspace configuration
│   ├── settings.json                    # Workspace settings (disabledSkills, etc.)
│   └── skills/
│       └── release-helper/
│           ├── SKILL.md                 # Required skill entrypoint
│           ├── scripts/
│           │   └── generate-notes.sh    # Executable automation script
│           ├── references/
│           │   └── guidelines.md        # Reference documentation loaded on demand
│           └── assets/
│               └── template.md          # Static release note template
├── src/
│   └── index.ts
└── package.json
```

---

## Invocation

Command Code provides four invocation mechanisms:

1. **Direct Slash Command:** Prefixing the skill name at prompt start:
   ```text
   /release-helper prepare v1.4.0 notes
   ```
2. **Guaranteed Namespaced Slash:** Using the `/skill:` namespace to bypass command name collisions:
   ```text
   /skill:release-helper prepare v1.4.0 notes
   ```
3. **Inline Prompt Mention:** Embedding `/release-helper` within natural language prose:
   ```text
   Review git history and follow /release-helper to create the changelog draft.
   ```
4. **Semantic Model Inference:** When a user request matches the skill `description`, Command Code automatically loads `SKILL.md` using progressive disclosure.

---

## Concrete Example

### Skill Definition: `.commandcode/skills/release-helper/SKILL.md`

````markdown
---
name: release-helper
description: Drafts release notes and verifies Git tag status. Use when preparing a new version release or tagging commits.
argument-hint: "<version>"
allowed-tools:
  - Read
  - Bash(git:*)
---

# Release Helper

Generate release notes and confirm tag readiness.

## Context

Current repository status:
!`git status --short`

## Release Steps

1. Verify working directory is clean:
   ```bash
   git diff --quiet || exit 1
   ```

2. Run note generation script for version `$ARGUMENTS`:
   ```bash
   scripts/generate-notes.sh "$ARGUMENTS"
   ```

3. Compare output with release criteria.

## Output Format

ALWAYS format the response with:
- **Target Version**: `<version>`
- **Validation**: CLEAN | DIRTY
- **Changelog Entries**: Bulleted list grouped by `Features`, `Fixes`, `Breaking Changes`
- **Recommended Tag Command**: `git tag -a v<version> -m "Release v<version>"`
````

### Execution Example

**Input:**
```text
/release-helper 1.4.0
```

**Agent Output:**
```markdown
- **Target Version**: 1.4.0
- **Validation**: CLEAN
- **Changelog Entries**:
  - Features: Added terminal command-code harness support
  - Fixes: Resolved path resolution edge case on recursive skill folders
- **Recommended Tag Command**: git tag -a v1.4.0 -m "Release v1.4.0"
```
