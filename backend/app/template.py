"""Printable PDF template generator.

Square writing boxes laid out as a **word-grouped flow**: a word's syllables sit
next to each other, and there's extra spacing between words (달 빛 · 꿈 · 행 복).
Boxes are empty; the target character is printed above each box (never inside —
an inside guide biases the handwriting). Content flows across as many pages as
needed; every page has its own four corner fiducials, and the geometry here is
the single source of truth ``scan.py`` reconstructs.
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
CELL = 18 * mm          # square writing box side
LABEL_H = 5 * mm        # space above each box for the guide character
INTRA_GAP = 1.5 * mm    # gap between boxes of the same word
INTER_GAP = 7 * mm      # gap between different words
ROW_GAP = 4 * mm        # vertical gap between rows
ROW_H = CELL + LABEL_H + ROW_GAP
_EPS = 0.5

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
    page: int
    x: float
    y: float
    w: float
    h: float


def _content_rect() -> tuple[float, float, float, float]:
    x0 = MARGIN + MARKER + INTRA_GAP
    y0 = MARGIN + MARKER + INTRA_GAP
    x1 = PAGE_W - MARGIN - MARKER - INTRA_GAP
    y1 = PAGE_H - MARGIN - MARKER - INTRA_GAP
    return x0, y0, x1, y1


def _group_key(c: Cell):
    if c.role == "syllable":
        return ("w", c.word)
    if c.label.isdigit():
        return ("d",)
    return ("s",)


def _groups() -> list[list[Cell]]:
    """Split template cells into runs that should stay together (words, digits,
    symbols), preserving order."""
    groups: list[list[Cell]] = []
    key = object()
    for c in template_cells():
        k = _group_key(c)
        if not groups or k != key:
            groups.append([c])
            key = k
        else:
            groups[-1].append(c)
    return groups


def layout_all() -> list[CellBox]:
    """Word-grouped flow layout across pages. Pure geometry, no drawing."""
    x0, y0, x1, y1 = _content_rect()
    boxes: list[CellBox] = []
    page = 0
    cx = x0
    rowtop = y1

    def page_break_if_needed() -> None:
        nonlocal page, rowtop, cx
        if rowtop - (CELL + LABEL_H) < y0 - _EPS:
            page += 1
            rowtop = y1
            cx = x0

    def newline() -> None:
        nonlocal cx, rowtop
        cx = x0
        rowtop -= ROW_H
        page_break_if_needed()

    for group in _groups():
        gw = len(group) * CELL + (len(group) - 1) * INTRA_GAP
        # keep a word together: wrap before it if it fits a row but not the rest
        if gw <= (x1 - x0) + _EPS and cx > x0 + _EPS and cx + gw > x1 + _EPS:
            newline()
        for c in group:
            if cx + CELL > x1 + _EPS and cx > x0 + _EPS:   # over-long group: wrap mid-way
                newline()
            y = rowtop - LABEL_H - CELL
            boxes.append(CellBox(cell=c, page=page, x=cx, y=y, w=CELL, h=CELL))
            cx += CELL + INTRA_GAP
        cx += INTER_GAP - INTRA_GAP   # widen the gap after a group
    return boxes


def num_pages() -> int:
    boxes = layout_all()
    return (max(b.page for b in boxes) + 1) if boxes else 1


def page_boxes(page: int) -> list[CellBox]:
    return [b for b in layout_all() if b.page == page]


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
    boxes = layout_all()
    pages = (max(b.page for b in boxes) + 1) if boxes else 1

    for pno in range(pages):
        for cx, cy in marker_centers():
            c.setFillColorRGB(0, 0, 0)
            c.rect(cx - MARKER / 2, cy - MARKER / 2, MARKER, MARKER, fill=1, stroke=0)

        c.setFillColorRGB(0, 0, 0)
        c.setFont(_KR_FONT, 10)
        c.drawCentredString(
            PAGE_W / 2, PAGE_H - MARGIN + 1 * mm,
            f"YOUROWNFONT — 칸 위 글자(단어)를 보고 빈 칸에 본인 글씨로  ({pno + 1}/{pages}쪽)")

        for box in (b for b in boxes if b.page == pno):
            c.setStrokeColorRGB(0.7, 0.7, 0.7)
            c.setLineWidth(0.6)
            c.rect(box.x, box.y, box.w, box.h, fill=0, stroke=1)
            c.setFillColorRGB(0.15, 0.15, 0.15)
            c.setFont(_KR_FONT, 11)
            c.drawCentredString(box.x + box.w / 2, box.y + box.h + 1.5 * mm, box.cell.label)

        c.showPage()

    c.save()
    return buf.getvalue()
