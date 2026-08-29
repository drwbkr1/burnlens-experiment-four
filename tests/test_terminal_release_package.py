from __future__ import annotations

import subprocess
import tempfile
import unittest
import zipfile
from pathlib import Path

from scripts.build_terminal_release_package import build_package


def git(repo: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True)


class TerminalReleasePackageTests(unittest.TestCase):
    def make_repo(self, root: Path) -> Path:
        repo = root / "repo"
        repo.mkdir()
        git(repo, "init")
        git(repo, "config", "user.email", "test@example.invalid")
        git(repo, "config", "user.name", "Release Test")
        (repo / "README.md").write_text("evidence\n", encoding="utf-8", newline="\n")
        (repo / "nested").mkdir()
        (repo / "nested" / "receipt.json").write_text(
            '{"status":"INCONCLUSIVE"}\n', encoding="utf-8", newline="\n"
        )
        git(repo, "add", ".")
        git(repo, "commit", "-m", "fixture")
        return repo

    def test_package_is_deterministic_and_contains_only_tracked_files(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            repo = self.make_repo(root)
            first = build_package(repo, root / "one", "release-one")
            second = build_package(repo, root / "two", "release-two")
            self.assertEqual(first["archive_sha256"], second["archive_sha256"])
            self.assertEqual(first["entry_count"], 2)
            with zipfile.ZipFile(first["archive_path"]) as archive:
                self.assertEqual(archive.namelist(), ["README.md", "nested/receipt.json"])

    def test_dirty_worktree_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            repo = self.make_repo(root)
            (repo / "README.md").write_text("changed\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "worktree must be clean"):
                build_package(repo, root / "output", "release")

    def test_existing_output_is_not_overwritten(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            repo = self.make_repo(root)
            output = root / "output"
            build_package(repo, output, "release")
            with self.assertRaises(FileExistsError):
                build_package(repo, output, "release")


if __name__ == "__main__":
    unittest.main()
