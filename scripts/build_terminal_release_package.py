#!/usr/bin/env python3
"""Build a deterministic, no-overwrite replay ZIP from one clean Git revision."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import zipfile
from pathlib import Path


RELEASE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
FIXED_ZIP_TIME = (1980, 1, 1, 0, 0, 0)


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def run_git(repo_root: Path, *args: str) -> str:
    completed = subprocess.run(
        ["git", "-C", str(repo_root), *args],
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    return completed.stdout.strip()


def tracked_paths(repo_root: Path) -> list[str]:
    completed = subprocess.run(
        ["git", "-C", str(repo_root), "ls-files", "-z"],
        check=True,
        capture_output=True,
    )
    paths = [part.decode("utf-8") for part in completed.stdout.split(b"\0") if part]
    if not paths:
        raise ValueError("repository has no tracked files")
    return sorted(paths)


def publish_no_overwrite(partial: Path, destination: Path) -> None:
    """Publish on the same filesystem without replacing an existing target."""
    os.link(partial, destination)
    partial.unlink()


def build_package(repo_root: Path, output_dir: Path, release_id: str) -> dict:
    repo_root = repo_root.resolve(strict=True)
    output_dir = output_dir.resolve()
    if not RELEASE_ID.fullmatch(release_id):
        raise ValueError("release id must contain only letters, numbers, dot, dash, or underscore")
    try:
        output_dir.relative_to(repo_root)
    except ValueError:
        pass
    else:
        raise ValueError("release output directory must remain outside the repository")

    if run_git(repo_root, "status", "--porcelain", "--untracked-files=all"):
        raise ValueError("repository worktree must be clean before packaging")

    commit = run_git(repo_root, "rev-parse", "HEAD")
    tree = run_git(repo_root, "rev-parse", "HEAD^{tree}")
    archive_name = f"{release_id}-replay.zip"
    manifest_name = f"{release_id}-evidence-manifest.json"
    output_dir.mkdir(parents=True, exist_ok=True)
    archive_path = output_dir / archive_name
    manifest_path = output_dir / manifest_name
    archive_partial = output_dir / f".{archive_name}.partial-{os.getpid()}"
    manifest_partial = output_dir / f".{manifest_name}.partial-{os.getpid()}"
    for target in (archive_path, manifest_path, archive_partial, manifest_partial):
        if target.exists():
            raise FileExistsError(f"refusing to overwrite {target}")

    entries: list[dict] = []
    try:
        with zipfile.ZipFile(
            archive_partial,
            mode="x",
            compression=zipfile.ZIP_DEFLATED,
            compresslevel=9,
        ) as archive:
            for relative in tracked_paths(repo_root):
                source = repo_root / relative
                if source.is_symlink():
                    raise ValueError(f"tracked symbolic link is not permitted: {relative}")
                resolved = source.resolve(strict=True)
                resolved.relative_to(repo_root)
                if not resolved.is_file():
                    raise ValueError(f"tracked path is not a regular file: {relative}")
                payload = resolved.read_bytes()
                info = zipfile.ZipInfo(relative.replace("\\", "/"), FIXED_ZIP_TIME)
                info.compress_type = zipfile.ZIP_DEFLATED
                info.external_attr = 0o100644 << 16
                info.create_system = 3
                archive.writestr(info, payload, compress_type=zipfile.ZIP_DEFLATED, compresslevel=9)
                entries.append(
                    {
                        "path": info.filename,
                        "size": len(payload),
                        "sha256": sha256_bytes(payload),
                    }
                )

        manifest = {
            "schema_version": "1.0",
            "release_id": release_id,
            "source_commit": commit,
            "source_tree": tree,
            "archive": {
                "name": archive_name,
                "sha256": sha256_file(archive_partial),
                "size": archive_partial.stat().st_size,
                "entry_count": len(entries),
            },
            "entries": entries,
            "boundaries": {
                "tracked_files_only": True,
                "worktree_clean": True,
                "output_outside_repository": True,
                "source_bodies_or_private_reviews_included": False,
            },
        }
        manifest_partial.write_text(
            json.dumps(manifest, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
            newline="\n",
        )
        publish_no_overwrite(archive_partial, archive_path)
        publish_no_overwrite(manifest_partial, manifest_path)
    except Exception:
        archive_partial.unlink(missing_ok=True)
        manifest_partial.unlink(missing_ok=True)
        raise

    return {
        "archive_path": str(archive_path),
        "archive_sha256": manifest["archive"]["sha256"],
        "manifest_path": str(manifest_path),
        "manifest_sha256": sha256_file(manifest_path),
        "source_commit": commit,
        "source_tree": tree,
        "entry_count": len(entries),
    }


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--release-id", required=True)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    try:
        result = build_package(args.repo_root, args.output_dir, args.release_id)
    except (FileExistsError, OSError, subprocess.CalledProcessError, ValueError) as exc:
        print(f"release package: FAIL: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
