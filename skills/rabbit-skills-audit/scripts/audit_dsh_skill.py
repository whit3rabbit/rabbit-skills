#!/usr/bin/env python3
"""DeepSeek Harness (DSH) Skill Static Linter.

Audits agent skills targeted for DeepSeek Harness (DSH) against native filesystem
specifications (@deepseek-ai/dsh-skill-filesystem), frontmatter schema rules,
progressive disclosure token budgets, and security standards.

Checks:
  - DSK-01..DSK-12: Layout shapes, frontmatter strictness, fail-closed booleans,
    link integrity, body limits, secrets, and precedence shadowing.

Standard library only (`argparse`, `json`, `pathlib`, `re`, `sys`).
Runs standalone or as part of the rabbit-skills suite.

Usage:
  python3 audit_dsh_skill.py <path-to-skill-or-skills-root> [options]
  python3 audit_dsh_skill.py --self-test
"""

import argparse
import json
import os
import re
import sys
import tempfile
from pathlib import Path

try:
    from frontmatter import parse as _fm_parse
except ImportError:
    import importlib.util as _ilu
    _spec = _ilu.spec_from_file_location("frontmatter", Path(__file__).with_name("frontmatter.py"))
    _fm = _ilu.module_from_spec(_spec)
    _spec.loader.exec_module(_fm)
    _fm_parse = _fm.parse

CHECK_INFO = {
    "DSK-01": (
        "Skill entrypoint missing or invalid layout shape",
        "DeepSeek Harness requires either a directory bundle `<root>/<name>/SKILL.md` or a flat file `<root>/<name>.md`.",
        "Ensure `SKILL.md` exists in the skill directory or format as a single `<name>.md` flat skill."
    ),
    "DSK-02": (
        "Missing or malformed YAML frontmatter",
        "DSH skill files must start with a valid YAML frontmatter block demarcated by `---` delimiters.",
        "Add a valid YAML frontmatter block at the top of the skill file starting with `---`."
    ),
    "DSK-03": (
        "Missing or invalid skill name identifier",
        "The `name` field is required, must be lowercase kebab-case (`^[a-z0-9-]+$`), and at most 64 characters.",
        "Set `name` to a valid kebab-case string (e.g. `code-reviewer`)."
    ),
    "DSK-04": (
        "Skill name does not match directory or file name",
        "Frontmatter `name` must exactly match the containing directory name (or file stem for flat `.md` skills).",
        "Align frontmatter `name` with directory or file name."
    ),
    "DSK-05": (
        "Missing or inadequate skill description",
        "The `description` field is required by DSH for catalog routing and model trigger selection.",
        "Add a descriptive `description` explaining both capability and activation triggers."
    ),
    "DSK-06": (
        "Invalid disable-model-invocation property",
        "DSH enforces strict typing for `disable-model-invocation` (must be boolean `true` or `false`). Non-boolean values fail closed.",
        "Set `disable-model-invocation: true` or `disable-model-invocation: false`."
    ),
    "DSK-07": (
        "Invalid user-invocable property",
        "DSH enforces strict typing for `user-invocable` (must be boolean `true` or `false`). Non-boolean values fail closed.",
        "Set `user-invocable: true` or `user-invocable: false`."
    ),
    "DSK-08": (
        "Disallowed or unrecognized frontmatter field",
        "DSH skill loader fails closed if unknown frontmatter fields are declared.",
        "Remove unrecognized fields from YAML frontmatter."
    ),
    "DSK-09": (
        "Broken local reference or missing linked resource",
        "Relative markdown links within the skill must resolve to valid existing files inside the skill directory.",
        "Ensure all linked reference files exist or update the relative link target."
    ),
    "DSK-10": (
        "Skill body exceeds recommended token budget",
        "DSH expands full skill text into prompt context on activation; body over 500 lines risks token bloat.",
        "Extract detailed reference documentation into `references/` files."
    ),
    "DSK-11": (
        "Potential hardcoded credentials or secret tokens",
        "Skill instructions or scripts must not expose plaintext API keys, passwords, or tokens.",
        "Replace raw credentials with environment variable references."
    ),
    "DSK-12": (
        "Skill precedence shadowing detected",
        "Identically named skill exists in a higher-priority layer and will shadow this definition.",
        "Rename the skill or verify that intentional layer shadowing is desired."
    ),
}

ALLOWED_FRONTMATTER_KEYS = {
    "name",
    "description",
    "disable-model-invocation",
    "user-invocable",
    "version",
    "author",
    "license",
    "tools",
    "allowed-tools",
    "metadata",
}

