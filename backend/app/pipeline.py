"""Glue: scanned template page(s) in, a finished Korean font out.

Each written syllable block is sliced into its 초성/중성/종성 regions to extract
jamo shapes *in context* (multi-belt: e.g. 초성 with a vertical vs horizontal
vowel). Those jamo are then composed into all 11,172 syllables, picking the belt
that matches each target syllable. Digit/symbol cells are mapped directly.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from . import hangul, template
from .fontbuild import GlyphEntry, build_font
from .scan import decode_image, extract_cells
from .vectorize import vectorize_bitmap

MIN_SUB_INK = 25  # min ink pixels for a sliced jamo region to count

# Belt-keyed jamo stores: (jamo_index, belt) -> contours
Store = dict[tuple[int, str], list]


@dataclass
class _Maps:
    cho: Store = field(default_factory=dict)
    jung: Store = field(default_factory=dict)
    jong: Store = field(default_factory=dict)


@dataclass
class BuildResult:
    font_bytes: bytes
    total_cells: int
    filled_cells: int
    syllables: int
    pages: int
    family: str
    fmt: str


def _crop_frac(bitmap, ink_bbox, rect):
    ix0, iy0, ix1, iy1 = ink_bbox
    bw, bh = ix1 - ix0 + 1, iy1 - iy0 + 1
    fx0, fy0, fx1, fy1 = rect
    cx0 = int(round(ix0 + fx0 * bw)); cx1 = int(round(ix0 + fx1 * bw))
    cy0 = int(round(iy0 + fy0 * bh)); cy1 = int(round(iy0 + fy1 * bh))
    sub = bitmap[cy0:cy1, cx0:cx1]
    if sub.size == 0 or int(np.count_nonzero(sub)) < MIN_SUB_INK:
        return None
    return sub


def _extract_jamo(bitmap, cho, jung, jong, maps: _Maps) -> None:
    """Slice a written syllable, storing each jamo into its belt (first-wins)."""
    ys, xs = np.where(bitmap > 0)
    if len(xs) < MIN_SUB_INK:
        return
    ink_bbox = (int(xs.min()), int(ys.min()), int(xs.max()), int(ys.max()))
    rects = hangul.extract_rects(jung, jong > 0)

    def store(target: Store, idx: int, belt: str, role: str) -> None:
        if (idx, belt) in target:
            return
        sub = _crop_frac(bitmap, ink_bbox, rects[role])
        if sub is None:
            return
        contours, _ = vectorize_bitmap(sub, is_blank=False)
        if contours:
            target[(idx, belt)] = contours

    store(maps.cho, cho, hangul.cho_belt(jung), "cho")
    store(maps.jung, jung, hangul.jung_belt(jong > 0), "jung")
    if jong > 0:
        store(maps.jong, jong - 1, "_", "jong")


def _pick(store: Store, idx: int, belts: list[str]):
    for b in belts:
        if (idx, b) in store:
            return store[(idx, b)]
    return None


def build_from_scan(images: list[bytes], family: str = "YourOwnFont",
                    fmt: str = "ttf") -> BuildResult:
    if not images:
        raise ValueError("No template pages were uploaded.")

    n_pages = template.num_pages()
    maps = _Maps()
    entries: list[GlyphEntry] = []
    total_cells = 0
    filled = 0

    # Pair each uploaded image with its page's placed boxes (in order).
    for p, img_bytes in enumerate(images):
        if p >= n_pages:
            break
        image = decode_image(img_bytes)
        for ec in extract_cells(image, template.page_boxes(p)):
            total_cells += 1
            if ec.is_blank:
                continue
            filled += 1
            if ec.cell.role == "syllable":
                _extract_jamo(ec.bitmap, ec.cell.cho, ec.cell.jung, ec.cell.jong, maps)
            elif ec.cell.role == "direct":
                contours, advance = vectorize_bitmap(ec.bitmap, False)
                if contours:
                    entries.append(GlyphEntry(ec.cell.name, ec.cell.codepoint,
                                              contours, advance))

    # Compose every syllable whose jamo were captured, picking matching belts.
    syllable_count = 0
    for cp in hangul.all_syllables():
        ci, ji, ti = hangul.decompose(cp)
        cho_c = _pick(maps.cho, ci, hangul.cho_belts(ji))
        jung_c = _pick(maps.jung, ji, hangul.jung_belts(ti > 0))
        if not cho_c or not jung_c:
            continue
        jong_c = None
        if ti > 0:
            jong_c = _pick(maps.jong, ti - 1, ["_"])
            if not jong_c:
                continue
        contours = hangul.compose_contours(cho_c, jung_c, jong_c, ji)
        entries.append(GlyphEntry(f"uni{cp:04X}", cp, contours, hangul.ADVANCE))
        syllable_count += 1

    font_bytes = build_font(entries, family=family, fmt=fmt)
    return BuildResult(
        font_bytes=font_bytes,
        total_cells=total_cells,
        filled_cells=filled,
        syllables=syllable_count,
        pages=n_pages,
        family=family,
        fmt=fmt,
    )
