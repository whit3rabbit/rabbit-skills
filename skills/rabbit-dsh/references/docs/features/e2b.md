# E2B Cloud Sandbox

**In one sentence**: `e2b` is a set of **experimental provider composition POCs** — moving a whole "filesystem + subprocess" execution world into an E2B Linux sandbox. E2B only provides the sandbox lifecycle and two low-level OS adapters (`fs-e2b` / `subprocess-e2b`); provider-agnostic consumers build higher-level capabilities on top of them.

It does not move the harness process itself; it only moves the "mutable execution world" into a remote sandbox.

## Contents

- [1. What it is](#1-what-it-is)
- [2. Packages](#2-packages)
- [3. Lifecycle and ownership (e2b)](#3-lifecycle-and-ownership-e2b)
- [4. The two adapters](#4-the-two-adapters)
- [5. Configuration](#5-configuration)
- [6. Mount status](#6-mount-status)
- [7. Known limitations](#7-known-limitations)
- [8. Verification](#8-verification)
- [Next steps](#next-steps)

---

## 1. What it is

The goal of this POC is a **portable execution world**: letting file tools, Bash, PTY, and LSP run inside the same E2B Linux sandbox. E2B is responsible for only two things — sandbox creation/destruction, and two OS adapter seams (filesystem, subprocess). Higher capabilities (Bash, PTY, LSP) need no E2B-specific fork:

The ready-made `bash-local`, `terminal-bash`, and `lsp-stdio` delegate every execution-world operation to `ctx.fs` and `ctx.subprocess`, so mounting the two E2B adapters makes their mutable work land in the same sandbox.

This boundary does **not** move the harness process, Cordis objects, model calls, agent/session state, session persistence, skills, higher-level protocol state, or the E2B SDK buffers — they stay in the host process.

## 2. Packages

| Package | ctx key | Role |
| --- | --- | --- |
| e2b | ctx.e2b | Creates a sandbox, prepares its working/runtime directories, exposes the shared SDK handle, and deletes it on timeout or teardown |
| fs-e2b | ctx.fs | Implements the filesystem seam over the E2B Filesystem API |
| subprocess-e2b | ctx.subprocess | Implements executable lookup, managed process groups and stdio, remote spill files, and terminal sessions over the E2B Commands and PTY APIs |

## 3. Lifecycle and ownership (e2b)

The `e2b` package is the **shared lifecycle owner**: the filesystem and subprocess adapters inject `ctx.e2b`, wait for its single SDK handle, and therefore live in the same remote Linux working tree and process world.

- **Sandbox created on construction**: before resolving `getSandbox()`, the service creates `cwd` and the private `cwd/.dsh-e2b` adapter state directory, validates that the reserved path is a real directory (not a symlink or another file type), then sets it to `0700`

- **Command shell isolation**: each adapter's internal E2B command shell receives a random root-level `HOME`, preventing the SDK's fixed login shell from resolving profile files from a mutable user home directory before control commands

- **Teardown**: first blocks new handle acquisition, then waits for setup to complete, and finally deletes the sandbox. `SandboxNotFoundError` means it already timed out or another owner deleted it, treated as silent

- An initial directory setup failure attempts a single deletion; the configured E2B timeout constrains the second failure. Provider plugins must load after this owner and be destroyed before it

**Model visibility**: none — this shared runtime owner registers no model-visible context.

## 4. The two adapters

`fs-e2b` implements the `dsh-fs` provider contract with no configuration: it loads `e2b` first, then replaces `fs-local` with it. File tools and E2B backend Bash processes see the same world.

- **Remote identity and metadata**: relative paths resolve against the caller's cwd or `ctx.e2b.cwd` per POSIX; `stat`/`lstat`/single-level directory listings project E2B metadata into the filesystem seam; version is E2B metadata plus an opaque hash extended per write

- **Execution-world paths**: canonical targets expose absolute POSIX process paths, percent-encoded `file:` URIs, and the provider's own containment checks

- **Bounded reads**: `readBytes` short-circuits at the stat size, streams the remote object, and cancels past `maxBytes` (`FS_TOO_LARGE`); the host does not buffer over-limit files in full

- **Atomic writes**: writes first create a random sibling staging directory (`0700`), then publish via an E2B same-filesystem atomic rename; `createIfAbsent` uses the remote `ln -T` to guarantee atomic no-replace

`subprocess-e2b` implements the `dsh-subprocess` seam, replacing `subprocess-local` with it.

- **Async remote launch**: the sync seam immediately returns a handle, and `Sandbox.commands.run(..., { background: true })` launches remotely; `pid` stays `-1` until the wrapper publishes and validates the process group id

- **Linux process groups**: a quoted wrapper launches each argv with `exec setsid --wait`, recording the real process group id; termination first sends `SIGTERM`, waits `graceMs`, then escalates to `SIGKILL` with an SDK kill fallback

- **Environment boundaries**: a trusted control shell probe resolves the sandbox user's login home; the wrapper strips `DSH_*` and credential-shaped (`*KEY*`/`*SECRET*`/`*TOKEN*`) names from the environment, restoring only explicit `spec.env` entries

- **stdio projection**: the remote wrapper diverts raw bytes to an optional bounded spill file, returns each live chunk as newline-delimited base64 frames, and the host incrementally restores them

- **Terminal sessions**: `spawnTerminal()` uses the E2B byte PTY API, writes argv and sanitized environment to a private `0600` file, sends real signals, and `terminate()` cleans up every live process group in the terminal session

## 5. Configuration

```yaml
- id: e2b

  name: '@deepseek-ai/dsh-e2b'

  config:

    cwd: /home/user/workspace

    timeoutMs: 300000

- id: subprocess-e2b

  name: '@deepseek-ai/dsh-subprocess-e2b'

- id: fs-e2b

  name: '@deepseek-ai/dsh-fs-e2b'
```

- `apiKey` is optional, defaults to reading `E2B_API_KEY`; it configures the host SDK connection and is **never installed into the sandbox**

- `cwd` defaults to `/home/user/workspace` and must be an absolute POSIX path

- `timeoutMs` defaults to five minutes and controls the sandbox lifecycle; the sandbox is deleted on expiry

`subprocess-e2b` additionally has:

| Key | Default | Meaning |
| --- | --- | --- |
| pollMs | 20 | Remote status/liveness polling interval (milliseconds); each tick is a control-plane request, so increasing it trades exit-observation latency for fewer requests |

## 6. Mount status

`e2b` is an **experimental POC, opt-in**: no shipping composition (base / headless / web-app) **mounts it by default**. To use it, explicitly declare the three plugins above in the profile's cordis config, and `fs-e2b`/`subprocess-e2b` must load after `e2b`.

## 7. Known limitations

- **Not a whole-machine runtime**: Cordis services, agent/session state, session logs, LLM requests, skills, and SDK-side buffers all stay in the host process

- **Sandbox state is ephemeral**: teardown and timeout both delete the sandbox; reconnect, pause/leave retention, templates, volumes, and snapshots are outside the POC

- **Unconfigured deployment platform**: network policy, host workspace sync, and sandbox discovery are outside the POC

- **`cwd` is a resolution convention, not containment**: adapters and commands can address other sandbox paths; E2B network access follows the base image's policy

## 8. Verification

```sh
# e2b is not mounted by default, so these three ids should not appear in dump-config

dsh web --dump-config | grep -iE "e2b"

# After explicit mounting, confirm all three plugins are in the composition tree

dsh web --dump-config | grep -iE "e2b"
```

## Next steps

- [Subprocess and terminals](../features/subprocess.md): the underlying seam implemented by `subprocess-e2b`

- [LSP code intelligence](../features/lsp.md): `lsp-stdio` needs no fork and runs straight into the sandbox

- [Sandbox and security](../learn/core/sandbox-security.md): the security boundary of local file effects (as opposed to the E2B remote world)
