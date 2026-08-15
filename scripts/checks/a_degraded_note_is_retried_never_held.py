"""Rule 21: a degraded note is retried, never held.

DP49, stated as the thing that happened rather than as a principle:

> An honest fallback that is never re-checked is a failure that has been
> silently timestamped.

Upstream, a provider's quota ran out, the run wrote a degraded result into
the day's slot, and the scheduler compared **dates**. The quota came back
an hour later and the degraded result held the day, because something was
already recorded for today. From outside that is indistinguishable from
success: a file exists, it is stamped with today, and the only way to
learn it is wrong is to open it. Which is why this needs a check and not a
comment.

**The static half** reads `murscope/daily.py` and refuses four shapes:

1. a scheduler that never looks at what is *in* the slot - the date-only
   comparison, which is the defect itself;
2. a scheduler that never consults the moment a degraded result becomes
   worth asking about again;
3. a scheduler that cannot answer both ways. One that always attempts
   satisfies "a degraded result is retried" completely and has no slot at
   all: it would re-send on every invocation, on the user's own paid key;
4. a degraded record written without a retry moment, and a backoff with no
   ceiling. A backoff is a hold with a timer on it, so an unbounded one
   rebuilds the upstream failure wearing a preference.

**The live half** runs the real module and drives the whole loop: a
degraded slot is *constructed by the product's own recorder*, written and
read back through the product's own files, the cause is cleared, and the
next round is observed to attempt rather than to hold. Then the reverse:
an ok slot is observed *not* to be attempted, because a rule that only
ever says yes is not a rule.

**What walks into this (DP87).** The degraded state is not a hand-built
dict. It is whatever `record_degraded()` produces, put on disk by
`write_slot()` and read back by `read_slot()`, and the check asserts that
what came back really is degraded and really carries a retry moment before
it draws any conclusion from it - because a fixture that was never
degraded would satisfy "a degraded slot is retried" without the scheduler
having a degraded slot to look at. That is the shape that cost M2 four
instances and this milestone two more.

**What this check does not cover, said rather than left to be assumed.**
It measures when a request is made, not what the request does. No socket
is opened here and no adapter is driven: the transports are Rules 18, 19
and 22's, and the live round trips are the acceptance report's.

Fails when: `should_attempt` is missing, never reads the slot's status,
never consults its retry moment, or cannot return both answers;
`record_degraded` writes no retry moment; the backoff has no ceiling; a
degraded slot whose moment has passed is not attempted; a degraded slot
whose moment has not passed is attempted; an ok slot is attempted; a slot
round-tripped through the product's own writer does not come back
degraded; or `murscope/daily.py` cannot be imported at all.
"""
from __future__ import annotations

import ast
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
DAILY = REPO_ROOT / "murscope" / "daily.py"

SCHEDULER = "should_attempt"
RECORDER = "record_degraded"
BACKOFF = "resolve_backoff"

# What the scheduler has to have looked at. `status` is the defect's whole
# story - the upstream scheduler knew a record existed and not what it
# was - and `retry_after` is the moment that keeps a retry from becoming
# a busy loop.
MUST_CONSULT = ("status", "retry_after")


def _functions(tree):
    return {node.name: node for node in ast.walk(tree)
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))}


def _names(node):
    """Every identifier and attribute name inside a node."""
    found = set()
    for child in ast.walk(node):
        if isinstance(child, ast.Attribute):
            found.add(child.attr)
        elif isinstance(child, ast.Name):
            found.add(child.id)
        elif isinstance(child, ast.Constant) and isinstance(child.value, str):
            found.add(child.value)
        elif isinstance(child, ast.keyword) and child.arg:
            found.add(child.arg)
    return found


def _answers(node):
    """{True, False} - which verdicts this function can return.

    A verdict is the first element of the returned tuple, because the
    scheduler returns `(attempt, why)`: the reason is printed whichever
    way it goes, so that a refusal is never invisible.
    """
    found = set()
    for child in ast.walk(node):
        if not isinstance(child, ast.Return) or child.value is None:
            continue
        value = child.value
        if isinstance(value, ast.Tuple) and value.elts:
            value = value.elts[0]
        if isinstance(value, ast.Constant) and isinstance(value.value, bool):
            found.add(value.value)
    return found


