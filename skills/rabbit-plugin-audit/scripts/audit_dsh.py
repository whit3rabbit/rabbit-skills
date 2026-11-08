#!/usr/bin/env python3
"""DeepSeek Harness (DSH) Plugin and Component Static Linter.

Audits DeepSeek Harness (DSH) plugins, Cordis patch manifests, tools, event systems,
and agent presets against official architecture standards and safety best practices.

Checks:
  - DSH-01..DSH-12: Package manifest, Cordis patches, tools, events, personas, secrets.

Standard library only (`argparse`, `json`, `pathlib`, `re`, `sys`).
Runs standalone or as part of the rabbit-skills suite.

Usage:
  python3 audit_dsh.py <path-to-dsh-plugin-or-preset> [options]
  python3 audit_dsh.py --self-test
"""

import argparse
import json
import os
import re
import sys
import tempfile
from pathlib import Path

CHECK_INFO = {
    "DSH-01": (
        "Package manifest missing or invalid JSON",
        "A DeepSeek Harness plugin bundle requires a valid `package.json` at root.",
        "Create a valid `package.json` file at the plugin root."
    ),
    "DSH-02": (
        "Missing or invalid package name or version",
        "Plugin `name` must be lowercase kebab-case (optionally scoped as `@scope/name`) and `version` must follow semver.",
        "Set `name` to a valid identifier and `version` to semver (e.g. `1.0.0`)."
    ),
    "DSH-03": (
        "Missing or invalid DSH extension configuration",
        "A DSH plugin bundle must declare `dsh.bundle.patch` pointing to its Cordis patch file (or `dsh.profile` for profiles).",
        "Add `\"dsh\": { \"bundle\": { \"patch\": \"./cordis.patch.yml\" } }` to `package.json`."
    ),
    "DSH-04": (
        "Patch file missing or invalid path",
        "The Cordis patch file referenced in `dsh.bundle.patch` does not exist on disk.",
        "Create the referenced patch file (e.g. `cordis.patch.yml`) or update `dsh.bundle.patch`."
    ),
    "DSH-05": (
        "Invalid Cordis patch structure",
        "Cordis patch file must be a valid YAML structure defining operations (e.g. `insert`) with `id` and `name`.",
        "Structure `cordis.patch.yml` as a list with `- insert: [ { id, name } ]`."
    ),
    "DSH-06": (
        "Entrypoint module missing",
        "Module entrypoint declared by `main` (or fallback `src/index.ts` / `index.js`) does not exist on disk.",
        "Ensure the entrypoint file exists or update `main` in `package.json`."
    ),
    "DSH-07": (
        "Missing required plugin exports",
        "DSH plugin entrypoint module must export a string `name` and an `apply(ctx)` function.",
        "Export `name` (e.g. `export const name = '...'`) and `apply` (e.g. `export function apply(ctx) { ... }`)."
    ),
    "DSH-08": (
        "Missing service dependency injection declaration",
        "Plugin utilizes framework services (e.g. `tools`, `persona`) but does not declare them in `export const inject = [...]`.",
        "Add `export const inject = ['tools']` to the entrypoint module."
    ),
    "DSH-09": (
        "Invalid or incomplete tool definition",
        "Tools defined with `defineTool` must declare `name`, `description`, and an `execute` function.",
        "Provide `name`, `description`, and `execute` in `defineTool({ ... })`."
    ),
    "DSH-10": (
        "Non-standard event system naming convention",
        "Event names registered with `ctx.on` or emitted with `ctx.emit` should follow the `namespace/action` convention.",
        "Use `namespace/action` naming for events (e.g. `tools/result`, `agent/turn-start`)."
    ),
    "DSH-11": (
        "Invalid persona or agent preset configuration",
        "Agent presets (`agent.cordis.yml`) must define `name` and at least `persona` or `tools`.",
        "Provide valid `name` and `persona` / `tools` fields in `agent.cordis.yml`."
    ),
    "DSH-12": (
        "Potential hardcoded credentials in configuration",
        "Configuration patches, manifests, or code files must not contain hardcoded API keys, tokens, or plaintext secrets.",
        "Replace raw secrets with environment variables or configuration parameters."
    ),
    "DSH-13": (
        "Missing Typert export in package manifest",
        "Plugin defines Typert RPC contracts (@Remote) but does not declare `./typert` in package.json `exports`.",
        "Add `\"./typert\": \"./dist/typert/index.js\"` to `package.json` `exports`."
    ),
}

