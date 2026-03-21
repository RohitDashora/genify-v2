"""Table-profiling MCP server.

4 tools: profile_table, get_schema, sample_rows, profile_columns_light.
Uses streamable HTTP transport on port 8000 (Databricks App default).
Auth is handled by the app's service principal — callers never pass tokens.
"""
import json

from mcp.server.fastmcp import FastMCP

from cdda_tools import data_tools
from server import client_factory

mcp = FastMCP("genify-table-profiler")


@mcp.tool()
def profile_table(table_fqn: str) -> str:
    """High-level table stats (DESCRIBE DETAIL). Returns storage location, size, partitions, last modified."""
    session = client_factory.get_session()
    result = data_tools.profile_table(session, table_fqn)
    return json.dumps(result)


@mcp.tool()
def get_schema(table_fqn: str) -> str:
    """Table schema — columns with name, type, and nullable flag."""
    session = client_factory.get_session()
    result = data_tools.get_schema(session, table_fqn)
    return json.dumps(result)


@mcp.tool()
def sample_rows(table_fqn: str, limit: int = 20) -> str:
    """Random sample of rows from the table."""
    session = client_factory.get_session()
    result = data_tools.sample_rows(session, table_fqn, limit=limit)
    return json.dumps(result)


@mcp.tool()
def profile_columns_light(table_fqn: str, top_k: int = 20) -> str:
    """Light column profiling — null rate, distinct estimate, top values per column."""
    session = client_factory.get_session()
    result = data_tools.profile_columns_light(session, table_fqn, top_k=top_k)
    return json.dumps(result)


def main() -> None:
    mcp.run(transport="streamable-http")


if __name__ == "__main__":
    main()
