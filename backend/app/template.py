"""Printable PDF template generator.

Empty writing boxes on a grid, each with the target character printed *above*
the box (never inside — an inside guide biases the handwriting). Four solid
corner squares (fiducials) let ``scan.py`` perspective-correct the scan. The
multi-belt charset needs more cells than fit on one page, so the template
paginates; every page carries its own fiducials and a fixed cell size, and the
geometry here is the single source of truth ``scan.py`` reconstructs per page.
"""
from __future__ import annotations

import io
import os
from dataclasses import dataclass

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas

from .charset import Cell, template_cells

PAGE_W, PAGE_H = A4
MARGIN = 15 * mm
MARKER = 8 * mm
COLS = 8
ROWS_PER_PAGE = 13          # 8 x 13 = 104 cells per page (fixed cell size)
CELL_GAP = 2 * mm
LABEL_H = 5 * mm
PER_PAGE = COLS * ROWS_PER_PAGE

# Register a Korean-capable font for the guides/labels. macOS paths first, then
# common Linux (Nanum) paths for the deployed container. Falls back to Helvetica
# (Latin-only) if none are found.
_KR_CANDIDATES = [
    "/System/Library/Fonts/Supplemental/AppleGothic.ttf",
    "/usr/share/fonts/truetype/nanum/NanumGothic.ttf",
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/truetype/noto/NotoSansCJKkr-Regular.otf",
]
_KR_FONT = "Helvetica"
for _p in _KR_CANDIDATES:
    if os.path.exists(_p):
        try:
            pdfmetrics.registerFont(TTFont("KRGuide", _p))
            _KR_FONT = "KRGuide"
            break
        except Exception:
            continue

@dataclass(frozen=True)
class CellBox:
    cell: Cell
    x: float
    y: float
    w: float
    h: float


def _content_rect() -> tuple[float, float, float, float]:
    x0 = MARGIN + MARKER + CELL_GAP
    y0 = MARGIN + MARKER + CELL_GAP
    x1 = PAGE_W - MARGIN - MARKER - CELL_GAP
    y1 = PAGE_H - MARGIN - MARKER - CELL_GAP
    return x0, y0, x1, y1


def paginate(cells: list[Cell] | None = None) -> list[list[Cell]]:
    """Split the cell list into pages of at most PER_PAGE cells."""
    cells = cells if cells is not None else template_cells()
    return [cells[i:i + PER_PAGE] for i in range(0, len(cells), PER_PAGE)] or [[]]


def layout_cells(cells: list[Cell]) -> list[CellBox]:
    """Compute the box for each cell on ONE page. Fixed cell size (ROWS_PER_PAGE)
    so geometry is identical across pages; pass a single page's cells."""
    x0, y0, x1, y1 = _content_rect()
    cell_w = (x1 - x0) / COLS
    cell_h = (y1 - y0) / ROWS_PER_PAGE

    boxes: list[CellBox] = []
    for i, c in enumerate(cells):
        col = i % COLS
        row = i // COLS
        cx = x0 + col * cell_w
        cy = y1 - (row + 1) * cell_h
        boxes.append(CellBox(
            cell=c,
            x=cx + CELL_GAP / 2,
            y=cy + CELL_GAP / 2,
            w=cell_w - CELL_GAP,
            h=cell_h - CELL_GAP - LABEL_H,
        ))
    return boxes


def marker_centers() -> list[tuple[float, float]]:
    """Centers of the four fiducial squares (TL, TR, BR, BL) in points."""
    m = MARGIN + MARKER / 2
    return [
        (m, PAGE_H - m),
        (PAGE_W - m, PAGE_H - m),
        (PAGE_W - m, m),
        (m, m),
    ]


def generate_template_pdf() -> bytes:
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    pages = paginate()

    for pno, page_cells in enumerate(pages, start=1):
        for cx, cy in marker_centers():
            c.setFillColorRGB(0, 0, 0)
            c.rect(cx - MARKER / 2, cy - MARKER / 2, MARKER, MARKER, fill=1, stroke=0)

        c.setFillColorRGB(0, 0, 0)
        c.setFont(_KR_FONT, 10)
        c.drawCentredString(
            PAGE_W / 2, PAGE_H - MARGIN + 1 * mm,
            f"YOUROWNFONT — 칸 위 글자(재미있는 단어들)를 보고 빈 칸에 본인 글씨로  ({pno}/{len(pages)}쪽)")

        for box in layout_cells(page_cells):
            c.setStrokeColorRGB(0.7, 0.7, 0.7)
            c.setLineWidth(0.6)
            c.rect(box.x, box.y, box.w, box.h, fill=0, stroke=1)
            c.setFillColorRGB(0.15, 0.15, 0.15)
            c.setFont(_KR_FONT, 10)
            c.drawCentredString(box.x + box.w / 2, box.y + box.h + 1.5 * mm, box.cell.label)

        c.showPage()

    c.save()
    return buf.getvalue()
