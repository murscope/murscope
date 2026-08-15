"""Build the board: one static file the user double-clicks (DP38).

Dual write, as the reference does and for the same reason: `data.json`
is the machine copy a person can open and read to check what the tool
actually concluded, and `data.js` is the same payload wrapped in one
assignment so the page can load it from `file://` without a server. A
board that needs `python -m http.server` to open is not a board a user
double-clicks.

The template ships with the package and is copied into the board
directory on every run. No build step, no front-end toolchain, no
bundler: the page is HTML with a `<style>` block and a `<script>` block,
and a reader who wants to know what it does can read it.

Two constraints shape it more than taste does. It loads no remote font,
no remote stylesheet and no remote anything - the offline promise covers
the artifact, not only the collector, and a board that phones a font CDN
on open would break promise two the first time anyone looked. And every
byte it writes goes through guard_write_path(), so the board cannot land
anywhere except under MURSCOPE_HOME.

The method block is not decoration either (DP46). The board tells people
their own project is slowing down; the numbers behind that sentence are
published beside it, because a verdict about somebody's work that will
not say how it was reached is the opposite of what this tool is for.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from . import __version__, activity, boundary, collect, i18n, state
from .guard import guard_write_path, murscope_home

TEMPLATE = Path(__file__).resolve().parent / "templates" / "board.html"
BOARD_DIRNAME = "board"
SCHEMA = 2


def method_block(settings, catalog):
    """Every threshold this board judged by, in the reader's language."""
    cuts = settings.section("trend")
    window = settings.section("collect").get("trend_window_days", 90)
    recent = cuts.get("recent_days", collect.TREND_RECENT_DAYS)
    limits = state.thresholds()
    return {
        "title": i18n.translate(catalog, "method.title"),
        "numbers": dict(limits, trend_window_days=window, trend_recent_days=recent,
                        **{k: v for k, v in cuts.items()}),
        "lines": [
            i18n.translate(catalog, "method.trend").format(
                window=window, recent=recent, prior=max(0, window - recent),
                up=cuts.get("accelerating_percent",
                            collect.TREND_ACCELERATING_PERCENT),
                down=cuts.get("slowing_percent", collect.TREND_SLOWING_PERCENT),
                floor=cuts.get("min_commits", collect.TREND_MIN_COMMITS)),
            i18n.translate(catalog, "method.state").format(
                uncommitted=limits["uncommitted_idle_days"],
                unpushed=limits["unpushed_idle_days"],
                wip=limits["wip_idle_days"],
                stash=limits["stash_age_days"],
                moving=limits["moving_recent_days"],
                stale=limits["declaration_stale_days"]),
            i18n.translate(catalog, "method.inferred"),
        ],
    }


def _without_activity_path(project):
    """The record with the activity signal's source path removed (R14)."""
    signals = project.get("signals") or {}
    block = signals.get("activity")
    if not isinstance(block, dict) or "path" not in block:
        return project
    trimmed = dict(project)
    trimmed["signals"] = dict(signals)
    trimmed["signals"]["activity"] = {
        key: value for key, value in block.items() if key != "path"}
    return trimmed


def _activity_line(project):
    """The activity clock's age, and nothing else about it (DP22, R14).

    The age only - never the path it came from. Rule 14 keeps `last_touch`
    and its source path out of any outbound payload, and a board file is
    outbound the moment somebody sends it to a colleague.
    """
    block = (project.get("signals") or {}).get("activity") or {}
    if block.get("quality") != "ok":
        return None
    return {"age_days": block.get("age_days")}


def hints(catalog, settings):
    """What an enhancement would add, stated and never asked for (DP35).

    The board may say what a GitHub token or an API key would buy. It may
    not ask for either, and nothing may stand between the scan and the
    board - so these are sentences at the bottom of a page that already
    rendered, not a step in front of it. The distinction is the whole of
    DP35: telling somebody what exists is giving them something, and
    stopping them until they provide it is asking.
    """
    lines = [i18n.translate(catalog, "hint.github"),
             i18n.translate(catalog, "hint.ai")]
    # Only when it is actually off. It used to be emitted unconditionally,
    # so a board built with the clock switched on told the reader the clock
    # was off - a hint about a setting, contradicting the setting.
    clock_on, _source, _problems = activity.configured(settings)
    if not clock_on:
        lines.append(i18n.translate(catalog, "hint.activity"))
    return lines


def honest_promise(catalog):
    """The catalog with the footer's promise line matched to this install.

    The board's footer carried "Makes no network call" on every install.
    That was true on both for exactly as long as the transport refused to
    send anything - and stage two supplies the consent it was waiting for,
    so the sentence expired the day the capability arrived. A promise
    printed on the artifact is the last place to find that out.

    The substitution happens on the **catalog**, not on the template. The
    board's JavaScript reads `t("board.promise")` and nothing in this
    repository executes that template (DP85), so a second key rendered by
    a new template line would be a change no check could reach. Replacing
    the value the existing line already renders puts the whole decision in
    Python, where `murscope selftest` measures both branches.

    A missing `board.promise.network` renders the loud `[[MISSING:key]]`
    marker rather than silently falling back to the base sentence: a
    footer that quietly reverts to "makes no network call" on an install
    that can is the failure this function exists to prevent.
    """
    reaching = boundary.survey().reaching
    if boundary.promise_key(reaching) == boundary.BASE_PROMISE_KEY:
        return catalog
    amended = dict(catalog)
    amended[boundary.BASE_PROMISE_KEY] = i18n.translate(
        catalog, boundary.NETWORK_PROMISE_KEY)
    return amended


