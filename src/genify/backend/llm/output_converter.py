"""YAML to Markdown conversion for completed metadata."""
import logging
import re
from typing import Any

import yaml

logger = logging.getLogger(__name__)


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


def _md_code_span(s: Any) -> str:
    """Sanitize content inside a Markdown `code` span."""
    return _md_plain(s).replace("|", " ")


def yaml_to_markdown(yaml_content: str, template_type: str = "table_comment") -> str:
    """Convert filled YAML metadata to human-readable Markdown.

    Produces a structured document with headings, tables, and lists
    based on the template type.
    """
    try:
        data = yaml.safe_load(yaml_content)
        if not data or not isinstance(data, dict):
            return f"```yaml\n{yaml_content}\n```"
    except yaml.YAMLError:
        return f"```yaml\n{yaml_content}\n```"

    if template_type == "table_comment":
        data = _unwrap_table_comment_dict(data)
        return _table_comment_to_md(data)
    elif template_type == "genie":
        return _genie_to_md(data)
    return _generic_to_md(data)


def _table_comment_to_md(data: dict) -> str:
    """Convert table comment YAML to markdown."""
    lines = []

    identity = data.get("table_identity", {})
    fqn = f"{identity.get('catalog', '')}.{identity.get('schema', '')}.{identity.get('name', '')}"
    biz_name = identity.get("business_name", "")
    lines.append(f"# {_md_plain(biz_name) or _md_plain(fqn)}")
    if biz_name:
        lines.append(f"**Table**: `{_md_code_span(fqn)}`\n")

    core = data.get("core_description", {})
    if core:
        lines.append("## Description")
        if core.get("description"):
            lines.append(_md_plain(str(core["description"])))
        if core.get("business_purpose"):
            lines.append("\n### Business Purpose")
            lines.append(_md_plain(str(core["business_purpose"])))
        if core.get("granularity"):
            lines.append(f"\n**Granularity**: {_md_plain(core['granularity'])}")
        if core.get("business_domain"):
            lines.append(f"\n**Domain**: {_md_plain(core['business_domain'])}")
        scope = core.get("data_scope", {})
        if scope:
            lines.append("\n### Data Scope")
            dr = scope.get("date_range", {})
            if dr.get("start_date"):
                lines.append(
                    f"- **Date range**: {_md_plain(dr['start_date'])} to {_md_plain(dr.get('current', 'present'))}"
                )
            if scope.get("completeness"):
                lines.append(f"- **Completeness**: {_md_plain(scope['completeness'])}")
            if scope.get("refresh_frequency"):
                lines.append(f"- **Refresh**: {_md_plain(scope['refresh_frequency'])}")

    rels = data.get("relationships")
    # Template expects a dict with business_concepts + relationships[]; the LLM may emit a bare list.
    if isinstance(rels, dict) and rels:
        concepts = rels.get("business_concepts", {})
        if concepts and isinstance(concepts, dict):
            lines.append("\n## Business Concepts")
            for name, info in concepts.items():
                if isinstance(info, dict):
                    lines.append(f"\n### {_md_plain(name)}")
                    if info.get("definition"):
                        lines.append(f"- **Definition**: {_md_plain(info['definition'])}")
                    if info.get("calculation"):
                        lines.append(f"- **Calculation**: {_md_plain(info['calculation'])}")

        relationships = rels.get("relationships", [])
        if relationships and isinstance(relationships, list):
            lines.append("\n## Relationships")
            for rel in relationships:
                if isinstance(rel, dict) and rel.get("table"):
                    desc = _md_inline(rel.get("description", ""))
                    lines.append(
                        f"- **{_md_inline(rel['table'])}** ({_md_inline(rel.get('type', ''))}) "
                        f"via `{_md_code_span(rel.get('join_key', ''))}` — {desc}"
                    )
    elif isinstance(rels, list) and rels:
        lines.append("\n## Relationships")
        for rel in rels:
            if isinstance(rel, dict) and rel.get("table"):
                desc = _md_inline(rel.get("description", ""))
                lines.append(
                    f"- **{_md_inline(rel['table'])}** ({_md_inline(rel.get('type', ''))}) "
                    f"via `{_md_code_span(rel.get('join_key', ''))}` — {desc}"
                )
            elif isinstance(rel, dict):
                lines.append(f"- {_md_inline(str(rel))}")
            else:
                lines.append(f"- {_md_inline(rel)}")

    dq = data.get("data_quality")
    if not isinstance(dq, dict):
        dq = {}
    if dq:
        dq_lines: list[str] = []
        nested = dq.get("data_quality")
        q = nested if isinstance(nested, dict) and nested else dq

        comp = q.get("completeness", {})
        if isinstance(comp, dict) and comp.get("overall"):
            dq_lines.append(f"**Overall completeness**: {_md_plain(comp['overall'])}")
        issues = q.get("known_issues", [])
        if isinstance(issues, list) and issues:
            dq_lines.append("\n### Known Issues")
            for issue in issues:
                if isinstance(issue, dict) and issue.get("issue"):
                    dq_lines.append(
                        f"- **{_md_plain(issue['issue'])}**: {_md_plain(issue.get('description', ''))}"
                    )

        rules = dq.get("business_rules", [])
        if isinstance(rules, list) and rules:
            dq_lines.append("\n### Business Rules")
            for rule in rules:
                if isinstance(rule, dict) and rule.get("rule"):
                    dq_lines.append(
                        f"- **{_md_plain(rule['rule'])}**: {_md_plain(rule.get('logic', ''))}"
                    )

        if dq_lines:
            lines.append("\n## Data Quality")
            lines.extend(dq_lines)

    meta = data.get("metadata")
    if not isinstance(meta, dict):
        meta = {}
    if meta:
        inner = meta.get("metadata")
        md_inner = inner if isinstance(inner, dict) and inner else {}
        pk = md_inner.get("primary_key") or meta.get("primary_key")
        own = md_inner.get("ownership") if isinstance(md_inner.get("ownership"), dict) else {}
        if not own.get("data_owner") and isinstance(meta.get("ownership"), dict):
            own = meta["ownership"]

        meta_lines: list[str] = []
        if pk:
            meta_lines.append(f"- **Primary key**: `{_md_code_span(pk)}`")
        if isinstance(own, dict) and own.get("data_owner"):
            meta_lines.append(f"- **Owner**: {_md_plain(own['data_owner'])}")

        if meta_lines:
            lines.append("\n## Metadata")
            lines.extend(meta_lines)

    tags = meta.get("tags", [])
    if tags:
        lines.append(f"\n**Tags**: {', '.join(_md_plain(t) for t in tags)}")

    return "\n".join(lines)


