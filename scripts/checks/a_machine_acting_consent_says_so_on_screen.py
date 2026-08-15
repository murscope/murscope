"""Rule 28: a consent that authorises a machine says so on screen.

DP125 left this product with **two consents of different strength**. The
daily note's and the reading's are completed by a person on each send: a
screen is read, `yes` is typed, and the request happens in the next second
while that person is looking at the answer. The alert's authorises a
machine to act alone, from then on, at moments nobody is present. Both are
recorded the same way, in the same directory, by the same command.

**A user has to be able to see which one they are giving**, and that is a
claim about printed text rather than about code - so this check renders the
screens and reads them, exactly as a person would. It is judged on the
output of `murscope consent show`, not on the shape of the module that
produces it.

Four things are asserted, and each one is a way the distinction could
quietly stop being visible:

  1. **Every disclosure this build can show has a `who sends` line.** A
     table that acquired one without a line saying who performs the send
     would be a third kind of consent nobody was told the strength of.
  2. **The alert's line is not the note's line.** Two screens that
     describe the same act are two screens a reader cannot tell apart, and
     the whole of E8 is that they can.
  3. **The alert's line carries the owner's own phrasing**, `this one
     leaves while you are not here`, and says that murscope sends it on
     its own. That wording is the requirement rather than a suggestion
     (DP125), and a check that accepted any sentence at all would be
     asserting that some words are printed rather than that these are.
  4. **The note's and the reading's lines say that the person sends**, and
     do *not* claim the machine does. The distinction has two ends, and a
     check that only read the alert's screen would stay green through an
     edit that made the daily note claim to send itself.
  5. **A provider this build cannot ask gets no screen at all** (DP156).
     Which of the three disclosures applies is decided by what the
     provider *is*, and a provider is in the registry only once
     `config.toml` names it - so `consent show <an alerter> --to <url>`
     *before* enabling it used to fall through to the daily note's table:
     sixteen fields under the alerter's name, the note's fingerprint, and
     a `who sends` line saying a person performs each send. Every one of
     the four assertions above was satisfied, because each screen taken on
     its own was internally consistent; what was wrong was which screen
     was printed. Nothing could have been sent under a grant taken from
     it - the recorded fingerprint would have been the note's and every
     field would have been refused - so it was a screen of untruths rather
     than an unauthorised send, and this rule exists because that is
     enough. The screen's entire job is to let a person see which consent
     they are giving.

The screens are rendered against a throwaway MURSCOPE_HOME holding a
roster of two fabricated projects, one of them marked sensitive, so the
alert screen's "the ids an alert could name" block is exercised rather
than skipped. Nothing here reads the owner's workspace and nothing is
written outside the temporary directory.

What exercises it: `murscope/cli.py`'s `_WHO_SENDS` table and
`_print_disclosure`, live, through `consent show`. The detector's own
cases are in
scripts/checks/fixtures/a_machine_acting_consent_says_so_on_screen.txt -
a screen with no `who sends` line, and one whose alert screen describes a
send the user performs.

Fails when: a disclosure this build can show has no `who sends` line; the
alert's line is the same as another's; the alert's line does not carry the
owner's phrasing or does not say murscope sends it on its own; a
person-completed disclosure's line does not say the person sends it, or
claims murscope does; a provider the registry does not hold is shown a
disclosure table anyway, or `consent show` for one exits 0 as though it
had shown something; a registered provider is *not* shown its own table;
or the screens cannot be rendered at all.
"""
from __future__ import annotations

import io
import json
import os
import re
import sys
import tempfile
from contextlib import redirect_stdout
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent

# The line this rule is about, as it appears on screen.
MARKER = "who sends  :"

# The owner's phrasing, which DP125 records as the requirement rather than
# as an example. Matched with whitespace collapsed, so re-wrapping a
# paragraph to fit a column is free and rewriting the sentence is not -
# the same trade `murscope.disclosure.normalise` makes.
REQUIRED_PHRASE = "this one leaves while you are not here"

# What a machine-acting screen has to claim, and what a person-completed
# screen has to claim instead.
MACHINE_MARKS = ("murscope, on its own",)
PERSON_MARKS = ("you, once per send",)

# A roster with one ordinary project and one sensitive one, so the id
# listing on the alert screen has both branches to print. Fabricated
# names; nothing here looks at anybody's workspace.
ROSTER = {"projects": [
    {"id": "rule28-ordinary", "name": "ordinary", "root": "/nonexistent/a"},
    {"id": "rule28-withheld", "name": "withheld", "root": "/nonexistent/b",
     "sensitive": True},
]}


def normalise(text):
    return " ".join(str(text).split())


