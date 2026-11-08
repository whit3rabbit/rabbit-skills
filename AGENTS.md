# rabbit-skills

Agent skill and plugin studio for creating, scaffolding, auditing, linting, and deploying agent skills across 29 harnesses, and validating Claude Code and Codex plugins and marketplaces.

Repository: https://github.com/whit3rabbit/rabbit-skills

## Layout

- `LICENSE` — MIT
- `.gitignore` — standard Python, macOS, and agent harness exclusions
- `.claude-plugin/`
  - `plugin.json` — plugin manifest (`rabbit-skills`)
  - `marketplace.json` — marketplace catalog indexing `rabbit-skills` and cross-referencing `rabbit-writes`
- `skills/`
  - `rabbit-skills-audit/` — agent skill auditor and scaffolder (Anthropic best practices, 45 checks, 29 harnesses)
    - `SKILL.md` — workflow instructions (Modes: Create, Audit, Fix/Improve, Multi-Harness Deploy)
    - `scripts/audit_static.py` — static checks for skills (python3 stdlib only, read-only)
    - `scripts/scaffold_skill.py` — skill scaffolder and 29-harness placement manager
    - `scripts/frontmatter.py` — YAML frontmatter fallback parser (has `--self-test`)
    - `references/audit-checks.md` — 45 numbered checks across 6 areas
    - `references/pre-share-checklist.md` — official 22-item pre-share checklist
    - `references/report-template.md` — severity model, verdict rules, report format
    - `references/harnesses/` — 29 harness-specific skill layouts, paths, and settings guides
    - `evals/` — evaluation suite and bad-skill fixture
  - `rabbit-plugin-audit/` — plugin and marketplace linter and scaffolder
    - `SKILL.md` — workflow instructions for Claude Code and OpenAI Codex plugins/marketplaces
    - `scripts/audit_plugin.py` — static linter for plugins and marketplaces (PL-01..PL-18, MP-01..MP-15)
    - `scripts/scaffold_plugin.py` — plugin and marketplace scaffolder
    - `references/claude-plugins.md` — Claude Code plugins guide
    - `references/codex-plugins.md` — OpenAI Codex & ChatGPT plugins guide
    - `references/plugin-marketplace-linting.md` — check catalog for plugins and marketplaces
- `README.md` — quickstart, installation instructions, and CLI/CI usage

## Working in this repo

- Both skills must pass their own audits:
  ```bash
  python3 skills/rabbit-skills-audit/scripts/audit_static.py skills/rabbit-skills-audit
  python3 skills/rabbit-skills-audit/scripts/audit_static.py skills/rabbit-plugin-audit
  python3 skills/rabbit-plugin-audit/scripts/audit_plugin.py .
  ```
- All self-tests must pass:
  ```bash
  python3 skills/rabbit-skills-audit/scripts/frontmatter.py --self-test
  python3 skills/rabbit-skills-audit/scripts/audit_static.py --self-test
  python3 skills/rabbit-skills-audit/scripts/scaffold_skill.py --self-test
  python3 skills/rabbit-plugin-audit/scripts/audit_plugin.py --self-test
  python3 skills/rabbit-plugin-audit/scripts/scaffold_plugin.py --self-test
  ```
- The scripts never execute target code or install untrusted dependencies.