SEMVER_REGEX = re.compile(r"^v?([0-9]+)\.([0-9]+)\.([0-9]+)(?:-[0-9a-zA-Z.-]+)?(?:\+[0-9a-zA-Z.-]+)?$")
PKG_NAME_REGEX = re.compile(r"^(?:@[a-z0-9_.-]+/)?[a-z0-9_.-]+$")
SECRET_PATTERNS = [
    re.compile(r"""(?i)(?:api[_-]?key|secret|token|password|auth[_-]?token)\s*[:=]\s*["'](?![$<{])[A-Za-z0-9_\-\.]{16,}["']"""),
    re.compile(r"""sk-[a-zA-Z0-9]{20,48}"""),
    re.compile(r"""ghp_[a-zA-Z0-9]{36}"""),
]


class Findings:
    """Accumulates findings for a DSH audit run."""

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


def read_text_safe(path: Path):
    """Read UTF-8 text file safely."""
    try:
        return path.read_text(encoding="utf-8", errors="replace"), None
    except OSError as exc:
        return None, str(exc)


def read_json_safe(path: Path):
    """Read and parse JSON file with error handling."""
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f), None
    except FileNotFoundError:
        return None, "File not found"
    except json.JSONDecodeError as exc:
        return None, f"JSON syntax error at line {exc.lineno}, col {exc.colno}: {exc.msg}"
    except OSError as exc:
        return None, f"I/O error reading file: {exc}"


def check_secrets(text: str, file_rel: Path, findings: Findings, check_id: str = "DSH-12"):
    """Scan text content for hardcoded secrets and tokens."""
    for idx, line in enumerate(text.splitlines(), 1):
        if line.strip().startswith(("#", "//", "/*")):
            continue
        for pat in SECRET_PATTERNS:
            match = pat.search(line)
            if match:
                findings.add(
                    check_id, "error", file_rel, idx, line,
                    message=f"Hardcoded credential or secret token detected: `{match.group(0)[:12]}...`"
                )
                return


def parse_simple_yaml_ops(text: str):
    """Zero-dependency parser for basic Cordis patch YAML files.

    Extracts inserted plugin IDs, names, and disabled flags.
    """
    entries = []
    current_entry = None
    in_insert = False

    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue

        if "insert:" in stripped:
            in_insert = True
            continue

        if in_insert:
            m_id = re.search(r"id:\s*['\"]?([a-zA-Z0-9_-]+)['\"]?", stripped)
            m_name = re.search(r"name:\s*['\"]?([a-zA-Z0-9_@/.-]+)['\"]?", stripped)

            if stripped.startswith("-") or stripped.startswith("id:"):
                if current_entry and ("id" in current_entry or "name" in current_entry):
                    entries.append(current_entry)
                current_entry = {}

            if current_entry is not None:
                if m_id:
                    current_entry["id"] = m_id.group(1)
                if m_name:
                    current_entry["name"] = m_name.group(1)

    if current_entry and ("id" in current_entry or "name" in current_entry):
        entries.append(current_entry)

    return entries


def find_entrypoint(root: Path, manifest: dict):
    """Locate plugin entrypoint file from package.json or common paths."""
    candidates = []
    main_field = manifest.get("main")
    if main_field:
        candidates.append(root / main_field.lstrip("./"))

    # Also search src/ and standard root files
    candidates.extend([
        root / "src" / "index.ts",
        root / "src" / "index.js",
        root / "index.ts",
        root / "index.js",
        root / "src" / "main.ts",
        root / "src" / "main.js",
    ])

    for p in candidates:
        if p.is_file():
            return p
    return None


