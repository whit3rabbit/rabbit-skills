/* ============================================================================
 * startup-screen-template — screen pack (browser, zero dependencies)
 * ----------------------------------------------------------------------------
 * A "screen" is one startup look. Each screen is a plain object:
 *
 *   {
 *     label: 'Human name',
 *     mount: function (root, cfg, done) { ...; return cleanupFn }
 *   }
 *
 * Contract (this is the whole API a screen gets):
 *   root  – the full-viewport overlay element (.sst-overlay). Build DOM inside
 *           it; the widget owns mounting, fading, skipping, and removal.
 *   cfg   – the normalized config object (title, subtitle, accent, durationMs…).
 *           Accent is pre-applied as the --sst-accent CSS variable.
 *   done  – call exactly once when the screen finishes; the widget then fades
 *           the overlay out and releases the page. Screens must always reach
 *           done (or be skipped) — a screen that never calls done relies on
 *           the 9s watchdog instead, which is a bug, not a design.
 *
 * mount returns a cleanup function the widget calls before unmounting
 * (clear timers, cancel animations). Register new screens on the registry
 * object below and add the key to `ENUMS.screen` in lib/index.js.
 * ========================================================================== */
;(function () {
  'use strict'

  var registry = window.__STARTUP_SCREEN_TEMPLATE_SCREENS__ || {}

  /** Baseline beat (ms) that all screen timings scale from. `durationMs` in
      config stretches or compresses the whole timeline proportionally. */
  var BASE = 2600

  function scaleFor(cfg) {
    var n = Number(cfg && cfg.durationMs)
    return (Number.isFinite(n) && n > 0 ? n : BASE) / BASE
  }

  /** Escape untrusted config text before it becomes HTML. */
  function esc(text) {
    return String(text == null ? '' : text).replace(/[&<>"']/g, function (ch) {
      return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[ch]
    })
  }

  /* ── Screen 1: wordmark ────────────────────────────────────────────────────
     Centered title + subtitle over a dark plate, thin progress bar underneath.
     The minimal "brand flash" every product ships with. */
  registry.wordmark = {
    label: 'Wordmark',
    mount: function (root, cfg, done) {
      root.innerHTML =
        '<div class="sst-center">' +
        '<div class="sst-title">' + esc(cfg.title) + '</div>' +
        '<div class="sst-subtitle">' + esc(cfg.subtitle) + '</div>' +
        '<div class="sst-progress"><div class="sst-progress-fill"></div></div>' +
        '</div>'

      var scale = scaleFor(cfg)
      var total = Math.round(2200 * scale)
      var fill = root.querySelector('.sst-progress-fill')
      fill.style.transition = 'width ' + total + 'ms linear'
      /* Two frames so the transition starts from width 0, not from the target. */
      requestAnimationFrame(function () {
        requestAnimationFrame(function () { fill.style.width = '100%' })
      })
      var timer = setTimeout(done, total + 300)
      return function () { clearTimeout(timer) }
    }
  }

  /* ── Screen 2: boot log ────────────────────────────────────────────────────
     Terminal-style lines appearing on a timer. Swap the `lines` array for your
     own boot sequence; the rendering and pacing stay the same. */
  registry['boot-log'] = {
    label: 'Boot log',
    mount: function (root, cfg, done) {
      var scale = scaleFor(cfg)
      var lines = [
        '[ok]   loading configuration',
        '[ok]   attaching session store',
        '[....] starting agent runtime',
        '[ok]   registering tools',
        '[ok]   ' + String(cfg.subtitle || 'ready').toLowerCase()
      ]
      root.innerHTML =
        '<div class="sst-center sst-mono">' +
        '<div class="sst-title">' + esc(cfg.title) + '</div>' +
        '<pre class="sst-log"></pre>' +
        '<div class="sst-log-cursor">&gt;_</div>' +
        '</div>'

      var log = root.querySelector('.sst-log')
      var i = 0
      var timer = setInterval(function () {
        if (i >= lines.length) {
          clearInterval(timer)
          setTimeout(done, 350 * scale)
          return
        }
        log.textContent += lines[i] + '\n'
        i += 1
      }, Math.round(300 * scale))
      return function () { clearInterval(timer) }
    }
  }

  /* ── Screen 3: steps ───────────────────────────────────────────────────────
     A checklist that ticks pending → active → ok. The generic form of a
     "system checks passed" access sequence. Edit the `steps` array freely. */
  registry.steps = {
    label: 'Status steps',
    mount: function (root, cfg, done) {
      var scale = scaleFor(cfg)
      var steps = ['Loading profile', 'Connecting services', 'Preparing workspace', 'Ready']
      root.innerHTML =
        '<div class="sst-center">' +
        '<div class="sst-title">' + esc(cfg.title) + '</div>' +
        '<ul class="sst-steps">' +
        steps.map(function (s) {
          return '<li class="sst-step" data-state="pending"><span class="sst-dot"></span>' + esc(s) + '</li>'
        }).join('') +
        '</ul>' +
        '</div>'

      var items = Array.prototype.slice.call(root.querySelectorAll('.sst-step'))
      var i = 0
      var timer = setInterval(function () {
        if (i >= items.length) {
          clearInterval(timer)
          setTimeout(done, 400 * scale)
          return
        }
        items[i].dataset.state = 'active'
        setTimeout(function (node) {
          return function () { node.dataset.state = 'ok' }
        }(items[i]), Math.round(220 * scale))
        i += 1
      }, Math.round(480 * scale))
      return function () { clearInterval(timer) }
    }
  }

  window.__STARTUP_SCREEN_TEMPLATE_SCREENS__ = registry
})()
