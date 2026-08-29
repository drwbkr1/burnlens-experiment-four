"""Acquire one public HTTPS object into a new staging file without overwrite."""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any


USER_AGENT = "BurnLens-E4-Controlled-Intake/1.0"


def _https_uri(value: str) -> str:
    parsed = urllib.parse.urlparse(value)
    if parsed.scheme.lower() != "https" or not parsed.netloc:
        raise ValueError("source URI must be an absolute HTTPS URL")
    if parsed.username or parsed.password:
        raise ValueError("source URI must not contain user information")
    return value


def acquire(uri: str, destination: Path, expected_size: int | None = None) -> dict[str, Any]:
    _https_uri(uri)
    destination = destination.resolve()
    destination.parent.mkdir(parents=True, exist_ok=True)
    request = urllib.request.Request(
        uri,
        headers={"User-Agent": USER_AGENT, "Accept": "application/octet-stream, application/zip"},
        method="GET",
    )
    bytes_written = 0
    response: Any = None
    try:
        with destination.open("xb") as sink:
            response = urllib.request.urlopen(request, timeout=120)
            final_uri = response.geturl()
            _https_uri(final_uri)
            status = getattr(response, "status", None)
            if status != 200:
                raise RuntimeError(f"unexpected HTTP status: {status}")
            header_size = response.headers.get("Content-Length")
            declared_size = int(header_size) if header_size is not None else None
            if expected_size is not None and declared_size != expected_size:
                raise RuntimeError(
                    f"remote Content-Length {declared_size!r} differs from expected {expected_size}"
                )
            while True:
                chunk = response.read(1024 * 1024)
                if not chunk:
                    break
                sink.write(chunk)
                bytes_written += len(chunk)
            sink.flush()
            os.fsync(sink.fileno())
        if expected_size is not None and bytes_written != expected_size:
            raise RuntimeError(
                f"downloaded size {bytes_written} differs from expected {expected_size}"
            )
        return {
            "status": status,
            "final_uri": final_uri,
            "content_length": declared_size,
            "content_type": response.headers.get_content_type(),
            "content_disposition": response.headers.get("Content-Disposition"),
            "etag": response.headers.get("ETag"),
            "last_modified": response.headers.get("Last-Modified"),
            "accept_ranges": response.headers.get("Accept-Ranges"),
            "local_bytes": bytes_written,
            "destination": str(destination),
        }
    finally:
        if response is not None:
            response.close()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--uri", required=True)
    parser.add_argument("--destination", required=True, type=Path)
    parser.add_argument("--expected-size", type=int)
    args = parser.parse_args()
    try:
        result = acquire(args.uri, args.destination, args.expected_size)
    except Exception as exc:  # retain partial bytes for controlled failure evidence
        print(json.dumps({"status": "failed", "error": str(exc)}, indent=2))
        return 1
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
