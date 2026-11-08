#!/usr/bin/env python3
"""Modular static linter and pre-share checklist runner for Agent Skills.

Audits skills against Anthropic's Agent Skills best practices:
https://platform.claude.com/docs/en/agents-and-tools/agent-skills/best-practices

Read-only: never executes or imports code from the audited skill. Uses Python's
standard library only (`ast`, `re`, `json`, `pathlib`) so it runs in any
environment with python3.

Linter functions by area:
  - lint_metadata(ctx)     -> Area MD (MD-01 .. MD-15)
  - lint_structure(ctx)    -> Area ST (ST-01 .. ST-05)
  - lint_content(ctx)      -> Area CQ (CQ-01 .. CQ-05)
  - lint_workflows(ctx)    -> Area WF (WF-01 .. WF-04)
  - lint_scripts(ctx)      -> Area SC (SC-01 .. SC-08)
  - lint_evaluations(ctx)  -> Area EV (EV-01 .. EV-03)
  - evaluate_checklist(ctx)-> 22-item official Pre-Share Checklist

Usage:
  python3 audit_static.py <skill-dir-or-parent> [--format text|json|markdown]
                          [--area MD,ST,CQ,WF,SC,EV] [--check ID,ID]
                          [--checklist] [--output FILE] [--strict]
  python3 audit_static.py --list-checks
  python3 audit_static.py --self-test
"""

import argparse
import ast
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

try:  # bundled fallback parser lives in this directory
    from frontmatter import parse as _fm_parse
except ImportError:  # exotic invocation (e.g. via symlink): load by file path
    import importlib.util as _ilu

    _spec = _ilu.spec_from_file_location(
        "frontmatter", Path(__file__).with_name("frontmatter.py"))
    _fm = _ilu.module_from_spec(_spec)
    _spec.loader.exec_module(_fm)
    _fm_parse = _fm.parse

STANDARD_URL = ("https://platform.claude.com/docs/en/agents-and-tools/"
                "agent-skills/best-practices")

# Documented thresholds per best-practices guide (no magic numbers / SC-02)
MAX_READ = 2_000_000        # 2 MB cap per file so huge assets never stall the linter
NAME_MAX_CHARS = 64         # Frontmatter validation limit for `name` (MD-03)
DESC_MAX_CHARS = 1024       # Frontmatter validation limit for `description` (MD-10)
DESC_MIN_CHARS = 40         # Minimum chars to plausibly state both what and when (MD-13)
DESC_MIN_WORDS = 10         # Minimum words for keyword richness (MD-15)
BODY_LIMIT = 500            # Maximum recommended SKILL.md body lines (ST-01)
BODY_WARN = 400             # Early-warning threshold for SKILL.md body lines (ST-01a)
BODY_SPLIT_HINT = 300       # Body lines threshold when zero reference files exist (ST-02)
MAX_FENCE_LINES = 80        # Single code block lines in SKILL.md before suggesting extraction (ST-02)
TOC_THRESHOLD = 100         # Reference files >100 lines need a table of contents (ST-04)
TOC_SCAN_LINES = 80         # Top lines scanned when detecting a table of contents (ST-04)
TOC_MIN_LINKS = 3           # Minimum consecutive bullet links to count as a link TOC (ST-04)
CQ02_CAP_PER_FILE = 5       # Cap time-sensitive heuristic flags per file to avoid noise (CQ-02)
WF_MIN_BODY_LINES = 60      # Body length above which ordered workflow steps are expected (WF-01)
WF_CHECKLIST_STEPS = 5      # Step count threshold for suggesting a copyable checklist (WF-02)
MIN_EVAL_SCENARIOS = 3      # Guide requires at least 3 evaluation scenarios (EV-01)

# Trivial numeric literals that do not need a justifying comment under SC-02
TRIVIAL_NUMBERS = {
    -1, 0, 1, 2, 3, 4, 5, 8, 10, 16, 32, 60, 64, 80, 100, 120, 160,
    256, 400, 500, 1000, 1024, 2_000_000,
}

