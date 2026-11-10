/* ============================================================================
 * startup-screen-template — Host half
 * ----------------------------------------------------------------------------
 * Does three things:
 *   1) Injects the startup screen into index.html: critical CSS that covers the
 *      page before the app mounts, a config object, a bootstrap guard, and the
 *      widget script tags (via webServer.tapIndex).
 *   2) Serves lib/widget.css, lib/screens.js, and lib/widget.js over routes so
 *      the browser never needs a second copy of the files.
 *   3) Persists config to $DSH_HOME/dsh-startup-screen-template.json and serves
 *      GET/POST on /startup-screen-template/config for the settings page.
 *
 * This file is the template for the Host half of any index-injected widget:
 * copy it, rename NS / ROUTE_BASE / CONFIG_FILE / DEFAULTS, and you are done.
 * The real-world reference this template was distilled from is the
 * dsh-startup-screen plugin (https://github.com/6shenhonghong9/dsh-startup-screen).
 * ========================================================================== */

import fs from 'node:fs'
import os from 'node:os'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const PACKAGE_ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
const DSH_HOME = process.env.DSH_HOME || path.join(os.homedir(), '.dsh')
const CONFIG_FILE = path.join(DSH_HOME, 'dsh-startup-screen-template.json')

/** Single rename point for the whole plugin: route prefix, DOM ids, storage
    keys, and window globals all derive from this string or the names below. */
const NS = 'startup-screen-template'
const ROUTE_BASE = '/' + NS
const ROOT_ID = NS + '-root'
const LOCK_CLASS = 'sst-lock'
const BOOT_CLASS = 'sst-boot'

/** Defaults must stay in sync with lib/widget.js — both files carry a copy so
    each half works standalone. Keep the two lists identical. */
const DEFAULTS = {
  enabled: true,
  mode: 'always',             // always | session | daily
  screen: 'wordmark',         // wordmark | boot-log | steps
  title: 'AGENT HARNESS',
  subtitle: 'STARTING UP',
  accent: '#4f8cff',
  durationMs: 2600,           // baseline duration; screens scale their beats by it
  allowSkip: true
}

const ENUMS = {
  mode: ['always', 'session', 'daily'],
  screen: ['wordmark', 'boot-log', 'steps']
}
const BOOL_KEYS = ['enabled', 'allowSkip']
const TEXT_KEYS = ['title', 'subtitle', 'accent']
const RANGES = { durationMs: [800, 30000] }

/** Keep only known keys, coerce types, and clamp values. Unknown input never
    reaches the config file, so a bad POST cannot corrupt the widget. */
function normalize(input) {
  const out = { ...DEFAULTS }
  const src = input && typeof input === 'object' ? input : {}
  for (const key of Object.keys(DEFAULTS)) {
    if (!(key in src) || src[key] === undefined || src[key] === null) continue
    const value = src[key]
    if (BOOL_KEYS.includes(key)) {
      out[key] = value === true || value === 'true' || value === 1 || value === '1'
    } else if (ENUMS[key]) {
      out[key] = ENUMS[key].includes(value) ? value : DEFAULTS[key]
    } else if (RANGES[key]) {
      const [lo, hi] = RANGES[key]
      const n = Number(value)
      out[key] = Number.isFinite(n) ? Math.min(hi, Math.max(lo, n)) : DEFAULTS[key]
    } else if (key === 'accent') {
      const s = String(value).trim()
      out[key] = /^#[0-9a-fA-F]{3,8}$/.test(s) ? s : DEFAULTS[key]
    } else if (TEXT_KEYS.includes(key)) {
      out[key] = String(value).slice(0, 64)
    } else {
      out[key] = value
    }
  }
  if (!String(out.title).trim()) out.title = DEFAULTS.title
  return out
}

/** Sanitize a client patch: valid values are coerced, invalid or unknown values
    are dropped so the previous setting survives a bad POST unchanged. */
