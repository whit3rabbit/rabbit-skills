#!/usr/bin/env python3
"""DeepSeek Harness (DSH) Artifact Static Linter.

Audits DSH runtime artifacts that rabbit_dsh.py's quick `audit` command treats
shallowly: cordis patch files, agent presets, workflow definitions, settings
documents, optional bundle manifests, credential files, and session JSONL logs.

Checks:
  - DA-01..DA-08:  Cordis patch + agent preset structure (insert/override verbs,
                   duplicate ids, `!!js` placement, MCP client rows, persona rows,
                   plaintext secrets).
  - DA-09..DA-12:  Workflow definitions (WorkflowMeta vocabulary, phase
                   declarations, script orchestration primitives, Ralph bounds).
  - DA-13..DA-16:  settings.yaml namespaces (agent-default-model, permission
                   presets, telemetry switches, custom LLM providers).
  - DA-17:         Optional `skill.json` bundle-manifest consistency.
  - DA-18:         Credential file permissions (.env / .credentials.yaml).
  - DA-19..DA-21:  Session JSONL logs (header version gate, seq monotonicity,
                   surfaceOp rules, unknown event types).

Every fix hint ends with an offline documentation pointer (`docs read <path>`)
so an agent new to DeepSeek Harness can teach itself from the bundled corpus.

Zero external dependencies - strictly Python 3 standard library.
Read-only: target code is never executed or imported; YAML is parsed by a
restricted line scanner, not a full YAML engine, so unrecognized shapes are
reported as notes instead of false errors.

Usage:
  python3 audit_dsh_artifacts.py <artifact-path> [options]
  python3 audit_dsh_artifacts.py --list-checks
  python3 audit_dsh_artifacts.py --self-test
"""

import argparse
import json
import re
import stat
import sys
import tempfile
from pathlib import Path

CHECK_INFO = {
    "DA-01": (
        "Patch document is not a top-level array of insert/override entries",
        "A cordis patch (`cordis.patch.yml`, `*.patch.yml`, `agent.cordis.yml`) must be a top-level YAML array whose entries are either `insert:` blocks with an indented row list, or bare rows located by `id`. Verbs like `replace:` or `ignore:` do not exist.",
        "Restructure the document as a YAML array of `insert:` blocks or `id:` row overrides. See: `docs read learn/core/plugin-anatomy.md` (section 6).",
    ),
    "DA-02": (
        "Inserted patch row is missing `id` or `name`",
        "Rows inside an `insert:` block append new components and are keyed by `id`; without a stable `id` (and the plugin `name`) the row cannot be targeted by later patches.",
        "Give every inserted row a unique `id` and the plugin package `name`. See: `docs read learn/core/plugin-anatomy.md` (section 6).",
    ),
    "DA-03": (
        "Duplicate patch row id",
        "Patch rows are keyed by `id`; two rows with the same id in one layer collide and the later row silently replaces the earlier one.",
        "Rename one of the rows so ids stay unique within the file. See: `docs read learn/core/plugin-anatomy.md` (section 6).",
    ),
    "DA-04": (
        "`!!js` expression outside a `config` value or `disabled` field",
        "The `!!js <expr>` JavaScript-expression tag is only interpreted inside `config` values (and `disabled` flags). Elsewhere it stays a literal string or fails to load.",
        "Move the `!!js` expression into a `config` value or `disabled` field, or replace it with a literal. See: `docs read features/mcp.md` (Configuration).",
    ),
    "DA-05": (
        "MCP client row has an invalid or duplicate `serverName`",
        "MCP rows mount `@deepseek-ai/dsh-mcp-client`; `serverName` must match `[A-Za-z0-9_-]{1,32}` and be unique across live instances. It becomes the `mcp__<serverName>__<tool>` prefix.",
        "Set a unique `serverName` of 1-32 characters from A-Za-z0-9_- . See: `docs read features/mcp.md` (Configuration).",
    ),
    "DA-06": (
        "MCP client row transport/fields mismatch",
        "`stdio` transport requires `command`; `streamable-http` requires `url`. `sse` appears only in older docs/examples - current documentation lists `stdio` and `streamable-http`.",
        "Align the row with its transport: stdio -> `command` (+ optional `args`/`env`/`cwd`), streamable-http -> `url` (+ optional `headers`). See: `docs read features/mcp.md` (field table).",
    ),
    "DA-07": (
        "Potential plaintext credential in patch",
        "Patches are plain files read by the harness; inline secret literals leak through logs and backups. The documented pattern is a `!!js process.env.VAR` reference.",
        "Replace the literal with `KEY: !!js process.env.VAR`. See: `docs read features/mcp.md` (env example).",
    ),
    "DA-08": (
        "Persona preset row is invalid",
        "In an agent preset (`agent.cordis.yml`), the `@deepseek-ai/dsh-persona` row must carry `config.text` (the system-prompt line); `complete` and `includeRuntimeContext` must be strict booleans.",
        "Add a non-empty `config.text` and keep `complete`/`includeRuntimeContext` as `true`/`false`. See: `docs read features/persona.md`.",
    ),
    "DA-09": (
        "Workflow meta is invalid",
        "Workflow `meta` requires `name` (short kebab-case; also the persistence key) and `description`; the engine validates meta and rejects loud BEFORE the script runs.",
        "Give `meta` a kebab-case `name` and a one-line `description`. See: `docs read features/workflow.md`.",
    ),
    "DA-10": (
        "Workflow meta contains unknown fields",
        "The official `WorkflowMeta` vocabulary is exactly `{name, description, whenToUse?, phases?}`. Fields like `mode` or `maxIterations` were emitted by older scaffolders but are not part of the engine schema.",
        "Remove unknown meta fields; keep only name/description/whenToUse/phases. See: `docs read official/reference/subsystems/workflow.md` (WorkflowMeta).",
    ),
    "DA-11": (
        "phase() call does not match declared meta.phases",
        "`phases` is progress vocabulary only: `phase()` calls match declared titles for observers; undeclared titles never show up in progress views.",
        "Declare every `phase('title')` in `meta.phases` (or drop the call). See: `docs read features/workflow.md`.",
    ),
    "DA-12": (
        "Workflow script violates the orchestration contract",
        "The script is a plain-JS function body with top-level await ending in `return <json-value>`; `export` statements are invalid, only `agent`/`parallel`/`pipeline`/`phase`/`log` are injected, and Ralph-style loops need an iteration bound.",
        "Remove exports, fix misspelled primitives, and end the script with a `return` of a JSON value. See: `docs read features/workflow.md`.",
    ),
    "DA-13": (
        "settings.yaml structural problem",
        "settings.yaml is a mapping of plugin-registered namespaces; the built-in `agent-default-model` section requires `provider` and `model` string fields. A non-mapping value under a namespace cannot be published by the settings provider.",
        "Keep every top-level namespace a mapping; give `agent-default-model` both `provider` and `model`. See: `docs read user-guide/settings.md`.",
    ),
    "DA-14": (
        "Unknown permission preset",
        "`permission.defaultPreset` accepts `workspace-write`, `read-only`, or `danger-full-access` (with approval `ask`/`never`). There is no `full-access` preset.",
        "Use one of workspace-write / read-only / danger-full-access. See: `docs read user-guide/permissions.md`.",
    ),
    "DA-15": (
        "Invalid telemetry switch in settings",
        "`telemetry.disabled` must be a strict YAML boolean; a `DSH_TELEMETRY_MODE`-style value must be FULL, FEEDBACK_ONLY, or DISABLED. Non-enums fail at startup.",
        "Set `telemetry.disabled: true` (or false) and keep modes within the documented enum. See: `docs read reference/env-vars.md`.",
    ),
    "DA-16": (
        "Custom LLM provider row is incomplete",
        "Provider rows under `llm-pi-ai.providers` reference credentials indirectly via `apiKeyEnv` (never inline keys) and declare their wire protocol via `api` (documented: `openai-completions`).",
        "Add `apiKeyEnv: <ENV_VAR_NAME>` to each provider and keep `api` values documented. See: `docs read user-guide/configuration.md`.",
    ),
    "DA-17": (
        "skill.json manifest inconsistent with the bundle",
        "DSH discovery reads `SKILL.md` frontmatter only - `skill.json` has no role in DSH discovery. If present for another harness, it must at least not contradict the bundle (name/version/entry).",
        "Align `skill.json` name with the frontmatter `name`, keep `version` semver-ish, and make any entry path resolve. See: `docs read features/skills.md`.",
    ),
    "DA-18": (
        "Credential file permissions or placeholders",
        "Credential files (`.env`, `.credentials.yaml`) hold bearer secrets and should be owner-only (0600). Empty `DEEPSEEK_API_KEY=` placeholders silently fail model requests; DSH_SHELL/DSH_SESSION_* are runtime-injected and must not be user-set.",
        "chmod 600 the file, fill or remove empty key placeholders, and delete reserved DSH_* variables. See: `docs read reference/env-vars.md`.",
    ),
    "DA-19": (
        "Session log header or line is malformed",
        "A session JSONL starts with a `type: session` header carrying the format `version`; each following line must be a JSON envelope. A version newer than the reader rejects the whole log.",
        "Fix the header (`type: session`, integer `version`) and repair or drop malformed lines. See: `docs read learn/core/event-system.md` (section 5).",
    ),
    "DA-20": (
        "Session envelope ordering or surfaceOp violation",
        "`seq` is the monotonically increasing ordering key, and `surfaceOp` (append or {op:'replace',startSeq,endSeq}) is only valid on the five surface event types (system/developer/user/assistant message, tool/result).",
        "Restore monotonically increasing `seq` values and move `surfaceOp` onto surface event types only. See: `docs read learn/core/event-system.md` (envelope table).",
    ),
    "DA-21": (
        "Unknown session event type without `ignorable`",
        "Unknown event types are rejected during rebuild unless the envelope sets `ignorable: true`. The bundled catalog below is partial (format v3/v4 skew), so treat findings as review hints.",
        "Add `ignorable: true` for skippable custom types or verify the type name is spelled correctly. See: `docs read learn/core/event-system.md` (format gate).",
    ),
}

