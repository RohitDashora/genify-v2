# Genify documentation

**Demo / reference only** — not intended for production deployments without your own hardening, support model, and compliance review.

This documentation describes a **reference LLM agent on Databricks Apps** that combines **Databricks managed MCP** (Unity Catalog functions), a **custom MCP app** (table profiler), **Lakebase** (PostgreSQL), and **Foundation Model serving**.

## Who this is for

- Teams building **agents** that need governed access to Unity Catalog data via MCP.
- Anyone **forking** this repo to adapt templates, MCP servers, or deploy layout.

## Reading order (~25 minutes)

1. **[product-overview.md](product-overview.md)** — What Genify is, templates, catalog → Library flow.
2. **[architecture.md](architecture.md)** — **§0 Three pillars**, system context, MCP topology, deploy flow, agent sequence, **SSE** (including `complete.completed_id`), **shell + Library UI**, **`completed_metadata` / `table_fqn`** (Mermaid diagrams). [ui-design.md](ui-design.md) summarizes session UX principles.
3. **[agentic-loop.md](agentic-loop.md)** — **What** the agentic loop is (architecture & design), then **how** Genify implements it: `run_agent` phases, cache rules, planner vs executor, code map, invariants.
4. **[mcp-and-agents.md](mcp-and-agents.md)** — Managed vs custom MCP, `app.yaml`, UC SQL functions, Python dependencies, BYO servers (overview).
5. **[mcp-servers-and-tools.md](mcp-servers-and-tools.md)** — Inventory of every shipped tool; `hidden_tools`; bring-your-own MCP checklist.
6. **[llm-and-tokens.md](llm-and-tokens.md)** — `max_prompt_tokens`, `trim_history`, `context_truncation`, cost heuristics; **summarizer endpoint is configured but not used by the default agent path**; SSE vs LLM limits.
7. **[deploy.md](deploy.md)** — Prerequisites, `deploy.config.yaml`, `./deploy.sh`, troubleshooting.
8. **[security-auth.md](security-auth.md)** — Service principals, resource bindings, secrets, UC permissions.
9. **[extending.md](extending.md)** — Add MCP servers, UC functions, new workspaces.
10. **[design-decisions.md](design-decisions.md)** — Short ADR-style rationale (see ADR index at top of file).
11. **[public-repo-checklist.md](public-repo-checklist.md)** — Before open-sourcing or publishing a fork: secrets, hygiene script, license headers.

## Repository map

| Area | Path |
|------|------|
| Main app (FastAPI + React) | [`src/genify/`](../src/genify/) |
| Custom profiler MCP app | [`src/mcp-profiler/`](../src/mcp-profiler/) |
| UC function definitions | [`uc_functions/`](../uc_functions/) |
| Python tests | [`tests/`](../tests/) — [README](../tests/README.md), `./scripts/setup_test_venv.sh` |
| Deploy orchestration | [`deploy.sh`](../deploy.sh), [`scripts/deploy/`](../scripts/deploy/) |
| UI screenshots (README + docs) | [`images/`](images/) — Home, Select Tables, **Templates**, Library, session flows; see [`images/README.md`](images/README.md); refresh when UI changes materially |
| MCP tool reference | [mcp-servers-and-tools.md](mcp-servers-and-tools.md) |

## External references

- [Use Databricks managed MCP servers](https://docs.databricks.com/gcp/en/generative-ai/mcp/managed-mcp) (URL patterns, authentication concepts)
- [Databricks Apps](https://docs.databricks.com/en/dev-tools/databricks-apps/index.html)

## Contributing and security

See [CONTRIBUTING.md](../CONTRIBUTING.md) in the repo root. Security disclosures: [SECURITY.md](../SECURITY.md). License: [LICENSE](../LICENSE). **Before making the repository public**, follow item **11** above and run `./scripts/check_repo_hygiene.sh`.
