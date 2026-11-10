"""`python -m mcp_server`：plugin 的 .mcp.json 啟動的進入點。"""

from mcp.server.mcpserver import MCPServer

from mcp_server import spike


def main() -> None:
    server = MCPServer("drive-reader")
    # SPIKE：只為了實測風險 #1、#4、#8，階段 2 結束前連同 spike.py 一起移除。
    spike.register(server)
    server.run()


if __name__ == "__main__":
    main()