def lint_dsh_entrypoint(entry_path: Path, root: Path, findings: Findings):
    """Inspect JS/TS source code of entrypoint for DSH conventions."""
    text, err = read_text_safe(entry_path)
    rel_path = entry_path.resolve().relative_to(root.resolve())
    if err or not text:
        return

    check_secrets(text, rel_path, findings)

    # DSH-07: Entrypoint Exports (name and apply)
    has_name = bool(re.search(r"(?:export\s+(?:const|let|var)\s+name\s*=|name\s*:\s*['\"][a-zA-Z0-9_-]+['\"])", text))
    has_apply = bool(re.search(r"(?:export\s+(?:default\s+)?function\s+apply\b|export\s+const\s+apply\s*=|apply\s*\(\s*ctx\b)", text))

    if not has_name:
        findings.add("DSH-07", "error", rel_path, 1, "export const name",
                     message=f"Plugin entrypoint `{rel_path}` does not export a `name` identifier.")
    if not has_apply:
        findings.add("DSH-07", "error", rel_path, 1, "export function apply",
                     message=f"Plugin entrypoint `{rel_path}` does not export an `apply(ctx)` lifecycle function.")

    # DSH-08: Dependency Injection (inject array)
    uses_tools = bool(re.search(r"\bctx\.tools\b", text))
    uses_persona = bool(re.search(r"\bctx\.persona\b", text))
    inject_match = re.search(r"export\s+const\s+inject\s*=\s*\[([^\]]*)\]", text)
    injected_services = set()
    if inject_match:
        injected_services = {s.strip().strip("'\"") for s in inject_match.group(1).split(",") if s.strip()}

    if uses_tools and "tools" not in injected_services:
        findings.add("DSH-08", "warning", rel_path, 1, "ctx.tools without inject",
                     message="Plugin accesses `ctx.tools` but does not declare `'tools'` in `export const inject = [...]`.")
    if uses_persona and "persona" not in injected_services:
        findings.add("DSH-08", "warning", rel_path, 1, "ctx.persona without inject",
                     message="Plugin accesses `ctx.persona` but does not declare `'persona'` in `export const inject = [...]`.")

    # DSH-09: Tool Definition Integrity (defineTool)
    tool_matches = re.finditer(r"defineTool\s*\(\s*\{([\s\S]*?)\}\s*\)", text)
    for m in tool_matches:
        block = m.group(1)
        tool_name = re.search(r"name\s*:\s*['\"]([^'\"]+)['\"]", block)
        tool_desc = re.search(r"description\s*:\s*['\"]([^'\"]+)['\"]", block)
        tool_exec = re.search(r"\b(?:async\s+)?execute\s*(?:\(|\:)", block)

        if not tool_name:
            findings.add("DSH-09", "error", rel_path, 1, "defineTool without name",
                         message="Tool defined in `defineTool` is missing required `name`.")
        if not tool_desc:
            findings.add("DSH-09", "error", rel_path, 1, "defineTool without description",
                         message=f"Tool `{tool_name.group(1) if tool_name else 'unknown'}` is missing `description`.")
        if not tool_exec:
            findings.add("DSH-09", "error", rel_path, 1, "defineTool without execute",
                         message=f"Tool `{tool_name.group(1) if tool_name else 'unknown'}` is missing `execute` function.")

    # DSH-10: Event System Naming Convention
    event_listeners = re.finditer(r"ctx\.on\s*\(\s*['\"]([^'\"]+)['\"]", text)
    for m in event_listeners:
        evt_name = m.group(1)
        if "/" not in evt_name and not evt_name.startswith("internal:"):
            findings.add("DSH-10", "warning", rel_path, 1, evt_name,
                         message=f"Event `{evt_name}` does not follow the `namespace/action` naming convention (e.g. `tools/result`).")

    # DSH-13: Typert Contract Authoring Check
    uses_remote = bool(re.search(r"@Remote\b|TypertRemoteService", text))
    if uses_remote:
        pkg_file = root / "package.json"
        pkg_data, _ = read_json_safe(pkg_file) if pkg_file.is_file() else (None, None)
        if pkg_data:
            exports = pkg_data.get("exports")
            has_typert = isinstance(exports, dict) and "./typert" in exports
            if not has_typert:
                findings.add("DSH-13", "warning", rel_path, 1, "@Remote used without ./typert export",
                             message="Plugin uses Typert RPC annotations (@Remote), but `package.json` does not declare a `./typert` export.")


