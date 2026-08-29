"""Tests for the exact approved literal-encoding amendment."""

from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "scripts" / "validate_literal_encoding_amendment.py"
SPEC = importlib.util.spec_from_file_location("validate_literal_encoding_amendment", MODULE_PATH)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class LiteralEncodingAmendmentTests(unittest.TestCase):
    def test_exact_approved_amendment_passes(self) -> None:
        self.assertEqual([], MODULE.validate())

    def test_only_exact_state_pairs_are_frozen(self) -> None:
        amendment = MODULE._load(MODULE.AMENDMENT)
        state = amendment["exact_source_representation_mappings"]["state"]
        self.assertEqual(
            [
                {"canonical": "ID", "wfigs": "US-ID"},
                {"canonical": "OR", "wfigs": "US-OR"},
                {"canonical": "WA", "wfigs": "US-WA"},
            ],
            state["allowed_exact_pairs"],
        )
        self.assertFalse(state["other_alias_prefix_name_or_fallback_mapping_allowed"])


if __name__ == "__main__":
    unittest.main()
