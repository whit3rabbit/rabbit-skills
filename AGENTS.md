# skill-auditor

A skill that audits other agent skills against Anthropic's Agent Skills best practices:
https://platform.claude.com/docs/en/agents-and-tools/agent-skills/best-practices

## Layout

Files are added over time; keep this list current when the tree changes.

- `LICENSE` — MIT
- `plugin.json` — plugin manifest (name, version, license)
- `README.md` — quickstart, harness install paths, CLI and CI usage
- `auditing-skills/` — the skill itself; installable into any harness's skills directory
  - `SKILL.md` — the audit workflow (inventory → static → judge → checklist → report)
  - `references/audit-checks.md` — the decomposition: 6 areas, 45 numbered checks
  - `references/pre-share-checklist.md` — the official pre-share checklist, mapped to check IDs
  - `references/report-template.md` — severity model, verdict rules, report format
  - `references/harnesses/` — harness-specific skill layouts, paths, and settings guides
  - `scripts/audit_static.py` — static checks (python3 stdlib only, read-only)
  - `scripts/frontmatter.py` — YAML frontmatter fallback parser (has `--self-test`)
  - `evals/` — guide-structured evaluations plus a deliberately broken fixture skill
- `README.md` — install paths per harness, standalone usage

## Working in this repo

- The skill must pass its own audit: run
  `python3 auditing-skills/scripts/audit_static.py auditing-skills` and
  `python3 auditing-skills/scripts/frontmatter.py --self-test` before committing
  changes to it. Heuristic flags on quoted examples are expected and dropped at
  judgment; only real regressions block.
- Changes to check definitions go in `references/audit-checks.md` first; the script's
  check IDs must stay in sync with it.
- The script never executes target-skill code; keep it that way.
