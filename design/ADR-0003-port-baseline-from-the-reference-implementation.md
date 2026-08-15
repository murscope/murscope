---
title: Port baseline from the reference implementation
type: adr
captured: 2026-08-12
status: active
---

# ADR-0003: the port baseline is one pinned commit

Implements DP39.

Numbered 0003, not 0002: the M1 task book already cites "ADR-0002
direction B" for the warm-editorial palette, and that ADR lives in the
reference implementation and has not been brought across yet. Taking the
number here would make one identifier mean two documents.

## Status

Accepted, and applied by M1. Every line of the state layer and the
signal readers in this repository is derived from the commit named
below and from nothing later.

## Context

The reference implementation is the owner's personal instance: a live
tool that runs every thirty minutes and is edited on the days it is
used. Across the six architecture-report revisions that produced this
product line, its collector grew 916 -> 1096 -> 1185 -> 1371 lines. In
the hours M0 took to land, it moved 1185 -> 1371 and its decision ledger
went from D27 to D35.

That is not a problem to be solved. It is a personal tool behaving
exactly as a personal tool should. It is a problem for a *port*, though,
because "port the collector" has no fixed referent while the collector
is moving, and every window that opens this task book would otherwise
have to re-decide whether to chase whatever landed upstream this
morning.

DP39 already settled the relationship: the two lines fork formally and
do not promise to stay in sync. What was missing was the number.

## Decision

The port baseline is:

| | |
|---|---|
| Repository | the owner's private personal instance, read-only for this line |
| Commit | `1a98cb182c8f90211aa57423dfd2d97254592554` |
| Short | `1a98cb1` |
| Date | 2026-08-11 18:39:29 +0800 |
| State at that commit | `src/collector.py` at 1371 lines; decision ledger through D35; 9 check scripts |

Read it with `git -C <reference> show 1a98cb1:src/collector.py`, never
from the working tree, which will have moved. The reference repository
is never written to by this line - not a commit, not a stash, not a
config edit - and a milestone that touches it has not passed.

**Upstream changes after this commit are reference material, not
obligations.** Nobody has to justify not chasing them. If something
landed upstream that this product wants, it arrives here as a new
decision with its own reasoning, not as a sync.

## What was ported, and what was deliberately not

Ported: the shape of the git and filesystem readers, the honest-
degradation habit, `guard_write_path()` as the single write path, the
tier bands, and - at stage two of M1 - the blocker parser with its three
refusals and the precedence rule.

Not ported, deliberately:

- **Everything that reaches the network.** The reference imports
  `urllib` and calls the GitHub API. Rule 11 forbids that in the core,
  and the MVP's second promise is that the path does not exist.
- **The whole personal shape of the roster.** Awards, records, hard
  deadlines, contribution heatmaps, model-usage panels. They are the
  owner's board, not the product's.
- **The hard-coded owner aliases.** The reference carries five, including
  a real name and a real handle - the single hard-coded human identity
  in that collector. DP19 forbids any real person's name in the shipped
  package; aliases come from configuration and default to empty.
- **The fixtures.** They are quoted from the owner's real ledgers. Rule
  10's shape cases are rewritten as synthetic text (DP21).
- **`data/` and `projects.json` living in the repository.** That is the
  arrangement `pip install --upgrade` destroys, and moving it is the
  point of the three boundaries (DP4).

## Baseline exceptions: defects, not evolution

The baseline says upstream may move freely and this repository does not
care. That holds for **evolution**. It does not hold for a **defect**:
if the reference had a bug at the pinned commit, porting that commit
later re-introduces the bug, and the fix is not upstream drift but
knowledge that was expensive to obtain and is free to accept.

The entries below are upstream fixes made after the baseline that a
future porting window must apply when it ports the affected reader.
Recorded here rather than ported now, because the code they touch does
not exist in this repository yet - verified: no contribution reader
appears anywhere under `murscope/`, `scripts/` or `design/`.
The GitHub module is M3.

Read them with `git -C <reference> show <commit>`. The reference is
read-only for this line, always.

### E1 - a range endpoint in the future returns a frozen snapshot
`a5d8e06` - affects the GitHub contributions reader (M3)

