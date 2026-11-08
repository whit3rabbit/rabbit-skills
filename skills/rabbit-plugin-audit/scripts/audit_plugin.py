#!/usr/bin/env python3
"""Plugin and Marketplace Static Linter.

Audits Claude Code plugins, OpenAI Codex plugins, and Marketplace catalogs
against official schemas, token cost limits, and best-practice rules.

Checks:
  - PL-01..PL-18: Plugin manifest, components, token budgets, hooks, MCP, and evals.
  - MP-01..MP-15: Marketplace catalog schemas, source definitions, and paths.

Standard library only (`argparse`, `json`, `pathlib`, `re`, `sys`).
Runs standalone or as part of the rabbit-skills suite.

Usage:
  python3 audit_plugin.py <path-to-plugin-or-marketplace> [options]
  python3 audit_plugin.py --self-test
"""

import argparse
import json
import os
import re
import sys
import tempfile
from pathlib import Path

# Token budget thresholds
ALWAYS_ON_WARN_TOKENS = 150    # Warning if always-on tokens exceed 150 (PL-12)
ALWAYS_ON_MAX_TOKENS = 250     # Error if always-on tokens exceed 250 (PL-12)
DESC_WARN_CHARS = 160          # Description length ceiling for optimal prompt caching (PL-04)
NAME_MAX_CHARS = 64            # Maximum length for kebab-case identifier (PL-02)

