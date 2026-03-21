# Extending Genify

Patterns for teams that want to **reuse or fork** this reference.

**Shipped MCP tools (names + behavior):** [mcp-servers-and-tools.md](mcp-servers-and-tools.md) — start there before adding functions or custom apps so you do not collide with existing tool semantics.

---

## Add a managed MCP server (another UC schema)

1. Deploy UC functions to a catalog/schema (add SQL under [`uc_functions/`](../uc_functions/) or a new folder with a parallel deploy script).
2. Add a `mcp_servers` entry in [`src/genify/app.yaml`](../src/genify/app.yaml):

```yaml
- name: "my-uc-tools"
  type: "uc_managed"
  uc_catalog: "my_catalog"
  uc_schema: "my_schema"
```

3. Ensure [`backend/mcp/client.py`](../src/genify/backend/mcp/client.py) `type` handling covers your case (today: `uc_managed`, `databricks_app`, optional `url`).

Optional: add hints, hide specific tools from gather, or inject planner-only tool rows via `config.mcp_tool_overrides` in `app.yaml` — see [mcp-and-agents.md](mcp-and-agents.md#optional-mcp_tool_overrides).
4. Redeploy Genify; grant the app principal **EXECUTE** on the UC functions.

---

## Add a custom MCP app

1. Build another Databricks App that exposes MCP (e.g. FastMCP) on a path such as `/mcp`.
2. Register it in `app.yaml`:

```yaml
- name: "my-custom-server"
  type: "databricks_app"
  app_name: "my-mcp-app-name"
```

3. Deploy that app and grant Genify’s principal access if the MCP server checks UC or other resources.
4. Run [`deploy.sh`](../deploy.sh) or update Genify only after the custom app exists.

---

## Add or change UC SQL functions

- Edit or add files in [`uc_functions/`](../uc_functions/).
- **Order matters** — `00_`, `01_`, … prefixes control apply order in [`scripts/deploy/uc_functions.sh`](../scripts/deploy/uc_functions.sh).
- Update [`deploy.config.yaml`](../deploy.config.example.yaml) `uc_catalog` / `uc_schema` if you target a different namespace.

---

## Session stream: add an SSE event type

1. Emit from [`backend/agent/streamer.py`](../src/genify/backend/agent/streamer.py) (or yield dicts matching `sse-starlette` shape).
2. Register the event name in [`src/genify/frontend/src/api.js`](../src/genify/frontend/src/api.js) `connectSSE` (`events` array + `handlerMap`).
3. Update [`SessionView.jsx`](../src/genify/frontend/src/components/SessionView.jsx) handlers—prefer **transcript** for user-visible text, **`trace`** only for diagnostics. For **`question`**, keep behavior aligned with [architecture.md](architecture.md#client-lifecycle-browser): close SSE after handling, preserve composer draft on same-pause replay.
4. Document the event in [architecture.md](architecture.md#sse-event-types-session-stream).

## Transcript hydration

If new fields on [`sessions`](../src/genify/backend/models.py) should appear when the user **opens** a session (before SSE), extend `GET /api/sessions/{id}` and map them in `SessionView` hydration logic alongside `conversation`.

## New workspace / fork checklist

1. Copy [`deploy.config.example.yaml`](../deploy.config.example.yaml) → `deploy.config.yaml`.
2. Set **`warehouse_id`**, **`lakebase_instance_name`** + **`lakebase_database_name`** (or autoscaling `postgres_*` paths), LLM endpoint names, UC catalog/schema, app names.
3. Align [`src/genify/app.yaml`](../src/genify/app.yaml) resource keys with [`scripts/deploy/genify_app_update_resources.py`](../scripts/deploy/genify_app_update_resources.py) (e.g. `sql-warehouse` hyphen for Genify).
4. Profiler uses **`sql_warehouse`** (underscore) in its `app.yaml` — keep consistent with [`scripts/deploy/profiler.sh`](../scripts/deploy/profiler.sh).
5. `databricks auth login --profile <name>` then `./deploy.sh --profile <name>`.

---

## Templates and agent behavior

- Seed templates live under [`src/genify/seed_templates/`](../src/genify/seed_templates/).
- Agent prompts and planning live under [`src/genify/backend/agent/`](../src/genify/backend/agent/).
- **Prompt context size:** character caps for MCP blobs embedded in LLM prompts are configured under **`config.context_truncation`** in [`src/genify/app.yaml`](../src/genify/app.yaml) (`planning_chars_per_key`, `executor_section_chars_per_key`, `prior_yaml_tail_chars`, `interactive_known_data_chars`). Use **`0`** for `prior_yaml_tail_chars` or per-key limits to disable tail/truncation where the helper supports it (`tail_chars` / `truncate_chars` in [`context_text.py`](../src/genify/backend/context_text.py)).

For large template structure changes, consider a dedicated prompt or validation pass in the agent layer.

### Agent progress and SSE

- Prefer **`EventStreamer.trace()`** for verbose / high-frequency updates; user-visible lines belong in the **transcript** via `plan`, `question`, `complete`, etc.
- Any **new SSE event name** must be added to [`src/genify/frontend/src/api.js`](../src/genify/frontend/src/api.js) and documented in [architecture.md](architecture.md#sse-event-types-session-stream).

---

## Library and completed metadata

- **UI routes:** `/library` (list + detail outlet), `/library/:completedId` (deep link). Shell: [`AppShell.jsx`](../src/genify/frontend/src/components/layout/AppShell.jsx), [`AppSidebar.jsx`](../src/genify/frontend/src/components/layout/AppSidebar.jsx).
- **Persistence:** [`backend/db.py`](../src/genify/backend/db.py) `completed_metadata` includes **`table_fqn`** (nullable). Multi-table completion writes a **combined** row (`table_fqn` NULL) plus **per-table** rows; single-table writes one row with `table_fqn` set. Logic: [`core.py`](../src/genify/backend/agent/core.py) `_save_completed`, `_split_yaml_per_table`.
- **API:** `GET/PUT/DELETE /api/completed`, `GET /api/sessions/{id}/completed` — see [architecture.md §6](architecture.md#6-lakebase-data-model-summary).
- **SSE:** `complete` payload may include **`completed_id`** ([`streamer.py`](../src/genify/backend/agent/streamer.py)); resume path re-emits it when loading existing completed rows.
- **Tooltips:** [`HelpHint.jsx`](../src/genify/frontend/src/components/HelpHint.jsx) — prefer for short contextual help on forms and panels.

---

## Documentation

When you add a new integration surface, update:

- [`docs/architecture.md`](architecture.md) if topology changes.
- [`docs/mcp-and-agents.md`](mcp-and-agents.md) for new MCP types or deps.
- [`README.md`](../README.md) or this file for high-level “how to extend” bullets.
- **Agent or SSE contract changes:** [architecture.md](architecture.md#sse-event-types-session-stream) and [CONTRIBUTING.md](../CONTRIBUTING.md).
