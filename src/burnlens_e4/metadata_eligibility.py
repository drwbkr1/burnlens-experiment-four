"""Deterministic metadata-only eligibility evaluation.

The evaluator accepts no raster, label, index, prediction, metric, or model
field. It never promotes missing evidence: unknown is not eligible.
"""

from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from datetime import date, datetime
from typing import Any


EVALUATOR_VERSION = "1.0.0"

REASON_ORDER = (
    "CANDIDATE_SCHEMA_INVALID",
    "PROFILE_NOT_FROZEN",
    "PROFILE_INVALID",
    "IDENTITY_CONFLICT",
    "PRIOR_EVENT_EXACT_MATCH",
    "PRIOR_EVENT_NAME_YEAR_MATCH",
    "DUPLICATE_EVENT",
    "PROBABLE_DUPLICATE_EVENT",
    "JURISDICTION_OUT_OF_SCOPE",
    "YEAR_OUT_OF_RANGE",
    "INCIDENT_TYPE_OUT_OF_SCOPE",
    "AREA_BELOW_MINIMUM",
    "AREA_ABOVE_MAXIMUM",
    "IGNITION_AFTER_MATURITY_CUTOFF",
    "PERIMETER_STATUS_INELIGIBLE",
    "ECOLOGY_OUT_OF_SCOPE",
    "IMAGERY_METADATA_UNAVAILABLE",
    "REFERENCE_METADATA_UNAVAILABLE",
    "RIGHTS_INCOMPATIBLE",
    "IDENTITY_UNKNOWN",
    "JURISDICTION_UNKNOWN",
    "YEAR_UNKNOWN",
    "INCIDENT_TYPE_UNKNOWN",
    "AREA_UNKNOWN",
    "IGNITION_DATE_UNKNOWN",
    "PERIMETER_STATUS_UNKNOWN",
    "ECOLOGY_UNKNOWN",
    "IMAGERY_METADATA_UNKNOWN",
    "REFERENCE_METADATA_UNKNOWN",
    "RIGHTS_UNRESOLVED",
    "PRIOR_EVENT_OVERLAP_UNKNOWN",
    "CANDIDATE_DUPLICATE_STATUS_UNKNOWN",
)

INVALID_REASONS = {
    "CANDIDATE_SCHEMA_INVALID",
    "PROFILE_NOT_FROZEN",
    "PROFILE_INVALID",
    "IDENTITY_CONFLICT",
}

EXCLUSION_REASONS = {
    "PRIOR_EVENT_EXACT_MATCH",
    "PRIOR_EVENT_NAME_YEAR_MATCH",
    "DUPLICATE_EVENT",
    "PROBABLE_DUPLICATE_EVENT",
    "JURISDICTION_OUT_OF_SCOPE",
    "YEAR_OUT_OF_RANGE",
    "INCIDENT_TYPE_OUT_OF_SCOPE",
    "AREA_BELOW_MINIMUM",
    "AREA_ABOVE_MAXIMUM",
    "IGNITION_AFTER_MATURITY_CUTOFF",
    "PERIMETER_STATUS_INELIGIBLE",
    "ECOLOGY_OUT_OF_SCOPE",
    "IMAGERY_METADATA_UNAVAILABLE",
    "REFERENCE_METADATA_UNAVAILABLE",
    "RIGHTS_INCOMPATIBLE",
}

UNKNOWN_REASONS = set(REASON_ORDER) - INVALID_REASONS - EXCLUSION_REASONS

EXPECTED_TOP_LEVEL = {
    "schema_version",
    "candidate_id",
    "source_record",
    "identity",
    "fire",
    "geography",
    "availability",
    "overlap",
}

PROHIBITED_KEYS = {
    "class_balance",
    "dnbr",
    "error",
    "label",
    "logit",
    "metric",
    "model",
    "nbr",
    "prediction",
    "probability",
    "rbr",
    "residual",
    "score",
    "selected_role",
}

SHA256 = re.compile(r"^[0-9a-f]{64}$")
CANDIDATE_ID = re.compile(r"^E4-CAND-[A-F0-9]{16}$")