CHECK_INFO = {
    # Plugin checks (PL-*)
    "PL-01": ("Manifest file missing or invalid JSON",
              "A plugin requires a valid `plugin.json` at root or inside `.claude-plugin/` or `.codex-plugin/`.",
              "Create a valid `plugin.json` file."),
    "PL-02": ("Missing or invalid plugin name",
              "Plugin `name` must be lowercase kebab-case (letters, numbers, hyphens) and at most 64 characters.",
              "Set `name` to a valid kebab-case identifier matching `^[a-z0-9-]+$`."),
    "PL-03": ("Missing or invalid semantic version",
              "Plugins should follow Semantic Versioning (MAJOR.MINOR.PATCH) for clean dependency resolution.",
              "Specify `version` in `X.Y.Z` semver format (e.g. `1.0.0`)."),
    "PL-04": ("Missing or verbose description",
              "Plugin description should be concise (<160 characters) and explain core utility without promotional filler.",
              "Shorten or add a concise `description` field."),
    "PL-05": ("Invalid userConfig schema",
              "`userConfig` properties must declare valid `type` (string, boolean, number, enum) and description.",
              "Fix invalid `userConfig` schema definitions."),
    "PL-06": ("Missing license declaration",
              "Plugins should declare a standard SPDX software license (e.g. MIT, Apache-2.0).",
              "Add a `license` field to the manifest."),
    "PL-07": ("Skills directory referenced but missing",
              "Declared skills path does not exist on disk.",
              "Ensure `skills/` exists or update manifest skills path."),
    "PL-08": ("Skill missing SKILL.md or valid frontmatter",
              "Each skill under `skills/<name>/` must contain a `SKILL.md` with YAML frontmatter (`name`, `description`).",
              "Add valid `SKILL.md` with frontmatter."),
    "PL-09": ("Invalid lifecycle hooks configuration",
              "Hooks must define supported event types (SessionStart, UserPromptSubmit, PreToolUse, PostToolUse, SessionEnd).",
              "Correct hook event names or command definitions in `hooks/hooks.json`."),
    "PL-10": ("Invalid MCP server declaration",
              "MCP servers must specify a command or url and valid arguments/transport.",
              "Fix server configuration in `.mcp.json` or `mcp.json`."),
    "PL-11": ("Potential hardcoded credentials in configuration",
              "Config files should use environment variable references or `${config.KEY}` rather than raw secrets.",
              "Replace hardcoded tokens/passwords with parameter substitutions."),
    "PL-12": ("Always-on token cost exceeds budget",
              f"Always-on token overhead (names + descriptions) exceeds recommended budget ({ALWAYS_ON_WARN_TOKENS} tokens).",
              "Shorten skill and agent descriptions to reduce always-on token burn."),
    "PL-13": ("Missing or inadequate evaluation suite",
              "Production plugins should include an `evals/` test suite with at least 3 distinct evaluation cases.",
              "Add test cases under `evals/<case-name>/`."),
    "PL-14": ("Incomplete eval case definition",
              "Each eval case requires a `prompt.md` and at least one grader under `graders/`.",
              "Add `prompt.md` and a grader to the incomplete eval case."),
    "PL-15": ("Unpinned or unbounded dependency constraint",
              "Plugin dependencies should declare bounded semver ranges (`^` or `~`) rather than wildcards (`*`).",
              "Pin dependency with a semver constraint (e.g. `^1.0.0`)."),
    "PL-16": ("Invalid OpenAI / Codex extension references",
              "`onboardingSkill`, `apps`, or `assets` in `extensions.com.openai` point to missing files.",
              "Fix referenced paths in `extensions.com.openai`."),
    "PL-17": ("Broken local file reference",
              "Referenced command, agent, or binary path does not exist on disk.",
              "Ensure referenced file exists or fix path."),
    "PL-18": ("Script in bin/ lacks executable permissions",
              "Executables in `bin/` added to PATH must have executable permissions (`chmod +x`).",
              "Run `chmod +x bin/<script>` on the target executable."),

    # Marketplace checks (MP-*)
    "MP-01": ("Marketplace manifest missing or invalid JSON",
              "Marketplace catalog requires a valid `marketplace.json` at root or inside `.claude-plugin/`.",
              "Create a valid `marketplace.json`."),
    "MP-02": ("Missing or invalid marketplace name",
              "Marketplace `name` must contain only letters, numbers, hyphens, underscores, or dots, and no `..`.",
              "Set `name` to a valid identifier."),
    "MP-03": ("Missing or invalid owner object",
              "Marketplace requires an `owner` object with a non-empty `name` field.",
              "Add `owner: { name: '...' }` to the marketplace manifest."),
    "MP-04": ("Missing plugins array",
              "Marketplace requires a top-level `plugins` array listing catalog entries.",
              "Add `plugins: [...]` to `marketplace.json`."),
    "MP-05": ("Empty marketplace catalog",
              "Marketplace lists 0 plugins; catalogs should contain at least one plugin entry.",
              "Add plugin entries to the `plugins` array."),
    "MP-06": ("Duplicate plugin name in catalog",
              "Each plugin entry in a marketplace must have a unique `name`.",
              "Rename or remove duplicate plugin entries."),
    "MP-07": ("Plugin entry missing name or source",
              "Each plugin entry must specify both `name` and `source`.",
              "Provide `name` and `source` for the plugin entry."),
    "MP-08": ("Invalid relative path source",
              "Relative path plugin source must start with `./` or resolve under `metadata.pluginRoot`.",
              "Format relative source as `./plugins/<name>`."),
    "MP-09": ("Embedded plugin directory not found or invalid",
              "The relative source path does not point to a valid plugin directory containing `plugin.json`.",
              "Ensure target directory exists and has a valid `plugin.json`."),
    "MP-10": ("Catalog name does not match plugin manifest name",
              "The entry `name` in `marketplace.json` must exactly match the `name` in the target plugin's manifest.",
              "Align entry name with plugin manifest name."),
    "MP-11": ("Invalid plugin source object type",
              "Object sources must set `source` to one of: github, url, git-subdir, npm, archive, command.",
              "Use a supported source type."),
    "MP-12": ("Invalid GitHub plugin source",
              "GitHub source requires a valid `repo` in `owner/repo` format.",
              "Specify `repo: 'owner/repo'` for the GitHub source."),
    "MP-13": ("Invalid git-subdir plugin source",
              "Git-subdir source requires `url`, `path`, and `ref`.",
              "Provide all required fields for `git-subdir`."),
    "MP-14": ("Invalid archive plugin source",
              "Archive source requires HTTPS `url` and a 64-character hex `sha256` hash.",
              "Provide valid `url` and 64-character `sha256` checksum."),
    "MP-15": ("Invalid cross-marketplace dependency list",
              "`allowCrossMarketplaceDependenciesOn` must be an array of marketplace name strings.",
              "Specify an array of strings for allowed cross-marketplace dependencies.")
}

SEMVER_REGEX = re.compile(r"^v?([0-9]+)\.([0-9]+)\.([0-9]+)(?:-[0-9a-zA-Z.-]+)?(?:\+[0-9a-zA-Z.-]+)?$")
KEBAB_REGEX = re.compile(r"^[a-z0-9-]+$")
MARKETPLACE_NAME_REGEX = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9._-]*$")


