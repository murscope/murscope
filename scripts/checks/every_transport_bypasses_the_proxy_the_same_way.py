"""Rule 25: every copy of the proxy bypass agrees, and the condition for
retiring them is re-measured rather than remembered.

DP111 made the route a decision rather than an inheritance: every
transport in the extras distribution builds its own opener with
`ProxyHandler({})`, so a payload consented to for a named destination
cannot be carried through a machine the consent screen never showed. Rule
19's static half already refuses a bare `urlopen()` and a module that
builds no proxy map, which is what stops a *new* transport shipping
without the bypass.

**What this adds is the thing Rule 19 cannot see: agreement.** The bypass
is written out once per transport, six times, byte for byte the same. The
acceptance window ran into the consequence directly - it edited
`network.py` to change the route and `murscope contributions` did not
change at all, because `github.py` carries its own copy. Six copies means
five of them can be corrected while one is not, and the one that is not
still opens a socket under a consent taken over a destination it does not
reach. Nothing about that is visible in a diff of the file somebody did
edit.

**Why they are copies and not one shared module, decided rather than
deferred.** A shared `_transport.py` was the obvious repair and it costs
something specific: `boundary.socket_capable` reads each provider module's
own imports, so the moment `urllib` moves out of them and into a sibling,
the provider-boundary step of `murscope selftest` prints "opens nothing"
beside every adapter that used to import it - rows that would each be
false in the only sense that table exists to report - and the board footer
that DP88 hangs on `reaching` is computed from the same survey. Trading a
duplication hazard for a promise-level surface that under-reports is the
wrong way round, and teaching the survey to follow relative imports is a
change to the guard the whole boundary rests on, not a tidy-up (DP116).

**The retirement condition is now measured on every run instead of being
remembered (DP148).** DP116 wrote it down - consolidate when
`boundary.socket_capable` can follow a relative import one level, so a
shared module is still reported as socket-capable on every adapter that
uses it - and a condition written in a paragraph is a condition whose
arrival nobody notices, which is DP81's shape exactly. `retirement()`
below hands the shipped survey two synthetic modules: one importing
`urllib.request` absolutely, one importing a sibling with `from
._transport import opener`. The absolute probe answering nothing is red,
because a survey that sees neither would report the condition unmet
forever while being broken. The relative probe answering *something* is
also red: the condition has arrived, and this check says so rather than
letting the copies outlive their reason.

**The first version of this check could be satisfied by a paragraph
(DP120).** It asked `ast.dump(node)` whether the string `ProxyHandler`
appeared, and `ast.dump` renders the docstring into that string. So all
six openers were changed to a bare `build_opener()` - which reads
`https_proxy` from the environment, the whole defect DP111 exists about -
with the docstrings untouched, and this file printed OK: six copies, byte
for byte identical, "each builds its opener with a ProxyHandler". Not one
`ProxyHandler` in any executable line. Delete only the sentence
`` `ProxyHandler({})` is an explicitly empty proxy map `` and leave that
same code, and it went red. **The third time this repository has had a
check that mentions the thing instead of testing it** - Rule 7 read a
word out of a comment, M2's truncation assertion counted dots instead of
sentences - and the first two are exactly what DP70 was written to stop,
so it happened inside a check written to hold that line. Every assertion
below now reads `ast.Call` nodes, which are not something a docstring can
contain.

**What walks into this check (DP87).** The extras provider modules, read
from the source tree, and every one of them that defines `_opener` must
agree with the others exactly - normalised for nothing but trailing
whitespace, because a bypass that differs by a character differs. That
text keeps its docstring on purpose: it is there to compare copies
against each other, and a comment is part of a correction. It is never
the thing a route assertion is asked about. Two floors make an empty
answer red rather than green: at least `MINIMUM_COPIES` modules must
define the function, and at least one of them must actually call
`ProxyHandler`. A run that found no copies would otherwise report that
all zero of them agree.

**What this still does not measure, stated rather than implied.** The two
calls are asserted inside `_opener`'s own executable code; that the proxy
map is the argument handed to `build_opener` is not checked here, so
`ProxyHandler({}); return build_opener()` inside one opener would pass
this rule. It would have to pass it in all six identically, and Rule 19's
live half drives the real transport. The dead-code route is closed: a
`ProxyHandler` call elsewhere in the module does not answer for `_opener`.

Fails when: two modules under extras/murscope-ai/murscope/providers/
define `_opener` with different bodies; fewer than six modules define it;
no copy calls ProxyHandler; a copy's `_opener` runs no `build_opener()`
call or no `ProxyHandler()` call; the extras provider directory is
missing; `boundary.socket_capable` reports nothing for an absolute
networking import, so the retirement probe measured a broken survey; or
it reports something for a relative one, which is DP116's retirement
condition arriving and the copies being due for consolidation.
"""
from __future__ import annotations

