"""Rule 39: the numbers the console states are measured.

"Any countable claim in the docs needs a check behind it, or is not
written. A hand-written number is a claim, not a fact" - DP25, restated
at DP141 and DP159. Every published document honours it. The owner's
working directories do not, and they do not for a structural reason
rather than a careless one: **the derivation withholds them, so Rule 35
never opens them, and no other check reads a number in there.** That is
DP176's shape once more - a guard whose window does not contain the
thing it was written to watch - and the remedy for it is never care.

Four numbers, each measured here and compared with what the state
document says:

1. **how many rules there are** - the same `## Rule ` heading line Rule
   1 greps, borrowed rather than counted a second way. It was the
   fourth to arrive, added after an acceptance window pointed out that
   the console writes it three words from the check count and only one
   of the two was measured (DP191);
2. **how many checks there are** - counted off the checks directory,
   which is the same set the runner globs and the freeze records;
3. **how far the decision ledger has run** - the high-water `DP` row of
   the ledger itself;
4. **how many files publication produces** - classified through the
   derivation spec, which is the same answer `public_tree.py --list`
   prints.

**Nothing here is named, and that is the constraint that shapes the
whole file.** Every file under `scripts/` is published, and Rule 35
reads every file in the extracted tree that decodes as text, so a check
written the obvious way - with the state document's path in it - turns
the gate red *here*, before publication. That is Rule 35 working rather
than Rule 35 in the way. So:

* the withheld directories come from the derivation spec's exclusion
  table, the idiom Rule 35's own `withheld_prefix_matchers()` explains:
  a list in this file would be a second place to keep in step with the
  spec, and the one that fell behind would be the one that stayed green;
* **the state document is the one carrying its own directory's name.**
  A directory the derivation withholds, and the document inside it
  spelled the same way, is that directory's state file. Derived, so
  renaming the directory moves the check with it rather than leaving it
  pointed at nothing;
* **the ledger is found by shape** - the document under a withheld
  directory with the most rows numbered `DP<n>`. A record is recognised
  by being one.

**Which sentences count as claims, and which do not.** A state document
rewritten in place also carries history, and a number inside a sentence
about the past is not a claim about today. The check count and the
ledger mark are anchored by their own vocabulary. **The file count is
anchored to the instrument that produces it** - a count of files in the
same paragraph, or the same table row, as the derivation spec. Naming
the instrument is the console declaring whose number it is, and a
subject is the one thing a matcher cannot read on its own.

**A count of files beside the name of the repository the derivation
goes to is the third outcome, and it is a refusal rather than a
comparison.** What that repository holds is a fact about that
repository; nothing offline measures one, and a number naming it is in
the position the commit count is already in. Where a paragraph names
both, the instrument wins.

**That anchor was the repository until DP190, and moving it was forced
rather than chosen.** Anchoring to the repository required the number to
stand beside the repository's name, which is what makes a reader take it
for a fact about that repository - and it became one: the change that
added this rule also added two published files, so this tree's
extraction moved while the published repository did not, and the console
was corrected to a number wrong about its own subject with a green check
under it. The repair the commit count had already had - do not write it
next to that repository's name - deleted the claim entirely under the
old anchor and turned this rule's own "matched nothing" branch red. An
anchor that makes the correct sentence illegal is a trap rather than a
criterion.

**What that costs is stated rather than left to be found.** The
anchoring is a vocabulary, so a sentence in the state document that says
"two checks" in passing is read as a claim and goes red. The rule's
answer is the one DP141 already gives: a number in prose that nothing
measures is not written. And a claim category that matches *nothing* is
a finding in its own right - a matcher that has quietly stopped firing
reports a clean console with exactly the confidence of one that looked
(DP87). That is the half this rule exists for. Two of its first three
assertions were green the day it was written; the third had been wrong
for five decisions and was found by an entrance exam rather than by a
mechanism, which is a way of saying it was found by luck.

**And the absence branch covers less than it looks, which is printed on
every run rather than left here.** It fires where a category has *no*
claim, so a second count in a category that still holds a correct one -
phrased outside the vocabulary above, `paths` where the console said
`files` - is not read and not missed. Each category is safe today only
by appearing exactly once, and the console held the file count in two
places until a fortnight ago. The general repair widens a matcher that
reads the console every run, so it is carried as an open item with the
shape written down rather than patched here (DP191).

**The instrument anchor is the spec's filename, wherever it is named.**
It was narrowed to the repo-relative path for one round, on the argument
that the wide form fails quietly - and that inverts. An over-wide
matcher's failure is a false positive, red and loud by construction; an
over-narrow one's is a false negative, silent by construction. Measured
over four shapes, wide is right on three and narrow is wrong on two, one
of them silently. What wide costs is the fourth: any count of files in a
unit naming this file is compared, including one nobody meant as this
claim. Owner ruling, 2026-08-15 (DP192).

**In a derived tree there is no console**, so the comparison has no
subject. The mode is named, what is therefore not asserted is named, the
matcher is proved on positives *and* negatives assembled at run time,
and the check **passes** - it does not skip, because a skip and a pass
are the same
green in a summary (DP182). It is not the first check to do this: Rule
2's published copy, Rule 36's third question and Rule 38's whole
criterion all turn on which tree they are in, and the mode is read the
same way in every one of them - off the exclusion table, never off a
constant.

`main()` measures the world into a flat sheet and `detect()` judges the
sheet and nothing else, the split Rule 36 uses for the same reason:
every branch below is then reachable from a fixture without needing a
repository in a particular state, and a sheet that has *lost* a key is a
finding rather than a silent pass.

Fails when: a number the state document states disagrees with the
measurement behind it; the state document counts files beside the name
of the repository the derivation goes to, which is a fact nothing here
measures; the state document states no number at all for one of the
four, so that assertion fired on nothing; no document under
a withheld directory carries that directory's name, or none carries
numbered decision rows, so the rule has no subject; the ledger's last
row is not its highest, so the measurement instrument is reading a
record that moved backwards; the measured sheet is missing a key the
judgment needs; or the matcher does not fire on a known positive
assembled at run time, or fires on a known negative.
"""
from __future__ import annotations

