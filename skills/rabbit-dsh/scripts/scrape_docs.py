#!/usr/bin/env python3
"""
DeepSeek Harness Documentation Scraper & Offline Reference Consolidator.

Scrapes and consolidates documentation from two key sources:
  1. Official DeepSeek Harness Docs: https://deepseek-harness.github.io/deepseek-harness/
     (VitePress docs: develop/basic, cordis-tutorial, subsystems, cordis-api, cookbook)
  2. DeepSeekDocs Community Portal: https://deepseekdocs.com/en/
     (Docusaurus docs: features, user-guide, learn/core, learn/dev, guides, reference)

Converts HTML into clean, offline GitHub-flavored Markdown, normalizes internal links,
and generates a consolidated catalog and search index for offline lookups.

Zero external dependencies - strictly Python 3 standard library.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import html
import json
import os
from pathlib import Path
import re
import sys
import time
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET


COMMUNITY_SITEMAP = "https://deepseekdocs.com/sitemap.xml"
COMMUNITY_BASE = "https://deepseekdocs.com"

OFFICIAL_ENTRY = "https://deepseek-harness.github.io/deepseek-harness/en/develop/basic/"
OFFICIAL_BASE = "https://deepseek-harness.github.io/deepseek-harness"

USER_AGENT = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko)"


def fetch_url(url: str, retries: int = 3, delay: float = 0.5) -> str:
    """Fetch text content from a URL with User-Agent header and retries."""
    headers = {"User-Agent": USER_AGENT}
    req = urllib.request.Request(url, headers=headers)
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                return resp.read().decode("utf-8", errors="replace")
        except Exception:
            if attempt == retries - 1:
                raise
            time.sleep(delay * (attempt + 1))
    return ""


# -----------------------------------------------------------------------------
# Official Docs Scraper (VitePress)
# -----------------------------------------------------------------------------

def get_official_pages() -> list[str]:
    """Extract list of English markdown page keys from official VitePress entry."""
    raw_html = fetch_url(OFFICIAL_ENTRY)
    m = re.search(r'__VP_HASH_MAP__=JSON\.parse\((.*?)\);', raw_html)
    if not m:
        return []
    try:
        val = json.loads(m.group(1))
        data = json.loads(val)
        return sorted([k for k in data.keys() if k.startswith("en_")])
    except Exception as e:
        print(f"Error parsing official VP_HASH_MAP: {e}", file=sys.stderr)
        return []


def official_key_to_rel_path(key: str) -> Path:
    """Map VitePress key like 'en_develop_cordis-tutorial_01-first-plugin.md' to local relative path."""
    clean = key[3:] if key.startswith("en_") else key
    parts = clean.split("_")
    # Join parts into directory structure, keeping last part as filename
    rel_path = Path(*parts)
    return Path("official") / rel_path


def official_key_to_url(key: str) -> str:
    """Map VitePress key to full HTML URL."""
    rel = key.replace("_", "/")
    if rel.endswith(".md"):
        rel = rel[:-3] + ".html"
    return f"{OFFICIAL_BASE}/{rel}"


def convert_vitepress_to_markdown(vp_html: str, rel_path: Path) -> str:
    """Convert VitePress pre-rendered HTML to clean Markdown."""
    content = vp_html

    # Clean anchors and edit links
    content = re.sub(r'<(?:script|style)\b[^>]*>.*?</(?:script|style)>', '', content, flags=re.DOTALL | re.I)
    content = re.sub(r'<a[^>]*class="header-anchor"[^>]*>.*?</a>', '', content, flags=re.DOTALL)
    content = re.sub(r'<footer[^>]*>.*?</footer>', '', content, flags=re.DOTALL)

    # 1. Protect code blocks
    code_blocks: list[str] = []
    def save_cb(match: re.Match) -> str:
        lang = match.group(1)
        inner = match.group(2)
        inner = re.sub(r'<div class="line"[^>]*>', '\n', inner)
        inner = re.sub(r'<br\s*/?>', '\n', inner)
        raw = re.sub(r'<[^>]+>', '', inner)
        raw = html.unescape(raw).strip()
        idx = len(code_blocks)
        code_blocks.append(f"```{lang}\n{raw}\n```")
        return f"\n\n__CODE_BLOCK_{idx}__\n\n"

    content = re.sub(
        r'<div class="language-([a-zA-Z0-9_-]+)[^"]*">.*?<pre[^>]*><code[^>]*>(.*?)</code></pre>.*?</div>',
        save_cb, content, flags=re.DOTALL
    )

    # Fallback pre blocks
    def save_raw_pre(match: re.Match) -> str:
        raw = re.sub(r'<[^>]+>', '', match.group(1))
        raw = html.unescape(raw).strip()
        idx = len(code_blocks)
        code_blocks.append(f"```text\n{raw}\n```")
        return f"\n\n__CODE_BLOCK_{idx}__\n\n"

    content = re.sub(r'<pre[^>]*><code[^>]*>(.*?)</code></pre>', save_raw_pre, content, flags=re.DOTALL)

    # 2. Custom block callouts (tip, warning, danger, info)
    def convert_custom_block(match: re.Match) -> str:
        block_html = match.group(0)
        adm_type = "NOTE"
        if "tip" in block_html:
            adm_type = "TIP"
        elif "warning" in block_html:
            adm_type = "WARNING"
        elif "danger" in block_html:
            adm_type = "CAUTION"
        elif "info" in block_html:
            adm_type = "NOTE"

        inner = re.sub(r'<p class="custom-block-title">.*?</p>', '', block_html)
        inner = re.sub(r'<[^>]+>', ' ', inner)
        inner = html.unescape(inner).strip()
        lines = [line.strip() for line in inner.splitlines() if line.strip()]
        quoted = "\n".join(f"> {line}" for line in lines)
        return f"\n\n> [!{adm_type}]\n{quoted}\n\n"

    content = re.sub(r'<div class="[^"]*custom-block[^"]*">.*?</div>', convert_custom_block, content, flags=re.DOTALL)

    # 3. Tables
    def convert_table(match: re.Match) -> str:
        table_html = match.group(0)
        rows: list[list[str]] = []
        for tr in re.findall(r'<tr[^>]*>(.*?)</tr>', table_html, flags=re.DOTALL):
            cells = re.findall(r'<(?:th|td)[^>]*>(.*?)</(?:th|td)>', tr, flags=re.DOTALL)
            clean_cells = []
            for c in cells:
                c_text = re.sub(r'<code[^>]*>(.*?)</code>', r'`\1`', c, flags=re.DOTALL)
                # Keep entities encoded until the final tag-stripping pass.
                c_text = re.sub(r'<[^>]+>', '', c_text).strip().replace('\n', ' ')
                clean_cells.append(c_text)
            if clean_cells:
                rows.append(clean_cells)
        if not rows:
            return ""
        col_count = max(len(r) for r in rows)
        header = rows[0] + [""] * (col_count - len(rows[0]))
        lines = [
            "| " + " | ".join(header) + " |",
            "| " + " | ".join(["---"] * col_count) + " |"
        ]
        for r in rows[1:]:
            padded = r + [""] * (col_count - len(r))
            lines.append("| " + " | ".join(padded) + " |")
        return "\n\n" + "\n".join(lines) + "\n\n"

    content = re.sub(r'<table[^>]*>.*?</table>', convert_table, content, flags=re.DOTALL)

    # 4. Headings
    for level in range(6, 0, -1):
        def replace_h(m: re.Match, lvl=level) -> str:
            h_text = re.sub(r'<[^>]+>', '', m.group(1))
            h_text = html.unescape(h_text).strip().replace('\u200b', '')
            hashes = '#' * lvl
            return f"\n\n{hashes} {h_text}\n\n"
        content = re.sub(rf'<h{level}[^>]*>(.*?)</h{level}>', replace_h, content, flags=re.DOTALL)

    # 5. Lists
    content = re.sub(r'<li[^>]*>(.*?)</li>', r'\n- \1', content, flags=re.DOTALL)
    content = re.sub(r'</?(?:ul|ol)[^>]*>', '\n', content)

    # 6. Links (normalize internal links)
    def rewrite_links(match: re.Match) -> str:
        href = match.group(1)
        text = match.group(2)
        clean_text = re.sub(r'<[^>]+>', '', text).strip()
        if href.startswith("#"):
            return clean_text
        if href.startswith("/deepseek-harness/en/"):
            # Internal link to another official doc
            target = href.replace("/deepseek-harness/en/", "").strip("/")
            if target.endswith(".html"):
                target = target[:-5] + ".md"
            elif not target.endswith(".md"):
                target = target + ".md"
            return f"[{clean_text}]({target})"
        if href.startswith("/docs/"):
            target = href.replace("/docs/", "").strip("/")
            if target.endswith(".html"):
                target = target[:-5] + ".md"
            elif not target.endswith(".md"):
                target = target + ".md"
            return f"[{clean_text}]({target})"
        return f"[{clean_text}]({href})"

    content = re.sub(r'<a[^>]*href="([^"]+)"[^>]*>(.*?)</a>', rewrite_links, content, flags=re.DOTALL)

    # 7. Inline markup
    content = re.sub(r'<strong[^>]*>(.*?)</strong>', r'**\1**', content, flags=re.DOTALL)
    content = re.sub(r'<b[^>]*>(.*?)</b>', r'**\1**', content, flags=re.DOTALL)
    content = re.sub(r'<em[^>]*>(.*?)</em>', r'*\1*', content, flags=re.DOTALL)
    content = re.sub(r'<code[^>]*>(.*?)</code>', r'`\1`', content, flags=re.DOTALL)
    content = re.sub(r'<p[^>]*>(.*?)</p>', r'\n\n\1\n\n', content, flags=re.DOTALL)

    # 8. Strip remaining tags and unescape
    content = re.sub(r'<[^>]+>', '', content)
    content = html.unescape(content)

    # 9. Restore code blocks
    for idx, cb in enumerate(code_blocks):
        content = content.replace(f"__CODE_BLOCK_{idx}__", cb)

    # 10. Normalize whitespace
    content = re.sub(r'\r\n', '\n', content)
    content = re.sub(r'[ \t]+$', '', content, flags=re.MULTILINE)
    content = re.sub(r'\n{3,}', '\n\n', content)

    # 11. Synthesize Table of Contents for long pages (>100 lines) if not already present
    lines = content.splitlines()
    if len(lines) > 100 and not any(re.match(r'^#{1,6}\s.*(contents|table of contents)', ln, re.I) for ln in lines[:80]):
        h2_headings = []
        for ln in lines:
            m_h2 = re.match(r'^##\s+(.+)$', ln)
            if m_h2:
                h2_title = m_h2.group(1).strip()
                if h2_title.lower() not in ('contents', 'table of contents'):
                    slug = re.sub(r'[^\w\s-]', '', h2_title.lower()).strip()
                    slug = re.sub(r'[-\s]+', '-', slug)
                    h2_headings.append(f"- [{h2_title}](#{slug})")
        if len(h2_headings) >= 2:
            toc = '## Contents\n\n' + '\n'.join(h2_headings) + '\n\n---\n\n'
            # Insert after the first H1 or intro block
            m_first_h2 = re.search(r'\n##\s+', content)
            if m_first_h2:
                insert_idx = m_first_h2.start() + 1
                content = content[:insert_idx] + toc + content[insert_idx:]
            else:
                m_h1 = re.search(r'^#\s+[^\n]+\n+', content)
                if m_h1:
                    insert_idx = m_h1.end()
                    content = content[:insert_idx] + "\n" + toc + content[insert_idx:]

    return content.strip() + "\n"


def scrape_official_docs(output_dir: Path) -> dict[str, str]:
    """Scrape all official VitePress docs."""
    print("Fetching official documentation keys from VitePress...")
    keys = get_official_pages()
    print(f"Found {len(keys)} official English documentation pages.")

    official_catalog: dict[str, str] = {}
    total = len(keys)

    for i, key in enumerate(keys, 1):
        rel_path = official_key_to_rel_path(key)
        url = official_key_to_url(key)
        target_file = output_dir / rel_path
        target_file.parent.mkdir(parents=True, exist_ok=True)

        try:
            raw_html = fetch_url(url)
            # Find vp-doc container
            m_doc = re.search(r'<div style="position:relative;" class="vp-doc[^"]*"[^>]*>(.*?)</div>\s*</div>\s*</main>', raw_html, re.DOTALL)
            if not m_doc:
                m_doc = re.search(r'<main[^>]*>(.*?)</main>', raw_html, re.DOTALL)

            article_html = m_doc.group(1) if m_doc else raw_html

            # Extract title
            m_title = re.search(r'<title[^>]*>(.*?)</title>', raw_html, re.DOTALL)
            title = ""
            if m_title:
                raw_title = html.unescape(m_title.group(1)).strip()
                title = raw_title.split("|")[0].strip()

            md_content = convert_vitepress_to_markdown(article_html, rel_path)

            if title and not md_content.lstrip().startswith("# "):
                md_content = f"# {title}\n\n" + md_content

            with open(target_file, "w", encoding="utf-8") as f:
                f.write(md_content)

            official_catalog[str(rel_path)] = title or rel_path.stem
            print(f"[OFFICIAL {i}/{total}] Scraped {rel_path} ({len(md_content)} chars)")
        except Exception as e:
            print(f"[OFFICIAL {i}/{total}] ERROR scraping {url}: {e}", file=sys.stderr)

    return official_catalog


# -----------------------------------------------------------------------------
# Community Docs Scraper (Docusaurus)
# -----------------------------------------------------------------------------

def get_community_urls() -> list[str]:
    raw_sitemap = fetch_url(COMMUNITY_SITEMAP)
    tree = ET.fromstring(raw_sitemap)
    urls: list[str] = []
    ns = {
        "sm": "http://www.sitemaps.org/schemas/sitemap/0.9",
        "xhtml": "http://www.w3.org/1999/xhtml",
    }
    for url_elem in tree.findall("sm:url", ns):
        for link in url_elem.findall("xhtml:link", ns):
            if link.attrib.get("hreflang") == "en":
                href = link.attrib.get("href", "")
                if href and href not in urls:
                    urls.append(href)
    return sorted(urls)


def community_url_to_rel_path(url: str) -> Path:
    path_part = url.replace(COMMUNITY_BASE, "").strip("/")
    if path_part.startswith("en/"):
        path_part = path_part[3:]
    elif path_part == "en":
        path_part = ""

    if not path_part:
        return Path("community/index.md")

    if path_part.startswith("docs/"):
        path_part = path_part[5:]

    return Path("community") / Path(f"{path_part}.md")


def convert_docusaurus_to_markdown(article_html: str, doc_rel_path: Path) -> str:
    content = re.sub(r'<footer[^>]*>.*?</footer>', '', article_html, flags=re.DOTALL)
    content = re.sub(r'<nav[^>]*pagination-nav[^>]*>.*?</nav>', '', content, flags=re.DOTALL)
    content = re.sub(r'<a[^>]*class="hash-link"[^>]*>.*?</a>', '', content, flags=re.DOTALL)
    content = re.sub(r'<div[^>]*class="toc-collapsible[^>]*>.*?</div>', '', content, flags=re.DOTALL)

    code_blocks: list[str] = []
    def save_cb(match: re.Match) -> str:
        lang = ""
        m_lang = re.search(r'class="[^"]*language-([a-zA-Z0-9_-]+)', match.group(0))
        if m_lang:
            lang = m_lang.group(1)
        inner = match.group(1)
        inner = re.sub(r'<div class="token-line"[^>]*>', '\n', inner)
        inner = re.sub(r'<br\s*/?>', '\n', inner)
        raw = re.sub(r'<[^>]+>', '', inner)
        raw = html.unescape(raw).strip()
        idx = len(code_blocks)
        code_blocks.append(f"```{lang}\n{raw}\n```")
        return f"\n\n__CODE_BLOCK_{idx}__\n\n"

    content = re.sub(r'<pre[^>]*><code[^>]*>(.*?)</code></pre>', save_cb, content, flags=re.DOTALL)

    def convert_table(match: re.Match) -> str:
        table_html = match.group(0)
        rows: list[list[str]] = []
        for tr in re.findall(r'<tr[^>]*>(.*?)</tr>', table_html, flags=re.DOTALL):
            cells = re.findall(r'<(?:th|td)[^>]*>(.*?)</(?:th|td)>', tr, flags=re.DOTALL)
            clean_cells = []
            for c in cells:
                c_text = re.sub(r'<[^>]+>', '', c)
                c_text = html.unescape(c_text).strip().replace('\n', ' ')
                clean_cells.append(c_text)
            if clean_cells:
                rows.append(clean_cells)
        if not rows:
            return ""
        col_count = max(len(r) for r in rows)
        header = rows[0] + [""] * (col_count - len(rows[0]))
        lines = [
            "| " + " | ".join(header) + " |",
            "| " + " | ".join(["---"] * col_count) + " |"
        ]
        for r in rows[1:]:
            padded = r + [""] * (col_count - len(r))
            lines.append("| " + " | ".join(padded) + " |")
        return "\n\n" + "\n".join(lines) + "\n\n"

    content = re.sub(r'<table[^>]*>.*?</table>', convert_table, content, flags=re.DOTALL)

    for level in range(6, 0, -1):
        def replace_h(m: re.Match, lvl=level) -> str:
            h_text = re.sub(r'<[^>]+>', '', m.group(1))
            h_text = html.unescape(h_text).strip().replace('\u200b', '')
            hashes = '#' * lvl
            return f"\n\n{hashes} {h_text}\n\n"
        content = re.sub(rf'<h{level}[^>]*>(.*?)</h{level}>', replace_h, content, flags=re.DOTALL)

    content = re.sub(r'<li[^>]*>(.*?)</li>', r'\n- \1', content, flags=re.DOTALL)
    content = re.sub(r'</?(?:ul|ol)[^>]*>', '\n', content)
    content = re.sub(r'<code[^>]*>(.*?)</code>', r'`\1`', content, flags=re.DOTALL)
    content = re.sub(r'<strong[^>]*>(.*?)</strong>', r'**\1**', content, flags=re.DOTALL)
    content = re.sub(r'<p[^>]*>(.*?)</p>', r'\n\n\1\n\n', content, flags=re.DOTALL)
    content = re.sub(r'<[^>]+>', '', content)
    content = html.unescape(content)

    for idx, cb in enumerate(code_blocks):
        content = content.replace(f"__CODE_BLOCK_{idx}__", cb)

    content = re.sub(r'\n{3,}', '\n\n', content).strip()
    return content.strip() + "\n"


def scrape_community_docs(output_dir: Path) -> dict[str, str]:
    print("Fetching community doc list from sitemap.xml...")
    urls = get_community_urls()
    print(f"Found {len(urls)} community documentation pages to scrape.")

    catalog: dict[str, str] = {}
    total = len(urls)

    for i, url in enumerate(urls, 1):
        rel_path = community_url_to_rel_path(url)
        target_file = output_dir / rel_path
        target_file.parent.mkdir(parents=True, exist_ok=True)

        try:
            raw_html = fetch_url(url)
            m_article = re.search(r'<article[^>]*>(.*?)</article>', raw_html, re.DOTALL)
            article_html = m_article.group(1) if m_article else raw_html

            m_title = re.search(r'<title[^>]*>(.*?)</title>', raw_html, re.DOTALL)
            title = ""
            if m_title:
                raw_title = html.unescape(m_title.group(1)).strip()
                title = raw_title.split("|")[0].strip()

            md_content = convert_docusaurus_to_markdown(article_html, rel_path)

            if title and not md_content.lstrip().startswith("# "):
                md_content = f"# {title}\n\n" + md_content

            with open(target_file, "w", encoding="utf-8") as f:
                f.write(md_content)

            catalog[str(rel_path)] = title or rel_path.stem
            print(f"[COMMUNITY {i}/{total}] Scraped {rel_path} ({len(md_content)} chars)")
        except Exception as e:
            print(f"[COMMUNITY {i}/{total}] ERROR scraping {url}: {e}", file=sys.stderr)

    return catalog


def main() -> None:
    parser = argparse.ArgumentParser(description="Scrape and consolidate DeepSeek Harness official & community docs.")
    parser.add_argument("--output", "-o", default="skills/rabbit-dsh/references/docs",
                        help="Target output directory for scraped docs")
    parser.add_argument("--official-only", action="store_true", help="Scrape only official docs")
    parser.add_argument("--community-only", action="store_true", help="Scrape only community docs")
    args = parser.parse_args()

    out_dir = Path(args.output).resolve()
    consolidated_catalog: dict[str, str] = {}

    if not args.community_only:
        official_cat = scrape_official_docs(out_dir)
        consolidated_catalog.update(official_cat)

    if not args.official_only:
        comm_cat = scrape_community_docs(out_dir)
        consolidated_catalog.update(comm_cat)

    # The maintained, version-pinned authoring notes are outside the scrape.
    for note in sorted(output_dir.glob("official/pinned/*.md")):
        title = note.read_text(encoding="utf-8").splitlines()[0].removeprefix("# ")
        consolidated_catalog[note.relative_to(output_dir).as_posix()] = title

    # Save consolidated catalog with scraped_at date
    catalog_path = out_dir / "catalog.json"
    consolidated_catalog["scraped_at"] = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    with open(catalog_path, "w", encoding="utf-8") as f:
        json.dump(consolidated_catalog, f, indent=2, ensure_ascii=False)

    print(f"\nConsolidated Scraping Complete. Total docs saved: {len(consolidated_catalog)}")


if __name__ == "__main__":
    main()
