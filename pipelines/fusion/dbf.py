"""Minimal dBase III reader for the CENACOM microdata (read-only, no dependency).

The INEI modules are plain dBase files inside ZIP archives: a 32-byte header,
32-byte field descriptors terminated by 0x0D, then fixed-width records whose
first byte is the deletion flag. Values are returned as stripped strings
(latin-1), the encoding used by the INEI exports.
"""

from __future__ import annotations

import struct
import zipfile
from collections.abc import Iterator
from pathlib import Path


def read_dbf_bytes(data: bytes) -> tuple[list[str], Iterator[dict[str, str]]]:
    """Field names and an iterator over records (deleted records skipped)."""
    n_records, header_len, record_len = struct.unpack("<IHH", data[4:12])
    fields: list[tuple[str, int]] = []
    for off in range(32, header_len - 1, 32):
        desc = data[off : off + 32]
        if desc[0] == 0x0D:
            break
        name = desc[:11].split(b"\0")[0].decode("latin-1")
        fields.append((name, desc[16]))

    def records() -> Iterator[dict[str, str]]:
        for i in range(n_records):
            start = header_len + i * record_len
            rec = data[start : start + record_len]
            if not rec or rec[0:1] == b"*":
                continue
            pos, row = 1, {}
            for name, width in fields:
                row[name] = rec[pos : pos + width].decode("latin-1").strip()
                pos += width
            yield row

    return [f for f, _ in fields], records()


def read_dbf_in_zip(archive: Path, member_suffix: str) -> list[dict[str, str]]:
    """All records of the first ``.dbf`` member whose name ends with ``member_suffix``."""
    with zipfile.ZipFile(archive) as z:
        name = next(n for n in z.namelist() if n.lower().endswith(member_suffix.lower()))
        _fields, rows = read_dbf_bytes(z.read(name))
        return list(rows)
