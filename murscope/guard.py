"""The single write path of the package (Rule 5).

Three boundaries (DP4): the code lives in site-packages and is read-only,
the user's configuration and the generated board live together under
MURSCOPE_HOME, and a monitored project is neither. This module is what
makes the third fact structural rather than promised: every byte the
package writes goes through guard_write_path(), which resolves its
target and refuses anything that does not land inside MURSCOPE_HOME. A
monitored project can therefore never be a write target, because it is
not under that root.

The guard performs the write itself. That is deliberate - if it only
validated and returned, a write-mode open() would still have to exist
somewhere else, and Rule 5's check would have to trust it. One function
writes; everything else asks this one.

Rule 5's check earns the exemption by content, not by name: the body has
to mention the root it defends and it has to raise. A guard that does
neither is a writer wearing a guard's name.

**M4 adds a second writer to this module, and that sentence is worth
saying out loud rather than discovering in a diff.** A scheduler reads
its job description from a directory it owns - `~/Library/LaunchAgents`
for launchd, `~/.config/systemd/user` for systemd - so a timer cannot be
installed without one write outside MURSCOPE_HOME. The reply is not an
exception: `guard_schedule_write()` holds a table of the exact paths it
will ever accept, computed from literals in this module, and refuses
anything else by equality. It takes no say in the matter from its
caller. The distinction that matters is the one DP126 states - **the
permission is for a path, not for a command** - and the difference
between the two is that a guard which trusts its caller has to be
audited at every call site, while this one can be read here, once.

The guard also prints the target before it writes it, and Rule 5's check
measures that by line number from the parse tree rather than by reading
the source for a `print`. A path named after the fact is a log line; a
path named before the fact is the user's last chance to say no.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

HOME_ENV = "MURSCOPE_HOME"
DEFAULT_HOME = "~/.murscope"

# The complete set of paths this package may write outside MURSCOPE_HOME,
# by platform, relative to the user's own home directory (DP126).
#
# A scheduler will not read a job description out of MURSCOPE_HOME. launchd
# reads ~/Library/LaunchAgents and systemd reads ~/.config/systemd/user, and
# no amount of preference about red line one changes where those two
# programs look. So `murscope timer install` is the first deliberate write
# outside the home in this product's life, and the shape of the permission
# is the whole of the ruling: **a path, on an explicit command, printed
# before it is written - never a command.**
#
# These are literals, and the table is exhaustive per platform. A guard
# that took the target from its caller would be a guard that trusts
# whoever is calling it, which is the shape Rule 17 was written against:
# `root / rel` on an absolute `rel` is `rel`, and every containment test
# that starts from a caller-supplied string has the same hole in it. This
# one never asks. It computes the paths it will accept and compares the
# request against them by equality - not by prefix, because a prefix test
# on ~/Library/LaunchAgents licenses every job on the machine.
#
# **Two jobs since M4's second stage, and the second one is the reason this
# table is now keyed by job rather than flat.** DP124 says the collecting
# job has no send path reachable from its entry point, and DP125 says an
# alert may leave the machine - so an alert cannot be something the
# collecting job does, and it needs a scheduled entry point of its own
# (`murscope-alert`, constrained by Rule 27 the way `murscope-timer` is by
# Rule 26). Two entry points that run unattended are two job descriptions
# on disk, and the permitted set is the union of both. It is still computed
# with no parameter and still compared by equality; what changed is how
# many literals are in it, not who decides.
SCHEDULE_JOBS = {
    "darwin": (
        ("collect", ("Library/LaunchAgents/com.murscope.core.timer.plist",)),
        ("alert", ("Library/LaunchAgents/com.murscope.core.alert.plist",)),
    ),
    "linux": (
        ("collect", (".config/systemd/user/murscope-core.service",
                     ".config/systemd/user/murscope-core.timer")),
        ("alert", (".config/systemd/user/murscope-core-alert.service",
                   ".config/systemd/user/murscope-core-alert.timer")),
    ),
}

# The flat per-platform view, derived rather than written twice. Everything
# that asks "what may this package write outside MURSCOPE_HOME" asks this;
# only the module that builds job descriptions cares which job a path
# belongs to.
SCHEDULE_FILES = {
    platform: tuple(rel for _job, rels in jobs for rel in rels)
    for platform, jobs in SCHEDULE_JOBS.items()
}


def murscope_home():
    """Where configuration and artifacts live (DP4).

    The environment variable when it is set and non-empty, otherwise
    ~/.murscope. Resolved, so a symlinked home is compared as the place
    it actually points at rather than as the name it was typed with.
    """
    raw = os.environ.get(HOME_ENV) or ""
    return Path(os.path.expanduser(raw.strip() or DEFAULT_HOME)).resolve()


def inside_home(path):
    """True when this path resolves inside MURSCOPE_HOME.

    Symlinks are followed before the comparison. A symlink planted in the
    board directory pointing at a monitored project resolves to the
    project, not to the board, and is refused on that resolved answer.
    """
    home = murscope_home()
    try:
        Path(os.path.expanduser(str(path))).resolve().relative_to(home)
    except ValueError:
        return False
    return True


def inside_root(root, path):
    """Does `path` resolve inside `root`? The third promise, as a function.

    `inside_home()` above is the write boundary; this is the read boundary,
    and they are deliberately the same shape. Symlinks are followed before
    the comparison, because a symlink is the obvious way past a string
    test: `ledgers: ["notes.md"]` where `notes.md` points at `~/.ssh/config`
    is a relative path that never leaves the project on paper.

    It lives here rather than in the module that first needed it because
    more than one reader needs it - a locale name and a marker pack name
    both arrive from the user's configuration and both get appended to a
    directory - and a containment test copied twice is a containment test
    that will differ once.
    """
    try:
        resolved = Path(os.path.expanduser(str(path))).resolve()
        base = Path(os.path.expanduser(str(root))).resolve()
    except OSError:
        return False
    try:
        resolved.relative_to(base)
    except ValueError:
        return False
    return True


def guard_write_path(path, text, mode=None):
    """Write `text` to `path`, or raise. The only writer in the package.

    Refuses any target that resolves outside MURSCOPE_HOME, then creates
    the parent directories and performs the write. Creating the parents
    is safe here and nowhere else: the target has already been proven to
    sit under the one root this tool owns.

    `mode` arrives with the key store at M3 (DP18). A key is a 0600 file
    under MURSCOPE_HOME, and the mode is applied **here** rather than by
    the caller for the reason this module exists at all: `os.chmod` is a
    write, Rule 5 refuses one outside this function, and a key store that
    had to be granted its own exemption would be a second writer with a
    written excuse. The file is *created* with the mode rather than
    created world-readable and narrowed afterwards - the narrowing still
    happens, because `O_CREAT` leaves an existing file's mode alone, but
    a new key never exists at 0644 for even one syscall. The containing
    directory is narrowed too, unless it is MURSCOPE_HOME itself: a 0600
    file inside a 0755 directory is still a 0600 file, but a directory
    listing that tells a reader which providers you hold a key for is
    method they did not ask to publish.
    """
    home = murscope_home()
    target = Path(os.path.expanduser(str(path))).resolve()
    try:
        target.relative_to(home)
    except ValueError:
        raise RuntimeError(
            "red line: refusing to write outside MURSCOPE_HOME.\n"
            "  target: %s\n"
            "  MURSCOPE_HOME: %s\n"
            "murscope writes nothing into the projects it reads; if this "
            "path looks like it should be allowed, the home is set wrong, "
            "not the guard." % (target, home))
    target.parent.mkdir(parents=True, exist_ok=True)
    if mode is None:
        with open(target, "w", encoding="utf-8") as handle:
            handle.write(text)
        return target
    descriptor = os.open(str(target), os.O_WRONLY | os.O_CREAT | os.O_TRUNC,
                         mode)
    try:
        os.write(descriptor, text.encode("utf-8"))
    finally:
        os.close(descriptor)
    os.chmod(str(target), mode)
    if target.parent != home:
        os.chmod(str(target.parent), 0o700)
    return target


def permitted_schedule_paths():
    """Every path outside MURSCOPE_HOME this package may ever write.

    Empty on a platform this product has no timer for, which is the
    correct answer rather than a gap: an empty table means every target
    is refused, so a platform nobody has written a timer for cannot have
    one installed by accident.

    Computed from SCHEDULE_FILES and the user's own home directory, with
    no parameter, because a permitted set that any caller can influence
    is not a permitted set. Resolved, so a symlinked home is compared as
    the place it points at - the same reason inside_home() resolves.
    """
    home = Path(os.path.expanduser("~")).resolve()
    return tuple(sorted(
        (home / relative).resolve()
        for relative in SCHEDULE_FILES.get(sys.platform, ())))


def _refuse_schedule_path(target, verb):
    permitted = permitted_schedule_paths()
    listing = "\n".join("    %s" % path for path in permitted) \
        or "    (none: this platform has no timer)"
    return RuntimeError(
        "red line: refusing to %s a path outside MURSCOPE_HOME that is not "
        "one of the scheduling files.\n"
        "  target: %s\n"
        "  the complete permitted set on %s:\n%s\n"
        "murscope writes outside its own home for exactly one purpose - the "
        "timer's job description, which the scheduler will not read from "
        "anywhere else. The permission is for those paths, not for whoever "
        "is calling (DP126)." % (verb, target, sys.platform, listing))


def guard_schedule_write(path, text):
    """Write one scheduling file, or raise. The second writer, and the last.

    The target is compared against permitted_schedule_paths() by equality.
    Not by prefix: a prefix test on ~/Library/LaunchAgents would license
    every launch agent on the machine, which is a permission for a
    directory dressed up as a permission for a path.

    The parent directory is created, and that is a write outside the home
    too - `~/.config/systemd/user` does not exist on a machine that has
    never had a user unit. It is the parent of a path already proven to be
    in the table, so it is the same permission rather than a wider one.

    The announcement comes first, and this is the reason the print sits
    here rather than in the command that calls it: a caller can be written
    that forgets, and then the guard's promise depends on every call site.
    """
    permitted = permitted_schedule_paths()
    target = Path(os.path.expanduser(str(path))).resolve()
    if target not in permitted:
        raise _refuse_schedule_path(target, "write")
    print("  writing outside MURSCOPE_HOME, on your explicit command: %s"
          % target)
    target.parent.mkdir(parents=True, exist_ok=True)
    with open(target, "w", encoding="utf-8") as handle:
        handle.write(text)
    return target


def guard_schedule_remove(path):
    """Remove one scheduling file, or raise. Returns None if it was absent.

    The same table, asked the same way. Uninstall has to be able to delete
    what install created or "uninstalling leaves nothing behind" is a
    sentence rather than a property, and a delete that took its target
    from the caller would be a far worse hole than the write - a write
    outside the home creates a file, and a delete outside the home
    destroys one.
    """
    permitted = permitted_schedule_paths()
    target = Path(os.path.expanduser(str(path))).resolve()
    if target not in permitted:
        raise _refuse_schedule_path(target, "remove")
    if not target.exists():
        return None
    print("  removing: %s" % target)
    os.remove(str(target))
    return target
