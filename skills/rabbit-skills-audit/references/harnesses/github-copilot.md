# GitHub Copilot Harness Reference

Reference guide for skill discovery, directory structure, configuration precedence, and feature support in GitHub Copilot, GitHub Copilot CLI, and Copilot Chat.

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
| CLI Identifier | `--agent github-copilot` |
| Supported Surfaces | GitHub Copilot CLI, GitHub Copilot App, Copilot in IDEs (VS Code, Visual Studio, JetBrains), GitHub.com (Cloud Agent, PR Review) |
| Specification URL | `https://docs.github.com/en/copilot/concepts/agents/about-agent-skills` |

---

## Compatibility Matrix

| Feature | Supported | Details |
|---|---|---|
| Basic Skills (`SKILL.md`) | Yes | Standard YAML frontmatter (`name`, `description`) and Markdown body instructions. |
| `allowed-tools` Frontmatter | Yes | Filters and declares tool access available to the skill during activation. |
| `context: fork` | No | Isolated context forking is unsupported in skill frontmatter. |
| Skill Frontmatter Hooks | No | Lifecycle event hooks are not supported in skill definitions. |
| Agent Mode Integration | Yes | Executes within agent mode across IDEs, CLI, and cloud environments. |
| Skill Management CLI | Yes | Discover and install skills from GitHub repositories using `gh skill`. |

---

## Skill Paths

GitHub Copilot searches defined project and personal paths for skill folders containing `SKILL.md`.

### Project Skills (Repository Scope)
Project skills live inside the repository root and apply to all contributors working within that codebase:
- **Primary Path**: `{repo-root}/.agents/skills/<skill-name>/SKILL.md`
- **Supported Alternates**:
  - `{repo-root}/.github/skills/<skill-name>/SKILL.md`
  - `{repo-root}/.claude/skills/<skill-name>/SKILL.md`

### User / Global Skills (Personal Scope)
Personal skills apply across local projects for a single developer:
- **Primary Path**: `~/.copilot/skills/<skill-name>/SKILL.md`
- **Supported Alternate**: `~/.agents/skills/<skill-name>/SKILL.md`

### Cloud Sessions (Dotfiles Scope)
To enable personal skills inside GitHub cloud sandbox sessions, store skill folders in `.copilot/skills/` within your personal dotfiles repository. Cloud environments sync dotfiles on launch. Note that dotfiles synchronization does not apply to GitHub Actions-based execution sessions.

---

## Settings & Configuration

GitHub Copilot centralizes custom instructions, tool enablement, and workspace behavior across repository and IDE configuration files:

| Location | Path | Scope | Purpose |
|---|---|---|---|
| Repository Instructions | `{repo-root}/.github/copilot-instructions.md` | Repository | Natural-language instructions loaded into prompt context for every Copilot interaction in the repo. |
| VS Code Settings | `{repo-root}/.vscode/settings.json` | Workspace | Workspace preferences such as `github.copilot.chat...` settings and custom instructions paths. |
| User Settings | `~/.config/github-copilot/` or IDE user settings | User | Machine-wide developer preferences and tool permissions. |
| Dotfiles Repository | `<dotfiles-repo>/.copilot/skills/` | Cloud Sessions | Personal skills synchronized to cloud environments and remote agent containers. |

---

## Discovery & Precedence

When multiple skills share identical `name` values, GitHub Copilot resolves collisions in priority order (highest to lowest):

1. **Repository / Project Skills**: `{repo-root}/.agents/skills/` (or `.github/skills/`, `.claude/skills/`). Project-level definitions override user-level definitions.
2. **User / Global Skills**: `~/.copilot/skills/` (or `~/.agents/skills/`). Loaded when no project skill overrides the name.
3. **Dotfiles Cloud Skills**: `.copilot/skills/` synced into remote cloud sandboxes.

---

## Feature Support

### `allowed-tools` Restriction
Skills can declare tool constraints in YAML frontmatter. This informs Copilot which tools are permitted during skill execution:

```yaml
---
name: release-notes
description: Generates formatted release notes from git commits and pull request metadata. Use when drafting release summaries.
allowed-tools:
  - git
  - read_file
---
```

### Context Isolation
GitHub Copilot does not support `context: fork`. Skills operate within the active conversation context or the running agent mode session.

### Agent Mode Integration
In IDEs (VS Code, Visual Studio, JetBrains) and GitHub Copilot CLI, agent mode plans and executes multi-step tasks. When a skill activates, its scripts (`scripts/*`) and references (`references/*`) are loaded progressively as needed by the agent loop.

---

## Directory Layout

Standard repository layout containing GitHub Copilot instructions, workspace configuration, and an agent skill:

```
my-project/
├── .github/
│   ├── copilot-instructions.md          # Global repository steering prompt
│   └── skills/                          # Alternative project skills directory
├── .agents/
│   └── skills/
│       └── release-notes/
│           ├── SKILL.md                 # Required skill entrypoint with frontmatter
│           ├── scripts/
│           │   └── gather_changes.py    # Script executed to extract git metadata
│           ├── references/
│           │   └── release_template.md  # Markdown template loaded on demand
│           └── resources/
│               └── categories.json      # Mapping of commit prefixes to categories
├── .vscode/
│   └── settings.json                    # Workspace settings for Copilot
├── package.json
└── src/
    └── index.ts
```

---

## Invocation

GitHub Copilot supports two primary invocation models:

1. **Automatic Prompt Matching**: Copilot evaluates available skills by indexing `name` and `description` frontmatter. When user prompts correspond to the skill description, the agent automatically activates the skill and reads `SKILL.md`.
2. **Copilot Chat `@agent` Direct Invocation**: Users explicitly direct prompts in Copilot Chat using `@agent` or designated participant handles. Specifying `@agent` activates agent mode, evaluating matching skills in the repository and global paths.

---

## Concrete Example

### Example Skill: `release-notes`

#### File: `.agents/skills/release-notes/SKILL.md`

````markdown
---
name: release-notes
description: Generates formatted release notes from git log commits and pull requests. Use when drafting release summaries or changelogs.
allowed-tools:
  - run_command
  - read_file
---

# Release Notes Generator

Generate structured release notes between git revisions.

## Workflow

1. **Extract Commits**:
   Execute the change gathering script:
   ```bash
   python3 scripts/gather_changes.py --since-tag $(git describe --tags --abbrev=0)
   ```

2. **Categorize Changes**:
   Group commits using `resources/categories.json`:
   - Features (`feat:`)
   - Fixes (`fix:`)
   - Documentation (`docs:`)

3. **Format Output**:
   Render the final markdown summary following the exact output format below.

## Output Format

Output:
```markdown
# Release Notes - [Version/Tag]

## Features
- <Description of feature> ([Commit/PR Hash])

## Bug Fixes
- <Description of fix> ([Commit/PR Hash])

## Documentation
- <Description of docs update> ([Commit/PR Hash])
```
````

### Execution Example

**Input:**
```
Generate release notes for the changes since the last tag.
```

**Agent Action:**
1. Evaluates available skills and matches request to `release-notes` description.
2. Loads `.agents/skills/release-notes/SKILL.md`.
3. Runs `python3 scripts/gather_changes.py --since-tag $(git describe --tags --abbrev=0)`.
4. Formats collected commits and emits the release notes conforming to the template:

**Output:**
```markdown
# Release Notes - v1.4.0

## Features
- Add streaming support to Copilot agent responses (a1b2c3d)

## Bug Fixes
- Resolve path resolution for global skill discovery (e4f5g6h)

## Documentation
- Update configuration guide with allowed-tools examples (i7j8k9l)
```
