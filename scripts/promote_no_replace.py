"""Promote verified bytes through an atomic same-filesystem no-replace link."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import stat
import sys
import uuid
from pathlib import Path


def _digest(path: Path) -> tuple[str, int]:
    digest = hashlib.sha256()
    size = 0
    with path.open("rb") as source:
        while chunk := source.read(1024 * 1024):
            digest.update(chunk)
            size += len(chunk)
    return digest.hexdigest(), size


def promote(
    source: Path,
    destination: Path,
    expected_sha256: str,
    expected_size: int,
) -> dict[str, object]:
    source = source.resolve(strict=True)
    destination = destination.resolve(strict=False)
    if not source.is_file() or source.is_symlink():
        raise ValueError("source must be a regular non-symlink file")
    if destination.exists() or destination.is_symlink():
        raise FileExistsError(f"destination already exists: {destination}")
    source_sha256, source_size = _digest(source)
    if source_sha256 != expected_sha256 or source_size != expected_size:
        raise ValueError("source identity differs from the verified identity")
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.parent / f".{destination.name}.promoting-{uuid.uuid4().hex}"
    try:
        descriptor = os.open(temporary, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        with os.fdopen(descriptor, "wb") as sink, source.open("rb") as input_stream:
            shutil.copyfileobj(input_stream, sink, length=1024 * 1024)
            sink.flush()
            os.fsync(sink.fileno())
        temporary_sha256, temporary_size = _digest(temporary)
        if temporary_sha256 != expected_sha256 or temporary_size != expected_size:
            raise ValueError("destination-directory temporary copy failed verification")
        os.link(temporary, destination)
        temporary.unlink()
        os.chmod(destination, stat.S_IREAD)
        promoted_sha256, promoted_size = _digest(destination)
        if promoted_sha256 != expected_sha256 or promoted_size != expected_size:
            raise ValueError("promoted file failed final verification")
        return {
            "source": str(source),
            "destination": str(destination),
            "promotion_primitive": "same-filesystem hard-link create without replace",
            "sha256": promoted_sha256,
            "size_bytes": promoted_size,
            "read_only": True,
        }
    except Exception:
        # Retain a completed temporary copy as failure evidence. Remove only an
        # empty temporary created before any bytes could be copied.
        if temporary.exists() and temporary.stat().st_size == 0:
            temporary.unlink()
        raise


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", required=True, type=Path)
    parser.add_argument("--destination", required=True, type=Path)
    parser.add_argument("--expected-sha256", required=True)
    parser.add_argument("--expected-size", required=True, type=int)
    args = parser.parse_args()
    try:
        result = promote(
            args.source,
            args.destination,
            args.expected_sha256,
            args.expected_size,
        )
    except Exception as exc:
        print(json.dumps({"status": "failed", "error": str(exc)}, indent=2))
        return 1
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
