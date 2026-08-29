"""Enumerate the complete MTBS 2021-2022 ID/OR/WA universe before amendment."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from burnlens_e4.dbf import Reader  # noqa: E402


ADMITTED_FIELDS = {
    "Event_ID",
    "irwinID",
    "Incid_Name",
    "Incid_Type",
    "Map_ID",
    "Map_Prog",
    "Asmnt_Type",
    "BurnBndAc",
    "BurnBndLat",
    "BurnBndLon",
    "Ig_Date",
}
TARGET_STATES = {"ID", "OR", "WA"}
TARGET_YEARS = {2021, 2022}


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        while chunk := source.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def normalize_identifier(value: object) -> str | None:
    if value is None:
        return None
    normalized = str(value).strip().strip("{}").upper()
    return normalized or None


def normalize_name(value: object) -> str:
    return " ".join(re.sub(r"[^A-Z0-9]+", " ", str(value or "").upper()).split())


def _prior_indexes(prior: dict[str, Any]) -> tuple[dict[str, set[str]], dict[tuple[str, int], set[str]]]:
    exact: dict[str, set[str]] = defaultdict(set)
    fallback: dict[tuple[str, int], set[str]] = defaultdict(set)
    for event in prior.get("events", []):
        exclusion_id = event.get("exclusion_id")
        if not isinstance(exclusion_id, str):
            continue
        for key in (
            "unique_fire_identifier",
            "source_global_id",
            "source_event_id",
            "project_event_id",
        ):
            identifier = normalize_identifier(event.get(key))
            if identifier:
                exact[identifier].add(exclusion_id)
        if "experiment-one-final-dataset" in event.get("prior_uses", []):
            name = normalize_name(event.get("canonical_name"))
            year = event.get("year")
            if name and isinstance(year, int):
                fallback[(name, year)].add(exclusion_id)
    return exact, fallback


def enumerate_rows(dbf_path: Path, prior_path: Path) -> dict[str, Any]:
    prior = json.loads(prior_path.read_text(encoding="utf-8"))
    exact_prior, fallback_prior = _prior_indexes(prior)
    rows: list[dict[str, Any]] = []
    by_state_year_type: Counter[tuple[str, int, str]] = Counter()
    event_ids: Counter[str] = Counter()
    irwin_ids: Counter[str] = Counter()
    reader = Reader(dbf_path)
    for row_index, values in reader.records(ADMITTED_FIELDS):
        event_id = str(values["Event_ID"] or "")
        state = event_id[:2]
        ignition = values["Ig_Date"]
        year = int(str(ignition)[:4]) if ignition else None
        if year not in TARGET_YEARS or state not in TARGET_STATES:
            continue
        if values["BurnBndLat"] is None or values["BurnBndLon"] is None:
            continue
        identifiers = {
            identifier
            for identifier in (
                normalize_identifier(values.get("Event_ID")),
                normalize_identifier(values.get("irwinID")),
                normalize_identifier(values.get("Map_ID")),
            )
            if identifier
        }
        exact_matches = sorted(
            {exclusion_id for identifier in identifiers for exclusion_id in exact_prior.get(identifier, set())}
        )
        fallback_matches = sorted(
            fallback_prior.get((normalize_name(values.get("Incid_Name")), year), set())
        )
        prior_matches = exact_matches or fallback_matches
        prior_match_mode = "exact_identifier" if exact_matches else (
            "experiment_one_name_year" if fallback_matches else None
        )
        event_ids[event_id] += 1
        irwin = normalize_identifier(values.get("irwinID"))
        if irwin:
            irwin_ids[irwin] += 1
        by_state_year_type[(state, year, str(values["Incid_Type"]))] += 1
        rows.append(
            {
                "source_row_index": row_index,
                "state_from_mtbs_event_id": state,
                "year": year,
                "attributes": values,
                "prior_exclusion_ids": prior_matches,
                "prior_exclusion_match_mode": prior_match_mode,
                "eligibility_status": "not_evaluated_protocol_blocked",
                "protocol_blockers": [
                    "MTBS_INCIDENT_TYPE_LITERAL_MISMATCH",
                    "WFIGS_STATE_CODE_LITERAL_MISMATCH",
                ],
            }
        )
    return {
        "schema_version": "1.0",
        "manifest_id": "E4-M1-MTBS-UNIVERSE-PREFLIGHT-2026-001",
        "status": "preflight_blocked_before_eligibility",
        "source_dbf_sha256": _sha256(dbf_path),
        "prior_exclusion_manifest_sha256": _sha256(prior_path),
        "field_policy": {
            "admitted_fields": sorted(ADMITTED_FIELDS),
            "denied_field_values_opened": False,
        },
        "universe_rule_applied": "MTBS rows with 2021 or 2022 ignition, Event_ID state prefix ID/OR/WA, and non-null mapped centroid fields; no eligibility exclusion applied before admission.",
        "summary": {
            "row_count": len(rows),
            "by_state_year_type": [
                {"state": key[0], "year": key[1], "incident_type": key[2], "count": count}
                for key, count in sorted(by_state_year_type.items())
            ],
            "mtbs_incid_type_exact_WF_count": sum(
                row["attributes"]["Incid_Type"] == "WF" for row in rows
            ),
            "mtbs_incid_type_exact_Wildfire_count": sum(
                row["attributes"]["Incid_Type"] == "Wildfire" for row in rows
            ),
            "wildfire_and_mtbs_area_at_least_1000_count": sum(
                row["attributes"]["Incid_Type"] == "Wildfire"
                and row["attributes"]["BurnBndAc"] >= 1000
                for row in rows
            ),
            "rows_with_prior_exclusion_match": sum(bool(row["prior_exclusion_ids"]) for row in rows),
            "duplicate_event_id_groups": sum(count > 1 for count in event_ids.values()),
            "duplicate_non_null_irwin_id_groups": sum(count > 1 for count in irwin_ids.values()),
        },
        "rows": rows,
        "limitations": [
            "No row is eligible while the frozen literal state/type semantics conflict with the admitted source encodings.",
            "WFIGS rows, HLS granules, EPA polygon rows, imagery, labels, rasters, model outputs, metrics, and denied MTBS field values were not opened by this manifest.",
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dbf", required=True, type=Path)
    parser.add_argument("--prior", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    try:
        manifest = enumerate_rows(args.dbf, args.prior)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        payload = json.dumps(manifest, indent=2, sort_keys=True) + "\n"
        with args.output.open("x", encoding="utf-8", newline="\n") as destination:
            destination.write(payload)
            destination.flush()
            os.fsync(destination.fileno())
        receipt = {
            "output": str(args.output.resolve()),
            "sha256": _sha256(args.output),
            "size_bytes": args.output.stat().st_size,
            "summary": manifest["summary"],
            "status": manifest["status"],
        }
    except Exception as exc:
        print(json.dumps({"status": "failed", "error": str(exc)}, indent=2))
        return 1
    print(json.dumps(receipt, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