def who_sends_lines(screen):
    """{`this is` label: the `who sends` sentence} out of one rendered screen.

    Read out of the text rather than out of the table it came from. A
    check that imported `_WHO_SENDS` and compared its values would pass on
    a build where `_print_disclosure` had stopped printing it.
    """
    found = {}
    label = None
    current = None
    for line in screen.splitlines():
        stripped = line.strip()
        if stripped.startswith("this is    :"):
            label = stripped.split(":", 1)[1].strip()
            current = None
        elif stripped.startswith(MARKER):
            current = stripped.split(":", 1)[1].strip()
            if label is not None:
                found[label] = current
        elif current is not None and stripped and not stripped.endswith(":") \
                and ":" not in stripped.split(" ", 1)[0] and label in found:
            # A wrapped continuation of the same sentence. The terminal
            # does the wrapping, so a line that is plainly a continuation
            # belongs to the sentence above it.
            if stripped.startswith("on whose key") or stripped.startswith(
                    "proxy"):
                current = None
                continue
            found[label] = found[label] + " " + stripped
    return found


def detect(payload):
    """Findings for a rendered consent screen, or a bundle of them.

    Pure: text in, list of strings out. The payload is one or more screens
    concatenated, which is what `main()` hands it after rendering them.
    """
    screen = payload.decode("utf-8", errors="replace")
    lines = who_sends_lines(screen)
    findings = []
    if not lines:
        return ["no `%s` line appears in this screen at all. It is the line "
                "that says whether a person or a machine performs the send, "
                "and a consent screen without it does not say which of the "
                "two kinds of consent it is asking for (DP125)." % MARKER]

    machine = {label: text for label, text in lines.items()
               if any(mark in normalise(text) for mark in MACHINE_MARKS)}
    person = {label: text for label, text in lines.items()
              if any(mark in normalise(text) for mark in PERSON_MARKS)}

    for label, text in sorted(machine.items()):
        if REQUIRED_PHRASE not in normalise(text).lower():
            findings.append(
                "the `%s` screen says murscope sends it on its own and does "
                "not carry the owner's phrasing %r. DP125 records that "
                "wording as the requirement rather than as an example, "
                "because it is the sentence a reader cannot skim past."
                % (label, REQUIRED_PHRASE))
    for label, text in sorted(person.items()):
        if REQUIRED_PHRASE in normalise(text).lower():
            findings.append(
                "the `%s` screen says the person performs the send and also "
                "carries %r. Both cannot be true of one screen, and a reader "
                "cannot tell the two consents apart if one of them says "
                "both." % (label, REQUIRED_PHRASE))
    for label, text in sorted(lines.items()):
        if label not in machine and label not in person:
            findings.append(
                "the `%s` screen's `%s` line says neither that you send it "
                "each time nor that murscope sends it on its own: %r. Every "
                "disclosure this build can show has to declare which of the "
                "two it is." % (label, MARKER, normalise(text)[:120]))
    seen = {}
    for label, text in sorted(lines.items()):
        key = normalise(text)
        if key in seen:
            findings.append(
                "the `%s` and `%s` screens print the same `%s` sentence. Two "
                "screens describing the same act are two screens a reader "
                "cannot tell apart, and telling them apart is the whole of "
                "what this rule asserts." % (seen[key], label, MARKER))
        seen[key] = label
    return findings


def render_screens():
    """(text, problems). Every disclosure this build can show, rendered.

    One `murscope consent show` per disclosure, against a throwaway home.
    The provider name handed to each is the one that resolves to that
    table, and the resolution is the product's own - `disclosure_for()`
    asks the registry what a provider *is*, so this cannot accidentally
    render the same screen three times under three names.
    """
    sys.path.insert(0, str(REPO_ROOT))
    from murscope import cli, providers, registry  # noqa: PLC0415

    screens = []
    problems = []
    with tempfile.TemporaryDirectory() as home:
        (Path(home) / "roster.json").write_text(
            json.dumps(ROSTER, indent=2) + "\n", encoding="utf-8")
        previous = os.environ.get("MURSCOPE_HOME")
        os.environ["MURSCOPE_HOME"] = home
        try:
            registry.reset()
            providers.load(providers.available())
            # One stand-in per capability, registered here rather than
            # depended on from the extras distribution: the base wheel does
            # not ship a reader or an alerter, and a check that only ran
            # where `[ai]` was installed would be a check nobody runs.
            registry.register("rule28-note", "stand-in", writes=lambda *a: None,
                              destination="https://example.invalid")
            registry.register("rule28-reader", "stand-in", reads=lambda *a: None,
                              destination="https://example.invalid")
            registry.register("rule28-alerter", "stand-in",
                              alerts=lambda *a: None, destination="")
            for name in ("rule28-note", "rule28-reader", "rule28-alerter"):
                buffer = io.StringIO()
                try:
                    with redirect_stdout(buffer):
                        cli._print_disclosure(name, "https://example.invalid",
                                              Path(home))
                except Exception as exc:
                    problems.append(
                        "the consent screen for %r could not be rendered "
                        "(%s: %s), so nothing about its text was asserted."
                        % (name, type(exc).__name__, exc))
                    continue
                screens.append(buffer.getvalue())
        finally:
            registry.reset()
            if previous is None:
                os.environ.pop("MURSCOPE_HOME", None)
            else:
                os.environ["MURSCOPE_HOME"] = previous
    return "\n".join(screens), problems


