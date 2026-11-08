#!/usr/bin/env python3
"""Plugin Scaffolder and Harness Placement Helper.

Generates best-practice compliant plugins tailored for Claude Code, OpenAI Codex,
or portable generic Agent Plugins standards.

Standard library only (`argparse`, `json`, `pathlib`, `sys`, `shutil`).
Runs standalone or as part of the rabbit-skills suite.

Usage:
  python3 scaffold_plugin.py <plugin-name> --harness claude|codex|generic [options]
  python3 scaffold_plugin.py --list-harnesses
  python3 scaffold_plugin.py --self-test
"""

import argparse
import json
import os
import re
import shutil
import sys
import tempfile
from pathlib import Path

SUPPORTED_HARNESSES = {
    "claude": {
        "name": "Claude Code CLI",
        "doc": "references/claude-plugins.md",
        "manifest_path": "plugin.json",
        "mcp_path": ".mcp.json",
        "description": "Claude Code plugin with skills, commands, hooks, and evals suite"
    },
    "codex": {
        "name": "OpenAI Codex & ChatGPT",
        "doc": "references/codex-plugins.md",
        "manifest_path": "plugin.json",
        "mcp_path": "mcp.json",
        "description": "Portable Agent Plugin with OpenAI extensions, onboarding skill, and MCP"
    },
    "dsh": {
        "name": "DeepSeek Harness (Cordis)",
        "doc": "references/deepseek-harness-plugins.md",
        "manifest_path": "package.json",
        "mcp_path": "cordis.patch.yml",
        "description": "DeepSeek Harness plugin bundle with Cordis patch, tools, and events"
    },
    "generic": {
        "name": "Portable Agent Plugins Standard",
        "doc": "references/claude-plugins.md",
        "manifest_path": "plugin.json",
        "mcp_path": "mcp.json",
        "description": "Vendor-agnostic portable Agent Plugins specification"
    }
}


def sanitize_name(raw: str) -> str:
    """Normalize plugin name to lowercase kebab-case."""
    clean = re.sub(r"[^a-zA-Z0-9_-]+", "-", raw.strip().lower())
    clean = re.sub(r"-+", "-", clean).strip("-")
    if not clean:
        clean = "sample-plugin"
    return clean[:64]


def write_file_safe(path: Path, content: str):
    """Write text content to file with explicit I/O error handling."""
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
    except OSError as exc:
        print(f"Error writing {path}: {exc}", file=sys.stderr)
        raise


def write_json_safe(path: Path, data: dict):
    """Write JSON data to file with explicit I/O error handling."""
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
            f.write("\n")
    except OSError as exc:
        print(f"Error writing JSON to {path}: {exc}", file=sys.stderr)
        raise


