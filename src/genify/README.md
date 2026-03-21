# Genify application

**Demo / reference app** — not for production use as-is. Hardening, scaling, and support are your responsibility if you deploy beyond evaluation.

Databricks App package: **FastAPI** backend + **Vite/React** frontend, deployed together from this directory.

## Layout

| Path | Purpose |
|------|---------|
| [`app.yaml`](app.yaml) | Databricks Apps manifest: command, `env` `valueFrom` resources, `config` (LLM, Lakebase, `mcp_servers`) |
| [`backend/`](backend/) | FastAPI app: `main.py`, `routes/`, `agent/`, `mcp/`, `llm/`, `db.py` |
| [`frontend/`](frontend/) | React SPA; `npm run build` → `frontend/dist` served by FastAPI in production |
| [`seed_templates/`](seed_templates/) | Initial YAML templates loaded into Lakebase on first start |
| [`requirements.txt`](requirements.txt) | Python dependencies for Apps runtime (pinned MCP stack; see file header) |

## Run locally

```bash
cd src/genify
pip install -r requirements.txt
export DATABRICKS_HOST=https://<workspace-host>
# OAuth or token — same as Databricks CLI / SDK
uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000
```

```bash
cd src/genify/frontend
npm install && npm run dev
```

For MCP and LLM calls to succeed, your shell must authenticate to the workspace (e.g. `databricks auth env` or token vars the SDK recognizes).

## Architecture

See **[../../docs/architecture.md](../../docs/architecture.md)** and **[../../docs/mcp-and-agents.md](../../docs/mcp-and-agents.md)**.

The **session page** loads **`GET /api/sessions/{id}`** (TanStack Query: loading/error/retry), **hydrates** the transcript from `conversation`, then opens **SSE** (`GET /api/sessions/{id}/stream`) via [`frontend/src/api.js`](frontend/src/api.js) `connectSSE` (optional **`onOpen`**). User-visible flow is a **conversation** plus a collapsible **activity trace** for `trace` events. See [client lifecycle](../../docs/architecture.md#client-lifecycle-browser) and [SSE event types](../../docs/architecture.md#sse-event-types-session-stream).

### Frontend UI surfaces

- **Shell:** `App.jsx` + `components/layout/AppShell.jsx` / `AppSidebar.jsx` — persistent sidebar (**Home**, **Library**), mobile drawer; lazy `Suspense` skeleton, `NotFound.jsx`, `ScrollToTop.jsx`.
- **Home:** catalog browser (React Query, table search), session launcher, session list (filters, relative time, delete confirm); `HelpHint` where useful.
- **Library:** `components/library/*` — list + detail (`/library`, `/library/:id`), YAML \| Markdown editor, Save/Revert, Copy; cards show `table_fqn` or **Combined**.
- **Session:** header (Back hidden on `md+`); transcript; composer; **CodeMirror** YAML panel; trace panel; **`complete` SSE** may carry **`completed_id`** for Library link and `PUT /api/completed/{id}`.

Details: [Frontend UI surfaces](../../docs/architecture.md#frontend-ui-surfaces) and [Lakebase §6](../../docs/architecture.md#6-lakebase-data-model-summary) in `docs/architecture.md`.

### Relationship to APX

[APX](https://github.com/databricks-solutions/apx) is Databricks’ toolkit for FastAPI + Vite/React Apps and AI-friendly workflows. Genify aligns on **manual `EventSource`**, **single-app FastAPI + static SPA**, and **`app.yaml` `valueFrom` resources**—not on reusing APX’s Rust CLI. For UX patterns close to APX’s agent guidance, see [skills/apx](https://github.com/databricks-solutions/apx/tree/main/skills/apx).

## Deploy

**[../../deploy.sh](../../deploy.sh)** runs `npm ci` / `npm run build` in `frontend/`, then uploads an **allowlist** to the workspace: `backend/`, `seed_templates/`, `app.yaml`, `requirements.txt`, and **`frontend/dist/`** only — not `node_modules`, not `frontend/src`, and not Vite/PostCSS/Tailwind config. Resource bindings are applied by **[../../scripts/deploy/genify_app_update_resources.py](../../scripts/deploy/genify_app_update_resources.py)** before `databricks apps deploy`. If you add new **runtime** top-level directories under `src/genify/`, add them to **`scripts/deploy/genify.sh`** staging as well.
