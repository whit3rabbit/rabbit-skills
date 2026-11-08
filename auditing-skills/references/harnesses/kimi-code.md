# Kimi Code CLI Harness Reference

Reference for skill discovery, structure, configuration, and invocation in Kimi Code CLI (`--agent kimi-code-cli`).

## Contents

- [Identifier & CLI Flag](#identifier--cli-flag)
- [Skill Paths](#skill-paths)
- [Settings & Configuration](#settings--configuration)
- [Discovery & Precedence](#discovery--precedence)
- [Feature Support](#feature-support)
  - [Directory Form vs. Flat Form](#directory-form-vs-flat-form)
  - [Frontmatter Specification](#frontmatter-specification)
  - [Variable Interpolation](#variable-interpolation)
  - [Progressive Disclosure & Limits](#progressive-disclosure--limits)
- [Concrete Directory Layout](#concrete-directory-layout)
- [Invocation](#invocation)
  - [Natural Language Trigger](#natural-language-trigger)
  - [CLI Slash Command](#cli-slash-command)
  - [Concrete Example](#concrete-example)

---

## Identifier & CLI Flag

- Harness Identifier: `kimi-code-cli`
- Audit Flag: `--agent kimi-code-cli`
- Official Documentation: `https://moonshotai.github.io/kimi-code/en/customization/skills`

---

## Skill Paths

Kimi Code CLI discovers skills across four scopes:

| Scope | Location | Description |
|---|---|---|
| Project (Generic) | `.agents/skills/` | Cross-tool standard skill directory at project root |
| Project (Specific) | `.kimi-code/skills/` | Kimi-specific skill directory at project root |
| Global / User (Specific) | `$KIMI_CODE_HOME/skills/` (default: `~/.kimi-code/skills/`) | User-level Kimi skills |
| Global / User (Generic) | `~/.agents/skills/` | Cross-tool generic user skill directory in OS home |
| Extra | Configured via `extra_skill_dirs` in `config.toml` | Custom shared or team skill locations |
| Built-in | Bundled within Kimi Code CLI | CLI internal management workflows |

Project root is determined by locating the nearest directory containing `.git`, searching upward from the current working directory.

In multi-root workspaces, Kimi Code CLI discovers skills across all configured workspace source directories and merges them into a single catalog.

---

## Settings & Configuration

Kimi Code CLI stores its configuration in `$KIMI_CODE_HOME/config.toml` (defaults to `~/.kimi-code/config.toml`).

### Environment Variables

- `KIMI_CODE_HOME`: Base directory for Kimi Code configuration and user data (default: `~/.kimi-code`).
- `KIMI_API_KEY` / `MOONSHOT_API_KEY`: API credentials for model access.

### Configuration Keys (`config.toml`)

- `extra_skill_dirs`: Array of file paths to scan for additional skills.
- `builtin_product_skills`: Boolean flag to enable or disable built-in skills describing Kimi Code CLI itself.

Example configuration (`~/.kimi-code/config.toml`):

```toml
extra_skill_dirs = [
  "~/team-skills",
  ".agents/team-skills"
]
builtin_product_skills = true
```

---

## Discovery & Precedence

Kimi Code CLI resolves skill names using a strict four-tier precedence hierarchy:

```
Project > User > Extra > Built-in
```

### Precedence Rules

1. **Project Scope**:
   - Project-level skills override user-level, extra, and built-in skills with identical names.
   - In multi-directory workspaces, the primary source directory takes precedence over secondary directories when skill names collide.
   - Skill file changes in workspace directories trigger automatic catalog reloads. Session-only directories are excluded unless saved to the workspace.
2. **User Scope**:
   - `$KIMI_CODE_HOME/skills/` and `~/.agents/skills/` provide global skills across projects.
   - When `$KIMI_CODE_HOME` is modified, Kimi-specific skills resolve from the new root, while generic `~/.agents/skills/` remains at the OS user home.
3. **Extra Directories**:
   - Scanned in the order listed in `extra_skill_dirs`.
4. **Built-in Skills**:
   - Lowest priority; shadowed by any matching skill name in higher scopes.

### Format Collision Rule

If both a directory form (`<name>/SKILL.md`) and a flat form (`<name>.md`) share the same skill name inside the same scan directory, the directory form takes precedence and the flat file is ignored.

---

## Feature Support

### Directory Form vs. Flat Form

| Feature | Directory Form (`<name>/SKILL.md`) | Flat Form (`<name>.md`) |
|---|---|---|
| Recommended Use | Multi-file skills, scripts, reference docs | Simple single-prompt skills |
| Name Derivation | Required `name:` frontmatter field | Frontmatter `name:` or filename stem |
| Description Derivation | Required `description:` frontmatter field | Frontmatter `description:` or first body line (up to 240 chars) |
| Supporting Files | Supported in subdirectories | Not supported (loose `.md` files in subdirs ignored) |
| `${KIMI_SKILL_DIR}` | Points to skill directory | Points to parent skills directory |

### Frontmatter Specification

YAML frontmatter in `SKILL.md` supports the following fields:

| Field | Type | Description |
|---|---|---|
| `name` | string | Unique skill identifier (case-insensitive). Required in directory form. |
| `description` | string | Summary used by the model for auto-invocation. Required in directory form. |
| `type` | string | `prompt` (default), `inline` (alias of prompt), or `flow` (manual slash invocation only). |
| `whenToUse` | string | Trigger condition description (aliases: `when-to-use`, `when_to_use`). |
| `disableModelInvocation` | boolean | Set `true` to disable automatic model invocation (aliases: `disable-model-invocation`, `disable_model_invocation`). |
| `arguments` | list / string | Named parameters (array of strings or space-delimited string). Accessible in body as `$<name>`. |

### Variable Interpolation

Before passing the skill body to the model, placeholders are expanded:

- `${KIMI_SKILL_DIR}`: Resolves to the absolute path of the directory containing the skill.
- `$ARGUMENTS`: Full unparsed string of arguments passed at invocation.
- `$0`, `$1`, `$ARGUMENTS[0]`, `$ARGUMENTS[1]`: Positional arguments parsed with quote preservation (`"quoted argument"`).
- `$<name>`: Named arguments declared in `arguments`.
- Unmatched Arguments: If no argument tokens appear in the body, passed arguments are automatically appended as `\n\nARGUMENTS: <text>`.

### Progressive Disclosure & Limits

1. **Discovery Tier**: `name`, `description`, and `whenToUse` are loaded into model system context during initialization (~100 tokens).
2. **Activation Tier**: `SKILL.md` body is loaded into the conversation context only upon invocation.
3. **On-Demand Tier**: Detailed procedures in `${KIMI_SKILL_DIR}/references/` and execution scripts in `${KIMI_SKILL_DIR}/scripts/` are read or executed as needed.
4. **Nesting Depth Limit**: Skill invocations allow up to 3 levels of recursive nesting before automatic termination.

---

## Concrete Directory Layout

```
my-project/
├── .git/
├── .kimi-code/
│   └── skills/
│       └── review-pr/                      # Project-specific directory form
│           ├── SKILL.md                    # Main skill definition
│           └── references/
│               └── checklist.md            # Supporting reference file
├── .agents/
│   └── skills/
│       ├── test-runner/                    # Standard cross-tool directory form
│       │   ├── SKILL.md
│       │   └── scripts/
│       │       └── run_tests.sh            # Helper script
│       └── quick-commit.md                 # Standard cross-tool flat form
└── src/

~/.kimi-code/                               # Global configuration root ($KIMI_CODE_HOME)
├── config.toml                             # Global settings (extra_skill_dirs, builtin_product_skills)
└── skills/
    └── global-helper/
        └── SKILL.md

~/.agents/
└── skills/                                 # Cross-tool user-level skills
    └── formatting/
        └── SKILL.md
```

---

## Invocation

### Natural Language Trigger

When `disableModelInvocation` is `false` (default) and `type` is `prompt` or `inline`, the model automatically triggers the skill whenever user prompt intent matches `description` or `whenToUse`.

### CLI Slash Command

Users can directly invoke any registered skill in the CLI session:

```bash
/skill:review-pr #1234
/skill:quick-commit "fix login redirect bug"
```

### Concrete Example

#### Skill Definition (`.kimi-code/skills/review-pr/SKILL.md`)

```markdown
---
name: review-pr
description: Review pull request diffs against team standards and emit a structured report
type: prompt
whenToUse: When asked to review a pull request, inspect code changes, or verify PR quality
arguments:
  - pr_number
---

Review pull request $pr_number:

1. Fetch and inspect the diff for PR $pr_number.
2. Check guidelines in `${KIMI_SKILL_DIR}/references/checklist.md`.
3. Emit output using the exact template below.

## Output Template

### Summary
[Brief overview of PR changes]

### Verdict
[APPROVE | REQUEST_CHANGES | COMMENT]

### Findings
- [Blocking] <Description with file:line reference>
- [Non-blocking] <Description with suggestion>
```

#### Reference Checklist (`.kimi-code/skills/review-pr/references/checklist.md`)

```markdown
# PR Quality Checklist

- Unit test coverage added or updated for new code paths.
- No exposed credentials or unencrypted sensitive tokens.
- Public functions include TSDoc or Docstring comments.
- Error handling handles timeouts and network failures.
```

#### Invocation Session

Input:

```
/skill:review-pr #42
```

Output:

```markdown
### Summary
PR #42 adds retry logic and exponential backoff to HTTP client requests.

### Verdict
APPROVE

### Findings
- [Non-blocking] client.py:45: Consider making `MAX_RETRIES` configurable via environment variable.
```
