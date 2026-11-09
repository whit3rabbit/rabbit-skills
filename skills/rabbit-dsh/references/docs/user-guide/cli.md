# Command Line

New behavior below tracks source `0.1.5-alpha.1` (`5dda764ed3`); npm `latest` / `next` resolve to `0.1.2-rc.1` and the `alpha` channel is `0.1.5-alpha.1`. See [version channels](../guides/deepseek-harness-status.md).

`dsh` is the single entry-point command — almost everything starts with a `dsh`.

The official zero-install entry point is `npx @deepseek-ai/dsh ...`, requiring Node.js `^22.19.0` or `>=24.0.0`. Inside the official source checkout, use `pnpm dsh ...`. The rest of this page uses `dsh ...` for either available entry point.

## Contents

- [1. Basic Usage](#1-basic-usage)
- [2. launcher flags (launcher layer)](#2-launcher-flags-launcher-layer)
- [3. Web subcommand](#3-web-subcommand)
- [4. headless one-off tasks](#4-headless-one-off-tasks)
- [5. Plugin management](#5-plugin-management)
- [6. Inspecting configuration](#6-inspecting-configuration)
- [7. Environment variables](#7-environment-variables)
- [8. Common command scenarios](#8-common-command-scenarios)
- [SDK and ACP profile entry points](#sdk-and-acp-profile-entry-points)
- [Next steps](#next-steps)

---

## 1. Basic Usage

```sh
dsh --profile web                      # Start the web profile (equivalent to dsh web)

dsh web                                # Web UI (alias for --profile web)

dsh --profile headless "run the tests" # One-off task; exits after it completes

dsh plugin ...                         # Manage profile plugin dependencies
```

The `dsh run` subcommand has been removed; one-off tasks now use `--profile headless <task>`.

## 2. launcher flags (launcher layer)

These are consumed by dsh before being passed to the app:

```text
--profile <name>            Select $DSH_HOME/profiles/<name> (auto-initialized on first use)

--from-default-profile <name>  Initialize a new custom profile from a shipped template, then boot it

--patch <path>             Stack an additional overlay patch (repeatable, takes precedence over the profile layer)

--dump-config              Print the composition tree and exit

--dump-default-config      Print only the bundle layer (no user layer / --patch)
```

```sh
dsh --profile web --dump-config       # Inspect the web profile's full composition

dsh --profile tui --patch ./extra.yml # Start with a custom patch

dsh --profile rescue --from-default-profile web  # Create rescue from the web template and boot it
```

Two key mechanisms:

- **The launcher only eats its own flags; everything else is passed through to the app as-is.** The first token the launcher does not recognize begins the "inner arguments", which flow verbatim into the config tree: for example, `dsh --profile tui --resume abc` has inner arguments `['--resume', 'abc']` (where `--resume` is a flag of the TUI app itself).

- **Flag position is significant**: launcher flags must come before the app arguments; a `--patch` placed after an app flag belongs to the app. The launcher consumes one `--`; to pass a literal `--` through to the app, write `-- --`.

- `-V` / `--version` is the **launcher's own** flag (it must precede app arguments); `-h` / `--help` goes to the **app**, and only a bare `dsh -h` (no profile to hand it to) prints the launcher help.

- Both dumps skip the app's command-line providers and therefore reject app arguments; `--dump-config` adds the profile's `cordis.patch.yml`, the home-level `$DSH_HOME/cordis.patch.yml`, and `--patch` overlays, while `--dump-default-config` prints only bundle layers and accepts no `--patch`.

## 3. Web subcommand

```sh
dsh web --port 8080              # Specify a port (0 = random)

dsh web --host <host>            # Bind host (0.0.0.0 is rejected)

dsh web --trusted-host <host>    # Trusted host (repeatable)

dsh web --no-open                # Do not open a browser automatically

dsh web --dump-config            # Print the config tree and exit
```

- The Web UI listens on `127.0.0.1:3080` by default

- The workspace is selected with a directory picker inside the Web UI (not a CLI flag)

- Dev HMR: in the source directory, `pnpm run dev:web` rebuilds the client assets and `dsh web` polls for hot updates automatically

Source Web builds exchange the printed token launch URL for a browser session. All RPC and WebSocket calls check the cookie. Startup rejects `--host 0.0.0.0`; `--trusted-host` configures Host trust, not authentication.

## 4. headless one-off tasks

`--profile headless` runs a one-off task: the task text is the rest of the command line, submitted as an ordinary user message, and after it finishes the last non-empty assistant text is written to stdout before exiting.

```sh
dsh --profile headless "run pnpm test, summarize the failures into a list"

dsh --profile headless "review the auth logic in src/server.ts and give 3 actionable suggestions"

dsh --profile headless "use glob to list all call sites still using the old API" > /tmp/out.txt
```

Behavior notes:

- Exit code: `turn/end` is `completed` → `0`, otherwise `1`.

- The source build streams non-empty provider reasoning fragments to stderr under a `dsh: reasoning:` heading and prints only the final text on stdout; a successful response with no reasoning keeps stderr empty. Errors also report their code and message there.

- Submits only **one** task, with no interactive follow-up UI; listens on no ports (no Host/Web/browser attached).

- It is a "run-and-exit" form friendly to CI/scripts, suitable for putting into a shell, cron, or Makefile.

## 5. Plugin management

```sh
# Install a bundle plugin (git source on one line)

dsh plugin --profile web add "github:dsh-external/<repo>#main"

# Local directory development

dsh plugin --profile web add link:/path/to/plugin

# Remove / inspect dependencies

dsh plugin --profile web remove <package>

dsh plugin --profile web why <package>
```

`plugin` **forwards its arguments verbatim to pnpm**, executed in the profile directory; it only accepts sources pnpm recognizes (pure git sources, `link:`, etc.). A missing profile is initialized first (from a shipped template when one exists, otherwise with only `@deepseek-ai/dsh-base`), and relative-path specs are anchored to the invocation directory first. The `&path:` subpath is a format of the repository plugin mechanism itself; to install a monorepo sub-package use the **repository source in the plugin panel**, not `dsh plugin add`. After installing a bundle, **restart `dsh web`** for it to take effect (repository plugins apply immediately).

## 6. Inspecting configuration

```sh
dsh web --dump-config              # Composed config tree (with layer-source comments)

dsh web --dump-default-config      # Bundle layer only
```

`--dump-config` is the authoritative tool for diagnosing "which layer overrode what" (see [Boot and Configuration](../learn/core/boot-config.md)).

## 7. Environment variables

| Variable | Purpose |
| --- | --- |
| DSH_HOME | Overrides the home directory (default ~/.dsh) |
| DSH_TELEMETRY_MODE | Telemetry mode (default FEEDBACK_ONLY; DISABLED keeps everything local, FULL streams uploads) |
| DSH_TELEMETRY_DISABLED | Any non-empty value disables telemetry |
| DSH_TELEMETRY_OTLP_URL | Overrides the telemetry reporting endpoint |
| DSH_PERMISSION_MODE | Permission/sandbox mode override (default workspace-write; danger-full-access disables approvals) |
| DSH_TOOLS_MODE | Tool presentation mode (native|ptc|both; unset uses the schema default native) |
| DEEPSEEK_API_KEY etc. | provider credentials (can also live in .env) |

See [Environment Variables](../reference/env-vars.md) for the full list.

## 8. Common command scenarios

| What you want | Command |
| --- | --- |
| Run a web session | dsh web |
| Run a one-off task | dsh --profile headless "task" |
| Save the result of a one-off task | dsh --profile headless "task" > /tmp/out.txt |
| Start with app-layer flags | dsh --profile tui --resume abc |
| Inspect the current composition | dsh web --dump-config |
| Bundle layer only | dsh web --dump-default-config |
| Install a plugin | dsh plugin --profile web add "github:..." |
| Install a plugin from a local directory | dsh plugin --profile web add link:/path/to/plugin |
| Start with a custom patch | dsh --profile tui --patch ./extra.yml |

## SDK and ACP profile entry points

```sh
dsh --profile sdk --help

dsh --profile sdk-minimal --help

dsh --profile acp --help
```

Source builds launch these applications through `dsh` profiles instead of separate demo bins. `sdk`, `headless`, and `acp` use `read`/`write`/`edit` for file editing by default (0.1.3-alpha.2), while `sdk-minimal` and Web minimal keep `str_replace_editor`. `sdk-minimal` is standalone, does not inherit `base`, and pins full filesystem access: use an isolated disposable workspace. SDK / ACP reserve stdout for protocol frames. See [SDK](../guides/drive-harness-from-program.md) and [ACP](../guides/acp-automation-server.md).

## Next steps

- [Configuration](../user-guide/configuration.md): profile / patch / settings

- [Plugins](../user-guide/plugins.md): full overview of plugin management

- [Quickstart](../getting-started/quickstart.md): get your first session running
