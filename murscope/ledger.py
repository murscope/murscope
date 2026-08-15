"""The declaration parser, ported from the pinned reference (ADR-0003).

Signal 14. It is the least universal signal there is - measured on the
reference implementation, an explicit marker fires on one project in
thirteen - and it is the most trustworthy one, because the project said
it about itself and dated it by its own file. Coverage comes from
elsewhere (see state.py); this is where precision comes from.

Precision is three refusals, and Rule 10 pins all three:

1. **Prose.** A line that merely mentions a marker mid-sentence. A
   declaration leads its line, or leads one of the line's table cells.
2. **Notation legends.** Marker text inside a code span or an HTML
   comment is a ledger explaining its own conventions, not a ledger
   declaring a state.
3. **An empty "Blocked" heading.** A heading is a bucket. Reporting the
   bucket invents a blocker out of a section title; the claim, if there
   is one, is the section's first item.

Leading the line is not sufficient on its own - "blockers, which
contradicts the spec" leads with a marker and is prose. One of four
shapes must also hold: a multi-word marker, a marker followed by
punctuation, a short status cell, or a non-ASCII marker, which ledgers
only ever use to declare a state.

The precedence rule is here too. A ledger line that names the owner
overrules the roster's hand-set next-move badge and joins the owner
queue marked as coming from the ledger; a generic blocker
("BLOCKED: upstream API is down") never overrules, because that is not
the owner's move to make. Without it a board shows "the AI side owes the
next move" beside a line reading "waiting on you" - two answers to one
question, with the stale one holding the badge.
"""
from __future__ import annotations

import re
from datetime import datetime, timezone
from . import fingerprints
from .guard import inside_root

CODE_SPAN = re.compile(r"`[^`]*`")
LINE_NOISE = re.compile(r"^[\s>#*_+\-]+")
EMPHASIS = re.compile(r"[*_]{1,3}")
# One table cell of a `|---|:--:|` separator line: dashes, optionally
# with the alignment colons.
TABLE_DASHES = re.compile(r"^:?-{1,}:?$")

# A file past this is not a ledger, it is a log or a dump.
MAX_LEDGER_BYTES = 400_000
TEXT_CAP = 220
STALE_DAYS = 14
# A short cell is a status cell: "BLOCKED" in a table column, not a
# sentence that happens to open with the word.
SHORT_CELL = 14
# The last three are the fullwidth colon, the em dash and the fullwidth
# opening parenthesis, escaped so this file stays ASCII (Rule 3).
PUNCTUATION_AFTER_MARKER = (":", "-", "(", "\uff1a", "\u2014", "\uff08")

# Files a project writes about itself, by fixed path. M1 kept this as a
# literal and left a note asking M2 to reconcile it with the design
# authority's fingerprint table rather than grow a second list - so it
# is now derived from that table and this name stays only because
# callers use it. The
# subset rule is unchanged and still argued in fingerprints.py: these are
# the rows that are ledgers, not the rows that are instructions for an
# agent.
LEDGER_SHAPES = fingerprints.LEDGER_SHAPES


