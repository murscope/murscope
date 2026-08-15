"""`murscope timer`: install, inspect and remove the scheduled jobs.

**Two jobs since M4's second stage, and they are not variations of one
thing.** The `collect` job runs `murscope-timer`, which collects and
renders and from whose entry point no transport is reachable at all (DP124,
Rule 26). The `alert` job runs `murscope-alert`, which evaluates the alert
rules and **may deliver one alert off this machine while nobody is here**
(DP125) - and which Rule 27 holds to exactly that, on the same kind of call
graph walk, so it can reach the alert's transport and no other.

They are separate files, written by separate acts: `--alerts` is what adds
the second one, and `install` says in as many words which of the two can
send. One job that did both would be one call graph, and then neither rule
could say anything.

This module builds a job description and hands it to guard.py. It does
not run one, it does not activate one, and it never speaks to the
scheduler - which is a design decision rather than an omission, and the
reason is Rule 5's second half.

**The package shells out to git and to nothing else.** That sentence is a
red line and not a style preference: an audit found that skipping
non-git programs let `rm -rf` and `/bin/sh -c` write into a monitored
project on a green gate. `launchctl bootstrap` and `systemctl --user
enable` are both perfectly harmless commands, and adding either one means
the allowlist stops being "git" and starts being "git and the ones we
decided were fine", which is the state that hole came out of. So murscope
writes the file, prints the one command that activates it, and stops. The
activation is the user's own act, in their own shell, where they can read
it first.

The cost is stated rather than hidden: `murscope timer status` reports
which files exist on disk, not whether the scheduler has them loaded.
Those are different questions and this command can only answer one of
them honestly. It says so on screen.

Platforms (DP89's rule, applied to platforms rather than to providers -
what is demonstrated and what is not are never printed in the same
column without a word between them):

  darwin   a launchd agent. Demonstrated: written, loaded, fired, and
           removed on a real machine.
  linux    a systemd user service and timer. Generated and readable;
           **never loaded by a real systemd**, because this line has no
           Linux machine to load it on.
  other    refused, with the reason. Windows Task Scheduler takes its job
           from `schtasks /create`, not from a file dropped in a
           directory, so the file-and-print shape this module is built on
           does not carry there at all - it needs the subprocess call the
           paragraph above refuses. That is a real decision to take, and
           it is not taken here.
"""
from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path

from .guard import (SCHEDULE_FILES, SCHEDULE_JOBS, guard_schedule_remove,
                    guard_schedule_write, murscope_home,
                    permitted_schedule_paths)

# The console script each job runs. Not `murscope run` and not `murscope
# alert`: the whole of DP124 is that a thing which runs unattended has no
# send path reachable from its entry point, and `murscope` is an argv
# dispatcher from which `daily --send` is one word away. The alert job has
# its own script for the mirror-image reason - it *may* send, and only the
# alert, which is Rule 27's statement about `murscope.alert:main`.
TIMER_PROGRAM = "murscope-timer"
ALERT_PROGRAM = "murscope-alert"

COLLECT_JOB = "collect"
ALERT_JOB = "alert"

# Derived from the guard's own table rather than written down again. The
# name of the job and the path it is written to are one fact, and this
# module holding a second copy of it is how `job_files()` below would one
# day build a body nothing asks for while the guard writes a file with no
# body - two literals that agree until somebody edits one.
_DARWIN = dict(SCHEDULE_JOBS["darwin"])
_LINUX = dict(SCHEDULE_JOBS["linux"])
LABEL = Path(_DARWIN[COLLECT_JOB][0]).stem
ALERT_LABEL = Path(_DARWIN[ALERT_JOB][0]).stem
UNIT = Path(_LINUX[COLLECT_JOB][0]).stem
ALERT_UNIT = Path(_LINUX[ALERT_JOB][0]).stem

DEFAULT_INTERVAL = 86400
# A timer is a convenience, not a poll. Anything under this is somebody
# who meant to run `murscope run` in a loop, and a scheduled job that
# walks every repository on the machine every thirty seconds is a
# different product with a different power budget.
MINIMUM_INTERVAL = 300


