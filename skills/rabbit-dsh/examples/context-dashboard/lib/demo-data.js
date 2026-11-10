/* ============================================================================
 * context-dashboard-template — demo dataset
 * ----------------------------------------------------------------------------
 * The skeleton data feed. Every figure here is SYNTHETIC: it exists so the
 * dashboard renders before any real data source is wired, and so the shape
 * contract between Host and Client is executable documentation.
 *
 * The category keys mirror the dsh-context token model (system prompt, tool
 * schemas, user messages, injected context, skill injections, tool calls,
 * reasoning, answers, tool results) so swapping in real data later does not
 * move the UI. See "Wire real data" in README.md.
 *
 * Replace this module's export (or serve your own object from the Host's
 * /context-dashboard/data.json route) when a real source is connected. The
 * `source: 'demo'` marker is what the dashboard's demo banner keys on.
 * ========================================================================== */

export const demoDataset = {
  source: 'demo',
  notice: 'Synthetic demo dataset — replace lib/demo-data.js or the Host data route with a real session source.',
  generatedAt: '2026-11-09T10:24:00Z',

  session: {
    id: 'demo-session-01',
    title: 'Refactor the ingest pipeline',
    model: 'deepseek-v4',
    windowTokens: 128000,
    reservedTokens: 8192
  },

  /* Headline counters for the Context Stats card. costUsd and cacheHitRate are
     estimates; real feeds should compute them the way dsh-context does (models.dev
     list prices; DeepSeek peak windows bill at 2x the listed off-peak rates). */
  stats: {
    turns: 14,
    steps: 37,
    humanInputs: 9,
    toolCalls: 52,
    activeMs: 1_512_000,
    costUsd: 0.83,
    cacheHitRate: 0.71
  },

  /* Where the billed tokens went. Order = draw order in the stacked bar. */
  composition: [
    { key: 'system', label: 'System prompt', tokens: 4200 },
    { key: 'toolSchemas', label: 'Tool schemas', tokens: 9800 },
    { key: 'user', label: 'User messages', tokens: 3100 },
    { key: 'injected', label: 'Injected context', tokens: 6400 },
    { key: 'skills', label: 'Skill injections', tokens: 5100 },
    { key: 'reasoning', label: 'Reasoning', tokens: 18700 },
    { key: 'answers', label: 'Answers', tokens: 12300 },
    { key: 'toolResults', label: 'Tool results', tokens: 27900 }
  ],

  /* One entry per model request (a "step"), cumulative totals per category.
     The client derives per-step deltas from these for Delta mode. */
  trend: [
    { step: 1, label: 'Read the repo map', system: 4200, toolSchemas: 9800, user: 900, injected: 0, skills: 0, reasoning: 400, answers: 300, toolResults: 1800 },
    { step: 2, label: 'Locate the ingest entry point', system: 4200, toolSchemas: 9800, user: 1400, injected: 0, skills: 0, reasoning: 900, answers: 500, toolResults: 3600 },
    { step: 3, label: 'Open pipeline.ts', system: 4200, toolSchemas: 9800, user: 1400, injected: 1200, skills: 0, reasoning: 1600, answers: 700, toolResults: 5900 },
    { step: 4, label: 'Trace the writer path', system: 4200, toolSchemas: 9800, user: 1900, injected: 1200, skills: 0, reasoning: 2400, answers: 900, toolResults: 8100 },
    { step: 5, label: 'Plan the refactor', system: 4200, toolSchemas: 9800, user: 1900, injected: 1200, skills: 5100, reasoning: 3900, answers: 1600, toolResults: 9400 },
    { step: 6, label: 'Edit pipeline.ts', system: 4200, toolSchemas: 9800, user: 2400, injected: 1200, skills: 5100, reasoning: 5300, answers: 2100, toolResults: 11600 },
    { step: 7, label: 'Run the test suite', system: 4200, toolSchemas: 9800, user: 2400, injected: 1200, skills: 5100, reasoning: 7100, answers: 2600, toolResults: 14800 },
    { step: 8, label: 'Fix two regressions', system: 4200, toolSchemas: 9800, user: 2900, injected: 1200, skills: 5100, reasoning: 9400, answers: 3300, toolResults: 17600 },
    { step: 9, label: 'Compact + summarize', system: 4200, toolSchemas: 9800, user: 2900, injected: 1200, skills: 5100, reasoning: 6200, answers: 2400, toolResults: 7300 },
    { step: 10, label: 'Re-verify and report', system: 4200, toolSchemas: 9800, user: 3100, injected: 1200, skills: 5100, reasoning: 8300, answers: 2900, toolResults: 11400 }
  ],

  /* Why the window changed. kind drives the filter chips. */
  events: [
    { kind: 'inject', producer: 'AGENTS.md (project instructions)', deltaTokens: 1200, turn: 3, step: 3, time: '10:04:12', detail: 'Workspace instructions joined the system side.' },
    { kind: 'inject', producer: 'skill: rabbit-dsh', deltaTokens: 5100, turn: 5, step: 5, time: '10:07:40', detail: 'Skill load added its SKILL.md body.' },
    { kind: 'prune', producer: 'harness auto-prune', deltaTokens: -900, turn: 6, step: 6, time: '10:09:55', detail: 'Older tool results folded to summaries.' },
    { kind: 'compact', producer: 'auto-compaction', deltaTokens: -11600, turn: 9, step: 9, time: '10:15:02', detail: 'Window crossed 92% of the soft limit.' },
    { kind: 'switch', producer: 'model switch', deltaTokens: 0, turn: 10, step: 10, time: '10:16:18', detail: 'deepseek-v4 → deepseek-v4 (reasoning profile).' }
  ],

  /* One row per touched file, with estimated line deltas for writes. */
  files: [
    { path: 'src/ingest/pipeline.ts', reads: 4, writes: 2, searches: 1, added: 64, removed: 31 },
    { path: 'src/ingest/writer.ts', reads: 2, writes: 1, searches: 0, added: 18, removed: 6 },
    { path: 'test/ingest/pipeline.test.ts', reads: 1, writes: 1, searches: 0, added: 42, removed: 0 },
    { path: 'AGENTS.md', reads: 1, writes: 0, searches: 0, added: 0, removed: 0 },
    { path: 'src/ingest/config.ts', reads: 3, writes: 0, searches: 2, added: 0, removed: 0 }
  ],

  /* Aggregated per program; runs are counted on dispatch like dsh-context. */
  commands: [
    { program: 'node', runs: 9, ok: 8, failed: 1, totalMs: 41_200 },
    { program: 'git', runs: 6, ok: 6, failed: 0, totalMs: 3_100 },
    { program: 'pytest', runs: 3, ok: 2, failed: 1, totalMs: 22_800 },
    { program: 'rg', runs: 5, ok: 5, failed: 0, totalMs: 900 }
  ],

  /* The agent family: the current agent, its parents, and its subagents. */
  agents: [
    { id: 'lead', title: 'Refactor lead', role: 'self', status: 'running', contextTokens: 46_000, occupancy: 0.36, steps: 37, runtimeMs: 1_512_000, parent: null },
    { id: 'explore', title: 'Repo explorer', role: 'subagent', status: 'done', contextTokens: 18_200, occupancy: 0.14, steps: 6, runtimeMs: 96_000, parent: 'lead' },
    { id: 'tests', title: 'Test runner', role: 'subagent', status: 'done', contextTokens: 11_400, occupancy: 0.09, steps: 4, runtimeMs: 61_000, parent: 'lead' },
    { id: 'docs', title: 'Changelog writer', role: 'subagent', status: 'running', contextTokens: 8_900, occupancy: 0.07, steps: 2, runtimeMs: 24_000, parent: 'lead' }
  ]
}

/** Category metadata the client uses for bar colors and delta math. Kept beside
    the dataset so the demo feed and the renderer cannot drift apart. */
export const demoCategories = [
  { key: 'system', colorVar: '--ctxd-c-system' },
  { key: 'toolSchemas', colorVar: '--ctxd-c-schemas' },
  { key: 'user', colorVar: '--ctxd-c-user' },
  { key: 'injected', colorVar: '--ctxd-c-injected' },
  { key: 'skills', colorVar: '--ctxd-c-skills' },
  { key: 'reasoning', colorVar: '--ctxd-c-reasoning' },
  { key: 'answers', colorVar: '--ctxd-c-answers' },
  { key: 'toolResults', colorVar: '--ctxd-c-results' }
]
