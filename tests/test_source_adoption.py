from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "scripts" / "validate_source_adoption.py"
SPEC = importlib.util.spec_from_file_location("validate_source_adoption", MODULE_PATH)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class SourceAdoptionTests(unittest.TestCase):
    def test_adoption_checkpoint_is_exact_and_public_safe(self) -> None:
        self.assertEqual(MODULE.validate(), [])

    def test_exact_source_set_contains_five_sources(self) -> None:
        self.assertEqual(len(MODULE.EXPECTED_SOURCE_IDENTITIES), 5)
        self.assertEqual(
            MODULE.EXPECTED_SOURCE_IDENTITIES["NASA-HLSL30-2.0-C2021957657"]["concept_id"],
            "C2021957657-LPCLOUD",
        )

    def test_owner_review_hashes_are_bound(self) -> None:
        self.assertEqual(
            MODULE.EXPECTED_HASHES["locked_response"],
            "897926590c470978cca2c5d8d424212f5372c445af8a9df05384f70bdcb7f83c",
        )
        self.assertEqual(
            MODULE.EXPECTED_HASHES["reconciliation"],
            "0dac0fdeff3f0f8d52fc54f7bab72c8a1aecfc3986dcefab37d8a9c01e8e453a",
        )


if __name__ == "__main__":
    unittest.main()
