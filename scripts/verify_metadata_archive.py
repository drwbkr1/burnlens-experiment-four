"""Hash and structurally verify the exact MTBS or EPA metadata archive."""

from __future__ import annotations

import argparse
import hashlib
import json
import struct
import sys
import zipfile
from pathlib import Path, PurePosixPath
from typing import BinaryIO


REQUIRED_FIELDS = {
    "epa-level3": {"US_L3CODE", "US_L3NAME"},
    "mtbs-perimeters-v12": {
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
    },
}
EXPECTED_BASE = {
    "epa-level3": "us_eco_l3",
    "mtbs-perimeters-v12": "mtbs_perims_DD",
}
REQUIRED_COMPONENTS = {".shp", ".shx", ".dbf", ".prj"}


def _digests(path: Path) -> tuple[str, str, int]:
    sha256 = hashlib.sha256()
    md5 = hashlib.md5(usedforsecurity=False)
    size = 0
    with path.open("rb") as source:
        while chunk := source.read(1024 * 1024):
            sha256.update(chunk)
            md5.update(chunk)
            size += len(chunk)
    return sha256.hexdigest(), md5.hexdigest(), size


def _safe_member(name: str) -> bool:
    normalized = name.replace("\\", "/")
    path = PurePosixPath(normalized)
    return bool(normalized) and not path.is_absolute() and ".." not in path.parts


def _dbf_fields(source: BinaryIO) -> list[str]:
    header = source.read(32)
    if len(header) != 32:
        raise ValueError("DBF header is truncated")
    header_length = struct.unpack("<H", header[8:10])[0]
    if header_length < 33 or (header_length - 33) % 32 != 0:
        raise ValueError("DBF header length is invalid")
    fields: list[str] = []
    for _ in range((header_length - 33) // 32):
        descriptor = source.read(32)
        if len(descriptor) != 32:
            raise ValueError("DBF field descriptor is truncated")
        name = descriptor[:11].split(b"\0", 1)[0].decode("ascii", errors="strict")
        if not name:
            raise ValueError("DBF field name is empty")
        fields.append(name)
    terminator = source.read(1)
    if terminator != b"\r":
        raise ValueError("DBF field descriptor terminator is invalid")
    return fields


def verify(path: Path, kind: str) -> dict[str, object]:
    path = path.resolve()
    sha256, md5, size = _digests(path)
    expected_base = EXPECTED_BASE[kind]
    with zipfile.ZipFile(path) as archive:
        names = archive.namelist()
        unsafe = sorted(name for name in names if not _safe_member(name))
        if unsafe:
            raise ValueError(f"unsafe ZIP members: {unsafe}")
        bad_crc = archive.testzip()
        if bad_crc is not None:
            raise ValueError(f"ZIP CRC failure: {bad_crc}")
        matching = {
            PurePosixPath(name.replace("\\", "/")).suffix.lower(): name
            for name in names
            if PurePosixPath(name.replace("\\", "/")).stem.casefold()
            == expected_base.casefold()
        }
        missing = sorted(REQUIRED_COMPONENTS - set(matching))
        if missing:
            raise ValueError(f"missing required shapefile components: {missing}")
        dbf_name = matching[".dbf"]
        with archive.open(dbf_name) as dbf:
            fields = _dbf_fields(dbf)
    missing_fields = sorted(REQUIRED_FIELDS[kind] - set(fields))
    if missing_fields:
        raise ValueError(f"missing required DBF fields: {missing_fields}")
    return {
        "kind": kind,
        "path": str(path),
        "size_bytes": size,
        "sha256": sha256,
        "md5": md5,
        "zip_member_count": len(names),
        "zip_members": sorted(names),
        "bad_crc_member": None,
        "shapefile_base": expected_base,
        "required_components": sorted(REQUIRED_COMPONENTS),
        "dbf_fields": fields,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("path", type=Path)
    parser.add_argument("--kind", choices=sorted(REQUIRED_FIELDS), required=True)
    args = parser.parse_args()
    try:
        result = verify(args.path, args.kind)
    except Exception as exc:
        print(json.dumps({"status": "failed", "error": str(exc)}, indent=2))
        return 1
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