def lint_dsh_preset(preset_path: Path, root: Path, findings: Findings):
    """Validate an agent preset configuration file (agent.cordis.yml)."""
    text, err = read_text_safe(preset_path)
    rel_path = preset_path.resolve().relative_to(root.resolve())
    if err or not text:
        return

    check_secrets(text, rel_path, findings)

    has_name = bool(re.search(r"^name:\s*['\"]?[a-zA-Z0-9_-]+['\"]?", text, re.MULTILINE))
    has_persona = bool(re.search(r"^persona:\s*", text, re.MULTILINE))
    has_tools = bool(re.search(r"^tools:\s*", text, re.MULTILINE))

    if not has_name:
        findings.add("DSH-11", "warning", rel_path, 1, "name missing",
                     message="Agent preset `agent.cordis.yml` is missing `name` identifier.")
    if not has_persona and not has_tools:
        findings.add("DSH-11", "warning", rel_path, 1, "empty preset",
                     message="Agent preset `agent.cordis.yml` does not declare `persona` or `tools`.")


def lint_dsh_plugin(root: Path, findings: Findings):
    """Main audit routine for a DeepSeek Harness plugin directory."""
    root = root.resolve()
    pkg_path = root / "package.json"

    # DSH-01: Package Manifest Validity
    if not pkg_path.is_file():
        # Check if this is an agent preset directory instead of a plugin
        preset_file = root / "agent.cordis.yml"
        if preset_file.is_file():
            lint_dsh_preset(preset_file, root, findings)
            return

        findings.add("DSH-01", "error", "package.json", 1, "missing",
                     message="No `package.json` found in target DeepSeek Harness plugin directory.")
        return

    data, err = read_json_safe(pkg_path)
    rel_pkg = Path("package.json")
    if err:
        findings.add("DSH-01", "error", rel_pkg, 1, err,
                     message=f"Failed to parse `package.json`: {err}")
        return

    check_secrets(json.dumps(data), rel_pkg, findings)

    # DSH-02: Identity and Semver
    name = data.get("name")
    if not name or not isinstance(name, str) or not PKG_NAME_REGEX.match(name):
        findings.add("DSH-02", "error", rel_pkg, 1, str(name),
                     message=f"Invalid package name `{name}`. Must be lowercase letters, numbers, hyphens, and optional scope.")

    version = data.get("version")
    if not version or not isinstance(version, str) or not SEMVER_REGEX.match(version):
        findings.add("DSH-02", "error", rel_pkg, 1, str(version),
                     message=f"Invalid package version `{version}`. Must follow semver (e.g. `1.0.0`).")

    # DSH-03: DSH Extension Configuration
    dsh_conf = data.get("dsh")
    patch_rel = None
    if not dsh_conf or not isinstance(dsh_conf, dict):
        findings.add("DSH-03", "error", rel_pkg, 1, "dsh field missing",
                     message="`package.json` missing `dsh` configuration object.")
    else:
        bundle_conf = dsh_conf.get("bundle")
        profile_conf = dsh_conf.get("profile")

        if bundle_conf and isinstance(bundle_conf, dict):
            patch_rel = bundle_conf.get("patch")
            if not patch_rel or not isinstance(patch_rel, str):
                findings.add("DSH-03", "error", rel_pkg, 1, "dsh.bundle.patch missing",
                             message="`dsh.bundle` must define a `patch` path (e.g. `./cordis.patch.yml`).")
        elif profile_conf and isinstance(profile_conf, dict):
            # Profile mode
            bundles = profile_conf.get("bundles")
            if bundles is None or not isinstance(bundles, list):
                findings.add("DSH-03", "error", rel_pkg, 1, "dsh.profile.bundles missing",
                             message="`dsh.profile` must define a `bundles` list.")
        else:
            findings.add("DSH-03", "error", rel_pkg, 1, "dsh.bundle or dsh.profile required",
                         message="`dsh` field must declare either `bundle` or `profile` configuration.")

    # DSH-04 & DSH-05: Patch File Check
    if patch_rel:
        patch_path = (root / patch_rel.lstrip("./")).resolve()
        if not patch_path.is_file():
            findings.add("DSH-04", "error", rel_pkg, 1, patch_rel,
                         message=f"Cordis patch file `{patch_rel}` not found on disk.")
        else:
            patch_text, p_err = read_text_safe(patch_path)
            rel_patch_path = patch_path.relative_to(root)
            if p_err or not patch_text:
                findings.add("DSH-05", "error", rel_patch_path, 1, p_err or "empty file",
                             message="Could not read Cordis patch file.")
            else:
                check_secrets(patch_text, rel_patch_path, findings)
                ops = parse_simple_yaml_ops(patch_text)
                if not ops:
                    findings.add("DSH-05", "error", rel_patch_path, 1, "no valid ops",
                                 message="Cordis patch file does not define any valid plugin operations with `id` and `name`.")

    # DSH-06 & DSH-07 & DSH-08 & DSH-09 & DSH-10: Entrypoint Analysis
    entry_path = find_entrypoint(root, data)
    if not entry_path:
        main_spec = data.get("main", "src/index.ts")
        findings.add("DSH-06", "error", rel_pkg, 1, str(main_spec),
                     message=f"Plugin entrypoint `{main_spec}` could not be found.")
    else:
        lint_dsh_entrypoint(entry_path, root, findings)

    # Check for agent preset if present
    preset_file = root / "agent.cordis.yml"
    if preset_file.is_file():
        lint_dsh_preset(preset_file, root, findings)


