"""Validate the static prior-event exclusion inventory.

The manifest is a public-safe metadata control. This validator checks internal
identity, provenance-tier, count, and disposition invariants without reaching
into prior repositories or accessing any scientific source body.
"""

from __future__ import annotations

import json
import re
import sys
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MANIFEST_PATH = (
    ROOT
    / "records"
    / "metadata"
    / "EXPERIMENT-FOUR-PRIOR-EVENT-EXCLUSION-MANIFEST-2026-001.json"
)
SHA256 = re.compile(r"^[0-9a-f]{64}$")
GIT_OBJECT = re.compile(r"^[0-9a-f]{40}$")


def validate() -> list[str]:
    errors: list[str] = []
    try:
        manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        return [f"unable to load exclusion manifest: {exc}"]

    events = manifest.get("events")
    if not isinstance(events, list):
        return ["events must be a list"]
    if len(events) != 68:
        errors.append(f"expected 68 permanent exclusions, found {len(events)}")

    summary = manifest.get("summary", {})
    expected_summary = {
        "experiment_one_accepted_events": 6,
        "experiment_three_additional_events": 0,
        "experiment_two_public_accepted_events": 0,
        "experiment_two_b_local_candidate_rows": 66,
        "experiment_two_b_local_unique_events": 62,
        "total_unique_permanent_exclusions": 68,
        "unresolved_duplicate_identities": 0,
        "external_source_adoptions": 0,
        "scientific_source_bodies_opened": 0,
    }
    for key, expected in expected_summary.items():
        if summary.get(key) != expected:
            errors.append(f"summary.{key} must be {expected!r}")

    exclusion_ids = [event.get("exclusion_id") for event in events]
    expected_ids = [f"E4-EXCL-{index:04d}" for index in range(1, 69)]
    if exclusion_ids != expected_ids:
        errors.append("exclusion IDs are not complete, ordered, and gap-free")

    project_ids = [event.get("project_event_id") for event in events]
    duplicate_project_ids = sorted(
        value for value, count in Counter(project_ids).items() if value and count > 1
    )
    if duplicate_project_ids:
        errors.append(f"duplicate project_event_id values: {duplicate_project_ids}")

    tiers = Counter(event.get("provenance_tier") for event in events)
    if tiers != {
        "accepted-public": 6,
        "unaccepted-local-conservative-exclusion": 62,
    }:
        errors.append(f"unexpected provenance-tier counts: {dict(tiers)}")

    for event in events:
        exclusion_id = event.get("exclusion_id", "<missing>")
        if event.get("disposition") != "permanently-excluded":
            errors.append(f"{exclusion_id} is not permanently excluded")
        prior_uses = event.get("prior_uses")
        if not isinstance(prior_uses, list) or not prior_uses:
            errors.append(f"{exclusion_id} has no prior-use provenance")
        if event.get("provenance_tier") == "accepted-public":
            if event.get("state") is not None:
                errors.append(f"{exclusion_id} infers an unrecorded Experiment One state")
            if len(event.get("source_product_native_ids", [])) != 2:
                errors.append(f"{exclusion_id} lacks the two bound source scenes")
            for key in ("scene_group_id", "geography_group_id", "time_group_id"):
                if not event.get(key):
                    errors.append(f"{exclusion_id} lacks {key}")
        else:
            if event.get("state") not in {"ID", "OR", "WA"}:
                errors.append(f"{exclusion_id} has an invalid state")
            if not isinstance(event.get("year"), int):
                errors.append(f"{exclusion_id} has an invalid year")
            for key in (
                "unique_fire_identifier",
                "source_event_id",
                "source_global_id",
            ):
                if not event.get(key):
                    errors.append(f"{exclusion_id} lacks {key}")

    e2_events = [
        event
        for event in events
        if event.get("provenance_tier") == "unaccepted-local-conservative-exclusion"
    ]
    for key in ("unique_fire_identifier", "source_event_id", "source_global_id"):
        values = [event.get(key) for event in e2_events]
        if len(values) != len(set(values)):
            errors.append(f"Experiment Two {key} values are not unique")

    revisions = manifest.get("source_revisions")
    if not isinstance(revisions, list) or len(revisions) != 4:
        errors.append("source_revisions must retain four provenance surfaces")
    else:
        for revision in revisions:
            for record in revision.get("records", []):
                sha = record.get("sha256")
                blob = record.get("git_blob")
                if sha is not None and not SHA256.fullmatch(sha):
                    errors.append(f"invalid source SHA-256 for {record.get('path')}")
                if blob is not None and not GIT_OBJECT.fullmatch(blob):
                    errors.append(f"invalid Git object for {record.get('path')}")
            record = revision.get("record")
            if isinstance(record, dict) and not GIT_OBJECT.fullmatch(
                str(record.get("git_blob", ""))
            ):
                errors.append(f"invalid Git object for {record.get('path')}")

    if manifest.get("disposition") != (
        "PASS-prior-event-exclusion-inventory-complete-for-inspected-records"
    ):
        errors.append("manifest disposition is not the bounded PASS")
    return errors


def main() -> int:
    errors = validate()
    if errors:
        print("Prior-event exclusions: FAIL")
        for error in errors:
            print(f"- {error}")
        return 1
    print("Prior-event exclusions: PASS (68 identities permanently excluded)")
    print("External source adoption: NONE; scientific source bodies opened: 0")
    return 0


if __name__ == "__main__":
    sys.exit(main())