# Check catalog: id -> (title, why it matters, suggested fix)
CHECK_INFO = {
    "MD-01": ("SKILL.md missing or has invalid frontmatter",
              "Harnesses discover skills through SKILL.md starting with a `---` YAML frontmatter block.",
              "Create SKILL.md starting with a `---` frontmatter block containing `name` and `description`."),
    "MD-02": ("`name` missing or empty",
              "The `name` field is the skill's required identifier across harnesses.",
              "Add a `name:` key with a lowercase kebab-case identifier (e.g. `processing-pdfs`)."),
    "MD-03": ("`name` longer than 64 characters",
              "Frontmatter validation rejects `name` values over 64 characters.",
              "Shorten `name` to <= 64 characters and move detail into `description`."),
    "MD-04": ("`name` uses characters other than lowercase letters, digits, hyphens",
              "Frontmatter validation only accepts `[a-z0-9-]` with no XML tags or leading/trailing hyphens.",
              "Rewrite `name` in lowercase kebab-case without spaces, underscores, capitals, or tags."),
    "MD-05": ("`name` contains reserved word `claude` or `anthropic`",
              "Reserved words `claude` and `anthropic` are rejected by frontmatter validation.",
              "Rename the skill without `claude` or `anthropic`."),
    "MD-06": ("`name` does not match the skill directory name",
              "Claude Code requires `name` and the skill directory name to match; other harnesses expect it.",
              "Rename the directory or the `name` field so they are identical."),
    "MD-07": ("`name` not in gerund form",
              "The naming convention prefers gerunds (`processing-pdfs`); noun phrases (`pdf-processing`) are acceptable.",
              "Consider a `verb-ing` gerund name unless a noun phrase is clearer."),
    "MD-08": ("`name` is vague or generic",
              "Generic names (`helper`, `utils`, `tools`, `documents`, `data`, `files`) hurt discovery and organization.",
              "Rename to describe the specific capability (e.g. `processing-pdfs`, `analyzing-spreadsheets`)."),
    "MD-09": ("`description` missing or empty",
              "The `description` is pre-loaded into the system prompt and drives skill selection.",
              "Write a non-empty `description` stating what the skill does and when to use it."),
    "MD-10": ("`description` longer than 1,024 characters",
              "Frontmatter validation rejects descriptions over 1,024 characters, and every character costs startup tokens.",
              "Trim `description` to <= 1,024 characters; move implementation detail into SKILL.md."),
    "MD-11": ("`description` contains XML tags",
              "XML/HTML angle-bracket tags in `description` are rejected by frontmatter validation.",
              "Remove `<...>` tags from `description`."),
    "MD-12": ("`description` is not in third person",
              "Descriptions are injected directly into the system prompt; first/second person causes discovery problems.",
              "Rewrite in third person: 'Processes Excel files and generates reports. Use when...'."),
    "MD-13": ("`description` may not state when to use the skill",
              "Claude selects from 100+ skills using `description`; it needs both what the skill does and when to trigger.",
              "Add explicit trigger conditions: 'Use when working with ... or when the user mentions ...'."),
    "MD-14": ("`description` is too vague",
              "Vague descriptions ('Helps with documents', 'Processes data') fail to trigger on real user requests.",
              "Replace vague verbs with concrete actions, file types, and domain terms."),
    "MD-15": ("`description` lacks specific keywords or artifacts",
              "Including concrete formats, file extensions, and user phrasing enables triggering on paraphrases.",
              "Name specific artifacts, formats, or domains (e.g. `.xlsx`, `PDF forms`, `git diffs`)."),
    "MD-16": ("`name` and `description` may collide with broader intents",
              "Claude selects from 100+ skills using metadata; generic phrasing risks unintended skill triggering.",
              "Refine description and domain keywords to distinguish the skill clearly without colliding with other intents."),
    "ST-01": ("SKILL.md body is 500 lines or more",
              "Best practices keep the SKILL.md body under 500 lines so activation does not bloat context.",
              "Move detailed tables, schemas, or examples into `references/` and link to them from SKILL.md."),
    "ST-01a": ("SKILL.md body is over 400 lines",
               "Approaching the 500-line ceiling; splitting now keeps SKILL.md lean.",
               "Extract the largest reference or workflow section into `references/`."),
    "ST-02": ("SKILL.md embeds heavy detail instead of progressive disclosure",
              "SKILL.md should act as a table of contents while heavy reference material loads on demand.",
              "Move large code blocks or reference tables into `references/` or `scripts/`."),
    "ST-03": ("Reference files are nested more than one level deep or unlinked",
              "Claude may partially read (`head -100`) nested `SKILL.md -> a.md -> b.md` chains or ignore unlinked files.",
              "Link every reference file directly from SKILL.md."),
    "ST-04": ("Reference file over 100 lines has no table of contents",
              "A table of contents near the top lets Claude see the full scope even on partial preview reads.",
              "Add a `## Contents` section with section links near the top of the file."),
    "ST-05": ("Non-descriptive file name",
              "Descriptive names (`form_validation_rules.md`, not `doc1.md`) let the agent navigate without opening every file.",
              "Rename the file to reflect its domain and contents."),
    "ST-06": ("Multi-domain skill not split into separate domain references",
              "Loading irrelevant domains bloats the context window during execution.",
              "Split reference files by domain (e.g. `reference/finance.md`) or conditional feature."),
    "CQ-01": ("Verbose or textbook explanation of standard concepts",
              "The context window is a public good; assume Claude already knows standard formats and libraries.",
              "Delete introductory definitions and keep only the specific command, pattern, or rule (~50 tokens)."),
    "CQ-02": ("Possible time-sensitive statement",
              "Date-relative instructions ('before August 2025') silently become wrong over time.",
              "Anchor to versions or move legacy instructions into an `Old patterns` `<details>` block."),
    "CQ-03": ("Inconsistent terminology across instructions",
              "Rotating synonyms for the same concept (e.g. endpoint/route/URL/path) confuses instruction following.",
              "Pick one term per concept and use it consistently throughout the skill."),
    "CQ-04": ("No concrete examples or templates found",
              "Input/output pairs and templates communicate expected format and detail better than prose descriptions.",
              "Add concrete `Input:` / `Output:` examples or a copyable output template (strict vs flexible)."),
    "CQ-05": ("Option dump without a clear default ('too many options')",
              "Listing many competing libraries without a single default forces the agent to guess each run.",
              "Recommend one default approach and match degree of freedom to task fragility (high/medium/low)."),
    "WF-01": ("Multi-step instructions lack clear sequential numbering",
              "Complex tasks are more reliable when broken into numbered sequential steps (`1.`, `Step 1`).",
              "Structure the workflow as an ordered step-by-step sequence."),
    "WF-02": ("Complex workflow has no copyable progress checklist",
              "A `- [ ] Step N` checklist helps the agent track state across multi-step operations.",
              "Add a copyable markdown checklist for the workflow steps."),
    "WF-03": ("Workflow lacks an explicit validation feedback loop",
              "Run validator -> fix errors -> repeat loops catch mistakes before finalizing output.",
              "Add a validation step with an explicit 'if validation fails, fix and re-run before proceeding' rule."),
    "WF-04": ("Conditional workflow modes could branch explicitly",
              "Distinct modes (e.g. create vs. edit) work best with an explicit decision point.",
              "Add a decision point routing each mode to its own steps."),
    "WF-05": ("Large or complex workflow crowded into SKILL.md",
              "Complex multi-step workflows in SKILL.md inflate initial activation token cost.",
              "Move large or specialized workflow procedures into dedicated reference files."),
    "SC-01": ("Script may defer errors instead of handling them explicitly",
              "Scripts should handle foreseeable I/O or parse errors with helpful messages or fallbacks.",
              "Wrap file/network/parse operations in `try/except` with actionable error output or safe defaults."),
    "SC-02": ("Unjustified magic number ('voodoo constant') in script",
              "Per Ousterhout's law, configuration constants need a comment explaining why that value was chosen.",
              "Document the constant with a comment justifying its value."),
    "SC-03": ("Script is unreferenced or lacks clear execution/documentation intent",
              "Instructions should state whether to run a script (`Run scripts/x.py`) or read it as reference, and scripts need docstrings.",
              "Reference the script in SKILL.md with explicit run/read intent and add a module docstring."),
    "SC-04": ("Windows-style backslash path",
              "Backslash paths (`scripts\\helper.py`) fail on Unix/macOS execution environments.",
              "Replace backslashes with forward slashes (`scripts/helper.py`)."),
    "SC-05": ("Third-party package imported in script without install instructions in SKILL.md",
              "Skills must not assume non-stdlib packages are pre-installed and must respect runtime network limits.",
              "List required packages in SKILL.md with install commands (e.g. `pip install <pkg>`)."),
    "SC-06": ("High-stakes or batch operation lacks plan-validate-execute pattern",
              "Validating an intermediate plan file before applying batch/destructive changes prevents partial corruption.",
              "Add an intermediate plan artifact, validation script step, or visual analysis before execution."),
    "SC-07": ("Unqualified MCP tool reference",
              "MCP tools referenced without `ServerName:tool_name` may fail with tool-not-found errors.",
              "Qualify MCP tool names as `ServerName:tool_name` (e.g. `BigQuery:bigquery_schema`)."),
    "SC-08": ("Referenced file does not exist",
              "Broken file links or script paths cause tool errors and wasted turns during execution.",
              "Fix the relative path or create the missing file."),
    "EV-01": ("Fewer than 3 evaluation scenarios shipped",
              "The best-practices guide recommends building at least 3 evaluation scenarios covering real gaps.",
              "Add an `evals/evals.json` file with at least 3 `{query, files, expected_behavior}` scenarios."),
    "EV-02": ("No cross-model testing evidence recorded",
              "Skills behave differently across Haiku (needs detail), Sonnet, and Opus (avoids over-explaining).",
              "Test the skill across target models and record results in `evals/evals.json`."),
    "EV-03": ("No trigger-paraphrase evaluation scenarios found",
              "Testing paraphrased queries verifies the description triggers when users don't type exact keywords.",
              "Add an evaluation query that paraphrases the task without using the skill's exact name."),
    "EV-04": ("No evidence that observed agent navigation or team feedback was incorporated",
              "Skills improve iteratively by observing model navigation failures or collecting team feedback.",
              "Document iterations or team feedback in `evals/` or project documentation."),
}

VAGUE_NAMES = {
    "helper", "helpers", "utils", "util", "utilities", "tools", "tool",
    "documents", "document", "docs", "data", "files", "file", "misc",
    "stuff", "general", "common", "assistant", "support", "miscellaneous",
}
NON_GERUNDS = {
    "string", "spring", "ping", "ring", "wing", "king", "thing",
    "anything", "everything", "something", "nothing", "bring", "sing",
    "cling", "fling", "sling", "sting", "swing", "wring",
}
XML_TAG_RE = re.compile(r"</?[A-Za-z][A-Za-z0-9_:-]*(?:\s[^<>]*)?>")
VAGUE_DESC = (
    "helps with", "does stuff", "deals with", "various things",
    "general tasks", "anything you", "useful for many", "processes data",
    "manages files", "works with files",
)
TEXTBOOK_PHRASES = (
    r"\bis a common file format\b",
    r"\byou(?:'ll| will) need to install it using\b",
    r"\bthere are many libraries available for\b",
    r"\bportable document format\b",
)
OPTION_DUMP_RE = re.compile(
    r"\b(?:you can use|use|try|choose from)\s+[A-Za-z0-9_-]+(?:\s*,\s*(?:or\s+)?[A-Za-z0-9_-]+){2,}\s*,\s*or\b",
    re.IGNORECASE,
)
SCRIPT_EXTS = {".py", ".js", ".ts", ".sh", ".rb", ".pl", ".ps1", ".lua", ".rs", ".go", ".mjs", ".cjs"}
BAD_FILENAME = re.compile(
    r"^(doc|file|page|untitled|new|misc|temp|notes|draft|copy|final)[-_ ]?\d*\.(md|py|txt|json|sh)$",
    re.IGNORECASE,
)
MONTHS = (r"january|february|march|april|may|june|july|august|september|october|"
          r"november|december")
STDLIB_MODULES = set(getattr(sys, "stdlib_module_names", ())) | {
    "__future__", "typing_extensions",
}


def read_text(path):
    """Return (text, error). text is None only when the file cannot be read."""
    try:
        return path.read_text(encoding="utf-8", errors="replace")[:MAX_READ], None
    except OSError as exc:
        return None, str(exc)


