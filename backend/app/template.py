"""Printable PDF template generator.

Lays out a grid of cells, one per target glyph, with a faint guide character
and four solid corner squares (fiducial markers) used to perspective-correct
the scan. The geometry produced here is the single source of truth for cell
positions; ``scan.py`` reconstructs the same grid from the detected markers.
"""
from __future__ import annotations

import io
from dataclasses import dataclass

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas

from .charset import Glyph, template_charset

# --- Layout constants (in mm), shared conceptually with scan reconstruction ---
PAGE_W, PAGE_H = A4                      # points
MARGIN = 15 * mm                         # outer margin
MARKER = 8 * mm                          # fiducial square side
COLS = 8                                 # cells per row
CELL_GAP = 2 * mm
LABEL_H = 5 * mm                         # space above each cell for the guide char


@dataclass(frozen=True)
class CellBox:
    """A glyph's writing area in PDF points (origin bottom-left, as in reportlab)."""

    glyph: Glyph
    x: float
    y: float
    w: float
    h: float


def _content_rect() -> tuple[float, float, float, float]:
    """Region between the fiducial markers (x0, y0, x1, y1) in points."""
    x0 = MARGIN + MARKER + CELL_GAP
    y0 = MARGIN + MARKER + CELL_GAP
    x1 = PAGE_W - MARGIN - MARKER - CELL_GAP
    y1 = PAGE_H - MARGIN - MARKER - CELL_GAP
    return x0, y0, x1, y1


def layout_cells(glyphs: list[Glyph] | None = None) -> list[CellBox]:
    """Compute the cell box for each glyph. Pure geometry, no drawing."""
    glyphs = glyphs if glyphs is not None else template_charset()
    x0, y0, x1, y1 = _content_rect()
    rows = (len(glyphs) + COLS - 1) // COLS
    cell_w = (x1 - x0) / COLS
    cell_h = (y1 - y0) / rows

    boxes: list[CellBox] = []
    for i, g in enumerate(glyphs):
        col = i % COLS
        row = i // COLS
        cx = x0 + col * cell_w
        # rows fill top-to-bottom; reportlab y grows upward
        cy = y1 - (row + 1) * cell_h
        boxes.append(
            CellBox(
                glyph=g,
                x=cx + CELL_GAP / 2,
                y=cy + CELL_GAP / 2,
                w=cell_w - CELL_GAP,
                h=cell_h - CELL_GAP - LABEL_H,
            )
        )
    return boxes


def marker_centers() -> list[tuple[float, float]]:
    """Centers of the four fiducial squares, in points (TL, TR, BR, BL order)."""
    m = MARGIN + MARKER / 2
    return [
        (m, PAGE_H - m),          # top-left
        (PAGE_W - m, PAGE_H - m),  # top-right
        (PAGE_W - m, m),           # bottom-right
        (m, m),                    # bottom-left
    ]


def generate_template_pdf() -> bytes:
    """Render the template to PDF bytes."""
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)

    # Fiducial markers: solid black squares at the four corners.
    for cx, cy in marker_centers():
        c.setFillColorRGB(0, 0, 0)
        c.rect(cx - MARKER / 2, cy - MARKER / 2, MARKER, MARKER, fill=1, stroke=0)

    # Title
    c.setFillColorRGB(0, 0, 0)
    c.setFont("Helvetica-Bold", 11)
    c.drawCentredString(PAGE_W / 2, PAGE_H - MARGIN + 1 * mm,
                        "YOUROWNFONT  —  write each character inside its box")

    boxes = layout_cells()
    for box in boxes:
        # cell border
        c.setStrokeColorRGB(0.75, 0.75, 0.75)
        c.setLineWidth(0.5)
        c.rect(box.x, box.y, box.w, box.h, fill=0, stroke=1)
        # faint guide glyph centered in the box
        c.setFillColorRGB(0.82, 0.82, 0.82)
        size = box.h * 0.7
        c.setFont("Helvetica", size)
        c.drawCentredString(box.x + box.w / 2,
                            box.y + box.h / 2 - size * 0.35,
                            box.glyph.char)
        # small label above the box (always crisp, for the user)
        c.setFillColorRGB(0.4, 0.4, 0.4)
        c.setFont("Helvetica", 7)
        label = box.glyph.char if box.glyph.char != " " else "(space)"
        c.drawString(box.x + 1 * mm, box.y + box.h + 1 * mm, label)

    c.showPage()
    c.save()
    return buf.getvalue()
