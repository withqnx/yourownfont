"""Printable PDF template generator.

Lays out a grid of cells (one per handwritten jamo / digit / symbol) with a
faint guide character, a small label, and four solid corner squares (fiducials)
used to perspective-correct the scan. The geometry here is the single source of
truth for cell positions; ``scan.py`` reconstructs the same grid.
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
CELL_GAP = 2 * mm
LABEL_H = 5 * mm

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

_ROLE_HINT = {"cho": "초성", "jung": "중성", "jong": "종성", "direct": ""}


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


def layout_cells(cells: list[Cell] | None = None) -> list[CellBox]:
    """Compute the box for each cell. Pure geometry, no drawing."""
    cells = cells if cells is not None else template_cells()
    x0, y0, x1, y1 = _content_rect()
    rows = (len(cells) + COLS - 1) // COLS
    cell_w = (x1 - x0) / COLS
    cell_h = (y1 - y0) / rows

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

    for cx, cy in marker_centers():
        c.setFillColorRGB(0, 0, 0)
        c.rect(cx - MARKER / 2, cy - MARKER / 2, MARKER, MARKER, fill=1, stroke=0)

    c.setFillColorRGB(0, 0, 0)
    c.setFont(_KR_FONT, 10)
    c.drawCentredString(PAGE_W / 2, PAGE_H - MARGIN + 1 * mm,
                        "YOUROWNFONT — 각 칸 안에 글자를 또박또박 써주세요")

    for box in layout_cells():
        cell = box.cell
        c.setStrokeColorRGB(0.75, 0.75, 0.75)
        c.setLineWidth(0.5)
        c.rect(box.x, box.y, box.w, box.h, fill=0, stroke=1)
        # faint guide glyph
        c.setFillColorRGB(0.82, 0.82, 0.82)
        size = box.h * 0.62
        c.setFont(_KR_FONT, size)
        c.drawCentredString(box.x + box.w / 2, box.y + box.h / 2 - size * 0.35,
                            cell.label)
        # label above: role hint + character
        hint = _ROLE_HINT.get(cell.role, "")
        label = f"{hint} {cell.label}".strip() if cell.role != "direct" else cell.label
        c.setFillColorRGB(0.4, 0.4, 0.4)
        c.setFont(_KR_FONT, 7)
        c.drawString(box.x + 1 * mm, box.y + box.h + 1 * mm, label)

    c.showPage()
    c.save()
    return buf.getvalue()
