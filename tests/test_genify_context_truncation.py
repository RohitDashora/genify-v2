"""context_truncation config + context_text helpers."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

GENIFY_ROOT = Path(__file__).resolve().parents[1] / "src" / "genify"
if str(GENIFY_ROOT) not in sys.path:
    sys.path.insert(0, str(GENIFY_ROOT))

from backend.config import _build_config  # noqa: E402
from backend.context_text import tail_chars, truncate_chars  # noqa: E402


class TestContextTextHelpers(unittest.TestCase):
    def test_truncate_chars_unlimited_when_non_positive(self):
        long = "a" * 100
        self.assertEqual(truncate_chars(long, 0), long)
        self.assertEqual(truncate_chars(long, -1), long)

    def test_truncate_chars_suffix(self):
        self.assertIn("(truncated)", truncate_chars("hello world", 5))

    def test_tail_chars_unlimited_when_non_positive(self):
        long = "a" * 100
        self.assertEqual(tail_chars(long, 0), long)

    def test_tail_chars(self):
        self.assertEqual(tail_chars("abcdefghij", 4), "ghij")


class TestContextTruncationConfig(unittest.TestCase):
    def test_yaml_defaults_match_previous_hardcoded(self):
        cfg = _build_config({})
        ct = cfg.context_truncation
        self.assertEqual(ct.planning_chars_per_key, 2000)
        self.assertEqual(ct.executor_section_chars_per_key, 2000)
        self.assertEqual(ct.prior_yaml_tail_chars, 3000)
        self.assertEqual(ct.interactive_known_data_chars, 2000)

    def test_yaml_overrides(self):
        raw = {
            "config": {
                "context_truncation": {
                    "planning_chars_per_key": 4096,
                    "prior_yaml_tail_chars": 8000,
                }
            }
        }
        ct = _build_config(raw).context_truncation
        self.assertEqual(ct.planning_chars_per_key, 4096)
        self.assertEqual(ct.prior_yaml_tail_chars, 8000)
        self.assertEqual(ct.executor_section_chars_per_key, 2000)


if __name__ == "__main__":
    unittest.main()