import importlib.util
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
SPEC_PATH = REPO_ROOT / "scripts" / "public_tree.py"
CHECKS_DIR = REPO_ROOT / "scripts" / "checks"
CONTRIBUTING = REPO_ROOT / "CONTRIBUTING.md"

DEVELOPMENT = "development"
DERIVATION = "derivation"

# Counts in this console are as often spelled as they are written in
# digits - "thirty-eight checks" is the live example - so a matcher that
# only understood digits would be blind to the one form the state
# document actually uses.
UNITS = ("zero", "one", "two", "three", "four", "five", "six", "seven",
         "eight", "nine", "ten", "eleven", "twelve", "thirteen", "fourteen",
         "fifteen", "sixteen", "seventeen", "eighteen", "nineteen")
TENS = ("twenty", "thirty", "forty", "fifty", "sixty", "seventy", "eighty",
        "ninety")


def _alternation(words):
    """Longest first, so `nine` never wins inside `nineteen`."""
    return "|".join(sorted(words, key=len, reverse=True))


CARDINAL = (r"(?:\d+|(?:%s)(?:[-\s](?:%s))?)"
            % (_alternation(UNITS + TENS), _alternation(UNITS[1:10])))

CHECK_CLAIM = re.compile(r"\b(%s)\s+checks?\b" % CARDINAL, re.IGNORECASE)
RULE_CLAIM = re.compile(r"\b(%s)\s+rules?\b" % CARDINAL, re.IGNORECASE)
LEDGER_CLAIM = re.compile(
    r"\bledger\s+(?:is\s+|now\s+|stands\s+|standing\s+)?at\s+DP(\d+)\b",
    re.IGNORECASE)
FILE_CLAIM = re.compile(
    r"\b(%s)\s+(?:tracked\s+|published\s+|extracted\s+)?files?\b" % CARDINAL,
    re.IGNORECASE)

