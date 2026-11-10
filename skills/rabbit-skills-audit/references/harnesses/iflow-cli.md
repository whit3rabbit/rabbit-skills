# iFlow CLI Harness Reference

Reference guide for skill discovery, directory structure, configuration precedence, and feature support in iFlow CLI.

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
| CLI Identifier | `--agent iflow-cli` |
| Supported Surfaces | iFlow CLI (`iflow`), interactive terminal interface |
| Specification URL | `https://platform.iflow.cn/en/cli/examples/skill` |

---

## Compatibility Matrix

| Feature | Supported | Details |
|---|---|---|
| Basic Skills (`SKILL.md`) | Yes | Requires YAML frontmatter (`name`, `description`, `license`) and Markdown body. |
| Project-Level Scope | Yes | Project directory `.iflow/skills/` isolated to workspace. |
| Global-Level Scope | Yes | User home directory `~/.iflow/skills/` available across all projects. |
| Multi-file Skills | Yes | Scripts in `scripts/`, templates in `templates/`, reference docs in `*.md`. |
| Lifecycle / Setup Scripts | Yes | Optional setup scripts (e.g. `command_setup.sh`) for dependency installation. |
| Workflow Steps | Yes | Ordered procedural steps and verification workflows within `SKILL.md`. |
| Tool Integration | Yes | Executes helper scripts via shell, integrates with MCP tools and CLI subcommands. |

---

## Skill Paths

iFlow CLI searches two scopes for skills:

### Project-Level Skills (Workspace)
- **Path**: `{project-root}/.iflow/skills/<skill-name>/SKILL.md`
- **Scope**: Local to the current project workspace. Ideal for version control, project-specific dependencies, and team workflows.

### Global-Level Skills (User-Wide)
- **Path**: `~/.iflow/skills/<skill-name>/SKILL.md`
- **Scope**: Machine-level user directory. Available across all projects run under the user profile.

---

## Settings & Configuration

iFlow CLI stores configuration, workflow parameters, and agent runtime settings across workspace and user locations:

| Location | Path | Scope | Purpose |
|---|---|---|---|
| Project Configuration | `{project-root}/.iflow/config.yaml` | Workspace | Project-specific agent parameters, active workflow overrides, and skill settings. |
| Project Skills | `{project-root}/.iflow/skills/` | Workspace | Workspace-scoped skill packages. |
| Global Configuration | `~/.iflow/config.yaml` | Machine / User | Default user preferences, model settings, and CLI options. |
| Global State & Auth | `~/.iflow/` | Machine / User | User authentication tokens, session logs, cached marketplace metadata. |
| Global Skills | `~/.iflow/skills/` | Machine / User | Universally available user skill packages. |

---

## Discovery & Precedence

When searching for skills, iFlow CLI scans the filesystem according to explicit precedence rules:

1. **Project-Level Overrides Global**: Skills located in `.iflow/skills/<skill-name>` take precedence over identically named skills in `~/.iflow/skills/<skill-name>`.
2. **Explicit Scope Selection**: CLI commands can target a specific scope using the `--scope` flag:
   - Project: `iflow skill add <skill-id> --scope project`
   - Global: `iflow skill add <skill-id> --scope global`
3. **Registry Rescan**: After creating, modifying, or deleting skills manually on disk, the registry is reloaded with:
   ```bash
   /skills refresh
   ```

---

## Feature Support

### Frontmatter Schema
iFlow CLI skills require three primary YAML frontmatter keys:

```yaml
---
name: data-cleaner
description: Sanitizes CSV and JSON datasets by removing duplicates, trimming whitespace, and validating schemas. Use when preprocessing tabular data.
license: MIT
---
```

- `name`: Unique skill identifier (kebab-case).
- `description`: Detailed summary used by the model for autonomous intent matching.
- `license`: Software license identifier (e.g. `MIT`, `Apache-2.0`, or `Proprietary. LICENSE.txt has complete terms`).

