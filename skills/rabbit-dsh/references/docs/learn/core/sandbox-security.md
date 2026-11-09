# Sandbox & Security

- 
- Concepts Course
- Core Mechanisms
- Sandbox & Security
On this page

# Sandbox & Security

Audit baseline 0.1.5-alpha.1 @ 5dda764ed3.

**Upstream notice (source `0.1.5-alpha.1`)**: the project has not been security-audited. Approval, permission presets, and sandbox mechanisms are not a containment guarantee. Use disposable environments without sensitive data, especially with full-access profiles.

**One-liner**: DSH's security philosophy is "**default not trusted, deny on failure**": commands are wrapped in a sandbox (`ctx.sandbox.confine`), and the process and all its children run under restrictions; **with no usable backend it throws `SANDBOX_UNAVAILABLE` — never runs bare**.

This page clarifies DSH's process-level boundary: what it can limit, what it cannot, how it behaves on failure, and how it works with permission presets / approval policies.

## Contents

- [1. Capability seam: definition separate from implementation](#1-capability-seam-definition-separate-from-implementation)
- [2. Core contract: confine](#2-core-contract-confine)
- [3. Restriction vocabulary](#3-restriction-vocabulary)
- [4. Backend implementations and prerequisites](#4-backend-implementations-and-prerequisites)
- [5. Policy rides the call, not the provider](#5-policy-rides-the-call-not-the-provider)
- [6. The home of policy: ctx.sandboxPolicy](#6-the-home-of-policy-ctxsandboxpolicy)
- [7. The filesystem fence: fs-sandbox](#7-the-filesystem-fence-fs-sandbox)
- [8. Windows' PowerShell executor: pwsh-sandbox](#8-windows-powershell-executor-pwsh-sandbox)
- [9. Failure modes (what the model sees)](#9-failure-modes-what-the-model-sees)
- [10. Relationship to permission presets and approval policies](#10-relationship-to-permission-presets-and-approval-policies)
- [11. Security boundary and known limitations (an honest list)](#11-security-boundary-and-known-limitations-an-honest-list)
- [12. Verification](#12-verification)
- [Next steps](#next-steps)

---

## 1. Capability seam: definition separate from implementation

`@deepseek-ai/dsh-sandbox` is the **capability seam (Service Definition)** of the sandbox: it holds only the `ctx.sandbox` service contract + the shared confinement vocabulary, with only cordis (plus the error base class) as dependencies — it **never depends on any backend**. This is one example of a [capability-seam] split: definition and implementation are transparently decoupled to any consumer.

```text
definition   dsh-sandbox        ctx.sandbox.confine(...) + vocabulary(SandboxMode/Policy/…)

implementation dsh-sandbox-local  Linux bwrap/Landlock · macOS Seatbelt · Windows via the ACL runner

               dsh-sandbox-windows-acl  Windows restricted-token runner (write-SID allowlist)

consumer     dsh-bash-sandbox / dsh-pwsh-sandbox / dsh-fs-sandbox   wrap argv or add a file fence
```

Swapping the sandbox implementation = swapping the provider; consumer code (bash tools, etc.) is unchanged.

## 2. Core contract: confine

The contract in a sentence:

`ctx.sandbox.confine(argv, policy)` returns argv **that should replace your original argv**: wrapped so that the process and every process it spawns run under restrictions: plus the chosen backend's enforcement completeness, the denial dialect (denialSignatures), and structured runner-failure evidence (runnerFailureRules); **with no usable backend it throws rather than passing argv through unconfined**.

```ts
const confined = ctx.sandbox.confine(['bash', '-c', command], policy)

runArgv(spec, confined.argv)   // real consumers like dsh-bash-sandbox do this
```

The shape of `ConfinedArgv`:

```ts
{

  argv: string[],                    // the argv to spawn (wrapped)

  enforcement: SandboxEnforcement,   // full | partial

  denialSignatures: ...,             // the stderr dialect a sandbox "denial" produces

  runnerFailureRules: ...,           // evidence rules for "runner/command failure"

}
```

**Key**: it returns an object, not an argv array itself: the consumer takes `.argv`, and can use denialSignatures / runnerFailureRules to distinguish the two classes of failure:

- **sandbox denial**: stderr dialect (EROFS / EACCES / EPERM, etc.)

- **runner / command failure**: exit code + stderr rules

## 3. Restriction vocabulary

| Type | Values / meaning |
| --- | --- |
| SandboxMode | read-only / workspace-write / danger-full-access (filesystem effects only) |
| SandboxEnforcement | full / partial (per kernel ABI; Windows ACL and older Landlock ABIs are partial) |
| SandboxPolicy | the restricted subset (confined) |
| SandboxExecutionPolicy | the full per-call mode + workspace root |
| ctx.sandboxPolicy | the owner that resolves mode+workspaceRoot per call (default read-only, fail-safe) |
| Errors | SANDBOX_UNAVAILABLE (could not execute the requested mode) |

**`SandboxMode` covers only filesystem effects**: there is **no** network, process, syscall, device, or credential limiting in the vocabulary. That is its security boundary, and also what it cannot do.

## 4. Backend implementations and prerequisites

| Platform | Backend | Prerequisite |
| --- | --- | --- |
| Linux | bwrap (bubblewrap) or the Landlock launcher | install bubblewrap or run a Landlock-enforcing kernel |
| macOS | sandbox-exec (Seatbelt) | already deprecated by Apple, seams remain usable |
| Windows | @deepseek-ai/dsh-sandbox-windows-acl restricted-token runner (write-SID allowlist) | the runner can start; enforcement is always partial |

**Containers / microVMs / remote executors are not backends of this seam**: they are providers that **replace** `ctx.shell`/`ctx.fs` wholesale (as an "environment-consistent group"), not providers added to the sandbox. Getting into Docker or a remote machine is a matter of replacing the capability implementation, not adding a backend to `confine`.

### "Same world" limit (explicit in source)

Sandbox backends **share the host's filesystem and kernel** (bwrap / Landlock / Seatbelt). `workspaceRoot` names a **real host directory** of the filesystem norm. Workspace identity is resolved **before lexical normalization**: so a legitimate cwd containing `symlink/..` authorizes the directory `chdir` actually lands in, not an unrelated lexical parent.

## 5. Policy rides the call, not the provider

Policy belongs to the call, not the provider:

- **two consumers can impose limits under different policies simultaneously**: bash uses `read-only` while a restricted subagent keeps its state directory writable

- an **approved escalation retry** = a **new call** issued with a wider policy

- **one context, one provider**: to combine different sandbox mechanisms you need a provider-level ladder or a separate Cordis context; callers pick policy per call, not backend identity

## 6. The home of policy: ctx.sandboxPolicy

`@deepseek-ai/dsh-sandbox-policy` is the **sole owner of policy resolution**: the deployment default `SandboxMode` + fallback workspace root, plus per-session persistent mode overrides and an immutable workspace root. Every execution capability receives the **same** "mode + root" policy per call; before each request the model receives the current policy, not a separate capability list.

Why a shared home: the fs tool, one-off bash commands, and terminal sessions may enforce the same mode vocabulary under **different combinations**. If each resolved `mode` + `workspaceRoot` on its own, they would drift into a "split world" — precisely what is to be avoided. So every execution backend consumes the **owner-resolved whole policy**; the current context only describes what that policy means for any operation the DSH file sandbox can perform.

```ts
ctx.sandboxPolicy.resolve({ session?, mode? })  // resolves one complete per-call policy

ctx.sandboxPolicy.defaultMode / .workspaceRoot  // deployment default and fallback root

setSandboxMode(session, mode)                   // sole write path for session overrides: appends exactly one sandbox/mode event
```

Resolution priority: **explicitly approved mode > the session's last `sandbox/mode` event > `defaultMode`**; the session's immutable `cwd` is normalized through filesystem semantics into `workspaceRoot` (normalization precedes lexical normalization, so `symlink/..` resolves consistently with the process working directory), otherwise it falls back to config. A runtime switch is just **one log-only `sandbox/mode` event**, `effective = explicit grant ?? fold(events) ?? deployment default`; overrides survive restarts via replay, and two sessions never see each other's state.

Mount: base defaults to mounting `sandbox-policy` (`mode: $DSH_PERMISSION_MODE ?? 'workspace-write'`, `workspaceRoot: process.cwd()`), with fail-safe default `read-only`.

## 7. The filesystem fence: fs-sandbox

`@deepseek-ai/dsh-fs-sandbox` extends `LocalFileSystem` and registers as `ctx.fs`: it verbatim inherits all text-storage mechanics (parsing, stat, read/stream, directory listing, atomic write, read-modify-write edit critical sections) and **adds only a per-call MODE fence** on `writeText`/`editText`. **Reads always pass** — every mode allows reads.

| mode | Fence behavior |
| --- | --- |
| read-only | denies all mutations, structured FS_SANDBOX_DENIED |
| workspace-write | passes only when the target, canonicalized, lands inside the writable roots: the workspace root + platform temp areas (/tmp, os.tmpdir()) — the same set the Seatbelt profile grants, both from the same writableRoots function, so the fs fence and the bash runner never drift |
| danger-full-access | delegates directly, no fence |

The threat model is explicit: **this is a policy fence, not a kernel boundary** — paths under model control are canonicalize-then-contain inside trusted code; kernel-level isolation of untrusted code remains `ctx.shell`'s job (`dsh-bash-sandbox`). Residual TOCTOU (an ancestor symlink swapped between the containment check and the syscall) is narrowed by re-canonicalizing immediately before writing. Denials are **structured `FsError`** (with the effective mode), not stderr-text inference (unlike bash's kernel denials) — because an in-process fence knows exactly what it denied.

Mount: base defaults to mounting `fs-sandbox` (**replacing** `fs-local`, which together with `ctx.sandboxPolicy` is the whole swap); the model-facing `dsh-tool-fs` is untouched, the tool layer resolves the session mode + cwd into the **same** per-call policy bash receives, and the two families never limit to different roots.

## 8. Windows' PowerShell executor: pwsh-sandbox

`@deepseek-ai/dsh-pwsh-sandbox` is a **sandbox-consuming PowerShell implementation** of the `ctx.shell` executor seam: every command runs as `pwsh -NoLogo -NoProfile -NonInteractive -Command <command>`, **constrained through `ctx.sandbox`**, and stamps the selected mode, enforcement, and denial facts onto each settled result. It is `dsh-bash-sandbox`'s pwsh twin, mirroring it call for call.

- the constraints are **substantively platform-neutral**: on Windows the sandbox seam resolves to the ACL restricted-token runner chain, on Linux/macOS to bwrap/Landlock/Seatbelt

- `danger-full-access`: the command passes through to the local executor as-is, result carries `sandbox: { mode, denied: false }`

- restricted modes (`read-only`/`workspace-write`): the pwsh argv is wrapped by `ctx.sandbox.confine()`; a denied runner start fails closed into `SANDBOX_UNAVAILABLE` (a foreground throw, a backend `runnerFailed` fact), and denied writes are classified into `sandbox.denied` per the selected backend's `denialSignatures`

- policy is **not** its config: it is carried in from `ctx.sandboxPolicy` per call (tool calls pass the calling session's resolved policy, direct calls fall back to the deployment policy)

Mount: the base bundle uses **inline platform gating** — `bash-sandbox` / `tool-bash` carry `disabled: !!js process.platform === 'win32'`, `pwsh-sandbox` / `tool-pwsh` carry `disabled: !!js process.platform !== 'win32'` (there is no separate `windows.cordis.patch.yml`), and the permission surface stays fully consistent with POSIX. A UTF-8 encoding preamble (`ENCODING_PREAMBLE`) is prepended to the command so Windows PowerShell 5.1 also emits UTF-8. Known limitations: on Windows **reads are unrestricted** (the ACL runner limits only writes); enforcement is always `partial` (the restricted token must retain Everyone, `> $null` redirection still works).

## 9. Failure modes (what the model sees)

When the requested mode cannot be enforced, `SANDBOX_UNAVAILABLE` + a precise error is returned:

```text
sandbox mode "<mode>" is requested but no sandbox backend is usable

  on this host; refusing to run the command unconfined.

  Install bubblewrap or run a Landlock-enforcing kernel (Linux),

  ensure sandbox-exec is usable (macOS),

  or ensure the ACL restricted-token runner can start (Windows) —

  otherwise switch the consumer to danger-full-access.
```

Execution-time runner failures append `Runner failure: <detail>`. This error text stays visible to that call until compaction hides it.

## 10. Relationship to permission presets and approval policies

These get confused easily, so the three concepts are spelled out:

| Mechanism | What it governs | Where it is chosen |
| --- | --- | --- |
| permission preset | one profile = one sandbox mode + one approval policy | permission.defaultPreset in settings or /permission |
| approval | whether ask / never asks the user | same preset |
| sandbox | the filesystem boundary when a command actually executes | per call ctx.sandbox.confine |

The shipped preset table has three profiles (the base bundle's `permission` row): `read-only` (sandbox `read-only` + approval `ask`), `workspace-write` (`workspace-write` + `ask`), `danger-full-access` (`danger-full-access` + `never`). Select one in settings:

```yaml
# ~/.dsh/settings.yaml — selects the "mode profile"

permission:

  defaultPreset: workspace-write
```

**Important**: a preset only writes the `sandbox/mode` + approval events; **the execution boundary follows the mode**. Under `read-only` / `workspace-write` consumers always pass through `ctx.sandbox.confine`; under **`danger-full-access` `bash-sandbox` / `pwsh-sandbox` / `fs-sandbox` short-circuit**, delegating straight to the underlying executor and stamping the result `sandbox: { mode, denied: false }` — that profile really does give up the filesystem boundary rather than staying wrapped by `confine`. So choosing a preset is choosing "boundary or not"; `SANDBOX_UNAVAILABLE` is thrown only when a restricted mode has no usable backend.

## 11. Security boundary and known limitations (an honest list)

The limitations the source README explicitly states, and which you should remember as "what it can't protect me from":

| Limitation | Meaning |
| --- | --- |
| filesystem effects are the whole vocabulary | no network/process/syscall/device/credential limiting |
| same world | does not isolate the host (containers/microVMs/remote require replacing the provider) |
| denial is a stderr dialect | no typed runtime denial channel; consumers must infer from child-process output |
| runner diagnostics are in-band | exit status + stderr cannot prove which line was written by which process: a constrained child process mimicking the runner can mislead diagnostics (but cannot bypass confinement) |
| one context, one provider | combining different sandboxes requires a provider-level ladder or a separate context |

The conclusion of these limitations: the DSH sandbox is a **process-level filesystem-effect boundary**, guarding against "don't let the agent accidentally write/change/delete out of bounds", not against "defending against malicious processes or full isolation".

## 12. Verification

```sh
# 1. With no backend, commands are denied rather than run bare (observe the SANDBOX_UNAVAILABLE error path)

dsh web

# 2. Check whether the sandbox is mounted / which provider, and the current preset

dsh web --dump-config | grep -iE "sandbox|permission"

# 3. Inspect mode switches and tool-execution denials in sessions (sandbox denials are stderr dialects; current format version v3)

zstdcat ~/.dsh/sessions/*/*/session.v3.jsonl.zstd | grep -E '"sandbox/mode"' | head

zstdcat ~/.dsh/sessions/*/*/session.v3.jsonl.zstd | grep -iE "EROFS|EACCES|EPERM" | head
```

## Next steps

- [Tool Execution](../../learn/core/tools-execution.md): tools declare capability, the sandbox bounds execution (how the two work together)

- [Permissions](../../user-guide/permissions.md): presets and ask/never

- [Agent Presets & Persona](../../features/persona.md): scope composition and security (restrict is visibility, not a permission boundary)
