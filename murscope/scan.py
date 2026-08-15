"""The cold-start scan: authorise a directory, get a roster (report 7).

The success condition is one sentence. The first thing a user sees must
not be an empty board waiting to be filled in - it must be a cross
section of everything they have, where not one cell was typed by them.

Four things shape this module.

**It walks directories nobody has vetted.** That is what makes it
different from the collector, which is handed a roster of paths the user
named. So it prunes on the sealed table *before* descending, never
after: a filter applied afterwards has already entered `node_modules`.
Rule 6 refuses `glob`/`rglob`/`iterdir` on a caller-supplied path for
exactly this reason, and the refusal is right - `os.walk` with
`dirnames[:] = ...` is the only shape here.

**A checkout is not a project (DP57).** Fifteen agent worktrees were
found under one workspace on this machine and seven of them resolved to
`declared`, each reading its parent project's ledger - so the board
would have shown the same blocker four times, once per checkout. They
are excluded two ways: by path, because `.claude/worktrees/` is where
they live, and by nature, because a linked worktree's `.git` is a file
pointing into another repository. The second catches the ones that do
not live where we expect.

**Proposing is not deciding.** Tier one is selected by default and
everything else is collapsed, because the accuracy of that first screen
decides whether anyone trusts the rest - better to make
someone expand a list than to make them clear sixty checkboxes. The cap
is twenty and **the collapsed count is always stated**: silent
truncation reads as "this tool can only see twenty projects", which is a
worse lie than showing too many. **The cap is also stated as the cap.**
Counting the overflow was never enough on its own: the overflow used to
have its tier rewritten to `tier2`, so a repository committed to minutes
before the scan was reported as older or non-git and the word "cap"
appeared nowhere in `init`'s output. A number the user cannot attribute
to the right cause is not the disclosure this paragraph promises.

**Running out of time is not failing.** The budget is sixty seconds.
What was scanned goes on the board; what was not is marked `unscanned`
and counted, never dropped. Ctrl-C keeps what is already in
hand, for the same reason.
"""
from __future__ import annotations

import os
import subprocess
import time
from pathlib import Path

from . import fingerprints

# Rule 5, half two, declared here rather than imported from collect.py.
# The check resolves the environment in the calling module's own scope,
# and that is the point of it: an invariant vouched for by a constant in
# another file is an invariant a reader has to go and verify elsewhere.
# One line of duplication buys a git call that proves itself where it
# stands (DP31).
GIT_ENV = dict(os.environ, GIT_OPTIONAL_LOCKS="0")

# The design authority's cut points.
TIER1_RECENT_DAYS = 90
TIER3_RECENT_DAYS = 30
PROPOSAL_CAP = 20

# The design authority's budget. The per-repository budget lives in
# collect.Budget; this is the whole-scan allowance.
TOTAL_BUDGET_SECONDS = 60
# How deep below an authorised root a project may hide. Deep enough for
# `~/code/<language>/<project>`, shallow enough that a misdirected scan
# at `/` gives up rather than reading a disk.
MAX_DEPTH = 4

# DP57, by path. Directory paths rather than bare names: sealing the name
# `worktrees` would seal every directory anybody ever called that, and
# this rule is about one specific convention.
SEALED_SUBPATHS = (
    os.path.join(".claude", "worktrees"),
)

TIER_SELECTED = "tier1"
TIER_OLDER = "tier2"
TIER_NON_GIT = "tier3"


class Candidate(object):
    """One directory the scan is willing to call a project."""

    def __init__(self, path, tier, last_commit_days=None, mtime_days=None):
        self.path = path
        self.tier = tier
        self.last_commit_days = last_commit_days
        self.mtime_days = mtime_days
        self.tools = []
        self.ledgers = []
        self.offers = []
        self.unscanned = False
        # Set when this is a tier-one repository pushed off the first
        # screen by PROPOSAL_CAP. It is a *selection* fact, not an age
        # fact: overwriting `tier` here is what made `init` report three
        # repositories committed to seconds earlier as "older or non-git".
        self.capped = False

    @property
    def name(self):
        return self.path.name

    @property
    def identifier(self):
        """A roster id: the directory name, reduced to the safe alphabet."""
        safe = "".join(c if (c.isalnum() or c in "-_.") else "-"
                       for c in self.path.name)
        return safe.strip("-") or "project"

    def entry(self):
        """The roster row, marked as something the scan produced."""
        row = {"id": self.identifier, "name": self.name, "root": str(self.path)}
        if self.ledgers:
            row["ledgers"] = list(self.ledgers)
        return row

    def describe(self):
        return {
            "id": self.identifier, "name": self.name, "root": str(self.path),
            "tier": self.tier, "tools": list(self.tools),
            "ledgers": list(self.ledgers), "offers": list(self.offers),
            "last_commit_days": self.last_commit_days,
            "mtime_days": self.mtime_days, "unscanned": self.unscanned,
            "capped": self.capped,
        }