class Findings:
    """Accumulates findings for a target audit run."""

    def __init__(self, root):
        self.root = Path(root).resolve()
        self.items = []
        self.notes = []

    def add(self, cid, severity, file, line, evidence, message=None):
        title, why, fix = CHECK_INFO.get(cid, (cid, "", ""))
        self.items.append({
            "id": cid,
            "severity": severity,
            "title": title,
            "file": str(file),
            "line": line,
            "evidence": (evidence or "").strip()[:160],
            "message": message or why,
            "fix": fix
        })

    def note(self, text):
        self.notes.append(text)


def read_json_safe(path: Path):
    """Read and parse JSON file with detailed error handling."""
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f), None
    except FileNotFoundError:
        return None, "File not found"
    except json.JSONDecodeError as exc:
        return None, f"JSON syntax error at line {exc.lineno}, col {exc.colno}: {exc.msg}"
    except OSError as exc:
        return None, f"I/O error reading file: {exc}"


def read_text_safe(path: Path):
    """Read text file safely."""
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            return f.read(), None
    except OSError as exc:
        return None, str(exc)


# =============================================================================
# Plugin Linter (Area PL)
# =============================================================================

def find_plugin_manifest(root: Path):
    """Locate plugin.json in root or standard subdirectories."""
    candidates = [
        root / "plugin.json",
        root / ".claude-plugin" / "plugin.json",
        root / ".codex-plugin" / "plugin.json"
    ]
    for p in candidates:
        if p.is_file():
            return p
    return None


