# Crush Harness Reference

Reference guide for skill discovery, directory structure, configuration precedence, and feature support in Charmbracelet Crush.

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
| CLI Identifier | `--agent crush` |
| Supported Surfaces | Terminal UI (macOS, Linux, Windows WSL/PowerShell, BSDs) |
| Repository URL | `https://github.com/charmbracelet/crush` |
| Specification | Agent Skills open standard (`https://agentskills.io`) |

---

## Compatibility Matrix

| Feature | Supported | Details |
|---|---|---|
| Basic Skills (`SKILL.md`) | Yes | Standard YAML frontmatter (`name`, `description`) and Markdown body. |
| `user-invocable` Frontmatter | Yes | Exposes skill in the TUI command palette (`ctrl+p`) under `project:` or `user:` prefix. |
| `disable-model-invocation` Frontmatter | Yes | Hides skill from autonomous model selection while preserving manual user invocation. |
| Terminal UI Tools | Yes | Interactive TUI built on the Charm ecosystem (Bubble Tea, Lip Gloss, Bubbles). |
| MCP Integration | Yes | Supports `stdio`, `http`, and `sse` transports configured in `crushrc` or `crush.json`. |
| LSP Integration | Yes | Built-in language server protocol context via `lsp add`. |
| Subagents | No | Operates within interactive multi-session contexts; no background subagent fork primitive. |

---

## Skill Paths

Crush discovers skills across project-level directories, global user paths, and application defaults.

### Project Skills (Repository Scope)

- **Primary Path**: `{project-root}/.crush/skills/<skill-name>/SKILL.md`
- **Compatibility Paths**:
  - `{project-root}/.agents/skills/<skill-name>/SKILL.md`
  - `{project-root}/.claude/skills/<skill-name>/SKILL.md`
  - `{project-root}/.cursor/skills/<skill-name>/SKILL.md`
- **Configured Paths**: Custom project-relative paths added via `option skill-path` in `crushrc`.

### Global Skills (User Scope)

- **Primary Path**: `~/.config/crush/skills/<skill-name>/SKILL.md` (respects `$XDG_CONFIG_HOME/crush/skills/`)
- **Environment Variable**: `$CRUSH_SKILLS_DIR` (takes precedence when set)
- **Shared Harness Paths**:
  - `~/.config/agents/skills/` (or `$XDG_CONFIG_HOME/agents/skills/`)
  - `~/.agents/skills/`
  - `~/.claude/skills/`
