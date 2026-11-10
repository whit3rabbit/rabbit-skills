/* ============================================================================
 * context-dashboard-template — client half (the dashboard)
 * ----------------------------------------------------------------------------
 * Loaded as a handwritten ModuleLoader bundle (no build step): the DSH browser
 * shell evaluates `exports["./client"]` through window.__ModuleLoader__.load.
 *
 * The registration id below MUST equal the package name (the loader entry
 * name); otherwise the loader fails with "loaded without registering …".
 *
 * Five surfaces, mirroring the dsh-context plugin layout (each one degrades
 * silently when its service is missing):
 *   1. Context tab        — `conversation.view` slot: the full dashboard.
 *   2. Fleet tab          — a second `conversation.view` slot: the agent family.
 *   3. /context command   — `inputTriggers.registerSource`: centered modal.
 *   4. Sidebar panel      — `sidebarRightTabs` + `sidebar.right.pane.tab`.
 *   5. Settings page      — `settings.section` slot: surface switches.
 *
 * Config gating without races: conversation tabs register unconditionally and
 * check the config they fetch on mount; the command and sidebar panel
 * register only after the Host config says they are enabled. Surface changes
 * apply when the affected view next mounts (or on reload).
 *
 * Data comes from the Host half's routes (relative paths, no leading slash —
 * the repo's proxy-safe rule). Until a real source is wired the Host serves
 * the demo fixture, and the dashboard carries a demo banner.
 * ========================================================================== */
