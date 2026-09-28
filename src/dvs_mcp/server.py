from dotenv import load_dotenv
from mcp.server.mcpserver import MCPServer

mcp = MCPServer("dvs")


def main() -> None:
    load_dotenv()
    from dvs_mcp.tools.estibot import register as register_estibot
    from dvs_mcp.tools.godaddy import register as register_godaddy

    register_estibot(mcp)
    register_godaddy(mcp)
    mcp.run(transport="stdio")
