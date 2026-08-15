"""The five-state ladder: the column that must never be blank (DP33).

    declared    the project's own ledger says so
    inferred    derived from weak signals, badged, with its evidence
    curated     the user wrote it in the roster
    no-source   nothing readable, and no weak signal to fall back on
    none        read, computed, and genuinely nothing to say

Two of those five carry the weight of this milestone.

**`no-source` and `none` are different facts and different code paths.**
"We did not look" and "we looked and found nothing" are not the same
sentence, and the reference implementation returns the same empty value
for both. Collapsing them is the dishonest degradation every other rule
in this repository exists to prevent (DP20). They are built by two
separate functions here, `_no_source()` and `_nothing_to_flag()`, and
neither can be reached from the other's branch.

**`inferred` never impersonates `declared`.** An inference carries a
badge, a different rule style on the board, and the evidence that
produced it, plus the one command that promotes it to something the user
wrote. It is a guess the tool is willing to show its working for; a
declaration is a quotation.

Coverage lives in the inference table (DP32). Measured on the reference
implementation, an explicit marker fires on one project in thirteen. The
other twelve get their state from signals 3 to 6, which every git
repository emits without anybody learning a convention - and that shift
is the whole reason this column can be non-empty for a stranger.

**The table below is not the design authority's; DP51 replaced it.**
Measured on real repositories with no ledger habit, that version made a
substantive judgment for barely half of them, and the diagnosis
mattered more than
the number: `no-source` and `degraded` were zero, so every repository had
handed over signals 3 to 6 exactly as DP32 predicted. What failed was the
mapping from those signals to a sentence, in two places:

* **an intersection gap** - all four in-hand rules required
  `idle >= threshold` while "moving normally" required a clean tree, so
  *active, and has work in hand*, the commonest state a working
  repository is in, matched no rule at all;
* **a missing row** - "clean and quiet for a long time" had no sentence,
  though the tier column already knew it.

The principle that replaces them: **what a project has in hand is stated
regardless of idleness.** Idleness changes the wording, not whether we
speak. Every in-hand rule therefore has two phrasings, and `thresholds()`
is now a wording table rather than a gate.
"""
from __future__ import annotations

from . import i18n

DECLARED = "declared"
INFERRED = "inferred"
CURATED = "curated"
NO_SOURCE = "no-source"
NONE = "none"

# The owner picked border language over colour blocks (2026-08-12): a
# solid rule for a quotation, a dashed one for a guess, a hairline for
# something the user wrote, nothing at all for the two that have no
# claim to make. Colour stays redundant with the label; shape carries
# the distinction, which is what stops an inference reading as a
# declaration before anyone has read the badge.
#
# The class is emitted here rather than decided in the template so that
# B4 can be checked by grepping one file: the data says which treatment
# each row gets, and the stylesheet says what each treatment looks like.
CSS_CLASS = {
    DECLARED: "st-declared",
    INFERRED: "st-inferred",
    CURATED: "st-curated",
    NO_SOURCE: "st-no-source",
    NONE: "st-none",
}

# The numbers are the design authority's; what they do is not (DP51).
# They no longer decide whether an in-hand rule fires - only whether its
# sentence takes the "and it has been a while" form. Keeping the same
# values makes the change legible in a diff: the wording moved, the cut
# points did not, and nothing here was retuned to raise a percentage
# (DP52).
#
# MOVING_RECENT_DAYS is the exception and still divides two rules: under
# it a clean tree reads as moving, over it as quiet. It has to divide
# something, because "clean" is one condition and the board owes it two
# different sentences.
UNCOMMITTED_IDLE_DAYS = 7
UNPUSHED_IDLE_DAYS = 14
WIP_IDLE_DAYS = 3
STASH_AGE_DAYS = 30
MOVING_RECENT_DAYS = 7
STALE_DAYS = 14