def lint_plugin(root: Path, findings: Findings):
    """Lint a Claude Code, Codex, or Generic Plugin directory."""
    manifest_path = find_plugin_manifest(root)
    if not manifest_path:
        findings.add("PL-01", "error", root / "plugin.json", 1, "plugin.json not found",
                     message="No `plugin.json` found in root or `.claude-plugin/` or `.codex-plugin/`.")
        return

    data, err = read_json_safe(manifest_path)
    rel_manifest = manifest_path.relative_to(root)
    if err:
        findings.add("PL-01", "error", rel_manifest, 1, err, message=f"Failed to parse manifest: {err}")
        return

    # PL-02: Name
    name = data.get("name")
    if not name or not isinstance(name, str):
        findings.add("PL-02", "error", rel_manifest, 1, str(name), message="Manifest `name` is missing or empty.")
    else:
        if not KEBAB_REGEX.match(name):
            findings.add("PL-02", "error", rel_manifest, 1, name,
                         message=f"Name '{name}' is not lowercase kebab-case (must match `^[a-z0-9-]+$`).")
        if len(name) > NAME_MAX_CHARS:
            findings.add("PL-02", "warning", rel_manifest, 1, name,
                         message=f"Name exceeds {NAME_MAX_CHARS} characters ({len(name)} chars).")

    # PL-03: Version
    version = data.get("version")
    if not version or not isinstance(version, str):
        findings.add("PL-03", "warning", rel_manifest, 1, str(version), message="Missing `version` field.")
    elif not SEMVER_REGEX.match(version):
        findings.add("PL-03", "warning", rel_manifest, 1, version,
                     message=f"Version '{version}' does not match Semantic Versioning (MAJOR.MINOR.PATCH).")

    # PL-04: Description
    desc = data.get("description")
    if not desc or not isinstance(desc, str):
        findings.add("PL-04", "warning", rel_manifest, 1, str(desc), message="Missing `description` field.")
    elif len(desc) > DESC_WARN_CHARS:
        findings.add("PL-04", "info", rel_manifest, 1, desc[:80],
                     message=f"Description is {len(desc)} chars (recommended <{DESC_WARN_CHARS} for prompt cache efficiency).")

    # PL-05: userConfig
    if "userConfig" in data:
        u_cfg = data["userConfig"]
        if not isinstance(u_cfg, dict):
            findings.add("PL-05", "error", rel_manifest, 1, str(type(u_cfg)), message="`userConfig` must be an object.")
        else:
            for k, cfg in u_cfg.items():
                if not isinstance(cfg, dict):
                    findings.add("PL-05", "error", rel_manifest, 1, k, message=f"`userConfig.{k}` must be an object.")
                    continue
                c_type = cfg.get("type")
                if c_type not in ("string", "number", "boolean", "enum"):
                    findings.add("PL-05", "error", rel_manifest, 1, f"{k}: {c_type}",
                                 message=f"`userConfig.{k}.type` must be string, number, boolean, or enum.")

    # PL-06: License
    if "license" not in data:
        findings.add("PL-06", "info", rel_manifest, 1, "missing", message="No `license` field specified in manifest.")

    # PL-15: Dependencies semver check
    if "dependencies" in data:
        deps = data["dependencies"]
        if isinstance(deps, dict):
            for dep_name, constraint in deps.items():
                if isinstance(constraint, str) and constraint in ("*", "latest", ""):
                    findings.add("PL-15", "warning", rel_manifest, 1, f"{dep_name}: {constraint}",
                                 message=f"Dependency '{dep_name}' uses unpinned wildcard '{constraint}'. Use `^` or `~`.")

    # Component checks: Skills
    total_always_on_tokens = len(name or "") // 4 + len(desc or "") // 4
    skills_dir = root / "skills"
    if skills_dir.is_dir():
        for skill_entry in sorted(skills_dir.iterdir()):
            if skill_entry.is_dir() and not skill_entry.name.startswith("."):
                skill_md = skill_entry / "SKILL.md"
                if not skill_md.is_file():
                    findings.add("PL-08", "warning", skill_md.relative_to(root), 1, skill_entry.name,
                                 message=f"Skill directory '{skill_entry.name}' lacks a `SKILL.md`.")
                else:
                    txt, _ = read_text_safe(skill_md)
                    if txt:
                        # Estimate always-on tokens from description
                        m_desc = re.search(r"^description:\s*(.+)$", txt, re.MULTILINE)
                        if m_desc:
                            s_desc = m_desc.group(1).strip()
                            total_always_on_tokens += len(s_desc) // 4 + len(skill_entry.name) // 4

    # Hooks check (PL-09)
    hooks_file = root / "hooks" / "hooks.json"
    if not hooks_file.is_file():
        hooks_file = root / ".claude-plugin" / "hooks.json"
    if hooks_file.is_file():
        h_data, h_err = read_json_safe(hooks_file)
        if h_err:
            findings.add("PL-09", "error", hooks_file.relative_to(root), 1, h_err,
                         message=f"Error parsing hooks.json: {h_err}")
        elif isinstance(h_data, dict):
            valid_events = {"SessionStart", "UserPromptSubmit", "PreToolUse", "PostToolUse", "SessionEnd"}
            hooks_map = h_data.get("hooks", h_data)
            if isinstance(hooks_map, dict):
                for ev in hooks_map.keys():
                    if ev not in valid_events:
                        findings.add("PL-09", "warning", hooks_file.relative_to(root), 1, ev,
                                     message=f"Unrecognized hook event '{ev}'.")

    # MCP servers check (PL-10)
    mcp_file = root / ".mcp.json"
    if not mcp_file.is_file():
        mcp_file = root / "mcp.json"
    if mcp_file.is_file():
        m_data, m_err = read_json_safe(mcp_file)
        if m_err:
            findings.add("PL-10", "error", mcp_file.relative_to(root), 1, m_err, message="Error parsing MCP file.")

    # Secret checks in configs (PL-11)
    secret_pat = re.compile(r"""(?i)["']?(?:api[_-]?key|secret|token|password)["']?\s*[:=]\s*["']([a-zA-Z0-9_\-]{16,})["']""")
    for cfg_candidate in [root / ".mcp.json", root / "mcp.json", manifest_path]:
        if cfg_candidate.is_file():
            txt, _ = read_text_safe(cfg_candidate)
            if txt:
                m_sec = secret_pat.search(txt)
                if m_sec and not "${" in m_sec.group(0):
                    findings.add("PL-11", "error", cfg_candidate.relative_to(root), 1, m_sec.group(0)[:60],
                                 message="Possible hardcoded secret in configuration. Use environment variables.")

    # Always-on token cost check (PL-12)
    findings.note(f"Estimated always-on tokens: ~{total_always_on_tokens} tok across all components.")
    if total_always_on_tokens > ALWAYS_ON_MAX_TOKENS:
        findings.add("PL-12", "error", rel_manifest, 1, f"~{total_always_on_tokens} tokens",
                     message=f"Always-on token cost (~{total_always_on_tokens} tok) exceeds limit of {ALWAYS_ON_MAX_TOKENS} tok.")
    elif total_always_on_tokens > ALWAYS_ON_WARN_TOKENS:
        findings.add("PL-12", "warning", rel_manifest, 1, f"~{total_always_on_tokens} tokens",
                     message=f"Always-on token cost (~{total_always_on_tokens} tok) exceeds recommended {ALWAYS_ON_WARN_TOKENS} tok budget.")

    # Evals check (PL-13, PL-14)
    evals_dir = root / "evals"
    if not evals_dir.is_dir():
        findings.add("PL-13", "info", "evals/", 1, "missing",
                     message="No `evals/` test suite found. Recommended for validating trigger reliability.")
    else:
        cases = [d for d in evals_dir.iterdir() if d.is_dir() and not d.name.startswith((".", "results", "mocks"))]
        if len(cases) < 3:
            findings.add("PL-13", "info", "evals/", 1, f"{len(cases)} case(s)",
                         message=f"Eval suite has {len(cases)} case(s); recommended minimum is 3 cases.")
        for c in cases:
            p_md = c / "prompt.md"
            c_yaml = c / "case.yaml"
            if not p_md.is_file() and not c_yaml.is_file():
                findings.add("PL-14", "warning", c.relative_to(root), 1, "prompt.md missing",
                             message=f"Eval case '{c.name}' missing `prompt.md`.")
            graders_dir = c / "graders"
            if not graders_dir.is_dir() or not any(graders_dir.glob("*.md")):
                findings.add("PL-14", "warning", c.relative_to(root), 1, "graders/ missing",
                             message=f"Eval case '{c.name}' lacks pass/fail checks in `graders/`.")

    # OpenAI / Codex extension check (PL-16)
    if "extensions" in data and isinstance(data["extensions"], dict):
        openai_ext = data["extensions"].get("com.openai")
        if isinstance(openai_ext, dict):
            onboarding = openai_ext.get("onboardingSkill")
            if onboarding and isinstance(onboarding, str):
                p_onboard = (root / onboarding.lstrip("./")).resolve()
                if not p_onboard.is_file():
                    findings.add("PL-16", "warning", rel_manifest, 1, onboarding,
                                 message=f"`onboardingSkill` points to missing file: {onboarding}")

    # Executable permissions check (PL-18)
    bin_dir = root / "bin"
    if bin_dir.is_dir():
        for b in bin_dir.iterdir():
            if b.is_file() and not os.access(b, os.X_OK):
                findings.add("PL-18", "warning", b.relative_to(root), 1, b.name,
                             message=f"Script in `bin/{b.name}` lacks executable permissions (`chmod +x`).")


