# DeepSeek Harness quick reference

## Skills

The filesystem provider discovers directory bundles at `<root>/<name>/SKILL.md` and flat files at `<root>/<name>.md`. It reads YAML frontmatter. `skill.json` has no role in DSH discovery.

| Rank | Root |
| --- | --- |
| 100 | `<projectRoot>/.dsh/skills` |
| 200 | `<projectRoot>/.agents/skills` |
| 300 | `Config.customSkillDirs` |
| 400 | `<dshHome>/skills` |
| 500 | `<agentsHome>/skills` |
| 600 | Configured bundled skill directory |

The nearest Git root determines the project root. Without Git, discovery uses the session's current working directory. Within a provider the lower rank wins for duplicate names.

```yaml
---
name: migration-review
description: "Review a migration: check data compatibility and index coverage."
---
```

- The model catalog shows the skill name and description. Put the trigger in `description`. `whenToUse` and `metadata` are optional.
- Omit invocation flags to allow both the model loader and direct user invocation. Set `disable-model-invocation: true` for a user-only skill, or `user-invocable: false` to keep it out of slash commands.
- A direct `/name` invocation injects the skill into the turn. Follow those instructions and skip a second load.
- Keep the entry short. Put engine-specific rules and longer examples in linked resources. Test that each resource opens from the loaded skill's base directory.

[Upstream filesystem provider](https://github.com/deepseek-ai/deepseek-harness/blob/fcc0ad462172522aaf5c93a7b2e01f6b9f0b0159/packages/skill/skill-filesystem/README.md) · [Upstream skill loader](https://github.com/deepseek-ai/deepseek-harness/blob/fcc0ad462172522aaf5c93a7b2e01f6b9f0b0159/packages/skill/tool-skill/README.md)

## Configuration commands

```bash
python3 "$rabbit_dsh_dir/scripts/rabbit_dsh.py" config init ./scratch-dsh-home
python3 "$rabbit_dsh_dir/scripts/rabbit_dsh.py" config telemetry status --root ./scratch-dsh-home
python3 "$rabbit_dsh_dir/scripts/rabbit_dsh.py" --self-test
```

Use the [environment variables guide](ENV.md) and [telemetry guide](TELEMETRY.md) for privacy settings. Use [MCP integration](mcp-integration.md) for server wiring and [Workflows and Ralph](workflow-ralph.md) for orchestrating agents.

## Known version skew

The bundled docs mix two generations (community pages track baseline `0.1.5-alpha.1`, official pages track current master). When sources disagree, trust the official page for API contracts and treat these known conflicts as version skew rather than errors:

- **Session format version**: community docs pin `SESSION_FORMAT_VERSION = 3`. Official docs mention V4, which rejects the retired `{ kind: 'plugin' }` wrapper. Validation tooling should accept v3 and v4.
- **Skill discovery ranks**: tables listing five roots (ranks 100-500) predate the rank 600 bundled directory shown above.
- **Log filenames**: official naming is `session.vN.jsonl[.zstd]` from v1 onward (v0 used `session.jsonl`). Community snippets glob `session*.jsonl.zstd`.
- **npm vs source**: npm `latest` lags the documented source (`guides/deepseek-harness-status.md` in the offline docs is the arbiter). Accept both generations of examples.

[Artifact validation catalog](artifact-checks.md) documents how `scripts/audit_dsh_artifacts.py` handles each skew case.