function pickPatch(patch) {
  const src = patch && typeof patch === 'object' ? patch : {}
  const out = {}
  for (const key of Object.keys(DEFAULTS)) {
    const value = src[key]
    if (value === undefined || value === null) continue
    if (BOOL_KEYS.includes(key)) {
      out[key] = value === true || value === 'true' || value === 1 || value === '1'
    } else if (ENUMS[key]) {
      if (ENUMS[key].includes(value)) out[key] = value
    } else if (RANGES[key]) {
      const [lo, hi] = RANGES[key]
      const n = Number(value)
      if (Number.isFinite(n)) out[key] = Math.min(hi, Math.max(lo, n))
    } else if (key === 'accent') {
      const s = String(value).trim()
      if (/^#[0-9a-fA-F]{3,8}$/.test(s)) out[key] = s
    } else if (TEXT_KEYS.includes(key)) {
      const s = String(value).slice(0, 64)
      if (s.trim()) out[key] = s
    }
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

/** Serve plugin files from disk with an mtime cache: edit + refresh is enough
    during development, no reinstall needed. */
function makeReader(rel) {
  let cache = null
  return function read() {
    const file = path.join(PACKAGE_ROOT, rel)
    try {
      const st = fs.statSync(file)
      if (!cache || cache.mtimeMs !== st.mtimeMs) {
        cache = { mtimeMs: st.mtimeMs, text: fs.readFileSync(file, 'utf8') }
      }
      return cache.text
    } catch (err) {
      return ''
    }
  }
}

const readWidgetCss = makeReader('lib/widget.css')
const readScreensJs = makeReader('lib/screens.js')
const readWidgetJs = makeReader('lib/widget.js')

/** Inline scripts must never contain a literal `</script>`: escape it away. */
function safeJson(value) {
  return JSON.stringify(value).replace(/</g, '\\u003c').replace(/\u2028|\u2029/g, '')
}

/** Critical CSS: covers the page with the boot layer before the app mounts so
    the real UI never flashes through. sst-boot is removed by the widget when
    the real overlay mounts; the watchdog below removes it if scripts fail. */
const CRITICAL_CSS = [
  'html.' + LOCK_CLASS + ',html.' + LOCK_CLASS + ' body{overflow:hidden!important}',
  '#' + ROOT_ID + '.' + BOOT_CLASS +
    '{position:fixed;inset:0;z-index:2147483000;background:#0b0d10}'
].join('\n')

/** Bootstrap guard, injected inline so it runs before any deferred script.
    Decides whether this page load plays at all (mode gating) and installs a
    watchdog: if the widget never starts (404, blocked, syntax error), release
    the page after 9s no matter what. A startup screen must never lock the
    user out — this timeout is the safety contract of the whole template. */
const BOOTSTRAP_JS = `(function(){try{
var c=window.__STARTUP_SCREEN_TEMPLATE__||{};
var root=document.getElementById('${ROOT_ID}');
var off=c.enabled===false;
if(!off&&c.mode==='session'&&sessionStorage.getItem('${NS}:shown')==='1')off=true;
if(!off&&c.mode==='daily'&&localStorage.getItem('${NS}:day')===new Date().toISOString().slice(0,10))off=true;
if(off){window.__STARTUP_SCREEN_TEMPLATE_SKIP__=true;if(root&&root.parentNode)root.parentNode.removeChild(root);}
else{document.documentElement.classList.add('${LOCK_CLASS}');setTimeout(function(){try{
if(window.__STARTUP_SCREEN_TEMPLATE_RUNNING__===true)return;
var r=document.getElementById('${ROOT_ID}');
if(r&&r.parentNode)r.parentNode.removeChild(r);
document.documentElement.classList.remove('${LOCK_CLASS}');
if(document.body)document.body.style.overflow='';
}catch(e){}},9000);}
}catch(e){} })()`

export const name = NS
const inject = ['webServer']

function apply(ctx) {
  const webServer = ctx.webServer
  const disposers = []

  /** Trust barrier: every custom route must pass the host's requestRejection
      check first, otherwise any web page could read the config endpoint. */
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

  function sendText(res, type, text) {
    const body = Buffer.from(text, 'utf8')
    res.writeHead(200, {
      'Content-Type': type,
      'Cache-Control': 'no-store',
      'Content-Length': String(body.length)
    })
    res.end(body)
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
    path: ROUTE_BASE + '/widget.css',
    handler: (req, res) => sendText(res, 'text/css; charset=utf-8', readWidgetCss())
  }))
  disposers.push(registerRoute({
    kind: 'exact',
    path: ROUTE_BASE + '/screens.js',
    handler: (req, res) => sendText(res, 'application/javascript; charset=utf-8', readScreensJs())
  }))
  disposers.push(registerRoute({
    kind: 'exact',
    path: ROUTE_BASE + '/widget.js',
    handler: (req, res) => sendText(res, 'application/javascript; charset=utf-8', readWidgetJs())
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
      sendJson(res, 200, { ok: true, config: writeConfig({ ...current, ...pickPatch(patch) }), defaults: DEFAULTS })
    }
  }))

  /** Index injection: idempotent (the include-check makes reloads safe) and
      split across </head> and <body> so CSS loads before the boot layer. */
  disposers.push(webServer.tapIndex((html) => {
    if (!html || html.includes(ROUTE_BASE + '/widget.js')) return html
    const cfg = readConfig()
    const head =
      '<link rel="stylesheet" href="' + ROUTE_BASE + '/widget.css">' +
      '<style id="' + NS + '-critical">' + CRITICAL_CSS + '</style>'
    const body =
      '<div id="' + ROOT_ID + '" class="' + BOOT_CLASS + '"></div>' +
      '<script>window.__STARTUP_SCREEN_TEMPLATE__=' + safeJson(cfg) + ';' + BOOTSTRAP_JS + '</script>' +
      '<script defer src="' + ROUTE_BASE + '/screens.js"></script>' +
      '<script defer src="' + ROUTE_BASE + '/widget.js"></script>'

    let out = html
    if (out.includes('</head>')) out = out.replace('</head>', head + '</head>')
    else out = head + out
    if (out.includes('<body>')) out = out.replace('<body>', '<body>' + body)
    else if (out.includes('</body>')) out = out.replace('</body>', body + '</body>')
    else out = out + body
    return out
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