MCP_CLIENT_NAME = "@deepseek-ai/dsh-mcp-client"
PERSONA_NAME = "@deepseek-ai/dsh-persona"

PATCH_ROW_KEYS = {"id", "name", "config", "disabled", "inject", "group", "isolate", "intercept"}
PATCH_UNKNOWN_VERBS = {"replace", "ignore", "remove", "delete", "update"}

SERVER_NAME_RE = re.compile(r"^[A-Za-z0-9_-]{1,32}$")
MCP_TRANSPORTS = {"stdio", "streamable-http"}
MCP_TRANSPORT_SKEW = {"sse"}
PERMISSION_PRESETS = {"workspace-write", "read-only", "danger-full-access"}
TELEMETRY_MODES = {"FULL", "FEEDBACK_ONLY", "DISABLED"}
WORKFLOW_META_KEYS = {"name", "description", "whenToUse", "phases"}
ORCHESTRATION_PRIMITIVES = {"agent", "parallel", "pipeline", "phase", "log"}
KEBAB_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
SEMVER_RE = re.compile(r"^\d+\.\d+\.\d+(?:[-+][0-9A-Za-z.-]+)?$")
SESSION_KNOWN_VERSIONS = {3, 4}

SURFACE_EVENT_TYPES = {
    "system/message",
    "developer/message",
    "user/message",
    "assistant/message",
    "tool/result",
}

# Curated from learn/core/event-system.md (section 5). Partial by design:
# plugins may declare their own types, and official docs mention v4 additions.
KNOWN_EVENT_TYPES = {
    "session",
    "system/message",
    "developer/message",
    "user/message",
    "assistant/message",
    "assistant/attempt",
    "request/header",
    "request/context",
    "tool/call",
    "tool/result",
    "step/start",
    "step/end",
    "turn/start",
    "turn/end",
    "turn/steer",
    "session/end-seed",
    "session/compaction",
    "permission/preset",
    "permission/request",
    "feedback/record",
    "todo/write",
    "goal/change",
    "llm/retry",
    "llm/retry-started",
    "plan/mode",
    "workflow/run-start",
    "workflow/run-end",
}
KNOWN_EVENT_PREFIXES = ("compaction/", "workflow/", "goal/", "todo/", "inbox/", "session/")

PRIMITIVE_TYPOS = {
    "agent": {"agnet", "agen", "aagent"},
    "parallel": {"parrallel", "paralell", "paralel", "parallal", "parllel", "paralle"},
    "pipeline": {"pipelien", "pipelin", "pipelline", "pipelne"},
    "phase": {"phaes", "phse", "phasee", "phaze"},
    "log": {"loge", "logg"},
}

SECRET_PATTERNS = [
    re.compile(r"""(?i)(?:api[_-]?key|secret|token|password|auth[_-]?token)\s*[:=]\s*["'](?![$<!])[A-Za-z0-9_\-.]{16,}["']"""),
    re.compile(r"sk-[a-zA-Z0-9]{20,48}"),
    re.compile(r"ghp_[a-zA-Z0-9]{36}"),
    re.compile(r"github_pat_[a-zA-Z0-9_]{20,}"),
]

MCP_MANAGED_HEADER = "# rabbit-dsh managed MCP patch\n"
PLUGIN_MANAGED_HEADER = "# rabbit-dsh managed plugin patch\n"
MANAGED_PATCH_HEADERS = (MCP_MANAGED_HEADER, PLUGIN_MANAGED_HEADER)

DOC_FAMILY_NOTES = {
    "patch": "Artifact family: Cordis patch layer (cordis.patch.yml / *.patch.yml / agent.cordis.yml). Top-level YAML array of `insert:` blocks or `id:` row overrides; layers stack profile -> machine -> --patch overlays.",
    "workflow": "Artifact family: workflow definition ({meta, script, args}). The engine validates meta against WorkflowMeta and rejects loud before the script runs.",
    "settings": "Artifact family: runtime user settings (~/.dsh/settings.yaml). Namespaces are plugin-registered; fail-loud at startup, last-good on reload.",
    "skill-manifest": "Artifact family: optional skill bundle manifest. DSH skill discovery reads SKILL.md frontmatter only.",
    "credentials": "Artifact family: credential file (.env / .credentials.yaml). Expected owner-only (0600); keys referenced via env vars, never inline.",
    "session": "Artifact family: session event log (JSONL, event-sourced, zstd-compressed on disk). Header line declares the format version.",
}


# -----------------------------------------------------------------------------
# Findings accumulator (house style shared with audit_dsh_skill.py / audit_dsh.py)
# -----------------------------------------------------------------------------

class Findings:
    """Accumulates findings for an artifact audit run."""

    def __init__(self, root):
        self.root = Path(root).resolve()
        self.items = []
        self.notes = []

    def add(self, cid, severity, file, line, evidence, message=None):
        title, why, fix = CHECK_INFO.get(cid, (cid, "", ""))
        self.items.append({
            "id": cid,
            "severity": severity,
            "title": title,
            "file": str(file),
            "line": line,
            "evidence": (evidence or "").strip()[:160],
            "message": message or why,
            "fix": fix,
        })

    def note(self, text):
        self.notes.append(text)


def read_text_safe(path: Path):
    try:
        return path.read_text(encoding="utf-8", errors="replace"), None
    except OSError as exc:
        return None, str(exc)


def _unquote(value: str) -> str:
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in ("'", '"'):
        return value[1:-1]
    return value


def _strict_bool(raw):
    """Return (is_bool, value) for a restricted-YAML scalar."""
    if isinstance(raw, bool):
        return True, raw
    if isinstance(raw, str):
        text = raw.split("#", 1)[0].strip()
        if text in ("true", "false"):
            return True, text == "true"
        return False, text
    return False, raw


# -----------------------------------------------------------------------------
# Restricted patch scanner (line-based; no YAML dependency)
# -----------------------------------------------------------------------------

def scan_patch(text: str):
    """Scan a cordis patch YAML document with a restricted line parser.

    Returns (entries, odd_lines):
      entries  - list of {line, kind, keys: {key: [(lineno, raw_value)]},
                 rows: [same shape as an entry]}
      odd_lines- [(lineno, line)] the parser could not attribute; reported as
                 notes, never as errors.
    """
    entries = []
    odd_lines = []
    cur_entry = None
    cur_row = None
    config_owner = None      # 'entry' | 'row' while inside a `config:` block
    config_indent = None

    def new_block(block_line, kind="override"):
        return {"line": block_line, "kind": kind, "keys": {}, "rows": []}

    for lineno, raw in enumerate(text.splitlines(), 1):
        stripped = raw.strip()
        if not stripped or stripped.startswith("#"):
            continue
        indent = len(raw) - len(raw.lstrip(" "))

        # Inside a config block: everything deeper than `config:` belongs to it,
        # which also swallows block scalars (e.g. persona `text: |`).
        if config_owner is not None and indent > config_indent:
            owner = cur_row if config_owner == "row" and cur_row is not None else cur_entry
            if re.match(r"^[A-Za-z_][\w.-]*\s*:", stripped) or stripped.startswith("- "):
                key_part = stripped[2:] if stripped.startswith("- ") else stripped
                key, _, val = key_part.partition(":")
                owner["keys"].setdefault(key.strip(), []).append((lineno, val.strip()))
            continue
        if config_owner is not None:
            config_owner = None
            config_indent = None

        if indent == 0 and stripped.startswith("- "):
            body = stripped[2:].strip()
            cur_entry = new_block(lineno)
            cur_row = None
            entries.append(cur_entry)
            if body == "insert:" or body.startswith("insert:"):
                cur_entry["kind"] = "insert"
                rest = body[len("insert"):].strip().lstrip(":").strip()
                if rest:
                    odd_lines.append((lineno, raw))
            elif re.match(r"^[A-Za-z_][\w.-]*\s*:", body):
                key, _, val = body.partition(":")
                key = key.strip()
                cur_entry["keys"].setdefault(key, []).append((lineno, val.strip()))
                if key == "config" and not val.strip():
                    config_owner = "entry"
                    config_indent = indent
            else:
                odd_lines.append((lineno, raw))
            continue

        if cur_entry is None:
            odd_lines.append((lineno, raw))
            continue

        if cur_entry["kind"] == "insert" and stripped.startswith("- ") and config_owner is None:
            body = stripped[2:].strip()
            cur_row = new_block(lineno, kind="insert")
            cur_entry["rows"].append(cur_row)
            if re.match(r"^[A-Za-z_][\w.-]*\s*:", body):
                key, _, val = body.partition(":")
                key = key.strip()
                cur_row["keys"].setdefault(key, []).append((lineno, val.strip()))
                if key == "config" and not val.strip():
                    config_owner = "row"
                    config_indent = indent
            else:
                odd_lines.append((lineno, raw))
            continue

        if re.match(r"^[A-Za-z_][\w.-]*\s*:", stripped):
            key, _, val = stripped.partition(":")
            key = key.strip()
            owner = cur_row if (cur_row is not None and indent > 2) else cur_entry
            owner["keys"].setdefault(key, []).append((lineno, val.strip()))
            if key == "config" and not val.strip():
                config_owner = "row" if owner is cur_row else "entry"
                config_indent = indent
            continue

        odd_lines.append((lineno, raw))

    return entries, odd_lines


