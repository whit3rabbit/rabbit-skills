# Verify the examples

Each check below needs its own observed evidence. A static audit PASS proves structure only. Build, load, call, and unload are separate checks, and skill discovery is checked in the session catalog, not in the audit. If `dsh` is unavailable on PATH, say which checks did not run instead of claiming the artifact works.

Set up a disposable profile first so no active profile is modified:

```bash
export DSH_HOME=$(mktemp -d)/dsh-home
python3 "$rabbit_dsh_dir/scripts/rabbit_dsh.py" config init "$DSH_HOME"
```

## Skill: review-sql-migration

Static check. `rabbit_dsh.py audit review-sql-migration` returns PASS. A failure case: change the description to an unquoted scalar containing a colon, run the audit again, and expect `Quote description as a YAML string.` Then restore the file.

Discovery checks, each observed from a DSH session rooted at a copy of this example directory:

| # | Prompt or gesture | Expected evidence |
| --- | --- | --- |
| 1 | Open the session skill catalog | `review-sql-migration` appears once, with its `description` as the catalog entry. |
| 2 | "Check this migration for a missing index before we ship it." | The skill loads. A paraphrase of the trigger wording is enough. |
| 3 | "What does ADD COLUMN do in SQLite?" | The skill does not load. A generic SQL question skips it. |
| 4 | `/review-sql-migration` | The skill is injected once. Follow its instructions without loading it again in the same turn. |
| 5 | Start a session in `review-sql-migration/fixtures/`, then follow the skill's link to `references/sqlite.md` | The reference opens, resolved from the loaded skill's resource directory rather than the current working directory. |

Result check. Reviewing `fixtures/001_orders_customer.sql` against `fixtures/baseline.sql` must cite `fixtures/001_orders_customer.sql:2` and report that `orders.customer_id` lacks an index with `customer_id` as its leading column. Confirm the citation points at that statement in the file.

## Plugin: schema-find-refs

Keep the four checks separate and record each outcome.

1. **Build.** For the JavaScript entry, `node --check schema-find-refs/index.js` exits 0. For a TypeScript variant, `npm run build` inside the package produces `lib/index.js`. `rabbit_dsh.py audit schema-find-refs` returns PASS.
2. **Load.** Apply the bundle in the disposable profile: `dsh plugin --profile web add "$PWD/schema-find-refs"`. The composition applies without error and the load log line fires.
3. **Call.** Check the structured return and the rendered text, not the transcript summary:
   - `schema_find_refs` with `{"table": "orders"}` returns references that include `fixtures/schema.sql` line numbers and `truncated: false`. The rendered text lists `fixtures/schema.sql:<n>` rows.
   - `{"table": "orders", "limit": 2}` returns two references and `truncated: true`.
   - Rejected input: `{"table": "orders; DROP TABLE"}` or `{"table": "orders", "limit": 0}` fails cleanly with the validation message. The plugin stays loaded afterwards.
4. **Unload.** Remove the bundle with the same profile, then list tools: `schema_find_refs` is gone and the unload log line fired.

The companion skill consumes the references. It decides what they mean for the migration. Exercise both paths with the skill scenario above when both artifacts are loaded.
