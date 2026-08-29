"""Capture the exact approved WFIGS metadata snapshot with no overwrite."""

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
STATE_WHERE = f"{DATE_WINDOW} AND attr_POOState IN ('US-ID','US-OR','US-WA')"
ORDER_BY = "GlobalID ASC"
USER_AGENT = "BurnLens-E4-WFIGS-Metadata/1.0"
SNAPSHOT_ID = "E4-M1-WFIGS-SNAPSHOT-2026-001"

ADMITTED_FIELDS = (
    "GlobalID",
    "poly_IRWINID",
    "poly_FORID",
    "poly_SourceGlobalID",
    "poly_Source",
    "poly_FeatureAccess",
    "poly_FeatureStatus",
    "poly_IsVisible",
    "poly_DeleteThis",
    "poly_DateCurrent",
    "poly_PolygonDateTime",
    "poly_Acres_AutoCalc",
    "attr_IrwinID",
    "attr_FORID",
    "attr_SourceGlobalID",
    "attr_Source",
    "attr_UniqueFireIdentifier",
    "attr_IncidentName",
    "attr_IncidentTypeCategory",
    "attr_FireDiscoveryDateTime",
    "attr_ContainmentDateTime",
    "attr_FireOutDateTime",
    "attr_FFReportApprovedDate",
    "attr_FinalAcres",
    "attr_POOState",
    "attr_IsValid",
    "attr_IsQuarantined",
    "attr_IsCpxChild",
    "attr_CpxID",
    "attr_CpxName",
)


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        while chunk := source.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def _request(uri: str, parameters: dict[str, str] | None = None) -> tuple[bytes, dict[str, Any]]:
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
    with urllib.request.urlopen(request, timeout=180) as response:
        data = response.read()
    value = json.loads(data)
    if not isinstance(value, dict):
        raise RuntimeError("ArcGIS response is not an object")
    if "error" in value:
        raise RuntimeError(f"ArcGIS query error: {value['error']}")
    return data, value


def _write_exclusive(path: Path, data: bytes) -> None:
    with path.open("xb") as destination:
        destination.write(data)
        destination.flush()
        os.fsync(destination.fileno())


def _canonical_bytes(value: Any) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode("utf-8")