def scaffold_claude_plugin(dest: Path, plugin_name: str, title: str, desc: str, with_mcp: bool, with_evals: bool):
    """Scaffold a Claude Code compliant plugin bundle."""
    dest.mkdir(parents=True, exist_ok=True)

    # 1. plugin.json
    manifest = {
        "name": plugin_name,
        "displayName": title,
        "version": "1.0.0",
        "description": desc,
        "author": {
            "name": "Plugin Author",
            "email": "author@example.com"
        },
        "license": "MIT",
        "keywords": ["claude-code", "developer-tools", plugin_name]
    }
    write_json_safe(dest / "plugin.json", manifest)

    # 2. Skill
    skill_content = f"""---
name: {plugin_name}
description: {desc} Use when running {plugin_name} workflows.
allowed-tools: [Bash, Read, Write]
---

# {title}

Step-by-step procedural guide:

1. Identify project context and parameters.
2. Execute required operations.
3. Validate and confirm results.
"""
    write_file_safe(dest / "skills" / plugin_name / "SKILL.md", skill_content)

    # 3. Command
    cmd_content = f"""---
description: Run {title} workflow
allowed-tools: [Bash]
---

Execute {plugin_name} operation on target: $1
"""
    write_file_safe(dest / "commands" / "run.md", cmd_content)

    # 4. Hooks
    hooks_content = {
        "hooks": {
            "PostToolUse": [
                {
                    "matcher": {"tool": "WriteFile"},
                    "command": "echo '[plugin hook] File modified' || true",
                    "description": "Log file modifications"
                }
            ]
        }
    }
    write_json_safe(dest / "hooks" / "hooks.json", hooks_content)

    # 5. MCP Server (optional)
    if with_mcp:
        mcp_content = {
            "mcpServers": {
                f"{plugin_name}-server": {
                    "command": "node",
                    "args": ["${pluginDir}/dist/server.js"],
                    "env": {
                        "DEBUG": "false"
                    }
                }
            }
        }
        write_json_safe(dest / ".mcp.json", mcp_content)

    # 6. Evals suite (optional)
    if with_evals:
        eval_case = dest / "evals" / "default-case"

        prompt_content = f"""---
name: default-case
description: Verifies {plugin_name} triggers on standard prompt
max_turns: 6
timeout_seconds: 120
allowed_tools: [Bash, Read, Write, Skill]
---

Please execute {plugin_name} for my repository.
"""
        write_file_safe(eval_case / "prompt.md", prompt_content)

        tool_grader = f"""---
type: tool_used
tool: Skill
input_match: '"skill"\\s*:\\s*"(?:[\\w-]+:)?{plugin_name}"'
---
"""
        write_file_safe(eval_case / "graders" / "skill-fired.md", tool_grader)

        criteria_grader = """---
type: llm
---

PASS if the output confirms successful execution.
FAIL if the assistant refused or encountered an unhandled error.
"""
        write_file_safe(eval_case / "graders" / "criteria.md", criteria_grader)

    # 7. README.md
    readme_content = f"""# {title}

{desc}

## Claude Code Quickstart

Load directly for testing:
```bash
claude --plugin-dir .
```

Validate plugin schema:
```bash
claude plugin validate .
```

Estimate token cost:
```bash
claude --plugin-dir . plugin details {plugin_name}
```

Run evaluations:
```bash
claude plugin eval .
```
"""
    write_file_safe(dest / "README.md", readme_content)


def scaffold_codex_plugin(dest: Path, plugin_name: str, title: str, desc: str, with_mcp: bool):
    """Scaffold an OpenAI Codex & ChatGPT compliant portable Agent Plugin."""
    dest.mkdir(parents=True, exist_ok=True)

    # 1. Portable plugin.json with extensions.com.openai
    manifest = {
        "$schema": "https://agent-plugins.org/schemas/1.0.0/plugin.schema.json",
        "name": plugin_name,
        "version": "1.0.0",
        "description": desc,
        "author": {
            "name": "Plugin Author",
            "email": "author@example.com"
        },
        "license": "MIT",
        "keywords": ["codex", "chatgpt", "agent-plugins", plugin_name],
        "extensions": {
            "com.openai": {
                "onboardingSkill": "./skills/setup/SKILL.md",
                "apps": "./.app.json",
                "interface": {
                    "displayName": title,
                    "shortDescription": desc[:100],
                    "longDescription": desc,
                    "developerName": "Engineering Tooling",
                    "category": "Development",
                    "capabilities": ["Read", "Write"],
                    "brandColor": "#10A37F",
                    "composerIcon": "./assets/icon.png",
                    "logo": "./assets/logo.png",
                    "defaultPrompt": [
                        f"Run {plugin_name} on current codebase"
                    ]
                }
            }
        }
    }
    write_json_safe(dest / "plugin.json", manifest)

    # 2. Main Skill
    skill_content = f"""---
name: {plugin_name}
description: {desc} Use when analyzing or refactoring code.
allowed-tools:
  - run_command
  - read_file
  - edit_file
---

# {title}

Instructions for executing {plugin_name} in Codex.
"""
    write_file_safe(dest / "skills" / plugin_name / "SKILL.md", skill_content)

    # 3. Onboarding Skill
    setup_content = f"""---
name: {plugin_name}-setup
description: Initial setup and repository check for {title}.
allowed-tools:
  - read_file
---

# Setup {title}

1. Inspect project repository root and dependencies.
2. Confirm prerequisites are satisfied.
"""
    write_file_safe(dest / "skills" / "setup" / "SKILL.md", setup_content)

    # 4. Portable mcp.json
    if with_mcp:
        mcp_content = {
            "$schema": "https://agent-plugins.org/schemas/1.0.0/mcp.schema.json",
            "mcpServers": {
                f"{plugin_name}-server": {
                    "type": "streamable-http",
                    "url": "https://mcp.example.com/api",
                    "extensions": {
                        "com.openai": {
                            "auth": {
                                "type": "none"
                            }
                        }
                    }
                }
            }
        }
        write_json_safe(dest / "mcp.json", mcp_content)

    # 5. App & Assets placeholders
    write_json_safe(dest / ".app.json", {"apps": []})
    write_file_safe(dest / "assets" / "README.txt", "Place square icon.png and marketplace logo.png in this folder.\n")

    # 6. README.md
    readme_content = f"""# {title}

{desc}

## Codex & ChatGPT Setup

Place plugin under `.codex/plugins/{plugin_name}` or `~/.codex/plugins/{plugin_name}`.

Configure in `.codex/config.toml`:
```toml
[[plugins.config]]
name = "{plugin_name}"
enabled = true
```

Invoke in Codex CLI / IDE:
```text
${plugin_name}
```
"""
    write_file_safe(dest / "README.md", readme_content)


