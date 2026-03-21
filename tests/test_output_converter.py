"""Tests for yaml_to_markdown (table_comment unwrap, flat shapes, escaping)."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

import yaml

GENIFY_ROOT = Path(__file__).resolve().parents[1] / "src" / "genify"
if str(GENIFY_ROOT) not in sys.path:
    sys.path.insert(0, str(GENIFY_ROOT))

from backend.llm import output_converter as oc  # noqa: E402


class TestUnwrapTableComment(unittest.TestCase):
    def test_fqn_wrapped_yaml_produces_title_and_core(self):
        inner = {
            "table_identity": {
                "catalog": "c",
                "schema": "s",
                "name": "t",
                "business_name": "My Table",
            },
            "core_description": {"description": "Hello world"},
        }
        wrapped = {"c.s.t": inner}
        md = oc.yaml_to_markdown(yaml.dump(wrapped, default_flow_style=False), "table_comment")
        self.assertIn("# My Table", md)
        self.assertIn("## Description", md)
        self.assertIn("Hello world", md)
        self.assertIn("**Table**:", md)

    def test_multi_key_dict_not_unwrapped(self):
        data = {
            "table_identity": {"catalog": "a", "schema": "b", "name": "c"},
            "extra": {},
        }
        md = oc.yaml_to_markdown(yaml.dump(data, default_flow_style=False), "table_comment")
        self.assertIn("# a.b.c", md)


class TestFlatDataQuality(unittest.TestCase):
    def test_known_issues_without_nested_data_quality(self):
        doc = {
            "table_identity": {"catalog": "c", "schema": "s", "name": "t"},
            "data_quality": {
                "known_issues": [
                    {"issue": "Stale data", "description": "Needs refresh"},
                ],
            },
        }
        md = oc.yaml_to_markdown(yaml.dump(doc, default_flow_style=False), "table_comment")
        self.assertIn("## Data Quality", md)
        self.assertIn("### Known Issues", md)
        self.assertIn("Stale data", md)
        self.assertIn("Needs refresh", md)

    def test_empty_nested_data_quality_no_heading(self):
        doc = {
            "table_identity": {"catalog": "c", "schema": "s", "name": "t"},
            "data_quality": {"data_quality": {}},
        }
        md = oc.yaml_to_markdown(yaml.dump(doc, default_flow_style=False), "table_comment")
        self.assertNotIn("## Data Quality", md)


class TestMetadataFlatPrimaryKey(unittest.TestCase):
    def test_primary_key_on_metadata_root(self):
        doc = {
            "table_identity": {"catalog": "c", "schema": "s", "name": "t"},
            "metadata": {"primary_key": "id_col", "tags": ["pii"]},
        }
        md = oc.yaml_to_markdown(yaml.dump(doc, default_flow_style=False), "table_comment")
        self.assertIn("## Metadata", md)
        self.assertIn("id_col", md)
        self.assertIn("**Tags**", md)
        self.assertIn("pii", md)


class TestRelationshipEscaping(unittest.TestCase):
    def test_backticks_in_description_sanitized(self):
        doc = {
            "table_identity": {"catalog": "c", "schema": "s", "name": "t"},
            "relationships": {
                "relationships": [
                    {
                        "table": "other.tbl",
                        "type": "many_to_one",
                        "join_key": "user_id",
                        "description": "Join on `user_id` and `session_id` please",
                    },
                ],
            },
        }
        md = oc.yaml_to_markdown(yaml.dump(doc, default_flow_style=False), "table_comment")
        self.assertIn("via `user_id`", md)
        self.assertIn("Join on 'user_id' and 'session_id' please", md)
        self.assertNotIn("`session_id`", md)


class TestUnwrapHelper(unittest.TestCase):
    def test_unwrap_only_single_fqn_shaped_inner(self):
        inner = {"table_identity": {"catalog": "x", "schema": "y", "name": "z"}}
        out = oc._unwrap_table_comment_dict({"a.b.c": inner})
        self.assertEqual(out, inner)

    def test_unwrap_leaves_multi_key(self):
        d = {"a": 1, "b": 2}
        self.assertIs(oc._unwrap_table_comment_dict(d), d)


if __name__ == "__main__":
    unittest.main()