KEBAB_NAME_REGEX = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
SECRET_PATTERNS = [
    re.compile(r"""(?i)(?:api[_-]?key|secret|token|password|auth[_-]?token)\s*[:=]\s*["'](?![$<{])[A-Za-z0-9_\-\.]{16,}["']"""),
    re.compile(r"""sk-[a-zA-Z0-9]{20,48}"""),
    re.compile(r"""ghp_[a-zA-Z0-9]{36}"""),
]


class Findings:
    """Accumulates findings for a DSH skill audit run."""

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
    """Safely read text with error handling."""
    try:
        return path.read_text(encoding="utf-8", errors="replace"), None
    except OSError as exc:
        return None, str(exc)


def check_secrets(text: str, file_rel: Path, findings: Findings, check_id: str = "DSK-11"):
    """Scan file lines for secrets and credentials."""
    for idx, line in enumerate(text.splitlines(), 1):
        if line.strip().startswith(("#", "//", "<!--")):
            continue
        for pat in SECRET_PATTERNS:
            match = pat.search(line)
            if match:
                findings.add(
                    check_id, "error", file_rel, idx, line,
                    message=f"Hardcoded credential or secret detected: `{match.group(0)[:12]}...`"
                )
                return


def lint_single_skill_file(skill_file: Path, skill_root: Path, findings: Findings, expected_name: str = None):
    """Lint a single SKILL.md or <name>.md file against DSH standards."""
    text, err = read_text_safe(skill_file)
    rel_file = skill_file.resolve().relative_to(skill_root.resolve())

    if err or text is None:
        findings.add("DSK-01", "error", rel_file, 1, err or "cannot read",
                     message=f"Could not read skill file `{rel_file}`: {err}")
        return

    check_secrets(text, rel_file, findings)

    # DSK-02: Frontmatter validation
    parsed = _fm_parse(text)
    if parsed.get("error"):
        findings.add("DSK-02", "error", rel_file, 1, parsed["error"],
                     message=f"Malformed frontmatter in `{rel_file}`: {parsed['error']}")
        return

    meta = parsed.get("meta", {})
    body = parsed.get("body", "")
    key_lines = parsed.get("key_lines", {})

    # DSK-03: Name validation
    raw_name = meta.get("name")
    if not raw_name or not isinstance(raw_name, str) or not raw_name.strip():
        findings.add("DSK-03", "error", rel_file, key_lines.get("name", 1), str(raw_name),
                     message="Skill is missing required `name` frontmatter field.")
    else:
        name_str = raw_name.strip()
        if not KEBAB_NAME_REGEX.match(name_str):
            findings.add("DSK-03", "error", rel_file, key_lines.get("name", 1), name_str,
                         message=f"Skill name '{name_str}' is not lowercase kebab-case.")
        if len(name_str) > 64:
            findings.add("DSK-03", "warning", rel_file, key_lines.get("name", 1), name_str,
                         message=f"Skill name exceeds 64 characters ({len(name_str)} chars).")

        # DSK-04: Name sync with directory or flat file stem
        if expected_name and name_str != expected_name:
            findings.add("DSK-04", "error", rel_file, key_lines.get("name", 1),
                         f"name: {name_str} != {expected_name}",
                         message=f"Frontmatter name '{name_str}' does not match path identifier '{expected_name}'.")

    # DSK-05: Description validation
    desc = meta.get("description")
    if not desc or not isinstance(desc, str) or not desc.strip():
        findings.add("DSK-05", "error", rel_file, key_lines.get("description", 1), "missing description",
                     message="Skill is missing required `description` frontmatter field.")
    elif len(desc.strip()) < 20:
        findings.add("DSK-05", "warning", rel_file, key_lines.get("description", 1), desc.strip(),
                     message=f"Description is very short ({len(desc.strip())} chars); DSH routing requires clear triggers.")

    raw_lines = text.splitlines()

    def is_valid_yaml_bool(key_name):
        line_no = key_lines.get(key_name)
        if not line_no or line_no > len(raw_lines):
            return True, None
        line_str = raw_lines[line_no - 1]
        m = re.search(rf"^{key_name}:\s*(.*)$", line_str)
        if not m:
            return True, None
        val_str = m.group(1).split("#")[0].strip()
        if val_str in ("true", "false"):
            return True, val_str
        return False, val_str

    # DSK-06: disable-model-invocation (Strict boolean check)
    if "disable-model-invocation" in meta:
        valid_b, val = is_valid_yaml_bool("disable-model-invocation")
        line_no = key_lines.get("disable-model-invocation", 1)
        if not valid_b:
            findings.add("DSK-06", "error", rel_file, line_no, f"disable-model-invocation: {val}",
                         message=f"`disable-model-invocation` must be strict YAML boolean `true` or `false`, got `{val}`. DSH fails closed.")

    # DSK-07: user-invocable (Strict boolean check)
    if "user-invocable" in meta:
        valid_b, val = is_valid_yaml_bool("user-invocable")
        line_no = key_lines.get("user-invocable", 1)
        if not valid_b:
            findings.add("DSK-07", "error", rel_file, line_no, f"user-invocable: {val}",
                         message=f"`user-invocable` must be strict YAML boolean `true` or `false`, got `{val}`. DSH fails closed.")

    # DSK-08: Unknown frontmatter keys
    for k in meta.keys():
        if k not in ALLOWED_FRONTMATTER_KEYS:
            line_no = key_lines.get(k, 1)
            findings.add("DSK-08", "warning", rel_file, line_no, k,
                         message=f"Unrecognized frontmatter field `{k}`. DSH skill parser may ignore or fail closed.")

    # DSK-09: Local link resolution within directory bundle
    if skill_file.name == "SKILL.md":
        skill_dir = skill_file.parent
        link_matches = re.finditer(r"\[([^\]]+)\]\(([^)]+)\)", body)
        for m in link_matches:
            target = m.group(2).strip()
            if target.startswith(("http://", "https://", "mailto:", "#")):
                continue
            # Strip anchors
            clean_target = target.split("#")[0]
            if not clean_target:
                continue
            resolved = (skill_dir / clean_target).resolve()
            if not resolved.exists():
                findings.add("DSK-09", "error", rel_file, 1, target,
                             message=f"Referenced link target `{target}` not found on disk.")

    # DSK-10: Body line count budget
    body_lines = len(body.splitlines())
    if body_lines > 500:
        findings.add("DSK-10", "warning", rel_file, 1, f"{body_lines} lines",
                     message=f"Skill body is {body_lines} lines (>500 lines). Progressive disclosure recommends extracting reference files.")


