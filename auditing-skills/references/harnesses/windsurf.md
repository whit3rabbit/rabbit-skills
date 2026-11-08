# Windsurf Harness Reference

Reference guide for skill discovery, directory layout, configuration precedence, and Cascade agent integration in Windsurf.

## Contents

- [Harness Identifier](#harness-identifier)
- [Compatibility Matrix](#compatibility-matrix)
- [Skill Paths](#skill-paths)
- [Settings & Configuration](#settings--configuration)
- [Discovery & Precedence](#discovery--precedence)
- [Feature Support](#feature-support)
- [Directory Layout](#directory-layout)
- [Invocation](#invocation)
- [Concrete Example](#concrete-example)

---

## Harness Identifier

To audit or target Windsurf harness specifications:

| Parameter | Value |
|---|---|
| CLI Flag | `--agent windsurf` |
| Primary Agent | Cascade |
| Platform | Windsurf IDE (powered by Codeium) |

---

## Compatibility Matrix

| Feature | Supported | Details |
|---|---|---|
| Basic Skills (`SKILL.md`) | Yes | Standard YAML frontmatter (`name`, `description`) with Markdown procedural instructions. |
| Tool Restriction (`allowed-tools`) | Yes | Restricts terminal and file tools during skill execution. |
| Context Forking (`context: fork`) | No | Operates within the active Cascade conversation session; does not fork subagent processes. |
| Skill Hooks | No | Skill lifecycle hooks are not supported; uses `.windsurfrules` for rule-level directives. |
| Cascade Agent Integration | Yes | Cascade reads skill metadata into context and invokes scripts through workspace tools. |
| Tool Execution | Yes | Direct terminal command execution, file system read/write, and codebase indexing. |

---

## Skill Paths

Windsurf resolves agent skills across project-scoped and user-scoped directory trees.

| Scope | Canonical Path | Recognized Alternatives |
|---|---|---|
| **Project (Workspace)** | `.windsurf/skills/<skill-name>/` | `.agents/skills/<skill-name>/` |
| **User (Global)** | `~/.codeium/windsurf/skills/<skill-name>/` | `~/.agents/skills/<skill-name>/` |

### Path Details

- **Project Skills**: Stored within the workspace repository (`.windsurf/skills/` or `.agents/skills/`). Shared across team members via version control and scoped to workspace tasks.
- **User (Global) Skills**: Stored in the user home directory under `~/.codeium/windsurf/skills/`. Available across all workspaces opened in Windsurf on the local machine.

---

## Settings & Configuration

Windsurf and its Cascade agent manage instructions, behavioral rules, and persistent context across dedicated configuration files:

| Scope | Path | Purpose |
|---|---|---|
| **Project Rules** | `.windsurfrules` | Project-level instructions, style guidelines, and behavioral boundaries loaded automatically into Cascade context. |
| **Workspace Settings** | `.windsurf/` or `.vscode/settings.json` | Project-specific IDE configuration, tool settings, and workspace preferences. |
| **User / Global Settings** | `~/.codeium/windsurf/` | Machine-wide Cascade preferences, user settings, cached memories, and global skill definitions. |
| **Global Rules** | `~/.codeium/windsurf/memories/global_rules.md` | Machine-wide persistent behavioral rules applied across all workspaces. |

---

## Discovery & Precedence

When Cascade initializes or loads skills for a workspace session, it resolves collisions using strict precedence rules:

1. **Project Skills Override User Skills**: If a skill with the same `name` exists in both `.windsurf/skills/<skill-name>` and `~/.codeium/windsurf/skills/<skill-name>`, the project-level skill takes precedence and overrides the global skill.
2. **Project-Local Paths**: `.windsurf/skills/` is evaluated first, followed by the cross-harness `.agents/skills/` path.
3. **Rule Hierarchy**: Project-local `.windsurfrules` takes precedence over global rules in `~/.codeium/windsurf/` and default system instructions.
4. **Collision Handling**: Duplicate skill names within the same scope emit a resolution warning; Cascade selects the first matching instance discovered during directory traversal.

---

## Feature Support

### Cascade Agent Integration
Cascade serves as Windsurf's agentic core, providing autonomous and collaborative reasoning modes:
- **Write and Run Capabilities**: Cascade executes shell commands in the integrated terminal, inspects outputs, creates and edits files, and iterates on validation feedback loops.
- **Index and Context Awareness**: Cascade utilizes real-time codebase indexing to link skill references to project code and dependencies.

### Tool Execution & Permissions
Skills executed by Cascade use Windsurf's built-in tool set:
- **Terminal Execution**: Command runs are subject to Windsurf user approval modes (automatic or prompt-before-execution).
- **File System Operations**: Direct read, write, and patch operations against workspace files.
- **`allowed-tools` Restriction**: Defining `allowed-tools` in skill frontmatter limits Cascade's tool scope while that skill is actively executing.

---

## Directory Layout

Standard directory structure for a project incorporating Windsurf skills and configuration:

```
my-project/
├── .windsurfrules               # Workspace rules and instructions for Cascade
├── .windsurf/
│   └── skills/
│       └── component-test/
│           ├── SKILL.md         # Required entrypoint with YAML frontmatter
│           └── scripts/
│               └── run_tests.py # Executable test runner script
├── src/
│   ├── components/
│   │   └── Button.tsx
│   └── index.ts
└── package.json
```

---

## Invocation

Cascade supports two primary methods for skill invocation:

### 1. Autonomous Semantic Triggering
When a user prompt aligns with the `description` in a skill's YAML frontmatter, Cascade automatically discovers and loads the skill:
- Skill metadata (`name` and `description`) is evaluated during prompt analysis.
- Cascade loads `SKILL.md` procedural instructions and executes required steps.

### 2. Explicit Mention (@ Mentions)
Users can directly invoke skills in Cascade chat by referencing them with the `@` operator:
- Input: `@component-test run unit tests for Button.tsx`
- Cascade pins the specified skill into context immediately, bypassing description matching.

---

## Concrete Example

### Example Skill: `component-test`

#### File: `.windsurf/skills/component-test/SKILL.md`

```markdown
---
name: component-test
description: Executes unit and integration tests for UI components and reports coverage. Use when testing frontend components or validating changes before commits.
allowed-tools:
  - run_command
  - read_file
---

# Component Test Workflow

Follow this procedure to test UI components:

## Execution Steps

1. **Run Component Test Suite**:
   Execute the test script for the target component:
   ```bash
   python3 scripts/run_tests.py --path src/components/
   ```

2. **Verify Results**:
   Inspect the test summary and ensure all test assertions pass. If any test fails, inspect component source and re-run.

3. **Format Output**:
   Present findings using the output template below.

## Output Format

Output:
- **Component**: Target component name
- **Status**: PASS | FAIL
- **Assertions**: Total executed and passed
- **Coverage**: Line and branch coverage percentage
- **Remediation**: Steps required to fix failing tests (if applicable)
```

### Execution Walkthrough

**Input:**
```
@component-test Run tests for Button.tsx and verify coverage
```

**Output:**
```
- Component: Button.tsx
- Status: PASS
- Assertions: 14 executed, 14 passed
- Coverage: 94.2% line coverage, 88.9% branch coverage
- Remediation: None required; all assertions passed
```
