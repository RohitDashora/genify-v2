"""MCP client using DatabricksMCPClient.

Resolves server URLs automatically:
- databricks_app: looks up app URL via WorkspaceClient SDK
- uc_managed: builds URL from workspace host + catalog + schema
- url override: uses the provided URL directly

DatabricksMCPClient's sync ``list_tools`` / ``call_tool`` use ``asyncio.run()`` internally.
When Genify runs inside FastAPI (SSE / async handlers), a loop is already running, so those
calls must run in a worker thread where ``asyncio.run()`` is valid.
"""
from __future__ import annotations

import asyncio
import concurrent.futures
import logging
from typing import Any, Callable, TypeVar

logger = logging.getLogger(__name__)

# databricks-mcp sync wrappers use asyncio.run(); offload when we're inside FastAPI's loop.
_MCP_EXECUTOR = concurrent.futures.ThreadPoolExecutor(
    max_workers=8,
    thread_name_prefix="mcp_databricks_sync",
)
_MCP_CALL_TIMEOUT_S = 300

T = TypeVar("T")


def _run_databricks_mcp_blocking(fn: Callable[..., T], *args: Any, **kwargs: Any) -> T:
    """Run a DatabricksMCPClient sync method; use a thread if an event loop is already running."""
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return fn(*args, **kwargs)
    fut = _MCP_EXECUTOR.submit(lambda: fn(*args, **kwargs))
    return fut.result(timeout=_MCP_CALL_TIMEOUT_S)


class MCPClient:
    """Connects to a single MCP server via DatabricksMCPClient."""

    def __init__(self, config: dict):
        self.name = config.get("name", "unknown")
        self.config = config
        self._client = None
        self._tools: list[dict] = []
        self._tool_map: dict[str, dict] = {}
        self._connected = False

    def _resolve_url(self) -> str:
        """Resolve the MCP server URL from config."""
        if self.config.get("url"):
            return self.config["url"]

        from databricks.sdk import WorkspaceClient
        ws = WorkspaceClient()

        server_type = self.config.get("type", "")

        if server_type == "uc_managed":
            host = ws.config.host.rstrip("/")
            catalog = self.config.get("uc_catalog", "")
            schema = self.config.get("uc_schema", "")
            if not catalog or not schema:
                logger.warning(f"MCP [{self.name}] uc_managed missing catalog/schema")
                return ""
            url = f"{host}/api/2.0/mcp/functions/{catalog}/{schema}"
            logger.info(f"MCP [{self.name}] resolved UC managed URL: {url}")
            return url

        if server_type == "databricks_app":
            app_name = self.config.get("app_name", "")
            if not app_name:
                logger.warning(f"MCP [{self.name}] databricks_app missing app_name")
                return ""
            try:
                app = ws.apps.get(app_name)
                url = f"{app.url}/mcp"
                logger.info(f"MCP [{self.name}] resolved app URL: {url}")
                return url
            except Exception as e:
                logger.warning(f"MCP [{self.name}] failed to look up app '{app_name}': {e}")
                return ""

        logger.warning(f"MCP [{self.name}] unknown type '{server_type}' and no url configured")
        return ""

    def connect(self) -> None:
        """Resolve URL, connect, and discover tools."""
        url = self._resolve_url()
        if not url:
            logger.warning(f"MCP [{self.name}] no URL resolved, skipping")
            return

        try:
            from databricks_mcp import DatabricksMCPClient
            from databricks.sdk import WorkspaceClient

            self._client = DatabricksMCPClient(
                server_url=url,
                workspace_client=WorkspaceClient(),
            )
            tools = _run_databricks_mcp_blocking(self._client.list_tools)
            self._tools = [
                {
                    "name": t.name,
                    "description": t.description or "",
                    "inputSchema": t.inputSchema if hasattr(t, "inputSchema") else {},
                }
                for t in tools
            ]
            self._tool_map = {t["name"]: t for t in self._tools}
            self._connected = True
            logger.info(f"MCP [{self.name}] connected, {len(self._tools)} tools discovered")
        except ImportError as e:
            logger.warning(f"MCP [{self.name}] import failed: {e}")
        except Exception as e:
            logger.error(f"MCP [{self.name}] connection failed: {e}", exc_info=True)
            self._connected = False

    def is_connected(self) -> bool:
        return self._connected

    def get_tools(self) -> list[dict]:
        return self._tools

    def call_tool(self, tool_name: str, arguments: dict) -> Any:
        """Invoke a tool and return the result as a string."""
        if not self._client:
            raise RuntimeError(f"MCP [{self.name}] not connected")
        if tool_name not in self._tool_map:
            raise ValueError(f"Tool '{tool_name}' not found on server '{self.name}'")

        logger.info(f"MCP [{self.name}] calling tool: {tool_name}")
        try:
            result = _run_databricks_mcp_blocking(
                self._client.call_tool, tool_name, arguments
            )
            if getattr(result, "isError", False):
                detail = _normalize_result(result)
                return {"_mcp_error": True, "detail": detail or "MCP tool returned an error"}
            return _normalize_result(result)
        except Exception as e:
            logger.error(f"MCP [{self.name}] tool call failed: {tool_name}: {e}", exc_info=True)
            raise


def _normalize_result(result: Any) -> str:
    """Extract text content from MCP CallToolResult, return as string."""
    if hasattr(result, "content"):
        texts = []
        for block in result.content:
            if hasattr(block, "text"):
                texts.append(block.text)
            else:
                texts.append(str(block))
        return "\n".join(texts) if texts else str(result)
    if isinstance(result, str):
        return result
    return str(result)
