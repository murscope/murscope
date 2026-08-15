"""Rule 29: the terminal table is measured in cells, not characters.

A column is a promise about where the next column starts. `%-38s` pads to
38 *characters*, and a terminal draws a CJK ideograph in two cells, so a
`zh` table padded that way begins its next column somewhere different on
every row. Measured before the fix, on four `zh` rows of the summary
screen: one character offset of 70, three cell offsets - 75, 76, 80 - and
rows 81, 82 and 86 cells wide, on rows meant to share one offset (DP86).
Nothing on that screen was untrue - which is why it was
filed rather than blocking a gate - and it was crooked for two milestones.

This check is judged on **rendered text**, not on the shape of the code
that renders it. `murscope.wizard._header` and `._row` are called for
real, once per locale this build ships, and the output is measured the
way a terminal draws it.

Four things are held:

  1. **Every row of the table puts the ledger column at the same cell
     offset**, and every row is the same number of cells wide. Per locale,
     because the defect is a property of the strings the locale supplies.
  2. **`murscope.width` classifies all three width classes**, and the
     three are not interchangeable. ASCII is one character, one cell and
     one byte; a French accented letter is one character, one cell and
     *two* UTF-8 bytes; a CJK ideograph is one character, two cells and
     three bytes. An implementation that counted bytes would be right on
     ASCII and wrong on the other two; one that counted characters is
     right on the first two and wrong on the third. Only a table holding
     all three tells those apart, which is why `fr` exists here and not
     only `zh`.
  3. **A clip never overruns its budget**, including where a wide
     character straddles the boundary and where the budget is odd - the
     one arithmetic case that separates "count in cells" from "count in
     cells and then round the wrong way".
  4. **The fixture actually reaches the code this is written for**
     (DP87). The floors are asserted before any verdict: the rendering
     must contain characters that are wide, characters that are accented
     and characters that are plain, at least one name must be long enough
     to be clipped, and at least one row's sub-text must be long enough
     to wrap. A table of ASCII cases would satisfy every assertion above
     while never once exercising the difference this rule is about, and
     would report a green result for a measurement that did not happen.

What this check does **not** claim: that no future column anywhere in the
product will be padded by character count. Finding that statically means
deciding which `%-*s` carries a rendered value and which carries an
identifier - `expand()` pads a tier name to eight and is right to - and
DP67 already priced that class of scanner at negative. So the guard is
behavioural and anchored to the one table that renders locale strings; a
second such table is added here by name, the way Rule 8's heading was.

Fails when: two rows of the rendered table start the ledger column at
different cell offsets; a locale's rows differ in width; `width.cells`
disagrees with the three width classes; a clip returns more cells than it
was given; or the fixture stops containing the characters that make the
measurement mean anything.
"""
from __future__ import annotations

import sys
import unicodedata
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent

# The column the alignment is measured against. It is the last field of a
# row and is a fixed string in this fixture, so its position is readable
# out of the line without re-deriving the layout the code under test
# produced - a check that recomputed the offset the same way the renderer
# does would agree with it whatever either of them did.
SOURCE = "- none"

# The three width classes, each with what it is not. `bytes` is here so
# that a byte-counting implementation is named by the case that catches
# it rather than merely failing somewhere.
#
# label, text, characters, cells, UTF-8 bytes
WIDTH_CLASSES = (
    ("ASCII", "abc", 3, 3, 3),
    # e-acute, a-grave, c-cedilla: the French case. One cell each, two
    # bytes each.
    ("Latin with accents", "\u00e9\u00e0\u00e7", 3, 3, 6),
    # "project" in Chinese, and one more: two cells each, three bytes each.
    ("East Asian wide", "\u9879\u76ee\u53f0", 3, 6, 9),
    # A decomposed e-acute. Two characters, one cell - a combining mark
    # draws on top of the letter before it rather than beside it.
    ("combining mark", "e\u0301", 2, 1, 3),
)