# Which console script each job runs, as a module constant. It exists
# because `console_script()` below joins a name onto a directory and then
# reads it, and Rule 17 refuses that shape when the joined name came from
# the caller - `root / rel` on an absolute `rel` is `rel`, which is how a
# read leaves the project it was supposed to stay in.
#
# **The check was right and the first version of this was wrong**, which
# is worth recording rather than quietly fixing: generalising
# `timer_program()` into a function taking a script name turned a join
# over a module literal into a join over a parameter, and the gate said
# so on the first run. The permitted shape is a name that came out of a
# constant, so the job-to-script mapping is one and a name that is not in
# it never reaches a path at all.
CONSOLE_SCRIPTS = ((COLLECT_JOB, TIMER_PROGRAM), (ALERT_JOB, ALERT_PROGRAM))


def console_script(job):
    """The absolute path of one job's console script, or None.

    Three candidates, and this docstring used to describe an order that is
    not what happens. It said "the interpreter's own script directory
    first, PATH second", which reads as two candidates; there are three,
    and the middle one answers far less often than that sentence implies.

    What actually runs, in order:

    1. **the directory of the script that is running** (`sys.argv[0]`).
       This is the one that answers, on every supported way of invoking
       murscope: a console script installed beside the interpreter that
       installed it. It is also the one that gets the answer *right* on a
       machine with more than one install - the job should run the
       murscope that installed it, not whichever is first on a PATH that a
       scheduler does not inherit anyway;
    2. **the resolved interpreter's directory** (`sys.executable`), which
       answers only where the interpreter is not a link out of its own
       install. In a virtual environment it never does: `bin/python` is a
       symlink to the real interpreter, `resolve()` follows it out of the
       environment, and the directory it lands in holds that interpreter's
       scripts rather than this one's. Measured, not assumed - in a fresh
       venv the candidate is `<the base interpreter's bin>/murscope-timer`
       and there is no such file. It is kept because a non-venv install
       where `argv[0]` is not a console script is the case it covers, and
       removing a fallback because today's shape does not reach it is how
       the next shape has none;
    3. **PATH**, last, and the least trustworthy of the three for the
       reason above.

    None of this changes what any user gets: candidate 1 answers, and the
    install path refuses to write a job at all when all three come back
    empty. What changed is that the sentence now describes the code.
    """
    name = ""
    for known, program in CONSOLE_SCRIPTS:
        if known == job:
            name = program
    if not name:
        raise RuntimeError(
            "job %r runs no console script this module knows about (%s). The "
            "mapping is a module constant on purpose: the only names that "
            "may be joined onto a directory and read are the ones written "
            "here." % (job, ", ".join(known for known, _p in CONSOLE_SCRIPTS)))
    candidates = []
    argv0 = sys.argv[0] if sys.argv and sys.argv[0] else ""
    if argv0:
        candidates.append(Path(argv0).resolve().parent / name)
    candidates.append(Path(sys.executable).resolve().parent / name)
    for candidate in candidates:
        if candidate.is_file() and os.access(str(candidate), os.X_OK):
            return candidate
    found = shutil.which(name)
    return Path(found).resolve() if found else None


def timer_program():
    """The collecting job's console script. Kept as its own name because
    the install path reads better for it than for a lookup by string."""
    return console_script(COLLECT_JOB)


def alert_program():
    """The alert job's console script."""
    return console_script(ALERT_JOB)


def _xml_text(value):
    """Escape a value for a plist. `&` first, or the escapes eat each other."""
    return (str(value).replace("&", "&amp;").replace("<", "&lt;")
            .replace(">", "&gt;"))