def thresholds():
    """Every number this module judges by, for the board to publish.

    DP46: a verdict about somebody's own work that does not say how it
    was reached is the opposite of what this product is for.
    """
    return {
        "uncommitted_idle_days": UNCOMMITTED_IDLE_DAYS,
        "unpushed_idle_days": UNPUSHED_IDLE_DAYS,
        "wip_idle_days": WIP_IDLE_DAYS,
        "stash_age_days": STASH_AGE_DAYS,
        "moving_recent_days": MOVING_RECENT_DAYS,
        "declaration_stale_days": STALE_DAYS,
    }


def _phrase(catalog, key, **values):
    """A locale string with its counts filled in.

    `{s}` and `{ies}` are plural placeholders. English needs them and
    Chinese ignores them, which is cheaper and more honest than either
    shipping "1 file(s)" or building a pluralisation engine for six
    sentences.
    """
    template = i18n.translate(catalog, key)
    filled = dict(values)
    for name, count in list(values.items()):
        if isinstance(count, int):
            filled.setdefault("s", "" if count == 1 else "s")
            filled.setdefault("ies", "y" if count == 1 else "ies")
    filled.setdefault("s", "s")
    filled.setdefault("ies", "ies")
    try:
        return template.format(**filled)
    except (KeyError, IndexError, ValueError):
        return "%s [[UNFILLED:%s]]" % (template, key)


def _ok(signals, name):
    block = signals.get(name) or {}
    return block if block.get("quality") == "ok" else None


def _value(signals, name, key, default=0):
    block = _ok(signals, name)
    return default if block is None else block.get(key, default)


def _idle_days(record):
    days = record.get("recency_days")
    return days if isinstance(days, (int, float)) else None


def _days(value):
    return "unknown" if value is None else "%.1f" % value


def counted(value):
    """A count for an evidence line, or the fact that nothing counted it.

    `%d` on a default of zero is how a privacy mechanism produced a
    number. `_shielded_signals` rebuilds four blocks for a sensitive row
    and `trend` is not one of them, so `trend.get("recent", 0)` read a
    missing block as "zero commits" and the board printed
    `recent_commits=0` beside a repository with eight - the shape rule 9's
    docstring says this module exists to refuse, produced by the code that
    refuses it. A trend reader that timed out on an ordinary row landed in
    the same place. Absence now reads as absence, which is a value the
    ladder above already has a name for.
    """
    return NO_SOURCE if value is None else "%d" % value


def whole_days(days):
    """The one rounding both columns use.

    `int(round(x))` in Python and `Math.round(x)` in JavaScript disagree on
    a .5 - Python rounds half to even, JavaScript rounds half up - and an
    audit caught them disagreeing on one row. Both sides now read a value
    rounded here, half up, once.
    """
    return None if days is None else int(days + 0.5)


def _long_enough(days, threshold):
    """Which of a rule's two phrasings applies.

    This is the whole remaining job of a threshold (DP51). It decides
    whether the sentence says "four files never committed" or "set aside,
    four files never committed, twenty days quiet". It does not decide
    whether the sentence is said at all, because a project holding four
    uncommitted files is holding them whether or not it also went quiet.
    """
    return days is not None and days >= threshold


