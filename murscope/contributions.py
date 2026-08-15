"""The contribution reading, and the three corrections it is not honest
without.

**Why this is in the core and the transport is not (DP95).** Promise two
is about sockets. Nothing in this file opens one: it builds a query
string, clamps a range, lays one day series over another, and adds up the
result. What crosses the `[ai]` boundary is the module that hands that
string to `urllib` - and that module ships in `murscope-ai`, which a base
install does not have. The gain is the same one DP95 bought for the key
store: the arithmetic below can be checked by the gate and exercised on
every install, rather than only on the ones that could reach out.

## The three corrections, and why they are not defensive coding

`design/ADR-0003` records four defects found upstream **after** the port
baseline was pinned. Three of them are this reader's, and each one
produced a wrong number on a page that looked right.

**E1 - a range endpoint in the future.** The query asked for a year
ending at `{year}-12-31T23:59:59Z`. When that endpoint has not happened
yet the API answers with a snapshot frozen part way through the current
day, and the answer is *stable*, so nothing about it looks like an error.
`clamp_end()` is one `min()` call, and it is the whole fix.

**E2 - a cache used as a freshness shortcut.** A 25-minute TTL let a
collection at 11:44 publish figures gathered at 11:22 under a masthead
reading "generated 11:44". `resolve()` below is what replaces the TTL:
**a cache answers only after a fetch has failed, never instead of one.**
There is no age parameter in this module, deliberately - an age parameter
is how the shortcut comes back (DP48). When the cache does answer, the
reading carries the moment the *data* was gathered rather than the moment
the page was built, because the alternative is a timestamp that describes
the render and is read as describing the figures.

**E3 - "January 1st to today" is a range the platform precomputes.** This
is the entry ADR-0003 says is worth the most, and it is worth restating
why: E1 and E2 are recognisable from first principles, and E3 is not. It
took a six-point bisection upstream to find that every start date from
March onward agreed with the profile page and only January 1st did not -
because that exact range is the one the platform precomputes and caches
for its own annual view, so it is served from cache while any other range
is computed live. No amount of care predicts that. The fix keeps the year
range for history, overlays a fresh query for the recent weeks, and sums
the **corrected daily series** rather than believing the total the API
reports.

That last clause is the load-bearing one. `total()` adds up days; it
never reads `totalContributions`. A reader that overlaid the series
correctly and then reported the API's own total would have done all the
work and thrown the answer away.

## What leaves, and what does not

`DISCLOSURE` is the list a user is shown before agreeing, in the same
shape `outbound.DISCLOSURE` uses and fingerprinted by the same code. It
is a **different** list, because this is a different request: the board
summary sends facts about the user's projects, and this sends two
timestamps and a credential.

The query asks about `viewer`, not about a login. That is not a
formatting choice - it means **the account name is not in the request**.
The platform resolves the account from the token, so what leaves is the
token, a date range, and nothing else. No project name, no path, no
repository, no file.
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

from . import disclosure
from .guard import guard_write_path, murscope_home

CACHE_DIRNAME = "contributions"
CACHE_NAME = "last-reading.json"
SCHEMA = 1

# How far back the overlay query reaches. Four weeks is well past any
# plausible precompute window and still one small request; the point is
# that it is *some other range* than the one the platform has cached, not
# that it is any particular length.
OVERLAY_DAYS = 28

# The query. `viewer` rather than `user(login:)` on purpose: the platform
# resolves the account from the token, so the account name never leaves
# this machine. Written as one string with no interpolation - the range
# travels as GraphQL variables, so there is no shape here into which a
# value could be spliced.
QUERY = (
    "query($from:DateTime!,$to:DateTime!){"
    "viewer{contributionsCollection(from:$from,to:$to){"
    "contributionCalendar{totalContributions "
    "weeks{contributionDays{date contributionCount}}}"
    "}}}"
)

# (path, scope, kind, what it is). Same shape as `outbound.DISCLOSURE`,
# fingerprinted by the same `consent.fingerprint`, and deliberately a
# separate table: agreeing to send eleven facts about your projects to a
# model is not agreeing to ask a code host what you did last month.
#
# Every row here is `REQUEST`-scoped, and that is the honest reading rather
# than a technicality: this reader builds no document of the user's own.
# What leaves is a credential, a range and a constant.
DISCLOSURE = (
    ("auth.token", disclosure.REQUEST, disclosure.SECRET,
     "your GitHub token, in an Authorization header - which is how the "
     "platform knows whose contributions to answer with. It is read from "
     "the key store for the request and goes into no artifact"),
    ("query.viewer", disclosure.REQUEST, disclosure.TEXT,
     "the literal word `viewer`: the platform resolves the account from "
     "your token, so your username is not in the request"),
    ("query.from", disclosure.REQUEST, disclosure.TEXT,
     "the start of the range being asked about, as a UTC timestamp"),
    ("query.to", disclosure.REQUEST, disclosure.TEXT,
     "the end of the range being asked about, as a UTC timestamp - never "
     "later than the moment the request is made"),
    ("headers.user_agent", disclosure.REQUEST, disclosure.TEXT,
     "the word `murscope`, so a request in your own account's access log "
     "is one you can attribute"),
    ("request.route", disclosure.REQUEST, disclosure.TEXT,
     "nothing between here and the platform. murscope builds its own opener "
     "with proxies switched off, so an `https_proxy` in your environment is "
     "not used and your token does not pass through a machine you were never "
     "shown. If your network requires one, the request fails and says so"),
)


class NoReading(RuntimeError):
    """No figure could be produced, and none was invented."""


def shown():
    """((path, sentence), ...). What `consent` fingerprints."""
    return disclosure.shown(DISCLOSURE)


def fields():
    """Just the paths, in table order. For messages, never for a digest."""
    return disclosure.paths(DISCLOSURE)


def disclosure_lines():
    """The table as the lines a user reads before agreeing."""
    return disclosure.lines(DISCLOSURE)


def stamp(moment):
    """A UTC timestamp in the shape the API's DateTime scalar wants."""
    return moment.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def parse_stamp(text):
    """A `...Z` timestamp back to an aware datetime. None if unreadable.

    Written out rather than handed to `datetime.fromisoformat`, which
    does not accept the trailing `Z` on the 3.9 floor this package ships
    for.
    """
    if not isinstance(text, str):
        return None
    try:
        naive = datetime.strptime(text.strip(), "%Y-%m-%dT%H:%M:%SZ")
    except ValueError:
        return None
    return naive.replace(tzinfo=timezone.utc)