The query asked for a year ending at `{year}-12-31T23:59:59Z`. When the
endpoint lies in the future the API answers with a snapshot frozen part
way through the current day. Measured upstream on the same account in
the same second: an end of December returned 1 for the day and 1571 for
the year, while an end of "now" returned 12 and 1582. Clamp the end of
the range to the current moment.

### E2 - a cache used as a freshness shortcut, on a page that dates itself
`a5d8e06` - same commit, independent defect

A 25-minute cache TTL let a collection at 11:44 publish figures gathered
at 11:22 under a masthead reading "generated 11:44". The fix demotes the
cache to a failure fallback and re-fetches every round. The principle
generalises past GitHub and is recorded as DP48.

### E3 - "start of year to today" is a range the API has precomputed
`6a110cb` - affects the same reader (M3)

After E1 and E2 the figure was still short by one. Bisecting the start
of the range showed every start date from March through today agreeing
with the profile page, and only January 1st disagreeing: that exact
range is the one the platform precomputes and caches for its own annual
view, so it is served from cache while any other range is computed live.
The fix keeps the year range for history and overlays a fresh query for
the recent weeks, then sums the corrected daily series for the total.
Time zones were ruled out separately.

**This is the entry worth the most.** E1 and E2 are recognisable from
first principles; E3 is a platform behaviour that took a six-point
bisection to find and that no amount of care would have predicted.

### E4 - a fallback that is never rechecked
`1a77db8` - affects an AI summary layer (M3), if one is built

A degraded result was written when a quota ran out, and because the
scheduler only compared dates, it held the slot for the rest of the day
even after the quota recovered. Recorded as DP49.

### E1 and E3, re-measured on this line - and not reproduced

`2026-08-13` - the contributions reader landed at M3's third stage, and
acceptance re-measured rather than took the numbers on trust. On the
owner's account, at 06:16 UTC, against the live API:

| | Upstream, at the baseline | Here, 2026-08-13 |
|---|---|---|
| E1, end of 31 December | day 1, year 1571 | day 87, year 1844 |
| E1, end of "now" | day 12, year 1582 | day 87, year 1844 |
| E1, difference | +11 day, +11 year | **0 and 0, on every day of the series** |
| E3, six start dates | only 1 January disagreed | **all six agree, day by day** |

The E1 comparison is not a comparison of totals only: the two series were
compared date by date and differ nowhere, and the future-ended range
carried no non-zero day after today. The E3 bisection was run the way it
discriminates - six start dates from 1 January to seven-days-ago, all
ending at `now`, compared over the last seven days, which lie inside every
one of them. A start date served from a stale precompute would show a
different recent tail. None did.

One caveat is recorded rather than buried: **the start-date test that
ADR-0003 describes cannot be run on this account.** 1 January to 28
February is empty here, so "1 January" and "1 March" describe the same
non-empty data and would agree under any implementation. That is why the
bisection above compares the *recent tail* across six starts instead,
which is a test this account can actually fail.

**The corrections are kept.** The reasoning is not sentiment about
upstream work: a range that ends later than now is wrong whether or not it
is currently answered wrongly, and the single most important thing E3
established is that this class of behaviour is not predictable from first
principles - which cuts both ways. A platform that stopped doing it in
one quarter can resume in the next, and the overlay costs one small
request. What has changed is the *evidence*: the corrections are now held
by Rule 20 rather than by the observation that produced them, and Rule 20
passes on synthetic cases that do not depend on the platform's mood.

Recorded as DP101. E2 is not on this table because it was never a
platform behaviour - it was the reference implementation's own cache, so
there is nothing upstream to re-measure. Its fix is structural and is
measured directly: three requests in the reproduction run, no cache read
before any of them, and a cached reading stamped with the moment its data
was gathered.

### Not carried

Upstream `D37` (a units label switching by data source) and `D38`
(roster content) are that instance's own. They are evolution, not
defects, and the baseline stands.

## Consequences

- The reference can move freely and this repository does not care.
- A reader who wants to know where a piece of logic came from has one
  commit to look at rather than a moving target.
- Anything the product gains after this point is the product's own, and
  has to earn its place here on its own reasoning.
