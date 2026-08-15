"""Console entry point.

M1 implemented `run`, `status --explain` and `selftest`; M2 adds `init`
with its summary screen, `try`, `doctor`, `note` and `open`. The command
surface the MVP promised is complete.

Two functions here exist for the wizard as much as for `run`: `prepare`
resolves configuration, locale and vocabulary, and `collect_records`
does the collecting. The wizard shows the states it collected on the
summary screen and then renders those same records, so a first run
collects once rather than twice.

Nothing here writes outside MURSCOPE_HOME and nothing touches a
monitored project. `run` returns non-zero only when the roster could not
be read at all: one unreadable project out of five is a row on the
board, not a failed run.
"""
from __future__ import annotations

import sys

from . import (__version__, alerts, collect, config, consent, contributions,
               daily, doctor, explain, i18n, keys, markers, matrix, notes,
               outbound, preview, providers, registry, render, scan, schedule,
               selftest, state, width)
from .guard import inside_home, murscope_home

PROGRAM = "murscope"

HELP = """usage: murscope <command> [options]

murscope is a read-only portfolio observability tool: it scans the
projects you point it at and renders a one-page static dashboard.

commands:
  init [<path>] [--add <p>]    scan, show one summary screen, build the board.
                               Enter accepts everything; --yes skips the screen
  try <path>                   scan one directory and show a throwaway board.
                               Writes nothing to your home; nothing to agree to
  note <project> "..."         say what is actually going on, into the roster
  doctor [path ...]            can this interpreter read what you pointed it at,
                               and how many projects are there
  open                         hand the board to your browser, from disk
  run                          collect every roster entry and write the board
  timer install|uninstall      schedule work to happen with nobody present.
       |status [--alerts]      Writes the job file(s) - the only thing murscope
                               writes outside MURSCOPE_HOME - names them before
                               writing, and prints the command that turns each
                               on. The collecting job collects and renders and
                               has no path to any transport; --alerts adds the
                               one job that can send while you are away
  alert [--send] [--status]    evaluate the alert rules against a fresh
                               collection and deliver. Local delivery always;
                               --send also sends, if a provider is enabled and
                               a consent covering the alert's own disclosure
                               is on file. --status says what left and what
                               did not
  status --explain <project>   show which file, which line, which marker,
                               and which state came out of them
  key set <name>               store a key, read from stdin, never from argv
  key list                     which keys are stored, where, and at what mode.
                               Never a value
  consent show <p> --to <url>  print, in full, what a request to that
                               destination would contain
  consent grant <p> --to <url> record that you agreed to exactly that
  consent status               what is recorded, and whether it still covers
                               what murscope would send today
  daily [--send] [--again]     the daily note. With no --send it prints the
                               payload byte for byte and sends nothing.
                               --providers lists every note adapter and
                               whether it has ever completed a round trip
  contributions [--measure]    read your own contribution calendar from your
                               own account. Needs murscope[ai], an enabled
                               provider and a recorded consent. --measure
                               reproduces the three platform defects
                               ADR-0003 records, and writes the numbers down
  modules                      the module matrix: every provider module on
                               this disk, which distribution put it there,
                               whether configuration enabled it, whether it
                               could open a socket, and - for the ones that
                               were imported - what each reads, writes and
                               alerts to, where it sends and whether it has
                               ever completed a round trip. A module nothing
                               imported reads `unknown`, never `no`
  selftest                     prove the marker vocabulary is still precise,
                               that a collection, a render and a scan reach
                               no network (imports excepted), that no stored
                               key reaches an artifact, and that no installed
                               provider could open a socket

options:
  --version   print the version and exit
  -h, --help  print this message and exit

Configuration, the board, your keys and your recorded consents live under
MURSCOPE_HOME (default ~/.murscope). Nothing is ever written anywhere
else. Nothing outside the roster is read, except by `init` with no path,
which looks in the conventional project directories under your home to
propose one and names them on screen before it scans.

`pip install murscope` installs no code that can reach the network - not
a disabled provider, none at all. A base install makes no network call at
all. The network layer is a separate distribution: `pip install
'murscope[ai]'` adds it, and it states what leaves, to where and on whose
key before it sends anything. Installed is not enabled - nothing runs
unless config.toml names it - and enabled is not consent: a consent is
recorded against the exact list of fields you were shown, so widening
what murscope would send asks you again instead of assuming.
`murscope selftest` reports which of the two installs you have.
"""


def _placeholder(entry, problems, extra=None):
    record = {
        "id": entry.id, "name": entry.name, "root": entry.root,
        "sensitive": entry.sensitive, "tier": "MISSING",
        "signals": {}, "degraded": [], "signal_quality": "bad",
        "problems": list(problems),
    }
    record.update(extra or {})
    return record


# Notes that describe the state of the home *before* this run created it.
# An audit read the first board a stranger gets: two files had just been
# written twenty lines above, and the notes said "no config.toml yet" and
# "no roster.json yet, so there is nothing to look at". Both were true when
# they were produced and neither was true when they were read.
STALE_ABSENCE = ("no config.toml yet", "no roster.json yet")


def drop_stale_absences(problems):
    """Remove notes that this run has already made untrue.

    The wizard reads configuration, then creates what was missing, then
    renders. A note recorded in step one and shown in step three tells the
    reader the opposite of what they are looking at.
    """
    return [line for line in problems
            if not any(mark in line for mark in STALE_ABSENCE)]


def prepare(home):
    """Everything a run needs before it touches a project. (bundle, problems)

    Shared by `run` and by the wizard, which needs the same configuration,
    the same vocabulary and the same catalog - and needs to collect only
    once, because the summary screen shows the states it is about to put
    on the board.
    """
    settings = config.load_config(home)
    roster = config.load_roster(home)
    problems = list(settings.problems) + list(roster.problems)

    locale, locale_problems = i18n.resolve(settings.locale)
    catalog, catalog_problems = i18n.load(locale)
    problems.extend(locale_problems + catalog_problems)

    vocabulary = markers.resolve(settings.locale, settings.section("blockers"))
    problems.extend(vocabulary.problems)

    return (settings, roster, locale, catalog, vocabulary), problems


def collect_records(roster, settings, catalog, vocabulary):
    """Collect and resolve every roster entry. (records, problems)."""
    problems = []
    collected = []
    for entry in roster:
        if not entry.usable:
            record = _placeholder(entry, entry.problems)
            record["state"] = state.resolve(record, entry, catalog)
            collected.append(state.apply_precedence(record, record["state"]))
            continue
        # DP47. The guard proves "murscope never writes into a monitored
        # project" by proving "murscope never writes outside
        # MURSCOPE_HOME". Those are one sentence only while no monitored
        # project sits inside MURSCOPE_HOME, so an overlap is reported
        # per entry and carried onto the board itself - a promise that
        # quietly stops holding is worse than one never made.
        overlap = inside_home(entry.path)
        if overlap:
            entry.problems.append(i18n.translate(catalog, "method.overlap"))
        try:
            record = collect.collect_project(entry, settings, vocabulary)
        except Exception as exc:  # one bad project must not end the round
            record = _placeholder(entry, list(entry.problems) + [
                "collection failed (%s: %s)" % (type(exc).__name__, exc)],
                {"tier": "UNKNOWN"})
        record["home_overlap"] = overlap
        # A ledger path that tried to leave the project is not a detail
        # for a log file. Promise three is on the front page, so a refusal
        # is a row-level problem the board shows (DP47's habit, applied to
        # reading rather than writing).
        for refusal in ((record.get("signals") or {}).get("ledger")
                        or {}).get("refused") or []:
            record.setdefault("problems", []).append(
                "ledger %r %s" % (refusal["source"], refusal["detail"]))
        record["state"] = state.resolve(record, entry, catalog)
        # Once each. This is a fact about the *configuration* - a source
        # name this build does not ship - and it is recorded per record, so
        # a run over twenty projects printed the same sentence twenty times.
        for line in record.get("activity_problems") or []:
            if line not in problems:
                problems.append(line)
        collected.append(state.apply_precedence(record, record["state"]))
    return collected, problems