def evaluate_publish_checklist(root: Path, pkg_data: dict, findings: Findings) -> list:
    """Evaluate DSH 5-point publishing checklist (config-publish standard)."""
    checks = []

    # 1. Build Artifacts
    files_declared = pkg_data.get("files", [])
    has_dist = any(f in ("dist", "lib", "dist/", "lib/") for f in files_declared) or (root / "dist").is_dir() or (root / "lib").is_dir()
    has_build_script = isinstance(pkg_data.get("scripts"), dict) and "build" in pkg_data["scripts"]
    status_1 = "PASS" if (has_dist or has_build_script) else "WARN"
    checks.append({
        "item": "1. Build Artifacts",
        "status": status_1,
        "detail": "Compiled output (dist/lib) in `files` or `scripts.build` defined." if status_1 == "PASS" else "Missing `dist/` or `lib/` in package.json `files` or `scripts.build`."
    })

    # 2. Dependency Declarations Complete
    peer_deps = pkg_data.get("peerDependencies", {})
    deps = pkg_data.get("dependencies", {})
    has_cordis = "@deepseek-ai/cordis" in peer_deps or "@deepseek-ai/cordis" in deps
    status_2 = "PASS" if has_cordis else "WARN"
    checks.append({
        "item": "2. Dependency Declarations",
        "status": status_2,
        "detail": "Core framework `@deepseek-ai/cordis` declared in dependencies." if status_2 == "PASS" else "Recommended: Declare `@deepseek-ai/cordis` in `peerDependencies`."
    })

    # 3. Config Schema Validation
    entry_path = find_entrypoint(root, pkg_data)
    entry_text, _ = read_text_safe(entry_path) if entry_path else ("", None)
    has_config = bool(re.search(r"\b(?:interface\s+Config|type\s+Config|const\s+Config|Schema\b)", entry_text or ""))
    status_3 = "PASS" if has_config else "WARN"
    checks.append({
        "item": "3. Config Schema Validation",
        "status": status_3,
        "detail": "Plugin defines typed `Config` interface or schema validation." if status_3 == "PASS" else "Plugin lacks explicit `Config` interface or schema validation."
    })

    # 4. Installability & Provenance
    has_desc = bool(pkg_data.get("description"))
    has_lic = bool(pkg_data.get("license"))
    has_readme = (root / "README.md").is_file()
    status_4 = "PASS" if (has_desc and has_lic and has_readme) else "WARN"
    checks.append({
        "item": "4. Metadata & Provenance",
        "status": status_4,
        "detail": "Description, license, and README.md are all present." if status_4 == "PASS" else "Incomplete metadata: ensure description, license, and README.md exist."
    })

    # 5. Runtime Settings & Typert
    uses_remote = bool(re.search(r"@Remote\b", entry_text or ""))
    exports = pkg_data.get("exports", {})
    has_typert_export = isinstance(exports, dict) and "./typert" in exports
    if uses_remote and not has_typert_export:
        status_5 = "FAIL"
        detail_5 = "Typert `@Remote` annotations used, but `./typert` export missing in `package.json`."
    else:
        status_5 = "PASS"
        detail_5 = "Runtime settings and Typert contract exports validated."
    checks.append({
        "item": "5. Runtime Settings & Typert",
        "status": status_5,
        "detail": detail_5
    })

    return checks


