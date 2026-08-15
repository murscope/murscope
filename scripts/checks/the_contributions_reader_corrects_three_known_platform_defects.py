"""Rule 20: the contributions reader corrects three known platform defects.

`design/ADR-0003` records four defects found upstream **after** the port
baseline was pinned, three of which are this reader's. They are not
hypotheses: each one produced a wrong number on a page that looked right,
and each one was expensive to find. Porting the reader without them
re-introduces them, which is why they are a rule rather than a comment.

| | The defect | What this rule holds |
|---|---|---|
| E1 | A range endpoint in the future is answered with a snapshot frozen part way through the current day | no range ends later than the moment it is asked |
| E2 | A 25-minute cache TTL published 11:22 figures under a masthead reading 11:44 | the cache answers only after a failed request, never instead of one |
| E3 | "1 January to today" is the range the platform precomputes for its own annual view, so it is served from cache while any other range is computed live | the year range is corrected by a second, live window, and the total is summed from the corrected series |

**The static half** reads any candidate reader source and refuses four
shapes, one per branch of `detect()`: a December endpoint with no clamp
anywhere in the module; a time-to-live that lets a cache answer instead
of a request; a total lifted from the API's own `totalContributions`
instead of summed; and a reader that builds one range and no overlay.

**The live half** is where the teeth are, and it runs the real module.
Every correction is asserted **in both directions**, because each one has
a degenerate implementation that would satisfy a one-sided assertion:

* a clamp that returns `now` unconditionally passes "no endpoint is in
  the future" and destroys every historical range, so a past endpoint is
  asserted to come back untouched;
* a `resolve()` that ignored its cache entirely passes "the cache is
  never a shortcut" and has no fallback at all, so the failure path is
  asserted to return the cached series *and* to carry the moment that
  series was gathered rather than the moment it was asked for;
* an `overlay()` that returned its base unchanged passes "the total is
  not the API's" whenever the two agree, so the arithmetic is asserted on
  a payload where the API's stated total is **wrong on purpose** and the
  summed answer is the only right one.

**What walks into this check (DP87), stated because a green result here
is otherwise unfalsifiable.** Two of the assertions exist purely to prove
the others were reachable:

* `measurement_documents()` must produce one range ending later than
  `now` and one ending at it. Without a request that still carries the
  defect, E1's measurement has nothing to differ from and "the clamp
  works" is a sentence with no number behind it;
* `reading_documents()` must produce two ranges that are actually
  different. A reader that overlaid the year range onto itself would
  correct nothing while passing every arithmetic assertion below.

**The corrections are held whether or not the platform still misbehaves.**
Re-measured on the product line on 2026-08-13, E1 and E3 did not
reproduce: a future endpoint and a clamped one agreed on every day, and
six start dates from 1 January to seven-days-ago returned identical
recent tails. That is recorded in ADR-0003 and in DP101 as a finding
about the platform. It is not a reason to drop the corrections and it is
not a reason to weaken this rule: a range that ends later than now is
wrong whether or not it is currently answered wrongly, and the whole
lesson of E3 is that this behaviour was not predictable from first
principles in either direction.

If the reader module cannot be imported this check is **red, not green**,
for the same reason Rule 13b is red without a build backend.

Fails when: a reader builds a range ending 31 December without clamping
it; a cache is consulted on a time-to-live instead of after a failure; a
total is read from `totalContributions` rather than summed from the day
series; a reader builds a year range and no second window to correct it;
`clamp_end` moves an endpoint that is already in the past, or fails to
move one in the future; `resolve()` prefers a cache to a completed
request, returns no cached series when the request failed, stamps a
cached reading with the present, or invents a figure when it has neither;
the overlaid total is not the sum of the corrected series; the
measurement plan carries no unclamped range, or the reading plan carries
two identical ones; or the reader module cannot be imported at all.
"""
from __future__ import annotations

import ast
import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
READER = REPO_ROOT / "murscope" / "contributions.py"

# A range endpoint pinned to the end of December, in either spelling: the
# formatted string upstream used, or the constructor this package would
# reach for.
DECEMBER_TEXT = "-12-31T23:59:59"
DECEMBER_PARTS = (12, 31, 23, 59, 59)

# Names that mean "this cache may answer because it is young enough".
# That is the defect, not a setting whose value was wrong: no value of a
# time-to-live makes a figure from 11:22 honest under a stamp of 11:44.
TTL_NAMES = ("ttl", "cache_ttl", "max_age", "cache_seconds", "fresh_seconds",
             "cache_age", "freshness", "stale_after")
AGE_NAMES = ("age", "elapsed", "age_seconds", "since", "cache_age")

API_TOTAL = "totalContributions"


