"""Turn a normalized cell bitmap into font-space contours.

Coordinate mapping:
  * The cell maps uniformly into font units with scale ``k = UPM / CELL_H``.
  * Vertical placement is absolute: the cell bottom sits at the descender and
    the top at the ascender, so directly-mapped glyphs share one baseline.
  * Horizontal placement is ink-relative: shifted to a fixed left sidebearing,
    advance width follows the ink width.

Contours are polygonal (straight segments). potrace-style smooth curves are a
planned quality upgrade; TrueType is happy with on-curve-only polygons.
"""
from __future__ import annotations

import cv2
import numpy as np

from .scan import CELL_H

UPM = 1000                  # units per em
DESCENT = 200               # cell bottom maps to y = -DESCENT
SIDEBEARING = 60            # left/right space around the ink, in font units
SPACE_ADVANCE = 300         # advance width for blank glyphs (e.g. space)
APPROX_EPS_PX = 0.8         # polygon simplification tolerance, in bitmap pixels
MIN_CONTOUR_AREA_PX = 8.0   # drop specks smaller than this (bitmap pixels^2)

Contours = list[list[tuple[int, int]]]


def _signed_area(pts: list[tuple[int, int]]) -> float:
    a = 0.0
    n = len(pts)
    for i in range(n):
        x0, y0 = pts[i]
        x1, y1 = pts[(i + 1) % n]
        a += x0 * y1 - x1 * y0
    return a / 2.0


def vectorize_bitmap(bitmap: np.ndarray, is_blank: bool) -> tuple[Contours, int]:
    """Return (contours, advance_width) for one normalized cell bitmap.

    Contours use TrueType fill orientation (outer clockwise, holes CCW, y up).
    For components used only in composition the advance is ignored.
    """
    if is_blank:
        return [], SPACE_ADVANCE

    k = UPM / CELL_H
    ys, xs = np.where(bitmap > 0)
    ink_x0 = int(xs.min())
    ink_w_px = int(xs.max() - xs.min() + 1)

    contours, hierarchy = cv2.findContours(
        bitmap, cv2.RETR_CCOMP, cv2.CHAIN_APPROX_SIMPLE
    )

    out: Contours = []
    for idx, cnt in enumerate(contours):
        if cv2.contourArea(cnt) < MIN_CONTOUR_AREA_PX:
            continue
        approx = cv2.approxPolyDP(cnt, APPROX_EPS_PX, True)
        if len(approx) < 3:
            continue
        is_hole = hierarchy[0][idx][3] != -1

        pts: list[tuple[int, int]] = []
        for p in approx.reshape(-1, 2):
            px, py = int(p[0]), int(p[1])
            fx = int(round((px - ink_x0) * k)) + SIDEBEARING
            fy = int(round((CELL_H - py) * k)) - DESCENT
            pts.append((fx, fy))

        area = _signed_area(pts)
        if (not is_hole and area > 0) or (is_hole and area < 0):
            pts.reverse()
        out.append(pts)

    advance = int(round(ink_w_px * k)) + 2 * SIDEBEARING
    return out, advance