def prose_lines(text, skip_details=False):
    """Yield (lineno, line) outside fenced code blocks with inline code blanked.

    When skip_details=True, also skips lines inside `<details>...</details>` or
    under `## Old patterns` / `## Deprecated` sections so legacy notes are not
    false-flagged by CQ-02.
    """
    out, fence, in_details, in_old_section = [], False, False, False
    for i, ln in enumerate(text.splitlines(), 1):
        if re.match(r"^\s*(```|~~~)", ln):
            fence = not fence
            continue
        if fence:
            continue
        if skip_details:
            if re.search(r"<details\b", ln, re.I):
                in_details = True
            if re.search(r"</details>", ln, re.I):
                in_details = False
                continue
            m_head = re.match(r"^(#{1,6})\s+(.*)$", ln)
            if m_head:
                heading = m_head.group(2).lower()
                in_old_section = any(k in heading for k in ("old pattern", "deprecated", "legacy"))
            if in_details or in_old_section:
                continue
        # Strip quoted example strings `"..."` that contain backticks before blanking inline code
        cleaned = re.sub(r"`[^`\n]*`", " ", ln)
        out.append((i, cleaned))
    return out


def resolve_ref(target, file_dir, root):
    """Resolve a relative target against the file's dir, then the skill root."""
    for base in (file_dir, root):
        try:
            cand = (base / target).resolve()
            cand.relative_to(root.resolve())
        except (ValueError, OSError):
            continue
        if cand.is_file():
            return cand
    return None


def _is_illustrative_line(ln):
    """True when a line is a Good/Bad anti-pattern label, example comment, or check-catalog rule row."""
    s = ln.strip()
    return bool(re.match(
        r"^(?:[-*]\s+)?(?:\*\*)?(?:✓|✗|good|bad|avoid|example)\b|"
        r"^#\s*(?:good|bad|avoid|example)\b|"
        r"^<!--\s*(?:good|bad|avoid|example)\b|"
        r"^\|\s*(?:\*\*)?(?:MD|ST|CQ|WF|SC|EV)\b|"
        r"^\|\s*(?:MD|ST|CQ|WF|SC|EV)-\d+[a-z]?\s*\|",
        s, re.I))


def file_refs(text, file_dir, root):
    """Extract local file references with line numbers.

    Includes markdown links outside fenced code blocks plus backtick path
    mentions `(scripts|references|assets|evals)/...` that are not enclosed in
    quoted illustrative strings (e.g. `"Run scripts/analyze.py"`).
    Returns [(target, resolved_or_None, line)].
    """
    refs, fence, example_fence = [], False, False
    for i, ln in enumerate(text.splitlines(), 1):
        if re.match(r"^\s*(```|~~~)", ln):
            fence = not fence
            example_fence = False
            continue
        if fence:
            if _is_illustrative_line(ln):
                example_fence = True
            if example_fence:
                continue
        if _is_illustrative_line(ln):
            continue
        if not fence:
            for m in re.finditer(r"\[[^\]]*\]\(([^)\s]+)[^)]*\)", ln):
                t = m.group(1).split("#")[0]
                if t and not t.startswith(("http://", "https://", "mailto:", "conversation://", "file://")):
                    refs.append((t, resolve_ref(t, file_dir, root), i))
        for m in re.finditer(r"`((?:scripts|references|assets|evals)/[\w./-]+\.[\w]+)`", ln):
            # Skip backtick paths inside double/single quotes on the same line (illustrative quotes)
            before = ln[:m.start()]
            after = ln[m.end():]
            if (before.count('"') % 2 == 1 and '"' in after) or (
                "\u201c" in before and "\u201d" in after
            ):
                continue
            refs.append((m.group(1), resolve_ref(m.group(1), file_dir, root), i))
    return refs


def parse_frontmatter(text):
    """Return (meta, body, name_line, desc_line, fm_error)."""
    lines = text.splitlines()
    if lines and lines[0].startswith("\ufeff"):
        lines[0] = lines[0].lstrip("\ufeff")
    if not lines or lines[0].strip() != "---":
        return {}, text, None, None, "missing opening --- delimiter"
    end = None
    for i in range(1, len(lines)):
        if lines[i].strip() in ("---", "..."):
            end = i
            break
    if end is None:
        return {}, text, None, None, "missing closing --- delimiter"
    meta = {}
    try:
        import yaml  # type: ignore
        loaded = yaml.safe_load("\n".join(lines[1:end]))
        if isinstance(loaded, dict):
            meta = {str(k): ("" if v is None else str(v)) for k, v in loaded.items()}
    except Exception:
        meta = {}
    if not meta:
        result = _fm_parse(text)
        meta = result["meta"]
    name_line = desc_line = None
    for j in range(1, end):
        if re.match(r"^name\s*:", lines[j]) and name_line is None:
            name_line = j + 1
        if re.match(r"^description\s*:", lines[j]) and desc_line is None:
            desc_line = j + 1
    body = "\n".join(lines[end + 1:])
    return meta, body, name_line, desc_line, None


def has_toc(lines):
    """True if the first TOC_SCAN_LINES lines contain a Contents heading or >=3 section links."""
    head = "\n".join(lines[:TOC_SCAN_LINES])
    if re.search(r"^#{1,6}\s.*(contents|table of contents)", head, re.I | re.M):
        return True
    run = best = 0
    for ln in lines[:TOC_SCAN_LINES]:
        if re.match(r"\s*[-*+]\s+\[[^\]]+\]\(", ln):
            run += 1
            best = max(best, run)
        else:
            run = 0
    return best >= TOC_MIN_LINKS


class Findings:
    """Accumulator for audit findings and informational notes."""

    def __init__(self, root):
        self.root = root
        self.items = []
        self.notes = []

    def add(self, cid, severity, file, line, evidence, message=None, needs_review=False):
        title, why, fix = CHECK_INFO.get(cid, (cid, "", ""))
        self.items.append({
            "id": cid,
            "severity": severity,
            "title": title,
            "file": str(file),
            "line": line,
            "evidence": (evidence or "").strip()[:160],
            "message": message or why,
            "why": why,
            "fix": fix,
            "needs_review": needs_review,
        })

    def note(self, text):
        self.notes.append(text)


class SkillContext:
    """Pre-loaded, read-only snapshot of a skill directory for area linters."""

    def __init__(self, skill_dir):
        self.skill_dir = Path(skill_dir).resolve()
        self.findings = Findings(self.skill_dir)
        self.skill_md = self.skill_dir / "SKILL.md"
        self.raw, self.read_err = read_text(self.skill_md)
        if self.raw is not None:
            (self.meta, self.body, self.name_line,
             self.desc_line, self.fm_error) = parse_frontmatter(self.raw)
            self.body_lines = self.body.splitlines()
        else:
            self.meta, self.body = {}, ""
            self.name_line = self.desc_line = None
            self.fm_error = self.read_err or "unreadable"
            self.body_lines = []

        excluded = {"evals", "tests", "test", "__pycache__", "node_modules", ".venv"}
        self.all_files = []
        if self.skill_dir.is_dir():
            self.all_files = [
                p for p in sorted(self.skill_dir.rglob("*"))
                if p.is_file()
                and not any(part.startswith(".") for part in p.relative_to(self.skill_dir).parts)
                and not (set(p.relative_to(self.skill_dir).parts) & excluded)
            ]
        self.md_files = [p for p in self.all_files if p.suffix.lower() == ".md"]
        self.script_files = [p for p in self.all_files if p.suffix.lower() in SCRIPT_EXTS]
        self.has_scripts = bool(self.script_files)
        self.evals_dir = self.skill_dir / "evals"
        self.has_evals_dir = self.evals_dir.is_dir()

    def rel(self, path):
        return str(Path(path).resolve().relative_to(self.skill_dir))


# =============================================================================
# Area Linters (MD, ST, CQ, WF, SC, EV)
# =============================================================================