def _inference_rules(record, signals, catalog):
    """Every rule that fires, in priority order, each with its evidence.

    DP51's table. The first match becomes the state column's one
    sentence; the rest are kept, because a project can be stopped
    mid-commit *and* sitting on unsent work, and `status --explain` is
    where the full list belongs.

    The order is the task book's proposal and the reasoning is worth
    keeping next to the code: WIP first because the last thing the author
    did was leave something half-finished, and unpushed above uncommitted
    because finished-but-unsent work is a larger fact than an unsaved
    edit.
    """
    idle = _idle_days(record)
    uncommitted = _value(signals, "uncommitted", "files")
    unpushed = _value(signals, "unpushed", "commits")
    stash_count = _value(signals, "stash", "entries")
    stash_age = _value(signals, "stash", "oldest_age_days", None)
    todos = _value(signals, "todos", "unchecked")
    last = _ok(signals, "last_commit") or {}
    trend = _ok(signals, "trend")
    wip = bool(last.get("wip"))
    # None, not zero, when nothing read the trend. See `counted`.
    recent_commits = trend.get("recent") if trend else None

    # Rules 6 and 7 are the only two that claim a project has *nothing*
    # outstanding, so they may speak only where the working tree was
    # actually read. A non-git directory reports every git signal as
    # not-applicable, which `_value` reads as zero; calling that "nothing
    # outstanding" would be the dishonest degradation DP20 exists to
    # refuse. Where the tree was never read, `no-source` is the answer.
    tree_read = _ok(signals, "uncommitted") is not None
    in_hand = bool(wip or unpushed or uncommitted or stash_count)

    fired = []

    def fire(key, text, evidence):
        fired.append({"rule": key, "text": text, "evidence": evidence})

    # 1. Stopped halfway.
    if wip:
        aged = _long_enough(idle, WIP_IDLE_DAYS)
        fire("wip",
             _phrase(catalog, "state.inferred.wip.aged", days=whole_days(idle))
             if aged else _phrase(catalog, "state.inferred.wip"),
             ["last_commit=%r" % last.get("subject", "")[:60],
              "idle_days=%s" % _days(idle),
              "wording_threshold=%d" % WIP_IDLE_DAYS])

    # 2. Finished but never sent.
    if unpushed:
        aged = _long_enough(idle, UNPUSHED_IDLE_DAYS)
        fire("unpushed",
             _phrase(catalog, "state.inferred.unpushed.aged",
                     commits=unpushed, days=whole_days(idle))
             if aged else _phrase(catalog, "state.inferred.unpushed",
                                  commits=unpushed),
             ["unpushed=%d" % unpushed, "idle_days=%s" % _days(idle),
              "wording_threshold=%d" % UNPUSHED_IDLE_DAYS])

    # 3. Never committed.
    if uncommitted:
        aged = _long_enough(idle, UNCOMMITTED_IDLE_DAYS)
        fire("uncommitted",
             _phrase(catalog, "state.inferred.uncommitted.aged",
                     files=uncommitted, days=whole_days(idle))
             if aged else _phrase(catalog, "state.inferred.uncommitted",
                                  files=uncommitted),
             ["uncommitted=%d" % uncommitted, "idle_days=%s" % _days(idle),
              "wording_threshold=%d" % UNCOMMITTED_IDLE_DAYS])

    # 4. Interrupted. A stash carries its own clock, and it is the better
    # one: a stash made yesterday inside a project quiet for a month is
    # not the same thing as a stash made a month ago.
    if stash_count:
        age = stash_age if stash_age is not None else idle
        aged = _long_enough(age, STASH_AGE_DAYS)
        fire("stash",
             _phrase(catalog, "state.inferred.stash.aged",
                     entries=stash_count, days=whole_days(age))
             if aged else _phrase(catalog, "state.inferred.stash",
                                  entries=stash_count),
             ["stash=%d" % stash_count, "oldest_days=%s" % _days(age),
              "wording_threshold=%d" % STASH_AGE_DAYS])

    # 6 and 7 come before the todo rule. Measured: unchecked boxes are the
    # dirtiest signal in the set - they count templates, other people's
    # documents and finished-but-unticked lists, and one repository here
    # carried 175 of them - so a repository that is demonstrably moving
    # should say so rather than announce a backlog it may not have. A
    # false positive costs more than a miss (Rule 10's creed), and the
    # reorder was measured to change no percentage: both sentences are
    # `inferred`, so this is where a sentence belongs, not a threshold.
    #
    # Nothing in hand: the two sentences a clean tree earns.
    # `recent_commits` is recorded but not required - it is implied by a
    # small idle time, and demanding it would hand a repository the wrong
    # sentence on the day the trend reader happened to time out.
    if tree_read and not in_hand and idle is not None:
        if idle <= MOVING_RECENT_DAYS:
            fire("moving",
                 _phrase(catalog, "state.inferred.moving"),
                 ["nothing_in_hand", "idle_days=%s" % _days(idle),
                  "recent_commits=%s" % counted(recent_commits),
                  "wording_threshold=%d" % MOVING_RECENT_DAYS])
        else:
            fire("quiet",
                 _phrase(catalog, "state.inferred.quiet", days=whole_days(idle)),
                 ["nothing_in_hand", "idle_days=%s" % _days(idle),
                  "recent_commits=%s" % counted(recent_commits),
                  "wording_threshold=%d" % MOVING_RECENT_DAYS])

    # 7 (last). A list with items still open, and no git work in hand.
    # Last because of the noise above, and still present because for a
    # directory that is not a repository it is the only signal there is -
    # rules 6 and 7 cannot speak there, so this is what keeps a writing
    # or design project from falling through to `no-source`.
    if todos and not in_hand:
        fire("todos",
             _phrase(catalog, "state.inferred.todos", items=todos),
             ["unchecked=%d" % todos, "uncommitted=0", "unpushed=0",
              "stash=0", "wip=False"])

    # 9 (last). A project with no version history at all (DP59).
    #
    # Same defect class as DP51 and the same fix. Signal 10 - the newest
    # mtime in the tree - was collected for every project and consumed by
    # no rule, so eleven non-git directories were proposed by the scan
    # and seven of them resolved to `no-source`: a cell reading "no weak
    # signal to fall back on" beside a signal that had in fact been
    # measured. This says the measured thing and does not dress it up as
    # a git judgment, because there is no git here to judge.
    if not tree_read and idle is not None:
        fire("touched",
             _phrase(catalog, "state.inferred.touched", days=whole_days(idle)),
             ["no_git_history", "newest_mtime_days=%s" % _days(idle)])

    return fired


