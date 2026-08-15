"""`murscope note <project> "..."`: the correction channel (DP37).

It writes into the roster under MURSCOPE_HOME. It never writes into the
project - not a marker, not a file, not a line appended to a ledger.
Bootstrapping a ledger belongs to the Skill at M4, where the user's own
agent puts it on disk (DP27), and Rule 5 makes the refusal structural
rather than polite: this module has no writer of its own and asks
`guard_write_path()` like everything else.

**It is a correction channel, not a data source.** The distinction is
why one command is enough and why there is no editing interface. The
value of `note` is not that the user can enter data - it is that when
the machine says something wrong about their project, there is somewhere
to say so, and the board then shows their sentence instead of the guess.
A tool that asks people to maintain notes has become the task manager
DP28 says this is not.
"""
from __future__ import annotations

import json
from datetime import date

from . import config
from .guard import guard_write_path, murscope_home

MAX_NOTE = 500


def apply(roster, project, text, today=None):
    """Return (document, message) with this note set, or (None, complaint)."""
    matches = [e for e in roster if e.id == project]
    if not matches:
        matches = [e for e in roster if e.name == project]
    if not matches:
        known = ", ".join(e.id for e in roster) or "the roster is empty"
        return None, ("no roster entry matches %r. Known: %s" % (project, known))
    if len(matches) > 1:
        return None, ("%r matches %d entries (%s); name one exactly."
                      % (project, len(matches), ", ".join(e.id for e in matches)))

    entry = matches[0]
    stamp = (today or date.today()).isoformat()
    projects = []
    for other in roster:
        row = dict(other.raw)
        if other is entry:
            if text:
                row["note"] = {"text": text[:MAX_NOTE], "since": stamp}
            else:
                row.pop("note", None)
        projects.append(row)
    verb = "cleared" if not text else "recorded"
    return ({"projects": projects},
            "%s the note on %s (roster.json, not the project)."
            % (verb, entry.id))


def run(argv):
    """`note <project> ["text"]`. An empty text clears it. Exit code."""
    if not argv or argv[0].startswith("-"):
        print("usage: murscope note <project> \"what is actually going on\"\n"
              "       murscope note <project> \"\"      clears it")
        return 2

    project = argv[0]
    text = " ".join(argv[1:]).strip()
    home = murscope_home()
    roster = config.load_roster(home)
    if not roster.exists:
        print("murscope note: no roster yet. Run murscope init first - there "
              "is nothing to attach a note to.")
        return 2

    document, message = apply(roster, project, text)
    if document is None:
        print("murscope note: %s" % message)
        return 2

    guard_write_path(home / config.ROSTER_NAME,
                     json.dumps(document, indent=2, ensure_ascii=True) + "\n")
    print("murscope: %s" % message)
    print("  it shows as `written by you` on the board, above any guess.")
    print("  run murscope run to rebuild the board.")
    return 0
