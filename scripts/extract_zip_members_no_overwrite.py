"""Extract exact verified ZIP members into a new runtime directory."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import sys
import zipfile
from pathlib import Path, PurePosixPath


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        while chunk := source.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def _safe_name(name: str) -> PurePosixPath:
    normalized = name.replace("\\", "/")
    value = PurePosixPath(normalized)
    if not normalized or value.is_absolute() or ".." in value.parts:
        raise ValueError(f"unsafe ZIP member: {name}")
    return value


def extract(
    archive_path: Path,
    destination: Path,
    members: list[str],
    expected_archive_sha256: str,
) -> dict[str, object]:
    archive_path = archive_path.resolve(strict=True)
    destination = destination.resolve(strict=False)
    if _sha256(archive_path) != expected_archive_sha256:
        raise ValueError("archive SHA-256 differs from the verified identity")
    if destination.exists() or destination.is_symlink():
        raise FileExistsError(f"destination already exists: {destination}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.mkdir()
    extracted: list[dict[str, object]] = []
    with zipfile.ZipFile(archive_path) as archive:
        available = set(archive.namelist())
        if len(set(members)) != len(members):
            raise ValueError("requested member list contains duplicates")
        missing = sorted(set(members) - available)
        if missing:
            raise ValueError(f"requested ZIP members are missing: {missing}")
        for member in members:
            relative = _safe_name(member)
            target = (destination / Path(*relative.parts)).resolve(strict=False)
            try:
                target.relative_to(destination)
            except ValueError as exc:
                raise ValueError(f"member escapes extraction root: {member}") from exc
            target.parent.mkdir(parents=True, exist_ok=True)
            with archive.open(member) as source, target.open("xb") as sink:
                shutil.copyfileobj(source, sink, length=1024 * 1024)
                sink.flush()
                os.fsync(sink.fileno())
            extracted.append(
                {
                    "member": member,
                    "path": str(target),
                    "size_bytes": target.stat().st_size,
                    "sha256": _sha256(target),
                }
            )
    return {
        "archive": str(archive_path),
        "archive_sha256": expected_archive_sha256,
        "destination": str(destination),
        "files": extracted,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive", required=True, type=Path)
    parser.add_argument("--destination", required=True, type=Path)
    parser.add_argument("--member", action="append", required=True)
    parser.add_argument("--expected-archive-sha256", required=True)
    args = parser.parse_args()
    try:
        result = extract(
            args.archive,
            args.destination,
            args.member,
            args.expected_archive_sha256,
        )
    except Exception as exc:
        print(json.dumps({"status": "failed", "error": str(exc)}, indent=2))
        return 1
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
