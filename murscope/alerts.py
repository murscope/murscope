"""An alert: one sentence about one project, and the only payload this
product will ever hand to a machine that sends while nobody is present.

DP125 is the ruling this module implements, and it is a ruling about a
conflict rather than about a feature. DP124 says the scheduled entry point
collects and cannot send. The owner also ruled that alerts may leave the
machine, because **an alert that only reaches the Mac you are sitting at
is not an alert**. Those two sentences collide, the collision was put on
the table before the task book was written, and the resolution is an
exception that is stated: outbound alerting is off, turning it on is an
act, and it carries its own disclosure table and its own fingerprint.

So this product now has **two consents of different strength**, and a user
has to be able to see which one they are giving:

* the daily note's, which a human completes on each send - a screen read,
  a `yes` typed, and the request in the next second;
* this one, which authorises **a machine to act alone**. Nobody is asked
  again. The consent screen says so in the owner's own words - *this one
  leaves while you are not here* - and `cli` prints that as a line of its
  own rather than as a clause somebody could skim past.

## What an alert carries, and why it cannot inherit the note's argument

The daily note's payload is eight numbers per project and its disclosure
reasons about *method*. **An alert is a sentence, and a useful alert names
the project.** That is not a wider version of the same argument, it is a
different one, so this table makes it from the beginning: a project id
leaves, and a sentence built around that id leaves with it.

What does **not** leave, and the difference matters more here than on the
board: no path, no branch, no commit subject, no declaration text, no
ledger line, no file name, no marker line. `sentence` below is composed by
`%` from `SENTENCES` and the declared fields and from nothing else, and
`build()` recomputes it and refuses the payload if the two differ - so a
future edit that interpolates a project's own words into the sentence is a
`DisclosureMismatch` rather than a surprise in somebody's chat channel.

## A sensitive project is not evaluated at all, and no count of them leaves

Red line four, on a surface that is push rather than pull, and it is
stronger here than on the note in two ways.

**Not evaluated rather than evaluated and dropped.** `evaluate()` skips a
sensitive record before any rule sees it, so there is no alert object
holding a sensitive project anywhere in the process. The note's `build()`
drops a row it has already constructed; here there is nothing to drop.

**And no `withheld_sensitive` count.** The note carries one and that is
right: the note is one document a day describing the whole portfolio, the
count is method about the portfolio, and it is what makes withholding
*visible to the user*. An alert is not that document. Alerts leave one at
a time, on the occasion of an event, to a destination that may well be a
channel other people read - and a count attached to a per-event message is
either constant and useless or it varies, and a count that varies over a
stream of timestamped messages tells an observer that something happened
in the set of projects whose whole point is that nothing about them
leaves. The count would also be describing projects that did not fire,
which is wider than the event the message is about.

The user still has to be able to see that something was held back, and
that has not been given up - it has been moved to the surface where it
costs nothing: `evaluate()` returns the number skipped and the **local**
delivery prints it. Visible on your machine, absent from the wire.

## What fires

Two rules, and both are transitions rather than states, because a rule
that fires on a condition fires again every time the job runs and an alert
that arrives every hour is a filter somebody writes.

* `went_quiet` - a project that was moving at the previous evaluation and
  is not now. The product's second question ("which stalled"), as an
  event.
* `on_you` - a project whose own ledger began naming its owner. The third
  question ("which are stuck on me"), as an event.

The first evaluation on a machine fires nothing. There is no previous
snapshot to have moved away from, and a fresh install that emitted one
alert per project would teach its user to mute the channel on day one.

An event also needs a known commit clock. A project whose git read failed
has `idle_days = None`, and an alert whose number is missing is not worth
waking anybody for - the board is the surface for "this could not be
read".
"""
from __future__ import annotations

import hashlib
import json

from . import __version__, disclosure, state
from .disclosure import COUNT, FLAG, PAYLOAD, REQUEST, SECRET, TEXT
from .guard import guard_write_path

# The two rules. Names are data - they go into the payload and are
# declared - so they are written in the vocabulary a reader of the alert
# has, not in the vocabulary of the code that produced it.
WENT_QUIET = "went_quiet"
ON_YOU = "on_you"
RULES = (WENT_QUIET, ON_YOU)

# `collect.tier` bands, split into the two halves this module reasons
# about. UNKNOWN and MISSING are in neither on purpose: "we could not read
# it" is not a transition and must not become one.
MOVING_TIERS = ("ACTIVE", "WARM")
QUIET_TIERS = ("QUIET", "COLD")