def build_document(projects, settings, locale, catalog, problems, providers):
    """The payload both files carry. Pure data: no I/O, no formatting.

    Rule 7 is applied again here, on every row. Collection already refuses
    to open a sensitive project's files, but keys are added to a record
    after collection returns - `home_overlap`, `state`, anything a
    provider contributes - and an audit showed that the shield sat before
    all three. This is the last place a record exists before it is
    written, so it is the right place for the net.
    """
    # Rounded once, in Python, so the activity column and the state
    # sentence cannot disagree - and rounded *before* the shield, not
    # after. Adding it afterwards put a key outside the whitelist into a
    # sensitive row's payload, which made the sentence above `shield()`
    # about being the last place a record exists into a false one.
    # Rule 14, the half about the source path - and the reason is specific
    # to the *activity source*, not to paths in general.
    #
    # The first version of this comment said "a board file is outbound the
    # moment somebody sends it to a colleague", which is true and is also
    # too wide: it covers `signals.tree.path` word for word, and that one is
    # deliberately kept (see `walk_tree` in collect.py). A reason that
    # reaches further than its implementation is the shape this project
    # keeps finding, and it turned up here in a justification written to fix
    # exactly that.
    #
    # What is specific: at M4 the activity source becomes an adapter that
    # reads an **external tool's** directory - somebody's session
    # transcripts - so a path from it is a path into data the user never
    # listed. Putting the MVP adapter's path in the payload would establish
    # the habit for the adapter where it matters. Stripped here rather than
    # never recorded, because `status --explain` saying which file was newest
    # is worth having in a terminal.
    projects = [_without_activity_path(p) for p in projects]

    # Only where there is one. Adding `activity: None` to every row would
    # put a key on a sensitive record that Rule 14 rightly refuses to see in
    # the whitelist - and a sensitive entry has no activity signal at all,
    # because its file readers never run. So the key simply is not there.
    projects = [dict(p, activity=_activity_line(p)) if _activity_line(p)
                else p for p in projects]
    projects = [dict(p, recency_days_display=state.whole_days(
        p.get("recency_days") if isinstance(p.get("recency_days"), (int, float))
        else None)) for p in projects]
    projects = [collect.shield(dict(p), strict=True) for p in projects]
    catalog = honest_promise(catalog)
    def count(predicate):
        return sum(1 for project in projects if predicate(project))

    return {
        "schema": SCHEMA,
        "generator": "murscope %s" % __version__,
        "generated_at": datetime.now(timezone.utc).astimezone().isoformat(
            timespec="seconds"),
        "home": str(murscope_home()),
        "locale": locale,
        "i18n": catalog,
        "problems": list(problems),
        "providers": providers,
        "method": method_block(settings, catalog),
        "hints": {"title": i18n.translate(catalog, "hint.title"),
                  "lines": hints(catalog, settings)},
        "stats": {
            "projects": len(projects),
            "active": count(lambda p: p.get("tier") == "ACTIVE"),
            # Read from `state`, which is also where `init`'s summary screen
            # gets these. The two screens each had their own definition and
            # printed different numbers about one collection; see the note
            # above `state.uncommitted_files`.
            "in_hand": count(lambda p: state.uncommitted_files(p) > 0),
            "unsent": count(lambda p: state.unpushed_commits(p) > 0),
            "owed": count(lambda p: p.get("owner_queue")),
            # Aliases are seeded from authorship at init (DP63), so the
            # naming half of "waiting on you" usually works - but it can
            # still be off, or on and unable to place a particular name.
            # The board publishes both facts rather than printing a number
            # that looks settled.
            "owner_aliases": len([a for a in settings.section("blockers")
                                  .get("owner_aliases", []) if a]),
            # Declarations that name a person we could not match to the
            # user. This, not the alias count, is what decides whether the
            # owed tile may print a number: an alias that exists but never
            # matches used to switch the honest marker off and leave a
            # confident zero in its place - a fix that made the board less
            # truthful than no fix at all.
            "owner_unmatched": count(
                lambda p: ((p.get("state") or {}).get("names_somebody")
                           and not (p.get("state") or {}).get("owner"))),
            "degraded": count(lambda p: p.get("signal_quality") != "ok"),
        },
        "projects": projects,
    }


def write_board(document, home=None):
    """Write data.json, data.js and index.html. Returns the paths written."""
    root = (home or murscope_home()) / BOARD_DIRNAME
    payload = json.dumps(document, indent=2, sort_keys=True, ensure_ascii=True)

    written = [guard_write_path(root / "data.json", payload + "\n")]
    written.append(guard_write_path(
        root / "data.js",
        "/* Written by murscope. Regenerated on every run; edit nothing here. */\n"
        "window.MURSCOPE_BOARD = " + payload + ";\n"))
    written.append(guard_write_path(
        root / "index.html", TEMPLATE.read_text(encoding="utf-8")))
    return written


def render(projects, settings, catalog, locale, problems, providers, home=None):
    """Collected projects in, three files out."""
    document = build_document(projects, settings, locale, catalog, problems,
                              providers)
    return document, write_board(document, home)
