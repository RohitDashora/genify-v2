"""Agent core — the main orchestrator that runs the full agent loop.

Called from routes/sessions.py when the SSE stream is opened.
Handles: context gathering, planning, execution, pause/resume, finalization.
"""
import asyncio
import copy
import json
import logging
from collections.abc import AsyncGenerator
from typing import Any

import yaml
from psycopg.rows import dict_row

from backend.agent.executor import execute_step, incorporate_answer, merge_section_output
from backend.agent.yaml_merge import format_yaml_for_persistence, load_yaml_document
from backend.agent.planner import generate_plan
from backend.agent.streamer import TRACE_DETAIL_MAX, EventStreamer
from backend.config import get_config
from backend.artifact_status import (
    ARTIFACT_COMPLETE,
    ARTIFACT_FAILED,
    ARTIFACT_IN_PROGRESS,
    ARTIFACT_MERGE_ERROR,
)
from backend.db import SCHEMA
from backend.llm.client import get_main_llm_client
from backend.llm.output_converter import safe_yaml_to_markdown
from backend.mcp.registry import MCPRegistry
from backend.mcp.tool_manifest import build_tool_manifest, tools_for_auto_gather

logger = logging.getLogger(__name__)

_MCP_GATHER_COMPLETE_KEY = "_mcp_gather_complete"

_USER_AGENT_FAIL = (
    "Something went wrong. You can retry the section or restart the session, "
    "or open the Library to edit your saved YAML."
)
_MERGE_FAIL_USER = (
    "We couldn't merge the latest section. Your previous YAML is saved in the Library—"
    "you can retry the section or restart the session."
)
_MD_EXPORT_HINT = (
    "Markdown preview had an issue. Your YAML was saved—you can edit it in the Library to refresh markdown."
)

# Serialize MCP gather per session so concurrent GET /stream handlers do not each run a full tool storm.
# Double-check context_cache after acquire (follower reloads DB and skips gather if leader finished).
# Single process only; multiple Uvicorn workers need DB advisory lock or workers=1.
_session_mcp_gather_locks: dict[str, asyncio.Lock] = {}
_session_mcp_gather_locks_mutex = asyncio.Lock()


def _format_yaml_for_session_persistence(
    yaml_str: str,
    streamer: EventStreamer | None,
    *,
    phase: str,
    trace_if_disabled: bool = False,
) -> tuple[str, list[dict]]:
    """Re-dump merged YAML before persistence when enabled. Fail-open; trace for apply / parse fail."""
    cfg = get_config().yaml_merge
    events: list[dict] = []
    if not cfg.format_on_persist_enabled:
        if streamer and trace_if_disabled:
            events.append(
                streamer.trace(
                    "system",
                    "YAML format on persist skipped (disabled)",
                    phase=phase,
                )
            )
        return yaml_str, events
    out, changed, parse_ok = format_yaml_for_persistence(
        yaml_str,
        enabled=True,
        dump_width=cfg.format_dump_width,
        use_literal_blocks=cfg.format_multiline_literals,
    )
    if streamer:
        if changed:
            events.append(
                streamer.trace(
                    "system",
                    "Canonical YAML format applied before persistence",
                    phase=phase,
                )
            )
        elif not parse_ok and (yaml_str or "").strip():
            events.append(
                streamer.trace(
                    "system",
                    "YAML format on persist failed (invalid YAML); keeping original text",
                    phase=phase,
                )
            )
    return out, events


def _format_committed_yaml_for_library_preview(committed: str) -> str:
    """Format only the committed merged document; never parse committed+pending concat."""
    cfg = get_config().yaml_merge
    out, _, _ = format_yaml_for_persistence(
        committed,
        enabled=cfg.format_on_persist_enabled,
        dump_width=cfg.format_dump_width,
        use_literal_blocks=cfg.format_multiline_literals,
    )
    return out


async def _get_session_mcp_gather_lock(session_id: str) -> asyncio.Lock:
    async with _session_mcp_gather_locks_mutex:
        lock = _session_mcp_gather_locks.get(session_id)
        if lock is None:
            lock = asyncio.Lock()
            _session_mcp_gather_locks[session_id] = lock
        return lock


def _mcp_needs_gather(context: dict) -> bool:
    """True if we should run MCP gather (empty cache or incremental gather not finished)."""
    if not context:
        return True
    return not bool(context.get(_MCP_GATHER_COMPLETE_KEY))


def _seed_merged_table_context(raw: dict) -> dict:
    """Copy per-table entries from an existing context_cache (exclude top-level metadata keys)."""
    out: dict[str, Any] = {}
    for k, v in raw.items():
        if k.startswith("_"):
            continue
        if isinstance(v, dict):
            out[k] = copy.deepcopy(v)
        else:
            out[k] = v
    return out


