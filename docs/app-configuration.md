# App configuration (`app.yaml`)

Genify reads runtime settings from **`src/genify/app.yaml`**. The FastAPI backend loads the nested **`config:`** object via [`get_config()`](../src/genify/backend/config.py) (`backend.config`). **Do not hardcode** these values in Python call sites; use `get_config()` (see project rules).

Databricks Apps also use sibling keys at the **root** of the same file (`name`, `command`, `env`, …) for deployment; only **`config:`** is documented here as application settings.

---

## Loading and overrides

| Mechanism | Behavior |
|-----------|----------|
| **File** | `Path(__file__).parent.parent / "app.yaml"` from `backend/config.py` (i.e. `src/genify/app.yaml`). |
| **Singleton** | `get_config()` is `@lru_cache` — one process loads once. |
| **Environment variables** | `LLM_ENDPOINT_NAME` and `SUMMARIZER_ENDPOINT_NAME` override the corresponding `llm.*` endpoint names if set. |
| **Missing file** | Warning in logs; `config` falls back to dataclass defaults in code. |

---

## `config.llm`

Main and summarizer LLM endpoints (Databricks Foundation Model / serving).

| Key | Type | Default (if omitted) | Usage |
|-----|------|----------------------|--------|
| `endpoint_name` | string | `databricks-gpt-5-2` | Primary model for planner, executor, merge retries. Overridden by **`LLM_ENDPOINT_NAME`**. |
| `max_tokens` | int | `4000` | Max **output** tokens per chat completion for the main LLM. |
| `temperature` | float | `0.7` | Sampling temperature for the main LLM. |
| `max_prompt_tokens` | int | `20000` | **Input** budget for `trim_history` and similar trimming — do not hardcode elsewhere. |
| `summarizer_endpoint_name` | string | `databricks-gemini-2-5-flash` | Secondary client from `get_summarizer_llm_client()`. Overridden by **`SUMMARIZER_ENDPOINT_NAME`**. |
| `summarizer_max_tokens` | int | `12000` | Max output tokens for the summarizer client. |
| `summarizer_temperature` | float | `0.3` | Temperature for the summarizer client. |

**Note:** The default agent loop uses the **main** endpoint; the summarizer is available for features that call `get_summarizer_llm_client()` (see [llm-and-tokens.md](llm-and-tokens.md)).

---

## `config.lakebase`

PostgreSQL (Lakebase) connectivity for sessions, templates, and Library metadata.

| Key | Type | Default | Usage |
|-----|------|---------|--------|
| `enabled` | bool | `true` | When `false`, app behavior depends on call sites (typically degraded or startup checks). |
| `schema` | string | `genify` | Postgres schema name for Genify tables. Loaded as `LakebaseConfig.schema_name`. |
| `pool_size` | int | `5` | Connection pool size for `psycopg`. |

Bindings (`PGHOST`, `PGUSER`, etc.) come from the Databricks App resource attachment, not from this block.

---

## `config.context_truncation`

**Character caps** for text sliced into LLM prompts (MCP context, prior YAML tail, interactive “known data”). These limit **prompt size**, not MCP gather completeness. Use **`0`** where the code path treats zero as “no limit” (see [llm-and-tokens.md](llm-and-tokens.md)).

| Key | Type | Default | Usage |
|-----|------|---------|--------|
| `planning_chars_per_key` | int | `2000` | Max characters **per MCP context key** in the **planner** prompt. |
| `executor_section_chars_per_key` | int | `2000` | Max characters **per key** in the **executor** section context blob. |
| `prior_yaml_tail_chars` | int | `3000` | Tail of **prior merged YAML** shown during section generation / incorporate. |
| `interactive_known_data_chars` | int | `2000` | Prefix cap for **known_data** in interactive question flows. |

---

## `config.yaml_merge`

Section merge policy, optional JSONB dual-write, and **canonical YAML formatting** at persistence boundaries ([ADR-5](design-decisions.md#adr-5-canonical-yaml-merge-for-sections), [agentic-loop.md](agentic-loop.md)).

| Key | Type | Default | Usage |
|-----|------|---------|--------|
| `merge_max_retries` | int | `2` | LLM retries when merge of a section fragment into merged YAML fails (not MCP retries). |
| `nested_validation` | string | `strip` | `off` — accept fragment structure as-is. `strip` — remove keys under a section that are not in the template subtree (see `yaml_merge.merge_section_fragment`). |
| `canonical_json_enabled` | bool | `false` | When `true`, session **`generated_json`** (JSONB) is updated from parsed merged YAML alongside YAML persistence. |
| `format_on_persist_enabled` | bool | `false` | When `true`, **parse → re-dump** merged YAML before saving to sessions, Library drafts, merge-error paths, finalize, and **`PUT /api/completed/{id}`**. Fail-open on invalid YAML. |
| `format_dump_width` | int | `120` | PyYAML **`width`** when formatting is enabled (line wrapping for long scalars). |
| `format_multiline_literals` | bool | `false` | When `true`, strings containing newlines serialize as literal block **`|`** for readability. |

**Not formatted as one document:** concatenation of committed **`generated_yaml`** + **`pending_section_yaml`** for preview; only the **committed** half is formatted before concat for Library upserts.

---

## `config.mcp_servers`

List of MCP server definitions passed to **`MCPRegistry`** (see [architecture.md](architecture.md), [mcp-and-agents.md](mcp-and-agents.md)).

Each item:

| Key | Required when | Usage |
|-----|----------------|--------|
| `name` | always | Logical id (e.g. `profiler`, `uc-functions`). |
| `type` | always | `databricks_app` — MCP served by another Databricks App; `uc_managed` — Unity Catalog managed MCP. |
| `app_name` | `type: databricks_app` | Target app name for URL resolution. |
| `uc_catalog` | `type: uc_managed` | UC catalog for managed MCP. |
| `uc_schema` | `type: uc_managed` | UC schema for managed MCP. |
| `url` | optional | If non-empty, used as MCP base URL (skips SDK resolution). |

---

## `config.mcp_tool_overrides`

Planner / gather manifest tweaks. Tool **names** must match the internal convention used in the manifest (often `catalog__schema__function_name` style for UC tools).

| Key | Type | Usage |
|-----|------|--------|
| `tool_hints` | map string → string | Optional **hints** keyed by tool name; consumed when building planner-facing tool descriptions. |
| `hidden_tools` | list of strings | Tools **omitted** from manifest and **auto-gather** (still can exist on server). |
| `extra_tools` | list of objects | Planner-only rows; each object should include at least **`name`** (and fields expected by manifest builder). Invalid entries are skipped with a warning. |

If a name appears in both **`tool_hints`** and **`hidden_tools`**, **hidden wins** (warning logged). **`extra_tools`** entries whose `name` is hidden are dropped at manifest build (warning logged).

---

## Quick reference: `get_config()` shape

```text
get_config().llm.*
get_config().lakebase.*
get_config().context_truncation.*
get_config().yaml_merge.*
get_config().mcp_servers          # tuple of MCPServerConfig
get_config().mcp_tool_overrides  # tool_hints, hidden_tools, extra_tools
```

---

## Related documentation

- [llm-and-tokens.md](llm-and-tokens.md) — token budgets, trimming, summarizer note.
- [mcp-servers-and-tools.md](mcp-servers-and-tools.md) — tool inventory and `hidden_tools` examples.
- [agentic-loop.md](agentic-loop.md) — where YAML merge and format-on-persist run in `run_agent`.
- [deploy.md](deploy.md) — deploy pipeline; App resource bindings are separate from `config:`.
