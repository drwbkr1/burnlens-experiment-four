"""Capture a hash-bound WFIGS literal-encoding probe without geometry."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


LAYER = "https://services3.arcgis.com/T4QMspbfLg3qTGWY/arcgis/rest/services/WFIGS_Interagency_Perimeters/FeatureServer/0"
QUERY = f"{LAYER}/query"
DATE_WINDOW = "attr_FireDiscoveryDateTime >= DATE '2021-01-01 00:00:00' AND attr_FireDiscoveryDateTime < DATE '2023-01-01 00:00:00'"
EXACT_STATE_WHERE = f"{DATE_WINDOW} AND attr_POOState IN ('ID','OR','WA')"
PREFIXED_STATE_WHERE = f"{DATE_WINDOW} AND attr_POOState IN ('US-ID','US-OR','US-WA')"
USER_AGENT = "BurnLens-E4-WFIGS-Metadata/1.0"


def _request(uri: str, parameters: dict[str, str] | None = None) -> dict[str, Any]:
    if parameters is None:
        request = urllib.request.Request(f"{uri}?f=pjson", headers={"User-Agent": USER_AGENT})
    else:
        body = urllib.parse.urlencode(parameters).encode("ascii")
        request = urllib.request.Request(
            uri,
            data=body,
            headers={
                "User-Agent": USER_AGENT,
                "Content-Type": "application/x-www-form-urlencoded",
            },
            method="POST",
        )
    with urllib.request.urlopen(request, timeout=120) as response:
        value = json.load(response)
    if "error" in value:
        raise RuntimeError(f"ArcGIS query error: {value['error']}")
    return value


def capture() -> dict[str, Any]:
    layer = _request(LAYER)
    selected_fields = {
        item["name"]: {"type": item.get("type"), "length": item.get("length")}
        for item in layer.get("fields", [])
        if item.get("name") in {
            "GlobalID",
            "attr_FireDiscoveryDateTime",
            "attr_IncidentTypeCategory",
            "attr_POOState",
        }
    }
    exact_parameters = {"f": "json", "where": EXACT_STATE_WHERE, "returnCountOnly": "true"}
    prefixed_parameters = {"f": "json", "where": PREFIXED_STATE_WHERE, "returnCountOnly": "true"}
    statistics = json.dumps(
        [
            {
                "statisticType": "count",
                "onStatisticField": "GlobalID",
                "outStatisticFieldName": "record_count",
            }
        ],
        separators=(",", ":"),
        sort_keys=True,
    )
    grouped_parameters = {
        "f": "json",
        "where": PREFIXED_STATE_WHERE,
        "outFields": "attr_POOState,attr_IncidentTypeCategory",
        "returnGeometry": "false",
        "groupByFieldsForStatistics": "attr_POOState,attr_IncidentTypeCategory",
        "orderByFields": "attr_POOState ASC,attr_IncidentTypeCategory ASC",
        "outStatistics": statistics,
    }
    exact = _request(QUERY, exact_parameters)
    prefixed = _request(QUERY, prefixed_parameters)
    grouped = _request(QUERY, grouped_parameters)
    groups = sorted(
        (feature.get("attributes", {}) for feature in grouped.get("features", [])),
        key=lambda item: (
            str(item.get("attr_POOState")),
            str(item.get("attr_IncidentTypeCategory")),
        ),
    )
    return {
        "schema_version": "1.0",
        "probe_id": "E4-M1-WFIGS-ENCODING-PROBE-2026-001",
        "captured_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z"),
        "layer": {
            "uri": LAYER,
            "name": layer.get("name"),
            "type": layer.get("type"),
            "object_id_field": layer.get("objectIdField"),
            "global_id_field": layer.get("globalIdField"),
            "max_record_count": layer.get("maxRecordCount"),
            "supports_pagination": layer.get("advancedQueryCapabilities", {}).get("supportsPagination"),
            "supports_order_by": layer.get("advancedQueryCapabilities", {}).get("supportsOrderBy"),
            "data_last_edit_date_epoch_ms": layer.get("editingInfo", {}).get("lastEditDate"),
            "selected_field_schema": selected_fields,
        },
        "queries": {
            "exact_unprefixed_states": {
                "parameters": exact_parameters,
                "count": exact.get("count"),
            },
            "exact_prefixed_states": {
                "parameters": prefixed_parameters,
                "count": prefixed.get("count"),
            },
            "prefixed_state_incident_type_groups": {
                "parameters": grouped_parameters,
                "groups": groups,
            },
        },
        "boundary": {
            "return_geometry": False,
            "full_feature_snapshot_created": False,
            "candidate_eligibility_assigned": False,
        },
    }


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    try:
        value = capture()
        args.output.parent.mkdir(parents=True, exist_ok=True)
        payload = json.dumps(value, indent=2, sort_keys=True) + "\n"
        with args.output.open("x", encoding="utf-8", newline="\n") as destination:
            destination.write(payload)
            destination.flush()
            os.fsync(destination.fileno())
        receipt = {
            "output": str(args.output.resolve()),
            "sha256": _sha256(args.output),
            "size_bytes": args.output.stat().st_size,
            "exact_unprefixed_state_count": value["queries"]["exact_unprefixed_states"]["count"],
            "exact_prefixed_state_count": value["queries"]["exact_prefixed_states"]["count"],
            "groups": value["queries"]["prefixed_state_incident_type_groups"]["groups"],
        }
    except Exception as exc:
        print(json.dumps({"status": "failed", "error": str(exc)}, indent=2))
        return 1
    print(json.dumps(receipt, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
