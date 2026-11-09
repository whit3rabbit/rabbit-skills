---
name: rabbit-dsh
version: 1.0.0
description: Scaffold, configure, audit, and look up docs for DSH skills, Cordis plugins, and MCP. Use for DSH development.
---

# Develop for DeepSeek Harness

Choose the smallest artifact that meets the request. For a design review, identify the target runtime, the extension point, and how to verify it. Keep the profile read-only during review.

| Request | Start here |
| --- | --- |
| Add a repeatable procedure, review rubric, or domain instructions | [Skill authoring](references/quick-reference.md#skills). Start with the [SQL migration review example](examples/review-sql-migration/SKILL.md). |
| Add a runtime tool, service, or Web UI extension | [Cordis plugin authoring](references/plugin-cordis.md). Start with the [schema lookup example](references/plugin-cordis.md#schema-lookup-example) for a Host tool. |
| Enable, configure, or move an existing capability | Use `editing-cordis-compositions` when available. For an offline explanation, read [composition and extension points](references/docs/official/pinned/extensions.md). |
| Connect an MCP server | [MCP integration](references/mcp-integration.md). |
| Orchestrate agents or verify a goal across rounds | [Workflows and Ralph](references/workflow-ralph.md). |
| Initialize a workspace or inspect its settings | [Configuration commands](references/quick-reference.md#configuration-commands), [environment variables](references/ENV.md), and [telemetry](references/TELEMETRY.md). |

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

## Find an offline reference

Start with [the reference index](references/official-reference-guide.md). Search for the API or behavior by name, then use the path and heading from the result to read the relevant section. Community pages are useful for context. Use the official result for an API contract. If DeepSeek Harness is new to you, `docs map` prints the whole concept-to-document map in one call, and `docs map <topic>` filters it.

```bash
python3 "$rabbit_dsh_dir/scripts/rabbit_dsh.py" docs map            # cold-start orientation
python3 "$rabbit_dsh_dir/scripts/rabbit_dsh.py" docs search 'skill discovery' --source official --limit 3
python3 "$rabbit_dsh_dir/scripts/rabbit_dsh.py" docs read official/reference/subsystems/skills.md \
  --section 'Local discovery priority'
```