def _december_literals(tree):
    """Line numbers where a range endpoint is pinned to 31 December."""
    hits = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            if DECEMBER_TEXT in node.value:
                hits.append(node.lineno)
        elif isinstance(node, ast.Call):
            name = getattr(node.func, "id", None) or getattr(node.func, "attr", None)
            if name != "datetime":
                continue
            # Positional, with non-literals kept as None rather than
            # dropped. `datetime(now.year, 12, 31, 23, 59, 59)` is the
            # spelling this defect actually takes, and a filter that only
            # kept constants would shift the month into the year slot and
            # miss every one of them.
            values = [arg.value if isinstance(arg, ast.Constant) else None
                      for arg in node.args]
            if len(values) >= 6 and tuple(values[1:6]) == DECEMBER_PARTS:
                hits.append(node.lineno)
    return hits


def _has_clamp(tree):
    """Is anything in this module capable of shortening a range?

    Either a `min()` call or a function whose name says it clamps. Both
    spellings are accepted because the rule is about the behaviour, and a
    check that insists on one idiom is a check that will be worked around
    with the other.
    """
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            name = getattr(node.func, "id", None) or getattr(node.func, "attr", None)
            if name == "min":
                return True
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if "clamp" in node.name.lower():
                return True
    return False


def _ttl_findings(tree):
    """A cache gated on age rather than on a failure."""
    findings = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            for target in node.targets:
                name = getattr(target, "id", "")
                if isinstance(name, str) and name.lower() in TTL_NAMES:
                    findings.append(
                        "%d: %r is a time-to-live. E2 is not a TTL that was "
                        "set too high - it is a cache consulted before a "
                        "request, which publishes figures from one moment "
                        "under a timestamp from another. There is no value "
                        "of this that is honest (DP48)." % (node.lineno, name))
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            for argument in node.args.args:
                if argument.arg.lower() in TTL_NAMES:
                    findings.append(
                        "%d: %s() takes %r. A reader that can be asked how "
                        "fresh is fresh enough is a reader whose cache is a "
                        "shortcut." % (node.lineno, node.name, argument.arg))
        if isinstance(node, ast.If):
            names = set()
            for sub in ast.walk(node.test):
                if isinstance(sub, ast.Name):
                    names.add(sub.id.lower())
                elif isinstance(sub, ast.Attribute):
                    names.add(sub.attr.lower())
            if not (names & set(AGE_NAMES)) and not (names & set(TTL_NAMES)):
                continue
            returns = [sub for sub in ast.walk(node) if isinstance(sub, ast.Return)]
            for statement in returns:
                text = ast.dump(statement)
                if "cache" in text.lower() or "cached" in text.lower():
                    findings.append(
                        "%d: a cached value is returned because it is young "
                        "enough. The cache is a failure fallback: it answers "
                        "after a request did not, never instead of one."
                        % statement.lineno)
                    break
    return findings


def _api_total_findings(tree):
    """A total lifted from the API instead of summed from the series."""
    findings = []
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        if "total" not in node.name.lower():
            continue
        if node.name in ("reported_total",):
            # Recording what the platform claims is fine, and the whole
            # point of the E3 measurement. Believing it is not.
            continue
        for sub in ast.walk(node):
            reads_api = (
                (isinstance(sub, ast.Constant) and sub.value == API_TOTAL)
                or (isinstance(sub, ast.Attribute) and sub.attr == API_TOTAL))
            if reads_api:
                findings.append(
                    "%d: %s() reads %r. E3 is exactly the case where the "
                    "platform's own total is the total of the stale series it "
                    "sent, so a reader that corrects the series and then "
                    "reports that number has done the work and thrown the "
                    "answer away." % (sub.lineno, node.name, API_TOTAL))
                break
    return findings


def _overlay_findings(tree):
    """A reader that builds one range and nothing to correct it with."""
    if not _december_literals(tree) and not any(
            isinstance(node, ast.Call)
            and (getattr(node.func, "id", None) or
                 getattr(node.func, "attr", None)) == "datetime"
            for node in ast.walk(tree)):
        return []
    names = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            names.add(node.name.lower())
        elif isinstance(node, ast.Call):
            called = getattr(node.func, "id", None) or getattr(node.func, "attr", None)
            if called:
                names.add(called.lower())
    if any("overlay" in name for name in names):
        return []
    if "timedelta" in names:
        return []
    return ["this module builds a range and never builds a second, shorter "
            "one to lay over it. E3 is the entry ADR-0003 says is worth the "
            "most: '1 January to today' is precisely the range the platform "
            "precomputes for its own annual view, so it is the one range "
            "whose freshness this product does not control. A reader with a "
            "single range has no way to notice."]