def run(argv, quiet_absences=False):
    """Collect every roster entry and write the board. Returns an exit code.

    `quiet_absences` is for `try`, which runs against a throwaway home:
    "no config.toml yet; it would go at <tempdir>" points at a directory
    the next line tells the user to delete.
    """
    home = murscope_home()
    (settings, roster, locale, catalog, vocabulary), problems = prepare(home)
    if quiet_absences:
        problems = drop_stale_absences(problems)

    loaded, provider_problems = providers.load(
        settings.section("providers").get("enabled", []))
    problems.extend(provider_problems)

    collected, collect_problems = collect_records(
        roster, settings, catalog, vocabulary)
    problems.extend(collect_problems)

    for provider in registry.registered().values():
        if provider.contribute is None:
            continue
        for record in collected:
            try:
                record.update(provider.contribute(record) or {})
            except Exception as exc:
                problems.append("provider %r failed on %r (%s)."
                                % (provider.name, record.get("id"), exc))

    document, written = render.render(
        collected, settings, catalog, locale, problems,
        registry.describe_all(), home)

    for record in collected:
        print("%-8s %-9s %-10s %s"
              % (record.get("tier", "?"), record.get("signal_quality", "?"),
                 (record.get("state") or {}).get("kind", "?"),
                 record.get("name", record.get("id", "?"))))
        print("         %s" % (record.get("state") or {}).get("text", ""))
        for line in record.get("problems") or []:
            print("         ! %s" % line)
    for line in problems:
        print("note: %s" % line)
    owed = sum(1 for r in collected if r.get("owner_queue"))
    unmatched = sum(1 for r in collected
                    if (r.get("state") or {}).get("names_somebody")
                    and not (r.get("state") or {}).get("owner"))
    # The board carries this caveat; the terminal used to state the count as
    # settled while the page beside it said the number was incomplete. Two
    # screens, two answers, and neither of them right.
    caveat = ("" if not unmatched else
              " (%d more name somebody your owner names do not cover)"
              % unmatched)
    print("OK: %d project(s), %d waiting on you%s -> %s"
          % (len(collected), owed, caveat, written[-1]))
    if loaded:
        print("providers loaded: %s" % ", ".join(loaded))
    return 0


def open_board(argv):
    """`murscope open`: hand the local board to the desktop browser.

    Rule 11 allows `webbrowser` and constrains what may be passed to it:
    a `file://` literal, a string with no scheme, or `Path(...).as_uri()`.
    That constraint is the point - an unconstrained browser call takes a
    URL, which makes it an exfiltration channel with a written exemption.
    This one can only ever open a file under MURSCOPE_HOME.
    """
    import webbrowser  # noqa: PLC0415 - imported where its one use lives

    home = murscope_home()
    board = home / render.BOARD_DIRNAME / "index.html"
    if not board.is_file():
        print("murscope open: no board yet at %s\n"
              "  build one with: murscope init <path>" % board)
        return 2
    # `as_uri()` inline at the call site, because that is the shape Rule 11
    # can verify - a variable holding a URL is exactly what it refuses, and
    # it is right to: an unconstrained browser call is an exfiltration
    # channel with a written exemption.
    #
    # `open_new_tab` rather than `open`, and not for taste. Rule 5 matches
    # the method being called rather than the receiver, deliberately - that
    # breadth is what catches `Path(p).write_text()` - so `webbrowser.open`
    # reads as a file `open()` with a non-literal mode and turns the
    # read-only check red. Rule 11 constrains all three browser openers
    # identically, so nothing is dodged here; narrowing Rule 5 to
    # accommodate one convenience would have been the wrong trade.
    if not webbrowser.open_new_tab(board.resolve().as_uri()):
        print("murscope open: no browser would take it. The board is a file "
              "you can open yourself:\n  %s" % board)
        return 1
    print("murscope: opened %s" % board)
    return 0


def doctor_command(argv):
    """`murscope doctor [path ...]`. Returns an exit code.

    With no arguments it checks the roots already in the roster, because
    the question "can I read what I was pointed at" is the same question
    on the tenth run as on the first - a permission that was revoked
    silently produces the same empty board as one never granted.
    """
    home = murscope_home()
    settings = config.load_config(home)
    sealed = config.sealed_dirs(settings.section("scan").get("sealed_dirs", []))

    roots = [str(p) for p in argv if not p.startswith("-")]
    scanned = None
    if not roots:
        roster = config.load_roster(home)
        roots = [entry.path for entry in roster if entry.path]
        if not roots:
            print("murscope doctor: no roster yet and no path given.\n"
                  "  usage: murscope doctor <path> [path ...]\n"
                  "  interpreter: %s" % doctor.interpreter_path())
            return 2
    else:
        scanned = scan.discover(roots, sealed)

    report = doctor.check(roots, sealed)
    doctor.render(report, scanned)
    return 1 if doctor.blocked(report) else 0


def _flag_value(argv, flag):
    """The value after `--flag`, or None. No dependency, no surprises."""
    for index, item in enumerate(argv):
        if item == flag and index + 1 < len(argv):
            return argv[index + 1]
        if item.startswith(flag + "="):
            return item.split("=", 1)[1]
    return None


def _key_backend(home):
    settings = config.load_config(home)
    return settings.section("keys").get("backend", "file")


def read_secret_value(stream=None):
    """A key, read from stdin. Never from argv, and never echoed.

    Not a convenience. A key on the command line is a key in the shell
    history and in every `ps` listing on the machine for as long as the
    process runs, and neither of those is under this tool's control - so
    there is no `--value` flag to reach for.
    """
    handle = stream or sys.stdin
    if handle.isatty():
        import getpass  # noqa: PLC0415 - only the interactive path needs it
        return getpass.getpass("key (not echoed): ")
    return handle.readline().rstrip("\n")


def key_command(argv):
    """`murscope key set <name>` / `murscope key list`. An exit code."""
    home = murscope_home()
    backend = _key_backend(home)
    action = argv[0] if argv else ""

    if action == "set":
        if len(argv) < 2:
            print("usage: murscope key set <name>\n"
                  "  the value is read from stdin, never from the command "
                  "line - a key in argv is a key in your shell history.")
            return 2
        name = argv[1]
        value = read_secret_value()
        where, problems = keys.store(name, value, home, backend=backend)
        for line in problems:
            print("murscope key: %s" % line)
        if where is None:
            return 1
        # The location, never the value. This line is the one most likely
        # to be pasted into an issue report.
        if backend == "file":
            print("murscope: stored key %r at %s (mode %04o)."
                  % (name, where, keys.FILE_MODE))
        else:
            print("murscope: stored key %r in the %s." % (name, where))
        return 0

    if action in ("", "list"):
        print("murscope keys")
        print("  backend : %s" % backend)
        if backend != "file":
            print("  note    : the system keychain holds these; murscope "
                  "cannot list them without asking it for each name.")
            return 0
        print("  location: %s" % keys.keys_dir(home))
        rows = keys.audit(home)
        if not rows:
            print("  none stored yet. `murscope key set <name>` reads one "
                  "from stdin.")
            return 0
        bad = 0
        for name, mode, length, findings in rows:
            # The length, beside the mode, and never the value. It is the
            # one number a user can hold against what their provider's
            # console shows them - and comparing exactly that is what
            # eventually explained a key that stored cleanly, read back
            # cleanly, and was refused by the far end with a status code
            # that said nothing (DP112).
            print("  %-24s mode %s   %s"
                  % (name, "%04o" % mode if mode else "?",
                     "%d characters" % length if length is not None
                     else "length unknown"))
            for line in findings:
                print("      ! %s" % line)
                bad += 1
        # The security difference, stated here as well as in README,
        # because this is where somebody is looking at their own keys.
        print("  A key file is protected by the filesystem and by nothing")
        print("  else: anything running as you can read it, and a backup that")
        print("  copies your home copies your keys with it. The system")
        print("  keychain is protected by the operating system and asks")
        print("  before it hands a secret over:")
        print("      pip install 'murscope[keyring]'")
        print("      [keys]")
        print("      backend = \"keyring\"")
        print("  The file is the default because it always works, not")
        print("  because it is as good.")
        print("  The length beside each key is there to be compared with")
        print("  what your provider's console shows. murscope cannot tell")
        print("  whether a key is the right one - that needs the network,")
        print("  and this command has none - but a key of the wrong length")
        print("  was mangled on the way here, and the far end will refuse it")
        print("  with a status code that explains nothing.")
        return 1 if bad else 0

    print("murscope key: '%s' is not a key command. Try: set, list." % action)
    return 2


# The disclosures this build knows how to show, as (label, fields,
# lines, closing sentences). Three, and they are deliberately separate
# tables rather than one union: agreeing to send facts about your projects
# to a model is not agreeing to ask a code host what you did last month,
# and a single fingerprint covering both would make one act of consent
# authorise the other.
#
# Which one applies to a provider is decided by **what the provider is**,
# never by its name: a provider registered with a `reads` callable is a
# reader and gets the reading disclosure. Rule 16 refuses the core any
# knowledge of a provider's name, and this is that rule held by
# construction rather than by care.
BOARD_SUMMARY = "the board summary"
CONTRIBUTION_QUERY = "a contribution query"
ALERT_NOTICE = "an alert"

