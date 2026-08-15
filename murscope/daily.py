"""The daily note's slot, and the retry that makes a fallback honest.

Nothing here opens a socket. The adapters do, and they ship in
`murscope-ai` (DP95, applied a third time): what is behind the `[ai]`
boundary is the transport, and what is here is the arithmetic of *when a
request is made at all* - which is the half that failed upstream, and the
half a base install can therefore still check.

## The failure this module is built around

DP49, stated as the thing that happened rather than as a principle:

> An honest fallback that is never re-checked is a failure that has been
> silently timestamped.

Upstream, a provider's quota ran out, the run wrote a degraded result into
the day's slot, and the scheduler compared **dates**. The quota came back
an hour later and the degraded result held the day, because there was
already something there for today. From outside, that is indistinguishable
from success: a file exists, it is stamped with today, and the only way to
learn it is wrong is to open it.

So `should_attempt()` below does not compare dates. It asks what is in the
slot, and a degraded result is a reason to try again rather than a reason
to stop.

## Both directions, because one of them is free to get right

A scheduler that always returns `True` satisfies "a degraded result is
retried" completely and has no slot at all - it would re-send on every
invocation, every hour, on the user's own paid key. So the rule is two
sentences and the check drives both:

* a **degraded** slot whose retry moment has passed is attempted again;
* an **ok** slot is not, because a note already in hand is not worth a
  second request.

And between them, a degraded slot whose retry moment has *not* passed is
also not attempted - the backoff exists so that a provider having a bad
minute is not asked sixty times in it.

**There is no attempt cap and that is deliberate.** A cap is how the hold
comes back wearing a number: after the fifth failure the slot would be
held for the rest of the day by a rule rather than by a bug, and the
outside view would be identical. What bounds the cost is the backoff and
the fact that nothing runs unless the user runs it.
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

from .guard import guard_write_path, murscope_home

NOTES_DIRNAME = "notes"
SCHEMA = 1

OK = "ok"
DEGRADED = "degraded"

# How long a degraded slot waits before it is worth asking again. Long
# enough that a provider having a bad minute is not asked sixty times in
# it, short enough that a quota which recovers at lunchtime does not hold
# the day - which is the whole of DP49's instance.
RETRY_AFTER_SECONDS = 900

# The ceiling, and it is the whole reason the backoff is allowed to be a
# setting at all. A backoff is a hold with a timer on it, so a setting
# that could be raised without limit would let a user - or a default
# copied out of somebody else's config file - rebuild the exact failure
# this module exists to prevent, and it would look like a preference. An
# hour is long enough for any provider outage worth waiting out and short
# enough that a day cannot be held by one.
MAX_RETRY_AFTER_SECONDS = 3600


class NoNote(RuntimeError):
    """No note was produced, and none was invented."""


def stamp(moment):
    """A UTC timestamp. Written out rather than shared with the reader's
    copy: six lines against a core module importing the GitHub reader's."""
    return moment.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def parse_stamp(text):
    """A `...Z` timestamp back to an aware datetime, or None.

    `datetime.fromisoformat` does not take the trailing `Z` on the 3.9
    floor this package ships for.
    """
    if not isinstance(text, str):
        return None
    try:
        naive = datetime.strptime(text.strip(), "%Y-%m-%dT%H:%M:%SZ")
    except ValueError:
        return None
    return naive.replace(tzinfo=timezone.utc)


def day_key(now):
    """The calendar day a note belongs to, in UTC."""
    return now.astimezone(timezone.utc).strftime("%Y-%m-%d")


class Note(object):
    """One day's slot: what was asked, what came back, and what is next.

    `text` is present on an `ok` note and absent on a degraded one. There
    is no third state and no partial note: a model that answered with
    something unreadable produced no note, and saying so is the point.
    """

    __slots__ = ("day", "status", "at", "provider", "destination", "model",
                 "digest", "text", "reason", "retry_after", "attempts")

    def __init__(self, day, status, at, provider="", destination="", model="",
                 digest="", text="", reason="", retry_after="", attempts=1):
        self.day = day
        self.status = status
        self.at = at
        self.provider = provider
        self.destination = destination
        self.model = model
        self.digest = digest
        self.text = text
        self.reason = reason
        self.retry_after = retry_after
        self.attempts = attempts

    def as_document(self):
        return {"schema": SCHEMA, "day": self.day, "status": self.status,
                "at": self.at, "provider": self.provider,
                "destination": self.destination, "model": self.model,
                "payload_digest": self.digest, "text": self.text,
                "reason": self.reason, "retry_after": self.retry_after,
                "attempts": self.attempts}

    def __str__(self):
        if self.status == OK:
            return ("note for %s from %r via %s, written %s"
                    % (self.day, self.provider, self.model or "an unnamed "
                       "model", self.at))
        return ("degraded slot for %s (attempt %d, %s), retry from %s"
                % (self.day, self.attempts, self.reason or "no reason "
                   "recorded", self.retry_after or "immediately"))


