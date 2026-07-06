"""Character set for the handwriting template.

Instead of a mechanical grid of syllables, the user writes a small set of **real,
fun words** chosen so that every 초성 appears in both a vertical- and a
horizontal-vowel context and every 중성/종성 appears at least once. From the
syllables of these words we extract each jamo *in context*; the rest of the
11,172 syllables are produced by math (composition + the 받침 compression ratio
from the Hunmin-geometry study), so the boring "받침 vowel" set is never written.

The word list was chosen by greedy set-cover to minimize how much is written
while staying meaningful; ``verify_coverage`` asserts it still covers everything.
"""
from __future__ import annotations

from dataclasses import dataclass

CHO = list("ㄱㄲㄴㄷㄸㄹㅁㅂㅃㅅㅆㅇㅈㅉㅊㅋㅌㅍㅎ")   # 19 leading
JUNG = list("ㅏㅐㅑㅒㅓㅔㅕㅖㅗㅘㅙㅚㅛㅜㅝㅞㅟㅠㅡㅢㅣ")  # 21 medial
JONG = list("ㄱㄲㄳㄴㄵㄶㄷㄹㄺㄻㄼㄽㄾㄿㅀㅁㅂㅄㅅㅆㅇㅈㅊㅋㅌㅍㅎ")  # 27 trailing

_VERT = set("ㅏㅐㅑㅒㅓㅔㅕㅖㅣ")  # vertical vowels -> 초성 belt "V"; others -> "H"

# Minimal fun word set covering every jamo in every needed context.
WORDS = [
    "달빛", "꿈", "행복", "흙", "넋", "펭귄", "뼈", "뭐", "삶", "값", "숲", "집",
    "얘", "참외", "초콜릿", "떡", "짬뽕", "포도", "귤", "토끼", "똥", "희망", "곬",
    "늘", "밭", "낮", "키읔", "밖", "곧", "구름", "새싹", "사과", "쪽지", "돼지",
    "궤짝", "여덟", "앉기", "핥기", "읊기", "용기", "쓰레기", "많음", "옳음", "있음",
    "히읗", "티읕", "예술", "고양이", "다람쥐",
]

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
    label: str            # printed above the (empty) box
    role: str             # "syllable" | "direct"
    word: str = ""        # source word (syllable role) for grouping/labels
    cho: int = -1
    jung: int = -1
    jong: int = -1        # 0 = no 받침
    codepoint: int = -1
    name: str = ""


def _decompose(ch: str) -> tuple[int, int, int] | None:
    c = ord(ch) - 0xAC00
    if c < 0 or c > 11171:
        return None
    return c // (21 * 28), (c % (21 * 28)) // 28, c % 28


def coverage_syllables() -> list[tuple[str, str, int, int, int]]:
    """Distinct (syllable, source_word, cho, jung, jong) from WORDS, in order."""
    out: list[tuple[str, str, int, int, int]] = []
    seen: set[str] = set()
    for word in WORDS:
        for ch in word:
            d = _decompose(ch)
            if d is None or ch in seen:
                continue
            seen.add(ch)
            out.append((ch, word, *d))
    return out


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
    for ch, word, cho, jung, jong in coverage_syllables():
        cells.append(Cell(id=f"syl:{ord(ch):04X}", label=ch, role="syllable",
                          word=word, cho=cho, jung=jung, jong=jong))
    for ch in direct_chars():
        cells.append(_direct_cell(ch))
    return cells


def belt_of(jung: int) -> str:
    return "V" if JUNG[jung] in _VERT else "H"


def verify_coverage() -> set:
    """Return the set of jamo/context requirements NOT covered by WORDS."""
    need = set()
    for i in range(len(CHO)):
        need |= {("C", i, "V"), ("C", i, "H")}
    for j in range(len(JUNG)):
        need.add(("V", j))
    for t in range(len(JONG)):
        need.add(("T", t))
    for _, _, cho, jung, jong in coverage_syllables():
        need.discard(("C", cho, belt_of(jung)))
        need.discard(("V", jung))
        if jong > 0:
            need.discard(("T", jong - 1))
    return need
