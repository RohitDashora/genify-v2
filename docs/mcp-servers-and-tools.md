# MCP servers and tools (reference)

This page lists **every MCP integration shipped in this repository**: the **custom profiler app** and the **Unity Catalog functions** exposed through **managed MCP**. Tool names as seen by the agent are often prefixed (e.g. `catalog__schema__function_name`); discovery scripts show the exact strings in your workspace.

**Related:** wiring and troubleshooting — [mcp-and-agents.md](mcp-and-agents.md); adding more servers — [extending.md](extending.md) and **Bring your own MCP servers** below.

---

## Bring your own MCP servers

Genify is designed so you are **not limited to the two sample servers**:

1. **Declare** additional entries under `config.mcp_servers` in [`src/genify/app.yaml`](../src/genify/app.yaml) (`databricks_app`, `uc_managed`, or a literal `url` where supported).
2. **Implement** tools on your side (another Databricks App with FastMCP, or UC functions in a schema you control).
3. **Grant** the Genify app identity permission to call those tools (warehouse, UC `EXECUTE`, app-to-app networking as applicable).
4. **Tune** the planner/gather surface with `mcp_tool_overrides` (`tool_hints`, `hidden_tools`, `extra_tools`) so the LLM sees helpful descriptions without auto-gathering expensive tools.

If `backend/mcp/client.py` already understands your `type`, wiring is **config-only**. New transport types require a small client extension — see [extending.md — Add a managed MCP server](extending.md#add-a-managed-mcp-server-another-uc-schema) and [Add a custom MCP app](extending.md#add-a-custom-mcp-app).

---

## Server 1: `profiler` (custom Databricks App)

| Item | Detail |
|------|--------|
| **Purpose** | Table-centric **profiling** via the SQL warehouse (row samples, schema, light stats). |
| **Code** | [`src/mcp-profiler/`](../src/mcp-profiler/) — FastMCP, streamable HTTP, default app port. |
| **Deploy** | [`scripts/deploy/profiler.sh`](../scripts/deploy/profiler.sh) |
| **URL resolution** | `WorkspaceClient().apps.get("genify-mcp-profiler")` + `/mcp` (see [`app.yaml`](../src/genify/app.yaml) `app_name`). |

### Tools (always four)

| Tool | Parameters | What it does |
|------|------------|--------------|
| `profile_table` | `table_fqn` | `DESCRIBE DETAIL` style overview: location, size, partition columns, last modified, file counts. |
| `get_schema` | `table_fqn` | Column names, types, nullable flags (parsed from `DESCRIBE TABLE`). |
| `sample_rows` | `table_fqn`, `limit` (default 20) | Random sample of rows for grounding examples in metadata text. |
| `profile_columns_light` | `table_fqn`, `top_k` (default 20) | Per-column null rate, distinct estimate, top values (lightweight profiling). |

Implementation: [`server/main.py`](../src/mcp-profiler/server/main.py), logic in [`cdda_tools/data_tools.py`](../src/mcp-profiler/cdda_tools/data_tools.py). **Views** may cause `profile_table` to surface warehouse errors; the agent can still call `get_schema` / `sample_rows` (as in session traces).

---

## Server 2: `uc-functions` (Databricks managed MCP)

| Item | Detail |
|------|--------|
| **Purpose** | **Unity Catalog metadata**, lineage, and optional workspace job listing — all enforced by UC / connection permissions. |
| **Definitions** | SQL under [`uc_functions/`](../uc_functions/) (deploy order in [`scripts/deploy/uc_functions.sh`](../scripts/deploy/uc_functions.sh)). |
| **Endpoint** | `{DATABRICKS_HOST}/api/2.0/mcp/functions/{uc_catalog}/{uc_schema}` |
| **Configured catalog/schema** | From [`app.yaml`](../src/genify/app.yaml) — example: `agent_spark` / `custom_agent` (must match deploy config). |

### UC functions exposed as MCP tools

Parameters are passed through MCP according to each function’s SQL signature; auto-gather in Genify only fires tools whose schemas match [`_build_tool_args`](../src/genify/backend/agent/core.py) (table FQN shapes). Tools still appear in the manifest for the planner.

| SQL object | Parameters (logical) | What it returns / does |
|------------|----------------------|-------------------------|
| `get_table_comments` | `p_catalog`, `p_schema`, `p_table` | Table-level and column-level **comments** from `system.information_schema`. |
| `get_table_column_metadata` | `p_catalog`, `p_schema`, `p_table` | Rich **column metadata** (types, nullability, defaults, comments, precision/scale). |
| `get_table_profile` | `p_catalog`, `p_schema`, `p_table` | **Wide profile** rows (`profile_category`, `profile_key`, `profile_value`) — table info, column aggregates, type distribution, etc. |
| `get_backward_lineage` | `table_full_name` (`catalog.schema.table`) | **Upstream** lineage — sources that feed the table, with job/pipeline hints. |
| `get_forward_lineage` | `table_full_name` | **Downstream** lineage — targets fed by this table. |
| `get_full_lineage` | `table_full_name` | **Both** directions with a `direction` column (`UPSTREAM` / `DOWNSTREAM`). |
| `list_jobs` | `max_results`, optional `name_filter` | Lists **Databricks jobs** via workspace HTTP connection `databricks_workspace_api` (see SQL prerequisites in file header). |
| `analyze_table` | `p_catalog`, `p_schema`, `p_table` | **Stored procedure** (not a table function): runs `ANALYZE TABLE … COMPUTE STATISTICS` + `DESCRIBE EXTENDED`. |

Source files: [`01_get_table_comments.sql`](../uc_functions/01_get_table_comments.sql) … [`08_analyze_table.sql`](../uc_functions/08_analyze_table.sql).

### Shipped `hidden_tools` (default `app.yaml`)

Some deployed functions are **omitted from the tool manifest and auto-gather** in the sample config to reduce noise, cost, or known platform quirks:

| Tool id pattern (example) | Reason in this demo |
|---------------------------|---------------------|
| `…__get_forward_lineage`, `…__get_backward_lineage` | Lineage often covered by `get_full_lineage` instead. |
| `…__get_table_profile` | Overlap with profiler + UC metadata; enable if you want UC-native profile rows in gather. |
| `…__analyze_table` | Procedure exposure via managed MCP can be **unreliable** (`UNRESOLVED_ROUTINE` in some setups); hide until invokable. |

Remove or edit these under `config.mcp_tool_overrides.hidden_tools` in [`app.yaml`](../src/genify/app.yaml) for your fork.

---

## Discovering exact tool names

From repo root (after `pip install -r src/genify/requirements.txt`):

```bash
python scripts/mcp_discover_profiler_tools.py
python scripts/mcp_discover_uc_tools.py --catalog agent_spark --schema custom_agent
```

---

## Context in the agent

Gather writes an incremental **`sessions.context_cache`**: per-table FQN maps, **`_mcp_tool_manifest`**, and **`_mcp_gather_complete`** when all expected tool cells exist. Reconnects **merge** existing cells and **skip** `call_tool` for keys already present (Activity trace: skip cached). See [mcp-and-agents.md — Context cache shape](mcp-and-agents.md#context-cache-shape-sessionscontext_cache).

The **executor does not call MCP again** per plan step; it uses the **cached** gather payload. Planner `data_sources` are **hints**, not a second tool scheduler — [architecture.md — Planner vs executor](architecture.md#5-agent-session-sequence-simplified).