import ast
import hashlib
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
PROVIDERS_DIR = (REPO_ROOT / "extras" / "murscope-ai" / "murscope"
                 / "providers")

# The two probes DP116's retirement condition turns on. Source, never a
# file: the question is what the survey reads out of a module's text, and
# writing one to disk would put a synthetic provider in the directory the
# real survey walks.
ABSOLUTE_PROBE = "import urllib.request\n\n\ndef _opener():\n    return None\n"
RELATIVE_PROBE = ("from ._transport import opener\n\n\n"
                  "def _opener():\n    return opener()\n")

FUNCTION = "_opener"
PROXY_HANDLER = "ProxyHandler"
BUILD_OPENER = "build_opener"

# Every transport that ships in the extras distribution today. A floor, not
# a ceiling: a seventh may arrive, and it will have to agree with the six.
# Below the floor this check is measuring an empty set and says so.
MINIMUM_COPIES = 6


def _normalise(node, source):
    """The function as written, trailing whitespace removed, nothing else.

    Deliberately not the parse tree: two openers that differ only in a
    comment differ in what a reader is told about the route, and this
    check's whole subject is what happens when one copy is corrected and
    the others are not. A comment is part of the correction.
    """
    lines = source.splitlines()[node.lineno - 1:(node.end_lineno or node.lineno)]
    return "\n".join(line.rstrip() for line in lines).strip()


def _callee(call):
    if not isinstance(call, ast.Call):
        return None
    return getattr(call.func, "id", None) or getattr(call.func, "attr", None)


def calls_in(node):
    """The names this function actually calls. Executable code only.

    **DP120: a check must test the thing, not mention it.** This used to
    be `ast.dump(node)` searched for the string `ProxyHandler`, and
    `ast.dump` renders the docstring into that same string - so the
    sentence in `_opener`'s own docstring, `` `ProxyHandler({})` is an
    explicitly empty proxy map ``, satisfied the assertion. All six
    openers were changed to a bare `build_opener()`, which reads
    `https_proxy` from the environment, and this check printed OK: six
    copies, byte for byte identical, "each builds its opener with a
    ProxyHandler". Delete the sentence and leave the same executable code,
    and it went red. Prose was the load-bearing half.

    A `Call` node is not something a docstring can contain, so what comes
    back here is what the interpreter would run.
    """
    return set(filter(None, (_callee(sub) for sub in ast.walk(node)
                             if isinstance(sub, ast.Call))))


def openers(tree):
    """Every `_opener` definition in a module, in source order."""
    return [node for node in ast.walk(tree)
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
            and node.name == FUNCTION]


def detect(payload):
    """Findings for one provider module's source: a bypass that is not one.

    Pure - source in, findings out. Agreement between modules is not
    something one module's source can answer, so that half lives in
    `main()`; what this answers is whether an `_opener` here builds an
    opener with a proxy map at all - in code that runs, not in a
    docstring that describes code that runs (DP120).
    """
    source = payload.decode("utf-8", errors="replace")
    try:
        tree = ast.parse(source)
    except SyntaxError as exc:
        return ["cannot parse (%s), so its route cannot be read." % exc]

    findings = []
    for node in openers(tree):
        called = calls_in(node)
        if BUILD_OPENER not in called:
            findings.append(
                "%d: %s() calls no %s(), so every request from this module "
                "goes out through whatever `urllib` inherited from the "
                "environment." % (node.lineno, FUNCTION, BUILD_OPENER))
        if PROXY_HANDLER not in called:
            findings.append(
                "%d: %s() calls no %s(), so the route is inherited rather "
                "than decided. A docstring naming one is not one (DP120). "
                "DP111: a payload consented to for a named destination must "
                "not pass through a machine the consent screen never showed."
                % (node.lineno, FUNCTION, PROXY_HANDLER))
    return findings


def copies():
    """{module name: (normalised source, digest, routed)} for every `_opener`.

    `routed` is read off the parse tree, not off the text the digest runs
    over: the text is there to compare copies against each other, and it
    holds the docstring on purpose (a comment is part of a correction).
    Asking that same text whether a proxy map exists is DP120 - the
    question would be answered by the paragraph describing the answer.
    """
    found = {}
    for path in sorted(PROVIDERS_DIR.glob("*.py")):
        source = path.read_text(encoding="utf-8")
        try:
            tree = ast.parse(source)
        except SyntaxError:
            continue
        for node in tree.body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) \
                    and node.name == FUNCTION:
                text = _normalise(node, source)
                found[path.name] = (
                    text, hashlib.sha256(text.encode("utf-8")).hexdigest(),
                    PROXY_HANDLER in calls_in(node))
    return found


