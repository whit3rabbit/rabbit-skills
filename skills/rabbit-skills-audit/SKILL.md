---
name: rabbit-skills-audit
description: Scaffold, audit, lint, and deploy agent skills against Anthropic's 45 best practices across 31 harnesses (Claude Code, DeepSeek Harness, Cursor, Antigravity). Use when creating, auditing, linting, scoring, or placing skills across harnesses.
---

# Auditing and Improving Agent Skills

Audit or improve any `SKILL.md`-based skill against Anthropic's Agent Skills best practices
(https://platform.claude.com/docs/en/agents-and-tools/agent-skills/best-practices).

## How Agent Skills work (mental model for any LLM)

Skills use a 3-tier progressive disclosure lifecycle to protect the context window:

1. **Discovery (always in system prompt, ~100 tokens):** Only `name` and `description` from YAML frontmatter load at startup. They alone determine whether the agent selects the skill among 100+ options.
2. **Activation (loaded when triggered):** The `SKILL.md` body (<500 lines) acts as a high-level guide and table of contents.
3. **On-demand resources (zero tokens until needed):** `references/*.md` (linked 1 level deep from `SKILL.md`) are read only when needed; `scripts/*` are executed via bash so only their output consumes tokens.

## Auditable areas, linter functions, and quick examples

`scripts/audit_static.py` (stdlib-only `python3`, no packages to install) provides modular linter functions per area plus `evaluate_checklist`:

| Area | Linter function | Checks | Bad example | Good example |
|------|-----------------|--------|-------------|--------------|
| **MD** Metadata | `lint_metadata` | MD-01 – MD-16 | `name: PDF_Helper`<br>`description: I can help you with docs.` | `name: processing-pdfs`<br>`description: Extracts text and tables from PDFs. Use when working with PDF files or forms.` |
| **ST** Structure | `lint_structure` | ST-01 – ST-06 | 800-line `SKILL.md`, `docs/doc1.md -> doc2.md` | <500-line `SKILL.md` linking directly to `references/audit-checks.md` (with `## Contents` if >100 lines) |
| **CQ** Content | `lint_content` | CQ-01 – CQ-05 | "PDF is a common format… Use pypdf, or pdfplumber, or PyMuPDF…" | Concise (~50 tokens), 1 default (`pdfplumber`) + OCR escape hatch, `Input:`/`Output:` examples |
| **WF** Workflows | `lint_workflows` | WF-01 – WF-05 | Unnumbered wall of prose with no verification | Numbered steps, copyable `- [ ]` checklist, and "run validator → fix → repeat" loop |
| **SC** Scripts | `lint_scripts` | SC-01 – SC-08 | `"scripts\run.py"`, `TIMEOUT = 47`, bare `open(p).read()` | `scripts/audit_static.py`, justified constants, explicit `try/except`, `pip install` listed, `Server:tool` MCP names |
| **EV** Evaluations | `lint_evaluations` | EV-01 – EV-04 | Zero test scenarios or trigger checks | `evals/evals.json` with ≥3 `{query, files, expected_behavior}` scenarios tested across models |

Read [`references/audit-checks.md`](references/audit-checks.md) before your first audit of a session for the full 45-check catalog, severities, and per-area examples.

## Safety rules

- **Read-only audit:** Never execute or import code from the audited skill, and never install its dependencies. `scripts/audit_static.py` inspects target scripts using `ast.parse` and regex only.
- **Archives:** Extract `.zip`/`.tar`/`.tgz` archives into a fresh temporary directory first and treat contents as untrusted files.
- **Fact-only reporting:** Every finding requires a check ID, severity, `file:line`, and verbatim quote. Runtime behavior and live trigger rates go under "Not audited" unless live evaluations are run.

## Task Routing (Auditing vs. Creating vs. Multi-Harness Deployment)

Match the user's intent to the appropriate task mode:

| Task Mode | Intent / Trigger Keywords | Action Sequence |
|---|---|---|
| **Mode 1: Create a Skill** | "create", "new skill", "scaffold", "build a skill", "write a skill", "author" | Run **Creation Workflow** (`scripts/scaffold_skill.py`) |
| **Mode 2: Audit a Skill** | "audit", "lint", "review", "check", "score", "evaluate", "is it compliant" | Run **Audit Workflow** (`scripts/audit_static.py`) |
| **Mode 3: Fix / Improve** | "fix warnings", "improve skill", "make it pass", "clean up" | Run Step 6 **Improvement Feedback Loop** |
| **Mode 4: Multi-Harness Deploy** | "place into...", "install to claude and cursor", "deploy across harnesses" | Run `scaffold_skill.py --harness id1,id2 [--symlink]` |

---

### Mode 1: Creation Workflow (Born Clean)

When asked to create a new skill:

1. **Intake & Use-Case Planning:**
   - **Brainstorm User Expectations:** List what users will reasonably expect from the skill's name, description, and keywords. Gather direct requests (naming the skill) and indirect requests (stating the user's goal without naming the skill).
   - **Build Use-Case Inventory:** Map each supported workflow:
     - *User goal:* What the person is trying to accomplish.
     - *Example requests:* Direct and indirect prompt phrasing.
     - *Expected result:* Tangible output that defines success.
     - *Required context:* Files, dependencies, environment state, or permissions needed.
     - *Capability choice:* Skill (`SKILL.md`) vs. external tool/script vs. UI.
     - *Safety boundary:* Data exposure, state mutation, filesystem changes, or side effects.
     - *Support decision:* Support in v1, defer, or intentionally exclude.
   - **Check Coverage & Exclusions:** Confirm an unbroken path from request to verified result. Ensure scripts/tools complete recognizable user goals rather than exposing raw technical mechanics. Document intentional exclusions with clear rationales (safety risks, unverified permissions, API unreliability) to define refusal behaviors and negative tests.
   - **Choose the Smallest Implementation:**
     - Add a **skill** when instructions, examples, or bundled resources guide the model through the workflow.
     - Add a **script or MCP tool** when the workflow requires live data, authentication, controlled tools, or runtime code execution.
     - Add **UI** only when visual interaction materially improves the workflow.
