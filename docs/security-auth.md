# Security and authentication

This page ties together **identity**, **Unity Catalog**, **Databricks Apps resources**, **secrets**, and **network** behavior for Genify. Step-by-step deploy and troubleshooting remain in **[deploy.md](deploy.md)**.

**Related:** [SECURITY.md](../SECURITY.md) (reporting, scope), [public-repo-checklist.md](public-repo-checklist.md) (before publishing), [design-decisions.md](design-decisions.md) (ADR-21: CORS).

---

## Demo vs production scope

Genify is a **reference / demo** application for Databricks Apps, MCP, and Lakebase. As shipped, it is **not** a fully threat-modeled production product. Your **workspace** controls who can run the app, which data it can reach, and how secrets are stored.

For vulnerability reporting and open-source hygiene, see **[SECURITY.md](../SECURITY.md)** and **[public-repo-checklist.md](public-repo-checklist.md)**.

---

## Genify app identity

When Genify runs as a **Databricks App**, requests use the **app’s service identity** (service principal / OAuth app associated with the app), not end-user credentials, for:

- **Lakebase** — SQLAlchemy sessions and persistence ([`db.py`](../src/genify/backend/db.py)).
- **MCP** — `DatabricksMCPClient` resolves UC-managed MCP and app-hosted MCP using that identity’s permissions.
- **Unity Catalog** — SQL executed by UC functions (warehouses, table metadata) runs under grants available to that identity.

End-user identity for API routes may still come from **`get_current_user`** / workspace SSO patterns you configure; **MCP and UC execution** are governed by the **app principal** unless you change the architecture.

---

## Unity Catalog

- **`app.yaml`** lists MCP servers, including **`uc_managed`** entries with **`uc_catalog`** and **`uc_schema`** (see [mcp-and-agents.md](mcp-and-agents.md)).
- The app identity needs **`EXECUTE`** (and any other required privileges) on **those functions** and **`USAGE`** on the catalog/schema.
- UC functions may read **table metadata**, **lineage**, and **profiles** via SQL against Unity Catalog and system tables—grant **`SELECT`** on the tables and resources those functions query, per your deployment.

If tools show **`0 tools discovered`** or permission errors after deploy, verify grants for the **Genify app identity**, not only your interactive user. See [deploy.md — Troubleshooting](deploy.md#troubleshooting) and [mcp-and-agents.md — Unity Catalog permissions](mcp-and-agents.md#unity-catalog-permissions-for-the-genify-app).

---

## Databricks Apps resources

Genify binds compute and data resources declared in [`src/genify/app.yaml`](../src/genify/app.yaml). Deploy scripts patch these via the SDK—see [`scripts/deploy/genify_app_update_resources.py`](../scripts/deploy/genify_app_update_resources.py):

| Resource | Purpose |
|----------|---------|
| **SQL warehouse** | UC function deployment scripts and MCP-backed SQL; app `sql-warehouse` binding in Genify. |
| **Serving endpoints** | Main LLM and (optional) summarizer endpoints referenced as env vars. |
| **Lakebase (`postgres`)** | Session storage and metadata; either **provisioned** (`instance_name` + `database_name`) or **autoscaling** (`branch` + `database` paths). |

Full sequence and config keys: **[deploy.md](deploy.md)** (warehouse, Lakebase, `deploy.config.yaml`).

---

## Secrets and environment

- **`deploy.config.yaml`** — Local deploy configuration (warehouse, endpoints, catalog/schema, app names). **Gitignored**; copy from `deploy.config.example.yaml`. See [public-repo-checklist.md](public-repo-checklist.md).
- **`LLM_ENDPOINT_NAME`** / **`SUMMARIZER_ENDPOINT_NAME`** — Can override endpoint names from `app.yaml` at runtime (see [config.py](../src/genify/backend/config.py)).
- **API keys** — Prefer Databricks-managed secrets and app env injection for any keys you add; do not commit secrets.

Run **`./scripts/check_repo_hygiene.sh`** before open-sourcing (see checklist).

---

## Network and CORS

The FastAPI app uses permissive CORS for the demo SPA (**ADR-21** in [design-decisions.md](design-decisions.md)). For strict production deployments, **restrict `allow_origins`** and align with your App’s public URL and cookie/session policy.

**SSE** (`GET /api/sessions/{id}/stream`) is a long-lived HTTP response from the same origin as the API in typical App deployments—harden **TLS**, **auth**, and **origin** policy for your environment.

---

## Checklist (operators)

- [ ] App identity has **UC** rights for catalog/schema/functions in `app.yaml`.
- [ ] **Warehouse** and **Lakebase** bindings match **Apps → your app → resources**.
- [ ] **`deploy.config.yaml`** not committed; endpoints and IDs set for each environment.
- [ ] Review **CORS** and **secrets** before production-style rollout.
