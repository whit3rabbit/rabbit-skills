/**
 * Client entry template for DSH Sidebar & Settings UI extensions.
 *
 * Purity gate rules:
 * 1. Only runtime-import packages from `CLIENT_EXTERNALS`:
 *    `react`, `react/jsx-runtime`, `react-dom`, `react-dom/client`, `cordis`,
 *    `@deepseek-ai/dsh-client-ui-slots`, `@deepseek-ai/dsh-client-ui-primitives`.
 * 2. Use `import type` for `@deepseek-ai/dsh-client-ui-sidebar-right`,
 *    `@deepseek-ai/dsh-client-ui-settings`, and `dsh-better-sidebar` so their
 *    types merge into `cordis.Context` and `SlotRegistry` without emitting
 *    runtime module imports.
 */

import type {} from '@deepseek-ai/dsh-client-ui-settings'
import type {} from '@deepseek-ai/dsh-client-ui-sidebar-right'
import type {} from 'dsh-better-sidebar/client/service'

import {
  Button,
  IconCodeOutlineRegular,
  IconPanelLeftOutlineRegular,
  IconRefreshOutlineRegular,
  IconSettingsOutlineRegular,
  Input,
  SegmentedControl,
  StateDot,
  Tooltip,
} from '@deepseek-ai/dsh-client-ui-primitives'
import type { SettingsSectionIconOwnerProps } from '@deepseek-ai/dsh-client-ui-settings'
import type {
  SidebarRightPaneTabOwnerProps,
  SidebarRightPaneTabTitleOwnerProps,
} from '@deepseek-ai/dsh-client-ui-sidebar-right'
import { useInjected } from '@deepseek-ai/dsh-client-ui-slots'
import type { Context } from 'cordis'
import type {
  BetterSidebarService,
  FileViewerProps,
  TabComponentProps,
} from 'dsh-better-sidebar/client/service'
import { useEffect, useState } from 'react'
import {
  Chip,
  ConfirmDialog,
  FeatureCard,
  IconButton,
  Notice,
  SectionHeader,
  SelectMenu,
  StatusBadge,
  Switch,
} from './ui-kit'
import s from './ui-kit.module.css'

export const name = 'sidebar-template-client'

/**
 * Declare required services in `inject` (module level — the Loader wires them
 * before `apply` runs). If your plugin only targets `dsh-better-sidebar`, use
 * `export const inject = ['betterSidebar']`. Here we declare the stock web
 * seats and read `betterSidebar` (the optional extension) with `ctx.get`,
 * so the template works in both setups.
 */
export const inject = ['slots', 'sidebarRight', 'sidebarRightTabs']

const BETTER_SIDEBAR_TAB_ID = 'sidebar-template:inspector'
const NATIVE_TAB_KEY = 'sidebar-template:inspector'
const NATIVE_TAB_KIND = 'sidebar-template-inspector'
const SETTINGS_SECTION_ID = 'sidebar-template-settings'

// ---------------------------------------------------------------------------
// Shared Tab Body Component (works in both Better Sidebar & Native Sidebar)
// ---------------------------------------------------------------------------

interface InspectorPanelProps {
  sessionId: string
  visible: boolean
  betterSidebar?: BetterSidebarService
}