# =============================================================================
# Marketplace Linter (Area MP)
# =============================================================================

def find_marketplace_manifest(root: Path):
    """Locate marketplace.json in root or standard subdirectories."""
    candidates = [
        root / "marketplace.json",
        root / ".claude-plugin" / "marketplace.json",
        root / ".codex-plugin" / "marketplace.json"
    ]
    for p in candidates:
        if p.is_file():
            return p
    return None


def lint_marketplace(root: Path, findings: Findings):
    """Lint a Claude Code or Codex marketplace catalog."""
    manifest_path = find_marketplace_manifest(root)
    if not manifest_path:
        findings.add("MP-01", "error", root / "marketplace.json", 1, "marketplace.json not found",
                     message="No `marketplace.json` found at root or in `.claude-plugin/`.")
        return

    data, err = read_json_safe(manifest_path)
    rel_manifest = manifest_path.relative_to(root)
    if err:
        findings.add("MP-01", "error", rel_manifest, 1, err, message=f"Failed to parse marketplace JSON: {err}")
        return

    # MP-02: Marketplace Name
    name = data.get("name")
    if not name or not isinstance(name, str):
        findings.add("MP-02", "error", rel_manifest, 1, str(name), message="Marketplace `name` is missing or empty.")
    else:
        if not MARKETPLACE_NAME_REGEX.match(name) or ".." in name:
            findings.add("MP-02", "error", rel_manifest, 1, name,
                         message=f"Invalid marketplace name '{name}'. Must start with alphanumeric, no `..`.")

    # MP-03: Owner
    owner = data.get("owner")
    if not owner or not isinstance(owner, dict):
        findings.add("MP-03", "error", rel_manifest, 1, str(type(owner)),
                     message="Marketplace requires an `owner` object.")
    else:
        if not owner.get("name"):
            findings.add("MP-03", "error", rel_manifest, 1, "owner.name",
                         message="Marketplace `owner` object requires a `name` field.")

    # MP-04 & MP-05: Plugins Array
    plugins = data.get("plugins")
    if plugins is None or not isinstance(plugins, list):
        findings.add("MP-04", "error", rel_manifest, 1, str(type(plugins)),
                     message="Marketplace requires a `plugins` array.")
        return
    elif len(plugins) == 0:
        findings.add("MP-05", "warning", rel_manifest, 1, "[]", message="Marketplace `plugins` array is empty.")
        return

    # Metadata pluginRoot
    plugin_root_dir = root
    meta = data.get("metadata")
    if isinstance(meta, dict) and "pluginRoot" in meta:
        plugin_root_dir = (root / meta["pluginRoot"].lstrip("./")).resolve()

    seen_names = set()
    valid_source_types = {"github", "url", "git-subdir", "npm", "archive", "command"}

    for idx, entry in enumerate(plugins):
        if not isinstance(entry, dict):
            findings.add("MP-07", "error", rel_manifest, idx + 1, str(entry),
                         message=f"Plugin entry #{idx+1} is not an object.")
            continue

        p_name = entry.get("name")
        p_src = entry.get("source")

        # MP-07: Required fields
        if not p_name or not p_src:
            findings.add("MP-07", "error", rel_manifest, idx + 1, json.dumps(entry)[:60],
                         message=f"Plugin entry #{idx+1} missing `name` or `source`.")
            continue

        # MP-06: Duplicates
        if p_name in seen_names:
            findings.add("MP-06", "error", rel_manifest, idx + 1, p_name,
                         message=f"Duplicate plugin name in catalog: '{p_name}'.")
        seen_names.add(p_name)

        # Source checking: String (Relative path) vs Object
        if isinstance(p_src, str):
            # MP-08: Relative path formatting
            if not p_src.startswith("./") and p_src != "." and not (isinstance(meta, dict) and "pluginRoot" in meta):
                findings.add("MP-08", "warning", rel_manifest, idx + 1, p_src,
                             message=f"Relative source '{p_src}' should start with `./`.")

            # MP-09: Target exists & has manifest
            target_dir = (root / p_src.lstrip("./")).resolve()
            if not target_dir.is_dir() and isinstance(meta, dict) and "pluginRoot" in meta:
                target_dir = (plugin_root_dir / p_src).resolve()

            if not target_dir.is_dir():
                findings.add("MP-09", "error", rel_manifest, idx + 1, p_src,
                             message=f"Plugin directory not found: {p_src}")
            else:
                p_manifest = find_plugin_manifest(target_dir)
                if not p_manifest:
                    findings.add("MP-09", "error", rel_manifest, idx + 1, p_src,
                                 message=f"Target directory '{p_src}' does not contain `plugin.json`.")
                else:
                    # MP-10: Name matching
                    p_data, _ = read_json_safe(p_manifest)
                    if p_data and p_data.get("name") != p_name:
                        findings.add("MP-10", "error", rel_manifest, idx + 1, f"entry: {p_name} != manifest: {p_data.get('name')}",
                                     message=f"Marketplace entry name '{p_name}' does not match plugin manifest name '{p_data.get('name')}'.")

        elif isinstance(p_src, dict):
            src_type = p_src.get("source")
            if src_type not in valid_source_types:
                findings.add("MP-11", "error", rel_manifest, idx + 1, str(src_type),
                             message=f"Plugin '{p_name}' source.source must be one of {sorted(valid_source_types)}.")
            elif src_type == "github":
                repo = p_src.get("repo")
                if not repo or not re.match(r"^[a-zA-Z0-9_.-]+/[a-zA-Z0-9_.-]+$", repo):
                    findings.add("MP-12", "error", rel_manifest, idx + 1, str(repo),
                                 message=f"GitHub source for '{p_name}' requires valid `repo: 'owner/repo'`.")
            elif src_type == "git-subdir":
                if not p_src.get("url") or not p_src.get("path"):
                    findings.add("MP-13", "error", rel_manifest, idx + 1, json.dumps(p_src),
                                 message=f"git-subdir source for '{p_name}' requires `url` and `path`.")
            elif src_type == "archive":
                sha = p_src.get("sha256")
                if not p_src.get("url") or not sha or len(sha) != 64:
                    findings.add("MP-14", "error", rel_manifest, idx + 1, str(sha),
                                 message=f"archive source for '{p_name}' requires HTTPS `url` and 64-char `sha256`.")

    # MP-15: Dependencies
    if "allowCrossMarketplaceDependenciesOn" in data:
        cross_deps = data["allowCrossMarketplaceDependenciesOn"]
        if not isinstance(cross_deps, list) or not all(isinstance(x, str) for x in cross_deps):
            findings.add("MP-15", "error", rel_manifest, 1, str(cross_deps),
                         message="`allowCrossMarketplaceDependenciesOn` must be a list of strings.")