def capture(output_directory: Path) -> dict[str, Any]:
    output_directory.mkdir(parents=True, exist_ok=False)
    captured_at = _utc_now()
    layer_bytes, layer_before = _request(LAYER)
    available_fields = {field.get("name") for field in layer_before.get("fields", [])}
    missing = sorted(set(ADMITTED_FIELDS) - available_fields)
    if missing:
        raise RuntimeError(f"approved WFIGS fields are missing: {missing}")
    if layer_before.get("objectIdField") != "OBJECTID":
        raise RuntimeError("WFIGS object ID field changed")
    if layer_before.get("globalIdField") != "GlobalID":
        raise RuntimeError("WFIGS global ID field changed")
    capabilities = layer_before.get("advancedQueryCapabilities", {})
    if capabilities.get("supportsPagination") is not True:
        raise RuntimeError("WFIGS pagination support is unavailable")
    if capabilities.get("supportsOrderBy") is not True:
        raise RuntimeError("WFIGS order-by support is unavailable")
    max_records = layer_before.get("maxRecordCount")
    if not isinstance(max_records, int) or max_records <= 0:
        raise RuntimeError("WFIGS maxRecordCount is invalid")

    layer_path = output_directory / "layer-before.json"
    _write_exclusive(layer_path, layer_bytes)
    count_parameters = {
        "f": "json",
        "where": STATE_WHERE,
        "returnCountOnly": "true",
    }
    count_before_bytes, count_before = _request(QUERY, count_parameters)
    expected_count = count_before.get("count")
    if not isinstance(expected_count, int) or expected_count < 0:
        raise RuntimeError("WFIGS count response is invalid")
    count_before_path = output_directory / "count-before.json"
    _write_exclusive(count_before_path, count_before_bytes)

    page_receipts: list[dict[str, Any]] = []
    observed_count = 0
    offset = 0
    page_number = 1
    while observed_count < expected_count:
        parameters = {
            "f": "json",
            "where": STATE_WHERE,
            "outFields": ",".join(ADMITTED_FIELDS),
            "returnGeometry": "true",
            "outSR": "4326",
            "returnZ": "false",
            "returnM": "false",
            "orderByFields": ORDER_BY,
            "resultOffset": str(offset),
            "resultRecordCount": str(max_records),
        }
        page_bytes, page = _request(QUERY, parameters)
        features = page.get("features")
        if not isinstance(features, list) or not features:
            raise RuntimeError("WFIGS returned an empty page before the declared count")
        for feature in features:
            if not isinstance(feature, dict) or not isinstance(feature.get("attributes"), dict):
                raise RuntimeError("WFIGS feature structure changed")
            returned = set(feature["attributes"])
            if returned != set(ADMITTED_FIELDS):
                raise RuntimeError("WFIGS returned fields outside or below the approved allowlist")
        page_path = output_directory / f"page-{page_number:04d}.json"
        _write_exclusive(page_path, page_bytes)
        page_receipts.append(
            {
                "page": page_number,
                "result_offset": offset,
                "feature_count": len(features),
                "sha256": _sha256_bytes(page_bytes),
                "size_bytes": len(page_bytes),
                "file_name": page_path.name,
                "exceeded_transfer_limit": page.get("exceededTransferLimit") is True,
            }
        )
        observed_count += len(features)
        offset += len(features)
        page_number += 1
        if len(features) > max_records:
            raise RuntimeError("WFIGS page exceeded maxRecordCount")
        if len(features) < max_records and observed_count < expected_count:
            raise RuntimeError("WFIGS pagination ended before the declared count")

    count_after_bytes, count_after = _request(QUERY, count_parameters)
    count_after_path = output_directory / "count-after.json"
    _write_exclusive(count_after_path, count_after_bytes)
    layer_after_bytes, layer_after = _request(LAYER)
    layer_after_path = output_directory / "layer-after.json"
    _write_exclusive(layer_after_path, layer_after_bytes)
    if count_after.get("count") != expected_count:
        raise RuntimeError("WFIGS count changed during capture")
    if observed_count != expected_count:
        raise RuntimeError("WFIGS observed count differs from the declared count")
    before_edit = layer_before.get("editingInfo", {}).get("lastEditDate")
    after_edit = layer_after.get("editingInfo", {}).get("lastEditDate")
    if before_edit != after_edit:
        raise RuntimeError("WFIGS dataLastEditDate changed during capture")

    selected_schema = {
        field["name"]: {
            "alias": field.get("alias"),
            "type": field.get("type"),
            "length": field.get("length"),
        }
        for field in layer_before.get("fields", [])
        if field.get("name") in ADMITTED_FIELDS
    }
    manifest = {
        "schema_version": "1.0",
        "snapshot_id": SNAPSHOT_ID,
        "status": "captured_exact_no_overwrite",
        "captured_at_utc": captured_at,
        "source": {
            "source_id": "NIFC-WFIGS-PERIMETERS-5E72B169",
            "layer_uri": LAYER,
            "layer_name": layer_before.get("name"),
            "layer_type": layer_before.get("type"),
            "object_id_field": layer_before.get("objectIdField"),
            "global_id_field": layer_before.get("globalIdField"),
            "max_record_count": max_records,
            "data_last_edit_date_epoch_ms": before_edit,
            "selected_field_schema": selected_schema,
        },
        "protocol": {
            "amendment_id": "E4-M1-LITERAL-ENCODING-AMENDMENT-2026-001",
            "where": STATE_WHERE,
            "order_by": ORDER_BY,
            "out_fields": list(ADMITTED_FIELDS),
            "return_geometry": True,
            "out_spatial_reference": 4326,
            "other_alias_or_fallback_mapping_allowed": False,
        },
        "capture": {
            "declared_count_before": expected_count,
            "observed_feature_count": observed_count,
            "declared_count_after": count_after.get("count"),
            "data_last_edit_date_stable": True,
            "page_count": len(page_receipts),
            "pages": page_receipts,
            "layer_before_sha256": _sha256(layer_path),
            "layer_after_sha256": _sha256(layer_after_path),
            "count_before_sha256": _sha256(count_before_path),
            "count_after_sha256": _sha256(count_after_path),
        },
        "boundary": {
            "approved_fields_only": True,
            "geometry_returned": True,
            "imagery_or_labels_opened": False,
            "candidate_eligibility_assigned": False,
            "credentials_used": False,
        },
    }
    manifest_path = output_directory / "manifest.json"
    _write_exclusive(manifest_path, _canonical_bytes(manifest))
    return {
        "output_directory": str(output_directory.resolve()),
        "manifest": str(manifest_path.resolve()),
        "manifest_sha256": _sha256(manifest_path),
        "manifest_size_bytes": manifest_path.stat().st_size,
        "feature_count": observed_count,
        "page_count": len(page_receipts),
        "data_last_edit_date_epoch_ms": before_edit,
        "status": manifest["status"],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-directory", required=True, type=Path)
    args = parser.parse_args()
    try:
        result = capture(args.output_directory)
    except Exception as exc:
        print(json.dumps({"status": "failed", "error": str(exc)}, indent=2))
        return 1
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
