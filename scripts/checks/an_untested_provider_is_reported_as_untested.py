"""Rule 23: an untested provider is reported as untested.

DP89, and it is a rule rather than a convention because of what it costs
to break:

> A provider that has never completed a live round trip is not delivered.
> It is written and it is honestly labelled as untested, with the reason.

Four adapters ship for the daily note. At M3's fourth stage exactly one of
them had ever spoken to a model. **Four rows in a table with no evidence
column read as four working providers** - the reader supplies the missing
claim themselves, and they are not wrong to, because a list of four things
under one heading is a list of four things of one kind. That is the
sentence this line does not get to make for free: Rule 1's whole position
is that a rule without a check is wall art, and a provider whose only
evidence is that the code looks right is the same thing in a different
hat.

So evidence is **data on the provider**, not prose in a commit message:
each adapter declares `EVIDENCE` and `EVIDENCE_NOTE`, passes both to
`register()` rather than leaving them to a default, and the command that
lists providers prints the value in a column of its own.

**The reason is required, and its shape is checked.** "unproven" with no
note is a label; "unproven, because no key for this vendor was available
and DP89 refuses a stub standing in for one" is something a reader can act
on. A note that merely repeats the label is refused.

**What walks into this (DP87), and what does not.** The live half loads
the real adapters, drives the real printer, and asserts that every
provider's name *and* its declared evidence value appear in what was
printed - so a printer that dropped the column goes red here rather than
in somebody's terminal a milestone later. It also counts the distinct
values declared and the distinct values printed and asserts they match,
which is the assertion that catches the failure this rule is named after:
several kinds collapsed into one.

What it cannot do is verify that a provider labelled `live` really has
completed a round trip. Nothing static can. What it enforces is that the
claim is made explicitly, per provider, with a reason - and the round trip
itself belongs in the acceptance report, which is where DP89 put it.

Fails when: an adapter that registers a note writer declares no
`EVIDENCE`, declares one outside the vocabulary, declares an empty or
label-repeating `EVIDENCE_NOTE`, or does not pass both to `register()`;
the registry does not carry evidence through to what it describes; the
provider listing omits a provider's name or its evidence value; the number
of distinct evidence values printed differs from the number declared; or
no adapter could be loaded at all.
"""
from __future__ import annotations

import ast
import contextlib
import io
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
EXTRAS_ROOT = REPO_ROOT / "extras"

# The only two answers there are. A third value would be a way to say
# "sort of", and there is no sort of: either a round trip happened or it
# did not.
VOCABULARY = ("live", "unproven")

# A note has to say more than the label does. Short enough that a real
# one-sentence reason clears it, long enough that "n/a" does not.
MINIMUM_NOTE = 40


def _assigned(tree, name):
    for node in tree.body:
        if not isinstance(node, ast.Assign):
            continue
        for target in node.targets:
            if isinstance(target, ast.Name) and target.id == name:
                try:
                    return ast.literal_eval(node.value)
                except (ValueError, SyntaxError):
                    return None
    return None


def _register_call(tree):
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        callee = getattr(node.func, "id", None) or getattr(node.func, "attr",
                                                           None)
        if callee == "register":
            return node
    return None


def _registers_writer(tree):
    call = _register_call(tree)
    if call is None:
        return False
    return any(keyword.arg == "writes" for keyword in call.keywords)


def detect(payload):
    """Findings about one adapter's source. Pure, so Rule 1 can feed it."""
    findings = []
    try:
        tree = ast.parse(payload)
    except SyntaxError as exc:
        return ["cannot be parsed (%s)" % exc]
    if not _registers_writer(tree):
        return []

    evidence = _assigned(tree, "EVIDENCE")
    note = _assigned(tree, "EVIDENCE_NOTE")

    if evidence is None:
        findings.append(
            "registers a note writer and declares no EVIDENCE. It will then "
            "be listed beside a provider that has completed a round trip, "
            "under one heading, and a reader will take the two for the same "
            "kind of thing.")
    elif evidence not in VOCABULARY:
        findings.append(
            "declares EVIDENCE = %r, which is not one of %s. There is no "
            "third answer: either a round trip happened or it did not."
            % (evidence, ", ".join(VOCABULARY)))

    if not note:
        findings.append(
            "declares no EVIDENCE_NOTE. A label with no reason is a label - "
            "DP89 asks for the reason, because \"unproven\" and \"unproven, "
            "no key for this vendor was available\" send a reader to two "
            "different places.")
    elif len(str(note).strip()) < MINIMUM_NOTE:
        findings.append(
            "declares an EVIDENCE_NOTE of %d character(s), which is too short "
            "to be a reason." % len(str(note).strip()))
    elif str(note).strip().lower().strip(".") in [v.lower() for v in VOCABULARY]:
        findings.append(
            "declares an EVIDENCE_NOTE that repeats the label and says "
            "nothing else.")

    call = _register_call(tree)
    passed = {keyword.arg for keyword in call.keywords} if call else set()
    for wanted in ("evidence", "evidence_note"):
        if wanted not in passed:
            findings.append(
                "does not pass %r to register(). A default would make every "
                "adapter that forgot look like one that answered, and the "
                "answer it would look like is somebody else's."
                % wanted)
    return findings


