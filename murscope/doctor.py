"""`murscope doctor`: refuse to fail silently.

There is one failure this product must never have, and it is not a
crash. On macOS an interpreter without full-disk access that reads
`~/Documents` gets **zero results and no error**. The scan finds
nothing, the board renders empty, and it looks exactly like an honest
answer to "what have I got". A crash would be better: a crash is
obviously wrong, and this is quietly wrong in the one direction the user
cannot check.

So `init` runs this first, and it is a gate rather than a courtesy. If a
root sits under a protected directory and produces nothing, the run
stops and says why. **No empty board is produced on the strength of a
permission failure.**

The remedy has to name the interpreter, in full. Full-disk access is
granted to a binary, not to an application, and the binary is usually
inside a `pipx` virtual environment the user has never looked at and
could not guess. Printing "grant access to your Python" is not a
remedy; printing the path is.

Linux and Windows have no equivalent gate. They are told so in one line
rather than shown a warning about a mechanism they do not have - a
health check that cries wolf on two platforms out of three stops being
read on all three.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

# The directories macOS puts behind TCC. A scan of anything under one of
# these is subject to the silent-empty failure; a scan of ~/code is not.
PROTECTED_HOME_DIRS = ("Documents", "Desktop", "Downloads", "Movies",
                       "Music", "Pictures", "Library")
PROTECTED_ROOTS = ("/Volumes",)

OK = "ok"
BLIND = "blind"
EMPTY = "empty"
MISSING = "missing"


def is_macos():
    return sys.platform == "darwin"


def interpreter_path():
    """The exact binary the user has to authorise.

    `sys.executable` resolved: a pipx shim is a symlink and the panel
    records the target, so handing over the shim sends someone to add a
    path that will not be the one asking for access.
    """
    try:
        return str(Path(sys.executable).resolve())
    except OSError:
        return sys.executable


def is_protected(path):
    """Would macOS gate a read of this path behind full-disk access?"""
    if not is_macos():
        return False
    resolved = Path(os.path.expanduser(str(path)))
    try:
        resolved = resolved.resolve()
    except OSError:
        pass
    home = Path.home()
    for name in PROTECTED_HOME_DIRS:
        candidate = home / name
        if resolved == candidate or candidate in resolved.parents:
            return True
    return any(str(resolved).startswith(root) for root in PROTECTED_ROOTS)


def probe(root, sealed):
    """Can this root actually be read? Returns (verdict, entries_seen).

    The probe is one pruned level of `os.walk`. It has to be a walk:
    Rule 6 refuses `listdir` and `scandir` on a caller-supplied path, and
    a permission check is exactly the moment not to make an exception.
    """
    path = Path(os.path.expanduser(str(root)))
    if not path.is_dir():
        return MISSING, 0
    seen = 0
    for _dirpath, dirnames, filenames in os.walk(str(path)):
        dirnames[:] = [name for name in dirnames if name not in sealed]
        seen = len(dirnames) + len(filenames)
        dirnames[:] = []
        break
    if seen:
        return OK, seen
    # An empty result is the ambiguous case, and the ambiguity is the
    # whole problem: a genuinely empty directory and a directory we are
    # not allowed to read look identical from here. Only the protected
    # ones are called blind, because saying "you may lack permission"
    # about `~/code/scratch` would teach the user to skip this message.
    return (BLIND if is_protected(path) else EMPTY), 0


def check(roots, sealed):
    """One report over every authorised root."""
    findings = []
    for root in roots:
        verdict, seen = probe(root, sealed)
        findings.append({"root": str(root), "verdict": verdict,
                         "entries": seen})
    return {
        "platform": sys.platform,
        "macos": is_macos(),
        "interpreter": interpreter_path(),
        "roots": findings,
        "blind": [f for f in findings if f["verdict"] == BLIND],
    }


def blocked(report):
    """Is there a permission failure that must stop the run?

    Only `BLIND`, and deliberately so: a root that does not exist is a
    typo the user can see in the listing above, and a genuinely empty
    directory is a legitimate answer. Neither is the silent-permission
    failure this gate exists for, and stopping `init` on them would teach
    people to run it with the gate off.

    What this must not do is get read as "everything is fine". `render()`
    counts the other two verdicts itself rather than asking this function,
    because for four milestones it did ask - and printed "Every root
    returned entries" over a listing whose only line said `missing`.
    """
    return bool(report["blind"])


def render(report, scan=None):
    """Print the report. Numbers, not adjectives."""
    print("murscope doctor")
    print("  platform    : %s" % report["platform"])
    print("  interpreter : %s" % report["interpreter"])
    print("  roots       : %d" % len(report["roots"]))
    for finding in report["roots"]:
        print("    %-9s %s" % (finding["verdict"], finding["root"]))
    if scan is not None:
        capped = ("; %d recent repo(s) past the cap of %d, collapsed rather "
                  "than dropped" % (scan.capped, scan.cap)
                  if scan.capped else "")
        print("  candidates  : %d (%d selected, %d collapsed%s)"
              % (len(scan.candidates), len(scan.selected), scan.collapsed,
                 capped))
        print("  not proposed: %d worktree(s), %d bare repo(s), %d container "
              "folder(s) holding repositories"
              % (scan.excluded_worktrees, scan.excluded_bare, scan.containers))
        print("  readable    : %d directories walked in %.1fs"
              % (scan.directories_seen, scan.seconds))
        # The scan already knows why it walked nothing, and this command
        # printed "0 directories walked" without it: the reason sat in
        # `scan.problems` and reached no screen the user ever sees.
        for line in scan.problems:
            print("  problem     : %s" % line)

    missing = [f for f in report["roots"] if f["verdict"] == MISSING]
    empty = [f for f in report["roots"] if f["verdict"] == EMPTY]
    for finding in missing:
        print("\n  %s does not exist. Nothing was read there and nothing on a "
              "board can have come from it." % finding["root"])
    for finding in empty:
        print("\n  %s exists and returned nothing, and it is not under a "
              "directory macOS gates. That reads as an empty directory - but "
              "an empty directory and one this interpreter may not read look "
              "identical from here, so this is what was seen, not a verdict."
              % finding["root"])

    if blocked(report):
        _blind_remedy(report)
        return

    if not report["macos"]:
        print("\n  Full-disk access is a macOS mechanism; %s does not have it, "
              "so there is nothing to grant here." % report["platform"])

    readable = [f for f in report["roots"] if f["verdict"] == OK]
    # The sentence this command is for. It used to be printed whenever
    # nothing was BLIND, which meant a run whose only root was `missing`
    # got a health certificate - in the command whose whole docstring is
    # about never being quietly wrong.
    if readable and len(readable) == len(report["roots"]):
        print("\n  Every root returned entries, so this interpreter can read "
              "what it was pointed at.")
    elif readable:
        print("\n  %d of %d root(s) returned entries. The other %d did not, "
              "so this run cannot say the interpreter can read everything it "
              "was pointed at - only these %d."
              % (len(readable), len(report["roots"]),
                 len(report["roots"]) - len(readable), len(readable)))
    else:
        print("\n  No root returned an entry, so this run says nothing about "
              "whether this interpreter can read what it was pointed at. "
              "Point murscope at a directory that has something in it and "
              "run doctor again.")


def _blind_remedy(report):
    """The stop, and the exact binary to authorise."""
    print("\n  STOPPED. %d root(s) exist and returned nothing:"
          % len(report["blind"]))
    for finding in report["blind"]:
        print("    %s" % finding["root"])
    print("""
  On macOS that is what a missing permission looks like: no error, no
  entries. It is indistinguishable from having no projects, so murscope
  will not render a board from it - an empty board here would be a lie
  with a timestamp on it.

  Grant Full Disk Access to this exact binary:

      %s

  System Settings -> Privacy & Security -> Full Disk Access -> +
  Press Cmd+Shift+G in the file picker and paste the path above. Then
  run murscope doctor again.

  If the directory really is empty, point murscope somewhere else - the
  check is on the directory, not on you.""" % report["interpreter"])