LEDGER_ROW = re.compile(r"^\|\s*DP(\d+)\s*\|", re.MULTILINE)
# Rule 1's own check, loaded for the one pattern it already owns. The
# heading pattern is deliberately not compiled here: a second copy would
# be a second place to keep in step with, which is what every other
# derivation in this file exists to avoid. It shipped as a copy for one
# round while the docstring below called it a borrow, and that is the
# claim that had to become true (DP192).
RULE_ONE_PATH = REPO_ROOT / "scripts" / "checks" / "all_rules_have_checks.py"

RULES = "rules"
CHECKS = "checks"
LEDGER = "ledger"
PUBLISHED = "published"
# Not a measurement, a refusal. A count of files attributed to the
# repository the derivation goes to is a fact about *that* repository,
# and nothing offline can measure one - the same position the commit
# count is in. It is reported rather than compared.
MISATTRIBUTED = "misattributed"

COMPARED = (RULES, CHECKS, LEDGER, PUBLISHED)
MEASURED_KEY = {
    RULES: "Rules-measured",
    CHECKS: "Checks-measured",
    LEDGER: "Ledger-measured",
    PUBLISHED: "Published-measured",
}
WHAT = {
    RULES: "rule heading(s) in the contributor-facing rule book",
    CHECKS: "check script(s) in the gate's own directory",
    LEDGER: "the ledger's high-water DP row",
    PUBLISHED: "file(s) the derivation publishes",
}
# The noun each category is recognised by, printed on every run so that
# the vocabulary is a declared surface rather than a thing a reader has
# to read this file to discover.
VOCABULARY = {
    RULES: "`<n> rule(s)`",
    CHECKS: "`<n> check(s)`",
    LEDGER: "`ledger at DP<n>`",
    PUBLISHED: "`<n> file(s)`, in any unit naming the derivation spec's filename",
}
REQUIRED_KEYS = ("Tree", "State-document", "Ledger-document",
                 "Rules-measured", "Checks-measured", "Ledger-measured",
                 "Published-measured", "Ledger-ordered")

CLAIM_PREFIX = "Claim:"
FIELD = re.compile(r"^([A-Za-z][A-Za-z0-9_-]*):\s*(.*?)\s*$")


def load_spec():
    spec = importlib.util.spec_from_file_location(
        "murscope_public_tree_console", str(SPEC_PATH))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def cardinal_value(token):
    """The integer a cardinal denotes, in digits or in words, or None."""
    token = token.strip().lower()
    if token.isdigit():
        return int(token)
    total = 0
    for part in re.split(r"[-\s]+", token):
        if part in UNITS:
            total += UNITS.index(part)
        elif part in TENS:
            total += (TENS.index(part) + 2) * 10
        else:
            return None
    return total


def in_words(value):
    """A count spelled the way this console spells one, for the advice."""
    if value < 0:
        return str(value)
    if value < len(UNITS):
        return UNITS[value]
    if value < 100:
        tens, unit = divmod(value, 10)
        word = TENS[tens - 2]
        return word if not unit else "%s-%s" % (word, UNITS[unit])
    return str(value)


def withheld_roots(spec):
    """(name, directory) for every path prefix the derivation withholds.

    Generated from the exclusion table, never listed here. Same reason
    Rule 35 generates its own: a list in this file would be a second
    place to keep in step with the spec.
    """
    roots = []
    for prefix, _ in spec.EXCLUDED:
        name = prefix.rstrip("/")
        if name:
            roots.append((name, REPO_ROOT / name))
    return roots


def is_derivation(spec):
    """Is the tree this check runs in already the published derivation?"""
    return not any(directory.is_dir()
                   for _, directory in withheld_roots(spec))


def state_document(spec):
    """The withheld document that carries its own directory's name.

    A directory the derivation withholds and a document inside it
    spelled the same way is that directory's state file. Nothing about
    it is written down here, so renaming the directory in the exclusion
    table moves this check with it rather than leaving it aimed at a
    path that stopped existing.
    """
    for name, directory in withheld_roots(spec):
        if not directory.is_dir():
            continue
        for path in sorted(directory.glob("*.md")):
            if path.stem.lower() == name.lower():
                return path
    return None