def unaskable_provider_findings():
    """(findings, asserted) - a name the registry does not hold shows nothing.

    Both directions, because one alone proves nothing. A build that
    answered "not enabled" for everything would satisfy the refusal and
    would never show anybody a disclosure at all; a build that answered
    with a table for everything is the defect. So a registered alerter is
    asserted to get the alert's own table in the same breath, and the
    stand-ins are registered here rather than depended on from the extras
    distribution, for the reason `render_screens()` gives.
    """
    sys.path.insert(0, str(REPO_ROOT))
    from murscope import cli, providers, registry  # noqa: PLC0415

    findings = []
    asserted = 0
    absent = "rule28-never-registered"
    with tempfile.TemporaryDirectory() as home:
        previous = os.environ.get("MURSCOPE_HOME")
        os.environ["MURSCOPE_HOME"] = home
        try:
            registry.reset()
            providers.load(providers.available())
            registry.register("rule28-alerter-live", "stand-in",
                              alerts=lambda *a: None, destination="")

            label, shown, lines = cli.disclosure_for(absent, Path(home))
            if label is not None:
                findings.append(
                    "`consent show %s` names the %r table for a provider the "
                    "registry does not hold. Which disclosure applies is "
                    "decided by what the provider is, and nothing imported "
                    "it - so this screen is a guess printed as a fact, under "
                    "somebody else's name." % (absent, label))
            elif shown or lines:
                findings.append(
                    "`consent show %s` names no disclosure and still hands "
                    "back %d field(s) and %d line(s) to print."
                    % (absent, len(shown), len(lines)))
            else:
                asserted += 1

            buffer = io.StringIO()
            with redirect_stdout(buffer):
                digest = cli._print_disclosure(absent, "https://example.invalid",
                                               Path(home))
            screen = buffer.getvalue()
            if digest is not None:
                findings.append(
                    "a fingerprint was produced for %r, which the registry "
                    "does not hold. A consent is recorded against the exact "
                    "table the user was shown, and there was no table."
                    % absent)
            elif MARKER in screen:
                findings.append(
                    "the screen for %r carries a `%s` line, so it is telling "
                    "a user which of the two consents they are giving for a "
                    "provider nothing could ask." % (absent, MARKER))
            elif absent not in screen:
                findings.append(
                    "the screen for %r never names it, so a reader cannot "
                    "tell which provider murscope could not answer for: %r"
                    % (absent, " ".join(screen.split())[:120]))
            else:
                asserted += 1

            # The other end. Without this, refusing everything passes.
            live, _shown, _lines = cli.disclosure_for("rule28-alerter-live",
                                                      Path(home))
            if live != cli.ALERT_NOTICE:
                findings.append(
                    "a registered provider that can deliver an alert was "
                    "shown %r rather than %r. A build that answered \"not "
                    "enabled\" to everything would satisfy the refusal above "
                    "and show nobody anything." % (live, cli.ALERT_NOTICE))
            else:
                asserted += 1
        finally:
            registry.reset()
            if previous is None:
                os.environ.pop("MURSCOPE_HOME", None)
            else:
                os.environ["MURSCOPE_HOME"] = previous
    return findings, asserted


def main():
    if not (REPO_ROOT / "murscope" / "cli.py").exists():
        print("OK: murscope/cli.py not present yet; nothing to inspect.")
        return 0

    text, problems = render_screens()
    bad = len(problems)
    for line in problems:
        print(line)

    lines = who_sends_lines(text)
    # DP87, stated as a floor rather than assumed: a render that produced
    # no screens produces no findings either, and would print a green line
    # about nothing. The count has to match what the build says it can show.
    from murscope import cli  # noqa: PLC0415 - after render_screens set the path
    expected = len(cli.known_disclosures())
    if len(lines) < expected:
        print("this build can show %d disclosure(s) and only %d rendered "
              "screen(s) carried a `%s` line. A rule about printed text that "
              "read fewer screens than exist is a rule reporting on a subset "
              "it did not name (DP87)." % (expected, len(lines), MARKER))
        bad += 1

    for finding in detect(text.encode("utf-8")):
        print(finding)
        bad += 1

    unaskable, asserted = unaskable_provider_findings()
    for finding in unaskable:
        print(finding)
        bad += 1

    if bad:
        print("\nFAILED: %d finding(s) against Rule 28." % bad)
        return 1
    print("OK: %d consent screen(s) rendered, each carrying a distinct `%s` "
          "line; the machine-acting one says murscope sends it on its own and "
          "carries the owner's phrasing %r, and the %d person-completed one(s) "
          "say you perform each send and do not claim otherwise. %d further "
          "assertion(s): a provider the registry does not hold is named no "
          "table, produces no fingerprint and is said so by name, while a "
          "registered alerter still gets the alert's own."
          % (len(lines), MARKER, REQUIRED_PHRASE,
             sum(1 for text in lines.values()
                 if any(mark in normalise(text) for mark in PERSON_MARKS)),
             asserted))
    return 0


if __name__ == "__main__":
    sys.exit(main())
