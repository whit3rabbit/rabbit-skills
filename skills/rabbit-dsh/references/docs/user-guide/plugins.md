# Plugins

**Short version**: plugins are the core of the DSH ecosystem: search, memory, vision, terminal, notifications, fun features... almost every capability is a plugin. Installing, removing, and writing all start with "knowing the plugin forms".

## Contents

- [1. Plugin types](#1-plugin-types)
- [2. Installing a bundle plugin](#2-installing-a-bundle-plugin)
- [3. Repository plugins](#3-repository-plugins)
- [4. Plugin panel](#4-plugin-panel)
- [5. Plugin categories overview](#5-plugin-categories-overview)
- [6. Writing your own plugin](#6-writing-your-own-plugin)
- [7. Uninstall and write-back](#7-uninstall-and-write-back)
- [8. Troubleshooting common errors](#8-troubleshooting-common-errors)
- [Next steps](#next-steps)

---

## 1. Plugin types

| Type | Install method | When it takes effect |
| --- | --- | --- |
| Bundle plugin | dsh plugin --profile web add "github:..." | Restart dsh web after installing |
| Repository plugin (.dsh-plugin) | Plugin panel → repository source | Takes effect immediately on change |

**Kernel vs community**: `@deepseek-ai/*` are DSH kernel packages (ship with the distribution); `@dsh-external/*` are **third-party community** plugins, installed on demand and not part of the kernel. The install examples below are mostly community plugins.

See [Plugin Anatomy](../learn/core/plugin-anatomy.md) for the difference between the forms and manifests.

## 2. Installing a bundle plugin

```sh
# One-line git source (build artifacts are already committed, about 15 seconds)

dsh plugin --profile web add "github:dsh-external/dsh-session-search#main"

# Local directory (development)

dsh plugin --profile web add link:/path/to/plugin
```

`dsh plugin --profile web add <source>` forwards the argument **verbatim to pnpm** (`_plugin.ts:128_`), accepting only sources pnpm recognizes (pure git sources, `link:`, etc.). The `&path:` subpath is a source format of the repository plugin mechanism itself; to install a monorepo sub-package, use the **repository source in the plugin panel** (below), not `dsh plugin add`.

After installing, inspect the composition tree:

```sh
dsh web --dump-config | grep <plugin name>
```

After a bundle install, **restart `dsh web`** for it to take effect (repository plugins don't need this).

### Dependency resolution: dual anchors + flat closure

Once a bundle is installed into a profile, dependencies resolve in the following order, letting out-of-tree plugins reuse the same cordis instance:

- **Bundle-name dual anchors**: first the bundle's own install directory, then the profile directory

- **Flat-closure fallback**: `$DSH_HOME/profiles/node_modules`

- The framework is vendored and published only as `@deepseek-ai/*` scoped packages; plugins should `import ... from '@deepseek-ai/cordis'`. Using the bare names `cordis`/`schemastery` fails to resolve; the workaround is to install the missing bare-name dependencies in the plugin's own directory (see [Plugin Anatomy](../learn/core/plugin-anatomy.md))

## 3. Repository plugins

The repository mechanism is implemented by the third-party `@dsh-external/plugin-console` + `$DSH_HOME/cordis.patch.yml` (`repository-plugins.repositories`) at the home-directory level — **not built into the DSH kernel**. Add `github:owner/repo#ref` in the plugin panel:

- Adding a row = installing

- Updating = pinning to the remote's latest commit

- Removing a row = uninstalling

- **Changes take effect immediately, no restart needed**

**Panel flow** (installing a monorepo sub-package as an example):

- Settings → Plugins → repository source → Add

- Write the source as `github:owner/repo#ref&path:/packages/<sub-package>` (`&path:` is the repository mechanism's own subpath format)

- The panel parses each row into a mounted `.dsh-plugin` directory; changing/removing a row takes effect immediately

The `.dsh-plugin` directory format belongs to the external plugin-registry mechanism, not the DSH kernel (see [Plugin Anatomy](../learn/core/plugin-anatomy.md)).

## 4. Plugin panel

Settings → **Plugins**:

- Browse loaded plugins (user / built-in categories)

- Enable / disable / uninstall

- Check for updates

- Manage repository plugin sources

## 5. Plugin categories overview

| Category | Examples |
| --- | --- |
| Context & retrieval | dsh-session-search, dsh-memory-evolve |
| Editing & input | dsh-message-edit, dsh-prompt-studio |
| Interface & experience | dsh-web-panel, dsh-live-stats |
| Model & reasoning | dsh-vision, dsh-advisor, dsh-llm-fallbacks |
| Notifications & channels | telegram, qqbot |

See [Plugin Ecosystem](../ecosystem.md) for the full curated list.

## 6. Writing your own plugin

- The **make-dsh-plugin** skill (the official bootstrap from plugin-registry)

- Manifest: the `dsh` field of package.json (`dsh.bundle.patch` for bundle form / `dsh.client` for the browser half / `dsh.profile.bundles` for profile dependencies)

- Mounting: `dsh plugin --profile web add` or the patch layer

- Full development is covered in [Principles Course · Plugin Development](../learn/dev/hello-plugin.md)

## 7. Uninstall and write-back

- Uninstall a bundle: `dsh plugin --profile web remove <package>` only deletes the dependency, and does **not write back the manually-mounted lines in the patch layer** — the corresponding `insert` line in `cordis.patch.yml` must be removed by hand (see [Configuration](../user-guide/configuration.md))

- **reconcile runs against installed state** (not a dependency diff): so `update` can activate a package whose `dsh.bundle` declaration only appears in the new version

- Plugins are third-party, so look at their source and permissions before installing (especially ones with outbound network capability: telegram, zotero, etc.)

## 8. Troubleshooting common errors

| Symptom / error | Cause | Fix |
| --- | --- | --- |
| Bare names cordis/schemastery fail to resolve | The mount closure only contains @deepseek-ai/* packages | Install the missing bare-name deps in the plugin's own directory |
| A patch change doesn't take effect | name mismatch → silently skipped; or config is a full-line replacement, not a deep merge | Align the id/name; check with --dump-config |
| An installed bundle doesn't take effect | Bundles need a restart | Restart dsh web |
| Still errors after uninstalling | remove doesn't write back the patch layer | Manually delete the matching insert line in cordis.patch.yml |
| Panel can't see a plugin | Missing client package / bundle not fully installed | Compare with dsh web --dump-config; check the browser console |

## Next steps

- [Plugin Anatomy](../learn/core/plugin-anatomy.md): forms and patch semantics

- [Configuration](../user-guide/configuration.md): how to configure the patch layer

- [Write Your First Plugin](../learn/dev/hello-plugin.md)