def lint_dsh_skill_directory(target_path: Path, findings: Findings):
    """Audit a directory bundle, flat skill file, or entire skills root directory."""
    target_path = target_path.resolve()

    # Case 1: Target is a flat markdown file
    if target_path.is_file() and target_path.suffix == ".md":
        expected = target_path.stem if target_path.name != "SKILL.md" else target_path.parent.name
        lint_single_skill_file(target_path, target_path.parent, findings, expected_name=expected)
        return

    if not target_path.is_dir():
        findings.add("DSK-01", "error", target_path.name, 1, "does not exist",
                     message=f"Target path `{target_path}` is neither a file nor a directory.")
        return

    # Case 2: Target is a single skill directory bundle (<dir>/SKILL.md)
    skill_md = target_path / "SKILL.md"
    if skill_md.is_file():
        lint_single_skill_file(skill_md, target_path, findings, expected_name=target_path.name)
        return

    # Case 3: Target is a skills collection root (e.g. .dsh/skills/ or ~/.dsh/skills/)
    # Traverse child entries looking for directory bundles or flat .md files
    found_any = False
    discovered_skills = {}

    for item in sorted(target_path.iterdir()):
        if item.name.startswith((".", "_")):
            continue
        if item.name == ".system":  # DSH automatically skips .system
            continue

        if item.is_dir():
            nested_skill = item / "SKILL.md"
            if nested_skill.is_file():
                found_any = True
                lint_single_skill_file(nested_skill, target_path, findings, expected_name=item.name)
                discovered_skills[item.name] = item
        elif item.is_file() and item.suffix == ".md" and item.name != "README.md":
            found_any = True
            lint_single_skill_file(item, target_path, findings, expected_name=item.stem)
            discovered_skills[item.stem] = item

    if not found_any:
        findings.add("DSK-01", "error", target_path.name, 1, "no skills found",
                     message=f"No DSH skills (`SKILL.md` or `<name>.md`) found in `{target_path}`.")