2. **Scaffold with `scripts/scaffold_skill.py`:** Run:
   ```bash
   # Single or multi-harness deployment:
   python3 scripts/scaffold_skill.py <skill-name> --harness claude-code,cursor --scope project --freedom medium
   ```
   This generates `SKILL.md`, `"references/reference.md"` (with TOC), `"evals/evals.json"` (3 scenarios with paraphrase triggers), and optional helper scripts.
3. **Draft Implementation:** Add specialized procedural patterns, concrete I/O examples, and verification steps.
4. **Immediate Audit Gate:** Run `python3 scripts/audit_static.py <new-skill-path> --strict`. Fix any warnings before presenting to the user.

---

### Mode 2: Audit Workflow

Copy this checklist and track progress:

```markdown
Audit Progress:
- [ ] Step 1: Inventory the skill directory and files
- [ ] Step 2: Run static linter and checklist evaluator (`scripts/audit_static.py`)
- [ ] Step 3: Judge prose quality, workflows, and `needs_review` flags against `references/audit-checks.md`
- [ ] Step 4: Verify all 22 items in `references/pre-share-checklist.md`
- [ ] Step 5: Compile report using `references/report-template.md`
- [ ] Step 6 (if improving): Apply fixes and re-run `scripts/audit_static.py --strict` until 0 errors remain
```

**Step 1: Inventory.** Locate `SKILL.md` and list all files in the skill directory.

**Step 2: Run static linter and checklist.** Run the linter using `scripts/audit_static.py` within this skill's installation directory (or relative to the workspace):

```bash
# From this skill's directory:
python3 scripts/audit_static.py <skill-dir> --format markdown

# Or from workspace root with installed path:
python3 skills/rabbit-skills-audit/scripts/audit_static.py <skill-dir> --format markdown
```

