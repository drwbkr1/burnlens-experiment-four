from __future__ import annotations

import hashlib
import importlib.util
import struct
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))


def _load(name: str):
    path = ROOT / "scripts" / f"{name}.py"
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


ACQUIRE = _load("acquire_https_no_overwrite")
VERIFY = _load("verify_metadata_archive")
PROMOTE = _load("promote_no_replace")
EXTRACT = _load("extract_zip_members_no_overwrite")

from burnlens_e4.dbf import Reader


class ControlledIntakeTests(unittest.TestCase):
    def test_only_absolute_https_sources_are_accepted(self) -> None:
        self.assertEqual(ACQUIRE._https_uri("https://example.org/a.zip"), "https://example.org/a.zip")
        for value in ("http://example.org/a.zip", "file:///tmp/a.zip", "https:///a.zip"):
            with self.assertRaises(ValueError):
                ACQUIRE._https_uri(value)

    def test_zip_member_safety_rejects_traversal_and_absolute_paths(self) -> None:
        self.assertTrue(VERIFY._safe_member("folder/file.dbf"))
        self.assertFalse(VERIFY._safe_member("../file.dbf"))
        self.assertFalse(VERIFY._safe_member("/absolute/file.dbf"))
        self.assertFalse(VERIFY._safe_member("folder\\..\\file.dbf"))

    def test_atomic_promotion_refuses_existing_destination(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "source.bin"
            destination = root / "custody" / "final.bin"
            source.write_bytes(b"verified bytes")
            digest = hashlib.sha256(source.read_bytes()).hexdigest()
            result = PROMOTE.promote(source, destination, digest, source.stat().st_size)
            self.assertEqual(result["sha256"], digest)
            with self.assertRaises(FileExistsError):
                PROMOTE.promote(source, destination, digest, source.stat().st_size)
            self.assertEqual(destination.read_bytes(), b"verified bytes")

    def test_extraction_is_exact_and_no_overwrite(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            archive = root / "source.zip"
            with zipfile.ZipFile(archive, "w") as output:
                output.writestr("safe/data.dbf", b"bytes")
            digest = hashlib.sha256(archive.read_bytes()).hexdigest()
            destination = root / "runtime"
            result = EXTRACT.extract(archive, destination, ["safe/data.dbf"], digest)
            self.assertEqual(result["files"][0]["size_bytes"], 5)
            with self.assertRaises(FileExistsError):
                EXTRACT.extract(archive, destination, ["safe/data.dbf"], digest)

    def test_dbf_reader_opens_only_admitted_field_values(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "sample.dbf"
            fields = [("Allowed", "C", 8, 0), ("Denied", "N", 4, 0)]
            header_length = 32 + 32 * len(fields) + 1
            record_length = 1 + sum(field[2] for field in fields)
            header = bytearray(32)
            header[0] = 3
            header[4:8] = struct.pack("<I", 1)
            header[8:10] = struct.pack("<H", header_length)
            header[10:12] = struct.pack("<H", record_length)
            descriptors = bytearray()
            for name, kind, length, decimals in fields:
                descriptor = bytearray(32)
                encoded = name.encode("ascii")
                descriptor[: len(encoded)] = encoded
                descriptor[11] = ord(kind)
                descriptor[16] = length
                descriptor[17] = decimals
                descriptors.extend(descriptor)
            body = b" " + b"visible " + b" 123" + b"\x1a"
            path.write_bytes(bytes(header) + bytes(descriptors) + b"\r" + body)
            reader = Reader(path)
            rows = list(reader.records({"Allowed"}))
            self.assertEqual(rows, [(0, {"Allowed": "visible"})])
            self.assertNotIn("Denied", rows[0][1])


if __name__ == "__main__":
    unittest.main()
