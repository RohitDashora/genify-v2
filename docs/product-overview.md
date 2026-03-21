# What is Genify?

**Scope:** Genify is a **demo and reference application**. It is meant for **learning, evaluation, and as a forkable starting point**—not as a supported production service. Operate it only in environments and with data you are comfortable treating as non-production.

Genify is an **AI-assisted metadata generator** for Databricks. It helps teams produce richer **Unity Catalog table comments** and **Genie space**-style metadata from real workspace context—not from guesswork alone.

## Screenshots

**Home** — Select catalog and schema, choose **Table comment** or **Genie space** template, hands-off vs interactive mode, then start a session; **Your sessions** shows status and shortcuts.

![Genify Home](images/screenshot-home.png)

**Library** — Browse completed metadata (**Table comment** / **Genie**, including **Combined** multi-table rows), edit **YAML** or **Markdown**, save, revert, or copy.

![Genify Library](images/screenshot-library.png)

### Session experience (MCP, trace, hands-off vs interactive)

**Hands-off — gather** — Progress shows “Gathering data context via MCP tools…” while **Activity trace** logs `profile_table`, `get_schema`, etc. **Generated YAML** warms up when the first sections stream.

![Hands-off session — MCP gather phase](images/screenshot-session-hands-off-gather.png)

**Hands-off — plan + execute** — Transcript shows the **plan** (sections and strategies); trace includes `Using cached MCP context` and per-section **EXECUTE** lines; YAML fills on the right.

![Hands-off session — plan and YAML streaming](images/screenshot-session-hands-off-execute.png)

**Genie template — gather** — Same pattern for **Genie | Interactive** sessions: MCP tool calls appear in the trace during context gathering.

![Genie session — MCP gather in activity trace](images/screenshot-session-genie-mcp-gather.png)

**Interactive — waiting for user** — Status **Waiting For User**; **PLAN** may mix “Draft, then ask you” steps; **Your answer** composer with suggestions.

![Interactive session — question and composer](images/screenshot-session-interactive-waiting-user.png)

**Interactive — YAML alongside** — Split view: conversation + draft **Generated YAML** while the user refines answers.

![Interactive session — YAML preview while composing](images/screenshot-session-interactive-yaml-compose.png)

**Interactive — complete** — Threaded Q&A through **Step N**; **Show YAML** / copy / download when finished.

![Interactive session — complete with transcript](images/screenshot-session-interactive-complete.png)

## Core ideas

- **Grounded in your data plane** — The agent calls **MCP tools** from the shipped **profiler** and **UC managed** servers—and you can **add your own MCP servers** via `app.yaml` (see [mcp-servers-and-tools.md](mcp-servers-and-tools.md)). Suggestions reflect profiles, lineage, UC comments, and related assets your identity can access.
- **Structured output** — Sessions produce **YAML** aligned to a template (sections, fields, conventions). That YAML is the source of truth; the app can derive **Markdown** for humans or downstream systems.
- **Save and revisit** — Completed runs land in the **Library** (Lakebase), including multi-table sessions where one **combined** artifact and optional **per-table** rows coexist. See [architecture.md §6 — Lakebase data model](architecture.md#6-lakebase-data-model-summary).

## Bring your own template

Templates define *what* metadata looks like (sections, nesting, placeholders). Genify stores them in Lakebase (`genify.templates`) and seeds initial versions from [`src/genify/seed_templates/`](../src/genify/seed_templates/) on first startup.

You can:

- Start from the shipped **table comment** or **Genie-oriented** seed templates.
- **Version** templates over time: clone, edit, and activate via the templates API (see [extending.md — Templates and agent behavior](extending.md#templates-and-agent-behavior) and [`src/genify/README.md`](../src/genify/README.md) for layout).

That lets different teams or use cases keep **different shapes** of metadata without forking the whole app—only the active template and prompts need to stay coherent.

## From catalog to metadata

1. On **Home**, browse the Unity Catalog hierarchy and **select one or more tables** for a session.
2. Launch a session: the agent **gathers** tool context, **plans** how to fill the template, then **executes** section by section (hands-off or interactive clarifications).
3. When complete, open **Library** to review YAML or Markdown, copy, or edit and save.

## Where to read next

| Topic | Doc |
|--------|-----|
| System diagram, agent loop, hands-off vs interactive, SSE, UI map | [architecture.md](architecture.md) |
| Every MCP tool + BYO servers | [mcp-servers-and-tools.md](mcp-servers-and-tools.md) |
| Managed vs custom MCP, `app.yaml`, troubleshooting | [mcp-and-agents.md](mcp-and-agents.md) |
| LLM token limits and context caps | [llm-and-tokens.md](llm-and-tokens.md) |
| UI principles (transcript-first, shell, Library) | [ui-design.md](ui-design.md) |
| Deploy and security | [deploy.md](deploy.md), [security-auth.md](security-auth.md) |