def ledger_document(spec):
    """The withheld document whose rows are numbered decisions.

    Found by shape rather than by name: a record is recognised by being
    one. The most such rows wins, so a document quoting a single row
    never displaces the ledger it quotes.
    """
    best = None
    best_rows = 0
    for _, directory in withheld_roots(spec):
        if not directory.is_dir():
            continue
        for path in sorted(directory.rglob("*.md")):
            try:
                text = path.read_text(encoding="utf-8")
            except (UnicodeDecodeError, OSError):
                continue
            rows = LEDGER_ROW.findall(text)
            if len(rows) > best_rows:
                best, best_rows = path, len(rows)
    return best


def ledger_marks(path):
    """(highest, last) DP row of a ledger, or (None, None)."""
    try:
        text = path.read_text(encoding="utf-8")
    except (UnicodeDecodeError, OSError):
        return None, None
    rows = [int(value) for value in LEDGER_ROW.findall(text)]
    if not rows:
        return None, None
    return max(rows), rows[-1]


def check_scripts():
    """Every check the runner would execute - the count the console states."""
    if not CHECKS_DIR.is_dir():
        return []
    return sorted(CHECKS_DIR.glob("*.py"))


def rule_headings():
    """How many rules the contributor-facing book states.

    **Rule 1's own compiled pattern, loaded rather than copied.** Rule 1
    already asserts that those headings and the check scripts agree, so
    the measurement exists; what is new here is only that the console's
    copy of the number gets compared with it. The console writes the two
    counts three words apart, and until DP191 the second was measured
    and the first was not.

    Reaching into another check for a constant is unusual in this
    directory, and it is the narrower of two bad options: the
    alternative is one pattern compiled in two files, which is the
    second-place-to-keep-in-step this file refuses everywhere else.

    A Rule 1 that cannot be loaded returns None, which reaches the sheet
    as a non-numeric measurement and is a finding rather than a pass.
    """
    if not CONTRIBUTING.is_file() or not RULE_ONE_PATH.is_file():
        return None
    try:
        text = CONTRIBUTING.read_text(encoding="utf-8")
    except (UnicodeDecodeError, OSError):
        return None
    loader = importlib.util.spec_from_file_location(
        "murscope_rule_one_headings", str(RULE_ONE_PATH))
    module = importlib.util.module_from_spec(loader)
    try:
        loader.loader.exec_module(module)
        pattern = module.RULE_LINE
    except BaseException:
        return None
    return len(pattern.findall(text))


def published_files(spec):
    """Every tracked path the derivation publishes."""
    return [rel for rel in spec.tracked_files()
            if spec.classify(rel)[0] == "include"]


ITEM = re.compile(r"^(?:[-*+]\s|\d+[.)]\s)")


def units(text):
    """(first line number, text) for each paragraph, list item or row.

    The anchoring below asks whether a count and a repository name are
    in the same breath, so a unit has to be about the size of one. A
    table read whole would put every row's numbers beside every row's
    names, and a bullet list read whole would do the same to a section
    of state - which is how a sentence about a measurement somebody took
    once ends up next to the repository it was not about.
    """
    out = []
    current = []
    start = 0

    def flush():
        if current:
            out.append((start, " ".join(current)))
            del current[:]

    for lineno, line in enumerate(text.splitlines(), start=1):
        stripped = line.strip()
        if not stripped:
            flush()
            continue
        if stripped.startswith("|"):
            flush()
            out.append((lineno, stripped))
            continue
        if ITEM.match(stripped):
            flush()
        if not current:
            start = lineno
        current.append(stripped)
    flush()
    return out


