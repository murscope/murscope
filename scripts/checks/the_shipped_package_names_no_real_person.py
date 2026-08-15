"""Rule 37: the shipped package names no real person.

DP19 said it in M0 - **no real person's name may appear anywhere in the
shipped package** - and for five milestones its whole enforcement was a
checkbox in the pull request template, ticked on every pull request this
repository merged. It was wrong the whole time: `murscope/ledger.py`
carried the owner's name in four lines of two docstrings, one of them
introduced by
"Measured on real data", which tells a reader the example came out of
the owner's own ledger. That shipped in every wheel.

This is the check. It is Rule 1 turned on this repository's own oldest
promise: a rule without a check is wall art, and this one had been
hanging on the wall since the first commit.

**The spelling space is generated, not listed.** Listing spellings is
how Rule 34 was nearly written and what DP161 refused: a list covers
what somebody thought of. The seed here is the copyright holder in
`LICENSE` - the one place a real name is correct and deliberately out of
scope - plus every author and committer name in this repository's own
history, which is where a *second* person's name would come from. From
each seed's word tokens the check generates every ordering and every
common joiner, so a family name written first and a family name written
last are the same finding, and so are the hyphenated, underscored,
dotted and run-together forms.

**Single tokens are never matched, deliberately.** A given name alone is
an ordinary word in some language and a matcher that fired on one would
be loosened within a week - and a loosened red line is worse than none.
What is matched is a whole name: two or more tokens, in any order, in
any joining. The cost of that is stated rather than hidden: a real
person's given name, alone, walks past this check.

**The matcher proves itself on a known positive, every run.** The same
generated spellings are run over `LICENSE`, where the holder's name
certainly is, and the check is red if they find nothing there. A scan
that reports "no name anywhere" is worth exactly as much as the proof
that it can find one, and this repository has been caught twice by a
guard that was searching for the wrong shape (DP147, DP161).

**Scope is what a stranger receives**, which is wider than the wheel:
every tracked file the public derivation publishes. `mgmt/` and `tasks/`
are out of scope because they are not published - a role table naming
the owner is correct in a management console.

**The exemption is a category, not a path, and it had to become one.**
It reads: the file named `LICENSE` at the root of a directory that
builds a distribution, where such a directory is one holding a
`pyproject.toml` with a `[project]` table, **discovered by walking the
published tree**. Written as the single path `LICENSE`, this rule made
the second distribution choose between shipping the copyright notice
MIT asks for and a green gate - `murscope-ai` shipped seven modules and
no notice, and adding one turned this check red. That is DP126's "a
permission for a path, not a command" failing in the other direction:
too narrow rather than too wide. Two roots exist today and a third is
covered the day somebody adds one, which is the property a list does
not have. The root `LICENSE` is still the seed, and widening the
exemption is not allowed to cost the rule its seeding - so a `LICENSE`
that stops naming the holder is still red.

Two limits worth writing down. A name inside a base64 fixture is not
seen, because the fixtures are data by construction (Rule 1). And the
seed is only as good as `LICENSE`: a holder written there in one script
and used in the package in another is a gap this cannot close.

Fails when: a whole name generated from the copyright holder or from
this repository's authorship appears in a published tracked file that
is not the `LICENSE` of a packaging root - a `NOTICE` beside a
`pyproject.toml` is not exempt, and neither is a `LICENSE` in a
directory that builds nothing; the seed carries fewer than two word
tokens, so the
generated space would be a common word or empty; or the generated
spellings find nothing in `LICENSE`, which means the matcher is looking
for the wrong shape.
"""
from __future__ import annotations

import importlib.util
import itertools
import os
import re
import subprocess
import sys
from pathlib import Path, PurePosixPath

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
LICENSE = REPO_ROOT / "LICENSE"
SPEC_PATH = REPO_ROOT / "scripts" / "public_tree.py"

# `Copyright (c) 2026 <holder>` and the variants a licence file uses.
COPYRIGHT = re.compile(
    r"^\s*copyright\s*(?:\(c\)|\u00a9|:)?\s*[0-9,\s-]*\s*(.+?)\s*$",
    re.IGNORECASE)

# A word token of a name. Two characters minimum: a one-letter initial
# generates spellings that are noise in every direction.
TOKEN = re.compile(r"[A-Za-z][A-Za-z'-]*")
MIN_TOKEN = 2
MIN_TOKENS = 2
# Four tokens is twenty-four orderings; beyond that the generated space
# grows factorially for no gain, so the tokens are truncated and the
# truncation is printed rather than being silent.
MAX_TOKENS = 4

# How a two-word name gets written when somebody is not writing prose.
JOINERS = ("", " ", "-", "_", ".")

SEED_MARK = "seed:"
SEPARATOR = "--"

# Trailing noise a licence line carries after the holder.
HOLDER_TRIM = re.compile(r"\s*(all rights reserved\.?)\s*$", re.IGNORECASE)


