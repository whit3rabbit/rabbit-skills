# Posit Assistant Harness Reference

Reference guide for skill discovery, directory layout, configuration precedence, and feature support in Posit Assistant across Positron, RStudio, and Posit data science environments.

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
| CLI Identifier | `--agent posit-assistant` |
| Supported Surfaces | Positron IDE (Chat panel & Inline Assistant), RStudio, Posit Workbench, TUI |
| Specification URL | `https://assistant.posit.co/docs/features/skills/` |

---

## Compatibility Matrix

| Feature | Supported | Details |
|---|---|---|
| Basic Skills (`SKILL.md`) | Yes | Standard YAML frontmatter (`name`, `description`) and Markdown body. |
| `argument-hint` Frontmatter | Yes | Hint displayed in slash-command menu (e.g., `<file>`, `<dataset>`). |
| `user-invocable` Frontmatter | Yes | When `false`, hides skill from slash command menu while keeping auto-loading. |
| `disable-model-invocation` | Yes | When `true`, suppresses autonomous loading; skill executes only via explicit slash command. |
| Multi-Language Scripts | Yes | Executable scripts in `scripts/` (R, Python, Bash). |
| Custom Skill Paths | Yes | Configurable via `skills.paths` in `settings.json`. |
| Prompt Migration | Yes | Built-in `/import-instructions` imports `.prompt.md` files from Copilot, Claude Code, and VS Code. |
| MCP Tools | Yes | Configured via `mcp.json` or `settings.json`. |

---

## Skill Paths

Posit Assistant resolves skills across project, user, and built-in scopes.

### Project Skills (Workspace-Scoped)
- **Primary Path**: `<project-root>/.posit/assistant/skills/<skill-name>/SKILL.md`
- **Shared Agent Skills Path**: `<project-root>/.agents/skills/<skill-name>/SKILL.md`
- **Scope**: Scoped to the current project or workspace root; suitable for team-shared repository assets.

### User Skills (Global)
- **Primary Path**: `~/.posit/assistant/skills/<skill-name>/SKILL.md`
- **Shared Agent Skills Path**: `~/.agents/skills/<skill-name>/SKILL.md`
- **Scope**: Available across all projects on the local machine.

<details>
<summary>Legacy paths</summary>

Older versions used `~/.positai/` instead of `~/.posit/assistant/`.
</details>

### Built-in Skills (Runtime-Bundled)
- Shipped with Posit Assistant for core data science workflows (e.g., `quarto-authoring`, `report`, `shiny-bslib`, `shiny-bslib-theming`, `predictive-modeling-r`, `predictive-modeling-python`, `r-package-development`, `snowflake`, `posit-products`, `create-skill`, `import-instructions`).
- Lowest lookup precedence; overridden by user and project skills with the same name.

---

## Settings & Configuration

Configurations and data science tool settings reside in `.posit/` and user configuration trees:

| Scope | Location | Purpose |
|---|---|---|
| Project Settings | `<project-root>/.posit/assistant/settings.json` | Project-specific overrides, model selections, and custom `skills.paths`. |
| Project Data Science Config | `<project-root>/.posit/` | Posit Assistant project-level state and data science tool configurations. |
| IDE / Editor Settings | `<project-root>/.positron/settings.json` | Positron IDE editor preferences and language runtime environments. |
| Global Settings | `~/.posit/assistant/settings.json` | User-wide preferences, fallback models, and default search paths. |
| Global Providers | `~/.posit/assistant/providers.json` | LLM provider endpoints and credentials. |

### Customizing Search Paths
Custom skill search paths can be configured in `settings.json` under `skills.paths`:

```json
{
  "skills": {
    "paths": [
      "~/.agents/skills",
      "~/.posit/assistant/skills",
      ".agents/skills",
      ".posit/assistant/skills",
      "~/shared/data-science-skills"
    ]
  }
}
```

> [!IMPORTANT]
> If `skills.paths` is declared at the project level, it completely replaces the global `skills.paths` list; paths are not merged.

---

## Discovery & Precedence

When identical skill names appear across multiple locations, Posit Assistant resolves collisions by order of precedence (highest to lowest):

1. **Project Posit Skills**: `.posit/assistant/skills/<skill-name>/` (relative to workspace root)
2. **Project Shared Skills**: `.agents/skills/<skill-name>/` (relative to workspace root)
3. **User Posit Skills**: `~/.posit/assistant/skills/<skill-name>/`
4. **User Shared Skills**: `~/.agents/skills/<skill-name>/`
5. **Built-in Skills**: Bundled system skills

Within the same tier (project or user), `.posit/assistant/skills/` takes precedence over `.agents/skills/`. Project-level directories override all user-level and built-in directories.

---

## Feature Support

### Frontmatter Configuration

Skills are declared via YAML frontmatter in `SKILL.md`:

