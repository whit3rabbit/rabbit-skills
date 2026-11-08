# Hermes Agent Harness Reference

Reference guide for skill discovery, hub installation, layout, and invocation in Hermes (Nous Research).

- **Harness Identifier:** `hermes` (CLI: `hermes`)
- **Documentation:** https://hermes-agent.nousresearch.com/docs/user-guide/features/skills (verified 8 November 2026)

## Contents

- [Skill Locations](#skill-locations)
- [Directory Layout](#directory-layout)
- [Frontmatter Specification](#frontmatter-specification)
- [Discovery and Precedence](#discovery-and-precedence)
- [Feature Support Matrix](#feature-support-matrix)
- [Hub Installation and GitHub Taps](#hub-installation-and-github-taps)
- [Invocation and Execution](#invocation-and-execution)

## Skill Locations

Hermes resolves skills from project, global, and config-declared directories:

| Scope | Type | Path |
|---|---|---|
| Project | Hermes-native | `.hermes/skills/<skill-id>/` |
| Project | Cross-tool convention | `.agents/skills/<skill-id>/` |
| Global | Primary (bundled, hub-installed, and agent-created skills all land here) | `~/.hermes/skills/<skill-id>/` |
| External | Config-declared, scanned alongside local | `skills.external_dirs` entries in Hermes config |

Location rules:

- Project root is the nearest ancestor directory containing `.git`.
- Project skills are active only for sessions launched inside the repository. Run `hermes skills trust` to trust a project (and `hermes skills untrust` to revoke).
- Hub state lives under `~/.hermes/skills/.hub/` (`lock.json`, `quarantine/`, `audit.log`). The bundled skill manifest is `~/.hermes/skills/.bundled_manifest`.
- `skills.create_dir` in config redirects agent-created skills elsewhere (e.g. `/opt/brain/skills`).
- Non-existent `external_dirs` paths are silently skipped. Entries support `~` expansion and `${VAR}` substitution.

Precedence order: project, then local `~/.hermes/skills/`, then `skills.create_dir`, then `external_dirs`.

## Directory Layout

A skill is a directory containing a `SKILL.md` entrypoint plus optional subdirectories:

```text
my-project/
├── .hermes/
│   └── skills/
│       └── release-notes/
│           ├── SKILL.md
│           ├── references/
│           ├── templates/
│           ├── scripts/
│           ├── examples/
│           └── assets/
└── .git/
```

Relative paths inside `SKILL.md` resolve against the skill directory, per the portable Agent Skills convention.

## Frontmatter Specification

`SKILL.md` requires valid YAML frontmatter with two required fields:

```yaml
---
name: release-notes
description: Draft release notes from merged commits and tags.
---
```

### Required Fields

| Field | Type | Description |
|---|---|---|
| `name` | string | Slash-command and display name. Lowercase letters, digits, and hyphens, with no leading, trailing, or consecutive hyphens (portable Agent Skills convention). |
| `description` | string | Routing description shown to the model. A declared skill without a description is not loaded. |

### Optional Fields

| Field | Description |
|---|---|
| `version` | Skill version string. |
| `platforms` | List of `macos`, `linux`, `windows`. Hides the skill on incompatible operating systems. |
| `author` | Skill author. |
| `metadata.hermes.tags` | Discovery tags. |
| `metadata.hermes.category` | Category shown in hub listings and `skills_list()`. |
| `metadata.hermes.config` | List of `{key, description, default, prompt}` user config settings. |
| `requires_toolsets` / `fallback_for_toolsets` | Conditional activation: show only when a toolset is present, or only when it is missing. |
| `requires_tools` / `fallback_for_tools` | Same gating at individual tool granularity. |
| `required_environment_variables` | Entries with `name`, `prompt`, `help`, `required_for`. |

### House Standard (Guidance, Not Load Requirements)

Hermes documents a house standard for authored skills: body sections `When to Use`, `Procedure`, `Pitfalls`, and `Verification`. Its linter emits advisory warnings for a description over 60 characters, a body past roughly 24,000 characters (`oversized-body`), and more than 60 reference files (`references-sprawl`). These warnings do not block loading. Only malformed frontmatter or a missing description does.

## Discovery and Precedence

1. **Startup registration:** Hermes adds each skill's `name`, `description`, and path to the system prompt. Full instructions load on demand.
2. **Hard load rules:** Malformed `SKILL.md` files and declared skills without descriptions are not loaded. Invalid optional fields mostly produce warnings, not startup failure.
3. **Collisions:** When two skills share a name, Hermes keeps the first discovered and emits a warning. Bundles take precedence over same-named skills.

## Feature Support Matrix

| Feature | Supported | Notes |
|---|---|---|
| Basic skills (`SKILL.md`) | Yes | Portable Agent Skills convention, directory-based. |
| Slash invocation | Yes | Up to 5 leading `/skill` tokens per message. |
| Skill bundles | Yes | `~/.hermes/skill-bundles/<slug>.yaml`, invoked as `/<bundle-name>`. |
| Platform gating | Yes | `platforms` frontmatter list. |
| Conditional activation | Yes | `requires_toolsets`, `fallback_for_toolsets`, `requires_tools`, `fallback_for_tools`. |
| Agent authoring | Yes | Agent creates and edits skills via the `skill_manage` tool. |
| Lifecycle hooks | No | Hooks belong to the separate Hermes plugin system. |

## Hub Installation and GitHub Taps

The skills hub installs skills from curated and community sources, with a security scan on every install. Trust tiers are `builtin`, `official`, `trusted`, and `community`. `--force` overrides only caution/warn-style findings, never a dangerous verdict.

```bash
hermes skills browse                        # interactive catalog
hermes skills search kubernetes             # search
hermes skills inspect <id>                  # inspect before install
hermes skills install official/security/1password
hermes skills install openai/skills/k8s     # GitHub source: owner/repo/skill
hermes skills check                         # verify installed skills
hermes skills update                        # update installed skills
hermes skills audit                         # audit installed skills
hermes skills uninstall <name>
hermes skills reset <name> [--restore]      # reset a bundled skill
```

Custom GitHub taps add private or third-party repos as sources:

```bash
hermes skills tap add myorg/skills-repo
```

The default tap path is `skills/`, so a repository that keeps skills under a root-level `skills/` directory is discovered without configuration. A URL installs a single file: `hermes skills install https://example.com/SKILL.md --name my-skill`. A desktop deep link is also available: `hermes://skill/install?identifier=...`.

There is no separate plugin-install command for skills. Plugins (hooks, tools, slash commands) are a separate system under `hermes plugins`, with user plugins at `~/.hermes/plugins/<name>/` and project plugins at `./.hermes/plugins/<name>/` (gated by `HERMES_ENABLE_PROJECT_PLUGINS=1`).

## Invocation and Execution

1. **Slash commands:** `/<skill-name>` with instruction text, e.g. `/release-notes draft notes for v2.1`. Up to 5 skill tokens stack in one message.
2. **Bundles:** `/<bundle-name>` loads all skills listed in the bundle.
3. **Model routing:** Skills matching the request context are offered to the model automatically. Toolset and tool gating provide `disable-model-invocation`-style behavior.
4. **Discovery in chat:** `hermes chat --toolsets skills -q "What skills do you have?"`.
5. **Agent tool API:** `skills_list()` (~3k token listing of name/description/category) and `skill_view(name)` or `skill_view(name, path)` read skill content on demand.