def detect(payload):
    """Findings for one candidate contributions reader's source."""
    source = payload.decode("utf-8", errors="replace")
    try:
        tree = ast.parse(source)
    except SyntaxError as exc:
        return ["cannot parse (%s), so its corrections cannot be read." % exc]

    findings = []
    december = _december_literals(tree)
    if december and not _has_clamp(tree):
        findings.append(
            "%d: a range endpoint is pinned to 31 December and nothing in "
            "this module can shorten it. When that endpoint has not happened "
            "yet the API answers with a snapshot frozen part way through the "
            "current day - and the answer is stable, so nothing about it "
            "looks like an error (E1)." % december[0])
    findings.extend(_ttl_findings(tree))
    findings.extend(_api_total_findings(tree))
    findings.extend(_overlay_findings(tree))
    return findings


LIVE = r'''
import json, sys
from datetime import datetime, timedelta, timezone

sys.path.insert(0, sys.argv[1])
report = {"loaded": False, "findings": [], "checked": 0}
try:
    from murscope import contributions as c
    report["loaded"] = True
except Exception as exc:
    report["error"] = "%s: %s" % (type(exc).__name__, exc)
    print(json.dumps(report))
    raise SystemExit(0)

bad = report["findings"]
def checked():
    report["checked"] += 1

now = datetime(2026, 8, 13, 11, 44, 0, tzinfo=timezone.utc)

# --- E1, both directions -------------------------------------------------
future = datetime(2026, 12, 31, 23, 59, 59, tzinfo=timezone.utc)
past = datetime(2026, 3, 1, 0, 0, 0, tzinfo=timezone.utc)
if c.clamp_end(future, now) != now:
    bad.append("clamp_end() left an endpoint in the future alone (E1).")
else:
    checked()
if c.clamp_end(past, now) != past:
    bad.append("clamp_end() moved an endpoint that had already happened. A "
               "clamp that returns now unconditionally passes the case above "
               "and destroys every historical range.")
else:
    checked()

start, end = c.year_range(now)
if end > now:
    bad.append("year_range() ends at %s, later than the moment it was asked "
               "about (%s)." % (end, now))
else:
    checked()

# The measurement plan has to still carry the defect, or E1 is measured
# against nothing (DP87).
plan = dict((label, doc["variables"]) for label, doc in
            c.measurement_documents(now))
ends = set(v["to"] for v in plan.values())
unclamped = [label for label, v in plan.items() if v["to"] > c.stamp(now)]
if not unclamped:
    bad.append("measurement_documents() carries no range ending later than "
               "now, so the E1 measurement has nothing to compare a clamped "
               "range against and 'the clamp works' is a sentence with no "
               "number behind it.")
else:
    checked()
if len(ends) < 2:
    bad.append("every range in measurement_documents() ends at the same "
               "moment, so the comparison E1 exists for cannot happen.")
else:
    checked()

# --- E2, both directions -------------------------------------------------
fresh = c.Reading({"2026-08-13": 5}, c.stamp(now), "cache")
live = c.Reading({"2026-08-13": 12}, c.stamp(now), "live")
got = c.resolve(live, fresh, now)
if got is not live:
    bad.append("resolve() preferred a cache to a request that completed. The "
               "cache is a failure fallback, never a freshness shortcut (E2).")
else:
    checked()

gathered = now - timedelta(minutes=22)
stale = c.Reading({"2026-08-13": 5}, c.stamp(gathered), "cache")
got = c.resolve(None, stale, now)
if got.source != "cache" or got.total != 5:
    bad.append("resolve() did not fall back to the cache when the request "
               "failed (%r). A reader with no fallback passes the case above "
               "and is useless on a bad day." % got.source)
else:
    checked()
if got.at != c.stamp(gathered):
    bad.append("a cached reading is stamped %r and the data was gathered at "
               "%r. That is the whole of E2: a page that stamps itself with "
               "the render time turns a stale figure into a fresh-looking "
               "one." % (got.at, c.stamp(gathered)))
else:
    checked()
if got.stale_seconds != 22 * 60:
    bad.append("a cached reading 22 minutes old reports %r seconds of "
               "staleness." % got.stale_seconds)
else:
    checked()
if not got.problems:
    bad.append("a cached reading carries no problem line, so nothing tells "
               "the reader the figure is not from now.")
else:
    checked()

try:
    c.resolve(None, None, now)
    bad.append("resolve() invented a figure with neither a request nor a "
               "cache. An empty series sums to zero, and zero is a number a "
               "board will happily print beside today's date.")
except c.NoReading:
    checked()

for name in dir(c):
    if name.lower() in ("ttl", "cache_ttl", "max_age", "cache_seconds"):
        bad.append("murscope.contributions exposes %r. E2 is not a TTL set "
                   "too high; it is the existence of one." % name)

# --- E3, arithmetic, on a payload whose stated total is wrong ------------
def payload_for(days, stated):
    return {"data": {"viewer": {"contributionsCollection": {
        "contributionCalendar": {
            "totalContributions": stated,
            "weeks": [{"contributionDays": [
                {"date": d, "contributionCount": n}
                for d, n in sorted(days.items())]}]}}}}}

year = {"2026-08-11": 3, "2026-08-12": 5, "2026-08-13": 1}
recent = {"2026-08-12": 5, "2026-08-13": 12}
# Deliberately not the sum of anything. A reader that consulted the
# platform's figure anywhere would produce 999 and be caught on the spot;
# one that only consulted it "when the series looks consistent" would be
# caught here too, because nothing here is consistent with it.
stated_wrong = 999

parsed = c.days_from(payload_for(year, stated_wrong))
if parsed != year:
    bad.append("days_from() returned %r for a calendar carrying %r."
               % (parsed, year))
else:
    checked()
if c.reported_total(payload_for(year, stated_wrong)) != stated_wrong:
    bad.append("reported_total() does not read back what the platform stated, "
               "so the E3 measurement cannot say how far off it was.")
else:
    checked()
if c.total(parsed) != 9:
    bad.append("total() returned %d for a series adding to 9 beside a stated "
               "total of %d. It must sum the series and never consult the "
               "platform's figure." % (c.total(parsed), stated_wrong))
else:
    checked()

corrected = c.overlay(parsed, recent)
if corrected.get("2026-08-13") != 12 or corrected.get("2026-08-11") != 3:
    bad.append("overlay() did not let the live window win where the two "
               "describe the same day, or dropped a day it does not cover "
               "(%r)." % corrected)
else:
    checked()
if c.total(corrected) != 20:
    bad.append("the corrected series sums to %d and its days add up to 20. "
               "total() must sum the corrected series, never report the "
               "platform's own figure (E3)." % c.total(corrected))
else:
    checked()
if c.total(parsed) == c.total(corrected):
    bad.append("the overlay changed nothing on a case built so that it must. "
               "An overlay() that returns its base unchanged passes every "
               "assertion above whenever the two happen to agree.")
else:
    checked()
moved = c.corrections(parsed, recent)
if moved != [("2026-08-13", 1, 12)]:
    bad.append("corrections() reported %r; the case moves exactly one day."
               % moved)
else:
    checked()

# The reading plan must carry two genuinely different ranges, or the
# overlay overlays the year range onto itself (DP87).
reading = dict((label, doc["variables"]) for label, doc in
               c.reading_documents(now))
if len(reading) < 2 or len(set(json.dumps(v, sort_keys=True)
                               for v in reading.values())) < 2:
    bad.append("reading_documents() does not produce two different ranges, "
               "so the correction is the year range laid over itself and "
               "corrects nothing by construction.")
else:
    checked()

try:
    c.days_from({"data": {"viewer": None}})
    bad.append("days_from() accepted a response with no calendar. An empty "
               "series sums to zero and a board prints it.")
except c.NoReading:
    checked()

print(json.dumps(report))
'''