def clip(text):
    """Cap the text and *say* it was capped.

    The summary screen already refuses to cut a word in half, on the
    grounds that it reads as a rendering bug. A declaration on the board
    was being cut at the cap with no ellipsis at all, which is worse: a
    reader cannot tell a short sentence from a truncated one.
    """
    if len(text) <= TEXT_CAP:
        return text
    cut = text[:TEXT_CAP - 1]
    if " " in cut[TEXT_CAP // 2:]:
        cut = cut[:cut.rfind(" ")]
    return cut.rstrip(" ,;:") + "\u2026"


def blocker_line(line, markers):
    """(text, marker) when this line declares a state, else None.

    Refusals 1 and 2 live here. The line is stripped of code spans first,
    then each candidate - the whole line, and every table cell in it - is
    stripped of markdown noise and tested against the vocabulary.
    """
    if "<!--" in line:
        return None
    stripped = CODE_SPAN.sub(" ", line)
    for cell in [stripped] + stripped.split("|"):
        text = LINE_NOISE.sub("", cell).strip()
        # A leftover backtick means this cell is the inside of a code
        # span that opened on an earlier line - a legend, not a state.
        if not text or "`" in text:
            continue
        low = text.lower()
        for marker in markers:
            if not low.startswith(marker):
                continue
            rest = low[len(marker):].lstrip("s")  # blocker / blockers
            if (" " in marker
                    or not marker.isascii()
                    or rest[:1] in PUNCTUATION_AFTER_MARKER
                    or len(text) <= SHORT_CELL):
                return EMPHASIS.sub("", text).strip(), marker
            break
    return None


def is_table_delimiter(text):
    """Is this the `|---|---|` line that separates a header from its rows?"""
    cells = [cell.strip() for cell in text.strip().strip("|").split("|")]
    return bool(cells) and all(TABLE_DASHES.match(cell) for cell in cells)


def table_cells(text):
    """A row's cells, cleaned, in order, without the pipes."""
    out = []
    for cell in text.strip().strip("|").split("|"):
        cell = EMPHASIS.sub("", LINE_NOISE.sub("", CODE_SPAN.sub(" ", cell))).strip()
        if cell:
            out.append(cell)
    return out


def section_first_item(lines, start):
    """The first real item under a heading, or None if the section is empty.

    Refusal 3 lives here. Comments do not count as content: template text
    under an empty heading is exactly what a ledger leaves behind, and
    treating it as the claim reports the template.

    **A table's header is not the section's first item.** Found in a real
    ledger rather than imagined: a section written as a table reported
    `Waiting on a human: | Item | Note |` - the column names, rendered
    with the pipes still in them, as though that were the state of the
    project. The header names the columns and the delimiter is
    punctuation; the claim is the first data row, and it is read as a
    sentence rather than echoed as markup.

    A table carrying only a header and a delimiter is still an empty
    bucket, so refusal 3 covers it too - two lines of column names
    declare nothing.
    """
    rows = []
    for line in lines[start + 1:]:
        text = line.strip()
        if not text or text.startswith("<!--"):
            continue
        if text.startswith("#"):
            break
        rows.append(text)
        # Header, delimiter, first data row: three is all a table needs,
        # and a non-table answers on the first.
        if len(rows) >= 3:
            break
    if not rows:
        return None

    if rows[0].startswith("|"):
        if len(rows) >= 2 and is_table_delimiter(rows[1]):
            if len(rows) < 3 or not rows[2].startswith("|"):
                return None
            cells = table_cells(rows[2])
        else:
            cells = table_cells(rows[0])
        return " - ".join(cells)[:TEXT_CAP] if cells else None

    text = LINE_NOISE.sub("", CODE_SPAN.sub(" ", rows[0])).strip()
    text = EMPHASIS.sub("", text).strip()
    return text[:TEXT_CAP] if text else None


NAME_SPLIT = re.compile(r"[^\w]+", re.UNICODE)


def _name_tokens(text):
    """Lowercased word tokens, for comparing names without fixing an order.

    Measured on real data: authorship seeded a two-word name in one
    order and the ledger wrote the same two words in the other, which is
    what a family name written first rather than last looks like to a
    matcher. A substring test missed it, so the naming
    half silently did nothing - and because an alias *was* configured, the
    board switched off its honest "not configured" marker and printed a
    confident zero instead. A wrong answer replacing an admitted unknown
    is the worst trade this product can make, so the comparison is on
    token sets and family-name order stops mattering.
    """
    return {token for token in NAME_SPLIT.split(text.lower()) if token}


def names_match(alias, head):
    """Is `alias` the person named in `head`, in any word order?"""
    tokens = _name_tokens(alias)
    if not tokens:
        return False
    if alias.lower() in head.lower():
        return True
    return tokens <= _name_tokens(head)


NAMING_LEAD = ("waiting on", "awaiting", "waiting for", "blocked on")
# Words that follow "waiting on" without naming anyone. A generic blocker
# is a real blocker and still not somebody's name, so counting it as one
# put a person-shaped hole in the owner queue: `Waiting on a human:` names
# nobody at all.
GENERIC_SUBJECTS = ("a ", "an ", "the ", "someone", "somebody", "anyone",
                    "a human", "a person", "a decision", "review",
                    "approval", "confirmation", "feedback", "upstream")


def strip_marker(text, markers):
    """The sentence with a leading marker and its punctuation removed.

    `waits_on_owner()` tested the whole text, so it only ever saw a naming
    phrase on a bare `Waiting on <name>` line - and the commonest shape a
    ledger actually uses, `BLOCKED: waiting on <name>`, could not match by
    construction. The owner queue was therefore wrong in the direction
    that matters: silently empty.
    """
    low = text.lower()
    for marker in sorted(markers, key=len, reverse=True):
        # A marker that *is* the naming phrase must survive: `waiting on`
        # is in the vocabulary, so stripping it removed the very thing the
        # caller was about to look for, and `waiting on <name>` stopped
        # matching the moment this function was introduced.
        if marker in NAMING_LEAD:
            continue
        if low.startswith(marker):
            rest = text[len(marker):].lstrip("sS")
            return rest.lstrip(" :-\u2014\uff1a\uff08(").strip()
    return text


def named_subject(text):
    """What comes after the naming phrase, or "" when nothing does."""
    low = text.lower()
    for lead in NAMING_LEAD:
        if low.startswith(lead):
            rest = text[len(lead):].strip()
            head = rest.split(":", 1)[0].strip()
            return head
    return ""


def naming_phrase(text):
    """Did this name somebody we should have been able to place?

    Used for the board's unmatched counter, not for matching. A generic
    blocker names nobody, so counting it would report "a line names a
    person we could not match to you" about a line that named no person.
    """
    head = named_subject(text)
    if not head:
        return False
    low = head.lower()
    return not any(low.startswith(word) for word in GENERIC_SUBJECTS)


def waits_on_owner(text, owner_markers, aliases, markers=()):
    """Does this declaration put the ball in the owner's court?

    Two ways it can. A marker from the owner subset says so by meaning -
    "needs decision" names nobody and still means you. "Waiting on X"
    says so by naming, and only if X matches one of the aliases the user
    configured; aliases default to empty, so this half is off until
    something fills it (DP63 seeds it from authorship).

    Matching is on word tokens rather than substrings, so the same two
    words in either order are the same person.
    """
    low = text.lower()
    if any(low.startswith(marker) for marker in owner_markers):
        return True
    body = strip_marker(text, markers) if markers else text
    head = named_subject(body)
    if not head:
        return False
    # Aliases are the user's own words, so they are tried before any
    # judgement about whether the subject looks generic. A shipped case
    # configures the alias `the owner`, and `Waiting on the owner` is
    # exactly the shape it is meant to catch - the generic filter belongs
    # to the *unmatched* counter, not to matching.
    return any(names_match(alias, head) for alias in aliases)


def ledger_paths(root, configured):
    """(files to read, refusals). Configured paths win, else the shapes.

    Falling back to the shape list is what makes `declared` reachable for
    somebody who has written no configuration at all.

    **Every path is confined to the project root, and a path that escapes
    is refused and reported rather than renamed.** This function used to
    join `root / rel` and read whatever came out, which meant two things
    a stranger would never guess from the README:

      ledgers: ["../secret/OUTSIDE.md"]   read it, and showed the ../ path
      ledgers: ["/abs/path/OUTSIDE.md"]   read it - and `root / rel` on an
                                          absolute rel *is* rel, so the
                                          project root was ignored
                                          entirely, and the board then
                                          showed the bare filename

    The second was the worse of the two: the caller downstream fell back
    to `path.name` whenever `relative_to` raised, so a file from outside
    the project appeared under a name with no provenance at all. The code
    had foreseen the out-of-root case and hidden it instead of refusing
    it. "murscope reads nothing outside the projects you listed" is a
    promise on the front page, so it is enforced here and checked by
    Rule 17 rather than left to whoever edits this next.
    """
    found = []
    refused = []
    seen = set()
    for rel in list(configured) + list(LEDGER_SHAPES if not configured else ()):
        path = root / rel
        key = str(path)
        if key in seen:
            continue
        seen.add(key)
        if not inside_root(root, path):
            refused.append({
                "source": str(rel),
                "detail": "refused: it resolves outside the project root, and "
                          "murscope reads nothing outside the projects you "
                          "listed",
            })
            continue
        if path.is_file() and not path.is_symlink():
            found.append(path)
    return found, refused


def _read(path):
    try:
        if path.stat().st_size > MAX_LEDGER_BYTES:
            return None, "larger than %d bytes; not read as a ledger" % MAX_LEDGER_BYTES
        return path.read_text(encoding="utf-8", errors="replace"), None
    except OSError as exc:
        return None, str(exc)[:200]


# A line that continues the one above rather than starting something new.
# Tested on the line with its indent removed, because an indented
# continuation is the ordinary way markdown wraps a list item - the first
# version of this pattern rejected leading whitespace and therefore matched
# nothing at all, which is the shape the bug had in the first place.
STARTS_SOMETHING = re.compile(
    r"^([#|>]|[*+\-]\s|\d+[.)]\s|```|~~~|<!--)")
# A soft wrap of a list item is indented under it. An unindented line at
# the same level is a new paragraph, and joining it produced a board entry
# whose own text said "this one is done" - the same inversion the wrap fix
# was written to remove, arriving from the other direction.
MIN_CONTINUATION_INDENT = 1


def continuation(lines, index, markers=()):
    """Physical lines that are the rest of this declaration's sentence.

    A ledger author wraps a long line and markdown treats the wrap as one
    paragraph. The parser read only the first physical line, and an audit
    found what that costs: a declaration ending `... RETURNED (D149): 2`
    on screen, which reads as "returned 2", where the sentence continued
    "2 passed 5 failed - the label holds". Truncated to the point of
    saying the opposite, with no ellipsis to show anything was missing.
    """
    out = []
    lead = len(lines[index]) - len(lines[index].lstrip())
    for line in lines[index + 1:]:
        text = line.strip()
        if not text or STARTS_SOMETHING.match(text):
            break
        indent = len(line) - len(line.lstrip())
        if indent < lead + MIN_CONTINUATION_INDENT:
            break
        # A line that is itself a declaration is a separate claim, however
        # it is indented. An audit found two adjacent declarations joined
        # into one sentence.
        # A line that is itself a declaration is a separate claim. The
        # vocabulary arrives as a parameter: the first version kept it in
        # module state set by `scan_file`, so this test silently did
        # nothing for every caller that did not go through there - which
        # included the check that was meant to verify it.
        if markers and blocker_line(text, markers):
            break
        # A line opening in bold is a sub-note - a heading in list
        # clothing. Requiring it to close in bold too was the first
        # attempt, and `**Note:** an aside` opens bold and closes in prose.
        if text.startswith("**") or text.startswith("__"):
            break
        # Emphasis markers are stripped from the first line and were kept
        # on every continued one, so a real board carried a declaration
        # ending in `**`.
        out.append(EMPHASIS.sub("", text).strip())
    return out


def scan_file(path, vocabulary):
    """Every declaration in one file, in order, with line numbers."""
    raw, problem = _read(path)
    if raw is None:
        return [], problem, 0
    lines = raw.splitlines()
    hits = []
    # Lines that mention a marker and were refused. `hits` cannot stand in
    # for this: the three refusals happen inside `blocker_line`, so a
    # refused line never becomes a hit, and "no marker was mentioned" and
    # "a marker was mentioned and refused" collapsed into one number. The
    # command that exists to show the working needs them apart.
    refused = 0
    for index, line in enumerate(lines):
        found = blocker_line(line, vocabulary.markers)
        if not found:
            low = line.lower()
            if any(marker in low for marker in vocabulary.markers):
                refused += 1
            continue
        text, marker = found
        if line.lstrip().startswith("#"):
            item = section_first_item(lines, index)
            if item is None:
                # Refusal 3: the bucket is empty, so nothing is stuck.
                continue
            text = clip("%s: %s" % (text, item))
        rest = continuation(lines, index, vocabulary.markers)
        if rest:
            text = " ".join([text] + rest)
        hits.append({"line_no": index + 1, "text": clip(text),
                     "marker": marker, "raw": clip(line.strip()),
                     "wrapped": bool(rest)})
    return hits, None, refused


def find_declaration(root, configured, vocabulary):
    """(declaration, evidence). Newest ledger wins; last marker in it wins.

    Ledgers are append-ordered, so the last marker in a file is the
    current claim and the earlier ones are history. `evidence` records
    every file that was opened, including the ones with nothing in them,
    because "we read three ledgers and found no marker" and "there was
    nothing to read" are the two facts the state layer has to separate.
    """
    paths, refused = ledger_paths(root, configured)
    evidence = {"read": [], "unreadable": list(refused), "hits": 0,
                "refused": list(refused), "refused_lines": 0}
    best = None
    for path in paths:
        hits, problem, near = scan_file(path, vocabulary)
        evidence["refused_lines"] += near
        try:
            rel = str(path.relative_to(root))
        except ValueError:
            # Unreachable: ledger_paths() refuses anything that does not
            # resolve inside the root. Kept as a loud failure rather than
            # a rename, because the rename is what hid the escape - a
            # file from outside the project appeared under a bare
            # filename with no provenance.
            evidence["unreadable"].append({
                "source": str(path),
                "detail": "refused: outside the project root, and not "
                          "renamed to look like it is not",
            })
            continue
        if problem is not None:
            evidence["unreadable"].append({"source": rel, "detail": problem})
            continue
        evidence["read"].append(rel)
        if not hits:
            continue
        evidence["hits"] += len(hits)
        try:
            stamp = path.stat().st_mtime
        except OSError:
            continue
        if best is None or stamp > best["_ts"]:
            hit = hits[-1]
            best = {"_ts": stamp, "source": rel, **hit}

    if best is None:
        return None, evidence
    stamp = best.pop("_ts")
    age = round((datetime.now(timezone.utc).timestamp() - stamp) / 86400.0, 1)
    best.update({
        "at": datetime.fromtimestamp(stamp, timezone.utc).astimezone().isoformat(
            timespec="seconds"),
        "age_days": age,
        "stale": age > STALE_DAYS,
        "owner": waits_on_owner(best["text"], vocabulary.owner_markers,
                                vocabulary.aliases, vocabulary.markers),
        # Whether this line names *somebody*, independently of whether it
        # matched the user. The board needs the difference: "nobody is
        # waiting on you" and "a line names a person we could not match to
        # you" are different facts, and printing a confident zero for the
        # second is the contradiction an audit found on one screen.
        "names_somebody": naming_phrase(
            strip_marker(best["text"], vocabulary.markers)),
    })
    return best, evidence
