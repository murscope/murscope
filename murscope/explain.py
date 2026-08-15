"""`murscope status --explain <project>`: show the working.

Once the vocabulary is editable, this is not a debugging convenience -
it is what stops "configurable" from becoming "breakable". A user who
adds a marker and gets a state they did not expect has exactly two
options without this command: read the source, or stop trusting the
column.

So it prints the whole chain. Which packs are enabled, what the three
layers resolved to, which files were opened, every line that matched and
the marker that matched it, which one won and why, then every inference
rule with its threshold and whether it fired - including the ones that
did not, because "why is this project not flagged" is the harder
question and the one nothing else answers.
"""
from __future__ import annotations

from . import collect, i18n, markers, state


# The rule key each table row describes, so "did it fire" can be answered
# from the same table that lists it. The keys are the ones
# `state._inference_rules` fires under.
RULE_KEYS = ("wip", "unpushed", "uncommitted", "stash", "todos", "moving",
             "quiet", "touched")


def _rule_table(record, catalog):
    """Every inference rule, fired or not, with the numbers behind it.

    Priority order, DP51's table. The `threshold` column no longer says
    whether a rule fires - it says which of that rule's two phrasings
    applies - and the printout labels it that way, because a reader who
    thinks a threshold gates the rule will misread every line here.
    """
    signals = record.get("signals") or {}
    idle = record.get("recency_days")
    last = (signals.get("last_commit") or {})
    stash = (signals.get("stash") or {})

    def block(name):
        found = signals.get(name) or {}
        return found if found.get("quality") == "ok" else None

    def value(name, key, default=0):
        found = block(name)
        return found.get(key, default) if found is not None else None

    # `None`, not a number, when nothing read the trend. This printed
    # `recent_commits=None` here and `recent_commits=0` on the board from
    # the same absent block; both now say the block was not read.
    trend = block("trend")
    recent = state.counted(trend.get("recent") if trend else None)
    tree_read = block("uncommitted") is not None
    return [
        ("1 stopped halfway", state.WIP_IDLE_DAYS,
         "wip=%s idle=%s" % (last.get("wip"), idle)),
        ("2 finished but never sent", state.UNPUSHED_IDLE_DAYS,
         "unpushed=%s idle=%s" % (value("unpushed", "commits"), idle)),
        ("3 never committed", state.UNCOMMITTED_IDLE_DAYS,
         "uncommitted=%s idle=%s" % (value("uncommitted", "files"), idle)),
        ("4 interrupted", state.STASH_AGE_DAYS,
         "stash=%s oldest=%s" % (stash.get("entries"),
                                 stash.get("oldest_age_days"))),
        ("5 items open on the list", 0,
         "unchecked=%s (fires only with nothing in hand)"
         % value("todos", "unchecked")),
        ("6 moving normally", state.MOVING_RECENT_DAYS,
         "idle=%s recent_commits=%s tree_read=%s" % (idle, recent, tree_read)),
        ("7 quiet, nothing outstanding", state.MOVING_RECENT_DAYS,
         "idle=%s tree_read=%s" % (idle, tree_read)),
        # Rule 9 (DP59), which this table simply did not have. The
        # docstring above says "every inference rule", and for a non-git
        # directory the one rule that can speak was the missing row.
        ("9 no version history", 0,
         "newest_mtime_days=%s tree_read=%s (fires only without git)"
         % (idle, tree_read)),
    ]


