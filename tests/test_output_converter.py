"""Tests for yaml_to_markdown (unwrap, hierarchical rendering, escaping)."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import patch

import yaml

GENIFY_ROOT = Path(__file__).resolve().parents[1] / "src" / "genify"
if str(GENIFY_ROOT) not in sys.path:
    sys.path.insert(0, str(GENIFY_ROOT))

from backend.llm import output_converter as oc  # noqa: E402


def _dump_preserve_order(obj: dict) -> str:
    """Dump without sorting keys so load order matches insertion order."""
    return yaml.dump(obj, default_flow_style=False, allow_unicode=True, sort_keys=False)


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
        md = oc.yaml_to_markdown(_dump_preserve_order(wrapped), "table_comment")
        self.assertIn("Hello world", md)
        self.assertIn("My Table", md)
        self.assertIn("Core Description", md)
        self.assertIn("Table Identity", md)

    def test_multi_key_dict_not_unwrapped(self):
        data = {
            "table_identity": {"catalog": "a", "schema": "b", "name": "c"},
            "extra": {},
        }
        md = oc.yaml_to_markdown(_dump_preserve_order(data), "table_comment")
        self.assertIn("Table Identity", md)
        self.assertIn("Extra", md)
        self.assertIn("a", md)
        self.assertIn("b", md)
        self.assertIn("c", md)


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
        md = oc.yaml_to_markdown(_dump_preserve_order(doc), "table_comment")
        self.assertIn("Data Quality", md)
        self.assertIn("Stale data", md)
        self.assertIn("Needs refresh", md)

    def test_empty_nested_data_quality_still_renders_section(self):
        doc = {
            "table_identity": {"catalog": "c", "schema": "s", "name": "t"},
            "data_quality": {"data_quality": {}},
        }
        md = oc.yaml_to_markdown(_dump_preserve_order(doc), "table_comment")
        self.assertIn("Data Quality", md)
        self.assertIn("—", md)


class TestMetadataFlatPrimaryKey(unittest.TestCase):
    def test_primary_key_on_metadata_root(self):
        doc = {
            "table_identity": {"catalog": "c", "schema": "s", "name": "t"},
            "metadata": {"primary_key": "id_col", "tags": ["pii"]},
        }
        md = oc.yaml_to_markdown(_dump_preserve_order(doc), "table_comment")
        self.assertIn("Metadata", md)
        self.assertIn("id_col", md)
        self.assertIn("pii", md)
        self.assertIn("Tags", md)


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
        md = oc.yaml_to_markdown(_dump_preserve_order(doc), "table_comment")
        self.assertIn("Join on 'user_id' and 'session_id' please", md)
        self.assertIn("user_id", md)
        self.assertIn("other.tbl", md)
        self.assertNotIn("`session_id`", md)


class TestGenieHierarchical(unittest.TestCase):
    def test_sql_expressions_get_sql_fence(self):
        doc = {
            "space_identity": {"space_name": "Demo Space"},
            "sql_expressions": [
                {
                    "name": "x",
                    "category": "metric",
                    "description": "A metric",
                    "sql": "SELECT 1\nFROM t",
                },
            ],
        }
        md = oc.yaml_to_markdown(_dump_preserve_order(doc), "genie")
        self.assertIn("Demo Space", md)
        self.assertIn("Sql Expressions", md)
        self.assertIn("```sql", md)
        self.assertIn("SELECT 1", md)
        self.assertIn("FROM t", md)


class TestUnwrapHelper(unittest.TestCase):
    def test_unwrap_only_single_fqn_shaped_inner(self):
        inner = {"table_identity": {"catalog": "x", "schema": "y", "name": "z"}}
        out = oc._unwrap_table_comment_dict({"a.b.c": inner})
        self.assertEqual(out, inner)

    def test_unwrap_leaves_multi_key(self):
        d = {"a": 1, "b": 2}
        self.assertIs(oc._unwrap_table_comment_dict(d), d)


class TestSafeYamlToMarkdown(unittest.TestCase):
    def test_returns_tuple_and_ok_true_on_success(self):
        md, ok = oc.safe_yaml_to_markdown("table_identity:\n  catalog: c\n  schema: s\n  name: t\n", "table_comment")
        self.assertTrue(ok)
        self.assertIsInstance(md, str)
        self.assertGreater(len(md), 0)

    def test_never_raises_on_garbage_yaml(self):
        md, ok = oc.safe_yaml_to_markdown("this is not: [ valid", "table_comment")
        self.assertIsInstance(md, str)
        self.assertGreater(len(md), 0)

    def test_never_raises_when_yaml_to_markdown_raises(self):
        with patch.object(oc, "yaml_to_markdown", side_effect=RuntimeError("internal")):
            md, ok = oc.safe_yaml_to_markdown("x: 1", "table_comment")
        self.assertIsInstance(md, str)
        self.assertFalse(ok)
        self.assertIn("```yaml", md)


if __name__ == "__main__":
    unittest.main()