# The whole of an alert's prose. A template per rule, filled by `%` from
# the declared fields and from nothing else, and `build()` recomputes the
# result and refuses a payload whose `sentence` does not match. That is
# what stops this field from becoming the hole in the middle of the table:
# every other row declares a value, and a free-text row would declare a
# place where anything at all could be put.
SENTENCES = {
    WENT_QUIET: ("murscope: %(project)s went quiet. It was %(was)s at the "
                 "last check and it is %(now)s now; its last commit was "
                 "%(idle_days)d day(s) ago."),
    ON_YOU: ("murscope: %(project)s is waiting on you. Its own ledger "
             "started naming you as the one it is waiting for. It is "
             "%(now)s; its last commit was %(idle_days)d day(s) ago."),
}

# Where the previous evaluation's tiers are remembered, under
# MURSCOPE_HOME like everything else this product keeps.
STATE_DIRNAME = "alerts"
STATE_FILENAME = "state.json"
STATE_SCHEMA = 1

# (path, scope, kind, what it is). The same four columns every disclosure
# table in this package has, so `consent.fingerprint` is handed the same
# kind of document whichever one is being agreed to.
DISCLOSURE = (
    ("request.url", REQUEST, SECRET,
     "the delivery address you stored with `murscope key set` - the whole "
     "of it, because a webhook URL is itself the credential and there is "
     "nothing else authenticating this. It is read from the key store for "
     "the request and goes into no artifact; the consent screen and every "
     "line murscope prints show its scheme and host only"),
    ("headers.user_agent", REQUEST, TEXT,
     "the word `murscope`, so a delivery in your channel's own logs is one "
     "you can attribute"),
    ("request.route", REQUEST, TEXT,
     "nothing between here and the destination named above. murscope builds "
     "its own opener with proxies switched off, so an `https_proxy` in your "
     "environment is not used and does not become a second machine your "
     "alert passes through. If your network requires one, the delivery "
     "fails, and it is recorded as failed rather than reported as sent"),
    ("generator", PAYLOAD, TEXT,
     "which version of murscope produced this"),
    ("unattended", PAYLOAD, FLAG,
     "whether nobody was present. True is the scheduled entry point sending "
     "on the authority you gave once; false is you having typed `murscope "
     "alert --send` a second ago. It is in the message because the "
     "difference between those two is the whole of what you are agreeing "
     "to here"),
    ("sentence", PAYLOAD, TEXT,
     "the alert itself, in words. It is composed from a fixed template that "
     "ships inside the package and from the four fields below - nothing "
     "your project wrote is in it. No commit subject, no ledger line, no "
     "declaration text, no file name, no path"),
    ("alert.rule", PAYLOAD, TEXT,
     "which rule fired: `went_quiet`, or `on_you`"),
    ("alert.project", PAYLOAD, TEXT,
     "the id in roster.json - which the scan set to the directory name "
     "unless you changed it. Rename it there and this sends what you "
     "renamed it to. **This is the field that makes an alert an alert**: "
     "the daily note describes a portfolio and this names one project, out "
     "loud, to the destination above. A project you marked sensitive is "
     "never evaluated by a rule at all, so it cannot appear here - and no "
     "count of how many were skipped leaves either, because an alert goes "
     "one at a time and a number that moves over a stream of timestamped "
     "messages is a way of saying something happened"),
    ("alert.was", PAYLOAD, TEXT,
     "which activity tier it was in at the previous check: ACTIVE, WARM, "
     "QUIET or COLD"),
    ("alert.now", PAYLOAD, TEXT,
     "which activity tier it is in now"),
    ("alert.idle_days", PAYLOAD, COUNT,
     "whole days since its last commit"),
)


class DisclosureMismatch(RuntimeError):
    """The payload carries something the disclosure does not declare."""


def shown():
    """((path, sentence), ...). What `consent` fingerprints."""
    return disclosure.shown(DISCLOSURE)


def fields():
    """Just the paths, in table order. For messages, never for a digest."""
    return disclosure.paths(DISCLOSURE)


def disclosure_lines():
    """The table as the lines a user reads before agreeing."""
    return disclosure.lines(DISCLOSURE)


class Event(object):
    """One fired rule, before it is a payload and before it is delivered.

    A class rather than a dict so that the local surface, the payload
    builder and the delivery record are all reading the same five values.
    """

    __slots__ = ("rule", "project", "was", "now", "idle_days")

    def __init__(self, rule, project, was, now, idle_days):
        self.rule = rule
        self.project = project
        self.was = was
        self.now = now
        self.idle_days = idle_days

    def as_fields(self):
        return {"rule": self.rule, "project": self.project, "was": self.was,
                "now": self.now, "idle_days": self.idle_days}

    def sentence(self):
        return sentence_for(self.rule, self.as_fields())

    def __str__(self):
        return self.sentence()


