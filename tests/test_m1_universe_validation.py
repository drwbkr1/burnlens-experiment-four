"""Unit checks for independent Milestone 1 validation helpers."""

from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "scripts" / "validate_m1_universe.py"
SPEC = importlib.util.spec_from_file_location("validate_m1_universe", MODULE_PATH)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class M1UniverseValidationTests(unittest.TestCase):
    def test_candidate_id_binding_is_deterministic(self) -> None:
        source = {
            "source_id": "source",
            "source_revision": "revision",
            "source_row_id": "row",
        }
        self.assertEqual(MODULE._candidate_id(source), MODULE._candidate_id(dict(source)))
        self.assertRegex(MODULE._candidate_id(source), r"^E4-CAND-[A-F0-9]{16}$")


if __name__ == "__main__":
    unittest.main()