class Scan(object):
    """What one scan saw, including everything it decided not to show."""

    def __init__(self, roots):
        self.roots = list(roots)
        self.candidates = []
        self.cap = PROPOSAL_CAP
        self.directories_seen = 0
        self.collapsed = 0
        self.capped = 0
        self.excluded_worktrees = 0
        self.excluded_bare = 0
        self.containers = 0
        self.seconds = 0.0
        self.stopped = ""
        self.problems = []

    @property
    def selected(self):
        """Tier one, minus whatever the cap pushed off the first screen.

        The cap used to be applied by rewriting `tier` to TIER_OLDER, and
        the overflow then described itself as old everywhere it was
        printed. Selection is filtered here instead, so a capped
        repository keeps the tier its commit date earned.
        """
        return [c for c in self.candidates
                if c.tier == TIER_SELECTED and not c.capped]

    def summary(self):
        return {
            "roots": [str(r) for r in self.roots],
            "directories_seen": self.directories_seen,
            "candidates": len(self.candidates),
            "selected": len(self.selected),
            "collapsed": self.collapsed,
            "capped": self.capped,
            "cap": self.cap,
            "excluded_worktrees": self.excluded_worktrees,
            "excluded_bare": self.excluded_bare,
            "containers": self.containers,
            "seconds": round(self.seconds, 1),
            "stopped": self.stopped,
            "projects": [c.describe() for c in self.candidates],
            "problems": list(self.problems),
        }


def distinct_roots(roots):
    """The roots that are actually different directories.

    Measured on a synthetic home while checking something else. macOS
    filesystems are case-insensitive by default and `CONVENTIONAL_ROOTS`
    lists both `Projects` and `projects`, so a home with either one hands
    this module two paths naming one directory. Both were walked, and
    every project under that directory was proposed **twice** - two rows
    with the same id, the same name and the same root, on the first board
    a stranger ever sees, with every tile count one too high and the
    closing "N project(s) on the board" one too many. `init ~/code ~/Code`
    reaches the same place by hand.

    Compared by `(st_dev, st_ino)` rather than by string, because that is
    the comparison the filesystem itself makes: it settles the case
    question without guessing at the platform, and it catches a root that
    is a symlink to another root as well.

    A root that cannot be stat'ed keeps its path as the key rather than
    being dropped. It is about to be reported as missing, and that is the
    caller's job to say.
    """
    seen = set()
    kept = []
    for root in roots:
        path = Path(os.path.expanduser(str(root)))
        try:
            info = path.stat()
            key = (info.st_dev, info.st_ino)
        except OSError:
            key = str(path)
        if key in seen:
            continue
        seen.add(key)
        kept.append(root)
    return kept


def is_worktree(path):
    """A linked worktree or a submodule: `.git` is a file, not a directory.

    DP57's second half. A worktree can be moved anywhere, so recognising
    it by nature rather than by location is what makes the exclusion hold
    for a user whose conventions are not this machine's. The `.git` file
    of a linked worktree points into its parent's `.git/worktrees/`.
    """
    marker = path / ".git"
    if not marker.is_file():
        return False
    try:
        head = marker.read_text(encoding="utf-8", errors="replace")[:512]
    except OSError:
        return False
    return "gitdir:" in head and "worktrees" in head


