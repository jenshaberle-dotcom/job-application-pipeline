#!/usr/bin/env python3
"""Generate the deterministic JAP Control Center Windows icon without external deps."""

from __future__ import annotations

import struct
import sys
import zlib
from pathlib import Path

SIZE = 256


def _chunk(kind: bytes, payload: bytes) -> bytes:
    body = kind + payload
    return struct.pack(">I", len(payload)) + body + struct.pack(">I", zlib.crc32(body) & 0xFFFFFFFF)


def _pixel(x: int, y: int) -> tuple[int, int, int, int]:
    cx = cy = (SIZE - 1) / 2
    dx = x - cx
    dy = y - cy
    radius = (dx * dx + dy * dy) ** 0.5
    edge = min(radius / 181.0, 1.0)

    # Deep-ocean background with a subtle center lift.
    r = int(7 + (1.0 - edge) * 5)
    g = int(20 + (1.0 - edge) * 17)
    b = int(34 + (1.0 - edge) * 24)

    # Cyan operator ring.
    if 94 <= radius <= 102:
        return (54, 215, 224, 255)

    # Stylized J: vertical spine plus rounded lower hook.
    if 132 <= x <= 158 and 60 <= y <= 164:
        return (225, 246, 249, 255)
    hook_radius = ((x - 112) ** 2 + (y - 162) ** 2) ** 0.5
    if 28 <= hook_radius <= 51 and y >= 155 and x <= 139:
        return (225, 246, 249, 255)

    # Three small data nodes.
    for px, py in ((82, 84), (72, 119), (82, 154)):
        if (x - px) ** 2 + (y - py) ** 2 <= 6**2:
            return (54, 215, 224, 255)

    return (r, g, b, 255)


def _png() -> bytes:
    raw = bytearray()
    for y in range(SIZE):
        raw.append(0)
        for x in range(SIZE):
            raw.extend(_pixel(x, y))
    header = b"\x89PNG\r\n\x1a\n"
    ihdr = struct.pack(">IIBBBBB", SIZE, SIZE, 8, 6, 0, 0, 0)
    return header + _chunk(b"IHDR", ihdr) + _chunk(b"IDAT", zlib.compress(bytes(raw), 9)) + _chunk(b"IEND", b"")


def main() -> int:
    if len(sys.argv) != 2:
        raise SystemExit("usage: generate_jap_control_center_icon.py OUTPUT.ico")
    target = Path(sys.argv[1]).resolve()
    target.parent.mkdir(parents=True, exist_ok=True)
    png = _png()
    # ICO header + one 256x256 PNG-backed image entry.
    header = struct.pack("<HHH", 0, 1, 1)
    entry = struct.pack("<BBBBHHII", 0, 0, 0, 0, 1, 32, len(png), 6 + 16)
    target.write_bytes(header + entry + png)
    print(f"JAP_CONTROL_CENTER_ICON={target}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