### Workflow Steps & Script Execution
Skills organize multi-step execution by referencing executable scripts and reference documentation:
- **Scripts (`scripts/`)**: Deterministic helper scripts (e.g. Python, Node.js, Shell) invoked by the model via shell commands to process data or call external APIs without inflating prompt tokens.
- **Templates (`templates/`)**: Scaffolding templates and configuration boilerplates copied into the workspace.
- **Reference Docs (`reference.md`, `*.md`)**: Progressive disclosure documents containing API definitions, domain schemas, or extended format instructions loaded on-demand.

### Tool & MCP Integration
Skills can leverage CLI built-in tools (file reading/writing, terminal command execution) as well as configured MCP servers declared in the iFlow runtime configuration.

---

## Directory Layout

A standard iFlow CLI workspace with local project configuration and skills adheres to the following tree structure:

```
my-project/
├── .iflow/
│   ├── config.yaml                      # Project agent configuration
│   └── skills/
│       └── data-cleaner/
│           ├── SKILL.md                 # Required entrypoint with frontmatter
│           ├── LICENSE.txt              # Complete license terms
│           ├── reference.md             # Format documentation
│           ├── scripts/
│           │   └── sanitize.py          # Python data cleaning script
│           └── templates/
│               └── report.md            # Report template
├── src/
│   └── pipeline.py
└── data/
    └── raw_input.csv
```

---

## Invocation

iFlow CLI supports two distinct invocation models:

### 1. Model-Initiated Prompt Triggering (Autonomous)
Skills are registered into the agent prompt context via their `name` and `description` frontmatter metadata. When the user prompt expresses an intent matching the description, the agent autonomously reads `SKILL.md` and executes the documented workflow.

```
User Prompt: "Clean up and deduplicate the customer list in data/raw_input.csv."
Model Action: Identifies match with data-cleaner description -> loads SKILL.md -> executes scripts/sanitize.py -> returns validation report.
```

### 2. Interactive CLI Management
Users manage skills inside the iFlow interactive session or directly via the command line:

| Command | Interface | Description |
|---|---|---|
| `/skills online` | Interactive TUI | Browse, search, and install skills from the online marketplace. |
| `/skills list` (or `/skills`) | Interactive TUI | View all installed global and project skills. |
| `/skills list details` | Text Mode | Print full details and file paths for all configured skills. |
| `/skills refresh` | CLI Command | Re-scan `.iflow/skills/` and `~/.iflow/skills/` to reload the registry. |
| `iflow skill add <skill-id> --scope project` | CLI Command | Install a skill package directly into `.iflow/skills/`. |
| `iflow skill add <skill-id> --scope global` | CLI Command | Install a skill package globally into `~/.iflow/skills/`. |

---

## Concrete Example

### Example Skill: `data-cleaner`

#### File: `.iflow/skills/data-cleaner/SKILL.md`

```markdown
---
name: data-cleaner
description: Sanitizes CSV and JSON datasets by removing duplicates, trimming whitespace, and validating schemas. Use when preprocessing tabular data.
license: MIT
---

# Data Cleaner Workflow

Process and sanitize input tabular data files using the local cleanup script.

## Execution Steps

1. **Inspect Data Structure**:
   Check file format and column headers using `read_file`.

2. **Execute Sanitization**:
   Run the preprocessing script on the input file:
   ```bash
   python3 scripts/sanitize.py --input data/raw_input.csv --output data/clean_input.csv
   ```

3. **Validate and Report**:
   Verify record count and schema integrity. Produce an execution report using the template below.

## Output Format

Output:
- **Input File**: `<path>`
- **Output File**: `<path>`
- **Records Processed**: `<count>`
- **Duplicates Removed**: `<count>`
- **Validation Status**: PASS | FAIL
```

### Execution Example

**Input:**
```
Clean up and deduplicate the customer list in data/raw_input.csv.
```

**Output:**
```
Input File: data/raw_input.csv
Output File: data/clean_input.csv
Records Processed: 1,420
Duplicates Removed: 38
Validation Status: PASS
```
