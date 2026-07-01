"""Assemble a TTF or OTF from glyph contours using fontTools.FontBuilder.

- ``ttf`` (default): TrueType outlines (glyf), built with TTGlyphPen.
- ``otf``: OpenType/CFF outlines, built with T2CharStringPen.
"""
from __future__ import annotations

import io
from dataclasses import dataclass, field

from fontTools.fontBuilder import FontBuilder
from fontTools.pens.t2CharStringPen import T2CharStringPen
from fontTools.pens.ttGlyphPen import TTGlyphPen

from .vectorize import SPACE_ADVANCE, UPM

ASCENT = 800
DESCENT = -200
NOTDEF_ADVANCE = 500
_NOTDEF_BOX = (60, NOTDEF_ADVANCE - 60, 0, ASCENT)

Contours = list[list[tuple[int, int]]]


@dataclass
class GlyphEntry:
    name: str
    codepoint: int
    contours: Contours
    advance: int = field(default=SPACE_ADVANCE)


def _draw_tt(contours: Contours):
    pen = TTGlyphPen(None)
    for c in contours:
        if len(c) < 3:
            continue
        pen.moveTo(c[0])
        for pt in c[1:]:
            pen.lineTo(pt)
        pen.closePath()
    return pen.glyph()


def _draw_cff(contours: Contours, width: int):
    pen = T2CharStringPen(width, None)
    for c in contours:
        if len(c) < 3:
            continue
        pen.moveTo(c[0])
        for pt in c[1:]:
            pen.lineTo(pt)
        pen.closePath()
    return pen.getCharString()


def _notdef_contours() -> Contours:
    x0, x1, y0, y1 = _NOTDEF_BOX
    return [[(x0, y0), (x0, y1), (x1, y1), (x1, y0)]]


def _xmin(contours: Contours) -> int:
    xs = [x for c in contours for x, _ in c]
    return min(xs) if xs else 0


def build_font(entries: list[GlyphEntry], family: str = "YourOwnFont",
               fmt: str = "ttf") -> bytes:
    """Build a TTF or OTF (bytes) from glyph entries (name/codepoint/contours)."""
    fmt = fmt.lower()
    if fmt not in ("ttf", "otf"):
        raise ValueError("fmt must be 'ttf' or 'otf'")
    is_ttf = fmt == "ttf"
    fb = FontBuilder(UPM, isTTF=is_ttf)

    glyph_order = [".notdef", "space"]
    metrics = {".notdef": (NOTDEF_ADVANCE, 0), "space": (SPACE_ADVANCE, 0)}
    cmap = {0x20: "space"}

    if is_ttf:
        outlines = {".notdef": _draw_tt(_notdef_contours()),
                    "space": TTGlyphPen(None).glyph()}
    else:
        outlines = {".notdef": _draw_cff(_notdef_contours(), NOTDEF_ADVANCE),
                    "space": T2CharStringPen(SPACE_ADVANCE, None).getCharString()}

    for e in entries:
        if e.name in outlines:
            continue
        glyph_order.append(e.name)
        adv = max(e.advance, 1)
        metrics[e.name] = (adv, _xmin(e.contours))
        if e.codepoint >= 0:
            cmap[e.codepoint] = e.name
        outlines[e.name] = _draw_tt(e.contours) if is_ttf else _draw_cff(e.contours, adv)

    fb.setupGlyphOrder(glyph_order)
    fb.setupCharacterMap(cmap)
    if is_ttf:
        fb.setupGlyf(outlines)
    else:
        fb.setupCFF(
            psName=f"{family.replace(' ', '')}-Regular",
            fontInfo={"FullName": f"{family} Regular"},
            charStringsDict=outlines,
            privateDict={},
        )
    fb.setupHorizontalMetrics(metrics)
    fb.setupHorizontalHeader(ascent=ASCENT, descent=DESCENT)
    fb.setupNameTable({
        "familyName": family,
        "styleName": "Regular",
        "fullName": f"{family} Regular",
        "psName": f"{family.replace(' ', '')}-Regular",
        "version": "Version 1.0",
    })
    fb.setupOS2(sTypoAscender=ASCENT, sTypoDescender=DESCENT,
                usWinAscent=ASCENT, usWinDescent=-DESCENT)
    fb.setupPost()

    buf = io.BytesIO()
    fb.save(buf)
    return buf.getvalue()