def scaffold_generic_plugin(dest: Path, plugin_name: str, title: str, desc: str, with_mcp: bool):
    """Scaffold a vendor-neutral portable Agent Plugin."""
    dest.mkdir(parents=True, exist_ok=True)

    manifest = {
        "$schema": "https://agent-plugins.org/schemas/1.0.0/plugin.schema.json",
        "name": plugin_name,
        "version": "1.0.0",
        "description": desc,
        "author": {
            "name": "Plugin Author",
            "email": "author@example.com"
        },
        "license": "MIT",
        "keywords": ["agent-plugins", plugin_name]
    }
    write_json_safe(dest / "plugin.json", manifest)

    skill_content = f"""---
name: {plugin_name}
description: {desc}
---

# {title}

Procedural workflows for {plugin_name}.
"""
    write_file_safe(dest / "skills" / plugin_name / "SKILL.md", skill_content)

    if with_mcp:
        mcp_content = {
            "$schema": "https://agent-plugins.org/schemas/1.0.0/mcp.schema.json",
            "mcpServers": {
                f"{plugin_name}-server": {
                    "type": "stdio",
                    "command": "node",
                    "args": ["dist/index.js"]
                }
            }
        }
        write_json_safe(dest / "mcp.json", mcp_content)

    readme_content = f"""# {title}

{desc}

Built following the portable Agent Plugins specification (`agent-plugins.org`).
"""
    write_file_safe(dest / "README.md", readme_content)


