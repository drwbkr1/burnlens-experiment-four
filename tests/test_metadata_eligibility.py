"""Synthetic tests for metadata-only candidate eligibility."""

from __future__ import annotations

import copy
import hashlib
import json
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from burnlens_e4.metadata_eligibility import (  # noqa: E402
    candidate_id_from_source,
    evaluate,
)


PRIOR_PATH = (
    ROOT
    / "records"
    / "metadata"
    / "EXPERIMENT-FOUR-PRIOR-EVENT-EXCLUSION-MANIFEST-2026-001.json"
)
PRIOR_BYTES = PRIOR_PATH.read_bytes()
PRIOR = json.loads(PRIOR_BYTES)
PRIOR_SHA256 = hashlib.sha256(PRIOR_BYTES).hexdigest()


def frozen_profile() -> dict:
    return {
        "schema_version": "1.0",
        "profile_id": "E4-ELIGIBILITY-SYNTHETIC-TEST",
        "status": "frozen",
        "jurisdictions": ["ID", "OR", "WA"],
        "year_start": 2017,
        "year_end": 2024,
        "minimum_area_acres": 100.0,
        "maximum_area_acres": None,
        "latest_eligible_ignition_date": "2024-12-31",
        "accepted_incident_types": ["Wildfire"],
        "accepted_perimeter_statuses": ["final"],
        "ecology_rule": {"mode": "any-recorded", "admitted_codes": []},
        "required_imagery_metadata_status": "available",
        "required_reference_metadata_status": "available",
        "required_rights_status": "admitted",
        "prior_exclusion_manifest_sha256": PRIOR_SHA256,
        "unknown_policy": "unknown-is-not-eligible",
    }


def candidate() -> dict:
    source = {
        "source_id": "synthetic-source",
        "source_revision": "synthetic-revision-1",
        "source_row_id": "synthetic-row-1",
        "retrieved_at_utc": "2026-08-25T00:00:00Z",
        "row_sha256": "0" * 64,
    }
    return {
        "schema_version": "1.0",
        "candidate_id": candidate_id_from_source(source),
        "source_record": source,
        "identity": {
            "canonical_name": "Synthetic Creek",
            "normalized_name": "SYNTHETIC CREEK",
            "incident_year": 2024,
            "jurisdiction": "OR",
            "unique_fire_identifier": "2024-ORXXX-000001",
            "source_event_id": "{11111111-1111-4111-8111-111111111111}",
            "source_global_id": "22222222-2222-4222-8222-222222222222",
            "identity_status": "exact",
            "aliases": [],
        },
        "fire": {
            "incident_type": "Wildfire",
            "ignition_at": "2024-08-01T00:00:00Z",
            "containment_at": "2024-08-15T00:00:00Z",
            "fire_out_at": "2024-09-01T00:00:00Z",
            "final_report_approved_at": "2025-01-01T00:00:00Z",
            "perimeter_effective_at": "2025-01-01T00:00:00Z",
            "area_acres": 5000.0,
            "area_source": "synthetic",
            "perimeter_status": "final",
        },
        "geography": {
            "centroid_lon": -121.0,
            "centroid_lat": 44.0,
            "ecology_codes": ["SYNTHETIC-ECOLOGY"],
            "geometry_fingerprint": "3" * 64,
        },
        "availability": {
            "imagery_metadata_status": "available",
            "reference_metadata_status": "available",
            "rights_status": "admitted",
            "imagery_programs": ["synthetic-imagery"],
            "reference_programs": ["synthetic-reference"],
        },
        "overlap": {
            "prior_event_match_status": "no_match",
            "candidate_duplicate_status": "unique",
            "matched_prior_exclusion_ids": [],
            "matched_candidate_ids": [],
        },
    }


class MetadataEligibilityTests(unittest.TestCase):
    def evaluate(self, record: dict, profile: dict | None = None) -> dict:
        return evaluate(record, profile or frozen_profile(), PRIOR, PRIOR_SHA256)

    def test_complete_synthetic_candidate_is_eligible(self) -> None:
        result = self.evaluate(candidate())
        self.assertEqual("eligible", result["status"])
        self.assertEqual([], result["reason_codes"])

    def test_proposed_profile_can_never_produce_eligibility(self) -> None:
        proposal_path = (
            ROOT
            / "records"
            / "metadata"
            / "EXPERIMENT-FOUR-ELIGIBILITY-PROFILE-PROPOSAL-2026-001.json"
        )
        proposal = json.loads(proposal_path.read_text(encoding="utf-8"))
        result = self.evaluate(candidate(), proposal)
        self.assertEqual("invalid", result["status"])
        self.assertEqual(["PROFILE_NOT_FROZEN"], result["reason_codes"])

    def test_exact_prior_identifier_is_excluded(self) -> None:
        record = candidate()
        record["identity"]["unique_fire_identifier"] = "2022-MTBRF-022131"
        result = self.evaluate(record)
        self.assertEqual("excluded", result["status"])
        self.assertIn("PRIOR_EVENT_EXACT_MATCH", result["reason_codes"])

    def test_experiment_one_name_year_fallback_is_excluded(self) -> None:
        record = candidate()
        record["identity"].update(
            {
                "canonical_name": "Grandview 0558 OD",
                "normalized_name": "GRANDVIEW 0558 OD",
                "incident_year": 2021,
            }
        )
        result = self.evaluate(record)
        self.assertEqual("excluded", result["status"])
        self.assertIn("PRIOR_EVENT_NAME_YEAR_MATCH", result["reason_codes"])

    def test_missing_required_evidence_is_unknown(self) -> None:
        record = candidate()
        record["fire"]["area_acres"] = None
        record["availability"]["reference_metadata_status"] = "not_checked"
        result = self.evaluate(record)
        self.assertEqual("unknown", result["status"])
        self.assertEqual(
            ["AREA_UNKNOWN", "REFERENCE_METADATA_UNKNOWN"],
            result["reason_codes"],
        )

    def test_exclusion_precedes_unknown_without_erasing_it(self) -> None:
        record = candidate()
        record["identity"]["jurisdiction"] = "ID"
        record["identity"]["incident_year"] = 2010
        record["availability"]["imagery_metadata_status"] = "unknown"
        result = self.evaluate(record)
        self.assertEqual("excluded", result["status"])
        self.assertEqual(
            ["YEAR_OUT_OF_RANGE", "IMAGERY_METADATA_UNKNOWN"],
            result["reason_codes"],
        )

    def test_prohibited_model_output_field_is_invalid(self) -> None:
        record = candidate()
        record["prediction"] = 0.9
        result = self.evaluate(record)
        self.assertEqual("invalid", result["status"])
        self.assertEqual(["CANDIDATE_SCHEMA_INVALID"], result["reason_codes"])

    def test_replay_is_deterministic_and_input_bound(self) -> None:
        record = candidate()
        first = self.evaluate(record)
        second = self.evaluate(copy.deepcopy(record))
        self.assertEqual(first, second)
        changed = copy.deepcopy(record)
        changed["fire"]["area_acres"] = 5001.0
        third = self.evaluate(changed)
        self.assertNotEqual(first["input_fingerprint"], third["input_fingerprint"])


if __name__ == "__main__":
    unittest.main()