def lint_metadata(ctx):
    """Area MD: Validate SKILL.md frontmatter, `name`, and `description` (MD-01..MD-15)."""
    f = ctx.findings
    if ctx.raw is None:
        f.add("MD-01", "error", "SKILL.md", 1, ctx.read_err or "unreadable",
              message="SKILL.md is missing or unreadable.")
        return

    if ctx.fm_error is not None or (ctx.name_line is None and ctx.desc_line is None and not ctx.meta):
        first = ctx.raw.splitlines()[0][:80] if ctx.raw.splitlines() else ""
        f.add("MD-01", "error", "SKILL.md", 1, first)

    name = str(ctx.meta.get("name") or "").strip()
    desc = str(ctx.meta.get("description") or "").strip()

    if not name:
        f.add("MD-02", "error", "SKILL.md", ctx.name_line or 2, "")
    else:
        if len(name) > NAME_MAX_CHARS:
            f.add("MD-03", "error", "SKILL.md", ctx.name_line, name)
        if not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", name) or XML_TAG_RE.search(name):
            f.add("MD-04", "error", "SKILL.md", ctx.name_line, name)
        if "claude" in name.lower() or "anthropic" in name.lower():
            f.add("MD-05", "error", "SKILL.md", ctx.name_line, name)
        if name != ctx.skill_dir.name:
            f.add("MD-06", "error", "SKILL.md", ctx.name_line,
                  f"name='{name}' dir='{ctx.skill_dir.name}'")
        tokens_name = re.split(r"[-_]+", name.lower())
        if not any(t.endswith("ing") and len(t) > 4 and t not in NON_GERUNDS for t in tokens_name):
            f.add("MD-07", "info", "SKILL.md", ctx.name_line, name)
        tokens = {t for t in re.split(r"-", name) if t}
        if name in VAGUE_NAMES or (tokens and tokens <= VAGUE_NAMES):
            f.add("MD-08", "warning", "SKILL.md", ctx.name_line, name)

    if not desc:
        f.add("MD-09", "error", "SKILL.md", ctx.desc_line or 3, "")
    else:
        if len(desc) > DESC_MAX_CHARS:
            f.add("MD-10", "error", "SKILL.md", ctx.desc_line, desc[:120] + "…")
        if XML_TAG_RE.search(desc):
            f.add("MD-11", "error", "SKILL.md", ctx.desc_line, desc[:120])
        m = re.search(
            r"\b(i|i'm|i'll|i've|i'd|we|we're|we'll|our|my|me|you|your|yours|let's|let me)\b",
            desc, re.IGNORECASE)
        if m:
            f.add("MD-12", "warning", "SKILL.md", ctx.desc_line,
                  desc[max(0, m.start() - 30):m.end() + 30],
                  message="Description uses first/second person; rewrite in third person.",
                  needs_review=True)
        when_words = ("when", "whenever", "use when", "use if", "use for", "if ", "after",
                      "before", "while", "trigger", "intended for")
        has_when = any(w in desc.lower() for w in when_words) or desc.strip().lower().startswith("use ")
        if len(desc) < DESC_MIN_CHARS or not has_when:
            f.add("MD-13", "warning", "SKILL.md", ctx.desc_line, desc[:120],
                  message="Description may not state when to use the skill.",
                  needs_review=True)
        low = desc.lower()
        if any(v in low for v in VAGUE_DESC):
            f.add("MD-14", "warning", "SKILL.md", ctx.desc_line, desc[:120],
                  message="Description contains vague phrasing.", needs_review=True)
        elif len(desc.split()) < DESC_MIN_WORDS:
            f.add("MD-15", "info", "SKILL.md", ctx.desc_line, desc[:120],
                  message="Short description may lack keywords/artifacts for paraphrase triggering.",
                  needs_review=True)


def lint_structure(ctx):
    """Area ST: Validate progressive disclosure, link depth, TOCs, and filenames (ST-01..ST-05)."""
    if ctx.raw is None:
        return
    f = ctx.findings
    n = len(ctx.body_lines)
    if n >= BODY_LIMIT:
        f.add("ST-01", "error", "SKILL.md", 1, f"{n} body lines (limit {BODY_LIMIT})")
    elif n > BODY_WARN:
        f.add("ST-01a", "info", "SKILL.md", 1, f"{n} body lines (approaching {BODY_LIMIT})")

    other_md = [p for p in ctx.md_files if p != ctx.skill_md]
    if n > BODY_SPLIT_HINT and not other_md:
        f.add("ST-02", "warning", "SKILL.md", 1,
              f"{n} body lines with 0 reference files",
              message="Large SKILL.md with no reference files; consider splitting details into references/.",
              needs_review=True)

    # Check for oversized fenced code blocks inside SKILL.md
    fence_start = None
    for idx, ln in enumerate(ctx.body_lines, 1):
        if re.match(r"^\s*(```|~~~)", ln):
            if fence_start is None:
                fence_start = idx
            else:
                fence_len = idx - fence_start - 1
                if fence_len > MAX_FENCE_LINES:
                    f.add("ST-02", "warning", "SKILL.md", fence_start,
                          f"{fence_len}-line code block in SKILL.md",
                          message="Move large code/template blocks (>80 lines) to references/ or scripts/.",
                          needs_review=True)
                fence_start = None

    # ST-05 descriptive filenames & ST-04 TOC on files > 100 lines
    for p in ctx.all_files:
        if BAD_FILENAME.match(p.name):
            f.add("ST-05", "warning", ctx.rel(p), 1, p.name)
        if p.suffix.lower() == ".md" and p != ctx.skill_md:
            t, _err = read_text(p)
            if t is not None:
                fl = t.splitlines()
                if len(fl) > TOC_THRESHOLD and not has_toc(fl):
                    f.add("ST-04", "warning", ctx.rel(p), 1,
                          f"{len(fl)} lines, no contents section")

    # ST-03: Reference depth via BFS link graph from SKILL.md
    level = {ctx.skill_md.resolve(): 0}
    parent = {}
    frontier = [ctx.skill_md.resolve()]
    while frontier:
        cur = frontier.pop(0)
        t, _err = read_text(cur)
        if t is None:
            continue
        for _target, ref, _line in file_refs(t, cur.parent, ctx.skill_dir):
            if ref is not None and ref.suffix.lower() == ".md" and ref not in level:
                level[ref] = level[cur] + 1
                parent[ref] = cur
                frontier.append(ref)
    for p, lv in sorted(level.items()):
        if lv >= 2:
            chain = []
            cur = p
            while cur in parent:
                chain.append(cur.name)
                cur = parent[cur]
            chain.append("SKILL.md")
            f.add("ST-03", "warning", ctx.rel(p), 1, " -> ".join(reversed(chain)))
    linked = set(level)
    for p in ctx.md_files:
        if p.resolve() not in linked:
            f.note(f"Orphan file (never referenced from SKILL.md): {ctx.rel(p)}")


def lint_content(ctx):
    """Area CQ: Check conciseness, time-sensitivity, examples, and option dumps (CQ-01..CQ-05)."""
    if ctx.raw is None:
        return
    f = ctx.findings

    for p in ctx.md_files:
        t, _err = read_text(p)
        if t is None:
            continue
        rel_p = ctx.rel(p)

        # CQ-01 & CQ-05 on prose lines
        for line_no, frag in prose_lines(t, skip_details=True):
            if _is_illustrative_line(frag):
                continue
            for pat in TEXTBOOK_PHRASES:
                m = re.search(pat, frag, re.I)
                if m:
                    f.add("CQ-01", "warning", rel_p, line_no, frag.strip()[:160],
                          message="Possible textbook filler; assume the model knows standard concepts.",
                          needs_review=True)
                    break
            m_opt = OPTION_DUMP_RE.search(frag)
            if m_opt:
                f.add("CQ-05", "info", rel_p, line_no, frag.strip()[:160],
                      message="Multiple competing options listed; provide one default plus escape hatch.",
                      needs_review=True)

        # CQ-02: Time-sensitive claims outside <details> / Old patterns sections
        flags = 0
        for line_no, frag in prose_lines(t, skip_details=True):
            if _is_illustrative_line(frag):
                continue
            if flags >= CQ02_CAP_PER_FILE:
                break
            for pat in (rf"\b(?:{MONTHS})\s+(?:19|20)\d{{2}}\b",
                        r"\b(?:before|after|since|until|as of)\s+(?:19|20)\d{2}\b",
                        r"\bcurrently\b"):
                mm = re.search(pat, frag, re.I)
                if mm:
                    f.add("CQ-02", "warning", rel_p, line_no, frag.strip()[:160],
                          message="Review for time-sensitivity; anchor to versions or Old patterns instead.",
                          needs_review=True)
                    flags += 1
                    break
        if flags >= CQ02_CAP_PER_FILE:
            f.note(f"CQ-02 flags capped at {CQ02_CAP_PER_FILE} in {rel_p}")

    # CQ-03: Inconsistent terminology heuristic (e.g. endpoint vs route)
    terms_endpoints, terms_routes = [], []
    for p in ctx.md_files:
        t, _err = read_text(p)
        if t is None:
            continue
        rel_p = ctx.rel(p)
        for line_no, frag in prose_lines(t, skip_details=True):
            if _is_illustrative_line(frag):
                continue
            if re.search(r"\b(?:api\s+)?endpoints?\b", frag, re.I):
                terms_endpoints.append((rel_p, line_no))
            if re.search(r"\b(?:api\s+)?routes?\b", frag, re.I):
                terms_routes.append((rel_p, line_no))
    if len(terms_endpoints) >= 2 and len(terms_routes) >= 2:
        rel_f, lno = terms_routes[0]
        f.add("CQ-03", "warning", rel_f, lno,
              f"endpoints ({len(terms_endpoints)}x) vs routes ({len(terms_routes)}x)",
              message="Possible inconsistent terminology across instructions; standardize on one term.",
              needs_review=True)

    # CQ-04: Concrete examples check across SKILL.md and linked markdown files
    if len(ctx.body_lines) >= WF_MIN_BODY_LINES:
        has_examples = False
        for p in ctx.md_files:
            t, _err = read_text(p)
            if t and (re.search(r"^\s*(```|~~~)", t, re.M) or
                      re.search(r"\b(example\s*\d*|input\s*:|output\s*:)\b", t, re.I)):
                has_examples = True
                break
        if not has_examples:
            f.add("CQ-04", "warning", "SKILL.md", 1,
                  "No code blocks or Input/Output examples found",
                  message="Add concrete input/output examples or templates to clarify expected output.",
                  needs_review=True)