async def run_agent(session_id: str, pool) -> AsyncGenerator[dict, None]:
    """Full agent loop — yields SSE events.

    Flow:
    1. Load session from Lakebase
    2. Load template from Lakebase
    3. Gather context via MCP tools (cached in session)
    4. Generate plan via LLM (cached in session)
    5. Execute plan steps, streaming events
    6. If interactive + needs input: emit question, set waiting_for_user, return
    7. On resume: pick up from current_step with user's answer
    8. Finalize: save completed metadata
    """
    streamer = EventStreamer()

    try:
        # 1. Load session
        session = _load_session(pool, session_id)
        if not session:
            yield streamer.error("not_found", "Session not found")
            return

        status = session["status"]

        # Handle terminal states
        if status == "complete":
            existing_id = _find_completed_id(pool, session_id, session["user_email"])
            yield streamer.complete(session["generated_yaml"], session_id, completed_id=existing_id)
            return
        if status == "failed":
            msg = session.get("error_message") or "This session stopped with an error."
            code = session.get("error_code") or "failed"
            yield streamer.error(code, msg)
            return

        yield streamer.status("loading", "Loading session and template...")

        # 2. Load template
        template_yaml = _load_template(pool, session["template_type"], session["template_version"])
        if not template_yaml:
            yield streamer.error("template_not_found", "Active template not found")
            _update_session_status(
                pool,
                session_id,
                "failed",
                error="Template not found",
                error_code="template_not_found",
            )
            return

        template = yaml.safe_load(template_yaml)

        # Resume hint (avoid noise on brand-new sessions)
        if _should_emit_session_resumed(session):
            yield streamer.trace(
                "system",
                "Session resumed",
                phase="system",
            )

        # 3. Gather context via MCP tools (serialized per session for concurrent /stream)
        context = _normalize_context_cache(session.get("context_cache"))
        if _mcp_needs_gather(context):
            gather_lock = await _get_session_mcp_gather_lock(session_id)
            if gather_lock.locked():
                yield streamer.trace(
                    "system",
                    "Waiting for MCP context gather from another connection…",
                    phase="gather",
                )
            async with gather_lock:
                session = _load_session(pool, session_id)
                if not session:
                    yield streamer.error("not_found", "Session not found")
                    return
                context = _normalize_context_cache(session.get("context_cache"))
                if _mcp_needs_gather(context):
                    yield streamer.status(
                        "gathering_context",
                        "Gathering data context via MCP tools...",
                    )
                    out: dict[str, Any] = {}
                    async for evt in _iter_gather_context_events(
                        session, streamer, out, pool, session_id
                    ):
                        yield evt
                    gathered = out.get("context")
                    if isinstance(gathered, dict) and gathered:
                        context = gathered
                    else:
                        session = _load_session(pool, session_id)
                        context = (
                            _normalize_context_cache(session.get("context_cache"))
                            if session
                            else {}
                        )
                        if not context:
                            logger.info(
                                "MCP gather did not persist context_cache (empty or incomplete) "
                                "for session %s",
                                session_id,
                            )
                else:
                    logger.info(
                        "MCP gather skipped for session %s — context populated while waiting (parallel stream)",
                        session_id,
                    )
                    yield streamer.trace(
                        "system",
                        "Using cached MCP context (another connection finished gather)",
                        phase="gather",
                    )
        else:
            yield streamer.trace(
                "system",
                "Using cached MCP context",
                phase="gather",
            )

        status = session.get("status")

        # 4. Generate plan
        conversation = session.get("conversation") or []
        reconnect_question_only = (
            status == "waiting_for_user"
            and session.get("pending_question")
            and conversation
            and isinstance(conversation[-1], dict)
            and conversation[-1].get("role") == "assistant"
        )

        plan = session.get("plan")
        if not plan:
            yield streamer.status("planning", "Analyzing template and creating a plan...")
            llm = get_main_llm_client()
            trace_buf: list[dict] = []
            plan = await generate_plan(
                template,
                context,
                session["mode"],
                llm,
                streamer=streamer,
                trace_out=trace_buf,
            )
            for ev in trace_buf:
                yield ev
            _save_plan(pool, session_id, plan)
        elif not reconnect_question_only:
            yield streamer.trace(
                "system",
                "Using cached plan",
                phase="plan",
            )

        # Avoid re-emitting plan on reconnect while waiting (reduces duplicate transcript rows).
        if not reconnect_question_only:
            total_steps = len(plan)
            yield streamer.plan(
                steps=plan,
                total_sections=total_steps,
                estimated_time=f"~{total_steps} minutes",
            )

        # 5. Execute plan from current_step
        current_step = session.get("current_step", 0)
        llm = get_main_llm_client()

        # Reconnect / refresh: re-emit stored question without re-running execute_step (no duplicate LLM).
        if reconnect_question_only:
            pq = session["pending_question"]
            if isinstance(pq, str):
                pq = json.loads(pq)
            if isinstance(pq, dict):
                yield streamer.trace(
                    "system",
                    "Resumed — same question (reconnect)",
                    phase="system",
                )
                yield streamer.question(
                    section=pq.get("section", ""),
                    field=pq.get("field", ""),
                    question_text=pq.get("question", ""),
                    suggested_answer=pq.get("suggested_answer", ""),
                )
            return

        _update_session_status(pool, session_id, "executing")

        generated_yaml = session.get("generated_yaml", "") or ""
        cfg_agent = get_config()

        for i in range(current_step, total_steps):
            step = plan[i]
            section_key = step["section_key"]
            section_name = _section_display_name(template, section_key)
            session = _load_session(pool, session_id) or session
            pending_section_yaml = session.get("pending_section_yaml") or ""

            # If we're resuming after a user answer, incorporate it
            if status == "waiting_for_user" and i == current_step and conversation:
                last_msg = conversation[-1] if conversation else {}
                if last_msg.get("role") == "user":
                    yield streamer.trace(
                        "thinking",
                        f"Incorporating your answer for section {section_key}",
                        phase="incorporate",
                    )
                    result = await incorporate_answer(
                        step=step,
                        answer=last_msg["content"],
                        context=context,
                        template=template,
                        prior_yaml=generated_yaml,
                        llm=llm,
                        streamer=streamer,
                        template_type=session["template_type"],
                        pending_section_yaml=pending_section_yaml,
                    )
                    for evt in result["events"]:
                        yield evt
                    frag = result.get("section_yaml") or ""
                    try:
                        merged, merge_events, _skipped = await merge_section_output(
                            prior_yaml=generated_yaml,
                            section_key=section_key,
                            fragment_yaml=frag,
                            template=template,
                            llm=llm,
                            streamer=streamer,
                            section_name=section_name,
                        )
                    except Exception:
                        logger.exception(
                            "merge_section_output failed (incorporate) session=%s section=%s",
                            session_id,
                            section_key,
                        )
                        sess = _load_session(pool, session_id) or session
                        _update_session_status(
                            pool,
                            session_id,
                            "failed",
                            error=_MERGE_FAIL_USER,
                            error_code="yaml_merge_invalid",
                        )
                        gy_err, _fe = _format_yaml_for_session_persistence(
                            generated_yaml, streamer, phase="execute"
                        )
                        for ev in _fe:
                            yield ev
                        _upsert_library_draft(pool, sess, gy_err, ARTIFACT_MERGE_ERROR)
                        yield streamer.error(
                            "yaml_merge_invalid",
                            _MERGE_FAIL_USER,
                            section_key=section_key,
                        )
                        return
                    for evt in merge_events:
                        yield evt
                    generated_yaml = merged
                    generated_yaml, _fmt_evts = _format_yaml_for_session_persistence(
                        generated_yaml, streamer, phase="execute"
                    )
                    for ev in _fmt_evts:
                        yield ev
                    _maybe_write_generated_json(pool, session_id, generated_yaml, cfg_agent)
                    _save_step_progress(
                        pool,
                        session_id,
                        i + 1,
                        generated_yaml,
                        conversation,
                        pending_section_yaml="",
                    )
                    yield streamer.full_yaml(generated_yaml, is_partial=False)
                    yield streamer.section_complete(section_key, i + 1, total_steps)
                    status = "executing"
                    continue

            # Normal execution
            result = await execute_step(
                step=step,
                context=context,
                template=template,
                prior_yaml=generated_yaml,
                conversation=conversation,
                llm=llm,
                streamer=streamer,
                template_type=session["template_type"],
            )

            for evt in result["events"]:
                yield evt

            if result["needs_user_input"]:
                q_data = result.get("question_data", {})
                conversation.append({
                    "role": "assistant",
                    "content": q_data.get("question", ""),
                })
                draft = result.get("section_yaml") or ""
                preview = _preview_yaml_with_pending(generated_yaml, draft)
                _save_waiting_state(
                    pool,
                    session_id,
                    i,
                    generated_yaml,
                    conversation,
                    pending_section_yaml=draft,
                    pending_question={
                        "section": section_key,
                        "field": q_data.get("fields", [section_key])[0]
                        if q_data.get("fields")
                        else section_key,
                        "question": q_data.get("question", ""),
                        "suggested_answer": q_data.get("suggested_answer", ""),
                    },
                )
                yield streamer.full_yaml(preview, is_partial=True)
                return

            strategy = step.get("strategy", "auto_fill")
            frag = result.get("section_yaml") or ""
            if strategy == "skip" or not frag.strip():
                generated_yaml, _fmt_evts = _format_yaml_for_session_persistence(
                    generated_yaml, streamer, phase="execute"
                )
                for ev in _fmt_evts:
                    yield ev
                _save_step_progress(
                    pool,
                    session_id,
                    i + 1,
                    generated_yaml,
                    conversation,
                    pending_section_yaml="",
                )
                _maybe_write_generated_json(pool, session_id, generated_yaml, cfg_agent)
                yield streamer.full_yaml(generated_yaml, is_partial=False)
                yield streamer.section_complete(section_key, i + 1, total_steps)
                continue

            try:
                merged, merge_events, _skipped = await merge_section_output(
                    prior_yaml=generated_yaml,
                    section_key=section_key,
                    fragment_yaml=frag,
                    template=template,
                    llm=llm,
                    streamer=streamer,
                    section_name=section_name,
                )
            except Exception:
                logger.exception(
                    "merge_section_output failed session=%s section=%s",
                    session_id,
                    section_key,
                )
                sess = _load_session(pool, session_id) or session
                _update_session_status(
                    pool,
                    session_id,
                    "failed",
                    error=_MERGE_FAIL_USER,
                    error_code="yaml_merge_invalid",
                )
                gy_err, _fe = _format_yaml_for_session_persistence(
                    generated_yaml, streamer, phase="execute"
                )
                for ev in _fe:
                    yield ev
                _upsert_library_draft(pool, sess, gy_err, ARTIFACT_MERGE_ERROR)
                yield streamer.error(
                    "yaml_merge_invalid",
                    _MERGE_FAIL_USER,
                    section_key=section_key,
                )
                return
            for evt in merge_events:
                yield evt
            generated_yaml = merged
            generated_yaml, _fmt_evts = _format_yaml_for_session_persistence(
                generated_yaml, streamer, phase="execute"
            )
            for ev in _fmt_evts:
                yield ev
            _maybe_write_generated_json(pool, session_id, generated_yaml, cfg_agent)
            _save_step_progress(
                pool,
                session_id,
                i + 1,
                generated_yaml,
                conversation,
                pending_section_yaml="",
            )
            yield streamer.full_yaml(generated_yaml, is_partial=False)
            yield streamer.section_complete(section_key, i + 1, total_steps)

        # 6. Finalize
        yield streamer.trace(
            "system",
            "Finalizing: saving completed metadata and markdown",
            phase="finalize",
        )
        yield streamer.status("finalizing", "Generating markdown and saving results...")
        generated_yaml, _fmt_evts = _format_yaml_for_session_persistence(
            generated_yaml,
            streamer,
            phase="finalize",
            trace_if_disabled=True,
        )
        for ev in _fmt_evts:
            yield ev
        markdown, md_ok = safe_yaml_to_markdown(generated_yaml, session["template_type"])
        combined_id = _save_completed(pool, session, generated_yaml, markdown)
        _update_session_status(pool, session_id, "complete")
        yield streamer.complete(
            generated_yaml,
            session_id,
            completed_id=combined_id,
            markdown_export_failed=not md_ok,
            markdown_export_message=_MD_EXPORT_HINT if not md_ok else "",
        )

    except Exception as e:
        logger.error("Agent loop error for session %s: %s", session_id, e, exc_info=True)
        _update_session_status(
            pool,
            session_id,
            "failed",
            error=_USER_AGENT_FAIL,
            error_code="agent_error",
        )
        try:
            sess = _load_session(pool, session_id)
            if sess and (sess.get("generated_yaml") or "").strip():
                gy_fail = _format_committed_yaml_for_library_preview(
                    sess.get("generated_yaml") or ""
                )
                _upsert_library_draft(
                    pool,
                    sess,
                    gy_fail,
                    ARTIFACT_FAILED,
                )
        except Exception:
            logger.exception("library draft upsert after agent failure failed session=%s", session_id)
        yield streamer.error("agent_error", _USER_AGENT_FAIL)