def evaluate_skill_publish_checklist(skill_file: Path, findings: Findings) -> list:
    """Evaluate DSH skill pre-publishing readiness checklist."""
    text, _ = read_text_safe(skill_file)
    parsed = _fm_parse(text or "")
    meta = parsed.get("meta", {})
    body = parsed.get("body", "")

    checks = []

    # 1. Frontmatter Delimiters & Parsing
    has_fm = bool(meta) and not parsed.get("error")
    status_1 = "PASS" if has_fm else "FAIL"
    checks.append({
        "item": "1. Frontmatter Delimiters & Parsing",
        "status": status_1,
        "detail": "YAML frontmatter parsed successfully with opening/closing delimiters." if status_1 == "PASS" else "Malformed YAML frontmatter or delimiters missing."
    })

    # 2. Identifier & Name Sync
    name = meta.get("name", "")
    is_kebab = bool(KEBAB_NAME_REGEX.match(name))
    expected = skill_file.stem if skill_file.name != "SKILL.md" else skill_file.parent.name
    name_synced = (name == expected)
    status_2 = "PASS" if (is_kebab and name_synced) else "FAIL"
    checks.append({
        "item": "2. Kebab-Case Naming & Path Alignment",
        "status": status_2,
        "detail": f"Name '{name}' matches path identifier and adheres to lowercase kebab-case." if status_2 == "PASS" else f"Name '{name}' does not match path identifier '{expected}' or is not kebab-case."
    })

    # 3. Routing Description
    desc = meta.get("description", "")
    status_3 = "PASS" if len(desc.strip()) >= 30 else "WARN"
    checks.append({
        "item": "3. Routing Description & Triggers",
        "status": status_3,
        "detail": f"Description is trigger-rich ({len(desc.strip())} chars)." if status_3 == "PASS" else "Description is short (<30 chars); expand with concrete trigger phrases."
    })

    # 4. Gating Policies Explicitly Configured
    has_gating_err = any(x["id"] in ("DSK-06", "DSK-07") for x in findings.items)
    status_4 = "FAIL" if has_gating_err else "PASS"
    detail_4 = "Invocation gating policies adhere to strict boolean typing." if status_4 == "PASS" else "Invalid non-boolean types found in gating properties (fails closed)."
    checks.append({
        "item": "4. Invocation Gating Policy Typing",
        "status": status_4,
        "detail": detail_4
    })

    # 5. Progressive Disclosure Token Budget
    lines = len(body.splitlines())
    status_5 = "PASS" if lines <= 500 else "WARN"
    checks.append({
        "item": "5. Body Line Count & Progressive Disclosure",
        "status": status_5,
        "detail": f"Body is concise ({lines} lines <= 500 lines limit)." if status_5 == "PASS" else f"Body exceeds 500 lines ({lines} lines); extract reference docs."
    })

    # 6. Safety & Link Integrity
    has_err = any(x["severity"] == "error" for x in findings.items)
    status_6 = "PASS" if not has_err else "FAIL"
    checks.append({
        "item": "6. Safety, Links & Credential Hygiene",
        "status": status_6,
        "detail": "Zero credential leaks and all internal resource links verified." if status_6 == "PASS" else "Resolve static errors (broken links or secrets) before sharing."
    })

    return checks