def is_bare_repo(path):
    """A repository with no working tree: `HEAD`, `objects/`, `refs/`.

    Measured, not imagined: a bare mirror sitting in a scanned directory
    put twenty rows on the proposal - `objects/`, `refs/heads/`, and one
    per two-character object shard - because its name does not begin with
    a dot, it is in nobody's exclusion list, and it contains no `.git`
    child to mark it as a repository, so the walk went straight in.

    It is excluded for the same reason a worktree is (DP57): a bare
    repository is a copy of a project rather than a project. It has no
    working tree at all, so the four signals that carry this product -
    uncommitted, unpushed, WIP, stash - have nothing to describe there.
    """
    return ((path / "HEAD").is_file()
            and (path / "objects").is_dir()
            and (path / "refs").is_dir()
            and not (path / ".git").exists())


def _sealed_subpath(dirpath, name):
    joined = os.path.join(dirpath, name)
    return any(joined.endswith(os.sep + tail) or joined == tail
               for tail in SEALED_SUBPATHS)


def last_commit_days(path, seconds):
    """Days since the last commit, or None when git cannot say.

    Read-only subcommand plus GIT_OPTIONAL_LOCKS=0, like every other git
    call in this package (Rule 5, DP31). A scan touches far more
    repositories than a collection run does, which makes the pairing
    matter more here rather than less.
    """
    try:
        proc = subprocess.run(
            ["git", "-C", str(path), "log", "-1", "--format=%ct"],
            capture_output=True, text=True, timeout=seconds, env=GIT_ENV)
    except (subprocess.TimeoutExpired, OSError):
        return None
    if proc.returncode != 0:
        return None
    raw = proc.stdout.strip()
    if not raw:
        return None
    try:
        return (time.time() - int(raw)) / 86400.0
    except ValueError:
        return None


# How far back to look for authorship. Twenty is enough to find the
# dominant name and short enough to stay inside the per-repository budget.
AUTHOR_COMMITS = 20


def author_names(path, seconds):
    """Author names on this project's recent commits, most frequent first.

    DP63. The owner's aliases are seeded from authorship rather than from
    git configuration, and the reason is worth keeping next to the call:
    `git config --get` would need `config` added to Rule 5's read-only
    allowlist, and `git config x y` writes - so that route widens a red
    line. Reading `~/.gitconfig` reads outside the listed projects, which
    is the promise Rule 17 exists to keep. `log` is already allowlisted
    and already called for every repository here, and the name written on
    these commits is better evidence anyway: it is the name most likely to
    appear in these projects' own ledgers.
    """
    try:
        proc = subprocess.run(
            ["git", "-C", str(path), "log", "-%d" % AUTHOR_COMMITS,
             "--format=%an"],
            capture_output=True, text=True, timeout=seconds, env=GIT_ENV)
    except (subprocess.TimeoutExpired, OSError):
        return []
    if proc.returncode != 0:
        return []
    counts = {}
    for line in proc.stdout.splitlines():
        name = line.strip()
        if name:
            counts[name] = counts.get(name, 0) + 1
    return [name for name, _ in sorted(counts.items(),
                                       key=lambda kv: (-kv[1], kv[0]))]


def alias_candidates(candidates, seconds=5.0):
    """Names to offer as owner aliases, ranked by how many projects use them.

    Ranked by *projects* rather than by commits on purpose. A single busy
    repository shared with colleagues would otherwise hand the top slot to
    whoever commits most there; the name that appears across somebody's
    own portfolio is the one that is theirs.
    """
    per_project = {}
    scanned = 0
    for candidate in candidates:
        names = author_names(candidate.path, seconds)
        if not names:
            continue
        scanned += 1
        # The dominant author of each project, not every contributor.
        per_project[candidate.identifier] = names[0]
    counts = {}
    for name in per_project.values():
        counts[name] = counts.get(name, 0) + 1
    if not counts:
        return [], 0
    ranked = sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))
    # One name, and only when it is unambiguously ahead.
    #
    # The first version used `hits >= max(1, scanned // 2)`, and measured:
    # with fewer than four projects scanned - the first run and every
    # `--add` - the second-place author was always seeded too. A colleague
    # then counted as the owner, and `Waiting on <colleague> to sign off`
    # was reported as work waiting on the user. Seeding a wrong name is
    # worse than seeding none: it replaces an honest "I do not know" with a
    # confident wrong answer.
    if len(ranked) > 1 and ranked[0][1] == ranked[1][1]:
        return [], scanned
    return [ranked[0][0]], scanned


