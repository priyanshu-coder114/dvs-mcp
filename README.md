# DVS MCP

Local MCP server that calls the Domain Valuation Service. Estibot and GoDaddy keys stay in DVS.

## Setup

```powershell
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
copy .env.example .env
```

Set `DVS_INTERNAL_TOKEN` in `.env` when DVS has internal auth turned on.

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

The server speaks stdio. In MCP 2.x the server class is `MCPServer`.
