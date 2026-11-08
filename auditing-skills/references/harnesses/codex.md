# Codex Harness Reference

Reference for OpenAI Codex skill discovery, configuration, and execution.

## Contents

- [Identifier](#identifier)
- [Skill paths](#skill-paths)
- [Settings and configuration](#settings-and-configuration)
- [Discovery and precedence](#discovery-and-precedence)
- [Feature support](#feature-support)
- [Concrete directory layout](#concrete-directory-layout)
- [Invocation](#invocation)
- [Concrete invocation example](#concrete-invocation-example)

---

## Identifier

- CLI flag / agent identifier: `--agent codex`
- Harness documentation: https://developers.openai.com/codex/skills

---

## Skill paths

Codex discovers skills across repository, user, machine, and bundled scopes:

| Scope | Path | Purpose |
|-------|------|---------|
| Project (Working Directory) | `.agents/skills/` (or `$CWD/.agents/skills/`) | Scoped to current working directory or microservice |
| Project (Parent / Repository) | `$CWD/../.agents/skills/` up to `$REPO_ROOT/.agents/skills/` | Shared skills checked into root or parent repository directories |
| User / Personal | `~/.agents/skills/` (or `$HOME/.agents/skills/`) | User-specific skills available across all projects |
| System / Machine | `/etc/codex/skills/` | System administrator skills for containers and multi-user machines |
| Bundled | Internal to Codex | Pre-installed system utilities (`skill-creator`, `skill-installer`) |

Codex traverses symlinks to target destinations when resolving skill directories.

---

## Settings and configuration

### Configuration files

- Project settings: `.codex/config.toml` (in repository root or project working directory)
- User settings: `~/.codex/config.toml` (in user home directory)

### Environment variables

Environment variables are configured in the user shell environment or loaded via project `.env` files. Scripts executed by Codex skills inherit the active environment variables.

### Disabling skills

Skills can be disabled selectively in `.codex/config.toml` or `~/.codex/config.toml`:

```toml
# Disable by file path
[[skills.config]]
path = "/path/to/skill/SKILL.md"
enabled = false

# Disable by skill name
[[skills.config]]
name = "unwanted-skill"
enabled = false
```

When multiple rules match a skill, the last matching entry determines the state.

To disable all built-in bundled skills for a repository, add to `.codex/config.toml`:

```toml
[skills.bundled]
enabled = false
```

### Context token budget

Configure the startup token budget for indexing skill descriptions:

```toml
[skills]
max_context_tokens = 5000
```

---

## Discovery and precedence

### Progressive disclosure

Codex manages context usage across three distinct phases:

1. **Discovery (Startup):** Codex indexes `name`, `description`, and file `path` for all available skills. The initial index uses at most 2% of the context window (or 8,000 characters if the model context window is unspecified), up to a maximum of 10,000 tokens configurable via `skills.max_context_tokens`. When the budget is exceeded, skill descriptions are shortened or omitted with a warning.
2. **Activation:** When a skill is triggered explicitly or matched implicitly, Codex loads the complete `SKILL.md` body into context.
3. **Execution:** External references in `references/` and code in `scripts/` load or execute on demand.

### Discovery precedence and collision handling

Codex traverses directories from `$CWD` upwards to `$REPO_ROOT`:

```
$CWD/.agents/skills/
└── $CWD/../.agents/skills/
    └── ... (parent directories)
        └── $REPO_ROOT/.agents/skills/
            └── ~/.agents/skills/
                └── /etc/codex/skills/
                    └── Bundled skills
```

- If multiple skills share the same `name` across different locations, Codex does not merge or overwrite them; both entries remain visible and selectable in skill listings.
- Repository-level skills provide project-specific workflows, whereas user-level skills provide developer-specific workflows across projects.

---

## Feature support

| Capability | Supported | Notes |
|------------|-----------|-------|
| Basic skills (`SKILL.md`) | Yes | Supported via standard YAML frontmatter (`name`, `description`) and markdown instructions |
| `allowed-tools` | Yes | Supported for declaring tool permissions |
| `context: fork` | No | Execution occurs within the main conversation session; isolated sub-context forks are not supported |
| Hooks | No | Pre-execution and post-execution lifecycle hooks are not supported |

### Optional metadata (`agents/openai.yaml`)

Skills can define an optional `agents/openai.yaml` to specify UI metadata, tool dependencies, and invocation policy:

```yaml
interface:
  display_name: "Code Refactor"
  short_description: "Automated refactoring workflows"
  icon_small: "./assets/small-logo.svg"
  icon_large: "./assets/large-logo.png"
  brand_color: "#3B82F6"
  default_prompt: "Refactor this module according to repo conventions"
policy:
  allow_implicit_invocation: false
dependencies:
  tools:
    - type: "mcp"
      value: "projectTools"
      description: "Project analysis MCP server"
      transport: "streamable_http"
      url: "https://localhost:8000/mcp"
```

Setting `policy.allow_implicit_invocation: false` disables automatic triggering based on user prompt, requiring explicit `$skill-name` invocation.

---

## Concrete directory layout

Standard project structure with repository skills and Codex configuration:

```
my-project/
├── .codex/
│   └── config.toml
├── .agents/
│   └── skills/
│       └── code-refactor/
│           ├── SKILL.md
│           ├── agents/
│           │   └── openai.yaml
│           ├── scripts/
│           │   └── analyze.py
│           └── references/
│               └── patterns.md
├── src/
│   └── main.py
└── README.md
```

### SKILL.md layout example

```markdown
---
name: code-refactor
description: Analyzes and refactors code modules following project architecture standards. Use when restructuring code or updating patterns.
allowed-tools:
  - run_command
  - read_file
  - edit_file
---

# Code Refactor

Instructions for refactoring repository code modules.
```

---

## Invocation

Codex supports both explicit and implicit invocation:

- **Explicit invocation:**
  - Prefix skill name with `$` in Codex CLI or IDE extension prompts: `$code-refactor`
  - Run the `/skills` slash command in CLI or IDE to list and choose skills
  - Prefix with `@` in ChatGPT web or desktop environments: `@code-refactor`
- **Implicit invocation:**
  - Function calling and natural language instruction matching evaluate the user prompt against each skill's `name` and `description`.
  - When the user task aligns with the skill description, Codex automatically reads `SKILL.md`.
  - Implicit invocation can be deactivated with `policy.allow_implicit_invocation: false` in `agents/openai.yaml`.

---

## Concrete invocation example

### Scenario: Refactoring module interfaces

Input:
```text
$code-refactor src/api/users.py
```

Output:
```text
[code-refactor] Reading src/api/users.py...
[code-refactor] Executing scripts/analyze.py --file src/api/users.py
[code-refactor] 2 architectural improvements identified.
[code-refactor] Applying refactoring changes to src/api/users.py...
[code-refactor] Refactoring complete. Running verification tests.
```
