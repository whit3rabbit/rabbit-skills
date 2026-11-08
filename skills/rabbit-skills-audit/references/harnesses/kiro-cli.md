# Kiro CLI Harness Reference

Harness specification and execution characteristics for Kiro CLI (`kiro-cli`).

## Contents

- [Overview and Identifier](#overview-and-identifier)
- [Skill Paths](#skill-paths)
- [Settings and Configuration](#settings-and-configuration)
- [Discovery and Precedence](#discovery-and-precedence)
- [Feature Support](#feature-support)
- [Directory Layout](#directory-layout)
- [Invocation](#invocation)
- [Examples](#examples)

## Overview and Identifier

- **Harness Identifier**: `--agent kiro-cli`
- **Documentation**: [Kiro CLI Custom Agents Configuration](https://kiro.dev/docs/cli/custom-agents/configuration-reference/#skill-resources)

## Skill Paths

Kiro CLI resolves skills from workspace-level and user-level directories:

| Scope | Path | Description |
|---|---|---|
| **Project (Workspace)** | `.kiro/skills/` | Project-specific skills scoped to repository workspace root. |
| **Global (User)** | `~/.kiro/skills/` | User-wide skills shared across workspaces. |

Project-level skills override global skills when skill folder names collide.

## Settings and Configuration

Custom agent configurations reside in `.kiro/agents/<agent>.json` (workspace) or `~/.kiro/agents/<agent>.json` (global).

Skills are declared for custom agents inside the `resources` array using the `skill://` URI scheme:

```json
{
  "name": "code-auditor",
  "description": "Custom agent equipped with auditing skills",
  "resources": [
    "skill://.kiro/skills/**/SKILL.md"
  ]
}
```

Glob patterns (such as `skill://.kiro/skills/**/SKILL.md`) or direct skill folder identifiers map target skills into custom agents.

## Discovery and Precedence

- **Default Agent**: Automatically loads skills from `.kiro/skills/` and `~/.kiro/skills/` at startup. Discovered skills follow standard progressive disclosure (YAML frontmatter metadata pre-loaded; full instructions loaded upon activation).
- **Custom Agents**: Do not automatically discover skills. Skills must be explicitly declared in `.kiro/agents/<agent>.json` under the `resources` list with the `skill://` URI prefix.
- **Precedence**: Workspace-level skills (`.kiro/skills/<skill-name>/`) take precedence over user-global skills (`~/.kiro/skills/<skill-name>/`) with matching names.

## Feature Support

| Feature | Supported | Description |
|---|---|---|
| **Basic Skills (`SKILL.md`)** | Yes | Full progressive disclosure with YAML frontmatter `name` and `description`. |
| **Hooks** | Yes | Pre-execution and post-execution hooks configured in agent definitions. |
| **`allowed-tools` Frontmatter** | No | Skill-level tool restrictions are not enforced; tools are scoped via agent config. |
| **Context Forking (`context: fork`)** | No | Isolated sub-agent execution context frontmatter is not supported. |

## Directory Layout

Standard project layout with `.kiro/skills/<skill-name>/` and `.kiro/agents/`:

```
project-root/
├── .kiro/
│   ├── agents/
│   │   └── auditor.json
│   └── skills/
│       └── auditing-skills/
│           ├── SKILL.md
│           ├── references/
│           │   └── audit-checks.md
│           └── scripts/
│               └── audit_static.py
├── src/
└── package.json
```

## Invocation

Skills are activated through prompt triggers or by launching custom agents configured with skill resources.

### Prompt Triggers

In interactive sessions, natural language prompts matching the skill `description` activate the skill:

```bash
kiro
```

Prompt example:
```
Audit the skill in ./custom-skills/validator against best practices
```

### Custom Agent Invocation

Invoke Kiro CLI with the `--agent` flag pointing to the configured custom agent:

```bash
kiro --agent auditor
```

## Examples

### Input: Custom Agent Configuration with Skill Resource

File: `.kiro/agents/auditor.json`

```json
{
  "name": "auditor",
  "description": "Agent with skill auditing capabilities",
  "resources": [
    "skill://.kiro/skills/auditing-skills/SKILL.md"
  ],
  "tools": [
    "read_file",
    "run_command"
  ]
}
```

### Output: Custom Agent Skill Activation

Command execution:
```bash
kiro --agent auditor "Audit ./skills/pdf-helper"
```

Execution trace:
```
[kiro] Initializing agent: auditor
[kiro] Loading resource: skill://.kiro/skills/auditing-skills/SKILL.md
[kiro] Activated skill: auditing-skills
[kiro] Evaluating ./skills/pdf-helper against audit checks...
```
