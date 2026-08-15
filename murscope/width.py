"""Terminal cells, not characters (DP86).

A column is a promise about where the next column starts, and `len()`
does not keep it. `%-38s` pads a string to 38 *characters*; a terminal
draws a CJK ideograph in two cells and a French `e` with an acute accent
in one, so a table padded by character count starts its next column
somewhere different on every row. Measured on the summary screen before
this module existed, on four `zh` rows: the ledger column sat at a single
*character* offset of 70 and at three *cell* offsets - 75, 76 and 80 -
and the rows were 81, 82 and 86 cells wide. The same four rows through
this module: one cell offset, 70, from three character offsets - 60, 64,
65 - and every row exactly 76 cells. The character offsets disagreeing is
what makes the cell offsets agreeing a measurement rather than luck.

Three width classes matter here and all three are exercised by the
fixtures that check this file:

* **ASCII** - one character, one cell, and `len()` happens to be right.
  This is the case a synthetic test would use, and it is the one case
  that proves nothing (DP87).
* **Latin with accents** - `\\u00e9` is one cell and *two* bytes in
  UTF-8. Any implementation that reached for `len(text.encode())` is
  wrong here and right on the other two, which is why `fr` is in the
  fixture and not only `zh`.
* **East Asian wide** - two cells, one character.

The classification is `unicodedata.east_asian_width`, which is the
Unicode data table the terminals themselves follow: `W` (wide) and `F`
(fullwidth) occupy two cells, everything else occupies one. Combining
marks occupy none - a decomposed `e` plus U+0301 is one cell on screen,
not two - so `Mn` and `Me` are counted as zero. `A` (ambiguous) is
counted as one, which is the choice every terminal on a Latin locale
makes; the alternative is a per-terminal setting nobody exports.

Pure stdlib, no state, no I/O. This is a core module and imports nothing
from murscope, so it is safe to call from anywhere that prints.
"""
from __future__ import annotations

import unicodedata

ELLIPSIS = "\u2026"
WIDE = ("W", "F")
ZERO_WIDTH_CATEGORIES = ("Mn", "Me")


def cells(text):
    """How many terminal cells `text` occupies."""
    total = 0
    for char in text:
        if unicodedata.category(char) in ZERO_WIDTH_CATEGORIES:
            continue
        total += 2 if unicodedata.east_asian_width(char) in WIDE else 1
    return total


def fit(text, width):
    """The longest prefix of `text` that occupies at most `width` cells.

    Stops one cell short rather than one cell over when the character on
    the boundary is wide and the budget is odd. A column that overruns by
    one cell is the defect this module exists to remove, so the rounding
    goes the other way.
    """
    if width <= 0:
        return ""
    total = 0
    for index, char in enumerate(text):
        if unicodedata.category(char) in ZERO_WIDTH_CATEGORIES:
            continue
        total += 2 if unicodedata.east_asian_width(char) in WIDE else 1
        if total > width:
            return text[:index]
    return text


def pad(text, width):
    """`text` followed by enough spaces to occupy `width` cells.

    Returns the text unchanged when it is already at or past the width -
    the same shape as `%-*s`, which also never truncates. A caller that
    needs the column to hold clips first.
    """
    return text + " " * max(0, width - cells(text))


def clip(text, width):
    """Trim to `width` terminal cells without cutting a word in half.

    "quiet for 41 days, nothing outstan" is worse than saying less: a
    sentence chopped mid-word reads as a rendering bug, and the screen
    this is written for is the first thing a stranger reads about their
    own work.

    The word-boundary rule is the one this replaced, restated in cells: a
    break at the last space is taken only when it leaves at least half
    the budget, so a single long word is cut rather than reduced to an
    ellipsis on its own.
    """
    if cells(text) <= width:
        return text
    if width <= 0:
        return ""
    cut = fit(text, width - cells(ELLIPSIS))
    space = cut.rfind(" ")
    if space >= 0 and cells(cut[:space]) >= width // 2:
        cut = cut[:space]
    return cut.rstrip(" ,;:") + ELLIPSIS


def column(text, width):
    """One table cell: clipped to the width, then padded out to it.

    The pairing is the point. Clipping alone leaves a short string short
    and the next column ragged; padding alone lets a long string push the
    next column right. A table is aligned when every cell is exactly this
    wide, and one call is harder to get half right than two.
    """
    return pad(clip(text, width), width)
