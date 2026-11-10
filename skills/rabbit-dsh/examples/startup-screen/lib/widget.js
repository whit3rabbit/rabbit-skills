/* ============================================================================
 * startup-screen-template — widget runtime (browser, zero dependencies)
 * ----------------------------------------------------------------------------
 * Lifecycle this template implements (keep it in this order when you adapt it):
 *
 *   Host injects into index.html:
 *     <div id="startup-screen-template-root" class="sst-boot">  ← boot layer
 *     <script> config + bootstrap guard + 9s watchdog </script>
 *     <script defer src=".../screens.js">  ← screen pack (this file's sibling)
 *     <script defer src=".../widget.js">   ← this file
 *
 *   widget.js (here):
 *     1. Bails out if the bootstrap guard set __STARTUP_SCREEN_TEMPLATE_SKIP__.
 *     2. Promotes the boot layer to the real overlay (.sst-overlay).
 *     3. Runs the configured screen from the screen pack until it calls done.
 *     4. finish(): fades out, removes the root, unlocks scrolling, records the
 *        session/daily marks, clears __STARTUP_SCREEN_TEMPLATE_RUNNING__.
 *     5. Skippable via Esc / Enter / Space / click when cfg.allowSkip.
 *
 * The watchdog in the Host bootstrap releases the page if this file never
 * runs; conversely, every path here ends in finish() so the page is always
 * released. Neither side may rely on the other.
 * ========================================================================== */
;(function () {
  'use strict'

  if (window.__STARTUP_SCREEN_TEMPLATE_LOADED__) return
  window.__STARTUP_SCREEN_TEMPLATE_LOADED__ = true

  var NS = 'startup-screen-template'
  var ROOT_ID = NS + '-root'
  var LOCK_CLASS = 'sst-lock'
  /** Fade-out length; must match .sst-out in widget.css. */
  var FADE_MS = 240

  var cfg = window.__STARTUP_SCREEN_TEMPLATE__ || {}
  if (cfg.enabled === false) return
  if (window.__STARTUP_SCREEN_TEMPLATE_SKIP__) return
  /* Cadence gate: session/daily marks are written by recordShown() after a
     finished play; the Preview button replays through the API, not here. */
  try {
    if (cfg.mode === 'session' && sessionStorage.getItem(NS + ':shown') === '1') return
    if (cfg.mode === 'daily' && localStorage.getItem(NS + ':day') === new Date().toISOString().slice(0, 10)) return
  } catch (err) { /* storage denied; showing again is fine */ }

  var root = null
  var finished = false
  var screenCleanup = null

  function unlock() {
    document.documentElement.classList.remove(LOCK_CLASS)
    if (document.body) document.body.style.overflow = ''
  }

  function recordShown() {
    try {
      if (cfg.mode === 'session') sessionStorage.setItem(NS + ':shown', '1')
      if (cfg.mode === 'daily') {
        localStorage.setItem(NS + ':day', new Date().toISOString().slice(0, 10))
      }
    } catch (err) { /* private browsing may deny storage; showing again is fine */ }
  }

  function finish() {
    if (finished) return
    finished = true
    if (root) root.classList.add('sst-out')
    setTimeout(function () {
      if (screenCleanup) {
        try { screenCleanup() } catch (err) { /* cleanup must not block release */ }
        screenCleanup = null
      }
      if (root && root.parentNode) root.parentNode.removeChild(root)
      root = null
      unlock()
      window.__STARTUP_SCREEN_TEMPLATE_RUNNING__ = false
    }, FADE_MS)
    recordShown()
  }

  function skip() {
    if (!cfg.allowSkip || finished) return
    finish()
  }

  function onKey(e) {
    if (e.key === 'Escape' || e.key === 'Enter' || e.key === ' ') skip()
  }

  function run() {
    var screens = window.__STARTUP_SCREEN_TEMPLATE_SCREENS__ || {}
    var screen = screens[cfg.screen] || screens.wordmark
    root.className = 'sst-overlay'
    root.style.setProperty('--sst-accent', cfg.accent || '#4f8cff')
    window.__STARTUP_SCREEN_TEMPLATE_RUNNING__ = true
    if (typeof screen.mount === 'function') {
      screenCleanup = screen.mount(root, cfg, finish)
    } else {
      /* No such screen: release immediately instead of hanging on the lock. */
      finish()
    }
  }

  function replay() {
    if (screenCleanup) {
      try { screenCleanup() } catch (err) { /* noop */ }
      screenCleanup = null
    }
    var old = document.getElementById(ROOT_ID)
    if (old && old.parentNode) old.parentNode.removeChild(old)
    unlock()
    finished = false
    mountRoot()
    run()
  }

  window.__STARTUP_SCREEN_TEMPLATE_API__ = { replay: replay }

  function mountRoot() {
    root = document.getElementById(ROOT_ID)
    if (!root) {
      /* Client-side self-boot path: the Host could not inject (e.g. a desktop
         build delivering the frontend over file:// + IPC), so create the root
         ourselves. The lock class is still needed to hold the page. */
      root = document.createElement('div')
      root.id = ROOT_ID
      ;(document.body || document.documentElement).appendChild(root)
    }
    root.addEventListener('click', skip)
  }

  document.addEventListener('keydown', onKey)
  mountRoot()
  document.documentElement.classList.add(LOCK_CLASS)
  run()
})()