# ---------------------------------------------------------------------------
# Database helpers
# ---------------------------------------------------------------------------

def _load_session(pool, session_id: str) -> dict | None:
    with pool.connection() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(f"SELECT * FROM {SCHEMA}.sessions WHERE id = %s", (session_id,))
            return cur.fetchone()


def _load_template(pool, template_type: str, version: int) -> str | None:
    with pool.connection() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                f"SELECT yaml_content FROM {SCHEMA}.templates "
                f"WHERE type = %s AND version = %s",
                (template_type, version),
            )
            row = cur.fetchone()
            return row["yaml_content"] if row else None


def _save_context_cache(pool, session_id: str, context: Any):
    if not isinstance(context, dict):
        logger.warning(
            "context_cache skip save: expected dict, got %s",
            type(context).__name__,
        )
        return
    if not context:
        logger.debug("context_cache skip save: empty dict")
        return
    serializable = {}
    for k, v in context.items():
        try:
            json.dumps(v)
            serializable[k] = v
        except (TypeError, ValueError):
            serializable[k] = str(v)

    with pool.connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"UPDATE {SCHEMA}.sessions SET context_cache = %s, updated_at = now() "
                f"WHERE id = %s",
                (json.dumps(serializable), session_id),
            )
        conn.commit()


def _normalize_context_cache(raw: Any) -> dict:
    """Ensure context_cache is a dict (canonical MCP shape)."""
    if raw is None:
        return {}
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            logger.warning("context_cache string could not be parsed as JSON")
            return {}
    if not isinstance(raw, dict):
        return {}
    return raw


