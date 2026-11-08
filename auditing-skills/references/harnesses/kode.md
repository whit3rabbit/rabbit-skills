# Kode Harness Reference

Reference guide for skill discovery, directory layout, configuration precedence, and feature support in Kode.

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
| CLI Identifier | `--agent kode` |
| Primary Command | `kode` |
| Upstream Specification | `https://github.com/shareAI-lab/kode/blob/main/docs/skills.md` |

---

## Compatibility Matrix

| Feature | Supported | Details |
|---|---|---|
| Basic Skills (`SKILL.md`) | Yes | Standard YAML frontmatter (`name`, `description`) with markdown body. |
| Tool Whitelisting (`allowed-tools`) | Yes | Supported in frontmatter; supports parameter patterns (e.g. `Read`, `Bash(git:*)`). |
| Slash Command Invocation | Yes | Discovered skills map to interactive slash commands (e.g. `/<skill-name>`). |
| Autonomous Model Invocation | Yes | Automated invocation via the internal `Skill` tool when prompt triggers match. |
| Plugin Packs & Marketplaces | Yes | Distribute and install skill packs via `.kode-plugin/marketplace.json` and `.kode-plugin/plugin.json`. |
| Legacy Compatibility | Yes | Discovers `.claude/skills` and `.claude/commands` for backwards compatibility. |

---

## Skill Paths

Kode discovers skills across project-level directories and global user configurations:

### Project-Level Skills (Workspace)
- **Primary Project Path**: `<project-root>/.kode/skills/<skill-name>/SKILL.md`
- **Standard Agent Path**: `<project-root>/.agents/skills/<skill-name>/SKILL.md`
- **Legacy Compatibility Paths**: `<project-root>/.claude/skills/<skill-name>/SKILL.md`, `<project-root>/.claude/commands/<skill-name>/SKILL.md`

Project skills are tracked in version control and shared across all repository contributors.

### Global Skills (User Scope)
- **Primary User Path**: `~/.kode/skills/<skill-name>/SKILL.md`
- **User Plugin Storage**: `~/.kode/plugins/` (installed with `--scope user`)

Global skills are available across all workspaces on the local system.

---

## Settings & Configuration

Kode stores project settings and user-wide agent configurations in the following paths:

| Configuration Scope | Path | Purpose |
|---|---|---|
| Project Settings | `<project-root>/.kode/config.json` | Project-specific overrides, enabled plugins, and tool policies. |
| Project Workspace Directory | `<project-root>/.kode/` | Project state, local marketplace plugins, and project skills. |
| User Settings | `~/.kode/config.json` | Global settings, default model preferences, and telemetry options. |
| User State Directory | `~/.kode/` | Global marketplaces registry, installed user plugins, and global skills. |
| Marketplace Manifest | `.kode-plugin/marketplace.json` | Repository-level catalog defining installable skill packs and plugins. |
| Plugin Manifest | `.kode-plugin/plugin.json` | Manifest declaring plugin components, permissions, and skill roots. |

---

## Discovery & Precedence

When multiple skills share the same `name`, Kode resolves collisions using the following precedence (highest to lowest priority):

1. **Project Scope (`.kode/skills/`)**: Local repository skills override all other definitions.
2. **Project Agents Scope (`.agents/skills/`)**: Cross-harness repository skills directory.
3. **Legacy Project Scope (`.claude/skills/`, `.claude/commands/`)**: Compatibility directories within the local workspace.
4. **Global User Scope (`~/.kode/skills/`)**: User-level skills installed on the machine.
5. **Installed Marketplace Plugins**: Skills bundled inside enabled user or project plugins.

---

## Feature Support

### Frontmatter Metadata
Skills require a `SKILL.md` file with valid YAML frontmatter:
- `name`: Must match the parent directory name, 1–64 characters, lowercase alphanumeric and hyphens only (`^[a-z0-9-]+$`).
- `description`: 1–1024 characters describing what the skill does and when to use it.
- `allowed-tools`: List or space-delimited string specifying permitted tools during execution.

```yaml
---
name: release-gate
description: Runs pre-release verification, checks git status, and validates semver tags. Use when preparing or verifying a release.
allowed-tools: Read Bash(git:*) Bash(jq:*)
---
```

### Execution Tools
Kode parses fine-grained tool restrictions from `allowed-tools`. Parameterized tool definitions such as `Bash(git:*)` permit bash operations restricted to specific subcommands or prefixes while the skill is active.

### Plugin and Marketplace Management
Skills can be bundled into plugin packs and managed via the `kode plugin` CLI or interactive slash commands:

- Add marketplace: `kode plugin marketplace add owner/repo` (or `/plugin marketplace add owner/repo`)
- Install plugin pack: `kode plugin install <plugin>@<marketplace> --scope project` (or `--scope user`)
- Manage plugins: `kode plugin enable <plugin>@<marketplace>` / `kode plugin disable <plugin>@<marketplace>`
- Inspect marketplaces: `kode plugin marketplace list`

---

## Directory Layout

Standard repository structure with project-level Kode skills and marketplace configuration:

```
my-project/
├── .kode/
│   ├── config.json
│   └── skills/
│       └── release-gate/
│           ├── SKILL.md
│           ├── scripts/
│           │   └── check_tags.py
│           └── references/
│               └── release-checklist.md
├── .agents/
│   └── skills/
│       └── linting/
│           └── SKILL.md
├── .kode-plugin/
│   └── marketplace.json
├── src/
│   └── main.py
└── README.md
```

---

## Invocation

Kode supports two invocation patterns:

1. **Natural Language Triggering**:
   Kode exposes skill metadata (`name` and `description`) to the model. When a user prompt matches a skill description, the model calls its internal `Skill` tool to activate the skill and read `SKILL.md`.

2. **CLI / Interactive Slash Command**:
   In interactive sessions, users trigger skills explicitly by entering `/<skill-name>`. For example, `/release-gate` immediately loads and activates `.kode/skills/release-gate/SKILL.md`.

---

## Concrete Example

### Example Skill: `release-gate`

#### File: `.kode/skills/release-gate/SKILL.md`

```markdown
---
name: release-gate
description: Verifies repository readiness and git status before creating tags. Use when preparing or verifying a software release.
allowed-tools: Read Bash(git:*)
---

# Release Gate Workflow

Follow this procedure to verify release readiness:

## Verification Steps

1. Verify working tree is clean:
   ```bash
   git status --porcelain
   ```
2. Retrieve the latest annotated tag:
   ```bash
   git describe --tags --abbrev=0
   ```
3. Check commits since the latest tag:
   ```bash
   git log $(git describe --tags --abbrev=0)..HEAD --oneline
   ```

## Output Format

Output:
- **Status**: READY | BLOCKED
- **Latest Tag**: `<tag>`
- **Unreleased Commits**: `<count>`
- **Blockers**: None, or list of uncommitted files / failed checks
```

### Execution Example

**Input:**
```
Check if the repository is ready to cut release v2.1.0.
```

**Agent Action:**
1. Matches prompt against `release-gate` description.
2. Invokes internal `Skill` tool to load `.kode/skills/release-gate/SKILL.md`.
3. Runs permitted `git` commands:
   ```bash
   git status --porcelain
   git describe --tags --abbrev=0
   git log v2.0.9..HEAD --oneline
   ```
4. Produces structured output matching the required format.

**Output:**
```markdown
- **Status**: READY
- **Latest Tag**: v2.0.9
- **Unreleased Commits**: 4
- **Blockers**: None
```