def lint_workflows(ctx):
    """Area WF: Check sequential steps, checklists, and validation feedback loops (WF-01..WF-04)."""
    if ctx.raw is None or len(ctx.body_lines) < WF_MIN_BODY_LINES:
        return
    f = ctx.findings

    all_md_text = "\n".join(filter(None, (read_text(p)[0] for p in ctx.md_files)))
    step_matches = re.findall(r"^(?:\s*\d+\.\s+|\s*#{2,4}\s*Step\s+\d+|\s*\*\*Step\s+\d+)", ctx.body, re.M | re.I)
    has_checklist = bool(re.search(r"^\s*[-*+]\s+\[\s*[xX ]?\s*\]", all_md_text, re.M))
    has_validation_loop = bool(re.search(
        r"\b(validat\w+|verif\w+|re-?run|check\s+that|only\s+proceed|if\s+.*?\s+fails|return\s+to\s+step)\b",
        all_md_text, re.I))

    if not step_matches:
        f.add("WF-01", "warning", "SKILL.md", 1,
              f"{len(ctx.body_lines)} lines with no numbered workflow steps",
              message="Break multi-step operations into numbered sequential steps.",
              needs_review=True)
    else:
        if len(step_matches) >= WF_CHECKLIST_STEPS and not has_checklist:
            f.add("WF-02", "info", "SKILL.md", 1,
                  f"{len(step_matches)} numbered steps, no `- [ ]` progress checklist",
                  message="Consider adding a copyable `- [ ]` checklist for multi-step tracking.",
                  needs_review=True)
        if len(step_matches) >= 3 and not has_validation_loop:
            f.add("WF-03", "warning", "SKILL.md", 1,
                  f"{len(step_matches)} steps without validation/verification loop keywords",
                  message="Include a validate -> fix -> re-validate feedback loop for quality-critical workflows.",
                  needs_review=True)

        has_mode_contrasts = bool(re.search(r"\b(?:creating\s+new\b.*\bediting\s+existing|creation\s+workflow\b.*\bediting\s+workflow)\b", ctx.body, re.I | re.S))
        has_decision_point = bool(re.search(r"\b(?:determine\s+the\s+|decision\s+point|task\s+mode|branch\s+on)\b", ctx.body, re.I))
        if has_mode_contrasts and not has_decision_point:
            f.add("WF-04", "info", "SKILL.md", 1,
                  "Multiple task modes mentioned without explicit decision point",
                  message="Add an explicit decision point routing distinct task modes to their respective steps.",
                  needs_review=True)


def _lint_python_ast(ctx, script_path, text):
    """Static AST analysis of a Python script for SC-01, SC-02, SC-03, SC-05 (never imports/executes)."""
    f = ctx.findings
    rel_p = ctx.rel(script_path)
    lines = text.splitlines()

    try:
        tree = ast.parse(text, filename=str(script_path))
    except SyntaxError as exc:
        f.add("SC-01", "error", rel_p, exc.lineno or 1,
              f"SyntaxError: {exc.msg}",
              message="Python script has a syntax error and cannot run.")
        return set(), set()

    # SC-03: Check for module docstring
    if not ast.get_docstring(tree):
        f.add("SC-03", "info", rel_p, 1, script_path.name,
              message="Script has no module docstring describing its usage and output.",
              needs_review=True)

    # SC-01: Check for risky I/O calls with zero try/except blocks or bare `except: pass`
    has_try = any(isinstance(node, ast.Try) for node in ast.walk(tree))
    io_calls = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ExceptHandler):
            if node.type is None and len(node.body) == 1 and isinstance(node.body[0], ast.Pass):
                f.add("SC-01", "warning", rel_p, node.lineno,
                      lines[node.lineno - 1].strip() if node.lineno <= len(lines) else "except: pass",
                      message="Bare `except: pass` swallows errors silently instead of handling them.",
                      needs_review=True)
        if isinstance(node, ast.Call):
            func_name = ""
            if isinstance(node.func, ast.Name):
                func_name = node.func.id
            elif isinstance(node.func, ast.Attribute):
                func_name = node.func.attr
            if func_name in {"open", "read_text", "write_text", "urlopen", "check_output", "run"}:
                io_calls.append((node.lineno, func_name))
    if io_calls and not has_try:
        lineno, fn = io_calls[0]
        f.add("SC-01", "warning", rel_p, lineno,
              lines[lineno - 1].strip() if lineno <= len(lines) else fn,
              message=f"Script calls `{fn}()` with no `try/except` error handling.",
              needs_review=True)

    # SC-02: Check module-level UPPER_CASE numeric constants for justifying comments
    for node in tree.body:
        if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
            name = node.targets[0].id
            val = node.value
            num = None
            if isinstance(val, ast.Constant) and isinstance(val.value, (int, float)) and not isinstance(val.value, bool):
                num = val.value
            elif isinstance(val, ast.UnaryOp) and isinstance(val.op, ast.USub) and isinstance(val.operand, ast.Constant):
                if isinstance(val.operand.value, (int, float)):
                    num = -val.operand.value
            if num is not None and name.isupper() and "_" in name and num not in TRIVIAL_NUMBERS:
                ln_idx = node.lineno - 1
                has_comment = "#" in lines[ln_idx]
                if not has_comment and ln_idx > 0 and lines[ln_idx - 1].strip().startswith("#"):
                    has_comment = True
                if not has_comment:
                    f.add("SC-02", "info", rel_p, node.lineno,
                          lines[ln_idx].strip(),
                          message=f"Constant `{name} = {num}` has no comment justifying its value.",
                          needs_review=True)

    # SC-05: Collect top-level required imports vs optional try/except imports
    try_Import_nodes = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Try):
            for stmt in node.body:
                for sub in ast.walk(stmt):
                    if isinstance(sub, (ast.Import, ast.ImportFrom)):
                        try_Import_nodes.add(sub)

    required_imports, all_imports = set(), set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                top = alias.name.split(".")[0]
                all_imports.add(top)
                if node not in try_Import_nodes:
                    required_imports.add(top)
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            top = node.module.split(".")[0]
            all_imports.add(top)
            if node not in try_Import_nodes:
                required_imports.add(top)
    return required_imports, all_imports


