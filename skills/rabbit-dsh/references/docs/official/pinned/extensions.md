# Extension inspection and placement

Offline notes for DSH `0.2.2-rc.1`. Match the installed composition before choosing an extension point.

## Inspect the running composition

Start with `cordis_inspect_list` in Creator mode. Use `cordis_inspect_query` for the one provider and method needed to answer the next design question. Inspect `Tool` for agent-visible tools, `Service` and `Event` for Host contracts, and `Slots` for Client placement. Client queries need a connected page.

Query `Config.listConfigs` by package name, then by entry ID. Use the returned `packageDir` to locate the installed package's README and type declarations. Resolve the package this way because shipped packages and profile-installed bundles live in different places.

## Choose where to make the change

- Use a Host plugin for model tools and services. Register effects from the contributing context so the runtime can remove them on unload.
- Use a Client module for browser slots and pages. Test the installed module in the connected Web UI.
- Use a bundle patch for configuration changes to a shipped capability. An override replaces the row's entire config, so carry over the fields the row still needs.
- Use the native `cordis-plugin-development` procedure and Plugin Manager when installing a persistent change from Creator mode.

[Upstream extensions subsystem](https://github.com/deepseek-ai/deepseek-harness/blob/fcc0ad462172522aaf5c93a7b2e01f6b9f0b0159/docs/subsystems/extensions.md) · [Upstream authoring procedure](https://github.com/deepseek-ai/deepseek-harness/blob/fcc0ad462172522aaf5c93a7b2e01f6b9f0b0159/packages/preset/agent-preset/skills/cordis-plugin-development/SKILL.md)