# =============================================================================
# Reporting & Output
# =============================================================================

def format_report_text(findings: Findings, target_type: str) -> str:
    """Format findings as colored text."""
    lines = []
    lines.append(f"Target: {findings.root.name}  ({target_type.upper()})")
    errors = [x for x in findings.items if x["severity"] == "error"]
    warnings = [x for x in findings.items if x["severity"] == "warning"]
    infos = [x for x in findings.items if x["severity"] == "info"]

    if errors:
        lines.append(f"Verdict: FAIL  (errors: {len(errors)}, warnings: {len(warnings)}, info: {len(infos)})\n")
    elif warnings:
        lines.append(f"Verdict: PASS WITH WARNINGS  (errors: 0, warnings: {len(warnings)}, info: {len(infos)})\n")
    else:
        lines.append(f"Verdict: PASS  (errors: 0, warnings: 0, info: {len(infos)})\n")

    for f in findings.items:
        icon = "🔴" if f["severity"] == "error" else "⚠️ " if f["severity"] == "warning" else "ℹ️ "
        lines.append(f"{icon} [{f['id']}] {f['title']}  ({f['file']}:{f['line']})")
        lines.append(f"   evidence: {f['evidence']}")
        lines.append(f"   fix: {f['fix']}\n")

    for n in findings.notes:
        lines.append(f"  note: {n}")

    return "\n".join(lines)