def lint_scripts(ctx):
    """Area SC: Check paths, broken references, script error handling, constants, and deps (SC-01..SC-08)."""
    if ctx.raw is None:
        return
    f = ctx.findings

    # SC-08: Referenced files exist (markdown links + backtick path mentions)
    seen_missing = set()
    referenced_files = set()
    for p in ctx.md_files:
        t, _err = read_text(p)
        if t is None:
            continue
        for target, ref, line in file_refs(t, p.parent, ctx.skill_dir):
            if ref is not None:
                referenced_files.add(ref.resolve())
            elif (p, target) not in seen_missing:
                seen_missing.add((p, target))
                f.add("SC-08", "warning", ctx.rel(p), line, target,
                      message=f"Referenced path does not exist: {target}",
                      needs_review=True)

    # SC-04: Windows-style backslash paths in prose or code spans
    for p in ctx.md_files:
        t, _err = read_text(p)
        if t is None:
            continue
        rel_p = ctx.rel(p)
        fence = False
        example_fence = False
        for line_no, raw_line in enumerate(t.splitlines(), 1):
            if re.match(r"^\s*(```|~~~)", raw_line):
                fence = not fence
                example_fence = False
                continue
            if fence:
                if _is_illustrative_line(raw_line):
                    example_fence = True
                if example_fence:
                    continue
            if _is_illustrative_line(raw_line):
                continue
            if 'r"' in raw_line or "r'" in raw_line or "\\\\" in raw_line:
                continue
            m = re.search(
                r"[A-Za-z0-9_.\-]+(?:\\[A-Za-z0-9_.\-]+)+\."
                r"(?:py|js|ts|sh|md|json|ya?ml|txt|csv|toml)\b",
                raw_line)
            if m:
                before = raw_line[:m.start()]
                after = raw_line[m.end():]
                if (before.count('"') % 2 == 1 and '"' in after) or (
                    "\u201c" in before and "\u201d" in after
                ):
                    continue
                f.add("SC-04", "error", rel_p, line_no, m.group(0))

    # SC-07: Unqualified MCP tool references
    for p in ctx.md_files:
        t, _err = read_text(p)
        if t is None:
            continue
        rel_p = ctx.rel(p)
        for line_no, frag in prose_lines(t):
            if _is_illustrative_line(frag):
                continue
            m = re.search(r"\b(?:MCP\s+tool|mcp\s+tool)\s+[`'\"]?([A-Za-z0-9_-]+)[`'\"]?", frag, re.I)
            if m:
                tool_ref = m.group(1)
                if ":" not in tool_ref and not any(k in tool_ref.lower() for k in ("name", "call", "use", "reference", "server")):
                    f.add("SC-07", "info", rel_p, line_no, m.group(0),
                          message="MCP tool reference may be unqualified; qualify as `ServerName:tool_name`.",
                          needs_review=True)

    all_md_text = "\n".join(filter(None, (read_text(p)[0] for p in ctx.md_files)))

    # SC-05: Check third-party imports in non-illustrative markdown code blocks
    for p in ctx.md_files:
        t, _err = read_text(p)
        if t is None:
            continue
        rel_p = ctx.rel(p)
        in_py, py_lines, py_start = False, [], 0
        example_block = False
        for lno, ln in enumerate(t.splitlines(), 1):
            if re.match(r"^\s*(```|~~~)python\b", ln, re.I):
                in_py = True
                py_lines = []
                py_start = lno
                example_block = False
                continue
            elif in_py and re.match(r"^\s*(```|~~~)", ln):
                in_py = False
                if not example_block and py_lines:
                    py_code = "\n".join(py_lines)
                    try:
                        tree = ast.parse(py_code)
                        for node in ast.walk(tree):
                            top = None
                            if isinstance(node, ast.Import):
                                for al in node.names:
                                    top = al.name.split(".")[0]
                            elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
                                top = node.module.split(".")[0]
                            if top and top not in STDLIB_MODULES:
                                if not re.search(rf"\b{re.escape(top)}\b", all_md_text, re.I):
                                    f.add("SC-05", "warning", rel_p, py_start, f"import {top}",
                                          message=f"Code snippet imports third-party package `{top}` without install instructions in SKILL.md.",
                                          needs_review=True)
                    except SyntaxError:
                        pass
                continue
            if in_py:
                if _is_illustrative_line(ln):
                    example_block = True
                py_lines.append(ln)

    # Inspect executable scripts if present
    if not ctx.has_scripts:
        return

    sibling_modules = {p.stem for p in ctx.script_files}
    imported_Across_scripts = set()
    third_party_deps = {}

    for sp in ctx.script_files:
        if sp.name in all_md_text:
            referenced_files.add(sp.resolve())
        t, _err = read_text(sp)
        if t is None:
            continue
        if sp.suffix.lower() == ".py":
            req_imps, all_imps = _lint_python_ast(ctx, sp, t)
            imported_Across_scripts |= all_imps
            for mod in sorted(req_imps):
                if mod not in STDLIB_MODULES and mod not in sibling_modules:
                    third_party_deps.setdefault(mod, sp)

    for sp in ctx.script_files:
        if sp.resolve() not in referenced_files and sp.stem not in imported_Across_scripts:
            f.add("SC-03", "warning", ctx.rel(sp), 1, sp.name,
                  message="Script is never referenced in SKILL.md or reference files.",
                  needs_review=True)

    for mod, sp in sorted(third_party_deps.items()):
        if not re.search(rf"\b{re.escape(mod)}\b", all_md_text, re.I):
            f.add("SC-05", "warning", ctx.rel(sp), 1, f"import {mod}",
                  message=f"Script imports third-party package `{mod}` not listed in SKILL.md.",
                  needs_review=True)


def lint_evaluations(ctx):
    """Area EV: Check for shipped evaluation scenarios and testing evidence (EV-01..EV-03)."""
    if ctx.raw is None:
        return
    f = ctx.findings
    if ctx.has_evals_dir:
        f.note("evals/ present; excluded from structure checks (fixtures are test "
               "data, not reference material) and counts toward EV-01 evidence.")
        evals_json = ctx.evals_dir / "evals.json"
        if evals_json.is_file():
            raw_json, _err = read_text(evals_json)
            if raw_json:
                try:
                    data = json.loads(raw_json)
                    scenarios = data.get("evals") if isinstance(data, dict) else data
                    if isinstance(scenarios, list):
                        if len(scenarios) < MIN_EVAL_SCENARIOS:
                            f.add("EV-01", "info", "evals/evals.json", 1,
                                  f"{len(scenarios)} eval scenarios (< {MIN_EVAL_SCENARIOS})",
                                  needs_review=True)
                        else:
                            f.note(f"EV-01 satisfied: {len(scenarios)} scenarios in evals/evals.json.")

                        has_trigger = any(
                            "trigger" in str(s.get("id", "")).lower() or
                            "paraphrase" in str(s.get("id", "")).lower() or
                            "trigger" in str(s.get("query", "")).lower()
                            for s in scenarios if isinstance(s, dict)
                        )
                        if not has_trigger:
                            f.add("EV-03", "info", "evals/evals.json", 1,
                                  "No trigger-paraphrase eval scenarios found",
                                  message="Include evaluation queries that test trigger paraphrases without exact skill name.",
                                  needs_review=True)
                        else:
                            f.note("EV-03 satisfied: trigger-paraphrase scenarios found in evals/evals.json.")

                    if isinstance(data, dict):
                        results = data.get("results") or []
                        tested_models = {r.get("model") for r in results if isinstance(r, dict) and r.get("model")}
                        if len(tested_models) < 2 and not any(
                            any(t in str(m).lower() for t in ("haiku", "sonnet", "opus"))
                            for m in tested_models
                        ):
                            f.add("EV-02", "info", "evals/evals.json", 1,
                                  f"{len(tested_models)} model(s) tested in results[]",
                                  message="Test skill across multiple model tiers (e.g. Haiku, Sonnet, Opus) and record in results[].",
                                  needs_review=True)
                        elif tested_models:
                            f.note(f"EV-02 satisfied: results recorded across {len(tested_models)} model(s) ({', '.join(sorted(tested_models))}).")
                except json.JSONDecodeError as exc:
                    f.add("EV-01", "warning", "evals/evals.json", exc.lineno or 1,
                          f"Invalid JSON: {exc.msg}")


# Ordered registry of area linters
AREA_LINTERS = {
    "MD": lint_metadata,
    "ST": lint_structure,
    "CQ": lint_content,
    "WF": lint_workflows,
    "SC": lint_scripts,
    "EV": lint_evaluations,
}


# =============================================================================
# Programmable Pre-Share Checklist Evaluator
# =============================================================================

