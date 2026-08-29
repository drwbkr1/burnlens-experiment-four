"""Structural tests for the exact WFIGS snapshot contract."""

from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "scripts" / "capture_wfigs_snapshot.py"
SPEC = importlib.util.spec_from_file_location("capture_wfigs_snapshot", MODULE_PATH)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class WfigsSnapshotTests(unittest.TestCase):
    def test_query_is_exact_reviewed_window_and_prefixed_states(self) -> None:
        self.assertIn("2021-01-01", MODULE.STATE_WHERE)
        self.assertIn("2023-01-01", MODULE.STATE_WHERE)
        self.assertIn("('US-ID','US-OR','US-WA')", MODULE.STATE_WHERE)
        self.assertNotIn("('ID','OR','WA')", MODULE.STATE_WHERE)

    def test_query_does_not_pre_filter_incident_type(self) -> None:
        self.assertNotIn("IncidentTypeCategory", MODULE.STATE_WHERE)

    def test_allowlist_is_exact_and_excludes_denied_categories(self) -> None:
        self.assertEqual(30, len(MODULE.ADMITTED_FIELDS))
        self.assertEqual(len(MODULE.ADMITTED_FIELDS), len(set(MODULE.ADMITTED_FIELDS)))
        self.assertIn("attr_UniqueFireIdentifier", MODULE.ADMITTED_FIELDS)
        self.assertIn("attr_FFReportApprovedDate", MODULE.ADMITTED_FIELDS)
        self.assertNotIn("attr_FireCause", MODULE.ADMITTED_FIELDS)
        self.assertNotIn("attr_EstimatedCostToDate", MODULE.ADMITTED_FIELDS)


if __name__ == "__main__":
    unittest.main()