# The four rules that describe what a project is *holding*, as opposed to
# what it is doing or not doing (DP80). Only these may appear under a
# declaration.
#
# The other four are excluded on purpose and the exclusions are the
# design: `moving`, `quiet` and `todos` only fire when nothing is in hand
# at all, so beneath a declaration they would have nothing to add;
# `touched` is a statement about the absence of git history, not about
# work held. Widening this tuple turns one row into a linter report,
# which is the shape DP56 refused.
IN_HAND_RULES = ("wip", "unpushed", "uncommitted", "stash")


def _in_hand_also(fired):
    """What a row is holding, for a headline that is about something else.

    DP80. A declaration outranks the whole inference table, so a row whose
    ledger says "waiting on the vendor" printed that and nothing else -
    while the summary line three rows above counted it among the "N
    holding uncommitted work" (DP73's literal reading, now settled). The
    two sentences were both true and could not be reconciled by reading
    the screen, because the fact that connected them was on neither.

    The rules still run under a declaration; the declaration still wins
    the headline. This is what was suppressed, and only the part of it
    that is about work in hand.
    """
    return [item["text"] for item in fired if item["rule"] in IN_HAND_RULES]


def rules_that_matched(record, signals, catalog):
    """Every inference rule that matched this record, winner or not.

    `status --explain` needs this, and the resolved state cannot give it:
    the state keeps one rule, so a row whose ledger declaration outranked
    four matching rules printed `won: none` beside a table of their
    inputs. Exposed rather than reached into privately, so the command
    reads the same table the board is judged by.
    """
    return _inference_rules(record, signals, catalog)


def _declared(declaration, catalog, fired):
    return {
        "kind": DECLARED,
        "css_class": CSS_CLASS[DECLARED],
        "text": declaration["text"],
        "source": declaration["source"],
        "line": declaration.get("line_no"),
        "marker": declaration.get("marker"),
        "at": declaration.get("at"),
        "age_days": declaration.get("age_days"),
        "stale": bool(declaration.get("stale")),
        "owner": bool(declaration.get("owner")),
        "names_somebody": bool(declaration.get("names_somebody")),
        "evidence": ["%s:%s" % (declaration["source"], declaration.get("line_no")),
                     "marker=%r" % declaration.get("marker")],
        "also": _in_hand_also(fired),
    }