def _has_ceiling(tree):
    """Is the backoff compared against a named maximum anywhere?

    A literal would do the job and is refused on purpose: a ceiling nobody
    named is a ceiling nobody can find when they raise the default.
    """
    for node in ast.walk(tree):
        if isinstance(node, ast.Compare):
            for name in _names(node):
                if name.startswith("MAX_"):
                    return True
    return False


def detect(payload):
    """Findings about a scheduler module. Pure, so Rule 1 can feed it."""
    findings = []
    try:
        tree = ast.parse(payload)
    except SyntaxError as exc:
        return ["cannot be parsed (%s)" % exc]

    functions = _functions(tree)

    scheduler = functions.get(SCHEDULER)
    if scheduler is None:
        findings.append(
            "no %s(): there is nothing deciding whether a round happens, so "
            "whatever calls this decides for itself - which is where a "
            "date-only comparison lives." % SCHEDULER)
    else:
        consulted = _names(scheduler)
        for wanted in MUST_CONSULT:
            if wanted not in consulted:
                findings.append(
                    "%s() never looks at %r. A scheduler that knows a record "
                    "exists and not what it is, is the upstream defect: the "
                    "quota came back and the degraded result held the day."
                    % (SCHEDULER, wanted))
        answers = _answers(scheduler)
        if answers != {True, False}:
            findings.append(
                "%s() can only answer %s. One that always attempts satisfies "
                "\"a degraded result is retried\" and has no slot at all; one "
                "that never attempts has no retry."
                % (SCHEDULER, sorted(answers) or "nothing"))

    recorder = functions.get(RECORDER)
    if recorder is None:
        findings.append(
            "no %s(): a failure with no recorded shape cannot carry a retry "
            "policy, and the next round has nothing to read." % RECORDER)
    elif "retry_after" not in _names(recorder):
        findings.append(
            "%s() records no retry moment. A degraded result that does not "
            "say when it becomes worth asking again is a hold with no end."
            % RECORDER)

    if BACKOFF not in functions:
        findings.append(
            "no %s(): a backoff that cannot be resolved cannot be bounded, "
            "and an unbounded one is the upstream failure wearing a "
            "preference." % BACKOFF)
    elif not _has_ceiling(tree):
        findings.append(
            "the backoff is compared against no MAX_ constant. A backoff is "
            "a hold with a timer on it: without a ceiling, a config file can "
            "rebuild a degraded result occupying the whole day and it will "
            "look like a setting.")
    return findings


