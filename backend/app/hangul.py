"""Hangul syllable composition.

Modern Hangul syllables (U+AC00..U+D7A3) decompose deterministically into
초성/중성/종성 indices. We place the user's handwritten jamo components into
zones of the em square, scaling each to fit, and merge them into one glyph.

The zone layout depends on the medial vowel's orientation:
  * RIGHT  — vertical vowels (ㅏ, ㅣ …): 초성 left,  중성 right
  * BOTTOM — horizontal vowels (ㅗ, ㅜ …): 초성 top,  중성 bottom
  * WRAP   — compound vowels (ㅘ, ㅟ …): 초성 top-left, 중성 wraps right+bottom
A trailing 종성 (받침) compresses the above upward and sits along the bottom.

This is a 1-set (1벌) scheme: each jamo is written once and reused everywhere,
with size/position doing the work a multi-set font would do with extra shapes.
"""
from __future__ import annotations

SBASE = 0xAC00
LCOUNT, VCOUNT, TCOUNT = 19, 21, 28  # T includes the "no 종성" slot
SCOUNT = LCOUNT * VCOUNT * TCOUNT     # 11172

# Em-square region the syllable is drawn into (font units; baseline y=0).
RX0, RY0, RX1, RY1 = 70, 0, 930, 760
ADVANCE = 1000

# Medial-vowel orientation by 중성 index (order matches charset.JUNG).
#   ㅏㅐㅑㅒㅓㅔㅕㅖ ㅗ ㅘㅙㅚ ㅛ ㅜ ㅝㅞㅟ ㅠ ㅡ ㅢ ㅣ
_ORIENT = [
    "R", "R", "R", "R", "R", "R", "R", "R",  # 0-7
    "B",                                       # 8  ㅗ
    "W", "W", "W",                             # 9-11 ㅘㅙㅚ
    "B",                                       # 12 ㅛ
    "B",                                       # 13 ㅜ
    "W", "W", "W",                             # 14-16 ㅝㅞㅟ
    "B",                                       # 17 ㅠ
    "B",                                       # 18 ㅡ
    "W",                                       # 19 ㅢ
    "R",                                       # 20 ㅣ
]

Box = tuple[float, float, float, float]  # x0, y0, x1, y1 as fractions of region


def orientation(jung: int) -> str:
    return _ORIENT[jung]


# --- Belts (문맥별 변형) --------------------------------------------------
# A jamo is captured in more than one context so it can be placed naturally:
#   초성 belt "V" = written with a vertical vowel (가, 거);  "H" = horizontal (고, 구)
#   중성 belt "0" = no 받침 (가);                              "T" = with 받침 (강)
#   종성 belt "_" = single set

def cho_belt(jung: int) -> str:
    return "V" if _ORIENT[jung] == "R" else "H"


def jung_belt(has_jong: bool) -> str:
    return "T" if has_jong else "0"


# Preferred belt first, then fallbacks (used when a context wasn't written).
def cho_belts(jung: int) -> list[str]:
    return ["V", "H"] if _ORIENT[jung] == "R" else ["H", "V"]


def jung_belts(has_jong: bool) -> list[str]:
    return ["T", "0"] if has_jong else ["0", "T"]


def zones(jung: int, has_jong: bool) -> dict[str, Box]:
    """Fractional zones (0..1 within the region) for each present component."""
    o = _ORIENT[jung]
    if not has_jong:
        if o == "R":
            return {"cho": (0.0, 0.0, 0.56, 1.0), "jung": (0.56, 0.0, 1.0, 1.0)}
        if o == "B":
            return {"cho": (0.0, 0.44, 1.0, 1.0), "jung": (0.0, 0.0, 1.0, 0.46)}
        # WRAP
        return {"cho": (0.02, 0.46, 0.52, 1.0), "jung": (0.0, 0.0, 1.0, 1.0)}
    # with 종성 (받침): squeeze cho/jung into the top, jong along the bottom
    jong_box: Box = (0.0, 0.0, 1.0, 0.30)
    if o == "R":
        return {"cho": (0.0, 0.32, 0.56, 1.0), "jung": (0.56, 0.32, 1.0, 1.0),
                "jong": jong_box}
    if o == "B":
        return {"cho": (0.0, 0.66, 1.0, 1.0), "jung": (0.0, 0.32, 1.0, 0.66),
                "jong": jong_box}
    return {"cho": (0.02, 0.66, 0.52, 1.0), "jung": (0.0, 0.30, 1.0, 1.0),
            "jong": jong_box}


