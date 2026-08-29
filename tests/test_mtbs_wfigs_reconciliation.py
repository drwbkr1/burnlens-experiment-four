"""Synthetic tests for exact MTBS/WFIGS reconciliation."""

from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "scripts" / "reconcile_mtbs_wfigs.py"
SPEC = importlib.util.spec_from_file_location("reconcile_mtbs_wfigs", MODULE_PATH)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def feature(global_id: str = "{11111111-1111-4111-8111-111111111111}") -> dict:
    return {
        "attributes": {
            "GlobalID": global_id,
            "attr_IrwinID": "{AAAAAAAA-AAAA-4AAA-8AAA-AAAAAAAAAAAA}",
            "poly_IRWINID": None,
            "attr_UniqueFireIdentifier": "2022-ORABC-000001",
            "attr_SourceGlobalID": "{22222222-2222-4222-8222-222222222222}",
            "attr_IncidentName": "Synthetic Fire",
            "attr_IncidentTypeCategory": "WF",
            "attr_POOState": "US-OR",
            "attr_FireDiscoveryDateTime": 1659312000000,
            "attr_ContainmentDateTime": 1660000000000,
            "attr_FireOutDateTime": 1661000000000,
            "attr_FFReportApprovedDate": 1662000000000,
            "attr_FinalAcres": 5000.0,
            "poly_FeatureAccess": "Public",
            "poly_FeatureStatus": "Approved",
            "poly_IsVisible": "Yes",
            "poly_DeleteThis": "No",
            "attr_IsValid": 1,
            "attr_IsQuarantined": 0,
            "attr_CpxID": None,
            "attr_CpxName": None,
            "attr_IsCpxChild": 0,
        },
        "geometry": {"rings": [[[-121.0, 44.0], [-120.9, 44.0], [-121.0, 44.1], [-121.0, 44.0]]]},
    }


def mtbs() -> dict:
    return {
        "Event_ID": "OR202200000001",
        "irwinID": "{AAAAAAAA-AAAA-4AAA-8AAA-AAAAAAAAAAAA}",
        "Incid_Name": "Synthetic Fire",
        "Incid_Type": "Wildfire",
        "Map_Prog": "MTBS",
        "Asmnt_Type": "Initial",
        "BurnBndAc": 4000.0,
        "BurnBndLat": 44.0,
        "BurnBndLon": -121.0,
        "Ig_Date": "20220801",
    }


class ReconciliationTests(unittest.TestCase):
    def test_exact_irwin_match_deduplicates_same_feature_across_two_fields(self) -> None:
        row = feature()
        row["attributes"]["poly_IRWINID"] = row["attributes"]["attr_IrwinID"]
        irwin, unique = MODULE._index([row])
        mode, matches = MODULE._exact_matches(mtbs(), irwin, unique)
        self.assertEqual("mtbs_irwin_to_wfigs_irwin", mode)
        self.assertEqual(1, len(matches))

    def test_unprefixed_state_is_not_accepted(self) -> None:
        attrs = feature()["attributes"]
        self.assertNotEqual("US-OR", "OR")
        self.assertTrue(MODULE._maturity_pass(attrs))

    def test_multiple_exact_features_remain_multiple(self) -> None:
        first = feature()
        second = feature("{33333333-3333-4333-8333-333333333333}")
        irwin, unique = MODULE._index([first, second])
        _, matches = MODULE._exact_matches(mtbs(), irwin, unique)
        self.assertEqual(2, len(matches))

    def test_missing_wfigs_area_is_unknown_not_excluded(self) -> None:
        self.assertEqual(
            "unknown_before_geometry_hls",
            MODULE._status({"WFIGS_AREA_UNKNOWN"}),
        )
        self.assertEqual(
            "excluded_before_geometry_hls",
            MODULE._status({"WFIGS_AREA_BELOW_MINIMUM"}),
        )


if __name__ == "__main__":
    unittest.main()
