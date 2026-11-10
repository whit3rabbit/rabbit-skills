# Gemini CLI Harness Reference

Reference guide for skill discovery, directory conventions, configuration, precedence, and feature support in Gemini CLI.

- **Harness Identifier:** `--agent gemini-cli`
- **Documentation:** https://geminicli.com/docs/cli/skills/

## Contents

- [Skill Paths](#skill-paths)
- [Settings & Configuration](#settings--configuration)
- [Discovery & Precedence](#discovery--precedence)
- [Feature Support](#feature-support)
- [Directory Layout](#directory-layout)
- [Invocation](#invocation)
- [Concrete Example](#concrete-example)

---

## Skill Paths

Gemini CLI discovers skills across workspace, global, extension, and built-in tiers.

| Scope | Path | Alias / Precedence Note |
|---|---|---|
| **Workspace (Project)** | `.agents/skills/<skill-name>/` | Takes precedence over `.gemini/skills/<skill-name>/` |
| **Workspace (Fallback)** | `.gemini/skills/<skill-name>/` | Secondary workspace location |
| **User (Global)** | `~/.gemini/skills/<skill-name>/` | Primary global directory |
| **User (Global Alias)** | `~/.agents/skills/<skill-name>/` | Cross-tool interoperable alias |
| **Extensions** | `{extension-root}/skills/<skill-name>/` | Packaged within installed Gemini CLI extensions |
| **Built-in** | Bundled internal skills | Shipped directly with the CLI runtime |

### Path Resolution
- **Project skills:** Version-controlled with the codebase. Shared across team members and take precedence over global definitions.
- **Global skills:** Reside in the user home directory for personal workflows available across all projects.
- **Interoperability:** The `.agents/skills/` path provides compatibility across different agent tools.

---

## Settings & Configuration

Gemini CLI stores configuration, authentication tokens, and environment parameters across standardized locations:

| Configuration Item | Path / Key | Scope | Purpose |
|---|---|---|---|
| **Global Configuration** | `~/.gemini/config.json` | Global (User) | CLI preferences, default model, theme, tool approvals. |
| **Project Context** | `GEMINI.md` | Workspace | Persistent workspace background loaded into agent context. |
| **Ignore Rules** | `.geminiignore` | Workspace | Patterns excluding files from context scanning and tools. |
| **API Credentials** | `GEMINI_API_KEY` | Environment | API authentication token. |
| **Model Selection** | `GEMINI_MODEL` | Environment / Config | Specifies default generative model. |
| **Config Directory Override** | `GEMINI_CLI_CONFIG_PATH` | Environment | Overrides default `~/.gemini/` configuration path. |

### Skill State Controls
Skill enablement states are managed per-scope:
- User-scope disabled skills are tracked in `~/.gemini/config.json`.
- Workspace-scope disabled skills are stored in project configuration when specifying `--scope workspace`.

---

## Discovery & Precedence

Gemini CLI evaluates skills hierarchically across four discovery tiers:

```text
[Highest] 1. Workspace Skills (.agents/skills/ > .gemini/skills/)
          2. User Skills      (~/.agents/skills/ > ~/.gemini/skills/)
          3. Extension Skills (<extension>/skills/)
[Lowest]  4. Built-in Skills  (bundled standard skills)
```

### Precedence Rules
1. **Workspace overrides Global:** A skill defined in `.agents/skills/<name>` or `.gemini/skills/<name>` overrides any identically named skill in user, extension, or built-in tiers.
2. **Alias Precedence:** Within both workspace and user tiers, `.agents/skills/` takes precedence over `.gemini/skills/`.
3. **Collision Handling:** If identical skill names exist in multiple tiers, only the highest-precedence instance is loaded.

### Discovery and Activation Lifecycle
1. **Discovery**: At session start, Gemini CLI scans enabled skills and injects only metadata (`name` and `description`) into the system prompt.
2. **Activation**: When a user prompt matches a skill description, Gemini invokes the `activate_skill` tool.
3. **Consent**: An interactive prompt requests user approval detailing the skill name, purpose, and directory path.
4. **Injection**: Upon confirmation, `SKILL.md` content and directory structure enter the context window, and the directory is added to allowed filesystem paths.
5. **Execution**: The model follows procedural guidelines provided by the activated skill.

---

## Feature Support

| Feature | Supported | Details |
|---|---|---|
| **Basic Skills (`SKILL.md`)** | Yes | Supports standard YAML frontmatter (`name`, `description`) and Markdown body. |
| **Tool Restriction** | Yes | Optional `allowed-tools` list masks unapproved tools during execution. |
| **Scripts & Assets** | Yes | Bundled executables in `scripts/`, references in `references/`, assets in `resources/`. |
| **Subagents** | Yes | Supports subagent delegation and task isolation. |
| **Model Steering & Config** | Yes | Controlled via `config.json`, CLI flags, or `GEMINI_MODEL`. |
| **MCP Integration** | Yes | Exposes tools configured in MCP server definitions. |

---

## Directory Layout

Standard project repository layout using the preferred `.agents/skills/` directory:

```text
my-repo/
├── .agents/
│   └── skills/
│       └── pr-review/
│           ├── SKILL.md                 # Entrypoint: frontmatter + workflow
│           ├── scripts/
│           │   └── analyze_diff.py      # Task automation script
│           ├── references/
│           │   └── guidelines.md        # Detailed criteria loaded on demand
│           └── resources/
│               └── review-template.md   # Markdown review template
├── GEMINI.md                            # Project-wide persistent context
├── .geminiignore                        # Context exclusion rules
└── src/
    └── index.ts
```

---

## Invocation

Gemini CLI supports both autonomous model invocation and manual command execution.

### 1. Autonomous Natural Language Trigger
The model identifies matching tasks from user input and calls `activate_skill`.

- **User Prompt:** `"Review this pull request for breaking changes and adherence to code standards"`
- **Harness Action:** Model identifies `pr-review`, calls `activate_skill`, requests consent, and executes the procedure.

### 2. Interactive Session Commands (`/skills`)
During an interactive CLI session, use `/skills` slash commands:

```bash
# List discovered skills (use "all" to include built-in, "nodesc" to hide descriptions)
/skills list [all] [nodesc]

# Link skills from a local directory into current scope
/skills link /path/to/custom-skills [--scope workspace|user]

# Disable or enable a skill (defaults to user scope; add --scope workspace for local)
/skills disable pr-review
/skills enable pr-review --scope workspace

# Reload discovered skills from disk
/skills reload
```

### 3. Terminal CLI Commands (`gemini skills`)
Manage skills directly from the command line outside an interactive session:

```bash
# List all discovered skills including built-ins
gemini skills list --all

# Install a skill from a repository or directory
gemini skills install https://github.com/org/review-skill.git --consent

# Uninstall a skill from workspace scope
gemini skills uninstall pr-review --scope workspace
```

---

## Concrete Example

### Example Skill: `pr-review`

#### File: `.agents/skills/pr-review/SKILL.md`

```markdown
---
name: pr-review
description: Evaluates pull request diffs for breaking changes, style conformance, and test coverage. Use when reviewing pull requests or reviewing code diffs.
allowed-tools:
  - run_command
  - read_file
---

# Pull Request Review Workflow

Follow this procedure to conduct a code review:

## 1. Extract and Inspect Changes
Run the diff extraction script:
```bash
python3 scripts/analyze_diff.py --branch main
```

## 2. Evaluate Findings
Review diff output against standards defined in the bundled review reference document.

## 3. Format Output
Output the review using the exact template below.

### Output Template:
Output:
- **Verdict**: APPROVE | REQUEST_CHANGES | COMMENT
- **Summary**: High-level overview of changes
- **Critical Issues**: List breaking changes or security risks (or "None")
- **Suggestions**: Recommended improvements with line references
```

### Execution Walkthrough

**Input:**
```
Review the changes on the current branch against main before I open a PR.
```

**Output:**
```markdown
- **Verdict**: APPROVE
- **Summary**: Added user authentication middleware and unit test fixtures.
- **Critical Issues**: None
- **Suggestions**: Consider memoizing token verification in src/auth.ts to avoid duplicate validation calls.
```
