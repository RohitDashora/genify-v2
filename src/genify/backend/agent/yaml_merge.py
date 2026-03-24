"""Canonical YAML merge for section fragments into one document.

Each fragment must have exactly one top-level key matching ``section_key``.
"""
from __future__ import annotations

import copy
import logging
from typing import Any

import yaml

logger = logging.getLogger(__name__)


def load_yaml_document(yaml_str: str) -> dict[str, Any]:
    """Parse session YAML; on failure return {} and let caller trace."""
    if not yaml_str or not yaml_str.strip():
        return {}
    try:
        data = yaml.safe_load(yaml_str)
        if data is None:
            return {}
        if not isinstance(data, dict):
            return {}
        return data
    except yaml.YAMLError as e:
        logger.warning("generated_yaml parse failed, treating as empty: %s", e)
        return {}


class _LiteralMultilineDumper(yaml.SafeDumper):
    """SafeDumper that prefers ``|`` for multi-line string scalars when enabled."""


def _represent_str_multiline(dumper: yaml.Dumper, data: str) -> yaml.Node:
    if "\n" in data:
        return dumper.represent_scalar("tag:yaml.org,2002:str", data, style="|")
    return dumper.represent_scalar("tag:yaml.org,2002:str", data)


_LiteralMultilineDumper.add_representer(str, _represent_str_multiline)


def dump_yaml_document(
    doc: dict[str, Any],
    *,
    width: int | None = None,
    literal_multiline: bool = False,
) -> str:
    """Stable YAML serialization for persisted/generated_yaml.

    ``width`` mirrors PyYAML's wrap width (default 80 when unset — matches historical behavior).
    ``literal_multiline`` uses block style ``|`` for strings containing newlines.
    """
    dump_kw: dict[str, Any] = {
        "default_flow_style": False,
        "allow_unicode": True,
        "sort_keys": False,
    }
    if width is not None:
        dump_kw["width"] = width
    if literal_multiline:
        return yaml.dump(doc, Dumper=_LiteralMultilineDumper, **dump_kw)
    return yaml.dump(doc, **dump_kw)


def format_yaml_for_persistence(
    yaml_str: str,
    *,
    enabled: bool,
    dump_width: int,
    use_literal_blocks: bool,
) -> tuple[str, bool, bool]:
    """Parse → re-dump for readable persisted YAML. Fail-open: bad input returns original.

    Returns ``(yaml_out, text_changed, parse_succeeded)``.
    ``parse_succeeded`` is False when the input was non-trivial but could not be round-tripped
    (parse error, non-dict root, or empty mapping ambiguity); used for trace without noise on
    byte-identical re-dumps.
    """
    if not enabled:
        return yaml_str, False, True
    if not yaml_str or not str(yaml_str).strip():
        return yaml_str, False, True
    s = str(yaml_str)
    try:
        data = yaml.safe_load(s)
    except yaml.YAMLError as e:
        logger.warning("format_yaml_for_persistence: parse failed, keeping original: %s", e)
        return yaml_str, False, False
    if data is None:
        data = {}
    if not isinstance(data, dict):
        logger.warning("format_yaml_for_persistence: root not a mapping, keeping original")
        return yaml_str, False, False
    if not data and s.strip():
        logger.debug("format_yaml_for_persistence: empty mapping for non-empty input, keeping original")
        return yaml_str, False, False
    out = dump_yaml_document(
        data,
        width=dump_width,
        literal_multiline=use_literal_blocks,
    )
    if out == s:
        return yaml_str, False, True
    return out, True, True


def _fragment_to_dict(fragment_yaml: str) -> tuple[dict[str, Any] | None, str | None]:
    if not fragment_yaml or not str(fragment_yaml).strip():
        return {}, None
    try:
        frag = yaml.safe_load(fragment_yaml)
    except yaml.YAMLError as e:
        return None, f"Invalid YAML fragment: {e}"
    if frag is None:
        return {}, None
    if not isinstance(frag, dict):
        return None, "Section YAML must be a mapping (object) at the top level"
    keys = [k for k in frag.keys() if k is not None]
    if len(keys) != 1:
        return None, f"Expected exactly one top-level key, got {len(keys)}: {keys[:5]}"
    return frag, None


def _strip_nested(value: Any, allowed: Any) -> Any:
    """Recursively drop keys not present in ``allowed`` template subtree."""
    if allowed is None or not isinstance(allowed, dict):
        return value
    if not isinstance(value, dict):
        return value
    out: dict[str, Any] = {}
    for k, v in value.items():
        if k not in allowed:
            continue
        sub = allowed[k]
        if isinstance(v, dict) and isinstance(sub, dict):
            out[k] = _strip_nested(v, sub)
        else:
            out[k] = copy.deepcopy(v)
    return out


def merge_section_fragment(
    base_doc: dict[str, Any],
    section_key: str,
    fragment_yaml: str,
    *,
    section_template: Any | None = None,
    nested_validation: str = "strip",
) -> tuple[dict[str, Any] | None, str | None]:
    """Merge one section fragment into ``base_doc`` (mutates a copy).

    ``nested_validation``: ``off`` | ``strip`` (strip removes keys not in template subtree).

    Returns ``(new_doc, error_message)``.
    """
    frag, err = _fragment_to_dict(fragment_yaml)
    if err:
        return None, err
    if frag is not None and not frag:
        out = copy.deepcopy(base_doc)
        if section_key in out:
            del out[section_key]
        return out, None

    assert frag is not None
    only_key = next(iter(frag.keys()))
    if only_key != section_key:
        return (
            None,
            f"Top-level key must be '{section_key}', got '{only_key}'",
        )

    out = copy.deepcopy(base_doc)
    val = copy.deepcopy(frag[section_key])

    if nested_validation == "strip" and isinstance(section_template, dict) and isinstance(val, dict):
        val = _strip_nested(val, section_template)

    out[section_key] = val
    return out, None


def merge_section_fragment_or_skip(
    base_doc: dict[str, Any],
    section_key: str,
    fragment_yaml: str,
    *,
    section_template: Any | None = None,
    nested_validation: str = "strip",
) -> tuple[dict[str, Any], bool]:
    """Merge or insert a placeholder on hard failure. Returns (doc, skipped)."""
    merged, err = merge_section_fragment(
        base_doc,
        section_key,
        fragment_yaml,
        section_template=section_template,
        nested_validation=nested_validation,
    )
    if merged is not None:
        return merged, False

    logger.warning("merge failed for %s, skipping section: %s", section_key, err)
    out = copy.deepcopy(base_doc)
    out[section_key] = {
        "NEEDS_CLARIFICATION": f"Section skipped — merge failed: {err}",
    }
    return out, True


def merge_from_strings(
    base_yaml: str,
    section_key: str,
    fragment_yaml: str,
    *,
    section_template: Any | None = None,
    nested_validation: str = "strip",
) -> tuple[str | None, str | None]:
    """Merge using string base; returns (merged_yaml, error)."""
    base_doc = load_yaml_document(base_yaml)
    merged, err = merge_section_fragment(
        base_doc,
        section_key,
        fragment_yaml,
        section_template=section_template,
        nested_validation=nested_validation,
    )
    if merged is None:
        return None, err
    return dump_yaml_document(merged), None


def remove_section_key(base_yaml: str, section_key: str) -> str:
    """Remove ``section_key`` from merged document (for retry-section)."""
    doc = load_yaml_document(base_yaml)
    if section_key in doc:
        del doc[section_key]
    return dump_yaml_document(doc)