def sentence_for(rule, values):
    """The alert's prose, from the template and the declared fields only.

    Raises `DisclosureMismatch` for a rule with no template rather than
    falling back to a generic sentence: a rule nobody wrote words for is a
    rule whose alert nobody has read, and inventing one here is how a
    field ends up in a message under a sentence describing something else.
    """
    template = SENTENCES.get(rule)
    if template is None:
        raise DisclosureMismatch(
            "rule %r has no sentence in murscope.alerts.SENTENCES, so there "
            "is no alert to send. Every rule's words ship inside the package "
            "and are part of what the disclosure describes." % rule)
    return template % values


def _tier_of(record):
    tier = record.get("tier")
    return tier if isinstance(tier, str) else "UNKNOWN"


def _idle_days_of(record):
    recency = record.get("recency_days")
    if not isinstance(recency, (int, float)):
        return None
    return state.whole_days(recency)


def snapshot(records):
    """{id: {tier, on_you}} for every record a rule may look at.

    Sensitive entries are not in it. That is deliberate and it is the
    reason this function exists rather than the snapshot being taken off
    the collected records where they are used: a remembered tier for a
    sensitive project would be a record, under MURSCOPE_HOME, of that
    project's activity over time, kept by a feature that is not allowed to
    read it. Nothing is written about a project no rule may see.
    """
    found = {}
    for record in records:
        if record.get("sensitive"):
            continue
        identifier = record.get("id")
        if not isinstance(identifier, str) or not identifier:
            continue
        found[identifier] = {"tier": _tier_of(record),
                             "on_you": bool(record.get("owner_queue"))}
    return found


def evaluate(records, previous):
    """(events, skipped_sensitive, snapshot) for one collection.

    `previous` is the snapshot the last evaluation wrote, or an empty dict
    on a machine that has never run one - in which case nothing fires. A
    first run that emitted one alert per project would be a first run that
    taught its user to mute the channel.

    The order is the roster's, so two runs over the same collection produce
    the same alerts in the same order.
    """
    events = []
    skipped = 0
    for record in records:
        if record.get("sensitive"):
            skipped += 1
            continue
        identifier = record.get("id")
        if not isinstance(identifier, str) or not identifier:
            continue
        before = (previous or {}).get(identifier)
        if not isinstance(before, dict):
            continue  # never seen: there is no transition to report
        idle_days = _idle_days_of(record)
        if idle_days is None:
            # An alert whose number could not be read is not worth waking
            # anybody for. The board is the surface that says "this could
            # not be read", and it says it without sending anything.
            continue
        was = before.get("tier") if isinstance(before.get("tier"), str) \
            else "UNKNOWN"
        now = _tier_of(record)
        if was in MOVING_TIERS and now in QUIET_TIERS:
            events.append(Event(WENT_QUIET, identifier, was, now, idle_days))
        if bool(record.get("owner_queue")) and not bool(before.get("on_you")):
            events.append(Event(ON_YOU, identifier, was, now, idle_days))
    return events, skipped, snapshot(records)


def build(event, unattended):
    """The payload for one alert, or raise.

    Raises `DisclosureMismatch` when the result carries a leaf `DISCLOSURE`
    does not declare, a leaf whose value is not the kind its row declares,
    or a `sentence` that is not what the template produces from the
    declared fields. All three are fatal rather than a problem line, for
    the reason the note's builder gives: a payload nobody consented to must
    not be sent, and the caller's correct answer is to stop rather than to
    send a smaller one it invented.
    """
    values = event.as_fields()
    payload = {
        "generator": "murscope %s" % __version__,
        "unattended": bool(unattended),
        "sentence": sentence_for(event.rule, values),
        "alert": {
            "rule": event.rule,
            "project": event.project,
            "was": event.was,
            "now": event.now,
            "idle_days": event.idle_days,
        },
    }
    declared = set(disclosure.payload_paths(DISCLOSURE))
    strays = sorted(disclosure.leaf_paths(payload) - declared)
    if strays:
        raise DisclosureMismatch(
            "the alert payload carries %s, which the disclosure does not "
            "declare. Nothing is sent: the user agreed to the fields in "
            "murscope.alerts.DISCLOSURE, and a field that is not on that "
            "list is a field nobody was shown. Add it to the table - which "
            "invalidates every recorded consent and asks again - or take it "
            "out of the payload." % ", ".join(strays))
    mistyped = disclosure.kind_findings(DISCLOSURE, payload)
    if mistyped:
        raise DisclosureMismatch(
            "the alert payload carries a value that is not the kind its row "
            "declares, so nothing is sent: %s" % " ".join(mistyped))
    # The sentence, recomputed from the payload's own declared fields. It
    # is the one row whose value is prose, so it is the one row where a
    # future edit could put a project's own words on the wire under a
    # heading saying it could not happen.
    recomposed = sentence_for(payload["alert"]["rule"], payload["alert"])
    if payload["sentence"] != recomposed:
        raise DisclosureMismatch(
            "the alert's sentence is not what murscope.alerts.SENTENCES "
            "produces from the fields beside it, so nothing is sent. That "
            "row is declared as prose composed from a fixed template and "
            "the four fields below it; a sentence that does not recompose "
            "is a sentence carrying something those fields do not.")
    return payload


