# CodeBuddy Harness Reference

Reference for skill discovery, layout, configuration, and execution in Tencent Cloud CodeBuddy IDE.

## Contents

- [Identifier](#identifier)
- [Skill Paths](#skill-paths)
- [Settings & Configuration](#settings--configuration)
- [Discovery & Precedence](#discovery--precedence)
- [Feature Compatibility](#feature-compatibility)
- [Concrete Directory Layout](#concrete-directory-layout)
- [Concrete SKILL.md Example](#concrete-skillmd-example)
- [Invocation](#invocation)

---

## Identifier

- CLI flag / agent identifier: `--agent codebuddy`
- Documentation URL: https://www.codebuddy.ai/docs/ide/Features/Skills

---

## Skill Paths

CodeBuddy distinguishes between workspace-scoped project skills and machine-wide user skills:

| Scope | Path | Purpose |
|---|---|---|
| **Project** | `.codebuddy/skills/<skill-name>/` | Shared with repository contributors; committed to version control. |
| **Global / User** | `~/.codebuddy/skills/<skill-name>/` | Personal skills available across all workspaces on the local machine. |

Each skill must reside in its own subdirectory named after the skill, containing a root `SKILL.md` file.

---

## Settings & Configuration

CodeBuddy is built on a VS Code-compatible architecture and stores configuration across the following locations:

### Directory Locations

- **Project Configuration**: `<workspace-root>/.codebuddy/`
  - `.codebuddy/settings.json` — Workspace-specific editor settings
  - `.codebuddy/rules/` — Workspace agent instructions and prompt rules
  - `.codebuddy/skills/` — Workspace skills directory
- **Global Configuration**: `~/.codebuddy/`
  - `~/.codebuddy/skills/` — Global skills directory
  - `~/.codebuddy/extensions/` — Installed CodeBuddy extensions
- **IDE Application Settings (`settings.json`)**:
  - macOS: `~/Library/Application Support/CodeBuddy/User/settings.json`
  - Linux: `~/.config/CodeBuddy/User/settings.json`
  - Windows: `%APPDATA%/CodeBuddy/User/settings.json`

### Visual Management UI

CodeBuddy provides a visual management page accessible via `Settings > Skills`:
- Displays centralized inventory of both Project Skills and User Skills.
- Supports toggling skills on or off (sets `disable: true`).
- Supports one-click skill imports via the **Import Skill** action.

---

## Discovery & Precedence

1. **Precedence**: When a skill with the same folder or skill `name` exists in both scopes, the **Project skill overrides the Global skill**:
   ```
   .codebuddy/skills/<skill-name>/ (Project) > ~/.codebuddy/skills/<skill-name>/ (Global)
   ```
2. **Metadata Ingestion**: At startup or workspace load, CodeBuddy scans all skills in both paths and loads only frontmatter metadata (`name` and `description`) into the agent's system prompt (~100 tokens per skill).
3. **Disabled Skills**: Skills with `disable: true` in frontmatter or toggled off in the IDE settings UI are excluded from discovery.

---

## Feature Compatibility

| Feature | Supported | Notes |
|---|---|---|
| **Basic Skills** | Yes | Standard `SKILL.md` with `scripts/`, `references/`, and `assets/`. |
| **YAML Frontmatter** | Yes | Requires `name` and `description`; supports `allowed-tools` and `disable`. |
| **`allowed-tools`** | Yes | Restricts agent tool calls while the skill is active. |
| **`disable`** | Yes | Disables skill without deleting the directory. |
| **`context: fork`** | No | CodeBuddy runs skills inside the primary conversation context. |
| **Skill Hooks** | No | Skill lifecycle event hooks are not supported inside skill packages. |

---

## Concrete Directory Layout

A complete CodeBuddy workspace layout containing a project skill with scripts, references, and assets:

```text
my-project/
├── .codebuddy/
│   ├── settings.json
│   └── skills/
│       └── document-processor/
│           ├── SKILL.md
│           ├── scripts/
│           │   └── extract_tables.py
│           ├── references/
│           │   └── schema.md
│           └── assets/
│               └── report_template.docx
├── src/
│   └── index.ts
└── package.json
```

---

## Concrete SKILL.md Example

Concrete `SKILL.md` demonstrating CodeBuddy frontmatter (`name`, `description`, `allowed-tools`, `disable`) and progressive disclosure:

```markdown
---
name: document-processor
description: Extracts tables and structured fields from docx and pdf files. Use when the user requests document data extraction or mentions processing forms and statements.
allowed-tools:
  - execute_command
  - read_file
  - write_file
disable: false
---

# Document Processor

Extract structured data from documents into standardized JSON format.

## Execution Workflow

1. Identify the input document type and target schema.
2. If processing non-standard tables, read [references/schema.md](references/schema.md).
3. Run extraction script:
   ```bash
   python3 .codebuddy/skills/document-processor/scripts/extract_tables.py input.docx output.json
   ```
4. Validate the resulting JSON against the expected schema before responding.
```

---

## Invocation

CodeBuddy triggers and executes skills through two mechanisms:

1. **Implicit Model Triggering**:
   - The user asks a question in IDE chat (for example: "Extract table data from invoices.docx").
   - CodeBuddy matches the query against skill descriptions in system prompt metadata.
   - When matched, CodeBuddy loads the full `SKILL.md` body into conversation context.
   - The agent reads `references/` or executes `scripts/` on demand.

2. **Explicit User Invocation**:
   - Users can explicitly invoke skills in the chat input via slash commands (`/document-processor`) or `@` mentions (`@document-processor`).
   - Explicit invocation immediately pulls the skill body into context, bypassing fuzzy description matching.