def _genie_to_md(data: dict) -> str:
    """Convert Genie space YAML to markdown."""
    lines = []

    identity = data.get("space_identity", {})
    lines.append(f"# {identity.get('space_name', 'Genie Space')}")
    if identity.get("purpose"):
        lines.append(f"\n{identity['purpose']}")
    audience = identity.get("audience", [])
    if audience:
        lines.append(f"\n**Audience**: {', '.join(audience)}")

    tables = data.get("tables", [])
    if tables:
        lines.append("\n## Tables")
        for t in tables:
            if isinstance(t, dict):
                lines.append(f"- `{t.get('catalog', '')}.{t.get('schema', '')}.{t.get('name', '')}`")

    exprs = data.get("sql_expressions", [])
    if exprs and isinstance(exprs, list):
        lines.append("\n## SQL Expressions")
        for e in exprs:
            if isinstance(e, dict) and e.get("name"):
                lines.append(f"\n### {e['name']} ({e.get('category', '')})")
                lines.append(f"{e.get('description', '')}")
                lines.append(f"```sql\n{e.get('sql', '')}\n```")

    instructions = data.get("query_instructions", [])
    if instructions and isinstance(instructions, list):
        lines.append("\n## Query Instructions")
        for instr in instructions:
            if isinstance(instr, dict) and instr.get("scenario"):
                lines.append(f"\n### {instr['scenario']}")
                lines.append(str(instr.get("instruction", "")))

    examples = data.get("example_queries", [])
    if examples and isinstance(examples, list):
        lines.append("\n## Example Queries")
        for ex in examples:
            if isinstance(ex, dict) and ex.get("prompt"):
                lines.append(f"\n### {ex['prompt']}")
                lines.append(f"```sql\n{ex.get('sql', '')}\n```")

    rules = data.get("clarification_rules", [])
    if rules and isinstance(rules, list):
        lines.append("\n## Clarification Rules")
        for rule in rules:
            if isinstance(rule, dict) and rule.get("trigger_condition"):
                lines.append(f"\n**When**: {rule['trigger_condition']}")
                lines.append(f"**Ask**: {rule.get('clarification_question', '')}")

    ctx = data.get("space_context", {})
    if ctx and isinstance(ctx, dict):
        lines.append("\n## Space Context")
        for area in ctx.get("focus_areas", []):
            lines.append(f"- {area}")

    return "\n".join(lines)


def _generic_to_md(data: dict) -> str:
    """Fallback: render YAML as a code block."""
    return f"```yaml\n{yaml.dump(data, default_flow_style=False)}\n```"