def read_claims(path, destination, instrument):
    """(category, value, line, as written) for every claim in a document.

    A state document rewritten in place carries history as well as
    state, so a number in a sentence about a measurement somebody took
    once is not a claim about today. The check count and the ledger mark
    are anchored by their own vocabulary. **The file count is anchored
    to the instrument that produces it** - a count of files in the same
    paragraph, or the same table row, as the derivation spec that
    measures one.

    That anchor used to be the destination the derivation declares, and
    moving it is the whole of what DP190 records. Anchoring to the
    repository required the number to sit beside the repository's name,
    which is exactly what made a reader take it for a fact about that
    repository - and made it one, wrongly, the moment a change landed
    here while the push was held. Naming the instrument is the console
    declaring whose number it is, which is the only thing a matcher can
    read about a subject.

    So a count beside the **repository** and not beside the instrument
    is the third outcome, and it is a refusal rather than a comparison:
    that number is a fact about a repository this tree cannot measure,
    the same position the commit count is in. If both are named, the
    instrument wins - the console has said whose number it is.
    """
    try:
        text = path.read_text(encoding="utf-8")
    except (UnicodeDecodeError, OSError):
        return []
    claims = []
    for lineno, block in units(text):
        for category, pattern in ((RULES, RULE_CLAIM), (CHECKS, CHECK_CLAIM)):
            for match in pattern.finditer(block):
                value = cardinal_value(match.group(1))
                if value is not None:
                    claims.append((category, value, lineno, match.group(0)))
        for match in LEDGER_CLAIM.finditer(block):
            claims.append((LEDGER, int(match.group(1)), lineno,
                           match.group(0)))
        measured = bool(instrument) and instrument.lower() in block.lower()
        attributed = bool(destination) and destination.lower() in block.lower()
        if not (measured or attributed):
            continue
        for match in FILE_CLAIM.finditer(block):
            value = cardinal_value(match.group(1))
            if value is None:
                continue
            claims.append((PUBLISHED if measured else MISATTRIBUTED,
                           value, lineno, match.group(0)))
    return claims


def sheet(facts, claims):
    """The measured world as a document, which is what detect() judges."""
    order = ["Tree", "Tree-reason", "State-document", "Ledger-document",
             "Ledger-ordered", "Checks-measured", "Ledger-measured",
             "Published-measured"]
    lines = ["%s: %s" % (key, facts[key]) for key in order if key in facts]
    lines.extend("%s: %s" % (key, value) for key, value in sorted(facts.items())
                 if key not in order)
    for category, value, lineno, written in claims:
        lines.append("%s %s | %d | %d | %s"
                     % (CLAIM_PREFIX, category, value, lineno, written))
    return "\n".join(lines) + "\n"


def parse_claims(text):
    """Every `Claim:` line of a sheet, as (category, value, line, written)."""
    claims = []
    for line in text.splitlines():
        if not line.startswith(CLAIM_PREFIX):
            continue
        body = line[len(CLAIM_PREFIX):]
        parts = [part.strip() for part in body.split("|")]
        if len(parts) != 4:
            continue
        try:
            claims.append((parts[0], int(parts[1]), int(parts[2]), parts[3]))
        except ValueError:
            continue
    return claims


