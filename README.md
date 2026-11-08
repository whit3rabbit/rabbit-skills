# rabbit-skills

> Developer studio and marketplace for agent skills and plugins: create, scaffold, audit, lint, and deploy agent skills across 29 harnesses, and validate Claude Code and OpenAI Codex plugins.

**Repository:** [https://github.com/whit3rabbit/rabbit-skills](https://github.com/whit3rabbit/rabbit-skills)

Built on [Anthropic's Agent Skills Best Practices](https://platform.claude.com/docs/en/agents-and-tools/agent-skills/best-practices) and official Claude Code & Codex plugin specifications. Powered by zero-dependency Python 3 standard-library linters and scaffolders, `rabbit-skills` runs inside any agent harness (Claude Code, Cursor, Antigravity, OpenCode, Codex) and in standalone CI/CD pipelines.

---

## Bundled Skills

The `rabbit-skills` suite packages two specialized agent skills:

### 1. `rabbit-skills-audit`
- **Purpose:** Author, scaffold, audit, lint, and deploy standard `SKILL.md` agent skills.
- **Standards:** Evaluates 45 rules across 6 auditable areas (**MD** Metadata, **ST** Structure, **CQ** Content Quality, **WF** Workflows, **SC** Scripts, **EV** Evaluations) and evaluates the official 22-item Pre-Share Checklist.
- **Harnesses:** Built-in placement manager supporting **29 agent harnesses** (Claude Code, Cursor, Google Antigravity, OpenCode, Cline, Windsurf, Codex, etc.).
- **Tools:**
  - `scripts/audit_static.py`: Read-only deterministic static linter and checklist runner.
  - `scripts/scaffold_skill.py`: "Born-Clean" skill generator and multi-harness placement manager.
  - `scripts/frontmatter.py`: Robust fallback YAML frontmatter parser.

### 2. `rabbit-plugin-audit`
- **Purpose:** Scaffold, audit, lint, and validate agent plugins and marketplace catalogs.
- **Standards:** Validates plugin manifests (`plugin.json`), marketplace catalogs (`marketplace.json`), lifecycle hooks (`hooks.json`), MCP server declarations (`.mcp.json`), and always-on token costs against 33 checks (**PL-01..PL-18** and **MP-01..MP-15**).
- **Ecosystems:** Supports Claude Code plugins, OpenAI Codex portable plugins, and community marketplaces.
- **Tools:**
  - `scripts/audit_plugin.py`: Static linter for plugins and marketplaces.
  - `scripts/scaffold_plugin.py`: Generator for plugins, hooks, MCP configs, and marketplace catalogs.

---

## Installation

### Option 1: Claude Code Plugin & Marketplace (Recommended)

Add the `rabbit-skills` marketplace catalog to Claude Code:

```bash
# Register the marketplace:
claude plugin marketplace add whit3rabbit/rabbit-skills

# Install the rabbit-skills suite (installs rabbit-skills-audit and rabbit-plugin-audit):
claude plugin install rabbit-skills
```

> **Note:** The `rabbit-skills` marketplace also cross-references [`rabbit-writes`](https://github.com/whit3rabbit/rabbit-writes) (the companion writing voice and AI-pattern engine), allowing you to install either suite directly.

### Option 2: Standalone CLI / Git Clone

Clone the repository to run the linters and scaffolders anywhere without dependencies:

```bash
git clone https://github.com/whit3rabbit/rabbit-skills.git
cd rabbit-skills
```

Python 3.10+ standard library is all that is required.

### Option 3: Deploying into Any Agent Harness (29 Platforms)

Use `scaffold_skill.py` to deploy either skill directly into your project or global configuration:

```bash
# Install rabbit-skills-audit to Claude Code and Cursor for the current project:
python3 skills/rabbit-skills-audit/scripts/scaffold_skill.py rabbit-skills-audit \
  --harness claude-code,cursor \
  --scope project

# Install to Google Antigravity globally:
python3 skills/rabbit-skills-audit/scripts/scaffold_skill.py rabbit-skills-audit \
  --harness antigravity \
  --scope user
```

---

## Quickstart & Common Commands

### Auditing an Agent Skill

```bash
# Standard Markdown report with evidence and checklist
python3 skills/rabbit-skills-audit/scripts/audit_static.py /path/to/my-skill --format markdown

# Text output with 22-item pre-share checklist
python3 skills/rabbit-skills-audit/scripts/audit_static.py /path/to/my-skill --checklist

# Strict CI mode (exit 1 on any error)
python3 skills/rabbit-skills-audit/scripts/audit_static.py /path/to/my-skill --strict

# Filter by area or specific checks
python3 skills/rabbit-skills-audit/scripts/audit_static.py /path/to/my-skill --area MD,ST
python3 skills/rabbit-skills-audit/scripts/audit_static.py /path/to/my-skill --check MD-04,SC-04
```

### Scaffolding a New Skill ("Born Clean")

```bash
# Generate a new skill with reference docs, evals, and multi-harness placement:
python3 skills/rabbit-skills-audit/scripts/scaffold_skill.py my-new-skill \
  --harness claude-code,cursor,antigravity \
  --scope project \
  --freedom medium
```

### Auditing a Plugin or Marketplace

```bash
# Audit a plugin directory (validates plugin.json, components, hooks, MCP)
python3 skills/rabbit-plugin-audit/scripts/audit_plugin.py /path/to/my-plugin --format markdown

# Audit a marketplace catalog (validates marketplace.json and listed plugins)
python3 skills/rabbit-plugin-audit/scripts/audit_plugin.py /path/to/marketplace.json --strict

# Self-audit this entire repository
python3 skills/rabbit-plugin-audit/scripts/audit_plugin.py .
```

### Scaffolding a Plugin or Marketplace

```bash
# Scaffold a Claude Code plugin with a skill and hook:
python3 skills/rabbit-plugin-audit/scripts/scaffold_plugin.py my-plugin --target claude-code --components skill,hook

# Scaffold an OpenAI Codex portable plugin:
python3 skills/rabbit-plugin-audit/scripts/scaffold_plugin.py my-plugin --target codex --components skill,mcp

# Scaffold a marketplace catalog:
python3 skills/rabbit-plugin-audit/scripts/scaffold_plugin.py my-marketplace --target claude-code --components marketplace
```

---

## Master Check Catalogs

### Agent Skills: 45 Auditable Checks (`rabbit-skills-audit`)

| Area | Checks | Focus | Example Rule |
|---|---|---|---|
| **MD** Metadata | MD-01 – MD-16 | YAML frontmatter, naming conventions, descriptions | `MD-04`: Description must state when to trigger. |
| **ST** Structure | ST-01 – ST-06 | Token economy, line limits, progressive disclosure | `ST-01`: SKILL.md body < 500 lines. |
| **CQ** Content Quality | CQ-01 – CQ-05 | Concrete examples, terminology, degrees of freedom | `CQ-04`: Requires concrete Input/Output examples. |
| **WF** Workflows | WF-01 – WF-05 | Procedural steps, checklists, feedback loops | `WF-01`: Clear sequential steps with copyable checklist. |
| **SC** Scripts & Tools | SC-01 – SC-08 | Script safety, forward slashes, valid file paths | `SC-08`: All referenced files and scripts must exist. |
| **EV** Evaluations | EV-01 – EV-04 | Test scenarios, multi-model evals, trigger checks | `EV-01`: At least 3 test scenarios in `evals/evals.json`. |

### Plugins & Marketplaces: 33 Checks (`rabbit-plugin-audit`)

| Target | Checks | Focus | Example Rule |
|---|---|---|---|
| **PL** Plugin Manifest | PL-01 – PL-08 | `plugin.json` schema, semver, kebab-case IDs | `PL-02`: Valid lowercase kebab-case name (<64 chars). |
| **PL** Components | PL-09 – PL-12 | Component structure, orphan files, always-on tokens | `PL-12`: Total always-on token budget <= 150 tokens. |
| **PL** Hooks & Lifecycle | PL-13 – PL-15 | Event triggers (`PreToolUse`, `PostToolUse`), hooks.json | `PL-14`: Hook script paths must exist and be executable. |
| **PL** MCP & Security | PL-16 – PL-18 | `.mcp.json`, parameter substitutions, credentials | `PL-16`: Use `${config.KEY}` rather than raw secrets. |
| **MP** Marketplace | MP-01 – MP-15 | `marketplace.json` schema, sources, categories | `MP-10`: Catalog entry name matches plugin manifest name. |

---

## 29 Supported Harnesses

`rabbit-skills-audit` includes explicit path matrices and configuration guides for 29 agent platforms:

| Harness | Primary Project Path | Primary Global Path |
|---|---|---|
| **Claude Code** | `.claude/skills/<name>/` | `~/.claude/skills/<name>/` |
| **Cursor** | `.cursor/skills/<name>/` | `~/.cursor/skills/<name>/` |
| **Google Antigravity** | `.agents/skills/<name>/` | `~/.gemini/config/skills/<name>/` |
| **OpenCode** | `.config/opencode/skills/<name>/` | `~/.config/opencode/skills/<name>/` |
| **Codex (OpenAI)** | `.codex/skills/<name>/` | `~/.codex/skills/<name>/` |
| **Cline** | `.cline/skills/<name>/` | `~/.cline/skills/<name>/` |
| **Windsurf** | `.windsurf/skills/<name>/` | `~/.windsurf/skills/<name>/` |
| **Roo Code** | `.roo/skills/<name>/` | `~/.roo/skills/<name>/` |
| **GitHub Copilot** | `.github/skills/<name>/` | `~/.copilot/skills/<name>/` |
| *... and 20 more* | See [`references/harnesses/`](skills/rabbit-skills-audit/references/harnesses/) | Fully indexed in matrix |

---

## Testing & Quality Assurance

Run the built-in self-tests for all linters and scaffolders:

```bash
# Skill auditor & YAML parser self-tests:
python3 skills/rabbit-skills-audit/scripts/frontmatter.py --self-test
python3 skills/rabbit-skills-audit/scripts/audit_static.py --self-test
python3 skills/rabbit-skills-audit/scripts/scaffold_skill.py --self-test

# Plugin & marketplace linter self-tests:
python3 skills/rabbit-plugin-audit/scripts/audit_plugin.py --self-test
python3 skills/rabbit-plugin-audit/scripts/scaffold_plugin.py --self-test
```

### Self-Audit

The repository continuously audits itself:
```bash
# Verify both skills pass static audit:
python3 skills/rabbit-skills-audit/scripts/audit_static.py skills/rabbit-skills-audit
python3 skills/rabbit-skills-audit/scripts/audit_static.py skills/rabbit-plugin-audit

# Verify plugin manifest and marketplace catalog pass linting:
python3 skills/rabbit-plugin-audit/scripts/audit_plugin.py .
```

---

## Repository Layout

```text
rabbit-skills/
├── LICENSE                                # MIT License
├── README.md                              # This documentation
├── AGENTS.md                              # Maintenance rules and CI standards
├── .gitignore                             # Python, macOS, and harness exclusions
├── .claude-plugin/
│   ├── plugin.json                        # Plugin manifest for rabbit-skills
│   └── marketplace.json                   # Marketplace catalog (rabbit-skills + rabbit-writes)
└── skills/
    ├── rabbit-skills-audit/               # Agent skill authoring & auditing
    │   ├── SKILL.md                       # Progressive disclosure workflow guide
    │   ├── scripts/
    │   │   ├── audit_static.py            # 45-check static linter & checklist runner
    │   │   ├── scaffold_skill.py          # 29-harness skill scaffolder
    │   │   └── frontmatter.py             # YAML frontmatter parser
    │   ├── references/
    │   │   ├── audit-checks.md            # 45 numbered checks & examples
    │   │   ├── pre-share-checklist.md     # Official 22-item checklist
    │   │   ├── report-template.md         # Severity rules & report template
    │   │   └── harnesses/                 # 29 harness guides (amp, claude-code, etc.)
    │   └── evals/                         # Evaluation scenarios & fixtures
    │
    └── rabbit-plugin-audit/               # Plugin & marketplace packaging & linting
        ├── SKILL.md                       # Plugin workflow guide
        ├── scripts/
        │   ├── audit_plugin.py            # Static linter for plugins and marketplaces
        │   └── scaffold_plugin.py         # Plugin & marketplace scaffolder
        └── references/
            ├── claude-plugins.md          # Comprehensive Claude Code plugin guide
            ├── codex-plugins.md           # OpenAI Codex & portable plugin guide
            └── plugin-marketplace-linting.md # PL-01..PL-18 & MP-01..MP-15 catalog
```

---

## License

MIT — see [LICENSE](LICENSE). Copyright (c) 2026 whit3rabbit.
