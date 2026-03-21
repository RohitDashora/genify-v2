# Security and authentication

This document summarizes how Genify and the profiler authenticate and what to lock down when copying this pattern.

---

## Databricks Apps identity

Each Databricks App runs as a **workspace service principal** (OAuth):

- Environment variables such as **`DATABRICKS_CLIENT_ID`**, **`DATABRICKS_CLIENT_SECRET`**, **`DATABRICKS_HOST`**, **`DATABRICKS_WORKSPACE_ID`** are injected by the platform.
- **`WorkspaceClient()`** (no profile) uses these credentials inside the app container.

Genify and the profiler use the same pattern for Databricks APIs (MCP, SQL statement execution, apps lookup).

---

## Resource bindings (least privilege)

Apps declare **resources** in [`src/genify/app.yaml`](../src/genify/app.yaml) (and the profiler’s `app.yaml`). At deploy time, [`scripts/deploy/`](../scripts/deploy/) PATCHes bindings so the service principal receives scoped access:

| Resource | Typical permission | Purpose |
|----------|-------------------|---------|
| SQL warehouse | `CAN_USE` | Run queries (profiler; Genify catalog browsing) |
| Serving endpoints | `CAN_QUERY` | LLM inference |
| Lakebase database | `CAN_CONNECT_AND_CREATE` | App state in PostgreSQL |

Do not grant broader permissions than needed. UC **function** and **table** access is enforced separately via Unity Catalog grants to the app principal.

---

## Unity Catalog

- Managed MCP tools execute **UC functions** in the catalog/schema you configure. Only grant **`EXECUTE`** (and any underlying table privileges those functions require) to the **app’s service principal**.
- Catalog browsing APIs in Genify use the warehouse + UC metadata paths; align grants with what you expose in the UI.

---

## Secrets and config

| Item | Guidance |
|------|----------|
| **`deploy.config.yaml`** | Gitignored — contains workspace-specific names and IDs. Do not commit. |
| **PATs in apps** | Prefer OAuth app identity; avoid embedding long-lived PATs in code. |
| **Lakebase** | Connection uses platform-injected `PG*` variables when the database is bound as an app resource. |

---

## User identity in the browser

If the app uses headers such as **`X-Forwarded-Email`** or similar for audit or personalization, document your workspace’s trusted proxy behavior. Do not treat client-supplied identity headers as authentication unless the gateway validates them.

Genify session rows are scoped by **`user_email`** from the gateway header. **Concurrent tabs** on the same session id are not server-serialized—see [architecture.md — Client lifecycle](architecture.md#client-lifecycle-browser).

---

## Related reading

- [Databricks Apps authorization](https://docs.databricks.com/en/dev-tools/databricks-apps/auth.html)
- [architecture.md](architecture.md) — where OAuth and MCP fit in the diagram
