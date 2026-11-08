# Claude Code Plugins: Architecture, Marketplaces, Installation, Evals, Cost Estimation, and Quality Linter

A comprehensive guide for authoring, evaluating, optimizing, distributing, and installing Claude Code plugins. Grounded in the official Anthropic Claude Code specifications: plugin creation, component schemas, marketplace file structures, installation filesystem placement, dependency resolution, evaluation harnesses, cost telemetry, and quality linting.

**Official documentation:** [Plugins overview](https://code.claude.com/docs/en/plugins) (Claude Code docs, verified 8 November 2026).

## Contents

- [Plugin Architecture and Mental Model](#plugin-architecture-and-mental-model)
- [Component Reference and File Layout](#component-reference-and-file-layout)
- [Marketplace Architecture and File/Folder Structure](#marketplace-architecture-and-filefolder-structure)
- [Installing Plugins and Filesystem Placement](#installing-plugins-and-filesystem-placement)
- [Anthropic Marketplaces: Official and Community](#anthropic-marketplaces-official-and-community)
- [Building and Designing Plugins: Step-by-Step Guide](#building-and-designing-plugins-step-by-step-guide)
- [Dependencies and Version Constraints](#dependencies-and-version-constraints)
- [Measuring Token Cost and Context Window Usage](#measuring-token-cost-and-context-window-usage)
- [Testing Plugins with Evals (`claude plugin eval`)](#testing-plugins-with-evals-claude-plugin-eval)
- [Plugin Linter Quality Catalog](#plugin-linter-quality-catalog)
- [Publishing and Distribution](#publishing-and-distribution)
- [Troubleshooting and Diagnostic Recipes](#troubleshooting-and-diagnostic-recipes)

---

## Plugin Architecture and Mental Model

A Claude Code plugin is a self-contained directory containing skills, commands, subagents, lifecycle hooks, MCP servers, LSP servers, binaries, settings, themes, and evaluation test suites, coordinated by a `plugin.json` (or `.claude-plugin/plugin.json`) manifest.

```text
my-plugin/
├── plugin.json                 # Manifest: identity, version, config, dependencies
├── skills/                     # Domain procedures (skills/<name>/SKILL.md)
│   └── code-formatter/
│       └── SKILL.md
├── commands/                   # Prompt templates and slash commands (*.md)
│   └── format.md
├── agents/                     # Specialized subagents (*.md)
│   └── review-agent.md
├── hooks/                      # Lifecycle hooks (hooks.json)
│   └── hooks.json
├── .mcp.json                   # MCP servers (or manifest mcpServers key)
├── .lsp.json                   # LSP language servers (or manifest lspServers key)
├── bin/                        # Executables exported to session PATH
├── settings.json               # Default harness settings (permissions, allowedTools)
├── themes/                     # UI color themes and styling (*.json)
├── evals/                      # Test cases and graders (claude plugin eval)
│   └── format-ruby/
│       ├── prompt.md
│       └── graders/
│           └── skill-fired.md
└── references/                 # Progressive disclosure documentation
    └── architecture.md
```

### When to Package as a Plugin

Use this decision table when choosing how to package agent capabilities:

| Scenario | Recommended Packaging | Reason |
|---|---|---|
| Project-specific rules, scripts, or workflows for one repository | `.claude/` in repo root (`.claude/skills/`, `.claude/settings.json`) | Minimal setup; versioned with repository code. |
| Personal scratchpad commands or scripts for your local machine | `~/.claude/` in user home directory | Always loaded locally without project pollution. |
| Reusable toolset shared with teammates or multiple repositories | **Claude Code Plugin** (local directory or git repo) | Clean install/uninstall, versioned updates, isolated namespaces. |
| Distributed tool integrating third-party APIs, CLI binaries, or MCP tools | **Claude Code Plugin** (published to marketplace) | Automated user configuration dialogs, dependency resolution, telemetry tracking. |

### Progressive Disclosure and Token Economics

Every plugin loaded in Claude Code consumes tokens in two distinct tiers:

1. **Always-On Context (Startup Cost):** The plugin name, command names, and the `description` and `when_to_use` frontmatter of every skill and subagent load into Claude's system prompt at session start. This cost is paid on *every single turn* whether the plugin is used or not.
2. **On-Invoke Context (Activation Cost):** The `SKILL.md` body, subagent instructions, and referenced markdown files load only when Claude explicitly invokes that component.

Effective plugin design keeps the always-on footprint minimal (target: <150 tokens) while deferring detailed instructions, schema tables, and examples to on-invoke files.

---

## Component Reference and File Layout

Claude Code discovers components in standard directories or through manifest keys in `plugin.json`.

### 1. Plugin Manifest (`plugin.json`)

The manifest identifies the plugin, defines user configuration parameters, declares dependencies, and optionally configures custom paths. Place it at `<plugin-root>/plugin.json` or `<plugin-root>/.claude-plugin/plugin.json`.

```json
{
  "name": "developer-toolkit",
  "displayName": "Developer Toolkit",
  "version": "1.2.0",
  "description": "Code formatting, linting, and automated git workflow automation.",
  "author": {
    "name": "Engineering Team",
    "email": "dev@example.com"
  },
  "license": "MIT",
  "homepage": "https://github.com/example/developer-toolkit",
  "repository": "https://github.com/example/developer-toolkit",
  "keywords": ["formatting", "git", "linting"],
  "userConfig": {
    "githubToken": {
      "type": "string",
      "description": "Personal GitHub Access Token with repo scope",
      "required": true,
      "secret": true
    },
    "enableStrictLinting": {
      "type": "boolean",
      "description": "Enforce strict lint errors before commits",
      "default": true
    }
  },
  "dependencies": {
    "formatter@community-marketplace": "^2.0.0"
  }
}
```

### 2. Skills (`skills/<skill-name>/SKILL.md`)

Skills define complex procedural workflows following Anthropic's progressive disclosure standard.

- **Location:** `skills/<skill-name>/SKILL.md`
- **Frontmatter:** Requires `name` (kebab-case) and `description` (concise summary with "Use when..." triggering guidance).
- **Execution:** When invoked, Claude executes the body instructions. Reference files placed under `references/*.md` are read on demand.

```markdown
---
name: format-staged
description: Formats staged git files with prettier and biome. Use when preparing commits or formatting changed files.
allowed-tools: [Bash, Read, Write]
---

# Format Staged Files

Follow these steps to format staged files:

1. Identify staged files with `git diff --cached --name-only`.
2. Run appropriate formatter based on file extensions.
3. Stage formatted modifications with `git add <files>`.
```

### 3. Commands (`commands/<name>.md` or manifest `commands`)

Commands define prompt templates invoked as slash commands (`/name`) or triggered by users.

- **Location:** `commands/<command-name>.md`
- **Parameter Substitution:** Use `$1`, `$2`, or `$@` for user-supplied arguments.
- **Example (`commands/pr-summary.md`):**

```markdown
---
description: Generates a PR summary from git diff against base branch
allowed-tools: [Bash]
---

Run `git diff $1...HEAD` and summarize all changes into:
- Problem Description
- Key Architectural Changes
- Verification Checklist
```

### 4. Subagents (`agents/<name>.md`)

Subagents define isolated personas that execute delegated sub-tasks with specialized tool restrictions and custom models.

- **Location:** `agents/<agent-name>.md`
- **Frontmatter Fields:**
  - `name`: Subagent identifier.
  - `description`: What the agent does.
  - `when_to_use`: Trigger conditions for parent delegation.
  - `tools`: Whitelist of permitted tools (e.g., `[Read, Grep, Glob]`).
  - `model`: Model override (e.g., `claude-3-5-haiku` for fast read-only audits).

```markdown
---
name: security-scanner
description: Read-only security vulnerability and credential leak scanner.
when_to_use: Delegate to this agent when reviewing PR diffs or untrusted third-party code for security issues.
tools: [Read, Grep, Glob]
model: claude-3-5-haiku
---

You are a read-only security auditing subagent. Never write files or execute bash commands.
Analyze code for hardcoded secrets, injection vulnerabilities, and insecure dependencies.
```

### 5. Lifecycle Hooks (`hooks/hooks.json` or manifest `hooks`)

Hooks execute shell commands upon system events. Hooks run in the local harness environment, do not invoke LLM turns, and cost **0 context window tokens**.

- **Events:**
  - `SessionStart`: Fires once when Claude Code initializes a session.
  - `UserPromptSubmit`: Fires when user sends a prompt before model sees it.
  - `PreToolUse`: Intercepts tool calls before execution (allows or denies).
  - `PostToolUse`: Fires immediately after a tool returns output.
  - `SessionEnd`: Fires during session teardown.

```json
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": { "tool": "Bash" },
        "command": "python3 hooks/validate_bash.py",
        "description": "Pre-execution command safety check"
      }
    ],
    "PostToolUse": [
      {
        "matcher": { "tool": "WriteFile" },
        "command": "npm run lint:fix --silent || true",
        "description": "Auto-lint files modified by Claude"
      }
    ]
  }
}
```

### 6. MCP Servers (`.mcp.json` or manifest `mcpServers`)

Plugins can package Model Context Protocol (MCP) servers providing custom tools and resources.

- **Parameter Substitution:** `${config.<key>}` injects values from `userConfig`.
- **Environment:** Injects environment variables dynamically.

```json
{
  "mcpServers": {
    "database-inspector": {
      "command": "node",
      "args": ["${pluginDir}/dist/mcp-server.js"],
      "env": {
        "DB_CONNECTION": "${config.dbUrl}",
        "DEBUG": "false"
      }
    }
  }
}
```

### 7. LSP Servers (`.lsp.json` or manifest `lspServers`)

LSP servers give Claude precise code intelligence (type definitions, jump-to-symbol, diagnostics).

```json
{
  "lspServers": {
    "pyright": {
      "command": "pyright-langserver",
      "args": ["--stdio"],
      "filetypes": ["python"]
    }
  }
}
```

### 8. Executables (`bin/` or manifest `executables`)

Any script or binary placed in `bin/` (with executable permissions `chmod +x`) is automatically added to Claude's `$PATH` for the duration of the session.

---

## Marketplace Architecture and File/Folder Structure

A Claude Code marketplace is a git repository or hosted directory containing a catalog file that indexes plugins and tells Claude Code where to fetch each one. The marketplace catalog file is saved at:
- **Primary Standard Path:** `.claude-plugin/marketplace.json` (inside the `.claude-plugin/` directory)
- **Alternative Permitted Path:** `marketplace.json` (at the root of the marketplace repository)

### 1. Monorepo Marketplace Structure (Embedded Plugins)

In a monorepo marketplace, the marketplace repository directly hosts both the catalog manifest and the source code of all listed plugins:

```text
my-marketplace/                           # Root of the marketplace git repository
├── .claude-plugin/
│   └── marketplace.json                  # Main marketplace catalog manifest
├── plugins/                              # Directory containing individual plugin trees
│   ├── code-formatter/                   # Plugin 1
│   │   ├── .claude-plugin/
│   │   │   └── plugin.json               # Manifest for code-formatter
│   │   ├── skills/
│   │   │   └── format/
│   │   │       └── SKILL.md
│   │   └── hooks/
│   │       └── hooks.json
│   ├── git-tools/                        # Plugin 2
│   │   ├── plugin.json                   # Manifest for git-tools
│   │   ├── commands/
│   │   │   └── squash.md
│   │   └── bin/
│   │       └── git-tidy
│   └── db-inspector/                     # Plugin 3
│       ├── plugin.json
│       └── .mcp.json
├── README.md                             # Marketplace overview and install commands
└── LICENSE
```

### 2. Distributed / Pointer Marketplace Structure (External Repositories)

In a distributed marketplace, the repository serves strictly as a catalog pointing to independent repositories, GitHub releases, npm packages, or archive downloads:

```text
central-marketplace/                      # Catalog repository
├── .claude-plugin/
│   └── marketplace.json                  # Manifest indexing external sources
├── README.md                             # Catalog index and contributor guide
└── LICENSE
```

### 3. Manifest Schema: `marketplace.json`

The marketplace catalog file requires `name`, `owner`, and `plugins`.

```json
{
  "$schema": "https://code.claude.com/schemas/marketplace.json",
  "name": "enterprise-tools",
  "description": "Internal developer tooling and enterprise workflow plugins",
  "version": "1.0.0",
  "owner": {
    "name": "DevOps Tooling Team",
    "email": "tooling@example.com",
    "url": "https://tools.example.com"
  },
  "metadata": {
    "pluginRoot": "./plugins"
  },
  "allowCrossMarketplaceDependenciesOn": [
    "claude-plugins-official",
    "claude-community"
  ],
  "forceRemoveDeletedPlugins": true,
  "plugins": [
    {
      "name": "code-formatter",
      "description": "Prettier and Biome code formatting automation",
      "version": "1.2.0",
      "source": "./plugins/code-formatter",
      "category": "Development",
      "tags": ["formatting", "code-quality"]
    },
    {
      "name": "cloud-deployer",
      "description": "Automated staging and production Kubernetes deployment",
      "version": "2.0.1",
      "source": {
        "source": "github",
        "repo": "example-org/cloud-deployer-plugin",
        "ref": "v2.0.1",
        "sha": "a1b2c3d4e5f67890123456789abcdef012345678"
      }
    },
    {
      "name": "jira-integration",
      "description": "Jira ticket search and branch synchronization",
      "version": "1.0.4",
      "source": {
        "source": "git-subdir",
        "url": "https://github.com/example-org/shared-monorepo.git",
        "path": "tooling/plugins/jira",
        "ref": "main"
      }
    },
    {
      "name": "schema-validator",
      "description": "Protobuf and OpenAPI validation CLI",
      "version": "3.1.0",
      "source": {
        "source": "npm",
        "package": "@example-org/claude-plugin-schema-validator",
        "version": "^3.0.0"
      }
    },
    {
      "name": "legacy-sync",
      "description": "Legacy database schema synchronizer",
      "version": "0.9.2",
      "source": {
        "source": "archive",
        "url": "https://artifacts.example.com/plugins/legacy-sync-0.9.2.zip",
        "sha256": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
      }
    }
  ]
}
```

### 4. Plugin Source Types Reference

The `source` field in each plugin entry tells Claude Code where and how to fetch the plugin:

| Source Type | Value Format | Description & Mandatory Fields |
|---|---|---|
| **Relative Path** | String: `"./plugins/my-plugin"` | For monorepos. Path relative to marketplace root. Must start with `./` (or bare folder name if `metadata.pluginRoot` is set). |
| **`github`** | Object: `{ "source": "github", ... }` | GitHub repository. Requires `repo` (`owner/repo`). Optional `ref` (branch/tag) and 40-character `sha`. |
| **`url`** | Object: `{ "source": "url", ... }` | Any Git repository by HTTPS/SSH URL. Requires `url`. Optional `ref` and `sha`. |
| **`git-subdir`** | Object: `{ "source": "git-subdir", ... }` | Sparse checkout of a subdirectory in a git repository. Requires `url`, `path`, and `ref`. |
| **`npm`** | Object: `{ "source": "npm", ... }` | Node package registry. Requires `package` and `version` constraint. Unpacked without executing untrusted install scripts. |
| **`archive`** | Object: `{ "source": "archive", ... }` | Zip archive downloaded over HTTPS. Requires `url` and `sha256` integrity hash. |
| **`command`** | Object: `{ "source": "command", ... }` | Local CLI command execution that prints a path to a directory. Requires `command` and optional `timeout`. |

### 5. Marketplace Validation and Local Testing

Run `claude plugin validate` on the marketplace directory to verify JSON syntax, required fields, and relative plugin paths before publishing:

```bash
# Validate marketplace catalog and its embedded plugins
claude plugin validate ./my-marketplace

# Register local marketplace into your Claude Code settings
claude plugin marketplace add ./my-marketplace

# Verify registration
claude plugin marketplace list

# Test installing a plugin from the local marketplace
claude plugin install code-formatter@my-marketplace
```

---

## Installing Plugins and Filesystem Placement

Understanding where plugins live on disk and how install scopes operate is essential for debugging, team coordination, and system administration.

### 1. Installation Scopes and Configuration Files

When installing a plugin, Claude Code records its enabled state in one of three settings files:

| Scope | Flag | Recorded Configuration File | Scope Behavior & Precedence |
|---|---|---|---|
| **Local Scope** | `--scope local` | `<workspace-root>/.claude/settings.local.json` | **Highest precedence.** Enables plugin for the current user in this repository only. Kept private (gitignored). Overrides project and user settings. |
| **Project Scope** | `--scope project` | `<workspace-root>/.claude/settings.json` | **Shared with team.** Enables plugin for anyone working in this repository. Checked into version control. |
| **User Scope** | `--scope user` | `~/.claude/settings.json` | **Default scope.** Enables plugin across all repositories and sessions on the user's computer. |

*Precedence Order:* If a plugin is configured at multiple levels, **Local Scope overrides Project Scope**, which in turn **overrides User Scope**.

### 2. Filesystem Placement: Where Plugins Go on Disk

Claude Code maintains all downloaded plugins, marketplace clones, and runtime state under a central plugins directory:
- **Default Plugins Root:** `~/.claude/plugins/`
- **Custom Override:** Configure via the `CLAUDE_CODE_PLUGIN_CACHE_DIR` environment variable.

```text
~/.claude/plugins/                        # Central plugins root directory
├── cache/                                # Versioned unpacked plugin code (${CLAUDE_PLUGIN_ROOT})
│   ├── claude-plugins-official/          # Organized by marketplace name
│   │   └── commit-commands/
│   │       └── 1.4.0/                    # Pinned version directory
│   │           ├── plugin.json
│   │           └── commands/
│   └── enterprise-tools/
│       └── code-formatter/
│           └── 1.2.0/
│               ├── plugin.json
│               └── skills/
├── data/                                 # Persistent plugin runtime storage (${CLAUDE_PLUGIN_DATA})
│   ├── code-formatter/                   # Durable across updates; deleted only on full uninstall
│   │   ├── config.sqlite
│   │   └── cache.db
│   └── jira-integration/
├── marketplaces/                         # Clones and catalogs of registered marketplaces
│   ├── claude-plugins-official/          # Cloned git catalog
│   │   └── .claude-plugin/
│   │       └── marketplace.json
│   ├── claude-community/
│   └── enterprise-tools/
├── synced/                               # Plugins synced automatically from claude.ai account
├── .trash/                               # Staged deletions from account sync
├── installed_plugins.json                # Master index of installed plugins, versions, scopes, and paths
├── known_marketplaces.json               # Master index of registered marketplaces and fetch URLs
└── flagged-plugins.json                  # Records of uninstalled delisted/flagged plugins
```

### 3. Path Variables in Plugin Components

When plugin scripts, MCP configurations, or hooks reference files, use Claude Code's built-in path variables:

- `${CLAUDE_PLUGIN_ROOT}`: Resolves to the specific version directory in the cache (e.g. `~/.claude/plugins/cache/marketplace/plugin/1.2.0/`). Use this to reference packaged binaries, scripts, or config files. **Changes on every update.**
- `${CLAUDE_PLUGIN_DATA}`: Resolves to the persistent data directory (e.g. `~/.claude/plugins/data/plugin-id/`). Use this for databases, caches, logs, or state files that **must persist across version upgrades**.
- `${pluginDir}`: Alias for `${CLAUDE_PLUGIN_ROOT}` commonly used in `.mcp.json`.

### 4. Installation Commands Reference

Install plugins from your terminal or from within an active session:

```bash
# Install from a known marketplace (User scope default)
claude plugin install code-formatter@enterprise-tools

# Install explicitly to Project scope (commits entry to .claude/settings.json)
claude plugin install code-formatter@enterprise-tools --scope project

# Install explicitly to Local scope (records entry in .claude/settings.local.json)
claude plugin install code-formatter@enterprise-tools --scope local

# Add a marketplace and install a plugin in a single command
claude plugin install deploy-tool@my-market --marketplace https://github.com/my-org/marketplace.git

# List all installed plugins with status, version, and scope
claude plugin list

# Update a specific plugin or all plugins
claude plugin update code-formatter
claude plugin update

# Disable/enable without removing files
claude plugin disable code-formatter
claude plugin enable code-formatter

# Uninstall a plugin and clean up cache
claude plugin uninstall code-formatter@enterprise-tools

# In-session commands (type at Claude Code prompt):
# /plugin                                 (Opens interactive management and discovery UI)
# /plugin install <name>@<marketplace>
# /plugin marketplace add <owner>/<repo>
# /reload-plugins                         (Hot-reloads modified plugins without restarting)
```

---

## Anthropic Marketplaces: Official and Community

Anthropic maintains two public plugin marketplaces for Claude Code:

| Marketplace Property | Official Marketplace | Community Marketplace |
|---|---|---|
| **Marketplace Name** | `claude-plugins-official` | `claude-community` |
| **GitHub Repository** | [`anthropics/claude-plugins-official`](https://github.com/anthropics/claude-plugins-official) | [`anthropics/claude-plugins-community`](https://github.com/anthropics/claude-plugins-community) |
| **Catalog Contents** | Plugins maintained by Anthropic, major developer platform partners, and core LSP servers | Community-submitted and open-source third-party plugins |
| **Registration** | Registered automatically on first interactive run of Claude Code | Added manually: `/plugin marketplace add anthropics/claude-plugins-community` |
| **Install Syntax** | `/plugin install <name>@claude-plugins-official`<br>`claude plugin install <name>@claude-plugins-official` | `/plugin install <name>@claude-community`<br>`claude plugin install <name>@claude-community` |

### Deprecated `claude-code-plugins`

> [!WARNING]
> The older `claude-code-plugins` marketplace (hosted in `anthropics/claude-code`) is deprecated. All official plugins now live in `claude-plugins-official`.
> - The former `ralph-wiggum` plugin is now `ralph-loop` in `claude-plugins-official`.
> - The `claude-opus-4-5-migration` plugin is retired and should be uninstalled.

### Discovering Plugins

1. **Terminal Interactive UI:** Type `/plugin` in any interactive Claude Code session. The **Discover** tab allows keyword searching across all registered marketplaces.
2. **Web Browser:** Browse and inspect verified plugins at [Claude Marketplace](https://claude.com/marketplace/plugins).
3. **Repository Inspection:** Inspect `.claude-plugin/marketplace.json` directly on GitHub in `anthropics/claude-plugins-official` or `anthropics/claude-plugins-community`.

---

## Building and Designing Plugins: Step-by-Step Guide

Follow this end-to-end development methodology when designing new plugins.

### Architecture Decision Flowchart

```
                 [What capability are you building?]
                                  │
          ┌───────────────────────┼────────────────────────┐
          ▼                       ▼                        ▼
  [Procedural Guide]       [Tool/API Access]     [Policy / Automation]
          │                       │                        │
  Does it need multiple   Does an API or DB       Should it run without
  conversational steps?   require native calls?   asking the model?
    ├── Yes: SKILL                 │                       │
    └── No: COMMAND                ▼                       ▼
                              MCP SERVER                 HOOK
                                  │                        │
                                  └──────────┬─────────────┘
                                             ▼
                                  [Combine into PLUGIN]
```

### Step 1: Scaffolding the Plugin

Create a dedicated directory and run `claude plugin init` or assemble files manually:

```bash
# Interactive scaffolding
claude plugin init my-developer-tools

# Or manual scaffolding
mkdir -p my-developer-tools/.claude-plugin
cd my-developer-tools
```

Create `.claude-plugin/plugin.json`:

```json
{
  "name": "my-developer-tools",
  "displayName": "My Developer Tools",
  "version": "1.0.0",
  "description": "Essential development workflows and automated code formatters.",
  "author": { "name": "Team" },
  "license": "MIT"
}
```

### Step 2: Adding Components

1. **Add a Skill:** Create `skills/git-cleanup/SKILL.md`:
   ```markdown
   ---
   name: git-cleanup
   description: Cleans up merged and stale local git branches. Use when pruning local branches.
   allowed-tools: [Bash]
   ---

   # Git Branch Cleanup

   1. Refresh remote tracking branches: `git fetch -p`.
   2. Identify branches merged into default: `git branch --merged`.
   3. Delete merged local branches except `main` or `master`.
   ```

2. **Add a Command:** Create `commands/squash.md`:
   ```markdown
   ---
   description: Squash recent commits into a single clean commit
   allowed-tools: [Bash]
   ---

   Review git log for the last $1 commits, draft a concise combined commit message, and prompt for confirmation before rebasing.
   ```

3. **Add Hooks:** Create `hooks/hooks.json` to enforce quality checks before tool execution.

### Step 3: Local Testing and Debugging Without a Marketplace

Load the plugin directly from disk into an isolated session:

```bash
# Load from directory
claude --plugin-dir ./my-developer-tools

# Load multiple plugins
claude --plugin-dir ./plugin-a --plugin-dir ./plugin-b

# Load from a packaged archive
claude --plugin-dir ./dist/my-developer-tools.zip
```

During a running session, reload updated plugin files instantly without restarting:
```text
/reload-plugins
```

Verify component registration and syntax:
```bash
claude plugin validate ./my-developer-tools
```

### Step 4: Converting Existing `.claude/` Project Files

If your repository already has `.claude/` skills, subagents, and hooks:
1. Move `.claude/skills/` to `<plugin-root>/skills/`.
2. Move `.claude/agents/` to `<plugin-root>/agents/`.
3. Move `.claude/commands/` to `<plugin-root>/commands/`.
4. Copy `.claude/settings.json` to `<plugin-root>/settings.json`.
5. Create `<plugin-root>/plugin.json` naming the plugin.
6. Verify file resolution: `claude plugin validate <plugin-root>`.

---

## Dependencies and Version Constraints

Plugins can declare dependencies on other plugins (e.g., relying on an MCP server or utility skill from another package).

### Declaring Dependencies

In `plugin.json`:

```json
{
  "name": "fullstack-suite",
  "version": "1.0.0",
  "dependencies": {
    "database-tools@engineering-catalog": "^2.1.0",
    "git-flow@community": "~1.0.0",
    "legacy-helper@internal": ">=0.8.0 <1.0.0"
  }
}
```

### Version Constraint Rules

| Specifier | Behavior | Example Range for `1.2.3` |
|---|---|---|
| `^1.2.3` | Compatible minor and patch updates (same major version). | `>=1.2.3 <2.0.0` |
| `~1.2.3` | Compatible patch updates only (same major and minor). | `>=1.2.3 <1.3.0` |
| `1.2.3` | Exact pinned release. | `1.2.3` |
| `>=1.0.0 <2.5.0` | Explicit bounded version window. | Range matching. |

### Dependency Resolution and Pruning

- Claude Code resolves dependencies when running `claude plugin install`.
- Diamond dependencies (Plugin A and Plugin B both depending on Plugin C) resolve to the highest version satisfying both constraints.
- Clean up unused or unreferenced dependencies with:
  ```bash
  claude plugin prune
  ```

---

## Measuring Token Cost and Context Window Usage

Every enabled plugin increases Claude Code's context consumption. Managing token overhead ensures users don't exhaust their context window prematurely.

### Running the Cost Estimator

Run `claude plugin details` in your shell (outside an active session) to profile a plugin's token overhead:

```bash
# Measure an installed plugin
claude plugin details my-developer-tools

# Measure a local development plugin
claude --plugin-dir ./my-developer-tools plugin details my-developer-tools
```

Sample output:

```text
my-developer-tools 1.0.0
  Description: Essential development workflows and automated code formatters
  Source: local (./my-developer-tools)

Component inventory
  Skills (2)      format-staged, git-cleanup
  Commands (1)    squash
  Agents (1)      security-scanner
  Hooks (2)       PreToolUse, PostToolUse  (harness-only — 0 context cost)
  MCP servers (0)

Projected token cost
  Always-on:   ~138 tok   added to every session

Per-component (rounded)
  component           always-on    on-invoke
  format-staged            ~38         ~240
  git-cleanup              ~42         ~310
  security-scanner         ~46         ~180
  squash                   ~12          ~65

  On-invoke cost is paid each time a skill or agent fires.
  Token counts are estimates based on standard tokenizer weights.
```

### Cost Categories Explained

1. **Always-On Cost:**
   - Composed of: plugin name, command names, skill/agent names, and `description`/`when_to_use` fields.
   - **Impact:** Loaded into system instructions on *every prompt turn*. A plugin with 500 always-on tokens burns 50,000 tokens across a 100-turn session.
   - **Target Budget:** Keep always-on cost under **150 tokens** total per plugin.

2. **On-Invoke Cost:**
   - Composed of: full markdown body of the skill/agent, plus allowed-tool declarations and execution rules.
   - **Impact:** Loaded only when triggered. Does not penalize inactive sessions.

3. **Hooks Cost:**
   - Always **0 tokens** in model context. Hooks are intercepted by the Claude Code runtime shell.

4. **MCP Tools Cost:**
   - MCP tools declare JSON schemas. Tool schemas resolve dynamically at session boot. Use `/context` inside a session to inspect runtime MCP token allocation.

### Optimization Playbook: Minimizing Token Footprint

- **Prune Verbose Descriptions:** Skill descriptions should focus strictly on intent and triggering conditions. Cut historical background and explanatory fluff:
  - *Bad (~65 tokens):* `This skill assists the software engineer by inspecting git branches that are currently stale or already merged upstream, ensuring the workspace remains orderly and free of clutter.`
  - *Good (~18 tokens):* `Cleans up merged and stale local git branches. Use when pruning branches.`
- **Move Heavy Reference Data to `references/`:** Large tables, JSON examples, and syntax specifications belong in on-demand reference files, not the top-level `SKILL.md` body.
- **Split Monolithic Plugins:** Rather than shipping a 20-skill monolith, split components into domain plugins (e.g., `cloud-aws`, `cloud-gcp`) so users install only what they require.

### Usage Monitoring and Fleet Telemetry

Administrators and authors can track plugin adoption:

- **Local Session Commands:**
  - `/plugin`: Displays loaded plugins and highlights plugins "Not used recently".
  - `/doctor`: Flags unreferenced or unused plugins consuming context.
  - `/usage`: Displays token breakdown per plugin.
- **OpenTelemetry Fleet Events:**
  - `claude_code.plugin_installed`: Emitted when a user installs a plugin.
  - `claude_code.plugin_loaded`: Emitted at session startup for each enabled plugin.
  - `claude_code.skill_activated`: Emitted when an agent invokes a plugin skill.
  - `claude_code.hook_plugin_metrics`: Execution statistics for plugin hooks.
- **Privacy and Redaction:** By default, third-party plugin names appear as `third-party` in telemetry. To expose exact plugin names for internal organizational plugins, configure the environment variable:
  ```bash
  OTEL_LOG_TOOL_DETAILS=1
  ```
- **Enterprise Analytics API:** Enterprise plan organizations can query:
  ```http
  GET /v1/organizations/analytics/plugins
  ```
  Returns daily installation, active session count, and invocation frequencies.

---

## Testing Plugins with Evals (`claude plugin eval`)

The `claude plugin eval` framework provides empirical, automated evaluation of plugin performance, trigger accuracy, and execution fidelity.

### Eval Directory Structure

Test cases live under `evals/<case-name>/`:

```text
evals/
├── format-ruby/
│   ├── prompt.md              # Frontmatter: run limits & tools; Body: realistic user prompt
│   ├── case.yaml              # Optional: advanced execution environments & fixtures
│   ├── graders/               # Pass/fail verification checks
│   │   ├── skill-fired.md     # Asserts the skill was triggered
│   │   └── criteria.md        # LLM judge rubric
│   └── fixtures/              # Workspace files seeded before the run
└── mocks/                     # Suite-wide MCP tool mocks
    └── github/
        ├── get_issue.md
        └── _tools.json
```

### Initializing Eval Suites

Generate test cases interactively or scaffold bare templates:

```bash
# Interactive case generation (Claude interviews you and builds test cases)
claude plugin eval init

# Scaffold a blank test case
claude plugin eval init --bare format-ruby
```

### Writing a Test Case (`prompt.md`)

Write realistic user requests rather than synthetic instructions that name the skill explicitly:

```markdown
---
name: format-ruby
description: Verifies ruby formatting skill triggers on syntax cleanup request
max_turns: 6
timeout_seconds: 120
allowed_tools: [Bash, Read, Write, Skill]
tags: [formatting, ruby]
---

Please clean up the formatting and indentation on app/models/user.rb.
```

### Grader Types and Verification Criteria

Each grader in `graders/<name>.md` evaluates output quality.

| Grader Type | Purpose | Configuration Options |
|---|---|---|
| `tool_used` | Asserts a specific tool was invoked. | `tool`: Tool name (e.g. `Skill`, `Bash`).<br>`input_match`: Regex matching tool arguments.<br>`min`: Minimum calls (default 1).<br>`max`: Maximum calls (use `min: 0, max: 0` to assert tool was never called). |
| `regex` | Asserts output or trace matches a pattern. | `pattern`: JavaScript regex pattern.<br>`flags`: Regex flags (e.g. `i`).<br>`target`: `last_message`, `trace`, or `files`.<br>`match`: `contains`, `not_contains`, or `"count:N"`. |
| `tool_order` | Asserts tool invocation sequencing. | `before`: Tool name or `{ tool, input_match }`.<br>`after`: Tool name or `{ tool, input_match }`. |
| `file_exists` | Asserts filesystem output artifacts. | `path`: File glob pattern.<br>`exists`: `true` or `false`. |
| `llm` | Rubric judged by a secondary model. | `criteria`: Markdown rubric with PASS and FAIL conditions.<br>`focus`: Target inspected (`last_message`, `trace`, or `{ source: file, path }`). |
| `baseline` | Regression check against transcript. | `baseline_file`: Path to reference `.jsonl` transcript.<br>`criteria`: Comparison criteria. |

#### Example: Tool Use Grader (`graders/skill-fired.md`)

```markdown
---
type: tool_used
tool: Skill
input_match: '"skill"\s*:\s*"(?:[\w-]+:)?format-ruby"'
---
```

#### Example: LLM Judge Grader (`graders/criteria.md`)

```markdown
---
type: llm
weight: 2
---

PASS if the final response confirms indentation was normalized to 2 spaces and no syntax errors were introduced.
FAIL if the assistant refused the request, recommended installing external gems manually, or altered business logic.
```

#### Example: Negative Assert Grader (`graders/no-destructive-bash.md`)

```markdown
---
type: tool_used
tool: Bash
input_match: 'rm\s+-rf'
min: 0
max: 0
---
```

### Baseline Ablation Scoring (`WITH`, `W/OUT`, and $\Delta$)

When you execute `claude plugin eval .`, each test case runs 3 times with the plugin loaded (`WITH`), and 3 times without the plugin (`W/OUT`).

$$\Delta = \text{Score}_{\text{WITH}} - \text{Score}_{\text{W/OUT}}$$

```text
CASE          WITH    W/OUT   Δ        RUNS  COST    NOTES
format-ruby   1.00    0.20    +0.80    6     $0.38   All graders passed
lint-staged   0.90    0.10    +0.80    6     $0.42   Minor whitespace difference

2 case(s) · mean Δ +0.80 · 82s · $0.80
Report: /Users/you/my-plugin/evals/results/2026-11-08T12-00-00Z/report.html
```

- **$\Delta > 0.0$:** Demonstrates the plugin provided measurable capability uplift.
- **$\Delta \approx 0.0$:** Indicates Claude can perform the task equally well without the plugin (or the skill failed to trigger). Review the skill's `description` trigger keywords.

### Mocking External MCP Servers

To keep evals deterministic, fast, and hermetic, mock external MCP tools under `evals/mocks/<server-name>/`:

#### Fixed Mocks (`mocks/github/get_issue.md`)

Returns a canned response with dynamic field substitutions:

```markdown
---
type: fixed
expect:
  issue_number: number
---

{
  "id": {{input.issue_number}},
  "title": "Fix memory leak in background worker",
  "state": "open",
  "author": "octocat"
}
```

#### Agent Mocks (`mocks/github/_server.md`)

Emulates dynamic server interactions using a lightweight judge model:

```markdown
---
type: agent
tools: [create_issue, update_issue, close_issue]
abort_when: "The user attempts to delete repository settings"
---

Simulate an issue tracker API. Store newly created issues in working memory and return realistic incremented issue IDs.
```

### Running Evals and CI Gating

Run evals during local development or in GitHub Actions:

```bash
# Run entire eval suite
claude plugin eval .

# Run a specific case with 1 run and no baseline ablation (fast mode)
claude plugin eval . --case format-ruby --runs 1 --ablation none

# Enforce a strict passing threshold in CI
claude plugin eval . --threshold 0.95 --max-cost-usd 2.50 --trust-plugin
```

CI Workflow Example (`.github/workflows/eval.yml`):

```yaml
name: Plugin Evals
on: [pull_request]
jobs:
  eval:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Install Claude Code
        run: npm install -g @anthropic-ai/claude-code
      - name: Run Plugin Evals
        env:
          ANTHROPIC_API_KEY: ${{ secrets.ANTHROPIC_API_KEY }}
        run: |
          claude plugin eval . --threshold 1.0 --max-cost-usd 3.00 --trust-plugin
```

---

## Plugin Linter Quality Catalog

When authoring or auditing Claude Code plugins, evaluate against these structured linter checks across 5 core quality domains:

| Check ID | Severity | Name | Description & Passing Rule |
|---|---|---|---|
| **PL-MN-01** | Error | Manifest File Location | `plugin.json` exists at root or `.claude-plugin/plugin.json` and parses as valid JSON. |
| **PL-MN-02** | Error | Identity and Naming | `name` is lowercase kebab-case (`^[a-z0-9-]+$`) and at most 64 characters. |
| **PL-MN-03** | Warning | Semantic Versioning | `version` follows strict semver (`MAJOR.MINOR.PATCH`). |
| **PL-MN-04** | Warning | Description Quality | `description` is concise (<160 characters), free of promotional filler, and explains core utility. |
| **PL-MN-05** | Error | User Config Schema | Any `userConfig` entry declares valid `type` (`string`, `number`, `boolean`), description, and flags. |
| **PL-CO-01** | Warning | Always-On Token Cap | Total always-on context overhead across all components is under **200 tokens** (ideal: <150 tokens). |
| **PL-CO-02** | Warning | Progressive Disclosure | On-invoke bodies avoid inlining extensive reference docs; complex tables reside in `references/*.md`. |
| **PL-CO-03** | Error | Hook Filter Specificity | Hooks declare specific `matcher` conditions; avoid unconditional intercepts that block legitimate tools. |
| **PL-CO-04** | Error | Secret Safety | MCP server definitions use `${config.<key>}` or environment variables; never hardcode API keys or secrets. |
| **PL-DP-01** | Warning | Bounded Dependencies | Dependencies declare explicit semver ranges (`^` or `~`); avoid unpinned or unbounded wildcards. |
| **PL-DP-02** | Error | No Dependency Cycles | Plugin dependencies form an acyclic directed graph with no circular references. |
| **PL-DP-03** | Warning | Portable Executables | Scripts in `bin/` use portable POSIX shell shebangs (`#!/usr/bin/env bash`) and forward slashes. |
| **PL-EV-01** | Warning | Minimum Eval Suite | Plugin contains an `evals/` directory with at least **3 distinct evaluation cases**. |
| **PL-EV-02** | Warning | Baseline Uplift ($\Delta$) | Eval cases demonstrate positive baseline contribution ($\Delta > 0.0$ across test runs). |
| **PL-EV-03** | Warning | Negative Control Cases | Eval suite includes at least one case verifying the plugin does *not* trigger on unrelated tasks. |
| **PL-EV-04** | Warning | Hermetic MCP Mocks | Any external MCP server dependencies are mocked under `evals/mocks/` with `expect` input guards. |
| **PL-PB-01** | Warning | Manifest Validation | `claude plugin validate .` passes cleanly with zero validation errors. |
| **PL-PB-02** | Warning | Pre-Release Git Tag | Repository contains a git tag matching the manifest version (`v<version>`). |
| **PL-PB-03** | Info | Documentation Coverage | Includes `README.md` with usage instructions, supported commands, prerequisites, and license. |

---

## Publishing and Distribution

Claude Code supports three distribution avenues: direct distribution, custom private marketplaces, and official Anthropic directories.

### Distribution Routes Compared

| Method | Who Can Install | Update Mechanism | Best For |
|---|---|---|---|
| **Direct Directory / Zip** | Anyone with file/repo access | Manual re-download or git pull | Early prototyping, local experimentation. |
| **Custom Marketplace** | Team / Organization | `claude plugin update <name>` | Private enterprise tooling, team repositories. |
| **Official Directory** | All Claude Code users globally | Automated update prompts | Public open-source developer tools. |

### Pre-Release Quality Checklist

Before sharing or releasing a plugin, verify every item:

- [ ] 1. Run `claude plugin validate .` to confirm schema compliance.
- [ ] 2. Run `claude plugin details <name>` to verify always-on token cost is within budget (<150 tokens).
- [ ] 3. Run `claude plugin eval .` to verify all test cases pass with positive baseline delta ($\Delta > 0$).
- [ ] 4. Verify all shell paths use forward slashes (`/`), compatible with macOS, Linux, and WSL.
- [ ] 5. Confirm no personal secrets, tokens, or hardcoded absolute paths exist in code or manifests.
- [ ] 6. Tag the release in git: `git tag v1.0.0 && git push --tags`.

### Publishing Through a Custom Marketplace

1. Create a `marketplace.json` catalog repository (under `.claude-plugin/marketplace.json`):
   ```json
   {
     "name": "internal-tools",
     "description": "Internal engineering utilities and workflow plugins",
     "owner": { "name": "Tooling Team" },
     "plugins": [
       {
         "name": "developer-toolkit",
         "description": "Code formatting and automated git workflows",
         "version": "1.2.0",
         "source": {
           "type": "git",
           "url": "https://github.com/my-org/developer-toolkit.git"
         }
       }
     ]
   }
   ```
2. Users add the marketplace catalog:
   ```bash
   claude plugin marketplace add my-org/internal-tools
   ```
3. Users install the plugin by name:
   ```bash
   claude plugin install developer-toolkit@internal-tools
   ```

---

## Troubleshooting and Diagnostic Recipes

### 1. Skill Fails to Trigger on Natural Prompts
- **Diagnosis:** Run `claude plugin eval . --case <case-name>` and inspect the `tool_used: Skill` grader. If failing with $\Delta \approx 0$, Claude's semantic routing is not recognizing the prompt as matching the skill.
- **Fix:** Update the skill's `description` frontmatter in `SKILL.md`. Include concrete user action phrases (e.g., "Use when formatting staged code or fixing linter errors before commit").

### 2. High Always-On Token Consumption Warning
- **Diagnosis:** `claude plugin details` reports always-on tokens exceeding 250 tokens.
- **Fix:** Inspect the Per-component table. Shorten the `description` and `when_to_use` fields for the highest-scoring component. Move detailed parameter tables into `references/`.

### 3. Eval Run Fails with "is not a trusted plugin directory"
- **Diagnosis:** Running in headless CI without user interaction.
- **Fix:** Pass `--trust-plugin` flag to bypass the interactive trust prompt:
  ```bash
  claude plugin eval . --trust-plugin
  ```

### 4. Hook Commands Failing Silently
- **Diagnosis:** Tools are blocked or behave unexpectedly without error output.
- **Fix:** Start Claude Code in debug mode to trace hook lifecycle events:
  ```bash
  claude --debug
  ```

### 5. Plugin Enabled in Project Settings but Not Found on Collaborator Machine
- **Diagnosis:** Project `.claude/settings.json` has `enabledPlugins: { "tool@market": true }`, but collaborator has not downloaded it.
- **Fix:** The collaborator runs:
  ```bash
  claude plugin install tool@market --scope project
  ```
