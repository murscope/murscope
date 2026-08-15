"""Rule 10: blocker extraction stays precise.

The state column claims a project is stuck. A false positive there is
worse than an empty column: it sends the user to a project that is fine,
and the second time that happens they stop believing the column - at
which point the most valuable thing this product does is gone.

Precision is three refusals, and this check pins all three:

1. **prose** that merely mentions a marker mid-sentence;
2. **notation legends** inside a code span or an HTML comment;
3. **an empty "Blocked" heading** - a heading is a bucket, and reporting
   the bucket invents a blocker out of a section title.

Three things are held here, and the split is DP21's.

**The shapes.** The synthetic cases in murscope/fixtures/ledger_cases.json
are run through the parser. They ship with the package too, so
`murscope selftest` runs the same cases on the user's machine against
the user's own vocabulary - the fixtures protect the maintainer here and
the user there. They are synthetic on purpose: the reference
implementation's cases are quoted verbatim from the owner's real
ledgers, and none of that text may enter this repository.

**The default packs.** The marker lists are pinned below as literals, so
changing a default marker without revisiting the fixtures goes red and
the diff shows a reviewer exactly which word moved. A hash would be
shorter and would tell the reviewer nothing.

**The precision predicate.** Every shipped marker is run through
markers.marker_problems(), the same function that warns a user about
their own extra_markers. An empty marker matches the start of every
line; a three-letter common word matches half of English.

Fails when: a case category in the shipped fixtures drops below its
floor; a shipped shape stops parsing, or starts parsing when it
must be refused; a section reads wrong; an owner claim is misread; a
default pack differs from the pin below; or a shipped marker cannot be
matched precisely.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from murscope import ledger, markers  # noqa: E402 - after the path insert

FIXTURES = REPO_ROOT / "murscope" / "fixtures" / "ledger_cases.json"

# The frozen default vocabulary. Ported from the pinned reference
# (ADR-0003): sixteen markers, seven of them CJK and written escaped so
# this file stays ASCII (Rule 3). French ships its pack now because a
# pack reads somebody's ledger; the French UI locale is M4.
PINNED_PACKS = {
    "en": {
        "markers": (
            "blocked",
            "blocker",
            "waiting on",
            "awaiting",
            "on hold",
            "needs decision",
            "pending decision",
            "todo(owner)",
            "unblock",
            ),
        "owner_markers": (
            "needs decision",
            "pending decision",
            "todo(owner)",
            ),
    },
    "zh": {
        "markers": (
            "\u5361\u70b9",
            "\u5361\u5728",
            "\u963b\u585e",
            "\u5f85\u62cd\u677f",
            "\u5f85\u786e\u8ba4",
            "\u7b49\u5f85",
            "\u7b49\u4f60",
            ),
        "owner_markers": (
            "\u5f85\u62cd\u677f",
            "\u5f85\u786e\u8ba4",
            "\u7b49\u4f60",
            ),
    },
    "fr": {
        "markers": (
            "bloque",
            "bloquee",
            "en attente de",
            "en attente",
            "en pause",
            "decision requise",
            "decision en attente",
            ),
        "owner_markers": (
            "decision requise",
            "decision en attente",
            "en attente de validation",
            ),
    },
}


def detect(payload):
    """Findings for a marker pack document: markers that cannot be precise.

    Pure. The predicate is the package's own, so a rule that protects
    the shipped packs here is the same rule that protects a user's
    extra_markers at runtime - one definition of "precise", not two.
    """
    try:
        document = json.loads(payload.decode("utf-8", errors="replace"))
    except ValueError as exc:
        return ["not readable as a marker pack (%s)." % exc]
    if not isinstance(document, dict):
        return ["a marker pack must be an object."]
    found = markers.marker_problems(document.get("markers", []), "pack")
    found.extend(markers.marker_problems(document.get("owner_markers", []),
                                         "pack owner_markers"))
    if not document.get("markers"):
        found.append("pack: no markers at all; the pack enables nothing.")
    return found


def check_pins():
    """Every shipped pack still says what this file says it says."""
    bad = 0
    for name in sorted(PINNED_PACKS):
        pinned = PINNED_PACKS[name]
        live_markers, live_owners, problems = markers.load_pack(name)
        for line in problems:
            print("  %s" % line)
            bad += 1
        for key, live in (("markers", live_markers),
                          ("owner_markers", live_owners)):
            want = list(pinned[key])
            if list(live) != want:
                added = sorted(set(live) - set(want))
                removed = sorted(set(want) - set(live))
                print("  pack %s: %s drifted from the pin. added=%s removed=%s"
                      % (name, key, added or "none", removed or "none"))
                print("    A default marker changed. Update PINNED_PACKS here "
                      "and revisit murscope/fixtures/ledger_cases.json in the "
                      "same change - the fixtures are what prove the new "
                      "vocabulary is still precise.")
                bad += 1
    return bad


# Floors per category, not a total. An audit deleted all six false-positive
# refusals - the half this check's own docstring calls the one that matters -
# padded the file with twenty markerless lines that cannot fail, regenerated
# the manifest, and the count went from 25 to 39. Green, and moving in the
# reassuring direction. A total is a number anybody can grow; a floor per
# category is a claim about coverage.
CASE_FLOORS = {
    "refusals": 6,
    "declarations": 6,
    "sections": 6,
    "owner_claims": 4,
    "not_owner_claims": 7,
    "wrapped": 11,
}


def check_floors(cases):
    """Every category keeps at least the coverage it had."""
    findings = []
    for name, floor in sorted(CASE_FLOORS.items()):
        found = len(cases.get(name) or [])
        if found < floor:
            findings.append(
                "murscope/fixtures/ledger_cases.json: %r holds %d case(s), "
                "below the floor of %d. Padding one category while another "
                "empties raises the total and lowers the coverage - and the "
                "refusals are the half that matters, because a false positive "
                "sends somebody to a project that is fine."
                % (name, found, floor))
    return findings


def check_shapes():
    """The three refusals, the declarations, the sections, the precedence."""
    try:
        cases = json.loads(FIXTURES.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        print("  cannot read %s: %s" % (FIXTURES, exc))
        return 1, 0

    vocabulary = markers.resolve("en", {"packs": markers.available()})
    aliases = markers.normalise(cases.get("aliases", []))
    bad = 0
    total = 0

    for case in cases.get("wrapped", []):
        total += 1
        lines = case["lines"]
        hit = ledger.blocker_line(lines[0], vocabulary.markers)
        got = None
        if hit:
            got = ledger.clip(" ".join(
                [hit[0]] + ledger.continuation(lines, 0, vocabulary.markers)))
        if case.get("ends_with_ellipsis"):
            # A trimmed declaration has to look trimmed. Without the mark a
            # reader cannot tell a short sentence from a cut one, and an
            # audit found one cut to the point of saying the opposite.
            if not (got or "").endswith("\u2026"):
                print("  a declaration past the cap was trimmed with no "
                      "ellipsis (%s):\n    got  %r"
                      % (case.get("why", "?"), got))
                bad += 1
        elif got != case["expect"]:
            print("  wrapped declaration read wrong (%s):\n    got  %r\n"
                  "    want %r" % (case.get("why", "?"), got, case["expect"]))
            bad += 1

    for finding in check_floors(cases):
        print("  " + finding)
        bad += 1

    for case in cases.get("declarations", []):
        total += 1
        found = ledger.blocker_line(case["line"], vocabulary.markers)
        got = found[0] if found else None
        if got != case["expect"]:
            print("  declaration missed or mangled (%s): %r -> %r, want %r"
                  % (case.get("shape", "?"), case["line"], got, case["expect"]))
            bad += 1

    for case in cases.get("refusals", []):
        total += 1
        found = ledger.blocker_line(case["line"], vocabulary.markers)
        if found is not None:
            print("  FALSE POSITIVE (%s): %r matched %r"
                  % (case.get("why", "prose"), case["line"], found[1]))
            bad += 1

    for case in cases.get("sections", []):
        total += 1
        got = ledger.section_first_item(case["lines"], case["start"])
        if got != case["expect"]:
            print("  section read wrong (%s): got %r, want %r"
                  % (case.get("why", "?"), got, case["expect"]))
            bad += 1

    for text in cases.get("owner_claims", []):
        total += 1
        if not ledger.waits_on_owner(text, vocabulary.owner_markers, aliases,
                                     vocabulary.markers):
            print("  should be read as naming the owner: %r" % text)
            bad += 1
    for text in cases.get("not_owner_claims", []):
        total += 1
        if ledger.waits_on_owner(text, vocabulary.owner_markers, aliases,
                                 vocabulary.markers):
            print("  a generic blocker must not claim the owner: %r" % text)
            bad += 1

    return bad, total


def check_precision():
    """The shipped packs pass the predicate users are held to."""
    bad = 0
    for name in sorted(PINNED_PACKS):
        path = REPO_ROOT / "murscope" / "markers" / ("%s.json" % name)
        try:
            payload = path.read_bytes()
        except OSError as exc:
            print("  pack %s: %s" % (name, exc))
            bad += 1
            continue
        for finding in detect(payload):
            print("  pack %s: %s" % (name, finding))
            bad += 1
    return bad


def main():
    bad = check_pins()
    shape_bad, total = check_shapes()
    bad += shape_bad + check_precision()

    if bad:
        print("\nFAILED: %d precision violation(s). The false positives are the "
              "ones that matter: a blocker reported on a project that is fine "
              "is how a user learns to ignore the column." % bad)
        return 1
    print("OK: %d synthetic case(s) parse as specified, %d default pack(s) match "
          "their pin, and every shipped marker can be matched precisely."
          % (total, len(PINNED_PACKS)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
