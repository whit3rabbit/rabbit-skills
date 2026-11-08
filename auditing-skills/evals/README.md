# Evaluations

Five scenarios in `evals.json`, structured per the best-practices guide (query,
files, expected_behavior). Evaluations are the source of truth for whether this
skill actually works; there is no built-in runner, so each eval is run by hand.

## Running an eval

1. Open a fresh session with the skill installed (metadata only in context).
2. Send the query verbatim, substituting any `<placeholder>` paths.
3. Compare what happened against the `expected_behavior` bullets.
4. Append a row to `results` in `evals.json`:

```json
{"date": "2026-11-07", "model": "<provider/model>", "eval_id": "audit-broken-skill", "pass": true, "notes": ""}
```

## Fixture expectations

`fixtures/bad-skill/` is deliberately broken. `audit_static.py` on it must
produce exactly these findings: MD-04, MD-06, SC-04 (errors); MD-12, MD-13,
MD-14, SC-08, ST-05 (warnings); MD-07 (info) — verdict FAIL. A quick check:

```
python3 scripts/audit_static.py evals/fixtures/bad-skill
```

Fixtures are excluded from the skill's own structure checks (they are test
data, not reference material), so they never appear as findings when auditing
`auditing-skills` itself.

## Why so few evals are automated

Triggering (evals 4 and 5) can only be measured in a live session where only
the skill's metadata is loaded. Static checks are verifiable in CI via the
fixture expectation above; everything else needs a real model turn.
