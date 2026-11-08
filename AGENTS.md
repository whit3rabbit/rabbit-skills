# rabbit-skills

Claude Code, Codex, and DeepSeek Harness (DSH) plugin studio and marketplace for agent skills across 31 harnesses, and plugin/marketplace validation.

Repository: https://github.com/whit3rabbit/rabbit-skills

## Verify before shipping

All changes must pass their own audits and self-tests before committing:

```bash
# Static audits for both bundled skills:
python3 skills/rabbit-skills-audit/scripts/audit_static.py skills/rabbit-skills-audit --strict
python3 skills/rabbit-skills-audit/scripts/audit_static.py skills/rabbit-plugin-audit --strict

# Plugin and marketplace schema validation:
python3 skills/rabbit-plugin-audit/scripts/audit_plugin.py . --strict

# All built-in self-tests:
python3 skills/rabbit-skills-audit/scripts/frontmatter.py --self-test
python3 skills/rabbit-skills-audit/scripts/audit_static.py --self-test
python3 skills/rabbit-skills-audit/scripts/audit_dsh_skill.py --self-test
python3 skills/rabbit-skills-audit/scripts/scaffold_skill.py --self-test
python3 skills/rabbit-plugin-audit/scripts/audit_plugin.py --self-test
python3 skills/rabbit-plugin-audit/scripts/audit_dsh.py --self-test
python3 skills/rabbit-plugin-audit/scripts/scaffold_plugin.py --self-test
```

## Architecture & Layout

One home per fact. Each skill under `skills/<name>/` is completely self-contained per Anthropic's progressive disclosure specification:

- **`.claude-plugin/`**:
  - `plugin.json`: Plugin manifest for `rabbit-skills` (v1.1.0). Keeps always-on token cost under 150 tokens (`PL-12`).
  - `marketplace.json`: Marketplace catalog indexing `rabbit-skills` and pointing to `whit3rabbit/rabbit-writes`.
- **`skills/rabbit-skills-audit/`**: Agent skill authoring, static auditing, and 31-harness deployment.
  - `SKILL.md`: Main progressive disclosure workflow (<500 lines).
  - `scripts/audit_static.py`: Read-only deterministic static linter (45 checks across `MD`, `ST`, `CQ`, `WF`, `SC`, `EV`).
  - `scripts/audit_dsh_skill.py`: Dedicated static linter for DeepSeek Harness (DSH) skills (DSK-01..DSK-12).
  - `scripts/scaffold_skill.py`: "Born-Clean" skill scaffolder and placement engine for 31 harnesses.
  - `scripts/frontmatter.py`: Zero-dependency YAML frontmatter parser fallback.
  - `references/audit-checks.md`: Full catalog of 45 checks with Good/Bad examples.
  - `references/pre-share-checklist.md`: Official Anthropic 22-item pre-share checklist mapped to check IDs.
  - `references/report-template.md`: Verdict criteria and markdown report template.
  - `references/harnesses/`: 31 markdown guides detailing paths and precedence for all supported agent harnesses (including DeepSeek Harness `dsh.md`).
  - `evals/`: 5 evaluation scenarios and test fixture (`fixtures/bad-skill/`) used by `--self-test`.
- **`skills/rabbit-plugin-audit/`**: Plugin and marketplace manifest linter and scaffolder.
  - `SKILL.md`: Plugin and marketplace workflow instructions.
  - `scripts/audit_plugin.py`: Static linter for Claude Code and Codex plugins/catalogs (PL-01..PL-18, MP-01..MP-15).
  - `scripts/audit_dsh.py`: Dedicated static linter for DeepSeek Harness (Cordis) plugins, tools, and presets (DSH-01..DSH-12).
  - `scripts/scaffold_plugin.py`: Scaffolder for plugin manifests, lifecycle hooks, MCP configurations, Cordis bundles, and catalogs.
  - `references/claude-plugins.md`: Complete guide to Claude Code plugins, components, evals, and cost profiling.
  - `references/codex-plugins.md`: Complete guide to OpenAI Codex & ChatGPT portable plugins.
  - `references/deepseek-harness-plugins.md`: Complete guide to DeepSeek Harness plugins, Cordis patches, tools, and events.
  - `references/plugin-marketplace-linting.md`: Check specifications for plugins, marketplaces, and DeepSeek Harness bundles.

## Invariants & Rules for Agents

1. **Zero External Dependencies**: All scripts in `scripts/` must run strictly on Python 3 standard library (`pathlib`, `json`, `re`, `argparse`, `ast`, `shutil`). Never add runtime dependencies to `requirements.txt` or import third-party packages.
2. **Read-Only Audit Safety**: Linters never execute, import, or evaluate target code or install untrusted dependencies. Code is inspected via `ast.parse` and regex only.
3. **Self-Contained Skills (`SC-08`)**: Every markdown file inside a skill (`references/*.md`, `SKILL.md`) must only link to files within that skill's own directory tree. Cross-skill links between `skills/rabbit-skills-audit` and `skills/rabbit-plugin-audit` must use plain text names or absolute URLs, not relative file links, so skills remain functional when deployed independently into foreign harnesses.
4. **Strict Check ID Synchronization**: Check IDs in `scripts/audit_static.py` and `scripts/audit_plugin.py` must stay in exact 1-to-1 parity with their definitions in `references/audit-checks.md` and `references/plugin-marketplace-linting.md`.
5. **Always-On Token Ceiling (`PL-12`)**: Total always-on token overhead from `plugin.json` and all bundled skill descriptions must remain under 150 tokens. Keep descriptions concise, high-signal, and trigger-oriented.
6. **No Breaking Changes to `--self-test`**: All self-test functions (`_self_test()`) must run standalone and verify regression fixtures (`bad-skill`, invalid manifests) before reporting success.
