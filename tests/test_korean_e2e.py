"""End-to-end synthetic test of the jamo-composition pipeline.

Synthesize a canonical page: draw the four fiducials and render each cell's
guide character (jamo / digit / symbol) with a Korean system font, standing in
for handwriting. Run the pipeline and assert that composed syllables exist with
sane geometry, then render a sample sentence.
"""
from __future__ import annotations

import io
import os
import sys

from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

from app import scan  # noqa: E402
from app.pipeline import build_from_scan  # noqa: E402
from app.scan import SCALE  # noqa: E402
from app.template import layout_cells, marker_centers  # noqa: E402

KR_FONT = "/System/Library/Fonts/Supplemental/AppleGothic.ttf"


def _pt_to_px(x_pt, y_pt):
    return x_pt * SCALE, (scan.PAGE_H - y_pt) * SCALE


def synthesize_page() -> bytes:
    img = Image.new("RGB", (scan.CANON_W, scan.CANON_H), "white")
    d = ImageDraw.Draw(img)

    half = (8 * 200 / 72) / 2
    for cx, cy in marker_centers():
        px, py = _pt_to_px(cx, cy)
        d.rectangle([px - half, py - half, px + half, py + half], fill="black")

    for box in layout_cells():
        ch = box.cell.label
        x0, ytop = _pt_to_px(box.x, box.y + box.h)
        w_px, h_px = box.w * SCALE, box.h * SCALE
        size = int(h_px * 0.6)
        font = ImageFont.truetype(KR_FONT, size)
        cx = x0 + w_px / 2
        if box.cell.role == "direct":
            # baseline-anchored so descenders (comma etc.) fall naturally
            d.text((cx, ytop + h_px * 0.78), ch, fill="black", font=font, anchor="ms")
        else:
            # jamo: center in cell (composition re-fits by bounding box anyway)
            d.text((cx, ytop + h_px * 0.5), ch, fill="black", font=font, anchor="mm")

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def test_pipeline_end_to_end():
    page = synthesize_page()
    result = build_from_scan(page, family="TestKR")
    print(f"cells filled {result.filled_cells}/{result.total_cells}, "
          f"syllables {result.syllables}, font {len(result.font_bytes)} bytes")

    assert result.syllables > 11000, f"expected ~11172 syllables, got {result.syllables}"

    from fontTools.ttLib import TTFont
    font = TTFont(io.BytesIO(result.font_bytes))
    cmap = font.getBestCmap()
    glyf = font["glyf"]

    # 가(no jong, RIGHT), 곡(BOTTOM+jong), 값(RIGHT+double jong), 한(RIGHT+jong), 뷁(WRAP+jong)
    for ch in ("가", "고", "곡", "값", "한", "뷁", "1", "?"):
        cp = ord(ch)
        assert cp in cmap, f"'{ch}' (U+{cp:04X}) missing from cmap"

    ga = glyf[cmap[ord("가")]]
    assert ga.numberOfContours > 0, "'가' has no outline"
    # a syllable with 받침 should use more vertical space than one without
    assert glyf[cmap[ord("한")]].numberOfContours >= glyf[cmap[ord("하")]].numberOfContours

    return result.font_bytes


if __name__ == "__main__":
    data = test_pipeline_end_to_end()
    os.makedirs("build", exist_ok=True)
    with open("build/korean_output.ttf", "wb") as f:
        f.write(data)

    # render a sample sentence
    fnt = ImageFont.truetype("build/korean_output.ttf", 60)
    img = Image.new("RGB", (900, 260), "white")
    d = ImageDraw.Draw(img)
    d.text((20, 20), "한글 손글씨 폰트", fill="black", font=fnt)
    d.text((20, 100), "가나다라 뷁값핡", fill="black", font=fnt)
    d.text((20, 180), "숫자 0123 !?.", fill="black", font=fnt)
    img.save("build/korean_sample.png")
    print("wrote build/korean_output.ttf and build/korean_sample.png")