# Clip cases that end on a wide character, so the budget cannot be spent
# exactly. `width` must stop short rather than over: a column that
# overruns by one cell is the defect, and rounding the convenient way
# would reintroduce it for every odd budget.
#
# text, budget in cells
CLIP_CASES = (
    ("\u9879\u76ee\u53f0\u5e10\u672c", 5),
    ("\u9879\u76ee\u53f0\u5e10\u672c", 6),
    ("\u9879\u76ee\u53f0\u5e10\u672c", 7),
    ("\u00e9tat actuel de ce projet, en un mot", 12),
    ("stopped halfway and never picked up again", 20),
    ("unbrokenwordwithnospacesatallanywhere", 15),
    ("abc", 1),
    ("", 4),
)

# The rows the table is built from. Each name is a width class, so the
# name column is exercised by all three rather than by whichever one the
# locale happened to supply.
#
# name, signal spec
ROWS = (
    # Plain ASCII, and short.
    ("orchestrator", dict(uncommitted=3)),
    # French: accented, and long enough that the name column has to clip.
    ("r\u00e9f\u00e9rentiel-des-donn\u00e9es-partag\u00e9es", dict(unpushed=2, uncommitted=1)),
    # Wide: the case that makes this rule exist. Holding all four things,
    # so the sub-text is long enough to wrap.
    ("\u8bfe\u7a0b\u8bbe\u8ba1\u5e73\u53f0", dict(uncommitted=4, unpushed=2, stash=1, wip=True)),
    # Wide and long, so a wide name meets the clip as well as the pad.
    ("\u8bfe\u7a0b\u8bbe\u8ba1\u5e73\u53f0\u7684\u4e0b\u4e00\u4ee3\u91cd\u5199\u7248\u672c", dict()),
)


def _cells(text):
    """This check's own cell count, written here rather than imported.

    The thing under test is a width function. Measuring its output with
    itself would make every assertion below a tautology - the shape this
    repository has found more than once, most recently a check satisfied
    by its own docstring (DP123).
    """
    total = 0
    for char in text:
        if unicodedata.category(char) in ("Mn", "Me"):
            continue
        total += 2 if unicodedata.east_asian_width(char) in ("W", "F") else 1
    return total


class _Entry:
    """The minimum a roster entry has to be for `state.resolve`."""

    def __init__(self, identifier):
        self.id = identifier
        self.note = None
        self.declaration = None
        self.ledgers = []


def _signals(uncommitted=0, unpushed=0, stash=0, wip=False):
    return {
        "uncommitted": {"quality": "ok", "signal": "uncommitted",
                        "files": uncommitted},
        "unpushed": {"quality": "ok", "signal": "unpushed",
                     "commits": unpushed},
        "stash": {"quality": "ok", "signal": "stash", "entries": stash,
                  "oldest_age_days": 1.0 if stash else None},
        "last_commit": {"quality": "ok", "signal": "last_commit", "wip": wip,
                        "subject": "wip: half of it" if wip else "a commit"},
        "ledger": {"quality": "ok", "read": ["STATUS.md"], "hits": 1},
    }


def render_table(locale, i18n, state, wizard):
    """(lines, anchors, findings) - the summary screen's table in one locale.

    `anchors` is the string that ends each line's last column: the
    translated ledger heading on the header, and this fixture's fixed
    source string on every row. The last column is the one whose starting
    offset is the whole question, and the header has to be in that
    comparison - it was not, and reverting `_header` alone to `%-*s` left
    this check green while the heading sat over the wrong column.
    """
    catalog, problems = i18n.load(locale)
    findings = ["locale %s: %s" % (locale, line) for line in problems]
    lines = [wizard._header(catalog)]
    anchors = [i18n.translate(catalog, "col.ledger")]
    for index, (name, spec) in enumerate(ROWS, start=1):
        signals = _signals(**spec)
        record = {"id": name, "name": name, "recency_days": 1.0,
                  "signals": signals}
        resolved = state.resolve(record, _Entry(name), catalog)
        row = wizard._row(index, dict(record, state=resolved), None)
        for number, line in enumerate(row.split("\n")):
            lines.append(line)
            anchors.append(SOURCE if number == 0 else None)
    return lines, anchors, findings