def _section_display_name(template: dict, section_key: str) -> str:
    for s in template.get("sections", []):
        if s.get("key") == section_key:
            return str(s.get("name", section_key))
    return section_key


def _draft_table_fqn(table_ref: dict) -> str | None:
    if not isinstance(table_ref, dict):
        return None
    if table_ref.get("tables"):
        return None
    t = table_ref.get("table")
    if not t:
        return None
    return f"{table_ref.get('catalog', '')}.{table_ref.get('schema', '')}.{t}"


def _upsert_library_draft(
    pool,
    session: dict,
    yaml_content: str,
    artifact_st: str,
) -> None:
    """Upsert progressive Library row linked to session (combined YAML)."""
    sid = str(session["id"])
    uid = session["user_email"]
    tpl = session["template_type"]
    tv = session.get("template_version")
    tr = session.get("table_ref") or {}
    tr_json = json.dumps(tr) if isinstance(tr, dict) else json.dumps({})
    aid = session.get("library_artifact_id")
    md, _ok = safe_yaml_to_markdown(yaml_content, tpl)
    fqn = _draft_table_fqn(tr) if isinstance(tr, dict) else None

    with pool.connection() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            if aid:
                cur.execute(
                    f"UPDATE {SCHEMA}.completed_metadata "
                    f"SET yaml_content = %s, markdown_content = %s, "
                    f"artifact_status = %s, updated_at = now() "
                    f"WHERE id = %s AND session_id = %s::uuid AND user_email = %s",
                    (yaml_content, md, artifact_st, str(aid), sid, uid),
                )
                if cur.rowcount:
                    conn.commit()
                    return
            cur.execute(
                f"INSERT INTO {SCHEMA}.completed_metadata "
                f"(session_id, user_email, template_type, template_version, table_ref, "
                f" yaml_content, markdown_content, table_fqn, artifact_status) "
                f"VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s) RETURNING id",
                (
                    sid,
                    uid,
                    tpl,
                    tv,
                    tr_json,
                    yaml_content,
                    md,
                    fqn,
                    artifact_st,
                ),
            )
            new_id = str(cur.fetchone()["id"])
            cur.execute(
                f"UPDATE {SCHEMA}.sessions SET library_artifact_id = %s, updated_at = now() "
                f"WHERE id = %s::uuid",
                (new_id, sid),
            )
        conn.commit()


