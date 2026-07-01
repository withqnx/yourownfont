"""Character set for the handwriting template.

The user handwrites whole **syllable blocks** (not isolated jamo) plus digits
and symbols. Because we know which syllable each cell asks for, we can slice the
written syllable into its 초성/중성/종성 regions and extract each jamo *in
context* — a more natural way to write than drawing bare jamo. The extracted
jamo are then composed into all 11,172 modern syllables.

The syllable list below is a *coverage set*: every 초성 (19), 중성 (21) and
종성 (27) appears at least once, so ~67 written syllables yield every jamo.
"""
from __future__ import annotations

from dataclasses import dataclass

CHO = list("ㄱㄲㄴㄷㄸㄹㅁㅂㅃㅅㅆㅇㅈㅉㅊㅋㅌㅍㅎ")   # 19 leading
JUNG = list("ㅏㅐㅑㅒㅓㅔㅕㅖㅗㅘㅙㅚㅛㅜㅝㅞㅟㅠㅡㅢㅣ")  # 21 medial
JONG = list("ㄱㄲㄳㄴㄵㄶㄷㄹㄺㄻㄼㄽㄾㄿㅀㅁㅂㅄㅅㅆㅇㅈㅊㅋㅌㅍㅎ")  # 27 trailing

_CHO_O = 11   # index of ㅇ in CHO (used as a neutral partner for coverage)
_JUNG_A = 0   # index of ㅏ in JUNG

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

    id: str
    label: str            # what to print above the (empty) box
    role: str             # "syllable" | "direct"
    # syllable role: the jamo indices to extract from the written block
    cho: int = -1
    jung: int = -1
    jong: int = -1        # 0 = no 받침 (None slot); >0 = JONG[jong-1]
    # direct role:
    codepoint: int = -1
    name: str = ""


def _syllable_cp(cho: int, jung: int, jong: int) -> int:
    return 0xAC00 + (cho * 21 + jung) * 28 + jong


def coverage_syllables() -> list[tuple[int, int, int]]:
    """(cho, jung, jong) triples covering every jamo at least once."""
    triples: list[tuple[int, int, int]] = []
    seen: set[tuple[int, int, int]] = set()

    def add(cho: int, jung: int, jong: int) -> None:
        key = (cho, jung, jong)
        if key not in seen:
            seen.add(key)
            triples.append(key)

    for i in range(len(CHO)):          # every 초성 (with ㅏ, no 받침)
        add(i, _JUNG_A, 0)
    for j in range(len(JUNG)):         # every 중성 (with ㅇ, no 받침)
        add(_CHO_O, j, 0)
    for t in range(1, len(JONG) + 1):  # every 종성 (with 아 + 받침)
        add(_CHO_O, _JUNG_A, t)
    return triples


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
    chars: list[str] = list("0123456789")
    for cp in range(0x21, 0x7F):
        ch = chr(cp)
        if ch.isalnum():
            continue
        chars.append(ch)
    return chars


def template_cells() -> list[Cell]:
    """Every cell drawn on the template, in grid order."""
    cells: list[Cell] = []
    for cho, jung, jong in coverage_syllables():
        cp = _syllable_cp(cho, jung, jong)
        cells.append(Cell(id=f"syl:{cp:04X}", label=chr(cp), role="syllable",
                          cho=cho, jung=jung, jong=jong))
    for ch in direct_chars():
        cells.append(_direct_cell(ch))
    return cells