def canonical(payload):
    """The payload as the bytes that actually go over the wire."""
    return json.dumps(payload, ensure_ascii=True, sort_keys=True,
                      separators=(",", ":")).encode("utf-8")


def payload_digest(payload):
    """A digest of one payload's bytes, for a record of what was sent."""
    return hashlib.sha256(canonical(payload)).hexdigest()


def preview(roster):
    """(ids, withheld) - the ids an alert could ever name, from the roster.

    The consent screen prints this for the same reason the note's screen
    prints its own: "it names projects" is a description and a list of
    twenty directory names is the thing being agreed to. Whether a project
    can appear is decided by `sensitive` in `roster.json`, so no project is
    opened to answer it.
    """
    kept = [entry.id for entry in roster if not entry.sensitive]
    return kept, sum(1 for entry in roster if entry.sensitive)


# One delivery's outcome. `LOCAL` is a real outcome and not the absence of
# one: an alert that was printed and written to alerts.log has been
# delivered as far as this configuration goes.
SENT = "sent"
FAILED = "failed"
LOCAL = "local"

DELIVERIES_FILENAME = "deliveries.json"
# Enough to answer "has this channel been broken all week", bounded so the
# file cannot grow without limit on a machine nobody looks at.
DELIVERY_KEEP = 50


def deliveries_path(home):
    return state_dir(home) / DELIVERIES_FILENAME


def read_deliveries(home):
    """([record], problems), oldest first. A missing file is no history."""
    path = deliveries_path(home)
    if not path.is_file():
        return [], []
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        return [], ["%s cannot be read (%s), so murscope cannot tell you "
                    "whether earlier alerts left this machine." % (path, exc)]
    records = document.get("deliveries") if isinstance(document, dict) else None
    if not isinstance(records, list):
        return [], ["%s holds no delivery list, so murscope cannot tell you "
                    "whether earlier alerts left this machine." % path]
    return [item for item in records if isinstance(item, dict)], []


def record_deliveries(existing, added, home):
    """Append `added` to the history and write it. Returns the path.

    **This is the file that makes a silent failure impossible**, and it is
    why an outbound attempt writes something whatever happens to it. A
    delivery that failed and left no trace is the exact shape this surface
    could not afford: the user is not at the machine, the alert never
    arrived, and nothing anywhere says so - which reads, from every angle
    a person can look at it later, like a quiet week.
    """
    kept = (list(existing) + list(added))[-DELIVERY_KEEP:]
    return guard_write_path(
        deliveries_path(home),
        json.dumps({"schema": STATE_SCHEMA, "deliveries": kept},
                   indent=2, sort_keys=True) + "\n")


def failures_since_last_success(records):
    """How many outbound deliveries have failed since the last one that did not.

    Counted from the tail, so it answers "is this channel broken now"
    rather than "has it ever been". Local deliveries are not in the count
    and do not clear it: they are a different question, and a local
    delivery that succeeded says nothing about whether the webhook is up.
    """
    failed = 0
    for record in reversed(list(records)):
        status = record.get("status")
        if status == SENT:
            break
        if status == FAILED:
            failed += 1
    return failed


def state_dir(home):
    return home / STATE_DIRNAME


def state_path(home):
    return state_dir(home) / STATE_FILENAME


def read_state(home):
    """(snapshot, problems). A missing file is a first run, not an error."""
    path = state_path(home)
    if not path.is_file():
        return {}, []
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        return {}, ["%s cannot be read (%s); this run is treated as a first "
                    "one and fires nothing." % (path, exc)]
    if not isinstance(document, dict):
        return {}, ["%s does not hold an object; this run is treated as a "
                    "first one and fires nothing." % path]
    projects = document.get("projects")
    if not isinstance(projects, dict):
        return {}, []
    return {key: value for key, value in projects.items()
            if isinstance(key, str) and isinstance(value, dict)}, []


def write_state(taken, home):
    """Remember this evaluation's tiers. Returns the path written."""
    return guard_write_path(
        state_path(home),
        json.dumps({"schema": STATE_SCHEMA, "projects": taken},
                   indent=2, sort_keys=True) + "\n")
