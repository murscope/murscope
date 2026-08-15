"""Rule 34: the brand name is never transliterated.

The product has two names and only two. In Latin letters it is
`murscope`. In Chinese it is two characters, and those two characters
are written **as themselves** - escaped, because Rule 3 keeps every
tracked file ASCII - and never spelled out in Latin letters.

A romanization is neither of the two names. It is a third one, and a
third name is how a product stops having a name at all: a reader who
meets the spelled-out form has no way to reach the Chinese one, no way
to reach `murscope`, and no reason to believe the three are the same
product. This is the same argument BRAND.md makes to a fork, applied
inward.

**Why this is generated and not a list of spellings (DP154).** The
obvious check is a list: the Hanyu Pinyin form, hyphenated, spaced,
camel-cased. That list is green until somebody types the next spelling,
and there are at least four romanization systems in ordinary use plus
tone marks in two notations - a list would have had to imagine all of
them, which is exactly the reviewed-by-eye table DP154 was about.

So the seed is the **syllables of the brand**, one entry per brand
character, written in a neutral (initial, final) key. Every romanization
system this file knows is a mapping from those keys to letters, and the
spelling space is **computed** from the two tables: systems x tone
notations x joiners x case. Teaching it a new system is one table entry;
a brand that gained a third character would need that character's
syllable and nothing else. Nothing here is a spelling somebody
remembered.

**What it cannot do, said rather than implied.** A *translation* - the
two characters rendered as English words - is not detectable by any
mechanism this file could carry, because the output is ordinary English.
That half of the rule is prose in CONTRIBUTING.md and is not claimed
here. Gwoyeu Romatzyh spells tone into the syllable itself rather than
marking it, and is not covered; it is named so the gap is a known one.

**And it has a floor.** A single Mandarin syllable romanizes to two or
three letters, and a few of those spellings are ordinary English words -
measured, by trimming the table to one entry and re-running: two shipped
fixtures matched. Two syllables joined are not English by accident, and
that is why this works at all. A brand that ever became one character
would need a different criterion, and `table_problems()` says so rather
than quietly reporting prose.

**This file cannot print an example of what it forbids**, for the reason
Rule 12 cannot name a telemetry vendor: it scans every tracked file
including itself. The tables below hold initials and finals, which are
fragments; no generated form appears literally in this source, and the
fixture is base64 like every other.

**The anchor (DP87).** If the brand's own code points are not in the
repository at all, this check is guarding nothing and every scan below
is vacuously clean. So their escaped form is looked for, and its absence
is a finding rather than a quiet pass.

Fails when: a tracked file or a commit message reachable from HEAD
carries a Latin-letter romanization of the brand's Chinese name, in any
system, tone notation, joiner or case the generator covers; or the
brand's escaped code points appear in no tracked file, so the rule
guards nothing; or the syllable table stops describing the brand it
claims to, or names an initial or a final some system cannot spell.
"""
from __future__ import annotations

import os
import re
import subprocess
import sys
import unicodedata
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent

# The brand's Chinese name, as escapes so this file is ASCII and passes
# Rule 3's scan like everything else. Its presence in the repository is
# asserted below rather than assumed.
BRAND_CJK = "\u77e5\u79cb"

# One entry per character of BRAND_CJK: (initial, final) in a neutral
# key. The keys are notation-agnostic labels - "-i" is the empty rime
# that follows a retroflex initial, "iou" is the full form of the
# diphthong Hanyu Pinyin abbreviates after an initial. Each system below
# spells them its own way.
BRAND_SYLLABLES = (
    ("zh", "-i"),
    ("q", "iou"),
)

# A romanization system is two mappings from the neutral keys to
# letters. Adding one is adding a row here; the spelling space widens
# without a single spelling being typed.
SYSTEMS = {
    "Hanyu Pinyin": (
        {"zh": "zh", "q": "q"},
        {"-i": "i", "iou": "iu"},
    ),
    "Wade-Giles": (
        {"zh": "ch", "q": "ch'"},
        {"-i": "ih", "iou": "iu"},
    ),
    "Yale": (
        {"zh": "j", "q": "ch"},
        {"-i": "r", "iou": "you"},
    ),
    "Tongyong": (
        {"zh": "jh", "q": "c"},
        {"-i": "ih", "iou": "iou"},
    ),
}

# Tone marks, as combining characters so this file stays ASCII. The
# generator lays each one over each vowel and keeps both the composed
# and the decomposed spelling, because a file may carry either.
TONE_MARKS = ("\u0304", "\u0301", "\u030c", "\u0300")
TONE_DIGITS = ("1", "2", "3", "4")
VOWELS = "aeiou"

