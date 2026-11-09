#!/usr/bin/env python3
"""
rabbit-dsh: Unified DeepSeek Harness (DSH) Studio & Offline Documentation Companion.

Provides comprehensive scaffolding, plugin/MCP patch management, configuration
editing, offline documentation lookup, and validation for DeepSeek Harness (dsh):
  - Scaffold skills (bundle or flat formats)
  - Scaffold Cordis plugins (TypeScript or JavaScript with services, tools, hooks)
  - Scaffold multi-agent workflows and Ralph iterative loops (official WorkflowMeta)
  - Manage MCP servers (JSON managed patches) and generic plugin rows
    (YAML managed patches carrying `!!js` env refs)
  - Inspect, initialize, and modify DSH configuration and settings
  - Offline documentation search, reading, and a cold-start concept map
  - Audit and validate DSH skills, plugins, workflows, and patch manifests
  - Deep artifact linting lives in audit_dsh_artifacts.py (DA-01..DA-21)

Zero external dependencies - strictly Python 3 standard library.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
from typing import Any


# -----------------------------------------------------------------------------
# Constants & Defaults
# -----------------------------------------------------------------------------

DEFAULT_PROFILE = "web"
DOCS_DIR = Path(__file__).resolve().parent.parent / "references" / "docs"

KEBAB_CASE_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
TOOL_NAME_RE = re.compile(r"^[a-zA-Z0-9_-]+$")
PACKAGE_NAME_RE = re.compile(r"(?:@[a-z0-9][a-z0-9._-]*/)?[a-z0-9][a-z0-9._-]*")
DSH_VERSION = "0.2.2-rc.1"

# Cold-start orientation: concept -> one-liner -> canonical offline doc paths.
# Paths are validated against the docs index at print time; stale entries drop.
CONCEPT_MAP = [
    ("architecture", "How DeepSeek Harness is structured: agent loop, capability seams, plugins, the session log as source of truth",
     ["official/reference/index.md", "official/reference/agent-lifecycle.md"]),
    ("skills", "Agent skills: SKILL.md bundles / flat files, frontmatter schema, discovery ranks",
     ["features/skills.md", "official/reference/subsystems/skills.md"]),
    ("plugins", "Cordis plugins: apply(ctx, config), inject, Service classes, the dsh manifest field",
     ["learn/core/plugin-anatomy.md", "official/develop/basic/index.md"]),
    ("patch", "The patch layer: cordis.patch.yml insert/override rows, layer precedence, !!js values",
     ["learn/core/plugin-anatomy.md", "learn/core/boot-config.md"]),
    ("workflows", "Workflow tool: {meta, script, args} and the agent/parallel/pipeline/phase/log primitives",
     ["features/workflow.md", "official/reference/subsystems/workflow.md"]),
    ("ralph", "Ralph loops: one immutable goal, a fresh agent every round, sentinel output",
     ["features/workflow.md", "features/goal-continuation.md"]),
    ("mcp", "MCP bridge: dsh-mcp-client rows, mcp__<serverName>__<tool> naming, stdio/streamable-http transports",
     ["features/mcp.md", "guides/mcp-memory.md"]),
    ("config", "Configuration stack: profile bundles -> cordis.patch.yml -> --patch overlays -> runtime settings",
     ["learn/core/boot-config.md", "user-guide/configuration.md", "user-guide/settings.md"]),
    ("env", "Environment variables: DSH_HOME, telemetry/permission/tool switches, reserved runtime vars",
     ["reference/env-vars.md"]),
    ("permissions", "Permission presets: workspace-write / read-only / danger-full-access x ask/never",
     ["user-guide/permissions.md", "official/reference/subsystems/permission-presets.md"]),
    ("persona", "Agent presets and personas: agent.cordis.yml, persona rows, agent->preset->global scope",
     ["features/persona.md"]),
    ("session", "Session log: JSONL event envelope, seq/surfaceOp/ignorable rules, format version gate",
     ["learn/core/event-system.md", "learn/core/session.md"]),
    ("tools", "Built-in tools and the defineTool contract",
     ["features/tools.md", "learn/dev/write-tool.md"]),
    ("commands", "Custom slash commands",
     ["features/commands.md"]),
    ("subagents", "Subagents and parallel fan-out",
     ["features/subagent.md"]),
    ("telemetry", "Telemetry switches and privacy hardening",
     ["official/reference/subsystems/session-telemetry.md"]),
]

# -----------------------------------------------------------------------------
# Offline Docs Search & Lookup Engine
# -----------------------------------------------------------------------------

class DocsEngine:
    def __init__(self, docs_dir: Path | None = None):
        self.docs_dir = (docs_dir or DOCS_DIR).resolve()
        self._index: list[dict] | None = None

    @staticmethod
    def _headings(text: str) -> list[tuple[int, int, str]]:
        headings = []
        fence = ""
        for index, line in enumerate(text.splitlines()):
            marker = re.match(r"^ {0,3}(`{3,}|~{3,})", line)
            if marker:
                if not fence:
                    fence = marker[1]
                elif marker[1].startswith(fence) and not line[marker.end():].strip():
                    fence = ""
            if not fence and (heading := re.match(r"^(#{1,6})\s+(.+?)\s*#*\s*$", line)):
                headings.append((index, len(heading[1]), heading[2]))
        return headings

    def load_index(self) -> list[dict]:
        if self._index is not None:
            return self._index

        index = []
        if not self.docs_dir.is_dir():
            self._index = []
            return self._index

        for md_path in sorted(self.docs_dir.glob("**/*.md")):
            rel = md_path.relative_to(self.docs_dir)
            try:
                text = md_path.read_text(encoding="utf-8", errors="replace")
            except Exception:
                continue

            # A legacy site snapshot can contain JavaScript outside the article.
            text = re.sub(r"(?m)^.*(?:window\.__VP_(?:HASH_MAP|SITE_DATA)__|__VITEPRESS__).*\n?", "", text)

            # Extract title
            title = ""
            m_title = re.search(r"^#\s+(.+)$", text, re.MULTILINE)
            if m_title:
                title = m_title.group(1).strip()
            else:
                title = rel.stem.replace("-", " ").title()

            # Category & Source Tag
            rel_parts = rel.parts
            is_official = len(rel_parts) > 0 and rel_parts[0] == "official"
            category = "/".join(rel_parts[:-1]) if len(rel_parts) > 1 else "root"
            source_tag = "[OFFICIAL]" if is_official else "[COMMUNITY]"

            index.append({
                "path": str(rel),
                "full_path": md_path,
                "title": title,
                "category": category,
                "is_official": is_official,
                "source_tag": source_tag,
                "content": text,
                "tokens": set(re.findall(r"\w+", text.lower())),
            })

        self._index = index
        return self._index

    def search(self, query: str, limit: int = 10, source: str | None = None) -> list[dict]:
        index = self.load_index()
        query_words = [w.lower() for w in re.findall(r"\w+", query)]
        if not query_words:
            return []

        results = []
        for doc in index:
            if source and doc["is_official"] != (source == "official"):
                continue
            score = 0
            doc_title_lower = doc["title"].lower()
            doc_path_lower = doc["path"].lower()

            # Exact phrase match in title
            if query.lower() in doc_title_lower:
                score += 50
            if query.lower() in doc_path_lower:
                score += 30

            for word in query_words:
                if word in doc_title_lower:
                    score += 20
                if word in doc_path_lower:
                    score += 15
                if word in doc["tokens"]:
                    # Count frequency
                    cnt = doc["content"].lower().count(word)
                    score += min(cnt, 15)

            # Boost official documentation
            if doc.get("is_official") and score > 0:
                score += 25

            if score > 0:
                results.append({
                    "path": doc["path"],
                    "title": doc["title"],
                    "category": doc["category"],
                    "source_tag": doc.get("source_tag", "[DOC]"),
                    "score": score,
                    "content": doc["content"],
                })

        results.sort(key=lambda x: x["score"], reverse=True)
        top = results[:max(limit, 0)]
        for result in top:
            result["snippet"], result["section"] = self._find_snippet(result.pop("content"), query_words)
        return top

    def _find_snippet(self, text: str, words: list[str], max_len: int = 240) -> tuple[str, str]:
        headings = {line: title for line, _, title in self._headings(text)}
        best_score = -1
        snippet = section = best_section = ""
        for index, line in enumerate(text.splitlines()):
            if index in headings:
                section = headings[index]
                continue
            line = line.strip()
            if not line:
                continue
            tokens = set(re.findall(r"\w+", line.lower()))
            score = sum(word in tokens for word in words)
            if score > best_score:
                snippet, best_section, best_score = line, section, score
        if len(snippet) > max_len:
            snippet = snippet[:max_len] + "..."
        return snippet, best_section

    def read_doc(self, target: str, section: str | None = None) -> str | None:
        target = target.strip().lower().removesuffix(".md")
        index = self.load_index()
        matches = [doc for doc in index if doc["path"].lower().removesuffix(".md") == target]
        if not matches and "/" not in target:
            matches = [doc for doc in index if Path(doc["path"]).stem.lower() == target]
        if len(matches) > 1:
            paths = ", ".join(doc["path"] for doc in matches)
            raise ValueError(f"Ambiguous document '{target}'. Use one of: {paths}")
        if not matches:
            return None
        content = matches[0]["content"]
        if section is None:
            return content

        headings = self._headings(content)
        for i, (start, level, title) in enumerate(headings):
            if title.casefold() == section.casefold():
                end = next((line for line, depth, _ in headings[i + 1:] if depth <= level), None)
                return "\n".join(content.splitlines()[start:end])
        raise ValueError(f"Section '{section}' not found in {matches[0]['path']}.")

    def list_categories(self) -> dict[str, list[dict]]:
        index = self.load_index()
        cats: dict[str, list[dict]] = {}
        for doc in index:
            cat = doc["category"]
            cats.setdefault(cat, []).append({
                "path": doc["path"],
                "title": doc["title"],
            })
        return cats

    def doc_map(self, topic: str | None = None) -> list[tuple[str, str, list[str]]]:
        """Curated concept map for agents new to DeepSeek Harness.

        Returns (concept, one_liner, doc_paths) rows, filtered by an optional
        topic substring. Doc paths are validated against the offline index so
        stale CONCEPT_MAP entries degrade gracefully instead of dead-ending.
        """
        index = self.load_index()
        known = {doc["path"] for doc in index}
        needle = topic.strip().lower() if topic else None
        rows = []
        for concept, blurb, paths in CONCEPT_MAP:
            if needle and needle not in concept and needle not in blurb.lower():
                continue
            valid_paths = [path for path in paths if path in known]
            if valid_paths:
                rows.append((concept, blurb, valid_paths))
        return rows


# -----------------------------------------------------------------------------
# Scaffolding Engine
# -----------------------------------------------------------------------------

class Scaffolder:
    @staticmethod
    def scaffold_skill(
        target_dir: Path,
        name: str,
        description: str,
        skill_type: str = "bundle",
        when_to_use: str | None = None,
        disable_model_invocation: bool = False,
        user_invocable: bool = False,
    ) -> Path:
        """Scaffold a DSH-compliant skill (bundle directory or flat file)."""
        name = name.strip()
        if not KEBAB_CASE_RE.fullmatch(name) or len(name) > 64:
            raise ValueError(f"Skill name '{name}' must be kebab-case (lowercase letters, digits, and hyphens).")
        description = description.strip()
        if not description:
            raise ValueError("Skill description must contain text.")

        frontmatter_lines = [
            "---",
            f"name: {json.dumps(name, ensure_ascii=False)}",
            f"description: {json.dumps(description, ensure_ascii=False)}",
        ]
        if when_to_use:
            frontmatter_lines.append(f"whenToUse: {json.dumps(when_to_use.strip(), ensure_ascii=False)}")
        if disable_model_invocation:
            frontmatter_lines.append("disable-model-invocation: true")
        if user_invocable:
            frontmatter_lines.append("user-invocable: true")
        frontmatter_lines.append("---")
        frontmatter_str = "\n".join(frontmatter_lines)

        body = f"""# {name.replace('-', ' ').title()}