# **Who performs each send, in one line, at the top of the screen.** This
# is E8 and DP125, and it is a line of its own rather than a clause in a
# paragraph because the distinction it carries is the whole of what M4
# added to this product: two of these disclosures describe a request a
# person makes while looking at the answer, and one describes a request a
# machine makes on an authority granted once, at a moment nobody is
# present. The owner's own phrasing is in the third and is not paraphrased.
_WHO_SENDS = {
    BOARD_SUMMARY: (
        "you, once per send. `murscope daily --send` is a command you type, "
        "and the request happens in the next second while you are looking "
        "at the answer. Nothing sends this on its own - the scheduled job "
        "has no path to it at all (Rule 26)."),
    CONTRIBUTION_QUERY: (
        "you, once per send. `murscope contributions` is a command you "
        "type, and the request happens in the next second while you are "
        "looking at the answer. Nothing sends this on its own - the "
        "scheduled job has no path to it at all (Rule 26)."),
    ALERT_NOTICE: (
        "murscope, on its own, from a scheduled job - **this one leaves "
        "while you are not here**. That is what makes this consent a "
        "different kind of thing from the other two on this build: they "
        "authorise the request you are about to watch happen, and this one "
        "authorises a machine to act alone, from now on, without asking "
        "again. Every alert that fires while you are asleep goes out under "
        "this answer. `murscope alert --status` is where you find out what "
        "went and what did not."),
}

_CLOSING = {
    BOARD_SUMMARY: (
        "Nothing else. No project name, no path, no branch, no commit "
        "message, no declaration text, no file name, no file contents.",
        "A project you marked sensitive is not described at all - only "
        "counted, so you can see that it was left out."),
    CONTRIBUTION_QUERY: (
        "Nothing else. Nothing about your projects crosses this boundary "
        "at all - not a name, not a path, not a count, not a state.",
        "This request reads. It is still a request: your key leaves this "
        "machine to authenticate it, and the platform learns that you "
        "asked, and when. That is why it is consented to rather than "
        "assumed - \"it only reads\" is the same exemption as \"localhost "
        "is not the network\", which DP90 already refused."),
    ALERT_NOTICE: (
        "Nothing else. No path, no branch, no commit message, no "
        "declaration text, no ledger line, no file name, no file contents. "
        "The sentence is composed from a template inside the package and "
        "the four fields above it, and murscope refuses to send one that "
        "does not recompose from exactly those.",
        "A project you marked sensitive is never evaluated by an alert "
        "rule at all, so it cannot appear here - and unlike the daily "
        "note, **no count of how many were skipped leaves either**. The "
        "note is one document a day about the whole portfolio and a count "
        "there is method about the portfolio; alerts go one at a time, "
        "timestamped, to a place other people may read, and a number that "
        "moves across that stream is a way of saying that something "
        "happened. The count is printed on your own machine instead.",
        "This is one alert per message. If four projects go quiet on the "
        "same night, four of these leave."),
}


def known_disclosures():
    """[(label, shown)] for every disclosure this build can show.

    `consent status` walks this rather than assuming one, because a grant
    recorded against a reader's disclosure is not stale merely for being
    fingerprinted on a different table than the board summary's.
    """
    return [(BOARD_SUMMARY, outbound.shown()),
            (CONTRIBUTION_QUERY, contributions.shown()),
            (ALERT_NOTICE, alerts.shown())]


def disclosure_for(name, home=None):
    """(label, shown, lines) for one provider, or (None, (), ()). Never by name.

    The registry is asked what the provider *is*. A provider that offers a
    reading is a reader; one that can deliver an alert gets the alert's
    table; a provider that is registered and does neither writes a note,
    and gets the board summary's.

    **A provider the registry does not hold gets no table at all, and that
    is the repair rather than a defensive branch (DP156).** This used to fall
    through to the board summary, on the argument that an absent reader
    cannot be consented to - which was true of the grant and false of the
    screen. A provider is in the registry only once `config.toml` names it,
    so `consent show <an alerter> --to <url>` *before* enabling it printed
    the daily note's sixteen-field table under the alert provider's name,
    with the note's fingerprint and the note's `who sends` line saying a
    person performs each send. Nothing could be sent under a grant taken
    from that screen - the fingerprint recorded would be the note's and
    every field of an alert would be refused against it - so it was one
    screen of untruths rather than an unauthorised send. That is still the
    whole job of this screen: it exists so a person knows what they are
    agreeing to, and a screen naming the wrong document has already failed
    at the only thing it does.

    Answering by capability and never by name or destination keeps Rule 16
    - the core still has no idea which module is which - and "nothing
    imported it" is an answer this module can give while knowing nothing
    about the provider at all.
    """
    settings = config.load_config(home or murscope_home())
    providers.load(settings.section("providers").get("enabled", []))
    found = registry.registered().get(name)
    if found is None:
        return None, (), ()
    if found.reads is not None:
        return (CONTRIBUTION_QUERY, contributions.shown(),
                contributions.disclosure_lines())
    # Asked before the fall-through, and by capability rather than by name
    # for the reason the reader is: a provider that can deliver an alert is
    # what an alert consent is recorded against, and a build where that
    # question was asked second would hand the board summary's table to a
    # provider that has no note to write.
    if found.alerts is not None:
        return ALERT_NOTICE, alerts.shown(), alerts.disclosure_lines()
    return BOARD_SUMMARY, outbound.shown(), outbound.disclosure_lines()


def _print_no_disclosure(provider, home):
    """Say that this build cannot state what that provider would send.

    Not a table, and deliberately not a guess. What decides which
    disclosure applies is what the provider *is*, and a provider nothing
    imported is a provider nobody can ask - so the honest screen is the
    one that says which of the three things is missing, and stops.
    """
    settings = config.load_config(home)
    enabled = settings.section("providers").get("enabled", [])
    print("murscope cannot say what a request to %r would contain, because "
          "nothing named %r is enabled on this install." % (provider, provider))
    print("  What decides this screen is what the provider *is* - whether it "
          "reads, writes a note, or delivers an alert - and a provider "
          "murscope has not imported is one it cannot ask. Three tables ship "
          "and they are different documents with different fingerprints; "
          "picking one of them here would be a guess printed as a fact.")
    print("  enabled in config.toml     : %s"
          % (", ".join(str(name) for name in enabled) or "nothing"))
    print("  imported and registered    : %s"
          % (", ".join(sorted(registry.registered())) or "nothing"))
    print("  installed on this disk     : %s"
          % (", ".join(providers.available()) or "nothing"))
    print("  Name it under [providers] enabled in %s and read this screen "
          "again. Nothing was recorded: a consent is recorded against the "
          "exact table you were shown, and you were shown none."
          % (home / config.CONFIG_NAME))


def _print_ids_that_would_go(home):
    """The ids this request would actually carry, listed one by one.

    Ruled with the wording of `projects[].id` itself, and for the same
    reason. "It sends project ids" is a description; twenty directory names
    on the screen is the thing being agreed to, and it is what let the
    owner see that the field he had been told was not a name was, on the
    default path, exactly the name.

    The roster is enough - whether a row leaves is decided by `sensitive`,
    which is in `roster.json` - so no project is opened to print this.
    Deliberately outside the fingerprint: the roster changes when the user
    adds a project, and a consent that expired on Tuesday because a
    directory appeared would teach people that the warning means nothing.
    """
    roster = config.load_roster(home)
    if not roster.exists:
        print("  no roster yet, so there is nothing this would send. Run "
              "`murscope init` first and read this screen again.")
        return
    going, withheld = outbound.preview(roster)
    print("  the ids this request would carry, today, one per line:")
    if not going:
        print("    (none)")
    for identifier in going:
        print("    %s" % identifier)
    print("  %d id(s) above; %d project(s) marked sensitive are not "
          "described at all, only counted." % (len(going), withheld))
    print("  This list is what your roster holds now. It is not part of the "
          "fingerprint - adding a project does not expire your consent, "
          "because what you agreed to is that ids leave, not which ones.")


def _print_ignored_proxy():
    """Say that the environment names a proxy and that it is not used.

    **A destination in the fingerprint has to be the destination the
    request reaches.** `urllib` reads `https_proxy` by default, so every
    transport here builds its own opener with proxying off - which makes
    the disclosure true and makes this line necessary, because a user whose
    network requires a proxy would otherwise get a connection failure with
    no idea why. Silence would have been the worse of the two: either the
    payload takes an undisclosed exit, or the request fails for a reason
    nobody names. Found on a machine that has one set (DP111).
    """
    found = consent.proxy_in_environment()
    if not found:
        return
    print("  proxy      : your environment sets %s. murscope does not use "
          "it: the disclosure names a destination and a proxy is a second "
          "one, which you were not shown and did not agree to. If your "
          "network requires a proxy this request will fail, and that is the "
          "honest outcome rather than a silent detour."
          % ", ".join("%s=%s" % (name, host) for name, host in found))


