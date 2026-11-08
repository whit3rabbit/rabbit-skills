# DeepSeek Harness Reference

Reference guide for skill discovery, layout, progressive disclosure, and invocation in DeepSeek Harness (DSH).

- **Harness Identifier:** `deepseek-harness` / `dsh` (CLI: `dsh`)
- **Documentation:** https://deepseekdocs.com/en/docs/features/skills

## Contents

- [Skill Locations](#skill-locations)
- [Directory Layout](#directory-layout)
- [Frontmatter Specification](#frontmatter-specification)
- [Discovery and Precedence](#discovery-and-precedence)
- [Progressive Disclosure and Invocation Seams](#progressive-disclosure-and-invocation-seams)
- [Feature Support Matrix](#feature-support-matrix)
- [CLI and Profile Integration](#cli-and-profile-integration)
- [DSH Skill Linter Checks (`DSK-01` through `DSK-12`)](#dsh-skill-linter-checks-dsk-01-through-dsk-12)

## Skill Locations

DeepSeek Harness resolves skills through `@deepseek-ai/dsh-skill-filesystem` across project, custom, and global scopes:

| Scope | Type | Path | Precedence Rank |
|---|---|---|---|
| Project | DSH-native | `<projectRoot>/.dsh/skills/<skill-name>/` | 100 (Highest) |
| Project | Cross-tool convention | `<projectRoot>/.agents/skills/<skill-name>/` | 200 |
| External | Config-declared | User-configured `customSkillDirs` | 300 |
| Global | Primary Harness root | `~/.dsh/skills/<skill-name>/` | 400 |
| Global | Shared agents root | `~/.agents/skills/<skill-name>/` | 500 (Fallback) |

Location rules:

- Project root is resolved by finding the nearest ancestor directory containing `.git`, falling back to the current working directory (`cwd`).
- The user global directory (`~/.dsh/skills/`) automatically excludes its internal `.system/` subdirectory from skill scanning.
- Skills may be provided as either a directory bundle containing `SKILL.md` or a single flat markdown file `<skill-name>.md`.
- When the same skill name exists at multiple ranks, the lower rank number (higher priority) shadows lower priority ranks.

## Directory Layout

DeepSeek Harness supports two layout shapes within skill root directories:

### Directory Bundle Shape (Recommended for Complex Skills)

```text
my-project/
├── .dsh/
│   └── skills/
│       └── code-reviewer/
│           ├── SKILL.md
│           ├── references/
│           ├── scripts/
│           └── assets/
└── .git/
```

### Flat File Shape (For Lightweight Single-File Skills)

```text
my-project/
├── .dsh/
│   └── skills/
│       └── quick-check.md
└── .git/
```

In directory bundles, relative paths inside `SKILL.md` resolve against the skill directory, maintaining portable Agent Skills compliance.

## Frontmatter Specification

Both `SKILL.md` and flat `<name>.md` skills require valid YAML frontmatter demarcated by `---` delimiters:

```yaml
---
name: code-reviewer
description: Review pull requests and staged git diffs against codebase conventions.
disable-model-invocation: false
user-invocable: true
---
```

### Required Fields

| Field | Type | Description |
|---|---|---|
| `name` | string | Unique skill identifier in lowercase `kebab-case` (`^[a-z0-9-]+$`). Maximum 64 characters. |
| `description` | string | Routing and trigger description inspected by the model during skill discovery. |

### DSH-Specific Optional Fields

| Field | Type | Default | Description |
|---|---|---|---|
| `disable-model-invocation` | boolean | `false` | When set to `true`, excludes the skill from the model's auto-discovery catalog and prompt loader. |
| `user-invocable` | boolean | `true` | When set to `false`, hides the skill from human-facing CLI command menus and manual invocation. |

> [!IMPORTANT]
> DeepSeek Harness enforces strict type checking on frontmatter: non-boolean values or misspelled boolean flags fail closed, preventing the skill from loading.

## Discovery and Precedence

1. **Discovery Phase:** At session startup or when refreshing skills, `@deepseek-ai/dsh-skill-filesystem` traverses discovered roots in ascending rank order (100 to 500).
2. **Deduplication:** When matching `name` values are discovered across layers, the nearest layer (lowest rank number) wins.
3. **Shadowing:** Project skills in `.dsh/skills/` cleanly shadow identically named global skills in `~/.dsh/skills/`.

## Progressive Disclosure and Invocation Seams

DeepSeek Harness implements strict progressive disclosure through the `ctx.skills` service in Cordis to conserve context tokens:

- **`ctx.skills.list(...)`**: Emits a lightweight, name-sorted catalog containing only skill names and descriptions. Only this catalog enters the model's initial context.
- **`ctx.skills.snapshot(...)`**: Generates a frozen observation of available skills for validation and tooling.
- **`ctx.skills.get(name, ...)`**: Dynamically loads and expands the complete `SKILL.md` body instructions and supporting files only when the skill is actively invoked.

## Feature Support Matrix

| Feature | Support Level | Implementation Notes |
|---|---|---|
| `SKILL.md` Bundle | Supported | Primary portable format under `<root>/<name>/SKILL.md`. |
| Flat `.md` Skill | Supported | Single-file format under `<root>/<name>.md`. |
| Subdirectories (`references/`, `scripts/`) | Supported | Fully supported in directory bundles. |
| Progressive Disclosure | Native | Managed by `ctx.skills` service. |
| Model Invocation Gating | Native | Supported via `disable-model-invocation: true`. |
| User CLI Invocability | Native | Supported via `user-invocable: false`. |
| Multi-Layer Stacking | Native | Ranks 100 through 500. |

## CLI and Profile Integration

In DeepSeek Harness, skills can be verified and managed across runtime profiles:

```bash
# Verify skills loaded in the active profile:
dsh skill list

# Inspect a specific skill definition:
dsh skill show code-reviewer

# Check active profile paths:
dsh profile info
```

## DSH Skill Linter Checks (`DSK-01` through `DSK-12`)

The specialized linter `scripts/audit_dsh_skill.py` validates skills against DSH-native requirements:

| Check ID | Severity | Check Name | Passing Condition & Fix |
|---|---|---|---|
| **DSK-01** | Error | Skill Layout Shape | Skill exists as directory bundle `<name>/SKILL.md` or flat `<name>.md`. |
| **DSK-02** | Error | YAML Frontmatter Delimiters | Skill begins with valid YAML frontmatter demarcated by `---`. |
| **DSK-03** | Error | Skill Identifier Format | `name` is lowercase kebab-case (`^[a-z0-9-]+$`), at most 64 characters. |
| **DSK-04** | Error | Name and Path Alignment | Frontmatter `name` matches the directory name or flat file stem. |
| **DSK-05** | Error | Routing Description | Frontmatter includes a clear, trigger-rich `description` (min 20 chars). |
| **DSK-06** | Error | Boolean Invocation Gating | `disable-model-invocation` is strict YAML boolean (`true` or `false`). |
| **DSK-07** | Error | Boolean User Invocability | `user-invocable` is strict YAML boolean (`true` or `false`). |
| **DSK-08** | Warning | Recognized Frontmatter | No unknown or unsupported frontmatter keys that trigger fail-closed loading. |
| **DSK-09** | Error | Link Resolution Integrity | All relative markdown links resolve to files within the skill bundle. |
| **DSK-10** | Warning | Token Budget Adherence | Skill body is within 500 lines to avoid bloat upon progressive expansion. |
| **DSK-11** | Error | Credential Safety | No plaintext API keys, secret tokens, or passwords in skill files. |
| **DSK-12** | Warning | Precedence Shadowing | Flag identically named skills across discovered filesystem roots. |

Run the DSH skill linter:

```bash
# Audit a single DSH skill bundle:
python3 skills/rabbit-skills-audit/scripts/audit_dsh_skill.py path/to/my-skill --strict

# Audit an entire DSH skills directory:
python3 skills/rabbit-skills-audit/scripts/audit_dsh_skill.py .dsh/skills/ --format markdown
```

