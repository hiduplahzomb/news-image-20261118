#!/usr/bin/env python3
"""news-image-20261118 — sum up the world news of Wednesday 18 November 2026
in one 1024x1024 image.

The program draws the image itself, pixel by pixel, with the Python standard
library only: a small rasteriser (rects, circles, polygons, lines, arcs),
text stamped from a glyph atlas baked from DejaVu Sans (free license; see
bake_glyphs.py, which produced glyphs.bin), and a minimal PNG encoder.

Deterministic: no network, no clock, no randomness — two runs write the
same bytes. Writes $MAKEFUN_OUTPUT_DIR/entry.png (default /output/entry.png).

Layout (1024 x 1024), a newspaper front page:
  masthead  "THE WORLD" + "WEDNESDAY · 18 NOVEMBER 2026"
  lead      US strikes Iran, Iran hits back (Gulf)
  5 cards   Kerch bridge · Trump in Manila · Ebola in Congo ·
            Democrats win Alaska · Cyclone Xavier
  footer    "AS REPORTED ON 18 NOVEMBER 2026" + an ALSO line
"""

import json
import math
import os
import struct
import sys
import zlib
from pathlib import Path

W, H = 1024, 1024

# ---------------------------------------------------------------- palette
PAPER = (247, 243, 234)      # warm newsprint
NAVY = (13, 27, 46)          # masthead / footer band
GOLD = (201, 162, 39)        # date line, rules
INK = (20, 20, 20)           # headlines
BODY = (74, 74, 74)          # descriptors
CARD = (255, 255, 255)       # story cards
CARD_EDGE = (219, 211, 192)  # card borders
RED = (192, 57, 43)          # lead accent
ORANGE = (230, 126, 34)
YELLOW = (241, 196, 15)
WHITE = (255, 255, 255)
STEEL = (93, 109, 126)
SMOKE = (118, 128, 132)

# ------------------------------------------------------------- the news
# (font, size) -> text. bake_glyphs.py imports this table and renders
# exactly the glyphs used here. Keep every string in this table so the
# atlas never misses a character.
MASTHEAD_TITLE = ("bold", 100, "THE WORLD")
MASTHEAD_DATE = ("bold", 36, "WEDNESDAY \u00b7 18 NOVEMBER 2026")

LEAD_KICKER = ("bold", 24, "GULF CRISIS")
LEAD_HEAD = ("bold", 60, "US STRIKES IRAN, IRAN HITS BACK")
LEAD_DESC = ("reg", 26,
             "US jets hit a missile site on Qeshm Island; Tehran fires "
             "drones at US bases in Bahrain and Kuwait.")

# (kicker, accent colour, headline, descriptor, icon)
CARDS = [
    ("UKRAINE", (37, 99, 235), "BRIDGE TO CRIMEA HIT",
     "Kerch span falls into the strait.", "bridge"),
    ("ASIA", (124, 58, 237), "TRUMP LANDS IN MANILA",
     "QUAD plan agreed; summit Thursday.", "jet"),
    ("HEALTH", (22, 163, 74), "EBOLA SURGE IN CONGO",
     "11,000 cases, 5,400 dead, UN says.", "virus"),
    ("USA", (30, 64, 175), "DEMOCRATS WIN ALASKA",
     "Peltola wins the Alaska seat; Democrats now hold 56 of 100 Senate seats.", "ballot"),
    ("PACIFIC", (8, 145, 178), "CYCLONE HITS COOK ISLANDS",
     "Category 5 Xavier strikes the northern Cook Islands.", "cyclone"),
]

FOOTER_1 = ("bold", 24, "AS REPORTED ON 18 NOVEMBER 2026")
FOOTER_2 = ("reg", 18,
            "ALSO: US LOSES MEASLES-FREE STATUS \u00b7 RUSSIAN PLANE "
            "CRASH KILLS 19 \u00b7 QUAKE IN PAPUA NEW GUINEA")

# every (font, size, text) the entry draws, for the glyph baker
ALL_TEXTS = [
    MASTHEAD_TITLE, MASTHEAD_DATE, LEAD_KICKER, LEAD_HEAD, LEAD_DESC,
    FOOTER_1, FOOTER_2,
]
for _kicker, _accent, _head, _desc, _icon in CARDS:
    ALL_TEXTS.append(("bold", 20, _kicker))
    ALL_TEXTS.append(("bold", 32, _head))
    ALL_TEXTS.append(("reg", 22, _desc))


