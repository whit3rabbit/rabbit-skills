# Design and verify a Cordis plugin

Use a plugin when DSH needs a runtime capability. Check the installed composition first. If it already provides the needed service or tool, configure that capability or write a skill that explains when to use it.

## Choose where the plugin runs

- **Host tool.** Register a model-callable tool through `ctx.tools` and `defineTool`. Declare `inject = ['tools']` so the plugin mounts when that service is available.
- **Service.** Add a Cordis service when multiple plugins need a shared API. Keep consumer code separate from the provider so the implementation can be replaced.
- **Client extension.** Discover the relevant Client slot or page before writing UI code. Use the native `cordis-plugin-development` skill's decoration template.
- **Configuration bundle.** Ship `dsh.bundle.patch` when the change only enables or configures existing plugin rows. A configuration-only bundle needs a package manifest and patch, with no Host entry.

Use the installed composition's inspection tools to find the exact service and event signatures. Offline, use [extension points](docs/official/pinned/extensions.md), [tool authoring](docs/official/reference/cookbook/adding-a-tool.md), and [bundle packaging](docs/official/develop/basic/publish.md).

## Build a starter

The generator targets DSH `0.2.2-rc.1`. Check the target release before changing its peer dependencies and `engines.dsh`. Use `--js` for an ESM JavaScript entry or the default for TypeScript. Add `--service` only if consumers need a service.

```bash
python3 "$rabbit_dsh_dir/scripts/rabbit_dsh.py" scaffold plugin ./plugins --name dsh-echo --js
node --check ./plugins/dsh-echo/index.js
python3 "$rabbit_dsh_dir/scripts/rabbit_dsh.py" audit ./plugins/dsh-echo
```

For TypeScript, install the generated package's dependencies and run `npm run build` inside that package. The resulting `lib/index.js` is the entry that DSH loads. The starter tool echoes its input, so one call can verify the full registration path before you implement the real behavior.

## Load a bundle

An installed bundle names its package in the patch. A source-only `--patch` overlay instead points at an existing entry file, resolved relative to the overlay. Keep these in separate files.

```yaml
- insert:
    - id: dsh-echo
      name: dsh-echo
```

For a requested change in Creator mode, install the workspace bundle with `plugin_manager` and `action: install_bundle`. Use the returned application status and a targeted inspection query to check registration. For local development, use `dsh plugin --profile NAME add /absolute/path/to/bundle` in a disposable DSH home. Use that same profile for the call and removal.

## Schema lookup example

The [example bundle](../examples/schema-find-refs/package.json) registers `schema_find_refs`. It searches a bundled SQL fixture by identifier and returns bounded file and line references. It renders a short model response separately from the structured return value. Read the [Host entry](../examples/schema-find-refs/index.js) and [bundle patch](../examples/schema-find-refs/cordis.patch.yml) together.

The tool looks up evidence. The [companion skill](../examples/review-sql-migration/SKILL.md) uses evidence to review a migration and can fall back to ordinary workspace search. Use the [verification walkthrough](../examples/verification.md) to exercise both paths.
