import type { IncomingMessage, ServerResponse } from 'node:http'
import type { Context } from '@deepseek-ai/cordis'
import type { Volatile } from '@deepseek-ai/schemastery'
import z from '@deepseek-ai/schemastery'

export const name = 'sidebar-template'
export const inject = ['webServer', 'connection', 'settings', 'loader']

/**
 * Use `@deepseek-ai/schemastery` (not public `schemastery`) so `.volatile()`
 * fields are wrapped in a live `Volatile<T>` reference and updated in place
 * on `loader/volatile-update` without remounting the plugin.
 */
export interface RawConfig {
  enableInspectorTab: boolean
  enableBottomDockToggle: boolean
  refreshIntervalSec: number
  ignoredGlobs: string
}

export type Config = {
  [K in keyof RawConfig]: Volatile<RawConfig[K]>
}

export const Config: z.Schema<RawConfig, Config> = z.object({
  enableInspectorTab: z
    .boolean()
    .default(true)
    .description('Enable the Inspector tab in the right sidebar or bottom dock.')
    .volatile(),
  enableBottomDockToggle: z
    .boolean()
    .default(true)
    .description('Show the quick-toggle button in the session header utility bar.')
    .volatile(),
  refreshIntervalSec: z
    .number()
    .min(1)
    .max(300)
    .default(10)
    .description('Polling interval in seconds while the sidebar tab is visible.')
    .volatile(),
  ignoredGlobs: z
    .string()
    .default('node_modules\n.git')
    .description('Newline-separated ignore patterns for the sidebar inspector.')
    .volatile(),
})

const DEFAULT_PREFS: RawConfig = {
  enableInspectorTab: true,
  enableBottomDockToggle: true,
  refreshIntervalSec: 10,
  ignoredGlobs: 'node_modules\n.git',
}

/**
 * The settings namespace of this plugin is its profile patch-row id
 * (`id: sidebar-template` in cordis.patch.yml). `ctx.settings.describe()`
 * keys live plugin forms by that same id, and `ctx.settings.update(ns, patch)`
 * merges user edits into the profile's user layer.
 */
const SETTINGS_NS = 'sidebar-template'

function readPrefs(ctx: Context, config: Config): RawConfig {
  const descriptor = ctx.settings
    ?.describe()
    .find((row) => row.ns === SETTINGS_NS)
  const raw = (descriptor?.value ?? {}) as Partial<RawConfig>
  return {
    enableInspectorTab:
      typeof raw.enableInspectorTab === 'boolean'
        ? raw.enableInspectorTab
        : (config.enableInspectorTab?.value ?? DEFAULT_PREFS.enableInspectorTab),
    enableBottomDockToggle:
      typeof raw.enableBottomDockToggle === 'boolean'
        ? raw.enableBottomDockToggle
        : (config.enableBottomDockToggle?.value ?? DEFAULT_PREFS.enableBottomDockToggle),
    refreshIntervalSec:
      typeof raw.refreshIntervalSec === 'number'
        ? raw.refreshIntervalSec
        : (config.refreshIntervalSec?.value ?? DEFAULT_PREFS.refreshIntervalSec),
    ignoredGlobs:
      typeof raw.ignoredGlobs === 'string'
        ? raw.ignoredGlobs
        : (config.ignoredGlobs?.value ?? DEFAULT_PREFS.ignoredGlobs),
  }
}

async function writePrefs(ctx: Context, current: RawConfig, patch: Partial<RawConfig>): Promise<RawConfig> {
  const next: RawConfig = { ...current, ...patch }
  if (ctx.settings) {
    await ctx.settings.update(SETTINGS_NS, next as unknown as Record<string, unknown>)
  }
  return next
}

function guardAdmission(ctx: Context, req: IncomingMessage, res: ServerResponse): boolean {
  const rejection = ctx.connection.requestRejection(req)
  if (!rejection) return true
  res.writeHead(rejection.statusCode, { 'content-type': 'application/json; charset=utf-8' })
  res.end(JSON.stringify({ ok: false, error: rejection.message }))
  return false
}

export function apply(ctx: Context, config: Config): void {
  const webServer = ctx.webServer

  // Opt out of the auto-generated plugin settings card when the client module
  // registers its own custom `settings.section` shell page. Remove this block
  // if you prefer DSH to render the `Config` schema automatically in Settings.
  ctx.effect(() => {
    ctx.settings?.configure({ auto: false }, ctx.fiber)
    return () => {}
  })

  // Fenced Host HTTP routes consumed by the client via `hostRouteUrl(...)`.
  // `webServer.register` routes are not method-aware: switch on `req.method`
  // inside the handler, and always pass the host's requestRejection trust
  // barrier first so arbitrary web pages cannot read the endpoint.
  ctx.effect(() => webServer.register({
    kind: 'exact',
    path: '/sidebar-template/api/prefs',
    handler: async (req: IncomingMessage, res: ServerResponse) => {
      if (!guardAdmission(ctx, req, res)) return
      const method = (req.method || 'GET').toUpperCase()
      if (method === 'GET') {
        res.writeHead(200, { 'content-type': 'application/json; charset=utf-8' })
        res.end(JSON.stringify({ ok: true, prefs: readPrefs(ctx, config) }))
        return
      }
      if (method !== 'POST') {
        res.writeHead(405, { 'content-type': 'application/json; charset=utf-8' })
        res.end(JSON.stringify({ ok: false, error: 'method not allowed' }))
        return
      }
      const chunks: Buffer[] = []
      req.on('data', (chunk: Buffer) => chunks.push(chunk))
      await new Promise<void>((resolve) => req.on('end', resolve))
      try {
        const patch = JSON.parse(Buffer.concat(chunks).toString('utf8') || '{}') as Partial<RawConfig>
        const prefs = await writePrefs(ctx, readPrefs(ctx, config), patch)
        res.writeHead(200, { 'content-type': 'application/json; charset=utf-8' })
        res.end(JSON.stringify({ ok: true, prefs }))
      } catch (err) {
        res.writeHead(400, { 'content-type': 'application/json; charset=utf-8' })
        res.end(JSON.stringify({ ok: false, error: (err as Error).message }))
      }
    },
  }))
}