def _print_alert_ids_that_could_go(home):
    """The ids an alert could ever name, listed one by one.

    The same argument `_print_ids_that_would_go` makes, and it is stronger
    here rather than merely repeated: the note's payload describes a
    portfolio in numbers and this one puts a single id in a sentence, on a
    surface that pushes rather than one you pull. "It names projects" is a
    description; twenty directory names on the screen is the thing being
    agreed to.
    """
    roster = config.load_roster(home)
    if not roster.exists:
        print("  no roster yet, so there is nothing an alert could name. Run "
              "`murscope init` first and read this screen again.")
        return
    going, withheld = alerts.preview(roster)
    print("  the ids an alert could name, from the roster you have today, "
          "one per line:")
    if not going:
        print("    (none)")
    for identifier in going:
        print("    %s" % identifier)
    print("  %d id(s) above; %d project(s) marked sensitive are never "
          "evaluated by an alert rule, so none of them can appear and no "
          "count of them leaves either." % (len(going), withheld))
    print("  This list is what your roster holds now. It is not part of the "
          "fingerprint - adding a project does not expire your consent, "
          "because what you agreed to is that an id leaves, not which one.")


def _print_disclosure(provider, destination, home=None):
    """Print the disclosure and return its fingerprint, or None.

    `None` means this build could not say what that provider would send,
    and the caller records nothing. A screen is still printed - the one
    that says why - because silence and a wrong table fail in the same
    direction: the user does not find out what would leave.
    """
    label, shown, lines = disclosure_for(provider, home)
    if label is None:
        _print_no_disclosure(provider, home or murscope_home())
        return None
    print("What a request from murscope to %s would contain" % destination)
    print("  provider   : %s" % provider)
    print("  destination: %s" % destination)
    print("  this is    : %s" % label)
    # Directly under what it is, and above the field table, because it is
    # the line that distinguishes the two consents this build can record
    # and a reader who stops early should have met it (DP125, E8).
    print("  who sends  : %s" % _WHO_SENDS[label])
    print("  on whose key: yours. There is no account, no proxy and no "
          "server belonging to this product.")
    _print_ignored_proxy()
    print()
    for line in lines:
        print("  %s" % line)
    print()
    for sentence in _CLOSING[label]:
        print("  %s" % sentence)
    print()
    if label == BOARD_SUMMARY:
        _print_ids_that_would_go(home or murscope_home())
        print()
    if label == ALERT_NOTICE:
        _print_alert_ids_that_could_go(home or murscope_home())
        print()
    digest = consent.fingerprint(shown, provider, destination)
    print("  fingerprint: %s" % digest)
    print("  Your consent is recorded against that fingerprint, not against "
          "the provider's name. If a later version of murscope would send "
          "one more field, or send it somewhere else, the fingerprint "
          "changes and murscope asks you again instead of assuming the "
          "answer carries over.")
    return digest


def consent_command(argv):
    """`murscope consent show|grant|status`. Returns an exit code."""
    home = murscope_home()
    action = argv[0] if argv else ""
    rest = [item for item in argv[1:] if not item.startswith("-")]
    provider = rest[0] if rest else ""
    destination = consent.destination_of(_flag_value(argv, "--to") or "")

    if action == "status":
        recorded = consent.recorded(home)
        print("murscope consent")
        print("  location: %s" % consent.consent_dir(home))
        if not recorded:
            print("  nothing recorded. Nothing can be sent: `send()` refuses "
                  "anything that is not a recorded consent covering the "
                  "exact request.")
            return 0
        stale = 0
        for name in recorded:
            grant, problems = consent.load(name, home)
            for line in problems:
                print("  ! %s" % line)
            if grant is None:
                stale += 1
                continue
            # Against every disclosure this build knows, not against the
            # board summary's. A grant recorded for a reader is
            # fingerprinted on a different table, and comparing it with the
            # summary's would report a perfectly current consent as stale -
            # which teaches the user that the staleness warning means
            # nothing, and that is the one thing it cannot afford to mean.
            covered_by = [label for label, shown in known_disclosures()
                          if grant.matches(shown, grant.provider,
                                           grant.destination)]
            covers = bool(covered_by)
            print("  %s" % grant)
            if covers:
                print("      covers: %s" % ", ".join(covered_by))
            print("      %s" % (
                "still covers what murscope would send today"
                if covers else
                "NO LONGER COVERS what murscope would send today - what "
                "leaves has changed since you agreed. Run `murscope consent "
                "show %s --to %s` and grant again if you still want it."
                % (grant.provider, grant.destination)))
            stale += 0 if covers else 1
        return 1 if stale else 0

    if action not in ("show", "grant") or not provider or not destination:
        print("usage: murscope consent show  <provider> --to <url>\n"
              "       murscope consent grant <provider> --to <url> [--yes]\n"
              "       murscope consent status\n"
              "  the url is read for its scheme and host only; a path and a "
              "query string are dropped, because a query string is where a "
              "key ends up and a destination is a place, not a request.")
        return 2

    digest = _print_disclosure(provider, destination, home)
    if digest is None:
        # Both actions stop here, and `grant` stops for the stronger
        # reason: a consent is recorded against the exact table the user
        # was shown, and there was no table.
        return 2
    if action == "show":
        print()
        print("  Nothing was recorded. `murscope consent grant %s --to %s` "
              "records it." % (provider, destination))
        return 0

    if "--yes" not in argv:
        print()
        try:
            answer = input("Type yes to agree to exactly the above: ")
        except EOFError:
            answer = ""
        if answer.strip().lower() != "yes":
            print("murscope: nothing recorded. Consent is an act; not "
                  "answering is not one.")
            return 1
    _label, shown, _lines = disclosure_for(provider, home)
    grant, path = consent.record(provider, destination, shown, home)
    print("murscope: recorded %s" % grant)
    print("  at %s" % path)
    print("  fingerprint %s" % digest)
    return 0


def _resolve_reader(home):
    """(reader, problems). The registered provider that offers a reading.

    Found by capability, never by name. Rule 16 forbids this module any
    knowledge of which provider module reads what, and `registry.readers()`
    is how that stays true while the command still works: a provider that
    registers a `reads` callable answers here, and one that does not is
    invisible.
    """
    settings = config.load_config(home)
    enabled = settings.section("providers").get("enabled", [])
    _loaded, problems = providers.load(enabled)
    found = registry.readers()
    if not found:
        return None, problems + [
            "no enabled provider offers a reading. Three things have to be "
            "true and they fail differently: the network layer has to be "
            "installed (`pip install 'murscope[ai]'` - a base install does "
            "not carry it and that is promise two, not an oversight), "
            "config.toml has to name the provider under [providers] enabled, "
            "and a consent has to be recorded. This is the first of the "
            "three: %s."
            % ("nothing is enabled" if not enabled else
               "enabled: %s" % ", ".join(str(name) for name in enabled))]
    return found[0], problems


def _fetch(reader, documents, grant, home, backend, counter):
    """Post one batch and return the parsed answers. Counts the requests.

    The counter is not decoration. E2 is a defect in which a *second*
    request silently did not happen, so a measurement of E2 that cannot
    count requests measures nothing (DP87).
    """
    counter.append(len(documents))
    return reader.reads([document for _label, document in documents],
                        home=home, grant=grant, backend=backend)


def _reading_now():
    from datetime import datetime, timezone  # noqa: PLC0415 - one use
    return datetime.now(timezone.utc)


def _print_series_tail(days, now, count=7):
    keys_sorted = sorted(days)[-count:]
    for date in keys_sorted:
        marker = "  <- today" if date == contributions.today_key(now) else ""
        print("    %s  %4d%s" % (date, days[date], marker))


def contributions_command(argv):
    """`murscope contributions [--measure]`. Returns an exit code.

    **This is the one command in the product that makes a real request**,
    and it is a command rather than a step of `run` for a reason worth
    stating: `murscope selftest` installs an audit hook that refuses every
    network event, and the gate runs the selftest. A reader wired into the
    collection path would either have to weaken that hook or be
    permanently untestable. DP93 left that conflict to the daily note's
    stage and DP90 has already refused the comfortable way out, so this
    stage does not touch the hook at all - it puts the socket somewhere
    the hook was never asked to cover.
    """
    home = murscope_home()
    settings = config.load_config(home)
    backend = settings.section("keys").get("backend", "file")
    measure = "--measure" in argv

    reader, problems = _resolve_reader(home)
    for line in problems:
        print("murscope contributions: %s" % line)
    if reader is None:
        return 2

    try:
        grant = consent.require(reader.name, reader.destination,
                                contributions.shown(), home)
    except (consent.ConsentRequired, consent.ConsentStale) as exc:
        print("murscope contributions: %s" % exc)
        return 1

    now = _reading_now()
    counter = []
    documents = (contributions.measurement_documents(now) if measure
                 else contributions.reading_documents(now))
    labels = [label for label, _document in documents]

    print("murscope contributions")
    print("  provider   : %s" % reader.name)
    print("  destination: %s" % consent.destination_of(reader.destination))
    _print_ignored_proxy()
    print("  consent    : %s" % grant)
    print("  asked at   : %s" % contributions.stamp(now))
    print("  ranges     : %s" % ", ".join(labels))
    print()

    try:
        answers = _fetch(reader, documents, grant, home, backend, counter)
    except Exception as exc:
        # A failed request is where the cache earns its keep, and the only
        # place it does. Nothing above consulted it.
        cached, cache_problems = contributions.read_cache(home)
        for line in cache_problems:
            print("  ! %s" % line)
        print("  ! the request did not complete: %s" % exc)
        try:
            reading = contributions.resolve(None, cached, now)
        except contributions.NoReading as nothing:
            print("  %s" % nothing)
            return 1
        print()
        print("  total (from cache): %d" % reading.total)
        for line in reading.problems:
            print("  ! %s" % line)
        return 1

    by_label = dict(zip(labels, answers))
    series = {}
    for label in labels:
        try:
            series[label] = contributions.days_from(by_label[label])
        except contributions.NoReading as exc:
            print("  ! %s: %s" % (label, exc))
            return 1

    if measure:
        return _report_measurement(series, by_label, now, home, counter,
                                   reader, grant, backend)

    corrected = contributions.overlay(series[contributions.CLAMPED],
                                      series[contributions.OVERLAY])
    moved = contributions.corrections(series[contributions.CLAMPED],
                                      series[contributions.OVERLAY])
    reading = contributions.Reading(
        corrected, contributions.stamp(now), "live",
        api_total=contributions.reported_total(by_label[contributions.CLAMPED]),
        moved=moved)
    path = contributions.write_cache(reading, home)

    print("  total this year (corrected): %d" % reading.total)
    print("  the platform's own total for the year range: %s"
          % (reading.api_total if reading.api_total is not None else "not stated"))
    print("  days the recent window corrected: %d" % len(moved))
    for date, was, is_now in moved:
        print("    %s  %d -> %d" % (date, was, is_now))
    print()
    print("  the last 7 days of the corrected series:")
    _print_series_tail(corrected, now)
    print()
    print("  cache written to %s. It is a failure fallback and nothing "
          "else: the next run re-fetches whatever its age (DP48)." % path)
    return 0


