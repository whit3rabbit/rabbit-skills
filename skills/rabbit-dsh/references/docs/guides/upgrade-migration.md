# Upgrade and migration guide

**In short**: retain the old environment, verify the source build in a new DSH home and test workspace, then switch your daily entry point. Rollback pairs the old runtime with an old data copy.

**Audit baseline `0.1.5-alpha.1` @ `5dda764ed3` (checked 2026-09-09).** The body of this guide covers migration to `0.1.5-alpha.1`: section 3 summarizes interface changes since 0.1.2 and section 4 covers the new session storage v2 -> v3 migration from 0.1.5. Neither is a compatibility promise for future releases. Historical note: the migration from `0.1.1-rc.2` to `0.1.2-alpha.1`; section 4 adds the Session storage format v2 → v3 migration new in `0.1.5-alpha.1`. Neither is a compatibility promise for future releases. Shell examples target macOS / Linux.

## Contents

- [1. Choose a channel before changing version numbers](#1-choose-a-channel-before-changing-version-numbers)
- [2. Upgrade workflow](#2-upgrade-workflow)
- [3. Required migration checks](#3-required-migration-checks)
- [4. Session storage format migration: V2 → V3](#4-session-storage-format-migration-v2-v3)
- [5. Verify each layer, not just startup](#5-verify-each-layer-not-just-startup)
- [6. Switch and roll back](#6-switch-and-roll-back)
- [Sources and next steps](#sources-and-next-steps)

---

## 1. Choose a channel before changing version numbers

| Channel | Checked result | Use |
| --- | --- | --- |
| npm latest / next | Both 0.1.2-rc.1 | Keep using the published package |
| Official source / tag | 0.1.5-alpha.1, tag dsh-v0.1.5-alpha.1 | Validate the new interfaces below |
| Exact npm alpha version | Returned E404 at this check | Select it only after actual publication |

```sh
node --version

npm view @deepseek-ai/dsh dist-tags --json
```

Source requires Node `^22.19.0 || >=24.0.0`. Default `npx @deepseek-ai/dsh web` still runs the npm release; a Git tag does not imply npm publication. Recheck the registry and [status page](../guides/deepseek-harness-status.md) for later changes.

## 2. Upgrade workflow

### Record and back up

Record npm vs source, exact version/commit, `DSH_HOME`, profile, extra patches, and external plugin paths. Stop Web, SDK, ACP, and other processes using that home and let pending writes finish. Closing a browser tab does not stop the Host.

```sh
export DSH_HOME="${DSH_HOME:-$HOME/.dsh}"

STAMP="$(date +%Y%m%d-%H%M%S)"

BACKUP="${DSH_HOME%/}.backup-$STAMP"

umask 077

test -d "$DSH_HOME" && test ! -e "$BACKUP" && \

  cp -a "$DSH_HOME" "$BACKUP" && printf 'Backup: %s\n' "$BACKUP"
```

The backup contains credentials, conversations, and plugin configuration; keep it private. It does not cover workspace files and may omit external plugin sources or MCP memory databases. Back up those locations separately. Do not copy active databases or Session logs while the runtime is writing.

### Build and try a separate checkout

Use new paths for both this checkout and trial home:

```sh
git clone --branch dsh-v0.1.5-alpha.1 --depth 1 \

  https://github.com/deepseek-ai/deepseek-harness.git \

  "$HOME/deepseek-harness-alpha-trial"

cd "$HOME/deepseek-harness-alpha-trial"

git rev-parse HEAD

pnpm install

pnpm run build

export TRIAL_HOME="$HOME/.dsh-alpha-trial-$STAMP"

DSH_HOME="$TRIAL_HOME" pnpm dsh web
```

Configure model credentials in the trial environment and select a test directory without sensitive information. A new home does not inherit old credentials, settings, or Sessions automatically; a separate home is not workspace isolation.

Verify the shipped composition first, then migrate old profile patches and custom plugins incrementally. Do not overwrite the new profile with the complete old directory: that also imports old dependency manifests and installation artifacts. Review absolute external paths and plugin versions.

## 3. Required migration checks

| Old configuration / habit | New baseline | Details |
| --- | --- | --- |
| DSH_TOOLS_MODE=code, mode: code | Use ptc; PTC-only direct named-tool calls return UNKNOWN_TOOL, while SDK bindings use run_code | Tool execution |
| Importing dsh-host-apiproxy | Removed; consume typed Remote contracts from Session / Settings / Workspace and other domain owners | Remote API |
| Importing dsh-client-runtime | Move to store, Session controller, or React adapters by responsibility, not a blind rename | Web UI |
| TS SDK launch: { command, args } | Use dshBin, profile, and patches; match client and runtime versions | SDK |
| SDK / ACP demo bins | Use dsh --profile sdk / sdk-minimal / acp | ACP |
| Opening only the clean Web root | First open the printed token launch URL to obtain a browser Session cookie | Quickstart |
| Exposing Web UI with --host 0.0.0.0 | Current Web startup rejects it; use SSH forwarding, with Host trust separate from login | Remote API |
| Treating telemetry as one switch | OTel defaults to FEEDBACK_ONLY; plugin metadata defaults on; extra Session-log metadata defaults off | Privacy |

Historical `tool/code-dispatch*` event names remain valid: do not bulk-rewrite logs because the mode was renamed. `sdk-minimal` is standalone and pins full access; it is not a more restricted SDK.

## 4. Session storage format migration: V2 → V3

**There is no command — opening the Session migrates it.** `session-persistence-jsonl`'s `open(id, 'read' | 'write')` selects the **numerically highest canonical generation** in the session directory; when it is below `SESSION_FORMAT_VERSION` (currently `3`, `packages/core/session/src/types.ts`), the catalog composes the adjacent migration edges from that version up to the current one into a single streaming restore — the edge new in `0.1.5-alpha.1` is the last one, `session-format-v2-to-v3` (0.1.2 wrote v0, so v0→v1→v2→v3 all run). There is no migration command in `apps/cli` and no migration switch on the JSONL backend — its config is only `root` (required) and `compression` (optional).

| Open mode | Behaviour |
| --- | --- |
| read | decodes and migrates in one pass, validates the current logical result, and returns it without publishing a successor |
| write | reuses the same revision-keyed preparation; encodes a same-directory temporary file in bounded chunks → verifies it in a Worker Thread → rechecks the source revision → publishes the current generation without overwrite; the source file stays byte-identical |

**One** current generation appears on disk; the source keeps its own name (intermediate v1/v2 generations never land — the catalog composes the adjacent edges into one streaming restore and publishes only the final result):

```text
<root>/--<normalized cwd>--/<encoded-id>/

  session.jsonl.zstd      ← the pre-migration generation, name retained (0.1.2 wrote v0)

  session.v3.jsonl.zstd   ← the current generation published by a write open
```

(With `compression: 'none'` the suffix is `.jsonl`; the name comes from `sessionFormatLogFilename` in `packages/session/session-format/src/filename.ts`: version 0 stays `session.jsonl`, later ones are `session.vN.jsonl`.)

What the migration changes (`packages/session/session-format-v2-to-v3`):

| Change | Content |
| --- | --- |
| logical header | version: 2 → 3; keeps id, createdAt, isSeeded, delegationDepth and the admitted optional cwd / parentSession / origin |
| system prompt | request/header.data.header.system is promoted into a surface system/message head (right after the first step/start) and then removed from every request header |
| preset | the exact id code becomes ptc (header.agentPreset and every agent-preset/selected) |
| PTC vocabulary | tool/code-dispatch-start / tool/code-dispatch become tool/ptc-dispatch-start / tool/ptc-dispatch; plugin attribution tools-code-mode becomes tools-ptc |
| reference remapping | surface sourceEventSeqs, compaction shadowedRange / shadowedSeqs, command/done.sourceEventSeq, and the title events' messageSeqs are recomputed for the inserted positions |
| envelope canonicalization | { op: 'replace', start, end } becomes { op: 'replace', startSeq, endSeq }; exactly tools: [] and adapterDefaults: {} are omitted |

**Compatibility and refusal**:

- The migration **preserves the meaning of each historical request**, but it inserts system events, so the event count, dense sequence positions, and local references all change; do not treat a v3 file as a byte-for-byte copy of v2.

- The source file stays byte-identical; when the migration edge refuses, no successor is published, `SessionFormatUnsupportedError` is raised (underneath it is `SessionFormatUnsupportedMigrationError`), and the raw log stays in place for diagnosis.

- Input already marked V3 does not run this edge (native V3 admission applies a separate, stricter set of checks).

- The catalog is a **build-static inventory** (`session-format-catalog`): a profile cannot add, remove, or reorder an edge by mounting a plugin.

**Rollback**: persistence explicitly provides no downgrade support for the retained predecessors, so the **only supported rollback is the pre-upgrade home backup from section 2**. Deleting or renaming `session.v3.jsonl*` by hand is a forensic move, not a rollback: the v3 generation holds every event appended after the migration, which an old build cannot read; and because an old runtime selects the numerically highest canonical generation, seeing v3 makes it fail with `SessionFormatUnsupportedError` since that version is above the one it supports.

Verification:

```sh
# the current format version

grep -n "SESSION_FORMAT_VERSION" packages/core/session/src/types.ts

# which generations exist in one session directory (compare before/after)

ls -1 ~/.dsh/sessions/*/*/session*.jsonl*

# the edge inventory is build-static, not a runtime plugin

grep -rn "sessionFormatMigration" packages/session/session-format-v2-to-v3/package.json
```

## 5. Verify each layer, not just startup

From the source checkout, using the trial home:

```sh
DSH_HOME="$TRIAL_HOME" pnpm dsh web --dump-config

DSH_HOME="$TRIAL_HOME" pnpm dsh --profile sdk --help

DSH_HOME="$TRIAL_HOME" pnpm dsh --profile acp --help
```

| Layer | Evidence to collect |
| --- | --- |
| Version / composition | Correct commit; migrated old imports; expected profile and patch origins |
| Web login | Full launch URL works; no continuous 401/403 or WebSocket reconnect loop |
| Basic execution | A real read-file / simple tool result in a test workspace, not just visible schemas |
| PTC, if used | Tool bindings inside run_code execute and appear in the Session |
| SDK / ACP, if used | Real prompt, result, and child shutdown; help validates only the entry point |
| Data / plugins | A new Session persists and reopens; each enabled external plugin works |
| Privacy | All three data controls, model routes, and permission preset match expectations |

Test old Session compatibility using another copy of the backup, leaving the original backup intact. Never run old and new runtimes against the same writable home concurrently.

## 6. Switch and roll back

After verification, update the runtime path, `DSH_HOME`, and profile in your daily launcher. Avoid accidentally mixing an old global `dsh` with the source entry point. Keep the backup until normal tasks have been exercised.

For rollback, stop the new runtime, preserve the failed environment, and restore the old backup into another home:

```sh
RESTORE_HOME="${DSH_HOME%/}.restored-$STAMP"

test -d "$BACKUP" && test ! -e "$RESTORE_HOME" && \

  cp -a "$BACKUP" "$RESTORE_HOME" && \

  DSH_HOME="$RESTORE_HOME" npx @deepseek-ai/dsh@0.1.2-rc.1 web
```

This command assumes the previous runtime was npm `0.1.2-rc.1`; if it was source-built, use the recorded old checkout. Runtime rollback does not undo Agent edits to workspace files: use the workspace's own Git / backup process. Do not assume data newly written by alpha is backward-compatible. The Session log format migration (section 4) is the same: it offers no downgrade, so rollback means restoring the pre-upgrade home backup.

## Sources and next steps

- [Official release](https://github.com/deepseek-ai/deepseek-harness/releases/tag/dsh-v0.1.5-alpha.1)

- [V2 → V3 Session format migration specification](https://github.com/deepseek-ai/deepseek-harness/tree/5dda764ed3/packages/session/session-format-v2-to-v3)

- [CLI and profiles](https://github.com/deepseek-ai/deepseek-harness/tree/5dda764ed3/apps/cli)

- [SDK launch contract](https://github.com/deepseek-ai/deepseek-harness/blob/5dda764ed3/packages/sdk/client/src/launch.ts)

- [GitHub PR review](../guides/github-pr-review.md) and [MCP memory](../guides/mcp-memory.md): optional workflows after migration.
