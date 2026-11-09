# DeepSeek Harness (dsh) Docs & Tutorials

> Snapshot of official + community documentation as of 2026-11-08.

DeepSeek Harness (dsh) Docs & Tutorials | DeepSeek Harness
- function insertBanner(){var n=document.createElement("div");n.id="__docusaurus-base-url-issue-banner-container";n.innerHTML='\n\n

Your Docusaurus site did not load properly.

\n

A very common reason is a wrong site [baseUrl configuration](https://docusaurus.io/docs/docusaurus.config.js/#baseUrl).

\n

Current configured baseUrl = /en/

\n

We suggest trying baseUrl =

\n\n',document.body.prepend(n);var e=document.getElementById("__docusaurus-base-url-issue-banner-suggestion-container"),s=window.location.pathname,o="/"===s.substr(-1)?s:s+"/";e.textContent=o}document.addEventListener("DOMContentLoaded",function(){void 0===window.docusaurus&&insertBanner()}){"@context":"https://schema.org","@type":"WebSite","name":"DeepSeek Harness (dsh) Docs & Tutorials","alternateName":["DeepSeek Harness","dsh docs","DeepSeek Harness docs"],"url":"https://deepseekdocs.com","inLanguage":"en"}{"@context":"https://schema.org","@type":"FAQPage","mainEntity":[{"@type":"Question","name":"What is DeepSeek Harness?","acceptedAnswer":{"@type":"Answer","text":"An AI harness for coding and automation. One dsh command starts the Web UI, TUI or tasks; capabilities are extended by plugins."}},{"@type":"Question","name":"How is it different from IDE assistants?","acceptedAnswer":{"@type":"Answer","text":"IDE assistants orbit the current window. A harness is a standalone process with its own config, sessions, plugins and permission model."}},{"@type":"Question","name":"Where do I start?","acceptedAnswer":{"@type":"Answer","text":"Open the docs from the left rail, or follow the three steps on this page: learn what DSH is, add your key, run npx @deepseek-ai/dsh web."}}]}{"@context":"https://schema.org","@type":"SoftwareApplication","name":"DeepSeek Harness (dsh)","description":"An AI harness for coding and automation, offering Web UI, TUI and task modes; capabilities are extended by plugins.","applicationCategory":"DeveloperApplication","operatingSystem":"macOS, Linux, Windows","url":"https://deepseekdocs.com","offers":{"@type":"Offer","price":"0","priceCurrency":"CNY"}}{"@context":"https://schema.org","@type":"Organization","name":"DeepSeek Harness Community","url":"https://deepseekdocs.com","logo":"https://deepseekdocs.com/img/logo.svg","sameAs":["https://github.com/dsh-external/hub","https://github.com/0xsline/awesome-deepseek-harness"]}{"@context":"https://schema.org","@type":"BreadcrumbList","itemListElement":[{"@type":"ListItem","position":1,"name":"Home","item":"https://deepseekdocs.com"},{"@type":"ListItem","position":2,"name":"DeepSeek Harness (dsh) Docs & Tutorials","item":"https://deepseekdocs.com/"}]}{"@context":"https://schema.org","@type":"WebSite","@id":"https://deepseekdocs.com/#website","url":"https://deepseekdocs.com/","name":"DeepSeek Harness (dsh) 教程与文档","description":"DeepSeek Harness 中文教程与文档：安装、配置、命令、插件、MCP 与工作流。","inLanguage":["zh-CN","en"]}
{"@context":"https://schema.org","@type":"Organization","@id":"https://deepseekdocs.com/#organization","name":"DeepSeek Harness 社区","url":"https://deepseekdocs.com/","logo":{"@type":"ImageObject","url":"https://deepseekdocs.com/img/logo-1024.png"}}

!function(){var t=function(){try{return new URLSearchParams(window.location.search).get("docusaurus-theme")}catch(t){}}()||function(){try{return window.localStorage.getItem("theme")}catch(t){}}();document.documentElement.setAttribute("data-theme",t||(window.matchMedia("(prefers-color-scheme: dark)").matches?"dark":"light")),document.documentElement.setAttribute("data-theme-choice",t||"system")}(),function(){try{const c=new URLSearchParams(window.location.search).entries();for(var[t,e]of c)if(t.startsWith("docusaurus-data-")){var a=t.replace("docusaurus-data-","data-");document.documentElement.setAttribute(a,e)}}catch(t){}}()Skip to main content[DeepSeek Harness](./index.md)[Docs](./getting-started/quickstart.md)[Ecosystem](./ecosystem.md)[Community](./community.md)[官方仓库](https://github.com/deepseek-ai/deepseek-harness){"@context":"https://schema.org","@type":"WebPage","@id":"https://deepseekdocs.com/en/#webpage","url":"https://deepseekdocs.com/en/","name":"DeepSeek Harness","inLanguage":"en","isPartOf":{"@id":"https://deepseekdocs.com/#website"},"publisher":{"@id":"https://deepseekdocs.com/#organization"}}[DeepSeek Harness](./index.md)Community docs·Open source

## Contents

- [Product](#product)
- [Capabilities](#capabilities)
- [Shortcuts](#shortcuts)
- [Community](#community)
- [Open the Web UI locally](#open-the-web-ui-locally)
- [What it actually does](#what-it-actually-does)
- [Read next](#read-next)
- [FAQ](#faq)

---

## Product

[Overview](./index.md)[Docs12](./getting-started/quickstart.md)[Ecosystem](./ecosystem.md)[Community](./community.md)

## Capabilities

[What is DSH](./learn/intro/what-is-dsh.md)[Setup](./user-guide/configuration.md)[Subagents](./features/subagent.md)[MCP](./features/mcp.md)[Workflows](./features/workflow.md)[Plugins](./user-guide/plugins.md)

## Shortcuts

[Start5min](./getting-started/quickstart.md)[Config](./user-guide/configuration.md)[CLI](./user-guide/cli.md)[Plugins](./user-guide/plugins.md)[FAQ](./reference/faq.md)

## Community

**WeChat**Scan to joinPath**Overview**中文[GitHub](https://github.com/0xsline/awesome-deepseek-harness)[Get started](./getting-started/quickstart.md)

# Get DeepSeek Harness running

Community docs. Run npx @deepseek-ai/dsh web, add your API key, then choose a local workspace.

[Get started](./getting-started/quickstart.md)[Browse plugins](./ecosystem.md)
[What is DSHA standalone process, distinct from IDE assistants. Capabilities ship as plugins.What is DSH](./learn/intro/what-is-dsh.md)
- [Add your keyPut DEEPSEEK_API_KEY in ~/.dsh/.env with 0600 perms.Configuration](./user-guide/configuration.md)
- [Open the Web UIRun npx @deepseek-ai/dsh web, pick a working directory, and start a session.CLI](./user-guide/cli.md)

## Open the Web UI locally

Pick a working directory and start chatting. Install plugins from Git sources, restart web after.

dsh  zsh

$ dsh web
dsh web: http://127.0.0.1:3080

$ dsh plugin --profile web add \
  "github:dsh-external/dsh-session-search#main"
✓ installed
[CLI reference](./user-guide/cli.md)

## What it actually does

PluginsOne-line bundle install. Repository sources apply on change. Search, memory, vision all ride on plugins.Session searchRead-only search across dsh, Codex, Claude Code, pi and OpenCode history. No index.Multi-modelDifferent agents or sessions can choose different providers/models; plan mode itself does not switch models.PrivacyTelemetry can be disabled (DSH_TELEMETRY_DISABLED=1). Anonymous ID is resettable.

## Read next

### Get started

- [Learning path](./getting-started/learning-path.md)
- [Quickstart](./getting-started/quickstart.md)

### Usage

- [CLI](./user-guide/cli.md)
- [Configuration](./user-guide/configuration.md)
- [Plugins](./user-guide/plugins.md)
- [Permissions](./user-guide/permissions.md)
- [Privacy](./user-guide/privacy.md)

### Features

- [Built-in tools](./features/tools.md)
- [Subagents](./features/subagent.md)
- [Skills](./features/skills.md)
- [MCP](./features/mcp.md)
- [Workflows](./features/workflow.md)
- [FAQ](./reference/faq.md)

## FAQ

What is DeepSeek Harness?An AI harness for coding and automation. One dsh command starts the Web UI, TUI or tasks; capabilities are extended by plugins.

How is it different from IDE assistants?

IDE assistants orbit the current window. A harness is a standalone process with its own config, sessions, plugins and permission model.

Where do I start?

Open the docs from the left rail, or follow the three steps on this page: learn what DSH is, add your key, run npx @deepseek-ai/dsh web.
