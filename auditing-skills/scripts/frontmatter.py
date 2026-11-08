#!/usr/bin/env python3
"""YAML frontmatter parser for SKILL.md files (fallback when PyYAML is absent).

Covers the flat key/value subset that appears in skill frontmatter: plain
scalars, single/double-quoted scalars (including multi-line quotes), block
scalars (| and > with chomping indicators), comments, and blank lines. Nested
structures are out of scope for skill metadata; keys are collected with their
line numbers so validation findings can cite exact locations.

Known divergences from PyYAML, acceptable for validation purposes:
- multi-line quoted scalars join with newlines (PyYAML folds with spaces)
- ambiguous lines such as `key: a: b` parse leniently instead of erroring

Usage from audit_static.py: `from frontmatter import parse`.
Verify with `python3 frontmatter.py --self-test`.
"""

import argparse
import re
import sys

KEY_RE = re.compile(r"^([A-Za-z0-9_-]+):\s*(.*)$")
SCALAR_INDICATORS = ("|", "|-", "|+", ">", ">-", ">+")


def parse(text):
    """Parse frontmatter from text.

    Returns {"meta": dict, "body": str, "key_lines": {key: 1-based line},
    "error": str or None}. body is everything after the closing delimiter.
    """
    lines = text.splitlines()
    if lines and lines[0].startswith("\ufeff"):
        lines[0] = lines[0].lstrip("\ufeff")
    if not lines or lines[0].strip() != "---":
        return {"meta": {}, "body": text, "key_lines": {},
                "error": "no opening '---' delimiter"}
    end = None
    for i in range(1, len(lines)):
        if lines[i].strip() in ("---", "..."):
            end = i
            break
    if end is None:
        return {"meta": {}, "body": text, "key_lines": {},
                "error": "no closing '---' delimiter"}

    meta, key_lines = {}, {}
    i = 1
    while i < end:
        raw = lines[i]
        stripped = raw.strip()
        if not stripped or stripped.startswith("#"):
            i += 1
            continue
        m = KEY_RE.match(raw)
        if not m:
            i += 1
            continue  # lenient: nested or unknown syntax is skipped
        key, rest = m.group(1), m.group(2).strip()
        key_lines[key] = i + 1
        if rest in SCALAR_INDICATORS:
            meta[key], i = _block_scalar(lines, i + 1, end, rest)
            continue
        if rest[:1] in ("'", '"'):
            meta[key], i = _quoted(lines, i, rest, end)
            continue
        meta[key] = _plain(rest)
        i += 1

    body = "\n".join(lines[end + 1:])
    return {"meta": meta, "body": body, "key_lines": key_lines, "error": None}


def _plain(rest):
    """Plain scalar: strip a trailing comment (# preceded by whitespace)."""
    return re.split(r"\s+#", rest, maxsplit=1)[0].rstrip()


def _find_close(s, quote):
    """Index of the closing quote, honoring escapes; None if unterminated."""
    j = 0
    while j < len(s):
        c = s[j]
        if quote == '"' and c == "\\":
            j += 2
            continue
        if c == quote:
            if quote == "'" and s[j + 1:j + 2] == "'":
                j += 2  # '' is an escaped single quote
                continue
            return j
        j += 1
    return None


def _quoted(lines, key_idx, rest, end):
    """Quoted scalar starting on line key_idx (0-based) with text `rest`.
    May continue on following lines until the quote closes or the block ends.
    Returns (value, next_line_index)."""
    quote = rest[0]
    buf = rest[1:]
    cur = key_idx
    while True:
        j = _find_close(buf, quote)
        if j is not None:
            inner = buf[:j]
            break
        cur += 1
        if cur >= end:
            inner = buf  # unterminated: be lenient, take what is there
            break
        buf += "\n" + lines[cur].lstrip()
    if quote == "'":
        value = inner.replace("''", "'")
    else:
        value = _unescape_double(inner)
    return value, cur + 1


def _unescape_double(s):
    out, i = [], 0
    pairs = {"\\\\": "\\", '\\"': '"', "\\n": "\n", "\\t": "\t", "\\r": "\r"}
    while i < len(s):
        if s[i] == "\\" and s[i:i + 2] in pairs:
            out.append(pairs[s[i:i + 2]])
            i += 2
        else:
            out.append(s[i])
            i += 1
    return "".join(out)


