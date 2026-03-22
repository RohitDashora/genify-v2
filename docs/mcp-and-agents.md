# MCP and agents (Genify)

This document summarizes how Genify connects to MCP servers, what **gather** does, and operational notes. It complements **[architecture.md](architecture.md)** and **[agentic-loop.md](agentic-loop.md)**.

## Topology

- **Custom MCP apps** (e.g. profiler) and **Unity Catalog managed MCP** (UC functions) are registered in [`src/genify/app.yaml`](../src/genify/app.yaml).
- The app uses **`MCPRegistry`** only — no ad-hoc HTTP from agent code to MCP endpoints.

## Gather (context_cache)

- Runs when `sessions.context_cache` is empty; results are persisted once per session.
- **One `call_tool` per `(table_fqn, tool_name)`** during that gather pass.
- **No MCP-level retries:** failures are stored as `{"_mcp_error": true, "detail": "..."}` under that tool key; the planner and executor continue with partial context.
- **Multi-worker:** the in-process `asyncio.Lock` for gather does not span Uvicorn workers — use a single worker or accept duplicate gather unless you add DB-level locking.

## Planner vs executor

- The **planner** sees the tool manifest and a text summary of context (including tool failures).
- The **executor** does **not** call MCP for plan `data_sources`; it only reads cached context.

## Deploy order

1. Deploy UC functions / custom MCP apps.
2. Register servers in `app.yaml` and deploy Genify.
3. Grant the app principal access to MCP-backed resources.

See **[extending.md](extending.md)** for adding servers and tools.

## Concurrent SSE and MCP gather

Genify serializes **MCP gather** per `session_id` in-process (`asyncio.Lock` in `core.py`). Overlapping `GET /api/sessions/{id}/stream` connections wait for the leader to persist `context_cache` before proceeding. **Multiple Uvicorn workers** do not share that lock — use one worker or add DB-level locking if you must scale workers.