def launchd_plist(program, home, interval, label=LABEL, log="timer.log"):
    """The launchd agent, as text.

    `StandardOutPath` points inside MURSCOPE_HOME. launchd does that write,
    not murscope, and it lands in the one directory this product owns - so
    a run with nobody watching still leaves something a person can read
    afterwards, which is most of what "it ran at 3am" is worth.

    That log is also the whole of the alert job's **local** delivery. The
    owner ruled the notification centre out for the reason DP129 ruled
    `launchctl` out: it needs `osascript` or `notify-send`, and Rule 5's
    allowlist is `git` rather than `git and the ones we decided were fine`.
    So an unattended alert's local half is this file, which the scheduler
    writes and a person can read.
    """
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" '
        '"http://www.apple.com/DTDs/PropertyList-1.0.dtd">\n'
        '<plist version="1.0">\n'
        '<dict>\n'
        '  <key>Label</key>\n'
        '  <string>%s</string>\n'
        '  <key>ProgramArguments</key>\n'
        '  <array>\n'
        '    <string>%s</string>\n'
        '  </array>\n'
        '  <key>EnvironmentVariables</key>\n'
        '  <dict>\n'
        '    <key>MURSCOPE_HOME</key>\n'
        '    <string>%s</string>\n'
        '  </dict>\n'
        '  <key>StartInterval</key>\n'
        '  <integer>%d</integer>\n'
        '  <key>RunAtLoad</key>\n'
        '  <true/>\n'
        '  <key>StandardOutPath</key>\n'
        '  <string>%s</string>\n'
        '  <key>StandardErrorPath</key>\n'
        '  <string>%s</string>\n'
        '</dict>\n'
        '</plist>\n'
        % (_xml_text(label), _xml_text(program), _xml_text(home), interval,
           _xml_text(Path(home) / log),
           _xml_text(Path(home) / log)))


def systemd_service(program, home, description):
    return (
        "[Unit]\n"
        "Description=%s\n"
        "\n"
        "[Service]\n"
        "Type=oneshot\n"
        "Environment=MURSCOPE_HOME=%s\n"
        "ExecStart=%s\n" % (description, home, program))


def systemd_timer(interval, description):
    return (
        "[Unit]\n"
        "Description=%s\n"
        "\n"
        "[Timer]\n"
        "OnBootSec=5min\n"
        "OnUnitActiveSec=%ds\n"
        "Persistent=true\n"
        "\n"
        "[Install]\n"
        "WantedBy=timers.target\n" % (description, interval))


COLLECT_DESCRIPTION = "murscope: collect the roster and render the board"
ALERT_DESCRIPTION = "murscope: evaluate the alert rules and deliver"


def job_paths(job):
    """Every permitted path belonging to one job, in permitted-set order.

    A **filter over `permitted_schedule_paths()`**, never a second
    computation of it. That distinction is the whole of DP128: the
    permitted set is computed with no parameter so that no call site can
    widen it, and a function here that took a job name and built paths
    would be exactly the call-site-supplied target the guard refuses to
    accept. This one can only ever return a subset of what the guard
    already permits, and it says so by construction.

    A job whose paths are not all in the permitted set is a drift finding
    rather than a short list, for the reason `job_files()` gives below.
    """
    wanted = dict(SCHEDULE_JOBS.get(sys.platform, ())).get(job, ())
    names = set(Path(rel).name for rel in wanted)
    found = tuple(path for path in permitted_schedule_paths()
                  if path.name in names)
    if len(found) != len(wanted):
        raise RuntimeError(
            "job %r declares %d file(s) and only %d of them are in the "
            "permitted set. The job table and the permitted set are one "
            "fact; this is the two halves disagreeing."
            % (job, len(wanted), len(found)))
    return found