def explain(entry, settings, vocabulary, catalog):
    """Print the chain for one project. Returns an exit code."""
    print("murscope status --explain %s" % entry.id)
    print("  root    : %s" % (entry.root or "(unset)"))
    print("  locale  : %s" % settings.locale)

    print("\nvocabulary, three layers")
    print("  packs enabled  : %s" % ", ".join(vocabulary.layers["packs"]))
    print("  from packs (%d): %s" % (len(vocabulary.layers["from_packs"]),
                                     ", ".join(vocabulary.layers["from_packs"])))
    print("  extra_markers  : %s" % (", ".join(vocabulary.layers["extra"]) or "none"))
    print("  disabled       : %s" % (", ".join(vocabulary.layers["disabled"]) or "none"))
    print("  owner aliases  : %s" % (", ".join(vocabulary.aliases)
                                     or "none configured (DP19: none ship)"))
    for line in vocabulary.problems:
        print("  problem        : %s" % line)

    record = collect.collect_project(entry, settings, vocabulary)
    if entry.sensitive and not record.get("signals"):
        # A sensitive record is shielded on the way out and `signals` is not
        # on the whitelist, so everything below would read as "we looked and
        # found nothing" about a project this command never opened - and
        # would also claim the working tree was unread while `git status`
        # had just returned a count. That is DP20's own distinction,
        # inverted by the privacy mechanism, in a shipped command.
        print("\nthis entry is marked sensitive")
        print("  Rule 7 permits method only, so the ledger was never opened "
              "and the working tree was never walked. There is no chain to "
              "print: the per-signal detail this command exists to show is "
              "withheld by design, not missing by accident.")
        print("\nwhat a sensitive entry does report")
        for key in ("tier", "recency_days", "uncommitted", "unpushed", "stash",
                    "wip", "trend", "tag", "branches"):
            if key in record:
                print("  %-14s : %s" % (key, record.get(key)))
        resolved = record.get("state") or state.resolve(record, entry, catalog)
        print("\nresult")
        print("  state          : %s" % resolved["kind"])
        print("  text           : %s" % resolved.get("text"))
        # What the headline outranked (DP80). Every sentence in this list
        # is built from the counts printed directly above - whitelisted
        # method, nothing newly read - so a sensitive row is not a reason
        # to withhold it, and withholding it here would leave the one kind
        # of row that most needs the reconciliation without it.
        if resolved.get("also"):
            print("  also true      : %s" % "; ".join(resolved["also"]))
        print("  note           : computed from the counts above, which are "
              "method. Remove `sensitive` from the roster entry to see the "
              "full chain.")
        return 0
    ledger_block = (record.get("signals") or {}).get("ledger") or {}

    print("\nledger, signal 14")
    if ledger_block.get("quality") == "sealed-skipped":
        print("  not read: %s" % ledger_block.get("detail"))
    else:
        read = ledger_block.get("read") or []
        print("  files read     : %s" % (", ".join(read) or "none"))
        for item in ledger_block.get("unreadable") or []:
            print("  unreadable     : %s (%s)" % (item["source"], item["detail"]))
        print("  lines matched  : %d" % ledger_block.get("hits", 0))
        declaration = ledger_block.get("declaration")
        if declaration:
            print("  winning line   : %s:%s" % (declaration["source"],
                                                declaration["line_no"]))
            print("  marker matched : %r" % declaration["marker"])
            print("  text           : %s" % declaration["text"])
            print("  names the owner: %s" % declaration["owner"])
            print("  age            : %s days%s"
                  % (declaration["age_days"],
                     " (stale)" if declaration["stale"] else ""))
        else:
            # `read_ledger` has already decided which of these it is, and
            # this printed the third answer for all three: no ledger file at
            # all, files read with no marker in them, and files read whose
            # markers were refused. Only the last one is "no line survived",
            # and saying it about the first is DP20's own distinction
            # inverted - in the command whose entire job is to show the
            # working.
            quality = ledger_block.get("quality")
            if quality == "not-applicable":
                print("  winning line   : none - there was no ledger file to "
                      "read, so nothing was refused")
                print("  detail         : %s"
                      % ledger_block.get("detail", "no ledger file"))
            elif ledger_block.get("refused_lines"):
                print("  winning line   : none - %d line(s) mentioned a marker "
                      "and every one was refused: prose, a legend inside a "
                      "code span, or an empty heading"
                      % ledger_block.get("refused_lines", 0))
            else:
                print("  winning line   : none - %d file(s) were read and no "
                      "line in them mentioned a marker at all"
                      % len(ledger_block.get("read") or []))

    print("\ninference rules, in priority order (DP51)")
    print("  a threshold here changes the wording, not whether the rule fires")
    resolved = state.resolve(record, entry, catalog)
    winner = resolved.get("rule")
    # Whether each rule fired, which is the column this table promised in
    # the module docstring and did not have: it printed each rule's inputs
    # and one `won:` line, so a rule that matched and was outranked was
    # indistinguishable from one that never matched. Recomputed from
    # `_inference_rules` rather than read off the resolved state, because
    # the resolved state keeps only the winner.
    matched = {rule["rule"] for rule in state.rules_that_matched(
        record, record.get("signals") or {}, catalog)}
    for (name, threshold, observed), key in zip(_rule_table(record, catalog),
                                                RULE_KEYS):
        print("  %-29s %-5s wording at=%-3s  %s"
              % (name, "fired" if key in matched else "-", threshold or "-",
                 observed))
    # Three different facts, and one word was printed for all three. A
    # board row carrying a ledger declaration printed `won: none` while
    # rules had matched: the declaration outranks the whole table, which is
    # not the same as the table having nothing to say.
    if winner:
        print("  won            : %s" % winner)
    elif matched:
        print("  won            : none of them - this row's state is %r, "
              "which outranks the inference table. Rules that matched "
              "anyway: %s" % (resolved["kind"], ", ".join(sorted(matched))))
    else:
        print("  won            : none - no rule above matched")

    print("\nresult")
    print("  state          : %s" % resolved["kind"])
    print("  text           : %s" % resolved.get("text"))
    if resolved.get("source"):
        print("  source         : %s" % resolved["source"])
    if resolved.get("evidence"):
        print("  evidence       : %s" % "; ".join(resolved["evidence"]))
    if resolved.get("also"):
        print("  also true      : %s" % "; ".join(resolved["also"]))
    if resolved.get("promote"):
        print("  make it yours  : %s" % resolved["promote"])
    if resolved.get("next_command"):
        print("  next command   : %s" % resolved["next_command"])
    if resolved["kind"] == state.NO_SOURCE:
        print("  note           : this is not 'nothing to report'. Nothing was "
              "readable, which is a different fact (DP20).")
    return 0


def find_entry(roster, wanted):
    """Match by id first, then by name. Ambiguity is reported, not guessed."""
    matches = [e for e in roster if e.id == wanted]
    if not matches:
        matches = [e for e in roster if e.name == wanted]
    if not matches:
        matches = [e for e in roster if wanted.lower() in e.id.lower()]
    return matches


def run(argv, settings, roster, home):
    if not argv or argv[0] != "--explain" or len(argv) < 2:
        print("usage: murscope status --explain <project>")
        return 2
    wanted = argv[1]
    matches = find_entry(roster, wanted)
    if not matches:
        known = ", ".join(e.id for e in roster) or "the roster is empty"
        print("murscope: no roster entry matches %r. Known: %s" % (wanted, known))
        return 2
    if len(matches) > 1:
        print("murscope: %r matches %d entries (%s); name one exactly."
              % (wanted, len(matches), ", ".join(e.id for e in matches)))
        return 2

    locale, _ = i18n.resolve(settings.locale)
    catalog, _ = i18n.load(locale)
    vocabulary = markers.resolve(settings.locale, settings.section("blockers"))
    return explain(matches[0], settings, vocabulary, catalog)
