# OpenClaw Harness Reference

Reference guide for skill discovery, directory structure, configuration precedence, sandboxing, and invocation in OpenClaw.

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
| CLI Identifiers | `--agent openclaw` |
| Supported Surfaces | OpenClaw Gateway, Control UI, WebChat, Claw CLI (`openclaw`) |
| Specification URL | `https://docs.openclaw.ai/tools/skills` |

---

## Compatibility Matrix

| Feature | Supported | Details |
|---|---|---|
| Basic Skills (`SKILL.md`) | Yes | Standard YAML frontmatter (`name`, `description`) and Markdown body. |
| `allowed-tools` Frontmatter | Yes | Filters tools available to the skill during activation. |
| `context: fork` | No | Frontmatter context forking is not supported; task isolation uses sandboxed sessions. |
| Skill Frontmatter Hooks | No | Skill files do not declare lifecycle hooks; hooks use Gateway/plugin hooks. |
| Metadata Gating | Yes | Supports `metadata.openclaw` block for platform, binary, env, and config preconditions. |
| Tool Dispatch | Yes | Supports `command-dispatch: tool` to dispatch slash commands directly to registered tools. |
| Variable Expansion | Yes | `{baseDir}` expands to the skill directory path in markdown instructions. |

---

## Skill Paths

OpenClaw scans multiple directory scopes to discover skills, supporting both flat and grouped layouts (up to 6 levels deep).

### Workspace Skills (Project-Specific)
- **Primary Workspace Path**: `<workspace>/skills/<skill-name>/SKILL.md`
- **Project Agent Skills**: `<workspace>/.agents/skills/<skill-name>/SKILL.md`
- Discovery stops further subdirectory traversal once a `SKILL.md` is detected.
- Project-level skills override global, managed, and bundled skills.

### Global & Managed Skills (User-Wide)
- **Personal Agent Skills**: `~/.agents/skills/<skill-name>/SKILL.md`
- **Managed Global Skills**: `~/.openclaw/skills/<skill-name>/SKILL.md` (or `<state-dir>/skills/`)
- **Workshop Skills**: `<state-dir>/agents/<agentId>/agent/workshop-skills/<skill-name>/SKILL.md` (agent self-learned skills)

### Bundled & Plugin Skills
- **Bundled Skills**: Shipped with the OpenClaw installation.
- **Extra Directories**: Declared via `skills.load.extraDirs` in `openclaw.json`.
- **Plugin Skills**: Shipped within enabled plugins (e.g. browser automation skills).

---

## Settings & Configuration

OpenClaw configures skills and execution environments in `~/.openclaw/openclaw.json` (or `$OPENCLAW_STATE_DIR/openclaw.json`).

### Skill Configuration (`skills.entries`)

Per-skill settings control enablement, environment variables, and credentials:

```json5
{
  "skills": {
    "entries": {
      "image-lab": {
        "enabled": true,
        "apiKey": { "source": "env", "provider": "default", "id": "IMAGE_API_KEY" },
        "env": {
          "IMAGE_API_KEY": "secret-value"
        },
        "config": {
          "model": "nano-pro"
        }
      },
      "code-review": {
        "enabled": true
      }
    },
    "load": {
      "extraDirs": ["~/custom-tools/skills"],
      "allowSymlinkTargets": ["~/shared-skills"],
      "watch": true
    }
  }
}
```

### Agent Allowlists (`agents.*.skills`)

Skill visibility is governed independently from skill location:

```json5
{
  "agents": {
    "defaults": {
      "skills": ["github", "weather"]  // Baseline skills for all agents
    },
    "entries": {
      "developer": {
        "workspace": "~/project"        // Inherits defaults ["github", "weather"]
      },
      "reviewer": {
        "skills": ["github", "linter"]  // Explicit allowlist replaces defaults entirely
      },
      "locked-down": {
        "skills": []                    // Disables all skills for this agent
      }
    }
  }
}
```

### Security & Sandboxing

- **Sandbox Backends**: Docker, Podman, SSH, OpenShell.
- **Materialized Copies**: Sandboxed sessions read synchronized copies in the container rather than raw host paths.
- **Binary Requirements (`requires.bins`)**: Verified on the host during load time. When sandboxing is enabled, binaries must also be installed in the container (e.g. via `agents.defaults.sandbox.docker.setupCommand` or pre-built container images).
- **Secret Scope**: `skills.entries.*.env` and `apiKey` inject values into the host process for the turn only; secrets are not leaked into the container sandbox.
- **Symlink Containment**: Realpaths must stay within the configured skill root unless explicitly permitted via `skills.load.allowSymlinkTargets`.

---

## Discovery & Precedence

When identical skill names collide across sources, OpenClaw resolves them in strict priority order (highest to lowest):