def job_files(job, program, home, interval):
    """[(path, text)] for one job on this platform, in permitted-set order.

    Built by pairing the guard's own table with the text each entry wants,
    so a path this module invents but the guard does not permit cannot be
    written, and a path the guard permits but this module forgets shows up
    as a missing key rather than as silence.
    """
    paths = job_paths(job)
    if not paths:
        return []
    if sys.platform == "darwin":
        if job == ALERT_JOB:
            bodies = {ALERT_LABEL + ".plist": launchd_plist(
                program, home, interval, ALERT_LABEL, "alerts.log")}
        else:
            bodies = {LABEL + ".plist": launchd_plist(program, home, interval)}
    elif sys.platform == "linux":
        unit, description = (ALERT_UNIT, ALERT_DESCRIPTION) \
            if job == ALERT_JOB else (UNIT, COLLECT_DESCRIPTION)
        bodies = {unit + ".service": systemd_service(program, home, description),
                  unit + ".timer": systemd_timer(interval, description)}
    else:  # pragma: no cover - permitted_schedule_paths() is empty here
        return []
    unbodied = sorted(path.name for path in paths if path.name not in bodies)
    if unbodied:
        # Loudly, rather than as a KeyError two lines down. The guard's
        # table is the authority on which files exist; a name here with
        # nothing to put in it means the two have drifted, and the right
        # answer is to say which name rather than to write the others and
        # leave the scheduler a job with a missing half.
        raise RuntimeError(
            "the scheduling table permits %s for job %r, and this module has "
            "no content for %s. The permitted paths and the files that fill "
            "them are one fact and this is the two halves disagreeing."
            % (", ".join(path.name for path in paths), job,
               ", ".join(unbodied)))
    return [(path, bodies[path.name]) for path in paths]


def activation_command(job=COLLECT_JOB):
    """The one command the user runs to turn a job on, and its opposite."""
    if sys.platform == "darwin":
        paths = job_paths(job)
        label = ALERT_LABEL if job == ALERT_JOB else LABEL
        return ("launchctl bootstrap gui/$(id -u) %s" % paths[0],
                "launchctl bootout gui/$(id -u)/%s" % label)
    if sys.platform == "linux":
        unit = ALERT_UNIT if job == ALERT_JOB else UNIT
        return ("systemctl --user enable --now %s.timer" % unit,
                "systemctl --user disable --now %s.timer" % unit)
    return ("", "")  # pragma: no cover - refused before this is reached


def _refuse_platform():
    print("murscope timer: no timer is written for this platform (%s)."
          % sys.platform)
    print("  Written and demonstrated: darwin (launchd).")
    print("  Written, never loaded on a real system: linux (systemd user "
          "timer).")
    print("  Not written: everything else. Windows Task Scheduler takes its "
          "job from `schtasks /create` rather than from a file, and murscope "
          "shells out to git and to nothing else (Rule 5), so the shape this "
          "command is built on does not carry there.")
    return 2


def _interval_from(argv):
    """(interval, problem). Refuses anything under MINIMUM_INTERVAL."""
    if "--interval" not in argv:
        return DEFAULT_INTERVAL, None
    index = argv.index("--interval")
    if index + 1 >= len(argv):
        return None, "--interval needs a number of seconds."
    raw = argv[index + 1]
    try:
        seconds = int(raw)
    except ValueError:
        return None, "--interval takes seconds as a whole number, not %r." % raw
    if seconds < MINIMUM_INTERVAL:
        return None, ("--interval %d is below the floor of %d seconds. A "
                      "scheduled job that walks every repository you listed "
                      "more often than that is a poll, and murscope is not "
                      "built to be one." % (seconds, MINIMUM_INTERVAL))
    return seconds, None


def _confirm(prompt):
    """True when the user agreed. EOF and anything but y/yes is a refusal."""
    try:
        answer = input(prompt)
    except (EOFError, KeyboardInterrupt):
        # No prompt was answerable, so this is a refusal. The caller says
        # so; saying it here too printed the same sentence twice, which
        # reads as two things having been refused.
        print("")
        return False
    return answer.strip().lower() in ("y", "yes")


