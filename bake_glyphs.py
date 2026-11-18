#!/usr/bin/env python3
"""Bake the glyph atlas (glyphs.bin) this entry draws its text from.

Build-time tool only: it runs on the developer machine (needs Pillow and
the DejaVu fonts), never in the grader. The grader runs main.py, which
reads glyphs.bin with the standard library alone.

Glyphs come from DejaVu Sans / DejaVu Sans Bold
(/usr/share/fonts/truetype/dejavu/), released under the DejaVu Fonts
License — a free license that allows redistribution, including in this
bitmap form. Only the characters main.py actually draws are baked.

Output format (see Atlas in main.py): zlib-compressed blob; 4-byte
big-endian JSON header length, the header, then raw 8-bit alpha bitmaps
concatenated. Each glyph record is [w, h, dx, dy, advance, offset, length]
where (dx, dy) is the ink offset from the pen's top-left anchor.
"""

import importlib.util
import json
import struct
import sys
import zlib
from pathlib import Path

from PIL import ImageFont

HERE = Path(__file__).resolve().parent
FONTS = {
    "bold": "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "reg": "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
}


def load_main():
    spec = importlib.util.spec_from_file_location("news_main", HERE / "main.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def main():
    main = load_main()
    wanted = {}  # (weight, size) -> set of chars
    for weight, size, text in main.ALL_TEXTS:
        wanted.setdefault((weight, size), set()).update(text)

    glyphs = {}
    metrics = {}
    blob = bytearray()
    for (weight, size), chars in sorted(wanted.items()):
        font = ImageFont.truetype(FONTS[weight], size)
        ascent, descent = font.getmetrics()
        metrics["%s:%d" % (weight, size)] = [ascent, descent]
        for ch in sorted(chars):
            adv = int(round(font.getlength(ch)))
            try:
                left, top, right, bottom = font.getbbox(ch, anchor="la")
            except Exception:
                left, top, right, bottom = (0, 0, 0, 0)
            w, h = max(0, right - left), max(0, bottom - top)
            if w and h:
                mask = font.getmask(ch, mode="L")
                bits = bytes(mask)
                if len(bits) != w * h:
                    # Pillow pads some masks; crop row by row.
                    rows = []
                    stride = mask.size[0]
                    for yy in range(h):
                        rows.append(bytes(mask)[yy * stride:yy * stride + w])
                    bits = b"".join(rows)
                off = len(blob)
                blob += bits
                glyphs["%s:%d:%s" % (weight, size, ch)] = [
                    w, h, left, top, adv, off, len(bits)]
            else:
                glyphs["%s:%d:%s" % (weight, size, ch)] = [
                    0, 0, 0, 0, adv, 0, 0]

    header = json.dumps({"glyphs": glyphs, "metrics": metrics},
                        ensure_ascii=False, sort_keys=True).encode("utf-8")
    packed = struct.pack(">I", len(header)) + header + bytes(blob)
    out = HERE / "glyphs.bin"
    out.write_bytes(zlib.compress(packed, 9))
    print("baked %d glyphs in %d (weight,size) faces -> %s (%d bytes)"
          % (len(glyphs), len(wanted), out, out.stat().st_size))


if __name__ == "__main__":
    main()
