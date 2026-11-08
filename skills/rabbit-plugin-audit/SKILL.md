---
name: rabbit-plugin-audit
description: Scaffold, audit, lint, and validate Claude Code and Codex plugins and marketplaces against PL-01..PL-18 and MP-01..MP-15. Use when packaging, linting, or releasing plugins.
---

# Auditing and Scaffolding Agent Plugins & Marketplaces

Scaffold, audit, and validate plugins and marketplace catalogs across Claude Code, OpenAI Codex, and portable agent standards.

## Mental model: Skills vs. Plugins vs. Marketplaces

- **Skill (`SKILL.md`):** Instructions, procedural guidance, and scripts loaded dynamically by an agent.
- **Plugin (`plugin.json`):** A distributable bundle that packages skills, lifecycle hooks, commands, agents, and MCP servers into a versioned unit.
- **Marketplace (`marketplace.json`):** A catalog indexing plugins (either local monorepos or remote git repositories) for user discovery and installation.

## Auditable Areas & Linter Rules

`scripts/audit_plugin.py` provides static validation with zero dependencies (Python stdlib):

| Target | Linter Checks | What is validated |
|---|---|---|
| **Plugin Manifest** | PL-01 – PL-08 | `plugin.json` structure, naming conventions (`kebab-case`), semver, required metadata, descriptions. |
| **Component Layout** | PL-09 – PL-12 | Canonical paths (`skills/`, `hooks/`, `commands/`, `agents/`), component discoverability, no orphan files. |
| **Hooks & Lifecycle** | PL-13 – PL-15 | Hook event triggers (`PreToolUse`, `PostToolUse`, etc.), JSON schema, executable target scripts. |
| **MCP & Config** | PL-16 – PL-18 | `.mcp.json` or manifest `mcpServers`, environment variables, config substitutions `${config.<key>}`. |
| **Marketplace Catalog** | MP-01 – MP-15 | `marketplace.json` schema, plugin listings, local vs. remote git sources, categories, unique identifiers. |

Read [`references/plugin-marketplace-linting.md`](references/plugin-marketplace-linting.md) for detailed descriptions, severity levels, and good/bad examples for all checks.

## Safety rules

- **Read-only audit:** Never execute plugin hook scripts, binaries, or MCP servers during audit.
- **Stateless verification:** Check path existence, file permissions, and JSON schemas without modifying the target workspace.

## Task Routing

| Task Mode | Intent / Trigger Keywords | Action Sequence |
|---|---|---|
| **Mode 1: Create Plugin / Marketplace** | "create plugin", "scaffold plugin", "new marketplace", "package my skill" | Run `scripts/scaffold_plugin.py` |
| **Mode 2: Audit Plugin** | "audit plugin", "lint plugin", "check plugin.json", "validate plugin" | Run `scripts/audit_plugin.py <plugin-dir> [--strict]` |
| **Mode 3: Audit Marketplace** | "audit marketplace", "lint marketplace", "check marketplace.json" | Run `scripts/audit_plugin.py <marketplace.json> [--strict]` |
| **Mode 4: Fix / Improve** | "fix plugin warnings", "prepare plugin for release", "make marketplace pass" | Apply findings and re-verify |

---

### Mode 1: Scaffold a Plugin or Marketplace

```bash
# Scaffold a Claude Code plugin with a skill and hook:
python3 scripts/scaffold_plugin.py my-plugin --target claude-code --components skill,hook

# Scaffold an OpenAI Codex portable plugin:
python3 scripts/scaffold_plugin.py my-plugin --target codex --components skill,mcp

# Scaffold a marketplace catalog:
python3 scripts/scaffold_plugin.py my-marketplace --target claude-code --components marketplace
```

---

### Mode 2: Audit a Plugin

Run `scripts/audit_plugin.py` against the root of a plugin repository or directory containing `plugin.json`:

```bash
# Markdown report to terminal:
python3 scripts/audit_plugin.py <path-to-plugin> --format markdown

# JSON output for CI / automation:
python3 scripts/audit_plugin.py <path-to-plugin> --format json --strict
```

---

### Mode 3: Audit a Marketplace Catalog

Run `scripts/audit_plugin.py` pointing directly to `marketplace.json` or a marketplace repo root:

```bash
python3 scripts/audit_plugin.py path/to/marketplace.json --strict
```

The linter validates both the top-level catalog format and each referenced plugin's metadata.

---

### Mode 4: Fix & Release Verification

1. Examine the generated audit report (`PASS`, `PASS WITH WARNINGS`, or `FAIL`).
2. Update `plugin.json` or `marketplace.json` to resolve any identified errors (missing fields, invalid semver, broken path references).
3. Re-run `python3 scripts/audit_plugin.py <path> --strict` until 0 errors remain.

## References

- [`references/claude-plugins.md`](references/claude-plugins.md): Comprehensive Claude Code plugins specification (manifests, hooks, MCP, marketplaces)
- [`references/codex-plugins.md`](references/codex-plugins.md): OpenAI Codex & ChatGPT plugins guide (portable manifests, auth, extensions)
- [`references/plugin-marketplace-linting.md`](references/plugin-marketplace-linting.md): Full check specifications (PL-01..PL-18, MP-01..MP-15)
- [`scripts/audit_plugin.py`](scripts/audit_plugin.py): Static linter for plugins and marketplaces (`--self-test` supported)
- [`scripts/scaffold_plugin.py`](scripts/scaffold_plugin.py): Plugin and marketplace scaffolding utility (`--self-test` supported)