## Overview
{description.strip()}

## Progressive Disclosure & Instructions
Describe procedural steps, trigger guidelines, and constraints here.
Keep the always-on description concise and high-signal so the agent loads this full document on demand.

## Verification
- Run tests or check assertions to confirm successful execution.
"""

        skill_md_content = f"{frontmatter_str}\n\n{body}\n"

        if skill_type == "flat":
            target_dir.mkdir(parents=True, exist_ok=True)
            out_file = target_dir / f"{name}.md"
            with out_file.open("x", encoding="utf-8") as file:
                file.write(skill_md_content)
            return out_file

        # Directory bundle
        skill_root = target_dir / name
        skill_root.mkdir(parents=True)
        (skill_root / "scripts").mkdir(exist_ok=True)
        (skill_root / "references").mkdir(exist_ok=True)

        # Write SKILL.md
        skill_md_path = skill_root / "SKILL.md"
        skill_md_path.write_text(skill_md_content, encoding="utf-8")

        # Starter script
        starter_script = f'''#!/usr/bin/env python3
"""Helper script for {name}."""

def run() -> None:
    print("{name} helper executed.")

if __name__ == "__main__":
    run()
'''
        script_file = skill_root / "scripts" / "helper.py"
        script_file.write_text(starter_script, encoding="utf-8")
        script_file.chmod(0o755)

        # Starter reference
        (skill_root / "references" / "guide.md").write_text(
            f"# {name} Reference Guide\n\nDetailed specifications and advanced reference material.\n",
            encoding="utf-8"
        )

        return skill_root

    @staticmethod
    def scaffold_plugin(
        target_dir: Path,
        name: str,
        is_ts: bool = True,
        service_name: str | None = None,
        with_tool: bool = True,
        with_hook: bool = True,
        with_command: bool = False,
    ) -> Path:
        """Scaffold an installable Cordis bundle with a minimal Host entry."""
        if not PACKAGE_NAME_RE.fullmatch(name) or len(name) > 214:
            raise ValueError("Use a lowercase npm package name, optionally scoped as @scope/name.")
        if service_name and not re.fullmatch(r"[a-zA-Z][a-zA-Z0-9_]*", service_name):
            raise ValueError("Service name must be an identifier such as gitTools.")

        pkg_root = target_dir / name
        # Resolve the parent too, since an existing scope directory can be a symlink.
        if not pkg_root.resolve().is_relative_to(target_dir.resolve()):
            raise ValueError("Plugin destination must be inside the target directory.")
        pkg_root.mkdir(parents=True)
        clean_id = name.rsplit("/", 1)[-1]
        entry = "lib/index.js" if is_ts else "index.js"

        peers = {}
        if is_ts or service_name:
            peers["@deepseek-ai/cordis"] = "4.1.0"
        if with_tool:
            peers["@deepseek-ai/dsh-tools"] = DSH_VERSION
        if with_command:
            peers["@deepseek-ai/dsh-commands"] = DSH_VERSION

        pkg_json = {
            "name": name,
            "version": "0.1.0",
            "type": "module",
            "main": entry,
            "files": [entry, "cordis.patch.yml"],
            "engines": {"dsh": DSH_VERSION},
            "dsh": {"bundle": {"patch": "./cordis.patch.yml"}},
        }
        if peers:
            pkg_json["peerDependencies"] = peers
        if is_ts:
            pkg_json.update({
                "types": "lib/index.d.ts",
                "files": ["lib", "cordis.patch.yml"],
                "scripts": {"build": "tsc"},
                "devDependencies": {"typescript": "^5.8.0", "@types/node": "^24.0.0"},
            })
            tsconfig = {
                "compilerOptions": {
                    "target": "ES2022",
                    "module": "NodeNext",
                    "declaration": True,
                    "outDir": "lib",
                    "rootDir": "src",
                    "strict": True,
                    "skipLibCheck": True,
                },
                "include": ["src/**/*.ts"],
            }
            (pkg_root / "tsconfig.json").write_text(json.dumps(tsconfig, indent=2) + "\n", encoding="utf-8")
        (pkg_root / "package.json").write_text(json.dumps(pkg_json, indent=2) + "\n", encoding="utf-8")

        imports = []
        if is_ts:
            imports.append("import type { Context } from '@deepseek-ai/cordis'")
        if service_name:
            imports.append("import { Service } from '@deepseek-ai/cordis'")
        if with_tool:
            imports.append("import { defineTool } from '@deepseek-ai/dsh-tools'")
        if is_ts and with_command:
            imports.append("import type {} from '@deepseek-ai/dsh-commands'")

        inject = [key for key, enabled in (("tools", with_tool), ("commands", with_command)) if enabled]
        lines = [*imports, "", f"export const name = {json.dumps(name)}"]
        if inject:
            lines.append(f"export const inject = {json.dumps(inject)}")
        if service_name:
            service_key = json.dumps(service_name)
            if is_ts:
                lines.extend([
                    "",
                    "declare module '@deepseek-ai/cordis' {",
                    f"  interface Context {{ {service_key}: PluginService }}",
                    "}",
                ])
            context_param = "ctx: Context" if is_ts else "ctx"
            lines.extend([
                "",
                "class PluginService extends Service {",
                f"  constructor({context_param}) {{",
                f"    super(ctx, {service_key})",
                "  }",
                "}",
            ])

        context_param = "ctx: Context" if is_ts else "ctx"
        lines.extend(["", f"export function apply({context_param}) {{"])
        if service_name:
            lines.append("  ctx.plugin(PluginService)")
        if with_tool:
            tool_name = re.sub(r"[^a-z0-9_]", "_", clean_id) + "_action"
            lines.append(f"""  ctx.tools.register(defineTool({{
    name: {json.dumps(tool_name)},
    description: 'Echo a string to verify that this bundle is loaded.',
    parameters: {{
      action: {{ type: 'string', required: true, description: 'Text to echo' }},
    }},
    output: {{
      schema: {{ type: 'string' }},
      render: (_args, value) => [{{ type: 'text', text: value }}],
    }},
    async execute({{ action }}) {{
      return action
    }},
  }}))""")
        if with_hook:
            lines.append(f"""  ctx.effect(() => {{
    ctx.logger.info({json.dumps(name + " loaded")})
    return () => ctx.logger.info({json.dumps(name + " unloaded")})
  }})""")
        if with_command:
            command_name = re.sub(r"[^a-z0-9-]", "-", clean_id)
            lines.append(f"""  ctx.commands.register({{
    name: {json.dumps(command_name)},
    description: 'Verify that this bundle is loaded.',
    handler: () => ({{ kind: 'success', text: 'Bundle loaded.' }}),
  }})""")
        lines.extend(["}", ""])
        src_file = pkg_root / ("src/index.ts" if is_ts else entry)
        src_file.parent.mkdir(exist_ok=True)
        src_file.write_text("\n".join(lines).lstrip(), encoding="utf-8")

        # Installed bundles resolve package names. Local overlays use file paths.
        patch = f"- insert:\n    - id: {json.dumps(clean_id)}\n      name: {json.dumps(name)}\n"
        (pkg_root / "cordis.patch.yml").write_text(patch, encoding="utf-8")
        return pkg_root

    @staticmethod
    def scaffold_workflow(
        target_path: Path,
        name: str,
        template: str = "ralph",
        output_format: str = "json",
    ) -> Path:
        """Scaffold a DSH workflow definition or Ralph iterative loop."""
        name = name.strip()
        clean_name = name.replace(" ", "-").lower()

        if template == "ralph":
            meta = {
                "name": clean_name,
                "description": f"Ralph iterative goal solver for {name}",
                "whenToUse": "When one stable goal needs repeated fresh-agent rounds (Ralph loop)",
            }
            script = """// Ralph iterative goal loop (Top-level await)
async function main(args) {
  const goal = args.goal || 'Complete task';
  let iteration = 0;
  let done = false;

  while (!done && iteration < 10) {
    iteration++;
    log(`[Ralph] Round ${iteration}: Starting fresh agent for goal: ${goal}`);
    const agentResult = await agent({
      prompt: `Iteration ${iteration}: Solve '${goal}'. Run the tests. When every test passes, your FINAL line of output must be exactly: SUCCESS_ALL_TESTS_PASSED`,
      tools: ['bash', 'readFile', 'writeFile']
    });

    if (agentResult.status === 'success' && agentResult.output?.includes('SUCCESS_ALL_TESTS_PASSED')) {
      done = true;
      log(`[Ralph] Goal achieved at iteration ${iteration}`);
      return { success: true, rounds: iteration, finalOutput: agentResult.output };
    }
  }

  return { success: done, rounds: iteration, status: 'iteration_limit_reached' };
}
"""
        elif template == "pr-review":
            meta = {
                "name": clean_name,
                "description": "Multi-agent GitHub PR review workflow",
                "phases": ["fetch-diff", "security-audit", "synthesize-report"]
            }
            script = """// Multi-Agent PR Review Workflow (Top-level await)
async function main(args) {
  const prNumber = args.prNumber || 1;
  phase('fetch-diff');
  log(`Fetching PR #${prNumber} diff...`);
  const diffResult = await agent({ prompt: `Fetch git diff for PR #${prNumber}` });

  phase('security-audit');
  log(`Fanning out security and quality auditors in parallel...`);
  const [secReview, qualReview] = await parallel([
    agent({ prompt: `Audit this diff for security vulnerabilities:\\n${diffResult.output}` }),
    agent({ prompt: `Audit this diff for code style and test coverage:\\n${diffResult.output}` })
  ]);

  phase('synthesize-report');
  log(`Synthesizing PR review report...`);
  const report = await agent({
    prompt: `Synthesize PR #${prNumber} final review from:\\nSecurity:\\n${secReview.output}\\nQuality:\\n${qualReview.output}`
  });

  return { pr: prNumber, report: report.output };
}
"""
        else: # generic task
            meta = {
                "name": clean_name,
                "description": f"DSH automated workflow for {name}",
            }
            script = """// DSH Standard Workflow (Top-level await)
