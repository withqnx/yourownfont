"""Turn a normalized cell bitmap into font-space contours.

Coordinate mapping (the heart of glyph quality):
  * The cell maps uniformly into font units with scale ``k = UPM / CELL_H``.
  * Vertical placement is *absolute*: the cell bottom sits at the descender and
    the top at the ascender, so every glyph shares one baseline.
  * Horizontal placement is *ink-relative*: the glyph is shifted to a fixed left
    sidebearing and the advance width follows the ink width — giving natural
    spacing instead of fixed-pitch cells.

Contours are polygonal (straight segments). potrace-style smooth curves are a
planned v1.1 quality upgrade; TrueType is perfectly happy with on-curve-only
polygons in the meantime.
"""
from __future__ import annotations

from dataclasses import dataclass

import cv2
import numpy as np

from .charset import Glyph
from .scan import CELL_H, ExtractedGlyph

UPM = 1000                  # units per em
DESCENT = 200               # cell bottom maps to y = -DESCENT
SIDEBEARING = 60            # left/right space around the ink, in font units
SPACE_ADVANCE = 300         # advance width for blank glyphs (e.g. space)
APPROX_EPS_PX = 0.8         # polygon simplification tolerance, in bitmap pixels
MIN_CONTOUR_AREA_PX = 8.0   # drop specks smaller than this (bitmap pixels^2)


@dataclass
class VectorGlyph:
    glyph: Glyph
    contours: list[list[tuple[int, int]]]  # font units, TrueType orientation
    advance_width: int
    is_blank: bool


def _signed_area(pts: list[tuple[int, int]]) -> float:
    a = 0.0
    n = len(pts)
    for i in range(n):
        x0, y0 = pts[i]
        x1, y1 = pts[(i + 1) % n]
        a += x0 * y1 - x1 * y0
    return a / 2.0


def vectorize(extracted: ExtractedGlyph) -> VectorGlyph:
    g = extracted.glyph
    if extracted.is_blank:
        return VectorGlyph(g, [], SPACE_ADVANCE, True)

    bmp = extracted.bitmap
    k = UPM / CELL_H

    ys, xs = np.where(bmp > 0)
    ink_x0 = int(xs.min())
    ink_w_px = int(xs.max() - xs.min() + 1)

    contours, hierarchy = cv2.findContours(
        bmp, cv2.RETR_CCOMP, cv2.CHAIN_APPROX_SIMPLE
    )

    out_contours: list[list[tuple[int, int]]] = []
    for idx, cnt in enumerate(contours):
        if cv2.contourArea(cnt) < MIN_CONTOUR_AREA_PX:
            continue
        approx = cv2.approxPolyDP(cnt, APPROX_EPS_PX, True)
        if len(approx) < 3:
            continue
        # RETR_CCOMP: hierarchy[0][idx][3] == -1 -> outer contour, else a hole.
        is_hole = hierarchy[0][idx][3] != -1

        pts: list[tuple[int, int]] = []
        for p in approx.reshape(-1, 2):
            px, py = int(p[0]), int(p[1])
            fx = int(round((px - ink_x0) * k)) + SIDEBEARING
            fy = int(round((CELL_H - py) * k)) - DESCENT
            pts.append((fx, fy))

        # TrueType fill convention: outer contours clockwise (signed area < 0),
        # holes counter-clockwise (signed area > 0), with y pointing up.
        area = _signed_area(pts)
        if (not is_hole and area > 0) or (is_hole and area < 0):
            pts.reverse()
        out_contours.append(pts)

    advance = int(round(ink_w_px * k)) + 2 * SIDEBEARING
    return VectorGlyph(g, out_contours, advance, False)