def _report_measurement(series, by_label, now, home, counter, reader, grant,
                        backend):
    """Reproduce E1, E2 and E3 on this account and write the evidence down.

    ADR-0003's numbers came from one account at one moment. This does not
    assert them - it measures again and prints what came back, so a
    divergence reads as a finding about the platform rather than as a
    failed test. Nothing below adjusts anything until it matches.
    """
    import json  # noqa: PLC0415 - only the evidence file needs it

    today = contributions.today_key(now)
    unclamped = series[contributions.UNCLAMPED]
    clamped = series[contributions.CLAMPED]
    recent = series[contributions.OVERLAY]

    print("E1  a range endpoint in the future returns a frozen snapshot")
    print("    both queries were made in the same run, seconds apart, on one "
          "account.")
    print("      end of 31 December : today %4d   year %5d"
          % (unclamped.get(today, 0), contributions.total(unclamped)))
    print("      end of now         : today %4d   year %5d"
          % (clamped.get(today, 0), contributions.total(clamped)))
    e1_day = clamped.get(today, 0) - unclamped.get(today, 0)
    e1_year = contributions.total(clamped) - contributions.total(unclamped)
    print("      difference         : today %+4d   year %+5d" % (e1_day, e1_year))
    if e1_day == 0 and e1_year == 0:
        print("    THE TWO RANGES AGREE. ADR-0003 measured a difference on "
              "one account at one time; this account, now, shows none. That "
              "is a finding about the platform and it is reported rather "
              "than tuned away - the clamp stays, because a range ending "
              "later than now is wrong whether or not it is answered wrongly "
              "today.")
    print()

    print("E2  the cache is a failure fallback, never a freshness shortcut")
    print("      requests made this run  : %d" % sum(counter))
    second = contributions.stamp(_reading_now())
    print("      this run re-fetched every range it needed rather than "
          "reading the file beside the board.")
    print("      first answer stamped    : %s" % contributions.stamp(now))
    print("      run finished            : %s" % second)
    print("    There is no age parameter anywhere in murscope.contributions. "
          "A cache consulted before a request publishes figures from one "
          "moment under a timestamp from another, and no value of a TTL "
          "makes that honest (DP48).")
    print()

    corrected = contributions.overlay(clamped, recent)
    moved = contributions.corrections(clamped, recent)
    print("E3  \"1 January to today\" is the range the platform precomputes")
    print("      year range, summed from its own series : %5d"
          % contributions.total(clamped))
    print("      the platform's stated total for it     : %5s"
          % contributions.reported_total(by_label[contributions.CLAMPED]))
    print("      corrected by a live recent window      : %5d"
          % contributions.total(corrected))
    print("      difference                             : %+5d"
          % (contributions.total(corrected) - contributions.total(clamped)))
    print("      days the overlay moved                 : %5d" % len(moved))
    for date, was, is_now in moved:
        print("        %s  %d -> %d" % (date, was, is_now))
    if not moved:
        print("    THE TWO AGREE ON THIS ACCOUNT. ADR-0003 calls this the "
              "entry worth the most and says so in as many words: a "
              "divergence is information about the platform and belongs in "
              "the report before it belongs in a fix. Agreement is the same "
              "kind of information. The overlay stays, because a range the "
              "platform precomputes for its own annual view is a range whose "
              "freshness this product does not control.")
    print()

    reading = contributions.Reading(
        corrected, contributions.stamp(now), "live",
        api_total=contributions.reported_total(by_label[contributions.CLAMPED]),
        moved=moved)
    record = {
        "schema": contributions.SCHEMA,
        "measured_at": contributions.stamp(now),
        "finished_at": second,
        "requests": sum(counter),
        "e1": {"unclamped_today": unclamped.get(today, 0),
               "unclamped_year": contributions.total(unclamped),
               "clamped_today": clamped.get(today, 0),
               "clamped_year": contributions.total(clamped)},
        "e2": {"cache_consulted_before_fetch": False,
               "requests_made": sum(counter)},
        "e3": {"year_range_total": contributions.total(clamped),
               "platform_stated_total": contributions.reported_total(
                   by_label[contributions.CLAMPED]),
               "corrected_total": contributions.total(corrected),
               "days_moved": [{"date": d, "was": w, "now": n}
                              for d, w, n in moved]},
    }
    from .guard import guard_write_path  # noqa: PLC0415 - one write
    evidence = guard_write_path(
        home / contributions.CACHE_DIRNAME / "measurement.json",
        json.dumps(record, indent=2, sort_keys=True) + "\n")
    contributions.write_cache(reading, home)
    print("  the numbers above are written to %s so nobody has to hold a "
          "token to read them later." % evidence)
    return 0


def _resolve_writer(home):
    """(writer, problems). The registered provider that can write a note.

    Found by capability, never by name - `registry.writers()`, the same
    shape `_resolve_reader` uses, for the same Rule 16 reason. Enabling two
    writers is refused rather than silently resolved: sending the same
    payload to two vendors because a list had two entries in it is not a
    thing this command should decide on the user's behalf.
    """
    settings = config.load_config(home)
    enabled = settings.section("providers").get("enabled", [])
    _loaded, problems = providers.load(enabled)
    found = registry.writers()
    if not found:
        return None, problems + [
            "no enabled provider can write a note. Three things have to be "
            "true and they fail differently: the network layer has to be "
            "installed (`pip install 'murscope[ai]'` - a base install does "
            "not carry it and that is promise two, not an oversight), "
            "config.toml has to name the provider under [providers] enabled, "
            "and a consent has to be recorded. This is the first of the "
            "three: %s."
            % ("nothing is enabled" if not enabled else
               "enabled: %s" % ", ".join(str(name) for name in enabled))]
    if len(found) > 1:
        return None, problems + [
            "%d providers that can write a note are enabled (%s). murscope "
            "will not pick one for you: the payload would go to whichever "
            "happened to import first, and a consent recorded for one is not "
            "a consent for the other. Name one under [providers] enabled."
            % (len(found), ", ".join(p.name for p in found))]
    return found[0], problems


