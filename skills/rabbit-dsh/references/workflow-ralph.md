# DeepSeek Harness Multi-Agent Workflows & Ralph Loop Guide

This guide covers authoring multi-agent workflows and iterative Ralph loops in DeepSeek Harness (`dsh`).

---

## 1. Mental Models: Workflow vs. Ralph vs. Subagents

| Pattern | Mechanism | Best Used When |
| --- | --- | --- |
| **Direct Subagent** | Single agent call (`ctx.subagent`) | 1 or 2 targeted delegations (e.g. read a file, run a grep). |
| **Workflow** | JS script orchestrating fan-out | Multi-phase pipelines, parallel specialist teams, or deterministic data flow between agents. |
| **Ralph** | Iterative goal rounds with fresh agents | Solving an open-ended goal requiring code, build, test, and fix cycles until verifiable success. |

---

## 2. Workflow Tool Architecture

The workflow tool is backed by `@deepseek-ai/dsh-tool-workflow` and executed by the worker thread engine `dsh-workflow-worker-thread`.

### Invocation Schema
A workflow invocation accepts:
- `meta`: `{ name: string, description: string, phases?: string[] }`
- `script`: Pure JavaScript function body (`async function main(args) { ... }`) executed with top-level await support.
- `args`: Arbitrary JSON object passed to `main(args)`.

### Orchestration Runtime Primitives

Inside the workflow script, the engine injects these global async functions:

1. `agent({ prompt, tools, cwd })`: Runs a single subagent with the specified prompt and tools list, returning `{ status, output, stopReason }`.
2. `parallel([agent(...), agent(...)])`: Runs multiple subagent promises concurrently in worker threads and returns an array of results.
3. `pipeline([fn1, fn2, ...])`: Chains sequential execution passing outputs down the pipe.
4. `phase(name)`: Emits a phase transition event for the Web UI and logger (e.g. `phase('linting')`).
5. `log(message)`: Outputs progress messages to the active session stream.

---

## 3. Ralph Iterative Goal Engine

Ralph (`tool-ralph`) addresses a specific challenge in agentic coding: context degradation across long debugging loops.

### How Ralph Works
Instead of continuing an bloated session transcript, Ralph retains an **immutable goal description** and starts an **independent, fresh Agent instance** in each iteration round:
1. Agent receives the original goal plus notes from the previous round.
2. Agent inspects current repository state, makes edits, and runs tests.
3. Agent checks its own exit condition (e.g. `SUCCESS_ALL_TESTS_PASSED`).
4. If not achieved, round ends, concise findings are persisted, and the next round launches fresh.

### Minimal Ralph Script Structure

```javascript
async function main(args) {
  const goal = args.goal;
  let round = 0;
  let success = false;

  while (!success && round < 10) {
    round++;
    log(`[Ralph] Round ${round}: launching fresh solver...`);
    const result = await agent({
      prompt: `Round ${round} of goal: ${goal}.
Run the tests. When every test passes, your FINAL line of output must be exactly:
SUCCESS_ALL_TESTS_PASSED`,
      tools: ['bash', 'readFile', 'writeFile']
    });

    if (result.output.includes('SUCCESS_ALL_TESTS_PASSED')) {
      success = true;
      return { success: true, rounds: round, output: result.output };
    }
  }

  return { success: false, rounds: round, error: 'Maximum rounds exceeded' };
}
```

---

## 4. Scaffolding Workflows with rabbit-dsh

Use `rabbit-dsh` to quickly scaffold workflow templates. Available templates: `ralph` (default; iterative goal loop), `pr-review` (multi-agent pipeline), `standard` (single task execution).

```bash
# Scaffold a Ralph loop (default template):
python3 skills/rabbit-dsh/scripts/rabbit_dsh.py scaffold workflow workflows/bug-fixer.json \
  --name bug-fixer \
  --template ralph

# Scaffold a parallel PR reviewer
python3 skills/rabbit-dsh/scripts/rabbit_dsh.py scaffold workflow workflows/pr-audit.yaml \
  --name pr-audit \
  --template pr-review \
  --format yaml
```