window.__ModuleLoader__.load({
  id: 'context-dashboard-template',
  factory: (require) => {
    /* Match the loader's module detection: mark exports as a Module, exactly
       as DSH internal handwritten bundles do. */
    var module = { exports: {} }
    var exports = module.exports
    Object.defineProperty(exports, Symbol.toStringTag, { value: 'Module' })

    var react = require('react')
    var h = react.createElement

    var NS = 'context-dashboard-template'
    var API_DATA = NS + '/data.json'
    var API_CONFIG = NS + '/config'
    var MODAL_ID = NS + '-modal'

    /* Local fallbacks so the UI renders even if the Host half is older than
       the client; each fetch replaces these with the server's real values. */
    var FALLBACK_CONFIG = {
      enableTab: true, enableFleetTab: true, enableSidebarPanel: false,
      enableCommand: true, demoMode: true
    }
    var FALLBACK_DATA = {
      source: 'demo',
      notice: 'Host route unreachable — showing the built-in skeleton fixture.',
      session: { id: 'local', title: 'Context dashboard', model: 'unknown', windowTokens: 128000, reservedTokens: 8192 },
      stats: { turns: 0, steps: 0, humanInputs: 0, toolCalls: 0, activeMs: 0, costUsd: 0, cacheHitRate: 0 },
      composition: [],
      trend: [], events: [], files: [], commands: [], agents: []
    }

    /* --------------------------------------------------------------------
     * Styles — token-pure except the chart palette
     * --------------------------------------------------------------------
     * Layout, text, and surfaces bind to `--dsw-alias-*` skin tokens so the
     * dashboard follows the active theme. The eight `--ctxd-c-*` chart colors
     * are fixed data-encoding hues (dsh-context does the same): category
     * colors must stay recognizable across themes, so they do not follow the
     * skin. Swap them for aliases only if you accept theme-dependent bars.
     */
    var CSS = [
      '.ctxd-root{--ctxd-c-system:#64748b;--ctxd-c-schemas:#0ea5e9;--ctxd-c-user:#22c55e;--ctxd-c-injected:#f59e0b;--ctxd-c-skills:#a855f7;--ctxd-c-reasoning:#ec4899;--ctxd-c-answers:#3b82f6;--ctxd-c-results:#f97316;',
      'display:flex;flex-direction:column;gap:14px;height:100%;min-height:0;overflow:auto;padding:16px;font-size:13px;color:var(--dsw-alias-label-primary);}',
      '.ctxd-head{display:flex;align-items:baseline;gap:10px;flex-wrap:wrap}',
      '.ctxd-title{font-size:15px;font-weight:700}',
      '.ctxd-sub{font-size:12px;color:var(--dsw-alias-label-tertiary)}',
      '.ctxd-actions{margin-left:auto;display:flex;gap:8px}',
      '.ctxd-btn{border:1px solid var(--dsw-alias-border-l2);background:var(--dsw-alias-bg-layer-3);color:var(--dsw-alias-label-primary);border-radius:8px;padding:5px 12px;font:inherit;font-size:12px;cursor:pointer}',
      '.ctxd-btn:hover{border-color:var(--dsw-alias-state-business-primary)}',
      '.ctxd-card{border:1px solid var(--dsw-alias-border-l2);background:var(--dsw-alias-bg-layer-2);border-radius:10px;padding:12px 14px;display:flex;flex-direction:column;gap:10px}',
      '.ctxd-cardTitle{font-size:12px;font-weight:700;letter-spacing:.04em;text-transform:uppercase;color:var(--dsw-alias-label-secondary)}',
      '.ctxd-kpis{display:grid;grid-template-columns:repeat(auto-fit,minmax(120px,1fr));gap:8px}',
      '.ctxd-kpi{border:1px solid var(--dsw-alias-border-l2);border-radius:8px;padding:8px 10px;background:var(--dsw-alias-bg-layer-3)}',
      '.ctxd-kpiValue{font-size:16px;font-weight:700;font-variant-numeric:tabular-nums}',
      '.ctxd-kpiLabel{font-size:11px;color:var(--dsw-alias-label-tertiary)}',
      '.ctxd-bar{display:flex;height:14px;border-radius:7px;overflow:hidden;background:var(--dsw-alias-bg-layer-3)}',
      '.ctxd-barSeg{height:100%}',
      '.ctxd-legend{display:grid;grid-template-columns:repeat(auto-fit,minmax(170px,1fr));gap:4px 14px}',
      '.ctxd-legendRow{display:flex;align-items:center;gap:7px;font-size:12px}',
      '.ctxd-swatch{width:9px;height:9px;border-radius:3px;flex:none}',
      '.ctxd-legendTokens{margin-left:auto;color:var(--dsw-alias-label-tertiary);font-variant-numeric:tabular-nums}',
      '.ctxd-trend{display:flex;align-items:flex-end;gap:3px;height:90px;padding:4px 2px;border-bottom:1px solid var(--dsw-alias-border-l2)}',
      '.ctxd-trendCol{flex:1;display:flex;flex-direction:column;justify-content:flex-end;height:100%;min-width:6px;overflow:hidden}',
      '.ctxd-trendCol:hover{outline:1px solid var(--dsw-alias-state-business-primary)}',
      '.ctxd-trendSteps{display:flex;gap:3px;padding-top:4px}',
      '.ctxd-trendStep{flex:1;min-width:6px;font-size:10px;color:var(--dsw-alias-label-tertiary);text-align:center;overflow:hidden;white-space:nowrap;text-overflow:ellipsis}',
      '.ctxd-chips{display:flex;gap:6px;flex-wrap:wrap}',
      '.ctxd-chip{border:1px solid var(--dsw-alias-border-l2);background:var(--dsw-alias-bg-layer-3);color:var(--dsw-alias-label-secondary);border-radius:999px;padding:2px 10px;font:inherit;font-size:11px;cursor:pointer}',
      '.ctxd-chip[data-active="true"]{border-color:var(--dsw-alias-state-business-primary);color:var(--dsw-alias-state-business-primary)}',
      '.ctxd-rows{display:flex;flex-direction:column;gap:2px}',
      '.ctxd-row{display:flex;align-items:center;gap:10px;padding:5px 6px;border-radius:6px;font-size:12px}',
      '.ctxd-row:hover{background:var(--dsw-alias-bg-layer-3)}',
      '.ctxd-rowMain{overflow:hidden;text-overflow:ellipsis;white-space:nowrap}',
      '.ctxd-rowMeta{margin-left:auto;color:var(--dsw-alias-label-tertiary);font-variant-numeric:tabular-nums;white-space:nowrap}',
      '.ctxd-deltaPos{color:var(--dsw-alias-state-success-primary,var(--ctxd-c-user))}',
      '.ctxd-deltaNeg{color:var(--dsw-alias-state-error-primary)}',
      '.ctxd-notice{border:1px dashed var(--dsw-alias-border-l2);border-radius:8px;padding:7px 10px;font-size:12px;color:var(--dsw-alias-label-secondary);background:var(--dsw-alias-bg-layer-3)}',
      '.ctxd-dot{width:8px;height:8px;border-radius:50%;flex:none}',
      '.ctxd-agents{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:8px}',
      '.ctxd-agent{border:1px solid var(--dsw-alias-border-l2);border-radius:8px;padding:9px 11px;display:flex;flex-direction:column;gap:6px;background:var(--dsw-alias-bg-layer-3)}',
      '.ctxd-agentTitle{display:flex;align-items:center;gap:7px;font-weight:600;font-size:12px}',
      '.ctxd-agentMeta{font-size:11px;color:var(--dsw-alias-label-tertiary);display:flex;gap:8px;flex-wrap:wrap}',
      '.ctxd-track{height:6px;border-radius:3px;background:var(--dsw-alias-bg-layer-3);overflow:hidden}',
      '.ctxd-fill{height:100%;border-radius:3px;background:var(--ctxd-c-answers)}',
      '.ctxd-modalBack{position:fixed;inset:0;z-index:2147482000;background:rgba(0,0,0,.45);display:flex;align-items:center;justify-content:center;padding:24px}',
      '.ctxd-modal{width:min(760px,100%);max-height:86vh;overflow:auto;border-radius:12px;border:1px solid var(--dsw-alias-border-l2);background:var(--dsw-alias-bg-layer-1);padding:18px}',
      '.ctxd-empty{font-size:12px;color:var(--dsw-alias-label-tertiary);padding:6px 2px}'
    ].join('')

    var tagId = NS + '/main.css'
    if (typeof document !== 'undefined' && document.querySelector('style[data-plugin-css="' + tagId + '"]') === null) {
      var tag = document.createElement('style')
      tag.dataset.plugin = NS
      tag.dataset.pluginCss = tagId
      tag.textContent = CSS
      document.head.appendChild(tag)
    }

    /* --------------------------------------------------------------------
     * Formatting helpers
     * ------------------------------------------------------------------ */
    function fmtTokens(n) {
      if (!Number.isFinite(n)) return '—'
      if (Math.abs(n) >= 1000000) return (n / 1000000).toFixed(1) + 'M'
      if (Math.abs(n) >= 1000) return (n / 1000).toFixed(1) + 'k'
      return String(Math.round(n))
    }
    function fmtPct(frac) {
      return Number.isFinite(frac) ? (frac * 100).toFixed(1) + '%' : '—'
    }
    function fmtDuration(ms) {
      if (!Number.isFinite(ms) || ms <= 0) return '—'
      var min = Math.floor(ms / 60000)
      if (min >= 60) return Math.floor(min / 60) + 'h ' + (min % 60) + 'm'
      if (min >= 1) return min + 'm ' + Math.round((ms % 60000) / 1000) + 's'
      return (ms / 1000).toFixed(1) + 's'
    }
    function fmtUsd(n) {
      return Number.isFinite(n) ? '$' + n.toFixed(2) : '—'
    }

    /* --------------------------------------------------------------------
     * Data loading — each surface loads its own copy; no shared hook state
     * ------------------------------------------------------------------ */
    function useDashboardData() {
      var pair = react.useState({ loading: true, error: '', config: FALLBACK_CONFIG, data: FALLBACK_DATA })
      var state = pair[0]
      var setState = pair[1]
      var refresh = react.useCallback(function () {
        setState(function (s) { return Object.assign({}, s, { loading: true, error: '' }) })
        Promise.all([
          fetch(API_DATA, { headers: { Accept: 'application/json' } }).then(function (r) { return r.json() }),
          fetch(API_CONFIG, { headers: { Accept: 'application/json' } }).then(function (r) { return r.json() })
        ]).then(function (results) {
          var data = results[0] && results[0].ok === true && results[0].data ? results[0].data : FALLBACK_DATA
          var config = results[1] && results[1].ok === true && results[1].config
            ? Object.assign({}, FALLBACK_CONFIG, results[1].config)
            : FALLBACK_CONFIG
          setState({ loading: false, error: '', config: config, data: data })
        }).catch(function (e) {
          setState(function (s) {
            return Object.assign({}, s, {
              loading: false,
              error: 'Load failed: ' + String(e && e.message ? e.message : e)
            })
          })
        })
      }, [])
      react.useEffect(function () { refresh() }, [refresh])
      return { state: state, refresh: refresh }
    }

    /* --------------------------------------------------------------------
     * Primitives
     * ------------------------------------------------------------------ */
    function Card(props) {
      return h('div', { className: 'ctxd-card' },
        h('div', { className: 'ctxd-cardTitle' }, props.title),
        props.children)
    }

    function Chip(props) {
      return h('button', {
        className: 'ctxd-chip',
        'data-active': props.active === true,
        onClick: props.onClick
      }, props.label + (props.count !== undefined ? ' · ' + props.count : ''))
    }

    function Dot(props) {
      var tone = props.status === 'running'
        ? 'var(--dsw-alias-state-success-primary, var(--ctxd-c-user))'
        : 'var(--dsw-alias-label-tertiary)'
      return h('span', { className: 'ctxd-dot', style: { background: tone } })
    }

    function Empty(props) {
      return h('div', { className: 'ctxd-empty' }, props.children)
    }

    function Disabled(props) {
      return h('div', { className: 'ctxd-root' },
        h('div', { className: 'ctxd-notice' },
          'The ' + props.name + ' is switched off in Settings → Context Dashboard. Reload after re-enabling.'))
    }

    /** Stacked composition bar. Segments render in array order; zero-token
        categories collapse away. */
    function StackedBar(props) {
      var entries = props.entries.filter(function (e) { return e.tokens > 0 })
      return h('div', { className: 'ctxd-bar' },
        entries.map(function (e) {
          return h('div', {
            key: e.key,
            className: 'ctxd-barSeg',
            style: {
              width: (e.share * 100).toFixed(2) + '%',
              background: 'var(' + (e.colorVar || '--ctxd-c-results') + ')'
            },
            title: e.label + ' · ' + fmtTokens(e.tokens) + ' (' + fmtPct(e.share) + ')'
          })
        }))
    }

    function Legend(props) {
      return h('div', { className: 'ctxd-legend' },
        props.entries.map(function (e) {
          return h('div', { key: e.key, className: 'ctxd-legendRow' },
            h('span', { className: 'ctxd-swatch', style: { background: 'var(' + (e.colorVar || '--ctxd-c-results') + ')' } }),
            h('span', null, e.label),
            h('span', { className: 'ctxd-legendTokens' }, fmtTokens(e.tokens) + ' · ' + fmtPct(e.share)))
        }))
    }

    /* Category metadata: labels + chart colors, keyed like the dataset. Keep
       in sync with lib/demo-data.js `demoCategories` when categories change. */
    var CATEGORY_META = {
      system: { label: 'System prompt', colorVar: '--ctxd-c-system' },
      toolSchemas: { label: 'Tool schemas', colorVar: '--ctxd-c-schemas' },
      user: { label: 'User messages', colorVar: '--ctxd-c-user' },
      injected: { label: 'Injected context', colorVar: '--ctxd-c-injected' },
      skills: { label: 'Skill injections', colorVar: '--ctxd-c-skills' },
      reasoning: { label: 'Reasoning', colorVar: '--ctxd-c-reasoning' },
      answers: { label: 'Answers', colorVar: '--ctxd-c-answers' },
      toolResults: { label: 'Tool results', colorVar: '--ctxd-c-results' }
    }
    var CATEGORY_ORDER = ['system', 'toolSchemas', 'user', 'injected', 'skills', 'reasoning', 'answers', 'toolResults']

    /** Normalize a trend row (cumulative per-category tokens) into legend
        entries with shares. */
    function compositionOf(row) {
      var total = 0
      var entries = CATEGORY_ORDER.map(function (key) {
        var meta = CATEGORY_META[key]
        var tokens = Math.max(0, Number(row[key]) || 0)
        total += tokens
        return { key: key, label: meta.label, colorVar: meta.colorVar, tokens: tokens }
      })
      entries.forEach(function (e) { e.share = total > 0 ? e.tokens / total : 0 })
      return { total: total, entries: entries }
    }

    /* --------------------------------------------------------------------
     * Cards — each answers one dashboard question (dsh-context's rule)
     * ------------------------------------------------------------------ */
    function StatsBand(props) {
      var s = props.stats
      var occupancy = props.session && props.session.windowTokens > 0
        ? (props.lastTotal || 0) / props.session.windowTokens
        : 0
      var kpis = [
        ['Occupancy', fmtPct(occupancy)],
        ['Turns', String(s.turns)],
        ['Steps', String(s.steps)],
        ['Tool calls', String(s.toolCalls)],
        ['Active time', fmtDuration(s.activeMs)],
        ['Est. cost', fmtUsd(s.costUsd)],
        ['Cache hit', fmtPct(s.cacheHitRate)]
      ]
      return h('div', { className: 'ctxd-kpis' },
        kpis.map(function (k) {
          return h('div', { key: k[0], className: 'ctxd-kpi' },
            h('div', { className: 'ctxd-kpiValue' }, k[1]),
            h('div', { className: 'ctxd-kpiLabel' }, k[0]))
        }))
    }

    function CompositionCard(props) {
      var comp = compositionOf(props.row)
      if (comp.total === 0) return h(Card, { title: 'Current composition' }, h(Empty, null, 'No composition data.'))
      return h(Card, { title: 'Current composition' },
        h(StackedBar, { entries: comp.entries }),
        h(Legend, { entries: comp.entries }))
    }

    /** Per-step stacked bars, one column per model request. mode 'total'
        draws each step's cumulative makeup; mode 'delta' draws the signed
        change vs the previous step — compactions dive below the baseline and
        render dimmed, like dsh-context's Delta view. */
    function TrendCard(props) {
      var trend = props.trend
      var modePair = react.useState('total')
      var mode = modePair[0]
      var setMode = modePair[1]
      if (!trend.length) return h(Card, { title: 'Context trend' }, h(Empty, null, 'No trend data.'))

      var cols = trend.map(function (row, i) {
        var prev = i > 0 ? trend[i - 1] : null
        var signed = CATEGORY_ORDER.map(function (key) {
          var now = Math.max(0, Number(row[key]) || 0)
          var before = prev ? Math.max(0, Number(prev[key]) || 0) : 0
          return { key: key, tokens: mode === 'delta' ? now - before : now }
        })
        var total = signed.reduce(function (acc, e) { return acc + e.tokens }, 0)
        return { step: row.step, label: row.label, signed: signed, total: total }
      })
      var scaleMax = 1
      cols.forEach(function (c) {
        c.signed.forEach(function (e) { scaleMax = Math.max(scaleMax, Math.abs(e.tokens)) })
      })

      return h(Card, { title: 'Context trend' },
        h('div', { className: 'ctxd-chips' },
          h(Chip, { label: 'Total', active: mode === 'total', onClick: function () { setMode('total') } }),
          h(Chip, { label: 'Delta', active: mode === 'delta', onClick: function () { setMode('delta') } })),
        h('div', { className: 'ctxd-trend' },
          cols.map(function (c) {
            var sign = c.total < 0 ? '' : '+'
            return h('div', {
              key: c.step,
              className: 'ctxd-trendCol',
              title: '#' + c.step + ' ' + c.label + ' · ' +
                (mode === 'delta' ? sign + fmtTokens(c.total) : fmtTokens(c.total))
            },
            c.signed.map(function (e) {
              if (e.tokens === 0) return null
              var frac = Math.abs(e.tokens) / scaleMax
              var negative = e.tokens < 0
              return h('div', {
                key: e.key,
                style: {
                  height: Math.max(1, frac * 100) + '%',
                  background: 'var(' + CATEGORY_META[e.key].colorVar + ')',
                  opacity: negative ? 0.4 : 1
                }
              })
            }))
          })),
        h('div', { className: 'ctxd-trendSteps' },
          cols.map(function (c) {
            return h('div', { key: c.step, className: 'ctxd-trendStep', title: '#' + c.step + ' ' + c.label }, '#' + c.step)
          })))
    }

    var EVENT_KINDS = ['inject', 'compact', 'prune', 'switch', 'mode']

    function EventsCard(props) {
      var events = props.events
      var filterPair = react.useState(null)
      var filter = filterPair[0]
      var setFilter = filterPair[1]
      if (!events.length) return h(Card, { title: 'Context events' }, h(Empty, null, 'No events.'))
      var counts = {}
      events.forEach(function (e) { counts[e.kind] = (counts[e.kind] || 0) + 1 })
      var shown = filter ? events.filter(function (e) { return e.kind === filter }) : events
      return h(Card, { title: 'Context events' },
        h('div', { className: 'ctxd-chips' },
          EVENT_KINDS.filter(function (k) { return counts[k] }).map(function (k) {
            return h(Chip, {
              key: k,
              label: k.charAt(0).toUpperCase() + k.slice(1),
              count: counts[k],
              active: filter === k,
              onClick: function () { setFilter(filter === k ? null : k) }
            })
          })),
        h('div', { className: 'ctxd-rows' },
          shown.map(function (e, i) {
            var neg = Number(e.deltaTokens) < 0
            return h('div', { key: i, className: 'ctxd-row', title: e.detail || '' },
              h('span', null, e.producer),
              h('span', { className: 'ctxd-rowMeta' },
                h('span', { className: neg ? 'ctxd-deltaNeg' : 'ctxd-deltaPos' },
                  (neg ? '' : '+') + fmtTokens(Number(e.deltaTokens) || 0) + ' tok'),
                ' · turn ' + e.turn + ' · step ' + e.step + ' · ' + e.time))
          })))
    }

    function FilesCard(props) {
      var files = props.files
      if (!files.length) return h(Card, { title: 'File activity' }, h(Empty, null, 'No file activity.'))
      return h(Card, { title: 'File activity' },
        h('div', { className: 'ctxd-rows' },
          files.map(function (f) {
            return h('div', { key: f.path, className: 'ctxd-row', title: f.path },
              h('span', { className: 'ctxd-rowMain' }, f.path),
              h('span', { className: 'ctxd-rowMeta' },
                'R ' + f.reads + ' · W ' + f.writes + ' · S ' + f.searches +
                (f.added || f.removed
                  ? ' · ' + (f.added ? '+' + f.added : '') + (f.added && f.removed ? '/' : '') + (f.removed ? '−' + f.removed : '')
                  : '')))
          })))
    }

    function CommandsCard(props) {
      var commands = props.commands
      if (!commands.length) return h(Card, { title: 'Command executions' }, h(Empty, null, 'No commands ran.'))
      var maxRuns = 1
      commands.forEach(function (c) { maxRuns = Math.max(maxRuns, c.runs) })
      return h(Card, { title: 'Command executions' },
        h('div', { className: 'ctxd-rows' },
          commands.map(function (c) {
            return h('div', { key: c.program, className: 'ctxd-row', title: c.program + ' — ' + c.ok + ' ok, ' + c.failed + ' failed' },
              h('span', {
                style: {
                  width: 9, height: 9, borderRadius: 3, flex: 'none',
                  background: 'var(--ctxd-c-schemas)',
                  opacity: 0.35 + 0.65 * (c.runs / maxRuns)
                }
              }),
              h('span', { className: 'ctxd-rowMain' }, c.program),
              h('span', { className: 'ctxd-rowMeta' },
                c.runs + ' runs · ' + fmtDuration(c.totalMs) + (c.failed ? ' · ' + c.failed + ' failed' : '')))
          })))
    }

    /* --------------------------------------------------------------------
     * Fleet — the agent family (current agent, parents, subagents)
     * ------------------------------------------------------------------ */
    function AgentCard(props) {
      var a = props.agent
      return h('div', { className: 'ctxd-agent' },
        h('div', { className: 'ctxd-agentTitle' },
          h(Dot, { status: a.status }),
          h('span', null, a.title),
          h('span', { className: 'ctxd-rowMeta' }, a.role)),
        h('div', { className: 'ctxd-track' },
          h('div', { className: 'ctxd-fill', style: { width: Math.min(100, (a.occupancy || 0) * 100).toFixed(1) + '%' } })),
        h('div', { className: 'ctxd-agentMeta' },
          h('span', null, fmtTokens(a.contextTokens) + ' tok · ' + fmtPct(a.occupancy)),
          h('span', null, a.steps + ' steps · ' + fmtDuration(a.runtimeMs)),
          a.parent ? h('span', null, '↑ ' + a.parent) : null))
    }

    function FleetView() {
      var shared = useDashboardData()
      var data = shared.state.data
      if (shared.state.config.enableFleetTab === false) return h(Disabled, { name: 'Fleet tab' })
      var agents = data.agents || []
      var running = agents.filter(function (a) { return a.status === 'running' }).length
      return h('div', { className: 'ctxd-root' },
        h('div', { className: 'ctxd-head' },
          h('span', { className: 'ctxd-title' }, 'Fleet'),
          h('span', { className: 'ctxd-sub' }, agents.length + ' agents · ' + running + ' running'),
          h('span', { className: 'ctxd-actions' },
            h('button', { className: 'ctxd-btn', onClick: shared.refresh }, 'Refresh'))),
        shared.state.loading ? h('div', { className: 'ctxd-notice' }, 'Loading fleet data…') : null,
        shared.state.error ? h('div', { className: 'ctxd-notice' }, shared.state.error) : null,
        data.source === 'demo' ? h('div', { className: 'ctxd-notice' }, 'Demo data — ' + (data.notice || 'synthetic dataset.')) : null,
        agents.length === 0
          ? h(Card, { title: 'Agent network' }, h(Empty, null, 'No agent data.'))
          : h('div', { className: 'ctxd-agents' }, agents.map(function (a) {
              return h(AgentCard, { key: a.id, agent: a })
            })),
        h(Card, { title: 'Cross-agent collaboration' },
          h(Empty, null, 'Skeleton: add a lane timeline of inter-agent messages, team tasks, and delegation records here.')))
    }

    /* --------------------------------------------------------------------
     * The dashboard — composition of the cards above
     * ------------------------------------------------------------------ */
    function DashboardView(props) {
      var shared = useDashboardData()
      var state = shared.state
      var data = state.data
      if (state.config.enableTab === false) return h(Disabled, { name: 'Context tab' })
      var lastRow = data.trend && data.trend.length ? data.trend[data.trend.length - 1] : null
      var lastComp = lastRow ? compositionOf(lastRow) : { total: 0 }
      var session = data.session || FALLBACK_DATA.session

      return h('div', { className: 'ctxd-root' },
        h('div', { className: 'ctxd-head' },
          h('span', { className: 'ctxd-title' }, 'Context'),
          h('span', { className: 'ctxd-sub' },
            (session.title ? session.title + ' · ' : '') +
            (session.model ? session.model + ' · ' : '') +
            fmtTokens(lastComp.total) + ' / ' + fmtTokens(session.windowTokens) + ' window'),
          h('span', { className: 'ctxd-actions' },
            h('button', { className: 'ctxd-btn', onClick: props.onOpenModal }, 'Expand'),
            h('button', { className: 'ctxd-btn', onClick: shared.refresh }, 'Refresh'))),
        state.loading ? h('div', { className: 'ctxd-notice' }, 'Loading dashboard data…') : null,
        state.error ? h('div', { className: 'ctxd-notice' }, state.error) : null,
        data.source === 'demo'
          ? h('div', { className: 'ctxd-notice' }, 'Demo data — ' + (data.notice || 'synthetic dataset.'))
          : null,
        h(StatsBand, { stats: data.stats, session: session, lastTotal: lastComp.total }),
        h(CompositionCard, { row: lastRow || {} }),
        h(TrendCard, { trend: data.trend || [] }),
        h(EventsCard, { events: data.events || [] }),
        h(FilesCard, { files: data.files || [] }),
        h(CommandsCard, { commands: data.commands || [] }))
    }

    /* --------------------------------------------------------------------
     * Modal — the /context target (portal overlay, Esc and backdrop close)
     * ------------------------------------------------------------------ */
    function makeRoot(host) {
      try {
        var client = require('react-dom/client')
        var root = client.createRoot(host)
        return { render: function (el) { root.render(el) }, unmount: function () { root.unmount() } }
      } catch (err) {
        var dom = require('react-dom')
        return {
          render: function (el) { dom.render(el, host) },
          unmount: function () { dom.unmountComponentAtNode(host) }
        }
      }
    }

    function openContextModal() {
      if (typeof document === 'undefined') return
      if (document.getElementById(MODAL_ID)) return
      var host = document.createElement('div')
      host.id = MODAL_ID
      document.body.appendChild(host)
      var root = makeRoot(host)

      function close() {
        try { root.unmount() } catch (err) { /* already gone */ }
        if (host.parentNode) host.parentNode.removeChild(host)
        document.removeEventListener('keydown', onKey, true)
      }
      function onKey(e) { if (e.key === 'Escape') close() }
      document.addEventListener('keydown', onKey, true)

      function Modal() {
        var shared = useDashboardData()
        return h('div', {
          className: 'ctxd-modalBack',
          onClick: function (e) { if (e.target === e.currentTarget) close() }
        }, h('div', { className: 'ctxd-modal' },
          h(DashboardView, { onOpenModal: close })))
      }
      root.render(h(Modal, {}))
    }

    /* --------------------------------------------------------------------
     * Surface 3 — the /context command
     * ------------------------------------------------------------------ */
    function registerCommand(ctx) {
      var triggers = ctx.inputTriggers || (typeof ctx.get === 'function' ? ctx.get('inputTriggers') : undefined)
      if (!triggers || typeof triggers.registerSource !== 'function') {
        console.warn('[' + NS + '] inputTriggers unavailable — /context command not registered')
        return
      }
      var COMMAND = 'context'
      ctx.effect(function () {
        return triggers.registerSource({
          trigger: '/',
          name: COMMAND,
          order: 1,
          candidates: function (_session, req) {
            if (req.position !== 'leading') return Promise.resolve([])
            var query = String(req.query || '').trim().toLowerCase()
            if (query !== '' && COMMAND.indexOf(query) !== 0) return Promise.resolve([])
            return Promise.resolve([{
              name: COMMAND,
              label: 'Context dashboard',
              section: 'Plugins',
              description: 'Show the context model for the current conversation.'
            }])
          },
          onPick: function () {
            openContextModal()
            return 'handled'
          },
          matchEnter: function (_session, line) {
            if (line !== '/' + COMMAND) return Promise.resolve(undefined)
            openContextModal()
            return Promise.resolve('handled')
          }
        })
      }, NS + ': /context command')
    }

    /* --------------------------------------------------------------------
     * Surfaces 1 & 2 — the Context and Fleet conversation tabs
     * ------------------------------------------------------------------ */
    function registerConversationTabs(ctx) {
      /* The slot hands the renderer session props; the skeleton treats them as
         opaque and reads its own data feed instead. A real feed can key its
         dataset off the props (session id) here. */
      ctx.slots.inject('conversation.view', function () {
        return ctx.slots.register(
          { name: 'conversation.view', id: NS + ':context', order: 20, label: 'Context' },
          function () { return h(DashboardView, { onOpenModal: openContextModal }) })
      })
      ctx.slots.inject('conversation.view', function () {
        return ctx.slots.register(
          { name: 'conversation.view', id: NS + ':fleet', order: 21, label: 'Fleet' },
          function () { return h(FleetView, {}) })
      })
    }

    /* --------------------------------------------------------------------
     * Surface 4 — the right-sidebar Context panel
     * ------------------------------------------------------------------ */
    function registerSidebarPanel(ctx) {
      try {
        ctx.inject(['sidebarRightTabs', 'sidebarRight'], function (innerCtx) {
          var tabs = innerCtx.sidebarRightTabs
          if (!tabs || typeof tabs.register !== 'function') return
          innerCtx.effect(function () {
            return tabs.register({
              id: NS + ':panel',
              kind: NS + '-context-panel',
              keepMounted: false,
              priority: 'extension',
              title: function () { return 'Context' },
              guide: [{
                id: NS + '-context-panel',
                order: 60,
                title: function () { return 'Context' },
                description: function () { return 'Context composition and trend for the current session.' }
              }]
            })
          }, NS + ': sidebar tab type')
          innerCtx.slots.inject('sidebar.right.pane.tab', function () {
            return innerCtx.slots.register(
              { name: 'sidebar.right.pane.tab', key: NS + ':panel' },
              function () {
                return h('div', { style: { height: '100%', minHeight: 0, overflow: 'auto' } },
                  h(DashboardView, { onOpenModal: openContextModal }))
              })
          })
        })
      } catch (err) {
        console.warn('[' + NS + '] sidebar panel unavailable: ' + String(err && err.message ? err.message : err))
      }
    }

    /* --------------------------------------------------------------------
     * Surface 5 — the settings page
     * ------------------------------------------------------------------ */
    function SettingRow(props) {
      return h('label', { className: 'ctxd-row' },
        h('input', {
          type: 'checkbox',
          checked: props.value === true,
          onChange: function (e) { props.onChange(e.target.checked) }
        }),
        h('span', null, props.label))
    }

    function registerSettingsPage(ctx) {
      ctx.slots.inject('settings.section', function () {
        return ctx.slots.register(
          { name: 'settings.section', id: NS, order: 30, label: 'Context Dashboard' },
          function () {
            var draftPair = react.useState(null)
            var draft = draftPair[0]
            var setDraft = draftPair[1]
            var noticePair = react.useState('')
            var notice = noticePair[0]
            var setNotice = noticePair[1]

            react.useEffect(function () {
              fetch(API_CONFIG, { headers: { Accept: 'application/json' } })
                .then(function (r) { return r.json() })
                .then(function (j) {
                  if (j && j.ok === true) setDraft(Object.assign({}, FALLBACK_CONFIG, j.config))
                  else setDraft(Object.assign({}, FALLBACK_CONFIG))
                })
                .catch(function () { setDraft(Object.assign({}, FALLBACK_CONFIG)) })
            }, [])

            function save(next) {
              setDraft(next)
              fetch(API_CONFIG, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ patch: next })
              }).then(function (r) { return r.json() })
                .then(function (j) {
                  setNotice(j && j.ok === true
                    ? 'Saved. Reload the page to apply surface changes.'
                    : 'Save failed: ' + ((j && j.error) || 'unknown error'))
                })
                .catch(function (e) { setNotice('Save failed: ' + String(e && e.message ? e.message : e)) })
            }

            if (!draft) return h('div', { className: 'ctxd-empty' }, 'Loading dashboard settings…')
            return h('div', { className: 'ctxd-root', style: { height: 'auto', overflow: 'visible' } },
              h(Card, { title: 'Context Dashboard surfaces' },
                h(SettingRow, { label: 'Context tab (dashboard)', value: draft.enableTab, onChange: function (v) { save(Object.assign({}, draft, { enableTab: v })) } }),
                h(SettingRow, { label: 'Fleet tab (agent family)', value: draft.enableFleetTab, onChange: function (v) { save(Object.assign({}, draft, { enableFleetTab: v })) } }),
                h(SettingRow, { label: 'Right-sidebar Context panel', value: draft.enableSidebarPanel, onChange: function (v) { save(Object.assign({}, draft, { enableSidebarPanel: v })) } }),
                h(SettingRow, { label: '/context command', value: draft.enableCommand, onChange: function (v) { save(Object.assign({}, draft, { enableCommand: v })) } }),
                h(SettingRow, { label: 'Serve the demo dataset (demoMode)', value: draft.demoMode, onChange: function (v) { save(Object.assign({}, draft, { demoMode: v })) } }),
                notice ? h('div', { className: 'ctxd-empty' }, notice) : null,
                h('div', { className: 'ctxd-empty' },
                  'Config persists to $DSH_HOME/dsh-context-dashboard-template.json. Switch surfaces off here instead of deleting code.')))
          })
      })
    }

    /* --------------------------------------------------------------------
     * apply — mount the always-on surfaces, then config-gate the rest
     * ------------------------------------------------------------------ */
    var inject = ['slots', 'inputTriggers', 'sidebarRightTabs']

    function apply(ctx) {
      registerConversationTabs(ctx)
      registerSettingsPage(ctx)

      /* The command and the sidebar panel mount only when the Host config
         enables them; the config route is fetched once at startup. */
      fetch(API_CONFIG, { headers: { Accept: 'application/json' } })
        .then(function (r) { return r.json() })
        .then(function (j) {
          var config = j && j.ok === true && j.config ? Object.assign({}, FALLBACK_CONFIG, j.config) : FALLBACK_CONFIG
          if (config.enableCommand !== false) registerCommand(ctx)
          if (config.enableSidebarPanel === true) registerSidebarPanel(ctx)
        })
        .catch(function () { registerCommand(ctx) })
    }

    exports.apply = apply
    exports.inject = inject
    return module.exports
  }
})
