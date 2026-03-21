"""Plan generation — LLM analyzes template + context and produces a JSON plan."""
import asyncio
import json
import logging
from typing import Any

import yaml

from backend.agent.prompts import PLANNING_PROMPT, SYSTEM_PROMPT
from backend.agent.streamer import EventStreamer
from backend.config import get_config
from backend.context_text import truncate_chars
from backend.llm.client import LLMClient
from backend.llm.token_manager import trim_history
from backend.mcp.tool_manifest import format_manifest_for_planner

logger = logging.getLogger(__name__)


async def generate_plan(
    template: dict,
    context: dict,
    mode: str,
    llm: LLMClient,
    streamer: EventStreamer | None = None,
    trace_out: list | None = None,
) -> list[dict]:
    """Call LLM to produce a plan for filling template sections.

    Returns a list of plan steps:
    [{"step": 1, "section_key": "core_description", "strategy": "auto_fill", ...}]
    """
    sections = template.get("sections", [])
    sections_yaml = yaml.dump(sections, default_flow_style=False)
    context_summary = _summarize_context(context)
    tools_manifest_text = _tools_block_for_plan(context)

    manifest_rows = context.get("_mcp_tool_manifest")
    if isinstance(manifest_rows, list):
        try:
            logger.info(
                "MCP tool manifest for planning (%d entries): %s",
                len(manifest_rows),
                json.dumps(manifest_rows, default=str),
            )
        except (TypeError, ValueError) as e:
            logger.warning("Could not serialize MCP tool manifest for logging: %s", e)

    prompt = PLANNING_PROMPT.format(
        sections_yaml=sections_yaml,
        tools_manifest_text=tools_manifest_text,
        context_summary=context_summary,
        mode=mode,
    )

    cfg = get_config()
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": prompt},
    ]
    messages = trim_history(messages, max_tokens=cfg.llm.max_prompt_tokens)

    def _trace(ev: dict) -> None:
        if trace_out is not None:
            trace_out.append(ev)

    if streamer is not None:
        _trace(
            streamer.trace(
                "plan",
                "LLM planning started",
                phase="plan",
            )
        )

    try:
        response = await asyncio.to_thread(llm.chat, messages)
        plan_data = _parse_plan_json(response)
        try:
            logger.info("Plan JSON: %s", json.dumps(plan_data, default=str))
        except (TypeError, ValueError) as e:
            logger.warning("Could not serialize plan for logging: %s", e)
        steps = plan_data.get("plan", [])
        logger.info(
            f"Plan generated: {len(steps)} steps, "
            f"auto_fill={plan_data.get('total_auto_fill', 0)}, "
            f"ask={plan_data.get('total_ask', 0)}"
        )
        if streamer is not None:
            _trace(
                streamer.trace(
                    "plan",
                    f"Plan ready — {len(steps)} steps",
                    phase="plan",
                )
            )
        return steps
    except Exception as e:
        logger.error(f"Plan generation failed: {e}", exc_info=True)
        if streamer is not None:
            _trace(
                streamer.trace(
                    "system",
                    f"Planning failed, using fallback: {e}",
                    phase="plan",
                )
            )
        steps = _fallback_plan(sections, mode)
        try:
            logger.info(
                "Plan JSON (fallback): %s",
                json.dumps({"plan": steps, "source": "fallback"}, default=str),
            )
        except (TypeError, ValueError) as e:
            logger.warning("Could not serialize fallback plan for logging: %s", e)
        return steps


def _tools_block_for_plan(context: dict) -> str:
    """Prefer structured manifest; fall back to legacy _tool_descriptions from old context_cache."""
    m = context.get("_mcp_tool_manifest")
    if isinstance(m, list) and m:
        return format_manifest_for_planner(m)
    legacy = context.get("_tool_descriptions")
    if isinstance(legacy, str) and legacy.strip():
        return f"## Legacy cached tool list\n{legacy.strip()}"
    return format_manifest_for_planner([])


def _summarize_context(context: dict) -> str:
    """Build a text summary of the MCP-gathered context for the LLM.

    Iterates all context keys dynamically — works with any MCP tool names.
    """
    if not context:
        return "No context data available."
    limit = get_config().context_truncation.planning_chars_per_key
    parts = []
    for key, data in context.items():
        if key.startswith("_"):
            continue
        text = str(data) if not isinstance(data, str) else data
        parts.append(f"## {key}\n{truncate_chars(text, limit)}")
    return "\n\n".join(parts) if parts else "No context data available."


def _parse_plan_json(response: str) -> dict:
    """Parse LLM response as JSON, handling markdown fences."""
    text = response.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        lines = lines[1:]  # skip ```json
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        text = "\n".join(lines)
    return json.loads(text)


def _fallback_plan(sections: list[dict], mode: str) -> list[dict]:
    """Generate a safe fallback plan if LLM planning fails."""
    steps = []
    for i, section in enumerate(sections):
        strategy = "auto_fill" if mode == "hands_off" else "partial_fill_then_ask"
        steps.append({
            "step": i + 1,
            "section_key": section["key"],
            "strategy": strategy,
            "data_sources": [],
            "confidence": "medium",
            "reasoning": "Fallback plan — LLM planning failed",
        })
    return steps
