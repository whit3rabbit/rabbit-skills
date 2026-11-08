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
- [Plugins, MCP, & App Integration](#plugins-mcp--app-integration)
- [Codex Use Case Checker & Plugin Planning](#codex-use-case-checker--plugin-planning)

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

---

## Plugins, MCP, & App Integration

Codex and ChatGPT support packaging skills, MCP servers, UI assets, and app widgets into portable Agent Plugins via root `plugin.json` and `mcp.json`.

For the complete guide on Codex plugin creation, portable Agent Plugins schemas, `extensions.com.openai` metadata, bundled MCP servers, and local marketplace catalogs, refer to the companion skill **rabbit-plugin-audit** (`codex-plugins.md`).

---

## Codex Use Case Checker & Plugin Planning

Before authoring or deploying skills and plugins in Codex, run a structured use-case check based on OpenAI's plugin planning specifications ([OpenAI Plugin Use-Case Planning](https://developers.openai.com/plugins/plan/use-case) and [OpenAI Skills Guide](https://developers.openai.com/plugins/build/skills)).

The use-case check determines what belongs in your Codex plugin or skill, identifies missing coverage, and enforces safety boundaries.

### 1. Start from User Expectations

A developer installing a Codex skill or plugin creates immediate expectations from its name, description, starter prompts, and tool permissions.

Gather likely requests from:
- **Developer tasks:** Refactorings, test migrations, linting fixes, build diagnostics, pull request reviews, schema validations.
- **Direct requests:** Prompts that name the skill or plugin directly:
  - Codex CLI / IDE: `$code-refactor src/api/users.py`
  - ChatGPT: `@code-refactor review this controller`
- **Indirect requests:** Natural language prompts stating the developer's underlying goal without naming the skill:
  - *"Why is the user API test failing?"*
  - *"Modernize the error handling in this module."*
  - *"Check this PR for breaking schema changes."*
- **Existing workarounds:** Manual tasks where developers copy logs or diffs between the terminal and browser.

Do not restrict brainstorming to existing CLI commands or APIs. First capture what developers expect Codex to accomplish, then evaluate what can be implemented safely.

### 2. Codex Use-Case Inventory

For each identified workflow, complete the 7-field inventory:

| Field | Question to Answer in Codex | Example for a Code Refactoring Plugin |
|---|---|---|
| **User goal** | What is the developer trying to achieve? | Restructure legacy callback-based functions into async/await |
| **Example requests** | How will users ask directly and indirectly? | Direct: `$modernize-async src/handlers/`<br>Indirect: *"Convert these callbacks to async/await syntax"* |
| **Expected result** | What output defines a successful run? | Updated files on disk, syntax validation passing, concise diff summary displayed |
| **Required context** | What repository state or permissions are required? | Access to target files, local Node.js or Python runtime for AST parsing |
| **Plugin capability** | Does it require a Skill, an MCP Tool, or UI? | **Skill** (`SKILL.md` + AST script in `scripts/`) |
| **Safety boundary** | Does it modify files, run shell commands, or touch git history? | Modifies code files on disk (`edit_file`). Requires clean git working tree before editing. |
| **Support decision** | Support in v1, defer to v2, or intentionally exclude? | **Support** (v1 release) |

Group related requests that share the same underlying goal (e.g., *"Convert callbacks to promises"*, *"Use async/await"*, and *"Modernize async syntax"* belong to one use case with parameter variations).

### 3. Codex Coverage Check

Review every supported use case against your Codex skill or plugin implementation:

1. **Complete execution path:** Trace from initial user prompt (CLI prompt or `@` mention) through skill activation, tool execution (`allowed-tools` or MCP tool), to verified output. Ensure there are no dead ends.
2. **Identify gaps:** Check for missing read permissions, absent AST parsers, missing dependencies (`pip install`, `npm install`), or unhandled compiler/interpreter errors.
3. **Avoid raw technical tool exposure:** Never expose low-level CLI utilities or raw API endpoints without wrapping them into recognizable developer goals. A skill should not merely expose `run_command("sed ...")`; it should provide a verified refactoring workflow with lint validation.
4. **Enforce write authorization and confirmation:** Sensitive write operations (destructive file overwrites, git force pushes, executing untrusted shell commands, cloud mutations) must require explicit user confirmation before executing.
5. **Handle refusals gracefully:** When a request is outside the plugin's scope, Codex must explain why it cannot fulfill the request and provide a recommended alternative or manual command.

### 4. Document Intentional Exclusions

Document deliberate reasons for excluding workflows rather than leaving silent gaps:

- **Safety & privacy risks:** Refuse to modify `.env`, credentials files, or secrets repositories automatically.
- **Unreliable execution:** Defer complex semantic refactoring across untyped dynamic languages if AST tooling cannot guarantee correctness.
- **Missing verification capabilities:** Exclude tasks that cannot be verified locally via tests or compilers.
- **Out of scope for v1:** Clearly document deferred features in the skill description and README to avoid false expectations.

These exclusions define refusal behaviors in `SKILL.md`, guide `policy.allow_implicit_invocation`, and shape negative test cases.

### 5. Build Decisions: The Smallest Implementation Rule

For each supported use case, select the minimal component that accomplishes the goal:

```
                          [Developer Goal]
                                  │
          ┌───────────────────────┼────────────────────────┐
          ▼                       ▼                        ▼
  [Procedural Guide]       [Tool/API Access]      [Visual Inspection]
          │                       │                        │
  Does it need repeatable  Does it need live data  Does visual comparison
  steps & repo context?   or controlled execution?  materially help?
          │                       │                        │
          ▼                       ▼                        ▼
     BUILD SKILL              BUILD MCP                 ADD UI
   (`SKILL.md`)            (`mcp.json`)             (`.app.json`)
```

- **Build a Skill (`SKILL.md`):** Use when instructions, code snippets, reference guidelines, and bundled scripts can guide Codex through the task.
- **Build an MCP Server (`mcp.json`):** Use when the workflow requires live database queries, remote cloud platform actions, OAuth authentication, or secure services.
- **Add UI (`.app.json` / ChatGPT App):** Use only when visual interaction (e.g. side-by-side diff review, interactive parameter form, dependency graph visualization) materially improves the workflow.

### 6. Codex Use-Case Test Matrix

Use the use-case inventory as your evaluation suite:

| Request Category | Example Prompt | Expected Codex Behavior |
|---|---|---|
| **Direct Invocation** | `$code-refactor src/api/auth.py` | Activates `code-refactor` skill, parses AST, applies refactoring, runs test suite |
| **Indirect / Natural Language** | *"Refactor the authentication handler to use dependency injection"* | Automatically triggers `code-refactor` via description matching, guides refactoring |
| **Edge Case / Boundary** | `$code-refactor empty_file.py` | Detects empty file, reports informative message without throwing unhandled exceptions |
| **Negative / Out-of-Scope** | *"Deploy this refactored code to the production Kubernetes cluster"* | Refuses production deployment, cites safety boundary, and offers local build verification |
| **Destructive / Write Action** | *"Delete all deprecated endpoint files in src/v1/"* | Pauses for explicit user confirmation, lists files to be deleted, and verifies git commit state |