def install(argv):
    if not permitted_schedule_paths():
        return _refuse_platform()

    interval, problem = _interval_from(argv)
    if problem:
        print("murscope timer install: %s" % problem)
        return 2

    with_alerts = "--alerts" in argv
    jobs = [(COLLECT_JOB, TIMER_PROGRAM, timer_program())]
    if with_alerts:
        jobs.append((ALERT_JOB, ALERT_PROGRAM, alert_program()))
    for _job, name, program in jobs:
        if program is None:
            print("murscope timer install: cannot find the %r console script "
                  "next to this interpreter or on PATH. A scheduler does not "
                  "inherit your shell's PATH, so the job needs an absolute "
                  "path and murscope will not guess one." % name)
            return 2

    home = murscope_home()
    plan = [(job, program, job_files(job, program, home, interval))
            for job, _name, program in jobs]

    # Shown before anything is written, in full. The guard prints each
    # target again at the moment it writes it; this is the plan and that
    # is the receipt, and they are deliberately two different sentences.
    print("murscope timer install, on %s:" % sys.platform)
    print("  every: %d seconds, and once at login" % interval)
    print("  with MURSCOPE_HOME: %s" % home)
    print("")
    print("  These are the only things murscope writes outside "
          "MURSCOPE_HOME, and this is the complete list of what it writes:")
    for job, program, files in plan:
        print("    job %r runs %s" % (job, program))
        for path, _text in files:
            print("      %s%s" % (path, "  (replacing what is there)"
                                  if path.exists() else ""))
    print("")
    print("  The %r job collects and renders the board. It cannot send "
          "anything: it runs %s, which takes no arguments and has no path to "
          "any transport at all (DP124, Rule 26)."
          % (COLLECT_JOB, TIMER_PROGRAM))
    if with_alerts:
        print("")
        print("  The %r job is the other thing, and it is the one worth "
              "reading twice. It runs %s, which evaluates the alert rules "
              "and delivers. Locally it prints and its output lands in "
              "%s. **It can also send an alert off this machine while you "
              "are not here** - but only if you have installed the network "
              "layer, named a delivery provider in config.toml, and "
              "recorded a consent against the alert's own disclosure. "
              "Without all three it delivers locally and says so (DP125)."
              % (ALERT_JOB, ALERT_PROGRAM, home / "alerts.log"))
        print("  It cannot send the daily note, cannot read your "
              "contribution calendar, and cannot reach any other payload: "
              "Rule 27 walks its call graph and fails if it can.")
    else:
        print("")
        print("  No alert job is being written. `murscope timer install "
              "--alerts` adds one, and that is a separate act because that "
              "job is the one that can send while you are away.")
    print("")

    if "--yes" not in argv and not _confirm("  write these? [y/N] "):
        print("  refused (nothing was written).")
        return 1

    for _job, _program, files in plan:
        for path, text in files:
            guard_schedule_write(path, text)

    print("")
    print("  Written. murscope does not activate any of them - it shells out "
          "to git and to nothing else, so the scheduler is yours to talk to:")
    for job, _program, _files in plan:
        activate, deactivate = activation_command(job)
        print("      %s" % activate)
        print("        (job %r; to undo that later: %s)" % (job, deactivate))
    print("  then `murscope timer uninstall` to remove the file(s).")
    return 0


def uninstall(argv):
    if not permitted_schedule_paths():
        return _refuse_platform()

    print("murscope timer uninstall:")
    removed = 0
    absent = 0
    for path in permitted_schedule_paths():
        if guard_schedule_remove(path) is None:
            absent += 1
            print("  already absent: %s" % path)
        else:
            removed += 1
    print("")
    print("  %d file(s) removed, %d already absent. Nothing else is left "
          "anywhere: these paths are the whole of what `timer install` "
          "wrote, for every job it can write." % (removed, absent))
    # **The one thing uninstall does not remove**, said here rather than
    # found by somebody hashing the directory afterwards. `guard_schedule_
    # write()` creates the parent when it is missing - `~/.config/systemd/
    # user` does not exist on a machine that never had a user unit - and an
    # empty directory is left behind. Removing it would mean deleting a
    # directory the scheduler owns and that other software writes into,
    # which is a larger act than the one being undone; `rmdir` on a
    # directory somebody else has since put a file in is exactly the kind
    # of guess this product does not make. So it stays, empty, and this
    # line is the difference between a choice and an oversight.
    #
    # Stated unconditionally rather than only when the directory turns out
    # to be empty, and the reason is Rule 6 rather than brevity: finding
    # out whether it is empty means listing a directory outside
    # MURSCOPE_HOME, which is a traversal this package does not get to
    # make. The gate said so. The sentence is true either way.
    for path in sorted(set(p.parent for p in permitted_schedule_paths())):
        print("  %s is left in place. murscope created it if it was missing "
              "and does not remove it: the scheduler owns that directory and "
              "other software writes into it, so removing it would be a "
              "larger act than the one being undone." % path)
    if removed:
        print("  If you activated either job, the scheduler may still hold a "
              "loaded copy until you tell it otherwise:")
        for job, _rels in SCHEDULE_JOBS.get(sys.platform, ()):
            print("      %s   (job %r)" % (activation_command(job)[1], job))
    return 0


