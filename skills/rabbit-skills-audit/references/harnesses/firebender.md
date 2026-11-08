# Firebender Harness Reference

Reference guide for skill discovery, directory structure, multi-agent dispatch, configuration precedence, and feature support in Firebender.

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
| CLI Identifier | `--agent firebender` |
| Supported Surfaces | Firebender IDE, Firebender Multi-Agent Core |
| Specification URL | `https://docs.firebender.com/multi-agent/skills` |

---

## Compatibility Matrix

| Feature | Supported | Details |
|---|---|---|
| Basic Skills (`SKILL.md`) | Yes | Standard YAML frontmatter (`name`, `description`) with Markdown instructions. |
| Extended Metadata | Yes | Supports `version`, `autoTrigger`, `projectTypes`, and `icon` in frontmatter. |
| `autoTrigger` Control | Yes | Defaults to `true`. Setting to `false` requires explicit slash command invocation. |
| `projectTypes` Filtering | Yes | Restricts skill activation to designated project domains (e.g., `[android, kotlin]`). |
| Context Forking (`context: fork`) | No | Context isolation relies on multi-agent subagent delegation. |
| Executable Scripts | Yes | Recommended over embedded code blocks; executed directly via the terminal tool. |
| Cross-Tool Compatibility | Yes | Discovers skills from standard shared paths (`.agents/skills/`, `~/.agents/skills/`, `~/.claude/skills/`). |

---

## Skill Paths

Firebender searches both workspace and global user scopes, with support for cross-agent compatibility directories.

### Workspace Skills (Team & Project-Specific)
- **Standard Shared Path**: `<workspace-root>/.agents/skills/<skill-name>/SKILL.md`
- **Native Team Path**: `<workspace-root>/.firebender/skills/<skill-name>/SKILL.md`
- **Scope**: Committed to version control; automatically available to all team members collaborating in the repository.

### Global Skills (User-Wide)
- **Primary User Path**: `~/.firebender/skills/<skill-name>/SKILL.md`
- **Generic Fallback**: `~/.agents/skills/<skill-name>/SKILL.md`
- **Cross-Agent Compatibility Fallbacks**:
  - `~/.claude/skills/<skill-name>/SKILL.md`
  - `~/.cursor/skills/<skill-name>/SKILL.md`
  - `~/.codex/skills/<skill-name>/SKILL.md`
  - `~/.goose/skills/<skill-name>/SKILL.md`
- **Scope**: Available across all projects for the local user.

---

## Settings & Configuration

Firebender maintains distinct scopes for workspace rules, multi-agent orchestration, and user configuration:

| Location | Path | Scope | Purpose |
|---|---|---|---|
| Workspace Rules | `<workspace-root>/.firebender/rules/`, `AGENTS.md` | Workspace | Coding standards, architecture guidelines, and system instructions. |
| Team Skills | `<workspace-root>/.agents/skills/`, `.firebender/skills/` | Workspace | Team-shared executable workflows committed to version control. |
| Workspace Settings | `<workspace-root>/.firebender/settings.json` | Workspace | Project-level subagent permissions and environment settings. |
| User Configuration | `~/.firebender/` | Machine / User | User-wide configuration, model preferences, and API credentials. |
| User Skills | `~/.firebender/skills/` | Machine / User | Personal workflows accessible across all workspaces. |

---

## Discovery & Precedence

When skills share the same `name` attribute across multiple search paths, Firebender resolves collisions in strict hierarchical order:

1. **Workspace Team Skills**: `<workspace-root>/.agents/skills/` and `<workspace-root>/.firebender/skills/` (highest priority).
2. **Primary User Skills**: `~/.firebender/skills/`.
3. **Generic User Skills**: `~/.agents/skills/`.
4. **Third-Party Compatibility Directories**: `~/.claude/skills/`, `~/.cursor/skills/`, `~/.codex/skills/`, `~/.goose/skills/` (lowest priority).

Workspace skills always override global skills of the same name, allowing project-specific configurations to adapt shared standards without modifying global files.

---

## Feature Support

### Frontmatter Metadata Specification

Firebender parses the following frontmatter fields in `SKILL.md`:

