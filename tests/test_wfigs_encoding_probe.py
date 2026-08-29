from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "scripts" / "capture_wfigs_encoding_probe.py"
SPEC = importlib.util.spec_from_file_location("capture_wfigs_encoding_probe", MODULE_PATH)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class WfigsEncodingProbeTests(unittest.TestCase):
    def test_probe_is_fixed_to_reviewed_window(self) -> None:
        self.assertIn("2021-01-01", MODULE.DATE_WINDOW)
        self.assertIn("2023-01-01", MODULE.DATE_WINDOW)

    def test_competing_literal_state_domains_are_explicit(self) -> None:
        self.assertIn("('ID','OR','WA')", MODULE.EXACT_STATE_WHERE)
        self.assertIn("('US-ID','US-OR','US-WA')", MODULE.PREFIXED_STATE_WHERE)


if __name__ == "__main__":
    unittest.main()