CHECKLIST_SPEC = [
    # (section, item_text, related_check_ids, requires_scripts, judgment_only)
    ("Core quality", "Description is specific and includes key terms", ["MD-14", "MD-15"], False, False),
    ("Core quality", "Description includes both what the Skill does and when to use it", ["MD-09", "MD-12", "MD-13"], False, False),
    ("Core quality", "SKILL.md body is under 500 lines", ["ST-01"], False, False),
    ("Core quality", "Additional details are in separate files, if needed", ["ST-02", "ST-06"], False, False),
    ("Core quality", "No time-sensitive information, or it lives in an 'old patterns' section", ["CQ-02"], False, False),
    ("Core quality", "Consistent terminology throughout", ["CQ-03"], False, True),
    ("Core quality", "Examples are concrete, not abstract", ["CQ-04"], False, False),
    ("Core quality", "File references are one level deep", ["ST-03"], False, False),
    ("Core quality", "Progressive disclosure used appropriately", ["ST-02", "ST-04", "ST-05"], False, False),
    ("Core quality", "Workflows have clear steps", ["WF-01"], False, False),
    ("Code and scripts", "Scripts solve problems rather than defer to Claude", ["SC-01"], True, False),
    ("Code and scripts", "Error handling is explicit and helpful", ["SC-01"], True, False),
    ("Code and scripts", "No 'voodoo constants'; every value is justified", ["SC-02"], True, False),
    ("Code and scripts", "Required packages are listed in instructions and verified as available", ["SC-05"], True, False),
    ("Code and scripts", "Scripts have clear documentation", ["SC-03"], True, False),
    ("Code and scripts", "No Windows-style paths; forward slashes only", ["SC-04", "SC-08"], False, False),
    ("Code and scripts", "Validation and verification steps for critical operations", ["SC-06"], True, True),
    ("Code and scripts", "Feedback loops included for quality-critical tasks", ["WF-03"], False, False),
    ("Testing", "At least three evaluations created", ["EV-01"], False, False),
    ("Testing", "Tested across model tiers (Haiku, Sonnet, Opus)", ["EV-02"], False, True),
    ("Testing", "Tested with real usage scenarios", ["EV-03"], False, False),
    ("Testing", "Team feedback incorporated, if applicable", ["EV-04"], False, True),
]


def evaluate_checklist(ctx):
    """Evaluate the 22-item official Pre-Share Checklist against findings and skill inventory."""
    by_id = {}
    for it in ctx.findings.items:
        by_id.setdefault(it["id"], []).append(it)

    n_lines = len(ctx.body_lines)
    other_md = [p for p in ctx.md_files if p != ctx.skill_md]
    eval_count = 0
    has_results = False
    has_multi_models = False
    models_in_res = set()
    has_trigger_eval = False
    evals_json = ctx.evals_dir / "evals.json"
    if evals_json.is_file():
        raw_json, _ = read_text(evals_json)
        if raw_json:
            try:
                data = json.loads(raw_json)
                if isinstance(data, dict):
                    evs = data.get("evals") or []
                    eval_count = len(evs) if isinstance(evs, list) else 0
                    res = data.get("results") or []
                    models_in_res = {r.get("model") for r in res if isinstance(r, dict) and r.get("model")}
                    has_multi_models = len(models_in_res) >= 2 or any(
                        any(t in str(m).lower() for t in ("haiku", "sonnet", "opus"))
                        for m in models_in_res
                    )
                    has_trigger_eval = any(
                        "trigger" in str(e.get("id", "")).lower() or
                        "paraphrase" in str(e.get("id", "")).lower()
                        for e in evs if isinstance(e, dict)
                    )
            except json.JSONDecodeError:
                pass

    items = []
    for section, label, cids, req_scripts, judge_only in CHECKLIST_SPEC:
        if req_scripts and not ctx.has_scripts:
            items.append({
                "section": section, "item": label, "checks": cids,
                "status": "na", "evidence": "n/a — no executable scripts shipped",
            })
            continue

        matched = [f for cid in cids for f in by_id.get(cid, [])]
        hard_Issues = [f for f in matched if not f.get("needs_review") and f["severity"] in ("error", "warning")]
        review_issues = [f for f in matched if f.get("needs_review") or f["severity"] == "info"]

        if hard_Issues:
            first = hard_Issues[0]
            items.append({
                "section": section, "item": label, "checks": cids,
                "status": "fail",
                "evidence": f"Open finding {first['id']} at {first['file']}:{first['line']}",
            })
        elif review_issues:
            first = review_issues[0]
            items.append({
                "section": section, "item": label, "checks": cids,
                "status": "review",
                "evidence": f"Verify {first['id']} at {first['file']}:{first['line']}",
            })
        elif section == "Testing":
            if "EV-01" in cids:
                if eval_count >= MIN_EVAL_SCENARIOS:
                    items.append({
                        "section": section, "item": label, "checks": cids,
                        "status": "pass",
                        "evidence": f"evals/evals.json ({eval_count} scenarios) [EV-01]",
                    })
                else:
                    items.append({
                        "section": section, "item": label, "checks": cids,
                        "status": "review",
                        "evidence": "No evals/evals.json with >=3 scenarios found [EV-01]",
                    })
            elif "EV-02" in cids:
                items.append({
                    "section": section, "item": label, "checks": cids,
                    "status": "pass" if has_multi_models else "review",
                    "evidence": f"evals/evals.json ({len(models_in_res)} models tested) [EV-02]" if has_multi_models else "Verify cross-model runs across tiers (Haiku, Sonnet, Opus) in evals/evals.json [EV-02]",
                })
            elif "EV-03" in cids:
                items.append({
                    "section": section, "item": label, "checks": cids,
                    "status": "pass" if has_trigger_eval else "review",
                    "evidence": "evals/evals.json trigger scenarios [EV-03]" if has_trigger_eval else "Verify real usage / trigger scenarios [EV-03]",
                })
            else:
                items.append({
                    "section": section, "item": label, "checks": cids,
                    "status": "review",
                    "evidence": "Confirm team feedback or mark n/a for solo skill [EV-04]",
                })
        elif judge_only:
            items.append({
                "section": section, "item": label, "checks": cids,
                "status": "review",
                "evidence": f"Static checks clean; confirm {','.join(cids)} by reading",
            })
        else:
            ev = f"Verified by {', '.join(cids)}"
            if "ST-01" in cids:
                ev = f"SKILL.md: {n_lines} body lines (< {BODY_LIMIT}) [ST-01]"
            elif "ST-03" in cids:
                ev = f"{len(other_md)} reference file(s), max depth 1 [ST-03]"
            elif "SC-04" in cids:
                ev = f"All {len(ctx.md_files)} markdown file(s) use forward slashes and valid paths [SC-04, SC-08]"
            items.append({
                "section": section, "item": label, "checks": cids,
                "status": "pass", "evidence": ev,
            })
    return items


def audit_skill(skill_dir, selected_areas=None, selected_checks=None):
    """Run area linters and checklist evaluation on a single skill directory."""
    ctx = SkillContext(skill_dir)
    f = ctx.findings

    areas_to_run = selected_areas or tuple(AREA_LINTERS.keys())
    for area in areas_to_run:
        linter = AREA_LINTERS.get(area)
        if linter is not None:
            linter(ctx)

    if selected_checks:
        f.items = [it for it in f.items if it["id"] in selected_checks]

    if ctx.raw is not None:
        est_tokens = len(ctx.body) // 4
        f.note(f"SKILL.md body: {len(ctx.body_lines)} lines, ~{est_tokens} tokens (chars/4 estimate).")
        if not ctx.has_scripts:
            f.note("No executable code found; area SC marked n/a (script checks SC-04/SC-08 still ran on prose).")

    checklist = evaluate_checklist(ctx)
    return summarize(ctx.skill_dir, f, ctx.has_scripts, checklist)


def summarize(skill_dir, f, has_scripts, checklist=None):
    order = {"error": 0, "warning": 1, "info": 2}
    f.items.sort(key=lambda x: (order.get(x["severity"], 3), x["id"]))
    counts = {"error": 0, "warning": 0, "info": 0}
    areas = {}
    for it in f.items:
        counts[it["severity"]] += 1
        area = it["id"].split("-")[0]
        agg = areas.setdefault(area, {"error": 0, "warning": 0, "info": 0, "na": False})
        agg[it["severity"]] += 1
    for area in areas:
        areas[area]["na"] = (area == "SC" and not has_scripts)
    verdict = ("FAIL" if counts["error"] else
               "PASS WITH WARNINGS" if counts["warning"] else "PASS")
    return {
        "name": skill_dir.name,
        "path": str(skill_dir),
        "verdict": verdict,
        "counts": counts,
        "areas": areas,
        "findings": f.items,
        "notes": f.notes,
        "checklist": checklist or [],
    }


