# Connect an MCP server

For an active DSH profile, use the shipped `cordis-plugin-development` skill's MCP bundle template. Install the workspace bundle with Plugin Manager when requested. Verify the installed row and call a tool exposed as `mcp__<serverName>__<toolName>`.

## Configuration-only bundle

The patch inserts an instance of the installed MCP client. For a remote server, use Streamable HTTP when the endpoint supports it.

```yaml
- insert:
    - id: mcp-demo
      name: '@deepseek-ai/dsh-mcp-client'
      config:
        serverName: demo
        transport: streamable-http
        url: http://127.0.0.1:3000/mcp
        failOnStartupError: true
```

For stdio, use `transport: stdio`, `command`, and optional `args`, `cwd`, and `env`. Use Loader expressions such as `!!js process.env.GITHUB_TOKEN` for existing credentials in a native patch. Inspect the installed client's schema for supported options.

## Use a scratch patch

`mcp list` inspects recognizable rows in a native patch or a managed patch. It does not resolve includes, expressions, or the final composed tool set. Use DSH inspection for the effective profile.

For local experiments, `mcp add` and `mcp remove` require an explicit path and write only their own managed format. Start with a new file. Pass leading-dash subprocess arguments individually as `--arg=-y`. Use a fixture endpoint or a local test server.

```bash
python3 "$rabbit_dsh_dir/scripts/rabbit_dsh.py" mcp add demo \
  --path ./demo.patch.yml --transport streamable-http --url http://127.0.0.1:3000/mcp
python3 "$rabbit_dsh_dir/scripts/rabbit_dsh.py" mcp list --path ./demo.patch.yml
# demo (streamable-http) -> Tool prefix: mcp__demo__<toolName>
python3 "$rabbit_dsh_dir/scripts/rabbit_dsh.py" mcp remove demo --path ./demo.patch.yml
```

When upgrading a patch created by an older version of `rabbit-dsh`, read its rows with `mcp list` and recreate the intended server in a fresh bundle. Preserve existing overrides and credential expressions in the native profile.

[Upstream MCP bundle procedure](https://github.com/deepseek-ai/deepseek-harness/blob/fcc0ad462172522aaf5c93a7b2e01f6b9f0b0159/packages/preset/agent-preset/skills/cordis-plugin-development/references/mcp-bundle.md)
