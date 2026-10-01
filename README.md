# DVS MCP

Local MCP server that calls the Domain Valuation Service. Estibot and GoDaddy keys stay in DVS.

The server speaks stdio. Each person installs it on their own machine. Cursor or Claude Desktop starts it and that machine calls DVS over HTTP. There is no hosted URL for this server.

## Requirements

- Python 3.11 or newer
- Network access to `DVS_BASE_URL` (default in `.env.example`: `https://dvs.vps4.auctionhacker.com`)
- `DVS_INTERNAL_TOKEN` when DVS has internal auth turned on. Send the token separately. Do not commit it.

## Setup

Windows:

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e .
copy .env.example .env
```

macOS / Linux:

```bash
python3.11 -m venv .venv
.venv/bin/python -m pip install -e .
cp .env.example .env
```

Use `pip install -e ".[dev]"` instead when you need the tests.

Edit `.env` and set `DVS_INTERNAL_TOKEN` if internal auth is on. Other values:

| Variable | Role |
|---|---|
| `DVS_BASE_URL` | DVS origin. `.env.example` points at `https://dvs.vps4.auctionhacker.com`. |
| `DVS_INTERNAL_TOKEN` | Sent as `X-Internal-Token` when non-empty. |
| `DVS_SOURCE` | Sent as `X-Source`. Default `dashboard`. |
| `DVS_PLATFORM_TYPE` | GoDaddy `platformType`. Default `AMP2`. |
| `DVS_SYSTEM_ACTOR` | Sent as `X-System-Actor`. Default `mcp`. |
| `DVS_DROPS_WAIT_SECONDS` | How long a drops tool waits before returning a `jobId`. Default `25`. Must be a positive number. |
| `DVS_DROPS_OUTPUT_DIR` | Where the drops ZIP is written. Default `output/estibot-drops`. |

A host `env` block replaces values loaded from `.env`. An empty `DVS_INTERNAL_TOKEN` in that block disables the token from `.env`.

A relative `DVS_DROPS_OUTPUT_DIR` is resolved from the MCP process working directory at startup. The tool result `path` is absolute and points at a file on the machine running the server.

## Cursor

Replace the command with the full path to the virtualenv Python from setup.

Windows:

```json
{
  "mcpServers": {
    "dvs": {
      "command": "C:\\path\\to\\MCP\\.venv\\Scripts\\python.exe",
      "args": ["-m", "dvs_mcp"],
      "env": {
        "DVS_BASE_URL": "https://dvs.vps4.auctionhacker.com",
        "DVS_INTERNAL_TOKEN": ""
      }
    }
  }
}
```

macOS / Linux: set `command` to `/path/to/MCP/.venv/bin/python`.

Put that in the user MCP config, or in the project `.cursor/mcp.json`. Restart Cursor and confirm the `dvs` server is connected.

## Claude Desktop

Same JSON, in the Claude Desktop MCP config. Fully quit Claude and open it again.

On Windows that file is `%APPDATA%\Claude\claude_desktop_config.json`. On macOS it is `~/Library/Application Support/Claude/claude_desktop_config.json`.

Set `DVS_DROPS_OUTPUT_DIR` in the `env` block to an absolute path when you want the ZIP somewhere other than the process working directory.

## Tools

Pass bare domains such as `example.com`, not URLs.

| Tool | Use |
|---|---|
| `estibot_appraisal` | Estibot appraisal |
| `estibot_siteinfo` | Estibot site info |
| `godaddy_govalue` | GoDaddy GoValue for one domain |
| `godaddy_govalue_bulk` | GoDaddy GoValue for more than one domain, at most 50 per call |
| `estibot_drops` | Start a drop-list download. May return a `jobId` before the ZIP exists. |
| `estibot_drops_status` | Check that `jobId` and download the ZIP when it is ready |

Leave `force_live` false unless you want a new paid vendor lookup. `force_live` spends vendor quota and cannot be combined with `max_age_days` or `cache_only`. Use `cache_only` when a cache miss must not call the vendor.

If a tool result has `"retry": false`, do not call that tool again in the same turn.

## Sharing

Push the repo or send the folder. Exclude `.venv`, `.env`, and `output/`. Each person runs the setup above with their own paths and their own token.
