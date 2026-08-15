"""Rule 3: english only.

Scans every git-tracked file (plus untracked files that are not
gitignored) and reports **every non-ASCII character** that is not one of
the few typographic marks named below. Sources stay ASCII; brand or
display CJK must be escaped (\\uXXXX in code and JSON, HTML entities in
pages).

**Why this is not a list of forbidden ranges any more (DP147).** It was:
twenty-seven named CJK and emoji ranges, and a raw character outside all
of them was invisible. That held for five milestones because the only
non-English language in this repository was Chinese, and Chinese is in
those ranges - so the rule appeared to work while what it actually
enforced was "no Chinese". Measured on `origin/main` at M4: rewrite the
shipped `fr.json` with its accents unescaped and it is a tracked file
carrying 161 raw non-ASCII characters, while this check printed *136
tracked file(s) are English-only* and exited 0. Red line five had nothing
behind it for every language whose letters are not CJK.

The ranges are still named, because a CJK hit should say "CJK unified
ideographs" rather than "a character outside ASCII" - but they are a
*label* now, not the test. The test is `ord(ch) > 127`.

**The permitted list is punctuation, and that is asserted rather than
intended.** Three marks are permitted, each named with its code point,
and `allowlist_problems()` refuses any entry whose Unicode general
category is a letter, a combining mark or a digit. A list nobody re-reads
is how this rule failed the first time; adding an e-acute to it goes red
on the category, not on somebody noticing. The permitted marks are also
counted and printed, so the OK line says what was let through instead of
only what was not.

This file is no longer exempt. It carries the ranges and the permitted
marks as escape sequences, so it is pure ASCII and passes its own scan -
an exemption it did not need was an exemption the next reader would have
had to take on trust.

archive/ is not exempt either: it is untracked entirely (DP40) and
therefore never reaches this scan in the first place.

A file that does not decode as UTF-8 is a finding, not a pass. Treating
a decode failure as "nothing to see here" is how a GBK-encoded Chinese
file scans clean: the bytes are there, this check just could not read
them, and the difference between "no CJK" and "could not look" is the
whole point of the rule.

Fails when: any tracked, non-exempt text file contains a raw non-ASCII
character that is not one of the permitted typographic marks - a CJK
ideograph, an emoji, a French accent, a Cyrillic letter, anything - or
fails to decode as UTF-8; or the permitted list itself grows an entry
that is a letter, a combining mark or a digit rather than punctuation.
"""
from __future__ import annotations

import os
import re
import subprocess
import sys
import unicodedata
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent

# Labels, not the test. A hit inside one of these says which script it is
# in; a hit outside all of them is still a hit.
NAMED_RANGES = [
    ("CJK unified ideographs", "[\u4e00-\u9fff]"),
    ("CJK extension A", "[\u3400-\u4dbf]"),
    ("Bopomofo", "[\u3100-\u312f]"),
    ("Bopomofo extended", "[\u31a0-\u31bf]"),
    ("Kangxi radicals", "[\u2f00-\u2fdf]"),
    ("CJK strokes", "[\u31c0-\u31ef]"),
    ("Hangul jamo", "[\u1100-\u11ff]"),
    ("Hangul compatibility jamo", "[\u3130-\u318f]"),
    ("Enclosed CJK letters and months", "[\u3200-\u32ff]"),
    ("Miscellaneous symbols and arrows", "[\u2b00-\u2bff]"),
    ("CJK extension G", "[\U00030000-\U0003134f]"),
    ("CJK extension B", "[\U00020000-\U0002a6df]"),
    ("CJK extension C-F", "[\U0002a700-\U0002ebef]"),
    ("CJK compatibility ideographs", "[\uf900-\ufaff]"),
    ("CJK symbols and punctuation", "[\u3000-\u303f]"),
    ("Halfwidth and fullwidth forms", "[\uff00-\uffef]"),
    ("Hiragana", "[\u3040-\u309f]"),
    ("Katakana", "[\u30a0-\u30ff]"),
    ("Hangul syllables", "[\uac00-\ud7af]"),
    ("Emoji: misc symbols and pictographs", "[\U0001f300-\U0001f5ff]"),
    ("Emoji: emoticons", "[\U0001f600-\U0001f64f]"),
    ("Emoji: transport and maps", "[\U0001f680-\U0001f6ff]"),
    ("Emoji: supplemental symbols", "[\U0001f700-\U0001f9ff]"),
    ("Emoji: extended-A", "[\U0001fa00-\U0001faff]"),
    ("Emoji: misc symbols", "[\u2600-\u26ff]"),
    ("Emoji: dingbats", "[\u2700-\u27bf]"),
    ("Emoji: regional indicators", "[\U0001f1e6-\U0001f1ff]"),
]
COMPILED = [(label, re.compile(pattern)) for label, pattern in NAMED_RANGES]

# The only raw non-ASCII characters a tracked file may carry. Typography,
# not language: each one is punctuation or a symbol in every text that
# uses it, and none of them is a letter in any alphabet. Written as escape
# sequences so this file stays ASCII and passes its own scan.
ALLOWED = {
    "\u00b7": "MIDDLE DOT - the board's and the summary screen's separator",
    "\u2192": "RIGHTWARDS ARROW - the method arrow in prose",
    "\u2026": "HORIZONTAL ELLIPSIS - what the width-aware clip appends",
}
# Categories a permitted mark may have. Deliberately excludes every letter
# category (Lu/Ll/Lt/Lm/Lo), every combining-mark category (Mn/Mc/Me) and
# every number category, because those are what a language is made of.
ALLOWED_CATEGORIES = ("Pc", "Pd", "Ps", "Pe", "Pi", "Pf", "Po",
                      "Sm", "Sc", "Sk", "So", "Zs")

