# Trae Harness Reference

Reference for skill discovery, directory layouts, configuration precedence, and agent integration in Trae and Trae CN.

## Contents

- [Identifier](#identifier)
- [Skill Paths](#skill-paths)
- [Settings & Configuration](#settings--configuration)
- [Discovery & Precedence](#discovery--precedence)
- [Feature Support](#feature-support)
- [Concrete Directory Layout](#concrete-directory-layout)
- [Concrete SKILL.md Example](#concrete-skillmd-example)
- [Invocation](#invocation)

---

## Identifier

- CLI flag / agent identifiers: `--agent trae`, `--agent trae-cn`
- Target platforms: Trae IDE, Trae CN (ByteDance)
- Documentation URL: https://docs.trae.ai/ide/skills

---

## Skill Paths

Trae discovers skills from workspace project directories and local user storage:

| Scope | Canonical Path | Recognized Alternatives / Ecosystem Paths |
|---|---|---|
| **Project (Workspace)** | `.trae/skills/<skill-name>/` | `.agents/skills/<skill-name>/` (Agent Skills standard) |
| **Global / User (Trae)** | `~/.trae/skills/<skill-name>/` (macOS/Linux)<br>`%userprofile%/.trae/skills/<skill-name>/` (Windows) | None |
| **Global / User (Trae CN)** | `~/.trae-cn/skills/<skill-name>/` (macOS/Linux)<br>`%userprofile%/.trae-cn/skills/<skill-name>/` (Windows) | None |

### Path Details

- **Directory Requirement**: Each skill must reside in its own subdirectory named after the skill, containing a required `SKILL.md` entrypoint.
- **Auxiliary Folders**: A skill directory may contain optional folders such as `examples/`, `templates/`, `resources/`, or `scripts/`.
- **Project Scope**: Stored in `.trae/skills/` (or `.agents/skills/`), committed to version control, and shared across workspace contributors.
- **Global Scope**: Stored in user home directories, persistent across all projects on the local machine.
- **Ecosystem Integration**: The `.agents/skills/` directory is supported for interoperability with open Agent Skills packages installed via the `skills` CLI (`find-skills`).

---

## Settings & Configuration

Trae organizes instructions, configuration parameters, and agent execution across specific workspace and application files:

| Scope | Path | Purpose |
|---|---|---|
| **Project Rules** | `.trae/project_rules.md` | Workspace prompt instructions loaded in full into agent context at session start. |
| **User Rules** | `.trae/user_rules.md` | User-defined prompt instructions applied across sessions. |
| **Workspace Settings** | `.trae/` | Workspace configurations, project rules, and project-specific skills. |
| **Application Settings (Trae)** | macOS: `~/Library/Application Support/Trae/User/settings.json`<br>Linux: `~/.config/Trae/User/settings.json`<br>Windows: `%APPDATA%/Trae/User/settings.json` | Global IDE preferences, agent settings, and feature configurations. |
| **Application Settings (Trae CN)** | macOS: `~/Library/Application Support/Trae CN/User/settings.json`<br>Linux: `~/.config/Trae CN/User/settings.json`<br>Windows: `%APPDATA%/Trae CN/User/settings.json` | Global IDE preferences for the Chinese release edition. |

### Visual Settings Management

Trae provides an integrated management view under **Settings > Skills & Commands**:
- **Skill Inventory**: Inspect, enable, disable, or delete Global and Project skills.
- **Scope Migration**: Convert Project skills to Global skills via the skill action menu.
- **Skill Creation**: Visual modal to configure a new skill (`name`, `description`, instructions) or upload a `.zip` archive / `SKILL.md` file.
- **Import Settings**: Toggle the **Enable .agents Skills Directory** switch to activate runtime scanning of `.agents/skills/`.

---

## Discovery & Precedence

When Trae loads skills during an active session, it resolves definitions using the following precedence rules:

1. **Project Skills Override Global Skills**: When a skill in `.trae/skills/<skill-name>/` shares an identical name with a skill in `~/.trae/skills/<skill-name>/` (or `~/.trae-cn/skills/`), the project-level skill is loaded.
2. **Directory Priority**: The primary workspace directory `.trae/skills/` takes precedence over `.agents/skills/` if both directories contain a skill with matching identifiers.
3. **Dynamic On-Demand Loading**: Trae does not inject full skill instructions into the prompt at session start. Only frontmatter metadata (`name` and `description`) is evaluated during initial task analysis (~100 tokens per skill). Full `SKILL.md` procedural instructions load only when the agent determines high relevance to the task.
4. **Rules vs. Skills Precedence**: Rules in `.trae/project_rules.md` remain permanently in the context window. Skills load on demand to provide task-specific workflows within the constraints established by the rules.

---

## Feature Support

| Feature | Supported | Notes |
|---|---|---|
| **Basic Skills (`SKILL.md`)** | Yes | Standard frontmatter (`name`, `description`) and Markdown instructions. |
| **Auxiliary Folders** | Yes | Supports `examples/`, `templates/`, `resources/`, and `scripts/`. |
| **Cross-Harness `.agents/`** | Yes | Enabled via the **Enable .agents Skills Directory** toggle in settings. |
| **Builder Mode Integration** | Yes | Autonomous agent mode executes terminal commands and modifies workspace files. |
| **Tool Execution** | Yes | Shell commands in the integrated terminal and direct file system read/write. |
| **Tool Restriction (`allowed-tools`)** | Yes | Restricts active tools available to the agent during skill execution. |
| **MCP Server Integration** | Yes | Skills define structured workflows while MCP servers supply callable tools. |
| **Built-in Skills** | Yes | Ships with built-in skills (`TRAE-generate-mini-app`, `TRAE-debugger`, `TRAE-code-review`). |
| **Context Forking (`context: fork`)** | No | Executes within the active conversation; does not fork subagent sessions. |
| **Skill Lifecycle Hooks** | No | Skill lifecycle event hooks are not supported inside skill folders. |

---

## Concrete Directory Layout

Standard project structure for a repository using Trae skills and rules:

```text
my-project/
├── .trae/
│   ├── project_rules.md         # Workspace prompt rules injected into context
│   └── skills/
│       └── taro-deploy/
│           ├── SKILL.md         # Primary skill entrypoint
│           ├── scripts/
│           │   └── build_dist.sh
│           └── references/
│               └── platform_matrix.md
├── .agents/
│   └── skills/
│       └── open-skill/
│           └── SKILL.md         # Cross-harness skill (active when enabled in settings)
├── src/
│   ├── app.ts
│   └── pages/
│       └── index/
└── package.json
```

---

## Concrete SKILL.md Example

Concrete `SKILL.md` demonstrating Trae frontmatter (`name`, `description`, `allowed-tools`) and procedural workflow:

```markdown
---
name: taro-deploy
description: Builds, verifies, and packages multi-platform Taro mini app applications for production deployment. Use when bundling mini apps or validating cross-platform build artifacts.
allowed-tools:
  - run_command
  - read_file
---

# Taro Deployment Workflow

Build and package Taro mini app projects across target client platforms.

## Execution Steps

1. Verify environment configuration and dependencies:
   ```bash
   read_file path="project.config.json"
   ```

2. Build distribution bundle for the target platform:
   ```bash
   run_command command="npm run build:weapp"
   ```

3. Inspect `dist/` directory contents against "`references/platform_matrix.md`" to ensure required manifests exist.

4. Report build status using the output template.

## Output Format

Output:
- Target Platform: weapp | alipay | tt
- Build Status: SUCCESS | FAILURE
- Output Directory: dist/
- Bundle Size: <size in KB>
- Warnings: <list of build warnings or None>
```

### Execution Walkthrough

**Input:**
```
Build and package the current Taro mini app project for the WeChat platform.
```

**Output:**
```
- Target Platform: weapp
- Build Status: SUCCESS
- Output Directory: dist/
- Bundle Size: 412 KB
- Warnings: None
```

---

## Invocation

Trae invokes skills through three operational modes:

### 1. Autonomous Semantic Triggering
Trae evaluates the task description and user intent against the `description` metadata and "When to use" criteria of discovered skills. When a match is detected, the agent loads `SKILL.md` without requiring explicit user commands.

### 2. Manual Chat Prompting
Users can instruct the AI to load and execute a specific skill directly in the Chat panel:
- Prompt: `"Use the taro-deploy skill to build this application for WeChat"`
- Explicit naming bypasses semantic description matching and loads the skill immediately into context.

### 3. Builder Mode Triggers
In Builder Mode, the autonomous agent plans multi-step development tasks, discovers matching skills during implementation phases, and executes associated scripts using terminal and file modification tools.
