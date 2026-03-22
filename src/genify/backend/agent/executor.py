"""Plan step execution — generates YAML from cached MCP context via LLM, merges, streams events.

Does not call MCP; context comes from gather (`context_cache`). See docs/design-decisions.md ADR-14.
"""
import asyncio
import json
import logging
from typing import Any

import yaml

from backend.agent.prompts import (
    INTERACTIVE_QUESTION_PROMPT,
    MERGE_CORRECTION_PROMPT,
    SECTION_GENERATION_PROMPT,
    SYSTEM_PROMPT,
    YAML_FORMAT_INSTRUCTIONS,
    GENIE_SYSTEM_SUPPLEMENT,
)
from backend.agent.yaml_merge import (
    dump_yaml_document,
    load_yaml_document,
    merge_from_strings,
    merge_section_fragment_or_skip,
)
from backend.agent.streamer import EventStreamer
from backend.config import get_config
from backend.context_text import tail_chars, truncate_chars
from backend.llm.client import LLMClient
from backend.llm.token_manager import trim_history

logger = logging.getLogger(__name__)


async def execute_step(
    step: dict,
    context: dict,
    template: dict,
    prior_yaml: str,
    conversation: list[dict],
    llm: LLMClient,
    streamer: EventStreamer,
    template_type: str = "table_comment",
) -> dict:
    """Execute one plan step: gather data, generate YAML, yield SSE events.

    Returns:
        {
            "section_yaml": str,       # generated YAML for this section
            "events": list[dict],      # SSE events to yield
            "needs_user_input": bool,  # True if interactive question was emitted
            "question_data": dict|None # Question details if needs_user_input
        }
    """
    section_key = step["section_key"]
    strategy = step["strategy"]
    step_num = step["step"]
    events = []
    cfg = get_config()
    trunc = cfg.context_truncation

    # Find section definition in template
    section_def = _find_section(template, section_key)
    section_name = section_def.get("name", section_key)
    section_template = _get_section_template(template, section_key)
    prompt_focus = section_def.get("prompt_focus", "")

    events.append(
        streamer.trace(
            "thinking",
            f"Section {section_key}: {section_name}",
            phase="execute",
        )
    )

    # Build context data for this section
    context_data = _build_section_context(context, trunc.executor_section_chars_per_key)

    # Build system prompt
    system = SYSTEM_PROMPT + YAML_FORMAT_INSTRUCTIONS
    if template_type == "genie":
        system += GENIE_SYSTEM_SUPPLEMENT

    if strategy in ("auto_fill", "skip"):
        if strategy == "skip":
            events.append(
                streamer.trace(
                    "thinking",
                    f"Skipping {section_name} (optional, insufficient data)",
                    phase="execute",
                )
            )
            return {"section_yaml": "", "events": events, "needs_user_input": False, "question_data": None}

        # Auto-fill: generate YAML from data
        prompt = SECTION_GENERATION_PROMPT.format(
            section_name=section_name,
            section_template=yaml.dump(section_template, default_flow_style=False) if section_template else "{}",
            context_data=context_data,
            prior_yaml=tail_chars(prior_yaml, trunc.prior_yaml_tail_chars),
            prompt_focus=prompt_focus,
        )

        messages = [
            {"role": "system", "content": system},
            {"role": "user", "content": prompt},
        ]
        messages = trim_history(messages, max_tokens=cfg.llm.max_prompt_tokens)
        events.append(
            streamer.trace(
                "llm",
                f"Generating YAML for {section_name}…",
                phase="execute",
            )
        )
        section_yaml = await asyncio.to_thread(llm.chat, messages)
        section_yaml = _clean_yaml_response(section_yaml)

        events.append(streamer.yaml_chunk(section_key, section_yaml, is_complete=True))
        return {"section_yaml": section_yaml, "events": events, "needs_user_input": False, "question_data": None}

    elif strategy == "partial_fill_then_ask":
        # First generate what we can
        events.append(
            streamer.thinking(step_num, section_key, f"Filling {section_name} from available data...")
        )

        prompt = SECTION_GENERATION_PROMPT.format(
            section_name=section_name,
            section_template=yaml.dump(section_template, default_flow_style=False) if section_template else "{}",
            context_data=context_data,
            prior_yaml=tail_chars(prior_yaml, trunc.prior_yaml_tail_chars),
            prompt_focus=prompt_focus,
        )

        messages = [
            {"role": "system", "content": system},
            {"role": "user", "content": prompt},
        ]
        messages = trim_history(messages, max_tokens=cfg.llm.max_prompt_tokens)
        events.append(
            streamer.trace(
                "llm",
                f"Partial YAML for {section_name}…",
                phase="execute",
            )
        )
        partial_yaml = await asyncio.to_thread(llm.chat, messages)
        partial_yaml = _clean_yaml_response(partial_yaml)
        events.append(streamer.yaml_chunk(section_key, partial_yaml, is_complete=False))

        # Generate question for unknown fields
        events.append(
            streamer.trace(
                "wait",
                "Generating follow-up question…",
                phase="wait_user",
            )
        )
        question_prompt = INTERACTIVE_QUESTION_PROMPT.format(
            section_name=section_name,
            known_data=truncate_chars(context_data, trunc.interactive_known_data_chars),
            fields_to_ask=", ".join(section_def.get("fields", [])),
        )
        q_messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": question_prompt},
        ]
        q_response = await asyncio.to_thread(llm.chat, q_messages)
        question_data = _parse_question_json(q_response, section_key)

        events.append(
            streamer.trace(
                "wait",
                "Waiting for your answer",
                phase="wait_user",
            )
        )
        events.append(
            streamer.question(
                section=section_key,
                field=question_data.get("fields", [section_key])[0] if question_data.get("fields") else section_key,
                question_text=question_data.get("question", f"Can you provide more details about {section_name}?"),
                suggested_answer=question_data.get("suggested_answer", ""),
            )
        )
        return {
            "section_yaml": partial_yaml,
            "events": events,
            "needs_user_input": True,
            "question_data": question_data,
        }

    elif strategy == "ask_user":
        events.append(
            streamer.trace(
                "wait",
                f"Preparing question for {section_name}…",
                phase="wait_user",
            )
        )
        question_prompt = INTERACTIVE_QUESTION_PROMPT.format(
            section_name=section_name,
            known_data=truncate_chars(context_data, trunc.interactive_known_data_chars),
            fields_to_ask=", ".join(section_def.get("fields", [])),
        )
        q_messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": question_prompt},
        ]
        q_response = await asyncio.to_thread(llm.chat, q_messages)
        question_data = _parse_question_json(q_response, section_key)

        events.append(
            streamer.trace(
                "wait",
                "Waiting for your answer",
                phase="wait_user",
            )
        )
        events.append(
            streamer.question(
                section=section_key,
                field=question_data.get("fields", [section_key])[0] if question_data.get("fields") else section_key,
                question_text=question_data.get("question", f"Tell me about {section_name}"),
                suggested_answer=question_data.get("suggested_answer", ""),
            )
        )
        return {"section_yaml": "", "events": events, "needs_user_input": True, "question_data": question_data}

    return {"section_yaml": "", "events": events, "needs_user_input": False, "question_data": None}


