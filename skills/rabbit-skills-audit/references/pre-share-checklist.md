# Pre-share checklist: is this skill ready to share?

The official 22-item "Checklist for effective Skills" from Anthropic's best-practices
guide, mapped to audit check IDs in [audit-checks.md](audit-checks.md).

`scripts/audit_static.py` runs `evaluate_checklist(ctx)` to pre-populate this
checklist (`[x]` pass, `[ ]` fail, `[?]` needs auditor judgment, `[n/a]` not
applicable). Resolve every `[?]` item during judgment before finalizing the report.

## Core quality (10 items)

- [ ] Description is specific and includes key terms (MD-14, MD-15)
- [ ] Description includes both what the Skill does and when to use it (MD-09, MD-12, MD-13)
- [ ] `SKILL.md` body is under 500 lines (ST-01)
- [ ] Additional details are in separate files, if needed (ST-02, ST-06)
- [ ] No time-sensitive information, or it lives in an "old patterns" section (CQ-02)
- [ ] Consistent terminology throughout (CQ-03)
- [ ] Examples are concrete, not abstract (CQ-04)
- [ ] File references are one level deep (ST-03)
- [ ] Progressive disclosure used appropriately (ST-02, ST-04, ST-05)
- [ ] Workflows have clear steps (WF-01)

## Code and scripts (8 items)

- [ ] Scripts solve problems rather than defer to Claude (SC-01)
- [ ] Error handling is explicit and helpful (SC-01)
- [ ] No "voodoo constants"; every value is justified (SC-02)
- [ ] Required packages are listed in instructions and verified as available (SC-05)
- [ ] Scripts have clear documentation (SC-03)
- [ ] No Windows-style paths; forward slashes only (SC-04, SC-08)
- [ ] Validation and verification steps for critical operations (SC-06)
- [ ] Feedback loops included for quality-critical tasks (WF-03)

## Testing (4 items)

- [ ] At least three evaluations created (EV-01)
- [ ] Tested across model tiers (Haiku, Sonnet, and Opus) (EV-02)
- [ ] Tested with real usage scenarios (EV-03)
- [ ] Team feedback incorporated, if applicable (EV-04)

## Filling it in

1. Run `python3 scripts/audit_static.py <skill-dir> --format markdown` (or `--checklist`) to generate the preliminary checklist.
2. For each `[?]` item, inspect the skill and turn it into `[x]` (with `file:line` evidence), `[ ]` (with a matching finding in the report), or `[n/a]` (with a short reason).
3. Every unchecked `[ ]` box must correspond to an open finding in the report.
4. No **PASS** verdict may be issued while an error-level item is unchecked.