def _row_name(row):
    occ = row["keys"].get("name")
    return _unquote(occ[0][1]) if occ else None


def _row_id(row):
    occ = row["keys"].get("id")
    return _unquote(occ[0][1]) if occ else None


def _iter_patch_rows(entries):
    """Normalize scanned entries into a flat row list."""
    rows = []
    for entry in entries:
        if entry["kind"] == "insert":
            for row in entry["rows"]:
                rows.append(row)
        else:
            rows.append(entry)
    return rows


def scan_managed_patch(text: str):
    """Parse a rabbit-dsh managed JSON (MCP) patch document into row dicts.

    Returns (rows, error). Rows use {line, kind, keys} shaped like scan_patch
    entries so both paths share the check logic. Only the JSON payload format
    is handled here; YAML managed patches go through scan_patch.
    """
    payload = text
    if text.startswith(MCP_MANAGED_HEADER):
        payload = text[len(MCP_MANAGED_HEADER):]
    else:
        return [], None
    try:
        data = json.loads(payload)
    except ValueError as exc:
        return [], f"Managed patch JSON is malformed: {exc}"
    if data == []:
        return [], None
    if not isinstance(data, list) or len(data) != 1 or not isinstance(data[0], dict):
        return [], "Managed patch must be a single {insert: [...]} operation."

    op = data[0]
    rows = op.get("insert")
    if set(op) != {"insert"} or not isinstance(rows, list):
        return [], "Managed patch must be a single {insert: [...]} operation."

    normalized = []
    for idx, row in enumerate(rows, 1):
        if not isinstance(row, dict):
            return [], "Managed patch rows must be JSON objects."
        block = {"line": idx, "kind": "insert", "keys": {}, "rows": [], "json": row}
        for key, value in row.items():
            block["keys"].setdefault(str(key), []).append((idx, value))
            if isinstance(value, dict):
                # Flatten one level so shared row checks see config fields.
                for sub_key, sub_value in value.items():
                    block["keys"].setdefault(str(sub_key), []).append((idx, sub_value))
        normalized.append(block)
    return normalized, None


def check_managed_js_placement(rows, findings, rel):
    """DA-04 variant for managed JSON rows: `!!js` only inside config/disabled."""
    for row in rows:
        json_row = row.get("json", {})
        for key, value in json_row.items():
            if key in ("config", "disabled"):
                continue
            candidates = value if isinstance(value, list) else [value]
            for item in candidates:
                if isinstance(item, str) and "!!js" in item:
                    findings.add("DA-04", "error", rel, row["line"], f"{key}: {item}",
                                 message="`!!js` expressions are only evaluated inside `config` values and `disabled` fields.")


# -----------------------------------------------------------------------------
# Patch / preset checks (DA-01..DA-08)
# -----------------------------------------------------------------------------

def check_js_tag_placement(text: str, findings, rel):
    """DA-04: `!!js` is only interpreted inside config values / disabled fields."""
    config_scopes = []  # (start_line, end_line)
    for lineno, raw in enumerate(text.splitlines(), 1):
        stripped = raw.strip()
        if re.match(r"^[ \t]*-?[ \t]*config\s*:", raw):
            indent = len(raw) - len(raw.lstrip(" "))
            end = lineno
            for follow in text.splitlines()[lineno:]:
                follow_indent = len(follow) - len(follow.lstrip(" "))
                if not follow.strip() or follow_indent > indent:
                    end += 1
                else:
                    break
            config_scopes.append((lineno, end))

    for lineno, raw in enumerate(text.splitlines(), 1):
        if "!!js" not in raw:
            continue
        stripped = raw.strip()
        if stripped.startswith("#"):
            continue
        if any(start <= lineno <= end for start, end in config_scopes):
            continue
        if re.match(r"^[ \t]*-?[ \t]*disabled\s*:", raw):
            continue
        findings.add("DA-04", "error", rel, lineno, raw.strip(),
                     message="`!!js` expression outside a `config` value or `disabled` field will not be evaluated by the harness.")


def check_patch_rows(rows, findings, rel, row_lines):
    """Shared row-level checks: DA-02, DA-03, DA-05, DA-06, DA-08."""
    seen_ids = {}
    seen_server_names = {}

    for row in rows:
        rid = _row_id(row)
        line = row["line"]
        if row["kind"] == "insert" and (rid is None or _row_name(row) is None):
            findings.add("DA-02", "error", rel, line,
                         f"id: {rid or '<missing>'}, name: {_row_name(row) or '<missing>'}",
                         message="Rows inside `insert:` blocks need both `id` and `name`.")

        if rid is not None:
            if rid in seen_ids:
                findings.add("DA-03", "error", rel, line, f"duplicate id: {rid}",
                             message=f"Row id '{rid}' first used at line {seen_ids[rid]}.")
            else:
                seen_ids[rid] = line

        if _row_name(row) == MCP_CLIENT_NAME:
            _check_mcp_row(row, findings, rel, seen_server_names)

        if _row_name(row) == PERSONA_NAME:
            _check_persona_row(row, findings, rel)

    # Unknown patch verbs anywhere in the document.
    for lineno, raw in row_lines:
        match = re.match(r"^[ \t]*-?[ \t]*([A-Za-z_][\w-]*)\s*:", raw)
        if match and match.group(1) in PATCH_UNKNOWN_VERBS:
            findings.add("DA-01", "error", rel, lineno, raw.strip(),
                         message=f"`{match.group(1)}:` is not a patch operation; patches only have `insert:` blocks and `id:` row overrides.")


def _check_mcp_row(row, findings, rel, seen_server_names):
    cfg = {}
    for key, occurrences in row["keys"].items():
        if key in ("id", "name"):
            continue
        cfg[key] = occurrences[0]

    line = row["line"]
    raw_transport = cfg.get("transport", (line, "stdio"))[1]
    transport = _unquote(str(raw_transport)) or "stdio"

    server_occ = cfg.get("serverName")
    server_name = _unquote(str(server_occ[1])) if server_occ else None
    if not server_name:
        findings.add("DA-05", "error", rel, line, "missing serverName",
                     message="MCP client rows must declare `config.serverName`; it becomes the mcp__<serverName>__ tool prefix.")
    elif not SERVER_NAME_RE.fullmatch(server_name):
        findings.add("DA-05", "error", rel, server_occ[0], f"serverName: {server_occ[1]}",
                     message=f"`{server_name}` must match [A-Za-z0-9_-]{{1,32}}.")
    elif server_name in seen_server_names:
        findings.add("DA-05", "error", rel, line, f"duplicate serverName: {server_name}",
                     message=f"Two live MCP instances with serverName '{server_name}' make the later mount fail.")
    else:
        seen_server_names[server_name] = line

    if transport in MCP_TRANSPORT_SKEW:
        findings.add("DA-06", "warning", rel, line, f"transport: {transport}",
                     message="`sse` appears only in older docs/examples; current documented transports are stdio and streamable-http.")
    elif transport not in MCP_TRANSPORTS:
        findings.add("DA-06", "error", rel, line, f"transport: {transport}",
                     message=f"Unknown MCP transport '{transport}'. Use stdio or streamable-http.")

    if transport == "stdio":
        if not cfg.get("command"):
            findings.add("DA-06", "error", rel, line, "stdio without command",
                         message="stdio transport launches a subprocess: `command` is required.")
        if cfg.get("url"):
            findings.add("DA-06", "warning", rel, cfg["url"][0], f"url: {cfg['url'][1]}",
                         message="`url` applies to streamable-http transport; stdio uses `command`.")
    elif transport == "streamable-http":
        if not cfg.get("url"):
            findings.add("DA-06", "error", rel, line, "streamable-http without url",
                         message="Remote transports connect to `url`; `command` is stdio-only.")
        if cfg.get("command"):
            findings.add("DA-06", "warning", rel, cfg["command"][0], f"command: {cfg['command'][1]}",
                         message="`command` applies to stdio transport; streamable-http uses `url`.")


