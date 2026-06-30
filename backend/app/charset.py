"""Character set definitions for the handwriting template.

v1 (MVP) covers ASCII printable characters only — uppercase, lowercase,
digits and common punctuation. Hangul seed glyphs are added in v2 once the
AI generation model is wired in.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Glyph:
    """One target glyph the user is asked to handwrite."""

    char: str          # the character to write, e.g. "A"
    codepoint: int     # unicode codepoint, e.g. 0x41
    name: str          # PostScript glyph name, e.g. "A"


# PostScript glyph names for punctuation that cannot be the literal char.
_PUNCT_NAMES = {
    " ": "space",
    "!": "exclam",
    '"': "quotedbl",
    "#": "numbersign",
    "$": "dollar",
    "%": "percent",
    "&": "ampersand",
    "'": "quotesingle",
    "(": "parenleft",
    ")": "parenright",
    "*": "asterisk",
    "+": "plus",
    ",": "comma",
    "-": "hyphen",
    ".": "period",
    "/": "slash",
    ":": "colon",
    ";": "semicolon",
    "<": "less",
    "=": "equal",
    ">": "greater",
    "?": "question",
    "@": "at",
    "[": "bracketleft",
    "\\": "backslash",
    "]": "bracketright",
    "^": "asciicircum",
    "_": "underscore",
    "`": "grave",
    "{": "braceleft",
    "|": "bar",
    "}": "braceright",
    "~": "asciitilde",
}


def _glyph_name(ch: str) -> str:
    if ch.isalnum() and ch.isascii():
        # digits get spelled-out names per Adobe glyph list convention
        digit_names = {
            "0": "zero", "1": "one", "2": "two", "3": "three", "4": "four",
            "5": "five", "6": "six", "7": "seven", "8": "eight", "9": "nine",
        }
        return digit_names.get(ch, ch)
    return _PUNCT_NAMES.get(ch, f"uni{ord(ch):04X}")


def latin_charset() -> list[Glyph]:
    """ASCII printable glyphs the user handwrites in the v1 template.

    Space (0x20) is excluded from the writing grid — it carries no ink — but it
    is still added to the font with a sensible advance width during build.
    """
    glyphs: list[Glyph] = []
    for cp in range(0x21, 0x7F):  # '!' .. '~'
        ch = chr(cp)
        glyphs.append(Glyph(char=ch, codepoint=cp, name=_glyph_name(ch)))
    return glyphs


def template_charset() -> list[Glyph]:
    """The full set of glyphs drawn on the current template (v1 = Latin)."""
    return latin_charset()
