"""SSE event formatting and yielding.

Each method produces a dict suitable for sse-starlette's EventSourceResponse.
"""
import json
import logging
from typing import Any

logger = logging.getLogger(__name__)

TRACE_DETAIL_MAX = 400


class EventStreamer:
    """Formats and yields SSE events for the agent loop."""

    def status(self, phase: str, message: str) -> dict:
        return {
            "event": "status",
            "data": json.dumps({"phase": phase, "message": message}),
        }

    def thinking(
        self,
        step: int,
        section: str,
        message: str,
        tool: str | None = None,
    ) -> dict:
        payload = {"step": step, "section": section, "message": message}
        if tool:
            payload["tool"] = tool
        return {"event": "thinking", "data": json.dumps(payload)}

    def plan(self, steps: list[dict], total_sections: int, estimated_time: str = "") -> dict:
        return {
            "event": "plan",
            "data": json.dumps({
                "steps": steps,
                "total_sections": total_sections,
                "estimated_time": estimated_time,
            }),
        }

    def yaml_chunk(self, section: str, content: str, is_complete: bool) -> dict:
        return {
            "event": "yaml_chunk",
            "data": json.dumps({
                "section": section,
                "content": content,
                "is_complete": is_complete,
            }),
        }

    def section_complete(self, section: str, step: int, total: int) -> dict:
        return {
            "event": "section_complete",
            "data": json.dumps({
                "section": section,
                "step": step,
                "total": total,
            }),
        }

    def question(
        self,
        section: str,
        field: str,
        question_text: str,
        suggested_answer: str,
    ) -> dict:
        return {
            "event": "question",
            "data": json.dumps({
                "section": section,
                "field": field,
                "question": question_text,
                "suggested_answer": suggested_answer,
            }),
        }

    def complete(
        self,
        yaml_content: str,
        session_id: str,
        completed_id: str | None = None,
        *,
        markdown_export_failed: bool = False,
        markdown_export_message: str = "",
    ) -> dict:
        payload = {"yaml": yaml_content, "session_id": session_id}
        if completed_id:
            payload["completed_id"] = completed_id
        if markdown_export_failed:
            payload["markdown_export_failed"] = True
        if markdown_export_message:
            payload["markdown_export_message"] = markdown_export_message
        return {"event": "complete", "data": json.dumps(payload)}

    def error(
        self,
        code: str,
        message: str,
        *,
        section_key: str | None = None,
    ) -> dict:
        payload: dict[str, Any] = {"code": code, "message": message}
        if section_key:
            payload["section_key"] = section_key
        return {
            "event": "error",
            "data": json.dumps(payload),
        }

    def full_yaml(self, yaml_content: str, *, is_partial: bool = False) -> dict:
        """Authoritative merged YAML for the client (prefer over yaml_chunk accumulation)."""
        return {
            "event": "full_yaml",
            "data": json.dumps({"yaml": yaml_content, "is_partial": bool(is_partial)}),
        }

    def trace(
        self,
        category: str,
        message: str,
        *,
        tool: str | None = None,
        detail: str | None = None,
        phase: str | None = None,
        table_fqn: str | None = None,
    ) -> dict:
        """Verbose diagnostic line for the trace panel (not the milestone timeline)."""
        d: dict[str, Any] = {"category": category, "message": message}
        if tool is not None:
            d["tool"] = tool
        if detail:
            d["detail"] = detail[:TRACE_DETAIL_MAX] + (
                "…" if len(detail) > TRACE_DETAIL_MAX else ""
            )
        if phase is not None:
            d["phase"] = phase
        if table_fqn is not None:
            d["table_fqn"] = table_fqn
        return {"event": "trace", "data": json.dumps(d)}
