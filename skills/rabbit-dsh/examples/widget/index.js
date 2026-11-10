// DSH floating overlay widget template — Host entry (bundle plugin, no build step).
//
// Pattern: this plugin does not ship a React client bundle. It serves a vanilla-JS
// widget over `webServer` routes and injects a `<script defer>` tag into every
// rendered index.html, so the widget appears on the chat page without touching
// the DSH client module graph. Replace `collectData()` to surface real data.
//
// Exports follow the named-export bundle convention: `name` (must match the
// package `name` row in cordis.patch.yml) and `apply(ctx)`.

import fs from 'node:fs'
import os from 'node:os'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

export const name = 'widget-template'

const PACKAGE_ROOT = path.dirname(fileURLToPath(import.meta.url))
const ROUTE_PREFIX = '/widget-template'
// User settings live under $DSH_HOME, not the package directory: node_modules
// may be read-only or wiped on update, and $DSH_HOME survives both.
const DSH_HOME = process.env.DSH_HOME || path.join(os.homedir(), '.dsh')
const CONFIG_FILE = path.join(DSH_HOME, 'widget-template-config.json')
const SCRIPT_TAG = `<script defer src="${ROUTE_PREFIX}/widget.js"></script>`

const DEFAULT_CONFIG = { pollSeconds: 60 }

// Desktop (Electron) injection row. The desktop shell serves a static index.html
// that never passes through `tapIndex`; its only channel is the structured
// `webserver/index-inject` table. Two hard rules learned in production:
//   1. The shell collects that table once at host startup, so the row must be
//      registered before apply() waits on any service — hence no top-level
//      `export const inject = [...]` here.
//   2. Use an inline `script` row, not `script-src`: the desktop interpreter
//      rejects the whole boot when a `script-src` row fails to load, while an
//      inline row we create ourselves can swallow its own onerror.
const DESKTOP_WIDGET_ROW_TEXT =
  '(function(){try{var d=document.body||document.head||document.documentElement;if(!d)return;' +
  `var s=document.createElement("script");s.src="${ROUTE_PREFIX}/widget.js";` +
  's.onerror=function(){};d.appendChild(s)}catch(e){}})()'

// ===========================================================================
// CUSTOMIZE HERE — the data your widget shows. Called once per poll and per
// manual refresh. Keep it cheap and never block for long: the widget renders
// whatever this returns, verbatim, through textContent.
// ===========================================================================
function collectData() {
  return {
    label: 'Widget',
    value: `up ${Math.round(process.uptime())}s`,
    detail: 'Template placeholder. Replace collectData() in index.js with your own data source.',
    updatedAt: new Date().toISOString(),
  }
}

function readConfig() {
  try {
    const parsed = JSON.parse(fs.readFileSync(CONFIG_FILE, 'utf8'))
    return {
      pollSeconds:
        typeof parsed.pollSeconds === 'number' && parsed.pollSeconds >= 5 && parsed.pollSeconds <= 3600
          ? parsed.pollSeconds
          : DEFAULT_CONFIG.pollSeconds,
    }
  } catch {
    return { ...DEFAULT_CONFIG }
  }
}

function writeConfig(patch) {
  const next = { ...readConfig(), ...patch }
  fs.mkdirSync(DSH_HOME, { recursive: true })
  fs.writeFileSync(CONFIG_FILE, `${JSON.stringify(next, null, 2)}\n`)
  return next
}

// Route handlers must always answer: an async handler that throws returns an
// empty 400 from the dispatcher. Wrap everything and send JSON on every path.
function sendJson(res, code, payload) {
  res.writeHead(code, { 'Content-Type': 'application/json; charset=utf-8', 'Cache-Control': 'no-store' })
  res.end(JSON.stringify(payload))
}

function readBody(req) {
  return new Promise((resolve, reject) => {
    const chunks = []
    req.on('data', (chunk) => chunks.push(chunk))
    req.on('end', () => resolve(Buffer.concat(chunks).toString('utf8')))
    req.on('error', reject)
  })
}

export function apply(root) {
  // --- Desktop channel: register before any service wait (see row comment). ---
  const rowDisposers = []
  root.effect(() => () => {
    for (const d of rowDisposers) {
      try {
        d()
      } catch {}
    }
  })
  rowDisposers.push(
    root.on('webserver/index-inject', (table) => {
      try {
        if (!Array.isArray(table)) return
        for (const row of table) {
          if (row && typeof row.text === 'string' && row.text.includes(`${ROUTE_PREFIX}/widget.js`)) return
        }
        table.push({ kind: 'script', placement: 'body', text: DESKTOP_WIDGET_ROW_TEXT })
      } catch {}
    }),
  )

  // --- Web channel: routes + tapIndex once the web server is up. ---
  root.inject(['webServer'], (ctx) => {
    const disposers = []
    // Read per request with no-store so local edits to widget.js show up on refresh.
    const widgetJs = () => fs.readFileSync(path.join(PACKAGE_ROOT, 'widget.js'), 'utf8')

    disposers.push(
      ctx.webServer.register({
        kind: 'exact',
        path: `${ROUTE_PREFIX}/widget.js`,
        handler: (req, res) => {
          try {
            const body = widgetJs()
            res.writeHead(200, {
              'Content-Type': 'application/javascript; charset=utf-8',
              'Cache-Control': 'no-store',
              'Content-Length': String(Buffer.byteLength(body)),
            })
            res.end(body)
          } catch (err) {
            res.writeHead(404, { 'Content-Type': 'text/plain; charset=utf-8' })
            res.end(`widget.js unavailable: ${err instanceof Error ? err.message : String(err)}`)
          }
        },
      }),
    )

    disposers.push(
      ctx.webServer.register({
        kind: 'exact',
        path: `${ROUTE_PREFIX}/data.json`,
        handler: (req, res) => {
          try {
            sendJson(res, 200, { ok: true, data: collectData() })
          } catch (err) {
            sendJson(res, 200, { ok: false, error: err instanceof Error ? err.message : String(err) })
          }
        },
      }),
    )

    disposers.push(
      ctx.webServer.register({
        kind: 'exact',
        path: `${ROUTE_PREFIX}/config.json`,
        handler: async (req, res) => {
          try {
            if (req.method === 'GET') {
              sendJson(res, 200, { ok: true, config: readConfig() })
              return
            }
            if (req.method === 'PUT') {
              const patch = JSON.parse((await readBody(req)) || '{}')
              if (patch.pollSeconds !== undefined) {
                const n = Number(patch.pollSeconds)
                if (!Number.isFinite(n) || n < 5 || n > 3600) {
                  throw new Error('pollSeconds must be a number between 5 and 3600.')
                }
                patch.pollSeconds = n
              }
              sendJson(res, 200, { ok: true, config: writeConfig(patch) })
              return
            }
            sendJson(res, 405, { ok: false, error: 'Use GET or PUT.' })
          } catch (err) {
            sendJson(res, 400, { ok: false, error: err instanceof Error ? err.message : String(err) })
          }
        },
      }),
    )

    // Web channel injection: one idempotent tap over every rendered index.html.
    // The desktop row above is a separate channel; each dedupes on its own.
    disposers.push(
      ctx.webServer.tapIndex((html) => {
        if (html.includes(`${ROUTE_PREFIX}/widget.js`)) return html
        if (html.includes('</body>')) return html.replace('</body>', `${SCRIPT_TAG}</body>`)
        return html + SCRIPT_TAG
      }),
    )

    ctx.effect(() => () => {
      for (const d of disposers) {
        try {
          d()
        } catch {}
      }
    })
  })
}