async function main(args) {
  log(`Starting workflow ${args.taskName || 'unnamed'}`);
  const result = await agent({
    prompt: `Execute task: ${args.instructions}`,
  });
  return { status: 'complete', result: result.output };
}
"""

        workflow_data = {
            "meta": meta,
            "args": {
                "instructions": "Task instructions here",
                "goal": "Reach objective with 0 errors"
            },
            "script": script.strip()
        }

        target_path.parent.mkdir(parents=True, exist_ok=True)
        if output_format == "yaml":
            # Simple zero-dependency YAML dump (WorkflowMeta vocabulary only)
            yaml_lines = [
                f"# DSH Workflow: {clean_name}",
                "meta:",
                f"  name: {meta['name']}",
                f"  description: \"{meta['description']}\"",
            ]
            if meta.get("whenToUse"):
                yaml_lines.append(f"  whenToUse: \"{meta['whenToUse']}\"")
            if "phases" in meta:
                yaml_lines.append("  phases:")
                for p in meta["phases"]:
                    yaml_lines.append(f"    - {p}")
            yaml_lines.append("args:")
            for k, v in workflow_data["args"].items():
                yaml_lines.append(f"  {k}: \"{v}\"")
            yaml_lines.append("script: |")
            for s_line in script.strip().splitlines():
                yaml_lines.append(f"  {s_line}")
            target_path.write_text("\n".join(yaml_lines) + "\n", encoding="utf-8")
        else:
            target_path.write_text(json.dumps(workflow_data, indent=2) + "\n", encoding="utf-8")

        return target_path


# -----------------------------------------------------------------------------
# MCP Server Manager for cordis.patch.yml
# -----------------------------------------------------------------------------

class MCPManager:
    MANAGED_HEADER = "# rabbit-dsh managed MCP patch\n"

    @staticmethod
    def get_patch_path(profile: str = DEFAULT_PROFILE, custom_path: Path | None = None) -> Path:
        if custom_path:
            return custom_path.resolve()
        # Default DSH profile patch path: ~/.dsh/profiles/<profile>/cordis.patch.yml
        dsh_home = Path(os.environ.get("DSH_HOME", Path.home() / ".dsh"))
        return dsh_home / "profiles" / profile / "cordis.patch.yml"

    @classmethod
    def list_servers(cls, patch_path: Path) -> list[dict]:
        """Parse cordis.patch.yml and list all MCP client server configurations."""
        if not patch_path.is_file():
            return []

        text = patch_path.read_text(encoding="utf-8", errors="replace")
        entries = (
            cls._managed_entries(text)
            if text.startswith(cls.MANAGED_HEADER)
            else cls._parse_patch_entries(text)
        )
        mcp_servers = []

        for entry in entries:
            # Check if this entry is an MCP client
            name = entry.get("name", "")
            cfg = entry.get("config", {})
            if name == "@deepseek-ai/dsh-mcp-client" or "serverName" in cfg:
                mcp_servers.append({
                    "id": entry.get("id", ""),
                    "serverName": cfg.get("serverName", entry.get("id", "").replace("mcp-", "")),
                    "transport": cfg.get("transport", "stdio"),
                    "command": cfg.get("command", ""),
                    "args": cfg.get("args", []),
                    "env": cfg.get("env", {}),
                    "url": cfg.get("url", ""),
                    "toolPrefix": f"mcp__{cfg.get('serverName', '')}__<toolName>"
                })

        return mcp_servers

    @classmethod
    def add_server(
        cls,
        patch_path: Path,
        server_name: str,
        command: str | None = None,
        args: list[str] | None = None,
        transport: str = "stdio",
        url: str | None = None,
        env: dict[str, str] | None = None,
    ) -> None:
        """Add or update an MCP server in a dedicated, managed patch."""
        if not TOOL_NAME_RE.fullmatch(server_name):
            raise ValueError("Server name must contain only letters, digits, underscores, or hyphens.")
        existing_text = patch_path.read_text(encoding="utf-8") if patch_path.exists() else None
        entries = cls._managed_entries(existing_text) if existing_text is not None else []

        mcp_id = f"mcp-{server_name}"
        # Remove any existing entry with this id or serverName
        filtered = [
            e for e in entries
            if e.get("id") != mcp_id and e.get("config", {}).get("serverName") != server_name
        ]

        cfg: dict = {
            "serverName": server_name,
            "transport": transport,
        }
        if transport == "stdio":
            if not command:
                raise ValueError("Command is required for stdio transport.")
            cfg["command"] = command
            if args:
                cfg["args"] = args
        elif transport in ("streamable-http", "sse"):
            if not url:
                raise ValueError(f"URL is required for {transport} transport.")
            cfg["url"] = url
        else:
            raise ValueError(f"Unknown MCP transport: {transport}")

        if env:
            cfg["env"] = env

        new_entry = {
            "id": mcp_id,
            "name": "@deepseek-ai/dsh-mcp-client",
            "config": cfg,
        }
        filtered.append(new_entry)

        cls._write_patch_entries(patch_path, filtered, existing_text)

    @classmethod
    def remove_server(cls, patch_path: Path, server_name: str) -> bool:
        """Remove an MCP server from a dedicated, managed patch."""
        if not patch_path.is_file():
            return False

        existing_text = patch_path.read_text(encoding="utf-8")
        entries = cls._managed_entries(existing_text)
        mcp_id = f"mcp-{server_name}"

        orig_len = len(entries)
        filtered = [
            e for e in entries
            if e.get("id") not in (mcp_id, server_name)
            and e.get("config", {}).get("serverName") != server_name
        ]

        if len(filtered) == orig_len:
            return False

        cls._write_patch_entries(patch_path, filtered, existing_text)
        return True

    @staticmethod
    def _parse_patch_entries(text: str) -> list[dict]:
        """Extract simple patch rows for read-only inspection of native or legacy YAML."""
        entries: list[dict] = []
        raw_blocks = re.split(r"(?m)^[ \t]*-[ \t]+(?=(?:id|name|insert):)", text)
        for block in raw_blocks:
            block = block.strip()
            if not block:
                continue

            entry: dict = {}
            # Check if wrapped in insert:
            if block.startswith("insert:"):
                block = block[len("insert:"):].strip()

            lines = block.splitlines()
            in_config = False
            in_args = False
            in_env = False
            args_list = []
            env_dict = {}
            config_dict = {}

            for line in lines:
                line_str = line.strip()
                if not line_str or line_str.startswith("#"):
                    continue

                if line_str.startswith("config:"):
                    in_config = True
                    in_args = False
                    in_env = False
                    continue

                if in_config:
                    if line.startswith("      ") or line.startswith("    "):
                        if line_str.startswith("args:"):
                            in_args = True
                            in_env = False
                            # check if inline JSON list
                            m_inline = re.search(r"args:\s*(\[.*\])", line_str)
                            if m_inline:
                                try:
                                    args_list = json.loads(m_inline.group(1).replace("'", '"'))
                                    config_dict["args"] = args_list
                                    in_args = False
                                except Exception:
                                    pass
                            continue
                        elif line_str.startswith("env:"):
                            in_env = True
                            in_args = False
                            continue
                        elif in_args and line_str.startswith("- "):
                            val = line_str[2:].strip().strip("'\"")
                            args_list.append(val)
                            config_dict["args"] = args_list
                            continue
                        elif in_env and ":" in line_str:
                            k, v = line_str.split(":", 1)
                            env_dict[k.strip()] = v.strip().strip("'\"")
                            config_dict["env"] = env_dict
                            continue

                        # Normal config field
                        if ":" in line_str:
                            k, v = line_str.split(":", 1)
                            config_dict[k.strip()] = v.strip().strip("'\"")
                            continue

                # Top-level fields
                if ":" in line_str:
                    k, v = line_str.split(":", 1)
                    k = k.strip()
                    v = v.strip().strip("'\"")
                    if k in ("id", "name", "action"):
                        entry[k] = v

            if config_dict:
                entry["config"] = config_dict
            if entry:
                entries.append(entry)

        return entries

    @classmethod
    def _managed_entries(cls, text: str) -> list[dict]:
        if not text.startswith(cls.MANAGED_HEADER):
            raise ValueError("Use a new patch path for rabbit-dsh MCP writes. Edit existing YAML with DSH.")
        try:
            patch = json.loads(text.removeprefix(cls.MANAGED_HEADER))
            if patch == []:
                return []
            [operation] = patch
            rows = operation["insert"]
            if (
                set(operation) == {"insert"}
                and isinstance(rows, list)
                and all(
                    row.get("name") == "@deepseek-ai/dsh-mcp-client"
                    and isinstance(row.get("id"), str)
                    and isinstance(row.get("config"), dict)
                    for row in rows
                )
            ):
                return rows
        except (AttributeError, KeyError, TypeError, ValueError):
            pass
        raise ValueError("Malformed rabbit-dsh MCP patch. Inspect the file before editing.")

    @classmethod
    def _write_patch_entries(cls, patch_path: Path, entries: list[dict], original: str | None) -> None:
        # JSON is a YAML subset. Keeping it in a dedicated file protects unrelated rows and YAML tags.
        patch = [{"insert": entries}] if entries else []
        patch_path.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", dir=patch_path.parent, delete=False
        ) as file:
            pending = Path(file.name)
            try:
                file.write(cls.MANAGED_HEADER + json.dumps(patch, indent=2, ensure_ascii=False) + "\n")
                file.close()
                if original is None:
                    os.link(pending, patch_path)
                else:
                    if patch_path.read_text(encoding="utf-8") != original:
                        raise ValueError("MCP patch changed during the edit. Retry against the current file.")
                    pending.replace(patch_path)
            finally:
                pending.unlink(missing_ok=True)


# -----------------------------------------------------------------------------
# Generic Plugin Patch Manager (YAML managed rows)
# -----------------------------------------------------------------------------

class PatchManager:
    """Manage generic Cordis patch rows in a rabbit-dsh managed YAML patch.

    Unlike the MCP manager's JSON format, this format is written as YAML so
    rows can carry `!!js` expression tags (e.g. `!!js process.env.TOKEN`
    env-var references). Only files starting with MANAGED_HEADER are written;
    hand-maintained YAML is never touched.
    """

    MANAGED_HEADER = "# rabbit-dsh managed plugin patch\n"

    @staticmethod
    def get_patch_path(profile: str = DEFAULT_PROFILE, custom_path: Path | None = None) -> Path:
        if custom_path:
            return custom_path.resolve()
        dsh_home = Path(os.environ.get("DSH_HOME", Path.home() / ".dsh"))
        return dsh_home / "profiles" / profile / "cordis.patch.yml"

    @classmethod
    def _parse_rows(cls, text: str) -> list[dict]:
        """Parse the exact row structure this class writes. Read-only."""
        if not text.startswith(cls.MANAGED_HEADER):
            raise ValueError("Use a new patch path for rabbit-dsh plugin writes. Edit existing YAML with DSH.")
        rows: list[dict] = []
        cur: dict | None = None
        in_config = False
        row_indent = 0
        config_stack: list[tuple[int, dict]] = []
        for raw in text.splitlines()[1:]:
            stripped = raw.strip()
            if not stripped or stripped.startswith("#"):
                continue
            indent = len(raw) - len(raw.lstrip(" "))
            if stripped == "- insert:":
                cur = None
                in_config = False
                config_stack = []
                continue
            if stripped.startswith("- ") and (cur is None or indent <= row_indent):
                cur = {"id": None, "name": None, "config": {}, "disabled": False}
                rows.append(cur)
                in_config = False
                config_stack = []
                row_indent = indent
                body = stripped[2:].strip()
                if ":" in body:
                    key, _, value = body.partition(":")
                    if key.strip() == "config":
                        in_config = True
                        config_stack = []
                    else:
                        cur[key.strip()] = cls._scalar(value.strip())
                continue
            if cur is None or ":" not in stripped:
                continue
            key, _, value = stripped.partition(":")
            key = key.strip()
            value = value.strip()
            if key == "config" and not value:
                in_config = True
                config_stack = []
                continue
            if in_config and indent > row_indent + 2:
                while config_stack and indent <= config_stack[-1][0]:
                    config_stack.pop()
                target = config_stack[-1][1] if config_stack else cur["config"]
                if not value:
                    nested: dict = {}
                    target[key] = nested
                    config_stack.append((indent, nested))
                else:
                    target[key] = cls._scalar(value)
            else:
                in_config = False
                config_stack = []
                if key in ("id", "name", "disabled"):
                    cur[key] = cls._scalar(value)
        return rows

    @staticmethod
    def _scalar(value: str):
        if value.startswith("!!js"):
            return value
        if value in ("true", "false"):
            return value == "true"
        try:
            return json.loads(value)
        except ValueError:
            return value

    @classmethod
    def list_rows(cls, patch_path: Path) -> list[dict]:
        """List plugin rows. Falls back to read-only inspection for foreign YAML."""
        if not patch_path.is_file():
            return []
        text = patch_path.read_text(encoding="utf-8", errors="replace")
        if text.startswith(cls.MANAGED_HEADER):
            return cls._parse_rows(text)
        return MCPManager._parse_patch_entries(text)

    @classmethod
    def add_row(
        cls,
        patch_path: Path,
        row_id: str,
        name: str,
        config: dict | None = None,
        env_refs: dict[str, str] | None = None,
        disabled: bool = False,
    ) -> None:
        """Insert or replace a row, keyed by id. env_refs become !!js tags."""
        if not row_id or not str(row_id).strip():
            raise ValueError("Patch row id is required.")
        if not name or not str(name).strip():
            raise ValueError("Patch row name (plugin package or component) is required.")
        cfg = dict(config or {})
        for key, var in (env_refs or {}).items():
            if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", var):
                raise ValueError(f"Env var name '{var}' is not a valid shell identifier.")
            cfg[key] = f"!!js process.env.{var}"
        if disabled:
            cfg.pop("disabled", None)

        existing_text = patch_path.read_text(encoding="utf-8") if patch_path.exists() else None
        rows = cls._parse_rows(existing_text) if existing_text is not None else []
        new_row = {
            "id": row_id,
            "name": str(name),
            "config": cfg,
            "disabled": bool(disabled),
        }
        # Replace in place so re-adding a row keeps its mount order.
        for idx, row in enumerate(rows):
            if row.get("id") == row_id:
                rows[idx] = new_row
                break
        else:
            rows.append(new_row)
        cls._write_rows(patch_path, rows, existing_text)

    @classmethod
    def remove_row(cls, patch_path: Path, row_id: str) -> bool:
        """Remove a row by id. Returns False when nothing matched."""
        if not patch_path.is_file():
            return False
        existing_text = patch_path.read_text(encoding="utf-8")
        rows = cls._parse_rows(existing_text)
        kept = [row for row in rows if row.get("id") != row_id]
        if len(kept) == len(rows):
            return False
        cls._write_rows(patch_path, kept, existing_text)
        return True

    @classmethod
    def _emit_mapping(cls, mapping: dict, indent: int, lines: list[str]) -> None:
        pad = " " * indent
        for key, value in mapping.items():
            if isinstance(value, dict):
                lines.append(f"{pad}{key}:")
                cls._emit_mapping(value, indent + 2, lines)
            elif isinstance(value, str) and value.startswith("!!js"):
                lines.append(f"{pad}{key}: {value}")
            elif isinstance(value, list):
                lines.append(f"{pad}{key}: {json.dumps(value, ensure_ascii=False)}")
            else:
                lines.append(f"{pad}{key}: {json.dumps(value, ensure_ascii=False)}")

    @classmethod
    def _write_rows(cls, patch_path: Path, rows: list[dict], original: str | None) -> None:
        lines = [cls.MANAGED_HEADER.rstrip("\n")]
        if rows:
            lines.append("- insert:")
        else:
            lines.append("[]")
        for row in rows:
            lines.append(f"    - id: {json.dumps(str(row['id']), ensure_ascii=False)}")
            if row.get("name"):
                lines.append(f"      name: {json.dumps(str(row['name']), ensure_ascii=False)}")
            if row.get("disabled"):
                lines.append("      disabled: true")
            cfg = row.get("config") or {}
            if cfg:
                lines.append("      config:")
                cls._emit_mapping(cfg, 8, lines)
        payload = "\n".join(lines) + "\n"

        patch_path.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", dir=patch_path.parent, delete=False
        ) as file:
            pending = Path(file.name)
            try:
                file.write(payload)
                file.close()
                if original is None:
                    os.link(pending, patch_path)
                else:
                    if patch_path.read_text(encoding="utf-8") != original:
                        raise ValueError("Plugin patch changed during the edit. Retry against the current file.")
                    pending.replace(patch_path)
            finally:
                pending.unlink(missing_ok=True)


# -----------------------------------------------------------------------------
# Configuration & Settings Manager
# -----------------------------------------------------------------------------

class ConfigManager:
    @staticmethod
    def init_dsh_workspace(root: Path, profile: str = DEFAULT_PROFILE) -> dict[str, Path]:
        """Initialize a standard DSH directory structure."""
        root.mkdir(parents=True, exist_ok=True)
        profile_dir = root / "profiles" / profile
        profile_dir.mkdir(parents=True, exist_ok=True)
        skills_dir = root / "skills"
        skills_dir.mkdir(parents=True, exist_ok=True)

        # 1. cordis.yml (empty base)
        cordis_yml = profile_dir / "cordis.yml"
        if not cordis_yml.is_file():
            cordis_yml.write_text("# Base Cordis entry file (empty list, maintained by dsh)\n[]\n", encoding="utf-8")

        # 2. cordis.patch.yml (patch layer)
        patch_yml = profile_dir / "cordis.patch.yml"
        if not patch_yml.is_file():
            patch_yml.write_text(
                "# DeepSeek Harness Mount Layer\n# Add your plugins and MCP client servers here\n",
                encoding="utf-8"
            )

        # 3. settings.yaml (runtime settings; namespaces are plugin-registered)
        settings_yml = root / "settings.yaml"
        if not settings_yml.is_file():
            settings_content = """# DeepSeek Harness Runtime Settings
