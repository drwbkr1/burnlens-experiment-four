"""Validate the pre-adoption Milestone 1 source and eligibility review package."""

from __future__ import annotations

import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
SOURCE_GATE = ROOT / "records" / "sources" / "EXPERIMENT-FOUR-SOURCE-GATE-ASSESSMENT-2026-001.json"
SOURCE_USE = ROOT / "records" / "sources" / "EXPERIMENT-FOUR-SOURCE-USE-PROPOSAL-2026-001.json"
PROFILE = ROOT / "records" / "metadata" / "EXPERIMENT-FOUR-ELIGIBILITY-PROFILE-PROPOSAL-2026-002.json"
PRIOR = ROOT / "records" / "metadata" / "EXPERIMENT-FOUR-PRIOR-EVENT-EXCLUSION-MANIFEST-2026-001.json"
REVIEW = ROOT / "docs" / "reviews" / "2026-08-25-m1-source-adoption-owner-review.md"
SURFACE = ROOT / "docs" / "reviews" / "e4-m1-source-adoption-review.html"

EXPECTED_SOURCES = {
    "NIFC-WFIGS-PERIMETERS-5E72B169",
    "USGS-MTBS-PERIMETERS-V12",
    "NASA-HLSL30-2.0-C2021957657",
    "NASA-HLSS30-2.0-C2021957295",
    "EPA-ECOREGIONS-LEVEL-III-US",
}
REQUIRED_CRITERIA = {
    "identity",
    "authority",
    "access",
    "rights",
    "provenance",
    "integrity",
    "fitness",
    "privacy-security",
}
PROHIBITED_SELECTION_TERMS = {
    "pre_id",
    "post_id",
    "perim_id",
    "dnbr_offst",
    "dnbr_stddv",
    "nodata_t",
    "incgreen_t",
    "low_t",
    "mod_t",
    "high_t",
    "comment",
}