def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def fingerprint(*values: Any) -> str:
    digest = hashlib.sha256()
    for value in values:
        digest.update(canonical_json(value).encode("utf-8"))
        digest.update(b"\n")
    return digest.hexdigest()


def candidate_id_from_source(source_record: dict[str, Any]) -> str:
    parts = [
        source_record.get("source_id"),
        source_record.get("source_revision"),
        source_record.get("source_row_id"),
    ]
    if not all(isinstance(part, str) and part for part in parts):
        raise ValueError("source identity requires source_id, source_revision, and source_row_id")
    payload = "\n".join(parts).encode("utf-8")
    return "E4-CAND-" + hashlib.sha256(payload).hexdigest()[:16].upper()


def normalize_name(value: str) -> str:
    decomposed = unicodedata.normalize("NFKD", value)
    ascii_value = "".join(char for char in decomposed if not unicodedata.combining(char))
    tokens = re.findall(r"[A-Z0-9]+", ascii_value.upper())
    return " ".join(tokens)


def _contains_prohibited_key(value: Any) -> bool:
    if isinstance(value, dict):
        for key, nested in value.items():
            if str(key).lower() in PROHIBITED_KEYS or _contains_prohibited_key(nested):
                return True
    elif isinstance(value, list):
        return any(_contains_prohibited_key(item) for item in value)
    return False


def _candidate_is_structurally_valid(candidate: Any) -> bool:
    if not isinstance(candidate, dict) or set(candidate) != EXPECTED_TOP_LEVEL:
        return False
    if _contains_prohibited_key(candidate):
        return False
    if candidate.get("schema_version") != "1.0":
        return False
    candidate_id = candidate.get("candidate_id")
    if not isinstance(candidate_id, str) or not CANDIDATE_ID.fullmatch(candidate_id):
        return False
    source = candidate.get("source_record")
    if not isinstance(source, dict):
        return False
    if not SHA256.fullmatch(str(source.get("row_sha256", ""))):
        return False
    try:
        if candidate_id_from_source(source) != candidate_id:
            return False
    except ValueError:
        return False
    for key in ("identity", "fire", "geography", "availability", "overlap"):
        if not isinstance(candidate.get(key), dict):
            return False
    return True


def _profile_errors(profile: Any, expected_exclusion_hash: str) -> set[str]:
    if not isinstance(profile, dict):
        return {"PROFILE_INVALID"}
    if profile.get("status") != "frozen":
        return {"PROFILE_NOT_FROZEN"}
    required_non_null = (
        "year_start",
        "year_end",
        "minimum_area_acres",
        "latest_eligible_ignition_date",
    )
    if any(profile.get(key) is None for key in required_non_null):
        return {"PROFILE_INVALID"}
    if sorted(profile.get("jurisdictions", [])) != ["ID", "OR", "WA"]:
        return {"PROFILE_INVALID"}
    if not isinstance(profile.get("year_start"), int) or not isinstance(
        profile.get("year_end"), int
    ):
        return {"PROFILE_INVALID"}
    if profile["year_start"] > profile["year_end"]:
        return {"PROFILE_INVALID"}
    minimum = profile.get("minimum_area_acres")
    maximum = profile.get("maximum_area_acres")
    if not isinstance(minimum, (int, float)) or minimum <= 0:
        return {"PROFILE_INVALID"}
    if maximum is not None and (
        not isinstance(maximum, (int, float)) or maximum < minimum
    ):
        return {"PROFILE_INVALID"}
    try:
        date.fromisoformat(profile["latest_eligible_ignition_date"])
    except (TypeError, ValueError):
        return {"PROFILE_INVALID"}
    if not profile.get("accepted_incident_types") or not profile.get(
        "accepted_perimeter_statuses"
    ):
        return {"PROFILE_INVALID"}
    if profile.get("unknown_policy") != "unknown-is-not-eligible":
        return {"PROFILE_INVALID"}
    if profile.get("prior_exclusion_manifest_sha256") != expected_exclusion_hash:
        return {"PROFILE_INVALID"}
    return set()


