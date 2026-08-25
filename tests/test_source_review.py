from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "scripts" / "validate_source_review.py"
SPEC = importlib.util.spec_from_file_location("validate_source_review", MODULE_PATH)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class SourceReviewTests(unittest.TestCase):
    def test_review_package_is_consistent_and_pre_adoption(self) -> None:
        self.assertEqual(MODULE.validate(), [])

    def test_expected_source_set_is_exact(self) -> None:
        self.assertEqual(len(MODULE.EXPECTED_SOURCES), 5)
        self.assertIn("USGS-MTBS-PERIMETERS-V12", MODULE.EXPECTED_SOURCES)
        self.assertIn("NIFC-WFIGS-PERIMETERS-5E72B169", MODULE.EXPECTED_SOURCES)

    def test_prohibited_mtbs_fields_are_explicit(self) -> None:
        self.assertIn("dnbr_offst", MODULE.PROHIBITED_SELECTION_TERMS)
        self.assertIn("high_t", MODULE.PROHIBITED_SELECTION_TERMS)
        self.assertIn("comment", MODULE.PROHIBITED_SELECTION_TERMS)


if __name__ == "__main__":
    unittest.main()
