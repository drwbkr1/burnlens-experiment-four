"""Tests for the complete candidate-universe builder."""

from __future__ import annotations

import importlib.util
import struct
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "scripts" / "build_candidate_universe.py"
SPEC = importlib.util.spec_from_file_location("build_candidate_universe", MODULE_PATH)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class CandidateUniverseBuilderTests(unittest.TestCase):
    def test_uuid_normalization_is_exact_and_lowercase(self) -> None:
        self.assertEqual(
            "11111111-1111-4111-8111-111111111111",
            MODULE._uuid("{11111111-1111-4111-8111-111111111111}"),
        )
        self.assertIsNone(MODULE._uuid("not-a-uuid"))

    def test_shx_binds_exact_shp_record(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            shp = root / "fixture.shp"
            shx = root / "fixture.shx"
            content = struct.pack("<I4d", 5, -121.0, 44.0, -120.0, 45.0)
            if len(content) % 2:
                content += b"\0"
            header = struct.pack(">2I", 1, len(content) // 2)
            shp.write_bytes(b"\0" * 100 + header + content)
            shx.write_bytes(b"\0" * 100 + struct.pack(">2I", 50, len(content) // 2))
            digest, bbox = MODULE._shp_record(shp, shx, 0)
            self.assertEqual(64, len(digest))
            self.assertEqual([-121.0, 44.0, -120.0, 45.0], bbox)


if __name__ == "__main__":
    unittest.main()