def _upsert_library_draft_after_step(pool, session_id: str) -> None:
    session = _load_session(pool, session_id)
    if not session:
        return
    g = session.get("generated_yaml") or ""
    p = session.get("pending_section_yaml") or ""
    if p.strip():
        g_fmt = _format_committed_yaml_for_library_preview(g) if g.strip() else g
        preview = _preview_yaml_with_pending(g_fmt, p)
    else:
        preview = g
    if not (preview or "").strip():
        return
    _upsert_library_draft(pool, session, preview, ARTIFACT_IN_PROGRESS)


def _preview_yaml_with_pending(committed: str, pending: str) -> str:
    c = (committed or "").strip()
    p = (pending or "").strip()
    if not p:
        return committed or ""
    if not c:
        return p
    return c + "\n" + p


def _maybe_write_generated_json(pool, session_id: str, yaml_str: str, cfg) -> None:
    if not getattr(cfg, "yaml_merge", None) or not cfg.yaml_merge.canonical_json_enabled:
        return
    doc = load_yaml_document(yaml_str)
    with pool.connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"UPDATE {SCHEMA}.sessions SET generated_json = %s::jsonb, updated_at = now() "
                f"WHERE id = %s",
                (json.dumps(doc), session_id),
            )
        conn.commit()


def _should_emit_session_resumed(session: dict) -> bool:
    st = session.get("status") or ""
    step = session.get("current_step") or 0
    conv = session.get("conversation") or []
    if st == "waiting_for_user":
        return True
    if step > 0:
        return True
    if st == "executing" and any(
        isinstance(m, dict) and m.get("role") == "user" for m in conv
    ):
        return True
    return False


def _save_plan(pool, session_id: str, plan: list[dict]):
    with pool.connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"UPDATE {SCHEMA}.sessions SET plan = %s, updated_at = now() WHERE id = %s",
                (json.dumps(plan), session_id),
            )
        conn.commit()