function InspectorPanel({ sessionId, visible, betterSidebar }: InspectorPanelProps) {
  const [mode, setMode] = useState<'events' | 'metrics'>('events')
  const [filter, setFilter] = useState<'all' | 'warn' | 'error'>('all')
  const [confirmResetOpen, setConfirmResetOpen] = useState(false)
  const [tick, setTick] = useState(0)

  // Always gate polling, timers, and WebSocket subscriptions on `visible`
  // so hidden kept-mounted tabs consume zero background CPU/network.
  useEffect(() => {
    if (!visible) return
    const timer = window.setInterval(() => {
      setTick((prev) => prev + 1)
    }, 10_000)
    return () => window.clearInterval(timer)
  }, [visible])

  // When calling custom Host HTTP routes, resolve via `hostRouteUrl(...)`
  // (never hardcode a leading `/` like `fetch('/sidebar-template/api/...')`).
  const prefsUrl = betterSidebar
    ? betterSidebar.hostRouteUrl('sidebar-template/api/prefs')
    : 'sidebar-template/api/prefs'

  return (
    <div className={s.tabRoot}>
      <SectionHeader
        label="Session Inspector"
        count={3}
        action={
          <>
            <Tooltip content={`Refresh (${prefsUrl})`}>
              <IconButton
                size="sm"
                aria-label="Refresh inspector"
                onClick={() => setTick((prev) => prev + 1)}
              >
                <IconRefreshOutlineRegular size={14} />
              </IconButton>
            </Tooltip>
            <Tooltip content="Reset state">
              <IconButton
                size="sm"
                danger
                aria-label="Reset inspector state"
                onClick={() => setConfirmResetOpen(true)}
              >
                <IconSettingsOutlineRegular size={14} />
              </IconButton>
            </Tooltip>
          </>
        }
      />

      <div className={s.tabBodyScroll}>
        <SegmentedControl
          ariaLabel="Inspector view mode"
          value={mode}
          onChange={(next) => setMode(next as 'events' | 'metrics')}
          options={[
            { value: 'events', label: 'Events' },
            { value: 'metrics', label: 'Metrics' },
          ]}
        />

        <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
          <Chip active={filter === 'all'} count={3} onClick={() => setFilter('all')}>
            All
          </Chip>
          <Chip active={filter === 'warn'} count={1} onClick={() => setFilter('warn')}>
            Warnings
          </Chip>
          <Chip active={filter === 'error'} count={0} onClick={() => setFilter('error')}>
            Errors
          </Chip>
        </div>

        {mode === 'events' ? (
          <Notice
            kind="hint"
            tone="well"
            title={
              <span style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }}>
                <StateDot state="success" />
                <span>Session {sessionId || 'global'} active</span>
                <StatusBadge tone="info">poll #{tick}</StatusBadge>
              </span>
            }
            detail="Replace this block with your domain tree, live trace stream, or resource cards."
          />
        ) : (
          <Notice
            kind="empty"
            tone="page"
            title="No metrics recorded yet"
            detail="Trigger a tool call in the active session to populate metrics."
          />
        )}
      </div>

      <ConfirmDialog
        open={confirmResetOpen}
        title="Reset Inspector State?"
        description="This clears local inspector counters for the active session."
        confirmLabel="Reset"
        onConfirm={() => setTick(0)}
        onClose={() => setConfirmResetOpen(false)}
      />
    </div>
  )
}

// ---------------------------------------------------------------------------
// Custom File Viewer Component (for `ctx.betterSidebar.registerFileViewer`)
// ---------------------------------------------------------------------------