def _print_provider_table(home):
    """Every enabled provider, and whether it has ever completed a round trip.

    **The evidence column is the point (DP89).** Four adapters ship for the
    daily note and one of them has spoken to a model; a table listing four
    names without saying which reads as four working providers, and that is
    a claim this line has not earned. So `evidence` is a column of its own,
    and the reason a provider is unproven is printed under it rather than
    left in a commit message.

    **The accounting below the table runs whether or not there is a table.**
    It used to sit after an early return, so the one install where the
    reader most needs it - nothing enabled that can write a note, and no
    explanation of what the modules on disk are then doing - printed a bare
    "no enabled provider can write a note." and stopped. It is also the only
    configuration in which a base install reaches these lines at all, which
    is what let the sentence be wrong for a stage without any check
    touching it.
    """
    settings = config.load_config(home)
    _loaded, problems = providers.load(
        settings.section("providers").get("enabled", []))
    for line in problems:
        print("  ! %s" % line)
    rows = [row for row in registry.describe_all() if row.get("writes")]
    if rows:
        print("  %-12s %-10s %s" % ("provider", "evidence", "destination"))
        for row in rows:
            print("  %-12s %-10s %s"
                  % (row["name"], row["evidence"], row["destination"]))
            if row.get("evidence_note"):
                print("      %s" % row["evidence_note"])
    else:
        print("  no enabled provider can write a note.")
    # **This table lists what is enabled *and can write a note*, not what is
    # installed**, and there are therefore two reasons a module on disk has
    # no row - which is why there are two sentences below rather than one.
    #
    # There was one, and it was false for a reader who had enabled the
    # contributions reader: `github` is imported the moment config.toml names
    # it, it is in `sys.modules`, `registry.readers()` returns it, and the
    # only reason it has no row here is that it registers `reads` and not
    # `writes`. The line said "installed and not enabled, so they were not
    # imported", which was wrong about the module and wrong about the count.
    # It sent nothing anywhere; it is repaired because a sentence wider than
    # the set it describes is the defect this line has found eight times.
    listed = {row["name"] for row in rows}
    imported = set(registry.registered())
    # Enabled, imported, and no note to write. `registry.registered()` is the
    # answer to "was it imported", asked of the registry rather than guessed
    # from the configuration: a name in `enabled` that failed to import is
    # not imported, and the problems above already say so.
    without_a_writer = sorted(name for name in imported if name not in listed)
    # Never named by configuration, so never imported. This is the set the
    # old sentence claimed to be describing.
    not_imported = sorted(name for name in providers.available()
                          if name not in listed and name not in imported)
    if without_a_writer:
        print("  %d enabled provider module(s) were imported and have no row "
              "above because they register no note writer: %s. Being enabled "
              "is not being able to write a note - a reader, for instance, "
              "registers a reading and nothing else."
              % (len(without_a_writer), ", ".join(without_a_writer)))
    if not_imported:
        print("  %d other provider module(s) are installed and not enabled, "
              "so they were not imported and have no row above: %s. Rule 13: "
              "a provider runs when config.toml names it and at no other "
              "time. Name one under [providers] enabled to see its evidence."
              % (len(not_imported), ", ".join(not_imported)))


MATRIX_COLUMNS = (
    ("module", "name", 14),
    ("from", "distribution", 15),
    ("enabled", "enabled", 8),
    ("imported", "imported", 9),
    ("socket", "socket", 9),
    ("reads", "reads", 9),
    ("writes", "writes", 9),
    ("alerts", "alerts", 9),
    ("evidence", "evidence", 10),
)


def modules_command(argv):
    """`murscope modules`: the module matrix. Returns an exit code.

    **The table and the sentences under it are one deliverable (DP115).**
    The last accounting sentence this product shipped about provider
    modules was false for anybody who had enabled the contributions
    reader, and it was false because it was *computed by subtraction* -
    installed minus the ones with a row - rather than read off what the
    registry actually holds. Everything printed here is read off
    `matrix.rows()`, and the one thing a row cannot know says `unknown`.

    That word is the whole design. A module `config.toml` does not name is
    never imported, so `register()` never ran for it and this command has
    no idea what it reads or writes. Printing `-` there would be a
    statement, and the statement would be wrong. Importing it to find out
    would be running a provider configuration did not name, which Rule 13
    forbids and which no amount of curiosity earns. So there is a third
    answer, and the sentence under the table says why it exists.

    The `socket` column is the exception, and it is the exception for a
    reason worth printing: `boundary.survey()` *reads* each module's
    source instead of importing it, so that column is known for every
    module on the disk whether or not anything ever ran it.
    """
    if argv:
        print("usage: murscope modules")
        return 2
    home = murscope_home()
    settings = config.load_config(home)
    # The same load `daily --providers` does, and for the same reason: this
    # is the only thing that may cause a provider to be imported, and it
    # imports exactly the names configuration gave (Rule 13).
    _loaded, problems = providers.load(
        settings.section("providers").get("enabled", []))
    for line in problems:
        print("  ! %s" % line)

    print("murscope modules: what is installed, what is enabled, what each does")
    table = matrix.rows(home, settings)
    if not table:
        # Not an early return. The install with nothing to show is the one
        # whose reader most needs the sentences below, and an early return
        # is exactly what made `daily --providers` print one bare line and
        # stop on a base install (DP115).
        print("  no provider module is installed under murscope.providers at "
              "all, which is not a base install - `noop` ships with the base "
              "package.")
    else:
        print("  " + "".join(width.column(head, size)
                             for head, _key, size in MATRIX_COLUMNS))
        for row in table:
            print("  " + "".join(width.column(str(row[key]), size)
                                 for _head, key, size in MATRIX_COLUMNS))
            if row["known"]:
                print("      %s  |  stage %s  |  sends to %s"
                      % (row["summary"], row["stage"], row["destination"]))
                if row["evidence_note"]:
                    print("      evidence: %s" % row["evidence_note"])
            if row["socket_imports"]:
                print("      opens a socket through: %s" % row["socket_imports"])
    for line in matrix.sentences(table):
        print("  %s" % line)
    return 0


def daily_command(argv):
    """`murscope daily [--send] [--again] [--providers]`. An exit code.

    **Why this is a command and not a step of `run` (DP93).** `murscope
    selftest` installs an audit hook that refuses every socket event for
    the whole of its run, and the gate runs the selftest. A provider wired
    into the collection path would leave exactly two options - weaken the
    hook, or ship a provider that can never be exercised - and DP90 has
    already ruled out the comfortable form of the first (a localhost
    exemption; a socket is a socket). Stage three took the same shape for
    the contributions reader and it is taken again here rather than
    inherited: the socket goes somewhere the hook was never asked to cover,
    and `selftest` says in words which commands its window does *not*
    contain instead of generalising to "the run".

    What that window covers and what it does not is now printed by the
    selftest itself, because the failure this line has found seven times is
    a guard whose sentence is wider than its window.

    With no `--send` this prints what would leave and sends nothing. That
    is the default on purpose: the smallest payload that produces a useful
    note is a product decision, and a user cannot weigh it from a
    description of the payload - only from the payload.
    """
    home = murscope_home()
    settings = config.load_config(home)
    backend = settings.section("keys").get("backend", "file")

    if "--providers" in argv:
        print("murscope daily: providers that can write a note")
        _print_provider_table(home)
        return 0

    (_settings, roster, locale, catalog, vocabulary), problems = prepare(home)
    for line in problems:
        print("note: %s" % line)
    collected, collect_problems = collect_records(
        roster, settings, catalog, vocabulary)
    for line in collect_problems:
        print("note: %s" % line)

    try:
        payload = outbound.build(collected)
    except outbound.DisclosureMismatch as exc:
        print("murscope daily: %s" % exc)
        return 1

    now = _reading_now()
    day = daily.day_key(now)
    slot, slot_problems = daily.read_slot(day, home)
    for line in slot_problems:
        print("murscope daily: ! %s" % line)

    if "--send" not in argv:
        print("murscope daily: this is what a request would carry, byte for "
              "byte. Nothing was sent.")
        print()
        print(outbound.canonical(payload).decode("utf-8"))
        print()
        print("  digest    : %s" % outbound.payload_digest(payload))
        print("  fields    : %d declared in murscope.outbound.DISCLOSURE"
              % len(outbound.DISCLOSURE))
        print("  today     : %s" % (slot if slot is not None else
                                    "nothing recorded for %s" % day))
        attempt, why = daily.should_attempt(slot, now)
        print("  next round: %s - %s"
              % ("would send" if attempt else "would not send", why))
        print()
        print("  `murscope daily --send` sends it, if a consent covering "
              "exactly the above is on file.")
        return 0

    writer, writer_problems = _resolve_writer(home)
    for line in writer_problems:
        print("murscope daily: %s" % line)
    if writer is None:
        return 2

    attempt, why = daily.should_attempt(slot, now)
    if "--again" in argv and not attempt:
        attempt, why = True, "%s - overridden by --again" % why
    print("murscope daily")
    print("  provider   : %s" % writer.name)
    print("  destination: %s" % consent.destination_of(writer.destination))
    _print_ignored_proxy()
    print("  evidence   : %s" % writer.evidence)
    print("  slot       : %s" % why)
    if not attempt:
        if slot is not None and slot.status == daily.OK:
            print()
            print(slot.text)
        return 0

    try:
        grant = consent.require(writer.name, writer.destination,
                                outbound.shown(), home)
    except (consent.ConsentRequired, consent.ConsentStale) as exc:
        print("murscope daily: %s" % exc)
        return 1
    print("  consent    : %s" % grant)

    model = settings.section("providers").get("model") or None
    backoff, backoff_problems = daily.resolve_backoff(
        settings.section("providers").get("retry_after_seconds"))
    for line in backoff_problems:
        print("  ! %s" % line)
    attempts = daily.next_attempt_number(slot)
    try:
        answer = writer.writes(payload, home=home, grant=grant,
                               backend=backend, model=model)
    except Exception as exc:
        # A degraded slot, with the reason and a moment it becomes worth
        # asking again. **The retry is the whole point** - upstream, a
        # degraded result held a day after its cause had cleared, because
        # the scheduler compared dates (DP49).
        note = daily.record_degraded(
            day, now, "%s: %s" % (type(exc).__name__, exc),
            provider=writer.name,
            destination=consent.destination_of(writer.destination),
            attempts=attempts, backoff=backoff)
        path = daily.write_slot(note, home)
        print("  ! the request did not complete: %s" % exc)
        print("  recorded a degraded slot at %s" % path)
        print("  %s" % daily.should_attempt(note, _reading_now())[1])
        return 1

    note = daily.record_ok(
        day, now, writer.name,
        consent.destination_of(writer.destination),
        answer.get("model") or "", outbound.payload_digest(payload),
        answer.get("text") or "", attempts=attempts)
    path = daily.write_slot(note, home)
    print("  model      : %s" % note.model)
    print("  digest     : %s" % note.digest)
    print()
    print(note.text)
    print()
    print("  written to %s" % path)
    return 0