def _save_step_progress(
    pool,
    session_id: str,
    step: int,
    yaml_content: str,
    conversation: list,
    *,
    pending_section_yaml: str = "",
):
    with pool.connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"UPDATE {SCHEMA}.sessions "
                f"SET current_step = %s, generated_yaml = %s, "
                f"conversation = %s, status = 'executing', "
                f"pending_question = NULL, pending_section_yaml = %s, updated_at = now() "
                f"WHERE id = %s",
                (step, yaml_content, json.dumps(conversation), pending_section_yaml, session_id),
            )
        conn.commit()
    _upsert_library_draft_after_step(pool, session_id)


def _save_waiting_state(
    pool,
    session_id: str,
    step: int,
    yaml_content: str,
    conversation: list,
    pending_question: dict | None = None,
    *,
    pending_section_yaml: str = "",
):
    with pool.connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"UPDATE {SCHEMA}.sessions "
                f"SET current_step = %s, generated_yaml = %s, "
                f"conversation = %s, status = 'waiting_for_user', "
                f"pending_question = %s, pending_section_yaml = %s, updated_at = now() "
                f"WHERE id = %s",
                (
                    step,
                    yaml_content,
                    json.dumps(conversation),
                    json.dumps(pending_question) if pending_question else None,
                    pending_section_yaml,
                    session_id,
                ),
            )
        conn.commit()
    _upsert_library_draft_after_step(pool, session_id)


def _update_session_status(
    pool,
    session_id: str,
    status: str,
    error: str | None = None,
    error_code: str | None = None,
):
    with pool.connection() as conn:
        with conn.cursor() as cur:
            if status == "complete":
                cur.execute(
                    f"UPDATE {SCHEMA}.sessions "
                    f"SET status = %s, completed_at = now(), "
                    f"pending_question = NULL, error_message = NULL, error_code = NULL, "
                    f"updated_at = now() WHERE id = %s",
                    (status, session_id),
                )
            elif error is not None:
                ec = error_code or "agent_error"
                cur.execute(
                    f"UPDATE {SCHEMA}.sessions "
                    f"SET status = %s, error_message = %s, error_code = %s, "
                    f"pending_question = NULL, updated_at = now() WHERE id = %s",
                    (status, error, ec, session_id),
                )
            elif status == "executing":
                cur.execute(
                    f"UPDATE {SCHEMA}.sessions "
                    f"SET status = %s, error_message = NULL, error_code = NULL, "
                    f"updated_at = now() WHERE id = %s",
                    (status, session_id),
                )
            else:
                cur.execute(
                    f"UPDATE {SCHEMA}.sessions SET status = %s, updated_at = now() WHERE id = %s",
                    (status, session_id),
                )
        conn.commit()


