"""Validate the exact owner-approved Milestone 1 source-adoption checkpoint."""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / "records" / "evidence" / "E4-EV-0008-SOURCE-ADOPTION-APPROVAL-2026-001.json"
REGISTRY = ROOT / "records" / "sources" / "EXPERIMENT-FOUR-ADMITTED-SOURCE-REGISTRY-2026-001.json"
SOURCE_GATE = ROOT / "records" / "sources" / "EXPERIMENT-FOUR-SOURCE-GATE-ASSESSMENT-2026-001.json"
SOURCE_USE = ROOT / "records" / "sources" / "EXPERIMENT-FOUR-SOURCE-USE-PROPOSAL-2026-001.json"
FROZEN_PROFILE = ROOT / "records" / "metadata" / "EXPERIMENT-FOUR-ELIGIBILITY-PROFILE-2026-001.json"
PROFILE_PROPOSAL = ROOT / "records" / "metadata" / "EXPERIMENT-FOUR-ELIGIBILITY-PROFILE-PROPOSAL-2026-002.json"
PRIOR = ROOT / "records" / "metadata" / "EXPERIMENT-FOUR-PRIOR-EVENT-EXCLUSION-MANIFEST-2026-001.json"
BUNDLE = ROOT / "records" / "reviews" / "E4-M1-SOURCE-ADOPTION-BUNDLE-2026-001.json"
CONTRACT = ROOT / "records" / "reviews" / "E4-M1-SOURCE-ADOPTION-CONTRACT-2026-001.json"

EXPECTED_HASHES = {
    "source_gate": "08dbe07f04963c25d6f35a19b201e1c3e4ae5dd3c59a9de9aaf181c76a90df93",
    "source_use": "3fcf8f5fbd9d7263a7dba2e56d71cdb4546cfc83e481ac4b37208d1bf65f70c2",
    "prior": "c819624011f5353bb085ba4b5a8db38cf0a0ca1c55e9a7741e7af59c0f7d164d",
    "bundle": "7423219b7d23388546fb7d1db0d66e83ade8958fe20ee97fc19ab95952ba62f7",
    "contract": "19ae65297a88917873164ce58ff7842a69b3e1b055eac58d73ea74917eed550c",
    "locked_response": "897926590c470978cca2c5d8d424212f5372c445af8a9df05384f70bdcb7f83c",
    "lock_receipt": "b7db031e433e7d3cce51a523b86ae0f65e764ce0e7597f43178e92681a38e3a4",
    "reconciliation": "0dac0fdeff3f0f8d52fc54f7bab72c8a1aecfc3986dcefab37d8a9c01e8e453a",
}

EXPECTED_SOURCE_IDENTITIES = {
    "NIFC-WFIGS-PERIMETERS-5E72B169": {
        "arcgis_item_id": "5e72b1699bf74eefb3f3aff6f4ba5511",
        "layer_id": 0,
        "revision_policy": "Dynamic service; freeze exact schema, query, UTC retrieval time, dataLastEditDate, page bytes, and aggregate SHA-256 at intake.",
    },
    "USGS-MTBS-PERIMETERS-V12": {
        "sciencebase_item_id": "5e7229b8e4b01d509268afba",
        "version": "12.0",
        "edition": "April 2025",
        "file_name": "mtbs_perims_DD.zip",
        "file_size_bytes": 374092911,
        "publisher_md5": "65278fcb893f94cd0eaf66d966ee7125",
    },
    "NASA-HLSL30-2.0-C2021957657": {
        "concept_id": "C2021957657-LPCLOUD",
        "version": "2.0",
        "cmr_revision_observed": 93,
        "doi": "https://doi.org/10.5067/HLS/HLSL30.002",
    },
    "NASA-HLSS30-2.0-C2021957295": {
        "concept_id": "C2021957295-LPCLOUD",
        "version": "2.0",
        "cmr_revision_observed": 95,
        "doi": "https://doi.org/10.5067/HLS/HLSS30.002",
    },
    "EPA-ECOREGIONS-LEVEL-III-US": {
        "file_name": "us_eco_l3.zip",
        "file_size_bytes_observed": 28424315,
        "last_modified_observed": "2024-11-14T17:09:20Z",
    },
}