def _resolve_alerter(home):
    """(alerter, problems). The registered provider that can deliver an alert.

    Found by capability, never by name - `registry.alerters()`, the third
    of the three lookups and the same shape as the other two for the same
    Rule 16 reason. Two enabled alerters is refused rather than resolved:
    sending the same alert to two destinations because a list had two
    entries is not a thing this command decides on anybody's behalf, and a
    consent recorded for one is not a consent for the other.

    **A `None` here is not a failure.** Nothing enabled that can deliver an
    alert is the default state of this product, and the caller's answer to
    it is a local delivery, not an exit code.
    """
    settings = config.load_config(home)
    enabled = settings.section("providers").get("enabled", [])
    _loaded, problems = providers.load(enabled)
    found = registry.alerters()
    if not found:
        return None, problems
    if len(found) > 1:
        return None, problems + [
            "%d providers that can deliver an alert are enabled (%s). "
            "murscope will not pick one for you: the alert would go to "
            "whichever happened to import first, and a consent recorded for "
            "one is not a consent for the other. Name one under [providers] "
            "enabled." % (len(found), ", ".join(p.name for p in found))]
    return found[0], problems


def _alert_destination(settings):
    """(destination, problem). Where an alert would go, from config.toml.

    The destination is in `config.toml` and the full delivery URL is in the
    key store, and that split is deliberate rather than awkward. A webhook
    URL is itself a credential, so it cannot be the thing printed on a
    consent screen or fingerprinted into a grant; but a consent has to be
    bound to *where the data goes* (DP90), so the scheme and host have to be
    somewhere the core can read without knowing any provider's name. They
    are therefore stated twice, on purpose, and the provider refuses to
    deliver if its stored URL does not resolve to the destination it was
    handed - two independent statements of one fact that have to agree.
    """
    raw = settings.section("alerts").get("destination") or ""
    destination = consent.destination_of(raw)
    if not destination:
        return "", ("[alerts] names no destination in config.toml, so "
                    "nothing can be sent and nothing can be consented to. "
                    "The scheme and host go there; the full URL, which is "
                    "itself the credential, goes in the key store.")
    return destination, None


def _deliver_locally(events, skipped, home):
    """Print every alert that fired. The default, and the only default.

    The task book asked for "the system's own notification centre, or the
    terminal" and this is the terminal half only. The other half needs
    `osascript` or `notify-send`, which is exactly the non-git subprocess
    DP129 refused for `launchctl`: Rule 5's allowlist is `git`, and an
    audit already found what happens when it becomes "git and the ones we
    decided were fine". The owner ruled on that rather than it being
    quietly substituted. Under the scheduled job this stream is
    MURSCOPE_HOME/alerts.log, which is where an unattended run leaves
    something a person can read.

    **The skipped count is printed here and is in no payload.** That is the
    trade `alerts.DISCLOSURE` describes: visible on your machine, absent
    from the wire.
    """
    for event in events:
        print("  %s" % event.sentence())
    if not events:
        print("  nothing fired.")
    if skipped:
        print("  %d project(s) marked sensitive were not evaluated at all. "
              "No rule saw them, nothing about them is remembered between "
              "runs, and this count is printed here and is in no alert."
              % skipped)


def alert_command(argv, unattended=False):
    """`murscope alert [--send] [--status]`. Returns an exit code.

    Also the whole of what `murscope-alert` does, with `unattended=True`.

    **Local delivery happens whatever else does.** An alert that fired is
    printed before anything is attempted over a wire, so a broken webhook
    costs you the remote copy and not the alert.

    **Outbound is off until three things are true**, and they fail
    differently: the network layer has to be installed (`pip install
    'murscope[ai]'`), `config.toml` has to name a delivery provider and a
    destination, and a consent has to be recorded against the alert's own
    disclosure - which is a different table and a different fingerprint
    from the daily note's, so agreeing to one has never agreed to the
    other. Under the scheduled entry point all three being true is what
    makes an alert leave with nobody present; that is the authority the
    consent screen says you are granting.

    Non-zero when an outbound delivery was attempted and did not complete.
    That is the failure this surface cannot afford to be quiet about: the
    user is not here, the alert did not arrive, and a zero exit code would
    be the process reporting a good night.
    """
    home = murscope_home()
    settings = config.load_config(home)
    backend = settings.section("keys").get("backend", "file")

    history, history_problems = alerts.read_deliveries(home)
    for line in history_problems:
        print("murscope alert: ! %s" % line)

    if "--status" in argv:
        print("murscope alert status")
        print("  history: %s" % alerts.deliveries_path(home))
        if not history:
            print("  nothing recorded yet.")
            return 0
        for record in history[-10:]:
            print("  %s  %-6s %-10s %s%s"
                  % (record.get("at", "?"), record.get("status", "?"),
                     record.get("rule", "?"), record.get("project", "?"),
                     ("  -> %s" % record.get("destination"))
                     if record.get("destination") else ""))
            if record.get("detail"):
                print("      %s" % record["detail"])
        broken = alerts.failures_since_last_success(history)
        if broken:
            print("  %d outbound delivery(ies) have failed since the last one "
                  "that succeeded. Alerts fired and did not arrive." % broken)
            return 1
        print("  no outbound delivery has failed since the last one that "
              "succeeded.")
        return 0

    (_settings, roster, _locale, catalog, vocabulary), problems = prepare(home)
    for line in problems:
        print("note: %s" % line)
    collected, collect_problems = collect_records(
        roster, settings, catalog, vocabulary)
    for line in collect_problems:
        print("note: %s" % line)

    previous, state_problems = alerts.read_state(home)
    for line in state_problems:
        print("murscope alert: ! %s" % line)
    events, skipped, taken = alerts.evaluate(collected, previous)

    print("murscope alert%s" % (" (unattended)" if unattended else ""))
    _deliver_locally(events, skipped, home)

    broken = alerts.failures_since_last_success(history)
    if broken:
        # Said on every run, not only when `--status` is asked for. A
        # failure the user has to go and look for is a failure they find out
        # about from the person who was waiting for the alert.
        print("  ! %d earlier outbound delivery(ies) have failed since the "
              "last one that succeeded (`murscope alert --status`)." % broken)

    alerter, alerter_problems = _resolve_alerter(home)
    for line in alerter_problems:
        print("murscope alert: %s" % line)
    destination, destination_problem = _alert_destination(settings)

    send = unattended or "--send" in argv
    records = []
    exit_code = 0
    if events and send and alerter is not None and not destination_problem:
        grant, refusal = _alert_grant(alerter, destination, home)
        if grant is None:
            print("murscope alert: %s" % refusal)
            print("  the alert(s) above were delivered locally and nothing "
                  "left this machine.")
            for event in events:
                records.append(_delivery_record(event, alerts.LOCAL, "",
                                                refusal))
        else:
            print("  provider   : %s" % alerter.name)
            print("  destination: %s" % destination)
            print("  consent    : %s" % grant)
            _print_ignored_proxy()
            for event in events:
                records.append(_send_one_alert(
                    alerter, event, grant, destination, home, backend,
                    unattended))
            exit_code = 1 if any(r["status"] == alerts.FAILED
                                 for r in records) else 0
    else:
        why = _why_nothing_leaves(events, send, alerter, destination_problem)
        print("  outbound   : %s" % why)
        for event in events:
            records.append(_delivery_record(event, alerts.LOCAL, "", why))
        if events and not send:
            print()
            print("  this is what one of those would carry, byte for byte, "
                  "if outbound delivery were configured and consented to. "
                  "Nothing was sent.")
            print()
            print(alerts.canonical(
                alerts.build(events[0], unattended)).decode("utf-8"))
            print()

    # The snapshot is written whatever happened to the deliveries, and that
    # is the right way round: it records what murscope *observed*, not what
    # it managed to tell anybody. A snapshot withheld because a webhook was
    # down would make the next run fire the same alerts again, which is how
    # an outage becomes a flood.
    alerts.write_state(taken, home)
    if records:
        alerts.record_deliveries(history, records, home)
    return exit_code