def _save_completed(pool, session: dict, yaml_content: str, markdown: str) -> str:
    """Save completed metadata. Returns the primary completed row's id.

    For multi-table sessions: one combined row (table_fqn=NULL) plus per-table rows.
    For single-table: one row with table_fqn set. Reuses progressive draft row when
    ``library_artifact_id`` is set.
    """
    session = _load_session(pool, str(session["id"])) or session
    table_ref = session.get("table_ref", {})
    tables: list[dict] = []
    if table_ref.get("tables"):
        tables = table_ref["tables"]
    elif table_ref.get("table"):
        tables = [{
            "catalog": table_ref.get("catalog", ""),
            "schema": table_ref.get("schema", ""),
            "table": table_ref["table"],
        }]

    multi = len(tables) > 1
    tpl_ver = session.get("template_version")
    sid = str(session["id"])
    uid = session["user_email"]
    aid = session.get("library_artifact_id")
    tr_json = json.dumps(table_ref)

    with pool.connection() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            if multi:
                if aid:
                    cur.execute(
                        f"UPDATE {SCHEMA}.completed_metadata "
                        f"SET yaml_content = %s, markdown_content = %s, "
                        f"artifact_status = %s, updated_at = now() "
                        f"WHERE id = %s AND session_id = %s::uuid AND user_email = %s",
                        (yaml_content, markdown, ARTIFACT_COMPLETE, str(aid), sid, uid),
                    )
                    combined_id = str(aid)
                else:
                    cur.execute(
                        f"INSERT INTO {SCHEMA}.completed_metadata "
                        f"(session_id, user_email, template_type, template_version, table_ref, "
                        f" yaml_content, markdown_content, table_fqn, artifact_status) "
                        f"VALUES (%s, %s, %s, %s, %s, %s, %s, NULL, %s) RETURNING id",
                        (
                            sid,
                            uid,
                            session["template_type"],
                            tpl_ver,
                            tr_json,
                            yaml_content,
                            markdown,
                            ARTIFACT_COMPLETE,
                        ),
                    )
                    combined_id = str(cur.fetchone()["id"])
                    cur.execute(
                        f"UPDATE {SCHEMA}.sessions SET library_artifact_id = %s, updated_at = now() "
                        f"WHERE id = %s::uuid",
                        (combined_id, sid),
                    )

                per_table_yamls = _split_yaml_per_table(yaml_content, tables)
                for tbl in tables:
                    fqn = f"{tbl.get('catalog', '')}.{tbl.get('schema', '')}.{tbl.get('table', '')}"
                    tbl_yaml = per_table_yamls.get(fqn, yaml_content)
                    tbl_md, _ok = safe_yaml_to_markdown(tbl_yaml, session["template_type"])
                    cur.execute(
                        f"INSERT INTO {SCHEMA}.completed_metadata "
                        f"(session_id, user_email, template_type, template_version, table_ref, "
                        f" yaml_content, markdown_content, table_fqn, artifact_status) "
                        f"VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)",
                        (
                            sid,
                            uid,
                            session["template_type"],
                            tpl_ver,
                            tr_json,
                            tbl_yaml,
                            tbl_md,
                            fqn,
                            ARTIFACT_COMPLETE,
                        ),
                    )
            else:
                fqn = None
                if tables:
                    t = tables[0]
                    fqn = f"{t.get('catalog', '')}.{t.get('schema', '')}.{t.get('table', '')}"
                if aid:
                    cur.execute(
                        f"UPDATE {SCHEMA}.completed_metadata "
                        f"SET yaml_content = %s, markdown_content = %s, "
                        f"artifact_status = %s, updated_at = now() "
                        f"WHERE id = %s AND session_id = %s::uuid AND user_email = %s",
                        (yaml_content, markdown, ARTIFACT_COMPLETE, str(aid), sid, uid),
                    )
                    combined_id = str(aid)
                else:
                    cur.execute(
                        f"INSERT INTO {SCHEMA}.completed_metadata "
                        f"(session_id, user_email, template_type, template_version, table_ref, "
                        f" yaml_content, markdown_content, table_fqn, artifact_status) "
                        f"VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s) RETURNING id",
                        (
                            sid,
                            uid,
                            session["template_type"],
                            tpl_ver,
                            tr_json,
                            yaml_content,
                            markdown,
                            fqn,
                            ARTIFACT_COMPLETE,
                        ),
                    )
                    combined_id = str(cur.fetchone()["id"])
                    cur.execute(
                        f"UPDATE {SCHEMA}.sessions SET library_artifact_id = %s, updated_at = now() "
                        f"WHERE id = %s::uuid",
                        (combined_id, sid),
                    )
        conn.commit()

    return combined_id


def _split_yaml_per_table(yaml_content: str, tables: list[dict]) -> dict[str, str]:
    """Best-effort split of combined YAML into per-table chunks.

    Returns {fqn: yaml_str}. Falls back to full content if parsing
    fails or the structure isn't partitioned by top-level keys.
    """
    try:
        data = yaml.safe_load(yaml_content)
        if not isinstance(data, dict):
            return {}
    except yaml.YAMLError:
        return {}

    fqns = set()
    for t in tables:
        fqns.add(f"{t.get('catalog', '')}.{t.get('schema', '')}.{t.get('table', '')}")

    # If top-level keys match table FQNs, split directly
    if fqns.issubset(set(data.keys())):
        result = {}
        for fqn in fqns:
            # Inner document only — matches table_comment template top-level keys
            # (not { fqn: { ... } }, which breaks yaml_to_markdown).
            result[fqn] = yaml.dump(data[fqn], default_flow_style=False)
        return result

    return {}


def _find_completed_id(pool, session_id: str, user_email: str) -> str | None:
    """Look up the primary completed_metadata row for a session (combined or single)."""
    with pool.connection() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                f"SELECT id FROM {SCHEMA}.completed_metadata "
                f"WHERE session_id = %s AND user_email = %s "
                f"ORDER BY table_fqn NULLS FIRST LIMIT 1",
                (session_id, user_email),
            )
            row = cur.fetchone()
    return str(row["id"]) if row else None


# ---------------------------------------------------------------------------
# MCP context gathering
# ---------------------------------------------------------------------------

def _build_tool_args(tool: dict, catalog: str, schema: str, table: str) -> dict | None:
    """Build arguments for a tool based on its inputSchema.

    Inspects the tool's parameter names to determine the calling convention.
    Returns None for tools that don't take table parameters (e.g. list_jobs).
    """
    props = tool.get("inputSchema", {}).get("properties", {})
    param_names = set(props.keys())
    fqn = f"{catalog}.{schema}.{table}"

    if "table_fqn" in param_names:
        return {"table_fqn": fqn}
    if "table_full_name" in param_names:
        return {"table_full_name": fqn}
    if "p_catalog" in param_names:
        return {"p_catalog": catalog, "p_schema": schema, "p_table": table}
    if "catalog_name" in param_names:
        return {"catalog_name": catalog, "schema_name": schema, "table_name": table}
    return None


