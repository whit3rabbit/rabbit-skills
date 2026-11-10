# Amp Harness Reference

Reference guide for skill discovery, directory structure, configuration precedence, and feature support in Amp.

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
| CLI Identifiers | `--agent amp`, `--agent universal` |
| Supported Surfaces | Amp Desktop, Amp TUI / CLI, Amp Orbs |
| Specification URL | `https://ampcode.com/manual#agent-skills` |

---

## Compatibility Matrix

| Feature | Supported | Details |
|---|---|---|
| Basic Skills (`SKILL.md`) | Yes | Standard YAML frontmatter (`name`, `description`) with Markdown instructions. |
| `allowed-tools` Frontmatter | Yes | Restricts or pre-approves tools accessible while the skill is active. |
| `context: fork` | No | Context forking is not supported; execution runs within the current thread or orb context. |
| Skill Frontmatter Hooks | No | Lifecycle hooks in skill frontmatter are not supported. |
| Universal Standard | Yes | Shares the standard `.agents/skills/` directory convention with Replit and Universal. |

---

## Skill Paths

Amp discovers skills across repository and machine scopes.

### Project Skills (Repository Scope)
- **Primary Path**: `{workspace-root}/.agents/skills/<skill-name>/SKILL.md`
- **Fallback / Compatibility Path**: `{workspace-root}/.claude/skills/<skill-name>/SKILL.md`
- **Behavior**: Scanned upward from the current working directory to the project repository root. These skills are version-controlled and shared across teams.

### Global Skills (Machine Scope)
- **Primary Global Path**: `~/.config/agents/skills/<skill-name>/SKILL.md`
- **Fallback Global Path**: `~/.agents/skills/<skill-name>/SKILL.md`
- **Behavior**: Available across all projects on the local machine or runner orb. Skills can be installed globally using `amp skill add <source> --global`.

---

## Settings & Configuration

Amp organizes workspace rules, skill directories, and personal defaults across distinct scopes:

| Location | Path | Scope | Purpose |
|---|---|---|---|
| Project Rules | `AGENTS.md` | Workspace | High-level instructions loaded into thread context for the repository. |
| Project Skills | `{workspace-root}/.agents/skills/` | Workspace | Team-shared skills tracked in version control. |
| Project Settings | `{workspace-root}/.amp/` or `amp.json` | Workspace | Project-specific configuration, runner options, and environment rules. |
| Global Settings | `~/.config/amp/settings.json` (or `~/.amp/`) | Machine / User | User-wide configuration, credentials, and default model preferences. |
| Global Skills | `~/.config/agents/skills/` (or `~/.agents/skills/`) | Machine / User | User-specific skills accessible across all workspaces. |

---

## Discovery & Precedence

When skills share identical `name` attributes, Amp resolves collisions in priority order (highest to lowest):

1. **Machine-level Personal Skills**: `~/.config/agents/skills/` and `~/.agents/skills/` (personal skills take precedence, allowing local developer customizations to override project defaults).
2. **Project-level Skills**: `{workspace-root}/.agents/skills/` and fallback `.claude/skills/` found by ascending from the working directory to the repository root.
3. **Official / Built-in Skills**: Bundled system skills provided with the Amp runtime.

---

## Feature Support

### Basic Skills
Skills require a `SKILL.md` file with standard YAML frontmatter containing `name` and `description`. Amp exposes the skill name and description to the model. Full instructions are loaded only when the skill is activated.

### `allowed-tools` Restriction
Skills can restrict or whitelist tools available during execution:

```yaml
---
name: lint-check
description: Runs project linting and checks formatting compliance.
allowed-tools:
  - run_command
  - read_file
---
```

### Unsupported Features
- **Context Forking (`context: fork`)**: Amp executes skills directly within the thread or orb environment rather than spinning off an isolated subagent context.
- **Hooks**: Skill frontmatter does not support lifecycle hooks (such as pre-tool or post-tool execution scripts).

---

## Directory Layout

A typical Amp project repository utilizing `.agents/skills/` adheres to the following structure:

```
my-project/
├── .agents/
│   └── skills/
│       └── test-runner/
│           ├── SKILL.md                 # Required entrypoint with YAML frontmatter
│           ├── scripts/
│           │   └── run_suite.py         # Helper script executed by the agent
│           └── references/
│               └── failure-codes.md     # Supplementary documentation loaded on demand
├── AGENTS.md                            # Repository-level instructions for Amp
├── package.json
└── src/
    └── index.ts
```

---

## Invocation

Amp supports two invocation mechanisms:

1. **Autonomous Contextual Triggering**: Amp provides registered skill names and descriptions in the agent prompt context. When a user request matches a skill's declared description, Amp retrieves `SKILL.md` and applies its workflow.
2. **Explicit User Request**: Users can invoke skills directly by mentioning the skill name in the conversation prompt (e.g., "Run test-runner on the auth package").

---

## Concrete Example

### Example Skill: `test-runner`

#### File: `.agents/skills/test-runner/SKILL.md`

```markdown
---
name: test-runner
description: Runs test suites and formats test failures. Use when verifying code changes or investigating broken tests.
allowed-tools:
  - run_command
  - read_file
---

# Test Runner Workflow

Follow these steps to execute test suites and summarize outcomes:

## Execution Steps

1. Run the test suite:
   ```bash
   python3 scripts/run_suite.py --target unit
   ```

2. Inspect failures:
   If any tests fail, inspect the relevant test source files and error logs.

3. Format the report using the template below.

## Output Format

Output:
- **Status**: PASS | FAIL
- **Suites Run**: Total number of test suites executed
- **Failures**: List of failing test cases with file paths and line numbers
- **Remediation**: Suggested next steps to resolve test failures
```

### Execution Example

**User Input:**
```
Input: Run tests for the user authentication module and report any failures.
```

**Agent Execution:**
1. Evaluates user request against skill descriptions and selects `test-runner`.
2. Reads `.agents/skills/test-runner/SKILL.md`.
3. Runs `python3 scripts/run_suite.py --target unit`.
4. Produces the structured report matching the output template:

**Skill Output:**
```
Output:
- **Status**: FAIL
- **Suites Run**: 4
- **Failures**:
  - `tests/auth/test_login.py:42`: `test_expired_session` raised `TokenExpiredError`
- **Remediation**: Update token validation logic in `src/auth/jwt.py` to refresh expired sessions gracefully.
```