def _curated(note, catalog, fired):
    since = note.get("since")
    return {
        "kind": CURATED,
        "css_class": CSS_CLASS[CURATED],
        "text": note["text"],
        "source": "roster.json",
        "since": since,
        "dated": bool(since),
        "byline": (_phrase(catalog, "state.curated.since", date=since) if since
                   else i18n.translate(catalog, "state.curated.undated")),
        "evidence": ["roster.json note"],
        # A note the user wrote outranks the table exactly as a
        # declaration does, and suppresses exactly the same facts, so it
        # gets the same treatment (DP80). The alternative - sub-text under
        # a quotation but not under the user's own sentence - would mean
        # the summary line reconciles with one kind of row and not the
        # other, for no reason a reader could infer.
        "also": _in_hand_also(fired),
    }


def _inferred(fired, catalog, project_id):
    first = fired[0]
    return {
        "kind": INFERRED,
        "css_class": CSS_CLASS[INFERRED],
        "rule": first["rule"],
        "text": first["text"],
        "badge": i18n.translate(catalog, "state.inferred"),
        "evidence": first["evidence"],
        # Every other rule that matched, not only the in-hand four: here
        # the winner is itself an inference, so the runners-up are the
        # same kind of statement and the row has already earned the space
        # to list them. `_in_hand_also` is the narrower filter, for the
        # two kinds whose headline is a quotation.
        "also": [item["text"] for item in fired[1:]],
        "promote": "murscope note %s \"...\"" % project_id,
    }


def _no_source(record, catalog, project_id):
    """Nothing readable, and no weak signal either.

    Deliberately its own function. B3 checks that this and
    _nothing_to_flag() are not one code path with a flag, because the
    day they become one is the day the board starts saying "fine" about
    a project it never managed to look at.
    """
    return {
        "kind": NO_SOURCE,
        "css_class": CSS_CLASS[NO_SOURCE],
        "text": i18n.translate(catalog, "state.no_source.text"),
        "next_command": "murscope note %s \"...\"" % project_id,
        "evidence": _why_nothing(record),
    }


def _nothing_to_flag(record, catalog):
    """Read, computed, and nothing worth saying. A positive answer.

    Also deliberately its own function, and note that it carries no
    next_command: there is nothing for the user to do here, and offering
    them an action would turn a clean result into a chore.
    """
    return {
        "kind": NONE,
        "css_class": CSS_CLASS[NONE],
        "text": i18n.translate(catalog, "state.none.text"),
        "evidence": _what_was_read(record),
    }


def _what_was_read(record):
    signals = record.get("signals") or {}
    read = []
    ledger = signals.get("ledger") or {}
    for source in ledger.get("read", []):
        read.append("read %s" % source)
    for name in ("uncommitted", "unpushed", "stash", "last_commit", "todos"):
        if _ok(signals, name) is not None:
            read.append("%s=ok" % name)
    return read


def _why_nothing(record):
    signals = record.get("signals") or {}
    why = []
    ledger = signals.get("ledger") or {}
    if not ledger.get("read"):
        why.append("no ledger file among the shapes this build reads")
    for name in ("uncommitted", "unpushed", "stash", "last_commit"):
        block = signals.get(name) or {}
        if block.get("quality") != "ok":
            why.append("%s=%s" % (name, block.get("quality", "absent")))
    return why


def has_weak_signals(record):
    """Was there anything to infer from at all?

    The four git facts the inference table runs on. If none of them
    answered, no inference was possible - which is a different situation
    from every rule having been evaluated and none having fired.
    """
    signals = record.get("signals") or {}
    return any(_ok(signals, name) is not None
               for name in ("uncommitted", "unpushed", "stash", "last_commit"))


# The three facts two different screens count, read from one place.
#
# The literal reading, and it is settled (DP73, ruled 2026-08-13, recorded
# as DP80). `init` printed "8 are holding uncommitted work" on the summary
# screen and the board it built seconds later printed "10 with uncommitted
# work", from the same collection: the summary counted rows where the
# `uncommitted` rule *won the state column*, and the tile counted rows
# that *have* uncommitted files. Two rows were holding work and saying
# something else, because a ledger declaration outranks an inference.
#
# What the counts mean is what these functions return: a row with at least
# one uncommitted file is holding uncommitted work, whatever its headline
# sentence is about. That is the number a user can check with `git status`,
# and it does not change when somebody writes a ledger line. The rows the
# old wording could not account for are reconciled on the row instead of
# in the predicate - see `_in_hand_also`, which puts the suppressed fact
# in the state column's sub-text. The same mismatch existed for unpushed
# and for WIP and was not measured; all three are routed through here so
# the next one cannot open silently.
#
# Both record shapes, because they are the same record at two moments. An
# ordinary row carries `signals`; a sensitive row has been through
# `collect.shield()` and carries the whitelisted counts flat.
def uncommitted_files(record):
    """Files this row has uncommitted, whichever shape the record is in."""
    block = _ok(record.get("signals") or {}, "uncommitted")
    if block is not None:
        return block.get("files") or 0
    return record.get("uncommitted") or 0


