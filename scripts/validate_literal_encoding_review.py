"""Validate the exact M1-U005 literal-encoding owner-review checkpoint."""

from __future__ import annotations

import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
BUNDLE = ROOT / "records" / "reviews" / "E4-M1-LITERAL-ENCODING-AMENDMENT-BUNDLE-2026-001.json"
CONTRACT = ROOT / "records" / "reviews" / "E4-M1-LITERAL-ENCODING-AMENDMENT-CONTRACT-2026-001.json"
BLANK = ROOT / "records" / "reviews" / "E4-M1-LITERAL-ENCODING-AMENDMENT-BLANK-RESPONSE-2026-001.json"
EVIDENCE = ROOT / "records" / "evidence" / "E4-EV-0009-CONTROLLED-INTAKE-AND-ENCODING-BLOCKER-2026-001.json"
PROPOSAL = ROOT / "records" / "decisions" / "E4-M1-LITERAL-ENCODING-AMENDMENT-PROPOSAL-2026-001.json"
INTAKE = ROOT / "records" / "intake" / "E4-M1-SOURCE-INTAKE-2026-001.json"
SURFACE = ROOT / "docs" / "reviews" / "e4-m1-literal-encoding-amendment-review.html"

EXPECTED = {
    "bundle": "3ff69ce031313db2010706cf481a63c24d45a88cfb23c2f6bb7a38d96f7b972a",
    "contract": "378223d8cd52ea1df88fc001afdffcdbbca3a0db4b35cc6f5e21e9d9cbe434a9",
    "blank": "78e4ada8db806388e3b75a5ab0674c4958411950c4244ab6d2e35cfbd2db0167",
    "intake": "28eb210d2ae8d154baec1f2a66ee10bbcac1c7b688d15a46ca5fdcfff680826b",
    "mtbs_preflight": "0cec99372a86b789ad939c70ab2c62081644664ba5a2cfe26538aae026e10729",
    "wfigs_probe": "eebf1289f12909cdc3c1321d7e1c7f25700762ad03037b2ff03175658a7db254",
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
    bundle = _load(BUNDLE, errors)
    contract = _load(CONTRACT, errors)
    blank = _load(BLANK, errors)
    evidence = _load(EVIDENCE, errors)
    proposal = _load(PROPOSAL, errors)
    intake = _load(INTAKE, errors)

    for label, path in (("bundle", BUNDLE), ("contract", CONTRACT), ("blank", BLANK), ("intake", INTAKE)):
        if path.is_file() and _sha256(path) != EXPECTED[label]:
            errors.append(f"{label} bytes differ from the handoff identity")

    for artifact in bundle.get("artifacts", []):
        if not isinstance(artifact, dict):
            errors.append("bundle artifact must be an object")
            continue
        path_value = artifact.get("path")
        if not isinstance(path_value, str):
            errors.append("bundle artifact lacks path")
            continue
        path = (ROOT / path_value).resolve()
        try:
            path.relative_to(ROOT)
        except ValueError:
            errors.append(f"bundle artifact leaves repository: {path_value}")
            continue
        if not path.is_file() or _sha256(path) != artifact.get("sha256"):
            errors.append(f"bundle artifact hash mismatch: {path_value}")
    surface_state = bundle.get("review_surface", {})
    for key in ("blank_state_verified", "completion_controls_verified", "export_guards_verified", "export_verified"):
        if surface_state.get(key) is not True:
            errors.append(f"review surface is not handoff-ready: {key}")

    if contract.get("review_bundle", {}).get("manifest_sha256") != EXPECTED["bundle"]:
        errors.append("review contract does not bind the exact bundle")
    if contract.get("allowed_decisions") != ["approve", "reject", "uncertain"]:
        errors.append("review contract decision domain changed")
    if contract.get("required_attestation") is not True:
        errors.append("review contract no longer requires attestation")
    item = contract.get("items", [{}])[0]
    if item.get("evidence_sha256") != EXPECTED["bundle"]:
        errors.append("review item does not bind the exact bundle")

    if blank.get("completed") is not False or blank.get("reviewer", {}).get("attestation") is not False:
        errors.append("blank response contains completion or attestation")
    blank_item = blank.get("responses", [{}])[0]
    if blank_item.get("evidence_sha256") != EXPECTED["bundle"] or blank_item.get("decision") is not None:
        errors.append("blank response is not blank and exactly bundle-bound")

    preflight = evidence.get("mtbs_universe_preflight", {})
    probe = evidence.get("wfigs_encoding_probe", {})
    if preflight.get("runtime_manifest_sha256") != EXPECTED["mtbs_preflight"]:
        errors.append("evidence does not bind the MTBS preflight manifest")
    if probe.get("runtime_probe_sha256") != EXPECTED["wfigs_probe"]:
        errors.append("evidence does not bind the WFIGS encoding probe")
    expected_counts = {
        "complete_pre_exclusion_row_count": 187,
        "mtbs_literal_WF_count": 0,
        "mtbs_literal_Wildfire_count": 177,
        "eligibility_assignments_created": 0,
    }
    for key, expected in expected_counts.items():
        if preflight.get(key) != expected:
            errors.append(f"MTBS preflight count changed: {key}")
    if probe.get("exact_unprefixed_ID_OR_WA_count") != 0:
        errors.append("WFIGS exact unprefixed count is not zero")
    if probe.get("exact_prefixed_US_ID_OR_WA_count") != 1756:
        errors.append("WFIGS exact prefixed count changed")
    if evidence.get("protocol_conflict", {}).get("owner_gate_required") is not True:
        errors.append("protocol conflict no longer requires owner review")

    amendment = proposal.get("proposed_exact_amendment", {})
    required_phrases = {
        "canonical_state_rule": ("US- plus", "No other"),
        "canonical_incident_type_rule": ("exactly Wildfire", "exactly WF", "No other"),
        "conflict_rule": ("unknown", "not eligible"),
    }
    for key, phrases in required_phrases.items():
        text = str(amendment.get(key, ""))
        if not all(phrase in text for phrase in phrases):
            errors.append(f"bounded amendment changed: {key}")
    if proposal.get("observed_before_decision", {}).get("candidate_eligibility_decisions") != 0:
        errors.append("proposal was prepared after eligibility decisions")

    assets = intake.get("assets", [])
    if len(assets) != 2 or any(asset.get("state") != "promoted" for asset in assets if isinstance(asset, dict)):
        errors.append("both exact intake assets must remain promoted")

    if SURFACE.is_file():
        html = SURFACE.read_text(encoding="utf-8")
        for value in ("approve", "reject", "uncertain"):
            if f'name="decision" value="{value}"' not in html:
                errors.append(f"review surface omits decision: {value}")
        if re.search(
            r'<input\b(?=[^>]*\bname=["\']decision["\'])[^>]*\schecked(?:\s|=|/?>)',
            html,
            flags=re.IGNORECASE,
        ):
            errors.append("review surface contains a preselected decision")
        if "evidence_sha256: evidenceHash" not in html:
            errors.append("review export is not dynamically bundle-bound")
    return errors


def main() -> int:
    errors = validate()
    if errors:
        print("Literal encoding review: FAIL")
        for error in errors:
            print(f"- {error}")
        return 1
    print("Literal encoding review: PASS (bundle 3ff69ce0; blank exact owner gate)")
    print("Boundary: 187 preflight rows; 0 eligibility decisions; no implicit normalization")
    return 0


if __name__ == "__main__":
    sys.exit(main())
