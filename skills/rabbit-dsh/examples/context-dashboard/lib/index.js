/* ============================================================================
 * context-dashboard-template — Host half
 * ----------------------------------------------------------------------------
 * Serves the dashboard's data and config over fenced HTTP routes:
 *   GET  /context-dashboard/data.json   the dataset (demo until you wire real
 *                                       sources — see "Wire real data" below)
 *   GET/POST /context-dashboard/config  dashboard config (surface switches)
 *
 * This file is the template for the Host half of any client-bundle plugin:
 * copy it, rename NS / ROUTE_BASE / CONFIG_FILE / DEFAULTS, and you are done.
 * The plugin architecture it was distilled from is dsh-context
 * (https://github.com/bowenliang123/dsh-context) — its Host half computes the
 * real dataset from session projections; this skeleton serves a demo fixture
 * with the same shape instead.
 * ========================================================================== */

import fs from 'node:fs'
import os from 'node:os'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { demoDataset } from './demo-data.js'

const PACKAGE_ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
const DSH_HOME = process.env.DSH_HOME || path.join(os.homedir(), '.dsh')
const CONFIG_FILE = path.join(DSH_HOME, 'dsh-context-dashboard-template.json')

/** Single rename point for the whole plugin: route prefix, storage keys, and
    window globals all derive from this string or the names below. */
const NS = 'context-dashboard-template'
const ROUTE_BASE = '/' + NS

/** Which surfaces the client may mount. The client fetches this on mount and
    degrades any unknown key to its fallback. */
const DEFAULTS = {
  enableTab: true,           // the "Context" conversation tab (the dashboard)
  enableFleetTab: true,      // the "Fleet" conversation tab (agent family)
  enableSidebarPanel: false, // the right-sidebar Context panel
  enableCommand: true,       // the /context slash command + centered modal
  demoMode: true             // serve the demo dataset even if a real one exists
}

const BOOL_KEYS = Object.keys(DEFAULTS)

/** Keep only known keys and coerce types, so a bad POST cannot corrupt the
    config file or flip the client into a broken surface set. */
function normalize(input) {
  const out = { ...DEFAULTS }
  const src = input && typeof input === 'object' ? input : {}
  for (const key of BOOL_KEYS) {
    if (!(key in src) || src[key] === undefined || src[key] === null) continue
    out[key] = src[key] === true || src[key] === 'true' || src[key] === 1 || src[key] === '1'
  }
  return out
}

function readConfig() {
  try {
    return normalize(JSON.parse(fs.readFileSync(CONFIG_FILE, 'utf8')))
  } catch (err) {
    return { ...DEFAULTS }
  }
}

function writeConfig(next) {
  const cfg = normalize(next)
  fs.mkdirSync(path.dirname(CONFIG_FILE), { recursive: true })
  const tmp = CONFIG_FILE + '.tmp'
  fs.writeFileSync(tmp, JSON.stringify(cfg, null, 2), 'utf8')
  fs.renameSync(tmp, CONFIG_FILE)
  return cfg
}

/* ----------------------------------------------------------------------------
 * Wire real data
 * ----------------------------------------------------------------------------
 * The demo dataset stands in for the real computation. dsh-context builds its
 * figures from, in decreasing fidelity:
 *   1. dsh's official token-meter projections (`contextPressure` /
 *      `contextBreakdown`) — the same numbers the chat composer's context ring
 *      shows, read through the `sessionProjections` Cordis service.
 *   2. The V4 session log under $DSH_HOME (turns, tool calls, file ops,
 *      command runs, agent events), folded per step.
 *   3. models.dev list prices for cost estimates (DeepSeek's listed rates are
 *      the off-peak tier; peak windows bill at 2x).
 * A skeleton route can start by reading the session log for the active
 * session and filling this same object shape; keep `source` honest
 * ('demo' | 'session-log' | 'projections') so the UI can label the banner.
 * -------------------------------------------------------------------------- */

