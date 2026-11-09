# rabbit-skills

Author, scaffold, audit, and deploy agent skills across 31 harnesses, and validate Claude Code, Codex, and DeepSeek Harness (DSH) plugins. Zero dependencies: everything runs on the Python 3 standard library.

## Skills

| Skill | What it does |
|---|---|
| [rabbit-skills-audit](skills/rabbit-skills-audit/) | Author, scaffold, and lint `SKILL.md` agent skills. 45 checks across metadata, structure, content, workflows, scripts, and evals, plus the official 22-item pre-share checklist and a placement engine for 31 harnesses. |
| [rabbit-plugin-audit](skills/rabbit-plugin-audit/) | Scaffold and lint Claude Code, Codex, and DeepSeek Harness plugins and marketplace catalogs. Checks across `plugin.json`, lifecycle hooks, MCP configs, Cordis patches, tools, and `marketplace.json`. |
| [rabbit-dsh](skills/rabbit-dsh/) | Unified DeepSeek Harness (DSH) studio: scaffold skills, Cordis plugins, and multi-agent workflows; manage MCP servers and settings; search 176 offline consolidated official and community documentation guides. |

Each skill is self-contained (`SKILL.md` workflow, `scripts/`, `references/`), so you can copy its directory into any harness as-is.

The companion [rabbit-writes](https://github.com/whit3rabbit/rabbit-writes) suite is also in this marketplace: six skills for writing and editing in your own voice, not a chatbot's. Voice profiles, AI-pattern scanning, and README and docs workflows. This README was written with it. Install it with `claude plugin install rabbit-writes`.

## Install

**Claude Code (recommended):**

```bash
claude plugin marketplace add whit3rabbit/rabbit-skills
claude plugin install rabbit-skills
```

**Codex:** add the same catalog and install from the Plugins Directory in the ChatGPT desktop app:

```bash
codex plugin marketplace add whit3rabbit/rabbit-skills
```

**Pi:** install as a package. The repo's root `skills/` directory matches Pi's conventional package layout, so all three skills are discovered without a manifest:

```bash
pi install git:github.com/whit3rabbit/rabbit-skills@main
```

**Hermes:** install through the skills hub, or copy into the Hermes-native paths:

```bash
# GitHub source, pattern: owner/repo/skill (scanned under the repo's skills/ directory)
hermes skills install whit3rabbit/rabbit-skills/rabbit-skills-audit
hermes skills install whit3rabbit/rabbit-skills/rabbit-plugin-audit
hermes skills install whit3rabbit/rabbit-skills/rabbit-dsh
```

Copy route: `.hermes/skills/` for project scope, `~/.hermes/skills/` for global. Run `hermes skills trust` inside the repo so project skills load.

**OpenCode:** discovers skills in `.agents/skills/`, so clone and copy:

```bash
git clone https://github.com/whit3rabbit/rabbit-skills.git
mkdir -p .agents/skills
cp -r rabbit-skills/skills/rabbit-skills-audit rabbit-skills/skills/rabbit-plugin-audit rabbit-skills/skills/rabbit-dsh .agents/skills/
```

Copy into `~/.agents/skills/` instead for all-user scope. OpenCode can also register the clone without copying:

```jsonc
// opencode.jsonc
{ "skills": ["/path/to/rabbit-skills/skills"] }
```

**DeepSeek Harness (DSH):** copy or link skills into `.dsh/skills/` (project) or `~/.dsh/skills/` (global):

```bash
mkdir -p .dsh/skills
cp -r rabbit-skills/skills/rabbit-skills-audit rabbit-skills/skills/rabbit-plugin-audit rabbit-skills/skills/rabbit-dsh .dsh/skills/
```

**Any other harness or CI:** clone and run the scripts directly. Python 3 standard library is all you need:

```bash
git clone https://github.com/whit3rabbit/rabbit-skills.git
```

**Deploy one skill into any of the 31 supported harnesses** (Claude Code, DeepSeek Harness, Cursor, Antigravity, Hermes, ...):

```bash
python3 skills/rabbit-skills-audit/scripts/scaffold_skill.py rabbit-skills-audit \
  --harness claude-code,cursor,dsh --scope project
```

Per-harness paths for all 31: [`references/harnesses/`](skills/rabbit-skills-audit/references/harnesses/).

## Use

```bash
# Audit a skill: markdown report, 45 checks + pre-share checklist
python3 skills/rabbit-skills-audit/scripts/audit_static.py /path/to/my-skill --format markdown --checklist

# Audit a plugin or marketplace catalog
python3 skills/rabbit-plugin-audit/scripts/audit_plugin.py /path/to/my-plugin --strict

# Scaffold a new skill ("born clean") with multi-harness placement
python3 skills/rabbit-skills-audit/scripts/scaffold_skill.py my-skill --harness claude-code --scope project

# DeepSeek Harness (DSH): search 176 offline docs (official + community), scaffold skills/plugins/workflows, manage MCP
python3 skills/rabbit-dsh/scripts/rabbit_dsh.py docs search "cordis tutorial"
python3 skills/rabbit-dsh/scripts/rabbit_dsh.py scaffold skill ./skills --name my-dsh-skill --type bundle
python3 skills/rabbit-dsh/scripts/rabbit_dsh.py scaffold plugin ./plugins --name @org/dsh-indexer --service indexer
python3 skills/rabbit-dsh/scripts/rabbit_dsh.py mcp add github --command npx --args -y @modelcontextprotocol/server-github
```

Audits are read-only (AST and regex only, so no target code is ever executed) and exit non-zero in `--strict` mode, ready for CI. Full check catalogs: [`audit-checks.md`](skills/rabbit-skills-audit/references/audit-checks.md) and [`plugin-marketplace-linting.md`](skills/rabbit-plugin-audit/references/plugin-marketplace-linting.md).

## License

Released under the MIT license. See [LICENSE](LICENSE).
