"""MCP Server Registry — manages connections, discovers tools, routes calls.

The agent interacts with the registry, not individual MCP clients.
Tool names are globally unique; the registry routes calls to the right server.
"""
import logging
from typing import Any

from backend.mcp.client import MCPClient

logger = logging.getLogger(__name__)


class MCPRegistry:
    """Registry of all configured MCP servers."""

    def __init__(self, server_configs: list[dict]):
        self._configs = server_configs
        self._clients: dict[str, MCPClient] = {}
        self._tool_router: dict[str, str] = {}
        self._all_tools: list[dict] = []

    def connect_all(self) -> None:
        """Connect to all configured servers and discover tools."""
        for cfg in self._configs:
            name = cfg.get("name", "unknown")
            client = MCPClient(cfg)
            client.connect()
            self._clients[name] = client

            tools_from_server = client.get_tools()
            for tool in tools_from_server:
                tool_name = tool["name"]
                if tool_name in self._tool_router:
                    logger.warning(
                        f"Duplicate tool name '{tool_name}' from server '{name}', "
                        f"already registered from '{self._tool_router[tool_name]}' "
                        f"(skipping duplicate)"
                    )
                    continue
                self._tool_router[tool_name] = name
                self._all_tools.append({**tool, "_server": name})
                logger.info("MCP tool discovered: server=%r tool=%r", name, tool_name)

            if not tools_from_server:
                logger.info(
                    "MCP server %r: 0 tools from list_tools (disconnected=%s)",
                    name,
                    not client.is_connected(),
                )

        logger.info(
            f"MCPRegistry: {len(self._clients)} servers, "
            f"{len(self._all_tools)} tools discovered (registered)"
        )

    def get_available_tools(self) -> list[dict]:
        """Return all tools across all servers."""
        return self._all_tools

    def get_tools_for_server(self, server_name: str) -> list[dict]:
        """Return tools for a specific server."""
        client = self._clients.get(server_name)
        if not client:
            return []
        return client.get_tools()

    def call_tool(self, tool_name: str, arguments: dict) -> Any:
        """Route a tool call to the correct server."""
        server_name = self._tool_router.get(tool_name)
        if not server_name:
            raise ValueError(
                f"Unknown tool '{tool_name}'. "
                f"Available: {list(self._tool_router.keys())}"
            )
        client = self._clients[server_name]
        return client.call_tool(tool_name, arguments)

    def health_check(self) -> dict[str, bool]:
        """Check connectivity to all servers."""
        return {
            name: client.is_connected()
            for name, client in self._clients.items()
        }
