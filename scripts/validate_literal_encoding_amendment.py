"""Validate the exact approved M1-U005 representation-only amendment."""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
AMENDMENT = ROOT / "records" / "decisions" / "E4-M1-LITERAL-ENCODING-AMENDMENT-2026-001.json"
EVIDENCE = ROOT / "records" / "evidence" / "E4-EV-0010-LITERAL-ENCODING-AMENDMENT-APPROVAL-2026-001.json"
PROPOSAL = ROOT / "records" / "decisions" / "E4-M1-LITERAL-ENCODING-AMENDMENT-PROPOSAL-2026-001.json"

EXPECTED = {
    "bundle": "3ff69ce031313db2010706cf481a63c24d45a88cfb23c2f6bb7a38d96f7b972a",
    "contract": "378223d8cd52ea1df88fc001afdffcdbbca3a0db4b35cc6f5e21e9d9cbe434a9",
    "response": "8b19e3002fee9df9349e88932474b17e4ba061e6348930efe6d5ed1feaad2fcc",
    "receipt": "e5a4e5a159743378c4a559be1bfa1b755fd08732f2ffffa892c9c0c4d191992f",
    "reconciliation": "ae77d66e31ecb605ff3feaddbfe9bd06f73107748eb691d4f2fa3044b62741cf",
}


def _load(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path.name} is not an object")
    return value


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def validate() -> list[str]:
    errors: list[str] = []
    amendment = _load(AMENDMENT)
    evidence = _load(EVIDENCE)
    review = amendment.get("owner_review", {})
    if amendment.get("status") != "frozen_approved":
        errors.append("amendment is not frozen_approved")
    if amendment.get("proposal_sha256") != _sha256(PROPOSAL):
        errors.append("amendment proposal hash changed")
    for key, expected in EXPECTED.items():
        field = {
            "bundle": "bundle_sha256",
            "contract": "contract_sha256",
            "response": "locked_response_sha256",
            "receipt": "lock_receipt_sha256",
            "reconciliation": "reconciliation_sha256",
        }[key]
        if review.get(field) != expected:
            errors.append(f"owner review {field} changed")
    if review.get("decision_counts") != {"approve": 1, "reject": 0, "uncertain": 0}:
        errors.append("amendment does not bind exactly one approval")
    if review.get("notes_included") is not False:
        errors.append("public amendment must omit private notes")
    if review.get("raw_private_artifacts_committed") is not False:
        errors.append("public amendment claims private artifacts were committed")

    mappings = amendment.get("exact_source_representation_mappings", {})
    state = mappings.get("state", {})
    expected_pairs = [
        {"canonical": "ID", "wfigs": "US-ID"},
        {"canonical": "OR", "wfigs": "US-OR"},
        {"canonical": "WA", "wfigs": "US-WA"},
    ]
    if state.get("canonical_values") != ["ID", "OR", "WA"]:
        errors.append("canonical state values changed")
    if state.get("allowed_exact_pairs") != expected_pairs:
        errors.append("exact state pairs changed")
    if state.get("other_alias_prefix_name_or_fallback_mapping_allowed") is not False:
        errors.append("state fallback mapping was enabled")
    incident = mappings.get("incident_type", {})
    if incident != {
        "canonical_value": "Wildfire",
        "mtbs_exact_value": "Wildfire",
        "wfigs_exact_value": "WF",
        "other_alias_or_fallback_mapping_allowed": False,
    }:
        errors.append("incident-type mapping changed")
    if "unknown and not eligible" not in str(mappings.get("conflict_rule", "")):
        errors.append("fail-closed conflict rule changed")

    evidence_review = evidence.get("owner_review", {})
    if evidence.get("disposition") != "PASS_protocol_amendment_only":
        errors.append("evidence disposition changed")
    if evidence_review.get("decision_counts") != review.get("decision_counts"):
        errors.append("evidence decision counts do not match amendment")
    if evidence_review.get("human_decisions_fabricated") is not False:
        errors.append("evidence permits fabricated decisions")
    unchanged = evidence.get("unchanged_boundary", {})
    if any(
        unchanged.get(key) is not False
        for key in (
            "eligibility_thresholds_changed",
            "candidate_years_changed",
            "candidate_states_changed",
            "prior_exclusions_changed",
            "maturity_ecology_hls_duplicate_or_capacity_rules_changed",
        )
    ):
        errors.append("an unchanged scientific rule was marked changed")
    if unchanged.get("candidate_eligibility_decisions_at_review") != 0:
        errors.append("eligibility decisions existed at review")
    return errors


def main() -> int:
    try:
        errors = validate()
    except (OSError, UnicodeError, json.JSONDecodeError, ValueError) as exc:
        errors = [str(exc)]
    if errors:
        print("Literal encoding amendment: FAIL")
        for error in errors:
            print(f"- {error}")
        return 1
    print("Literal encoding amendment: PASS (one exact approval; mappings frozen)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