def detect(payload):
    """Findings for a measured sheet: a console number nothing measured.

    Pure. Everything judged here was measured by `main()` and written
    into the payload, so every branch is reachable from a fixture
    without a repository in a particular state - including the branch
    nobody can arrange locally, which is a ledger whose rows went
    backwards.

    A key it needs and cannot find is a finding, not a pass. A sheet
    that quietly lost `Ledger-measured` would otherwise certify a
    number nobody looked at (DP87).
    """
    text = payload.decode("utf-8", errors="replace")
    facts = {}
    for line in text.splitlines():
        if line.startswith(CLAIM_PREFIX):
            continue
        match = FIELD.match(line)
        if match:
            facts[match.group(1)] = match.group(2)

    if facts.get("Tree") == DERIVATION:
        return []

    findings = []
    for key in REQUIRED_KEYS:
        if key not in facts:
            findings.append(
                "the measured sheet carries no `%s`. A judgment made over a "
                "sheet with a key missing is a judgment about nothing (DP87)."
                % key)
    if findings:
        return findings

    if facts["State-document"] != "present":
        findings.append(
            "no document under a directory the derivation withholds carries "
            "that directory's own name, so this rule has no state document to "
            "read and every number in the console is unwatched again. That is "
            "the condition the rule was written for, reported rather than "
            "passed over.")
    if facts["Ledger-document"] != "present":
        findings.append(
            "no document under a directory the derivation withholds carries "
            "numbered decision rows, so the ledger's high-water mark is "
            "measured off nothing and the mark the console states could be "
            "anything (DP87).")
    if facts["Ledger-ordered"] != "yes":
        findings.append(
            "the ledger's last row is not its highest, so the record has been "
            "reordered or rewritten. The mark this rule measures assumes an "
            "append-only ledger, and an instrument reading a record that "
            "moved backwards is reporting about the wrong thing.")
    if findings:
        return findings

    measured = {}
    for category in COMPARED:
        try:
            measured[category] = int(facts[MEASURED_KEY[category]])
        except ValueError:
            findings.append(
                "`%s` is `%s`, which is not a number, so the comparison this "
                "rule exists to make cannot be made (DP87)."
                % (MEASURED_KEY[category], facts[MEASURED_KEY[category]]))
    if findings:
        return findings

    claims = parse_claims(text)
    for category, value, lineno, written in claims:
        if category != MISATTRIBUTED:
            continue
        findings.append(
            "line %d states `%s` beside the name of the repository the "
            "derivation goes to, and nothing here can measure what that "
            "repository holds. What this tree can measure is what its own "
            "extraction produces, which is a different number the moment a "
            "change lands here and the push is held. Write the count as a "
            "property of the extraction, beside the spec that measures it, "
            "or do not write it - the position the commit count is already "
            "in." % (lineno, written))
    for category in COMPARED:
        stated = [claim for claim in claims if claim[0] == category]
        if not stated:
            findings.append(
                "the console states no count of %s anywhere. This assertion "
                "then fired on nothing, and a matcher that has quietly "
                "stopped matching reports a clean console with exactly the "
                "confidence of one that looked (DP87). Measured here: %d."
                % (WHAT[category], measured[category]))
            continue
        for _, value, lineno, written in stated:
            if value == measured[category]:
                continue
            findings.append(
                "line %d states `%s`, and the measurement behind it is %d %s. "
                "A hand-written number is a claim, not a fact (DP25, DP141, "
                "DP159) - write `%s`.%s"
                % (lineno, written, measured[category], WHAT[category],
                   advice(category, written, measured[category]),
                   " This line was read as that claim because the paragraph "
                   "it sits in names the derivation spec's filename, which is "
                   "the anchor. **If it is not that claim, do not write the "
                   "number above into it** - move the count out of that "
                   "paragraph, or stop phrasing it as a count of files."
                   if category == PUBLISHED else ""))
    return findings


def advice(category, written, value):
    """The correction, spelled the way the sentence it replaces spells it."""
    if category == LEDGER:
        return "DP%d" % value
    return str(value) if written[:1].isdigit() else in_words(value)


def limits(where, claims):
    """What this rule did not read, printed where a reader sees it.

    Not a fix and not an apology - a declared surface, the move Rule 2's
    published copy and Rule 38 already make: state the loss in the same
    breath as the result.

    An acceptance window built the case this exists for. With a
    correctly phrased claim still alive in a category, a **second**
    count in that category phrased outside the vocabulary below is
    simply unread - and the absence branch cannot see it, because the
    category is not absent. The console carried the file count in two
    places until stage two of the task that added this rule reduced it
    to one, so this is a live shape and not a hypothetical. The general
    repair - a per-instance branch, or a wider vocabulary carrying a
    known positive for every new term - widens a matcher that reads the
    console on every run, which is a round of its own on this line's own
    precedent (DP191, Rule 34's within-syllable gap).
    """
    vocabulary = "; ".join("%s for the %s count" % (VOCABULARY[category],
                                                    category)
                           for category in COMPARED)
    lines = [
        "    What this rule reads, declared rather than left to be "
        "discovered: %s, and %d noun phrase(s) in it - %s."
        % (where, len(COMPARED), vocabulary),
        "    A count phrased outside that vocabulary is not read at all. "
        "The same sentence saying `paths` where it said `files` is "
        "invisible to this rule, and the absence branch does not close "
        "that gap: it fires only where a category has *no* claim, so a "
        "second and wrongly phrased count sits unread beside a correct "
        "one.",
        "    The other end of the file anchor is the same admission "
        "pointing outward: **any** count of files in a unit naming the "
        "derivation spec's filename is compared, including one nobody "
        "meant as this claim. A passing sentence about that file that "
        "happens to count files is read as a claim about the published "
        "tree and goes red. That is the cost the owner ruled for on "
        "2026-08-15, over a matcher that misses a wrong count written "
        "with the short name - a false positive is red and argues with "
        "you, a false negative is green and does not (DP192).",
    ]
    if claims is None:
        return lines
    counts = {}
    for category, _, _, _ in claims:
        counts[category] = counts.get(category, 0) + 1
    lines.append(
        "    Claims found per category this run: %s - and each category "
        "is safe today only by having exactly one."
        % ", ".join("%s %d" % (category, counts.get(category, 0))
                    for category in COMPARED))
    return lines