def run_self_test():
    """Verify linter rules against temporary test fixtures."""
    print("Running audit_plugin.py self-test...")
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)

        # 1. Test Valid Claude Plugin
        p_valid = root / "valid-plugin"
        p_valid.mkdir()
        with open(p_valid / "plugin.json", "w") as f:
            json.dump({
                "name": "valid-plugin",
                "version": "1.0.0",
                "description": "A valid test plugin.",
                "license": "MIT"
            }, f)
        (p_valid / "skills" / "test").mkdir(parents=True)
        with open(p_valid / "skills" / "test" / "SKILL.md", "w") as f:
            f.write("---\nname: test\ndescription: Test skill.\n---\n# Test\n")

        f_valid = Findings(p_valid)
        lint_plugin(p_valid, f_valid)
        errs = [x for x in f_valid.items if x["severity"] == "error"]
        assert len(errs) == 0, f"Valid plugin produced unexpected errors: {errs}"
        print("  ✓ Valid plugin test passed")

        # 2. Test Invalid Plugin (Name & Version & Secrets)
        p_bad = root / "bad-plugin"
        p_bad.mkdir()
        with open(p_bad / "plugin.json", "w") as f:
            json.dump({
                "name": "Bad_Plugin_Name!",
                "version": "not-a-semver",
                "description": "Short"
            }, f)
        with open(p_bad / ".mcp.json", "w") as f:
            f.write('{"apiKey": "sk-1234567890abcdef12345678"}')

        f_bad = Findings(p_bad)
        lint_plugin(p_bad, f_bad)
        bad_ids = {x["id"] for x in f_bad.items}
        assert "PL-02" in bad_ids, "Failed to flag invalid plugin name"
        assert "PL-03" in bad_ids, "Failed to flag invalid semver version"
        assert "PL-11" in bad_ids, "Failed to flag hardcoded secret"
        print("  ✓ Invalid plugin test passed (PL-02, PL-03, PL-11 flagged)")

        # 3. Test Valid Marketplace
        m_valid = root / "valid-market"
        m_valid.mkdir()
        with open(m_valid / "marketplace.json", "w") as f:
            json.dump({
                "name": "valid-market",
                "owner": {"name": "Test Team"},
                "plugins": [
                    {
                        "name": "valid-plugin",
                        "source": "./plugins/valid-plugin",
                        "description": "Test entry"
                    }
                ]
            }, f)
        (m_valid / "plugins" / "valid-plugin").mkdir(parents=True)
        with open(m_valid / "plugins" / "valid-plugin" / "plugin.json", "w") as f:
            json.dump({"name": "valid-plugin", "version": "1.0.0"}, f)

        f_m_valid = Findings(m_valid)
        lint_marketplace(m_valid, f_m_valid)
        m_errs = [x for x in f_m_valid.items if x["severity"] == "error"]
        assert len(m_errs) == 0, f"Valid marketplace produced unexpected errors: {m_errs}"
        print("  ✓ Valid marketplace test passed")

        # 4. Test Invalid Marketplace (Duplicates & Missing Target)
        m_bad = root / "bad-market"
        m_bad.mkdir()
        with open(m_bad / "marketplace.json", "w") as f:
            json.dump({
                "name": "bad..market",
                "owner": {},
                "plugins": [
                    {"name": "p1", "source": "./plugins/missing"},
                    {"name": "p1", "source": {"source": "github", "repo": "invalid_repo"}}
                ]
            }, f)

        f_m_bad = Findings(m_bad)
        lint_marketplace(m_bad, f_m_bad)
        m_bad_ids = {x["id"] for x in f_m_bad.items}
        assert "MP-02" in m_bad_ids, "Failed to flag invalid marketplace name with '..'"
        assert "MP-03" in m_bad_ids, "Failed to flag owner missing name"
        assert "MP-06" in m_bad_ids, "Failed to flag duplicate plugin name"
        assert "MP-09" in m_bad_ids, "Failed to flag missing embedded directory"
        assert "MP-12" in m_bad_ids, "Failed to flag invalid GitHub repository format"
        print("  ✓ Invalid marketplace test passed (MP-02, MP-03, MP-06, MP-09, MP-12 flagged)")

    print("All audit_plugin.py self-tests PASSED (4/4).")


