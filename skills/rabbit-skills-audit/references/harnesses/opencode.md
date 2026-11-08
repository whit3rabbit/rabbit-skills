# OpenCode Harness Reference

Reference for skill discovery, layout conventions, and configuration when targeting the OpenCode agent harness.

- **Harness identifier:** `opencode` (CLI: `--agent opencode`)
- **Documentation:** https://opencode.ai/docs/skills

## Contents

- [Skill Locations](#skill-locations)
- [Directory Layout](#directory-layout)
- [Configuration and Settings](#configuration-and-settings)
- [Discovery and Precedence](#discovery-and-precedence)
- [Feature Compatibility](#feature-compatibility)
- [Frontmatter Specification](#frontmatter-specification)
- [Invocation and Execution](#invocation-and-execution)

## Skill Locations

OpenCode searches for skills across global and project-scoped directories, supporting both native paths and cross-agent compatibility paths.

| Scope | Type | Path |
|---|---|---|
| Project | Primary | `.opencode/skills/<skill-id>/` |
| Project | Compatibility | `.agents/skills/<skill-id>/` |
| Project | Compatibility | `.claude/skills/<skill-id>/` |
| Global | Primary | `~/.config/opencode/skills/<skill-id>/` |
| Global | Compatibility | `~/.agents/skills/<skill-id>/` |
| Global | Compatibility | `~/.claude/skills/<skill-id>/` |
| Configured | Custom / HTTP | Defined in `opencode.json` / `opencode.jsonc` via `"skills"` |

Project-level paths take precedence over global paths when skill IDs match.

## Directory Layout

OpenCode supports directory-based skills containing a `SKILL.md` entry file, as well as root-level single-file skills (`<skill-id>.md`). Directory-based skills provide a dedicated base directory for private scripts, references, and assets.

```text
my-project/
├── .opencode/
│   └── skills/
│       └── git-release/
│           ├── SKILL.md
│           ├── scripts/
│           │   └── changelog.sh
│           └── references/
│               └── release-policy.md
├── .agents/
│   └── skills/
│       └── sql-lint/
│           └── SKILL.md
├── opencode.jsonc
└── src/
```

Rules for skill directories:
- A directory containing `SKILL.md` constitutes one self-contained skill. OpenCode does not search child directories of a skill directory for nested skills.
- Relative paths referenced inside `SKILL.md` resolve relative to the directory containing `SKILL.md`.
- Flat single-file skills must reside directly at the source root (for example, `.opencode/skills/review.md`).

## Configuration and Settings

Configuration files control custom skill directories, HTTP skill catalogs, and execution permissions.

### File Locations

- **Project:** `opencode.json` or `opencode.jsonc` in repository root.
- **Global:** `~/.config/opencode/opencode.json` or `~/.config/opencode/opencode.jsonc`.

### Registering Skill Sources

Define the `"skills"` array in `opencode.jsonc` to register additional local directories or remote HTTP catalogs:

```jsonc
{
  "$schema": "https://opencode.ai/config.json",
  "skills": [
    "./team-skills",
    "~/shared/opencode-skills",
    "/opt/company-skills",
    "https://example.com/opencode/skills/"
  ]
}
```

Path resolution behavior:
- **Relative path (`./...`):** Resolves from active working directory where OpenCode runs.
- **User home path (`~/...`):** Resolves relative to current user's home directory.
- **Absolute path (`/...`):** Used as written.
- **HTTP/HTTPS URL:** Fetched as a remote catalog expecting an `index.json` registry file.

### Skill Permissions

Configure `"permissions"` rules in `opencode.jsonc` using `"action": "skill"` and skill ID glob patterns as the resource:

```jsonc
{
  "permissions": [
    { "action": "skill", "resource": "*", "effect": "allow" },
    { "action": "skill", "resource": "internal-*", "effect": "deny" },
    { "action": "skill", "resource": "prod-*", "effect": "ask" }
  ]
}
```

Rules evaluate in declaration order; the last matching rule takes effect.

| Effect | Behavior |
|---|---|
| `allow` | Advertises matching skills and loads them without prompt confirmation. |
| `ask` | Advertises matching skills; requests user confirmation before loading. |
| `deny` | Hides matching skills from the model and blocks loading. |

Permissions can also be scoped to specific agents under `agents.<agent-id>.permissions`.

## Discovery and Precedence

OpenCode assigns skill IDs based strictly on file path, not the frontmatter `name` field.

### Skill ID Resolution

- `<source>/<skill-id>/SKILL.md` yields skill ID `<skill-id>`.
- `<source>/<skill-id>.md` yields skill ID `<skill-id>`.
- Nested grouping directories `<source>/teams/<skill-id>/SKILL.md` yield skill ID `<skill-id>`.

Skill IDs are case-sensitive. Standard convention uses lowercase alphanumeric characters and hyphens:
`^[a-z0-9]+(-[a-z0-9]+)*$`

### Source Precedence

When multiple sources define the same skill ID, the source registered later in precedence overrides earlier definitions:

1. Built-in skills (lowest precedence)
2. `.claude/skills` (global user directory, then ancestor directories toward working directory)
3. `.agents/skills` (global user directory, then ancestor directories toward working directory)
4. `~/.config/opencode/skills` (global user configuration)
5. Project `.opencode/skills` (repository root toward current working directory)
6. Explicit `"skills"` entries in `opencode.jsonc` (highest precedence, evaluated in array order)

Project-local directory skills always override global and compatibility configurations. Discovery stops six directory levels below each source root. Hidden directories and `node_modules` are excluded.

## Feature Compatibility

| Feature | Supported | Specification |
|---|---|---|
| Basic skills | Yes | `SKILL.md` with YAML frontmatter and Markdown body. Directory skills expose base directory and sample of up to 10 supporting file paths. |
| `allowed-tools` | Yes | Configured via `permissions` in `opencode.jsonc` or agent configurations. |
| `context: fork` | No | Sub-agent context isolation frontmatter is not supported. |
| Hooks | No | Lifecycle pre/post execution hooks are not supported. |
| Model disable | Yes | `metadata.opencode/autoinvoke: false` or `disable-model-invocation: true`. |
| HTTP Catalogs | Yes | Remote catalogs serving `index.json` manifests over HTTP/HTTPS. |

## Frontmatter Specification

OpenCode parses YAML frontmatter enclosed in `---` blocks at the start of `SKILL.md`.

```yaml
---
name: Git Release
description: Prepare release notes, bump version numbers, and tag GitHub releases.
metadata:
  opencode/autoinvoke: false
---
```

Field behavior:
- `name`: Human-readable display label. Optional; defaults to path-derived skill ID.
- `description`: Plain-text summary inspected by the model during skill discovery. A description is required for the model to automatically discover and list the skill.
- `metadata.opencode/autoinvoke`: Boolean. Setting `false` omits the skill from model prompt advertisement while keeping it manually callable via `@<skill-id>`.
- `disable-model-invocation`: Boolean alias for `opencode/autoinvoke: false`. When both are present, `opencode/autoinvoke` takes precedence.
- Portability fields: Common metadata fields (`license`, `compatibility`) parse without causing syntax errors.

## Invocation and Execution

OpenCode supports model-driven tool loading, direct user prompt mentions, and CLI-specified agent sessions.

### Model Tool Invocation

OpenCode provides the model with a list of permitted skills (IDs, names, and descriptions). The model loads full instructions dynamically using the built-in `skill` tool:

```json
{
  "id": "git-release"
}
```

Upon tool execution:
1. OpenCode evaluates agent permissions for the requested skill ID.
2. The Markdown body is appended to conversation context (frontmatter stripped).
3. The skill directory path and a sample of up to 10 supporting file paths are provided.

### User Prompt Invocation

Users explicitly load skills into context by prefixing the skill ID with `@` in prompt text:

```text
Prepare changelog for next release with @git-release
```

### CLI Execution

To run OpenCode with a specific agent configuration from the terminal:

```bash
opencode --agent opencode
```
