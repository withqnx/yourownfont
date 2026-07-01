"""Character set for the handwriting template.

Korean-first design. The user handwrites a small set of **cells**:

  * jamo components — 19 초성 (leading), 21 중성 (medial), 27 종성 (trailing).
    These are *composed* by ``hangul.py`` into all 11,172 modern syllables, so
    the user writes each jamo only once instead of writing every syllable.
  * digits and punctuation — written once and mapped directly (no composition).

Latin letters are intentionally excluded per project scope (Korean + digits +
symbols only).
"""
from __future__ import annotations

from dataclasses import dataclass

# 19 leading consonants (초성), in Unicode composition order.
CHO = list("ㄱㄲㄴㄷㄸㄹㅁㅂㅃㅅㅆㅇㅈㅉㅊㅋㅌㅍㅎ")
# 21 medial vowels (중성), in Unicode composition order.
JUNG = list("ㅏㅐㅑㅒㅓㅔㅕㅖㅗㅘㅙㅚㅛㅜㅝㅞㅟㅠㅡㅢㅣ")
# 27 trailing consonants (종성), in Unicode order (index 0 here = jong value 1).
JONG = list("ㄱㄲㄳㄴㄵㄶㄷㄹㄺㄻㄼㄽㄾㄿㅀㅁㅂㅄㅅㅆㅇㅈㅊㅋㅌㅍㅎ")

_PUNCT_NAMES = {
    "!": "exclam", '"': "quotedbl", "#": "numbersign", "$": "dollar",
    "%": "percent", "&": "ampersand", "'": "quotesingle", "(": "parenleft",
    ")": "parenright", "*": "asterisk", "+": "plus", ",": "comma",
    "-": "hyphen", ".": "period", "/": "slash", ":": "colon", ";": "semicolon",
    "<": "less", "=": "equal", ">": "greater", "?": "question", "@": "at",
    "[": "bracketleft", "\\": "backslash", "]": "bracketright",
    "^": "asciicircum", "_": "underscore", "`": "grave", "{": "braceleft",
    "|": "bar", "}": "braceright", "~": "asciitilde",
}
_DIGIT_NAMES = {
    "0": "zero", "1": "one", "2": "two", "3": "three", "4": "four",
    "5": "five", "6": "six", "7": "seven", "8": "eight", "9": "nine",
}


@dataclass(frozen=True)
class Cell:
    """One thing the user handwrites in the template grid."""

    id: str          # unique key, e.g. "cho:0", "jung:8", "jong:3", "dir:0x35"
    label: str       # what to print in the cell as a guide, e.g. "ㄱ", "5", "."
    role: str        # "cho" | "jung" | "jong" | "direct"
    index: int = -1  # jamo index (cho/jung/jong roles)
    codepoint: int = -1  # unicode codepoint (direct role)
    name: str = ""       # PostScript glyph name (direct role)


def _direct_cell(ch: str) -> Cell:
    if ch in _DIGIT_NAMES:
        name = _DIGIT_NAMES[ch]
    elif ch in _PUNCT_NAMES:
        name = _PUNCT_NAMES[ch]
    else:
        name = f"uni{ord(ch):04X}"
    return Cell(id=f"dir:{ord(ch):#x}", label=ch, role="direct",
                codepoint=ord(ch), name=name)


def direct_chars() -> list[str]:
    """Digits + ASCII punctuation/symbols (letters excluded)."""
    chars: list[str] = list("0123456789")
    for cp in range(0x21, 0x7F):
        ch = chr(cp)
        if ch.isalnum():        # skip digits (already added) and any letters
            continue
        chars.append(ch)
    return chars


def template_cells() -> list[Cell]:
    """Every cell drawn on the template, in grid order."""
    cells: list[Cell] = []
    for i, ch in enumerate(CHO):
        cells.append(Cell(id=f"cho:{i}", label=ch, role="cho", index=i))
    for i, ch in enumerate(JUNG):
        cells.append(Cell(id=f"jung:{i}", label=ch, role="jung", index=i))
    for i, ch in enumerate(JONG):
        cells.append(Cell(id=f"jong:{i}", label=ch, role="jong", index=i))
    for ch in direct_chars():
        cells.append(_direct_cell(ch))
    return cells