def retirement():
    """(findings, note) for DP116's retirement condition, measured now.

    Two probes, and the first one is the floor. If the shipped survey
    cannot see `import urllib.request` then it cannot see anything, and
    "the relative probe found nothing" would mean the instrument is
    broken rather than the condition unmet - which is the shape DP87
    names: a guard whose window does not contain the thing it watches.

    The second probe is the condition itself. While it answers nothing,
    a shared `_transport` module is invisible to the boundary survey and
    the copies are the cheaper of two wrong things. The day it answers,
    that stops being true and this check goes red on it, because the one
    failure DP81 exists to make visible is a condition arriving with
    nobody watching for it.
    """
    from murscope import boundary  # noqa: PLC0415 - only this probe needs it

    absolute = boundary.socket_capable(ABSOLUTE_PROBE)
    relative = boundary.socket_capable(RELATIVE_PROBE)
    findings = []
    if not absolute:
        findings.append(
            "boundary.socket_capable() reports nothing for a module whose "
            "first line is `import urllib.request`. The retirement probe below "
            "is then measuring a broken survey, and its silence about the "
            "relative import would mean nothing at all.")
    if relative:
        findings.append(
            "boundary.socket_capable() now follows a relative import: it "
            "reports %s for `from ._transport import opener`. That is DP116's "
            "retirement condition, and it has arrived. A shared transport "
            "module would now be reported as socket-capable on every adapter "
            "that imports it, so the reason the copies exist is gone - "
            "consolidate them and retire this floor. Left alone, 'keep them' "
            "becomes 'nobody looks again', which is what DP81 is about."
            % ", ".join(relative))
    return findings, (
        "DP116's retirement condition is re-measured here rather than "
        "remembered: the survey answers %s for an absolute networking import "
        "and nothing for a relative one, so a shared module would still be "
        "reported as opening nothing and the copies remain the cheaper of two "
        "wrong things. This line goes red on the day that changes."
        % ", ".join(absolute or ["nothing"]))


def main():
    if not PROVIDERS_DIR.is_dir():
        print("FAILED: %s is missing, so there is no transport to read."
              % PROVIDERS_DIR.relative_to(REPO_ROOT).as_posix())
        return 1

    findings = []
    for path in sorted(PROVIDERS_DIR.glob("*.py")):
        for finding in detect(path.read_bytes()):
            findings.append("%s:%s" % (path.name, finding))

    found = copies()
    if len(found) < MINIMUM_COPIES:
        findings.append(
            "%d module(s) under %s define %s() and %d is the floor. This "
            "check's subject is whether the copies agree; with fewer than the "
            "known set it would be certifying agreement across a smaller "
            "group than ships, which is a green result for a measurement that "
            "did not happen."
            % (len(found), PROVIDERS_DIR.relative_to(REPO_ROOT).as_posix(),
               FUNCTION, MINIMUM_COPIES))
    if found and not any(routed for _t, _d, routed in found.values()):
        findings.append(
            "not one of the %d copies calls %s. They agree, and they agree on "
            "not bypassing the proxy." % (len(found), PROXY_HANDLER))

    retirement_findings, retirement_note = retirement()
    findings.extend(retirement_findings)

    digests = {}
    for name, (_text, digest, _routed) in sorted(found.items()):
        digests.setdefault(digest, []).append(name)
    if len(digests) > 1:
        groups = sorted(digests.values(), key=len, reverse=True)
        findings.append(
            "the %d copies of %s() are not identical: %s. One of these was "
            "corrected and the others were not, and the ones that were not "
            "still open a socket under a consent taken over a destination "
            "they do not reach. Change all of them or none."
            % (len(found), FUNCTION,
               " | ".join("[%s]" % ", ".join(group) for group in groups)))

    if findings:
        for finding in findings:
            print(finding)
        print("\nFAILED: %d finding(s) against the proxy bypass."
              % len(findings))
        return 1

    digest = next(iter(digests))
    print("OK: %d transport module(s) under %s define %s(), all %d byte for "
          "byte identical (sha256 %s), and in each one the executable code of "
          "that function calls both %s() and %s() - read off the parse tree as "
          "call nodes, because a docstring that names a proxy map is not one "
          "(DP120). "
          "The duplication is deliberate and recorded (DP116): moving it to a "
          "shared module would take `urllib` out of every adapter's own "
          "imports, and `boundary.socket_capable` reads exactly those - the "
          "provider-boundary step of the selftest and the board footer would "
          "then report %d socket-capable adapters as opening nothing."
          % (len(found), PROVIDERS_DIR.relative_to(REPO_ROOT).as_posix(),
             FUNCTION, len(found), digest[:12], BUILD_OPENER, PROXY_HANDLER,
             len(found)))
    print("    %s" % retirement_note)
    return 0


if __name__ == "__main__":
    sys.exit(main())