# What may sit between two syllables. The empty string is in it, which
# is the ordinary joined spelling.
JOINERS = ("", " ", "\t", "-", "_", ".")

# A match may begin at the start of an alphabetic run or at a
# lower-to-upper transition, so a camel-cased form welded onto another
# word is still seen.
PREFIX = r"(?:(?<![A-Za-z])|(?<=[a-z])(?=[A-Z]))"
SUFFIX = r"(?:(?![A-Za-z])|(?=[A-Z]))"

SKIP_SUFFIXES = {
    ".png", ".jpg", ".jpeg", ".gif", ".webp", ".pdf", ".zip", ".gz",
    ".woff", ".woff2", ".ttf", ".eot", ".ico", ".mp3", ".mp4", ".wav",
}


def _toned(form):
    """Every tone-marked spelling of one bare syllable.

    Marks are laid over every vowel rather than only the one the tone
    rules would pick: over-generating costs nothing - none of these
    tokens is an English word - and under-generating is how a list
    fails.
    """
    out = set()
    for digit in TONE_DIGITS:
        out.add(form + digit)
    for index, char in enumerate(form):
        if char not in VOWELS:
            continue
        for mark in TONE_MARKS:
            decomposed = form[:index] + char + mark + form[index + 1:]
            out.add(decomposed)
            out.add(unicodedata.normalize("NFC", decomposed))
    return out


def syllable_forms(initial, final):
    """Every spelling of one brand syllable, across every system."""
    forms = set()
    for initials, finals in SYSTEMS.values():
        if initial not in initials or final not in finals:
            continue
        bare = initials[initial] + finals[final]
        for variant in (bare, bare.replace("'", "")):
            forms.add(variant)
            forms |= _toned(variant)
    return forms


def table_problems():
    """Findings about the seed itself, before anything is scanned.

    The table is what this rule is computed from, so it gets the
    treatment Rule 5's permitted-path table gets: a seed that has
    stopped describing the brand, or that names a key no system can
    spell, would generate a smaller space in silence.
    """
    findings = []
    if len(BRAND_SYLLABLES) < 2:
        findings.append(
            "the brand is described by %d syllable(s). A single Mandarin "
            "syllable romanizes to two or three letters, and some of those "
            "spellings are ordinary English words - this mechanism can tell "
            "a two-syllable name from English text and cannot tell a "
            "one-syllable one, so it would report findings on prose. Measured "
            "when a trimmed table was tried: two shipped fixtures matched. If "
            "the brand ever becomes one character, this check needs a "
            "different criterion, not a longer allowlist"
            % len(BRAND_SYLLABLES))
    if len(BRAND_SYLLABLES) != len(BRAND_CJK):
        findings.append(
            "the syllable table has %d entry/entries for a brand of %d "
            "character(s); it has stopped describing the name it is derived "
            "from, and a syllable nobody declared generates no spelling"
            % (len(BRAND_SYLLABLES), len(BRAND_CJK)))
    for position, (initial, final) in enumerate(BRAND_SYLLABLES, start=1):
        for system, (initials, finals) in sorted(SYSTEMS.items()):
            if initial not in initials:
                findings.append(
                    "syllable %d: %s cannot spell the initial %r, so it "
                    "contributes nothing for this syllable"
                    % (position, system, initial))
            if final not in finals:
                findings.append(
                    "syllable %d: %s cannot spell the final %r, so it "
                    "contributes nothing for this syllable"
                    % (position, system, final))
        if not syllable_forms(initial, final):
            findings.append(
                "syllable %d (%r, %r) generates no spelling at all"
                % (position, initial, final))
    return findings


def build_pattern():
    """One regex over the whole generated spelling space.

    Built per position and joined, rather than as an alternation of
    whole names: the cross terms fall out for free, so a spelling that
    mixes two systems is matched without being enumerated.
    """
    groups = []
    for initial, final in BRAND_SYLLABLES:
        forms = sorted(syllable_forms(initial, final), key=lambda f: (-len(f), f))
        groups.append("(?:%s)" % "|".join(re.escape(f) for f in forms))
    joiner = "(?:%s)" % "|".join(
        re.escape(j) for j in sorted(JOINERS, key=lambda j: (-len(j), j)))
    return re.compile(PREFIX + joiner.join(groups) + SUFFIX, re.IGNORECASE)


PATTERN = build_pattern()