def clamp_end(end, now):
    """E1: a range never ends later than the moment it is asked.

    One `min()`, and the reason it is a named function rather than an
    inline expression is that a named function can be called by a check.
    An endpoint in the future does not fail - it answers, with a snapshot
    frozen part way through the current day, and the answer is stable
    enough that nothing about it looks wrong.
    """
    return now if end > now else end


def year_range(now):
    """(from, to) for the calendar year, with E1's clamp applied."""
    start = datetime(now.year, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
    unclamped = datetime(now.year, 12, 31, 23, 59, 59, tzinfo=timezone.utc)
    return start, clamp_end(unclamped, now)


def overlay_range(now, days=OVERLAY_DAYS):
    """(from, to) for the recent window E3 lays over the year.

    Its whole job is to be a range the platform has *not* precomputed, so
    it is computed live. The clamp applies here too - not because this end
    is ever in the future today, but because a range builder that clamps
    only where the bug was found is a clamp that stops applying the first
    time somebody changes the arithmetic.
    """
    return clamp_end(now - timedelta(days=days), now), clamp_end(now, now)


def request_for(start, end):
    """The GraphQL document and variables for one range. Opens nothing."""
    return {"query": QUERY,
            "variables": {"from": stamp(start), "to": stamp(end)}}


def days_from(payload):
    """{date: count} out of one calendar response. Raises on a shape it
    does not recognise, rather than returning an empty series.

    The difference matters: an empty series sums to zero, and zero is a
    number a board will happily print beside today's date. A reader that
    cannot read is not a reader that saw no activity.
    """
    if not isinstance(payload, dict):
        raise NoReading("the response was %s, not an object"
                        % type(payload).__name__)
    errors = payload.get("errors")
    if errors:
        first = errors[0] if isinstance(errors, list) and errors else errors
        message = (first.get("message") if isinstance(first, dict)
                   else str(first))
        raise NoReading("the API answered with an error: %s" % message)
    try:
        calendar = (payload["data"]["viewer"]["contributionsCollection"]
                    ["contributionCalendar"])
        weeks = calendar["weeks"]
    except (KeyError, TypeError) as exc:
        raise NoReading("the response carries no contribution calendar (%s)"
                        % exc)
    days = {}
    for week in weeks:
        for day in (week or {}).get("contributionDays") or []:
            date = day.get("date")
            count = day.get("contributionCount")
            if isinstance(date, str) and isinstance(count, int):
                days[date] = count
    if not days:
        raise NoReading("the contribution calendar carried no days at all")
    return days


def reported_total(payload):
    """The total the API states for itself. Recorded, never believed.

    Kept so the reading can say *how far* the platform's own figure was
    from the corrected one, which is the measurement E3 exists to produce.
    `total()` below never consults it.
    """
    try:
        return int(payload["data"]["viewer"]["contributionsCollection"]
                   ["contributionCalendar"]["totalContributions"])
    except (KeyError, TypeError, ValueError):
        return None


def overlay(base, recent):
    """E3: the recent series wins wherever the two describe the same day.

    `base` is the year range, which the platform serves from its own
    precomputed annual view; `recent` is a range it has no reason to have
    cached and therefore computes live. Where they disagree, the live one
    is the correction and the cached one is the defect.

    A copy rather than an update in place, so a caller can compare the two
    afterwards - which is exactly what the measurement does.
    """
    corrected = dict(base)
    corrected.update(recent)
    return corrected


def corrections(base, recent):
    """[(date, was, now)] for every day the overlay actually changed.

    The evidence half of E3. An overlay that changed nothing is a finding
    about the platform rather than a failed correction (ADR-0003 says so
    in as many words), and it can only be reported as one if the days that
    moved are counted rather than assumed.
    """
    moved = []
    for date in sorted(recent):
        if date in base and base[date] != recent[date]:
            moved.append((date, base[date], recent[date]))
    return moved


def total(days):
    """The sum of a day series.

    Never `totalContributions`. The API's own total is the total of the
    series the API sent, and E3 is precisely the case where that series is
    the stale one - so a reader that corrected the series and then
    reported the platform's total would have done the work and discarded
    the answer.
    """
    return sum(int(count) for count in days.values())


class Reading(object):
    """One answer, and where it came from.

    `at` is when the **figures** were gathered, not when this object was
    built. E2 is the whole reason that distinction is in the type: a
    reading served from cache after a failed fetch is honest only if it
    carries the moment it was collected, and a page that stamps itself
    with the render time turns a stale figure into a fresh-looking one.
    """

    __slots__ = ("days", "at", "source", "stale_seconds", "problems",
                 "api_total", "moved")

    def __init__(self, days, at, source, stale_seconds=0, problems=(),
                 api_total=None, moved=()):
        self.days = dict(days)
        self.at = at
        self.source = source
        self.stale_seconds = stale_seconds
        self.problems = list(problems)
        self.api_total = api_total
        self.moved = list(moved)

    @property
    def total(self):
        return total(self.days)

    def as_document(self):
        return {"schema": SCHEMA, "at": self.at, "source": self.source,
                "days": dict(self.days), "api_total": self.api_total}


def resolve(fetched, cached, now):
    """E2: the cache answers only when the fetch did not. Returns a Reading.

    **There is no age parameter and there is not going to be one.** A TTL
    is the shape of the defect, not a tuning knob that was set too high: a
    cache consulted *before* a fetch publishes a figure from one moment
    under a timestamp from another, and no value of the TTL makes that
    honest. DP48 generalises it past this reader.

    So the ordering is fixed by the signature. `fetched` is whatever the
    transport came back with - a `Reading` on success, `None` on failure -
    and it wins whenever it exists, however new the cache is. Only when it
    does not exist does `cached` get a turn, and then the reading carries
    the age of the data rather than the age of the request.

    Raises `NoReading` when both are absent, because the alternative is
    returning an empty series that sums to zero, and zero is a number a
    board will print.
    """
    if fetched is not None:
        return fetched
    if cached is None:
        raise NoReading(
            "the request failed and no earlier reading is on disk, so there "
            "is no figure to show. murscope reports that rather than "
            "printing a zero: an unanswered question and a quiet month look "
            "identical once they are both a number.")
    gathered = parse_stamp(cached.at)
    age = int((now - gathered).total_seconds()) if gathered else None
    return Reading(cached.days, cached.at, "cache",
                   stale_seconds=age if age and age > 0 else 0,
                   problems=list(cached.problems) + [
                       "this figure was gathered %s and is being shown "
                       "because the request just now did not complete. It is "
                       "stamped with when it was collected, not with now."
                       % (cached.at or "at an unrecorded time")],
                   api_total=cached.api_total)


def today_key(now):
    """The calendar-day key the API uses, for the day `now` falls in."""
    return now.astimezone(timezone.utc).strftime("%Y-%m-%d")


# The labels the measurement uses. Named constants rather than strings
# scattered through a command, because the evidence file is read later by
# somebody who was not here, and a renamed label makes two records
# incomparable for no reason.
UNCLAMPED = "year-ending-31-december"
CLAMPED = "year-ending-now"
OVERLAY = "recent-window"


def reading_documents(now):
    """[(label, document)] for an ordinary corrected reading. Two queries.

    The year range for history and one live window laid over it - E3's
    fix, and the reason it is two queries rather than the obvious one.
    """
    start, end = year_range(now)
    recent_start, recent_end = overlay_range(now)
    return [(CLAMPED, request_for(start, end)),
            (OVERLAY, request_for(recent_start, recent_end))]


def measurement_documents(now):
    """[(label, document)] for the reproduction. Three queries, one of them
    deliberately wrong.

    The first carries the **unclamped** endpoint on purpose. It is the only
    place in this package that builds a range ending later than now, and it
    exists so that E1 can be measured rather than asserted: without a
    request that still has the defect there is nothing for the corrected
    one to differ from, and "the clamp works" would be a sentence with no
    number behind it.
    """
    start = datetime(now.year, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
    december = datetime(now.year, 12, 31, 23, 59, 59, tzinfo=timezone.utc)
    recent_start, recent_end = overlay_range(now)
    return [(UNCLAMPED, request_for(start, december)),
            (CLAMPED, request_for(start, clamp_end(december, now))),
            (OVERLAY, request_for(recent_start, recent_end))]


def cache_path(home=None):
    return (home or murscope_home()) / CACHE_DIRNAME / CACHE_NAME


def write_cache(reading, home=None):
    """Put a successful reading away as a failure fallback. Returns path."""
    return guard_write_path(
        cache_path(home),
        json.dumps(reading.as_document(), indent=2, sort_keys=True) + "\n")


def read_cache(home=None):
    """(reading, problems). A missing file is no cache, not an error."""
    path = cache_path(home)
    if not path.is_file():
        return None, []
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        return None, ["%s cannot be read (%s); treat it as no cache." % (path, exc)]
    if not isinstance(document, dict) or not isinstance(document.get("days"), dict):
        return None, ["%s holds no day series; treat it as no cache." % path]
    return Reading(document["days"], document.get("at") or "",
                   "cache", api_total=document.get("api_total")), []
