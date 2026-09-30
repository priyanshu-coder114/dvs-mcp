from dotenv import load_dotenv
from mcp.server.mcpserver import MCPServer

INSTRUCTIONS = """
Domain Valuation Service tools. Pass bare domains like example.com, not URLs.
Use estibot_appraisal for Estibot appraisals and estibot_siteinfo for site info.
Use godaddy_govalue for one domain and godaddy_govalue_bulk for more than one, at most 50 domains per call.
Leave force_live false unless the user explicitly asks for a new paid lookup. force_live spends vendor quota and cannot be combined with max_age_days or cache_only.
Use cache_only when a cache miss must not call the vendor.
estibot_drops starts a drop-list download and may return a jobId before the ZIP exists. Then call estibot_drops_status with that jobId. The ZIP is saved on the machine running this server; the path in the result is a local absolute path.
If a tool result has "retry": false, do not call that tool again in this turn.
""".strip()

mcp = MCPServer("dvs", instructions=INSTRUCTIONS)


def main() -> None:
    load_dotenv()
    from dvs_mcp.tools.estibot import register as register_estibot
    from dvs_mcp.tools.godaddy import register as register_godaddy

    register_estibot(mcp)
    register_godaddy(mcp)
    mcp.run(transport="stdio")