def discover(path):
    path = Path(path).resolve()
    if path.is_file() and path.name == "SKILL.md":
        return [path.parent]
    if (path / "SKILL.md").is_file():
        return [path]
    found = []
    if path.is_dir():
        for child in sorted(path.iterdir()):
            if child.is_dir() and (child / "SKILL.md").is_file():
                found.append(child)
                skills_dir = child / "skills"
                if skills_dir.is_dir():
                    for gc in sorted(skills_dir.iterdir()):
                        if gc.is_dir() and (gc / "SKILL.md").is_file():
                            found.append(gc)
    return found


SEV_ICON = {"error": "⛔", "warning": "⚠️ ", "info": "ℹ️ "}
CHK_BOX = {"pass": "[x]", "fail": "[ ]", "review": "[?]", "na": "[n/a]"}


def render_checklist_markdown(checklist):
    out = ["### Pre-share checklist (preliminary)", ""]
    cur_sec = None
    for item in checklist:
        if item["section"] != cur_sec:
            cur_sec = item["section"]
            out.append(f"#### {cur_sec}")
            out.append("")
        box = CHK_BOX.get(item["status"], "[ ]")
        cids = ", ".join(item["checks"])
        out.append(f"- {box} {item['item']} ({cids}) — *{item['evidence']}*")
    out.append("")
    return out


def render_text(result, show_checklist=False):
    out = [f"Skill: {result['name']}  ({result['path']})",
           f"Verdict: {result['verdict']}  "
           f"(errors: {result['counts']['error']}, warnings: {result['counts']['warning']}, "
           f"info: {result['counts']['info']})", ""]
    for it in result["findings"]:
        loc = it["file"] + (f":{it['line']}" if it.get("line") else "")
        out.append(f"{SEV_ICON[it['severity']]} [{it['id']}] {it['title']}  ({loc})")
        if it["evidence"]:
            out.append(f"    evidence: {it['evidence']}")
        if it.get("needs_review"):
            out.append("    (heuristic: verify context before reporting)")
    if result["findings"]:
        out.append("")
    for note in result["notes"]:
        out.append(f"  note: {note}")
    if show_checklist and result.get("checklist"):
        out.append("")
        out.extend(render_checklist_markdown(result["checklist"]))
    return "\n".join(out)


def render_markdown(results):
    out = [f"# Skill audit: {results[0]['name']}" if len(results) == 1
           else "# Skill audit report",
           "",
           f"- Standard: Anthropic Agent Skills best practices ({STANDARD_URL})",
           f"- Generated: {datetime.now(timezone.utc).isoformat(timespec='seconds')} by audit_static.py (static + heuristic linter)",
           "- Judgment checks and `needs_review` heuristics must be verified by the auditor per references/audit-checks.md",
           ""]
    for r in results:
        if len(results) > 1:
            out += [f"## {r['name']}", ""]
        out += [f"**Preliminary verdict: {r['verdict']}** — "
                f"{r['counts']['error']} errors / {r['counts']['warning']} warnings / "
                f"{r['counts']['info']} info", ""]
        grouped = {}
        for it in r["findings"]:
            grouped.setdefault(it["id"].split("-")[0], []).append(it)
        for area in ("MD", "ST", "CQ", "WF", "SC", "EV"):
            items = grouped.get(area, [])
            if not items:
                continue
            out.append(f"### Area {area}")
            out.append("")
            for it in items:
                rev = " *(needs_review)*" if it.get("needs_review") else ""
                out.append(f"- **{it['id']} ({it['severity']})**{rev} {it['title']} — `{it['file']}"
                           + (f":{it['line']}`" if it.get("line") else "`"))
                if it["evidence"]:
                    out.append(f"  - Evidence: `{it['evidence']}`")
                out.append(f"  - Why: {it['why'] or it['message']}")
                if it["fix"]:
                    out.append(f"  - Fix: {it['fix']}")
            out.append("")
        if r.get("checklist"):
            out.extend(render_checklist_markdown(r["checklist"]))
        for note in r["notes"]:
            out.append(f"> note: {note}")
        out.append("")
    return "\n".join(out)


def _list_checks():
    lines = ["ID      Area  Title", "------  ----  --------------------------------------------------------"]
    for cid, (title, _why, _fix) in sorted(CHECK_INFO.items()):
        area = cid.split("-")[0]
        lines.append(f"{cid:<6}  {area:<4}  {title}")
    return "\n".join(lines)


def _self_test():
    """Verify area linters and checklist on `auditing-skills` and `evals/fixtures/bad-skill`."""
    skill_root = Path(__file__).resolve().parent.parent
    bad_skill = skill_root / "evals" / "fixtures" / "bad-skill"
    failures = []

    self_res = audit_skill(skill_root)
    if self_res["counts"]["error"] != 0:
        failures.append(f"self-audit errors: {self_res['findings']}")

    if bad_skill.is_dir():
        bad_res = audit_skill(bad_skill)
        got_ids = {f["id"] for f in bad_res["findings"]}
        expected_ids = {"MD-04", "MD-06", "SC-04", "MD-12", "MD-13", "MD-14", "SC-08", "ST-05", "MD-07"}
        missing = expected_ids - got_ids
        if bad_res["verdict"] != "FAIL" or missing:
            failures.append(f"bad-skill missing expected findings: {missing} (got {got_ids})")
        if not bad_res.get("checklist") or len(bad_res["checklist"]) != len(CHECKLIST_SPEC):
            failures.append("bad-skill checklist evaluation incomplete")

    if failures:
        for msg in failures:
            print(f"FAIL: {msg}")
        return 1
    print(f"pass self-audit ({skill_root.name}: {self_res['verdict']}) and fixture checks ({len(CHECK_INFO)} rules)")
    return 0


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("path", nargs="?", help="skill directory, a SKILL.md file, or a parent containing skills")
    ap.add_argument("--format", choices=("text", "json", "markdown"), default="text")
    ap.add_argument("--area", help="comma-separated areas to lint (MD,ST,CQ,WF,SC,EV)")
    ap.add_argument("--check", help="comma-separated check IDs to filter (e.g. MD-04,SC-04)")
    ap.add_argument("--checklist", action="store_true",
                    help="include the 22-item pre-share checklist in text output")
    ap.add_argument("--list-checks", action="store_true",
                    help="list all supported static and heuristic check IDs")
    ap.add_argument("--self-test", action="store_true",
                    help="run built-in self-audit and fixture tests")
    ap.add_argument("--output", help="write the report to this file instead of stdout")
    ap.add_argument("--strict", action="store_true",
                    help="exit 1 when any error-level finding exists")
    args = ap.parse_args()

    if args.list_checks:
        print(_list_checks())
        return
    if args.self_test:
        sys.exit(_self_test())
    if not args.path:
        ap.print_help()
        sys.exit(2)

    selected_areas = None
    if args.area:
        selected_areas = [a.strip().upper() for a in args.area.split(",") if a.strip()]
    selected_checks = None
    if args.check:
        selected_checks = {c.strip().upper() for c in args.check.split(",") if c.strip()}

    skills = discover(args.path)
    if not skills:
        print(f"No skills found under {args.path} (no SKILL.md).", file=sys.stderr)
        sys.exit(2)

    results = [audit_skill(s, selected_areas=selected_areas, selected_checks=selected_checks)
               for s in skills]
    payload = {
        "standard": STANDARD_URL,
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "skills": results,
    }
    if args.format == "json":
        text = json.dumps(payload, indent=2, ensure_ascii=False)
    elif args.format == "markdown":
        text = render_markdown(results)
    else:
        text = "\n\n".join(render_text(r, show_checklist=args.checklist) for r in results)

    if args.output:
        Path(args.output).write_text(text + "\n", encoding="utf-8")
        print(f"Report written to {args.output}", file=sys.stderr)
    else:
        print(text)

    if args.strict and any(r["counts"]["error"] for r in results):
        sys.exit(1)


if __name__ == "__main__":
    main()