def format_skill_checklist_report(checks: list) -> str:
    """Format skill checklist results as a readable markdown table."""
    lines = [
        "## DeepSeek Harness Skill Pre-Publishing Checklist\n",
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
    """Format audit findings into clean markdown report."""
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
        f"Target: {target_name}  (DEEPSEEK HARNESS SKILL)",
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
    """Verify DSH skill linter against valid and invalid fixtures."""
    print("Running audit_dsh_skill.py self-test...")
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)

        # 1. Test Valid Directory Bundle Skill
        bundle_dir = root / "valid-reviewer"
        bundle_dir.mkdir()
        with open(bundle_dir / "SKILL.md", "w") as f:
            f.write("""---
name: valid-reviewer
description: Review pull requests and staged git diffs against codebase conventions.
disable-model-invocation: false
user-invocable: true
---
# Valid Reviewer

See [references](references/guide.md) for details.
""")
        ref_dir = bundle_dir / "references"
        ref_dir.mkdir()
        with open(ref_dir / "guide.md", "w") as f:
            f.write("# Guide\n")

        f_bundle = Findings(bundle_dir)
        lint_dsh_skill_directory(bundle_dir, f_bundle)
        errs = [x for x in f_bundle.items if x["severity"] == "error"]
        assert len(errs) == 0, f"Valid bundle skill produced unexpected errors: {errs}"
        print("  ✓ Valid DSH bundle skill test passed")

        # 2. Test Valid Flat .md Skill
        flat_file = root / "quick-tool.md"
        with open(flat_file, "w") as f:
            f.write("""---
name: quick-tool
description: Quickly inspect system parameters and log runtime statuses.
user-invocable: true
---
# Quick Tool
""")
        f_flat = Findings(flat_file)
        lint_dsh_skill_directory(flat_file, f_flat)
        f_errs = [x for x in f_flat.items if x["severity"] == "error"]
        assert len(f_errs) == 0, f"Valid flat skill produced unexpected errors: {f_errs}"
        print("  ✓ Valid DSH flat skill test passed")

        # 3. Test Invalid Skill (Bad Name, Non-Boolean Flag, Name Mismatch, Broken Link, Secret)
        bad_dir = root / "mismatched-name"
        bad_dir.mkdir()
        with open(bad_dir / "SKILL.md", "w") as f:
            f.write("""---
name: BAD_NAME_WITH_CAPS
description: Short
disable-model-invocation: "yes"
user-invocable: 1
---
# Bad Skill

[Broken Link](references/nonexistent.md)

sk-1234567890abcdef12345678
""")
        f_bad = Findings(bad_dir)
        lint_dsh_skill_directory(bad_dir, f_bad)
        bad_ids = {x["id"] for x in f_bad.items}
        assert "DSK-03" in bad_ids, "Failed to flag non-kebab name"
        assert "DSK-04" in bad_ids, "Failed to flag name mismatch"
        assert "DSK-06" in bad_ids, "Failed to flag non-boolean disable-model-invocation"
        assert "DSK-07" in bad_ids, "Failed to flag non-boolean user-invocable"
        assert "DSK-09" in bad_ids, "Failed to flag broken link"
        assert "DSK-11" in bad_ids, "Failed to flag secret token"
        print("  ✓ Invalid DSH skill test passed (DSK-03, DSK-04, DSK-06, DSK-07, DSK-09, DSK-11 flagged)")

        # 4. Test Multi-Skill Root Collection
        skills_root = root / "skills-root"
        skills_root.mkdir()
        s1 = skills_root / "skill-one"
        s1.mkdir()
        with open(s1 / "SKILL.md", "w") as f:
            f.write("---\nname: skill-one\ndescription: First skill in collection for testing.\n---\n# S1\n")
        with open(skills_root / "skill-two.md", "w") as f:
            f.write("---\nname: skill-two\ndescription: Second flat skill in collection for testing.\n---\n# S2\n")

        f_root = Findings(skills_root)
        lint_dsh_skill_directory(skills_root, f_root)
        root_errs = [x for x in f_root.items if x["severity"] == "error"]
        assert len(root_errs) == 0, f"Skills root collection produced unexpected errors: {root_errs}"
        print("  ✓ Multi-skill collection root test passed")

        # 5. Test Pre-Publishing Readiness Checklist
        chk = evaluate_skill_publish_checklist(bundle_dir / "SKILL.md", f_bundle)
        assert all(c["status"] == "PASS" for c in chk), f"Checklist failed: {chk}"
        print("  ✓ Skill pre-publishing checklist test passed")

    print("All audit_dsh_skill.py self-tests PASSED (5/5).")


def main():
    parser = argparse.ArgumentParser(description="Audit DeepSeek Harness (DSH) skills.")
    parser.add_argument("path", nargs="?", default=".", help="Path to SKILL.md, <name>.md, or skills root folder.")
    parser.add_argument("--format", choices=["text", "json", "markdown"], default="markdown", help="Output format.")
    parser.add_argument("--strict", action="store_true", help="Fail with non-zero exit code on warnings.")
    parser.add_argument("--publish-check", "--checklist", action="store_true",
                        help="Evaluate DSH skill pre-publishing readiness checklist.")
    parser.add_argument("--check", help="Comma-separated check IDs to filter (e.g. DSK-01,DSK-03).")
    parser.add_argument("--output", help="Write report to specified file path.")
    parser.add_argument("--self-test", action="store_true", help="Run internal self-tests.")

    args = parser.parse_args()

    if args.self_test:
        run_self_test()
        sys.exit(0)

    target_path = Path(args.path).resolve()
    findings = Findings(target_path)
    lint_dsh_skill_directory(target_path, findings)

    checklist_output = ""
    checklist_passed = True
    if args.publish_check:
        skill_target = None
        if target_path.is_file() and target_path.suffix == ".md":
            skill_target = target_path
        elif target_path.is_dir() and (target_path / "SKILL.md").is_file():
            skill_target = target_path / "SKILL.md"

        if skill_target:
            checks = evaluate_skill_publish_checklist(skill_target, findings)
            checklist_output = "\n" + format_skill_checklist_report(checks) + "\n"
            if any(c["status"] == "FAIL" for c in checks):
                checklist_passed = False

    if args.check:
        allowed = set(args.check.split(","))
        findings.items = [x for x in findings.items if x["id"] in allowed]

    if args.format == "json":
        report_output = json.dumps({
            "target": target_path.name,
            "findings": findings.items,
            "notes": findings.notes
        }, indent=2)
    else:
        report_output = format_report_markdown(findings, target_path.name)
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