def live_findings():
    """Run the real reader. Import failure is red, never green."""
    result = subprocess.run(
        [sys.executable, "-c", LIVE, str(REPO_ROOT)],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    raw = result.stdout.decode("utf-8", errors="replace").strip()
    if not raw:
        return ["the live probe printed nothing (%s)."
                % result.stderr.decode("utf-8", errors="replace")
                .strip()[-300:]], 0
    try:
        report = json.loads(raw.splitlines()[-1])
    except ValueError as exc:
        return ["the live probe's report was unreadable (%s)." % exc], 0
    if not report.get("loaded"):
        return ["murscope.contributions could not be imported (%s), so not "
                "one correction was exercised. This check is red rather than "
                "green." % report.get("error", "no reason given")], 0
    return report.get("findings", []), report.get("checked", 0)


def main():
    if not READER.exists():
        print("FAILED: %s is missing. The three corrections are this rule's "
              "whole subject; without the reader there is nothing to hold."
              % READER.relative_to(REPO_ROOT).as_posix())
        return 1

    findings = detect(READER.read_bytes())
    for finding in findings:
        print("murscope/contributions.py:%s" % finding)

    live, checked = live_findings()
    for finding in live:
        print(finding)

    total = len(findings) + len(live)
    if total:
        print("\nFAILED: %d finding(s) against the contributions reader."
              % total)
        return 1
    print("OK: the reader was read and then run. %d live assertion(s) held, "
          "each of the three corrections pinned in both directions - a clamp "
          "that shortens a future endpoint and leaves a past one alone, a "
          "cache that answers only after a failure and carries the moment its "
          "data was gathered, and a total summed from the corrected series on "
          "a payload whose stated total is wrong on purpose. The measurement "
          "plan still carries one unclamped range and the reading plan two "
          "different ones, so neither measurement is being taken against "
          "itself." % checked)
    return 0


if __name__ == "__main__":
    sys.exit(main())