def git(args):
    """A read-only git call under Rule 5's locked environment, or None."""
    env = dict(os.environ)
    env["GIT_OPTIONAL_LOCKS"] = "0"
    try:
        proc = subprocess.run(
            ["git", "-C", str(REPO_ROOT)] + args,
            capture_output=True, text=True, timeout=60, env=env)
    except (subprocess.TimeoutExpired, OSError):
        return None
    if proc.returncode != 0:
        return None
    return proc.stdout


def tokens_of(name):
    """The word tokens of a name, lowercased, noise dropped."""
    found = [t.lower() for t in TOKEN.findall(name or "")]
    return [t for t in found if len(t) >= MIN_TOKEN]


def spellings(name):
    """Every way this whole name gets written, as lowercase strings.

    Generated from the tokens rather than enumerated. Orderings cover a
    family name written first or last; joiners cover the forms a name
    takes once it leaves prose - a directory, a handle, an identifier.
    """
    parts = tokens_of(name)[:MAX_TOKENS]
    if len(parts) < MIN_TOKENS:
        return set()
    out = set()
    for order in itertools.permutations(parts):
        for joiner in JOINERS:
            out.add(joiner.join(order))
    return out


def copyright_holders(text):
    """Every name a licence text names as its copyright holder."""
    names = []
    for line in text.splitlines():
        match = COPYRIGHT.match(line)
        if not match:
            continue
        holder = HOLDER_TRIM.sub("", match.group(1)).strip(" .,")
        if holder:
            names.append(holder)
    return names


def authorship():
    """Every distinct author and committer name in this history."""
    out = git(["log", "--all", "--format=%an%n%cn"])
    if out is None:
        return None
    return sorted({line.strip() for line in out.splitlines() if line.strip()})


def detect(payload):
    """Findings for a seeded document: whole names written in it.

    Pure, and seeded from the payload rather than from `LICENSE`, so the
    fixture can hand it a fabricated person. The payload is one or more
    `seed: <name>` lines, a `--` line, then the text to scan.

    A payload with no usable seed is a finding rather than a clean
    result. A matcher generated from nothing finds nothing and would
    report every file in the repository as clean (DP87).
    """
    text = payload.decode("utf-8", errors="replace")
    seeds = []
    body_start = 0
    lines = text.splitlines(True)
    for index, line in enumerate(lines):
        stripped = line.strip()
        if stripped.lower().startswith(SEED_MARK):
            seeds.append(stripped[len(SEED_MARK):].strip())
            continue
        if stripped == SEPARATOR:
            body_start = index + 1
            break
        body_start = index
        break

    findings = []
    space = set()
    for seed in seeds:
        found = spellings(seed)
        if not found:
            findings.append(
                "the seed %r carries fewer than %d word token(s) of %d or "
                "more characters. A single token is an ordinary word in some "
                "language, so the generated space would be noise or empty, "
                "and a matcher generated from nothing reports every file "
                "clean (DP87)." % (seed, MIN_TOKENS, MIN_TOKEN))
        space |= found
    if not space:
        findings.append(
            "no usable seed in this payload, so no spelling was generated "
            "and nothing could have been found. A scan with an empty needle "
            "is the empty-graph pass (DP87).")
        return findings

    for offset, line in enumerate(lines[body_start:], start=1):
        low = line.lower()
        for spelling in sorted(space):
            if spelling in low:
                findings.append(
                    "%d: writes a real person's whole name as %r. DP19 has "
                    "said since M0 that no real person's name appears in what "
                    "ships; `LICENSE` carries the copyright holder and that is "
                    "the only place." % (offset, spelling))
                break
    return findings


# A directory that builds a distribution: it holds a `pyproject.toml`
# with a `[project]` table. Line-anchored rather than parsed with a TOML
# reader, because `tomllib` arrived in 3.11 and this gate runs on 3.9 -
# a check that answers differently depending on the interpreter is its
# own defect, so it answers the same way on all three. What that does
# not cover is a `[project]` written inside a string literal; the
# discovered roots are printed for exactly that reason, so a surprising
# one is visible rather than inferred.
PROJECT_TABLE = re.compile(r"^\[project\]\s*$", re.MULTILINE)
PACKAGING_MANIFEST = "pyproject.toml"


def packaging_roots(files):
    """Every directory in the published tree that builds a distribution.

    Discovered by walking, never listed. Today this yields two - the
    repository root and the extras distribution - and a third would be
    included the day somebody adds one, which is the whole difference
    between a category and two paths written down. That difference is
    what DP126 named in the other direction, and Rule 37's exemption was
    on the wrong side of it: `LICENSE` was a path, so the second
    distribution could not carry the copyright notice MIT asks for
    without turning this rule red.
    """
    roots = set()
    for rel in files:
        if PurePosixPath(rel).name != PACKAGING_MANIFEST:
            continue
        try:
            text = (REPO_ROOT / rel).read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        if PROJECT_TABLE.search(text):
            roots.add(PurePosixPath(rel).parent.as_posix())
    return roots


