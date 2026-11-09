# Running a Code Review with DSH

For event-driven review instead of a manually submitted task, see [Automatic GitHub PR review](../guides/github-pr-review.md): dedicated webhook ingress, signature checks, and a review Session.

End-to-end walkthrough: we don't dive deep into the mechanics (see the corresponding pages for those) — we take you through **doing it once**. The goal is to review a repo/piece of code with DSH and get actionable change suggestions.

## Contents

- [1. Preparation](#1-preparation)
- [2. Step One: Have the Agent Map the Structure](#2-step-one-have-the-agent-map-the-structure)
- [3. Split the Review in Parallel with Sub Agents](#3-split-the-review-in-parallel-with-sub-agents)
- [4. Lock Down Permissions and Boundaries](#4-lock-down-permissions-and-boundaries)
- [5. Get Results and Follow Up](#5-get-results-and-follow-up)
- [6. Pinpoint with lsp](#6-pinpoint-with-lsp)
- [7. Edit Precisely with str_replace_editor](#7-edit-precisely-with-str_replace_editor)
- [8. Run Tests to Verify with bash](#8-run-tests-to-verify-with-bash)
- [9. Review and Follow Up](#9-review-and-follow-up)
- [Summary](#summary)

---

## 1. Preparation

- DSH installed and a key configured (see [Quick Start](../getting-started/quickstart.md))

- A project you want to review (a local directory is enough)

```sh
dsh web     # start the Web UI, pick the working directory in /docs
```

The working directory you pick = the main activity scope for `tool-fs`/`tool-bash` afterwards.

## 2. Step One: Have the Agent Map the Structure

Enter this in the Web UI (or use a `headless` one-shot task):

```text
Use tool-fs to list the top-level structure of this project; check whether there is a package.json, and if so read its dependencies;

then use bash to run git status to see whether it is a clean worktree.
```

DSH will call `fs` (read files) and then `bash` (run git) in turn. This single message verifies that it can write, read, and run.

Don't stop at the top level — spread the structure out with the directory-scan tools:

```text
Use glob to list all .ts/.tsx files under src and tests;

then use grep to search for code smells: TODO, FIXME, console.log, any, @ts-ignore;

open the hits with read to see context, and judge whether each is legacy or a new problem.
```

`glob`/`grep` are backed by the bundled ripgrep (no dependency on the system `rg`). A `glob` pattern without `/` matches by **filename at any depth**, and by default **includes hidden and ignored files**; `grep` returns file-grouped `Line N: <preview>` output — use `read` to open the matching lines when you need context.

Every step behind this is covered in [Tool Execution](../learn/core/tools-execution.md) and the [Agent Main Loop](../learn/core/agent-loop.md).

## 3. Split the Review in Parallel with Sub Agents

When there are many files / concerns to check, don't let the main agent do it serially — use sub Agents in parallel:

```text
Split the review into 3 subtasks to run in parallel:

  1) check "whether dependencies are outdated / have security advisories" (subagent-read packagelock + search)

  2) check "whether there are obvious security vulnerabilities" (injection / path traversal / credential leaks)

  3) check "structural issues" (duplicate code, over-deep nesting, mixed responsibilities)

  report each one's results to me for aggregation.
```

DSH will start sub Agents in parallel and aggregate at the end. The full delegation model is in [Sub Agents](../features/subagent.md).

Don't let the same batch self-verify its own results — spin up an **independent review sub Agent** that only cross-checks the high-priority items flagged in the previous batch's reports:

```text
Start a review sub Agent:

  only read the "critical" files flagged by the previous 3 reports,

  confirm one by one whether file/line/reason hold up, marking  confirmed / doubtful / not substantiated;

  don't raise new issues, and report the checklist back.
```

Sub Agents are independent sessions and don't pollute the main context; a `spawn` child session by default **cannot see the parent session's history**, so give full task descriptions when delegating and don't expect it to remember prior context.

## 4. Lock Down Permissions and Boundaries

A review runs commands and reads files. Set a preset temporarily for the scenario:

```text
Switch permissions to workspace-write; afterwards every time you want to write/change something, ask for my decision.
```

The permission-versus-sandbox tradeoff is covered in [Permissions](../user-guide/permissions.md) and [Sandbox](../learn/core/sandbox-security.md).

## 5. Get Results and Follow Up

Once the aggregation is back, continue:

```text
For each of the 3 most severe issues, give: file/line, why it is a problem, and how to fix it (with examples).

Finally write a REVIEW.md into the project root, listing all findings as a checklist.
```

Because of `workspace-write`, DSH will ask whether you approve before writing files (or you may have already allowed it).

## 6. Pinpoint with lsp

When text search collides with same-named symbols/strings, use `lsp` for semantic location. It is a read-only tool with four operations: `goToDefinition` (jump to definition), `findReferences` (find references, including the declaration), `goToImplementation` (find implementations), and `hover` (view signatures):

```text
Use lsp to run findReferences on handleRequest in src/server.ts,

listing all call sites; then run goToImplementation on the entry one

to confirm which version actually runs.
```

Coordinates are **1-based row/column (UTF-16)**; positions outside a symbol may return an empty result; `findReferences` always includes the declaration line, so impact analysis won't miss definition points. Once located to a specific line, pair with `read` to view context.

## 7. Edit Precisely with str_replace_editor

When review conclusions land on modifications, one tool handles both "view" and "change", avoiding back-and-forth between `read`/`edit`:

```text
Use str_replace_editor view to open src/util.ts near line 40;

change fetch(url) to request(url, {timeout: 5000}) with a timeout;

then use view to confirm only this occurrence was replaced.
```

It provides the four actions `view` / `create` / `str_replace` / `insert`, and paths use **absolute paths**; `str_replace` requires `old_str` to match **uniquely** and no `replace_all`, while inserting uses `insert` (zero-based boundaries). A directory `view` skips hidden/dependency/cache directories and descends two levels.

## 8. Run Tests to Verify with bash

After changing, don't rely only on your eyes: have the agent run targeted tests with `bash`, pinning failures to specific cases:

```text
Use bash to run pnpm test -- --runInBand;

paste the first failing case's error and the file/line it's in,

don't fix it yet — wait until I've reviewed it before deciding.
```

`bash` shares the session working directory with `read`/`glob`, so relative paths resolve against the workspace you picked; heavy commands like tests and builds all run as-is.

## 9. Review and Follow Up

- Want to see the DSH history behind a given suggestion? Use the [session_query](../features/tools.md) tool (the DSH core's workspace session retrieval)

- Want to track these findings long-term? Use [Goals / Tasks](../features/goals-tasks.md)

## Summary

A single "code review" task chains together these DSH capabilities: tools (fs/glob/grep/lsp), sub Agents, permissions, precise edits, and tests. You now have a **repeatable end-to-end usage**. To make it more automatic, you can wrap the process into [Skills](../features/skills.md) or [Workflows](../features/workflow.md).
