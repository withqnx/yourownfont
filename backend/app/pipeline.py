"""Glue: a scanned template image in, a finished Korean font out.

Each written syllable block is sliced into its 초성/중성/종성 regions to extract
jamo shapes in context; those jamo are then composed into all 11,172 syllables.
Digit/symbol cells are mapped directly.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from . import hangul
from .fontbuild import GlyphEntry, build_font
from .scan import decode_image, extract_cells
from .vectorize import vectorize_bitmap

MIN_SUB_INK = 25  # min ink pixels for a sliced jamo region to count


@dataclass
class BuildResult:
    font_bytes: bytes
    total_cells: int
    filled_cells: int
    syllables: int
    family: str
    fmt: str


def _crop_frac(bitmap: np.ndarray, ink_bbox, rect):
    """Crop a top-down fractional rect within the ink bounding box."""
    ix0, iy0, ix1, iy1 = ink_bbox
    bw, bh = ix1 - ix0 + 1, iy1 - iy0 + 1
    fx0, fy0, fx1, fy1 = rect
    cx0 = int(round(ix0 + fx0 * bw)); cx1 = int(round(ix0 + fx1 * bw))
    cy0 = int(round(iy0 + fy0 * bh)); cy1 = int(round(iy0 + fy1 * bh))
    sub = bitmap[cy0:cy1, cx0:cx1]
    if sub.size == 0 or int(np.count_nonzero(sub)) < MIN_SUB_INK:
        return None
    return sub


def _extract_jamo(bitmap: np.ndarray, cho: int, jung: int, jong: int,
                  cho_map, jung_map, jong_map) -> None:
    """Slice a written syllable and store each jamo's contours (first-wins)."""
    ys, xs = np.where(bitmap > 0)
    if len(xs) < MIN_SUB_INK:
        return
    ink_bbox = (int(xs.min()), int(ys.min()), int(xs.max()), int(ys.max()))
    rects = hangul.extract_rects(jung, jong > 0)

    def store(target: dict, idx: int, role: str) -> None:
        if idx in target:            # first-wins: keep the earliest (cleanest) sample
            return
        sub = _crop_frac(bitmap, ink_bbox, rects[role])
        if sub is None:
            return
        contours, _ = vectorize_bitmap(sub, is_blank=False)
        if contours:
            target[idx] = contours

    store(cho_map, cho, "cho")
    store(jung_map, jung, "jung")
    if jong > 0:
        store(jong_map, jong - 1, "jong")


def build_from_scan(image_bytes: bytes, family: str = "YourOwnFont",
                    fmt: str = "ttf") -> BuildResult:
    image = decode_image(image_bytes)
    cells = extract_cells(image)

    cho_map: dict[int, list] = {}
    jung_map: dict[int, list] = {}
    jong_map: dict[int, list] = {}
    entries: list[GlyphEntry] = []
    filled = 0

    for ec in cells:
        if ec.is_blank:
            continue
        filled += 1
        if ec.cell.role == "syllable":
            _extract_jamo(ec.bitmap, ec.cell.cho, ec.cell.jung, ec.cell.jong,
                          cho_map, jung_map, jong_map)
        elif ec.cell.role == "direct":
            contours, advance = vectorize_bitmap(ec.bitmap, False)
            if contours:
                entries.append(GlyphEntry(ec.cell.name, ec.cell.codepoint,
                                          contours, advance))

    # Compose every syllable whose required jamo were extracted.
    syllable_count = 0
    for cp in hangul.all_syllables():
        ci, ji, ti = hangul.decompose(cp)
        cho_c = cho_map.get(ci)
        jung_c = jung_map.get(ji)
        if not cho_c or not jung_c:
            continue
        jong_c = None
        if ti > 0:
            jong_c = jong_map.get(ti - 1)
            if not jong_c:
                continue
        contours = hangul.compose_contours(cho_c, jung_c, jong_c, ji)
        entries.append(GlyphEntry(f"uni{cp:04X}", cp, contours, hangul.ADVANCE))
        syllable_count += 1

    font_bytes = build_font(entries, family=family, fmt=fmt)
    return BuildResult(
        font_bytes=font_bytes,
        total_cells=len(cells),
        filled_cells=filled,
        syllables=syllable_count,
        family=family,
        fmt=fmt,
    )
