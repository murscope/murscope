"""Rule 33: no command acts on an argument it could not read.

Two shapes of one defect (DP155), and the loud one is `--help`.

**A question about a command was answered by running it.** `murscope open
--help` opened a browser. `murscope alert --help` collected the roster and
wrote an alert snapshot. `murscope run --help` built the board, `murscope
daily --help` printed the payload a send would carry, and `murscope init
--help` started scanning the user's home directory for projects. Only
`murscope timer` recognised the word; every other command took `--help`
as an argument it had no use for, ignored it, and did the thing. The
acceptance window that found this created a file in the owner's real
`~/.murscope` doing nothing but asking what a command was.

**The quiet one is every other unrecognised flag.** `murscope alert
--sendd` collected, delivered locally and never mentioned that the word it
was handed was not `--send`. The failure direction was safe - a
misspelling could only ever send less - but a command that silently does
something other than what was typed leaves no line anybody can read back
to what they asked for, and the next flag to be misspelled will not
necessarily fail in the safe direction.

So: **an argument this build cannot read is answered, never acted on.**
Every command answers `-h`/`--help` with its usage, exits 0 and writes
nothing; every command that does not take free text refuses a flag it does
not recognise with exit 2, names the flag, and writes nothing. `note` is
the one exception and it is a category rather than a favour - everything
after the project name is a sentence the user writes about their own
project, and "- waiting on the vendor" is not a flag.

**Measured by running the commands, not by reading the dispatcher.** Each
one goes into a subprocess with `HOME` and `MURSCOPE_HOME` both pointed at
throwaway directories, which are hashed before and after: what a command
*wrote* is the evidence that it acted, and it is the evidence a source
scan cannot produce. Pointing `HOME` at the throwaway matters as much as
`MURSCOPE_HOME` - the shape being refused here is `init` with no path,
which walks the conventional project directories under the user's home,
and a check that reproduced the defect by scanning the owner's workspace
would be a worse thing than the one it is checking. The absence of a board
in the throwaway home is what keeps `open` from reaching a browser even if
this rule is failing.

What walks into it (DP87): the command list is `cli.implemented_commands()`
- the same list the help screen is read from - so a command added to this
build is a command this check exercises without anybody remembering to add
it here. The commands covered are counted against that list, and a run
that exercised fewer than it names is red rather than green.

Fails when: a command answers `--help` by exiting non-zero, by writing
anything into either throwaway directory, or by printing nothing that
names it; a command that takes flags absorbs one it does not recognise -
by exiting anything but 2, by writing something, or by not saying which
argument it could not read; a command cannot be run at all or does not
finish; or fewer commands were exercised than this build declares.
"""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
PACKAGE = REPO_ROOT / "murscope"

HELP_KIND = "help"
STRAY_KIND = "stray"
# A flag no build will ever take. Spelled so that it could not be mistaken
# for a near-miss of a real one - the point of this probe is a word the
# command has to refuse, not a word it might have meant.
STRAY_FLAG = "--murscope-rule33-not-a-flag"

TIMEOUT = 120


def _wanted_exit(record):
    return 0 if record.get("kind") == HELP_KIND else 2


def detect(payload):
    """Findings for a transcript of commands that were actually run.

    Pure: a JSON document in, a list of strings out. Each record is one
    invocation - the command, what it was handed, what it exited with,
    what it printed, and every path that appeared or changed underneath
    the throwaway `HOME` and `MURSCOPE_HOME` while it ran.

    The transcript is the interface deliberately. What this rule asserts
    is about behaviour that only exists once a process has run, and a
    detector fed source could only ever assert that a dispatcher *looks*
    like it answers `--help`.
    """
    try:
        records = json.loads(payload.decode("utf-8", errors="replace"))
    except ValueError as exc:
        return ["the transcript is not readable JSON (%s), so no command's "
                "behaviour was judged." % exc]
    if not isinstance(records, list) or not records:
        return ["the transcript holds no invocations at all. A rule about "
                "what commands do that ran none of them reports on nothing "
                "(DP87)."]

    findings = []
    for record in records:
        command = record.get("command", "?")
        kind = record.get("kind")
        typed = " ".join(record.get("argv") or [])
        output = record.get("output") or ""

        if record.get("error"):
            findings.append(
                "`murscope %s` could not be run at all (%s). A command this "
                "check cannot exercise is a command nothing here asserts "
                "anything about." % (typed, record["error"]))
            continue

        wrote = record.get("wrote") or []
        if wrote:
            findings.append(
                "`murscope %s` wrote %s. It was asked %s and it acted: an "
                "argument this build cannot read is answered, never acted "
                "on, and a file on disk is the difference between the two."
                % (typed, ", ".join(sorted(wrote)),
                   "what it does" if kind == HELP_KIND
                   else "to do something with a word it does not know"))

        code = record.get("exit")
        if code != _wanted_exit(record):
            findings.append(
                "`murscope %s` exited %s and should have exited %d. %s"
                % (typed, code, _wanted_exit(record),
                   "Asking a command for its usage is not an error."
                   if kind == HELP_KIND else
                   "An argument this build cannot read has to be refused "
                   "loudly - the two entry points that run unattended "
                   "already exit 2 on one, and a command that exits 0 has "
                   "told the caller it did what was asked."))

        if kind == HELP_KIND:
            if command not in output:
                findings.append(
                    "`murscope %s` printed nothing that names %r. A usage "
                    "screen that does not describe the command it was asked "
                    "about is a command answering a different question: %r"
                    % (typed, command, output.strip()[:120]))
        elif kind == STRAY_KIND:
            flag = record.get("flag") or ""
            if flag and flag not in output:
                findings.append(
                    "`murscope %s` never says which argument it could not "
                    "read. A refusal the user cannot map back to the word "
                    "they typed sends them to diff their own command line: "
                    "%r" % (typed, output.strip()[:120]))
        else:
            findings.append(
                "an invocation of `murscope %s` carries no kind, so nothing "
                "decided what it should have done." % typed)
    return findings