def format_checklist_report(checks: list) -> str:
    """Format checklist results as a readable markdown table."""
    lines = [
        "## DeepSeek Harness Pre-Publishing Checklist (config-publish)\n",
        "| Status | Item | Verification Detail |",
        "|---|---|---|"
    ]
    all_pass = True
    for c in checks:
        icon = "✅ PASS" if c["status"] == "PASS" else "⚠️ WARN" if c["status"] == "WARN" else "❌ FAIL"
        if c["status"] != "PASS":
            all_pass = False
        lines.append(f"| {icon} | **{c['item']}** | {c['detail']} |")

    pass_count = sum(1 for c in checks if c["status"] == "PASS")
    lines.append(f"\n**Checklist Score:** {pass_count}/{len(checks)} passed.")
    if all_pass:
        lines.append("🚀 **Verdict: READY TO PUBLISH** (All pre-publishing requirements met)")
    else:
        lines.append("ℹ️ **Verdict: ACTION NEEDED BEFORE PUBLISHING** (Review items above)")
    return "\n".join(lines)


def format_report_markdown(findings: Findings, target_name: str) -> str:
    """Format audit findings into a clean Markdown report."""
    errs = sum(1 for x in findings.items if x["severity"] == "error")
    warns = sum(1 for x in findings.items if x["severity"] == "warning")
    infos = sum(1 for x in findings.items if x["severity"] == "info")

    if errs > 0:
        verdict = "FAIL"
    elif warns > 0:
        verdict = "PASS WITH WARNINGS"
    else:
        verdict = "PASS"

    lines = [
        f"Target: {target_name}  (DEEPSEEK HARNESS PLUGIN)",
        f"Verdict: {verdict}  (errors: {errs}, warnings: {warns}, info: {infos})\n"
    ]

    for f in findings.items:
        icon = "❌" if f["severity"] == "error" else "⚠️" if f["severity"] == "warning" else "ℹ️"
        lines.append(f"{icon}  [{f['id']}] {f['title']}  ({f['file']}:{f['line']})")
        lines.append(f"    evidence: {f['evidence']}")
        lines.append(f"    fix: {f['fix']}\n")

    for n in findings.notes:
        lines.append(f"  note: {n}")

    return "\n".join(lines)