# ---------------------------------------------------------------- canvas
class Canvas:
    """An RGB raster with a few flat-design drawing primitives."""

    def __init__(self, w, h, bg):
        self.w, self.h = w, h
        self.px = bytearray(w * h * 3)
        self.rect(0, 0, w, h, bg)

    def _idx(self, x, y):
        return (y * self.w + x) * 3

    def set(self, x, y, color):
        if 0 <= x < self.w and 0 <= y < self.h:
            i = self._idx(x, y)
            self.px[i], self.px[i + 1], self.px[i + 2] = color

    def rect(self, x, y, w, h, color):
        x0, y0 = max(0, x), max(0, y)
        x1, y1 = min(self.w, x + w), min(self.h, y + h)
        r, g, b = color
        for yy in range(y0, y1):
            i = self._idx(x0, yy)
            for xx in range(x0, x1):
                self.px[i], self.px[i + 1], self.px[i + 2] = r, g, b
                i += 3

    def circle(self, cx, cy, r, color):
        r2 = r * r
        for yy in range(max(0, cy - r), min(self.h, cy + r + 1)):
            dy = yy - cy
            dx = int(math.sqrt(max(0, r2 - dy * dy)))
            self.rect(cx - dx, yy, 2 * dx + 1, 1, color)

    def ring(self, cx, cy, r, width, color):
        for yy in range(max(0, cy - r), min(self.h, cy + r + 1)):
            dy = yy - cy
            for xx in range(max(0, cx - r), min(self.w, cx + r + 1)):
                d = math.sqrt((xx - cx) ** 2 + dy * dy)
                if r - width <= d <= r:
                    self.set(xx, yy, color)

    def polygon(self, pts, color):
        """Scanline fill of a simple polygon (even-odd)."""
        if not pts:
            return
        ymin = max(0, min(p[1] for p in pts))
        ymax = min(self.h - 1, max(p[1] for p in pts))
        edges = []
        n = len(pts)
        for i in range(n):
            x0, y0 = pts[i]
            x1, y1 = pts[(i + 1) % n]
            if y0 != y1:
                edges.append((x0, y0, x1, y1))
        for yy in range(ymin, ymax + 1):
            xs = []
            for x0, y0, x1, y1 in edges:
                lo, hi = (y0, y1) if y0 < y1 else (y1, y0)
                if lo <= yy < hi:
                    t = (yy - y0) / (y1 - y0)
                    xs.append(x0 + t * (x1 - x0))
            xs.sort()
            for j in range(0, len(xs) - 1, 2):
                xa, xb = int(math.ceil(xs[j])), int(math.floor(xs[j + 1]))
                if xb >= xa:
                    self.rect(xa, yy, xb - xa + 1, 1, color)

    def line(self, x0, y0, x1, y1, color, width=1):
        """Thick line as a rotated rectangle (plus round caps)."""
        dx, dy = x1 - x0, y1 - y0
        length = math.hypot(dx, dy)
        if length == 0:
            self.circle(x0, y0, max(1, width // 2), color)
            return
        ux, uy = dx / length, dy / length
        px, py = -uy, ux
        hw = width / 2.0
        corners = [
            (round(x0 + px * hw), round(y0 + py * hw)),
            (round(x1 + px * hw), round(y1 + py * hw)),
            (round(x1 - px * hw), round(y1 - py * hw)),
            (round(x0 - px * hw), round(y0 - py * hw)),
        ]
        self.polygon(corners, color)
        r = max(1, int(round(hw)))
        self.circle(x0, y0, r, color)
        self.circle(x1, y1, r, color)

    def arc(self, cx, cy, r, a0, a1, color, width=1):
        """Arc from angle a0 to a1 (degrees), drawn as short segments."""
        steps = max(8, int(abs(a1 - a0) / 6))
        prev = None
        for i in range(steps + 1):
            a = math.radians(a0 + (a1 - a0) * i / steps)
            p = (round(cx + r * math.cos(a)), round(cy + r * math.sin(a)))
            if prev is not None:
                self.line(prev[0], prev[1], p[0], p[1], color, width)
            prev = p


# -------------------------------------------------------------- glyphs
class Atlas:
    """Glyph bitmaps baked by bake_glyphs.py into glyphs.bin.

    File format: zlib-compressed blob; first 4 bytes (big-endian) are the
    JSON header length, then the header, then the raw 8-bit alpha bitmaps
    concatenated. Header: {"glyphs": {"<weight>:<size>:<char>": [w, h, dx,
    dy, adv, off, len], ...}, "metrics": {"<weight>:<size>": [ascent,
    descent]}}. (dx, dy) is the ink offset from the pen's ascender-line
    anchor ("la" in Pillow terms).
    """

    def __init__(self, path):
        raw = zlib.decompress(Path(path).read_bytes())
        (hlen,) = struct.unpack(">I", raw[:4])
        header = json.loads(raw[4:4 + hlen].decode("utf-8"))
        blob = raw[4 + hlen:]
        self.glyphs = {}
        for key, (w, h, dx, dy, adv, off, ln) in header["glyphs"].items():
            weight, size, ch = key.split(":", 2)
            self.glyphs[(weight, int(size), ch)] = (
                w, h, dx, dy, adv, blob[off:off + ln])
        self.metrics = {k: tuple(v) for k, v in header["metrics"].items()}

    def text_width(self, weight, size, text):
        total = 0
        for ch in text:
            g = self.glyphs.get((weight, size, ch))
            if g is None:
                raise KeyError("glyph missing: %r %s %d" % (ch, weight, size))
            total += g[4]
        return total

    def draw(self, cv, x, y, weight, size, text, color):
        """Stamp text with its ascender-line anchor at (x, y)."""
        pen = x
        for ch in text:
            w, h, dx, dy, adv, bits = self.glyphs[(weight, size, ch)]
            if w and h:
                gx, gy = pen + dx, y + dy
                r, g, b = color
                for yy in range(h):
                    row = yy * w
                    for xx in range(w):
                        a = bits[row + xx]
                        if a:
                            px, py = gx + xx, gy + yy
                            if 0 <= px < cv.w and 0 <= py < cv.h:
                                i = cv._idx(px, py)
                                inv = 255 - a
                                cv.px[i] = (r * a + cv.px[i] * inv) // 255
                                cv.px[i + 1] = (g * a + cv.px[i + 1] * inv) // 255
                                cv.px[i + 2] = (b * a + cv.px[i + 2] * inv) // 255
            pen += adv
        return pen

    def wrap(self, weight, size, text, max_w):
        """Greedy word wrap; returns a list of lines."""
        words = text.split(" ")
        lines, cur = [], ""
        for word in words:
            trial = word if not cur else cur + " " + word
            if self.text_width(weight, size, trial) <= max_w or not cur:
                cur = trial
            else:
                lines.append(cur)
                cur = word
        if cur:
            lines.append(cur)
        return lines


# ---------------------------------------------------------------- icons
def starburst(cv, cx, cy, spikes, r_out, r_in, color):
    pts = []
    for i in range(spikes * 2):
        r = r_out if i % 2 == 0 else r_in
        a = math.pi * i / spikes - math.pi / 2
        pts.append((round(cx + r * math.cos(a)), round(cy + r * math.sin(a))))
    cv.polygon(pts, color)


def jet(cv, x, y, s, color):
    """Side-view jet silhouette in a box of width ~2.2*s, height ~s."""
    pts = [
        (x, y + int(0.42 * s)), (x + int(0.55 * s), y + int(0.36 * s)),
        (x + int(1.95 * s), y), (x + int(2.2 * s), y + int(0.14 * s)),
        (x + int(1.95 * s), y + int(0.28 * s)), (x + int(1.15 * s), y + int(0.55 * s)),
        (x + int(0.75 * s), y + int(0.95 * s)), (x + int(0.55 * s), y + int(0.95 * s)),
        (x + int(0.62 * s), y + int(0.58 * s)), (x + int(0.18 * s), y + int(0.62 * s)),
        (x + int(0.05 * s), y + int(0.82 * s)), (x, y + int(0.82 * s)),
        (x + int(0.08 * s), y + int(0.60 * s)),
    ]
    cv.polygon(pts, color)


def icon_bridge(cv, x, y, s, accent):
    # Bold and simple: two towers, a deck split by a dropped middle span,
    # smoke above the gap.
    deck_y = y + int(0.62 * s)
    cv.rect(x + int(0.10 * s), y + int(0.16 * s), int(0.13 * s),
            int(0.60 * s), accent)
    cv.rect(x + int(0.75 * s), y + int(0.16 * s), int(0.13 * s),
            int(0.60 * s), accent)
    cv.rect(x + int(0.02 * s), deck_y, int(0.38 * s), int(0.12 * s), STEEL)
    cv.rect(x + int(0.60 * s), deck_y, int(0.38 * s), int(0.12 * s), STEEL)
    cv.polygon([(x + int(0.38 * s), deck_y),
                (x + int(0.60 * s), deck_y),
                (x + int(0.56 * s), deck_y + int(0.22 * s)),
                (x + int(0.42 * s), deck_y + int(0.16 * s))], STEEL)
    cv.circle(x + int(0.44 * s), y + int(0.36 * s), int(0.12 * s), SMOKE)
    cv.circle(x + int(0.54 * s), y + int(0.26 * s), int(0.15 * s), SMOKE)
    cv.circle(x + int(0.50 * s), y + int(0.46 * s), int(0.08 * s), SMOKE)


def icon_jet(cv, x, y, s, accent):
    jet(cv, x + int(0.05 * s), y + int(0.10 * s), int(0.42 * s), accent)
    cv.line(x + int(0.08 * s), y + int(0.82 * s), x + int(0.92 * s),
            y + int(0.82 * s), STEEL, 4)
    for i, dx in enumerate((0.14, 0.34, 0.54)):
        cv.line(x + int(dx * s), y + int(0.70 * s),
                x + int((dx + 0.12) * s), y + int(0.70 * s), GOLD, 3)


def icon_virus(cv, x, y, s, accent):
    cx, cy = x + s // 2, y + s // 2
    for i in range(8):
        a = math.pi * i / 4
        ex, ey = round(cx + 0.44 * s * math.cos(a)), round(cy + 0.44 * s * math.sin(a))
        cv.line(cx, cy, ex, ey, accent, 4)
        cv.circle(ex, ey, max(2, int(0.07 * s)), accent)
    cv.circle(cx, cy, int(0.24 * s), accent)
    cv.circle(cx - int(0.08 * s), cy - int(0.06 * s), int(0.05 * s), WHITE)
    cv.circle(cx + int(0.07 * s), cy + int(0.08 * s), int(0.04 * s), WHITE)


def icon_ballot(cv, x, y, s, accent):
    cv.rect(x + int(0.14 * s), y + int(0.34 * s), int(0.72 * s), int(0.56 * s), accent)
    cv.rect(x + int(0.10 * s), y + int(0.22 * s), int(0.80 * s), int(0.14 * s),
            (max(0, accent[0] - 40), max(0, accent[1] - 40), max(0, accent[2] - 40)))
    cv.rect(x + int(0.38 * s), y + int(0.26 * s), int(0.24 * s), int(0.05 * s), WHITE)
    cv.line(x + int(0.28 * s), y + int(0.60 * s), x + int(0.44 * s),
            y + int(0.76 * s), WHITE, 5)
    cv.line(x + int(0.44 * s), y + int(0.76 * s), x + int(0.74 * s),
            y + int(0.42 * s), WHITE, 5)


def icon_cyclone(cv, x, y, s, accent):
    cx, cy = x + s // 2, y + s // 2
    for i, r in enumerate((0.14, 0.24, 0.34, 0.44)):
        cv.arc(cx, cy, int(r * s), 40 + i * 55, 300 + i * 55, accent, 4)
    cv.circle(cx, cy, int(0.08 * s), WHITE)


ICONS = {
    "bridge": icon_bridge,
    "jet": icon_jet,
    "virus": icon_virus,
    "ballot": icon_ballot,
    "cyclone": icon_cyclone,
}


# -------------------------------------------------------------- layout
def draw_image(atlas):
    cv = Canvas(W, H, PAPER)

    # ---- masthead ---------------------------------------------------
    cv.rect(0, 0, W, 160, NAVY)
    w, size, text = MASTHEAD_TITLE
    tw = atlas.text_width(w, size, text)
    atlas.draw(cv, (W - tw) // 2, 8, w, size, text, WHITE)
    w, size, text = MASTHEAD_DATE
    tw = atlas.text_width(w, size, text)
    atlas.draw(cv, (W - tw) // 2, 108, w, size, text, GOLD)
    cv.rect(28, 152, W - 56, 3, GOLD)

    # ---- lead story -------------------------------------------------
    lx, ly, lw, lh = 28, 174, W - 56, 264
    cv.rect(lx, ly, lw, lh, CARD)
    cv.rect(lx, ly, lw, 2, CARD_EDGE)
    cv.rect(lx, ly + lh - 2, lw, 2, CARD_EDGE)
    cv.rect(lx, ly, 2, lh, CARD_EDGE)
    cv.rect(lx + lw - 2, ly, 2, lh, CARD_EDGE)
    cv.rect(lx, ly, 10, lh, RED)

    w, size, text = LEAD_KICKER
    atlas.draw(cv, lx + 30, ly + 18, w, size, text, RED)
    w, size, text = LEAD_HEAD
    lines = atlas.wrap(w, size, text, 660)
    yy = ly + 50
    for ln in lines:
        atlas.draw(cv, lx + 30, yy, w, size, ln, INK)
        yy += 68
    w, size, text = LEAD_DESC
    lines = atlas.wrap(w, size, text, 660)
    yy = ly + 50 + 68 * len(atlas.wrap(*LEAD_HEAD[:2], LEAD_HEAD[2], 660)) + 8
    for ln in lines:
        atlas.draw(cv, lx + 30, yy, w, size, ln, BODY)
        yy += 32

    # lead art: explosion + jet, right side
    starburst(cv, 872, 306, 14, 96, 42, ORANGE)
    starburst(cv, 872, 306, 10, 58, 26, YELLOW)
    cv.circle(872, 306, 20, RED)
    jet(cv, 780, 196, 34, INK)

    # ---- story cards ------------------------------------------------
    # row 1: 3 cards, row 2: 2 cards
    rows = [(452, 3, CARDS[:3]), (694, 2, CARDS[3:])]
    card_h = 228
    for cy, count, cards in rows:
        gap = 12
        cw = (W - 56 - gap * (count - 1)) // count
        for i, (kicker, accent, head, desc, icon) in enumerate(cards):
            cx = 28 + i * (cw + gap)
            cv.rect(cx, cy, cw, card_h, CARD)
            cv.rect(cx, cy, cw, 2, CARD_EDGE)
            cv.rect(cx, cy + card_h - 2, cw, 2, CARD_EDGE)
            cv.rect(cx, cy, 2, card_h, CARD_EDGE)
            cv.rect(cx + cw - 2, cy, 2, card_h, CARD_EDGE)
            cv.rect(cx, cy, cw, 6, accent)
            ICONS[icon](cv, cx + 16, cy + 16, 60, accent)
            atlas.draw(cv, cx + 88, cy + 34, "bold", 20, kicker, accent)
            lines = atlas.wrap("bold", 32, head, cw - 32)
            yy = cy + 84
            for ln in lines[:2]:
                atlas.draw(cv, cx + 16, yy, "bold", 32, ln, INK)
                yy += 38
            lines = atlas.wrap("reg", 22, desc, cw - 32)
            yy = cy + 84 + 38 * 2 + 8
            for ln in lines[:2]:
                atlas.draw(cv, cx + 16, yy, "reg", 22, ln, BODY)
                yy += 27

    # ---- footer -----------------------------------------------------
    cv.rect(0, 936, W, H - 936, NAVY)
    w, size, text = FOOTER_1
    tw = atlas.text_width(w, size, text)
    atlas.draw(cv, (W - tw) // 2, 948, w, size, text, WHITE)
    w, size, text = FOOTER_2
    tw = atlas.text_width(w, size, text)
    atlas.draw(cv, (W - tw) // 2, 982, w, size, text, GOLD)

    return cv


# ------------------------------------------------------------ png out
def encode_png(w, h, px):
    raw = bytearray()
    stride = w * 3
    for y in range(h):
        raw.append(0)  # filter: None
        raw += px[y * stride:(y + 1) * stride]

    def chunk(typ, data):
        return (struct.pack(">I", len(data)) + typ + data +
                struct.pack(">I", zlib.crc32(typ + data) & 0xFFFFFFFF))

    ihdr = struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0)
    return (b"\x89PNG\r\n\x1a\n" +
            chunk(b"IHDR", ihdr) +
            chunk(b"IDAT", zlib.compress(bytes(raw), 6)) +
            chunk(b"IEND", b""))


def main():
    here = Path(__file__).resolve().parent
    atlas = Atlas(here / "glyphs.bin")
    cv = draw_image(atlas)
    out_dir = Path(os.environ.get("MAKEFUN_OUTPUT_DIR", "/output"))
    out_dir.mkdir(parents=True, exist_ok=True)
    data = encode_png(W, H, bytes(cv.px))
    (out_dir / "entry.png").write_bytes(data)
    print("wrote %s (%d bytes)" % (out_dir / "entry.png", len(data)))


if __name__ == "__main__":
    main()
