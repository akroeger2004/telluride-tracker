"""Draw the app icons (two white peaks on blue) with the standard library only.

    python tools/make_icons.py

Writes icons/icon-192.png, icons/icon-512.png and icons/icon-maskable-512.png.
The maskable icon keeps the artwork inside the central safe zone.
"""
import struct
import zlib
from pathlib import Path

BLUE = (42, 120, 214, 255)
PAPER = (252, 252, 251, 255)
CLEAR = (0, 0, 0, 0)


def png(width, height, pixels):
    raw = b"".join(b"\x00" + bytes(c for px in pixels[y * width:(y + 1) * width] for c in px)
                   for y in range(height))

    def chunk(kind, body):
        crc = zlib.crc32(kind + body) & 0xFFFFFFFF
        return struct.pack(">I", len(body)) + kind + body + struct.pack(">I", crc)

    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(raw, 9)) + chunk(b"IEND", b""))


def icon(size, maskable):
    pad = 0.2 if maskable else 0.0          # maskable: keep art in the safe zone
    radius = 0 if maskable else size * 0.22  # maskable icons are full-bleed squares
    art = size * (1 - 2 * pad)
    left, top = size * pad, size * pad
    # two triangles (a tall peak and a shorter one), as (apex_x, apex_y, left_x, right_x, base_y)
    base = top + art * 0.82
    peaks = [(left + art * 0.40, top + art * 0.18, left + art * 0.04, left + art * 0.76, base),
             (left + art * 0.72, top + art * 0.40, left + art * 0.46, left + art * 0.98, base)]

    def in_peak(x, y):
        for ax, ay, lx, rx, by in peaks:
            if ay <= y <= by:
                t = (y - ay) / (by - ay)
                if ax - (ax - lx) * t <= x <= ax + (rx - ax) * t:
                    return True
        return False

    def inside_round(x, y):
        if radius == 0:
            return True
        cx = min(max(x, radius), size - radius)
        cy = min(max(y, radius), size - radius)
        return (x - cx) ** 2 + (y - cy) ** 2 <= radius ** 2

    pixels = []
    for y in range(size):
        for x in range(size):
            if not inside_round(x + 0.5, y + 0.5):
                pixels.append(CLEAR)
            elif in_peak(x + 0.5, y + 0.5):
                pixels.append(PAPER)
            else:
                pixels.append(BLUE)
    return png(size, size, pixels)


def main():
    out = Path(__file__).resolve().parent.parent / "icons"
    out.mkdir(exist_ok=True)
    (out / "icon-192.png").write_bytes(icon(192, False))
    (out / "icon-512.png").write_bytes(icon(512, False))
    (out / "icon-maskable-512.png").write_bytes(icon(512, True))
    print("wrote icons to", out)


if __name__ == "__main__":
    main()