def floors(locale, lines, width):
    """What has to be true of one rendering before its verdict counts (DP87).

    Per locale, and that is the correction rather than the detail. Pooled
    across every locale these same five questions were all answered by
    `zh` and `fr` supplying between them every character class the fixture
    was supposed to supply - so taking the wide name out of `ROWS`
    entirely left this check green, with the `en` table it had just
    measured containing not one wide character. A floor that another
    locale can satisfy on this locale's behalf is not a floor.
    """
    text = "\n".join(lines)
    found = []
    if not any(unicodedata.east_asian_width(c) in ("W", "F") for c in text):
        found.append("holds no wide character, so every assertion about it "
                     "would be equally true of a renderer that counted "
                     "characters. This locale's table measures nothing.")
    # A *letter*, not merely a non-ASCII character. Written as "non-ASCII
    # and not wide" this was satisfied by the ellipsis the clip appends -
    # so taking every accent out of the fixture left the floor standing on
    # a character the renderer had put there itself.
    if not any(ord(c) > 127 and unicodedata.category(c) in ("Ll", "Lu")
               and unicodedata.east_asian_width(c) not in ("W", "F")
               for c in text):
        found.append("holds no accented Latin letter, so a renderer counting "
                     "UTF-8 bytes would pass here.")
    if not any(ord(c) < 128 and c.isalpha() for c in text):
        found.append("holds no ASCII letter, so the narrow case is untested.")
    if width.ELLIPSIS not in text:
        found.append("no row was clipped, so the clip half of the fix is "
                     "unexercised - only the pad half.")
    if not any(line.strip().startswith("\u00b7") for line in lines):
        found.append("no row produced a sub-text line, so the wrap budget "
                     "and the sub-text indent are both unexercised.")
    return ["locale %s: %s" % (locale, line) for line in found]


def bundle(lines, anchors, state_width):
    """A rendered table encoded as the bytes `detect` reads.

    Tab-separated, one line per line: the anchor that ends the line, then
    the line itself. An empty anchor is a sub-text line, which has no last
    column of its own and is measured against the row above. The first
    record carries the layout constant the sub-text indent is derived
    from.

    The encoding exists so that `detect` can be a pure function of text -
    Rule 1 requires one, and requires it to fire on a fixture of violating
    shapes rather than on a rendering nobody can hand it. `main()` renders
    the real screen, encodes it with this, and reads the answer out of the
    same detector the fixture exercises; there is no second implementation
    to drift.
    """
    records = ["#state_width\t%d" % state_width]
    for line, anchor in zip(lines, anchors):
        records.append("%s\t%s" % (anchor or "", line))
    return "\n".join(records).encode("utf-8")


def detect(payload):
    """Findings for a rendered table, encoded by `bundle`."""
    lines, anchors = [], []
    state_width = None
    for record in payload.decode("utf-8", errors="replace").split("\n"):
        if not record:
            continue
        anchor, _tab, line = record.partition("\t")
        if anchor == "#state_width":
            try:
                state_width = int(line)
            except ValueError:
                return ["the state column's width is %r rather than a number, "
                        "so the sub-text indent has nothing to be measured "
                        "against." % line]
            continue
        lines.append(line)
        anchors.append(anchor or None)
    if state_width is None:
        return ["no #state_width record; this payload does not say how wide "
                "the state column is and half the assertions need it."]
    return alignment(lines, anchors, state_width)