def _why_nothing_leaves(events, send, alerter, destination_problem):
    """One sentence saying which of the gates is shut. Never silence."""
    if not events:
        return "nothing fired, so nothing was sent."
    if not send:
        return ("`murscope alert` alone sends nothing. `--send` sends, and "
                "the scheduled alert job sends without asking - which is "
                "what its consent screen says you are agreeing to.")
    if alerter is None:
        return ("no enabled provider can deliver an alert. Three things have "
                "to be true and they fail differently: the network layer has "
                "to be installed (`pip install 'murscope[ai]'`), config.toml "
                "has to name the provider under [providers] enabled, and a "
                "consent has to be recorded. This is the first.")
    return destination_problem or "nothing left this machine."


def _alert_grant(alerter, destination, home):
    """(grant, refusal). The consent for this exact alert, or why not."""
    try:
        return consent.require(alerter.name, destination, alerts.shown(),
                               home), None
    except (consent.ConsentRequired, consent.ConsentStale) as exc:
        return None, str(exc)


def _delivery_record(event, status, destination, detail, digest=""):
    return {"at": _reading_now().isoformat(timespec="seconds"),
            "rule": event.rule, "project": event.project, "status": status,
            "destination": destination, "detail": detail, "digest": digest}


def _send_one_alert(alerter, event, grant, destination, home, backend,
                    unattended):
    """Deliver one alert and return the record of what happened to it.

    Every path through this returns a record. **There is no branch that
    leaves without writing one**, which is the point: the caller appends
    whatever comes back to the delivery history, so an alert that did not
    arrive is a line in a file rather than an absence somebody would have
    to notice.
    """
    try:
        payload = alerts.build(event, unattended)
    except alerts.DisclosureMismatch as exc:
        print("  ! %s did not become a payload: %s" % (event.rule, exc))
        return _delivery_record(event, alerts.FAILED, destination, str(exc))
    digest = alerts.payload_digest(payload)
    try:
        answer = alerter.alerts(payload, home=home, grant=grant,
                                backend=backend, destination=destination)
    except Exception as exc:
        detail = "%s: %s" % (type(exc).__name__, exc)
        print("  ! this alert did not leave: %s" % detail)
        print("    %s" % event.sentence())
        return _delivery_record(event, alerts.FAILED, destination, detail,
                                digest)
    print("  sent %s (%s, status %s)"
          % (event.project, event.rule, answer.get("status")))
    return _delivery_record(event, alerts.SENT, destination,
                            "", digest)


def implemented_commands():
    """The command names HELP documents, in the order it lists them.

    One source, so the two cannot drift. They had: the unknown-command
    message named five while HELP named ten.
    """
    found = []
    for line in HELP.splitlines():
        if not line.startswith("  ") or line.startswith("   "):
            continue
        word = line.strip().split(" ", 1)[0]
        if word and word[0].isalpha() and word not in found:
            found.append(word)
    return found


HELP_FLAGS = ("-h", "--help")

# The flags each command takes (DP155). **A flag nobody recognised used
# to be ignored**, and the two halves of that were separately wrong.
#
# `--help` was the loud half: every command except `timer` *ran* when it
# was handed one. `murscope open --help` opened a browser, `murscope alert
# --help` collected the roster and wrote a snapshot, `murscope run --help`
# built the board, and `murscope init --help` started scanning the user's
# home for projects. A question about a command is not permission to run
# it, and answering it by doing the thing is the one reply that cannot be
# taken back.
#
# The quiet half is this table. `murscope alert --sendd` collected,
# delivered locally, and never said that the word it was given was not
# `--send`. The failure direction was safe - a misspelling could only ever
# send less - but a command that silently does something other than what
# was typed leaves no line anybody can read back to what they asked for,
# and the next flag to be misspelled need not fail in the safe direction.
# The two entry points that run unattended already exit 2 on an argument
# they cannot read; the dispatcher was the surface that did not.
#
# `note` is deliberately absent: everything after the project name is free
# text the user writes about their own project, and "- waiting on the
# vendor" is a sentence rather than a flag.
COMMAND_FLAGS = {
    "run": (),
    "try": (),
    "doctor": (),
    "open": (),
    "init": ("--add", "--yes", "-y"),
    "key": (),
    "consent": ("--to", "--yes"),
    "contributions": ("--measure",),
    "daily": ("--send", "--again", "--providers"),
    "timer": ("--alerts", "--interval", "--yes"),
    "alert": ("--send", "--status"),
    "modules": (),
    "selftest": (),
    "status": ("--explain",),
}
FREE_TEXT_COMMANDS = ("note",)
# Flags whose next argument is a value rather than another flag, so that
# `--interval -5` is a bad interval and not an unknown flag.
VALUE_FLAGS = ("--to", "--interval", "--add", "--explain")


def command_usage(name):
    """The lines HELP gives one command, plus whatever it says for itself.

    Read out of HELP rather than written down a second time, for the same
    reason `implemented_commands()` is read out of it: two copies of one
    fact drift, and the copy nobody prints is the one that goes stale.
    """
    lines = []
    taking = False
    for line in HELP.splitlines():
        if line.startswith("  ") and not line.startswith("   "):
            taking = line.strip().split(" ", 1)[0] == name
        elif not line.startswith("   "):
            taking = False
        if taking:
            lines.append(line)
    if name == "timer":
        lines = lines + [""] + schedule.usage_lines()
    return lines


def unknown_flags(command, argv):
    """Flags this command does not take, in the order they were typed."""
    if command in FREE_TEXT_COMMANDS:
        return []
    accepted = set(COMMAND_FLAGS.get(command, ())) | set(HELP_FLAGS)
    found = []
    skip = False
    for item in argv:
        if skip:
            skip = False
            continue
        if not item.startswith("-") or item == "-":
            continue
        name = item.split("=", 1)[0]
        if name not in accepted:
            found.append(item)
        elif name in VALUE_FLAGS and "=" not in item:
            skip = True
    return found


def asks_for_help(argv):
    return any(item in HELP_FLAGS for item in argv)


def print_command_usage(command):
    for line in command_usage(command):
        print(line)
    print()
    print("`murscope --help` lists every command. Nothing was run: this "
          "command was asked about, not asked for.")


def main(argv=None):
    args = list(sys.argv[1:] if argv is None else argv)

    if not args or args[0] in ("-h", "--help"):
        print(HELP)
        return 0
    if args[0] == "--version":
        print("%s %s" % (PROGRAM, __version__))
        return 0

    # Both of these happen **before** anything is dispatched, and that
    # placement is the whole of the fix rather than a detail of it. Each
    # command used to read its own arguments, which meant each one decided
    # for itself what an unreadable argument meant - fifteen commands, six
    # of which answered "run anyway", and `murscope open --help` opening a
    # browser to answer a question about itself. One place decides now, and
    # it decides the same way every time: an argument this build cannot
    # read is answered, never acted on.
    if args[0] in implemented_commands():
        if asks_for_help(args[1:]):
            print_command_usage(args[0])
            return 0
        stray = unknown_flags(args[0], args[1:])
        if stray:
            print("%s %s: %s is not a flag this command takes. Nothing was "
                  "run.\n  A flag it did not recognise used to be ignored, "
                  "which made `--sendd` a quiet way of not sending and left "
                  "you no line to read it back from."
                  % (PROGRAM, args[0], ", ".join(repr(f) for f in stray)))
            print()
            print_command_usage(args[0])
            return 2

    if args[0] == "run":
        return run(args[1:])
    if args[0] == "try":
        return preview.run(args[1:])
    if args[0] == "init":
        from . import wizard  # noqa: PLC0415 - wizard imports cli back
        return wizard.run(args[1:])
    if args[0] == "note":
        return notes.run(args[1:])
    if args[0] == "doctor":
        return doctor_command(args[1:])
    if args[0] == "open":
        return open_board(args[1:])
    if args[0] == "key":
        return key_command(args[1:])
    if args[0] == "consent":
        return consent_command(args[1:])
    if args[0] == "contributions":
        return contributions_command(args[1:])
    if args[0] == "daily":
        return daily_command(args[1:])
    if args[0] == "timer":
        return schedule.run(args[1:])
    if args[0] == "alert":
        return alert_command(args[1:])
    if args[0] == "modules":
        return modules_command(args[1:])
    if args[0] == "selftest":
        return selftest.main(args[1:])
    if args[0] == "status":
        home = murscope_home()
        return explain.run(args[1:], config.load_config(home),
                           config.load_roster(home), home)

    # Read out of HELP rather than restated here. The hand-written list
    # said five commands while the help two lines below listed ten - it had
    # been true at M1 and nobody updated it, which is the whole argument for
    # not keeping a second copy of a fact.
    print("%s: '%s' is not a command. This build supports: %s."
          % (PROGRAM, args[0], ", ".join(implemented_commands())))
    return 2


if __name__ == "__main__":
    sys.exit(main())