def _prior_identity_sets(prior_manifest: dict[str, Any]) -> dict[str, set[Any]]:
    sets: dict[str, set[Any]] = {
        "unique_fire_identifier": set(),
        "source_event_id": set(),
        "source_global_id": set(),
        "project_event_id": set(),
        "name_year": set(),
    }
    for event in prior_manifest.get("events", []):
        for key in (
            "unique_fire_identifier",
            "source_event_id",
            "source_global_id",
            "project_event_id",
        ):
            value = event.get(key)
            if value:
                sets[key].add(value)
        if event.get("provenance_tier") == "accepted-public":
            name = event.get("canonical_name")
            year = event.get("year")
            if isinstance(name, str) and isinstance(year, int):
                sets["name_year"].add((normalize_name(name), year))
    return sets


def _ordered(reasons: set[str]) -> list[str]:
    return [reason for reason in REASON_ORDER if reason in reasons]


def _outcome(reasons: set[str]) -> str:
    if reasons & INVALID_REASONS:
        return "invalid"
    if reasons & EXCLUSION_REASONS:
        return "excluded"
    if reasons & UNKNOWN_REASONS:
        return "unknown"
    return "eligible"


def _date_part(value: Any) -> date | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).date()
    except ValueError:
        return None


def evaluate(
    candidate: dict[str, Any],
    profile: dict[str, Any],
    prior_manifest: dict[str, Any],
    prior_manifest_sha256: str | None = None,
) -> dict[str, Any]:
    """Return a deterministic metadata disposition and ordered reason list."""
    reasons: set[str] = set()
    if not _candidate_is_structurally_valid(candidate):
        reasons.add("CANDIDATE_SCHEMA_INVALID")

    expected_hash = prior_manifest_sha256 or hashlib.sha256(
        canonical_json(prior_manifest).encode("utf-8")
    ).hexdigest()
    reasons.update(_profile_errors(profile, expected_hash))

    if reasons & INVALID_REASONS:
        return {
            "evaluator_version": EVALUATOR_VERSION,
            "candidate_id": candidate.get("candidate_id") if isinstance(candidate, dict) else None,
            "profile_id": profile.get("profile_id") if isinstance(profile, dict) else None,
            "input_fingerprint": fingerprint(candidate, profile, prior_manifest),
            "status": "invalid",
            "reason_codes": _ordered(reasons),
        }

    identity = candidate["identity"]
    fire = candidate["fire"]
    geography = candidate["geography"]
    availability = candidate["availability"]
    overlap = candidate["overlap"]

    if identity.get("identity_status") == "conflict":
        reasons.add("IDENTITY_CONFLICT")
    elif identity.get("identity_status") in {"partial", "unknown"}:
        reasons.add("IDENTITY_UNKNOWN")
    canonical_name = identity.get("canonical_name")
    normalized_name = identity.get("normalized_name")
    if isinstance(canonical_name, str) and isinstance(normalized_name, str):
        if normalize_name(canonical_name) != normalized_name:
            reasons.add("IDENTITY_CONFLICT")

    prior_sets = _prior_identity_sets(prior_manifest)
    for key in ("unique_fire_identifier", "source_event_id", "source_global_id"):
        value = identity.get(key)
        if value and value in prior_sets[key]:
            reasons.add("PRIOR_EVENT_EXACT_MATCH")
    if candidate.get("candidate_id") in prior_sets["project_event_id"]:
        reasons.add("PRIOR_EVENT_EXACT_MATCH")
    year = identity.get("incident_year")
    if normalized_name and isinstance(year, int):
        if (normalized_name, year) in prior_sets["name_year"]:
            reasons.add("PRIOR_EVENT_NAME_YEAR_MATCH")

    jurisdiction = identity.get("jurisdiction")
    if jurisdiction is None:
        reasons.add("JURISDICTION_UNKNOWN")
    elif jurisdiction not in profile["jurisdictions"]:
        reasons.add("JURISDICTION_OUT_OF_SCOPE")
    if year is None:
        reasons.add("YEAR_UNKNOWN")
    elif year < profile["year_start"] or year > profile["year_end"]:
        reasons.add("YEAR_OUT_OF_RANGE")

    incident_type = fire.get("incident_type")
    if incident_type is None:
        reasons.add("INCIDENT_TYPE_UNKNOWN")
    elif incident_type not in profile["accepted_incident_types"]:
        reasons.add("INCIDENT_TYPE_OUT_OF_SCOPE")

    area = fire.get("area_acres")
    if area is None:
        reasons.add("AREA_UNKNOWN")
    else:
        if area < profile["minimum_area_acres"]:
            reasons.add("AREA_BELOW_MINIMUM")
        maximum = profile.get("maximum_area_acres")
        if maximum is not None and area > maximum:
            reasons.add("AREA_ABOVE_MAXIMUM")

    ignition = _date_part(fire.get("ignition_at"))
    if ignition is None:
        reasons.add("IGNITION_DATE_UNKNOWN")
    elif ignition > date.fromisoformat(profile["latest_eligible_ignition_date"]):
        reasons.add("IGNITION_AFTER_MATURITY_CUTOFF")

    perimeter_status = fire.get("perimeter_status")
    if perimeter_status == "unknown":
        reasons.add("PERIMETER_STATUS_UNKNOWN")
    elif perimeter_status not in profile["accepted_perimeter_statuses"]:
        reasons.add("PERIMETER_STATUS_INELIGIBLE")

    ecology_codes = geography.get("ecology_codes", [])
    ecology_rule = profile["ecology_rule"]
    if not ecology_codes:
        reasons.add("ECOLOGY_UNKNOWN")
    elif ecology_rule["mode"] == "admitted-codes" and not (
        set(ecology_codes) & set(ecology_rule["admitted_codes"])
    ):
        reasons.add("ECOLOGY_OUT_OF_SCOPE")

    imagery_status = availability.get("imagery_metadata_status")
    if imagery_status == "unavailable":
        reasons.add("IMAGERY_METADATA_UNAVAILABLE")
    elif imagery_status != profile["required_imagery_metadata_status"]:
        reasons.add("IMAGERY_METADATA_UNKNOWN")
    reference_status = availability.get("reference_metadata_status")
    if reference_status == "unavailable":
        reasons.add("REFERENCE_METADATA_UNAVAILABLE")
    elif reference_status != profile["required_reference_metadata_status"]:
        reasons.add("REFERENCE_METADATA_UNKNOWN")
    rights_status = availability.get("rights_status")
    if rights_status == "incompatible":
        reasons.add("RIGHTS_INCOMPATIBLE")
    elif rights_status != profile["required_rights_status"]:
        reasons.add("RIGHTS_UNRESOLVED")

    prior_overlap = overlap.get("prior_event_match_status")
    if prior_overlap in {"exact_match", "probable_match"}:
        reasons.add("PRIOR_EVENT_EXACT_MATCH")
    elif prior_overlap in {"unknown", "not_checked"}:
        reasons.add("PRIOR_EVENT_OVERLAP_UNKNOWN")
    duplicate_status = overlap.get("candidate_duplicate_status")
    if duplicate_status == "duplicate":
        reasons.add("DUPLICATE_EVENT")
    elif duplicate_status == "probable_duplicate":
        reasons.add("PROBABLE_DUPLICATE_EVENT")
    elif duplicate_status in {"unknown", "not_checked"}:
        reasons.add("CANDIDATE_DUPLICATE_STATUS_UNKNOWN")

    ordered_reasons = _ordered(reasons)
    return {
        "evaluator_version": EVALUATOR_VERSION,
        "candidate_id": candidate["candidate_id"],
        "profile_id": profile["profile_id"],
        "input_fingerprint": fingerprint(candidate, profile, prior_manifest),
        "status": _outcome(reasons),
        "reason_codes": ordered_reasons,
    }
