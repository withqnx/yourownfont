"""Glue: a scanned template image in, a finished Korean font out.

Component cells (jamo) are vectorized once, then all 11,172 modern syllables
are composed from them. Digit/symbol cells are mapped directly.
"""
from __future__ import annotations

from dataclasses import dataclass

from . import hangul
from .fontbuild import GlyphEntry, build_font
from .scan import decode_image, extract_cells
from .vectorize import vectorize_bitmap


@dataclass
class BuildResult:
    font_bytes: bytes
    total_cells: int
    filled_cells: int
    syllables: int
    family: str
    fmt: str


def build_from_scan(image_bytes: bytes, family: str = "YourOwnFont",
                    fmt: str = "ttf") -> BuildResult:
    image = decode_image(image_bytes)
    cells = extract_cells(image)

    cho: dict[int, list] = {}
    jung: dict[int, list] = {}
    jong: dict[int, list] = {}
    entries: list[GlyphEntry] = []
    filled = 0

    for ec in cells:
        contours, advance = vectorize_bitmap(ec.bitmap, ec.is_blank)
        if not ec.is_blank:
            filled += 1
        role = ec.cell.role
        if role == "cho":
            cho[ec.cell.index] = contours
        elif role == "jung":
            jung[ec.cell.index] = contours
        elif role == "jong":
            jong[ec.cell.index] = contours
        elif role == "direct" and contours:
            entries.append(GlyphEntry(ec.cell.name, ec.cell.codepoint, contours, advance))

    # Compose every syllable whose required components were actually written.
    syllable_count = 0
    for cp in hangul.all_syllables():
        ci, ji, ti = hangul.decompose(cp)
        cho_c = cho.get(ci)
        jung_c = jung.get(ji)
        if not cho_c or not jung_c:
            continue
        jong_c = None
        if ti > 0:
            jong_c = jong.get(ti - 1)
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
