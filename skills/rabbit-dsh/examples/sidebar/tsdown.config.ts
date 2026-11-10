/**
 * Standalone build for the sidebar template. Emits the two halves a DSH
 * `dsh.client` package publishes:
 *
 * - `lib/index.js`  — the Node (Host) half. `@deepseek-ai/*` specifiers stay
 *   imports: the DSH node loader resolves them from its own module table.
 * - `lib/client.js` — the browser half as a closure factory. The bundle ends
 *   with `window.__ModuleLoader__.load({ id, factory: (require) => {...} })`,
 *   so the client module system can register and later materialize it; every
 *   specifier the loader's baseline module table provides (react, cordis,
 *   dsh-client-ui-slots, dsh-client-ui-primitives, ...) stays an import, and
 *   anything else inlines. A `*.module.css` import compiles (lightningcss,
 *   class map pattern `[hash]_[local]`) into a class-map export plus a style
 *   tag injected at materialization.
 */
import { readFile } from 'node:fs/promises'
import { basename, dirname, resolve } from 'node:path'
import { transform } from 'lightningcss'
import { defineConfig, type TsdownPlugin } from 'tsdown'

const ID = '@rabbit-dsh/sidebar-template'

/**
 * The loader's baseline module table (packages/client/web/src/platform.ts in
 * the DSH repository): specifiers every client bundle may import without
 * declaring `dsh.client.external`.
 */
const BASELINE_MODULES = new Set([
  'react',
  'react/jsx-runtime',
  'react-dom',
  'react-dom/client',
  '@deepseek-ai/cordis',
  'zod',
  '@tanstack/react-virtual',
  '@deepseek-ai/dsh-client-store',
  '@deepseek-ai/dsh-client-ui-slots',
  '@deepseek-ai/dsh-client-ui-primitives',
  '@deepseek-ai/dsh-client-ui-dockkit',
])

const isExternal = (specifier: string): boolean =>
  BASELINE_MODULES.has(specifier) || specifier.startsWith('node:')

/** Compile `*.module.css` to a class-map export plus a materialization-time style tag. */
const cssModules: TsdownPlugin = {
  name: 'sidebar-template-css-modules',
  resolveId(source: string, importer: string | undefined) {
    if (!source.endsWith('.module.css') || importer === undefined) return null
    // The virtual id must not end in `.css`: tsdown's own CSS guard would claim it.
    return '\0sidebar-template-css:' + resolve(dirname(importer), source) + '.mjs'
  },
  async load(virtualId: string) {
    if (!virtualId.startsWith('\0sidebar-template-css:')) return null
    const file = virtualId.slice('\0sidebar-template-css:'.length, -'.mjs'.length)
    this.addWatchFile(file)
    const source = await readFile(file)
    const { code, exports: cssExports } = transform({
      filename: file,
      code: source,
      cssModules: { pattern: '[hash]_[local]' },
      minify: true,
    })
    const classMap: Record<string, string> = {}
    for (const [local, exp] of Object.entries(cssExports ?? {})) classMap[local] = exp.name
    const tagId = `${ID}/${basename(file)}`
    return [
      `const css = ${JSON.stringify(code.toString())};`,
      `const tagId = ${JSON.stringify(tagId)};`,
      `if (typeof document !== 'undefined' && document.querySelector('style[data-plugin-css=' + JSON.stringify(tagId) + ']') === null) {`,
      `  const tag = document.createElement('style');`,
      `  tag.dataset.plugin = ${JSON.stringify(ID)};`,
      `  tag.dataset.pluginCss = tagId;`,
      `  tag.textContent = css;`,
      `  document.head.appendChild(tag);`,
      `}`,
      `export default ${JSON.stringify(classMap)};`,
    ].join('\n')
  },
}

export default defineConfig([
  {
    name: ID,
    entry: { index: 'src/index.ts' },
    outDir: 'lib',
    format: 'esm',
    platform: 'node',
    target: 'es2024',
    dts: false,
    clean: false,
    outExtensions: () => ({ js: '.js' }),
    deps: {
      neverBundle: (specifier: string) => specifier.startsWith('@deepseek-ai/'),
      alwaysBundle: (specifier: string) => !isExternal(specifier),
    },
  },
  {
    name: `${ID}/client`,
    entry: { client: 'src/client/index.tsx' },
    outDir: 'lib',
    format: 'cjs',
    platform: 'browser',
    target: 'es2024',
    dts: false,
    sourcemap: true,
    clean: false,
    deps: {
      neverBundle: isExternal,
      alwaysBundle: (specifier: string) => !isExternal(specifier),
    },
    plugins: [cssModules],
    outputOptions: {
      entryFileNames: 'client.js',
      banner: () => `window.__ModuleLoader__.load({ id: ${JSON.stringify(ID)}, factory: (require) => {`,
      intro: 'var module = { exports: {} }; var exports = module.exports;',
      footer: 'return module.exports; } });',
    },
  },
])