def _check_persona_row(row, findings, rel):
    line = row["line"]
    text_occ = row["keys"].get("text")
    if text_occ is None:
        findings.add("DA-08", "error", rel, line, "persona row without config.text",
                     message="The persona row needs a non-empty `config.text` system-prompt line.")
    elif not str(text_occ[0][1]).strip():
        findings.add("DA-08", "error", rel, text_occ[0][0], "empty persona text",
                     message="`config.text` is the persona's system-prompt line; it must not be empty.")

    for key in ("complete", "includeRuntimeContext"):
        occ = row["keys"].get(key)
        if occ is None:
            continue
        ok, value = _strict_bool(occ[0][1])
        if not ok:
            findings.add("DA-08", "error", rel, occ[0][0], f"{key}: {occ[0][1]}",
                         message=f"`{key}` must be strict boolean true/false (persona shadowing semantics depend on it).")


def check_patch_secrets(text: str, findings, rel):
    """DA-07: plaintext credentials; `!!js` refs and ${...} templates are fine."""
    for lineno, raw in enumerate(text.splitlines(), 1):
        stripped = raw.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if "!!js" in stripped or "${" in stripped:
            continue
        for pattern in SECRET_PATTERNS:
            match = pattern.search(stripped)
            if match:
                findings.add("DA-07", "warning", rel, lineno, stripped,
                             message=f"Possible inline credential (`{match.group(0)[:12]}...`). Reference it via `!!js process.env.VAR` instead.")
                break


# -----------------------------------------------------------------------------
# Workflow checks (DA-09..DA-12)
# -----------------------------------------------------------------------------

def scan_workflow_yaml(text: str):
    """Restricted scan of a workflow YAML document -> (meta, script) or None.

    meta: {key: (lineno, raw_value)}; phases collected from `- item` lines.
    script: block-scalar body text or None.
    """
    meta = {}
    script_lines = []
    section = None       # 'meta' | 'args' | 'script'
    section_indent = 0
    in_phases = False
    phases_indent = 0

    for lineno, raw in enumerate(text.splitlines(), 1):
        stripped = raw.strip()
        if not stripped or stripped.startswith("#"):
            continue
        indent = len(raw) - len(raw.lstrip(" "))

        if section == "script":
            if indent > section_indent:
                script_lines.append(raw[section_indent + 2:] if len(raw) > section_indent + 2 else raw)
            elif script_lines:
                section = None
            continue

        if indent == 0:
            in_phases = False
            match = re.match(r"^([A-Za-z_][\w-]*)\s*:\s*(.*)$", stripped)
            if not match:
                continue
            section = match.group(1)
            section_indent = indent
            value = match.group(2).strip()
            if section == "script":
                if value not in ("|", "|-", "|+", ">", ">-", ">+"):
                    script_lines.append(_unquote(value))
                    section = None
                continue
            if section == "meta":
                if value:
                    meta["__root__"] = value
                continue
            continue

        if section == "meta":
            if in_phases and indent > phases_indent and stripped.startswith("- "):
                meta.setdefault("phases", []).append((lineno, _unquote(stripped[2:])))
                continue
            match = re.match(r"^([A-Za-z_][\w-]*)\s*:\s*(.*)$", stripped)
            if not match:
                continue
            key, value = match.group(1), match.group(2).strip()
            if not value:
                in_phases = key == "phases"
                phases_indent = indent
                continue
            in_phases = False
            meta[key] = (lineno, _unquote(value))

    script = "\n".join(script_lines).strip() if script_lines else None
    return (meta, script) if (meta or script) else (None, None)


def analyze_workflow_script(script: str):
    """Static workflow-script analysis -> list of (kind, detail, match_text).

    kind: 'export' | 'typo' | 'case' | 'no-return' | 'unbounded'
    """
    results = []
    if re.search(r"^\s*export\s+", script, re.MULTILINE):
        results.append(("export", "script contains an `export` statement; workflow scripts are plain function bodies", "`export`"))

    defined = set(re.findall(r"\b(?:function|const|let|var|class)\s+([A-Za-z_$][\w$]*)", script))
    defined.update(re.findall(r"\b([a-z][\w]*)\s*(?:=|:)\s*(?:function|\()", script))
    for token in re.findall(r"\b([A-Za-z_$][\w$]*)\s*\(", script):
        if token in defined or token in ORCHESTRATION_PRIMITIVES:
            continue
        lowered = token.lower()
        for primitive, typos in PRIMITIVE_TYPOS.items():
            if lowered in typos:
                results.append(("typo", f"`{token}(` looks like a misspelled `{primitive}` orchestration primitive", token))
                break
        else:
            if lowered in ORCHESTRATION_PRIMITIVES and token not in defined:
                results.append(("case", f"`{token}` differs only in case from primitive `{lowered}`; JS is case-sensitive", token))

    body_no_comments = re.sub(r"//[^\n]*", "", script)
    if "return" not in body_no_comments:
        results.append(("no-return", "script never returns a value; the engine materializes `null` and consumers see an empty result", "no return"))

    if re.search(r"\bwhile\s*\(", body_no_comments) and re.search(r"\biteration\b|\bround\b|\brounds\b", body_no_comments):
        if not re.search(r"<\s*\w+|\+\+|limit", body_no_comments):
            results.append(("unbounded", "Ralph-style loop has no visible iteration bound; the engine has no overall deadline", "while loop"))
    return results


def lint_workflow(path: Path, rel: Path, findings: Findings, text: str):
    findings.note(DOC_FAMILY_NOTES["workflow"])

    meta = {}
    script = None
    if path.suffix == ".json":
        try:
            data = json.loads(text)
        except ValueError as exc:
            findings.add("DA-09", "error", rel, 1, f"Malformed workflow JSON: {exc}")
            return
        if not isinstance(data, dict) or not {"meta", "script"} <= data.keys():
            findings.add("DA-09", "error", rel, 1, "workflow JSON needs 'meta' and 'script'",
                         message="The workflow tool carries exactly {meta, script, args}.")
            return
        raw_meta = data.get("meta")
        if isinstance(raw_meta, dict):
            meta = {key: (1, value) for key, value in raw_meta.items()}
        raw_script = data.get("script")
        if isinstance(raw_script, str):
            script = raw_script
        if isinstance(data.get("args"), dict):
            findings.note(f"args keys: {', '.join(sorted(data['args']))}.")
    else:
        scanned_meta, scanned_script = scan_workflow_yaml(text)
        if scanned_meta is None and scanned_script is None:
            findings.add("DA-09", "error", rel, 1, "no meta/script sections found",
                         message="Workflow YAML needs `meta:` and `script:` blocks (the scaffold format) or top-level-await JS.")
            return
        meta = scanned_meta or {}
        script = scanned_script

    # DA-09: required identity fields.
    name_occ = meta.get("name")
    desc_occ = meta.get("description")
    if name_occ is None:
        findings.add("DA-09", "error", rel, 1, "meta.name missing",
                     message="`meta.name` is required (short kebab-case; also the persistence key).")
    else:
        name_text = str(name_occ[1])
        if not KEBAB_RE.fullmatch(name_text):
            findings.add("DA-09", "error", rel, name_occ[0], f"name: {name_text}",
                         message=f"Workflow name '{name_text}' must be kebab-case.")
    if desc_occ is None:
        findings.add("DA-09", "error", rel, 1, "meta.description missing",
                     message="`meta.description` is required; the engine rejects the start request without it.")

    # DA-10: unknown meta vocabulary.
    declared_phases = set()
    phases_line = 1
    phases_occ = meta.get("phases")
    if phases_occ:
        if isinstance(phases_occ, list):
            # YAML scan shape: [(lineno, title), ...]
            declared_phases = {str(item[1]) for item in phases_occ}
            phases_line = phases_occ[0][0] if phases_occ else 1
        elif isinstance(phases_occ, tuple):
            # JSON shape: (line, [title, ...])
            phases_line = phases_occ[0]
            raw_value = phases_occ[1]
            if isinstance(raw_value, list):
                declared_phases = {str(item) for item in raw_value}
    for key, occ in meta.items():
        if key in WORKFLOW_META_KEYS or key == "__root__":
            continue
        if isinstance(occ, tuple):
            lineno, value = occ
        else:
            lineno, value = 1, occ
        findings.add("DA-10", "warning", rel, lineno, f"{key}: {value}",
                     message=f"`{key}` is not in the official WorkflowMeta vocabulary {{name, description, whenToUse, phases}}; the engine validates meta and rejects loud before the script runs.")

    # DA-11: phase() calls vs declared phases.
    if script:
        called_phases = re.findall(r"\bphase\s*\(\s*['\"]([^'\"]+)['\"]", script)
        if declared_phases:
            for title in called_phases:
                if title not in declared_phases:
                    findings.add("DA-11", "warning", rel, phases_line, f"phase('{title}')",
                                 message=f"`{title}` is not declared in meta.phases ({', '.join(sorted(declared_phases))}); progress observers will not match it.")
            unused = declared_phases - set(called_phases)
            if unused:
                findings.note(f"Declared phases never matched by a phase() call: {', '.join(sorted(unused))} (phases are progress vocabulary only).")

    # DA-12: script contract.
    if script is None:
        findings.add("DA-12", "warning", rel, 1, "script section missing",
                     message="A workflow without a script cannot start any agent.")
    else:
        for kind, detail, evidence in analyze_workflow_script(script):
            if kind == "export":
                severity = "error"
            elif kind == "typo":
                severity = "error"
            else:
                severity = "warning"
            findings.add("DA-12", severity, rel, 1, evidence, message=detail)