def record_ok(day, now, provider, destination, model, digest, text,
              attempts=1):
    """The slot for a note that exists."""
    return Note(day, OK, stamp(now), provider=provider,
                destination=destination, model=model, digest=digest,
                text=text, attempts=attempts)


def record_degraded(day, now, reason, provider="", destination="",
                    attempts=1, backoff=RETRY_AFTER_SECONDS):
    """The slot for a request that did not produce a note.

    It carries the moment it becomes worth asking again, and that moment
    is what `should_attempt()` reads. A degraded slot with no retry moment
    is treated as retryable rather than as a hold - a record that forgot to
    say when is not a record that said never.
    """
    return Note(day, DEGRADED, stamp(now), provider=provider,
                destination=destination, reason=reason,
                retry_after=stamp(now + timedelta(seconds=backoff)),
                attempts=attempts)


def should_attempt(slot, now):
    """(attempt, why). The whole of DP49, and it does not compare dates.

    The caller prints `why` whichever way it goes, because "murscope did
    not send anything just now" is a fact the user is entitled to the
    reason for - and because a scheduler whose refusals are invisible is
    the scheduler that held a day.
    """
    if slot is None:
        return True, "nothing is recorded for %s yet" % day_key(now)
    if slot.status == OK:
        return False, ("a note for %s was written at %s; a note already in "
                       "hand is not fetched twice. `--again` overrides this."
                       % (slot.day, slot.at))
    moment = parse_stamp(slot.retry_after)
    if moment is None:
        return True, ("the recorded result for %s is degraded and names no "
                      "retry moment, so it is retried rather than held"
                      % slot.day)
    if now >= moment:
        return True, ("the recorded result for %s is degraded (%s) and its "
                      "retry moment %s has passed"
                      % (slot.day, slot.reason or "no reason recorded",
                         slot.retry_after))
    return False, ("the recorded result for %s is degraded (%s) and it is "
                   "worth asking again from %s, in %d second(s)"
                   % (slot.day, slot.reason or "no reason recorded",
                      slot.retry_after, int((moment - now).total_seconds())))


def resolve_backoff(value):
    """(seconds, problems) for a configured `retry_after_seconds`.

    Clamped rather than trusted, and the clamp is reported rather than
    applied quietly - a setting that was silently ignored is a setting the
    user believes is in effect. See `MAX_RETRY_AFTER_SECONDS` for why the
    ceiling exists at all.
    """
    if value is None or value == "":
        return RETRY_AFTER_SECONDS, []
    try:
        seconds = int(value)
    except (TypeError, ValueError):
        return RETRY_AFTER_SECONDS, [
            "[providers] retry_after_seconds is %r, which is not a whole "
            "number of seconds; %d is used instead."
            % (value, RETRY_AFTER_SECONDS)]
    if seconds < 0:
        return 0, ["[providers] retry_after_seconds is negative; 0 is used, "
                   "which retries on the next round."]
    if seconds > MAX_RETRY_AFTER_SECONDS:
        return MAX_RETRY_AFTER_SECONDS, [
            "[providers] retry_after_seconds is %d and is clamped to %d. A "
            "backoff is a hold with a timer on it, and an unbounded one "
            "rebuilds the failure the retry exists to prevent - a degraded "
            "result occupying the day after its cause has cleared - while "
            "looking like a preference." % (seconds, MAX_RETRY_AFTER_SECONDS)]
    return seconds, []


def slot_path(day, home=None):
    return (home or murscope_home()) / NOTES_DIRNAME / ("%s.json" % day)


def write_slot(note, home=None):
    """Put a slot on disk. Returns the path."""
    return guard_write_path(
        slot_path(note.day, home),
        json.dumps(note.as_document(), indent=2, sort_keys=True) + "\n")


def read_slot(day, home=None):
    """(note, problems). A missing file is an open slot, not an error."""
    path = slot_path(day, home)
    if not path.is_file():
        return None, []
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        return None, ["%s cannot be read (%s); the slot is treated as open, "
                      "because an unreadable record is not a note." % (path, exc)]
    if not isinstance(document, dict) or document.get("status") not in (OK,
                                                                        DEGRADED):
        return None, ["%s records no status murscope recognises; the slot is "
                      "treated as open." % path]
    return Note(document.get("day") or day, document["status"],
                document.get("at") or "", document.get("provider") or "",
                document.get("destination") or "", document.get("model") or "",
                document.get("payload_digest") or "", document.get("text") or "",
                document.get("reason") or "", document.get("retry_after") or "",
                int(document.get("attempts") or 1)), []


def next_attempt_number(slot):
    """What to record as this round's attempt count.

    A degraded slot that is retried is the same day's second attempt, and
    a record that says so is how a user learns their provider failed four
    times rather than once.
    """
    return (slot.attempts + 1) if slot is not None and slot.status == DEGRADED \
        else 1
