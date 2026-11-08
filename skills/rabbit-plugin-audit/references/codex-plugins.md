# OpenAI Codex Plugins: Architecture, Manifest Schemas, MCP Integration, and Harness Placement

A reference guide for authoring, packaging, configuring, and distributing plugins for OpenAI Codex and ChatGPT. Grounded in the official OpenAI Developer documentation: portable Agent Plugins specifications, OpenAI extensions, MCP server configuration, and Codex harness file structures.

## Contents

- [Codex Plugin Architecture and Portable Specification](#codex-plugin-architecture-and-portable-specification)
- [Directory Layout and File Structure](#directory-layout-and-file-structure)
- [Manifest Schema: Root `plugin.json` and OpenAI Extensions](#manifest-schema-root-pluginjson-and-openai-extensions)
- [Bundled MCP Servers and Authentication (`mcp.json`)](#bundled-mcp-servers-and-authentication-mcpjson)
- [Filesystem Placement: Where Plugins Go on Disk](#filesystem-placement-where-plugins-go-on-disk)
- [Settings and Configuration (`.codex/config.toml`)](#settings-and-configuration-codexconfigtoml)
- [Marketplaces and Distribution](#marketplaces-and-distribution)
- [Authoring Workflow and `@plugin-creator`](#authoring-workflow-and-plugin-creator)
- [Plugin Planning and the Codex Use Case Checker](#plugin-planning-and-the-codex-use-case-checker)
- [Comparison: Generic Shared Plugins vs Harness-Specific Implementations](#comparison-generic-shared-plugins-vs-harness-specific-implementations)

---

## Codex Plugin Architecture and Portable Specification

OpenAI Codex and ChatGPT adopt the **portable Agent Plugins specification** (`agent-plugins.org`), combining skills, Model Context Protocol (MCP) servers, UI assets, and desktop lifecycle hooks into a single distributable bundle.

### Core Architecture Principles

1. **Portable Core with Vendor Extensions:** Standard metadata (`name`, `version`, `description`, `skills`, `license`) resides at the root of `plugin.json`. OpenAI and Codex specific presentation, app bindings, and onboarding skills are isolated under the `extensions.com.openai` namespace.
2. **Standardized Component Paths:** Portable components reside in fixed root locations:
   - Skills live in `skills/<skill-name>/SKILL.md`.
   - MCP servers are declared in `mcp.json`.
   - Brand and composer visual assets live in `assets/`.
3. **Dual Manifest Support:**
   - **Modern Portable Standard (Recommended):** Root `plugin.json` + `mcp.json` + inline `extensions.com.openai`.
   - **Codex Compatibility Overlay (Legacy):** `.codex-plugin/plugin.json` with `.mcp.json` and `.app.json`.

---

## Directory Layout and File Structure

### 1. Modern Portable Plugin Layout (Recommended)

```text
my-codex-plugin/
├── plugin.json                 # Portable manifest with extensions.com.openai
├── mcp.json                    # Portable MCP server declarations (agent-plugins schema)
├── skills/                     # Domain workflows and procedures
│   ├── refactor/
│   │   ├── SKILL.md
│   │   └── references/
│   │       └── guidelines.md
│   └── setup/
│       └── SKILL.md            # Onboarding skill
├── hooks/                      # Desktop lifecycle hooks (Codex desktop only)
│   └── hooks.json
├── assets/                     # UI visual assets
│   ├── icon.png                # Composer icon (square, SVG or PNG)
│   └── logo.png                # Marketplace logo
├── .app.json                   # ChatGPT interactive apps / widgets mapping
├── README.md
└── LICENSE
```

### 2. Codex Compatibility Overlay Layout (Legacy)

```text
my-codex-plugin/
├── .codex-plugin/
│   └── plugin.json             # Codex-specific overlay manifest
├── .mcp.json                   # Legacy MCP server configuration
├── .app.json                   # Legacy app mapping
├── skills/
│   └── refactor/
│       └── SKILL.md
└── assets/
```

---

## Manifest Schema: Root `plugin.json` and OpenAI Extensions

The portable manifest identifies the plugin using the `https://agent-plugins.org/schemas/1.0.0/plugin.schema.json` schema.

```json
{
  "$schema": "https://agent-plugins.org/schemas/1.0.0/plugin.schema.json",
  "name": "code-intelligence",
  "version": "1.0.0",
  "description": "Automated code refactoring, AST analysis, and repository health audits.",
  "author": {
    "name": "Engineering Tooling",
    "email": "tooling@example.com",
    "url": "https://tools.example.com"
  },
  "homepage": "https://tools.example.com/plugins/code-intelligence",
  "repository": "https://github.com/example/code-intelligence-plugin",
  "license": "MIT",
  "keywords": ["refactoring", "ast", "code-quality", "codex"],
  "extensions": {
    "com.openai": {
      "onboardingSkill": "./skills/setup/SKILL.md",
      "apps": "./.app.json",
      "hooks": "./hooks/hooks.json",
      "interface": {
        "displayName": "Code Intelligence Studio",
        "shortDescription": "Automated code refactoring and AST analysis",
        "longDescription": "Deep static code analysis and automated refactoring workflows tailored for Codex and ChatGPT.",
        "developerName": "Engineering Tooling",
        "category": "Development",
        "capabilities": ["Read", "Write", "Execute"],
        "websiteURL": "https://tools.example.com",
        "privacyPolicyURL": "https://tools.example.com/privacy",
        "termsOfServiceURL": "https://tools.example.com/terms",
        "defaultPrompt": [
          "Refactor this module according to repo conventions",
          "Analyze test coverage gaps in src/api"
        ],
        "brandColor": "#10A37F",
        "composerIcon": "./assets/icon.png",
        "logo": "./assets/logo.png"
      }
    }
  }
}
```

### OpenAI Extension Fields (`extensions.com.openai`)

| Field | Type | Description |
|---|---|---|
| `onboardingSkill` | string | Relative path to a `SKILL.md` run automatically when the user first activates the plugin. |
| `apps` | string | Relative path to `.app.json` for ChatGPT interactive app widgets. |
| `hooks` | string | Relative path to `hooks/hooks.json` (supported in Codex desktop local installs). |
| `interface.displayName` | string | Human-readable title displayed in the Codex and ChatGPT plugin directories. |
| `interface.shortDescription`| string | One-line summary (<120 characters) for cards and lists. |
| `interface.brandColor` | string | Hex color code (e.g. `#10A37F`) for UI highlights. |
| `interface.composerIcon` | string | Relative path to square icon shown in the prompt composer. |
| `interface.logo` | string | Relative path to marketplace catalog badge. |
| `interface.defaultPrompt` | array | Suggested starter prompts shown to users. |

---

## Bundled MCP Servers and Authentication (`mcp.json`)

Configure portable MCP servers in root `mcp.json` using the Agent Plugins MCP schema (`https://agent-plugins.org/schemas/1.0.0/mcp.schema.json`).

### 1. Remote HTTP Server (`streamable-http`)

```json
{
  "$schema": "https://agent-plugins.org/schemas/1.0.0/mcp.schema.json",
  "mcpServers": {
    "repository-analyzer": {
      "type": "streamable-http",
      "url": "https://mcp.example.com/api",
      "extensions": {
        "com.openai": {
          "auth": {
            "type": "oauth",
            "client": {
              "mode": "provided",
              "clientId": "client_123456789",
              "authorizationEndpoint": "https://auth.example.com/oauth/authorize",
              "tokenEndpoint": "https://auth.example.com/oauth/token"
            }
          }
        }
      }
    }
  }
}
```

### 2. Local Stdio Server (`stdio`)

```json
{
  "$schema": "https://agent-plugins.org/schemas/1.0.0/mcp.schema.json",
  "mcpServers": {
    "local-linter": {
      "type": "stdio",
      "command": "node",
      "args": ["${pluginDir}/dist/server.js"],
      "env": {
        "NODE_ENV": "production"
      }
    }
  }
}
```

### Authentication Types in `extensions["com.openai"].auth`

| Auth Method | Configuration | Usage Scenario |
|---|---|---|
| No Auth | `type: "none"` | Public endpoints and read-only local servers. |
| OAuth Provided | `type: "oauth"`, `client.mode: "provided"` | Enterprise servers with pre-registered OAuth applications. |
| OAuth Dynamic | `type: "oauth"`, `client.mode: "dynamic"` | Automatic client registration via RFC 7591. |
| API Key | `type: "api_key"` | Header-based key authentication (`Authorization: Bearer <key>`). |
| Mixed | `type: "mixed"` | Endpoints supporting both public discovery and authenticated actions. |

---

## Filesystem Placement: Where Plugins Go on Disk

Codex and ChatGPT resolve plugins across user, repository, and system scopes:

| Scope | Path on Disk | Purpose |
|---|---|---|
| **Local / Project Scope** | `<repo-root>/.codex/plugins/<plugin-name>/`<br>*(or `<repo-root>/.agents/plugins/<plugin-name>/`)* | Version-controlled or private plugins dedicated to one codebase. |
| **User / Personal Scope** | `~/.codex/plugins/<plugin-name>/`<br>*(or `~/.agents/plugins/<plugin-name>/`)* | Developer's global plugins available across all repositories. |
| **System / Machine Scope** | `/etc/codex/plugins/<plugin-name>/` | Pre-installed system plugins on multi-user workstations or CI containers. |
| **Cache Root** | `~/.codex/cache/plugins/` | Downloaded remote plugins and marketplace caches. |

---

## Settings and Configuration (`.codex/config.toml`)

Codex controls plugin loading, permissions, and tool whitelists through TOML configuration:

- **Project Config:** `<repo-root>/.codex/config.toml`
- **User Config:** `~/.codex/config.toml`

```toml
# Indexing budget for startup discovery
[plugins]
max_context_tokens = 5000

# Enable/disable specific plugins
[[plugins.config]]
name = "code-intelligence"
enabled = true

[[plugins.config]]
path = "/path/to/experimental-plugin"
enabled = false

# Whitelist allowed tools for a plugin
[plugins.permissions.code-intelligence]
allowed_tools = ["read_file", "edit_file", "run_command"]

# Register a custom local or team marketplace
[[plugins.marketplaces]]
name = "internal-marketplace"
source = "https://github.com/example-org/codex-plugins-marketplace.git"
```

---

## Marketplaces and Distribution

Codex plugins can be shared via:
1. **Universal Plugin Directory:** The shared, public directory accessible to both ChatGPT and Codex desktop users. Published via the OpenAI Developer submission portal.
2. **Local and Repository Marketplaces:** Defined in `.codex-plugin/marketplace.json` or `.agents/marketplace.json`.

### Marketplace Manifest (`marketplace.json`)

```json
{
  "name": "internal-codex-catalog",
  "description": "Internal engineering plugins for Codex and ChatGPT",
  "owner": { "name": "Tooling Team" },
  "plugins": [
    {
      "name": "code-intelligence",
      "description": "Automated code refactoring and AST analysis",
      "version": "1.0.0",
      "source": {
        "type": "git",
        "url": "https://github.com/example-org/code-intelligence.git"
      }
    }
  ]
}
```

---

## Authoring Workflow and `@plugin-creator`

Codex provides a built-in interactive skill for authoring plugins:

### Using `@plugin-creator`

1. Open a conversation in ChatGPT or the Codex CLI.
2. Invoke the creator skill:
   ```text
   @plugin-creator scaffold a code review plugin with an MCP server and refactoring skill
   ```
3. `@plugin-creator` asks required intake questions, creates the compatibility manifest `.codex-plugin/plugin.json`, scaffolds `skills/` and `.mcp.json`, and links it to a local test marketplace.

### Invoking Plugin Capabilities

Users trigger installed Codex plugin skills via:
- **Explicit Symbol Prefix:** `$refactor src/main.py` (Codex CLI / IDE) or `@refactor` (ChatGPT).
- **Slash Commands:** `/skills` opens the interactive skill picker.
- **Implicit Routing:** When a user prompt matches a skill's `name` and `description`, Codex loads `SKILL.md` automatically via function calling.

---

## Plugin Planning and the Codex Use Case Checker

Before authoring code or generating manifests, OpenAI's development guidelines specify running a comprehensive use-case brainstorm and coverage check ([Brainstorm plugin use cases](https://developers.openai.com/plugins/plan/use-case) and [Build skills](https://developers.openai.com/plugins/build/skills)).

### 1. User Expectations and Request Brainstorming

The plugin name, short description, listing copy, and starter prompts create immediate user expectations. A developer should never have to read documentation to guess what a plugin does.

Capture likely requests from:
- Existing workflows and tools developers already use daily.
- Search terms, feature requests, and support issues.
- Workarounds involving manual data copy-pasting between terminals, logs, and browser dashboards.
- Direct prompts naming the plugin/skill (`$lint-staged`, `@database-tools`).
- Indirect prompts expressing goals (*"Find which query is causing the spike in latency"*, *"Format changed files"*).

### 2. The Use-Case Inventory

For each target workflow, record the 7 foundational fields:

| Field | Purpose | Codex & ChatGPT Context |
|---|---|---|
| **User goal** | Concrete outcome the user seeks | Identify and fix broken unit test imports |
| **Example requests** | Direct & indirect prompt variations | Direct: `$fix-imports`<br>Indirect: *"Resolve broken module import paths"* |
| **Expected result** | Definition of successful completion | Modified files saved cleanly, tests re-run and passing |
| **Required context** | State, accounts, or file permissions | File tree access, language server or package manager |
| **Plugin capability** | Architecture component needed | Skill (`SKILL.md` + AST resolver script) |
| **Safety boundary** | Side effects, file mutations, risk | File edits. Requires git status check to avoid overwriting uncommitted work. |
| **Support decision** | Scope determination | Supported in initial v1 release |

### 3. Coverage Checking and Gap Analysis

Review the proposed capabilities against user expectations:
- **End-to-End Integrity:** Verify a continuous, automated path from user prompt to final output without awkward human handoffs.
- **Goal-Oriented Tooling:** Eliminate tools that expose raw technical mechanics without accomplishing an identifiable user goal.
- **Authorization & Confirmations:** Require user confirmation before executing state-altering actions, destructive filesystem operations, or billable API calls.
- **Refusal Guidance:** Ensure the plugin clearly explains what it cannot do and suggests safe alternatives.

### 4. Intentional Exclusions

Document deliberate reasons when excluding anticipated capabilities:
- Unacceptable safety or privacy risks (e.g., exposing credentials or production databases).
- Unreliable upstream APIs or inability to verify correctness locally.
- Unverified permissions.
- Out-of-scope for v1 release (with listing copy that explicitly sets that boundary).

### 5. Build Decision Matrix

Select the smallest implementation that solves the user's goal:
- **Build a Skill (`SKILL.md`):** For prompt instructions, reference documentation, and repeatable procedural patterns ([OpenAI Build Skills](https://developers.openai.com/plugins/build/skills)).
- **Build an MCP Server (`mcp.json`):** When the workflow requires live external data, authentication, private infrastructure tools, or remote actions.
- **Add UI (`.app.json`):** Only when structured visual interaction (interactive diffs, visual forms, graphical graphs) materially improves the workflow.

---

## Comparison: Generic Shared Plugins vs Harness-Specific Implementations

When authoring cross-harness plugins, separate shared components from harness-specific configurations:

| Component / Layer | Generic Shared Standard (Portable) | Claude Code Specifics (`claude`) | OpenAI Codex Specifics (`codex`) |
|---|---|---|---|
| **Root Manifest** | `plugin.json` (agent-plugins schema) | Accepts `.claude-plugin/plugin.json` or root `plugin.json` | Accepts `.codex-plugin/plugin.json` or root `plugin.json` with `extensions.com.openai` |
| **Skills Directory** | `skills/<name>/SKILL.md` (progressive disclosure) | Namespaced invocation `/plugin:skill`; frontmatter `allowed-tools` | Invoked via `$name` or `@name`; frontmatter `allowed-tools` |
| **MCP Definition** | `mcp.json` (`agent-plugins.org` schema) | `.mcp.json` or manifest `mcpServers`; parameters `${config.KEY}` | `mcp.json` with transport `type`; auth in `extensions["com.openai"].auth` |
| **Marketplace Catalog** | `marketplace.json` | `.claude-plugin/marketplace.json`; verified on `claude.com/marketplace` | `.codex-plugin/marketplace.json`; universal directory shared with ChatGPT |
| **Install Locations** | `<repo>/plugins/` or `~/.<agent>/plugins/` | Cache: `~/.claude/plugins/cache/<market>/<pkg>/<v>/`; Data: `~/.claude/plugins/data/` | Cache: `~/.codex/cache/plugins/`; Paths: `~/.codex/plugins/` or `.codex/plugins/` |
| **Configuration File** | None (standardized settings) | JSON: `~/.claude/settings.json`, `.claude/settings.local.json` | TOML: `~/.codex/config.toml`, `.codex/config.toml` |
| **Lifecycle Hooks** | `hooks/hooks.json` | Zero-token harness triggers on `SessionStart`, `PreToolUse`, `PostToolUse` | Supported on Codex desktop manual installs under `extensions.com.openai.hooks` |
| **Validation & Testing** | None | CLI: `claude plugin validate .`, `claude plugin eval .`, `claude plugin details` | Interactive: `@plugin-creator` built-in scaffolding and test harness |
