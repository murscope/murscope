"""The activity clock: a second answer, kept in its place (DP22, DP23).

"How long since this moved" already has an answer - the last commit -
and this is a different one. A file can be touched without a commit, and
for some kinds of work that is the only trace there is.

Three constraints shape this module, and all three are about keeping a
weaker answer from behaving like a stronger one.

**Off by default (DP22).** Nothing here runs unless the user turns it on
in `config.toml`. The MVP adapter reads mtimes **inside the work tree
only** - the projects the user listed and nothing else - which is what
keeps the third promise absolute at MVP: murscope reads nothing outside
the roster. The adapter that reads an external AI tool's session
directory is M4, and it is not built here, not disabled here, not
present here.

**It never colours the tier (DP23).** Two answers to one question must
not compete. The tier is the commit clock; this is a secondary line
underneath it. Letting an editor's swap file or a build artifact paint a
dead project green would not be a bug in this adapter, it would be the
adapter working exactly as written and the board being wrong.

**Rule 14: mtime only, never content.** This module calls `os.stat` and
nothing else. It does not open a file, it does not read one, and it must
never be able to - the M4 adapter will point at a directory full of
somebody's conversations, and the difference between "when did this
change" and "what does it say" is the whole boundary. `last_touch` and
the path it came from also stay out of any outbound payload, which today
is trivially true because no payload leaves this machine, and which is
written down now because the day a provider exists is the day it stops
being trivial.
"""
from __future__ import annotations

import os
from datetime import datetime, timezone

WORKTREE_MTIME = "worktree-mtime"
SOURCES = (WORKTREE_MTIME,)
DEFAULT_SOURCE = WORKTREE_MTIME

# Bounded like every other walk here: the answer only has to be good
# enough to say "yesterday" rather than "three weeks ago".
MAX_FILES = 5000


def configured(settings):
    """(enabled, source, problems) from the [activity] table."""
    table = settings.section("activity") if hasattr(settings, "section") else {}
    enabled = bool(table.get("enabled", False))
    source = table.get("source", DEFAULT_SOURCE) or DEFAULT_SOURCE
    problems = []
    if enabled and source not in SOURCES:
        problems.append(
            "[activity]: source %r is not one this build ships (%s); the "
            "activity clock stayed off." % (source, ", ".join(SOURCES)))
        enabled = False
    return enabled, source, problems


def worktree_mtime(root, sealed):
    """Newest mtime inside the work tree. `os.stat` only - Rule 14.

    Sealed directories are pruned before descending, so a dependency tree
    that npm rewrote this morning cannot report the project as active.
    That is not only a Rule 6 obligation; it is the difference between
    this signal meaning anything and meaning nothing.
    """
    newest = None
    newest_path = ""
    seen = 0
    root_str = str(root)
    for dirpath, dirnames, filenames in os.walk(root_str):
        dirnames[:] = sorted(
            name for name in dirnames
            if name not in sealed and not name.startswith("."))
        for name in filenames:
            if name.startswith("."):
                continue
            seen += 1
            if seen > MAX_FILES:
                break
            full = os.path.join(dirpath, name)
            try:
                stamp = os.stat(full).st_mtime
            except OSError:
                continue
            if newest is None or stamp > newest:
                newest = stamp
                newest_path = os.path.relpath(full, root_str)
        if seen > MAX_FILES:
            break
    if newest is None:
        return None
    return {
        # Carries a quality like every other signal block: without one,
        # the run-wide quality summary reads a keyless dict as a signal
        # that failed and marks every project degraded the moment the
        # clock is switched on.
        "quality": "ok",
        "signal": "activity",
        "source": WORKTREE_MTIME,
        "at": datetime.fromtimestamp(newest, timezone.utc).astimezone().isoformat(
            timespec="seconds"),
        "age_days": round((datetime.now(timezone.utc).timestamp() - newest)
                          / 86400.0, 1),
        "path": newest_path,
        "files_seen": min(seen, MAX_FILES),
    }


def last_touch(root, sealed, source=DEFAULT_SOURCE):
    """The activity clock for one project, or None when it has nothing.

    Never called unless the user enabled it; the caller owns that gate so
    that "off by default" is visible at the call site rather than buried
    in here.
    """
    if source == WORKTREE_MTIME:
        return worktree_mtime(root, sealed)
    return None
