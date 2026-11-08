# Roo Code Harness Reference

Reference for skill discovery, mode targeting, configuration, and invocation in Roo Code.

- **Harness Identifier:** `--agent roo`
- **Official Documentation:** https://docs.roocode.com/features/skills

## Contents

- [Overview](#overview)
- [Skill Discovery Paths](#skill-discovery-paths)
- [Settings & Configuration](#settings--configuration)
- [Discovery & Precedence](#discovery--precedence)
- [Feature Support Matrix](#feature-support-matrix)
- [Mode Targeting](#mode-targeting)
- [Directory Layout](#directory-layout)
- [Example Skill Specification](#example-skill-specification)
- [Invocation & Triggering](#invocation--triggering)

## Overview

Roo Code implements the Agent Skills specification via a three-tier progressive disclosure model:
1. **Discovery:** Scans `SKILL.md` frontmatter (`name`, `description`) at startup. Metadata is indexed into memory without loading file bodies.
2. **Activation:** Loads `SKILL.md` into the model prompt via `read_file` when user requests match the skill description.
3. **Resource Access:** Discovers supporting assets (`scripts/`, `templates/`, `references/`) on demand when instructions reference them.

## Skill Discovery Paths

Roo Code discovers skills across project-scoped and user-scoped (global) roots, supporting both Roo-specific and cross-agent directories:

| Scope | Roo-Specific Path (Higher Priority) | Cross-Agent Shared Path |
|---|---|---|
| **Project (Workspace)** | `<project-root>/.roo/skills/<skill-name>/` | `<project-root>/.agents/skills/<skill-name>/` |
| **Project Mode-Specific** | `<project-root>/.roo/skills-<modeSlug>/<skill-name>/` | `<project-root>/.agents/skills-<modeSlug>/<skill-name>/` |
| **Global (User)** | `~/.roo/skills/<skill-name>/` | `~/.agents/skills/<skill-name>/` |
| **Global Mode-Specific** | `~/.roo/skills-<modeSlug>/<skill-name>/` | `~/.agents/skills-<modeSlug>/<skill-name>/` |

### Path Notes
- **Cross-Platform Storage:** Global paths resolve to `~/.roo/skills/` on macOS/Linux and `%USERPROFILE%/.roo/skills/` on Windows.
- **Cross-Agent Sharing:** `.agents/skills/` paths allow sharing identical skill trees across multiple agent harnesses.
- **Symlink Resolution:** Directories and symlinks inside skill folders are indexed; the skill identifier derives from the directory or symlink name.

## Settings & Configuration

Roo Code configuration files govern modes, permissions, and tool execution boundaries:

| Scope | Location | Format & Purpose |
|---|---|---|
| **Custom Modes (Project)** | `<project-root>/.roomodes` | JSON/YAML defining custom modes, role descriptions, and tool restrictions. |
| **Custom Instructions (Project)** | `<project-root>/.roorules`, `.clinerules` | Markdown instructions applied across all prompts. |
| **Mode Rules (Project)** | `<project-root>/.roo/rules-<modeSlug>/`, `.clinerules-<modeSlug>` | Markdown rules loaded only in the targeted mode. |
| **File Exclusions** | `<project-root>/.rooignore` | Glob patterns that prevent Roo Code from reading or modifying matching files. |
| **Global Settings & Modes** | VS Code global extension storage | User profiles, API providers, and global custom modes across workspaces. |

## Discovery & Precedence

When multiple skills share the same name across project and global locations, Roo Code resolves collisions using strict precedence (highest to lowest):

1. **Project `.roo` mode-specific:** `.roo/skills-<modeSlug>/<skill-name>/`
2. **Project `.roo` generic:** `.roo/skills/<skill-name>/`
3. **Project `.agents` mode-specific:** `.agents/skills-<modeSlug>/<skill-name>/`
4. **Project `.agents` generic:** `.agents/skills/<skill-name>/`
5. **Global `.roo` mode-specific:** `~/.roo/skills-<modeSlug>/<skill-name>/`
6. **Global `.roo` generic:** `~/.roo/skills/<skill-name>/`
7. **Global `.agents` mode-specific:** `~/.agents/skills-<modeSlug>/<skill-name>/`
8. **Global `.agents` generic:** `~/.agents/skills/<skill-name>/`

### Resolution Rules
- **Project Overrides Global:** Project-level skills always override user-level global skills of identical name.
- **Roo-Specific Overrides Cross-Agent:** At the same scoping tier, `.roo/` paths override `.agents/` paths.
- **Mode-Specific Overrides Generic:** Mode-targeted skill folders override untargeted folders in the same root.
- **Name Validation:** The YAML frontmatter `name` must match the parent directory or symlink name exactly (1–64 characters, lowercase alphanumeric and single hyphens).

## Feature Support Matrix

| Feature | Supported | Notes |
|---|---|---|
| **Basic Skills (`SKILL.md`)** | **Yes** | Validates `name` and `description` YAML frontmatter. |
| **Tool Restriction (`allowed-tools`)** | **Yes** | Configurable via custom mode definitions (`.roomodes`) or skill declarations. |
| **Forked Context (`context: fork`)** | **No** | Executes in the active session context without isolated agent branching. |
| **Lifecycle Hooks** | **No** | Pre-tool and post-tool lifecycle execution hooks are not supported for skills. |
| **Mode Targeting** | **Yes** | Scoped activation via `skills-<modeSlug>/` directory structures. |
| **Symlink Support** | **Yes** | Supports symlinked skill trees for sharing across repositories. |

## Mode Targeting

Roo Code allows constraining skills to specific modes by naming the skill parent directory with a `-<modeSlug>` suffix:

- `skills-code/`: Active only when operating in Code mode.
- `skills-architect/`: Active only when operating in Architect mode.
- `skills-ask/`: Active only when operating in Ask mode.
- `skills-<customMode>/`: Active only when operating in a custom mode defined in `.roomodes`.

When switching modes, Roo Code filters the active skill catalog so that mode-specific skills from other modes remain dormant. Generic skills in `skills/` remain available across all modes unless overridden.

## Directory Layout

Example structure of a workspace with project configuration, custom modes, and mode-targeted skills:

```text
my-project/
├── .roo/
│   ├── skills/
│   │   └── api-builder/
│   │       ├── SKILL.md
│   │       ├── scripts/
│   │       │   └── generate-endpoint.py
│   │       └── references/
│   │           └── endpoint-conventions.md
│   ├── skills-code/
│   │   └── refactor-patterns/
│   │       └── SKILL.md
│   └── rules-code/
│       └── formatting.md
├── .agents/
│   └── skills/
│       └── shared-linter/
│           └── SKILL.md
├── .roomodes
├── .roorules
├── .rooignore
└── src/
```

## Example Skill Specification

Concrete `SKILL.md` implementation with tool restrictions:

```markdown
---
name: api-builder
description: Generates API endpoint schemas and boilerplate handlers. Use when creating or updating API endpoint definitions.
allowed-tools:
  - read_file
  - write_to_file
  - execute_command
---

# API Builder

Generate endpoint definitions and validate route schemas.

## Workflow

1. Generate endpoint handlers:
   ```bash
   python3 scripts/generate-endpoint.py --spec references/endpoint-conventions.md
   ```
2. Verify output files against API standards.
```

### Mode Definition Example

Associated custom mode configuration in `.roomodes`:

```json
{
  "customModes": [
    {
      "slug": "api-designer",
      "name": "API Designer",
      "roleDefinition": "Designs and validates API schemas and endpoints.",
      "groups": ["read", ["edit", { "fileRegex": "\\.(json|ya?ml|ts)$" }], "command"]
    }
  ]
}
```

## Invocation & Triggering

Skills activate via natural language matching or mode switching:

### Semantic Matching
Roo Code matches incoming user prompts against discovered skill descriptions:
- **Input:** `"Generate a new endpoint for user profile retrieval"`
- **Behavior:** The model identifies `api-builder` by matching description terms, executes `read_file` on `.roo/skills/api-builder/SKILL.md`, and incorporates instructions into context.

### Mode Switching
Switching modes in the Roo Code interface alters active skill catalogs:
- Switching to `Code` activates `skills-code/` entries.
- Skills residing in `skills-architect/` are removed from the active tool and instruction catalog during `Code` turns.