def status(argv):
    if not permitted_schedule_paths():
        return _refuse_platform()

    print("murscope timer status, on %s:" % sys.platform)
    present = 0
    alert_present = 0
    for job, _rels in SCHEDULE_JOBS.get(sys.platform, ()):
        for path in job_paths(job):
            if path.exists():
                present += 1
                alert_present += 1 if job == ALERT_JOB else 0
                print("  present: %s  (job %r, %d bytes)"
                      % (path, job, path.stat().st_size))
            else:
                print("  absent:  %s  (job %r)" % (path, job))
    print("")
    # Which of the two is on disk is the sentence a reader most needs,
    # because only one of them can send. Said plainly rather than left to
    # be worked out from two file names that differ by one word.
    print("  The %r job can send an alert off this machine while you are "
          "not here, if the network layer is installed, a delivery provider "
          "is named in config.toml and a consent is recorded. It is %s. The "
          "%r job cannot send anything at all, on any configuration."
          % (ALERT_JOB,
             "on disk" if alert_present else "not on disk", COLLECT_JOB))
    print("")
    # The honest limit of this command, printed every time rather than
    # documented once. A status line that implies it asked the scheduler
    # when it only listed a directory is the same shape as a board that
    # reports a stale number as a fresh one.
    print("  This reads files. It does not ask %s whether the job is loaded "
          "or when it last ran - murscope shells out to git and to nothing "
          "else, so it cannot, and a status that implied otherwise would be "
          "guessing." % ("launchd" if sys.platform == "darwin" else "systemd"))
    if present:
        print("  What it did produce, if anything, is in %s."
              % (murscope_home() / "timer.log"))
    return 0


def usage_lines():
    """What `murscope timer` has to say beyond the one-line summary.

    A function rather than a block of text inside `run()`, because
    `murscope timer --help` is answered in `cli.main()` now - one place
    decides that `--help` prints instead of acting, for every command -
    and this is the only command with more to say than the help screen's
    summary. The sentences live beside the code they describe; the
    dispatcher asks for them.
    """
    return [
        "usage: murscope timer <install|uninstall|status> "
        "[--alerts] [--interval <seconds>] [--yes]",
        "",
        "--alerts additionally writes the alert job, which is the one that "
        "can send while you are not here. Without it, nothing murscope "
        "schedules has any path to a transport.",
        "",
        "Platforms: %s. Everything else is refused."
        % ", ".join(sorted(SCHEDULE_FILES)),
    ]


def run(argv):
    """`murscope timer <install|uninstall|status>`.

    `--help` never arrives here: `cli.main()` answers it for every command
    before dispatching, so that a command cannot answer a question by
    doing the thing it was asked about.
    """
    if not argv:
        for line in usage_lines():
            print(line)
        return 2
    if argv[0] == "install":
        return install(argv[1:])
    if argv[0] == "uninstall":
        return uninstall(argv[1:])
    if argv[0] == "status":
        return status(argv[1:])
    print("murscope timer: '%s' is not a subcommand. Try install, uninstall "
          "or status." % argv[0])
    return 2
