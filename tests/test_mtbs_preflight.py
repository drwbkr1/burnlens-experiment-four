from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "scripts" / "enumerate_mtbs_preflight.py"
SPEC = importlib.util.spec_from_file_location("enumerate_mtbs_preflight", MODULE_PATH)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class MtbsPreflightTests(unittest.TestCase):
    def test_identifier_normalization_is_exact_and_case_insensitive(self) -> None:
        self.assertEqual(
            MODULE.normalize_identifier("{a1b2-c3}"),
            "A1B2-C3",
        )
        self.assertIsNone(MODULE.normalize_identifier(None))

    def test_name_normalization_is_bounded(self) -> None:
        self.assertEqual(MODULE.normalize_name("  Grandview-0558 / OD "), "GRANDVIEW 0558 OD")

    def test_only_reviewed_mtbs_fields_are_opened(self) -> None:
        self.assertIn("Event_ID", MODULE.ADMITTED_FIELDS)
        self.assertNotIn("dNBR_offst", MODULE.ADMITTED_FIELDS)
        self.assertNotIn("High_T", MODULE.ADMITTED_FIELDS)


if __name__ == "__main__":
    unittest.main()
