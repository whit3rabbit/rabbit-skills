# Claude Code Harness Reference

Reference guide for skill discovery, directory structure, configuration precedence, and feature support in Claude Code.

## Contents

- [Harness Identifiers](#harness-identifiers)
- [Compatibility Matrix](#compatibility-matrix)
- [Skill Paths](#skill-paths)
- [Settings & Configuration](#settings--configuration)
- [Discovery & Precedence](#discovery--precedence)
- [Feature Support](#feature-support)
  - [Tool Pre-Approval and Restriction](#tool-pre-approval-and-restriction)
  - [Subagent Execution via context: fork](#subagent-execution-via-context-fork)
  - [Lifecycle Hooks](#lifecycle-hooks)
  - [Dynamic Context Injection & Variable Substitution](#dynamic-context-injection--variable-substitution)
- [Directory Layout](#directory-layout)
- [Invocation](#invocation)
- [Concrete Example](#concrete-example)

---

## Harness Identifiers

| Field | Value |
|---|---|
| CLI Identifiers | `--agent claude-code` |
| Supported Surfaces | Claude Code CLI (terminal, IDE extension, desktop app) |
| Specification URL | `https://code.claude.com/docs/en/skills` |

---

## Compatibility Matrix

| Feature | Supported | Details |
|---|---|---|
| Basic Skills (`SKILL.md`) | Yes | Standard YAML frontmatter (`name`, `description`) and Markdown body. |
| `allowed-tools` Frontmatter | Yes | Pre-approves tools without confirmation prompts for the active invocation turn. |
| `context: fork` | Yes | Runs skill instructions within an isolated subagent context (`agent: Explore`, etc.). |
| Skill Frontmatter Hooks | Yes | Declares event hooks (`PreToolUse`, `PostToolUse`, etc.) active for the session. |
| Dynamic Context Injection | Yes | Prefix shell commands with `!` to inline live command output before prompt delivery. |
| Subagents | Yes | Autonomous subagent execution via `context: fork` or `.claude/agents/`. |

---

## Skill Paths

Claude Code searches multiple directory scopes to discover skills.

### Project Skills (Repository Scope)
- **Primary Path**: `<workspace-root>/.claude/skills/<skill-name>/SKILL.md`
- **Subdirectory / Monorepo Path**: `<workspace-root>/<subdir>/.claude/skills/<skill-name>/SKILL.md`
- **Behavior**: Scanned from the current working directory upward to the repository root. Subdirectory skills load lazily when Claude touches files within `<subdir>`. Intended for version-controlled, team-shared skills.

### Personal Skills (User Scope)
- **Primary Path**: `~/.claude/skills/<skill-name>/SKILL.md`
- **Behavior**: Available across all projects on the local machine for the current user. Not automatically shared in cloud or remote environments unless synced.

### Enterprise / Managed Skills (System Scope)
- **Primary Path**: `/etc/claude-code/.claude/skills/<skill-name>/SKILL.md` (or platform equivalent managed settings path)
- **Behavior**: Deployed by administrative policy across all users on the host machine.

### External & Synced Skills
- **External Directories**: Added at runtime via `--add-dir <path>` or `/add-dir <path>`. Loads `<path>/.claude/skills/`.
- **Synced Skills**: Synced from claude.ai account settings into `~/.claude/skills/synced/<skill-name>/`.

---

## Settings & Configuration

Claude Code separates configuration and permissions into tiered configuration files:

- **Global User Settings (`~/.claude.json` / `~/.claude/settings.json`)**:
  Stores user-wide preferences, active default models, telemetry options, and user-level approved tools and permission rules.
- **Project Settings (`<workspace-root>/.claude/settings.json` or `.claude.json`)**:
  Stores team-level configurations, project-specific permission rules, approved MCP servers, and repository-wide tool allowlists and denylists.
- **Instruction Memory (`CLAUDE.md`)**:
  Placed at the project root or in subdirectories. Contains coding guidelines, architectural summaries, and standing instructions loaded into session context at startup.
- **Permission Configurations**:
  Managed via `permissions.allow` and `permissions.deny` rules in `settings.json`:
  ```json
  {
    "permissions": {
      "allow": [
        "Skill(review-pr *)",
        "Bash(git status *)",
        "Bash(npm test *)"
      ],
      "deny": [
        "Skill(deploy-prod *)",
        "Bash(rm -rf *)"
      ]
    }
  }
  ```

---

## Discovery & Precedence

### Indexing & Progressive Disclosure
Claude Code indexes available skill metadata on session launch. It places each skill's `name` and `description` (capped at 1,536 characters) into the agent's system prompt (~50–100 tokens per skill).
Full skill instructions, supporting documents in `references/`, and helper scripts in `scripts/` remain on disk until the skill is invoked, preserving context window budget.

### Precedence Resolution
When identically named skills exist across multiple scopes:

1. **Enterprise over Personal & Project**: Managed enterprise skills override matching personal and project skills.
2. **Personal over Project**: When invoking `/name` directly, personal skills in `~/.claude/skills/` override project skills in `.claude/skills/`.
3. **Project over Built-ins**: Project skills replace built-in commands sharing the same name.
4. **Nested Skills**: Root skills take `/name`. Nested skills in `<subdir>/.claude/skills/` are accessible via `/<subdir>:<name>` or prioritized when working on files within that directory.
5. **External Directory Skills**: Added directory skills with colliding names are prefixed with the directory name (e.g., `/cli:verify`).
6. **Local over Synced**: Local skills take `/name`; synced skills with colliding names remain callable as `/anthropic-skills:<name>`.

### Invocation Visibility Controls
Frontmatter fields control skill exposure:
- `disable-model-invocation: true`: Removes the skill description from model context. Only executed when the user explicitly triggers `/name`.
- `user-invocable: false`: Omits the skill from the user `/` autocompletion menu. Remains visible to the model for autonomous triggering.

---

## Feature Support

### Tool Pre-Approval and Restriction
The `allowed-tools` frontmatter field grants permission for specified tools without user confirmation prompts during the turn the skill is invoked:

```yaml
allowed-tools:
  - Bash(git status *)
  - Bash(git diff *)
  - Read
  - Grep
```

The grant clears when the user sends their next message.

`disallowed-tools` removes tools from the agent's available tool pool for the turn:
```yaml
disallowed-tools:
  - AskUserQuestion
```

### Subagent Execution via `context: fork`
Executes skill instructions inside an isolated subagent conversation thread:

```yaml
context: fork
agent: Explore
background: false
```

- `context: fork`: Isolates intermediate command output from the primary conversation. The `SKILL.md` body becomes the subagent's task prompt.
- `agent`: Selects execution subagent (`Explore`, `Plan`, `general-purpose`, or custom definitions from `.claude/agents/`). Defaults to `general-purpose`.
- `background`: Sets execution mode. When `true` (default), runs in background; when `false`, halts until the subagent completes and returns findings.

### Lifecycle Hooks
Skills can define event hooks in frontmatter that activate upon invocation and remain registered for the remainder of the session:

```yaml
hooks:
  PreToolUse:
    - matcher: "Bash"
      command: "${CLAUDE_SKILL_DIR}/scripts/validate_cmd.sh"
  PostToolUse:
    - matcher: "Write|Edit"
      command: "npm run lint:fix"
```

Supported hook events:
- `PreToolUse`: Triggers before a tool executes; inspects arguments or aborts execution.
- `PostToolUse`: Triggers after tool execution; inspects results or triggers automatic formatting/tests.
- `UserPromptSubmit`: Triggers when the user sends a message.
- `SessionStart`: Triggers on session startup.
- `Stop`: Triggers at session conclusion.

### Dynamic Context Injection & Variable Substitution
Prefixing a shell command with `!` executes it locally and inlines standard output into instructions before Claude reads the prompt:
```markdown
## Current Status
!`git status --short`
```

Dynamic string substitutions supported:
- `${CLAUDE_SKILL_DIR}`: Path to the directory containing the skill's `SKILL.md`.
- `${CLAUDE_PROJECT_DIR}`: Root directory of the current project workspace.
- `${CLAUDE_SESSION_ID}`: Active session identifier.
- `$ARGUMENTS` or `$0`, `$1`: Positional CLI arguments passed to slash commands.
- `$name`: Named arguments defined in frontmatter `arguments: [name, target]`.

---

## Directory Layout

Standard project directory layout with skills, scripts, and references:

```text
my-project/
├── .claude/
│   ├── settings.json            # Project-level tool permissions & config
│   └── skills/
│       ├── test-runner/         # Complex skill with bundled script
│       │   ├── SKILL.md
│       │   ├── scripts/
│       │   │   └── run_suite.sh
│       │   └── references/
│       │       └── failure-codes.md
│       └── pr-review/           # Subagent review skill
│           ├── SKILL.md
│           └── references/
│               └── checklist.md
├── CLAUDE.md                    # Primary repository instructions
├── package.json
└── src/
    └── index.ts
```

---

## Invocation

Claude Code supports three skill trigger mechanisms:

1. **User Slash Commands**:
   Direct execution using the slash command prefix:
   ```bash
   /test-runner unit --coverage
   ```
   Passes arguments directly into `$ARGUMENTS` in `SKILL.md`.

2. **Model Autonomous Invocation**:
   When user requests match the skill's `description`, the model automatically triggers the skill:
   ```text
   Please review my uncommitted changes against main and flag any security issues.
   ```

3. **In-Prompt Permission Grants**:
   Referencing `/skill-name` inside conversational text authorizes Claude to invoke that skill during its execution turn:
   ```text
   Look over the implementation and run /test-runner if changes are complete.
   ```

---

## Concrete Example

### Example Skill: `pr-review`

#### File: `.claude/skills/pr-review/SKILL.md`

````markdown
---
name: pr-review
description: Audits git branch diffs against main for security risks, error handling gaps, and missing tests. Use when reviewing pull requests or reviewing local branch changes.
argument-hint: "[target-branch]"
arguments:
  - branch
allowed-tools:
  - Bash(git diff *)
  - Bash(git log *)
  - Read
  - Grep
disallowed-tools:
  - AskUserQuestion
context: fork
agent: Explore
background: false
---

# Pull Request Review Guide

## Target Branch
Target comparison: $branch (defaults to `main` if omitted).

## Working Diff Summary
!`git diff --stat ${branch:-main}`

## Review Procedure

1. **Inspect Modifications**:
   Execute `git diff ${branch:-main}` to analyze modified hunks.

2. **Verification Criteria**:
   - Check input boundary validation and error branches.
   - Flag insecure credentials or unescaped data in queries.
   - Verify test suite additions cover new logic branches.

3. **Output Format**:
   Return audit results using the following template:

   ```markdown
   ### Review Summary
   - Target Branch: <branch>
   - Files Analyzed: <count>

   ### Critical Findings
   - <file>:<line> - <defect description and recommended correction>

   ### Non-blocking Suggestions
   - <file>:<line> - <maintainability or style suggestion>
   ```
````

### Execution Example

**User Input:**
```bash
/pr-review main
```

**Agent Action:**
1. Isolates execution in a forked `Explore` subagent without blocking or polluting the main conversation.
2. Inlines `git diff --stat main` output via dynamic context injection.
3. Inspects changed files using pre-approved read and git tools without interactive confirmation prompts.
4. Returns formatted review findings matching the Output Format template.