def newest_mtime_days(path, sealed, cap_files):
    """Signal 10 for a directory that is not a repository.

    Bounded on purpose: this runs on every non-git directory under an
    authorised root, and the answer only has to be good enough to sort
    "touched this month" from "untouched since 2019".
    """
    newest = None
    seen = 0
    root_str = str(path)
    for dirpath, dirnames, filenames in os.walk(root_str):
        dirnames[:] = sorted(
            name for name in dirnames
            if name not in sealed and not name.startswith("."))
        for name in filenames:
            if name.startswith("."):
                continue
            seen += 1
            if seen > cap_files:
                break
            try:
                stamp = os.stat(os.path.join(dirpath, name)).st_mtime
            except OSError:
                continue
            if newest is None or stamp > newest:
                newest = stamp
        if seen > cap_files:
            break
    return None if newest is None else (time.time() - newest) / 86400.0


def discover(roots, sealed, budget_seconds=TOTAL_BUDGET_SECONDS,
             max_depth=MAX_DEPTH, progress=None):
    """Walk the authorised roots and propose projects in four tiers.

    Returns a `Scan`. Ctrl-C is caught and keeps what was found, because
    losing a fifty-second scan to a keystroke teaches people not to try
    the tool again.
    """
    # Deduplicated before anything is recorded, so `Scan.roots` and every
    # count derived from this walk describe directories rather than paths.
    roots = distinct_roots(roots)
    scan = Scan(roots)
    started = time.monotonic()
    git_dirs = []
    plain_dirs = []

    def out_of_time():
        return (time.monotonic() - started) >= budget_seconds

    try:
        for root in roots:
            root = Path(os.path.expanduser(str(root))).resolve()
            if not root.is_dir():
                scan.problems.append(
                    "%s is not a directory; nothing was scanned there." % root)
                continue
            root_str = str(root)
            for dirpath, dirnames, filenames in os.walk(root_str):
                dirnames[:] = sorted(
                    name for name in dirnames
                    if name not in sealed
                    and not name.startswith(".")
                    and not _sealed_subpath(dirpath, name))
                scan.directories_seen += 1
                if out_of_time():
                    scan.stopped = "budget"
                    dirnames[:] = []
                    break
                here = Path(dirpath)
                depth = dirpath[len(root_str):].count(os.sep)
                if depth >= max_depth:
                    dirnames[:] = []
                if is_bare_repo(here):
                    scan.excluded_bare += 1
                    dirnames[:] = []
                    continue
                if (here / ".git").exists():
                    # A repository is a leaf. Whatever is inside it
                    # belongs to it, and descending would propose a
                    # project's own subdirectories as projects.
                    dirnames[:] = []
                    if is_worktree(here):
                        scan.excluded_worktrees += 1
                        continue
                    git_dirs.append(here)
                elif depth >= 1:
                    plain_dirs.append(here)
            if scan.stopped:
                break
    except KeyboardInterrupt:
        scan.stopped = "interrupted"

    scan.seconds = time.monotonic() - started
    _classify(scan, git_dirs, plain_dirs, sealed, started, budget_seconds,
              progress)
    scan.seconds = time.monotonic() - started
    return scan


def _project_shaped(plain_dirs, git_dirs, scan):
    """Which non-git directories are projects rather than folders of them.

    Two ways a directory earns a row, and both are about not saying the
    same thing twice on the first screen a user ever sees:

    * **it holds no repository.** `~/code` with four repositories under it
      is a container, and proposing it alongside its own contents offers
      the user their workspace as a fifth project;
    * **it is not inside another proposal.** A writing project's `draft/`
      subdirectory is part of that project, not a peer of it.

    Repositories do not need this: a repository is already a leaf, since
    the walk stops descending the moment it finds one.
    """
    repos = set(git_dirs)
    holds_repo = set()
    for repo in repos:
        holds_repo.update(repo.parents)

    accepted = []
    for path in sorted(plain_dirs, key=lambda p: (len(p.parts), str(p))):
        if path in holds_repo:
            scan.containers += 1
            continue
        if any(parent in accepted for parent in path.parents):
            continue
        accepted.append(path)
    return accepted


