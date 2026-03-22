# Contributing

Thanks for helping improve this **demo / reference** repository. Changes should preserve the expectation that this is **not** a production-supported product—see the README and [docs/product-overview.md](docs/product-overview.md).

## Documentation

- User-facing docs live under **[docs/](docs/)** — update **[docs/README.md](docs/README.md)** if you add a new guide or change the recommended reading order.
- **Product / UX copy:** **[docs/product-overview.md](docs/product-overview.md)** and **[docs/ui-design.md](docs/ui-design.md)**. UI screenshot assets: **[docs/images/README.md](docs/images/README.md)** (replace PNGs in place; keep filenames stable).
- **LLM limits:** document new `app.yaml` keys in **[docs/llm-and-tokens.md](docs/llm-and-tokens.md)** only if **[src/genify/backend/config.py](src/genify/backend/config.py)** loads them and code consumes them—avoid documenting “dead” YAML.
- **New MCP tools or servers:** update **[docs/mcp-servers-and-tools.md](docs/mcp-servers-and-tools.md)** and, if wiring or gather behavior changes, **[docs/mcp-and-agents.md](docs/mcp-and-agents.md)** / **[docs/architecture.md](docs/architecture.md)**.
- Architecture or MCP topology changes should include an update to **[docs/architecture.md](docs/architecture.md)** (including **§0 Three pillars** when the split of responsibilities changes) or **[docs/mcp-and-agents.md](docs/mcp-and-agents.md)** (Mermaid diagrams render on GitHub).
- **Agent loop, SSE events, or session UI:** update **[docs/architecture.md](docs/architecture.md)** (especially [SSE event types](docs/architecture.md#sse-event-types-session-stream)) and, if behavior or persistence changes, **[docs/mcp-and-agents.md](docs/mcp-and-agents.md)** or **[docs/design-decisions.md](docs/design-decisions.md)**.
- Keep **[README.md](README.md)** short; prefer linking to `docs/` for depth.

## Code changes

- **Genify backend/frontend:** follow existing layout under `src/genify/`.
- **Deploy scripts:** changes in `scripts/deploy/` should be reflected in **[docs/deploy.md](docs/deploy.md)** if behavior or prerequisites change.
- **UC functions:** preserve numeric ordering in `uc_functions/` filenames; document new functions in **mcp-and-agents** or **extending** if they affect managed MCP tools.

## Local checks (suggested)

**Python 3.12** (or 3.11) is recommended; **3.14** may fail to install some wheels (e.g. `pyarrow` / ML stack).

### Tests (dedicated venv)

```bash
# From repository root — creates .venv-test/ (gitignored)
./scripts/setup_test_venv.sh
./scripts/run_tests.sh
```

See [tests/README.md](tests/README.md) for pytest vs unittest and `PYTHON=…` overrides.

### Full dev venv (optional)

```bash
python3.12 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r src/genify/requirements.txt

python -c "from databricks_mcp import DatabricksMCPClient; print('ok')"

# Frontend
cd src/genify/frontend && npm install && npm run build
```

## Pull requests

- Describe **workspace impact** (e.g. new env vars, new deploy config keys).
- If you change `app.yaml` resource names, call out **Genify vs profiler** naming (`sql-warehouse` vs `sql_warehouse`).

## Questions

Open a discussion or issue in your team’s process; for Databricks product behavior, prefer official docs linked from **[docs/README.md](docs/README.md)**.
