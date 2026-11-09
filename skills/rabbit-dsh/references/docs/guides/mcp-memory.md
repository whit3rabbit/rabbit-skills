# Add persistent memory through MCP

**In short**: DSH connects MCP, discovers tools, and calls them. The external memory server owns stored content, retrieval, and deletion policies. Remembering earlier messages in one conversation is not cross-session persistence.

**Source baseline: `0.1.5-alpha.1` / `5dda764ed3`, checked 2026-09-09.** Versions below are pins from the official examples, not claims about the latest upstream releases. DSH npm `latest` / `next` resolve to `0.1.2-rc.1` (the `alpha` channel is `0.1.5-alpha.1`); prepare source using the [migration guide](../guides/upgrade-migration.md).

## Contents

- [1. Start with one backend](#1-start-with-one-backend)
- [2. Run Reference Memory](#2-run-reference-memory)
- [3. Verify write → fresh-session recall → use](#3-verify-write-fresh-session-recall-use)
- [4. Choose Memorix or Engram instead](#4-choose-memorix-or-engram-instead)
- [5. Data, backup, and disabling](#5-data-backup-and-disabling)
- [6. Troubleshooting](#6-troubleshooting)
- [Sources and next steps](#sources-and-next-steps)

---

## 1. Start with one backend

The shipped composition enables none of these three servers. Connecting one at a time makes diagnosis easier.

| Backend | Official example pin / command | Behavior | Example storage |
| --- | --- | --- | --- |
| MCP Reference Memory | @modelcontextprotocol/server-memory@2026.7.4 / mcp-server-memory | Local entity/relation/observation graph; no additional model required | $HOME/.dsh-mcp-reference-memory.jsonl, overridden by MEMORY_FILE_PATH |
| Memorix | memorix@1.3.0 / memorix serve | Local heuristic mode; manages its own optional model / embedding providers | ~/.memorix/data, overridden by MEMORIX_DATA_DIR |
| Engram | v1.20.0 / engram mcp | Engram owns persistence and Git-project scope | ~/.engram; ENGRAM_DATA_DIR / ENGRAM_PROJECT overrides |

Start with **Reference Memory** to verify the full path with few dependencies and an explicit file location. Its search is case-insensitive substring matching over names, types, and observations—not semantic retrieval. It adds no automatic summarization, conflict resolution, or forgetting policy.

## 2. Run Reference Memory

These macOS / Linux shell examples assume a matching built source checkout and a new demo home. Do not test against your everyday memory database.

```sh
export DSH_SOURCE="/absolute/path/to/deepseek-harness"

export DSH_HOME="$HOME/.dsh-memory-demo"

export MEMORY_FILE_PATH="$DSH_HOME/memory/reference.jsonl"

umask 077

mkdir -p "$DSH_HOME/memory" "$DSH_HOME/examples/mcp-memory"

npm install --global @modelcontextprotocol/server-memory@2026.7.4

command -v mcp-server-memory

cp "$DSH_SOURCE/apps/cli/config/examples/mcp-memory/mcp-reference-memory.cordis.yml" \

  "$DSH_HOME/examples/mcp-memory/mcp-reference-memory.cordis.yml"

cd "$DSH_SOURCE"

pnpm dsh web --patch "$DSH_HOME/examples/mcp-memory/mcp-reference-memory.cordis.yml"
```

Configure model credentials, select a test workspace, and wait for discovery of the `mcp__...` tools. DSH launches the installed executable; the official overlay does not run a package manager or install dependencies.

This guide deliberately places `MEMORY_FILE_PATH` inside the demo home for convenient backup. That is an explicit choice, not every memory server's default. Use an absolute path with an existing writable parent directory.

### Pin the working directory and project scope

The official examples use `cwd: !!js process.cwd()`, which means the **Host launch directory**. Selecting another Workspace later in the Web UI does not rewrite that MCP server's `cwd`.

Our Reference Memory example fixes scope through its file path. Memorix / Engram also use Git-project identity. After copying their overlays, set `config.cwd` to the absolute test-repository path:

```yaml
# Replace the existing config.cwd line in the copied memory overlay.

cwd: /absolute/path/to/test-repo
```

After changing backend, storage path, or project identity, restart the relevant connection before cross-session testing. A changed storage scope is not necessarily lost memory.

## 3. Verify write → fresh-session recall → use

Choose a value unlikely to exist already, such as `lapsang-20260830-demo7`.

| Step | Example prompt | Evidence |
| --- | --- | --- |
| Write in Session A | “Use a memory tool to save that my validation drink is lapsang-20260830-demo7.” | Actual write-tool name, arguments, and successful result |
| Recall in new Session B | “Check memory: what is my validation drink?” | A search/recall call returning the complete unique value |
| Use in Session B | “Use that preference to suggest one drink for the meeting.” | The answer actually uses the recalled value |

Keep the same Host, backend, and storage scope when creating Session B. Do not paste Session A's conversation. A model merely saying “saved” or “found it” is not sufficient evidence.

After cross-session verification, optionally stop/restart the Host with the same environment and project scope, create Session C, and recall again. **Restart is an additional persistence check**, not a prerequisite for the first cross-session test.

If tool use is inconsistent, add a short rule to existing instructions: “Use a memory write tool for explicit requests to remember. Search memory when historical information is relevant, then use relevant results.” Keep the existing persona rather than replacing the entire system prompt.

## 4. Choose Memorix or Engram instead

Copy the corresponding official overlay, use separate storage and an explicit `cwd`, and keep one backend per initial test.

| Backend | Installation | Before startup |
| --- | --- | --- |
| Memorix | npm install --global memorix@1.3.0 | command -v memorix; it requires Node 22.18+, while DSH's requirement is stricter |
| Engram | go install github.com/Gentleman-Programming/engram/cmd/engram@v1.20.0 | Official example requires Go 1.25.10+; command -v engram must find the executable |

Files are `memorix.cordis.yml` and `engram.cordis.yml`. Copy and edit `cwd` as above, then launch with `pnpm dsh web --patch ABSOLUTE_PATCH_PATH`.

Memorix's optional providers are configured in its own `~/.memorix/config.toml` or project `memorix.toml`. Engram also owns its project and storage settings. These are not DSH `settings.yaml` fields.

## 5. Data, backup, and disabling

- **Track home and memory separately**: default `~/.engram`, `~/.memorix/data`, and the reference JSONL are not automatically included in a backup of another `DSH_HOME`.

- **Local storage is not zero egress**: recalled content used by the model enters its request context; optional external model/embedding providers can make their own requests.

- **Stop writes before backing up**: stop the relevant runtime / MCP server, then preserve backend data, project scope, and configuration.

- **Disabling is not deletion**: removing the overlay or MCP row stops integration; use the backend's deletion and data-management facilities to remove test entities or databases.

- Retain only information that should persist. Keep keys and unrelated sensitive content out of test memories.

## 6. Troubleshooting

| Symptom | Check |
| --- | --- |
| No memory tools | Overlay argument, executable in the Host PATH, and completion of asynchronous discovery |
| Executable not found | Run command -v in the same shell that starts DSH; installation and launch shells can have different PATH values |
| New Session forgets | Actual write result, file location, Git-project identity, and selected backend |
| Write fails | Absolute path, existing parent directory, write permission, and the tool's error—not just the model's summary |
| Exact search works but paraphrases fail | Reference Memory uses substring search, not semantic retrieval |
| MCP child disconnects | DSH retries with backoff and re-syncs tools; after budget exhaustion tools are withdrawn until reload/restart |

## Sources and next steps

- [Official memory guide](https://github.com/deepseek-ai/deepseek-harness/blob/5dda764ed3aa172535a7967b06ff95d9cbfe536a/docs/user/guide/mcp-memory.md)

- [Three example overlays](https://github.com/deepseek-ai/deepseek-harness/tree/5dda764ed3aa172535a7967b06ff95d9cbfe536a/apps/cli/config/examples/mcp-memory)

- [MCP integration](../features/mcp.md), [MCP + subagent assistant](../guides/mcp-subagent-assistant.md), and [Privacy](../user-guide/privacy.md).