def scaffold_dsh_plugin(dest: Path, plugin_name: str, title: str, desc: str):
    """Scaffold a DeepSeek Harness (DSH) compliant plugin bundle."""
    dest.mkdir(parents=True, exist_ok=True)
    pkg_name = f"dsh-{plugin_name}"
    tool_fn_name = plugin_name.replace("-", "_")

    # 1. package.json
    manifest = {
        "name": pkg_name,
        "version": "1.0.0",
        "description": desc,
        "license": "MIT",
        "type": "module",
        "main": "src/index.ts",
        "scripts": {
            "build": "tsc -b"
        },
        "files": [
            "dist",
            "cordis.patch.yml"
        ],
        "dsh": {
            "bundle": {
                "patch": "./cordis.patch.yml"
            }
        },
        "peerDependencies": {
            "@deepseek-ai/cordis": "^1.0.0",
            "@deepseek-ai/dsh-tools": "^1.0.0"
        }
    }
    write_json_safe(dest / "package.json", manifest)

    # 2. cordis.patch.yml
    patch_content = f"""- insert:
    - id: {plugin_name}
      name: {pkg_name}
      disabled: false
      config:
        enabled: true
"""
    write_file_safe(dest / "cordis.patch.yml", patch_content)

    # 3. src/index.ts
    index_content = f"""import type {{ Context }} from '@deepseek-ai/cordis'
import {{ defineTool }} from '@deepseek-ai/dsh-tools'

export const name = '{pkg_name}'
export const inject = ['tools']

export interface Config {{
  enabled?: boolean
}}

export function apply(ctx: Context, config: Config = {{}}) {{
  ctx.logger.info(`[{pkg_name}] Initializing plugin`)

  // Register custom agent tool
  ctx.tools.register(
    defineTool({{
      name: '{tool_fn_name}',
      description: '{desc}',
      parameters: {{
        query: {{
          type: 'string',
          required: true,
          description: 'Input query or operation parameter',
        }},
      }},
      output: {{
        schema: {{ type: 'string' }},
        render: (_args, value) => [{{ type: 'text', text: value }}],
      }},
      async execute(args) {{
        return `Result for ${{args.query}} from {tool_fn_name}`
      }},
    }})
  )

  // Listen to lifecycle event
  ctx.on('tools/result', (event: any) => {{
    ctx.logger.info(`[{pkg_name}] Tool execution completed: ${{event.name}}`)
  }})
}}
"""
    write_file_safe(dest / "src" / "index.ts", index_content)

    # 4. agent.cordis.yml (Preset template)
    preset_content = f"""name: {plugin_name}-expert
description: Dedicated agent preset for {title} workflows
persona:
  role: Senior {title} Specialist
  tone: Direct, accurate, and concise
  instructions: |
    - Analyze problems methodically before taking action.
    - Validate inputs and report structured outcomes.
tools:
  - {tool_fn_name}
"""
    write_file_safe(dest / "agent.cordis.yml", preset_content)

    # 5. README.md
    readme_content = f"""# {title} (DeepSeek Harness Plugin)

{desc}

## DeepSeek Harness Installation

```bash
# Add local development plugin to active profile:
dsh plugin --profile web add link:"$(pwd)"

# Verify active plugins:
dsh plugin --profile web ls
```

## Architecture

- **Cordis Container:** Configured via `cordis.patch.yml`
- **Tooling:** Implements `{tool_fn_name}` using `@deepseek-ai/dsh-tools`
- **Events:** Subscribes to `tools/result` with automatic lifecycle teardown
- **Preset:** Optional agent preset available in `agent.cordis.yml`
"""
    write_file_safe(dest / "README.md", readme_content)


def run_self_test():
    """Verify scaffolding functionality for claude, codex, and generic targets."""
    print("Running scaffold_plugin.py self-test...")
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)

        # Test Claude
        claude_dir = root / "test-claude"
        scaffold_claude_plugin(claude_dir, "test-claude", "Test Claude", "Claude test desc", True, True)
        assert (claude_dir / "plugin.json").is_file(), "Claude plugin.json missing"
        assert (claude_dir / "skills" / "test-claude" / "SKILL.md").is_file(), "Claude SKILL.md missing"
        assert (claude_dir / "commands" / "run.md").is_file(), "Claude commands missing"
        assert (claude_dir / "hooks" / "hooks.json").is_file(), "Claude hooks missing"
        assert (claude_dir / ".mcp.json").is_file(), "Claude .mcp.json missing"
        assert (claude_dir / "evals" / "default-case" / "prompt.md").is_file(), "Claude evals missing"
        print("  ✓ Claude scaffolding test passed")

        # Test Codex
        codex_dir = root / "test-codex"
        scaffold_codex_plugin(codex_dir, "test-codex", "Test Codex", "Codex test desc", True)
        assert (codex_dir / "plugin.json").is_file(), "Codex plugin.json missing"
        assert (codex_dir / "mcp.json").is_file(), "Codex mcp.json missing"
        assert (codex_dir / "skills" / "setup" / "SKILL.md").is_file(), "Codex onboarding skill missing"
        with open(codex_dir / "plugin.json") as f:
            data = json.load(f)
        assert "extensions" in data and "com.openai" in data["extensions"], "Codex extensions missing"
        print("  ✓ Codex scaffolding test passed")

        # Test Generic
        generic_dir = root / "test-generic"
        scaffold_generic_plugin(generic_dir, "test-generic", "Test Generic", "Generic test desc", True)
        assert (generic_dir / "plugin.json").is_file(), "Generic plugin.json missing"
        assert (generic_dir / "mcp.json").is_file(), "Generic mcp.json missing"
        print("  ✓ Generic scaffolding test passed")

        # Test DeepSeek Harness (DSH)
        dsh_dir = root / "test-dsh"
        scaffold_dsh_plugin(dsh_dir, "test-dsh", "Test DSH", "DSH test desc")
        assert (dsh_dir / "package.json").is_file(), "DSH package.json missing"
        assert (dsh_dir / "cordis.patch.yml").is_file(), "DSH cordis.patch.yml missing"
        assert (dsh_dir / "src" / "index.ts").is_file(), "DSH src/index.ts missing"
        assert (dsh_dir / "agent.cordis.yml").is_file(), "DSH agent.cordis.yml missing"
        with open(dsh_dir / "package.json") as f:
            dsh_manifest = json.load(f)
        assert "dsh" in dsh_manifest and "bundle" in dsh_manifest["dsh"], "DSH bundle config missing"
        print("  ✓ DeepSeek Harness (DSH) scaffolding test passed")

    print("All scaffold_plugin.py self-tests PASSED (4/4).")


