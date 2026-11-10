/**
 * startup-screen-template — client half (settings page)
 * ----------------------------------------------------------------------------
 * Loaded as a handwritten ModuleLoader bundle (no build step): the DSH browser
 * shell evaluates `exports["./client"]` through window.__ModuleLoader__.load.
 *
 * The registration id below MUST equal the package name (the loader entry
 * name); otherwise the loader fails with "loaded without registering …".
 *
 * The panel persists config through the Host half's HTTP API
 * (GET/POST startup-screen-template/config) instead of the settings namespace,
 * so the widget and the panel always read the same file. Per the repo's
 * proxy-safe rule the fetch uses a relative path without a leading slash.
 */
window.__ModuleLoader__.load({
  id: 'startup-screen-template',
  factory: (require) => {
    /* Match the loader's module detection: mark exports as a Module, exactly
       as DSH internal handwritten bundles do. */
    var module = { exports: {} }
    var exports = module.exports
    Object.defineProperty(exports, Symbol.toStringTag, { value: 'Module' })

    var react = require('react')
    var h = react.createElement

    var API = 'startup-screen-template/config'
    var NS = 'startup-screen-template'

    var CSS = [
      '.sst-panel{max-width:560px;display:flex;flex-direction:column;gap:12px;font-size:13px;color:var(--dsw-alias-label-primary)}',
      '.sst-row{display:flex;align-items:center;gap:10px;flex-wrap:wrap}',
      '.sst-label{font-size:12px;font-weight:600;color:var(--dsw-alias-label-primary)}',
      '.sst-hint{font-size:11px;line-height:1.5;color:var(--dsw-alias-label-tertiary)}',
      '.sst-input,.sst-select{border:1px solid var(--dsw-alias-border-l2);background:var(--dsw-alias-bg-layer-3);color:var(--dsw-alias-label-primary);border-radius:8px;padding:6px 10px;font:inherit;font-size:13px;outline:none}',
      '.sst-input:focus,.sst-select:focus{border-color:var(--dsw-alias-state-business-primary)}',
      '.sst-field{display:flex;flex-direction:column;gap:4px}',
      '.sst-color{width:42px;height:28px;padding:0;border:1px solid var(--dsw-alias-border-l2);border-radius:6px;background:transparent;cursor:pointer}',
      '.sst-btn{border:1px solid var(--dsw-alias-border-l2);background:var(--dsw-alias-bg-layer-3);color:var(--dsw-alias-label-primary);border-radius:8px;padding:6px 14px;font:inherit;font-size:13px;cursor:pointer}',
      '.sst-btn:hover:not(:disabled){border-color:var(--dsw-alias-state-business-primary)}',
      '.sst-btn:disabled{opacity:.5;cursor:default}',
      '.sst-btnPrimary{border-color:var(--dsw-alias-state-business-primary);background:var(--dsw-alias-state-business-primary);color:#fff}',
      '.sst-status{font-size:12px;color:var(--dsw-alias-label-tertiary)}',
      '.sst-ok{color:var(--dsw-alias-state-success-primary,var(--dsw-alias-state-business-primary))}',
      '.sst-err{color:var(--dsw-alias-state-error-primary)}'
    ].join('')

    var tagId = NS + '/main.css'
    if (typeof document !== 'undefined' && document.querySelector('style[data-plugin-css="' + tagId + '"]') === null) {
      var tag = document.createElement('style')
      tag.dataset.plugin = NS
      tag.dataset.pluginCss = tagId
      tag.textContent = CSS
      document.head.appendChild(tag)
    }

    /* Local fallback so the panel renders even if the Host half is older than
       the panel; load() replaces this with the server's real config. */
    var FALLBACK = {
      enabled: true, mode: 'always', screen: 'wordmark',
      title: 'AGENT HARNESS', subtitle: 'STARTING UP',
      accent: '#4f8cff', durationMs: 2600, allowSkip: true
    }

    function Field(props) {
      return h('div', { className: 'sst-field' },
        h('label', { className: 'sst-label' }, props.label),
        props.children,
        props.hint ? h('div', { className: 'sst-hint' }, props.hint) : null
      )
    }

    function Panel() {
      var [draft, setDraft] = react.useState(null)
      var [notice, setNotice] = react.useState('')
      var [error, setError] = react.useState('')
      var [busy, setBusy] = react.useState(false)

      function load() {
        setError(''); setNotice('')
        return fetch(API, { headers: { Accept: 'application/json' } })
          .then(function (r) { return r.json() })
          .then(function (j) {
            if (!j || j.ok !== true) throw new Error((j && j.error) || 'load failed')
            setDraft(Object.assign({}, FALLBACK, j.config))
          })
          .catch(function (e) { setError('Load failed: ' + String(e && e.message ? e.message : e)) })
      }

      react.useEffect(function () { load() }, [])

      function set(key, value) {
        setNotice(''); setError('')
        setDraft(function (d) { return Object.assign({}, d, (function () { var o = {}; o[key] = value; return o })()) })
      }

      function save() {
        if (!draft) return
        setBusy(true)
        fetch(API, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ patch: draft })
        })
          .then(function (r) { return r.json() })
          .then(function (j) {
            if (!j || j.ok !== true) throw new Error((j && j.error) || 'save failed')
            setDraft(Object.assign({}, FALLBACK, j.config))
            setNotice('Saved. Takes effect on the next page load; use Preview to replay now.')
          })
          .catch(function (e) { setError('Save failed: ' + String(e && e.message ? e.message : e)) })
          .then(function () { setBusy(false) })
      }

      function reset() {
        setBusy(true)
        fetch(API, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ action: 'reset' })
        })
          .then(function (r) { return r.json() })
          .then(function (j) {
            if (!j || j.ok !== true) throw new Error((j && j.error) || 'reset failed')
            setDraft(Object.assign({}, FALLBACK, j.config))
            setNotice('Restored defaults.')
          })
          .catch(function (e) { setError('Reset failed: ' + String(e && e.message ? e.message : e)) })
          .then(function () { setBusy(false) })
      }

      function preview() {
        var api = window.__STARTUP_SCREEN_TEMPLATE_API__
        if (api && typeof api.replay === 'function') {
          try { api.replay(); return } catch (err) { /* fall through to reload */ }
        }
        window.location.reload()
      }

      if (!draft) {
        return h('div', { className: 'sst-panel' },
          h('div', { className: 'sst-status' }, error || 'Loading configuration…'))
      }

      return h('div', { className: 'sst-panel' },
        h(Field, { label: 'Screen' },
          h('select', {
            className: 'sst-select',
            value: draft.screen,
            onChange: function (e) { set('screen', e.target.value) }
          },
          h('option', { value: 'wordmark' }, 'Wordmark — centered title + progress bar'),
          h('option', { value: 'boot-log' }, 'Boot log — terminal-style lines'),
          h('option', { value: 'steps' }, 'Status steps — ticking checklist'))),
        h('div', { className: 'sst-row' },
          h(Field, { label: 'Title' },
            h('input', {
              className: 'sst-input', type: 'text', maxLength: 64,
              value: draft.title, spellCheck: false,
              onChange: function (e) { set('title', e.target.value) }
            })),
          h(Field, { label: 'Subtitle' },
            h('input', {
              className: 'sst-input', type: 'text', maxLength: 64,
              value: draft.subtitle, spellCheck: false,
              onChange: function (e) { set('subtitle', e.target.value) }
            })),
          h(Field, { label: 'Accent' },
            h('input', {
              className: 'sst-color', type: 'color',
              value: /^#[0-9a-fA-F]{6}$/.test(draft.accent) ? draft.accent : '#4f8cff',
              onChange: function (e) { set('accent', e.target.value) }
            }))),
        h('div', { className: 'sst-row' },
          h(Field, { label: 'Play' },
            h('select', {
              className: 'sst-select',
              value: draft.mode,
              onChange: function (e) { set('mode', e.target.value) }
            },
            h('option', { value: 'always' }, 'Every page load'),
            h('option', { value: 'session' }, 'Once per browser session'),
            h('option', { value: 'daily' }, 'Once per day'))),
          h(Field, { label: 'Duration (ms)', hint: '800–30000; screens scale their beats by it.' },
            h('input', {
              className: 'sst-input', type: 'number', min: 800, max: 30000, step: 100,
              value: draft.durationMs,
              onChange: function (e) { set('durationMs', Number(e.target.value)) }
            })),
          h('label', { className: 'sst-row' },
            h('input', {
              type: 'checkbox', checked: !!draft.allowSkip,
              onChange: function (e) { set('allowSkip', e.target.checked) }
            }),
            h('span', null, 'Allow skip (Esc / Enter / Space / click)'))),
        h('div', { className: 'sst-row' },
          h('button', { className: 'sst-btn sst-btnPrimary', disabled: busy, onClick: save }, 'Save'),
          h('button', { className: 'sst-btn', onClick: preview }, 'Preview'),
          h('button', { className: 'sst-btn', disabled: busy, onClick: reset }, 'Reset'),
          notice ? h('span', { className: 'sst-status sst-ok' }, notice) : null,
          error ? h('span', { className: 'sst-status sst-err' }, error) : null))
    }

    var inject = ['slots']

    function apply(ctx) {
      ctx.slots.inject('settings.section', function () {
        return ctx.slots.register(
          { name: 'settings.section', id: NS, order: 30, label: 'Startup Screen' },
          function () { return h(Panel, {}) }
        )
      })
    }

    exports.apply = apply
    exports.inject = inject
    return module.exports
  }
})
