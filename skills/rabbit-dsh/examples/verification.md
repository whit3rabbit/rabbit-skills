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

## Plugin: widget-template

Keep the four checks separate and record each outcome.

1. **Build.** `node --check index.js` and `node --check widget.js` exit 0. `rabbit_dsh.py audit widget` returns PASS. `audit_dsh_artifacts.py widget/cordis.patch.yml --strict` returns PASS.
2. **Load.** Apply the bundle in the disposable profile from the package root: `dsh plugin --profile web add link:.`. The composition applies without error. Restart `dsh web`, then curl `http://127.0.0.1:3080/` and confirm the HTML carries `<script defer src="/widget-template/widget.js"></script>`.
3. **Call.** Each route answers with JSON or JS, never an empty body:
   - `GET /widget-template/data.json` returns `{ ok: true, data: { label, value, detail, updatedAt } }`.
   - `GET /widget-template/config.json` returns `{ ok: true, config: { pollSeconds } }`. `PUT` with `{"pollSeconds": 30}` returns the merged config, and a later GET keeps the value. `PUT` with `{"pollSeconds": 0}` fails with the validation message, and the widget stays loaded.
   - `GET /widget-template/widget.js` serves JavaScript with `Cache-Control: no-store`.
   - Browser check: the pill mounts on the chat page bottom-right, drags, and the click bubble opens. The marketplace view mounts nothing.
4. **Unload.** Remove the bundle with the same profile, then reload the chat page: the script tag is gone from the served index, the routes answer 404, and no pill mounts.

## Plugin: startup-screen-template

Keep the four checks separate and record each outcome. The [preview page](startup-screen/preview/index.html) runs the same widget files without a DSH runtime, so the screen look can be confirmed anywhere, but build, load, call, and unload still need the disposable profile.

1. **Build.** `node --check` exits 0 for `startup-screen/lib/index.js`, `startup-screen/lib/widget.js`, `startup-screen/lib/screens.js`, and `startup-screen/lib/client.js`. `audit_dsh.py startup-screen --strict` returns PASS. `audit_dsh_artifacts.py startup-screen/cordis.patch.yml --strict` returns PASS.
2. **Load.** Apply the bundle in the disposable profile: `dsh plugin --profile web add link:./startup-screen`. The composition applies without error. Restart `dsh web`, then curl `http://127.0.0.1:3080/` and confirm the served index carries the boot layer `<div id="startup-screen-template-root"`, the injected `window.__STARTUP_SCREEN_TEMPLATE__` config, and `<script defer src="/startup-screen-template/widget.js"></script>`.
3. **Call.** Check responses and the rendered page, not the transcript summary:
   - `GET /startup-screen-template/config` returns `{ ok: true, config: …, defaults: … }`. `POST` with `{"patch": {"screen": "boot-log", "title": "NIGHT OPS"}}` returns the merged config, a later GET keeps the value, and the served index now embeds `"screen":"boot-log"`.
   - `POST` with `{"patch": {"screen": "nope"}}` silently keeps the previous screen (enum clamping), and `POST` with malformed JSON answers 400 while the plugin stays loaded.
   - `GET /startup-screen-template/widget.js` and `/startup-screen-template/screens.js` serve JavaScript with `Cache-Control: no-store`.
   - Browser check: the wordmark screen plays on first load and the page unlocks when it finishes. Pressing Esc or clicking mid-play skips. **Settings → Startup Screen** lists the panel. Switching the screen there and clicking Preview replays it. With `mode: session`, a reload does not play again in the same browser session.
4. **Unload.** Remove the bundle with the same profile, then reload the chat page: the injected markers are gone from the served index, the routes answer 404, and no splash plays.

## Plugin: context-dashboard-template

Keep the four checks separate and record each outcome. The [static preview](context-dashboard/preview/index.html) shows the target look in any browser without a DSH runtime, but build, load, call, and unload still need the disposable profile.

1. **Build.** `node --check` exits 0 for `context-dashboard/lib/index.js`, `context-dashboard/lib/client.js`, and `context-dashboard/lib/demo-data.js`. `audit_dsh.py context-dashboard --strict` returns PASS. `audit_dsh_artifacts.py context-dashboard/cordis.patch.yml --strict` returns PASS.
2. **Load.** Apply the bundle in the disposable profile: `dsh plugin --profile web add link:./context-dashboard`. The composition applies without error. Restart `dsh web`, then curl the two routes:
   - `GET /context-dashboard-template/data.json` returns `{ ok: true, data: { source: "demo", session, stats, composition, trend, events, files, commands, agents } }` with `Cache-Control: no-store`.
   - `GET /context-dashboard-template/config` returns `{ ok: true, config: { enableTab, enableFleetTab, enableSidebarPanel, enableCommand, demoMode }, defaults: … }`.
3. **Call.** Check responses and the rendered page, not the transcript summary:
   - `POST /context-dashboard-template/config` with `{"patch": {"enableSidebarPanel": true}}` returns the merged config, a later GET keeps the value, and the sidebar tab appears on reload. `POST` with malformed JSON answers 400 while the plugin stays loaded.
   - Browser check: the **Context** and **Fleet** tabs appear beside the chat with the demo banner on every card. The trend card toggles Total/Delta, the event chips filter the list, `/context` opens the centered modal, Esc or a backdrop click closes it, and **Settings → Context Dashboard** lists all five switches. Switching the Context tab off and reloading shows the disabled notice instead of the cards.
4. **Unload.** Remove the bundle with the same profile, then reload the chat page: the tabs, the `/context` entry, and the settings section are gone, the routes answer 404, and no demo banner mounts.