def adapter_modules():
    if not EXTRAS_ROOT.is_dir():
        return []
    found = []
    for path in sorted(EXTRAS_ROOT.glob("*/murscope/providers/*.py")):
        if path.name == "__init__.py":
            continue
        try:
            tree = ast.parse(path.read_bytes())
        except SyntaxError:
            found.append(path)
            continue
        if _registers_writer(tree):
            found.append(path)
    return found


def live_findings(modules):
    """Load the real adapters, drive the real printer, read what it said."""
    import importlib.util  # noqa: PLC0415 - only this half loads by path
    import os  # noqa: PLC0415 - only this half touches the environment
    import tempfile  # noqa: PLC0415 - same

    sys.path.insert(0, str(REPO_ROOT))
    try:
        from murscope import cli, registry
    except Exception as exc:
        return ["the command layer could not be imported (%s: %s), so the "
                "listing was never driven." % (type(exc).__name__, exc)], 0

    findings = []
    checked = 0
    registry.reset()
    declared = {}
    for path in modules:
        rel = path.relative_to(REPO_ROOT).as_posix()
        spec = importlib.util.spec_from_file_location(
            "murscope.providers.%s" % path.stem, path)
        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module
        try:
            spec.loader.exec_module(module)
        except Exception as exc:
            findings.append("%s: could not be loaded (%s: %s), so its "
                            "evidence was never read."
                            % (rel, type(exc).__name__, exc))
            continue
        declared[getattr(module, "PROVIDER", path.stem)] = getattr(
            module, "EVIDENCE", None)

    described = {row["name"]: row.get("evidence")
                 for row in registry.describe_all() if row.get("writes")}
    for name, value in sorted(declared.items()):
        if described.get(name) != value:
            findings.append(
                "%s declares EVIDENCE %r and the registry describes it as "
                "%r. What the listing prints comes from the registry, so a "
                "provider could declare one thing and be listed as another."
                % (name, value, described.get(name)))
        else:
            checked += 1

    if not described:
        return findings + [
            "no provider reached the registry as a note writer, so the "
            "listing below was driven over an empty set and would have "
            "printed nothing wrong."], checked

    with tempfile.TemporaryDirectory() as work:
        previous = os.environ.get("MURSCOPE_HOME")
        os.environ["MURSCOPE_HOME"] = work
        buffer = io.StringIO()
        try:
            with contextlib.redirect_stdout(buffer):
                cli._print_provider_table(Path(work))
        except Exception as exc:
            findings.append("the provider listing raised (%s: %s)"
                            % (type(exc).__name__, exc))
        finally:
            if previous is None:
                os.environ.pop("MURSCOPE_HOME", None)
            else:
                os.environ["MURSCOPE_HOME"] = previous
    printed = buffer.getvalue()

    for name, value in sorted(described.items()):
        if name not in printed:
            findings.append("the listing does not name %r at all." % name)
            continue
        if value not in printed:
            findings.append(
                "the listing names %r and never prints its evidence value "
                "%r. A list of four providers under one heading with no such "
                "column reads as four working providers." % (name, value))
            continue
        checked += 1

    # The assertion this rule is named after. Several kinds collapsed into
    # one is exactly what a table without the column does, and counting is
    # the only way to notice it: every individual row can be present while
    # the distinction between them is not.
    kinds_declared = {value for value in described.values() if value}
    kinds_printed = {kind for kind in kinds_declared if kind in printed}
    if kinds_declared != kinds_printed:
        findings.append(
            "%d distinct evidence value(s) are declared and %d appear in the "
            "listing (%s). The rows are there and the distinction between "
            "them is not."
            % (len(kinds_declared), len(kinds_printed),
               ", ".join(sorted(kinds_declared - kinds_printed))))
    else:
        checked += 1
    registry.reset()
    return findings, checked


def main():
    modules = adapter_modules()
    if not modules:
        print("FAILED: no note adapter was found under %s, so this check "
              "asserted nothing about how one is reported. Red rather than "
              "green." % EXTRAS_ROOT.relative_to(REPO_ROOT).as_posix())
        return 1

    bad = 0
    for path in modules:
        rel = path.relative_to(REPO_ROOT).as_posix()
        for finding in detect(path.read_bytes()):
            print("%s: %s" % (rel, finding))
            bad += 1

    live, checked = live_findings(modules)
    for finding in live:
        print("live: %s" % finding)
        bad += 1

    if bad:
        print("\nFAILED: %d way(s) in which an unproven provider could read "
              "as a working one." % bad)
        return 1
    print("OK: %d note adapter(s) each declare their evidence and a reason "
          "for it, and pass both to register() rather than inheriting a "
          "default. Live: %d assertion(s) - the registry carries every "
          "declaration through unchanged, the listing prints each provider "
          "and its evidence value, and every distinct value declared is a "
          "distinct value on the screen. Whether a provider labelled `live` "
          "really made a round trip is the acceptance report's to say; "
          "nothing static can, and this does not claim to."
          % (len(modules), checked))
    return 0


if __name__ == "__main__":
    sys.exit(main())