# -----------------------------------------------------------------------------
# settings.yaml checks (DA-13..DA-16)
# -----------------------------------------------------------------------------

def parse_yaml_tree(text: str):
    """Parse restricted nested YAML mappings into {key: node}.

    node = {line, value (raw str | None), children {}}. Block scalars collapse
    to a single raw leaf value; sequences are recorded per-parent as `values`.
    """
    root = {}
    stack = [(-1, root)]
    skip_indent = None

    for lineno, raw in enumerate(text.splitlines(), 1):
        stripped = raw.strip()
        if not stripped or stripped.startswith("#"):
            continue
        indent = len(raw) - len(raw.lstrip(" "))

        if skip_indent is not None:
            if indent > skip_indent:
                continue
            skip_indent = None

        if stripped.startswith("- "):
            if stack:
                parent = stack[-1][1]
                parent.setdefault("__values__", []).append((lineno, _unquote(stripped[2:])))
            continue

        match = re.match(r"^([A-Za-z_][\w.-]*)\s*:\s*(.*)$", stripped)
        if not match:
            continue
        key, value = match.group(1), match.group(2).strip()

        while stack and indent <= stack[-1][0]:
            stack.pop()
        parent = stack[-1][1] if stack else root

        if value in ("|", "|-", "|+", ">", ">-", ">+"):
            parent[key] = {"line": lineno, "value": "<block>", "children": None}
            skip_indent = indent
            continue
        if not value:
            node = {"line": lineno, "value": None, "children": {}}
            parent[key] = node
            stack.append((indent, node["children"]))
            continue

        parent[key] = {"line": lineno, "value": _unquote(value), "children": None}

    return root


def lint_settings(path: Path, rel: Path, findings: Findings, text: str):
    findings.note(DOC_FAMILY_NOTES["settings"])

    if path.suffix == ".json":
        try:
            data = json.loads(text)
        except ValueError as exc:
            findings.add("DA-13", "error", rel, 1, f"Malformed settings JSON: {exc}")
            return
        tree = {}
        for key, value in data.items():
            tree[key] = {"line": 1, "value": value if isinstance(value, str) else None,
                         "children": value if isinstance(value, dict) else None}
    else:
        tree = parse_yaml_tree(text)

    if not tree:
        findings.add("DA-13", "error", rel, 1, "empty or unparsable settings document",
                     message="settings.yaml must be a mapping of namespace sections.")
        return

    known = {"agent-default-model", "permission", "permission-presets", "telemetry",
             "llm-pi-ai", "credentials", "ui"}
    unknown = [key for key in tree if key not in known]
    if unknown:
        findings.note(f"Namespaces are plugin-registered; unlisted top-level sections found: {', '.join(sorted(unknown))}. Verify they belong to a mounted plugin.")

    adm = tree.get("agent-default-model")
    if adm is not None:
        children = adm["children"] or {}
        for field in ("provider", "model"):
            node = children.get(field)
            if node is None or not str(node.get("value") or "").strip():
                findings.add("DA-13", "error", rel, adm["line"], f"agent-default-model.{field} missing",
                             message="The built-in agent-default-model section requires `{ provider, model }` string fields.")
        extra = set(children) - {"provider", "model", "reasoningEffort"}
        for field in sorted(extra):
            findings.add("DA-13", "warning", rel, children[field]["line"], field,
                         message="agent-default-model accepts provider/model/reasoningEffort only (reasoningEffort is settings-only, never plugin config).")

    perm = tree.get("permission")
    if perm is not None:
        preset_node = (perm["children"] or {}).get("defaultPreset")
        if preset_node is not None:
            value = str(preset_node.get("value") or "")
            if value and value not in PERMISSION_PRESETS:
                hint = " There is no `full-access` preset." if value == "full-access" else ""
                findings.add("DA-14", "error", rel, preset_node["line"], f"defaultPreset: {value}",
                             message=f"'{value}' is not a permission preset.{hint} Documented: workspace-write, read-only, danger-full-access.")
        else:
            findings.add("DA-14", "warning", rel, perm["line"], "permission without defaultPreset",
                         message="The documented permission section key is `defaultPreset`; check the section spelling.")

    tele = tree.get("telemetry")
    if tele is not None:
        children = tele["children"] or {}
        disabled = children.get("disabled")
        if disabled is not None:
            ok, value = _strict_bool(disabled["value"])
            if not ok:
                findings.add("DA-15", "error", rel, disabled["line"], f"telemetry.disabled: {disabled['value']}",
                             message="`telemetry.disabled` must be strict boolean true/false; other values fail the settings schema.")
        mode = children.get("mode")
        if mode is not None and str(mode.get("value") or "") not in TELEMETRY_MODES:
            findings.add("DA-15", "error", rel, mode["line"], f"telemetry.mode: {mode['value']}",
                         message="Telemetry mode must be FULL, FEEDBACK_ONLY, or DISABLED.")

    pi = tree.get("llm-pi-ai")
    if pi is not None:
        providers = ((pi["children"] or {}).get("providers") or {}).get("children") or {}
        for provider_id, node in providers.items():
            children = node.get("children") or {}
            api_key = children.get("apiKeyEnv")
            if api_key is None or not str(api_key.get("value") or "").strip():
                findings.add("DA-16", "warning", rel, node["line"], f"providers.{provider_id} without apiKeyEnv",
                             message="Provider credentials are referenced indirectly via `apiKeyEnv`; never inline API keys in settings.")
            api = children.get("api")
            if api is not None and str(api.get("value") or "") not in ("openai-completions",):
                findings.add("DA-16", "warning", rel, api["line"], f"api: {api['value']}",
                             message="Documented wire protocol value is `openai-completions`; custom values need a matching client plugin.")


# -----------------------------------------------------------------------------
# skill.json / credentials / session checks (DA-17, DA-18, DA-19..21)
# -----------------------------------------------------------------------------

def lint_skill_manifest(path: Path, rel: Path, findings: Findings, text: str):
    findings.note(DOC_FAMILY_NOTES["skill-manifest"])

    try:
        manifest = json.loads(text)
    except ValueError as exc:
        findings.add("DA-17", "error", rel, 1, f"Malformed skill.json: {exc}")
        return
    if not isinstance(manifest, dict):
        findings.add("DA-17", "error", rel, 1, "skill.json must be a JSON object")
        return

    findings.note("DSH discovery reads SKILL.md frontmatter only; skill.json is consumed by other tooling. Keeping it consistent avoids drift.")

    name = manifest.get("name")
    if isinstance(name, str) and name.strip():
        expected = path.parent.name
        fm_match = re.search(r"^name:\s*['\"]?([^'\"\n]+)", (path.parent / "SKILL.md").read_text(encoding="utf-8", errors="replace"), re.MULTILINE) if (path.parent / "SKILL.md").is_file() else None
        fm_name = fm_match.group(1).strip() if fm_match else None
        if fm_name and name != fm_name:
            findings.add("DA-17", "error", rel, 1, f"name: {name} != frontmatter {fm_name}",
                         message="skill.json name contradicts SKILL.md frontmatter; align both.")
        elif not fm_name and name != expected:
            findings.add("DA-17", "warning", rel, 1, f"name: {name} != directory {expected}",
                         message="skill.json name does not match the bundle directory name.")

    version = manifest.get("version")
    if version is not None and (not isinstance(version, str) or not SEMVER_RE.fullmatch(version)):
        findings.add("DA-17", "warning", rel, 1, f"version: {version}",
                     message="Use a semver-ish version (MAJOR.MINOR.PATCH) so tooling can compare releases.")

    for entry_key in ("entry", "main"):
        entry = manifest.get(entry_key)
        if isinstance(entry, str) and entry.strip():
            target = (path.parent / entry).resolve()
            if not target.exists():
                findings.add("DA-17", "error", rel, 1, f"{entry_key}: {entry}",
                             message=f"Manifest entry `{entry}` does not resolve to an existing file.")
            break

    for flag in ("disableModelInvocation", "userInvocable"):
        if flag in manifest:
            value = manifest[flag]
            if not isinstance(value, bool):
                findings.add("DA-17", "error", rel, 1, f"{flag}: {value}",
                             message=f"`{flag}` must be a strict JSON boolean; consumers fail closed on other types.")