def _abs_box(frac: Box, pad: float = 0.06) -> Box:
    """Fractional zone -> absolute font-unit box, shrunk by a small padding."""
    fx0, fy0, fx1, fy1 = frac
    w, h = RX1 - RX0, RY1 - RY0
    px, py = (fx1 - fx0) * w * pad, (fy1 - fy0) * h * pad
    return (RX0 + fx0 * w + px, RY0 + fy0 * h + py,
            RX0 + fx1 * w - px, RY0 + fy1 * h - py)


def place_component(contours: list[list[tuple[int, int]]], frac: Box
                    ) -> list[list[tuple[int, int]]]:
    """Scale+translate a component's contours to fill the given zone."""
    if not contours:
        return []
    xs = [x for c in contours for x, _ in c]
    ys = [y for c in contours for _, y in c]
    sx0, sy0, sx1, sy1 = min(xs), min(ys), max(xs), max(ys)
    sw, sh = max(sx1 - sx0, 1), max(sy1 - sy0, 1)

    bx0, by0, bx1, by1 = _abs_box(frac)
    kx, ky = (bx1 - bx0) / sw, (by1 - by0) / sh

    out: list[list[tuple[int, int]]] = []
    for c in contours:
        out.append([(int(round(bx0 + (x - sx0) * kx)),
                     int(round(by0 + (y - sy0) * ky))) for x, y in c])
    return out


def extract_rects(jung: int, has_jong: bool) -> dict[str, Box]:
    """Rectangles (top-down fractions of the ink bbox) to slice a written
    syllable into its jamo. Tuned for extraction, so each rect isolates one
    jamo as cleanly as a rectangle allows (compound vowels are approximate).

    Box = (x0, y0, x1, y1) with y0 at the TOP (image coordinates).
    """
    o = _ORIENT[jung]
    if not has_jong:
        if o == "R":
            return {"cho": (0.0, 0.0, 0.55, 1.0), "jung": (0.55, 0.0, 1.0, 1.0)}
        if o == "B":
            return {"cho": (0.0, 0.0, 1.0, 0.52), "jung": (0.0, 0.48, 1.0, 1.0)}
        # WRAP: 초성 top-left; 중성 fills the lower-right L (approx rectangle)
        return {"cho": (0.0, 0.0, 0.5, 0.5), "jung": (0.32, 0.12, 1.0, 1.0)}
    # with 받침 — coverage syllables only use ㅏ (RIGHT) here
    if o == "R":
        return {"cho": (0.0, 0.0, 0.55, 0.66), "jung": (0.55, 0.0, 1.0, 0.66),
                "jong": (0.0, 0.66, 1.0, 1.0)}
    if o == "B":
        return {"cho": (0.0, 0.0, 1.0, 0.4), "jung": (0.0, 0.4, 1.0, 0.7),
                "jong": (0.0, 0.7, 1.0, 1.0)}
    return {"cho": (0.0, 0.0, 0.5, 0.42), "jung": (0.32, 0.1, 1.0, 0.7),
            "jong": (0.0, 0.7, 1.0, 1.0)}


def decompose(codepoint: int) -> tuple[int, int, int]:
    """Syllable codepoint -> (cho, jung, jong) where jong 0 means none."""
    s = codepoint - SBASE
    cho = s // (VCOUNT * TCOUNT)
    jung = (s % (VCOUNT * TCOUNT)) // TCOUNT
    jong = s % TCOUNT
    return cho, jung, jong


def compose_contours(cho_c, jung_c, jong_c, jung_idx: int
                     ) -> list[list[tuple[int, int]]]:
    """Merge component contours for one syllable into placed contours.

    ``*_c`` are raw contour lists (font units) for the components; ``jong_c`` is
    None when the syllable has no 받침.
    """
    z = zones(jung_idx, jong_c is not None)
    merged: list[list[tuple[int, int]]] = []
    merged += place_component(cho_c, z["cho"])
    merged += place_component(jung_c, z["jung"])
    if jong_c is not None:
        merged += place_component(jong_c, z["jong"])
    return merged


def all_syllables() -> list[int]:
    return list(range(SBASE, SBASE + SCOUNT))
