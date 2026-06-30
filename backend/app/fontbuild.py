"""Assemble a TTF or OTF from vectorized glyphs using fontTools.FontBuilder.

- ``ttf`` (default): TrueType outlines (glyf), built with TTGlyphPen.
- ``otf``: OpenType/CFF outlines, built with T2CharStringPen.

The same polygonal contours feed both; only the outline encoding differs.
"""
from __future__ import annotations

import io

from fontTools.fontBuilder import FontBuilder
from fontTools.pens.t2CharStringPen import T2CharStringPen
from fontTools.pens.ttGlyphPen import TTGlyphPen

from .vectorize import SPACE_ADVANCE, UPM, VectorGlyph

ASCENT = 800
DESCENT = -200
NOTDEF_ADVANCE = 500

_NOTDEF_BOX = (60, NOTDEF_ADVANCE - 60, 0, ASCENT)  # x0, x1, y0, y1


def _draw_tt(vg: VectorGlyph):
    pen = TTGlyphPen(None)
    for contour in vg.contours:
        if len(contour) < 3:
            continue
        pen.moveTo(contour[0])
        for pt in contour[1:]:
            pen.lineTo(pt)
        pen.closePath()
    return pen.glyph()


def _notdef_tt():
    pen = TTGlyphPen(None)
    x0, x1, y0, y1 = _NOTDEF_BOX
    pen.moveTo((x0, y0)); pen.lineTo((x0, y1)); pen.lineTo((x1, y1)); pen.lineTo((x1, y0)); pen.closePath()
    return pen.glyph()


def _draw_cff(vg: VectorGlyph, width: int):
    pen = T2CharStringPen(width, None)
    for contour in vg.contours:
        if len(contour) < 3:
            continue
        pen.moveTo(contour[0])
        for pt in contour[1:]:
            pen.lineTo(pt)
        pen.closePath()
    return pen.getCharString()


def _notdef_cff():
    pen = T2CharStringPen(NOTDEF_ADVANCE, None)
    x0, x1, y0, y1 = _NOTDEF_BOX
    pen.moveTo((x0, y0)); pen.lineTo((x0, y1)); pen.lineTo((x1, y1)); pen.lineTo((x1, y0)); pen.closePath()
    return pen.getCharString()


def _xmin(vg: VectorGlyph) -> int:
    xs = [x for c in vg.contours for x, _ in c]
    return min(xs) if xs else 0


def build_font(vglyphs: list[VectorGlyph], family: str = "YourOwnFont",
               fmt: str = "ttf") -> bytes:
    """Build a TTF or OTF (bytes) from the vectorized glyphs."""
    fmt = fmt.lower()
    if fmt not in ("ttf", "otf"):
        raise ValueError("fmt must be 'ttf' or 'otf'")
    is_ttf = fmt == "ttf"
    fb = FontBuilder(UPM, isTTF=is_ttf)

    glyph_order = [".notdef", "space"]
    metrics = {".notdef": (NOTDEF_ADVANCE, 0), "space": (SPACE_ADVANCE, 0)}
    cmap = {0x20: "space"}

    if is_ttf:
        outlines = {".notdef": _notdef_tt(), "space": TTGlyphPen(None).glyph()}
    else:
        outlines = {".notdef": _notdef_cff(),
                    "space": T2CharStringPen(SPACE_ADVANCE, None).getCharString()}

    for vg in vglyphs:
        name = vg.glyph.name
        if name in outlines:
            continue
        glyph_order.append(name)
        adv = max(vg.advance_width, 1)
        metrics[name] = (adv, _xmin(vg))
        cmap[vg.glyph.codepoint] = name
        outlines[name] = _draw_tt(vg) if is_ttf else _draw_cff(vg, adv)

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
