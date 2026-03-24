"""YAML to Markdown conversion for completed metadata."""
import logging
import re
from typing import Any

import yaml

logger = logging.getLogger(__name__)

# section_depth 0..4 → Markdown h2..h6; deeper nesting uses bold labels only.
_MAX_HEADING_SECTION_DEPTH = 4


def _unwrap_table_comment_dict(data: dict) -> dict:
    """If YAML was stored as { fqn: { table_identity: ... } }, unwrap to inner dict."""
    if len(data) != 1:
        return data
    only = next(iter(data.values()))
    if not isinstance(only, dict):
        return data
    if "table_identity" in only or "core_description" in only:
        return only
    return data


def _humanize_key(key: str) -> str:
    """Turn snake_case YAML keys into short titles."""
    parts = str(key).split("_")
    out: list[str] = []
    for p in parts:
        if not p:
            continue
        out.append(p[0].upper() + p[1:] if len(p) > 1 else p.upper())
    return " ".join(out) if out else str(key)


def _md_plain(s: Any) -> str:
    """Strip and remove backticks so text won't break Markdown parsing."""
    if s is None:
        return ""
    return str(s).strip().replace("`", "'")


def _md_inline(s: Any) -> str:
    """Single-line safe text for bullets (no backticks, collapse whitespace)."""
    t = _md_plain(s)
    t = re.sub(r"\s+", " ", t)
    return t


def _section_heading(label: str, section_depth: int, lines: list[str]) -> None:
    if section_depth <= _MAX_HEADING_SECTION_DEPTH:
        level = 2 + section_depth
        lines.append("#" * level + " " + _md_plain(label))
    else:
        lines.append(f"**{_md_plain(label)}**")


def _emit_scalar_body(key: str, value: Any, lines: list[str]) -> None:
    if value is None:
        lines.append("—")
        return
    if isinstance(value, bool):
        lines.append("true" if value else "false")
        return
    if isinstance(value, (int, float)):
        lines.append(str(value))
        return
    s = str(value)
    pk = str(key)
    if (pk == "sql" or pk.endswith("_sql")) and "\n" in s.strip():
        lines.append("```sql")
        lines.append(s.rstrip())
        lines.append("```")
        return
    if "\n" in s:
        lines.append("")
        lines.append(_md_plain(s))
    else:
        lines.append(_md_inline(s))


def _emit_list(items: list[Any], lines: list[str], section_depth: int) -> None:
    if not items:
        lines.append("—")
        return

    if all(isinstance(x, dict) for x in items):
        for i, item in enumerate(items, 1):
            assert isinstance(item, dict)
            _section_heading(f"Item {i}", section_depth, lines)
            if not item:
                lines.append("—")
            else:
                for sk, sv in item.items():
                    _emit_key_value(sk, sv, lines, section_depth + 1)
        return

    item_num = 0
    for x in items:
        if isinstance(x, dict):
            item_num += 1
            _section_heading(f"Item {item_num}", section_depth, lines)
            if not x:
                lines.append("—")
            else:
                for sk, sv in x.items():
                    _emit_key_value(sk, sv, lines, section_depth + 1)
        else:
            lines.append(f"- {_md_inline(x)}")


def _emit_key_value(key: str, value: Any, lines: list[str], section_depth: int) -> None:
    label = _humanize_key(key)
    if isinstance(value, dict):
        _section_heading(label, section_depth, lines)
        if not value:
            lines.append("—")
        else:
            for sk, sv in value.items():
                _emit_key_value(sk, sv, lines, section_depth + 1)
    elif isinstance(value, list):
        _section_heading(label, section_depth, lines)
        _emit_list(value, lines, section_depth + 1)
    else:
        _section_heading(label, section_depth, lines)
        _emit_scalar_body(key, value, lines)


def hierarchical_dict_to_md(data: dict) -> str:
    """Render a YAML-loaded dict as Markdown by walking keys (headings) and values."""
    lines: list[str] = []
    if not data:
        lines.append("—")
        return "\n".join(lines)
    for k, v in data.items():
        _emit_key_value(k, v, lines, section_depth=0)
    return "\n".join(lines)


def safe_yaml_to_markdown(yaml_content: str, template_type: str = "table_comment") -> tuple[str, bool]:
    """Convert YAML to Markdown; never raises. Returns (markdown, ok).

    ``ok`` is False when conversion fell back (fenced YAML or empty) due to error.
    """
    try:
        md = yaml_to_markdown(yaml_content, template_type)
        return md, True
    except Exception as e:
        logger.warning("yaml_to_markdown failed: %s", e, exc_info=True)
        return f"```yaml\n{yaml_content}\n```", False


def yaml_to_markdown(yaml_content: str, template_type: str = "table_comment") -> str:
    """Convert filled YAML metadata to Markdown by mirroring the document hierarchy."""
    try:
        data = yaml.safe_load(yaml_content)
        if not data or not isinstance(data, dict):
            return f"```yaml\n{yaml_content}\n```"
    except yaml.YAMLError:
        return f"```yaml\n{yaml_content}\n```"

    if template_type == "table_comment":
        data = _unwrap_table_comment_dict(data)
    return hierarchical_dict_to_md(data)
