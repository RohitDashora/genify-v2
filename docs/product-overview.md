# Genify — product overview

**Demo / reference** — Genify is a Databricks App that runs an **agent loop** over your Unity Catalog tables: **gather** context via MCP tools, **plan** with an LLM, **execute** template sections, stream progress over **SSE**, and persist results in **Lakebase**. The UI includes a persistent **demo banner**; treat security, cost, and governance as your responsibility when you fork or deploy beyond a lab.

## What you can do

- **Browse** catalogs and schemas, **select** one or more tables, and **start a session** (Table comment or Genie Space template; **hands-off** or **interactive** mode).
- **Watch** gather → plan → section execution with an optional **Activity trace** (verbose MCP/LLM diagnostics).
- **Answer** targeted questions in **interactive** mode; the transcript stays primary; trace stays secondary.
- **Save** completed metadata to the **Library** (YAML source, Markdown derived), and **edit** later.
- **Own templates** under **Templates**: versioned YAML (`_meta` + `sections`), default version, upload/copy/save as new version.

## Primary surfaces and routes

Routes are defined in [`src/genify/frontend/src/App.jsx`](../src/genify/frontend/src/App.jsx).

| Surface | Route(s) | Role |
|---------|----------|------|
| **Home** | `/` | Catalog/schema pickers, **Select Tables**, session launcher, **Your Sessions** |
| **Session** | `/session/:id` | Transcript, plan/progress, optional YAML panel, Activity trace, interactive composer when paused |
| **Library** | `/library`, `/library/:completedId` | Saved **completed_metadata** rows: search, type filters, sort; detail editor (YAML \| Markdown) |
| **Templates** | `/templates`, `/templates/new`, `/templates/:templateId` | List templates, create/edit version, set default |

Backend APIs are under `/api/*` (sessions, completed metadata, templates, catalog). See [architecture.md](architecture.md) for the full stack.

## Typical flows

1. **Home** — Pick catalog/schema → select table(s) → choose template type and mode → **Start**. Open an existing row from **Your Sessions** to resume.
2. **Agent run** — SSE connects; MCP tools **incrementally** populate **`context_cache`** (merge, skip cached cells, **`_mcp_gather_complete`** when done); the LLM **plans** sections; each section **executes** (hands-off runs through; interactive may **pause** with a `question`).
3. **Complete** — Final YAML is merged and saved; **Open in Library** uses `completed_id` from the `complete` event when present.
4. **Library** — Find a card, edit YAML, **Save** (server regenerates Markdown).
5. **Templates** — Adjust template YAML for your org; activate/default as needed for new sessions.

<a id="session-experience-mcp-trace-hands-off-vs-interactive"></a>

## Session experience: MCP, trace, hands-off vs interactive

- **Hands-off** — The agent fills sections from gathered context; unknowns may appear as `NEEDS_CLARIFICATION` in YAML. One continuous stream from gather through **Complete** (subject to network/proxy limits).
- **Interactive** — The planner may use strategies that **pause** for your input. On a **question**, the client closes SSE while you compose an answer; you **POST** `/api/sessions/{id}/answer` and open a **new** stream to continue. The **Activity trace** shows MCP tool names, cache hints, and merge/LLM phases—use it for debugging, not as the main narrative (see [ADR-9](design-decisions.md#adr-9-transcript-first-session-ui)).
- **MCP gather** — Runs until **`_mcp_gather_complete`**; partial caches **resume** after reconnect. Failures are stored and the run continues (**fail-open**). Details: [agentic-loop.md](agentic-loop.md), [mcp-and-agents.md](mcp-and-agents.md).

Full UX principles and component map: **[ui-design.md](ui-design.md)**.

<a id="screenshots"></a>

## Screenshots

Assets live under [`images/`](images/). Full inventory: **[images/README.md](images/README.md)**. Detailed UI walkthrough: **[ui-design.md](ui-design.md)**.

**Home** — catalog, **Select Tables**, session launcher, **Your Sessions**.

![Home — catalog, template type, sessions](images/screenshot-home.png)

**Select Tables** — filter, bulk select, table type pill.

![Select Tables](images/screenshot-home-select-tables.png)

**Library** — saved metadata (YAML and Markdown).

![Library — YAML](images/screenshot-library.png)

![Library — Markdown](images/screenshot-library-markdown.png)

**Templates** — versioned template YAML.

![Templates](images/screenshot-templates.png)

**Session (interactive complete, transcript-first)** — AGENT / YOU rounds and footer actions.

![Interactive session complete](images/screenshot-session-interactive-complete-transcript.png)

## Where to read next

| Doc | Focus |
|-----|--------|
| [architecture.md](architecture.md) | System context, MCP topology, deploy, SSE, Lakebase |
| [agentic-loop.md](agentic-loop.md) | Loop concept + `run_agent` gather/plan/execute, cache rules |
| [ui-design.md](ui-design.md) | Transcript-first UI, shell, screenshots |
| [deploy.md](deploy.md) | `deploy.sh`, `deploy.config.yaml` |
