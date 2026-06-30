"""End-to-end synthetic test of the scan -> font pipeline.

We synthesize a *canonical* page image (the same space scans are warped into):
draw the four fiducial markers and render each target character into its cell
with a real system font, standing in for handwriting. Then we run the full
pipeline and assert the resulting TTF carries the expected glyphs with sane
geometry.
"""
from __future__ import annotations

import os
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

from app import scan  # noqa: E402
from app.charset import template_charset  # noqa: E402
from app.pipeline import build_from_scan  # noqa: E402
from app.scan import SCALE  # noqa: E402
from app.template import layout_cells, marker_centers  # noqa: E402

HANDWRITING_FONT = "/System/Library/Fonts/Supplemental/Arial.ttf"


def _pt_to_px(x_pt, y_pt):
    return x_pt * SCALE, (scan.PAGE_H - y_pt) * SCALE


def synthesize_page() -> bytes:
    """Render a filled canonical page as PNG bytes."""
    img = Image.new("RGB", (scan.CANON_W, scan.CANON_H), "white")
    d = ImageDraw.Draw(img)

    half = (8 * 200 / 72) / 2  # MARKER/2 in px (MARKER = 8mm)
    for cx, cy in marker_centers():
        px, py = _pt_to_px(cx, cy)
        d.rectangle([px - half, py - half, px + half, py + half], fill="black")

    for box in layout_cells():
        ch = box.glyph.char
        if ch == " ":
            continue
        # cell rect in pixels
        x0, ytop = _pt_to_px(box.x, box.y + box.h)
        w_px = box.w * SCALE
        h_px = box.h * SCALE
        size = int(h_px * 0.6)
        font = ImageFont.truetype(HANDWRITING_FONT, size)
        # Render on a shared baseline (like real writing) so descenders fall
        # below it: anchor="ms" = horizontally centered, vertically on baseline.
        cx = x0 + w_px / 2
        baseline_y = ytop + h_px * 0.78
        d.text((cx, baseline_y), ch, fill="black", font=font, anchor="ms")

    import io
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def test_pipeline_end_to_end(tmp_path=None):
    page = synthesize_page()
    result = build_from_scan(page, family="TestFont")

    expected_fillable = sum(1 for g in template_charset() if g.char != " ")
    # Allow a few glyphs to be missed/blank at the segmentation edges.
    assert result.filled_cells >= expected_fillable * 0.9, (
        f"only {result.filled_cells}/{expected_fillable} glyphs captured"
    )

    # Load the produced font and verify glyph coverage + metrics.
    from fontTools.ttLib import TTFont
    import io
    font = TTFont(io.BytesIO(result.font_bytes))
    cmap = font.getBestCmap()

    for cp in (ord("A"), ord("a"), ord("g"), ord("1"), ord("?")):
        assert cp in cmap, f"codepoint {cp:#x} missing from cmap"

    glyf = font["glyf"]
    # 'A' should have ink and live above the baseline.
    a = glyf[cmap[ord("A")]]
    assert a.numberOfContours > 0
    assert a.yMax > 300, f"'A' too short: yMax={a.yMax}"
    # 'g' is a descender: should dip below the baseline.
    g = glyf[cmap[ord("g")]]
    assert g.yMin < 50, f"'g' should descend, yMin={g.yMin}"

    print(f"OK: {result.filled_cells}/{expected_fillable} glyphs, "
          f"{len(cmap)} cmap entries, font {len(result.font_bytes)} bytes")
    return result.font_bytes


if __name__ == "__main__":
    data = test_pipeline_end_to_end()
    out = os.path.join(os.path.dirname(__file__), "..", "build", "test_output.ttf")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "wb") as f:
        f.write(data)
    print("wrote", out)
