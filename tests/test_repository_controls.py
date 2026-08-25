"""Focused regression tests for the Experiment Four control plane."""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
VALIDATOR_PATH = ROOT / "scripts" / "validate_repository.py"
SPEC = importlib.util.spec_from_file_location("validate_repository", VALIDATOR_PATH)
assert SPEC is not None and SPEC.loader is not None
VALIDATOR = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(VALIDATOR)


class RepositoryControlTests(unittest.TestCase):
    def test_repository_validator_passes(self) -> None:
        self.assertEqual([], VALIDATOR.validate())

    def test_all_json_records_parse(self) -> None:
        json_paths = sorted(ROOT.rglob("*.json"))
        self.assertGreaterEqual(len(json_paths), 3)
        for path in json_paths:
            with self.subTest(path=path.relative_to(ROOT)):
                parsed = json.loads(path.read_text(encoding="utf-8"))
                self.assertIsInstance(parsed, dict)

    def test_profile_and_contract_are_bidirectionally_bound(self) -> None:
        pointer_path = ROOT / "records/governance/ACTIVE-PROJECT-CONTROL-PROFILE"
        profile_path = ROOT / pointer_path.read_text(encoding="utf-8").strip()
        profile = json.loads(profile_path.read_text(encoding="utf-8"))
        contract_path = ROOT / profile["control_surfaces"]["active_contract"]
        contract = json.loads(contract_path.read_text(encoding="utf-8"))
        self.assertEqual(
            contract["project_profile_ref"],
            profile_path.relative_to(ROOT).as_posix(),
        )
        self.assertEqual(
            profile["control_surfaces"]["active_contract"],
            contract_path.relative_to(ROOT).as_posix(),
        )

    def test_no_prohibited_scientific_artifacts(self) -> None:
        violations = [
            path.relative_to(ROOT).as_posix()
            for path in VALIDATOR.repository_files()
            if path.suffix.lower() in VALIDATOR.PROHIBITED_SUFFIXES
        ]
        self.assertEqual([], violations)

    def test_cli_reports_non_scientific_scope(self) -> None:
        result = subprocess.run(
            [sys.executable, str(VALIDATOR_PATH)],
            cwd=ROOT,
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)
        self.assertIn("Scientific evidence status: NOT STARTED", result.stdout)


if __name__ == "__main__":
    unittest.main()