function datasetFor() {
  const config = readConfig()
  if (!config.demoMode) {
    // TODO: return the real dataset here once a source is wired.
    // Until then, demoMode:false serves the same fixture with an honest note.
    return { ...demoDataset, notice: 'demoMode is off but no real source is wired yet — still serving the demo fixture.' }
  }
  return demoDataset
}

export const name = NS
const inject = ['webServer']

function apply(ctx) {
  const webServer = ctx.webServer
  const disposers = []

  /** Trust barrier: every custom route must pass the host's requestRejection
      check first, otherwise any web page could read the data endpoint. */
  function rejected(req, res) {
    try {
      const conn = typeof ctx.get === 'function' ? ctx.get('connection') : undefined
      if (!conn || typeof conn.requestRejection !== 'function') return false
      const code = conn.requestRejection(req)
      if (code === undefined || code === null || code === false) return false
      res.statusCode = typeof code === 'number' ? code : 403
      res.end()
      return true
    } catch (err) {
      return false
    }
  }

  function registerRoute(route) {
    const inner = route.handler
    return webServer.register(Object.assign({}, route, {
      handler: async (req, res) => {
        if (rejected(req, res)) return
        return inner(req, res)
      }
    }))
  }

  function sendJson(res, code, payload) {
    const body = Buffer.from(JSON.stringify(payload), 'utf8')
    res.writeHead(code, {
      'Content-Type': 'application/json; charset=utf-8',
      'Cache-Control': 'no-store',
      'Content-Length': String(body.length)
    })
    res.end(body)
  }

  function readBody(req, limit = 64 * 1024) {
    return new Promise((resolve) => {
      let size = 0
      const chunks = []
      req.on('data', (c) => {
        size += c.length
        if (size > limit) {
          req.destroy()
          resolve('')
          return
        }
        chunks.push(c)
      })
      req.on('end', () => resolve(Buffer.concat(chunks).toString('utf8')))
      req.on('error', () => resolve(''))
    })
  }

  disposers.push(registerRoute({
    kind: 'exact',
    path: ROUTE_BASE + '/data.json',
    handler: (req, res) => {
      const data = datasetFor()
      sendJson(res, 200, { ok: true, data, defaults: DEFAULTS })
    }
  }))

  disposers.push(registerRoute({
    kind: 'exact',
    path: ROUTE_BASE + '/config',
    handler: async (req, res) => {
      const method = (req.method || 'GET').toUpperCase()
      if (method === 'GET') {
        sendJson(res, 200, { ok: true, config: readConfig(), defaults: DEFAULTS, file: CONFIG_FILE })
        return
      }
      if (method !== 'POST') {
        sendJson(res, 405, { ok: false, error: 'method not allowed' })
        return
      }
      const text = await readBody(req)
      let payload = {}
      try {
        payload = text ? JSON.parse(text) : {}
      } catch (err) {
        sendJson(res, 400, { ok: false, error: 'invalid json' })
        return
      }
      if (payload && payload.action === 'reset') {
        sendJson(res, 200, { ok: true, config: writeConfig(DEFAULTS), defaults: DEFAULTS })
        return
      }
      const current = readConfig()
      const patch = payload && typeof payload.patch === 'object' && payload.patch ? payload.patch : payload
      sendJson(res, 200, { ok: true, config: writeConfig({ ...current, ...patch }), defaults: DEFAULTS })
    }
  }))

  ctx.effect(() => () => {
    for (const dispose of disposers) {
      try { dispose() } catch (err) { /* unload must never throw */ }
    }
  })
}

/* Export shape matches DSH internal plugins: named `name` / `inject` / `apply`
   only. Do not add a default export (the loader unwraps `exports.default ??
   exports`, so a default export hides the named ones), and do not export a
   `Config` object (Cordis expects a Schemastery schema under that name). */
export { apply, inject }
