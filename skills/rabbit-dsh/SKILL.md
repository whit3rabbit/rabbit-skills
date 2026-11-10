---
name: rabbit-dsh
version: 1.1.0
description: Scaffold, configure, audit, and look up docs for DSH skills, Cordis plugins, and MCP. Use for DSH development.
---

# Develop for DeepSeek Harness

Choose the smallest artifact that meets the request. For a design review, identify the target runtime, the extension point, and how to verify it. Keep the profile read-only during review.

| Request | Start here |
| --- | --- |
| Add a repeatable procedure, review rubric, or domain instructions | [Skill authoring](references/quick-reference.md#skills). Start with the [SQL migration review example](examples/review-sql-migration/SKILL.md). |
| Add a runtime tool or Cordis service | [Cordis plugin authoring](references/plugin-cordis.md). Start with the [schema lookup example](references/plugin-cordis.md#schema-lookup-example) for a Host tool. |
| Add or customize a sidebar tab, file viewer, settings page, or Web UI component | [UI, sidebar, and settings](references/ui-sidebar.md). Start with the [sidebar UI template](examples/sidebar/README.md). |
| Add a floating overlay widget (badge, ticker, or mini panel) on the chat page | [Floating widget template](examples/widget/README.md). |
| Add a startup screen (full-page splash or boot animation) that plays on load and releases the page | [Startup screen template](examples/startup-screen/README.md). |
| Add a context dashboard (token composition, trend, events, file activity, agent fleet) as a conversation tab, slash command, or sidebar panel | [Context dashboard template](examples/context-dashboard/README.md). |
| Enable, configure, or move an existing capability | Use `editing-cordis-compositions` when available. For an offline explanation, read [composition and extension points](references/docs/official/pinned/extensions.md). |
| Connect an MCP server | [MCP integration](references/mcp-integration.md). |
| Orchestrate agents or verify a goal across rounds | [Workflows and Ralph](references/workflow-ralph.md). |
| Initialize a workspace or inspect its settings | [Configuration commands](references/quick-reference.md#configuration-commands), [environment variables](references/ENV.md), and [telemetry](references/TELEMETRY.md). |
| Re-sync or update the offline docs corpus | Re-fetch official and community documentation with [scrape_docs.py](scripts/scrape_docs.py). |

## Choose the API before writing code

In DSH Creator mode, use the shipped `cordis-plugin-development` skill for plugin work and `agent-experience` for model-facing design. Start with `cordis_inspect_list`, then query the relevant service, tool, event, config schema, or Client slot. Use the resolved package's docs and types for details. Outside Creator mode, match the installed DSH version against the [offline references](references/official-reference-guide.md).

For scripts and examples, resolve paths from this loaded skill's resource directory. In DSH, the loader reports that directory in `<skill_resources>`. Use its absolute path as `rabbit_dsh_dir` in shell examples. In a source checkout, that directory is `skills/rabbit-dsh` under the repository root.

## Scaffold and verify

1. Choose a new destination. For a project skill, scaffold into `.dsh/skills` or `.agents/skills`.
2. Run the relevant scaffold command. Replace starter content with the task's trigger, behavior, and success criteria.
3. Audit the artifact. `audit` covers skills, plugins, workflows, and patches. For patches, presets, workflow definitions, settings, credentials, and session logs, run the deep linter instead (check catalog: [artifact checks](references/artifact-checks.md)). Then verify discovery for a skill, or build, load, call, and unload a plugin in a disposable profile.
4. Report which checks ran. Include the actual catalog entry or tool result when a DSH runtime is available.

```bash
python3 "$rabbit_dsh_dir/scripts/rabbit_dsh.py" scaffold skill .dsh/skills \
  --name code-review --description 'Review a code diff for regressions and missing tests.'
python3 "$rabbit_dsh_dir/scripts/rabbit_dsh.py" audit .dsh/skills/code-review
# Verdict: PASS means the static structure check passed.

# Deep artifact lint (DA-01..DA-21) for patches, presets, workflows, settings, credentials, session logs:
python3 "$rabbit_dsh_dir/scripts/audit_dsh_artifacts.py" ./cordis.patch.yml --strict
```

See [example verification](examples/verification.md) for expected discovery, invocation, and failure cases.

## Build sidebar, settings, and Web UI components

When adding a sidebar tab, custom file viewer, session header button, or settings page, start from the modular [sidebar UI template](examples/sidebar/README.md) and the [UI, sidebar, and settings reference](references/ui-sidebar.md):

- **Place the surface**: Pick from the 4 recipes in [examples/sidebar/src/client/index.tsx](examples/sidebar/src/client/index.tsx): `ctx.betterSidebar` (`registerTab`, `registerFileViewer`, declarative `pluginToggles`), native DSH right sidebar (`ctx.sidebarRightTabs` + `sidebar.right.pane.tab`), session header utility strip (`conversation.session.header.utilities`), or a dedicated Settings shell page (`settings.section` + `settings.section.icon` paired with Host [examples/sidebar/src/index.ts](examples/sidebar/src/index.ts)).
- **Compose UI components**: Reuse `@deepseek-ai/dsh-client-ui-primitives` (`Button`, `Input`, `Menu`, `Modal`, `SegmentedControl`, `Tooltip`, `StateDot`) together with the extracted sidebar kit in [examples/sidebar/src/client/ui-kit.tsx](examples/sidebar/src/client/ui-kit.tsx) (`SectionHeader`, `IconButton`, `Chip`, `Notice`, `StatusBadge`, `Switch`, `ConfirmDialog`, `SelectMenu`, `FeatureCard`) and token-pure styles in [examples/sidebar/src/client/ui-kit.module.css](examples/sidebar/src/client/ui-kit.module.css).
- **Float a widget on the chat page instead**: for a badge, ticker, or mini panel that lives directly on the page (not docked in a sidebar), start from the [floating widget template](examples/widget/README.md). It serves a vanilla-JS script over Host routes and injects it into every rendered index.html, with no React client bundle and no client module graph changes.
- **Play a startup screen instead**: for a full-page splash that covers the app before it mounts and releases it when done (boot animation, brand flash, access sequence), start from the [startup screen template](examples/startup-screen/README.md). It shows the pre-mount boot layer with a 9-second watchdog, a screen pack with three swappable looks, config persistence over HTTP, and a handwritten client bundle that adds the settings page.
- **Build a context dashboard instead**: for token composition, trend, events, file activity, and agent fleet cards in a conversation tab, a `/context` modal, or a right-sidebar panel, start from the [context dashboard template](examples/context-dashboard/README.md). It registers the five dsh-context surfaces over a demo data feed, with the dataset shape documented as the contract for wiring real session data.

## Find an offline reference

Start with [the reference index](references/official-reference-guide.md). Search for the API or behavior by name, then use the path and heading from the result to read the relevant section. Community pages are useful for context. Use the official result for an API contract.

If DeepSeek Harness is new to you, `docs map` prints the whole concept-to-document map in one call, and `docs map <topic>` filters it. To re-fetch or update the offline documentation mirror, run [scripts/scrape_docs.py](scripts/scrape_docs.py).

```bash
python3 "$rabbit_dsh_dir/scripts/rabbit_dsh.py" docs map            # cold-start orientation
python3 "$rabbit_dsh_dir/scripts/rabbit_dsh.py" docs search 'skill discovery' --source official --limit 3
python3 "$rabbit_dsh_dir/scripts/rabbit_dsh.py" docs read official/reference/subsystems/skills.md \
  --section 'Local discovery priority'
```