function TraceLogViewer({ path, content }: FileViewerProps) {
  const lines = (content ?? '').split('\n').filter(Boolean)
  return (
    <div className={s.tabRoot}>
      <SectionHeader label={path} count={lines.length} />
      <div className={s.tabBodyScroll}>
        {lines.length === 0 ? (
          <Notice kind="empty" tone="page" title="Empty trace log" />
        ) : (
          lines.map((line, idx) => (
            <div key={idx} className={s.noticeInline}>
              <StatusBadge tone={line.includes('ERROR') ? 'error' : 'info'}>
                #{idx + 1}
              </StatusBadge>{' '}
              <span>{line}</span>
            </div>
          ))
        )}
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Custom Settings Shell Page (for `settings.section` slot)
// ---------------------------------------------------------------------------

function SidebarTemplateSettingsPage() {
  const [inspectorEnabled, setInspectorEnabled] = useState(true)
  const [headerToggleEnabled, setHeaderToggleEnabled] = useState(true)
  const [defaultDock, setDefaultDock] = useState('right')
  const [pollSeconds, setPollSeconds] = useState('10')

  return (
    <div className={s.settingsPage}>
      <section>
        <h3 className={s.groupTitle}>Sidebar Features</h3>
        <div className={s.featureGrid}>
          <FeatureCard
            title="Session Inspector"
            description="Live event and metric inspector in the right sidebar or bottom dock."
            enabled={inspectorEnabled}
            onToggle={setInspectorEnabled}
            onOpenSettings={() => {}}
          />
          <FeatureCard
            title="Header Quick Toggle"
            description="Pin a one-click utility button in the conversation session header."
            enabled={headerToggleEnabled}
            onToggle={setHeaderToggleEnabled}
          />
        </div>
      </section>

      <section>
        <h3 className={s.groupTitle}>Behavior & Defaults</h3>
        <div className={s.groupCard}>
          <div className={s.settingRow}>
            <div className={s.settingCopy}>
              <span className={s.settingLabel}>Default Dock Target</span>
              <span className={s.settingDesc}>
                Choose whether new Inspector tabs open in the right sidebar or bottom workbench.
              </span>
            </div>
            <SelectMenu
              value={defaultDock}
              onSelect={setDefaultDock}
              items={[
                { id: 'right', label: 'Right Sidebar' },
                { id: 'bottom', label: 'Bottom Workbench' },
              ]}
            />
          </div>

          <div className={s.settingRow}>
            <div className={s.settingCopy}>
              <span className={s.settingLabel}>Refresh Interval (seconds)</span>
              <span className={s.settingDesc}>
                Background polling interval while the tab is visible in the active pane.
              </span>
            </div>
            <div style={{ width: 96 }}>
              <Input
                type="number"
                value={pollSeconds}
                onChange={(e) => setPollSeconds(e.target.value)}
              />
            </div>
          </div>

          <div className={s.settingRow}>
            <div className={s.settingCopy}>
              <span className={s.settingLabel}>Auto-reveal on Warnings</span>
              <span className={s.settingDesc}>
                Automatically focus the Inspector tab when a tool emits a warning.
              </span>
            </div>
            <Switch
              checked={inspectorEnabled}
              onChange={setInspectorEnabled}
              ariaLabel="Toggle auto-reveal on warnings"
            />
          </div>
        </div>
      </section>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Plugin Entry (`apply`) — 4 Modular UI Placement Recipes
// ---------------------------------------------------------------------------

export function apply(ctx: Context): void {
  // =========================================================================
  // RECIPE 1: `dsh-better-sidebar` Extension (`ctx.get('betterSidebar')`)
  // Use when building a tab, file viewer, or declarative settings card inside
  // the `dsh-better-sidebar` workbench (right panel + bottom dock). The
  // extension is an optional peer: skip the recipe entirely when it is not
  // mounted instead of declaring a hard dependency on it.
  // =========================================================================
  const betterSidebar = ctx.get('betterSidebar') as BetterSidebarService | undefined
  if (betterSidebar) {
    ctx.effect(() => {
      const disposeTab = betterSidebar.registerTab({
        id: BETTER_SIDEBAR_TAB_ID,
        title: 'Inspector',
        description: 'Inspect session events, tool calls, and live metrics.',
        icon: <IconCodeOutlineRegular size={16} />,
        order: 60,
        single: true,
        // Set `bottomOnly: true` if this tab should only dock in the bottom
        // workbench (like Terminal / Editor) and never in the right sidebar.
        bottomOnly: false,
        settings: {
          // Declarative settings rendered automatically in the feature's gear
          // modal inside the "Side card" settings page:
          pluginToggles: [
            {
              key: 'autoReveal',
              title: 'Auto-reveal on warnings',
              desc: 'Open the Inspector tab when a tool call reports a warning.',
              type: 'switch',
            },
            {
              key: 'refreshIntervalSec',
              title: 'Refresh interval',
              desc: 'Polling interval while the tab is visible.',
              type: 'number',
              min: 1,
              max: 300,
              unit: 's',
            },
            {
              key: 'defaultFilter',
              title: 'Default event filter',
              desc: 'Initial filter chip selected when the tab mounts.',
              type: 'select',
              options: [
                { value: 'all', title: 'All events' },
                { value: 'warn', title: 'Warnings only' },
                { value: 'error', title: 'Errors only' },
              ],
            },
            {
              key: 'ignoredGlobs',
              title: 'Ignored paths',
              desc: 'One glob pattern per line.',
              type: 'patterns',
              patternsPlaceholder: 'node_modules\n.git',
            },
          ],
          // Optional custom React footer inside the feature's gear modal:
          render: ({ pluginSettings, updatePluginSetting, close }) => (
            <div style={{ display: 'flex', justifyContent: 'space-between', paddingTop: 8 }}>
              <StatusBadge tone="info">
                Filter: {String(pluginSettings.defaultFilter ?? 'all')}
              </StatusBadge>
              <Button
                variant="outline"
                onClick={() => {
                  updatePluginSetting('defaultFilter', 'all')
                  close()
                }}
              >
                Reset & Close
              </Button>
            </div>
          ),
        },
        component: ({ scope, visible }: TabComponentProps) => (
          <InspectorPanel
            sessionId={scope}
            visible={visible}
            betterSidebar={betterSidebar}
          />
        ),
      })

      // Register a custom file viewer for `.log` and `.trace` files.
      // Note: Office/PDF/image extensions (`HOST_OWNED_EXTS`) are yielded to
      // DSH's native `ui-sidebar-documentpreview` and cannot be overridden here.
      const disposeViewer = betterSidebar.registerFileViewer({
        id: 'sidebar-template:trace-viewer',
        title: 'Trace Log',
        icon: <IconCodeOutlineRegular size={14} />,
        exts: ['log', 'trace'],
        priority: 10,
        fetchStrategy: 'fsRead',
        component: TraceLogViewer,
      })

      return () => {
        disposeTab()
        disposeViewer()
      }
    }, 'sidebar-template: better-sidebar tab + viewer')
  }

  // =========================================================================
  // RECIPE 2: Native DSH Right Sidebar (`ctx.sidebarRightTabs` + `ctx.slots`)
  // Use when targeting stock DSH (`@deepseek-ai/dsh-client-ui-sidebar-right`)
  // without requiring `dsh-better-sidebar`.
  // =========================================================================
  {
    // 2a. Register the tab type and "+ New Tab" guide card (`MAX_DESCRIBED_ENTRIES = 4`)
    ctx.effect(() =>
      ctx.sidebarRightTabs.register({
        id: NATIVE_TAB_KEY,
        kind: NATIVE_TAB_KIND,
        keepMounted: true,
        priority: 'extension',
        title: () => 'Inspector',
        guide: [
          {
            id: NATIVE_TAB_KIND,
            order: 60,
            title: () => 'Inspector',
            description: () => 'Inspect live session events and metrics.',
            icon: ({ size = 16 }) => <IconCodeOutlineRegular size={size} />,
          },
        ],
      }),
    )

    // 2b. Register the tab body slot (`key` must match `id` in `sidebarRightTabs.register`)
    ctx.slots.inject('sidebar.right.pane.tab', () =>
      ctx.slots.register(
        {
          name: 'sidebar.right.pane.tab',
          key: NATIVE_TAB_KEY,
          inject: (sessionId: string) => ({ sessionId }),
        },
        function NativeInspectorTabBody(props: SidebarRightPaneTabOwnerProps) {
          const { sessionId } = useInjected<{ sessionId: string }>()
          return (
            <InspectorPanel
              sessionId={sessionId || props.sessionId}
              visible={true}
            />
          )
        },
      ),
    )

    // 2c. Optional custom tab chip title slot in the pane header bar
    ctx.slots.inject('sidebar.right.pane.tab.title', () =>
      ctx.slots.register(
        {
          name: 'sidebar.right.pane.tab.title',
          key: NATIVE_TAB_KEY,
        },
        function NativeInspectorTabTitle(_props: SidebarRightPaneTabTitleOwnerProps) {
          return (
            <span style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }}>
              <IconCodeOutlineRegular size={14} />
              <span>Inspector</span>
            </span>
          )
        },
      ),
    )
  }

  // =========================================================================
  // RECIPE 3: Session Header Utility Button (`conversation.session.header.utilities`)
  // Places a quick-toggle button right beside the Session Log capsule in the
  // top-right session header. (`conversation.session.header.corner` is a single
  // slot owned by the native right-sidebar toggle — always use `.utilities`.)
  // =========================================================================
  ctx.slots.inject('conversation.session.header.utilities', () =>
    ctx.slots.register(
      {
        name: 'conversation.session.header.utilities',
        id: 'sidebar-template-header-toggle',
        order: 50,
      },
      function HeaderInspectorToggle() {
        return (
          <Tooltip content="Open Session Inspector">
            <IconButton
              size="sm"
              aria-label="Open Session Inspector"
              onClick={() => {
                const extension = ctx.get('betterSidebar') as BetterSidebarService | undefined
                if (extension) {
                  extension.openTab({
                    type: BETTER_SIDEBAR_TAB_ID,
                    target: 'right',
                    reveal: true,
                  })
                } else {
                  ctx.sidebarRight.openTab(NATIVE_TAB_KIND, {
                    revealIfOpened: true,
                  })
                }
              }}
            >
              <IconPanelLeftOutlineRegular size={14} />
            </IconButton>
          </Tooltip>
        )
      },
    ),
  )

  // =========================================================================
  // RECIPE 4: Dedicated Settings Shell Section (`settings.section` + `.icon`)
  // Adds a top-level section in the DSH Settings navigation rail. Pair with
  // `ctx.settings.configure({ auto: false }, ctx.fiber)` on the Host entry so
  // DSH does not also render a duplicate auto-generated schema card.
  // =========================================================================
  ctx.slots.inject('settings.section.icon', () =>
    ctx.slots.register(
      {
        name: 'settings.section.icon',
        id: SETTINGS_SECTION_ID,
        order: 85,
        label: () => 'Sidebar Template',
      },
      ({ size }: SettingsSectionIconOwnerProps) => (
        <IconPanelLeftOutlineRegular size={size} />
      ),
    ),
  )

  ctx.slots.inject('settings.section', () =>
    ctx.slots.register(
      {
        name: 'settings.section',
        id: SETTINGS_SECTION_ID,
        order: 85,
        label: () => 'Sidebar Template',
      },
      SidebarTemplateSettingsPage,
    ),
  )
}
