# Table profiling MCP server

**Demo / reference** — companion to the Genify sample app; not a standalone production MCP product.

**Custom MCP server** deployed as a **Databricks App**. Exposes profiling tools over MCP (FastMCP / streamable HTTP) for use by Genify or other agents.

## Tools

| Tool | Parameters | Behavior |
|------|------------|----------|
| `profile_table` | `table_fqn` | DESCRIBE DETAIL — location, size, partitions, last modified |
| `get_schema` | `table_fqn` | DESCRIBE TABLE — columns, types, nullable |
| `sample_rows` | `table_fqn`, `limit` | Random row sample |
| `profile_columns_light` | `table_fqn`, `top_k` | Null rates, distinct estimates, top values |

`table_fqn` is `catalog.schema.table`.

## Architecture

- **Transport:** MCP over HTTP on port 8000 (path `/mcp`).
- **Auth:** Workspace **service principal** via `WorkspaceClient()` when running on Databricks Apps.
- **SQL:** Databricks **Statement Execution API** against the warehouse bound as `sql_warehouse` in [`app.yaml`](app.yaml).

## Local development

```bash
cd src/mcp-profiler
export WAREHOUSE_ID=<warehouse-id>
export DATABRICKS_HOST=https://<workspace-host>
export DATABRICKS_TOKEN=<pat>   # or use OAuth via CLI
uv run mcp-server
```

MCP endpoint: `http://0.0.0.0:8000/mcp`.

## Deployment (this repository)

**Do not rely on a local `.venv` in this directory for deploys.** `uv run` creates `.venv` with large native wheels; Databricks source snapshots reject files over **10MB**. The deploy script stages a **clean copy** (excludes `.venv` and caches) before `workspace import`.

**Primary:** deploy from the **repo root** with the shared pipeline (uploads a staged tree, updates app resources, triggers deploy):

```bash
./deploy.sh --profile <databricks-cli-profile>
```

Profiler-specific logic: [`scripts/deploy/profiler.sh`](../../scripts/deploy/profiler.sh). Config: `profiler_app` and `warehouse_id` in `deploy.config.yaml`.

The app receives **`WAREHOUSE_ID`** from the **`sql_warehouse`** resource binding (underscore name in [`app.yaml`](app.yaml)) — must stay aligned with the deploy script JSON.

## Genify integration

Genify references this app by name under `config.mcp_servers` in [`../genify/app.yaml`](../genify/app.yaml) (`type: databricks_app`, `app_name` matching `profiler_app` in deploy config).

## Project structure

```
src/mcp-profiler/
├── app.yaml              # Databricks App: command, resources
├── pyproject.toml        # Dependencies + entry point
├── server/
│   ├── main.py           # FastMCP server
│   └── client_factory.py
└── cdda_tools/           # Profiling + statement execution helpers
```

## Further reading

- [docs/architecture.md](../../docs/architecture.md) — MCP topology diagram
- [docs/deploy.md](../../docs/deploy.md) — full deploy checklist