async def incorporate_answer(
    step: dict,
    answer: str,
    context: dict,
    template: dict,
    prior_yaml: str,
    llm: LLMClient,
    streamer: EventStreamer,
    template_type: str = "table_comment",
    pending_section_yaml: str = "",
) -> dict:
    """Re-generate section YAML incorporating the user's answer."""
    section_key = step["section_key"]
    section_def = _find_section(template, section_key)
    section_name = section_def.get("name", section_key)
    section_template = _get_section_template(template, section_key)
    prompt_focus = section_def.get("prompt_focus", "")
    cfg = get_config()
    trunc = cfg.context_truncation
    context_data = _build_section_context(context, trunc.executor_section_chars_per_key)

    system = SYSTEM_PROMPT + YAML_FORMAT_INSTRUCTIONS
    if template_type == "genie":
        system += GENIE_SYSTEM_SUPPLEMENT

    combined_prior = prior_yaml.strip()
    if pending_section_yaml and str(pending_section_yaml).strip():
        combined_prior = (combined_prior + "\n" + pending_section_yaml.strip()).strip()

    prompt = SECTION_GENERATION_PROMPT.format(
        section_name=section_name,
        section_template=yaml.dump(section_template, default_flow_style=False) if section_template else "{}",
        context_data=context_data + f"\n\n## User Clarification\n{answer}",
        prior_yaml=tail_chars(combined_prior, trunc.prior_yaml_tail_chars),
        prompt_focus=prompt_focus,
    )

    messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": prompt},
    ]
    messages = trim_history(messages, max_tokens=cfg.llm.max_prompt_tokens)
    events = [
        streamer.trace(
            "llm",
            f"Regenerating {section_name} with your answer…",
            phase="incorporate",
        ),
    ]
    section_yaml = await asyncio.to_thread(llm.chat, messages)
    section_yaml = _clean_yaml_response(section_yaml)

    events.append(
        streamer.trace(
            "thinking",
            f"Updated {section_name} with your input",
            phase="incorporate",
        )
    )
    events.append(streamer.yaml_chunk(section_key, section_yaml, is_complete=True))
    return {"section_yaml": section_yaml, "events": events}