def lint_credentials(path: Path, rel: Path, findings: Findings):
    findings.note(DOC_FAMILY_NOTES["credentials"])

    try:
        mode = stat.S_IMODE(path.stat().st_mode)
    except OSError as exc:
        findings.add("DA-18", "error", rel, 1, str(exc))
        return
    if mode & 0o077:
        findings.add("DA-18", "warning", rel, 1, f"mode {oct(mode)}",
                     message=f"Credential file is readable beyond its owner ({oct(mode)}); `chmod 600` it. Documented default is 0600.")

    text, err = read_text_safe(path)
    if err or text is None:
        return
    for lineno, raw in enumerate(text.splitlines(), 1):
        stripped = raw.strip()
        if not stripped or stripped.startswith("#"):
            continue
        match = re.match(r"^([A-Za-z_][\w]*)=(.*)$", stripped)
        if not match:
            continue
        key, value = match.group(1), match.group(2).strip()
        if key == "DEEPSEEK_API_KEY" and not value:
            findings.add("DA-18", "warning", rel, lineno, "DEEPSEEK_API_KEY= (empty)",
                         message="Empty API key placeholder: model requests will fail until it is filled or removed.")
        if key.startswith("DSH_") and key not in ("DSH_HOME",):
            findings.add("DA-18", "warning", rel, lineno, f"{key}={value}",
                         message="DSH_* variables are reserved (DSH_SHELL/DSH_SESSION_* are runtime-injected); set user config through DSH_HOME or documented switches instead.")


def lint_session_log(path: Path, rel: Path, findings: Findings, text: str):
    findings.note(DOC_FAMILY_NOTES["session"])

    lines = [line for line in text.splitlines() if line.strip()]
    if not lines:
        findings.add("DA-19", "error", rel, 1, "empty session log")
        return

    try:
        header = json.loads(lines[0])
    except ValueError as exc:
        findings.add("DA-19", "error", rel, 1, lines[0][:120], message=f"First line is not a JSON header: {exc}")
        return
    if not isinstance(header, dict) or header.get("type") != "session":
        findings.add("DA-19", "error", rel, 1, lines[0][:120],
                     message="Session logs start with a header envelope {type: 'session', version: N, ...}.")
    else:
        version = header.get("version")
        if not isinstance(version, int):
            findings.add("DA-19", "error", rel, 1, f"version: {version!r}",
                         message="Header `version` must be an integer format version.")
        elif version > max(SESSION_KNOWN_VERSIONS):
            findings.add("DA-19", "warning", rel, 1, f"version: {version}",
                         message=f"Format version {version} is newer than this catalog knows ({max(SESSION_KNOWN_VERSIONS)}); older harnesses reject the log outright.")

    last_seq = None
    for idx, line in enumerate(lines[1:], 2):
        try:
            event = json.loads(line)
        except ValueError as exc:
            findings.add("DA-19", "error", rel, idx, line[:120], message=f"Malformed JSONL line: {exc}")
            continue
        if not isinstance(event, dict):
            findings.add("DA-19", "error", rel, idx, line[:120], message="Event envelopes must be JSON objects.")
            continue

        event_type = str(event.get("type", ""))
        seq = event.get("seq")
        if seq is not None:
            if not isinstance(seq, int):
                findings.add("DA-20", "error", rel, idx, f"seq: {seq!r}", message="`seq` must be an integer ordering key.")
            elif last_seq is not None and seq <= last_seq:
                findings.add("DA-20", "error", rel, idx, f"seq {seq} after {last_seq}",
                             message="`seq` must increase monotonically; rebuilds order the session by it.")
            else:
                last_seq = seq

        if "surfaceOp" in event:
            op = event["surfaceOp"]
            valid_shape = op == "append" or (
                isinstance(op, dict) and op.get("op") == "replace"
                and isinstance(op.get("startSeq"), int) and isinstance(op.get("endSeq"), int)
            )
            if event_type not in SURFACE_EVENT_TYPES:
                findings.add("DA-20", "error", rel, idx, f"surfaceOp on {event_type or '<missing type>'}",
                             message="`surfaceOp` is only valid on system/developer/user/assistant message and tool/result events.")
            elif not valid_shape:
                findings.add("DA-20", "error", rel, idx, f"surfaceOp: {json.dumps(op)[:80]}",
                             message="surfaceOp must be 'append' or {op:'replace', startSeq, endSeq}.")

        if event_type and event_type != "session":
            known = event_type in KNOWN_EVENT_TYPES or any(event_type.startswith(p) for p in KNOWN_EVENT_PREFIXES)
            if not known:
                if event.get("ignorable") is True:
                    findings.note(f"Line {idx}: unknown-but-ignorable event type '{event_type}' (skipped during rebuild).")
                else:
                    findings.add("DA-21", "warning", rel, idx, f"type: {event_type}",
                                 message=f"Event type '{event_type}' is not in the bundled catalog; without `ignorable: true` rebuilds reject it. Catalog is partial (v3/v4 skew).")


# -----------------------------------------------------------------------------
# Artifact sniffing + dispatch
# -----------------------------------------------------------------------------

def sniff_artifact(path: Path):
    """Guess the artifact family from filename/shape. Returns a type string."""
    name = path.name
    if path.is_dir():
        if (path / "agent.cordis.yml").is_file():
            return "patch"
        return "unknown"
    if (name.endswith((".patch.yml", ".patch.yaml"))
            or name in ("cordis.patch.yml", "cordis.patch.yaml")
            or name.endswith("agent.cordis.yml")):
        return "patch"
    if re.match(r"^settings(?:[.-][\w.-]*)?\.(?:ya?ml|json)$", name):
        return "settings"
    if name == "skill.json":
        return "skill-manifest"
    if name in (".env", ".credentials.yaml", "credentials.yaml"):
        return "credentials"
    if name.endswith(".jsonl.zstd"):
        return "session-zstd"
    if name.endswith(".jsonl"):
        return "session"
    if path.suffix in (".json", ".yaml", ".yml"):
        text, _ = read_text_safe(path)
        if text and re.search(r"\bmeta\b", text) and re.search(r"\bscript\b", text):
            return "workflow"
    return "unknown"


ARTIFACT_TYPES = ("patch", "workflow", "settings", "skill-manifest", "credentials", "session", "session-zstd")


def lint_artifact(path: Path, findings: Findings, forced_type=None):
    target = path.resolve()
    rel = Path(target.name)
    artifact_type = forced_type or sniff_artifact(target)

    if artifact_type == "unknown":
        findings.add("DA-01", "error", rel, 1, f"unrecognized artifact: {target.name}",
                     message="Point the linter at a cordis patch, workflow definition, settings.yaml, skill.json, .env, or session .jsonl file - or force a family with --type.")
        return artifact_type

    if artifact_type == "session-zstd":
        findings.note(DOC_FAMILY_NOTES["session"])
        findings.note("On-disk session logs are zstd-compressed; decode first (`zstdcat session.v3.jsonl.zstd`) and lint the plaintext.")
        return artifact_type

    text, err = read_text_safe(target)
    if err or text is None:
        findings.add("DA-01", "error", rel, 1, err or "cannot read",
                     message=f"Could not read `{rel}`: {err}")
        return artifact_type

    if artifact_type == "patch":
        findings.note(DOC_FAMILY_NOTES["patch"])
        if text.startswith(PLUGIN_MANAGED_HEADER):
            # rabbit-dsh YAML managed plugin patch: scan like hand-written YAML.
            findings.note("Detected a rabbit-dsh managed YAML plugin patch; parsed structurally.")
            entries, odd_lines = scan_patch(text)
            rows = _iter_patch_rows(entries)
            if not rows:
                findings.note("Managed patch contains no rows; nothing to validate.")
                return artifact_type
            verb_lines = [(lineno, raw) for lineno, raw in enumerate(text.splitlines(), 1) if raw.strip()]
            check_patch_rows(rows, findings, rel, verb_lines)
            check_js_tag_placement(text, findings, rel)
            check_patch_secrets(text, findings, rel)
            for lineno, raw in odd_lines[:5]:
                findings.note(f"Restricted patch parser could not attribute line {lineno}: {raw.strip()[:80]!r}.")
            return artifact_type

        managed_rows, managed_error = scan_managed_patch(text)
        if managed_error:
            findings.add("DA-01", "error", rel, 1, managed_error)
            return artifact_type
        if text.startswith(MCP_MANAGED_HEADER) and not managed_rows:
            findings.note("Managed patch contains no rows (empty insert list); nothing to validate.")
            return artifact_type
        if managed_rows:
            findings.note("Detected a rabbit-dsh managed JSON patch document; parsed structurally.")
            rows = managed_rows
            entries = []
            odd_lines = []
            check_managed_js_placement(managed_rows, findings, rel)
        else:
            entries, odd_lines = scan_patch(text)
            rows = _iter_patch_rows(entries)
        if not entries and not rows:
            findings.add("DA-01", "error", rel, 1, "no patch entries found",
                         message="A cordis patch must be a top-level YAML array of `insert:` blocks or `id:` row overrides.")
            return artifact_type
        for entry in entries:
            unknown = set(entry["keys"]) - PATCH_ROW_KEYS - {"insert"}
            # Verb errors come from check_patch_rows; avoid double-reporting.
            unknown -= PATCH_UNKNOWN_VERBS
            if entry["kind"] == "override" and unknown:
                first = sorted(unknown)[0]
                findings.add("DA-01", "warning", rel, entry["keys"][first][0][0], first,
                             message=f"`{first}` is not a patch row field (id/name/config/disabled/inject/group/isolate/intercept).")
        verb_lines = [(lineno, raw) for lineno, raw in enumerate(text.splitlines(), 1) if raw.strip()]
        check_patch_rows(rows, findings, rel, verb_lines)
        check_js_tag_placement(text, findings, rel)
        check_patch_secrets(text, findings, rel)
        for lineno, raw in odd_lines[:5]:
            findings.note(f"Restricted patch parser could not attribute line {lineno}: {raw.strip()[:80]!r}. Verify manually with `dsh web --dump-config`.")

    elif artifact_type == "workflow":
        lint_workflow(target, rel, findings, text)

    elif artifact_type == "settings":
        lint_settings(target, rel, findings, text)

    elif artifact_type == "skill-manifest":
        lint_skill_manifest(target, rel, findings, text)

    elif artifact_type == "credentials":
        lint_credentials(target, rel, findings)

    elif artifact_type == "session":
        lint_session_log(target, rel, findings, text)

    return artifact_type