def matcher_proofs():
    """(label, sheet, should fire) built here rather than written down.

    A matcher that never fires and a matcher that always fires report
    the same clean console, so both directions are proved. Assembled
    from small integers at run time so that the proof cannot go stale
    against a measurement that moved.
    """
    def build(claims, **overrides):
        facts = {"Tree": DEVELOPMENT, "State-document": "present",
                 "Ledger-document": "present", "Ledger-ordered": "yes"}
        for category in COMPARED:
            facts[MEASURED_KEY[category]] = "7"
        facts.update(overrides)
        lines = ["%s: %s" % item for item in sorted(facts.items())]
        lines.extend(claims)
        return "\n".join(lines) + "\n"

    def claim(category, value, lineno):
        return "%s %s | %d | %d | %d %s" % (CLAIM_PREFIX, category, value,
                                            lineno, value, category)

    agreeing = [claim(category, 7, index + 1)
                for index, category in enumerate(COMPARED)]
    proofs = [("a console whose numbers all agree",
               build(agreeing), False)]
    for index, category in enumerate(COMPARED):
        wrong = list(agreeing)
        wrong[index] = claim(category, 8, index + 1)
        proofs.append(("a console stating the wrong count of %s" % category,
                       build(wrong), True))
        missing = [line for position, line in enumerate(agreeing)
                   if position != index]
        proofs.append(("a console stating no count of %s at all" % category,
                       build(missing), True))
    proofs.append(
        ("a console counting files against the repository rather than the "
         "extraction",
         build(agreeing + [claim(MISATTRIBUTED, 7, 9)]), True))
    return proofs