def main():
    parser = argparse.ArgumentParser(description="Plugin Scaffolder for Claude Code, Codex, and Generic Standards.")
    parser.add_argument("name", nargs="?", help="Plugin name (lowercase kebab-case)")
    parser.add_argument("--harness", choices=("claude", "codex", "dsh", "generic"), default="claude",
                        help="Target harness layout (claude, codex, dsh, or generic)")
    parser.add_argument("--dest", help="Destination folder (defaults to current dir / <name>)")
    parser.add_argument("--title", help="Human-readable title")
    parser.add_argument("--desc", help="Short summary description")
    parser.add_argument("--with-mcp", action="store_true", default=True, help="Include MCP server configuration")
    parser.add_argument("--with-evals", action="store_true", default=True, help="Include evals suite (Claude only)")
    parser.add_argument("--list-harnesses", action="store_true", help="List supported plugin harnesses")
    parser.add_argument("--self-test", action="store_true", help="Run internal self-tests")

    args = parser.parse_args()

    if args.self_test:
        run_self_test()
        sys.exit(0)

    if args.list_harnesses:
        print("\nSupported Plugin Harnesses:\n")
        print(f"{'Harness':<10} {'Name':<32} {'Manifest':<16} {'Reference Guide'}")
        print("-" * 80)
        for hid, info in sorted(SUPPORTED_HARNESSES.items()):
            print(f"{hid:<10} {info['name']:<32} {info['manifest_path']:<16} {info['doc']}")
        print()
        sys.exit(0)

    if not args.name:
        parser.error("Plugin name is required (or use --list-harnesses / --self-test)")

    plugin_name = sanitize_name(args.name)
    title = args.title or " ".join(word.capitalize() for word in plugin_name.split("-"))
    desc = args.desc or f"Automated workflows and capabilities for {title}."
    dest = Path(args.dest).resolve() if args.dest else Path.cwd() / plugin_name

    print(f"Scaffolding {args.harness.upper()} plugin: '{plugin_name}' -> {dest}")

    if args.harness == "claude":
        scaffold_claude_plugin(dest, plugin_name, title, desc, args.with_mcp, args.with_evals)
    elif args.harness == "codex":
        scaffold_codex_plugin(dest, plugin_name, title, desc, args.with_mcp)
    elif args.harness == "dsh":
        scaffold_dsh_plugin(dest, plugin_name, title, desc)
    elif args.harness == "generic":
        scaffold_generic_plugin(dest, plugin_name, title, desc, args.with_mcp)

    print("\nPlugin scaffolded successfully:")
    for p in sorted(dest.rglob("*")):
        if p.is_file():
            print(f"  ✓ {p.relative_to(dest)}")

    print(f"\nGuide: {SUPPORTED_HARNESSES[args.harness]['doc']}")


if __name__ == "__main__":
    main()
