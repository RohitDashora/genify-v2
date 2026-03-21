# LLM configuration and token budgeting

Genify keeps **model limits and context size** configurable in [`src/genify/app.yaml`](../src/genify/app.yaml) under `config.llm` and `config.context_truncation`. Runtime code loads these via [`get_config()`](../src/genify/backend/config.py); avoid hardcoding limits in Python.

## Main model (`config.llm`)

| Key | Role |
|-----|------|
| `endpoint_name` | Default serving endpoint name (overridden in Apps by `LLM_ENDPOINT_NAME` from `app.yaml` `env`). |
| `max_tokens` | **Output** token cap per chat completion (Databricks / OpenAI-compatible `max_tokens`). |
| `temperature` | Sampling temperature for the main model. |
| `max_prompt_tokens` | **Input** budget passed to [`trim_history()`](../src/genify/backend/llm/token_manager.py) before planner / executor / interactive LLM calls so each request stays within a predictable size. |

### How `trim_history` works

[`token_manager.trim_history`](../src/genify/backend/llm/token_manager.py) uses **tiktoken** (`cl100k_base`) to count tokens. It:

1. Keeps all **system** messages.
2. Keeps the most recent **four** non-system messages.
3. Drops older middle messages until the total is ≤ `max_prompt_tokens`.

Call sites include [`planner.py`](../src/genify/backend/agent/planner.py) and [`executor.py`](../src/genify/backend/agent/executor.py) (each uses `cfg.llm.max_prompt_tokens`).

## Summarizer endpoint

`app.yaml` can also set `summarizer_endpoint_name`, `summarizer_max_tokens`, and `summarizer_temperature` under `config.llm`. These populate [`LLMConfig`](../src/genify/backend/config.py) and [`get_summarizer_llm_client()`](../src/genify/backend/llm/client.py). Deploy scripts bind a second resource (`summarizer-endpoint`) for Apps.

The **current agent loop** uses the **main** client for planning and execution; the summarizer client is **available for extensions** (e.g. future context compression) but is not invoked by the shipped gather/plan/execute path.

## Character caps for embedded context (`config.context_truncation`)

Large MCP blobs are **not** sent whole by default. Under `config.context_truncation`, character limits trim or tail strings when building prompts (planner, executor, interactive questions). Keys:

- `planning_chars_per_key`
- `executor_section_chars_per_key`
- `prior_yaml_tail_chars`
- `interactive_known_data_chars`

Implementation touches [`planner.py`](../src/genify/backend/agent/planner.py), [`executor.py`](../src/genify/backend/agent/executor.py), and [`context_text.py`](../src/genify/backend/context_text.py). Use **`0`** where supported to disable a particular tail/truncation (see [extending.md — Templates and agent behavior](extending.md#templates-and-agent-behavior)).

## Streaming progress to the UI

Token budgeting applies to **LLM requests**. **User-visible progress** is streamed separately as **Server-Sent Events** (`GET /api/sessions/{id}/stream`): status, plan, YAML chunks, questions, completion, and verbose `trace` lines. See [architecture.md §5 — Agent session sequence](architecture.md#5-agent-session-sequence-simplified) and [architecture.md — SSE event types](architecture.md#sse-event-types-session-stream). The browser client is [`api.js` `connectSSE`](../src/genify/frontend/src/api.js).

## Documentation rule of thumb

Only document **`app.yaml` keys that `config.py` reads and code uses.** If you add a new knob, wire it in [`_build_config`](../src/genify/backend/config.py) and consume it in the agent or LLM layer, then mention it here.
