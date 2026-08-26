from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "scripts" / "validate_literal_encoding_review.py"
SPEC = importlib.util.spec_from_file_location("validate_literal_encoding_review", MODULE_PATH)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class LiteralEncodingReviewTests(unittest.TestCase):
    def test_exact_review_package_passes(self) -> None:
        self.assertEqual(MODULE.validate(), [])

    def test_runtime_probe_hashes_are_bound(self) -> None:
        self.assertEqual(MODULE.EXPECTED["mtbs_preflight"], "0cec99372a86b789ad939c70ab2c62081644664ba5a2cfe26538aae026e10729")
        self.assertEqual(MODULE.EXPECTED["wfigs_probe"], "eebf1289f12909cdc3c1321d7e1c7f25700762ad03037b2ff03175658a7db254")

    def test_bundle_hash_is_exact(self) -> None:
        self.assertEqual(MODULE.EXPECTED["bundle"], "3ff69ce031313db2010706cf481a63c24d45a88cfb23c2f6bb7a38d96f7b972a")


if __name__ == "__main__":
    unittest.main()