def detect(payload):
    """Findings for one file's raw bytes: romanizations of the brand.

    Pure. Takes bytes because a tracked file is bytes; a file that does
    not decode is Rule 3's finding, not this one, so it is skipped here
    rather than reported twice.
    """
    try:
        text = payload.decode("utf-8")
    except UnicodeDecodeError:
        return []
    findings = []
    for lineno, line in enumerate(text.splitlines(), start=1):
        for match in PATTERN.finditer(line):
            findings.append(
                "%d: the brand's Chinese name spelled in Latin letters "
                "(%d character(s) at column %d). The product has two names: "
                "`murscope`, and the two characters themselves, escaped."
                % (lineno, len(match.group(0)), match.start() + 1))
            break
    return findings


def _git(args):
    env = dict(os.environ)
    env["GIT_OPTIONAL_LOCKS"] = "0"
    return subprocess.check_output(
        ["git"] + args, cwd=str(REPO_ROOT), env=env).decode("utf-8", "replace")


def scanned_files():
    out = _git(["ls-files", "-z", "--cached", "--others", "--exclude-standard"])
    seen = set()
    paths = []
    for rel in out.split("\0"):
        if rel and rel not in seen:
            seen.add(rel)
            paths.append(rel)
    return paths


def anchor_problems(paths):
    """The brand's escaped code points must be somewhere in the tree.

    Without this the whole check is an assertion over a product whose
    Chinese name has left the repository, which is green for the wrong
    reason (DP87).

    This file does not count towards it. It declares BRAND_CJK as
    escapes, so it satisfies its own anchor by construction - an anchor
    a check can hold up on its own evidence is the circle DP87 is about.
    The name has to be found in the product.
    """
    wanted = ["\\u%04x" % ord(ch) for ch in BRAND_CJK]
    myself = Path(__file__).resolve()
    for rel in paths:
        path = REPO_ROOT / rel
        if path.suffix.lower() in SKIP_SUFFIXES or not path.is_file():
            continue
        if path.resolve() == myself:
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        lowered = text.lower()
        if all(w in lowered for w in wanted):
            return [], rel
    return ["the brand's escaped code points (%s) appear in no tracked file, "
            "so this rule is guarding a name the repository no longer carries"
            % " ".join(wanted)], None


def commit_messages():
    """Every commit message reachable from HEAD, as (hash, text)."""
    out = _git(["log", "--format=%H%x1f%B%x1e", "HEAD"])
    records = []
    for chunk in out.split("\x1e"):
        chunk = chunk.strip("\n")
        if not chunk or "\x1f" not in chunk:
            continue
        sha, body = chunk.split("\x1f", 1)
        records.append((sha.strip(), body))
    return records


def main():
    bad = 0
    for finding in table_problems():
        print("scripts/checks/the_brand_name_is_never_transliterated.py: %s"
              % finding)
        bad += 1

    paths = scanned_files()
    anchor_findings, anchor_at = anchor_problems(paths)
    for finding in anchor_findings:
        print("scripts/checks/the_brand_name_is_never_transliterated.py: %s"
              % finding)
        bad += 1

    inspected = 0
    for rel in paths:
        path = REPO_ROOT / rel
        if path.suffix.lower() in SKIP_SUFFIXES or not path.is_file():
            continue
        try:
            payload = path.read_bytes()
        except OSError as exc:
            print("%s: unreadable (%s)" % (rel, exc))
            bad += 1
            continue
        inspected += 1
        for finding in detect(payload):
            print("%s:%s" % (rel, finding))
            bad += 1

    commits = commit_messages()
    for sha, body in commits:
        for finding in detect(body.encode("utf-8")):
            print("commit %s:%s" % (sha[:12], finding))
            bad += 1

    if bad:
        print("\nFAILED: %d finding(s): the brand's Chinese name spelled in "
              "Latin letters, or a seed that has stopped describing it." % bad)
        print("Fix: write `murscope`, or the two characters escaped. A "
              "romanization is a third name, and a product with three names "
              "has none.")
        return 1
    print("OK: %d tracked file(s) and %d commit message(s) carry no "
          "romanization of the brand's Chinese name, over a spelling space "
          "generated from %d syllable(s) x %d system(s) x %d joiner(s) - %s "
          "spellings per position, computed rather than listed (DP154). The "
          "escaped name itself is present, in %s."
          % (inspected, len(commits), len(BRAND_SYLLABLES), len(SYSTEMS),
             len(JOINERS),
             " and ".join(str(len(syllable_forms(i, f)))
                          for i, f in BRAND_SYLLABLES),
             anchor_at or "no tracked file"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