| Field | Required | Type | Description |
|---|---|---|---|
| `name` | Yes | string | Skill identifier (lowercase alphanumeric with hyphens, max 64 chars). |
| `description` | Yes | string | Description of capability and trigger conditions (max 1024 chars). |
| `version` | No | string | Semantic version string for reference. |
| `autoTrigger` | No | boolean | Enables autonomous activation (`true` by default). Set to `false` for manual-only invocation. |
| `projectTypes` | No | array | List of project tags matching the active workspace (e.g., `[android, kotlin]`). |
| `icon` | No | string | Relative path to SVG, PNG, or JPG icon asset within the skill directory. |

### Multi-Agent Dispatch
Firebender's core orchestrator delegates tasks across specialized subagents. When a subtask matches an active skill's trigger conditions:
- The orchestrator dispatches the skill directly to the relevant subagent.
- Subagents execute scripts declared within the skill directory via terminal tools rather than generating shell commands on the fly.
- Subagents return structured outputs back to the main coordination loop.

### Progressive Disclosure
- Keep `SKILL.md` under 500 lines to preserve context capacity.
- Place extended reference docs (e.g., `reference.md`, `FORMS.md`) in auxiliary files within the skill directory.
- Reference auxiliary files with relative markdown links; Firebender reads them only when required by the task.

### Executable Scripts Over Code Blocks
Rather than placing multi-line bash or python snippets into markdown code blocks for the model to copy and rewrite, bundle executable scripts inside the skill directory (e.g., `scripts/` or root executables) and reference their relative execution path.

---

## Directory Layout

A standard Firebender project repository with team skills and multi-agent configuration adheres to the following tree structure:

```
my-project/
├── .agents/
│   └── skills/
│       └── pr-review/
│           ├── SKILL.md                 # Required entrypoint with frontmatter
│           ├── icon.svg                 # Skill icon (optional)
│           ├── scripts/
│           │   └── check_pr.py          # Executable validation script
│           └── references/
│               └── review_rubric.md     # Secondary documentation loaded on demand
├── .firebender/
│   ├── rules/
│   │   └── style-guide.md               # Context rules for multi-agent core
│   └── settings.json                    # Workspace multi-agent settings
├── AGENTS.md                            # High-level repo instructions
├── package.json
└── src/
    └── index.ts
```

---

## Invocation

Firebender provides three invocation paths:

1. **Autonomous Multi-Agent Routing**: When user prompts match the `description` and `autoTrigger: true` is set, Firebender automatically activates the skill and injects instructions into context.
2. **Explicit Slash Command**: Typing `/skill:<skill-name>` (e.g., `/skill:pr-review`) forces direct activation regardless of the prompt context.
3. **Capability Querying**: Asking `"What skills can you use?"` lists all discovered workspace and user skills available for invocation.

---

## Concrete Example

### Example Skill: `git-release`

#### File: `.agents/skills/git-release/SKILL.md`

```markdown
---
name: git-release
description: Validates changelogs, bumps version tags, and creates GitHub releases. Use when preparing a release, tagging versions, or publishing release notes.
version: 1.0.0
autoTrigger: true
projectTypes:
  - node
  - python
---

# Git Release Workflow

Execute release preparation and validation steps in order.

## Prerequisites

Ensure working directory is clean before running the release helper:
```bash
git status --porcelain
```

## Release Steps

1. Run the release validation script:
   ```bash
   ./scripts/validate_release.sh
   ```

2. Generate the changelog summary:
   - Extract commit subjects since the last tag.
   - Categorize entries into `Features`, `Fixes`, and `Maintenance`.

3. Prompt the user for final tag confirmation before publishing.

## Output Format

ALWAYS use this exact template for release summaries:

```markdown
### Release <version> Summary
- **Tag**: <vX.Y.Z>
- **Commit**: <hash>
- **Changelog**:
  - Features: <count>
  - Bug Fixes: <count>
- **Validation**: PASS | FAIL
```
```

### Execution Example

**User Input:**
```
Prepare the v1.4.0 release and check the changelog.
```

**Agent Action:**
1. Evaluates prompt and matches `git-release` description (`"preparing a release, tagging versions"`).
2. Reads `.agents/skills/git-release/SKILL.md`.
3. Dispatches task to subagent with terminal execution permission.
4. Executes `./scripts/validate_release.sh`.
5. Returns output formatted according to the Release Summary template:

```markdown
### Release v1.4.0 Summary
- **Tag**: v1.4.0
- **Commit**: 8f3a1c2
- **Changelog**:
  - Features: 3
  - Bug Fixes: 2
- **Validation**: PASS
```
