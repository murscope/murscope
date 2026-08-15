"""`murscope init`: from nothing to a board, in one command (DP34, DP36).

Two commands is the promise - install, then this - and the default path
through here costs **one keystroke**. Not one confirmation per project:
one, for all of them.

The summary screen is the piece worth explaining. After the scan and
before the board, one screen and one question. It is the first delivery
of value in the whole product, because it answers "how much have I
actually got on my plate" before any board exists, and it does that with
sentences the user did not write about projects they did not list.

**Only inferred things are editable.** Whether a directory is a project,
what it is called, which file is its ledger - those are guesses and the
scan gets them wrong. A commit timestamp is computed; the user can
neither confirm nor deny it, and putting a fact up for confirmation
implies we are unsure of it, which costs more credibility than the
occasional wrong guess does.

This does not violate DP35. That rule constrains asking the user *for*
something - a key, an authorisation, a subscription. This is giving them
something and offering to be corrected.

**Incremental, not a ceremony.** `--add` widens the
authorised set later; the roster is merged rather than replaced, and
anything the user wrote - a note, a chosen ledger, a renamed project -
survives a rescan, because losing a correction is how a tool teaches
people to stop correcting it.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

from . import (cli, config, doctor, i18n, markers, providers, registry,
               render, scan, state, width)
from .guard import guard_write_path, murscope_home

# Where a first run looks when the user names nothing. Conventional
# directories only, and only the ones that exist - this is a guess, so
# it is a small one, it is printed before anything is scanned, and
# `init <path>` overrides it entirely.
CONVENTIONAL_ROOTS = ("code", "src", "Projects", "projects", "dev",
                      "repos", "workspace", "git", "Documents")

STATE_WIDTH = 38
NAME_WIDTH = 22


def _progress(name, tier):
    print("  found %-6s %s" % (tier, name), flush=True)


def default_roots():
    """Conventional project directories that exist under the home.

    Deduplicated by identity, not by name. The table above lists both
    `Projects` and `projects`, and on a case-insensitive filesystem - the
    macOS default - a home with either one matched both, so this returned
    two paths to one directory and the line printed above the scan named
    it twice. See `scan.distinct_roots`.
    """
    home = Path.home()
    found = []
    for name in CONVENTIONAL_ROOTS:
        candidate = home / name
        if candidate.is_dir():
            found.append(candidate)
    return scan.distinct_roots(found)


def resolve_paths(raw):
    """(paths, problems): expand ~, resolve, and refuse the wrong shapes."""
    paths = []
    problems = []
    for item in raw:
        path = Path(os.path.expanduser(str(item)))
        if not path.exists():
            problems.append("%s does not exist." % path)
            continue
        if path.is_file():
            problems.append(
                "%s is a file. Point init at the directory that holds your "
                "projects, or at one project." % path)
            continue
        try:
            resolved = path.resolve()
        except OSError as exc:
            problems.append("%s cannot be resolved (%s)." % (path, exc))
            continue
        if resolved not in paths:
            paths.append(resolved)
    # By identity as well as by string: `init ~/code ~/Code` names one
    # directory twice on a case-insensitive filesystem, and resolving does
    # not fold the case.
    return scan.distinct_roots(paths), problems


def seed_aliases(home, settings, names):
    """Write owner aliases into config.toml, once, without clobbering.

    DP63: the names come from the authorship on the user's own commits.
    They land in the user's own file under MURSCOPE_HOME - never in the
    package, which DP19 forbids and a check enforces.

    **It only ever creates.** If `config.toml` already exists, this leaves
    it alone and returns the line to add: there is no TOML writer here,
    appending a `[blockers]` table to a file that may already have one
    produces a duplicate-table error, and silently rewriting a
    configuration the user wrote is worse than not helping.
    """
    path = home / config.CONFIG_NAME
    if not names:
        return None, "no authorship found, so no owner names were seeded."
    listed = ", ".join('"%s"' % n.replace('"', "") for n in names)
    if path.exists():
        return None, ("config.toml already exists, so it was left alone. To "
                      "count a ledger line that names you, add:\n"
                      "    [blockers]\n    owner_aliases = [%s]" % listed)
    body = (
        "# Written by murscope init. Yours to edit; upgrades never touch it.\n"
        "\n"
        "[blockers]\n"
        "# From the author name on your own commits, or what you typed on the\n"
        "# summary screen (DP63). A ledger\n"
        "# line reading \"waiting on <one of these>\" then counts as waiting\n"
        "# on you. Remove a name and it stops counting; nothing else reads\n"
        "# these.\n"
        "owner_aliases = [%s]\n" % listed)
    guard_write_path(path, body)
    return path, ("owner names written to config.toml: %s" % ", ".join(names))


def _apply_aliases(settings, names):
    """Put the aliases into the live configuration and rebuild the vocabulary.

    In memory. `config.toml` is written when the user accepts, and this is
    what makes the first board agree with it.
    """
    blockers = dict(settings.section("blockers"))
    blockers["owner_aliases"] = list(names)
    settings.values["blockers"] = blockers
    return settings, markers.resolve(settings.locale, blockers)


def merge_roster(existing, candidates):
    """Existing entries win; scanned ones are added.

    What the user wrote survives a rescan. An entry they renamed, gave a
    note to, or pointed at a particular ledger keeps all of it, because a
    tool that discards a correction on the next run has taught the user
    that correcting it is not worth the keystrokes.
    """
    rows = []
    seen_roots = set()
    for entry in existing:
        rows.append(dict(entry.raw))
        if entry.path:
            seen_roots.add(str(Path(entry.path).resolve()))
    added = 0
    for candidate in candidates:
        if str(candidate.path) in seen_roots:
            continue
        rows.append(candidate.entry())
        added += 1
    return {"projects": rows}, added


def _one_line_total(records):
    """The sentence, not the tally (DP56).

    It is the first thing said about somebody's entire body of work, and
    a row of counts separated by dots reads like a linter report.

    The three git counts come from `state`, which is also where the board's
    tiles get theirs. They used to be computed here from *which rule won
    the state column*, so one `init` said "8 are holding uncommitted work"
    and the board it wrote seconds later said "10 with uncommitted work" -
    the same collection, two definitions, both printed as fact.

    The literal reading is settled (DP73, ruled 2026-08-13): a row with
    uncommitted files is counted here whatever its state column says. The
    rows that used to make the two look contradictory now say what they
    are holding in their own sub-text - see `_row` - so the sentence and
    the rows below it can be reconciled by reading them.
    """
    moved = sum(1 for r in records
                if isinstance(r.get("recency_days"), (int, float))
                and r["recency_days"] <= 7)
    holding = sum(1 for r in records if state.uncommitted_files(r) > 0)
    halfway = sum(1 for r in records if state.stopped_halfway(r))
    unsent = sum(1 for r in records if state.unpushed_commits(r) > 0)

    def plural(count, one, many):
        return (one if count == 1 else many) % count

    parts = []
    if moved:
        parts.append(plural(moved, "%d moved this week",
                            "%d moved this week"))
    if holding:
        parts.append(plural(holding, "%d is holding uncommitted work",
                            "%d are holding uncommitted work"))
    if unsent:
        parts.append(plural(unsent, "%d finished something and never sent it",
                            "%d finished something and never sent it"))
    if halfway:
        parts.append(plural(halfway, "%d stopped halfway",
                            "%d stopped halfway"))
    if not parts:
        return "Nothing is outstanding anywhere."
    if len(parts) == 1:
        return parts[0].capitalize() + "."
    return "%s, and %s." % (", ".join(parts[:-1]), parts[-1])


# `_clip` used to live here and count characters. It is gone rather than
# fixed in place, and both halves of the move matter (DP86). The clip is
# now `width.clip`, which counts terminal cells; and the *padding* moved
# with it, because the defect was never the clip alone - it was a `_clip`
# measuring one thing sitting beside a `%-*s` measuring another, so a row
# trimmed correctly was still padded to the wrong place. Every cell of
# this screen's table goes through `width.column`, which does both.


def _wrap_also(also, budget):
    """The sub-text packed into lines, with nothing dropped (DP82).

    `budget` is in cells, and the parameter is not called `width` because
    `width` is the module that measures them.

    This used to be one line, clipped to the width of the row above. What
    the clip removed was the sub-text's whole reason for existing: a row
    holding all four things printed "stopped halfway - 2 commits finished
    but..." while the tile beside it counted the uncommitted work the clip
    had just taken off the screen. DP80 shipped to close exactly that gap
    and did not close it here.

    Breaks fall only between items, so no sentence is ever cut, and an
    item wider than the budget takes a line to itself and overruns it. On
    this screen an over-long line is a smaller lie than a short one, and
    the alternative - abbreviating the sentences to fit - is the same
    defect committed one layer down.

    The budget is spent in cells rather than characters (DP86). Measured
    in characters, a `zh` sub-text packed three sentences onto one line
    that then drew 13 cells past the row above it; in cells the same three
    take two lines and neither overruns.
    """
    lines = []
    current = []
    length = 0
    for item in also:
        addition = width.cells(item) + (3 if current else 2)
        if current and length + addition > budget:
            lines.append("· " + " · ".join(current))
            current, length = [], 0
            addition = width.cells(item) + 2
        current.append(item)
        length += addition
    if current:
        lines.append("· " + " · ".join(current))
    return lines


def _row(index, record, candidate):
    """One row, and under it what its headline suppressed (DP80).

    A declaration or a note wins the state column outright, so a project
    whose ledger says "waiting on the vendor" said that and only that -
    while the sentence a few lines below counted it among the ones holding
    uncommitted work. Both true, neither reconcilable from the screen.

    The sub-text is the missing half and is deliberately only that: what
    the row has *in hand*. It is not a second state column, and nothing
    else belongs in it - a row that turns into a list of measurements is
    what DP56 refused when it chose a sentence over a tally.

    The indent and the width are both measured off the row above rather
    than typed, so widening a column cannot leave the sub-text under the
    wrong one, and the block never grows wider than the row it belongs to.
    The width is where the block *wraps*, not where it is cut: a row
    holding four different things spends the extra lines (DP82). Nine
    synthetic rows produce one such row and a real twenty-project
    workspace produced none, so the screen still stays a screen - and
    where it cannot, the fact wins over the line count.

    Every measurement here is in terminal cells (DP86). The two columns
    are `width.column`, which clips and pads in the same unit, and the
    indent under the row is counted in cells too - `" " * len(head)` put
    the sub-text of a row named with six ideographs at cell 31 while the
    sentence it hangs under started at cell 37, because `head` holds the
    project's name and a name can be wide.
    """
    name = record.get("name") or record.get("id") or "?"
    st = record.get("state") or {}
    inferred = "?" if st.get("kind") == "inferred" else " "
    ledgers = (candidate.ledgers if candidate is not None
               else record.get("ledgers") or [])
    source = ledgers[0] if ledgers else "- none"
    head = "  %-3d %s %s " % (index, width.column(name, NAME_WIDTH), inferred)
    lines = ["%s%s %s" % (head, width.column(st.get("text") or "", STATE_WIDTH),
                          source)]
    # Only where there is something to say. An empty list must leave no
    # bullet and no blank line behind it: a row with nothing in hand looks
    # exactly as it did before this existed.
    also = st.get("also") or []
    indent = width.cells(head)
    for line in _wrap_also(also, width.cells(lines[0]) - indent):
        lines.append(" " * indent + line)
    return "\n".join(lines)


def _collapsed_clause(found):
    """Why the collapsed rows are collapsed, split by cause.

    One phrase used to cover both causes - "%d older or non-git one(s)
    collapsed" - and the cap was one of them. Three repositories committed
    to seconds before the scan were reported as older or non-git, and the
    cap that actually excluded them was never printed at all.
    """
    aged = found.collapsed - found.capped
    parts = []
    if aged:
        parts.append("%d older or non-git one%s" % (aged, "" if aged == 1 else "s"))
    if found.capped:
        parts.append("%d recent one%s past the cap of %d"
                     % (found.capped, "" if found.capped == 1 else "s",
                        found.cap))
    if not parts:
        return ""
    return "; %s collapsed - press e to see them" % " and ".join(parts)


def _header(catalog):
    """The column headings, out of the catalog rather than out of English.

    These three were typed in English while the rows under them came from
    `state.resolve`, which is given the catalog and answers in the locale.
    Under `locale = "zh"` the screen printed a Chinese table with an
    English heading over it (DP83). The keys are the board's own - the
    board already renders `col.project` and `col.state` over the same two
    columns - so this reuses a vocabulary rather than opening a second one
    beside it; only `col.ledger` is new, because the board has no such
    column.

    Kept in a function of its own so Rule 8's check has something to
    anchor on: every string constant here that is not the format template
    must be a key present in every locale. That is a narrow guard and is
    meant to be - it holds this heading and claims nothing about the rest
    of the screen, which is English on purpose and recorded as such.

    Measured in cells like the rows under it (DP86), and clipped as well
    as padded. A heading is the one string on this screen a translator
    chooses freely, so it is also the one that can silently be wider than
    its column; `zh` reads `col.state` as four ideographs, which `%-38s`
    counted as four and a terminal draws as eight.
    """
    return "  #   %s   %s %s" % (
        width.column(i18n.translate(catalog, "col.project"), NAME_WIDTH),
        width.column(i18n.translate(catalog, "col.state"), STATE_WIDTH),
        i18n.translate(catalog, "col.ledger"))


def summary_screen(found, records, by_id, seconds, catalog):
    """Print the one screen. Returns nothing; the caller asks the question."""
    clock = ("under a second" if seconds < 1 else "%.0fs" % seconds)
    print("\nScanned %d directories in %s. %d project%s included%s."
          % (found.directories_seen, clock, len(records),
             "" if len(records) == 1 else "s", _collapsed_clause(found)))
    excluded = []
    if found.excluded_worktrees:
        excluded.append("%d worktree%s" % (found.excluded_worktrees,
                                           "" if found.excluded_worktrees == 1
                                           else "s"))
    if found.excluded_bare:
        excluded.append("%d bare repo%s" % (found.excluded_bare,
                                            "" if found.excluded_bare == 1
                                            else "s"))
    if found.containers:
        excluded.append("%d folder%s that only hold repositories"
                        % (found.containers,
                           "" if found.containers == 1 else "s"))
    if excluded:
        print("Not proposed: %s." % ", ".join(excluded))

    print()
    print(_header(catalog))
    for index, record in enumerate(records, start=1):
        print(_row(index, record, by_id.get(record.get("id"))))

    print("\n  %s" % _one_line_total(records))
    print("\n  ? marks an inference - a guess with its working shown.")


def expand(found, shown_ids):
    print("\ncollapsed, not selected:")
    any_capped = False
    for candidate in found.candidates:
        if candidate.identifier in shown_ids:
            continue
        age = candidate.last_commit_days
        clock = ("last commit %d days ago" % round(age) if age is not None
                 else "touched %d days ago" % round(candidate.mtime_days)
                 if candidate.mtime_days is not None else "not scanned")
        # The reason this row is here, which is not always its tier. A
        # capped row printed `tier2` - this scan's own name for ">90 days"
        # - directly beside "last commit 0 days ago".
        why = "capped" if candidate.capped else candidate.tier
        any_capped = any_capped or candidate.capped
        # The same column as the row above, so it is measured the same way
        # (DP86). This used to be `name[:NAME_WIDTH]`, a hard slice by
        # character that both over-ran the column on a wide name and cut a
        # word in half on a long one.
        print("  %s %-8s %s" % (width.column(candidate.name, NAME_WIDTH),
                                why, clock))
    if any_capped:
        print("\n  capped: recent enough for the first screen, past the cap of "
              "%d. Not old, and not dropped." % found.cap)
    print("\n  These are in the roster's reach but not selected. Add one with "
          "murscope init --add <path>.")


def ask(records, by_id, found, alias_names):
    """The one question. Returns (records to keep, aliases), or (None, ...)."""
    shown = list(records)
    aliases = list(alias_names)
    shown_ids = {r.get("id") for r in shown}
    while True:
        print("\n  [Enter] build the board   <number> rename or repoint one   "
              "d<number> drop one   o owner names   e expand   q quit")
        try:
            answer = input("  > ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return shown, aliases
        if not answer:
            return shown, aliases
        if answer == "q":
            return None, aliases
        if answer == "o":
            aliases = _edit_aliases(aliases)
            continue
        if answer == "e":
            expand(found, shown_ids)
            continue
        if answer.startswith("d") and answer[1:].strip().isdigit():
            index = int(answer[1:].strip())
            if 1 <= index <= len(shown):
                dropped = shown.pop(index - 1)
                print("  dropped %s" % (dropped.get("name")))
            else:
                print("  there is no row %d" % index)
            continue
        if answer.isdigit():
            index = int(answer)
            if not 1 <= index <= len(shown):
                print("  there is no row %d" % index)
                continue
            _edit(shown[index - 1], by_id.get(shown[index - 1].get("id")))
            continue
        print("  did not understand %r" % answer[:20])


def _edit_aliases(aliases):
    """Correct the seeded owner names before anything is written."""
    print("\n  Owner names: %s" % (", ".join(aliases) or "none"))
    print("  A ledger line reading \"waiting on <one of these>\" counts as "
          "waiting on you. Word order does not matter.")
    try:
        answer = input("  names, comma separated [keep]: ").strip()
    except (EOFError, KeyboardInterrupt):
        return aliases
    if not answer:
        return aliases
    if answer in ("-", "none"):
        print("  cleared; no ledger line will be matched to you by name.")
        return []
    return [part.strip() for part in answer.split(",") if part.strip()]


def _edit(record, candidate):
    """Rename, or point at a different ledger. Facts are not offered."""
    print("\n  %s" % (record.get("name")))
    print("  Only what was guessed can be changed here: what this is called, "
          "and which file speaks for it.")
    try:
        name = input("  name [%s]: " % record.get("name")).strip()
    except (EOFError, KeyboardInterrupt):
        return
    if name:
        record["name"] = name
        record["_renamed"] = True

    options = []
    if candidate is not None:
        options = list(candidate.ledgers) + list(candidate.offers)
    if not options:
        print("  no ledger file was recognised here, so there is nothing to "
              "point at yet.")
        return
    print("  ledger source:")
    for number, rel in enumerate(options, start=1):
        kind = ("read now" if candidate and rel in candidate.ledgers
                else "recognised, not read")
        print("    %d  %-34s %s" % (number, rel, kind))
    print("    0  none")
    try:
        choice = input("  which [keep]: ").strip()
    except (EOFError, KeyboardInterrupt):
        return
    if not choice:
        return
    if choice == "0":
        record["_ledgers"] = []
        return
    if choice.isdigit() and 1 <= int(choice) <= len(options):
        record["_ledgers"] = [options[int(choice) - 1]]
    else:
        print("  did not understand %r; kept what was there" % choice[:20])


def interactive():
    return sys.stdin.isatty() and sys.stdout.isatty()


def run(argv):
    """`init [<path> ...] [--add <path>] [--yes]`. Returns an exit code."""
    assume_yes = "--yes" in argv or "-y" in argv
    raw = [a for a in argv if not a.startswith("-")]
    for flag in ("--add",):
        while flag in argv:
            argv.remove(flag)

    home = murscope_home()
    (settings, existing, locale, catalog, vocabulary), problems = cli.prepare(home)
    sealed = config.sealed_dirs(settings.section("scan").get("sealed_dirs", []))

    if raw:
        roots, path_problems = resolve_paths(raw)
    else:
        # A sensitive entry's root is not rescanned. Rule 7 says such a
        # project exposes method only, and walking inside it would put the
        # names of its subdirectories on the summary screen - which is
        # information from inside the project, whatever else it is. The
        # entry stays on the board; it is only the *rescan* that stops.
        roots = [Path(e.path) for e in existing
                 if e.path and not e.sensitive] or default_roots()
        sealed_out = [e.id for e in existing if e.path and e.sensitive]
        if sealed_out:
            print("Not rescanned, because they are marked sensitive: %s"
                  % ", ".join(sealed_out))
        path_problems = []
        if roots:
            print("No path given, so murscope is looking in: %s"
                  % ", ".join(str(r) for r in roots))
            print("Point it somewhere else with: murscope init <path>")
    for line in path_problems:
        print("murscope init: %s" % line)
    if not roots:
        print("murscope init: nothing to scan.\n"
              "  usage: murscope init <path>            authorise a directory\n"
              "         murscope init --add <path>      widen it later")
        return 2

    report = doctor.check(roots, sealed)
    if doctor.blocked(report):
        doctor.render(report)
        return 1

    print("\nscanning %s" % ", ".join(str(r) for r in roots))
    # The design authority asks for visible progress and the first
    # version had none: a sixty-second budget with a silent terminal is
    # indistinguishable from a hang, and the user's only move is Ctrl-C.
    found = scan.discover(roots, sealed, progress=_progress)
    if not found.candidates:
        print("Nothing here looks like a project: %d directories walked, no "
              "repository and no recently touched directory among them."
              % found.directories_seen)
        return 1

    # DP63, and the order matters. Seeding has to happen before collection,
    # not after: a name-based "waiting on you" match is resolved while the
    # ledger is parsed, so aliases written after the fact would not reach
    # the first board - the user would see the blind tile once and a
    # correct one only on the next run. Prefilled rather than asked for,
    # which leaves DP35 alone: this gives the user something.
    # Proposed here, written only if the user accepts. The first version
    # wrote config.toml at this point - before the summary screen, before
    # the one question, and before `q` could decline - so the names were
    # on disk by the time anybody saw them, and `ask()` offered no way to
    # change them. A guess the user cannot correct at the moment it is
    # shown is not a proposal.
    alias_names, alias_scanned = ([], 0)
    if not settings.section("blockers").get("owner_aliases"):
        alias_names, alias_scanned = scan.alias_candidates(found.selected)

    document, added = merge_roster(existing, found.selected)
    guard_write_path(home / config.ROSTER_NAME,
                     json.dumps(document, indent=2, ensure_ascii=True) + "\n")

    (settings, roster, locale, catalog, vocabulary), reread = cli.prepare(home)
    problems.extend(p for p in reread if p not in problems)
    # The roster was just written; anything that said it was missing is now
    # wrong (see cli.STALE_ABSENCE).
    problems = cli.drop_stale_absences(problems)

    # Applied in memory before collecting, written only if the user
    # accepts. Both halves matter and the first two attempts each got one:
    # writing the file early meant the names were on disk before anybody
    # saw them, and deferring the write meant collection ran without them,
    # so a ledger line naming the user did not match on the first board.
    # Whether a declaration names the owner is decided while the ledger is
    # parsed, so the aliases have to exist *here*, in the vocabulary - the
    # file is a record of the decision, not the mechanism.
    if alias_names:
        settings, vocabulary = _apply_aliases(settings, alias_names)
    records, collect_problems = cli.collect_records(
        roster, settings, catalog, vocabulary)
    problems.extend(collect_problems)
    by_id = {c.identifier: c for c in found.selected}

    summary_screen(found, records, by_id, found.seconds, catalog)
    if alias_names:
        print("  Owner names, from the authorship on %d of your project(s): %s"
              % (alias_scanned, ", ".join(alias_names)))
        print("    a ledger line naming one of these counts as waiting on you"
              " - press o to change them")
    elif alias_scanned:
        print("  No owner name was clear enough to seed: the leading authors "
              "were level across your projects. Nothing was written - add "
              "blockers.owner_aliases yourself if a ledger line names you.")

    if assume_yes or not interactive():
        if not assume_yes:
            print("\n  (not a terminal, so taking the default: building the "
                  "board)")
        kept = records
    else:
        kept, edited = ask(records, by_id, found, alias_names)
        if kept is not None and edited != alias_names:
            # The user corrected the guess, so the rows have to be judged
            # again: `waiting on <name>` was resolved with the old list.
            alias_names = edited
            settings, vocabulary = _apply_aliases(settings, alias_names)
            records, recollect = cli.collect_records(
                roster, settings, catalog, vocabulary)
            problems.extend(p for p in recollect if p not in problems)
            # Re-apply what the user decided, instead of throwing it away.
            # `kept = records` was the bug: the screen said "dropped one"
            # and then every row went onto the board, because the fresh
            # collection replaced the edited list wholesale. Drops and
            # renames both vanished, whatever order they were made in.
            kept = _reapply(kept, records)
        if kept is None:
            print("  nothing was built. The roster is at %s and murscope run "
                  "will pick it up." % (home / config.ROSTER_NAME))
            return 0

    if alias_names:
        _path, note = seed_aliases(home, settings, alias_names)
        print("  %s" % note)
    _persist(home, document, kept)
    # Count what actually landed, not what the scan proposed: a row the
    # user dropped on the summary screen was never added, and saying it
    # was is the kind of small lie that makes someone re-check the rest.
    before = {e.id for e in existing}
    added = sum(1 for r in kept if r.get("id") not in before)
    return _build(home, kept, settings, locale, catalog, problems, added)


def _reapply(decided, fresh):
    """Carry the user's decisions onto a freshly collected set of rows.

    Keyed by id: the rows the user kept, in the order they left them, with
    any name they typed. A recollection is a new list of objects, so the
    decisions have to be transferred rather than assumed to survive.
    """
    by_id = {row.get("id"): row for row in fresh}
    out = []
    for row in decided:
        current = by_id.get(row.get("id"))
        if current is None:
            out.append(row)
            continue
        if row.get("_renamed"):
            current["name"] = row["name"]
            current["_renamed"] = True
        if "_ledgers" in row:
            current["_ledgers"] = row["_ledgers"]
        out.append(current)
    return out


def _persist(home, document, kept):
    """Write back what the user changed, and only that."""
    keep_ids = {r.get("id") for r in kept}
    rows = []
    for row in document["projects"]:
        if row.get("id") not in keep_ids:
            continue
        for record in kept:
            if record.get("id") != row.get("id"):
                continue
            if record.get("_renamed"):
                row["name"] = record["name"]
            if "_ledgers" in record:
                if record["_ledgers"]:
                    row["ledgers"] = record["_ledgers"]
                else:
                    row.pop("ledgers", None)
        rows.append(row)
    guard_write_path(home / config.ROSTER_NAME,
                     json.dumps({"projects": rows}, indent=2,
                                ensure_ascii=True) + "\n")


def _build(home, records, settings, locale, catalog, problems, added):
    """Render the board from what was already collected."""
    loaded, provider_problems = providers.load(
        settings.section("providers").get("enabled", []))
    problems.extend(provider_problems)
    document, written = render.render(
        records, settings, catalog, locale, problems,
        registry.describe_all(), home)
    print("\n%d project(s) on the board, %d newly added -> %s"
          % (len(records), added, written[-1]))
    print("  refresh it later with: murscope run")
    print("  correct a guess with:  murscope note <project> \"...\"")
    return 0
