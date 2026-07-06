"""Scan ingestion: align a photographed/scanned template and cut out glyphs.

The pipeline:
  1. detect the four solid corner squares (fiducials)
  2. warp the image so those markers land on their known canonical positions
  3. binarize the ink
  4. for each template cell, crop the writing area and extract a clean,
     centered, normalized glyph bitmap

Cell geometry comes from ``template.layout_cells`` so the template and the
scanner can never drift out of sync.
"""
from __future__ import annotations

from dataclasses import dataclass

import cv2
import numpy as np

from .charset import Cell
from .template import PAGE_H, PAGE_W, marker_centers

DPI = 200
SCALE = DPI / 72.0                       # points -> canonical pixels
CANON_W = int(round(PAGE_W * SCALE))
CANON_H = int(round(PAGE_H * SCALE))
# Each cell is rendered to a fixed bitmap whose *aspect ratio matches the cell*,
# so the whole cell maps uniformly into font space. Ink keeps its position and
# relative size within the cell — a period stays small, a capital stays tall.
CELL_H = 256


@dataclass
class ExtractedCell:
    cell: Cell
    bitmap: np.ndarray  # CELL_H x CELL_W, uint8, 255=ink on 0 background
    is_blank: bool


def _pt_to_px(x_pt: float, y_pt: float) -> tuple[float, float]:
    """Convert reportlab points (origin bottom-left) to canonical pixels (top-left)."""
    return x_pt * SCALE, (PAGE_H - y_pt) * SCALE


def _order_corners(pts: np.ndarray) -> np.ndarray:
    """Order 4 points as TL, TR, BR, BL."""
    s = pts.sum(axis=1)
    d = np.diff(pts, axis=1).ravel()
    return np.array([
        pts[np.argmin(s)],   # TL: smallest x+y
        pts[np.argmin(d)],   # TR: smallest y-x
        pts[np.argmax(s)],   # BR: largest x+y
        pts[np.argmax(d)],   # BL: largest y-x
    ], dtype=np.float32)


def _detect_markers(gray: np.ndarray) -> np.ndarray:
    """Return the four fiducial centers as ordered (TL,TR,BR,BL) float32 points."""
    _, th = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    contours, _ = cv2.findContours(th, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    img_area = gray.shape[0] * gray.shape[1]

    candidates: list[tuple[float, float]] = []
    for c in contours:
        area = cv2.contourArea(c)
        # markers are small solid squares; glyph strokes are larger and not solid
        if area < img_area * 0.00003 or area > img_area * 0.02:
            continue
        peri = cv2.arcLength(c, True)
        approx = cv2.approxPolyDP(c, 0.04 * peri, True)
        if len(approx) != 4 or not cv2.isContourConvex(approx):
            continue
        x, y, w, h = cv2.boundingRect(approx)
        ar = w / float(h)
        if not (0.7 < ar < 1.4):          # roughly square
            continue
        if area / float(w * h) < 0.85:    # solidly filled (excludes letters)
            continue
        M = cv2.moments(c)
        candidates.append((M["m10"] / M["m00"], M["m01"] / M["m00"]))

    if len(candidates) < 4:
        raise ValueError(
            f"Found only {len(candidates)} corner markers; need 4. "
            "Make sure the whole sheet with its four black corner squares is visible."
        )

    # Match the four image corners to their nearest solid-square candidate.
    h_img, w_img = gray.shape
    img_corners = [(0, 0), (w_img, 0), (w_img, h_img), (0, h_img)]
    pts = np.array(candidates, dtype=np.float32)
    chosen = []
    for corner in img_corners:
        d = np.hypot(pts[:, 0] - corner[0], pts[:, 1] - corner[1])
        chosen.append(pts[int(np.argmin(d))])
    return _order_corners(np.array(chosen, dtype=np.float32))


def align(image_bgr: np.ndarray) -> np.ndarray:
    """Perspective-correct the scan to the canonical A4 pixel space (returns gray)."""
    gray = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2GRAY)
    src = _detect_markers(gray)
    dst = np.array([_pt_to_px(x, y) for x, y in marker_centers()], dtype=np.float32)
    H = cv2.getPerspectiveTransform(src, dst)
    return cv2.warpPerspective(gray, H, (CANON_W, CANON_H),
                               flags=cv2.INTER_LINEAR,
                               borderValue=255)


def _binarize(gray: np.ndarray) -> np.ndarray:
    """Ink -> 255, paper -> 0, robust to uneven lighting."""
    blur = cv2.GaussianBlur(gray, (5, 5), 0)
    return cv2.adaptiveThreshold(
        blur, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY_INV, 31, 15,
    )


def _render_cell(cell: np.ndarray, cell_w_px: int) -> tuple[np.ndarray, bool]:
    """Resize the whole cell crop to a fixed (CELL_H x cell_w_px) bitmap.

    The cell is mapped uniformly — ink position and size within the cell are
    preserved, so vectorize() can place glyphs on a shared baseline.
    """
    out = cv2.resize(cell, (cell_w_px, CELL_H), interpolation=cv2.INTER_AREA)
    _, out = cv2.threshold(out, 64, 255, cv2.THRESH_BINARY)
    is_blank = int(np.count_nonzero(out)) < 30
    return out, is_blank


def extract_cells(image_bgr: np.ndarray, boxes) -> list[ExtractedCell]:
    """Full ingestion for ONE page: align, binarize, cut out its placed boxes."""
    aligned = align(image_bgr)
    binary = _binarize(aligned)

    if not boxes:
        return []
    # All boxes share a shape; derive the fixed bitmap width from the aspect ratio.
    aspect = boxes[0].w / boxes[0].h
    cell_w_px = max(1, int(round(CELL_H * aspect)))

    results: list[ExtractedCell] = []
    for box in boxes:
        x_px, top_px = _pt_to_px(box.x, box.y + box.h)  # top-left corner of writing area
        w_px = int(round(box.w * SCALE))
        h_px = int(round(box.h * SCALE))
        x = int(round(x_px))
        y = int(round(top_px))
        region = binary[y:y + h_px, x:x + w_px]
        if region.size == 0:
            results.append(ExtractedCell(box.cell, np.zeros((CELL_H, cell_w_px), np.uint8), True))
            continue
        # erode away the cell's printed border ink near the edges
        region = region.copy()
        b = max(2, int(0.04 * min(region.shape)))
        region[:b, :] = 0; region[-b:, :] = 0; region[:, :b] = 0; region[:, -b:] = 0
        bitmap, blank = _render_cell(region, cell_w_px)
        results.append(ExtractedCell(box.cell, bitmap, blank))
    return results


def decode_image(data: bytes) -> np.ndarray:
    arr = np.frombuffer(data, np.uint8)
    img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    if img is None:
        raise ValueError("Could not decode the uploaded image.")
    return img