def unpushed_commits(record):
    """Commits this row has finished and not sent."""
    block = _ok(record.get("signals") or {}, "unpushed")
    if block is not None:
        return block.get("commits") or 0
    return record.get("unpushed") or 0


def stopped_halfway(record):
    """Whether this row's newest commit is a work-in-progress marker."""
    block = _ok(record.get("signals") or {}, "last_commit")
    if block is not None:
        return bool(block.get("wip"))
    return bool(record.get("wip"))


def _shielded_signals(record):
    """Rebuild a minimal signal set from what a sensitive row may emit.

    A sensitive entry is shielded on the way out (Rule 7), and `signals`
    is not on the whitelist - so the rules above saw an empty dict and
    rule 9 announced "no version history to read" about a repository with
    a full one. That is a false sentence produced by a privacy mechanism,
    which is the worst way to get one.

    The counts themselves *are* method and *are* whitelisted: how many
    files are uncommitted, how many commits are unsent. So the rules run
    on those, and a sensitive project gets the same true sentence as any
    other without anything new being read or exposed.
    """
    if record.get("signals") or "uncommitted" not in record:
        return None
    def block(name, key, value):
        if value is None:
            return {"quality": "not-applicable", "signal": name}
        return {"quality": "ok", "signal": name, key: value}
    return {
        "uncommitted": block("uncommitted", "files", record.get("uncommitted")),
        "unpushed": block("unpushed", "commits", record.get("unpushed")),
        "stash": block("stash", "entries", record.get("stash")),
        "last_commit": {"quality": "ok", "signal": "last_commit",
                        "wip": bool(record.get("wip")),
                        "subject": ""},
    }


def resolve(record, entry, catalog):
    """The state for one collected project. Reads no file; pure judgement.

    Every path through this function returns a state with a non-empty
    text. That is the product promise for this column, and it is enforced
    by the fact that there is no `return None`.
    """
    signals = record.get("signals") or _shielded_signals(record) or {}
    ledger_block = signals.get("ledger") or {}

    # Run first, used by every branch below (DP80). The table used to be
    # evaluated only where it could win, so a declaration or a note
    # discarded it unread - which is why what those rows were holding had
    # nowhere to appear. It is pure judgement over signals already
    # collected: reordering it opens no file and costs one pass over four
    # counts.
    fired = _inference_rules(record, signals, catalog)

    declaration = ledger_block.get("declaration")
    if declaration:
        return _declared(declaration, catalog, fired)

    if entry.note and entry.note.get("text"):
        return _curated(entry.note, catalog, fired)

    if fired:
        return _inferred(fired, catalog, entry.id)

    read_something = bool(ledger_block.get("read"))
    if not read_something and not has_weak_signals(record):
        return _no_source(record, catalog, entry.id)
    return _nothing_to_flag(record, catalog)


def apply_precedence(record, state):
    """A ledger line that names the owner takes the badge.

    Only an owner-naming declaration overrules. "BLOCKED: upstream API is
    down" is a real blocker and still not the owner's move, so it leaves
    whatever the roster said standing. Without the distinction the board
    can show two answers to one question and let the stale one win.
    """
    owner_queue = False
    derived_from = None
    if state.get("kind") == DECLARED and state.get("owner"):
        owner_queue = True
        derived_from = state.get("source")
    record["owner_queue"] = owner_queue
    record["owner_queue_source"] = derived_from
    return record
