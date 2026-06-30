"""Glue: a scanned template image in, a finished font out."""
from __future__ import annotations

from dataclasses import dataclass

from .fontbuild import build_font
from .scan import decode_image, extract_glyphs
from .vectorize import VectorGlyph, vectorize


@dataclass
class BuildResult:
    font_bytes: bytes
    total_cells: int
    filled_cells: int
    family: str
    fmt: str


def build_from_scan(image_bytes: bytes, family: str = "YourOwnFont",
                    fmt: str = "ttf") -> BuildResult:
    image = decode_image(image_bytes)
    extracted = extract_glyphs(image)

    vglyphs: list[VectorGlyph] = [vectorize(e) for e in extracted]
    # Only carry glyphs the user actually wrote (blanks get no outline).
    drawn = [vg for vg in vglyphs if not vg.is_blank]

    font_bytes = build_font(drawn, family=family, fmt=fmt)
    return BuildResult(
        font_bytes=font_bytes,
        total_cells=len(extracted),
        filled_cells=len(drawn),
        family=family,
        fmt=fmt,
    )
