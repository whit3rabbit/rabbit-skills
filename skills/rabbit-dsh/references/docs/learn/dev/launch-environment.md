# Launch Environment Snapshot

- 
- Concepts Course
- Plugin Development
- Launch Environment Snapshot
On this page

# Launch Environment Snapshot

**In one sentence**: `launchEnvironmentOf(ctx)` returns the one snapshot frozen at launch for this run, and **remembers which layer each value came from** — the inherited `process` environment, the project `<cwd>/.env`, or the user's `$DSH_HOME/.env`. Plugins resolve user-facing values with `get(name)`, or use `getFrom(name, sources)` to search only the allowed layers, where omitting a layer is a **refusal, not a demotion**.

This is an extension of [Runtime introspection](../../learn/dev/runtime-tools.md): instead of checking which plugins are mounted, it peels open **the launch environment layer**. DSH does not want you to read a flattened `process.env`, because the three layers are not equally trusted and a flattened view cannot tell them apart — "this is what the user explicitly exported" versus "this was slipped in by someone's `.env` in the project." After this read you can correctly resolve environment configuration in your own plugin and understand its boundary with env-vars (the loading side) and credentials (the credential-resolution side).

## Contents

- [1. The overall model](#1-the-overall-model)
- [2. Entry point: launchEnvironmentOf(ctx)](#2-entry-point-launchenvironmentofctx)
- [3. The two snapshot methods: get and getFrom](#3-the-two-snapshot-methods-get-and-getfrom)
- [4. Three immutable construction details](#4-three-immutable-construction-details)
- [5. Boundary with env-vars (loading side) and credentials (credential-resolution side)](#5-boundary-with-env-vars-loading-side-and-credentials-credential-resolution-side)
- [6. Verification and try it](#6-verification-and-try-it)
- [Next steps](#next-steps)

---

## 1. The overall model

| Layer | Source id | What it is |
| --- | --- | --- |
| Inherited process environment | process | What the launching shell, CI job, or container passed in — this run's explicit intent |
| /.env | project-env | The project the harness was launched in; the product trusts it to configure its own agent |
| $DSH_HOME/.env | user-env | The user's own machine-level defaults |

Trust order, highest to lowest: **inherited environment > project `.env` > user `.env`**, hardcoded in the source:

```ts
// packages/util/launch-environment/src/index.ts

const SOURCE_ORDER: readonly LaunchEnvironmentSource[] = ['process', 'project-env', 'user-env']
```

These values also reach `process.env` — the user's own `--config` tree and third-party libraries read it — but that flattened view is **not the authority** for anything the harness resolves. Plugins resolve through the snapshot API, not `process.env`.

## 2. Entry point: launchEnvironmentOf(ctx)

Source: `launchEnvironmentOf` and `DSH_LAUNCH_ENVIRONMENT_KEY` in `packages/util/launch-environment/src/index.ts`.

The context slot key is **`launchEnvironment`** (the string constant `DSH_LAUNCH_ENVIRONMENT_KEY`). It reads it with `ctx.get(DSH_LAUNCH_ENVIRONMENT_KEY)`; **when there is no snapshot it falls back to a snapshot with only the `process` layer** (the `??` branch below):

```ts
// packages/util/launch-environment/src/index.ts

export function launchEnvironmentOf(ctx: Context): LaunchEnvironmentSnapshot {

  return ctx.get(DSH_LAUNCH_ENVIRONMENT_KEY)

    ?? createLaunchEnvironmentSnapshot([{ source: 'process', values: process.env as Record<string, string> }])

}
```

The fallback does not weaken the rules: when the product CLI boots the tree, the launcher puts the snapshot into `ctx.launchEnvironment`; an SDK host or a bare `cordis.yml` never discovered any files, so all it has **really is** the environment it was launched with (only the `process` layer — no project/user `.env`).

The slot's type is exposed through declaration merging, so plugins can type-access it directly:

```ts
// packages/util/launch-environment/src/index.ts (tail)

declare module '@deepseek-ai/cordis' {

  interface Context {

    /** Launcher-owned snapshot of this run's environment; absent in compositions the product CLI did not boot. */

    launchEnvironment?: LaunchEnvironmentSnapshot

  }

}
```

A consumption example — resolve a user-facing value, falling back to your own default:

```ts
import { launchEnvironmentOf } from '@deepseek-ai/dsh-launch-environment'

import type { Context } from '@deepseek-ai/cordis'

export function apply(ctx: Context) {

  const entry = launchEnvironmentOf(ctx).get('DEEPSEEK_BASE_URL')

  const baseUrl = entry?.value ?? 'https://api.deepseek.com'

  // entry?.source   → 'process' | 'project-env' | 'user-env' (who supplied it)

  // entry?.path     → absolute path of the .env that supplied it (absent for process)

}
```

## 3. The two snapshot methods: get and getFrom

`LaunchEnvironmentSnapshot` is a read-only interface with just two methods. After construction **nothing mutates the snapshot** — so even a later `chdir`, workspace switch, or resumed session observes the same values a consumer resolved at boot.

| Method | Semantics |
| --- | --- |
| get(name) | Searches all layers in canonical trust order; returns the winning { value, source, path? }, or undefined when no layer supplies it |
| getFrom(name, sources) | Searches only the layers listed in sources, retaining canonical trust order; unlisted layers are unreachable |

Each entry looks like this:

```ts
interface LaunchEnvironmentEntry {

  value: string                 // the value as the layer supplied it; may be empty, each owner judges for itself

  source: LaunchEnvironmentSource  // 'process' | 'project-env' | 'user-env'

  path?: string                 // absolute path of the .env that supplied it; absent for process

}
```

The source tests over a three-layer snapshot illustrate the behavior best (`packages/util/launch-environment/tests/launch-environment.spec.ts`):

```ts
const layered = createLaunchEnvironmentSnapshot([

  { source: 'process',     values: { SHARED: 'from-process', ONLY_PROCESS: 'p' } },

  { source: 'project-env', path: '/work/.env', values: { SHARED: 'from-project' } },

  { source: 'user-env',    path: '/home/.dsh/.env', values: { SHARED: 'from-user' } },

])

layered.get('SHARED')        // { value: 'from-process', source: 'process' }  ← trust order wins

layered.get('ABSENT')        // undefined

layered.getFrom('SHARED', ['user-env', 'process'])

                             // { value: 'from-process', source: 'process' }  ← still canonical order, not your ordering

layered.getFrom('ONLY_PROCESS', [])  // undefined
```

### Omitting a layer is a "refusal", not a "demotion"

`getFrom` does not change trust order, it **excludes layers**. That is the whole reason it exists: **a caller that must never accept a layer simply leaves it out of the list.** A routing field that must never come from a project directory can only be secured by *not listing* `project-env` — not by reordering, because reordering would still let it leak back in unchanged.

`credentials-local` is the textbook example (`packages/credentials/credentials-local/src/index.ts`): the inherited environment goes through `getFrom(ref, ['process'])`, and the `.env` fallback through `getFrom(ref, ['project-env', 'user-env'])` — the two sides are deliberately split and neither may cross into the other:

```ts
// inherited environment first, and only process

const entry = launchEnvironmentOf(this.ctx).getFrom(ref, ['process'])

// the .env fallback sits below the managed store, project ranks over user

const entry = launchEnvironmentOf(this.ctx).getFrom(ref, ['project-env', 'user-env'])
```

Provider adapters (e.g. an LLM provider reading its API key) list all three layers: the product trusts the project it runs in. The `getFrom` mechanism exists for the decisions where that is **not** true.

### Windows case folding

Names match the way the platform matches them: exactly on POSIX, case-insensitively on Windows. `lookupKey` calls `toUpperCase()` only on `win32`:

```ts
// packages/util/launch-environment/src/index.ts

function lookupKey(name: string): string {

  return process.platform === 'win32' ? name.toUpperCase() : name

}
```

Why it matters: a case-sensitive lookup on Windows would **rank the wrong layer** — a shell's `deepseek_api_key` and a project `.env`'s `DEEPSEEK_API_KEY` are one variable to the OS, and treating them as two would let the project win. POSIX does not fold.

## 4. Three immutable construction details

`createLaunchEnvironmentSnapshot` carries three more details that prevent misuse (all from the source and tests):

```ts
// packages/util/launch-environment/src/index.ts (excerpt)

const bySource = new Map(...)  // every layer's contents are copied into a Map; later mutation of the source cannot change it
```

- **It copies layer contents**: construction copies each layer's `values` into its own `Map`; later edits to the source object (e.g. adding a key to `process.env`) cannot change the snapshot. A test verifies "build the snapshot, then mutate the source, the snapshot is unchanged."

- **An empty value counts as present**: if a layer supplies an empty string, `get` still returns `{ value: '', ... }` — the owner judges for itself whether the empty string counts (e.g. credentials-local only treats a value when `length > 0`).

- **Lookup order is independent of construction order**: the snapshot searches by canonical `SOURCE_ORDER` regardless of the order you pass the layers.

## 5. Boundary with env-vars (loading side) and credentials (credential-resolution side)

`dsh-launch-environment` only **provides a read-only snapshot**. It does not load `.env` and does not parse credentials — loading and credential resolution live in other packages.

| Stage | Package | Responsibility |
| --- | --- | --- |
| env-vars loading side | loadLayeredEnv in packages/boot/app-boot | At launch, reads process, /.env, $DSH_HOME/.env, constructs the snapshot and puts it on ctx.launchEnvironment |
| snapshot read side | launch-environment | This is the API documented here |
| credentials resolution side | packages/credentials/credentials-local | Uses getFrom to treat the environment as a fallback below the managed store |

Key points of the loading side `loadLayeredEnv` (`packages/boot/app-boot/src/index.ts`):

- It parses the `.env` files **before** applying either: a rejection in one layer must not leave only one file applied.

- When materializing checked values back into `process.env`, it does **not overwrite** a higher-ranked name (`if (process.env[name] === undefined)`).

- A `.env` must not declare **bootstrap-only** variables — variables that decide "how this process starts, where its code and instructions load, and how it reaches the network" may only be exported by the launching environment; putting them in a `.env` is rejected.

- **No per-workspace layer**: the project layer is the *invoking* directory, fixed at launch; a workspace selected later in the Web UI contributes nothing, deliberately (following it would let a model's own workspace change the harness environment mid-session).

The boundary with credential resolution in one sentence: **credentials' precedence lives in the managed store; the `.env`/environment is only its lowest fallback tier.** The credentials package never treats `.env` as the first source; it uses `getFrom` to pin down exactly which layers it is allowed to read and touches nothing else.

## 6. Verification and try it

```sh
# See the three-layer snapshot, SOURCE_ORDER, and the "refusal, not demotion" behavior of getFrom

cd ~/.dsh/source/current && npx vitest run packages/util/launch-environment/tests/launch-environment.spec.ts

# See a real consumer resolving value + reading only the process layer

grep -n "launchEnvironmentOf.*getFrom" packages/credentials/credentials-local/src/index.ts

# See configs that fall back to an environment variable

grep -rn "launchEnvironmentOf(ctx).get" packages/llm packages/web | head
```

Verify which layer a concrete value comes from in a session (after exporting it, observe `source`/`path`):

```sh
# Have the model run a consumer that prints the source; or just check:

#   launchEnvironmentOf(ctx).get('DEEPSEEK_BASE_URL')

# returns { value, source, path? } — use source to tell who provided it
```

## Next steps

- [Runtime invariants](../../learn/dev/runtime-invariants.md): how DSH continuously self-checks runtime contracts

- [Runtime inspection and dynamic plugins](../../learn/dev/runtime-tools.md): query contracts with `cordis_inspect_list/query`, then use `define → run/update`

- [Write a service](../../learn/dev/write-service.md): a capability, not just a tool
