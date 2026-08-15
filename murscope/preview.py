"""`murscope try <path>`: see the thing before agreeing to anything (DP34).

Zero commitment, and the word is meant literally. The task book asked
for a board and C8 asked for the user's home to be untouched afterwards,
and those two could not both be true while the board had to land
somewhere - `guard_write_path()` refuses every target outside
MURSCOPE_HOME, and that red line does not bend for a convenience.

The way out is to give this one run a home of its own. `try` points
MURSCOPE_HOME at a fresh temporary directory for the length of the call,
so the guard governs every byte exactly as it always does, the user's
real home is not touched at all, and the board is disposable by
construction. Nothing about the write path is special-cased; only its
root is different, and it is printed so the user can go and look.

No confirmation prompt before reading. The user typed the path. Asking
"may I read this directory" immediately after being told to read it is
theatre, and DP35 constrains asking the user *for* something - a key, an
authorisation - not confirming an instruction they just gave.
"""
from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

from . import config, doctor, scan
from .guard import HOME_ENV, guard_write_path, murscope_home


class TemporaryHome(object):
    """MURSCOPE_HOME pointed at a throwaway directory, then put back.

    The guard reads the environment on every call, so redirecting the
    root is enough to move the whole write boundary - no code that writes
    has to know this is a preview.
    """

    def __init__(self):
        self.path = None
        self._previous = None
        self._was_set = False

    def __enter__(self):
        self.path = Path(tempfile.mkdtemp(prefix="murscope-try-"))
        self._was_set = HOME_ENV in os.environ
        self._previous = os.environ.get(HOME_ENV)
        os.environ[HOME_ENV] = str(self.path)
        return self

    def __exit__(self, *exc):
        if self._was_set:
            os.environ[HOME_ENV] = self._previous or ""
        else:
            os.environ.pop(HOME_ENV, None)
        return False


def _progress(name, tier):
    print("  found %-8s %s" % (tier, name), flush=True)


def run(argv):
    """Scan one directory and render a throwaway board. Exit code."""
    if not argv or argv[0].startswith("-"):
        print("usage: murscope try <path>")
        return 2

    target = Path(os.path.expanduser(argv[0]))
    if not target.exists():
        print("murscope try: %s does not exist." % target)
        return 2
    if not target.is_dir():
        print("murscope try: %s is a file, not a directory. Point try at the "
              "directory that holds your projects, or at one project."
              % target)
        return 2
    target = target.resolve()

    real_home = murscope_home()
    settings = config.load_config(real_home)
    sealed = config.sealed_dirs(settings.section("scan").get("sealed_dirs", []))

    # 1.1 first, always. A permission failure here would otherwise render
    # an empty board that looks exactly like an honest answer.
    report = doctor.check([target], sealed)
    if doctor.blocked(report):
        doctor.render(report)
        return 1

    print("scanning %s" % target)
    found = scan.discover([target], sealed, progress=_progress)

    if not found.candidates:
        print("\nNothing here looks like a project: %d directories walked, no "
              "git repository and no recently touched directory among them.\n"
              "That is a finding, not a board - murscope will not render an "
              "empty page and call it an answer." % found.directories_seen)
        return 1

    with TemporaryHome() as home:
        guard_write_path(home.path / config.ROSTER_NAME,
                         json.dumps(scan.roster_document(found), indent=2)
                         + "\n")
        from . import cli  # noqa: PLC0415 - avoids an import cycle at load
        print()
        code = cli.run([], quiet_absences=True)
        print("\n%d project(s) scanned, %d collapsed, %d worktree(s) excluded, "
              "%.1fs." % (len(found.selected), found.collapsed,
                          found.excluded_worktrees, found.seconds))
        # Precise about what "nothing was written" means. It writes - a
        # roster and a board - into a throwaway home, and saying "nothing
        # was written" invites the reading "nowhere on disk". The guard
        # still governs every byte; only its root moved.
        print("This was a preview. Your %s was not touched; the roster and "
              "board for this run went to a temporary directory instead:\n"
              "  %s\nDelete it whenever you like."
              % (real_home, home.path))
    return code