def alignment(lines, anchors, state_width):
    """Findings for one rendered table: a column that starts in two places.

    Two columns are measured, not one. The last column is anchored on the
    string that ends the line. The *sub-text* indent is anchored on the
    state column of the row it hangs under, which is derived from the last
    column's offset and `wizard.STATE_WIDTH` - a declared layout constant
    rather than the arithmetic under test. Without that second half,
    putting `len(head)` back left this check green while a `zh` row's
    sub-text sat eight cells left of the sentence it belongs under.
    """
    offsets = {}
    widths = {}
    head_cells = None
    indents = {}
    found = []
    for line, anchor in zip(lines, anchors):
        if anchor is None:
            # A sub-text line: measured against the row it follows.
            leading = len(line) - len(line.lstrip(" "))
            indents.setdefault(_cells(line[:leading]), []).append(line)
            continue
        if anchor not in line:
            found.append("a line was rendered without its last column (%r "
                         "does not appear in %r), so its offset could not be "
                         "measured at all." % (anchor, line))
            continue
        offsets.setdefault(_cells(line[:line.rindex(anchor)]), []).append(line)
        # Grouped by the anchor rather than pooled. The heading's last
        # column is a translated word and the rows' is this fixture's
        # source string; those are different lengths on purpose, and a
        # pooled comparison would call the table crooked for it.
        widths.setdefault(anchor, {}).setdefault(_cells(line), []).append(line)

    compared = sum(len(group) for group in offsets.values())
    if compared < 2:
        found.append("%d line(s) carried a last column, so nothing was "
                     "compared against anything." % compared)
    if len(offsets) > 1:
        found.append(
            "the ledger column starts at %d different cell offsets across the "
            "table (%s); a column that starts in more than one place is not a "
            "column."
            % (len(offsets), ", ".join(str(n) for n in sorted(offsets))))
    elif offsets:
        head_cells = sorted(offsets)[0] - state_width - 1
    for anchor in sorted(widths, key=str):
        group = widths[anchor]
        if len(group) > 1:
            found.append(
                "the %d line(s) ending in %r are %d different widths in cells "
                "(%s); they are padded to one width in characters, which is "
                "the defect rather than the fix."
                % (sum(len(v) for v in group.values()), anchor, len(group),
                   ", ".join(str(n) for n in sorted(group))))
    if head_cells is not None and len(indents) > 1:
        found.append(
            "the sub-text is indented to %d different cell offsets (%s); it "
            "hangs under the state column and there is only one of those."
            % (len(indents), ", ".join(str(n) for n in sorted(indents))))
    elif head_cells is not None and indents:
        indent = sorted(indents)[0]
        if indent != head_cells:
            found.append(
                "the sub-text is indented %d cell(s) and the state column it "
                "hangs under starts at %d; an indent counted in characters "
                "lands left of its own column the moment a name is wide."
                % (indent, head_cells))
    return found


def classes(width):
    """Findings for the width function against the three width classes."""
    found = []
    for label, text, chars, cells, encoded in WIDTH_CLASSES:
        if len(text) != chars or len(text.encode("utf-8")) != encoded:
            found.append("%s: the case itself is wrong - %d character(s) and "
                         "%d byte(s), not %d and %d."
                         % (label, len(text), len(text.encode("utf-8")),
                            chars, encoded))
            continue
        measured = width.cells(text)
        if measured != cells:
            found.append(
                "%s: width.cells(%r) is %d and a terminal draws it in %d. "
                "This string is %d character(s) and %d UTF-8 byte(s), so the "
                "answer matches neither by accident."
                % (label, text, measured, cells, chars, encoded))
    return found


