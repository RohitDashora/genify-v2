# Design decisions (ADR-style)

Short rationale for major choices in this reference repo. For full diagrams see [architecture.md](architecture.md).

---

## ADR-1: Lakebase for session and template state

**Decision:** Persist templates, sessions, and completed metadata in **Lakebase** (PostgreSQL), not only in browser or UC volumes.

**Rationale:** Durable resume, multi-user sessions, and versioned templates fit relational storage; Apps inject standard `PG*` env vars when the database is bound as a resource.

**Tradeoff:** Requires Lakebase provisioning and backup/ops like any app database.

---

## ADR-2: SSE for agent progress

**Decision:** Stream agent events to the browser with **Server-Sent Events** over HTTP.

**Rationale:** One-way server→client fits the agent loop; simpler than WebSockets for many proxies and App gateways; native `EventSource` in browsers.

**Tradeoff:** Not full-duplex on a single SSE channel (client uses separate REST calls for answers).

---

## ADR-3: MCP for data plane access

**Decision:** Use **Databricks managed MCP** (UC functions) plus one **custom MCP app** (profiler) instead of ad-hoc REST to arbitrary internal services.

**Rationale:** Aligns with Databricks’ tool-calling model, UC enforcement on managed tools, and a clear pattern for teams to add more servers via config.

**Tradeoff:** Requires correct Python deps (`databricks-mcp`, transitive `databricks-ai-bridge`) and healthy MCP endpoints.

---

## ADR-3b: MCP gather fail-open (no retries)

**Decision:** Each `call_tool` runs **once** per `(table, tool)` **while that cell is missing** from `context_cache`. The agent **merges** prior cells, **skips** existing keys (including error sentinels) on reconnect, and sets **`_mcp_gather_complete: true`** only when every expected cell exists. Failures and MCP error payloads are stored as structured entries; the run **continues**.

**Rationale:** Some tools do not apply to all table types; retrying the same failing call rarely helps. Incremental persistence avoids redoing work after partial gathers or client disconnects.

**Tradeoff:** Planners must tolerate partial context (documented in prompts). Retrying a failed cell requires a new session or cache clear unless a future feature adds explicit invalidation.

---

## ADR-5: Canonical YAML merge for sections

**Decision:** Persist **`generated_yaml`** as one merged document. Section LLM output must use a **single top-level key** matching **`section_key`**. Interactive drafts live in **`pending_section_yaml`** until merged after **`incorporate_answer`**.

**Rationale:** String concatenation duplicated YAML after partial-fill + resume.

**Tradeoff:** Stricter model output; `merge_max_retries` and optional nested strip vs template add config surface.

---

## ADR-4: Imperative `deploy.sh` pipeline

**Decision:** Single shell entrypoint deploys **UC SQL → profiler app → Genify app** in order.

**Rationale:** One command for demos and CI; explicit ordering prevents “Genify before UC functions exist”; works without adopting DABs for the whole monorepo.

**Tradeoff:** Less declarative than a single bundle file; teams may later wrap the same steps in Terraform or DABs.

---

## ADR-5: SDK PATCH for Genify app resources

**Decision:** Update Genify’s **warehouse, serving endpoints, and Lakebase** bindings via **`WorkspaceClient.api_client.do("PATCH", ...)`** in [`scripts/deploy/genify_app_update_resources.py`](../scripts/deploy/genify_app_update_resources.py).

**Rationale:** Some CLI versions reject certain JSON fields for Lakebase (`postgres` vs `database`); the REST API accepts the payload; SDK works across `databricks-sdk` versions used locally.

**Tradeoff:** Extra Python dependency for deploy preflight (`scripts/deploy/requirements.txt`).

---

## ADR-6: Distinct resource keys for Genify vs profiler

**Decision:** Genify `app.yaml` uses **`sql-warehouse`** (hyphen); profiler uses **`sql_warehouse`** (underscore), matching each app’s `valueFrom` and deploy JSON.

**Rationale:** Historical/API consistency per app; deploy scripts encode the correct shape per target.

**Tradeoff:** Copy-paste between apps can confuse — documented in [deploy.md](deploy.md).

---

## ADR-7: Milestone timeline vs activity trace (SSE)

**Decision (historical):** Split session UX into two channels on the same SSE connection: a **sparse milestone** list and a dedicated **`trace`** event stream for verbose lines.