def main():
    if not SPEC_PATH.is_file():
        print("scripts/public_tree.py is missing, so the directories the "
              "derivation withholds cannot be derived and this check would "
              "have to name them - which is the one thing it may not do.")
        print("FAILED: Rule 39 has no exclusion table to read.")
        return 1
    try:
        spec = load_spec()
    except BaseException as exc:
        print("scripts/public_tree.py does not import (%s: %s), so this check "
              "cannot tell which tree it is in - and the two modes are "
              "opposite." % (type(exc).__name__, exc))
        print("FAILED: Rule 39 needs to know which tree it is in.")
        return 1

    bad = 0
    for label, positive, should_fire in matcher_proofs():
        fired = bool(detect(positive.encode("utf-8")))
        if fired != should_fire:
            print("the matcher %s on %s, a known %s assembled here for exactly "
                  "this question. Its verdict over the console therefore means "
                  "nothing (DP87)."
                  % ("fired" if fired else "stayed quiet", label,
                     "positive" if should_fire else "negative"))
            bad += 1
    if bad:
        print("\nFAILED: %d matcher proof(s) - this rule cannot vouch for its "
              "own reading." % bad)
        return 1

    derivation = is_derivation(spec)
    facts = {"Tree": DERIVATION if derivation else DEVELOPMENT}
    if derivation:
        print("OK: this tree is the derivation - it holds none of the "
              "directories the exclusion table withholds - so the documents "
              "whose numbers this rule compares are not in it, and no count "
              "here was asserted against one.")
        print("    What is therefore not measured in this tree: that the "
              "state document of the repository this one was derived from "
              "still states the right number of rules and checks, the "
              "right ledger mark, and the right published file count. "
              "Those are facts "
              "about a repository a derivation carries no evidence about, so "
              "the assertion belongs where that repository is.")
        print("    The matcher was proved either way rather than skipped: all "
              "%d positive and negative sheet(s) were put to it and every one "
              "answered as it should. A skip and a pass are the same green in "
              "a summary (DP182), which is why this is a pass that says what "
              "it did not do." % len(matcher_proofs()))
        for line in limits("the one state document a development tree "
                           "has, which this tree does not", None):
            print(line)
        return 0

    state = state_document(spec)
    ledger = ledger_document(spec)
    facts["Tree-reason"] = ", ".join(
        name for name, directory in withheld_roots(spec) if directory.is_dir())
    facts["State-document"] = "present" if state else "absent"
    facts["Ledger-document"] = "present" if ledger else "absent"
    rules = rule_headings()
    facts["Rules-measured"] = "absent" if rules is None else str(rules)
    facts["Checks-measured"] = str(len(check_scripts()))
    facts["Published-measured"] = str(len(published_files(spec)))

    highest, last = (ledger_marks(ledger) if ledger else (None, None))
    facts["Ledger-measured"] = "absent" if highest is None else str(highest)
    facts["Ledger-ordered"] = "yes" if highest is not None and highest == last \
        else "no"

    destination = getattr(spec, "DESTINATION", "")
    # The spec's filename, wherever it is named - not its repo-relative
    # path. DP191 narrowed this and gave a reason that inverts: an
    # over-wide matcher's failure is a false positive, which is red and
    # so loud by construction, and an over-narrow matcher's is a false
    # negative, which is silent by construction. The narrow form is loud
    # only where under-matching happens to empty the category, and it is
    # silent in the shape that decides it - a correct count anchored
    # here and a second, wrong one written with the short name. Owner
    # ruling, 2026-08-15, on a measured table: wide is right on three
    # shapes of four, and what it costs is the fourth, a passing mention
    # of this file beside a count nobody meant as this claim (DP192).
    instrument = SPEC_PATH.name
    claims = read_claims(state, destination, instrument) if state else []
    payload = sheet(facts, claims)
    findings = detect(payload.encode("utf-8"))

    where = state.relative_to(REPO_ROOT).as_posix() if state else "nowhere"
    if findings:
        for finding in findings:
            print(finding)
        print("\nThe document those lines are in: %s" % where)
        print("\nMeasured:")
        for line in payload.splitlines():
            print("  %s" % line)
        for line in limits("one document, %s" % where, claims):
            print(line)
        print("\nFAILED: %d number(s) the console states that nothing behind "
              "them agrees with." % len(findings))
        return 1

    by_category = {}
    for category, _, _, _ in claims:
        by_category[category] = by_category.get(category, 0) + 1
    print("OK: every count %s states was measured against the thing it "
          "counts - %s rule heading(s), %s check script(s), the ledger at "
          "DP%s, and %s file(s) the derivation publishes. %d claim(s) read "
          "in all: %s."
          % (where, facts["Rules-measured"], facts["Checks-measured"],
             facts["Ledger-measured"], facts["Published-measured"],
             len(claims),
             ", ".join("%d of %s" % (by_category[key], key)
                       for key in sorted(by_category))))
    print("    Not one of those numbers is written down in this check. The "
          "directories are derived from the derivation spec's exclusion "
          "table, the state document is the one carrying its directory's own "
          "name, and the ledger is the document with the most numbered "
          "decision rows - so this file names nothing the public tree "
          "withholds, which is the constraint that shaped it (DP169, Rule "
          "35).")
    for line in limits("one document, %s" % where, claims):
        print(line)
    print("    Each assertion had to find something: a category the console "
          "states nothing about is a finding, because a matcher that has "
          "stopped matching reports a clean console exactly as loudly as one "
          "that looked. All %d matcher proof(s), positive and negative, were "
          "fired before any of this was read." % len(matcher_proofs()))
    return 0


if __name__ == "__main__":
    sys.exit(main())