# Namespaces are plugin-registered; see: docs read user-guide/settings.md
telemetry:
  disabled: true

agent-default-model:
  provider: deepseek-official
  model: deepseek-chat

permission:
  defaultPreset: workspace-write
"""
            settings_yml.write_text(settings_content, encoding="utf-8")

        # 4. .env placeholder
        env_file = root / ".env"
        if not env_file.is_file():
            env_file.write_text(
                "# DeepSeek API Key\nDEEPSEEK_API_KEY=\n",
                encoding="utf-8"
            )
            try:
                env_file.chmod(0o600)
            except Exception:
                pass

        return {
            "root": root,
            "profile_dir": profile_dir,
            "cordis_yml": cordis_yml,
            "patch_yml": patch_yml,
            "settings_yml": settings_yml,
            "env_file": env_file,
            "skills_dir": skills_dir,
        }

    @staticmethod
    def disable_telemetry(root: Path, profile: str = DEFAULT_PROFILE, reset_id: bool = True) -> dict[str, Any]:
        """Apply full telemetry disable patches and configuration."""
        root = Path(root).expanduser().resolve()
        profile_dir = root / "profiles" / profile
        profile_dir.mkdir(parents=True, exist_ok=True)
        patch_file = profile_dir / "cordis.patch.yml"

        telemetry_rows = [
            "- id: session-telemetry-otel\n  disabled: true",
            "- id: otel\n  disabled: true",
            "- id: plugin-package-inventory-deepseek\n  config:\n    enabled: false",
            "- id: session-log-deepseek\n  config:\n    enabled: false",
        ]

        existing_content = patch_file.read_text(encoding="utf-8") if patch_file.is_file() else "# DeepSeek Harness Mount Layer\n"
        added = []
        for row in telemetry_rows:
            match = re.search(r"id:\s*([a-zA-Z0-9_\-]+)", row)
            if match:
                row_id = match.group(1)
                if f"id: {row_id}" not in existing_content:
                    existing_content += f"\n{row}\n"
                    added.append(row_id)
        patch_file.write_text(existing_content, encoding="utf-8")

        # Update settings.yaml
        settings_file = root / "settings.yaml"
        if settings_file.is_file():
            text = settings_file.read_text(encoding="utf-8")
            if "telemetry:" in text:
                text = re.sub(r"telemetry:\s*\n\s*disabled:\s*(?:true|false)", "telemetry:\n  disabled: true", text)
            else:
                text = "telemetry:\n  disabled: true\n\n" + text
            settings_file.write_text(text, encoding="utf-8")
        else:
            settings_file.write_text("telemetry:\n  disabled: true\n", encoding="utf-8")

        # Reset anonymous user id if requested
        id_file = root / ".anonymous-user-id"
        id_removed = False
        if reset_id and id_file.is_file():
            id_file.unlink()
            id_removed = True

        return {
            "root": root,
            "patch_file": patch_file,
            "settings_file": settings_file,
            "added_rows": added,
            "id_removed": id_removed,
        }

    @staticmethod
    def get_telemetry_status(root: Path, profile: str = DEFAULT_PROFILE) -> dict[str, Any]:
        """Inspect the current telemetry and identity correlation status."""
        import os
        root = Path(root).expanduser().resolve()
        profile_dir = root / "profiles" / profile
        patch_file = profile_dir / "cordis.patch.yml"
        settings_file = root / "settings.yaml"
        id_file = root / ".anonymous-user-id"

        env_disabled = os.environ.get("DSH_TELEMETRY_DISABLED")
        env_mode = os.environ.get("DSH_TELEMETRY_MODE", "FEEDBACK_ONLY")
        env_url = os.environ.get("DSH_TELEMETRY_OTLP_URL", "https://dsh-otel-collector.deepseeksvc.com/v1/logs")

        patch_text = patch_file.read_text(encoding="utf-8") if patch_file.is_file() else ""
        otel_disabled = "id: session-telemetry-otel\n  disabled: true" in patch_text or "id: session-telemetry-otel" in patch_text and "disabled: true" in patch_text
        inventory_disabled = "plugin-package-inventory-deepseek" in patch_text and "enabled: false" in patch_text
        session_log_disabled = "session-log-deepseek" in patch_text and "enabled: false" in patch_text

        settings_text = settings_file.read_text(encoding="utf-8") if settings_file.is_file() else ""
        settings_disabled = "disabled: true" in settings_text

        has_id = id_file.is_file()
        user_id = id_file.read_text(encoding="utf-8").strip() if has_id else None

        return {
            "env_disabled": env_disabled is not None and env_disabled != "",
            "env_disabled_value": env_disabled,
            "env_mode": env_mode,
            "env_url": env_url,
            "patch_otel_disabled": otel_disabled,
            "patch_inventory_disabled": inventory_disabled,
            "patch_session_log_disabled": session_log_disabled,
            "settings_disabled": settings_disabled,
            "has_anonymous_id": has_id,
            "anonymous_id": user_id,
        }


# -----------------------------------------------------------------------------
# DSH Auditor & Verification Engine
# -----------------------------------------------------------------------------

class DSHAuditor:
    @staticmethod
    def _skill_errors(skill_md: Path) -> list[str]:
        """Check DSH frontmatter basics without executing code or evaluating YAML tags."""
        text = skill_md.read_text(encoding="utf-8-sig")
        match = re.match(r"^---[ \t]*\n(.*?)^---[ \t]*(?:\n|$)", text, re.DOTALL | re.MULTILINE)
        if not match:
            return ["Skill needs opening and closing YAML frontmatter delimiters."]

        errors = []
        fields = dict(re.findall(r"^([\w-]+):[ \t]*(.*)$", match[1], re.MULTILINE))
        for key in ("name", "description", "whenToUse"):
            if key == "whenToUse" and key not in fields:
                continue
            raw = fields.get(key, "").strip()
            if raw.startswith('"'):
                try:
                    raw, _ = json.JSONDecoder().raw_decode(raw)
                except ValueError:
                    errors.append(f"Invalid quoted {key} in frontmatter.")
                    continue
            elif raw.startswith("'"):
                quoted = re.fullmatch(r"'((?:[^']|'')*)'\s*(?:#.*)?", raw)
                if not quoted:
                    errors.append(f"Invalid quoted {key} in frontmatter.")
                    continue
                raw = quoted[1].replace("''", "'")
            else:
                raw = re.split(r"(?:^|\s)#", raw, maxsplit=1)[0].strip()
                if re.search(r":(?:\s|$)", raw) or raw.startswith(("[", "{", "&", "*", "!")):
                    errors.append(f"Quote {key} as a YAML string.")
                    continue
            if not raw.strip():
                errors.append(f"Missing or empty '{key}' field in frontmatter.")
            elif key == "name" and (not KEBAB_CASE_RE.fullmatch(raw) or len(raw) > 64):
                errors.append("Skill name must be kebab-case and at most 64 characters.")
        return errors

    @staticmethod
    def audit_target(target_path: Path) -> dict:
        """Check artifact structure. Compilation and loader behavior need separate checks."""
        target = target_path.resolve()
        errors = []
        warnings = []
        notes = []
        artifact_type = "unknown"

        if not target.exists():
            errors.append(f"Path does not exist: {target}")
        elif target.is_dir():
            if (target / "SKILL.md").is_file():
                artifact_type = "dsh-bundle-skill"
            elif (target / "package.json").is_file():
                artifact_type = "dsh-plugin"
            elif any(target.glob("*.md")) or any(target.glob("*/SKILL.md")):
                artifact_type = "dsh-skills-collection"
        elif target.suffix == ".md":
            artifact_type = "dsh-skill"
        elif target.name.endswith(".patch.yml") or target.name.endswith(".patch.yaml"):
            artifact_type = "dsh-cordis-patch"
        elif target.name in ("settings.yaml", "settings.json"):
            artifact_type = "dsh-settings"
        elif target.suffix in (".json", ".yaml", ".yml"):
            if re.search(r"\b(?:meta|script)\b", target.read_text(encoding="utf-8")):
                artifact_type = "dsh-workflow"

        if artifact_type in ("dsh-skill", "dsh-bundle-skill"):
            skill_md = target / "SKILL.md" if target.is_dir() else target
            errors.extend(DSHAuditor._skill_errors(skill_md))
        elif artifact_type == "dsh-skills-collection":
            for skill_md in sorted([*target.glob("*.md"), *target.glob("*/SKILL.md")]):
                if skill_md.name.lower() != "readme.md":
                    errors.extend(f"{skill_md.relative_to(target)}: {err}" for err in DSHAuditor._skill_errors(skill_md))
        elif artifact_type == "dsh-plugin":
            try:
                pkg = json.loads((target / "package.json").read_text(encoding="utf-8"))
                if not isinstance(pkg, dict):
                    raise ValueError("expected a JSON object")
                if not isinstance(pkg.get("name"), str) or not PACKAGE_NAME_RE.fullmatch(pkg["name"]):
                    errors.append("Plugin package.json needs a valid npm package name.")

                dsh = pkg.get("dsh", {})
                bundle = dsh.get("bundle") if isinstance(dsh, dict) else None
                if bundle is not None:
                    patches = bundle.get("patch") if isinstance(bundle, dict) else None
                    if isinstance(patches, str):
                        patches = [patches]
                    if not isinstance(patches, list) or not patches:
                        errors.append("dsh.bundle.patch needs a file path or a list of paths.")
                    else:
                        for patch in patches:
                            if not isinstance(patch, str) or not patch or not (target / patch).resolve().is_relative_to(target):
                                errors.append("Bundle patch paths must stay inside the package.")
                            elif not (target / patch).is_file():
                                errors.append(f"Bundle patch file is missing: {patch}")
                main = pkg.get("main")
                if main is not None and (not isinstance(main, str) or not main or not (target / main).resolve().is_relative_to(target)):
                    errors.append("Plugin main must be a path inside the package.")
                elif isinstance(main, str) and not (target / main).is_file():
                    if (target / "src/index.ts").is_file():
                        warnings.append("The built entry is missing. Compile the TypeScript source before loading.")
                    else:
                        errors.append(f"Plugin main is missing: {main}")
                elif bundle is None and main is None and not any(
                    (target / name).is_file() for name in ("index.js", "src/index.ts", "lib/index.js")
                ) and not pkg.get("exports"):
                    errors.append("No plugin entry or bundle patch found.")
            except (ValueError, OSError) as error:
                errors.append(f"Invalid package.json: {error}")
            notes.append("Static structure check. Build, load, invoke, and unload in DSH to verify behavior.")
        elif artifact_type == "dsh-workflow":
            text = target.read_text(encoding="utf-8")
            if target.suffix == ".json":
                try:
                    workflow = json.loads(text)
                    if not isinstance(workflow, dict) or not {"meta", "script"} <= workflow.keys():
                        errors.append("Workflow JSON needs 'meta' and 'script' properties.")
                except ValueError as error:
                    errors.append(f"Malformed workflow JSON: {error}")
            elif "meta:" not in text or "script:" not in text:
                errors.append("Workflow needs 'meta' and 'script' sections.")
        elif artifact_type == "dsh-cordis-patch":
            text = target.read_text(encoding="utf-8")
            try:
                if text.startswith(MCPManager.MANAGED_HEADER):
                    entries = MCPManager._managed_entries(text)
                else:
                    entries = MCPManager._parse_patch_entries(text)
                notes.append(f"Found {len(entries)} recognizable patch row(s). Verify composition with DSH.")
            except ValueError as error:
                errors.append(str(error))
        elif artifact_type == "unknown" and not errors:
            errors.append("Unrecognized DSH artifact.")

        return {
            "target": str(target),
            "type": artifact_type,
            "valid": not errors,
            "errors": errors,
            "warnings": warnings,
            "notes": notes,
        }


# -----------------------------------------------------------------------------
# Self-Test Suite
# -----------------------------------------------------------------------------

def run_self_tests() -> None:
    """Run comprehensive self-tests verifying all rabbit-dsh capabilities."""
    print("Running rabbit-dsh self-tests...")
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)

        # 1. Test Documentation Index & Search
        print("  Testing offline docs search...")
        docs = DocsEngine()
        idx = docs.load_index()
        assert len(idx) > 0, "Docs index should not be empty"
        mcp_results = docs.search("mcp client stdio", limit=5)
        assert len(mcp_results) > 0, "Docs search for 'mcp client stdio' should return matches"
        assert any("mcp" in r["path"].lower() for r in mcp_results), "MCP doc should rank in search results"
        assert not any("__VP_HASH_MAP__" in r["snippet"] for r in docs.search("defineTool basic", limit=10))
        section = docs.read_doc("official/reference/subsystems/skills.md", "Local discovery priority")
        assert section and "<projectRoot>/.agents/skills" in section and "## Cordis API" not in section
        try:
            docs.read_doc("skills")
        except ValueError as error:
            assert "Ambiguous document" in str(error)
        else:
            raise AssertionError("Duplicate document basenames must require an exact path")
        print(f"    ✓ Loaded {len(idx)} docs; search returned top match: {mcp_results[0]['path']}")

        # 2. Test Skill Scaffolding (Bundle & Flat)
        print("  Testing skill scaffolding...")
        bundle_skill = Scaffolder.scaffold_skill(
            tmp_path,
            name="test-dsh-bundle",
            description='Verify skills: inspect "quoted" metadata.',
            skill_type="bundle",
            when_to_use="Use when: verifying DSH bundle skills",
        )
        assert (bundle_skill / "SKILL.md").is_file(), "Bundle must contain SKILL.md"
        assert (bundle_skill / "scripts" / "helper.py").is_file(), "Bundle must contain helper.py"
        metadata = (bundle_skill / "SKILL.md").read_text(encoding="utf-8").splitlines()
        assert json.loads(metadata[2].removeprefix("description: ")) == 'Verify skills: inspect "quoted" metadata.'
        assert json.loads(metadata[3].removeprefix("whenToUse: ")) == "Use when: verifying DSH bundle skills"

        flat_skill = Scaffolder.scaffold_skill(
            tmp_path,
            name="test-flat-skill",
            description="A test DSH flat skill for verification",
            skill_type="flat",
        )
        assert flat_skill.is_file() and flat_skill.name == "test-flat-skill.md"
        print("    ✓ Bundle and flat skill scaffolding verified")

        # 3. Test Plugin Scaffolding
        print("  Testing plugin scaffolding...")
        ts_plugin = Scaffolder.scaffold_plugin(
            tmp_path,
            name="@test/dsh-indexer",
            is_ts=True,
            service_name="indexer",
            with_tool=True,
            with_hook=True,
        )
        assert (ts_plugin / "package.json").is_file(), "Plugin must have package.json"
        assert (ts_plugin / "src" / "index.ts").is_file(), "Plugin must have src/index.ts"
        assert (ts_plugin / "cordis.patch.yml").is_file(), "Plugin must have cordis.patch.yml"

        pkg_data = json.loads((ts_plugin / "package.json").read_text(encoding="utf-8"))
        assert pkg_data["main"] == "lib/index.js"
        assert '    - id: "dsh-indexer"' in (ts_plugin / "cordis.patch.yml").read_text(encoding="utf-8")
        js_plugin = Scaffolder.scaffold_plugin(tmp_path, name="test-js", is_ts=False)
        js_entry = (js_plugin / "index.js").read_text(encoding="utf-8")
        assert "export function apply(ctx)" in js_entry and "require(" not in js_entry
        print("    ✓ TypeScript plugin scaffolding verified")

        # 4. Test Workflow Scaffolding (official WorkflowMeta vocabulary only)
        print("  Testing workflow scaffolding...")
        wf_path = tmp_path / "ralph-loop.json"
        Scaffolder.scaffold_workflow(wf_path, name="verify-fix", template="ralph", output_format="json")
        assert wf_path.is_file()
        wf_json = json.loads(wf_path.read_text(encoding="utf-8"))
        assert set(wf_json["meta"]) <= {"name", "description", "whenToUse", "phases"}, (
            f"Workflow meta must stay within WorkflowMeta vocabulary: {sorted(wf_json['meta'])}"
        )
        assert wf_json["meta"].get("whenToUse"), "Ralph template should carry a whenToUse hint"
        assert "SUCCESS_ALL_TESTS_PASSED" in wf_json["script"]
        assert "iteration <" in wf_json["script"], "Ralph loop must keep an iteration bound in the script"
        print("    ✓ Ralph workflow scaffolding verified (official WorkflowMeta)")

        # 5. Test MCP Manager
        print("  Testing MCP manager...")
        patch_file = tmp_path / "cordis.patch.yml"
        cli = [sys.executable, str(Path(__file__).resolve())]
        subprocess.run(
            [*cli, "mcp", "add", "github", "--path", str(patch_file), "--command", "npx",
             "--arg=-y", "--arg=@modelcontextprotocol/server-github"],
            check=True, capture_output=True,
        )
        servers = MCPManager.list_servers(patch_file)
        assert len(servers) == 1, f"Expected 1 server, got {len(servers)}"
        assert servers[0]["serverName"] == "github"
        assert servers[0]["toolPrefix"] == "mcp__github__<toolName>"
        assert servers[0]["args"] == ["-y", "@modelcontextprotocol/server-github"]

        # Add second server
        MCPManager.add_server(
            patch_file,
            server_name="filesystem",
            command="npx",
            args=["-y", "@modelcontextprotocol/server-filesystem", "/tmp"],
        )
        servers = MCPManager.list_servers(patch_file)
        assert len(servers) == 2, f"Expected 2 servers, got {len(servers)}"

        # Remove first server
        removed = MCPManager.remove_server(patch_file, "github")
        assert removed, "Expected successful removal of server"
        servers = MCPManager.list_servers(patch_file)
        assert len(servers) == 1 and servers[0]["serverName"] == "filesystem"
        native_patch = tmp_path / "native.patch.yml"
        original = (
            "# Keep this override\n- id: otel\n  disabled: true\n"
            "- insert:\n    - id: mcp-old\n      name: '@deepseek-ai/dsh-mcp-client'\n"
            "      config:\n        serverName: old\n"
        )
        native_patch.write_text(original, encoding="utf-8")
        assert MCPManager.list_servers(native_patch)[0]["serverName"] == "old"
        result = subprocess.run(
            [*cli, "mcp", "remove", "old", "--path", str(native_patch)],
            capture_output=True, text=True,
        )
        assert result.returncode != 0 and native_patch.read_text(encoding="utf-8") == original
        print("    ✓ MCP add, list, and remove verified")

        # 5b. Test MCP env-ref writes a YAML managed patch with !!js tags
        print("  Testing MCP env-ref (YAML managed patch)...")
        yaml_patch = tmp_path / "plugin.patch.yml"
        result = subprocess.run(
            [*cli, "mcp", "add", "secret-srv", "--path", str(yaml_patch), "--command", "npx",
             "--arg=-y", "--arg=@example/server", "--env-ref", "EXAMPLE_TOKEN=EXAMPLE_TOKEN"],
            check=True, capture_output=True, text=True,
        )
        yaml_text = yaml_patch.read_text(encoding="utf-8")
        assert yaml_text.startswith(PatchManager.MANAGED_HEADER)
        assert "env:" in yaml_text and "!!js process.env.EXAMPLE_TOKEN" in yaml_text, (
            "env-ref must nest under config.env as a !!js tag"
        )
        listed = PatchManager.list_rows(yaml_patch)
        assert listed and listed[0]["id"] == "mcp-secret-srv"
        assert listed[0]["config"]["env"]["EXAMPLE_TOKEN"] == "!!js process.env.EXAMPLE_TOKEN"
        removed = PatchManager.remove_row(yaml_patch, "mcp-secret-srv")
        assert removed and not PatchManager.list_rows(yaml_patch)
        print("    ✓ MCP --env-ref YAML roundtrip verified (nested config.env)")

        # 5c. Test generic plugin patch manager
        print("  Testing plugin patch manager...")
        plugin_patch = tmp_path / "rows.patch.yml"
        PatchManager.add_row(
            plugin_patch, row_id="docker-plugin", name="my-docker-plugin",
            config={"socketPath": "/var/run/docker.sock"},
        )
        PatchManager.add_row(plugin_patch, row_id="otel", name="otel", disabled=True)
        rows = PatchManager.list_rows(plugin_patch)
        assert [r["id"] for r in rows] == ["docker-plugin", "otel"]
        assert rows[0]["config"]["socketPath"] == "/var/run/docker.sock"
        assert rows[1]["disabled"] is True
        PatchManager.add_row(plugin_patch, row_id="docker-plugin", name="my-docker-plugin",
                             config={"socketPath": "/run/docker.sock"})
        rows = PatchManager.list_rows(plugin_patch)
        assert len(rows) == 2 and rows[0]["config"]["socketPath"] == "/run/docker.sock"
        assert PatchManager.remove_row(plugin_patch, "otel")
        assert [r["id"] for r in PatchManager.list_rows(plugin_patch)] == ["docker-plugin"]
        print("    ✓ Plugin patch add, list, replace, and remove verified")

        # 5d. Test docs concept map
        print("  Testing docs concept map...")
        engine = DocsEngine()
        map_rows = engine.doc_map()
        assert len(map_rows) >= 10, f"Concept map should cover the main components, got {len(map_rows)}"
        all_paths = [path for _, _, paths in map_rows for path in paths]
        assert all_paths, "Concept map rows must resolve to offline docs"
        filtered = engine.doc_map("workflow")
        assert filtered and all("workflow" in c or "workflow" in b.lower() for c, b, _ in filtered)
        print(f"    ✓ Concept map verified ({len(map_rows)} concepts, filterable)")

        # 6. Test Config Manager
        print("  Testing config manager and telemetry...")
        ws_info = ConfigManager.init_dsh_workspace(tmp_path / "workspace")
        assert ws_info["cordis_yml"].is_file()
        assert ws_info["settings_yml"].is_file()
        assert ws_info["env_file"].is_file()
        telem_res = ConfigManager.disable_telemetry(tmp_path / "workspace")
        assert telem_res["patch_file"].is_file()
        st = ConfigManager.get_telemetry_status(tmp_path / "workspace")
        assert st["patch_otel_disabled"]
        assert st["settings_disabled"]
        print("    ✓ Workspace init and telemetry disable verified")

        # 7. Test Auditor
        print("  Testing DSH auditor...")
        audit_skill = DSHAuditor.audit_target(bundle_skill)
        assert audit_skill["valid"], f"Bundle skill audit failed: {audit_skill['errors']}"
        bad_skill = tmp_path / "collection" / "bad-skill"
        bad_skill.mkdir(parents=True)
        (bad_skill / "SKILL.md").write_text(
            "---\nname: bad-skill\ndescription: Review: invalid scalar\n---\n", encoding="utf-8"
        )
        assert not DSHAuditor.audit_target(bad_skill.parent)["valid"]
        assert not DSHAuditor.audit_target(tmp_path / "missing")["valid"]

        audit_plugin = DSHAuditor.audit_target(ts_plugin)
        assert audit_plugin["valid"], f"Plugin audit failed: {audit_plugin['errors']}"

        audit_wf = DSHAuditor.audit_target(wf_path)
        assert audit_wf["valid"], f"Workflow audit failed: {audit_wf['errors']}"

        audit_patch = DSHAuditor.audit_target(patch_file)
        assert audit_patch["valid"], f"Patch audit failed: {audit_patch['errors']}"
        print("    ✓ Artifact audit engine verified")

        # 8. Born-clean: deep artifact linter must pass everything we scaffold.
        print("  Testing born-clean artifacts (audit_dsh_artifacts)...")
        import importlib.util as _ilu
        sys.dont_write_bytecode = True
        linter_path = Path(__file__).resolve().parent / "audit_dsh_artifacts.py"
        spec = _ilu.spec_from_file_location("audit_dsh_artifacts", linter_path)
        linter = _ilu.module_from_spec(spec)
        spec.loader.exec_module(linter)

        for artifact in (wf_path, yaml_patch):
            fdeep = linter.Findings(artifact)
            linter.lint_artifact(artifact, fdeep)
            deep_errors = [x for x in fdeep.items if x["severity"] == "error"]
            assert not deep_errors, f"Born-clean failed for {artifact.name}: {deep_errors}"

        for template, out_format in (("ralph", "yaml"), ("pr-review", "yaml"), ("standard", "yaml"),
                                     ("ralph", "json"), ("pr-review", "json"), ("standard", "json")):
            wf_file = tmp_path / f"born-clean-{template}-{out_format}.{ 'yml' if out_format == 'yaml' else 'json' }"
            Scaffolder.scaffold_workflow(wf_file, name=f"born clean {template}", template=template, output_format=out_format)
            fdeep = linter.Findings(wf_file)
            linter.lint_artifact(wf_file, fdeep)
            deep_errors = [x for x in fdeep.items if x["severity"] == "error"]
            assert not deep_errors, f"Born-clean failed for {template}/{out_format}: {deep_errors}"
        print("    ✓ Scaffolded workflows and patches pass the deep linter (DA-01..DA-21)")

    print("\nAll rabbit-dsh self-tests PASSED (11/11).\n")


# -----------------------------------------------------------------------------
# CLI Entrypoint
# -----------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        prog="rabbit-dsh",
        description="Unified DeepSeek Harness (DSH) Studio & Offline Documentation Companion."
    )
    parser.add_argument("--self-test", action="store_true", help="Run comprehensive self-tests and exit")

    subparsers = parser.add_subparsers(dest="command", help="Available subcommands")

    # 1. scaffold
    scaffold_p = subparsers.add_parser("scaffold", help="Scaffold DSH skills, plugins, and workflows")
    scaffold_sub = scaffold_p.add_subparsers(dest="scaffold_type", required=True)

    # scaffold skill
    sc_skill = scaffold_sub.add_parser("skill", help="Scaffold a DSH-compliant skill")
    sc_skill.add_argument("target", help="Directory where skill will be created")
    sc_skill.add_argument("--name", "-n", required=True, help="Skill name (kebab-case)")
    sc_skill.add_argument("--description", "-d", required=True, help="Trigger-oriented description")
    sc_skill.add_argument("--type", choices=["bundle", "flat"], default="bundle", help="Skill format")
    sc_skill.add_argument("--when-to-use", help="Optional whenToUse trigger condition")
    sc_skill.add_argument("--disable-model-invocation", action="store_true", help="Disable direct model invocation")
    sc_skill.add_argument("--user-invocable", action="store_true", help="Enable user invocation")

    # scaffold plugin
    sc_plugin = scaffold_sub.add_parser("plugin", help="Scaffold a Cordis-based DSH plugin package")
    sc_plugin.add_argument("target", help="Directory where plugin package will be created")
    sc_plugin.add_argument("--name", "-n", required=True, help="npm package name (e.g. @scope/dsh-my-plugin)")
    sc_plugin.add_argument("--js", dest="is_ts", action="store_false", default=True, help="Use JavaScript instead of TypeScript")
    sc_plugin.add_argument("--service", help="Custom Cordis service name")
    sc_plugin.add_argument("--no-tool", dest="with_tool", action="store_false", default=True, help="Do not include starter tool")
    sc_plugin.add_argument("--no-hook", dest="with_hook", action="store_false", default=True, help="Do not include lifecycle hooks")
    sc_plugin.add_argument("--with-command", action="store_true", help="Include starter user command")

    # scaffold workflow
    sc_wf = scaffold_sub.add_parser("workflow", help="Scaffold a DSH multi-agent workflow or Ralph loop")
    sc_wf.add_argument("target", help="Target output file path")
    sc_wf.add_argument("--name", "-n", required=True, help="Workflow name")
    sc_wf.add_argument("--template", choices=["ralph", "pr-review", "standard"], default="ralph", help="Workflow template")
    sc_wf.add_argument("--format", choices=["json", "yaml"], default="json", help="Output format")

    # 2. mcp
    mcp_p = subparsers.add_parser("mcp", help="Manage MCP client servers in cordis.patch.yml")
    mcp_sub = mcp_p.add_subparsers(dest="mcp_action", required=True)

    # mcp list
    mcp_list = mcp_sub.add_parser("list", help="List all configured MCP servers")
    mcp_list.add_argument("--profile", default=DEFAULT_PROFILE, help="Profile name (default: web)")
    mcp_list.add_argument("--path", help="Custom path to cordis.patch.yml")

    # mcp add
    mcp_add = mcp_sub.add_parser("add", help="Add or update an MCP server configuration")
    mcp_add.add_argument("server_name", help="MCP server name (e.g. github, filesystem)")
    mcp_add.add_argument("--command", "-c", dest="executable", help="Executable command for stdio")
    server_args = mcp_add.add_mutually_exclusive_group()
    server_args.add_argument("--args", "-a", nargs="*", help="Command arguments without leading dashes")
    server_args.add_argument("--arg", action="append", help="One command argument, repeat as --arg=-y")
    mcp_add.add_argument("--transport", choices=["stdio", "streamable-http", "sse"], default="stdio")
    mcp_add.add_argument("--url", help="Server URL (for HTTP/SSE transport)")
    mcp_add.add_argument("--env", nargs="*", help="Environment variables as KEY=VALUE pairs")
    mcp_add.add_argument("--env-ref", dest="env_ref", action="append",
                         help="Environment variable by reference KEY=ENV_VAR, written as a `!!js process.env.<VAR>` YAML tag (requires a YAML managed patch)")
    mcp_add.add_argument("--path", required=True, help="Path to a new or rabbit-dsh managed patch")

    # 2b. patch (generic plugin rows)
    patch_p = subparsers.add_parser("patch", help="Mount or inspect plugin rows in a managed cordis patch")
    patch_sub = patch_p.add_subparsers(dest="patch_action", required=True)

    patch_list = patch_sub.add_parser("list", help="List patch rows (managed or native YAML, read-only)")
    patch_list.add_argument("--profile", default=DEFAULT_PROFILE, help="Profile name (default: web)")
    patch_list.add_argument("--path", help="Custom path to cordis.patch.yml")

    patch_add = patch_sub.add_parser("add", help="Insert or update a plugin row (insert: block)")
    patch_add.add_argument("row_id", help="Unique patch row id (e.g. docker-plugin)")
    patch_add.add_argument("--name", "-n", required=True, help="Plugin package or component name")
    patch_add.add_argument("--config", action="append", help="Config entry as KEY=VALUE (repeatable)")
    patch_add.add_argument("--env-ref", dest="env_ref", action="append",
                           help="Config entry by env reference KEY=ENV_VAR -> !!js process.env.<VAR> (repeatable)")
    patch_add.add_argument("--disabled", action="store_true", help="Write the row as disabled: true")
    patch_add.add_argument("--profile", default=DEFAULT_PROFILE, help="Profile name when --path is omitted")
    patch_add.add_argument("--path", help="Path to a new or rabbit-dsh managed plugin patch (YAML)")

    patch_rm = patch_sub.add_parser("remove", help="Remove a patch row by id from a managed plugin patch")
    patch_rm.add_argument("row_id", help="Patch row id to remove")
    patch_rm.add_argument("--path", required=True, help="Path to a rabbit-dsh managed plugin patch")

    # mcp remove
    mcp_rm = mcp_sub.add_parser("remove", help="Remove an MCP server from cordis.patch.yml")
    mcp_rm.add_argument("server_name", help="MCP server name to remove")
    mcp_rm.add_argument("--path", required=True, help="Path to a rabbit-dsh managed patch")

    # 3. docs
    docs_p = subparsers.add_parser("docs", help="Offline documentation search and lookup")
    docs_sub = docs_p.add_subparsers(dest="docs_action", required=True)

    # docs search
    docs_search = docs_sub.add_parser("search", help="Full-text search offline DSH documentation")
    docs_search.add_argument("query", help="Search query words")
    docs_search.add_argument("--limit", "-l", type=int, default=5, help="Maximum number of results")
    docs_search.add_argument("--source", choices=["official", "community"], help="Limit results by source")

    # docs read
    docs_read = docs_sub.add_parser("read", help="Read offline documentation page")
    docs_read.add_argument("doc_name", help="Document path or name (e.g. features/skills, workflow, mcp)")
    docs_read.add_argument("--section", help="Read one section by its exact Markdown heading")

    # docs list
    docs_list = docs_sub.add_parser("list", help="List all offline documentation topics")

    # docs map
    docs_map = docs_sub.add_parser("map", help="Concept map: what DSH components exist and where they are documented")
    docs_map.add_argument("topic", nargs="?", help="Filter concepts by substring (e.g. patch, workflow, mcp)")

    # 4. config
    cfg_p = subparsers.add_parser("config", help="DSH configuration and workspace management")
    cfg_sub = cfg_p.add_subparsers(dest="cfg_action", required=True)

    # config init
    cfg_init = cfg_sub.add_parser("init", help="Initialize clean DSH workspace or profile")
    cfg_init.add_argument("target", nargs="?", default=".", help="Target workspace directory")
    cfg_init.add_argument("--profile", default=DEFAULT_PROFILE, help="Profile name (default: web)")

    # config telemetry
    cfg_telemetry = cfg_sub.add_parser("telemetry", help="Manage or block DSH telemetry and tracking")
    cfg_telemetry.add_argument("telemetry_action", choices=["disable", "status"], help="Telemetry action")
    cfg_telemetry.add_argument("--root", default="~/.dsh", help="DSH root directory (default: ~/.dsh)")
    cfg_telemetry.add_argument("--profile", default=DEFAULT_PROFILE, help="Profile name (default: web)")
    cfg_telemetry.add_argument("--reset-id", action="store_true", help="Reset/delete anonymous user ID (.anonymous-user-id)")

    # 5. audit
    audit_p = subparsers.add_parser("audit", help="Audit and validate DSH skills, plugins, workflows, or patches")
    audit_p.add_argument("target", help="Target file or directory to audit")

    args = parser.parse_args()

    if args.self_test:
        run_self_tests()
        sys.exit(0)

    if not args.command:
        parser.print_help()
        sys.exit(1)

    # Execute commands
    if args.command == "scaffold":
        target = Path(args.target)
        if args.scaffold_type == "skill":
            out = Scaffolder.scaffold_skill(
                target,
                name=args.name,
                description=args.description,
                skill_type=args.type,
                when_to_use=args.when_to_use,
                disable_model_invocation=args.disable_model_invocation,
                user_invocable=args.user_invocable,
            )
            print(f"✓ Created DSH {args.type} skill at: {out}")
        elif args.scaffold_type == "plugin":
            out = Scaffolder.scaffold_plugin(
                target,
                name=args.name,
                is_ts=args.is_ts,
                service_name=args.service,
                with_tool=args.with_tool,
                with_hook=args.with_hook,
                with_command=args.with_command,
            )
            print(f"✓ Created DSH plugin package at: {out}")
        elif args.scaffold_type == "workflow":
            out = Scaffolder.scaffold_workflow(
                target,
                name=args.name,
                template=args.template,
                output_format=args.format,
            )
            print(f"✓ Created DSH workflow at: {out}")

    elif args.command == "mcp":
        custom_p = Path(args.path) if args.path else None
        patch_path = MCPManager.get_patch_path(getattr(args, "profile", DEFAULT_PROFILE), custom_p)
        if args.mcp_action == "list":
            servers = MCPManager.list_servers(patch_path)
            if not servers:
                print(f"No MCP servers found in {patch_path}")
            else:
                print(f"MCP servers in {patch_path}:")
                for s in servers:
                    print(f"  • {s['serverName']} ({s['transport']}) -> Tool prefix: {s['toolPrefix']}")
                    if s.get("command"):
                        args_str = " ".join(s.get("args", []))
                        print(f"    cmd: {s['command']} {args_str}".strip())
                    if s.get("url"):
                        print(f"    url: {s['url']}")
        elif args.mcp_action == "add":
            env_refs = {}
            for item in (args.env_ref or []):
                if "=" not in item:
                    sys.exit(f"rabbit-dsh: --env-ref expects KEY=ENV_VAR, got '{item}'")
                ref_key, _, ref_var = item.partition("=")
                env_refs[ref_key.strip()] = ref_var.strip()
            if env_refs:
                # YAML tags cannot survive the JSON managed format; use YAML rows.
                if patch_path.is_file() and patch_path.read_text(encoding="utf-8").startswith(MCPManager.MANAGED_HEADER):
                    sys.exit("rabbit-dsh: --env-ref needs a YAML managed patch, but the target is a JSON managed MCP patch. Use a new --path.")
                cfg: dict = {"serverName": args.server_name, "transport": args.transport}
                env_cfg: dict = {}
                for ref_key, ref_var in env_refs.items():
                    if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", ref_var):
                        sys.exit(f"rabbit-dsh: env var name '{ref_var}' is not a valid shell identifier.")
                    env_cfg[ref_key] = f"!!js process.env.{ref_var}"
                if env_cfg:
                    cfg["env"] = env_cfg
                if args.transport == "stdio":
                    if not args.executable:
                        sys.exit("rabbit-dsh: --command is required for stdio transport.")
                    cfg["command"] = args.executable
                    cmd_args = args.arg if args.arg is not None else args.args
                    if cmd_args:
                        cfg["args"] = cmd_args
                elif args.transport in ("streamable-http", "sse"):
                    if not args.url:
                        sys.exit(f"rabbit-dsh: --url is required for {args.transport} transport.")
                    cfg["url"] = args.url
                else:
                    sys.exit(f"rabbit-dsh: unknown MCP transport: {args.transport}")
                PatchManager.add_row(
                    patch_path,
                    row_id=f"mcp-{args.server_name}",
                    name="@deepseek-ai/dsh-mcp-client",
                    config=cfg,
                )
                print(f"✓ Added MCP server '{args.server_name}' (YAML managed patch) to {patch_path}")
                print(f"  Env refs written as !!js process.env.<VAR>; tool prefix: mcp__{args.server_name}__<toolName>")
            else:
                env_map = {}
                if args.env:
                    for item in args.env:
                        if "=" in item:
                            k, v = item.split("=", 1)
                            env_map[k] = v
                MCPManager.add_server(
                    patch_path,
                    server_name=args.server_name,
                    command=args.executable,
                    args=args.arg if args.arg is not None else args.args,
                    transport=args.transport,
                    url=args.url,
                    env=env_map if env_map else None,
                )
                print(f"✓ Added MCP server '{args.server_name}' to {patch_path}")
                print(f"  After DSH loads this patch, inspect tools prefixed mcp__{args.server_name}__")
        elif args.mcp_action == "remove":
            current_text = patch_path.read_text(encoding="utf-8") if patch_path.is_file() else ""
            if current_text.startswith(PatchManager.MANAGED_HEADER):
                removed = PatchManager.remove_row(patch_path, f"mcp-{args.server_name}")
                if not removed:
                    removed = PatchManager.remove_row(patch_path, args.server_name)
            else:
                removed = MCPManager.remove_server(patch_path, args.server_name)
            if removed:
                print(f"✓ Removed MCP server '{args.server_name}' from {patch_path}")
            else:
                print(f"MCP server '{args.server_name}' not found in {patch_path}")

    elif args.command == "patch":
        custom_p = Path(args.path) if getattr(args, "path", None) else None
        patch_path = PatchManager.get_patch_path(getattr(args, "profile", DEFAULT_PROFILE), custom_p)
        if args.patch_action == "list":
            rows = PatchManager.list_rows(patch_path)
            if not rows:
                print(f"No patch rows found in {patch_path}")
            else:
                source = "managed" if patch_path.is_file() and patch_path.read_text(encoding="utf-8").startswith(PatchManager.MANAGED_HEADER) else "native (read-only view)"
                print(f"Patch rows in {patch_path} ({source}):")
                for row in rows:
                    rid = row.get("id", "?")
                    name = row.get("name", "?")
                    disabled = " [disabled]" if row.get("disabled") in (True, "true") else ""
                    print(f"  • {rid} -> {name}{disabled}")
                    cfg = row.get("config") or {}
                    for key, value in cfg.items():
                        print(f"      {key}: {value}")
        elif args.patch_action == "add":
            config_map = {}
            for item in (args.config or []):
                if "=" not in item:
                    sys.exit(f"rabbit-dsh: --config expects KEY=VALUE, got '{item}'")
                cfg_key, _, cfg_value = item.partition("=")
                config_map[cfg_key.strip()] = cfg_value.strip()
            env_refs = {}
            for item in (args.env_ref or []):
                if "=" not in item:
                    sys.exit(f"rabbit-dsh: --env-ref expects KEY=ENV_VAR, got '{item}'")
                ref_key, _, ref_var = item.partition("=")
                env_refs[ref_key.strip()] = ref_var.strip()
            PatchManager.add_row(
                patch_path,
                row_id=args.row_id,
                name=args.name,
                config=config_map,
                env_refs=env_refs,
                disabled=args.disabled,
            )
            print(f"✓ Mounted '{args.row_id}' -> {args.name} in {patch_path}")
            if env_refs:
                print("  Secret refs written as !!js process.env.<VAR> tags")
        elif args.patch_action == "remove":
            if PatchManager.remove_row(patch_path, args.row_id):
                print(f"✓ Removed patch row '{args.row_id}' from {patch_path}")
            else:
                print(f"Patch row '{args.row_id}' not found in {patch_path}")

    elif args.command == "docs":
        engine = DocsEngine()
        if args.docs_action == "search":
            results = engine.search(args.query, limit=args.limit, source=args.source)
            if not results:
                print(f"No offline documentation matches found for '{args.query}'.")
            else:
                print(f"Found {len(results)} offline document(s) matching '{args.query}':\n")
                for i, r in enumerate(results, 1):
                    tag = r.get("source_tag", "")
                    print(f"  {i}. {tag} [{r['title']}] ({r['path']})")
                    if r["section"]:
                        print(f"     Section: {r['section']}")
                    if r["snippet"]:
                        print(f"     \"{r['snippet']}\"")
                    print()
        elif args.docs_action == "read":
            content = engine.read_doc(args.doc_name, args.section)
            if not content:
                sys.exit(f"Document '{args.doc_name}' not found in offline catalog.")
            else:
                print(content)
        elif args.docs_action == "list":
            cats = engine.list_categories()
            print("Offline DeepSeek Harness Documentation Topics:\n")
            for cat, docs in sorted(cats.items()):
                print(f"📁 {cat.upper()} ({len(docs)} documents):")
                for d in docs:
                    print(f"   • {d['title']} ({d['path']})")
                print()
        elif args.docs_action == "map":
            rows = engine.doc_map(args.topic)
            total = len(engine.load_index())
            if not rows:
                print(f"No concept matches '{args.topic}'. Try: architecture, skills, plugins, patch, workflows, ralph, mcp, config, env, permissions, persona, session, tools, commands, subagents, telemetry.")
            else:
                print(f"DeepSeek Harness Concept Map ({total} offline docs; read any page with `docs read <path>`):\n")
                for concept, blurb, paths in rows:
                    print(f"  {concept} — {blurb}")
                    for path in paths:
                        print(f"      → {path}")
                    print()

    elif args.command == "config":
        if args.cfg_action == "init":
            target = Path(args.target).resolve()
            res = ConfigManager.init_dsh_workspace(target, profile=args.profile)
            print(f"✓ Initialized DSH workspace at {res['root']}:")
            print(f"  - Profile ({args.profile}): {res['profile_dir']}")
            print(f"  - Cordis Base: {res['cordis_yml']}")
            print(f"  - Cordis Patch: {res['patch_yml']}")
            print(f"  - Runtime Settings: {res['settings_yml']}")
            print(f"  - Env config: {res['env_file']}")
        elif args.cfg_action == "telemetry":
            root = Path(args.root).expanduser().resolve()
            if args.telemetry_action == "disable":
                res = ConfigManager.disable_telemetry(root, profile=args.profile, reset_id=args.reset_id)
                print(f"✓ Telemetry and reporting disabled in {root}:")
                print(f"  - Cordis Patch ({args.profile}): {res['patch_file']}")
                print(f"  - Settings: {res['settings_file']}")
                if res['added_rows']:
                    print(f"  - Disabled components: {', '.join(res['added_rows'])}")
                if res['id_removed']:
                    print("  - Removed .anonymous-user-id (tracking UUID reset)")
                print("\nRecommended environment variables to export in your shell:")
                print("  export DSH_TELEMETRY_DISABLED=1")
                print("  export DSH_TELEMETRY_MODE=DISABLED")
                print("  export DSH_TELEMETRY_OTLP_URL=http://127.0.0.1:9/sink")
            elif args.telemetry_action == "status":
                st = ConfigManager.get_telemetry_status(root, profile=args.profile)
                print(f"DeepSeek Harness Telemetry Status for {root}:")
                print(f"  • Environment switch (DSH_TELEMETRY_DISABLED): {'DISABLED (Active)' if st['env_disabled'] else 'NOT SET'}")
                print(f"  • Telemetry Mode (DSH_TELEMETRY_MODE): {st['env_mode']}")
                print(f"  • Telemetry OTLP URL: {st['env_url']}")
                print(f"  • cordis.patch.yml otel disabled: {'YES' if st['patch_otel_disabled'] else 'NO'}")
                print(f"  • cordis.patch.yml inventory disabled: {'YES' if st['patch_inventory_disabled'] else 'NO'}")
                print(f"  • cordis.patch.yml session log disabled: {'YES' if st['patch_session_log_disabled'] else 'NO'}")
                print(f"  • settings.yaml telemetry disabled: {'YES' if st['settings_disabled'] else 'NO'}")
                print(f"  • Anonymous Tracking ID: {st['anonymous_id'] if st['has_anonymous_id'] else 'None (Clean)'}")

    elif args.command == "audit":
        target = Path(args.target)
        result = DSHAuditor.audit_target(target)
        status = "PASS" if result["valid"] else "FAIL"
        print(f"Auditing: {result['target']}")
        print(f"Artifact Type: {result['type']}")
        print(f"Verdict: {status}")
        if result["errors"]:
            print("\nErrors:")
            for e in result["errors"]:
                print(f"  ❌ {e}")
        if result["warnings"]:
            print("\nWarnings:")
            for w in result["warnings"]:
                print(f"  ⚠️  {w}")
        if result["notes"]:
            print("\nNotes:")
            for n in result["notes"]:
                print(f"  ℹ️  {n}")
        sys.exit(0 if result["valid"] else 1)


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError) as error:
        sys.exit(f"rabbit-dsh: {error}")