EXPECTED_SOURCE_LOCATORS = {
    "NIFC-WFIGS-PERIMETERS-5E72B169": "https://services3.arcgis.com/T4QMspbfLg3qTGWY/arcgis/rest/services/WFIGS_Interagency_Perimeters/FeatureServer/0",
    "USGS-MTBS-PERIMETERS-V12": "https://www.sciencebase.gov/catalog/item/5e7229b8e4b01d509268afba",
    "NASA-HLSL30-2.0-C2021957657": "https://cmr.earthdata.nasa.gov/search/collections.umm_json?short_name=HLSL30&version=2.0",
    "NASA-HLSS30-2.0-C2021957295": "https://cmr.earthdata.nasa.gov/search/collections.umm_json?short_name=HLSS30&version=2.0",
    "EPA-ECOREGIONS-LEVEL-III-US": "https://dmap-prod-oms-edc.s3.us-east-1.amazonaws.com/ORD/Ecoregions/us/us_eco_l3.zip",
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
    evidence = _load(EVIDENCE, errors)
    registry = _load(REGISTRY, errors)
    gate = _load(SOURCE_GATE, errors)
    source_use = _load(SOURCE_USE, errors)
    frozen = _load(FROZEN_PROFILE, errors)
    proposal = _load(PROFILE_PROPOSAL, errors)

    for label, path in (
        ("source_gate", SOURCE_GATE),
        ("source_use", SOURCE_USE),
        ("prior", PRIOR),
        ("bundle", BUNDLE),
        ("contract", CONTRACT),
    ):
        if not path.is_file():
            errors.append(f"missing hash-bound artifact: {path.relative_to(ROOT).as_posix()}")
        elif _sha256(path) != EXPECTED_HASHES[label]:
            errors.append(f"{label} bytes changed after owner review")

    if evidence.get("owner_decision") != "approve":
        errors.append("public adoption evidence does not record the reconciled approval")
    review = evidence.get("review_binding", {})
    expected_review = {
        "bundle_sha256": EXPECTED_HASHES["bundle"],
        "contract_sha256": EXPECTED_HASHES["contract"],
        "locked_response_sha256": EXPECTED_HASHES["locked_response"],
        "lock_receipt_sha256": EXPECTED_HASHES["lock_receipt"],
        "reconciliation_sha256": EXPECTED_HASHES["reconciliation"],
        "human_decision_count": 1,
        "decision_counts": {"approve": 1, "reject": 0, "uncertain": 0},
        "notes_included": False,
        "human_decisions_fabricated": False,
        "downstream_authorization_created_by_reconciliation": False,
    }
    for key, expected in expected_review.items():
        if review.get(key) != expected:
            errors.append(f"review binding {key} differs from the locked aggregate")

    custody = evidence.get("custody", {})
    if custody.get("inheritance_disabled") is not True:
        errors.append("private review custody is not recorded as inheritance-disabled")
    for key in ("raw_response_committed", "raw_receipt_committed", "raw_reconciliation_committed"):
        if custody.get(key) is not False:
            errors.append(f"private-custody boundary changed: {key}")

    if proposal.get("status") != "proposed":
        errors.append("the exact reviewed profile proposal must remain historical and proposed")
    if frozen.get("status") != "frozen" or frozen.get("profile_id") != "E4-ELIGIBILITY-2026-001":
        errors.append("owner-approved eligibility profile is not frozen under its final identity")
    comparable_proposal = dict(proposal)
    comparable_proposal["profile_id"] = "E4-ELIGIBILITY-2026-001"
    comparable_proposal["status"] = "frozen"
    if frozen != comparable_proposal:
        errors.append("frozen eligibility profile values differ from reviewed proposal 2026-002")
    if frozen.get("prior_exclusion_manifest_sha256") != EXPECTED_HASHES["prior"]:
        errors.append("frozen profile does not bind the exact prior-event exclusions")

    if registry.get("status") != "admitted":
        errors.append("source registry is not admitted")
    if registry.get("source_gate_sha256") != EXPECTED_HASHES["source_gate"]:
        errors.append("source registry does not bind the reviewed source gate")
    if registry.get("source_use_proposal_sha256") != EXPECTED_HASHES["source_use"]:
        errors.append("source registry does not bind the reviewed source-use proposal")
    if registry.get("prior_exclusion_manifest_sha256") != EXPECTED_HASHES["prior"]:
        errors.append("source registry does not bind the exact prior-event exclusions")
    if registry.get("owner_review") != {
        "review_id": "E4-M1-SOURCE-ADOPTION-2026-001",
        "bundle_sha256": EXPECTED_HASHES["bundle"],
        "contract_sha256": EXPECTED_HASHES["contract"],
        "locked_response_sha256": EXPECTED_HASHES["locked_response"],
        "lock_receipt_sha256": EXPECTED_HASHES["lock_receipt"],
        "reconciliation_sha256": EXPECTED_HASHES["reconciliation"],
        "decision_counts": {"approve": 1, "reject": 0, "uncertain": 0},
        "notes_included": False,
        "raw_private_artifacts_committed": False,
    }:
        errors.append("source registry owner-review binding changed")

    sources = registry.get("sources", [])
    observed_sources = {
        item.get("source_id"): item for item in sources if isinstance(item, dict)
    } if isinstance(sources, list) else {}
    if set(observed_sources) != set(EXPECTED_SOURCE_IDENTITIES):
        errors.append("admitted source set differs from the exact five-source proposal")
    for source_id, expected_identity in EXPECTED_SOURCE_IDENTITIES.items():
        source = observed_sources.get(source_id, {})
        if source.get("identity") != expected_identity:
            errors.append(f"{source_id} exact identity changed")
        if source.get("locator") != EXPECTED_SOURCE_LOCATORS[source_id]:
            errors.append(f"{source_id} locator changed")
        if not source.get("role") or not source.get("admitted_actions"):
            errors.append(f"{source_id} lacks a bounded role or admitted action")

    if registry.get("released_actions") != source_use.get("actions_released_only_if_owner_approves_exact_bundle"):
        errors.append("released source actions differ from the reviewed proposal")
    if registry.get("still_not_authorized") != source_use.get("still_not_authorized_after_approval"):
        errors.append("post-adoption restrictions differ from the reviewed proposal")
    boundary = registry.get("boundary_at_adoption", {})
    if any(boundary.get(key) != 0 for key in (
        "candidate_rows_observed",
        "scientific_source_bodies_opened",
        "hls_imagery_opened",
        "credentials_used",
        "pilot_or_final_events_selected",
    )):
        errors.append("adoption checkpoint crosses a source-body or cohort boundary")

    gate_ids = {
        source.get("source_id") for source in gate.get("sources", []) if isinstance(source, dict)
    }
    if gate_ids != set(EXPECTED_SOURCE_IDENTITIES):
        errors.append("admitted source set no longer matches the reviewed source gate")
    if evidence.get("adoption", {}).get("source_count") != 5:
        errors.append("public evidence source count is not five")
    if evidence.get("adoption", {}).get("candidate_rows_observed_at_decision") != 0:
        errors.append("public evidence does not preserve the zero-row decision boundary")
    return errors


def main() -> int:
    errors = validate()
    if errors:
        print("Source adoption: FAIL")
        for error in errors:
            print(f"- {error}")
        return 1
    print("Source adoption: PASS (1 exact approval; 5 admitted sources; frozen profile)")
    print("Decision boundary: 0 candidate rows; 0 scientific source bodies opened")
    return 0


if __name__ == "__main__":
    sys.exit(main())
