"""Unit tests for canonical YAML section merge."""
import pytest

from backend.agent.yaml_merge import (
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
