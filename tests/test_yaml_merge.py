"""Unit tests for canonical YAML section merge."""
import pytest

import yaml

from backend.agent.yaml_merge import (
    dump_yaml_document,
    format_yaml_for_persistence,
    load_yaml_document,
    merge_from_strings,
    merge_section_fragment,
    remove_section_key,
)


def test_merge_single_key():
    base = "a:\n  x: 1\n"
    frag = "b:\n  y: 2\n"
    merged, err = merge_from_strings(base, "b", frag)
    assert err is None
    assert merged
    doc = load_yaml_document(merged)
    assert doc["a"]["x"] == 1
    assert doc["b"]["y"] == 2


def test_merge_wrong_root_key_fails():
    merged, err = merge_from_strings("", "want", "wrong:\n  z: 1\n")
    assert merged is None
    assert err and "want" in err


def test_strip_nested():
    tpl = {"keep": {}, "drop_me": "x"}
    base = {}
    frag = "sec:\n  keep: {a: 1}\n  extra: 2\n"
    doc, err = merge_section_fragment(
        base,
        "sec",
        frag,
        section_template=tpl,
        nested_validation="strip",
    )
    assert err is None
    assert "extra" not in doc["sec"]


def test_remove_section_key():
    y = "x:\n  a: 1\ny:\n  b: 2\n"
    out = remove_section_key(y, "x")
    doc = load_yaml_document(out)
    assert "x" not in doc
    assert doc["y"]["b"] == 2


def test_load_invalid_yaml_returns_empty():
    assert load_yaml_document("{unclosed") == {}


def test_format_disabled_returns_unchanged():
    raw = "a:\n  b: 1\n"
    out, changed, ok = format_yaml_for_persistence(
        raw,
        enabled=False,
        dump_width=120,
        use_literal_blocks=False,
    )
    assert out == raw
    assert changed is False
    assert ok is True


def test_format_round_trip_preserves_semantics():
    raw = "section:\n  title: Hello\n  items:\n    - x: 1\n    - x: 2\n"
    out, changed, ok = format_yaml_for_persistence(
        raw,
        enabled=True,
        dump_width=120,
        use_literal_blocks=False,
    )
    assert ok is True
    assert yaml.safe_load(out) == yaml.safe_load(raw)
    assert changed is True or out == raw


def test_format_invalid_yaml_unchanged():
    bad = "foo: bar: baz\n"
    out, changed, ok = format_yaml_for_persistence(
        bad,
        enabled=True,
        dump_width=120,
        use_literal_blocks=False,
    )
    assert out == bad
    assert changed is False
    assert ok is False


def test_format_multiline_literal_block():
    doc = {"desc": "line1\nline2"}
    raw = yaml.dump(doc, default_flow_style=False, allow_unicode=True, sort_keys=False)
    out, changed, ok = format_yaml_for_persistence(
        raw,
        enabled=True,
        dump_width=120,
        use_literal_blocks=True,
    )
    assert ok is True
    assert changed is True
    assert "|" in out
    assert yaml.safe_load(out) == doc


def test_dump_yaml_document_width_affects_wrapping():
    doc = {"a": "x" * 120}
    narrow = dump_yaml_document(doc, width=40, literal_multiline=False)
    wide = dump_yaml_document(doc, width=500, literal_multiline=False)
    assert narrow.count("\n") >= wide.count("\n")