async def _iter_gather_context_events(
    session: dict,
    streamer: EventStreamer,
    out: dict[str, Any],
    pool,
    session_id: str,
) -> AsyncGenerator[dict, None]:
    """Run MCP gather; yield trace SSE dicts; set out['context'] to the result dict.

    Merges existing table/tool cells from context_cache, skips call_tool when a cell
    exists, persists partial progress, and sets _mcp_gather_complete when done.
    """
    config = get_config()
    registry = MCPRegistry([
        {"name": s.name, "type": s.type, "app_name": s.app_name,
         "uc_catalog": s.uc_catalog, "uc_schema": s.uc_schema, "url": s.url}
        for s in config.mcp_servers
    ])

    raw_cache = _normalize_context_cache(session.get("context_cache"))
    context: dict[str, Any] = _seed_merged_table_context(raw_cache)

    yield streamer.trace(
        "system",
        "Connecting to MCP servers…",
        phase="gather",
    )
    try:
        await asyncio.to_thread(registry.connect_all)
    except Exception as e:
        logger.warning(f"MCP registry connect failed: {e}")
        yield streamer.trace(
            "system",
            f"MCP connect failed: {e}",
            phase="gather",
        )
        return

    table_ref = session.get("table_ref", {})

    tables: list[dict] = []
    if table_ref.get("tables"):
        tables = table_ref["tables"]
    elif table_ref.get("table"):
        tables = [{
            "catalog": table_ref.get("catalog", ""),
            "schema": table_ref.get("schema", ""),
            "table": table_ref["table"],
        }]

    all_tools = registry.get_available_tools()
    overrides = config.mcp_tool_overrides
    context["_mcp_tool_manifest"] = build_tool_manifest(all_tools, overrides)
    gather_tools = tools_for_auto_gather(all_tools, overrides)
    multi_table = len(tables) > 1

    if not all_tools:
        yield streamer.trace(
            "system",
            "No MCP tools discovered from servers — proceeding with template only",
            phase="gather",
        )

    def persist_partial() -> None:
        context[_MCP_GATHER_COMPLETE_KEY] = False
        _save_context_cache(pool, session_id, context)

    for tbl in tables:
        cat = tbl.get("catalog", "")
        sch = tbl.get("schema", "")
        tname = tbl.get("table", "")
        tbl_key = f"{cat}.{sch}.{tname}"
        seeded = context.get(tbl_key)
        if isinstance(seeded, dict):
            tbl_context: dict[str, Any] = copy.deepcopy(seeded)
        else:
            tbl_context = {}

        for tool in gather_tools:
            tool_name = tool["name"]
            args = _build_tool_args(tool, cat, sch, tname)
            if args is None:
                continue
            tfqn = tbl_key if multi_table else None
            if tool_name in tbl_context:
                yield streamer.trace(
                    "tool",
                    f"Skipping {tool_name} (cached)",
                    tool=tool_name,
                    phase="gather",
                    table_fqn=tfqn,
                )
                continue
            yield streamer.trace(
                "tool",
                f"Calling {tool_name}",
                tool=tool_name,
                phase="gather",
                table_fqn=tfqn,
            )
            try:
                result = await asyncio.to_thread(
                    registry.call_tool, tool_name, args
                )
                tbl_context[tool_name] = result
                preview = str(result) if result is not None else ""
                if isinstance(result, dict) and result.get("_mcp_error"):
                    preview = f"[error] {result.get('detail', '')}"
                detail = preview[:TRACE_DETAIL_MAX] + (
                    "…" if len(preview) > TRACE_DETAIL_MAX else ""
                )
                yield streamer.trace(
                    "tool",
                    f"{tool_name} returned",
                    tool=tool_name,
                    detail=detail,
                    phase="gather",
                    table_fqn=tfqn,
                )
            except Exception as e:
                logger.warning(f"MCP tool {tool_name} failed for {tbl_key}: {e}")
                tbl_context[tool_name] = {"_mcp_error": True, "detail": str(e)}
                yield streamer.trace(
                    "system",
                    f"Tool {tool_name} failed: {e}",
                    tool=tool_name,
                    phase="gather",
                    table_fqn=tfqn,
                )
            context[tbl_key] = tbl_context
            persist_partial()

        context[tbl_key] = tbl_context

    context[_MCP_GATHER_COMPLETE_KEY] = True
    _save_context_cache(pool, session_id, context)
    out["context"] = context
    yield streamer.trace(
        "system",
        "MCP context gather complete",
        phase="gather",
    )
