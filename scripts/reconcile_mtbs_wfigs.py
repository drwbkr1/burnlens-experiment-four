"""Reconcile exact MTBS/WFIGS identities before ecology or HLS checks."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from burnlens_e4.metadata_eligibility import candidate_id_from_source  # noqa: E402


REASON_ORDER = (
    "PRIOR_EVENT_MATCH",
    "MTBS_INCIDENT_TYPE_MISMATCH",
    "MTBS_AREA_BELOW_MINIMUM",
    "NO_EXACT_WFIGS_MATCH",
    "MULTIPLE_EXACT_WFIGS_MATCHES",
    "WFIGS_STATE_MISMATCH",
    "WFIGS_INCIDENT_TYPE_MISMATCH",
    "IGNITION_DATE_MISMATCH",
    "WFIGS_MATURITY_INCOMPLETE",
    "WFIGS_AREA_UNKNOWN",
    "WFIGS_AREA_BELOW_MINIMUM",
    "WFIGS_GEOMETRY_MISSING",
)
EXCLUSION_REASONS = {
    "PRIOR_EVENT_MATCH",
    "MTBS_INCIDENT_TYPE_MISMATCH",
    "MTBS_AREA_BELOW_MINIMUM",
    "WFIGS_STATE_MISMATCH",
    "WFIGS_INCIDENT_TYPE_MISMATCH",
    "WFIGS_AREA_BELOW_MINIMUM",
}
UNKNOWN_REASONS = set(REASON_ORDER) - EXCLUSION_REASONS


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        while chunk := source.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def _canonical_bytes(value: Any) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode("utf-8")


def _fingerprint(value: Any) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def normalize_identifier(value: object) -> str | None:
    if value is None:
        return None
    normalized = str(value).strip().strip("{}").upper()
    return normalized or None


def normalize_name(value: object) -> str | None:
    normalized = " ".join(re.sub(r"[^A-Z0-9]+", " ", str(value or "").upper()).split())
    return normalized or None


def _date(value: object) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(value / 1000, tz=timezone.utc)
    if isinstance(value, str) and value:
        text = value.strip()
        if re.fullmatch(r"\d{8}", text):
            return datetime.strptime(text, "%Y%m%d").replace(tzinfo=timezone.utc)
        try:
            result = datetime.fromisoformat(text.replace("Z", "+00:00"))
            return result if result.tzinfo else result.replace(tzinfo=timezone.utc)
        except ValueError:
            return None
    return None


def _global_id(feature: dict[str, Any]) -> str:
    value = normalize_identifier(feature.get("attributes", {}).get("GlobalID"))
    if not value:
        raise ValueError("WFIGS feature has no GlobalID")
    return value


def _index(features: list[dict[str, Any]]) -> tuple[dict[str, dict[str, dict[str, Any]]], dict[str, dict[str, dict[str, Any]]]]:
    irwin: dict[str, dict[str, dict[str, Any]]] = defaultdict(dict)
    unique_fire: dict[str, dict[str, dict[str, Any]]] = defaultdict(dict)
    for feature in features:
        global_id = _global_id(feature)
        attributes = feature.get("attributes", {})
        for key in ("attr_IrwinID", "poly_IRWINID"):
            identifier = normalize_identifier(attributes.get(key))
            if identifier:
                irwin[identifier][global_id] = feature
        identifier = normalize_identifier(attributes.get("attr_UniqueFireIdentifier"))
        if identifier:
            unique_fire[identifier][global_id] = feature
    return irwin, unique_fire


def _exact_matches(
    mtbs: dict[str, Any],
    irwin_index: dict[str, dict[str, dict[str, Any]]],
    unique_fire_index: dict[str, dict[str, dict[str, Any]]],
) -> tuple[str | None, list[dict[str, Any]]]:
    irwin = normalize_identifier(mtbs.get("irwinID"))
    if irwin and irwin in irwin_index:
        return "mtbs_irwin_to_wfigs_irwin", list(irwin_index[irwin].values())
    event_id = normalize_identifier(mtbs.get("Event_ID"))
    if event_id and event_id in unique_fire_index:
        return "mtbs_event_id_to_wfigs_unique_fire_identifier", list(
            unique_fire_index[event_id].values()
        )
    return None, []


def _maturity_pass(attributes: dict[str, Any]) -> bool:
    return (
        attributes.get("poly_FeatureAccess") == "Public"
        and attributes.get("poly_FeatureStatus") == "Approved"
        and attributes.get("poly_IsVisible") == "Yes"
        and attributes.get("poly_DeleteThis") == "No"
        and attributes.get("attr_IsValid") in (1, True, "1")
        and attributes.get("attr_IsQuarantined") in (0, False, "0")
        and _date(attributes.get("attr_FFReportApprovedDate")) is not None
        and _date(attributes.get("attr_FireOutDateTime")) is not None
    )


def _status(reasons: set[str]) -> str:
    if reasons & EXCLUSION_REASONS:
        return "excluded_before_geometry_hls"
    if reasons & UNKNOWN_REASONS:
        return "unknown_before_geometry_hls"
    return "ready_for_geometry_hls"


def reconcile(
    preflight: dict[str, Any],
    snapshot_manifest: dict[str, Any],
    features: list[dict[str, Any]],
    amendment: dict[str, Any],
    *,
    preflight_sha256: str,
    snapshot_manifest_sha256: str,
    snapshot_page_sha256: str,
    amendment_sha256: str,
) -> dict[str, Any]:
    mappings = amendment["exact_source_representation_mappings"]
    pairs = {
        pair["canonical"]: pair["wfigs"]
        for pair in mappings["state"]["allowed_exact_pairs"]
    }
    if pairs != {"ID": "US-ID", "OR": "US-OR", "WA": "US-WA"}:
        raise ValueError("state mapping differs from the exact approved amendment")
    incident = mappings["incident_type"]
    if incident.get("mtbs_exact_value") != "Wildfire" or incident.get("wfigs_exact_value") != "WF":
        raise ValueError("incident-type mapping differs from the exact approved amendment")
    if snapshot_manifest.get("snapshot_id") != "E4-M1-WFIGS-SNAPSHOT-2026-001":
        raise ValueError("unexpected WFIGS snapshot identity")
    if preflight.get("manifest_id") != "E4-M1-MTBS-UNIVERSE-PREFLIGHT-2026-001":
        raise ValueError("unexpected MTBS preflight identity")

    irwin_index, unique_fire_index = _index(features)
    records: list[dict[str, Any]] = []
    status_counts: Counter[str] = Counter()
    reason_counts: Counter[str] = Counter()
    match_mode_counts: Counter[str] = Counter()
    state_status_counts: Counter[tuple[str, str]] = Counter()
    source_revision = f"mtbs-v12:{preflight_sha256};wfigs:{snapshot_manifest_sha256}"
    retrieved_at = snapshot_manifest.get("captured_at_utc")
    for row in preflight.get("rows", []):
        mtbs = row["attributes"]
        state = row["state_from_mtbs_event_id"]
        source_row_id = str(mtbs.get("Event_ID"))
        source_record = {
            "source_id": "USGS-MTBS-PERIMETERS-V12+NIFC-WFIGS-PERIMETERS-5E72B169",
            "source_revision": source_revision,
            "source_row_id": source_row_id,
            "retrieved_at_utc": retrieved_at,
            "row_sha256": _fingerprint(
                {
                    "mtbs": mtbs,
                    "prior_exclusion_ids": row.get("prior_exclusion_ids", []),
                }
            ),
        }
        candidate_id = candidate_id_from_source(source_record)
        reasons: set[str] = set()
        if row.get("prior_exclusion_ids"):
            reasons.add("PRIOR_EVENT_MATCH")
        if mtbs.get("Incid_Type") != incident["mtbs_exact_value"]:
            reasons.add("MTBS_INCIDENT_TYPE_MISMATCH")
        mtbs_area = mtbs.get("BurnBndAc")
        if not isinstance(mtbs_area, (int, float)) or mtbs_area < 1000:
            reasons.add("MTBS_AREA_BELOW_MINIMUM")

        match_mode, matches = _exact_matches(mtbs, irwin_index, unique_fire_index)
        match_mode_counts[match_mode or "none"] += 1
        matched: dict[str, Any] | None = None
        if not matches:
            reasons.add("NO_EXACT_WFIGS_MATCH")
        elif len(matches) > 1:
            reasons.add("MULTIPLE_EXACT_WFIGS_MATCHES")
        else:
            matched = matches[0]
            attributes = matched["attributes"]
            if attributes.get("attr_POOState") != pairs.get(state):
                reasons.add("WFIGS_STATE_MISMATCH")
            if attributes.get("attr_IncidentTypeCategory") != incident["wfigs_exact_value"]:
                reasons.add("WFIGS_INCIDENT_TYPE_MISMATCH")
            mtbs_ignition = _date(mtbs.get("Ig_Date"))
            wfigs_ignition = _date(attributes.get("attr_FireDiscoveryDateTime"))
            if (
                mtbs_ignition is None
                or wfigs_ignition is None
                or abs((mtbs_ignition.date() - wfigs_ignition.date()).days) > 1
            ):
                reasons.add("IGNITION_DATE_MISMATCH")
            if not _maturity_pass(attributes):
                reasons.add("WFIGS_MATURITY_INCOMPLETE")
            wfigs_area = attributes.get("attr_FinalAcres")
            if not isinstance(wfigs_area, (int, float)):
                reasons.add("WFIGS_AREA_UNKNOWN")
            elif wfigs_area < 1000:
                reasons.add("WFIGS_AREA_BELOW_MINIMUM")
            if not isinstance(matched.get("geometry"), dict):
                reasons.add("WFIGS_GEOMETRY_MISSING")

        ordered_reasons = [reason for reason in REASON_ORDER if reason in reasons]
        status = _status(reasons)
        status_counts[status] += 1
        state_status_counts[(state, status)] += 1
        reason_counts.update(ordered_reasons)
        matched_attributes = matched.get("attributes", {}) if matched else {}
        records.append(
            {
                "candidate_id": candidate_id,
                "source_record": source_record,
                "mtbs": {
                    "source_row_index": row.get("source_row_index"),
                    "event_id": mtbs.get("Event_ID"),
                    "irwin_id": mtbs.get("irwinID"),
                    "incident_name": mtbs.get("Incid_Name"),
                    "incident_type": mtbs.get("Incid_Type"),
                    "ignition_date": mtbs.get("Ig_Date"),
                    "area_acres": mtbs.get("BurnBndAc"),
                    "centroid_lon": mtbs.get("BurnBndLon"),
                    "centroid_lat": mtbs.get("BurnBndLat"),
                    "map_program": mtbs.get("Map_Prog"),
                    "assessment_type": mtbs.get("Asmnt_Type"),
                },
                "wfigs": {
                    "match_mode": match_mode,
                    "exact_match_count": len(matches),
                    "global_id": matched_attributes.get("GlobalID"),
                    "irwin_id": matched_attributes.get("attr_IrwinID"),
                    "unique_fire_identifier": matched_attributes.get("attr_UniqueFireIdentifier"),
                    "source_global_id": matched_attributes.get("attr_SourceGlobalID"),
                    "incident_name": matched_attributes.get("attr_IncidentName"),
                    "incident_type_category": matched_attributes.get("attr_IncidentTypeCategory"),
                    "poo_state": matched_attributes.get("attr_POOState"),
                    "discovery_at": matched_attributes.get("attr_FireDiscoveryDateTime"),
                    "containment_at": matched_attributes.get("attr_ContainmentDateTime"),
                    "fire_out_at": matched_attributes.get("attr_FireOutDateTime"),
                    "final_report_approved_at": matched_attributes.get("attr_FFReportApprovedDate"),
                    "final_acres": matched_attributes.get("attr_FinalAcres"),
                    "complex_id": matched_attributes.get("attr_CpxID"),
                    "complex_name": matched_attributes.get("attr_CpxName"),
                    "is_complex_child": matched_attributes.get("attr_IsCpxChild"),
                    "geometry_sha256": _fingerprint(matched.get("geometry")) if matched else None,
                },
                "canonical_preview": {
                    "normalized_name": normalize_name(
                        matched_attributes.get("attr_IncidentName") or mtbs.get("Incid_Name")
                    ),
                    "incident_year": row.get("year"),
                    "jurisdiction": state,
                    "incident_type": "Wildfire" if not reasons & {
                        "MTBS_INCIDENT_TYPE_MISMATCH",
                        "WFIGS_INCIDENT_TYPE_MISMATCH",
                    } else None,
                    "prior_exclusion_ids": row.get("prior_exclusion_ids", []),
                },
                "status": status,
                "reason_codes": ordered_reasons,
            }
        )

    return {
        "schema_version": "1.0",
        "manifest_id": "E4-M1-MTBS-WFIGS-IDENTITY-MATURITY-2026-001",
        "status": "identity_maturity_reconciled_before_ecology_hls",
        "created_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds").replace(
            "+00:00", "Z"
        ),
        "inputs": {
            "mtbs_preflight_sha256": preflight_sha256,
            "wfigs_snapshot_manifest_sha256": snapshot_manifest_sha256,
            "wfigs_snapshot_page_sha256": snapshot_page_sha256,
            "amendment_sha256": amendment_sha256,
        },
        "policy": {
            "amendment_id": amendment["amendment_id"],
            "exact_state_pairs": mappings["state"]["allowed_exact_pairs"],
            "exact_incident_type": mappings["incident_type"],
            "name_only_match_permitted": False,
            "one_to_one_required": True,
            "date_agreement_calendar_days": 1,
            "minimum_area_acres_both_sources": 1000,
        },
        "summary": {
            "row_count": len(records),
            "status_counts": dict(sorted(status_counts.items())),
            "match_mode_counts": dict(sorted(match_mode_counts.items())),
            "reason_counts": dict(sorted(reason_counts.items())),
            "state_status_counts": [
                {"state": state, "status": status, "count": count}
                for (state, status), count in sorted(state_status_counts.items())
            ],
        },
        "records": records,
        "boundary": {
            "ecology_evaluated": False,
            "hls_metadata_queried": False,
            "candidate_eligibility_assigned": False,
            "candidate_or_role_selected": False,
            "imagery_labels_models_or_metrics_opened": False,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mtbs-preflight", required=True, type=Path)
    parser.add_argument("--wfigs-manifest", required=True, type=Path)
    parser.add_argument("--wfigs-page", required=True, type=Path)
    parser.add_argument("--amendment", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    try:
        if args.output.exists():
            raise FileExistsError(f"refusing to overwrite: {args.output}")
        preflight = json.loads(args.mtbs_preflight.read_text(encoding="utf-8"))
        snapshot_manifest = json.loads(args.wfigs_manifest.read_text(encoding="utf-8"))
        snapshot_page = json.loads(args.wfigs_page.read_text(encoding="utf-8"))
        amendment = json.loads(args.amendment.read_text(encoding="utf-8"))
        value = reconcile(
            preflight,
            snapshot_manifest,
            snapshot_page.get("features", []),
            amendment,
            preflight_sha256=_sha256(args.mtbs_preflight),
            snapshot_manifest_sha256=_sha256(args.wfigs_manifest),
            snapshot_page_sha256=_sha256(args.wfigs_page),
            amendment_sha256=_sha256(args.amendment),
        )
        args.output.parent.mkdir(parents=True, exist_ok=True)
        payload = _canonical_bytes(value)
        with args.output.open("xb") as destination:
            destination.write(payload)
            destination.flush()
            os.fsync(destination.fileno())
        result = {
            "output": str(args.output.resolve()),
            "sha256": _sha256(args.output),
            "size_bytes": args.output.stat().st_size,
            "summary": value["summary"],
            "status": value["status"],
        }
    except Exception as exc:
        print(json.dumps({"status": "failed", "error": str(exc)}, indent=2))
        return 1
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
