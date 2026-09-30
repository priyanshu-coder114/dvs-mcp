# DVS MCP

Local MCP server that calls the Domain Valuation Service. Estibot and GoDaddy keys stay in DVS.

## Setup

```powershell
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
copy .env.example .env
```

Set `DVS_INTERNAL_TOKEN` in `.env` when DVS has internal auth turned on. A host `env` block replaces values loaded from `.env`. An empty `DVS_INTERNAL_TOKEN` in that block disables the token from `.env`.

`DVS_DROPS_WAIT_SECONDS` is how long a drops tool waits before returning a `jobId` (default 25). `DVS_DROPS_OUTPUT_DIR` is where the ZIP is written. A relative path is resolved from the MCP process working directory at startup. The tool result `path` is absolute and points at a file on that machine.

## Cursor

```json
{
  "mcpServers": {
    "dvs": {
      "command": "D:\\Web_devlopment\\Namekart-official\\MCP\\.venv\\Scripts\\python.exe",
      "args": ["-m", "dvs_mcp"],
      "env": {
        "DVS_BASE_URL": "http://localhost:90",
        "DVS_INTERNAL_TOKEN": ""
      }
    }
  }
}
```

## Claude Desktop

```json
{
  "mcpServers": {
    "dvs": {
      "command": "D:\\Web_devlopment\\Namekart-official\\MCP\\.venv\\Scripts\\python.exe",
      "args": ["-m", "dvs_mcp"],
      "env": {
        "DVS_BASE_URL": "http://localhost:90",
        "DVS_INTERNAL_TOKEN": "",
        "DVS_DROPS_OUTPUT_DIR": "D:\\Web_devlopment\\Namekart-official\\MCP\\output\\estibot-drops"
      }
    }
  }
}
```

The server speaks stdio. In MCP 2.x the server class is `MCPServer`.
