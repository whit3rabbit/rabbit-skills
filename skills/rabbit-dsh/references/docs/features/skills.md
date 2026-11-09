# Skill System

Skills are **on-demand-loadable capability descriptions**: the model loads a skill's instructions into context when it needs them, rather than stuffing every skill's full text into the system prompt. This is **progressive disclosure**: occupy as little token real estate as possible until the moment you genuinely need the full content.

DSH's skill seam is `ctx.skills` (`@deepseek-ai/dsh-skill`). It is a host + per-scope layered registry, consistent with the scope model of tool registration.

## Contents

- [Three observation/load interfaces](#three-observationload-interfaces)
- [Where skills come from](#where-skills-come-from)
- [Skill catalog layout (skill-filesystem)](#skill-catalog-layout-skill-filesystem)
- [Invocation policy](#invocation-policy)
- [Registering a skill at runtime](#registering-a-skill-at-runtime)
- [Model invocation via tool-skill](#model-invocation-via-tool-skill)
- [The badge package](#the-badge-package)
- [Events and invalidation](#events-and-invalidation)
- [Verification](#verification)
- [Configuration](#configuration)
- [Next steps](#next-steps)

---

## Three observation/load interfaces

| Interface | Purpose | Token magnitude |
| --- | --- | --- |
| ctx.skills.list(...) | summaries of the skills in the current workspace's merged layers (name-sorted) | small |
| ctx.skills.snapshot({ cwd, signal, scope }) | a call-independent { skills, complete } observation | medium |
| ctx.skills.get(name, ...) | fetches the full skill definition (discovery + load) | large, on demand |

The model typically does: `list()` to get a name list → `get(name)` to expand the full text when needed. `isModelInvocable(skill)` / `isUserInvocable(skill)` decide who can trigger it.

## Where skills come from

`ctx.skills` itself doesn't know whether a skill lives in a local file, embedded plugin data, or a remote location: a **provider** provides the source:

- `@deepseek-ai/dsh-skill-filesystem`: the shipping local-file implementation

- `ctx.skills.register(skill)`: registers a read-only **runtime-embedded** skill into the current scope layer

- any third-party provider plugs in via `ctx.skills.registerProvider(...)`

Layer semantics (consistent with tools): a global layer vs an agent-preset layer; reads merge the global layer + the inspecting scope's chain, with the nearest same-name layer winning.

## Skill catalog layout (skill-filesystem)

The local provider recognizes two shapes, discovering **only one directory level deep**: a directory bundle `<root>/<name>/SKILL.md`, or a flat file `<root>/<name>.md`. In the frontmatter, `name` and `description` are required; `whenToUse`, `metadata`, `disable-model-invocation`, and `user-invocable` are optional, and the name must be kebab-case.

Default roots resolve by rank:

| Rank | Source | Path |
| --- | --- | --- |
| 100 | project-dsh |

/.dsh/skills |
| 200 | project-agents | /.agents/skills |
| 300 | custom | Config.customSkillDirs |
| 400 | user-dsh | /skills |
| 500 | user-agents | /skills |

The project root is the nearest `.git`-containing ancestor, falling back to the current cwd; the user DSH root skips the `.system` subdirectory.

## Invocation policy

`SkillSummary.invocation` is a required policy object; two positive booleans independently describe the "model side" and the "user side":

| Policy | Model | User |
| --- | --- | --- |
| { modelInvocable: true, userInvocable: true } | included | included |
| { modelInvocable: true, userInvocable: false } | included | excluded |
| { modelInvocable: false, userInvocable: true } | excluded | included |
| { modelInvocable: false, userInvocable: false } | excluded | excluded |

`ctx.skills.get()` remains the **policy-neutral** load primitive; each model-facing/user-facing consumer executes the corresponding predicate at its own boundary before exposing or loading. The frontmatter `disable-model-invocation: true` excludes a skill from the model catalog/loader, and `user-invocable: false` excludes it from human-facing commands; both default to allowed, and an invalid spelling or non-boolean value **drops that skill entirely** (fail-closed).

## Registering a skill at runtime

```ts
import { Context } from '@deepseek-ai/cordis'

export const name = 'skill-demo'

export const inject = ['skills']

export function apply(ctx: Context) {

  ctx.skills.register({

    name: 'my-procedure',

    description: 'a fixed procedure for doing something',

    // omitting platform and other metadata

    load: async () => ({

      title: 'My Procedure',

      instructions: [

        '1. Read the config file first',

        '2. Then run the validation command',

        '3. Last, write the result into the session',

      ],

    }),

  })

}
```

Runtime skills use rank `250`: a project provider can override them, and they can override the shipping local provider's custom/user roots; same-layer same-name is first-come-first-served.

## Model invocation via tool-skill

Shipping includes `@deepseek-ai/dsh-tool-skill`: the model-facing skill loading tool, responsible for "on-demand expansion."

- **Catalog lifecycle**: every eligible `agent/pre-step` calls `snapshot()` against the session cwd, rendering sorted `name` + `description`; the first non-empty snapshot adds a durable user-role `<system-reminder>` initial catalog to the downstream `enter` decision, and a changed summary appends a **whole-value replacement**. The catalog is omitted when there's no model-invocable skill or the `skill` tool is restricted/shadowed.

- **The `skill` tool**: parameter `name` (string, required, exact kebab-case name). Success returns `{ name, provider, resourceBase?, content }`, Native-rendered as a `<skill_content>` block; unknown names, invalid names, and `modelInvocable: false` produce distinct error results.

- **Explicit user injection**: a whitespace-delimited `/name` token in a user message that hits a user-invocable skill injects the full `<skill_content>` as a `user`-role instruction at the end of that step. This is the **only** entry point for `disable-model-invocation` skills (which neither the catalog nor the `skill` tool exposes).

## The badge package

`@deepseek-ai/dsh-skill-badge` is an optional embedded provider contributing the `dsh-badge` skill: an official "powered by dsh" Markdown snippet + a packaged PNG (for environments that can't reliably pull remote images). No configuration; the shipping CLI composition mounts it `disabled: true`, and you must explicitly enable it for it to enter the catalog.

## Events and invalidation

- `skills/change` is an **unfiltered invalidation notice**: any provider/runtime registration or deregistration, or a specific provider's internal invalidation, triggers it. It carries no catalog or diff; each consumer re-fetches with its own `snapshot()`.

- A listener that throws/rejects is only logged; **it cannot veto a registration change**.

## Verification

```sh
# which skills the current workspace can list (via a model conversation or a tool)

# see skill-related events in the session log

zstdcat ~/.dsh/sessions/*/*/session*.jsonl.zstd | grep -E "skills" | head
```

## Configuration

| Field | Default | Effect |
| --- | --- | --- |
| collectCacheMaxEntries | 128 | max cached in-memory cwd/provider catalogs |

`skill-filesystem` provider config:

| Field | Default | Effect |
| --- | --- | --- |
| providerName | local | the unique name registered on ctx.skills |
| includeDefaultRoots | true | includes project and user roots in addition to customSkillDirs; false yields an isolated custom-root provider |
| customSkillDirs | [] | extra local skill roots, scanned after project roots and before user roots |
| dshHome | $DSH_HOME or ~/.dsh | the DSH config root, scanning its skills |
| agentsHome | $DSH_AGENTS_HOME or ~/.agents | shared agent config root |
| watch | true | watches host roots, invalidating the provider on catalog-member/frontmatter changes |
| watchUsePolling | false | uses Chokidar polling instead of native events |

## Next steps

- [Writing a tool](../learn/dev/write-tool.md): tools are another kind of model capability alongside skills

- [Built-in tools](../features/tools.md): which tools ship out of the box
