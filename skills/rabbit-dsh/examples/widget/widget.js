// DSH floating overlay widget template — page-side client (vanilla JS, no build step).
//
// Injected by the host plugin (index.js) through two channels: the tapIndex
// <script defer> tag on web, and the inline webserver/index-inject row on desktop.
// Mounts a small draggable pill at the bottom-right of the chat page showing
// whatever the host's collectData() returns. Click the pill for details.

(function () {
  // Idempotency guard: the script can be injected twice (tapIndex + desktop row,
  // or a stale HMR reload). Run exactly once per page.
  if (window.__dshWidgetTemplate) return
  window.__dshWidgetTemplate = true

  var ROUTE = '/widget-template'
  var POS_KEY = 'dsh-widget-template.pos'
  var MOVE_SQUARED_CLICK_THRESHOLD = 9 // drag if displacement > 3px, else click

  var state = {
    config: { pollSeconds: 60 },
    data: null,
    timer: 0,
    root: null,
    pillEl: null,
    valueEl: null,
    bubbleEl: null,
    detailEl: null,
    updatedEl: null,
  }

  // =========================================================================
  // CUSTOMIZE HERE — markup and styling. Keep data rendering on textContent:
  // the payload comes from a route and must never be turned into HTML.
  // =========================================================================
  function buildDom() {
    var style = document.createElement('style')
    style.textContent = [
      '.dshwt-root{position:fixed;z-index:9999;font:12px/1.4 system-ui,sans-serif;color:#1f2937;color-scheme:light}',
      '.dshwt-pill{position:fixed;display:flex;align-items:center;gap:6px;padding:6px 12px;border-radius:999px;',
        'background:#fff;border:1px solid #cbd5e1;box-shadow:0 2px 8px rgba(0,0,0,.18);',
        'cursor:grab;user-select:none;white-space:nowrap}',
      '.dshwt-pill:active{cursor:grabbing}',
      '.dshwt-label{font-weight:700;color:#475569}',
      '.dshwt-bubble{display:none;position:absolute;bottom:calc(100% + 8px);left:0;width:240px;',
        'padding:8px 10px;background:#fff;border:1px solid #cbd5e1;border-radius:10px;',
        'box-shadow:0 4px 14px rgba(0,0,0,.2);cursor:pointer}',
      '.dshwt-bubble.dshwt-open{display:block}',
      '.dshwt-detail{color:#334155}',
      '.dshwt-updated{margin-top:4px;color:#94a3b8;font-size:10px}',
    ].join('')
    document.head.appendChild(style)

    var root = document.createElement('div')
    root.className = 'dshwt-root'

    var pill = document.createElement('button')
    pill.className = 'dshwt-pill'
    pill.type = 'button'
    var label = document.createElement('span')
    label.className = 'dshwt-label'
    label.textContent = 'Widget'
    var value = document.createElement('span')
    value.className = 'dshwt-value'
    pill.appendChild(label)
    pill.appendChild(value)

    var bubble = document.createElement('div')
    bubble.className = 'dshwt-bubble'
    var detail = document.createElement('div')
    detail.className = 'dshwt-detail'
    var updated = document.createElement('div')
    updated.className = 'dshwt-updated'
    bubble.appendChild(detail)
    bubble.appendChild(updated)

    root.appendChild(pill)
    root.appendChild(bubble)
    document.body.appendChild(root)

    state.root = root
    state.pillEl = pill
    state.valueEl = value
    state.bubbleEl = bubble
    state.detailEl = detail
    state.updatedEl = updated

    place(pill, loadPos())
    wirePill(pill)
    bubble.addEventListener('click', function () {
      setOpen(false)
    })
    window.addEventListener('resize', function () {
      place(pill, currentPos(pill))
    })
  }

  function loadPos() {
    try {
      var saved = JSON.parse(window.localStorage.getItem(POS_KEY) || 'null')
      if (saved && typeof saved.left === 'number' && typeof saved.top === 'number') return saved
    } catch (err) {}
    // Default: bottom-right, 16px insets. Always position with left/top pixels —
    // CSS transitions cannot interpolate `right`/`auto`, and anchored moves jump.
    return { left: window.innerWidth - 16, top: window.innerHeight - 16 }
  }

  function currentPos(pill) {
    return { left: parseFloat(pill.style.left) || 0, top: parseFloat(pill.style.top) || 0 }
  }

  function clampPos(pos, pill) {
    var rect = pill.getBoundingClientRect()
    return {
      left: Math.min(Math.max(0, pos.left), Math.max(0, window.innerWidth - rect.width)),
      top: Math.min(Math.max(0, pos.top), Math.max(0, window.innerHeight - rect.height)),
    }
  }

  function place(pill, pos) {
    var clamped = clampPos(pos, pill)
    pill.style.left = clamped.left + 'px'
    pill.style.top = clamped.top + 'px'
  }

  // Drag with pointer capture. A press that moves less than 3px is a click:
  // open the bubble and refresh. Everything else repositions the pill.
  function wirePill(pill) {
    var startX = 0
    var startY = 0
    var origin = null
    var dragged = false
    pill.addEventListener('pointerdown', function (event) {
      if (event.button !== 0) return
      pill.setPointerCapture(event.pointerId)
      startX = event.clientX
      startY = event.clientY
      origin = currentPos(pill)
      dragged = false
    })
    pill.addEventListener('pointermove', function (event) {
      if (origin === null) return
      var dx = event.clientX - startX
      var dy = event.clientY - startY
      if (dx * dx + dy * dy >= MOVE_SQUARED_CLICK_THRESHOLD) dragged = true
      if (dragged) place(pill, { left: origin.left + dx, top: origin.top + dy })
    })
    pill.addEventListener('pointerup', function (event) {
      if (origin === null) return
      var wasDragged = dragged
      origin = null
      if (wasDragged) {
        place(pill, currentPos(pill))
        try {
          window.localStorage.setItem(POS_KEY, JSON.stringify(currentPos(pill)))
        } catch (err) {}
        return
      }
      setOpen(!state.bubbleEl.classList.contains('dshwt-open'))
      refresh()
      event.preventDefault()
    })
  }

  function setOpen(open) {
    state.bubbleEl.classList.toggle('dshwt-open', open)
  }

  function render() {
    var data = state.data
    if (!data) return
    if (state.valueEl.firstChild) state.valueEl.removeChild(state.valueEl.firstChild)
    state.valueEl.appendChild(document.createTextNode(String(data.value)))
    state.detailEl.textContent = String(data.detail || '')
    state.updatedEl.textContent = data.updatedAt ? 'Updated ' + String(data.updatedAt) : ''
    // The value text changes the pill's width; re-clamp so it stays on screen.
    if (state.pillEl) place(state.pillEl, currentPos(state.pillEl))
  }

  function fetchJson(url, options) {
    var controller = new AbortController()
    var timer = setTimeout(function () {
      controller.abort()
    }, 15000)
    return fetch(url, Object.assign({ signal: controller.signal }, options || {})).then(
      function (res) {
        clearTimeout(timer)
        if (!res.ok) throw new Error('HTTP ' + res.status)
        return res.json()
      },
      function (err) {
        clearTimeout(timer)
        throw err
      },
    )
  }

  function loadConfig() {
    return fetchJson(ROUTE + '/config.json')
      .then(function (body) {
        if (body && body.ok && body.config) state.config = body.config
      })
      .catch(function () {}) // defaults already in place; keep the widget alive offline
  }

  function refresh() {
    return fetchJson(ROUTE + '/data.json')
      .then(function (body) {
        state.data = body && body.ok ? body.data : { value: '—', detail: String((body && body.error) || 'Data unavailable.'), updatedAt: null }
        render()
      })
      .catch(function () {
        state.data = { value: '—', detail: 'Host route unreachable.', updatedAt: null }
        render()
      })
  }

  function start() {
    buildDom()
    loadConfig().then(function () {
      refresh()
      state.timer = window.setInterval(refresh, (state.config.pollSeconds || 60) * 1000)
    })
  }

  // Gate: mount only on the chat page. The composer markers exist only on the
  // conversation view, so marketplace/settings SPA views are left untouched.
  function isChatRoot() {
    var root = document.getElementById('root')
    if (!root || !root.querySelector) return false
    return !!root.querySelector(
      'textarea, [contenteditable="true"], [data-composer-input], [data-composer-seat]',
    )
  }

  // Deferred scripts run before React renders #root, and the user can leave the
  // chat view for marketplace/settings later, so keep the observer connected and
  // show or hide the pill as the composer appears or disappears.
  function sync() {
    if (isChatRoot()) {
      if (!state.root) start()
      else state.root.style.display = ''
    } else if (state.root) {
      state.root.style.display = 'none'
      setOpen(false)
    }
  }
  var observer = new MutationObserver(sync)
  function observe() {
    if (document.body) observer.observe(document.body, { childList: true, subtree: true })
    else document.addEventListener('DOMContentLoaded', observe)
  }
  observe()
  sync()
})()