Useful flags: `--checklist` (adds the 22-item checklist to text output), `--area MD,ST` (lint specific areas), `--check MD-04,SC-04` (filter checks), `--strict` (exit 1 on errors). Frontmatter parsing falls back to [`scripts/frontmatter.py`](scripts/frontmatter.py) when PyYAML is absent.

**Step 3: Judge.** Read `SKILL.md`, every reference file, and any scripts. Apply the `judgment` checks in [`references/audit-checks.md`](references/audit-checks.md). Resolve every `needs_review` flag from Step 2: keep it if the passage violates the practice, or drop it if it is a quoted example of an anti-pattern.

- **Cheapest model delegation (Haiku / Flash-Lite):** When running in an agent harness supporting subagents or multi-model routing, invoke a subagent using the cheapest model tier (`claude-3-5-haiku` / `haiku` in Claude Code, or `flash_lite` in Antigravity) to audit each file's prose and wording. Weaker, lightweight models expose confusing instructions, ambiguous terms (CQ-03), and missing context far more reliably than frontier models that silently compensate for vague wording. Check each file for:
  1. Filler or textbook explanations exceeding the ~50-token guideline (CQ-01).
  2. Rotating synonyms for the same concept (CQ-03).
  3. Missing input/output examples or strict templates (CQ-04).
  4. Unclear degrees of freedom or option dumps without defaults (CQ-05).
  5. Use-case coverage and scope: Verifying that user expectations from name/description are fulfilled, technical actions complete recognizable user goals, write operations have confirmation/verification, and intentional exclusions are explained.

**Step 4: Verify the pre-share checklist.** Review the 22-item checklist from [`references/pre-share-checklist.md`](references/pre-share-checklist.md) (pre-populated by `evaluate_checklist` in Step 2). Confirm every `[?]` item with cited `file:line` evidence or open a matching finding. Mark script items `n/a` when no scripts exist.

**Step 5: Report.** Format the report per [`references/report-template.md`](references/report-template.md) and write it to `<skill-name>-audit.md` in the current working directory (unless told otherwise). Recompute the final verdict (`FAIL` if any error, `PASS WITH WARNINGS` if warnings only, `PASS` if 0 errors and 0 warnings).

**Step 6: Improve and re-validate (feedback loop).** When asked to fix or improve the skill, rewrite offending sections using the Good patterns in [`references/audit-checks.md`](references/audit-checks.md), then re-run `python3 scripts/audit_static.py <skill-dir> --checklist --strict`. If any error or fixable warning remains, return to Step 6 and repeat until clean.

## References

- [`references/audit-checks.md`](references/audit-checks.md): 45-check catalog across 6 areas with Good/Bad examples
- [`references/pre-share-checklist.md`](references/pre-share-checklist.md): 22-item official pre-share checklist mapped to check IDs
- [`references/report-template.md`](references/report-template.md): severity model, verdict rules, and copy-paste report template
- [`evals/README.md`](evals/README.md): evaluation suite guide and test runner instructions
- [`evals/evals.json`](evals/evals.json): 5 evaluation scenarios and cross-model results log
- [`scripts/audit_static.py`](scripts/audit_static.py): modular static linter + checklist evaluator (`--self-test` supported)
- [`scripts/scaffold_skill.py`](scripts/scaffold_skill.py): compliant skill scaffolder and 31-harness placement manager (`--self-test` supported)
- [`scripts/audit_dsh_skill.py`](scripts/audit_dsh_skill.py): dedicated static linter for DeepSeek Harness (DSH) skills (`--self-test` supported)
- [`scripts/frontmatter.py`](scripts/frontmatter.py): stdlib YAML frontmatter parser (`--self-test` supported)

### Harness references