# -----------------------------------------------------------------------------
# Report rendering (house style)
# -----------------------------------------------------------------------------

def format_report_text(findings: Findings, target_name: str, artifact_type: str) -> str:
    errors = sum(1 for x in findings.items if x["severity"] == "error")
    warnings = sum(1 for x in findings.items if x["severity"] == "warning")
    infos = sum(1 for x in findings.items if x["severity"] == "info")

    if errors > 0:
        verdict = "FAIL"
    elif warnings > 0:
        verdict = "PASS WITH WARNINGS"
    else:
        verdict = "PASS"

    lines = [
        f"Target: {target_name}  (DSH ARTIFACT: {artifact_type})",
        f"Verdict: {verdict}  (errors: {errors}, warnings: {warnings}, info: {infos})",
        "",
    ]
    for item in findings.items:
        icon = "❌" if item["severity"] == "error" else "⚠️" if item["severity"] == "warning" else "ℹ️"
        lines.append(f"{icon}  [{item['id']}] {item['title']}  ({item['file']}:{item['line']})")
        lines.append(f"    evidence: {item['evidence']}")
        lines.append(f"    why: {item['message']}")
        lines.append(f"    fix: {item['fix']}")
        lines.append("")
    for note in findings.notes:
        lines.append(f"  note: {note}")
    return "\n".join(lines)


def format_report_markdown(findings: Findings, target_name: str, artifact_type: str) -> str:
    errors = sum(1 for x in findings.items if x["severity"] == "error")
    warnings = sum(1 for x in findings.items if x["severity"] == "warning")
    infos = sum(1 for x in findings.items if x["severity"] == "info")

    if errors > 0:
        verdict = "FAIL"
    elif warnings > 0:
        verdict = "PASS WITH WARNINGS"
    else:
        verdict = "PASS"

    lines = [
        f"Target: {target_name}  (DSH ARTIFACT: {artifact_type})",
        f"Verdict: {verdict}  (errors: {errors}, warnings: {warnings}, info: {infos})",
        "",
    ]
    for item in findings.items:
        icon = "❌" if item["severity"] == "error" else "⚠️" if item["severity"] == "warning" else "ℹ️"
        lines.append(f"{icon}  **[{item['id']}]** {item['title']}  (`{item['file']}:{item['line']}`)")
        lines.append(f"    - evidence: `{item['evidence']}`")
        lines.append(f"    - why: {item['message']}")
        lines.append(f"    - fix: {item['fix']}")
        lines.append("")
    for note in findings.notes:
        lines.append(f"  note: {note}")
    return "\n".join(lines)


# -----------------------------------------------------------------------------
# Self-test suite (standalone; tempfile fixtures only)
# -----------------------------------------------------------------------------

