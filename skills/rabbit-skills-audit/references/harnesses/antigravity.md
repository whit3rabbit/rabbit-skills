# Antigravity Harness Reference

Reference guide for skill discovery, directory structure, configuration precedence, and feature support in Google Antigravity and Antigravity CLI.

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
| CLI Identifiers | `--agent antigravity`, `--agent antigravity-cli` |
| Supported Surfaces | Antigravity App, Antigravity CLI (`agy`), Antigravity IDE |
| Specification URL | `https://antigravity.google/docs/skills` |

---

## Compatibility Matrix

| Feature | Supported | Details |
|---|---|---|
| Basic Skills (`SKILL.md`) | Yes | Standard YAML frontmatter (`name`, `description`) and Markdown body. |
| `allowed-tools` Frontmatter | Yes | Filters tools available to the skill during activation. |
| `context: fork` | No | Context forking in frontmatter is not supported; task isolation uses subagents. |
| Skill Frontmatter Hooks | No | Skill files do not declare lifecycle hooks; hooks use `hooks.json`. |
| Subagents | Yes | Autonomous subagent invocation via `invoke_subagent` and `define_subagent`. |
| MCP Tools | Yes | Configured via `mcp_config.json`; callable natively or via `call_mcp_tool`. |

---

## Skill Paths

Antigravity searches multiple directory scopes to discover skills.

### Workspace Skills (Project-Specific)
- **Primary Path**: `{workspace-root}/.agents/skills/<skill-name>/SKILL.md`
- **Fallback Paths**: `{workspace-root}/.agent/skills/`, `{workspace-root}/_agents/skills/`
- **Traversal**: Scanned upward from the current working directory to the repository root. Suitable for version-controlled, team-shared skills.

### Global Skills (User-Wide)
- **Shared Global Path**: `~/.gemini/config/skills/<skill-name>/SKILL.md` (shared by App, CLI, and IDE)
- **CLI-Specific Global Paths**: `~/.gemini/antigravity-cli/skills/`, `~/.gemini/skills/`
- **Plugin Bundles**: `~/.gemini/config/plugins/<plugin-name>/skills/<skill-name>/SKILL.md`

### Built-in Skills (Application-Bundled)
- **Path**: `~/.gemini/antigravity/builtin/skills/<skill-name>/SKILL.md`
- Mounted directly by the application runtime; not scanned via directory walking.

---

## Settings & Configuration

Antigravity separates workspace rules, project settings, and user-level defaults across dedicated paths:

| Location | Path | Scope | Purpose |
|---|---|---|---|
| Project Rules | `AGENTS.md`, `GEMINI.md` | Workspace | High-priority project instructions loaded into prompt context. |
| Granular Rules | `{workspace-root}/.agents/rules/*.md` | Workspace | Topic-specific rule files traversed hierarchically. |
| Workspace Config | `{workspace-root}/.agents/` | Workspace | Project skill configurations and custom subagent definitions. |
| User Configuration | `~/.gemini/config/` | Machine / User | User-wide configurations, `mcp_config.json`, and plugin installations. |
| Runtime App Data | `~/.gemini/antigravity/` | Machine / User | Internal conversation transcripts, logs, and artifacts. |

---

## Discovery & Precedence

When skills share identical `name` values, Antigravity resolves collisions in strict priority order (highest to lowest):

1. **Workspace Project**: `{workspace-root}/.agents/skills/` discovered by ascending from CWD to repository root.
2. **Workspace Declared**: Customizations explicitly listed in workspace `skills.json` or `plugins.json`.
3. **Global User Discovery**: `~/.gemini/config/skills/` (and CLI-specific directories).
4. **Built-in Skills**: Bundled runtime skills in `~/.gemini/antigravity/builtin/skills/`.
5. **Global Declared**: Customizations explicitly pinned in global JSON configurations.

---

## Feature Support

### `allowed-tools` Restriction
Skills can restrict or whitelist execution tools in YAML frontmatter. Tools omitted from `allowed-tools` are masked while the skill is active.

```yaml
---
name: schema-validator
description: Validates database migrations against current production schemas.
allowed-tools:
  - run_command
  - read_file
---
```

### Subagent Delegation
Rather than running multi-step background jobs in the main conversation window, Antigravity uses subagents (`invoke_subagent`). Subagents execute in isolated contexts, inheriting workspace skills and returning results upon completion.

### Model Context Protocol (MCP)
MCP tools defined in `~/.gemini/config/mcp_config.json` or plugin manifests are exposed either as native tools (`mcp_<server>_<tool>`) or lazily via `call_mcp_tool`.

---

## Directory Layout

A standard Antigravity project repository with local skills and rules adheres to the following tree structure:

```
my-project/
├── .agents/
│   ├── rules/
│   │   └── style-guide.md               # Contextual coding rules
│   └── skills/
│       └── audit-deployment/
│           ├── SKILL.md                 # Required entrypoint with frontmatter
│           ├── scripts/
│           │   └── check_endpoints.py   # Executable verification script
│           ├── references/
│           │   └── checklist.md         # On-demand reference document
│           └── resources/
│               └── schema.json          # Supporting schema or asset
├── AGENTS.md                            # Primary project instructions
├── package.json
└── src/
    └── index.ts
```

---

## Invocation

Antigravity supports three invocation models:

1. **Autonomous Progressive Disclosure**: Skill metadata (`name` and `description`) is loaded into the agent prompt context. When user requests match the skill description, the agent automatically reads `SKILL.md` and applies the workflow.
2. **Manual Slash Commands**: Every discovered skill creates a matching interactive slash command (`/<skill-name>`). Typing `/audit-deployment` in the Antigravity App or CLI TUI forces immediate skill activation.
3. **Background Agent Execution**: Subagents initiated with `invoke_subagent` invoke skills autonomously in parallel execution branches without blocking the primary user conversation.

---

## Concrete Example

### Example Skill: `code-audit`

#### File: `.agents/skills/code-audit/SKILL.md`

```markdown
---
name: code-audit
description: Audits source code for security vulnerabilities, formatting issues, and test coverage gaps. Use when checking code quality or preparing pull requests.
allowed-tools:
  - read_file
  - run_command
---

# Code Audit Workflow

Follow this procedure to evaluate code quality before submitting changes:

## Verification Steps

1. **Syntax & Linting**:
   Run the static linter script:
   ```bash
   python3 scripts/check_syntax.py --path src/
   ```

2. **Security Checks**:
   Inspect dependencies and credentials:
   - Verify no secrets or keys are hardcoded.
   - Run dependency vulnerability scan.

3. **Report Results**:
   Output audit results using the format below.

## Output Format

Output:
- **Status**: PASS | FAIL
- **Lint Errors**: Total count and location (`file:line`)
- **Security Findings**: Summary of vulnerabilities
- **Recommended Action**: Concrete remediation steps
```

### Execution Example

**User Input:**
```
Audit the authentication service code in src/auth before I open a pull request.
```

**Agent Action:**
1. Recognizes match with `code-audit` description.
2. Loads `.agents/skills/code-audit/SKILL.md`.
3. Executes `python3 scripts/check_syntax.py --path src/auth`.
4. Returns formatted audit findings matching the Output Format template.