def clips(width):
    """Findings for the clip: a result wider than the budget it was given."""
    found = []
    reached_wide_boundary = False
    for text, budget in CLIP_CASES:
        result = width.clip(text, budget)
        if _cells(result) > budget:
            found.append(
                "width.clip(%r, %d) returned %r, which is %d cell(s) - one "
                "column over is what a crooked table is made of."
                % (text, budget, result, _cells(result)))
        if _cells(text) > budget and any(
                unicodedata.east_asian_width(c) in ("W", "F") for c in text):
            reached_wide_boundary = True
    if not reached_wide_boundary:
        found.append("no clip case both overflowed its budget and held a wide "
                     "character, so the boundary arithmetic was never "
                     "exercised (DP87).")
    return found


def main():
    sys.path.insert(0, str(REPO_ROOT))
    try:
        from murscope import i18n, state, width, wizard
    except ImportError as exc:
        print("FAILED: murscope could not be imported (%s); this check "
              "renders the real screen and cannot fall back to reading it."
              % exc)
        return 1

    bad = 0
    locales = i18n.available()
    if len(locales) < 2:
        print("FAILED: %d locale(s) ship; the alignment this rule is about is "
              "a property of the strings a locale supplies, and one locale "
              "compares nothing." % len(locales))
        return 1

    for finding in classes(width):
        print("murscope/width.py: %s" % finding)
        bad += 1
    for finding in clips(width):
        print("murscope/width.py: %s" % finding)
        bad += 1

    rendered = {}
    for locale in locales:
        lines, anchors, findings = render_table(locale, i18n, state, wizard)
        rendered[locale] = (lines, anchors)
        for finding in findings:
            print("murscope/wizard.py: %s" % finding)
            bad += 1

    for locale in sorted(rendered):
        for finding in floors(locale, rendered[locale][0], width):
            print("this check's own fixture: %s" % finding)
            bad += 1

    for locale in sorted(rendered):
        lines, anchors = rendered[locale]
        for finding in detect(bundle(lines, anchors, wizard.STATE_WIDTH)):
            print("murscope/wizard.py, locale %s: %s" % (locale, finding))
            bad += 1

    if bad:
        print("\nFAILED: %d width problem(s)." % bad)
        return 1

    spread = {}
    subtexts = 0
    for locale, (lines, anchors) in rendered.items():
        columned = [(line, anchor) for line, anchor in zip(lines, anchors)
                    if anchor is not None]
        subtexts = len(lines) - len(columned)
        spread[locale] = (
            len({_cells(line[:line.rindex(anchor)])
                 for line, anchor in columned}),
            len({len(line[:line.rindex(anchor)]) for line, anchor in columned}),
            len(columned))
    print("OK: %d line(s) with a last column rendered per locale across %d "
          "locale(s) (%s), and in every one of them that column starts at a "
          "single cell offset - the heading counted in with the rows."
          % (spread[locales[0]][2], len(locales), ", ".join(locales)))
    print("    The point is the second number: %s. The cell offsets agree and "
          "the *character* offsets do not, which is the whole of DP86 - the "
          "old code padded those character counts to one number and drew a "
          "crooked table doing it."
          % ", ".join("%s %d cell offset(s) from %d character offset(s)"
                      % (locale, spread[locale][0], spread[locale][1])
                      for locale in sorted(spread)))
    print("    %d sub-text line(s) per locale were measured separately, "
          "against the state column they hang under rather than against the "
          "left margin - an indent counted in characters sits left of its own "
          "column the moment a project's name is wide, and the row above it "
          "stays perfectly aligned while it does." % subtexts)
    print("    %d width class(es) checked against characters, cells and UTF-8 "
          "bytes (%s), because a byte count and a character count are each "
          "right about a different two of them."
          % (len(WIDTH_CLASSES),
             ", ".join(label for label, _t, _c, _w, _b in WIDTH_CLASSES)))
    print("    What exercises this: every locale's own table has to hold a "
          "wide name, an accented name and an ASCII one, a clip, and a row "
          "whose sub-text wraps. Those floors are per locale, because pooled "
          "across all three they were answered by `zh` and `fr` on `en`'s "
          "behalf and taking the wide name out left this green (DP87).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
