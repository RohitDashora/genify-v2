# MCP and agents (Genify)

This document summarizes how Genify connects to MCP servers, what **gather** does, and operational notes. It complements **[architecture.md](architecture.md)** and **[agentic-loop.md](agentic-loop.md)**.

## Topology

- **Custom MCP apps** (e.g. profiler) and **Unity Catalog managed MCP** (UC functions) are registered in [`src/genify/app.yaml`](../src/genify/app.yaml).
- The app uses **`MCPRegistry`** only — no ad-hoc HTTP from agent code to MCP endpoints.

## Gather (context_cache)

- Runs while the cache is **empty** or **`_mcp_gather_complete`** is not `true` (including **partial** progress after reconnect). The agent **merges** existing table/tool cells from the row, **skips** `call_tool` for cells that already exist (**trace**: skip cached), and **persists** after new cells until **`_mcp_gather_complete: true`**.
- **At most one successful `call_tool` per cell** while building a missing key; existing keys (including `{"_mcp_error": true, ...}`) are not retried unless the cache is cleared or a new session is used.
- **No MCP-level retries** within a single attempt: failures are stored as `{"_mcp_error": true, "detail": "..."}` under that tool key; the planner and executor continue with partial context.
- **Multi-worker:** the in-process `asyncio.Lock` for gather does not span Uvicorn workers — use a single worker or accept duplicate gather unless you add DB-level locking.

<a id="context-cache-shape-sessionscontext_cache"></a>

## Context cache shape (`sessions.context_cache`)

Lakebase stores one JSONB blob per session. Shape:

| Area | Role |
|------|------|
| **Table keys** | `catalog.schema.table` → `{ tool_name: result }`. Each key is a cell from auto-gather (or a prior run). |
| **`_mcp_tool_manifest`** | Rebuilt every time gather runs (`connect_all`); gives the planner current tool names and `inputSchema`. |
| **`_mcp_gather_complete`** | `true` only when every expected `(table_fqn, tool_name)` for the session `table_ref` and auto-gather list exists. Missing or `false` means the next stream may **resume** incremental gather. |

**Persistence:** Partial `UPDATE`s may occur after each newly filled cell (`_mcp_gather_complete` false until the final save). An **empty `{}`** must not be written when gather produces no usable payload (so reconnects do not “lock in” emptiness). Details: [agentic-loop.md — Gather](agentic-loop.md#1-gather-mcp), [`core.py`](../src/genify/backend/agent/core.py).

## Planner vs executor

- The **planner** sees the tool manifest and a text summary of context (including tool failures).
- The **executor** does **not** call MCP for plan `data_sources`; it only reads cached context.

## Deploy order

1. Deploy UC functions / custom MCP apps.
2. Register servers in `app.yaml` and deploy Genify.
3. Grant the app principal access to MCP-backed resources.

See **[extending.md](extending.md)** for adding servers and tools.

## Concurrent SSE and MCP gather

Genify serializes **MCP gather** per `session_id` in-process (`asyncio.Lock` in `core.py`). Overlapping `GET /api/sessions/{id}/stream` connections wait for the leader to persist `context_cache` (including **partial** incremental saves) before proceeding. **Multiple Uvicorn workers** do not share that lock — use one worker or add DB-level locking if you must scale workers.

## Python dependencies (Genify app)

The Genify Databricks App must install **`databricks-mcp`** and transitive **`databricks-ai-bridge`** (pinned in [`requirements.txt`](../src/genify/requirements.txt)). If you see **`No module named 'databricks_ai_bridge'`**, **`0 tools discovered`** for every server, or similar after deploy, **redeploy** the app so the Apps build reinstalls wheels.

## Unity Catalog permissions for the Genify app

The **Genify service principal / app identity** needs **Unity Catalog** grants to execute the functions in the catalog/schema referenced in `app.yaml` (and any resources those functions touch). See **[security-auth.md](security-auth.md)** and **[deploy.md](deploy.md)** troubleshooting.

<a id="optional-mcp_tool_overrides"></a>

## Optional `mcp_tool_overrides`

In [`app.yaml`](../src/genify/app.yaml), `config.mcp_tool_overrides` controls **`hidden_tools`**, **`tool_hints`**, and **`extra_tools`** (planner-only rows). See **[mcp-servers-and-tools.md](mcp-servers-and-tools.md#shipped-hidden_tools-default-appyaml)** for the shipped defaults and tuning notes.