def is_packaging_license(rel, roots):
    """Is this the `LICENSE` of a directory that builds a distribution?

    The name is exact and the location is a discovered packaging root.
    A `NOTICE` beside a `pyproject.toml` is not this, and a `LICENSE`
    somewhere that builds nothing is not this either - both are still
    scanned, because the exemption is for the one file a distribution
    must carry and not for a place a name may be written.
    """
    path = PurePosixPath(rel)
    return path.name == "LICENSE" and path.parent.as_posix() in roots


def published_files():
    """(paths, note) - every tracked file a stranger would receive."""
    listing = git(["ls-files", "-z"])
    if listing is None:
        return None, "git could not list the tracked files"
    tracked = [rel for rel in listing.split("\0") if rel]
    if not SPEC_PATH.is_file():
        return tracked, ("scripts/public_tree.py is absent, so every tracked "
                         "file was treated as published")
    spec = importlib.util.spec_from_file_location(
        "murscope_public_tree_names", str(SPEC_PATH))
    module = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(module)
    except BaseException:
        return tracked, ("scripts/public_tree.py does not import, so every "
                         "tracked file was treated as published")
    keep = [rel for rel in tracked if not module.excluded_reason(rel)]
    return keep, ""


def main():
    if not LICENSE.is_file():
        print("LICENSE is missing, so there is no copyright holder to seed "
              "the spelling space from and this check has no needle. A scan "
              "with nothing to look for reports every file clean (DP87).")
        print("FAILED: Rule 37 has no seed.")
        return 1

    license_text = LICENSE.read_text(encoding="utf-8")
    seeds = copyright_holders(license_text)
    if not seeds:
        print("LICENSE names no copyright holder that %s recognises, so no "
              "spelling could be generated." % COPYRIGHT.pattern)
        print("FAILED: Rule 37 has no seed.")
        return 1

    authors = authorship()
    if authors is None:
        print("note: git history is unreadable here, so the seed is the "
              "copyright holder alone. A second person's name would come "
              "from authorship.")
        authors = []
    seeds = sorted(set(seeds) | set(authors))

    usable = [seed for seed in seeds if spellings(seed)]
    if not usable:
        for seed in seeds:
            print("the seed %r carries fewer than %d word token(s); nothing "
                  "generated from it." % (seed, MIN_TOKENS))
        print("FAILED: Rule 37 generated no spelling from %d seed(s)."
              % len(seeds))
        return 1

    header = "".join("%s %s\n" % (SEED_MARK, seed) for seed in usable)
    header += "%s\n" % SEPARATOR

    # The known positive, every run. LICENSE is where the holder's name
    # certainly is, so a matcher that cannot find it there is looking for
    # the wrong shape and its silence everywhere else means nothing.
    proof = detect((header + license_text).encode("utf-8"))
    if not proof:
        print("the generated spellings find nothing in LICENSE, where the "
              "copyright holder's name certainly is. The matcher is looking "
              "for the wrong shape, so its silence over every other file is "
              "worth nothing (DP87).")
        print("FAILED: Rule 37's matcher failed its own known positive.")
        return 1

    files, note = published_files()
    if files is None:
        print("cannot list the published files: %s." % note)
        print("FAILED: Rule 37 needs the tree it scans.")
        return 1
    if note:
        print("note: %s." % note)

    roots = packaging_roots(files)
    bad = 0
    scanned = 0
    exempt = []
    space = set()
    for seed in usable:
        space |= spellings(seed)
    for rel in files:
        if is_packaging_license(rel, roots):
            exempt.append(rel)
            continue
        path = REPO_ROOT / rel
        if not path.is_file():
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        scanned += 1
        for finding in detect((header + text).encode("utf-8")):
            print("%s:%s" % (rel, finding))
            bad += 1

    if bad:
        print("\nFAILED: %d line(s) in the published tree name a real person."
              % bad)
        print("Fix: say what the example shows without the person. The "
              "technical point survives being depersonalised; the name does "
              "not survive being published.")
        return 1

    print("OK: %d spelling(s) generated from %d seed(s) - the copyright "
          "holder in LICENSE and %d name(s) in this repository's authorship - "
          "and every one of them was proved to fire on LICENSE before %d "
          "published file(s) were scanned and came back clean."
          % (len(space), len(usable), len(authors), scanned))
    print("    The exemption is a category rather than a path: the `LICENSE` "
          "at the root of a directory that builds a distribution. %d such "
          "root(s) were found by walking the published tree for a %s carrying "
          "a `[project]` table - %s - and %d file(s) were exempt: %s. A third "
          "distribution would be covered the day it exists, and the root "
          "LICENSE is still the seed. Written as a path, this rule made the "
          "second distribution choose between shipping the copyright notice "
          "MIT asks for and a green gate (DP126, in the other direction)."
          % (len(roots), PACKAGING_MANIFEST,
             ", ".join(sorted(r or "the repository root" for r in roots))
             or "none",
             len(exempt), ", ".join(sorted(exempt)) or "none"))
    print("    What this does not claim: a given name on its own is not "
          "matched, deliberately - a matcher that fired on one word would be "
          "loosened within a week - and a name inside a base64 fixture is "
          "data rather than text and is not read.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
