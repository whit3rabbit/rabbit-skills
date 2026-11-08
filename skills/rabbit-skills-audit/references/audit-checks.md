# Audit checks: Anthropic Agent Skills best practices, decomposed

Every check derives from the official best-practices guide
(https://platform.claude.com/docs/en/agents-and-tools/agent-skills/best-practices).
Cite the check ID and `file:line` with a verbatim quote in every finding.

## Contents

- [How to read this catalog](#how-to-read-this-catalog)
- [Area MD — Metadata (`lint_metadata`)](#area-md--metadata-lint_metadata)
- [Area ST — Structure and progressive disclosure (`lint_structure`)](#area-st--structure-and-progressive-disclosure-lint_structure)
- [Area CQ — Content quality (`lint_content`)](#area-cq--content-quality-lint_content)
- [Area WF — Workflows and feedback loops (`lint_workflows`)](#area-wf--workflows-and-feedback-loops-lint_workflows)
- [Area SC — Scripts and executable code (`lint_scripts`)](#area-sc--scripts-and-executable-code-lint_scripts)
- [Area EV — Evaluation and testing evidence (`lint_evaluations`)](#area-ev--evaluation-and-testing-evidence-lint_evaluations)
- [Verdict rules](#verdict-rules)

## How to read this catalog

- **Severity** — `error` (violates an explicit rule; blocks), `warning` (violates a strong recommendation), `info` (polish or process evidence; never blocks).
- **Method** — `script` (deterministic check in `scripts/audit_static.py`), `both` (script emits a heuristic `needs_review` flag; agent confirms context), or `judgment` (agent verifies by reading).
- **Verify** — how to confirm and fix. Drop any `needs_review` flag triggered by a quoted anti-pattern example.

---

## Area MD — Metadata (`lint_metadata`)

At startup, only `name` and `description` from all installed skills are pre-loaded into the system prompt (~100 tokens/skill). They drive triggering among 100+ skills and pay a permanent token cost. A structured use-case inventory directly guides writing concise, specific `description` frontmatter that covers both what the skill does and when to use it, preventing scope creep and intent collision across direct and indirect prompts.
Source: "YAML Frontmatter", "Naming conventions", "Writing effective descriptions".

| ID | Severity | Method | Rule |
|----|----------|--------|------|
| MD-01 | error | script | `SKILL.md` exists and starts with a valid YAML frontmatter block delimited by `---`. |
| MD-02 | error | script | `name` key present and non-empty. |
| MD-03 | error | script | `name` is at most 64 characters. |
| MD-04 | error | script | `name` uses lowercase letters, digits, and hyphens only (`[a-z0-9-]`); no leading/trailing/consecutive hyphens; no XML tags. |
| MD-05 | error | script | `name` does not contain reserved words `claude` or `anthropic`. |
| MD-06 | error | script | `name` matches the skill's directory name (required by Claude Code; safest everywhere). |
| MD-07 | info | both | `name` uses the preferred gerund form (`processing-pdfs`, `testing-code`); noun phrases (`pdf-processing`) or action-oriented (`process-pdfs`) are acceptable. |
| MD-08 | warning | both | `name` is specific — not `helper`, `utils`, `tools`, `documents`, `data`, `files`, or similarly generic. |
| MD-09 | error | script | `description` key present and non-empty. |
| MD-10 | error | script | `description` is at most 1,024 characters. |
| MD-11 | error | script | No XML tags (`<...>`) in `description`. |
| MD-12 | warning | both | `description` is written in third person ("Processes Excel files…"), never first/second person ("I can help…", "You can use…"). |
| MD-13 | warning | both | `description` states both **what** the skill does and **when** to use it (explicit triggers/contexts). |
| MD-14 | warning | both | `description` is specific — not "Helps with documents" or "Processes data". Concrete nouns beat adjectives. |
| MD-15 | info | both | Effective keywords present: mentions file extensions, artifacts, and domain terms users actually type (e.g. `.xlsx`, `PDF forms`, `git diffs`). |
| MD-16 | info | judgment | `name` and `description` select cleanly among 100+ skills without colliding with broader intents. |

### Short examples (Area MD)

```yaml
# GOOD: Gerund name, 3rd person, states WHAT + WHEN with concrete keywords
---
name: processing-pdfs
description: Extracts text and tables from PDF files, fills forms, and merges documents. Use when working with PDF files or when the user mentions PDFs, forms, or document extraction.
---

# BAD: Uppercase/underscore name (MD-04), vague (MD-08), 1st/2nd person (MD-12), no trigger (MD-13/MD-14)
---
name: PDF_Helper
description: I can help you do various things with your documents.
---
```

---

## Area ST — Structure and progressive disclosure (`lint_structure`)

`SKILL.md` is an onboarding table of contents loaded when triggered; detailed reference material stays on disk in `references/` at zero token cost until read.
Source: "Progressive disclosure patterns", "Avoid deeply nested references", "Structure longer reference files with a table of contents", "Runtime environment".

| ID | Severity | Method | Rule |
|----|----------|--------|------|
| ST-01 | error | script | `SKILL.md` body is under 500 lines (`ST-01a` info at >400 lines to split soon). |
| ST-02 | warning | both | `SKILL.md` is a high-level overview; heavy reference material or >60-line blocks live in separate files loaded on demand. |
| ST-03 | warning | script | References are **one level deep**: every reference `.md` file links directly from `SKILL.md` (no `SKILL.md -> a.md -> b.md` chains and no unreferenced orphan `.md` files). |
| ST-04 | warning | script | Any reference file over 100 lines includes a `Contents` / `Table of contents` section near the top so partial reads (`head -100`) see the full scope. |
| ST-05 | warning | script | File names are descriptive (`form_validation_rules.md`, `reference/finance.md`) — not `doc2.md`, `misc.md`, `notes.md`, `file1.md`. |
| ST-06 | info | judgment | Multi-domain skills split references by domain (`reference/finance.md`, `reference/sales.md`) or conditional feature (`REDLINING.md`) rather than dumping everything into one file. |

### Short examples (Area ST)

```markdown
<!-- GOOD: One-level references with clear conditional/domain routing -->
## Advanced features
- **Form filling**: See [references/forms.md](references/forms.md)
- **Finance metrics (ARR, billing)**: See [references/finance.md](references/finance.md)

<!-- BAD: Deeply nested chain (ST-03) and generic filenames (ST-05) -->
See [docs/doc1.md](docs/doc1.md) (which then tells the agent to read docs/doc2.md).
```

---

## Area CQ — Content quality (`lint_content`)

The context window is a public good. Assume the model is already smart; only add procedural context it lacks.
Source: "Concise is key", "Set appropriate degrees of freedom", "Avoid time-sensitive information", "Use consistent terminology", "Template pattern", "Examples pattern", "Avoid offering too many options".

| ID | Severity | Method | Rule |
|----|----------|--------|------|
| CQ-01 | warning | both | Concise: no textbook explanations of concepts/libraries the model already knows ("PDF is a common format…"). Target ~50 tokens where padded prose takes ~150. |
| CQ-02 | warning | both | No time-sensitive claims ("before August 2025 use the old API"). Put deprecated info in a collapsed `<details>` block under an `Old patterns` section. |
| CQ-03 | warning | both | Consistent terminology: one term per concept throughout (don't rotate "API endpoint" / "URL" / "route" or "field" / "box" / "control"). |
| CQ-04 | warning | both | Concrete input/output examples (`Input: … Output: …`) or explicit output templates wherever format or style matters (strict templates: "ALWAYS use this exact template"; flexible templates: "sensible default... use best judgment"). |
| CQ-05 | info | both | Degrees of freedom match task fragility (high: heuristics/prose; medium: parameterized scripts/pseudocode; low: exact command with no flags allowed); one recommended default tool plus a targeted escape hatch instead of option dumps ("use pypdf, or pdfplumber, or PyMuPDF…"). |

### Short examples (Area CQ)

````markdown
<!-- GOOD: Concise default + escape hatch (CQ-01, CQ-05) -->
Extract text with `pdfplumber`:
```python
import pdfplumber
with pdfplumber.open("file.pdf") as pdf:
    text = pdf.pages[0].extract_text()
```
For scanned PDFs requiring OCR, use `pdf2image` with `pytesseract` instead.

<!-- BAD: Textbook filler (CQ-01), option dump (CQ-05), time-sensitive (CQ-02) -->
PDF (Portable Document Format) is a common format. Before August 2025, use pypdf,
or pdfplumber, or PyMuPDF, or pdf2image depending on your preference. First install pip...
````

---

## Area WF — Workflows and feedback loops (`lint_workflows`)

Complex tasks need sequential steps, copyable progress checklists, conditional branches, and validation loops. A coverage check ensures every supported use case has an unbroken execution path from user request to verified result, and that write actions require authorization or confirmation.
Source: "Use workflows for complex tasks", "Implement feedback loops", "Conditional workflow pattern".

| ID | Severity | Method | Rule |
|----|----------|--------|------|
| WF-01 | warning | both | Multi-step operations are written as an explicit numbered sequence (`1.`, `Step 1`), not a wall of prose. |
| WF-02 | info | both | Complex or failure-prone workflows include a `- [ ]` checklist the agent copies and tracks, with explicit "return to Step N" recovery rules. |
| WF-03 | warning | both | Quality-critical outputs have a validation feedback loop: run validator (script or checklist) → fix errors → re-validate → proceed only when passing. |
| WF-04 | info | both | Distinct task modes (e.g., Creating new vs. Editing existing) branch explicitly at a decision point before listing steps. |
| WF-05 | info | judgment | Large or specialized workflows are pushed into separate reference files instead of crowding `SKILL.md`. |

### Short examples (Area WF)

```markdown
<!-- GOOD: Copyable checklist + validation feedback loop (WF-01, WF-02, WF-03) -->
Copy this checklist and track progress:
- [ ] Step 1: Analyze form (`python3 scripts/analyze_form.py input.pdf`)
- [ ] Step 2: Edit `fields.json` and validate (`python3 scripts/validate_fields.py fields.json`)
- [ ] Step 3: Fill and verify (`python3 scripts/fill_form.py input.pdf fields.json output.pdf`)

If Step 2 validation fails, fix `fields.json` and re-run validation before proceeding to Step 3.
```

---

## Area SC — Scripts and executable code (`lint_scripts`)

Mark Area SC as `n/a` when a skill ships no scripts (prose path checks `SC-04`, `SC-07`, `SC-08` still run on markdown files).
Source: "Solve, don't defer", "Provide utility scripts", "Create verifiable intermediate outputs", "Package dependencies", "Runtime environment", "MCP tool references", "Avoid assuming tools are installed", "Avoid Windows-style paths".

| ID | Severity | Method | Rule |
|----|----------|--------|------|
| SC-01 | warning | both | Scripts solve rather than defer: foreseeable errors (`FileNotFoundError`, `PermissionError`, parse errors) are caught with fallbacks or actionable messages instead of crashing raw. |
| SC-02 | info | both | No voodoo constants (Ousterhout's law): configuration constants (`REQUEST_TIMEOUT = 30`) have comments justifying the value, no unexplained magic numbers (`TIMEOUT = 47`). |
| SC-03 | warning | both | Execution intent is unambiguous in prose ("Run `scripts/analyze.py`" vs "See `scripts/analyze.py` for the algorithm"), scripts are referenced from docs, and output formats are documented. |
| SC-04 | error | script | Forward slashes only (`scripts/helper.py`) — never Windows-style backslashes (`scripts\helper.py`). |
| SC-05 | warning | both | Dependencies are never assumed: third-party packages used in scripts or markdown code snippets are listed in `SKILL.md` with install commands (`pip install pypdf`) and respect runtime network limits (Claude API has no network access; claude.ai can install from PyPI/npm). |
| SC-06 | info | judgment | High-stakes/batch operations use plan → validate → execute (e.g., write `changes.json`, validate with a script that lists valid options on error, then apply), or visual analysis (render to images for layout inspection). |
| SC-07 | info | both | MCP tool references use fully qualified `ServerName:tool_name` format (`BigQuery:bigquery_schema`, `GitHub:create_issue`). |
| SC-08 | warning | script | Every local file the skill links to or mentions (`scripts/…`, `references/…`, `assets/…`, `evals/…`) exists at that relative path. |

### Short examples (Area SC)

```python
# GOOD: Documented constant (SC-02) + explicit error handling (SC-01)
REQUEST_TIMEOUT = 30  # HTTP requests typically complete within 30s; accounts for slow links

def read_config(path):
    try:
        with open(path, encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        return "{}"  # Safe default instead of crashing and deferring to the agent

# BAD: Magic number (SC-02) + unhandled crash deferred to agent (SC-01)
TIMEOUT = 47
def read_config(path):
    return open(path).read()
```

---

## Area EV — Evaluation and testing evidence (`lint_evaluations`)

Static audit checks for *shipped evidence* of evaluation; runtime behavior itself is always listed under "Not audited" unless live evals are executed. A use-case inventory serves as the primary matrix for generating direct, indirect, edge-case, and negative/out-of-scope test scenarios.
Source: "Build evaluations first", "Test with all models you plan to use", "Develop Skills iteratively with Claude", "Observe how Claude navigates Skills".

| ID | Severity | Method | Rule |
|----|----------|--------|------|
| EV-01 | info | both | At least 3 evaluation scenarios exist (`evals/evals.json` or documented test cases with `query`, `files`, and `expected_behavior`). |
| EV-02 | info | both | Evidence of testing across model tiers (Haiku, Sonnet, Opus or multiple models recorded in `evals` / notes). |
| EV-03 | info | both | Evidence of realistic trigger testing: paraphrased queries tested so the description triggers without exact keyword matching. |
| EV-04 | info | judgment | Evidence that observed agent navigation issues (missed links, ignored files) or team feedback were incorporated. |

### Short examples (Area EV)

```json
{
  "skills": ["processing-pdfs"],
  "query": "Extract all text from this PDF file and save it to output.txt",
  "files": ["test-files/document.pdf"],
  "expected_behavior": [
    "Reads test-files/document.pdf using pdfplumber",
    "Extracts text from all pages into output.txt"
  ]
}
```

---

## Verdict rules

1. Any `error` → **FAIL**.
2. Zero errors, one or more `warning`s → **PASS WITH WARNINGS**.
3. Zero errors and zero warnings → **PASS** (`info` findings allowed).
4. Areas that do not apply (`SC` for a prose-only skill) are marked `n/a` and excluded from counts.
5. Every reported finding requires: check ID, severity, `file:line`, verbatim quote, 1-sentence why, and 1 concrete fix.