- **Windows Paths**:
  - `%LOCALAPPDATA%\crush\skills\`
  - `%LOCALAPPDATA%\agents\skills\`
- **Configured Paths**: Additional directories declared in `options.skills_paths` within `crush.json`.

### Built-in Skills (Application Scope)

Crush bundles built-in runtime skills (such as `crush-config` for interactive configuration).

---

## Settings & Configuration

Crush supports configuration through Bash-based script files (`crushrc`) and declarative JSON files (`crush.json`):

| Configuration File | Path | Scope | Purpose |
|---|---|---|---|
| Project Config (`crushrc`) | `./.crushrc`, `./crushrc` | Project | Project-specific commands, permissions, LSPs, and MCP servers (Priority 1 and 2). |
| Global Config (`crushrc`) | `~/.config/crush/crushrc` | User / Global | User-wide providers, models, and tools (Priority 3). |
| Global Config (`crush.json`) | `~/.config/crush/crush.json` | User / Global | Primary terminal agent JSON configuration file. |
| Global Rules | `~/.config/crush/CRUSH.md`, `~/.config/AGENTS.md` | User / Global | Cross-project user instructions injected into prompt context. |
| Project Rules & Ignore | `AGENTS.md`, `.crushignore` | Project | Project instructions and file exclusion patterns. |
| Ephemeral State | `~/.local/share/crush/crush.json` | Internal State | Runtime session state and cache (not manual configuration). |

### Environment Variable Overrides

- `CRUSH_GLOBAL_CONFIG`: Overrides the global configuration directory path.
- `CRUSH_GLOBAL_DATA`: Overrides the global data directory path.
- `CRUSH_DATA_DIR`: Overrides the per-project `.crush/` directory path.
- `CRUSH_SKILLS_DIR`: Overrides the global skills discovery directory path.

---

## Discovery & Precedence

When skills share identical `name` values across multiple locations, Crush resolves collisions with strict precedence:

1. **Project Directory**: Local skills in `{project-root}/.crush/skills/` (and compatibility paths) take precedence over all global locations.
2. **Explicit Custom Paths**: Directories configured via `option skill-path` in `crushrc` or `options.skills_paths` in `crush.json`.
3. **Environment Override**: Directory path set in `$CRUSH_SKILLS_DIR`.
4. **Global User Directory**: `~/.config/crush/skills/` (or `$XDG_CONFIG_HOME/crush/skills/`).
5. **Shared Global Paths**: `~/.config/agents/skills/`, `~/.agents/skills/`, and `~/.claude/skills/`.
6. **Built-in Skills**: Bundled application defaults (e.g., `crush-config`).

### Disabling Skills

Skills can be disabled globally or per project in `crushrc`:

```bash
option disable-skill crush-config
```

Disabled skills are hidden from the agent and excluded from discovery.

---

## Feature Support

### Frontmatter Controls

- **`user-invocable: true`**: Exposes the skill in the interactive command palette (<kbd>ctrl+p</kbd>).
  - Global skills display with prefix `user:<skill-name>`.
  - Project skills display with prefix `project:<skill-name>`.
- **`disable-model-invocation: true`**: Prevents the model from autonomously auto-triggering the skill, restricting execution to explicit user command palette selection.

```yaml
---
name: deploy-preview
description: Deploys current branch to staging preview environment.
user-invocable: true
disable-model-invocation: true
---
```

### Terminal UI & Charm Integration

Crush is built upon the Charm ecosystem:
- **Bubble Tea**: Event-driven terminal UI handling interactive prompts, spinner animations, and keybindings.
- **Lip Gloss**: Formatted terminal output styling and custom color themes (configured via `ctrl+p` -> Themes or `options.tui.active_theme`).
- **Permissions Management**: Fine-grained tool permission prompts with allowlist configuration (`permissions allow view edit`).
- **Native Bash Interpreter**: Built-in interpreter ensuring cross-platform execution of `crushrc` commands without external shell dependencies.

---

## Directory Layout

Standard Crush project repository layout incorporating local skills and configuration:

```
my-project/
├── .crush/
│   ├── logs/
│   │   └── crush.log                    # Crush execution logs
│   └── skills/
│       └── git-hygiene/
│           ├── SKILL.md                 # Entrypoint with YAML frontmatter
│           ├── scripts/
│           │   └── check_branches.sh    # Executable verification script
│           └── references/
│               └── commit-rules.md      # Supporting reference document
├── .crushrc                             # Project-specific Bash configuration
├── .crushignore                         # Context file exclusion patterns
├── AGENTS.md                            # High-priority project instructions
└── src/
    └── main.go
```

---

## Invocation

Crush provides two invocation models:

1. **Autonomous Progressive Disclosure**: The agent loads `name` and `description` from all discovered skills into the system prompt context (~100 tokens each). When a user query matches the skill description, Crush autonomously reads the full `SKILL.md` body and executes the instructions.
2. **Command Palette Selection**: Users press <kbd>ctrl+p</kbd> to open the command palette. Skills marked with `user-invocable: true` appear with `project:` or `user:` prefix. Selecting a skill immediately injects its instructions into the conversation context.

---

## Concrete Example

### Example Skill: `git-hygiene`

#### File: `.crush/skills/git-hygiene/SKILL.md`

```markdown
---
name: git-hygiene
description: Audits git branches, uncommitted changes, and commit conventions before pushing. Use when preparing commits or cleaning stale branches.
user-invocable: true
---

# Git Hygiene Workflow

Inspect repository state, verify commit message conventions, and identify stale merged branches.

## Instructions

1. **Inspect Branch State**:
   Execute the branch inspection script:
   ```bash
   bash scripts/check_branches.sh
   ```

2. **Verify Commit Style**:
   Confirm that recent commits follow conventional commit prefixes (`feat:`, `fix:`, `refactor:`, `chore:`).

3. **Format Output**:
   Present audit findings matching the Output Format template below.

## Output Format

Output:
- **Cleanliness Status**: PASS | FAIL
- **Active Branch**: `<branch-name>`
- **Uncommitted Files**: `<count-of-staged-and-unstaged-files>`
- **Merged Stale Branches**: `<list-of-branches-merged-into-main>`
- **Recommended Action**: `<concrete-git-command-or-next-step>`
```

### Execution Example

**User Input:**
```
Check my git branches and uncommitted changes before I push.
```

**Agent Action:**
1. Matches user request against `git-hygiene` description.
2. Reads `.crush/skills/git-hygiene/SKILL.md`.
3. Runs `bash scripts/check_branches.sh`.
4. Returns formatted audit findings matching the Output Format template:

```markdown
- **Cleanliness Status**: PASS
- **Active Branch**: feature/login-flow
- **Uncommitted Files**: 0
- **Merged Stale Branches**: feature/user-profile, bugfix/typo
- **Recommended Action**: git branch -d feature/user-profile bugfix/typo
```