def live_findings():
    """Drive the real module through the whole loop. Returns (findings, n)."""
    sys.path.insert(0, str(REPO_ROOT))
    try:
        from murscope import daily
    except Exception as exc:
        return ["murscope.daily could not be imported (%s: %s), so the "
                "scheduler was never run. This check is red rather than "
                "green." % (type(exc).__name__, exc)], 0

    import os  # noqa: PLC0415 - only this half touches the environment
    import tempfile  # noqa: PLC0415 - same

    findings = []
    checked = 0
    now = datetime(2026, 8, 13, 9, 0, 0, tzinfo=timezone.utc)
    day = daily.day_key(now)

    with tempfile.TemporaryDirectory() as work:
        previous = os.environ.get("MURSCOPE_HOME")
        os.environ["MURSCOPE_HOME"] = work
        try:
            home = Path(work)

            # The degraded state is the product's own, not a dict this
            # check invented: recorded by `record_degraded`, put on disk by
            # `write_slot`, read back by `read_slot`. Everything below is
            # asserted about *that* object, so the scheduler is looking at
            # the shape a real failure leaves behind.
            written = daily.record_degraded(
                day, now, "the provider's quota was exhausted",
                provider="gate", destination="https://example.invalid",
                backoff=60)
            daily.write_slot(written, home)
            slot, problems = daily.read_slot(day, home)
            for line in problems:
                findings.append("the slot this check wrote could not be read "
                                "back: %s" % line)
            if slot is None:
                return findings + [
                    "nothing came back from the product's own reader, so "
                    "every assertion below would have been made about "
                    "nothing."], checked
            # DP87, before any conclusion is drawn from it.
            if slot.status != daily.DEGRADED:
                findings.append(
                    "the slot round-tripped through the product's own writer "
                    "came back as %r, not %r. Every assertion below would "
                    "have been testing the retry of something that was never "
                    "degraded." % (slot.status, daily.DEGRADED))
            if not slot.retry_after:
                findings.append(
                    "the round-tripped degraded slot carries no retry moment, "
                    "so 'its moment has passed' and 'its moment has not' are "
                    "the same case and only one of them is being measured.")
            checked += 1

            # The cause is still present and the moment has not come.
            attempt, why = daily.should_attempt(slot, now + timedelta(seconds=1))
            if attempt:
                findings.append(
                    "a degraded slot recorded one second ago was attempted "
                    "again immediately (%s). The backoff exists so that a "
                    "provider having a bad minute is not asked sixty times "
                    "in it." % why)
            else:
                checked += 1

            # The cause has cleared and the moment has passed. This is the
            # upstream failure, and the whole reason for the rule.
            attempt, why = daily.should_attempt(slot, now + timedelta(seconds=61))
            if not attempt:
                findings.append(
                    "a degraded slot was not retried after its moment passed "
                    "(%s). That is the upstream failure exactly: the quota "
                    "recovered and the degraded result held the day, and from "
                    "outside it looked like success." % why)
            else:
                checked += 1

            # A degraded record that forgot to say when. Retryable, because
            # a record that forgot is not a record that said never.
            forgetful = daily.Note(day, daily.DEGRADED, daily.stamp(now),
                                   reason="no moment recorded")
            if not daily.should_attempt(forgetful, now)[0]:
                findings.append(
                    "a degraded slot carrying no retry moment was treated as "
                    "a hold. A record that forgot to say when is not a record "
                    "that said never.")
            else:
                checked += 1

            # The other direction. Without this, a scheduler that always
            # attempts passes everything above.
            good = daily.record_ok(day, now, "gate", "https://example.invalid",
                                   "a-model", "a-digest", "a note")
            daily.write_slot(good, home)
            done, problems = daily.read_slot(day, home)
            if done is None or done.status != daily.OK:
                findings.append("an ok slot did not round-trip; the negative "
                                "case below is being made against nothing.")
            elif daily.should_attempt(done, now + timedelta(days=1))[0]:
                findings.append(
                    "a note already in hand was fetched again. A scheduler "
                    "that always attempts satisfies every assertion above "
                    "and re-sends the payload on the user's own paid key "
                    "every time the command is run.")
            else:
                checked += 1

            # Nothing recorded is an open slot, not a hold.
            if not daily.should_attempt(None, now)[0]:
                findings.append("an empty slot was treated as a hold, so the "
                                "first round of a day would never happen.")
            else:
                checked += 1

            # The ceiling, exercised rather than read off the source.
            seconds, complaints = daily.resolve_backoff(
                daily.MAX_RETRY_AFTER_SECONDS * 10)
            if seconds > daily.MAX_RETRY_AFTER_SECONDS:
                findings.append(
                    "a configured backoff of %d was accepted; the ceiling is "
                    "%d and an unbounded backoff is the upstream failure "
                    "wearing a preference."
                    % (seconds, daily.MAX_RETRY_AFTER_SECONDS))
            elif not complaints:
                findings.append(
                    "an over-large backoff was clamped silently. A setting "
                    "that was quietly ignored is a setting the user believes "
                    "is in effect.")
            else:
                checked += 1
        finally:
            if previous is None:
                os.environ.pop("MURSCOPE_HOME", None)
            else:
                os.environ["MURSCOPE_HOME"] = previous
    return findings, checked


def main():
    if not DAILY.is_file():
        print("FAILED: %s is missing, so the retry policy has nothing to "
              "live in and this check cannot answer its question."
              % DAILY.relative_to(REPO_ROOT).as_posix())
        return 1

    bad = 0
    rel = DAILY.relative_to(REPO_ROOT).as_posix()
    for finding in detect(DAILY.read_bytes()):
        print("%s: %s" % (rel, finding))
        bad += 1

    live, checked = live_findings()
    for finding in live:
        print("live: %s" % finding)
        bad += 1

    if bad:
        print("\nFAILED: %d way(s) in which a degraded note could hold a day."
              % bad)
        return 1
    print("OK: the scheduler reads what is in the slot rather than its date, "
          "and answers both ways. Live: %d assertion(s) on a degraded state "
          "the product's own recorder produced and its own reader read back - "
          "it is retried once its moment passes and not before, an ok slot is "
          "not fetched twice, an empty slot is not a hold, and a configured "
          "backoff is clamped out loud. What this measures is when a request "
          "happens, never what the request does: no socket is opened here."
          % checked)
    return 0


if __name__ == "__main__":
    sys.exit(main())