def _find_section(template: dict, section_key: str) -> dict:
    for s in template.get("sections", []):
        if s.get("key") == section_key:
            return s
    return {"key": section_key, "name": section_key}


def _get_section_template(template: dict, section_key: str) -> Any:
    tpl = template.get("template", {})
    return tpl.get(section_key)


def _build_section_context(context: dict, chars_per_key: int) -> str:
    """Format all MCP context data for the LLM. Dynamic — works with any tool names."""
    if not context:
        return "No context data available."
    parts = []
    for key, val in context.items():
        if key.startswith("_"):
            continue
        if isinstance(val, dict) and val.get("_mcp_error"):
            text = f"[Tool failed] {val.get('detail', '')}"
            parts.append(f"### {key}\n{truncate_chars(text, chars_per_key)}")
            continue
        if isinstance(val, dict):
            sub_parts = []
            for tk, tv in val.items():
                if isinstance(tv, dict) and tv.get("_mcp_error"):
                    sub_parts.append(
                        f"#### {tk}\n[Tool failed] {truncate_chars(str(tv.get('detail', '')), chars_per_key)}"
                    )
                else:
                    tstr = str(tv) if not isinstance(tv, str) else tv
                    sub_parts.append(f"#### {tk}\n{truncate_chars(tstr, chars_per_key)}")
            parts.append(f"### {key}\n" + "\n".join(sub_parts))
            continue
        text = str(val) if not isinstance(val, str) else val
        parts.append(f"### {key}\n{truncate_chars(text, chars_per_key)}")
    return "\n\n".join(parts) if parts else "No context data available."


async def merge_section_output(
    *,
    prior_yaml: str,
    section_key: str,
    fragment_yaml: str,
    template: dict,
    llm: LLMClient,
    streamer: EventStreamer,
    section_name: str,
) -> tuple[str, list[dict], bool]:
    """Merge a section fragment into prior YAML with LLM correction retries.

    Returns ``(merged_full_yaml, extra_sse_events, skipped_placeholder)``.
    """
    cfg = get_config()
    ym = cfg.yaml_merge
    nested = ym.nested_validation if ym.nested_validation in ("off", "strip") else "strip"
    section_template = _get_section_template(template, section_key)
    events: list[dict] = []
    frag = fragment_yaml
    max_r = max(0, ym.merge_max_retries)

    for attempt in range(max_r + 1):
        merged_str, err = merge_from_strings(
            prior_yaml,
            section_key,
            frag,
            section_template=section_template,
            nested_validation=nested,
        )
        if merged_str is not None:
            return merged_str, events, False
        if attempt < max_r:
            events.append(
                streamer.trace(
                    "system",
                    f"Merge validation failed (attempt {attempt + 1}): {err}",
                    phase="execute",
                )
            )
            fix_prompt = MERGE_CORRECTION_PROMPT.format(
                section_key=section_key,
                section_name=section_name,
                error=err or "unknown",
                attempt=frag[:8000],
            )
            messages = [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": fix_prompt},
            ]
            messages = trim_history(messages, max_tokens=cfg.llm.max_prompt_tokens)
            frag = await asyncio.to_thread(llm.chat, messages)
            frag = _clean_yaml_response(frag)
        else:
            base_doc = load_yaml_document(prior_yaml)
            doc, skipped = merge_section_fragment_or_skip(
                base_doc,
                section_key,
                frag,
                section_template=section_template,
                nested_validation=nested,
            )
            events.append(
                streamer.trace(
                    "system",
                    f"Merge failed after retries — placeholder inserted: {err}",
                    phase="execute",
                )
            )
            return dump_yaml_document(doc), events, skipped


def _clean_yaml_response(response: str) -> str:
    text = response.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        text = "\n".join(lines)
    return text


def _parse_question_json(response: str, section_key: str) -> dict:
    try:
        text = response.strip()
        if text.startswith("```"):
            lines = text.split("\n")[1:]
            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]
            text = "\n".join(lines)
        return json.loads(text)
    except (json.JSONDecodeError, ValueError):
        return {
            "question": f"Can you provide more details about {section_key}?",
            "suggested_answer": "",
            "fields": [section_key],
        }