def run_self_test() -> None:
    """Verify every check family against valid and invalid fixtures."""
    print("Running audit_dsh_artifacts.py self-test...")
    fired = set()

    def audit(fixture: Path, forced=None):
        local = Findings(fixture)
        artifact_type = lint_artifact(fixture, local, forced_type=forced)
        fired.update(item["id"] for item in local.items)
        return local, artifact_type

    with tempfile.TemporaryDirectory() as td:
        root = Path(td)

        # 1. Valid hand-written YAML patch: no errors expected.
        good_patch = root / "good.patch.yml"
        good_patch.write_text("""\
# profile patch layer
- insert:
    - id: docker-plugin
      name: 'my-docker-plugin'
      config:
        socketPath: /var/run/docker.sock
- id: session-telemetry-otel
  disabled: true
- id: mcp-github
  name: '@deepseek-ai/dsh-mcp-client'
  config:
    serverName: github
    transport: stdio
    command: npx
    args: ['-y', '@modelcontextprotocol/server-github']
    env:
      GITHUB_TOKEN: !!js process.env.GITHUB_TOKEN
""", encoding="utf-8")
        f1, _ = audit(good_patch)
        assert not [x for x in f1.items if x["severity"] == "error"], f"good patch errors: {f1.items}"
        assert not [x for x in f1.items if x["id"] == "DA-07"], "!!js env ref must not flag DA-07"
        print("  ✓ Valid YAML patch test passed")

        # 2. Valid managed (JSON) patch: no errors expected.
        good_managed = root / "managed.patch.yml"
        good_managed.write_text(
            "# rabbit-dsh managed MCP patch\n"
            + json.dumps([{"insert": [
                {"id": "mcp-fs", "name": "@deepseek-ai/dsh-mcp-client",
                 "config": {"serverName": "fs", "transport": "stdio", "command": "npx",
                            "args": ["-y", "@modelcontextprotocol/server-filesystem", "/tmp"]}},
            ]}], indent=2) + "\n",
            encoding="utf-8")
        f2, _ = audit(good_managed)
        assert not [x for x in f2.items if x["severity"] == "error"], f"managed patch errors: {f2.items}"
        print("  ✓ Valid managed JSON patch test passed")

        # 2b. Valid rabbit-dsh YAML managed plugin patch (nested env + !!js tags).
        good_yaml_managed = root / "yaml-managed.patch.yml"
        good_yaml_managed.write_text("""\
# rabbit-dsh managed plugin patch
- insert:
    - id: "mcp-github"
      name: "@deepseek-ai/dsh-mcp-client"
      config:
        serverName: "github"
        transport: "stdio"
        command: "npx"
        args: ["-y", "@modelcontextprotocol/server-github"]
        env:
          GITHUB_TOKEN: !!js process.env.GITHUB_TOKEN
""", encoding="utf-8")
        f2b, _ = audit(good_yaml_managed)
        assert not [x for x in f2b.items if x["severity"] == "error"], f"YAML managed patch errors: {f2b.items}"

        empty_managed = root / "empty-managed.patch.yml"
        empty_managed.write_text(PLUGIN_MANAGED_HEADER + "[]\n", encoding="utf-8")
        f2c, _ = audit(empty_managed)
        assert not [x for x in f2c.items if x["severity"] in ("error", "warning")], f"empty managed patch findings: {f2c.items}"
        print("  ✓ Valid YAML managed plugin patch tests passed (rows + empty)")

        # 3. Invalid patch: verbs, missing name, dup id, !!js, MCP fields, secret.
        bad_patch = root / "bad.patch.yml"
        bad_patch.write_text("""\
- replace:
    - id: broken-row
- insert:
    - id: no-name-row
- id: dup-id
  name: 'plugin-a'
- id: dup-id
  name: 'plugin-b'
- id: bad-js
  name: 'plugin-c'
  inject: !!js ['tools']
- id: mcp-bad
  name: '@deepseek-ai/dsh-mcp-client'
  config:
    serverName: 'bad name!!'
    transport: stdio
- id: mcp-worse
  name: '@deepseek-ai/dsh-mcp-client'
  config:
    serverName: fs
    transport: streamable-http
    command: npx
- id: leaky
  name: 'plugin-d'
  config:
    apiKey: 'sk-abcdefghijklmnopqrstuvwxyz012345'
""", encoding="utf-8")
        f3, _ = audit(bad_patch)
        fired.update(x["id"] for x in f3.items)
        for cid in ("DA-01", "DA-02", "DA-03", "DA-04", "DA-05", "DA-06", "DA-07"):
            assert cid in {x["id"] for x in f3.items}, f"{cid} did not fire on bad patch: {sorted({x['id'] for x in f3.items})}"
        print("  ✓ Invalid patch test passed (DA-01..DA-07 flagged)")

        # 4. Persona preset rows.
        good_preset = root / "agent.cordis.yml"
        good_preset.write_text("""\
- id: persona
  name: '@deepseek-ai/dsh-persona'
  config:
    text: You are a code review assistant. Read-only suggestions, no implementation.
    complete: false
    includeRuntimeContext: true
- insert:
    - id: tools
      name: '@deepseek-ai/dsh-tools'
""", encoding="utf-8")
        f4a, _ = audit(good_preset)
        assert not [x for x in f4a.items if x["severity"] == "error"], f"good preset errors: {f4a.items}"

        bad_preset = root / "bad-preset.agent.cordis.yml"
        bad_preset.write_text("""\
- id: persona
  name: '@deepseek-ai/dsh-persona'
  config:
    complete: maybe
""", encoding="utf-8")
        f4b, _ = audit(bad_preset)
        preset_ids = {x["id"] for x in f4b.items}
        assert "DA-08" in preset_ids, f"DA-08 did not fire on bad persona: {preset_ids}"
        print("  ✓ Persona preset test passed (valid clean, invalid flagged DA-08)")

        # 5. Workflows: valid scaffold-shaped and invalid meta/script.
        good_wf = root / "good-workflow.json"
        good_wf.write_text(json.dumps({
            "meta": {"name": "pr-review", "description": "Multi-agent PR review", "phases": ["fetch-diff", "audit"]},
            "args": {"prNumber": 1},
            "script": "async function main(args) {\n  phase('fetch-diff');\n  const r = await parallel([agent('a'), agent('b')]);\n  return r.filter(Boolean);\n}",
        }, indent=2), encoding="utf-8")
        f5a, _ = audit(good_wf)
        assert not [x for x in f5a.items if x["severity"] == "error"], f"good workflow errors: {f5a.items}"

        bad_wf = root / "bad-workflow.yaml"
        bad_wf.write_text("""\
meta:
  name: Bad Workflow Name
  description: "x"
  mode: ralph
  maxIterations: 10
  phases:
    - fetch-diff
script: |
  export const meta = {};
  async function main(args) {
    phase('undeclared-phase');
    const r = await parrallel([agent('a')]);
    return r;
  }
""", encoding="utf-8")
        f5b, _ = audit(bad_wf)
        wf_ids = {x["id"] for x in f5b.items}
        for cid in ("DA-09", "DA-10", "DA-11", "DA-12"):
            assert cid in wf_ids, f"{cid} did not fire on bad workflow: {sorted(wf_ids)}"
        print("  ✓ Workflow test passed (valid clean, invalid flagged DA-09..DA-12)")

        # 6. settings.yaml.
        good_settings = root / "settings.yaml"
        good_settings.write_text("""\
telemetry:
  disabled: true

agent-default-model:
  provider: deepseek-official
  model: deepseek-chat

permission:
  defaultPreset: workspace-write
""", encoding="utf-8")
        f6a, _ = audit(good_settings)
        assert not [x for x in f6a.items if x["severity"] == "error"], f"good settings errors: {f6a.items}"

        bad_settings = root / "settings-invalid.yaml"
        bad_settings.write_text("""\
agent-default-model:
  provider: deepseek-official

permission:
  defaultPreset: full-access

telemetry:
  disabled: "yes"

llm-pi-ai:
  providers:
    deepseek-official:
      api: openai-completions
      baseURL: https://api.example.com
""", encoding="utf-8")
        f6b, _ = audit(bad_settings)
        st_ids = {x["id"] for x in f6b.items}
        for cid in ("DA-13", "DA-14", "DA-15", "DA-16"):
            assert cid in st_ids, f"{cid} did not fire on bad settings: {sorted(st_ids)}"
        print("  ✓ settings.yaml test passed (valid clean, invalid flagged DA-13..DA-16)")

        # 7. skill.json consistency.
        skill_dir = root / "my-skill"
        skill_dir.mkdir()
        (skill_dir / "SKILL.md").write_text("---\nname: my-skill\ndescription: Fixture skill for manifest consistency checks.\n---\n# Skill\n", encoding="utf-8")
        (skill_dir / "skill.json").write_text(json.dumps({
            "name": "other-name", "version": "1.0", "entry": "missing.py",
            "disableModelInvocation": "false",
        }), encoding="utf-8")
        f7, _ = audit(skill_dir / "skill.json")
        assert "DA-17" in {x["id"] for x in f7.items}, f"DA-17 did not fire: {f7.items}"
        print("  ✓ skill.json manifest test passed (DA-17 flagged)")

        # 8. Credentials permissions.
        cred = root / ".env"
        cred.write_text("DEEPSEEK_API_KEY=\nDSH_SESSION_ID=should-not-be-here\n", encoding="utf-8")
        cred.chmod(0o644)
        f8, _ = audit(cred)
        assert "DA-18" in {x["id"] for x in f8.items}, f"DA-18 did not fire: {f8.items}"
        cred.chmod(0o600)
        f8b, _ = audit(cred)
        assert not [x for x in f8b.items if x["id"] == "DA-18" and x["evidence"].startswith("mode")], "0600 file must not flag permission warning"
        print("  ✓ Credential file test passed (DA-18 flagged on 0644, clean on 0600)")

        # 9. Session JSONL.
        good_log = root / "session.v3.jsonl"
        good_log.write_text("\n".join([
            json.dumps({"type": "session", "version": 3, "id": "abc", "createdAt": 0}),
            json.dumps({"type": "user/message", "seq": 1, "time": 0, "data": {}, "surfaceOp": "append"}),
            json.dumps({"type": "tool/call", "seq": 2, "time": 0, "data": {}}),
            json.dumps({"type": "custom/thing", "seq": 3, "time": 0, "data": {}, "ignorable": True}),
        ]) + "\n", encoding="utf-8")
        f9a, _ = audit(good_log)
        assert not [x for x in f9a.items if x["severity"] == "error"], f"good session errors: {f9a.items}"

        bad_log = root / "session-bad.jsonl"
        bad_log.write_text("\n".join([
            json.dumps({"type": "not-a-session", "seq": 1}),
            json.dumps({"type": "user/message", "seq": 5, "data": {}, "surfaceOp": "append"}),
            json.dumps({"type": "user/message", "seq": 2, "data": {}, "surfaceOp": "append"}),
            json.dumps({"type": "tool/call", "seq": 3, "data": {}, "surfaceOp": "append"}),
            json.dumps({"type": "mystery/event", "seq": 4, "data": {}}),
            "not json at all",
        ]) + "\n", encoding="utf-8")
        f9b, _ = audit(bad_log)
        log_ids = {x["id"] for x in f9b.items}
        for cid in ("DA-19", "DA-20", "DA-21"):
            assert cid in log_ids, f"{cid} did not fire on bad session log: {sorted(log_ids)}"
        print("  ✓ Session JSONL test passed (valid clean, invalid flagged DA-19..DA-21)")

    expected = {f"DA-{n:02d}" for n in range(1, 22)}
    missing = expected - fired
    assert not missing, f"Self-test fixtures never fired: {sorted(missing)}"

    print("\nAll audit_dsh_artifacts.py self-tests PASSED (9/9).")


# -----------------------------------------------------------------------------
# CLI entrypoint
# -----------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="DeepSeek Harness (DSH) artifact static linter (DA-01..DA-21)."
    )
    parser.add_argument("path", nargs="?", default=".",
                        help="Patch/preset/workflow/settings/skill.json/.env/session-JSONL path.")
    parser.add_argument("--type", choices=ARTIFACT_TYPES,
                        help="Force the artifact family instead of sniffing.")
    parser.add_argument("--format", choices=["text", "json", "markdown"], default="text",
                        help="Output format (default: text).")
    parser.add_argument("--strict", action="store_true", help="Exit 1 on warnings too.")
    parser.add_argument("--check", help="Comma-separated check IDs to filter (e.g. DA-04,DA-06).")
    parser.add_argument("--list-checks", action="store_true", help="Print the check catalog and exit.")
    parser.add_argument("--output", help="Write report to this file instead of stdout.")
    parser.add_argument("--self-test", action="store_true", help="Run internal self-tests and exit.")

    args = parser.parse_args()

    if args.self_test:
        run_self_test()
        sys.exit(0)

    if args.list_checks:
        for cid in sorted(CHECK_INFO):
            title, why, fix = CHECK_INFO[cid]
            print(f"{cid}  {title}\n    why: {why}\n    fix: {fix}\n")
        sys.exit(0)

    target = Path(args.path)
    if not target.exists():
        sys.exit(f"audit_dsh_artifacts: target does not exist: {target}")

    findings = Findings(target)
    artifact_type = lint_artifact(target, findings, forced_type=args.type)

    if args.check:
        allowed = {part.strip() for part in args.check.split(",")}
        findings.items = [x for x in findings.items if x["id"] in allowed]

    if args.format == "json":
        report = json.dumps({
            "target": str(target),
            "type": artifact_type,
            "findings": findings.items,
            "notes": findings.notes,
        }, indent=2, ensure_ascii=False)
    elif args.format == "markdown":
        report = format_report_markdown(findings, target.name, artifact_type)
    else:
        report = format_report_text(findings, target.name, artifact_type)

    if args.output:
        Path(args.output).write_text(report, encoding="utf-8")
        print(f"Report written to {args.output}", file=sys.stderr)
    else:
        print(report)

    errors = [x for x in findings.items if x["severity"] == "error"]
    warnings = [x for x in findings.items if x["severity"] == "warning"]
    if errors or (args.strict and warnings):
        sys.exit(1)
    sys.exit(0)


if __name__ == "__main__":
    main()
