# Report template and severity model

Severity definitions and verdict math are normative (matching
[audit-checks.md](audit-checks.md)); the report template below is copy-paste.

## Severity model

| Severity | Meaning | Verdict effect |
|----------|---------|----------------|
| `error` | Violates an explicit rule (frontmatter validation, 500-line limit, backslash paths). | Any error → **FAIL** |
| `warning` | Violates a strong recommendation (third-person description, 1-level references, examples, error handling). | 0 errors + warnings → **PASS WITH WARNINGS** |
| `info` | Polish or process evidence (gerund name, shipped evals, degree-of-freedom tuning). | 0 errors + 0 warnings → **PASS** |

Areas that do not apply (`SC` for prose-only skills) are marked `n/a` and excluded from
verdict math. Heuristic flags marked `needs_review` by `scripts/audit_static.py` must be
confirmed or dropped before computing the final verdict.

## Template

```markdown
# Skill audit: <skill-name>

- **Path:** <path> · **Date:** <YYYY-MM-DD> · **Auditor:** auditing-skills
- **Standard:** Anthropic Agent Skills best practices
  (https://platform.claude.com/docs/en/agents-and-tools/agent-skills/best-practices)
- **Verdict:** <FAIL | PASS WITH WARNINGS | PASS> — <e> errors, <w> warnings, <i> info

## Summary by area

| Area | Linter function | Status | Findings (e/w/i) |
|------|-----------------|--------|------------------|
| MD — Metadata | `lint_metadata` | pass / warn / fail | 0/0/0 |
| ST — Structure | `lint_structure` | pass / warn / fail | 0/0/0 |
| CQ — Content quality | `lint_content` | pass / warn / fail | 0/0/0 |
| WF — Workflows | `lint_workflows` | pass / warn / fail | 0/0/0 |
| SC — Scripts & code | `lint_scripts` | pass / warn / fail / n/a | 0/0/0 |
| EV — Evaluations | `lint_evaluations` | pass / info | 0/0/0 |

## Findings

### <CHECK-ID> · <severity> · <title>
- **Evidence:** `<file>:<line>` — "<verbatim quote>"
- **Why:** <one sentence tied to the best practice>
- **Fix:** <concrete, copy-pasteable rewrite or command>

## Pre-share checklist (22 items)

<Paste completed checklist from references/pre-share-checklist.md with [x], [ ], or [n/a] and evidence>

## Strengths

- <2–4 practices the skill already does well, cited by check ID and file:line>

## Not audited

- <e.g. "Runtime behavior and live trigger accuracy — static audit only">
```

## Writing findings that help LLMs fix skills

1. **Quote verbatim:** Never paraphrase the evidence line.
2. **Show the exact rewrite:** Don't say "make description third person"; provide the exact replacement YAML or markdown snippet so an LLM or author can apply it immediately.
3. **Drop false positives silently:** If a `needs_review` heuristic fired on a quoted anti-pattern example, omit it from the report.
4. **Batch mode:** When auditing multiple skills, start with a cross-skill table (`Skill | Verdict | Errors | Warnings | Top Fix`) followed by per-skill sections.