```yaml
---
name: tidyverse-eda
description: Explores tabular datasets using dplyr and ggplot2. Use when analyzing data distributions or generating summary statistics.
argument-hint: <dataset.csv>
user-invocable: true
disable-model-invocation: false
compatibility: R >= 4.3.0, tidyverse >= 2.0.0
---
```

- **`name`** (required): Lowercase letters, numbers, and hyphens only; maximum 64 characters; must match the parent folder name.
- **`description`** (required): Context description guiding autonomous activation; maximum 1024 characters.
- **`argument-hint`** (optional): Parameter hint displayed beside the command in the slash-command menu.
- **`user-invocable`** (optional): Set to `false` to hide from slash-command listings while retaining autonomous model activation.
- **`disable-model-invocation`** (optional): Set to `true` for procedural tasks intended only for direct user invocation.

### Data Science Workflows (R / Python / Quarto)
Posit Assistant natively bridges skills with data science environments:
- **R Workflows**: Integration with `devtools`, `testthat`, `roxygen2`, and `tidymodels`.
- **Python Workflows**: Machine learning pipelines using `scikit-learn` and standard scientific packages.
- **Quarto Authoring**: Document generation, conversion of chat sessions into notebooks (`.qmd`), and document rendering via Quarto CLI.
- **Shiny & Dashboards**: Interactive application scaffolding with `bslib` and Bootstrap theming.

### Tool & MCP Integration
- Connects to external services (e.g., Snowflake data warehouses via semantic views, Databricks).
- Integrates with Positron IDE language runtimes (R and Python consoles) and Posit Connect publishing endpoints.
- Extensible via Model Context Protocol (MCP) server definitions declared in assistant configuration.

---

## Directory Layout

A typical data science repository incorporating project-specific Posit Assistant skills:

```
my-data-project/
├── .posit/
│   └── assistant/
│       ├── settings.json                # Project assistant configuration
│       └── skills/
│           └── quarto-report/
│               ├── SKILL.md             # Required skill entrypoint
│               ├── scripts/
│               │   └── render_report.R  # Script executed during report build
│               ├── references/
│               │   └── formatting.md    # Style guide for document generation
│               └── assets/
│                   └── template.qmd     # Quarto document scaffold template
├── data/
│   └── sales_2026.csv
├── analysis.qmd
├── renv.lock
└── my-data-project.Rproj
```

---

## Invocation

Posit Assistant supports two primary execution mechanisms:

1. **Autonomous Progressive Disclosure**: The assistant monitors conversation context against indexed skill metadata (`name` and `description`). When relevant, the assistant dynamically loads `SKILL.md` instructions and executes referenced workflows.
2. **Explicit Slash Commands**: Every eligible skill doubles as a slash command (`/<skill-name>`). Users invoke skills deterministically from the chat panel or inline assistant interface, optionally passing arguments:
   ```
   /quarto-report data/sales_2026.csv --format html
   ```

### Inline Assistant Execution
Within Positron and RStudio, skills can be triggered inline inside source code buffers. The inline assistant consumes active skill instructions to refactor code, generate documentation (e.g., `roxygen2` comments), or construct Quarto blocks directly in editor buffers.

---

## Concrete Example

### Example Skill: `quarto-report`

#### File: `.posit/assistant/skills/quarto-report/SKILL.md`

```markdown
---
name: quarto-report
description: Generates reproducible Quarto (.qmd) reports and renders them to HTML or PDF. Use when creating analytical summaries or presenting data findings.
argument-hint: <data-file>
user-invocable: true
disable-model-invocation: false
---

# Quarto Report Generation

Generate standardized analytical reports from tabular datasets.

## Execution Steps

1. **Inspect Data Structure**:
   Examine column names and types using R:
   ```bash
   Rscript -e "str(read.csv('$DATA_FILE'))"
   ```

2. **Scaffold Report**:
   Copy "assets/template.qmd" to the target report destination and insert analysis sections.

3. **Render Document**:
   Compile the document with Quarto CLI:
   ```bash
   quarto render report.qmd --to html
   ```

## Output Format

Always structure completion output using this exact format:

Output:
- **Generated File**: `path/to/report.qmd`
- **Render Output**: `path/to/report.html` (or PDF)
- **Dataset Evaluated**: `<data-file>` (row/column summary)
- **Key Findings**: 2-3 bullet points highlighting prominent patterns
```

### Execution Example

**User Input:**
```
/quarto-report data/sales_2026.csv
```

**Assistant Action:**
1. Loads `.posit/assistant/skills/quarto-report/SKILL.md`.
2. Inspects `data/sales_2026.csv`.
3. Creates and renders `sales_report.qmd`.
4. Returns formatted summary per output template:

```markdown
Output:
- **Generated File**: `reports/sales_summary.qmd`
- **Render Output**: `reports/sales_summary.html`
- **Dataset Evaluated**: `data/sales_2026.csv` (1,250 rows, 8 columns)
- **Key Findings**:
  - Q3 revenue grew 14% quarter-over-quarter.
  - Regional variance was highest in the Western territory.
```
