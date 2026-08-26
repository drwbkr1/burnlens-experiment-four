"""Minimal dependency-free dBASE reader with field-level value admission."""

from __future__ import annotations

import struct
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator


@dataclass(frozen=True)
class Field:
    name: str
    kind: str
    length: int
    decimals: int
    offset: int


class Reader:
    def __init__(self, path: Path, *, encoding: str = "utf-8") -> None:
        self.path = path
        self.encoding = encoding
        with path.open("rb") as source:
            header = source.read(32)
            if len(header) != 32:
                raise ValueError("DBF header is truncated")
            self.record_count = struct.unpack("<I", header[4:8])[0]
            self.header_length = struct.unpack("<H", header[8:10])[0]
            self.record_length = struct.unpack("<H", header[10:12])[0]
            if self.header_length < 33 or (self.header_length - 33) % 32 != 0:
                raise ValueError("DBF header length is invalid")
            fields: list[Field] = []
            offset = 1
            for _ in range((self.header_length - 33) // 32):
                descriptor = source.read(32)
                if len(descriptor) != 32:
                    raise ValueError("DBF field descriptor is truncated")
                name = descriptor[:11].split(b"\0", 1)[0].decode("ascii")
                kind = chr(descriptor[11])
                length = descriptor[16]
                decimals = descriptor[17]
                fields.append(Field(name, kind, length, decimals, offset))
                offset += length
            if source.read(1) != b"\r":
                raise ValueError("DBF header terminator is invalid")
            if offset != self.record_length:
                raise ValueError("DBF field widths do not equal record length")
            self.fields = tuple(fields)

    def records(self, admitted_fields: set[str]) -> Iterator[tuple[int, dict[str, object]]]:
        schema = {field.name: field for field in self.fields}
        missing = sorted(admitted_fields - set(schema))
        if missing:
            raise ValueError(f"requested DBF fields are missing: {missing}")
        selected = [field for field in self.fields if field.name in admitted_fields]
        with self.path.open("rb") as source:
            source.seek(self.header_length)
            for index in range(self.record_count):
                record = source.read(self.record_length)
                if len(record) != self.record_length:
                    raise ValueError(f"DBF record {index} is truncated")
                if record[0:1] == b"*":
                    continue
                if record[0:1] != b" ":
                    raise ValueError(f"DBF record {index} has invalid deletion marker")
                values = {
                    field.name: self._decode(
                        record[field.offset : field.offset + field.length], field
                    )
                    for field in selected
                }
                yield index, values

    def _decode(self, raw: bytes, field: Field) -> object:
        stripped = raw.strip(b" \x00")
        if not stripped:
            return None
        if field.kind in {"C", "M"}:
            return stripped.decode(self.encoding, errors="strict")
        if field.kind in {"N", "F"}:
            text = stripped.decode("ascii")
            return float(text) if field.decimals else int(text)
        if field.kind == "D":
            text = stripped.decode("ascii")
            if len(text) != 8 or not text.isdigit():
                raise ValueError(f"invalid DBF date in field {field.name}")
            return f"{text[0:4]}-{text[4:6]}-{text[6:8]}"
        if field.kind == "L":
            value = stripped.upper()
            if value in {b"Y", b"T"}:
                return True
            if value in {b"N", b"F"}:
                return False
            return None
        return stripped.hex()