def run_self_test():
    """Verify DSH linter rules against temporary test fixtures."""
    print("Running audit_dsh.py self-test...")
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)

        # 1. Test Valid DSH Plugin
        p_valid = root / "valid-dsh-plugin"
        p_valid.mkdir()
        with open(p_valid / "package.json", "w") as f:
            json.dump({
                "name": "dsh-tool-tester",
                "version": "1.0.0",
                "type": "module",
                "main": "src/index.ts",
                "dsh": {
                    "bundle": {
                        "patch": "./cordis.patch.yml"
                    }
                }
            }, f)

        with open(p_valid / "cordis.patch.yml", "w") as f:
            f.write("- insert:\n    - id: tester\n      name: dsh-tool-tester\n")

        src_dir = p_valid / "src"
        src_dir.mkdir()
        with open(src_dir / "index.ts", "w") as f:
            f.write("""import type { Context } from '@deepseek-ai/cordis'
import { defineTool } from '@deepseek-ai/dsh-tools'

export const name = 'dsh-tool-tester'
export const inject = ['tools']

export function apply(ctx: Context) {
  ctx.tools.register(
    defineTool({
      name: 'run_test',
      description: 'Run automated harness tests',
      execute: async () => 'ok',
    })
  )
  ctx.on('tools/result', () => {})
}
""")

        f_valid = Findings(p_valid)
        lint_dsh_plugin(p_valid, f_valid)
        errs = [x for x in f_valid.items if x["severity"] == "error"]
        assert len(errs) == 0, f"Valid DSH plugin produced unexpected errors: {errs}"
        print("  ✓ Valid DSH plugin test passed")

        # 2. Test Invalid DSH Plugin (Bad Name, Missing Patch, Missing Exports, Secret)
        p_bad = root / "bad-dsh-plugin"
        p_bad.mkdir()
        with open(p_bad / "package.json", "w") as f:
            json.dump({
                "name": "Bad_DSH_Name!",
                "version": "not-semver",
                "main": "src/index.ts",
                "dsh": {
                    "bundle": {
                        "patch": "./missing.patch.yml"
                    }
                }
            }, f)

        b_src = p_bad / "src"
        b_src.mkdir()
        with open(b_src / "index.ts", "w") as f:
            f.write('const secret = "sk-1234567890abcdef12345678"\nconsole.log(secret)\n')

        f_bad = Findings(p_bad)
        lint_dsh_plugin(p_bad, f_bad)
        bad_ids = {x["id"] for x in f_bad.items}
        assert "DSH-02" in bad_ids, "Failed to flag invalid name/version"
        assert "DSH-04" in bad_ids, "Failed to flag missing patch file"
        assert "DSH-07" in bad_ids, "Failed to flag missing name/apply exports"
        assert "DSH-12" in bad_ids, "Failed to flag hardcoded secret"
        print("  ✓ Invalid DSH plugin test passed (DSH-02, DSH-04, DSH-07, DSH-12 flagged)")

        # 3. Test Incomplete Tool Definition & Bad Event Naming
        p_tool = root / "bad-tool-plugin"
        p_tool.mkdir()
        with open(p_tool / "package.json", "w") as f:
            json.dump({
                "name": "dsh-bad-tool",
                "version": "0.1.0",
                "dsh": {"bundle": {"patch": "./cordis.patch.yml"}}
            }, f)
        with open(p_tool / "cordis.patch.yml", "w") as f:
            f.write("- insert:\n    - id: bad\n      name: dsh-bad-tool\n")
        t_src = p_tool / "src"
        t_src.mkdir()
        with open(t_src / "index.ts", "w") as f:
            f.write("""export const name = 'dsh-bad-tool'
export function apply(ctx: any) {
  ctx.tools.register(defineTool({
    name: 'incomplete_tool'
  }))
  ctx.on('rawEventNameWithoutSlash', () => {})
}
""")
        f_tool = Findings(p_tool)
        lint_dsh_plugin(p_tool, f_tool)
        tool_ids = {x["id"] for x in f_tool.items}
        assert "DSH-08" in tool_ids, "Failed to flag missing inject for ctx.tools"
        assert "DSH-09" in tool_ids, "Failed to flag missing description/execute in tool"
        assert "DSH-10" in tool_ids, "Failed to flag non-standard event naming"
        print("  ✓ Incomplete tool and event test passed (DSH-08, DSH-09, DSH-10 flagged)")

        # 4. Test Typert and Pre-Publishing Checklist
        p_typert = root / "typert-plugin"
        p_typert.mkdir()
        with open(p_typert / "package.json", "w") as f:
            json.dump({
                "name": "dsh-typert-demo",
                "version": "1.0.0",
                "description": "Typert demo plugin",
                "license": "MIT",
                "files": ["dist", "cordis.patch.yml"],
                "scripts": {"build": "tsc -b"},
                "peerDependencies": {"@deepseek-ai/cordis": "^1.0.0"},
                "exports": {
                    ".": "./dist/index.js",
                    "./typert": "./dist/typert/index.js"
                },
                "dsh": {"bundle": {"patch": "./cordis.patch.yml"}}
            }, f)
        with open(p_typert / "cordis.patch.yml", "w") as f:
            f.write("- insert:\n    - id: demo\n      name: dsh-typert-demo\n")
        with open(p_typert / "README.md", "w") as f:
            f.write("# Demo\n")
        t_src2 = p_typert / "src"
        t_src2.mkdir()
        with open(t_src2 / "index.ts", "w") as f:
            f.write("""export const name = 'dsh-typert-demo'
export interface Config { enabled?: boolean }
export function apply(ctx: any) {}
class Svc {
  @Remote('test')
  async test() {}
}
""")
        f_typert = Findings(p_typert)
        lint_dsh_plugin(p_typert, f_typert)
        checklist = evaluate_publish_checklist(p_typert, json.load(open(p_typert / "package.json")), f_typert)
        assert all(c["status"] == "PASS" for c in checklist), f"Checklist failed: {checklist}"
        print("  ✓ Typert and pre-publishing checklist test passed")

    print("All audit_dsh.py self-tests PASSED (4/4).")


