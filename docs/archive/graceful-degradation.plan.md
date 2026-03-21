# Graceful degradation when no MCP tools are available

> **Archived** from repo root (2026). Not implemented unless explicitly picked up. Summary: [design-decisions.md](../design-decisions.md).

## Overview

When `_gather_context` returns empty (no MCP servers connected or all tool calls failed), skip the full plan/execute loop. Instead, ask the user for one brief table description, generate YAML in a single LLM call, and finalize.

## Files to change (2)

### 1. `src/genify/backend/agent/core.py` (~50 lines)

- After line 75 (after `_gather_context` + `_save_context_cache`), add a check: `if _no_tool_data(context):` — enter fallback path.
- **Fallback first visit** (context just gathered, empty):
  - Emit `streamer.status("fallback", "No data tools available...")`.
  - Emit `streamer.question(section="core_description", ...)` asking for one table description.
  - Call `_save_waiting_state(pool, session_id, 0, "", [assistant message])`.
  - `return` (end the generator — frontend shows the question input).
- **Fallback resume** (detect at the top of `run_agent`, when `status == "waiting_for_user"` and `context_cache == {}`):
  - Extract user's description from `conversation[-1]["content"]`.
  - Call `_fallback_generate(template, user_description, session, llm)` — single LLM call — full YAML.
  - `yaml_to_markdown` → `_save_completed` → `_update_session_status("complete")` → emit `streamer.complete`.
  - `return`.
- New helper: `_no_tool_data(context)` — returns `True` if context has no keys that don't start with `_`.
- New helper: `_fallback_generate(template, description, session, llm)` — builds one prompt from the template + description, calls LLM, returns YAML string.

### 2. `src/genify/backend/agent/prompts.py` (~15 lines)

- Add one new constant `FALLBACK_GENERATION_PROMPT` used by `_fallback_generate`:

> "Here is a YAML template for a {template_type}. The user described this table as: {description}. Fill every section using only this description. For fields you cannot determine, write `NEEDS_CLARIFICATION: <reason>`. Output valid YAML only."

## Files NOT changed

| File | Why untouched |
|------|---------------|
| `executor.py` | Fallback skips the plan/execute loop entirely |
| `planner.py` | Fallback skips planning entirely |
| `streamer.py` | Reuses existing `status`, `question`, `complete` events |
| `sessions.py` (routes) | `/answer` endpoint already handles `waiting_for_user` → `executing` transition |
| `SessionView.jsx` (frontend) | Already renders `status`, `question`, `complete` events + answer input |
| DB schema | `context_cache = {}` is the fallback signal — no new columns |

## Detection logic

```python
def _no_tool_data(context: dict) -> bool:
    return not any(k for k in context if not k.startswith("_"))
```

Covers: (a) `_gather_context` returned `{}` (connect failed), (b) returned only `_tool_descriptions` (connected but all tool calls failed).

## Insertion point in `run_agent`

After line 75 (existing context gathering block), before line 78 (plan generation):

```
[line 68-75: existing gather context + save + emit thinking events]
>>> NEW: fallback check here
[line 78+: plan generation, execution loop]
```

On resume, the check goes at the top of `run_agent` before the normal resume path (line 100-129).

## User experience

- **Today (no tools):** full multi-section loop, 5-8 LLM calls producing hollow YAML with `NEEDS_CLARIFICATION` everywhere. Slow, confusing.
- **After:** one question → one answer → one LLM call → done. Fast, honest.

## Todos

1. Add `FALLBACK_GENERATION_PROMPT` to `prompts.py`
2. Add `_no_tool_data`, `_fallback_generate` helpers to `core.py`
3. Add fallback branch (first visit) in `run_agent` after context gathering
4. Add fallback resume path in `run_agent` for `waiting_for_user` + empty context
