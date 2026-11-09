---
name: review-sql-migration
description: Review SQL migrations for data loss, incompatible schema changes, and missing indexes. Use for migration diffs and deployment review.
---

# Review a SQL migration

Review the requested diff and nearby schema files. Keep the review read-only. Do not apply the migration, connect to a database, or edit the source.

1. Identify the database engine from project configuration or the migration syntax. If it is unclear, state which findings depend on the engine.
2. Open [SQLite review rules](references/sqlite.md) for SQLite migrations. Resolve the file from the loaded skill's resource directory, even when the session starts in a subdirectory.
3. Trace each changed table or constraint to its existing definition and relevant callers. Use workspace search. If `schema_find_refs` is available for the fixture in this example, use it to locate references and then read the cited lines.
4. Check data compatibility, dependency order, index coverage, and how the change could be rolled back. Distinguish a demonstrated defect from a risk that depends on existing data or access patterns.
5. Report each finding with the file, line, impact, and proposed fix. Verify that every citation points to the statement that supports it.

## Try the example

Review [the migration](fixtures/001_orders_customer.sql) against [the baseline](fixtures/baseline.sql). The new child key lacks an index with `customer_id` as its leading column. Cite the column declaration on line 2 and explain which operation benefits from the index.
