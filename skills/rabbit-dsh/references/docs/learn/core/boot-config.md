# Boot & Configuration

- 
- Concepts Course
- Core Mechanisms
- Boot & Configuration
On this page

# Boot & Configuration

Audit baseline 0.1.5-alpha.1 @ 5dda764ed3.

**One-liner**: `dsh`'s startup = the `app-boot` glue layer that assembles "environment → profile → bundle layers → your patch layers" into one config tree; the Loader loads, asserts, activates, and fails loudly on failure (`dsh:`-prefixed exit).

`dsh web` / `dsh --profile <name>` both run through the same boot. Understand it and you'll know "which layer a change lands in, which layer overrides which, and how to inspect the config tree".

## Contents

- [1. Startup flow (boot glue layer)](#1-startup-flow-boot-glue-layer)
- [2. Layered environment variables](#2-layered-environment-variables)
- [3. Profile mechanism](#3-profile-mechanism)
- [4. Fail-loud behavior](#4-fail-loud-behavior)
- [5. Inspecting configuration: --dump-config](#5-inspecting-configuration-dump-config)
- [6. Verification](#6-verification)
- [Next steps](#next-steps)

---

## 1. Startup flow (boot glue layer)

## 2. Layered environment variables

`loadLayeredEnv` priority:

```text
inherited env > project .env > user .env
```

- **bootstrap-only variables from files are rejected**

- file values are materialized **without replacing inherited values**

## 3. Profile mechanism

| Function | Responsibility |
| --- | --- |
| resolveProfileDir / initProfile | Locate / initialize $DSH_HOME/profiles/ |
| readProfileManifest | Read the profile's dsh.profile.bundles list |
| composeEntries | Combine the bundle layers into entries |
| loadOptionalPatches | Parse cordis.patch.yml (top-level YAML: insert / override / !!js) |
| watchUserPatches | HMR: transactionally re-compose on patch change |

Key details:

- **5 built-in templates** (auto-initialized on first use); `tui` etc. require a self-built directory

| Template | dsh.profile.bundles | patchReload |
| --- | --- | --- |
| acp | @deepseek-ai/dsh-base + @deepseek-ai/dsh-acp-app | startup |
| web | @deepseek-ai/dsh-base + @deepseek-ai/dsh-web-app | live |
| headless | @deepseek-ai/dsh-base + @deepseek-ai/dsh-headless | startup |
| sdk | @deepseek-ai/dsh-base + @deepseek-ai/dsh-sdk-app | startup |
| sdk-minimal | @deepseek-ai/dsh-sdk-minimal | startup |

- A self-built profile absent from the table defaults to `patchReload: live`; `dsh --profile <new-name> --from-default-profile <template>` copies a new profile from a template

- `initProfile` creates: directory + `package.json` (with `dsh.profile.bundles` and `patchReload`) + a commented `cordis.patch.yml` template + `pnpm-workspace.yaml` (`nodeLinker: hoisted`)

- `healProfilesModuleFallback` maintains the `$DSH_HOME/profiles/node_modules` installation-dependency-closure fallback (symlinks under plain Node, ESM proxies for a packaged executable), so out-of-tree plugins resolve to the **same** cordis; bundle-private dependencies are linked through the profile's own `node_modules`

- A home-directory-level `cordis.patch.yml` (`$DSH_HOME/cordis.patch.yml`) overrides the per-profile layer; the application order is **bundle layers → profile patch → home patch → `--patch` overlays → telemetry switch**

See the complete patch application order in [Plugin Anatomy](../../learn/core/plugin-anatomy.md).

## 4. Fail-loud behavior

When `$DSH_SNAPSHOT === 'replay'`, `resolveConfigPath` swaps `cordis.yml` for `cordis.snapshot.yml` (snapshot replay). On load failure:

```sh
$ dsh web   # on plugin resolution failure

dsh: plugin tree failed to load: ...

# or

dsh: fatal load failure: <Error stack>

# The tag prefix is always 'dsh:', the process exits(1), it never runs while broken
```

The two assertion functions differ:

| Assertion | What it checks |
| --- | --- |
| assertEntriesLoaded | After the tree settles, entries that exist as enabled but have no fiber → throw |
| assertEntriesActivated | Then waits for each enabled entry to activate; errors carry the raw stack |

## 5. Inspecting configuration: --dump-config

```sh
dsh web --dump-config          # renders the current composition tree (with '# == ' layer-source comments)

dsh web --dump-default-config  # renders only the bundle layers (no user layer, no --patch overlays)

dsh web --patch ./extra.yml    # temporarily overlays one patch layer (repeatable, applied after the profile layer)
```

`--dump-default-config` is the recovery diagnostic for a broken user layer: it does **not** parse `cordis.patch.yml`. `renderConfigDump` synthesizes the tree offline using the Loader's own parser, **so the result matches real startup**: this is the authoritative tool for troubleshooting "which layer overrode what". Each line's `# ==` comment marks which layer it came from (base / web-app / your profile / a `--patch` file).

## 6. Verification

```sh
dsh web --dump-config | head -30      # inspect the layered structure and source comments
```

## Next steps

- [Context](../../learn/core/context.md): what the model sees

- [Agent Main Loop](../../learn/core/agent-loop.md): how the loop drives

- [Plugin Anatomy](../../learn/core/plugin-anatomy.md): how the patch layer works