def _classify(scan, git_dirs, plain_dirs, sealed, started, budget_seconds,
              progress):
    """Sort what the walk found into the design authority's tiers."""
    def left():
        return budget_seconds - (time.monotonic() - started)

    found = []
    # Classification is the slow half - a git call and an mtime walk per
    # candidate - so it is where a user actually reaches for Ctrl-C, and
    # it has to survive that. An earlier version guarded only the
    # discovery walk and lost the whole scan to an interrupt raised here;
    # the design authority asks for the opposite, and the reason is not
    # politeness. Somebody who loses a fifty-second scan to one keystroke
    # does not run the tool a second time.
    try:
        for path in sorted(git_dirs):
            if left() <= 0:
                candidate = Candidate(path, TIER_OLDER)
                candidate.unscanned = True
                scan.stopped = scan.stopped or "budget"
                found.append(candidate)
                continue
            days = last_commit_days(path, min(15.0, max(1.0, left())))
            tier = (TIER_SELECTED
                    if days is not None and days <= TIER1_RECENT_DAYS
                    else TIER_OLDER)
            found.append(Candidate(path, tier, last_commit_days=days))
            if progress is not None:
                progress(path.name, tier)

        for path in _project_shaped(plain_dirs, git_dirs, scan):
            if left() <= 0:
                scan.stopped = scan.stopped or "budget"
                break
            days = newest_mtime_days(path, sealed, cap_files=2000)
            if days is None or days > TIER3_RECENT_DAYS:
                continue
            found.append(Candidate(path, TIER_NON_GIT, mtime_days=days))
            if progress is not None:
                progress(path.name, TIER_NON_GIT)
    except KeyboardInterrupt:
        scan.stopped = "interrupted"

    for candidate in found:
        if candidate.unscanned:
            continue
        try:
            candidate.tools = fingerprints.tools(candidate.path)
            candidate.ledgers = (
                fingerprints.fixed_ledgers(candidate.path)
                + fingerprints.wildcard_ledgers(candidate.path, sealed))
            candidate.offers = fingerprints.offered(candidate.path)
        except KeyboardInterrupt:
            scan.stopped = "interrupted"
            candidate.unscanned = True
            break

    # Tier order first, then most recently touched inside each tier. The
    # first screen is the one that decides whether anyone believes the
    # rest of the board, so the rows most likely to matter go on top.
    def sort_key(candidate):
        tier_rank = {TIER_SELECTED: 0, TIER_OLDER: 1, TIER_NON_GIT: 2}
        age = candidate.last_commit_days
        if age is None:
            age = candidate.mtime_days
        return (tier_rank.get(candidate.tier, 3),
                age if age is not None else 1e9, candidate.name)

    found.sort(key=sort_key)
    first = [c for c in found if c.tier == TIER_SELECTED]
    rest = [c for c in found if c.tier != TIER_SELECTED]

    # The cap limits what is *selected*, never what is *reported*. An
    # earlier version of this function sliced the overflow off the list
    # and counted it only in a separate field, which meant twenty-five
    # recent repositories were shown as twenty and five went nowhere -
    # the exact silent truncation the design authority forbids,
    # reintroduced by the code meant to implement it. The overflow now
    # joins the collapsed group: still off the first screen, still in
    # the list, still counted.
    if len(first) > PROPOSAL_CAP:
        scan.capped = len(first) - PROPOSAL_CAP
        overflow = first[PROPOSAL_CAP:]
        # Flagged, not retiered. Rewriting `tier` to TIER_OLDER here is
        # how three repositories with commits minutes old were reported as
        # "older or non-git" by `init` and printed `tier2` - this module's
        # own name for ">90 days" - on the expanded list. The cap is a
        # decision about the first screen; it is not evidence about age,
        # and it may not overwrite the evidence there is.
        for candidate in overflow:
            candidate.capped = True
        first = first[:PROPOSAL_CAP]
        rest = overflow + rest

    scan.collapsed = len(rest)
    scan.candidates = first + rest
    return scan


def roster_document(scan):
    """The initial roster, tier one only, marked as scanned."""
    return {"projects": [c.entry() for c in scan.selected]}