def _load(path: Path, errors: list[str]) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        errors.append(f"unable to load {path.relative_to(ROOT).as_posix()}: {exc}")
        return {}
    if not isinstance(value, dict):
        errors.append(f"{path.relative_to(ROOT).as_posix()} must contain an object")
        return {}
    return value


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def validate() -> list[str]:
    errors: list[str] = []
    gate = _load(SOURCE_GATE, errors)
    source_use = _load(SOURCE_USE, errors)
    profile = _load(PROFILE, errors)

    for path in (PRIOR, REVIEW, SURFACE):
        if not path.is_file():
            errors.append(f"missing review dependency: {path.relative_to(ROOT).as_posix()}")

    if gate.get("decision", {}).get("status") != "ready":
        errors.append("source gate must be evidence-ready before handoff")
    if gate.get("decision", {}).get("blocking_reasons") != []:
        errors.append("source gate has declared blocking reasons")
    approved = set(gate.get("decision", {}).get("approved_actions", []))
    if approved != {"metadata review", "record assessment evidence", "prepare owner review bundle"}:
        errors.append("pre-owner source gate approved actions changed")
    if any("adopt" in action or "download" in action or "enumerate" in action for action in approved):
        errors.append("source gate silently authorizes post-owner work")

    sources = gate.get("sources", [])
    if not isinstance(sources, list):
        errors.append("source gate sources must be a list")
        sources = []
    source_ids = {source.get("source_id") for source in sources if isinstance(source, dict)}
    if source_ids != EXPECTED_SOURCES:
        errors.append("source gate exact source set changed")
    for source in sources:
        if not isinstance(source, dict):
            continue
        criteria = source.get("criteria", [])
        ids = {criterion.get("id") for criterion in criteria if isinstance(criterion, dict)}
        if ids != REQUIRED_CRITERIA:
            errors.append(f"{source.get('source_id')} criterion set changed")
        for criterion in criteria:
            if not isinstance(criterion, dict):
                continue
            if criterion.get("required") is not True or criterion.get("status") != "pass":
                errors.append(f"{source.get('source_id')}:{criterion.get('id')} is not a required pass")
            if not criterion.get("evidence"):
                errors.append(f"{source.get('source_id')}:{criterion.get('id')} lacks evidence")

    if source_use.get("status") != "proposed_owner_gate":
        errors.append("source-use package is not visibly proposed")
    if source_use.get("observed_candidate_rows") != 0:
        errors.append("candidate rows were observed before source adoption")
    if source_use.get("scientific_source_bodies_opened") != 0:
        errors.append("scientific source bodies were opened before source adoption")
    if profile.get("status") != "proposed":
        errors.append("eligibility profile must remain proposed at handoff")
    expected_profile = {
        "jurisdictions": ["ID", "OR", "WA"],
        "year_start": 2021,
        "year_end": 2022,
        "minimum_area_acres": 1000,
        "maximum_area_acres": None,
        "latest_eligible_ignition_date": "2022-12-31",
        "accepted_incident_types": ["Wildfire"],
        "accepted_perimeter_statuses": ["final"],
        "unknown_policy": "unknown-is-not-eligible",
    }
    for key, expected in expected_profile.items():
        if profile.get(key) != expected:
            errors.append(f"eligibility profile {key} differs from the review proposal")

    if PRIOR.is_file():
        observed_prior_hash = _sha256(PRIOR)
        expected_prior_hash = profile.get("prior_exclusion_manifest_sha256")
        if observed_prior_hash != expected_prior_hash:
            errors.append("eligibility profile prior-exclusion hash does not bind current bytes")
        if source_use.get("prior_exclusion_manifest_sha256") != observed_prior_hash:
            errors.append("source-use package prior-exclusion hash does not bind current bytes")

    policy = source_use.get("field_policy", {})
    mtbs_allow = {str(value).lower() for value in policy.get("mtbs_allowlist", [])}
    mtbs_deny = {str(value).lower() for value in policy.get("mtbs_explicit_denylist", [])}
    if not PROHIBITED_SELECTION_TERMS <= mtbs_deny:
        errors.append("MTBS denylist does not retain every prohibited selection field")
    if mtbs_allow & PROHIBITED_SELECTION_TERMS:
        errors.append("MTBS allowlist admits a prohibited selection field")
    if mtbs_allow & mtbs_deny:
        errors.append("MTBS allowlist and denylist overlap")

    capacity = source_use.get("capacity_and_terminal_rules", {})
    if capacity.get("required_selectable_slots_per_state") != 12:
        errors.append("per-state 12-slot capacity rule changed")
    if capacity.get("required_total_slots") != 36:
        errors.append("36-slot capacity rule changed")
    if capacity.get("shortfall_disposition") != "INCONCLUSIVE":
        errors.append("capacity shortfall must remain INCONCLUSIVE")

    still_denied = " ".join(source_use.get("still_not_authorized_after_approval", [])).lower()
    denied_concepts = {
        "hls imagery": ("hls imagery",),
        "credentials": ("authenticate to earthdata", "credentials"),
        "event selection": ("choose pilot or final events", "event selection"),
        "training": ("assign train", "training"),
        "test opening": ("test roles", "test opening"),
    }
    for concept, accepted_phrases in denied_concepts.items():
        if not any(phrase in still_denied for phrase in accepted_phrases):
            errors.append(f"post-approval boundary omits {concept}")

    if SURFACE.is_file():
        html = SURFACE.read_text(encoding="utf-8")
        if 'name="decision" value="approve"' not in html or 'value="reject"' not in html or 'value="uncertain"' not in html:
            errors.append("review surface closed decision domain changed")
        if re.search(
            r'<input\b(?=[^>]*\bname=["\']decision["\'])[^>]*\schecked(?:\s|=|/?>)',
            html,
            flags=re.IGNORECASE,
        ):
            errors.append("review surface contains a preselected control")
        if "evidence_sha256: evidenceHash" not in html:
            errors.append("review export is not bound to the supplied bundle hash")
    return errors


def main() -> int:
    errors = validate()
    if errors:
        print("Source review: FAIL")
        for error in errors:
            print(f"- {error}")
        return 1
    print("Historical pre-adoption source review: PASS (5 sources, 40 criteria, 0 candidate rows)")
    print("Snapshot state: owner decision pending at package handoff; current adoption is validated separately")
    return 0


if __name__ == "__main__":
    sys.exit(main())
