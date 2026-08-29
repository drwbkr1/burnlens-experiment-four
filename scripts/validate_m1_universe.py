"""Independently validate M1 universe completeness and terminal shortfall."""

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

from burnlens_e4.metadata_eligibility import evaluate  # noqa: E402


HEX64 = re.compile(r"^[0-9a-f]{64}$")
EXCLUSION_REASONS = {
    "PRIOR_EVENT_MATCH",
    "MTBS_INCIDENT_TYPE_MISMATCH",
    "MTBS_AREA_BELOW_MINIMUM",
    "WFIGS_STATE_MISMATCH",
    "WFIGS_INCIDENT_TYPE_MISMATCH",
    "WFIGS_AREA_BELOW_MINIMUM",
}


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        while chunk := source.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def _load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path.name} is not an object")
    return value


def _canonical_bytes(value: Any) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode("utf-8")


def _candidate_id(source: dict[str, Any]) -> str:
    payload = "\n".join(
        [source["source_id"], source["source_revision"], source["source_row_id"]]
    ).encode("utf-8")
    return "E4-CAND-" + hashlib.sha256(payload).hexdigest()[:16].upper()


def _geometry_digest(shp: Path, shx: Path, index: int) -> str:
    with shx.open("rb") as offsets:
        offsets.seek(100 + index * 8)
        entry = offsets.read(8)
    if len(entry) != 8:
        raise ValueError(f"missing SHX record {index}")
    offset_words, length_words = struct.unpack(">2I", entry)
    with shp.open("rb") as source:
        source.seek(offset_words * 2)
        raw = source.read(8 + length_words * 2)
    if len(raw) != 8 + length_words * 2:
        raise ValueError(f"truncated SHP record {index}")
    record_number, header_length = struct.unpack(">2I", raw[:8])
    if record_number != index + 1 or header_length != length_words:
        raise ValueError(f"SHP/SHX identity mismatch at record {index}")
    return hashlib.sha256(raw).hexdigest()