Harness-specific skill layouts, project vs. user paths, settings locations, and feature compatibility:
- [`references/harnesses/amp.md`](references/harnesses/amp.md): Amp & Universal agent skills layout and configuration
- [`references/harnesses/antigravity.md`](references/harnesses/antigravity.md): Google Antigravity & CLI (`agy`) skills layout and priority
- [`references/harnesses/claude-code.md`](references/harnesses/claude-code.md): Claude Code CLI skills layout, hooks, and context forks
- [`references/harnesses/cline.md`](references/harnesses/cline.md): Cline IDE extension skills layout, paths, and hooks
- [`references/harnesses/codebuddy.md`](references/harnesses/codebuddy.md): CodeBuddy IDE skills layout, user configuration, and tool restrictions
- [`references/harnesses/codex.md`](references/harnesses/codex.md): OpenAI Codex skills layout, discovery hierarchy, and configuration
- [`references/harnesses/command-code.md`](references/harnesses/command-code.md): Command Code terminal agent skills layout and precedence
- [`references/harnesses/crush.md`](references/harnesses/crush.md): Charmbracelet Crush terminal agent skills layout and TUI configuration
- [`references/harnesses/cursor.md`](references/harnesses/cursor.md): Cursor editor skills layout, project vs. global paths, and rules
- [`references/harnesses/dsh.md`](references/harnesses/dsh.md): DeepSeek Harness (DSH) skills layout, progressive disclosure, and precedence
- [`references/harnesses/droid.md`](references/harnesses/droid.md): Factory AI / Droid CLI skills layout and resolution hierarchy
- [`references/harnesses/firebender.md`](references/harnesses/firebender.md): Firebender multi-agent skills layout and workspace scopes
- [`references/harnesses/gemini-cli.md`](references/harnesses/gemini-cli.md): Gemini CLI skills layout, project vs. global paths, and configuration
- [`references/harnesses/github-copilot.md`](references/harnesses/github-copilot.md): GitHub Copilot Agent skills layout and repository instructions
- [`references/harnesses/hermes.md`](references/harnesses/hermes.md): Hermes Agent (Nous Research) skills layout, hub installation, and GitHub taps
- [`references/harnesses/iflow-cli.md`](references/harnesses/iflow-cli.md): iFlow CLI skills layout, configuration scopes, and workflows
- [`references/harnesses/kimi-code.md`](references/harnesses/kimi-code.md): Kimi Code CLI skills layout, configuration, and precedence order
- [`references/harnesses/kiro-cli.md`](references/harnesses/kiro-cli.md): Kiro CLI skills layout and custom agent resource configuration
- [`references/harnesses/kode.md`](references/harnesses/kode.md): Kode agent skills layout, marketplace integration, and configuration
- [`references/harnesses/openclaw.md`](references/harnesses/openclaw.md): OpenClaw skills layout, workspace scopes, and sandboxing
- [`references/harnesses/opencode.md`](references/harnesses/opencode.md): OpenCode skills layout, global configuration, and permissions
- [`references/harnesses/openhands.md`](references/harnesses/openhands.md): OpenHands skills layout, microagents, and precedence
- [`references/harnesses/pi.md`](references/harnesses/pi.md): Pi Coding Agent skills layout, configuration scopes, and CLI execution
- [`references/harnesses/posit-assistant.md`](references/harnesses/posit-assistant.md): Posit Assistant skills layout, data science tools, and configuration
- [`references/harnesses/qoder.md`](references/harnesses/qoder.md): Qoder & Qoder CN skills layout, configuration, and precedence
- [`references/harnesses/qwen-code.md`](references/harnesses/qwen-code.md): Qwen Code skills layout, path gating, and lifecycle hooks
- [`references/harnesses/replit.md`](references/harnesses/replit.md): Replit Agent skills layout, repl-level scopes, and workspace tools
- [`references/harnesses/roo-code.md`](references/harnesses/roo-code.md): Roo Code IDE skills layout, mode targeting, and configuration
- [`references/harnesses/trae.md`](references/harnesses/trae.md): Trae & Trae CN IDE skills layout, builder mode, and configuration
- [`references/harnesses/windsurf.md`](references/harnesses/windsurf.md): Windsurf Cascade skills layout, project rules, and global configurations
- [`references/harnesses/zcode.md`](references/harnesses/zcode.md): ZCode skills layout, standard vs. override paths, and configuration
