# MCP and agents

Genify uses the **Model Context Protocol (MCP)** so the LLM can call **tools** with workspace-enforced permissions. This document explains how **managed** and **custom** servers are wired in this repo.

**Tool inventory (every server + tool shipped here):** [mcp-servers-and-tools.md](mcp-servers-and-tools.md).

**Bring your own MCP:** Genify loads **any** servers you list in `app.yaml` (`databricks_app`, `uc_managed`, optional `url`). Add your own UC functions or another Databricks App exposing MCP — see [mcp-servers-and-tools.md — Bring your own MCP servers](mcp-servers-and-tools.md#bring-your-own-mcp-servers) and [extending.md](extending.md).

### Cursor / agent operators

For a **repo-grounded** walkthrough (gather vs planner vs executor, `_build_tool_args`, `mcp_tool_overrides`, and troubleshooting), use the Cursor skill:

- **`.cursor/skills/genify-uc-managed-mcp/SKILL.md`** (local only if `.cursor/` is gitignored — copy from a teammate or recreate from this doc).

**Discovery scripts** (from repo root, after `pip install -r src/genify/requirements.txt`):

- `python scripts/mcp_discover_uc_tools.py` — UC managed endpoint (catalog/schema flags)
- `python scripts/mcp_discover_profiler_tools.py` — profiler Databricks App `/mcp`

---

## Managed vs custom (in this demo)

| Pattern | What it is | In this repo |
|---------|------------|--------------|
| **Managed MCP** | Databricks-hosted MCP over HTTPS; tools map to UC functions (and other managed server types). | `uc-functions` server → `/api/2.0/mcp/functions/{catalog}/{schema}` |
| **Custom MCP** | Your own server, often a **Databricks App** exposing an MCP route. | `profiler` server → `{profiler_app_url}/mcp` (FastMCP) |

Both are reached from Genify using **`DatabricksMCPClient`** (`databricks-mcp` on PyPI), with auth via the app’s **workspace OAuth** credentials (`WorkspaceClient()` inside the app runtime).

Reference: [Use Databricks managed MCP servers](https://docs.databricks.com/gcp/en/generative-ai/mcp/managed-mcp).

---

## Configuration: `app.yaml`

MCP servers are declared under `config.mcp_servers` in [`src/genify/app.yaml`](../src/genify/app.yaml):

```yaml
mcp_servers:
  - name: "profiler"
    type: "databricks_app"
    app_name: "genify-mcp-profiler"

  - name: "uc-functions"
    type: "uc_managed"
    uc_catalog: "agent_spark"
    uc_schema: "custom_agent"
```

- **`databricks_app`** — Genify resolves the URL with `WorkspaceClient().apps.get(app_name)` and appends `/mcp`.
- **`uc_managed`** — URL is `{host}/api/2.0/mcp/functions/{uc_catalog}/{uc_schema}`.

Adding another server is typically **config-only** if the client already supports the type; see [extending.md](extending.md).

### Optional: `mcp_tool_overrides`

Under `config.mcp_tool_overrides` in [`src/genify/app.yaml`](../src/genify/app.yaml) you can tune how tools appear to the **planner** and which tools run during **auto-gather**:

| Key | Purpose |
|-----|---------|
| `tool_hints` | Map tool name → short text merged into the manifest as `planner_hint` (section guidance). |
| `hidden_tools` | Tool names omitted from the manifest **and** skipped during MCP `call_tool` gather. |
| `extra_tools` | List of `{name, description, inputSchema?}` entries that appear in the manifest only (`callable: false`) — not invoked via MCP. |

If an `extra_tools` name matches a discovered tool, the discovered row wins; the config description is appended as an extra hint (warning logged).

---

## UC functions (managed MCP backend)

SQL in [`uc_functions/`](../uc_functions/) is deployed **in filename order** by [`scripts/deploy/uc_functions.sh`](../scripts/deploy/uc_functions.sh). Those functions become the **tool implementations** behind the managed MCP endpoint for the configured catalog and schema.

Deploy config keys: `uc_catalog`, `uc_schema` in [`deploy.config.example.yaml`](../deploy.config.example.yaml) must match `app.yaml`.

### Unity Catalog permissions for the Genify app

Genify calls managed MCP with **`WorkspaceClient()` inside the Databricks App** — that is the **app’s OAuth / service principal**, not your personal CLI user.

**`list_tools` only returns UC functions that identity is allowed to use.** If the app principal lacks Unity Catalog access on the configured catalog and schema, you can see:

- App logs: `MCP [uc-functions] connected, 0 tools discovered` (and `MCP server 'uc-functions': 0 tools from list_tools (disconnected=False)`).
- Meanwhile, locally: `python scripts/mcp_discover_uc_tools.py --catalog … --schema …` shows many tools — because that script uses **`WorkspaceClient(profile=…)`** (your user), which *does* have access.

**What to grant** (exact SQL varies by org; names are examples):

- **`USE CATALOG`** on the catalog (e.g. `agent_spark`).
- **`USE SCHEMA`** on the schema (e.g. `custom_agent`).
- **`EXECUTE`** on the **functions** in that schema that should appear as MCP tools (or a role that includes those privileges).

Grant these to the **Genify app’s service principal** (the identity shown for the app in the Databricks workspace / Apps settings).

**Verify after grants:** Redeploy or restart the app, open a new session, and confirm logs show  
`MCP [uc-functions] connected, N tools discovered` with **N &gt; 0**, and the planner manifest includes UC tool names (often prefixed, e.g. `agent_spark__custom_agent__get_table_comments`).

---

## Python dependencies (Genify app)

The MCP client stack must be installable on **Databricks Apps** (see [`src/genify/requirements.txt`](../src/genify/requirements.txt)):

- **`databricks-mcp==0.9.0`** — Declares **`databricks-ai-bridge`** (older `0.2.0` omitted it and caused `No module named 'databricks_ai_bridge'` at runtime).
- **`mcp`** — Pinned compatible release (see requirements file); `databricks-mcp` requires `>=1.13.0`.
- **`databricks-ai-bridge`** and **`mlflow`** — Pinned explicitly so **`pip` does not backtrack** for minutes during app deploy (large transitive trees). **`tiktoken>=0.8`** is required by `databricks-ai-bridge` (older `0.5.x` worsened resolution).
- **`numpy==1.26.4`** — Matches **`databricks-sql-connector`**’s `numpy<2` constraint early in resolution.
- **`databricks-sdk`** — Pinned in requirements for reproducibility.

If MCP connects but **0 tools** appear, check app logs for import errors and verify these packages appear in the deployed environment’s installed list.

---

## Context cache shape (`sessions.context_cache`)

After MCP gather, Genify persists a **canonical JSON object** in Lakebase:

- **`_mcp_tool_manifest`** — list of tool records for the planner and debugging: `name`, `server`, `description`, `inputSchema`, `source` (`mcp` or `config`), `callable` (boolean), optional `hint`. Built from live `list_tools` plus optional `mcp_tool_overrides`. Query in SQL, e.g. `context_cache->'_mcp_tool_manifest'`.
- **One key per fully qualified table** — `catalog.schema.table` → object mapping **tool name → string result** (MCP text).

Older sessions may still have **`_tool_descriptions`** (legacy string); the planner falls back to that when `_mcp_tool_manifest` is absent.

There is **no** single-table flattening of the outer dict (that would collide with metadata keys). **Genie** sessions with multiple tables produce **multiple** FQN keys. While gathering, the SSE **`trace`** event may include **`table_fqn`** when more than one table is in scope.

See also: [architecture.md](architecture.md#sse-event-types-session-stream).

### Concurrent SSE and MCP gather

Each `GET /api/sessions/{id}/stream` runs the agent from the start. **MCP gather** (connecting to servers and calling tools) is **serialized per session** inside the Genify process using an `asyncio.Lock` and a **double-check** of `sessions.context_cache` after acquiring the lock:

- If two browser tabs (or overlapping EventSource connections) open the same session before `context_cache` is written, the second waits, then reloads the session; if the first finished gather, the second **skips** duplicate MCP calls and may emit a trace like “Using cached MCP context (another connection finished gather)”.
- After an interactive **`question`**, the session UI **closes** `EventSource` while the user composes an answer, then opens a **new** stream after **`POST /answer`**—see [architecture.md — Client lifecycle](architecture.md#client-lifecycle-browser).
- **Recommendation:** Still use **one tab per session** when possible — cleaner UX and avoids racing two full agent loops (planning/execution can still overlap across streams).
- **Multi-worker:** The lock is **per process**. If you run **multiple Uvicorn workers**, two workers can still gather the same session in parallel until you use **one worker** for the app or add a **database advisory lock** around gather (future hardening).

---

## Runtime flow (conceptual)

1. **`MCPRegistry`** connects each configured server during gather (see [`backend/mcp/registry.py`](../src/genify/backend/mcp/registry.py)).
2. **`run_agent`** calls MCP tools (via `asyncio.to_thread` around `call_tool` where needed), streams **`trace`** lines per tool, and saves the structured dict above to **`context_cache`**. If connect or individual tools fail, the agent **continues** with partial or empty context—check the session **activity trace** for warnings; the transcript may still produce YAML (template-only quality).
3. **Planner** uses the LLM to build steps; **executor** runs steps (LLM calls also offloaded with `asyncio.to_thread`).

Full sequence: [architecture.md](architecture.md#5-agent-session-sequence-simplified). Session **UI** behavior (transcript, hydration, 409 answer handling): [architecture.md — Client lifecycle](architecture.md#client-lifecycle-browser).

---

## Troubleshooting

| Symptom | Likely cause |
|---------|----------------|
| `No module named 'databricks_ai_bridge'` | Upgrade `databricks-mcp` / ensure `databricks-ai-bridge` is installed (see requirements above). |
| `0 tools discovered` (all servers) | Import failure or wrong URL — check logs after each server’s `connect()`. |
| `0 tools` for **uc-functions** only (profiler OK) | **UC permissions for the Genify app identity**, not deploy: HTTP can still be 200 while `list_tools` returns []. See [Unity Catalog permissions for the Genify app](#unity-catalog-permissions-for-the-genify-app) above; compare with `mcp_discover_uc_tools.py` using your **user** profile. |
| UI looks idle during gather | Expand **Activity trace** — tool-level **`trace`** events should advance during MCP calls; the **conversation** shows sparse plan/question lines by design. |
| `asyncio.run() cannot be called from a running event loop` (older builds) | Sync `DatabricksMCPClient.list_tools` / `call_tool` use `asyncio.run()`; Genify now runs those calls in a **thread pool** when invoked from FastAPI’s async context (see `backend/mcp/client.py`). Redeploy Genify after pulling the fix. |
| UC tools missing | UC SQL not deployed, wrong `uc_catalog` / `uc_schema` in `app.yaml`, or **app service principal** lacks UC access — see [Unity Catalog permissions for the Genify app](#unity-catalog-permissions-for-the-genify-app). |
| Profiler unreachable | Profiler app not deployed, wrong `app_name`, or app URL not resolvable from Genify. |
| Pip “taking longer than usual” / backtracking on deploy | Keep **`mlflow`**, **`mcp`**, **`databricks-ai-bridge`**, **`numpy`**, **`tiktoken`** pinned in `requirements.txt` as shipped; see [deploy.md](deploy.md#troubleshooting). |

More deploy-side fixes: [deploy.md](deploy.md#troubleshooting).
