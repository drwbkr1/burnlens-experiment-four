"""Build the complete candidate schema manifest from reconciled M1 metadata."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import struct
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from burnlens_e4.metadata_eligibility import evaluate, normalize_name  # noqa: E402


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        while chunk := source.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def _canonical_bytes(value: Any) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode("utf-8")


def _iso(value: object) -> str | None:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(value / 1000, tz=timezone.utc).isoformat(
            timespec="seconds"
        ).replace("+00:00", "Z")
    if isinstance(value, str) and value:
        text = value.strip()
        if re.fullmatch(r"\d{4}-\d{2}-\d{2}", text):
            return f"{text}T00:00:00Z"
        try:
            result = datetime.fromisoformat(text.replace("Z", "+00:00"))
        except ValueError:
            return None
        if result.tzinfo is None:
            result = result.replace(tzinfo=timezone.utc)
        return result.astimezone(timezone.utc).isoformat(timespec="seconds").replace(
            "+00:00", "Z"
        )
    return None


def _uuid(value: object) -> str | None:
    if value is None:
        return None
    normalized = str(value).strip().strip("{}").lower()
    if re.fullmatch(
        r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}",
        normalized,
    ):
        return normalized
    return None


def _shp_record(shp: Path, shx: Path, index: int) -> tuple[str, list[float] | None]:
    if index < 0:
        raise ValueError("negative shapefile record index")
    with shx.open("rb") as offsets:
        offsets.seek(100 + index * 8)
        entry = offsets.read(8)
    if len(entry) != 8:
        raise ValueError(f"SHX record {index} is unavailable")
    offset_words, length_words = struct.unpack(">2I", entry)
    offset = offset_words * 2
    content_length = length_words * 2
    with shp.open("rb") as source:
        source.seek(offset)
        header = source.read(8)
        content = source.read(content_length)
    if len(header) != 8 or len(content) != content_length:
        raise ValueError(f"SHP record {index} is truncated")
    record_number, header_length_words = struct.unpack(">2I", header)
    if record_number != index + 1 or header_length_words != length_words:
        raise ValueError(f"SHP/SHX record {index} identity differs")
    shape_type = struct.unpack("<I", content[:4])[0] if len(content) >= 4 else None
    bbox: list[float] | None = None
    if shape_type in {3, 5, 13, 15, 23, 25} and len(content) >= 36:
        bbox = list(struct.unpack("<4d", content[4:36]))
    return hashlib.sha256(header + content).hexdigest(), bbox


def _candidate(record: dict[str, Any], geometry_sha256: str) -> dict[str, Any]:
    mtbs = record["mtbs"]
    wfigs = record["wfigs"]
    reasons = set(record["reason_codes"])
    names = [value for value in (wfigs.get("incident_name"), mtbs.get("incident_name")) if value]
    canonical_name = names[0] if names else None
    aliases = sorted({str(value) for value in names[1:] if value != canonical_name})
    exact_identity = (
        wfigs.get("exact_match_count") == 1
        and "WFIGS_STATE_MISMATCH" not in reasons
        and "IGNITION_DATE_MISMATCH" not in reasons
    )
    type_pass = not reasons & {
        "MTBS_INCIDENT_TYPE_MISMATCH",
        "WFIGS_INCIDENT_TYPE_MISMATCH",
    }
    maturity_pass = "WFIGS_MATURITY_INCOMPLETE" not in reasons and exact_identity
    prior_ids = record["canonical_preview"].get("prior_exclusion_ids", [])
    return {
        "schema_version": "1.0",
        "candidate_id": record["candidate_id"],
        "source_record": record["source_record"],
        "identity": {
            "canonical_name": canonical_name,
            "normalized_name": normalize_name(canonical_name) if canonical_name else None,
            "incident_year": record["canonical_preview"].get("incident_year"),
            "jurisdiction": record["canonical_preview"].get("jurisdiction"),
            "unique_fire_identifier": wfigs.get("unique_fire_identifier"),
            "source_event_id": mtbs.get("event_id"),
            "source_global_id": _uuid(wfigs.get("source_global_id")),
            "identity_status": "exact" if exact_identity else "unknown",
            "aliases": aliases,
        },
        "fire": {
            "incident_type": "Wildfire" if type_pass else None,
            "ignition_at": _iso(wfigs.get("discovery_at") or mtbs.get("ignition_date")),
            "containment_at": _iso(wfigs.get("containment_at")),
            "fire_out_at": _iso(wfigs.get("fire_out_at")),
            "final_report_approved_at": _iso(wfigs.get("final_report_approved_at")),
            "perimeter_effective_at": _iso(wfigs.get("fire_out_at")),
            "area_acres": mtbs.get("area_acres"),
            "area_source": "USGS-MTBS-PERIMETERS-V12.BurnBndAc",
            "perimeter_status": "final" if maturity_pass else "unknown",
        },
        "geography": {
            "centroid_lon": mtbs.get("centroid_lon"),
            "centroid_lat": mtbs.get("centroid_lat"),
            "ecology_codes": [],
            "geometry_fingerprint": geometry_sha256,
        },
        "availability": {
            "imagery_metadata_status": "not_checked",
            "reference_metadata_status": "available"
            if mtbs.get("map_program") == "MTBS"
            else "unknown",
            "rights_status": "admitted",
            "imagery_programs": [],
            "reference_programs": ["USGS-MTBS-PERIMETERS-V12"],
        },
        "overlap": {
            "prior_event_match_status": "exact_match" if prior_ids else "no_match",
            "candidate_duplicate_status": "not_checked",
            "matched_prior_exclusion_ids": prior_ids,
            "matched_candidate_ids": [],
        },
    }


def build(
    identity_manifest: dict[str, Any],
    profile: dict[str, Any],
    prior: dict[str, Any],
    *,
    identity_manifest_sha256: str,
    profile_sha256: str,
    prior_sha256: str,
    shp: Path,
    shx: Path,
    shp_sha256: str,
    shx_sha256: str,
) -> dict[str, Any]:
    candidates: list[dict[str, Any]] = []
    evaluator_status: Counter[str] = Counter()
    evaluator_reasons: Counter[str] = Counter()
    source_gate_status: Counter[str] = Counter()
    state_source_gate: Counter[tuple[str, str]] = Counter()
    for source_record in identity_manifest.get("records", []):
        index = source_record["mtbs"]["source_row_index"]
        geometry_sha256, bbox = _shp_record(shp, shx, index)
        candidate = _candidate(source_record, geometry_sha256)
        evaluation = evaluate(candidate, profile, prior, prior_sha256)
        evaluator_status[evaluation["status"]] += 1
        evaluator_reasons.update(evaluation["reason_codes"])
        source_status = source_record["status"]
        source_gate_status[source_status] += 1
        state_source_gate[(candidate["identity"]["jurisdiction"], source_status)] += 1
        candidates.append(
            {
                "candidate": candidate,
                "evaluation": evaluation,
                "source_gate": {
                    "status": source_status,
                    "reason_codes": source_record["reason_codes"],
                    "wfigs_final_acres": source_record["wfigs"].get("final_acres"),
                },
                "mtbs_geometry": {
                    "source_row_index": index,
                    "record_sha256": geometry_sha256,
                    "bbox_nad83": bbox,
                },
            }
        )
    ready_count = source_gate_status.get("ready_for_geometry_hls", 0)
    return {
        "schema_version": "1.0",
        "manifest_id": "E4-M1-COMPLETE-CANDIDATE-UNIVERSE-2026-001",
        "status": "complete_terminal_source_shortfall",
        "created_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds").replace(
            "+00:00", "Z"
        ),
        "inputs": {
            "identity_maturity_manifest_sha256": identity_manifest_sha256,
            "eligibility_profile_sha256": profile_sha256,
            "prior_exclusion_manifest_sha256": prior_sha256,
            "mtbs_shp_sha256": shp_sha256,
            "mtbs_shx_sha256": shx_sha256,
        },
        "summary": {
            "candidate_count": len(candidates),
            "source_gate_status_counts": dict(sorted(source_gate_status.items())),
            "source_gate_reason_counts": identity_manifest.get("summary", {}).get(
                "reason_counts", {}
            ),
            "evaluator_status_counts_before_ecology_hls": dict(
                sorted(evaluator_status.items())
            ),
            "evaluator_reason_counts_before_ecology_hls": dict(
                sorted(evaluator_reasons.items())
            ),
            "state_source_gate_counts": [
                {"state": state, "status": status, "count": count}
                for (state, status), count in sorted(state_source_gate.items())
            ],
            "maximum_candidates_reaching_ecology_hls": ready_count,
            "required_total_selectable_slots": 36,
            "terminal_shortfall_proven": ready_count < 36,
        },
        "candidates": candidates,
        "boundary": {
            "all_187_pre_exclusion_rows_accounted": len(candidates) == 187,
            "ecology_not_needed_after_terminal_source_shortfall": True,
            "hls_queries_not_needed_after_terminal_source_shortfall": True,
            "candidate_eligibility_assigned": False,
            "candidate_or_role_selected": False,
            "imagery_labels_models_or_metrics_opened": False,
            "shortfall_cannot_be_rescued_without_protocol_change": True,
        },
        "terminal_rule": "Fewer than 36 qualifying candidates without relaxing a frozen requirement yields Milestone 1 INCONCLUSIVE.",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--identity-manifest", required=True, type=Path)
    parser.add_argument("--profile", required=True, type=Path)
    parser.add_argument("--prior", required=True, type=Path)
    parser.add_argument("--mtbs-shp", required=True, type=Path)
    parser.add_argument("--mtbs-shx", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    try:
        if args.output.exists():
            raise FileExistsError(f"refusing to overwrite: {args.output}")
        identity = json.loads(args.identity_manifest.read_text(encoding="utf-8"))
        profile = json.loads(args.profile.read_text(encoding="utf-8"))
        prior = json.loads(args.prior.read_text(encoding="utf-8"))
        value = build(
            identity,
            profile,
            prior,
            identity_manifest_sha256=_sha256(args.identity_manifest),
            profile_sha256=_sha256(args.profile),
            prior_sha256=_sha256(args.prior),
            shp=args.mtbs_shp,
            shx=args.mtbs_shx,
            shp_sha256=_sha256(args.mtbs_shp),
            shx_sha256=_sha256(args.mtbs_shx),
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