def _block_scalar(lines, i, end, indicator):
    """Block scalar (| or > with optional -/+ chomping) starting at line i.
    Returns (value, next_line_index)."""
    block = []
    while i < end:
        ln = lines[i]
        if ln.strip() == "":
            block.append("")
        elif ln[:1] in (" ", "\t"):
            block.append(ln)
        else:
            break
        i += 1
    while block and block[-1] == "":
        block.pop()
    ind = None
    for ln in block:
        if ln.strip():
            ind = len(ln) - len(ln.lstrip(" "))
            break
    if ind is None:
        return "", i
    out = [ln[ind:] if ln.strip() else "" for ln in block]
    text = _fold(out) if indicator.startswith(">") else "\n".join(out)
    if indicator.endswith("-"):
        return text.rstrip("\n"), i
    if text:
        text = text.rstrip("\n") + "\n"
    return text, i


def _fold(out):
    """Folded style: single newlines become spaces; blank lines stay newlines."""
    parts = []
    prev_empty = True
    for ln in out:
        if ln == "":
            parts.append("\n")
            prev_empty = True
        else:
            if parts and not prev_empty and not parts[-1].endswith("\n"):
                parts.append(" ")
            parts.append(ln)
            prev_empty = False
    return "".join(parts)


def _self_test():
    cases = [
        ("plain scalars",
         "---\nname: test-skill\ndescription: Does things\n---\nbody",
         {"name": "test-skill", "description": "Does things"}, {"name": 2}, None),
        ("trailing comment stripped",
         "---\ndescription: Does things # comment\n---\n",
         {"description": "Does things"}, {}, None),
        ("hash comment needs preceding space",
         "---\ndescription: use #tags\n---\n",
         {"description": "use"}, {}, None),
        ("quoted hash preserved",
         "---\ndescription: \"use #tags freely\"\n---\n",
         {"description": "use #tags freely"}, {}, None),
        ("single-quote escape",
         "---\ndescription: 'it''s fine'\n---\n",
         {"description": "it's fine"}, {}, None),
        ("double-quote escapes",
         '---\ndescription: "a\\nb \\"q\\""\n---\n',
         {"description": 'a\nb "q"'}, {}, None),
        ("literal block with colon",
         "---\ndescription: |\n  audits skills: metadata\n  second line\nname: x\n---\n",
         {"description": "audits skills: metadata\nsecond line\n", "name": "x"},
         {"description": 2, "name": 5}, None),
        ("folded block",
         "---\ndescription: >\n  one two\n\n  three\n---\n",
         {"description": "one two\nthree\n"}, {}, None),
        ("strip chomping",
         "---\ndescription: |-\n  no trailing\n---\n",
         {"description": "no trailing"}, {}, None),
        ("comments and blanks between keys",
         "---\n# lead comment\nname: a\n\n# mid\ndescription: b\n---\n",
         {"name": "a", "description": "b"}, {"name": 3, "description": 6}, None),
        ("multi-line double quote joins with newline",
         "---\ndescription: \"first\n  second\"\n---\n",
         {"description": "first\nsecond"}, {}, None),
        ("missing closing delimiter",
         "---\nname: x\n",
         {}, {}, "no closing"),
        ("missing opening delimiter",
         "name: x\n",
         {}, {}, "no opening"),
    ]
    failures = 0
    for label, text, want_meta, want_lines, want_err in cases:
        got = parse(text)
        problems = []
        for k, v in want_meta.items():
            if got["meta"].get(k) != v:
                problems.append(f"{k}: want {v!r}, got {got['meta'].get(k)!r}")
        for k, ln in want_lines.items():
            if got["key_lines"].get(k) != ln:
                problems.append(f"line {k}: want {ln}, got {got['key_lines'].get(k)}")
        if want_err is None and got["error"] is not None:
            problems.append(f"unexpected error: {got['error']}")
        if want_err is not None and (got["error"] is None or want_err not in got["error"]):
            problems.append(f"error: want ~{want_err}, got {got['error']!r}")
        if problems:
            failures += 1
            print(f"FAIL {label}: " + "; ".join(problems))
        else:
            print(f"pass {label}")
    print(f"{len(cases) - failures}/{len(cases)} passed")
    return 1 if failures else 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="YAML frontmatter parser (stdlib only)")
    ap.add_argument("--self-test", action="store_true",
                    help="run the built-in parser test cases")
    args = ap.parse_args()
    if args.self_test:
        sys.exit(_self_test())
    ap.print_help()