def validate(
    *,
    snapshot_manifest_path: Path,
    snapshot_page_path: Path,
    identity_path: Path,
    universe_path: Path,
    profile_path: Path,
    prior_path: Path,
    amendment_path: Path,
    mtbs_shp_path: Path,
    mtbs_shx_path: Path,
) -> tuple[list[str], dict[str, Any]]:
    errors: list[str] = []
    snapshot = _load(snapshot_manifest_path)
    page = _load(snapshot_page_path)
    identity = _load(identity_path)
    universe = _load(universe_path)
    profile = _load(profile_path)
    prior = _load(prior_path)
    amendment = _load(amendment_path)

    page_sha = _sha256(snapshot_page_path)
    manifest_sha = _sha256(snapshot_manifest_path)
    identity_sha = _sha256(identity_path)
    universe_sha = _sha256(universe_path)
    profile_sha = _sha256(profile_path)
    prior_sha = _sha256(prior_path)
    amendment_sha = _sha256(amendment_path)
    shp_sha = _sha256(mtbs_shp_path)
    shx_sha = _sha256(mtbs_shx_path)

    pages = snapshot.get("capture", {}).get("pages", [])
    if len(pages) != 1 or pages[0].get("sha256") != page_sha:
        errors.append("snapshot does not bind the exact WFIGS page")
    features = page.get("features", [])
    if not isinstance(features, list) or len(features) != 1756:
        errors.append("WFIGS snapshot feature count is not 1756")
    if snapshot.get("capture", {}).get("observed_feature_count") != len(features):
        errors.append("WFIGS manifest count differs from page")
    allowed = set(snapshot.get("protocol", {}).get("out_fields", []))
    if not allowed or "attr_FinalAcres" not in allowed:
        errors.append("WFIGS allowlist is missing attr_FinalAcres")
    for index, feature in enumerate(features):
        attrs = feature.get("attributes") if isinstance(feature, dict) else None
        if not isinstance(attrs, dict) or set(attrs) != allowed:
            errors.append(f"WFIGS feature {index} does not match the exact allowlist")
            break
    final_acres_non_null = sum(
        feature.get("attributes", {}).get("attr_FinalAcres") is not None
        for feature in features
        if isinstance(feature, dict)
    )
    if final_acres_non_null != 0:
        errors.append("WFIGS snapshot contains a non-null attr_FinalAcres value")

    inputs = identity.get("inputs", {})
    expected_identity_inputs = {
        "mtbs_preflight_sha256": "0cec99372a86b789ad939c70ab2c62081644664ba5a2cfe26538aae026e10729",
        "wfigs_snapshot_manifest_sha256": manifest_sha,
        "wfigs_snapshot_page_sha256": page_sha,
        "amendment_sha256": amendment_sha,
    }
    if inputs != expected_identity_inputs:
        errors.append("identity manifest input bindings differ")
    records = identity.get("records", [])
    if not isinstance(records, list) or len(records) != 187:
        errors.append("identity manifest does not account for 187 rows")
        records = []
    candidate_ids = [record.get("candidate_id") for record in records]
    if len(set(candidate_ids)) != len(candidate_ids):
        errors.append("identity manifest candidate IDs are not unique")
    reason_counts: Counter[str] = Counter()
    status_counts: Counter[str] = Counter()
    state_ready: Counter[str] = Counter()
    source_by_id: dict[str, dict[str, Any]] = {}
    for record in records:
        source = record.get("source_record", {})
        candidate_id = record.get("candidate_id")
        if candidate_id != _candidate_id(source):
            errors.append(f"candidate ID binding failed for {candidate_id}")
        reasons = record.get("reason_codes", [])
        reason_counts.update(reasons)
        exact_count = record.get("wfigs", {}).get("exact_match_count")
        final_acres = record.get("wfigs", {}).get("final_acres")
        if exact_count == 1 and final_acres is None and "WFIGS_AREA_UNKNOWN" not in reasons:
            errors.append(f"missing WFIGS final acres was not unknown for {candidate_id}")
        if exact_count == 0 and "NO_EXACT_WFIGS_MATCH" not in reasons:
            errors.append(f"missing WFIGS match was not retained for {candidate_id}")
        expected_status = (
            "excluded_before_geometry_hls"
            if set(reasons) & EXCLUSION_REASONS
            else "unknown_before_geometry_hls"
            if reasons
            else "ready_for_geometry_hls"
        )
        if record.get("status") != expected_status:
            errors.append(f"source status differs for {candidate_id}")
        status_counts[expected_status] += 1
        if expected_status == "ready_for_geometry_hls":
            state_ready[record.get("canonical_preview", {}).get("jurisdiction")] += 1
        source_by_id[candidate_id] = record
    if reason_counts.get("WFIGS_AREA_UNKNOWN") != 171:
        errors.append("WFIGS_AREA_UNKNOWN count is not 171")
    if reason_counts.get("NO_EXACT_WFIGS_MATCH") != 16:
        errors.append("NO_EXACT_WFIGS_MATCH count is not 16")
    if status_counts.get("ready_for_geometry_hls", 0) != 0:
        errors.append("a candidate unexpectedly reached geometry/HLS")
    if identity.get("summary", {}).get("reason_counts") != dict(sorted(reason_counts.items())):
        errors.append("identity reason summary differs from records")

    universe_inputs = universe.get("inputs", {})
    if universe_inputs != {
        "identity_maturity_manifest_sha256": identity_sha,
        "eligibility_profile_sha256": profile_sha,
        "prior_exclusion_manifest_sha256": prior_sha,
        "mtbs_shp_sha256": shp_sha,
        "mtbs_shx_sha256": shx_sha,
    }:
        errors.append("candidate universe input bindings differ")
    candidates = universe.get("candidates", [])
    if not isinstance(candidates, list) or len(candidates) != 187:
        errors.append("candidate universe does not contain 187 rows")
        candidates = []
    seen: set[str] = set()
    replay_counts: Counter[str] = Counter()
    for item in candidates:
        candidate = item.get("candidate", {})
        candidate_id = candidate.get("candidate_id")
        if candidate_id in seen:
            errors.append(f"duplicate candidate in universe: {candidate_id}")
        seen.add(candidate_id)
        source_record = source_by_id.get(candidate_id)
        if source_record is None:
            errors.append(f"candidate is not bound to identity manifest: {candidate_id}")
            continue
        if item.get("source_gate", {}).get("reason_codes") != source_record.get("reason_codes"):
            errors.append(f"source reasons changed for {candidate_id}")
        geometry = item.get("mtbs_geometry", {})
        index = geometry.get("source_row_index")
        if not isinstance(index, int):
            errors.append(f"missing geometry index for {candidate_id}")
        elif geometry.get("record_sha256") != _geometry_digest(
            mtbs_shp_path, mtbs_shx_path, index
        ):
            errors.append(f"geometry digest changed for {candidate_id}")
        replay = evaluate(candidate, profile, prior, prior_sha)
        if replay != item.get("evaluation"):
            errors.append(f"eligibility replay changed for {candidate_id}")
        replay_counts[replay["status"]] += 1
    summary = universe.get("summary", {})
    if summary.get("candidate_count") != 187:
        errors.append("candidate summary count changed")
    if summary.get("maximum_candidates_reaching_ecology_hls") != 0:
        errors.append("candidate upper bound is not zero")
    if summary.get("required_total_selectable_slots") != 36:
        errors.append("required selectable slot count changed")
    if summary.get("terminal_shortfall_proven") is not True:
        errors.append("terminal shortfall is not asserted")
    boundary = universe.get("boundary", {})
    if boundary.get("all_187_pre_exclusion_rows_accounted") is not True:
        errors.append("universe boundary does not account for all rows")
    if boundary.get("shortfall_cannot_be_rescued_without_protocol_change") is not True:
        errors.append("universe does not preserve the no-rescue boundary")
    if boundary.get("candidate_eligibility_assigned") is not False:
        errors.append("candidate eligibility was assigned despite terminal shortfall")
    if boundary.get("candidate_or_role_selected") is not False:
        errors.append("candidate or role selection occurred")

    results = {
        "wfigs_snapshot_manifest_sha256": manifest_sha,
        "wfigs_snapshot_page_sha256": page_sha,
        "wfigs_feature_count": len(features),
        "wfigs_non_null_final_acres_count": final_acres_non_null,
        "identity_manifest_sha256": identity_sha,
        "candidate_universe_sha256": universe_sha,
        "candidate_count": len(candidates),
        "source_status_counts": dict(sorted(status_counts.items())),
        "source_reason_counts": dict(sorted(reason_counts.items())),
        "eligibility_replay_status_counts": dict(sorted(replay_counts.items())),
        "maximum_selectable_slots_by_state": {
            state: state_ready.get(state, 0) for state in ("ID", "OR", "WA")
        },
        "maximum_selectable_slots_total": sum(state_ready.values()),
        "required_selectable_slots_by_state": {"ID": 12, "OR": 12, "WA": 12},
        "required_selectable_slots_total": 36,
        "milestone_1_disposition": "INCONCLUSIVE",
    }
    return errors, results


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--snapshot-manifest", required=True, type=Path)
    parser.add_argument("--snapshot-page", required=True, type=Path)
    parser.add_argument("--identity-manifest", required=True, type=Path)
    parser.add_argument("--candidate-universe", required=True, type=Path)
    parser.add_argument("--profile", required=True, type=Path)
    parser.add_argument("--prior", required=True, type=Path)
    parser.add_argument("--amendment", required=True, type=Path)
    parser.add_argument("--mtbs-shp", required=True, type=Path)
    parser.add_argument("--mtbs-shx", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    try:
        if args.output.exists():
            raise FileExistsError(f"refusing to overwrite: {args.output}")
        errors, results = validate(
            snapshot_manifest_path=args.snapshot_manifest,
            snapshot_page_path=args.snapshot_page,
            identity_path=args.identity_manifest,
            universe_path=args.candidate_universe,
            profile_path=args.profile,
            prior_path=args.prior,
            amendment_path=args.amendment,
            mtbs_shp_path=args.mtbs_shp,
            mtbs_shx_path=args.mtbs_shx,
        )
        receipt = {
            "schema_version": "1.0",
            "receipt_id": "E4-M1-INDEPENDENT-VALIDATION-2026-001",
            "validated_at_utc": datetime.now(timezone.utc).isoformat(
                timespec="seconds"
            ).replace("+00:00", "Z"),
            "status": "PASS" if not errors else "FAIL",
            "results": results,
            "errors": errors,
            "checks": [
                "exact snapshot page and allowlist binding",
                "187-row universe completeness and unique candidate IDs",
                "independent source-reason and status recount",
                "exact MTBS geometry-record hash replay",
                "candidate evaluator replay",
                "zero-slot upper bound under the frozen WFIGS final-acres rule",
                "no-rescue, no-selection, and no-imagery boundaries",
            ],
        }
        args.output.parent.mkdir(parents=True, exist_ok=True)
        payload = _canonical_bytes(receipt)
        with args.output.open("xb") as destination:
            destination.write(payload)
            destination.flush()
            os.fsync(destination.fileno())
        print(
            json.dumps(
                {
                    "output": str(args.output.resolve()),
                    "sha256": _sha256(args.output),
                    "size_bytes": args.output.stat().st_size,
                    "status": receipt["status"],
                    "results": results,
                    "errors": errors,
                },
                indent=2,
                sort_keys=True,
            )
        )
        return 0 if not errors else 1
    except Exception as exc:
        print(json.dumps({"status": "failed", "error": str(exc)}, indent=2))
        return 1


if __name__ == "__main__":
    sys.exit(main())