def main():
    parser = argparse.ArgumentParser(description="Audit DeepSeek Harness plugins and components.")
    parser.add_argument("path", nargs="?", default=".", help="Path to DSH plugin bundle directory or preset.")
    parser.add_argument("--format", choices=["text", "json", "markdown"], default="markdown", help="Output format.")
    parser.add_argument("--strict", action="store_true", help="Fail with non-zero exit code on warnings.")
    parser.add_argument("--publish-check", "--checklist", action="store_true",
                        help="Evaluate official DSH pre-publishing readiness checklist.")
    parser.add_argument("--check", help="Comma-separated check IDs to filter (e.g. DSH-01,DSH-02).")
    parser.add_argument("--output", help="Write report to specified file path.")
    parser.add_argument("--self-test", action="store_true", help="Run internal self-tests.")

    args = parser.parse_args()

    if args.self_test:
        run_self_test()
        sys.exit(0)

    target_dir = Path(args.path).resolve()
    if not target_dir.is_dir():
        print(f"Error: Target path is not a directory: {target_dir}", file=sys.stderr)
        sys.exit(2)

    findings = Findings(target_dir)
    lint_dsh_plugin(target_dir, findings)

    checklist_output = ""
    checklist_passed = True
    if args.publish_check:
        pkg_file = target_dir / "package.json"
        if pkg_file.is_file():
            pkg_data, _ = read_json_safe(pkg_file)
            if pkg_data:
                checks = evaluate_publish_checklist(target_dir, pkg_data, findings)
                checklist_output = "\n" + format_checklist_report(checks) + "\n"
                if any(c["status"] == "FAIL" for c in checks):
                    checklist_passed = False

    if args.check:
        allowed = set(args.check.split(","))
        findings.items = [x for x in findings.items if x["id"] in allowed]

    if args.format == "json":
        report_output = json.dumps({
            "target": target_dir.name,
            "findings": findings.items,
            "notes": findings.notes
        }, indent=2)
    else:
        report_output = format_report_markdown(findings, target_dir.name)
        if checklist_output:
            report_output += checklist_output

    if args.output:
        Path(args.output).write_text(report_output, encoding="utf-8")
    else:
        print(report_output)

    errors = [x for x in findings.items if x["severity"] == "error"]
    warnings = [x for x in findings.items if x["severity"] == "warning"]

    if errors or not checklist_passed or (args.strict and warnings):
        sys.exit(1)
    sys.exit(0)


if __name__ == "__main__":
    main()