def _snapshot(*roots):
    """{relative path: content hash} across every throwaway directory."""
    found = {}
    for root in roots:
        base = Path(root)
        if not base.is_dir():
            continue
        for path in sorted(base.rglob("*")):
            if not path.is_file():
                continue
            key = "%s/%s" % (base.name, path.relative_to(base).as_posix())
            try:
                found[key] = hashlib.sha256(path.read_bytes()).hexdigest()
            except OSError as exc:  # unreadable is still a change to report
                found[key] = "unreadable: %s" % exc
    return found


def _changed(before, after):
    return sorted(key for key in set(before) | set(after)
                  if before.get(key) != after.get(key))


def run_one(command, argv, kind, flag=""):
    """One invocation, in its own process, against throwaway directories.

    `HOME` goes to the throwaway as well as `MURSCOPE_HOME`, and that is
    not tidiness: `murscope init` with no path walks the conventional
    project directories under the user's home, so a check that reproduced
    this defect against the real one would be scanning somebody's
    workspace to prove that a command should not have run.
    """
    with tempfile.TemporaryDirectory() as work:
        home = Path(work) / "home"
        murscope_home = Path(work) / "murscope-home"
        home.mkdir()
        murscope_home.mkdir()
        record = {"command": command, "argv": argv, "kind": kind,
                  "flag": flag}
        before = _snapshot(home, murscope_home)
        environment = dict(os.environ,
                           HOME=str(home),
                           MURSCOPE_HOME=str(murscope_home),
                           PYTHONPATH=str(REPO_ROOT))
        # No browser, no pager, no editor: this drives commands that in a
        # failing build would reach for one.
        environment.pop("BROWSER", None)
        try:
            result = subprocess.run(
                [sys.executable, "-m", "murscope.cli"] + argv,
                cwd=str(work), env=environment, timeout=TIMEOUT,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        except subprocess.TimeoutExpired:
            record["error"] = ("it did not finish within %d seconds"
                               % TIMEOUT)
            record["wrote"] = _changed(before, _snapshot(home, murscope_home))
            return record
        except OSError as exc:
            record["error"] = "%s: %s" % (type(exc).__name__, exc)
            return record
        record["exit"] = result.returncode
        record["output"] = result.stdout.decode("utf-8", errors="replace")
        record["wrote"] = _changed(before, _snapshot(home, murscope_home))
        return record


def transcript():
    """(records, commands, free_text) - every command this build declares.

    The list comes from `cli.implemented_commands()`, which is read out of
    the help screen, so a command that lands in this build is exercised
    here without anybody remembering to add it.
    """
    sys.path.insert(0, str(REPO_ROOT))
    from murscope import cli  # noqa: PLC0415 - the list is the product's own

    commands = list(cli.implemented_commands())
    free_text = list(getattr(cli, "FREE_TEXT_COMMANDS", ()))
    records = []
    for command in commands:
        records.append(run_one(command, [command, "--help"], HELP_KIND))
        if command in free_text:
            continue
        records.append(run_one(command, [command, STRAY_FLAG], STRAY_KIND,
                               STRAY_FLAG))
    return records, commands, free_text


def main():
    if not (PACKAGE / "cli.py").exists():
        print("OK: murscope/cli.py not present yet; nothing to inspect.")
        return 0

    records, commands, free_text = transcript()
    bad = 0

    # DP87 as a floor: a transcript missing a command reports nothing about
    # it and would still print a green line naming a number.
    exercised = {record["command"] for record in records}
    missing = sorted(set(commands) - exercised)
    if missing or not commands:
        print("this build declares %d command(s) and %d were exercised; %s. A "
              "rule about what every command does that ran some of them is "
              "reporting on a subset it did not name."
              % (len(commands), len(exercised),
                 "missing: %s" % ", ".join(missing) if missing
                 else "the build declares none"))
        bad += 1

    for finding in detect(json.dumps(records).encode("utf-8")):
        print(finding)
        bad += 1

    if bad:
        print("\nFAILED: %d command(s) acted on an argument they could not "
              "read." % bad)
        return 1
    helps = sum(1 for r in records if r["kind"] == HELP_KIND)
    strays = sum(1 for r in records if r["kind"] == STRAY_KIND)
    print("OK: %d command(s) run %d time(s) against a throwaway HOME and "
          "MURSCOPE_HOME. All %d answered --help with their own usage, exit "
          "0, and wrote nothing; the %d that take flags refused %r with exit "
          "2, named it, and wrote nothing. %s takes free text and is "
          "deliberately not asked to refuse a word."
          % (len(commands), len(records), helps, strays, STRAY_FLAG,
             ", ".join(free_text) or "No command"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