**Update:** The primary surface is now a **conversation transcript** (ADR-9). ADR-7’s split still applies to **transcript vs trace**: verbose diagnostics stay in the trace panel, not the main thread.

---

## ADR-9: Transcript-first session UI

**Decision:** The session page uses a **transcript** (assistant / user / system messages), humanized **plan** copy, a **working** state with `status` / `thinking` subtitles, **Activity trace** collapsed by default, **hydration** from `GET /api/sessions/{id}` (`conversation`), and a **non-fatal banner** for `POST .../answer` when the session returns **409** with `code: not_waiting_for_user`.

**Rationale:** Non-technical users need a chat-like mental model; operators still get a copyable trace; resume must not look “empty” before SSE catches up.

**Tradeoff:** More client state (dedupe on `question`, stream reconnect after answer); document single-tab use to avoid concurrent `run_agent` instances.

---

## ADR-10: Interactive resume — answer queue and `pending_question`

**Decision:** (1) **`POST /api/sessions/{id}/answer`** appends the user message but keeps **`status = waiting_for_user`** until the next **`run_agent`** run executes **`incorporate_answer`** and **`_save_step_progress`** (then `executing` and incremented `current_step`). (2) If the last `conversation` message is already **`user`**, return **409** with **`answer_already_queued`**. (3) Persist **`pending_question`** (JSONB) when pausing so **`GET /sessions/{id}`** and a **reconnecting SSE** can restore the same `question` event **without** calling **`execute_step`** again.

**Rationale:** Setting `executing` on POST previously skipped the incorporate branch (snapshot `status`), so the same plan index re-ran and looked like an infinite loop. Queued-answer guard avoids stacked user messages before the stream consumes them. `pending_question` fixes refresh/reconnect duplicate LLM and empty composer.

**Tradeoff:** Extra column and client hydration logic; still recommend single-tab until a server-side session lock exists.

---

## ADR-11: Interactive pause — composer draft and SSE lifecycle

**Decision:** (1) After handling an SSE **`question`** event, the **client closes** the `EventSource` so the browser does not **auto-reconnect** while the user is typing. (2) Treat **`question`** payloads with the same **`section` + `field` + `question`** text as the **same pause**: merge into state (e.g. refresh **`suggested_answer`**) but **do not** clear the composer draft or append a duplicate assistant transcript line. (3) Seed the same pause key when hydrating from **`pending_question`** on **`GET /sessions/{id}`** so the first stream replay matches. (4) On **`EventSource` `open`**, skip flipping to “working” when a question is **already** shown (refresh / deep link). (5) Clear the pause key after a successful **`POST …/answer`**; the next execution segment opens a **new** SSE stream as today.

**Rationale:** Native `EventSource` reconnect after the HTTP response ends plus the server’s **`reconnect_question_only`** replay would otherwise fire **`question`** repeatedly and wipe a controlled textarea; suggestion chips should update without destroying in-progress text.

**Tradeoff:** While paused, there is **no** live SSE until the user answers and the client opens a new stream—acceptable because the pause is user-bound.

---

## ADR-8: Canonical MCP context dict in sessions

**Decision:** Store `context_cache` as a dict with **metadata keys (`_` prefix)** plus **`catalog.schema.table` → { tool: result }**, never flattening to a single table’s inner map at the top level.

**Primary metadata:** **`_mcp_tool_manifest`** — structured list from MCP discovery (full `inputSchema`, server, `callable` / `source`) plus optional `app.yaml` `mcp_tool_overrides`. **`_mcp_gather_complete`** — boolean; when `true`, gather is skipped on subsequent streams unless the cache is cleared or session scope changes (if `table_ref` ever becomes mutable, invalidate completion). **Legacy:** `_tool_descriptions` string (planner still accepts old caches).

**Rationale:** The planner and executor expect metadata keys (`_`) and FQN keys; flattening broke saves when metadata was the first key. The manifest gives the planning LLM exact tool names and schemas without maintaining a duplicate registry in YAML.

**Tradeoff:** Slightly more nesting in prompts; summarization already stringifies per FQN key.

---

## Optional future: MCP-less graceful path

A planned UX improvement when **no MCP tools** succeed is sketched in [`archive/graceful-degradation.plan.md`](archive/graceful-degradation.plan.md) (short user description → single LLM YAML). Not implemented in application code unless that plan is executed.
