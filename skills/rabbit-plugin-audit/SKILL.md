---
name: rabbit-plugin-audit
description: Scaffold, audit, lint, and validate Claude Code, Codex, and DeepSeek Harness (DSH) plugins and marketplaces. Use when packaging, linting, or releasing plugins.
---

# Auditing and Scaffolding Agent Plugins & Marketplaces

Scaffold, audit, and validate plugins and marketplace catalogs across Claude Code, OpenAI Codex, DeepSeek Harness (DSH), and portable agent standards.

## Mental model: Skills vs. Plugins vs. Marketplaces

- **Skill (`SKILL.md`):** Instructions, procedural guidance, and scripts loaded dynamically by an agent.
- **Plugin (`plugin.json` or `package.json` with Cordis patch):** A distributable bundle that packages skills, lifecycle hooks, commands, agents, tools, and MCP servers into a versioned unit.
- **Marketplace (`marketplace.json`):** A catalog indexing plugins (either local monorepos or remote git repositories) for user discovery and installation.

## Auditable Areas & Linter Rules

`scripts/audit_plugin.py` and `scripts/audit_dsh.py` provide static validation with zero dependencies (Python stdlib):

| Target | Linter Checks | What is validated |
|---|---|---|
| **Plugin Manifest** | PL-01 – PL-08 | `plugin.json` structure, naming conventions (`kebab-case`), semver, required metadata, descriptions. |
| **Component Layout** | PL-09 – PL-12 | Canonical paths (`skills/`, `hooks/`, `commands/`, `agents/`), component discoverability, no orphan files. |
| **Hooks & Lifecycle** | PL-13 – PL-15 | Hook event triggers (`PreToolUse`, `PostToolUse`, etc.), JSON schema, executable target scripts. |
| **MCP & Config** | PL-16 – PL-18 | `.mcp.json` or manifest `mcpServers`, environment variables, config substitutions `${config.<key>}`. |
| **Marketplace Catalog** | MP-01 – MP-15 | `marketplace.json` schema, plugin listings, local vs. remote git sources, categories, unique identifiers. |
| **DeepSeek Harness** | DSH-01 – DSH-12 | `package.json` (`dsh.bundle.patch`), Cordis patch YAML, entrypoint `apply(ctx)`, tool definitions (`defineTool`), events, presets. |

Read [`references/plugin-marketplace-linting.md`](references/plugin-marketplace-linting.md) for detailed descriptions, severity levels, and good/bad examples for all checks.

## Safety rules

- **Read-only audit:** Never execute plugin hook scripts, binaries, or MCP servers during audit.
- **Stateless verification:** Check path existence, file permissions, and JSON schemas without modifying the target workspace.

## Task Routing

| Task Mode | Intent / Trigger Keywords | Action Sequence |
|---|---|---|
| **Mode 1: Create Plugin / Marketplace** | "create plugin", "scaffold plugin", "new marketplace", "package my skill" | Run `scripts/scaffold_plugin.py` |
| **Mode 2: Audit Plugin** | "audit plugin", "lint plugin", "check plugin.json", "validate plugin" | Run `scripts/audit_plugin.py <plugin-dir> [--strict]` |
| **Mode 3: Audit DSH Plugin** | "audit dsh", "lint cordis", "check dsh plugin", "validate deepseek harness" | Run `scripts/audit_dsh.py <dsh-plugin-dir> [--strict]` |
| **Mode 4: Audit Marketplace** | "audit marketplace", "lint marketplace", "check marketplace.json" | Run `scripts/audit_plugin.py <marketplace.json> [--strict]` |
| **Mode 5: Fix / Improve** | "fix plugin warnings", "prepare plugin for release", "make marketplace pass" | Apply findings and re-verify |

---

### Mode 1: Scaffold a Plugin or Marketplace

```bash
# Scaffold a Claude Code plugin with a skill and hook:
python3 scripts/scaffold_plugin.py my-plugin --harness claude

# Scaffold an OpenAI Codex portable plugin:
python3 scripts/scaffold_plugin.py my-plugin --harness codex

# Scaffold a DeepSeek Harness (Cordis) plugin bundle with tools and events:
python3 scripts/scaffold_plugin.py my-plugin --harness dsh
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

### Mode 3: Audit a DeepSeek Harness (DSH) Plugin or Preset

Run `scripts/audit_dsh.py` against a DSH plugin bundle directory containing `package.json` and `cordis.patch.yml`:

```bash
# Markdown report to terminal:
python3 scripts/audit_dsh.py <path-to-dsh-plugin> --format markdown

# Strict validation:
python3 scripts/audit_dsh.py <path-to-dsh-plugin> --strict
```

---

### Mode 4: Audit a Marketplace Catalog

Run `scripts/audit_plugin.py` pointing directly to `marketplace.json` or a marketplace repo root:

```bash
python3 scripts/audit_plugin.py path/to/marketplace.json --strict
```

The linter validates both the top-level catalog format and each referenced plugin's metadata.

---

### Mode 5: Fix & Release Verification

1. Examine the generated audit report (`PASS`, `PASS WITH WARNINGS`, or `FAIL`).
2. Update manifests or configs to resolve any identified errors.
3. Re-run verification until 0 errors remain.

## References

- [`references/claude-plugins.md`](references/claude-plugins.md): Comprehensive Claude Code plugins specification (manifests, hooks, MCP, marketplaces)
- [`references/codex-plugins.md`](references/codex-plugins.md): OpenAI Codex & ChatGPT plugins guide (portable manifests, auth, extensions)
- [`references/deepseek-harness-plugins.md`](references/deepseek-harness-plugins.md): DeepSeek Harness (DSH) plugin architecture, Cordis patches, tool authoring, and events
- [`references/plugin-marketplace-linting.md`](references/plugin-marketplace-linting.md): Full check specifications (PL-01..PL-18, MP-01..MP-15, DSH-01..DSH-12)
- [`scripts/audit_plugin.py`](scripts/audit_plugin.py): Static linter for plugins and marketplaces (`--self-test` supported)
- [`scripts/audit_dsh.py`](scripts/audit_dsh.py): Static linter for DeepSeek Harness plugins (`--self-test` supported)
- [`scripts/scaffold_plugin.py`](scripts/scaffold_plugin.py): Plugin and marketplace scaffolding utility (`--self-test` supported)