1. **Workspace Skills**: `<workspace>/skills/`
2. **Project Agent Skills**: `<workspace>/.agents/skills/`
3. **Personal Agent Skills**: `~/.agents/skills/` (default state directory only)
4. **Managed Global Skills**: `~/.openclaw/skills/` (or `<state-dir>/skills/`)
5. **Workshop Skills**: `<state-dir>/agents/<agentId>/agent/workshop-skills/`
6. **Bundled Skills**: Shipped with the OpenClaw release
7. **Extra Directories & Plugins**: `skills.load.extraDirs` and plugin `openclaw.plugin.json` skills

Project-level definitions in `skills/` override any identically named global or bundled definition.

---

## Feature Support

### `allowed-tools` Restriction
Limits available tools while the skill is active. Tools not listed are masked during execution:

```yaml
---
name: schema-checker
description: Validates database migrations against schema definitions.
allowed-tools:
  - run_command
  - read_file
---
```

### Precondition Gating (`metadata.openclaw`)
Skills can specify binary, environment variable, platform, or configuration prerequisites in frontmatter:

```yaml
---
name: image-generator
description: Generates project graphics using CLI tooling.
metadata:
  {
    "openclaw": {
      "requires": {
        "bins": ["magick"],
        "env": ["GRAPHICS_API_KEY"],
        "config": ["graphics.enabled"]
      },
      "os": ["darwin", "linux"]
    }
  }
---
```

### Direct Tool Dispatch
Skills can bind slash commands directly to registered tools, bypassing LLM prompt expansion:

```yaml
---
name: quick-format
description: Runs project code formatter directly.
user-invocable: true
command-dispatch: tool
command-tool: format_code
command-arg-mode: raw
---
```

---

## Directory Layout

A typical OpenClaw repository layout with local skills, configuration, and supporting scripts:

```
my-project/
├── .clawhub/
│   └── lock.json                     # ClawHub package lock file
├── openclaw.json                      # Workspace configuration and allowlists
├── skills/
│   ├── code-audit/
│   │   ├── SKILL.md                  # Main skill definition with YAML frontmatter
│   │   ├── references/
│   │   │   └── security-rules.md     # Reference doc loaded on demand (<256 KiB)
│   │   └── scripts/
│   │       └── run_audit.py          # Executable verification script
│   └── deployment/
│       └── k8s-sync/
│           └── SKILL.md              # Grouped layout (nested up to 6 levels)
├── package.json
└── src/
    └── index.ts
```

---

## Invocation

OpenClaw supports three invocation mechanisms:

1. **Autonomous Model Selection**: Eligible skills are summarized into an XML `<available_skills>` block in the system prompt (~24 tokens base per skill). The model invokes the skill and reads `SKILL.md` when the user task matches the skill description.
2. **Explicit Prompt References (`$skill-name`)**: Typing `$` in the composer inserts an explicit skill reference (e.g. `Use $code-audit to check src/`). OpenClaw instructs the model to read `SKILL.md` before taking action.
3. **Interactive Slash Commands (`/<skill-name>`)**: Skills with `user-invocable: true` register interactive slash commands (e.g. `/code-audit`). If configured with `command-dispatch: tool`, execution dispatches directly to the underlying tool without model reasoning.

### CLI Management Commands

```bash
# Verify skill eligibility, prerequisites, and visibility
openclaw skills check

# List active skills for the current workspace
openclaw skills list

# Install a skill from ClawHub into the workspace
openclaw skills install @owner/slug

# Install globally for all agents
openclaw skills install @owner/slug --global

# Inspect or restore self-learned workshop skills
openclaw skills workshop list
openclaw skills workshop restore <name>
```

---

## Concrete Example

### Example Skill: `code-audit`

#### File: `skills/code-audit/SKILL.md`

```markdown
---
name: code-audit
description: Audits source code for security vulnerabilities, formatting issues, and test coverage gaps. Use when checking code quality or preparing pull requests.
allowed-tools:
  - read_file
  - run_command
metadata:
  {
    "openclaw": {
      "requires": {
        "bins": ["python3"]
      }
    }
  }
---

# Code Audit Workflow

Follow this procedure to evaluate code quality before submitting changes:

## Verification Steps

1. **Run Static Checks**:
   Execute the audit script located at `{baseDir}/scripts/run_audit.py`:
   ```bash
   python3 {baseDir}/scripts/run_audit.py --path src/
   ```

2. **Inspect Vulnerabilities**:
   - Verify no secret keys or credentials are committed.
   - Check dependency manifests against known security advisories.

3. **Format Report**:
   Provide findings using the exact template below.

## Output Format

ALWAYS use this exact template:

Output:
- **Status**: PASS | FAIL
- **Lint Errors**: Total count and location (`file:line`)
- **Security Findings**: Summary of vulnerabilities
- **Recommended Action**: Concrete remediation steps
```

### Execution Example

**User Input:**
```
Check the authentication handler in src/auth.ts before I commit.
```

**Agent Action:**
1. Matches query against `code-audit` description.
2. Reads `skills/code-audit/SKILL.md`.
3. Executes `{baseDir}/scripts/run_audit.py --path src/`.
4. Outputs the structured audit report following the required output template.
