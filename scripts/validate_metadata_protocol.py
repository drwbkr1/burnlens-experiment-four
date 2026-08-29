"""Validate the frozen metadata schema and evaluator contract."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from burnlens_e4 import metadata_eligibility  # noqa: E402


CANDIDATE_SCHEMA = ROOT / "schemas" / "candidate-event.schema.json"
PROFILE_SCHEMA = ROOT / "schemas" / "metadata-eligibility-profile.schema.json"
FREEZE_RECORD = (
    ROOT
    / "records"
    / "metadata"
    / "EXPERIMENT-FOUR-METADATA-SCHEMA-FREEZE-2026-001.json"
)
PROFILE_PROPOSAL = (
    ROOT
    / "records"
    / "metadata"
    / "EXPERIMENT-FOUR-ELIGIBILITY-PROFILE-PROPOSAL-2026-001.json"
)
APPROVED_PROFILE_PROPOSAL = (
    ROOT
    / "records"
    / "metadata"
    / "EXPERIMENT-FOUR-ELIGIBILITY-PROFILE-PROPOSAL-2026-002.json"
)
FROZEN_PROFILE = (
    ROOT
    / "records"
    / "metadata"
    / "EXPERIMENT-FOUR-ELIGIBILITY-PROFILE-2026-001.json"
)


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


def _property_names(value: Any) -> set[str]:
    names: set[str] = set()
    if isinstance(value, dict):
        properties = value.get("properties")
        if isinstance(properties, dict):
            names.update(str(key).lower() for key in properties)
        for nested in value.values():
            names.update(_property_names(nested))
    elif isinstance(value, list):
        for nested in value:
            names.update(_property_names(nested))
    return names


def validate() -> list[str]:
    errors: list[str] = []
    candidate_schema = _load(CANDIDATE_SCHEMA, errors)
    profile_schema = _load(PROFILE_SCHEMA, errors)
    freeze = _load(FREEZE_RECORD, errors)
    proposal = _load(PROFILE_PROPOSAL, errors)
    approved_proposal = _load(APPROVED_PROFILE_PROPOSAL, errors)
    frozen_profile = _load(FROZEN_PROFILE, errors)

    for label, schema in (
        ("candidate", candidate_schema),
        ("profile", profile_schema),
    ):
        if schema.get("$schema") != "https://json-schema.org/draft/2020-12/schema":
            errors.append(f"{label} schema is not Draft 2020-12")
        if schema.get("additionalProperties") is not False:
            errors.append(f"{label} schema must reject additional top-level properties")

    expected_candidate_properties = metadata_eligibility.EXPECTED_TOP_LEVEL
    observed_candidate_properties = set(candidate_schema.get("properties", {}))
    if observed_candidate_properties != expected_candidate_properties:
        errors.append("candidate schema and evaluator top-level fields differ")
    if set(candidate_schema.get("required", [])) != expected_candidate_properties:
        errors.append("every candidate top-level field must be required")

    prohibited = _property_names(candidate_schema) & metadata_eligibility.PROHIBITED_KEYS
    if prohibited:
        errors.append(f"candidate schema admits prohibited fields: {sorted(prohibited)}")

    if proposal.get("status") != "proposed":
        errors.append("eligibility profile must remain proposed before owner gate")
    for key in (
        "year_start",
        "year_end",
        "minimum_area_acres",
        "maximum_area_acres",
        "latest_eligible_ignition_date",
    ):
        if proposal.get(key) is not None:
            errors.append(f"proposal.{key} must remain unset before owner decision")
    if sorted(proposal.get("jurisdictions", [])) != ["ID", "OR", "WA"]:
        errors.append("proposal jurisdictions must match the approved three-state scope")
    if proposal.get("unknown_policy") != "unknown-is-not-eligible":
        errors.append("proposal must fail closed on unknown evidence")

    if approved_proposal.get("status") != "proposed":
        errors.append("the reviewed 2026-002 profile proposal must remain historical")
    expected_frozen = dict(approved_proposal)
    expected_frozen["profile_id"] = "E4-ELIGIBILITY-2026-001"
    expected_frozen["status"] = "frozen"
    if frozen_profile != expected_frozen:
        errors.append("frozen profile differs from the exact owner-reviewed values")

    if freeze.get("evaluator", {}).get("version") != metadata_eligibility.EVALUATOR_VERSION:
        errors.append("freeze record and evaluator versions differ")
    if freeze.get("evaluator", {}).get("reason_order") != list(
        metadata_eligibility.REASON_ORDER
    ):
        errors.append("freeze record and evaluator reason order differ")
    if freeze.get("observed_candidate_rows") != 0:
        errors.append("schema freeze must precede all candidate-row observation")
    if freeze.get("external_source_adoptions") != 0:
        errors.append("schema freeze cannot adopt an external source")
    if freeze.get("scientific_source_bodies_opened") != 0:
        errors.append("schema freeze cannot open scientific source bodies")
    if not freeze.get("owner_decisions_required_before_profile_freeze"):
        errors.append("freeze record does not retain the owner-decision boundary")
    return errors


def main() -> int:
    errors = validate()
    if errors:
        print("Metadata protocol: FAIL")
        for error in errors:
            print(f"- {error}")
        return 1
    print("Metadata protocol: PASS (schema, semantics, and evaluator aligned)")
    print("Eligibility profile: FROZEN from exact reviewed values; schema-freeze snapshot rows: 0")
    return 0


if __name__ == "__main__":
    sys.exit(main())
