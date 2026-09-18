"""Pack schematic records into a native (OLE compound) Altium .SchDoc.

Record framing was reverse engineered from the reference reader: each record is
    <payload length: uint16 LE> <0x00> <type: uint8> <payload>
and for a property record the payload is the familiar pipe separated text followed by
a single null byte. So the ASCII record text can be reused verbatim.
"""
import os
import struct
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from cfb_writer import OleWriter  # noqa: E402

HEADER_TEXT = "|HEADER=Protel for Windows - Schematic Capture Binary File Version 5.0|WEIGHT=%d"
STORAGE_TEXT = "|HEADER=Icon storage|WEIGHT=0"


def record(text, encoding="utf-8"):
    payload = text.encode(encoding) + b"\x00"
    if len(payload) > 0xFFFF:
        raise ValueError("record too long")
    return struct.pack("<HBB", len(payload), 0, 0) + payload


def records_from_lines(lines, encoding="utf-8"):
    stream = bytearray()
    for index, text in enumerate(lines):
        if index == 0:
            text = HEADER_TEXT % (len(lines) - 1)
        stream += record(text, encoding)
    return bytes(stream)


def build(lines, path):
    """lines: list where [0] is the ASCII header line, [1] the sheet, rest objects."""
    file_header = records_from_lines(lines)
    writer = OleWriter()
    writer.add("FileHeader", file_header)
    writer.add("Storage", record(STORAGE_TEXT))
    data = writer.build()
    with open(path, "wb") as fh:
        fh.write(data)
    return path, len(data), len(file_header)


def pack_ascii_file(ascii_path, out_path):
    with open(ascii_path, encoding="utf-8") as fh:
        lines = [ln.rstrip("\n") for ln in fh if ln.strip()]
    return build(lines, out_path)


if __name__ == "__main__":
    src = sys.argv[1]
    dst = sys.argv[2]
    print(pack_ascii_file(src, dst))