SKIP_SUFFIXES = {
    ".png", ".jpg", ".jpeg", ".gif", ".webp", ".pdf", ".zip", ".gz",
    ".woff", ".woff2", ".ttf", ".eot", ".ico", ".mp3", ".mp4", ".wav",
}

# Nothing. This check used to exempt itself on the grounds that it names
# the forbidden ranges; it names them as escape sequences, so it never
# needed the exemption and no longer claims one.
EXEMPT_PATHS = set()


def allowlist_problems():
    """Findings for the permitted list itself.

    The list is the one part of this rule a future change could widen
    without widening anything visible, which is precisely how the rule
    failed before. So it is constrained by category rather than by review:
    a letter cannot be permitted here whatever anybody types, and the
    excuse typed beside it is printed back in the finding.
    """
    findings = []
    for char, why in sorted(ALLOWED.items()):
        category = unicodedata.category(char)
        if category not in ALLOWED_CATEGORIES:
            findings.append(
                "U+%04X (%s) is on the permitted list with category %s, which "
                "is not punctuation or a symbol. The permitted list is for "
                "typography; a letter, a combining mark or a digit on it is a "
                "language walking through red line five. Reason given: %s"
                % (ord(char), unicodedata.name(char, "unnamed"), category, why))
    return findings


def _label(ch):
    for label, regex in COMPILED:
        if regex.match(ch):
            return label
    return "non-ASCII"


def detect(payload):
    """Findings for one file's raw bytes.

    Pure, and takes bytes rather than text on purpose: a decode failure
    is one of the two shapes this rule refuses, and a detector handed a
    str could not see it.
    """
    try:
        text = payload.decode("utf-8")
    except UnicodeDecodeError as exc:
        return ["not valid UTF-8 (%s at byte %d); a non-UTF-8 encoding can hide "
                "a raw character from this scan" % (exc.reason, exc.start)]
    findings = []
    for lineno, line in enumerate(text.splitlines(), start=1):
        for ch in line:
            if ord(ch) < 128 or ch in ALLOWED:
                continue
            findings.append(
                "%d: %s: U+%04X %s: %s"
                % (lineno, _label(ch), ord(ch),
                   unicodedata.name(ch, "unnamed"), line.strip()[:120]))
            break
    return findings


def permitted_counts(text):
    """How many of each permitted mark one decoded file carries."""
    counts = {}
    for ch in text:
        if ch in ALLOWED:
            counts[ch] = counts.get(ch, 0) + 1
    return counts


def scanned_files():
    env = dict(os.environ)
    env["GIT_OPTIONAL_LOCKS"] = "0"
    out = subprocess.check_output(
        ["git", "ls-files", "-z", "--cached", "--others", "--exclude-standard"],
        cwd=str(REPO_ROOT),
        env=env,
    ).decode("utf-8")
    seen = set()
    paths = []
    for rel in out.split("\0"):
        if rel and rel not in seen:
            seen.add(rel)
            paths.append(rel)
    return paths


def scan(path):
    try:
        payload = path.read_bytes()
    except (FileNotFoundError, IsADirectoryError, OSError) as exc:
        return ["unreadable (%s)" % exc], {}
    findings = detect(payload)
    try:
        counts = permitted_counts(payload.decode("utf-8"))
    except UnicodeDecodeError:
        counts = {}
    return findings, counts


def main():
    bad = 0
    inspected = 0
    permitted = {}

    for finding in allowlist_problems():
        print("scripts/checks/english_only.py: %s" % finding)
        bad += 1

    for rel in scanned_files():
        if rel in EXEMPT_PATHS:
            continue
        path = REPO_ROOT / rel
        if path.suffix.lower() in SKIP_SUFFIXES or not path.is_file():
            continue
        inspected += 1
        findings, counts = scan(path)
        for finding in findings:
            print("%s:%s" % (rel, finding))
            bad += 1
        for ch, count in counts.items():
            permitted[ch] = permitted.get(ch, 0) + count

    if bad:
        print("\nFAILED: %d finding(s): a raw non-ASCII character, a file this "
              "scan could not decode, or a permitted mark that is not "
              "punctuation." % bad)
        print("Fix: rewrite in English and save as UTF-8; escape display CJK "
              "(\\uXXXX or entities).")
        return 1
    print("OK: %d tracked file(s) hold no raw non-ASCII character outside the "
          "%d permitted typographic mark(s) [%s], each of which is asserted to "
          "be punctuation or a symbol rather than a letter. The test is "
          "`ord(ch) > 127` and not a list of scripts: a French accent, a "
          "Cyrillic letter and a CJK ideograph are all findings, and only the "
          "last of those three was one before (DP147)."
          % (inspected, len(ALLOWED),
             ", ".join("U+%04X x%d" % (ord(ch), permitted.get(ch, 0))
                       for ch in sorted(ALLOWED))))
    return 0


if __name__ == "__main__":
    sys.exit(main())