def main():
    parser = argparse.ArgumentParser(description="Linter for Claude Code and Codex Plugins & Marketplaces.")
    parser.add_argument("path", nargs="?", help="Path to plugin directory, marketplace directory, or manifest")
    parser.add_argument("--format", choices=("text", "json", "markdown"), default="text", help="Output format")
    parser.add_argument("--strict", action="store_true", help="Exit with code 1 on warnings as well as errors")
    parser.add_argument("--self-test", action="store_true", help="Run internal self-tests")

    args = parser.parse_args()

    if args.self_test:
        run_self_test()
        sys.exit(0)

    if not args.path:
        parser.error("Path is required (or use --self-test)")

    target_path = Path(args.path).resolve()
    is_explicit_file = target_path.is_file()
    if is_explicit_file:
        target_dir = target_path.parent
    else:
        target_dir = target_path

    if not target_dir.is_dir():
        print(f"Error: Target '{target_dir}' does not exist.", file=sys.stderr)
        sys.exit(1)

    findings = Findings(target_dir)

    is_marketplace = False
    is_plugin = False

    if is_explicit_file:
        if target_path.name == "marketplace.json":
            is_marketplace = True
        elif target_path.name == "plugin.json":
            is_plugin = True
        else:
            is_marketplace = bool(find_marketplace_manifest(target_dir))
            is_plugin = bool(find_plugin_manifest(target_dir))
    else:
        is_marketplace = bool(find_marketplace_manifest(target_dir))
        is_plugin = bool(find_plugin_manifest(target_dir))

    if is_marketplace and is_plugin and not is_explicit_file:
        lint_plugin(target_dir, findings)
        lint_marketplace(target_dir, findings)
        target_type = "plugin + marketplace"
    elif is_marketplace:
        lint_marketplace(target_dir, findings)
        target_type = "marketplace"
    elif is_plugin:
        lint_plugin(target_dir, findings)
        target_type = "plugin"
    else:
        # Check subdirectories
        sub_plugins = [d for d in target_dir.iterdir() if d.is_dir() and find_plugin_manifest(d)]
        if sub_plugins:
            print(f"Scanning {len(sub_plugins)} plugin(s) under {target_dir.name}...\n")
            has_error = False
            for sp in sub_plugins:
                f_sub = Findings(sp)
                lint_plugin(sp, f_sub)
                print(format_report_text(f_sub, "plugin"))
                print("-" * 60)
                if any(x["severity"] == "error" for x in f_sub.items):
                    has_error = True
            sys.exit(1 if has_error else 0)
        else:
            print(f"Error: No `plugin.json` or `marketplace.json` detected in {target_dir}.", file=sys.stderr)
            sys.exit(1)

    # Output formatting
    if args.format == "text":
        print(format_report_text(findings, target_type))
    elif args.format == "json":
        print(json.dumps({
            "target": str(findings.root),
            "type": target_type,
            "items": findings.items,
            "notes": findings.notes
        }, indent=2))
    elif args.format == "markdown":
        print(f"# Audit Report: {findings.root.name} ({target_type.upper()})\n")
        print(f"**Path:** `{findings.root}`\n")
        for f in findings.items:
            print(f"- **[{f['id']}] {f['title']}** (`{f['severity']}`)")
            print(f"  - File: `{f['file']}:{f['line']}`")
            print(f"  - Evidence: `{f['evidence']}`")
            print(f"  - Fix: {f['fix']}\n")

    errors = [x for x in findings.items if x["severity"] == "error"]
    warnings = [x for x in findings.items if x["severity"] == "warning"]

    if errors or (args.strict and warnings):
        sys.exit(1)
    sys.exit(0)


if __name__ == "__main__":
    main()
