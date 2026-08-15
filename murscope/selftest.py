"""`murscope selftest`: prove the promises on the user's own machine.

Four sections, and all of them exist for the user rather than for the
maintainer.

**The parser still reads the shipped shapes.** Every synthetic case runs
against every pack this build carries. This is the invariant a release
must not break, and it is checked against all packs rather than the
user's own so that an English-only configuration is not reported as a
defect in the Chinese cases.

**Your vocabulary does not fire on prose.** The refusal cases run
against the user's own resolved three layers. The vocabulary is editable
by design and that is also a loaded gun: a word added to
`extra_markers` that happens to open ordinary sentences will report a
blocker on a project that is fine, and after the second false positive
nobody believes the column again (DP21). Somebody who adds a bad marker
learns it here in the same minute, rather than from a wrong board a week
later.

**A count you can check against the row it counts.** DP73 settled the
summary line and the board tiles on the literal reading - a project
holding uncommitted files is counted whether or not that is what its
state column is about. A number nobody can reconcile with the rows under
it is the kind of number that gets checked once and disbelieved after
that, so every in-hand fact that matched is asserted to appear on its own
row, as the headline or as its sub-text, on both surfaces. Asserted in
terms of rule keys rather than English, so it holds in every locale.

**Offline.** Rule 11 proves that no networking symbol is imported. That
proof does not reach "and no code path calls one anyway". A
`sys.addaudithook` that raises on socket events is installed **at the top
of `main()`**, and a real collection **and a real scan** run under it -
`init` reaches further than `run` does, walking directories nobody listed
and shelling out to git in each repository it meets, so it is the command
whose silence is worth proving. A syscall trace would be stronger and
needs root on macOS, would not reproduce in CI, and could never become a
permanent test; this runs everywhere the tool runs, on the 3.9 floor.

**Nothing installed here can open a socket.** The offline step above
proves that the *code paths this run walked* reached no network. That is a
different claim from "nothing on this disk could", and the difference is
not academic: this command never loads a provider and never calls one -
`providers.load()` and `contribute()` live in `cli.run` - so step 4 would
stay true word for word on an install whose provider sends every night.
Step 4 is therefore scoped to what it walked, and the closing line says so
rather than generalising to "everything this run did".

The claim that has no shelf life is this one, and M3 is what makes the
distinction matter: network capability now ships as a separate
distribution (DP88), so promise two is a fact about which files `pip` put
on the user's machine rather than about what a run happened to do. This
step reads
every module under `murscope/providers/` - reads, never imports - and
asserts that everything the base package ships is incapable of opening a
socket and that anything else present is owned by a distribution the user
installed on purpose. It runs here rather than in the gate because the
question is about the built artifact, and CI runs this command from a
built wheel in a fresh environment outside every checkout. A file dropped
into `site-packages` by hand belongs to no distribution and turns this
step red, which is what makes "absent" a measurement instead of a claim.

**Both runtime hooks go on together, before step 1.** The network hook
used to be installed inside step 4, while the closing line generalised its
silence to "the run". Steps 1-3 contain a full collection, a full render
and two explains, and every one of them was outside the window: an audit
planted a network call in `render.build_document` - which step 3 runs, and
which every `murscope run` runs - and the gate stayed green while still
printing that the run made no network attempt. That is the fourth time a
guard in this package measured a stretch narrower than its own sentence,
so the shape is fixed rather than the instance: `READS` and `NETWORK` are
installed on the first two lines of `main()`, one window covers every
step, and what the window still cannot cover - this package's own imports,
which finish before `main()` is entered - is said in the line rather than
left for a reader to discover.

The fixtures are synthetic. The reference implementation's cases are
quoted verbatim from the owner's real ledgers and are not copied here.
"""
from __future__ import annotations

import ast
import contextlib
import io
import json
import os
import re
import sys
import sysconfig
import tempfile
import traceback
import unicodedata
from pathlib import Path

from . import (alerts, boundary, collect, config, consent, doctor, explain,
               keys, ledger, markers, outbound, render, scan, state)
from .guard import (SCHEDULE_FILES, guard_schedule_remove,
                    guard_schedule_write, guard_write_path, inside_root,
                    murscope_home, permitted_schedule_paths)

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "ledger_cases.json"

# Audit events that mean the network was reached for. Compared as
# strings: naming them does not import anything (Rule 11).
NETWORK_EVENTS = (
    "socket.connect", "socket.getaddrinfo", "socket.gethostbyname",
    "socket.sendto", "socket.bind", "urllib.Request",
)


def load_cases():
    try:
        return json.loads(FIXTURES.read_text(encoding="utf-8")), []
    except (OSError, ValueError) as exc:
        return None, ["cannot read %s: %s" % (FIXTURES, exc)]


def check_shapes(vocabulary, cases):
    """Do the shipped shapes still parse? The parser's own invariant.

    Run against every pack this build carries, not against the user's
    resolved vocabulary. A Chinese declaration is a shape the parser has
    to keep reading correctly whether or not this particular user has
    the Chinese pack switched on; testing it against an English-only
    vocabulary would report the user's own configuration as a defect.
    """
    failures = []
    counts = {"declarations": 0, "refusals": 0, "sections": 0, "owner": 0}

    for case in cases.get("declarations", []):
        found = ledger.blocker_line(case["line"], vocabulary.markers)
        got = found[0] if found else None
        counts["declarations"] += 1
        if got != case["expect"]:
            failures.append(
                "a declaration was missed or mangled (%s)\n    line: %r\n"
                "    want: %r\n    got : %r"
                % (case.get("shape", "?"), case["line"], case["expect"], got))

    for case in cases.get("sections", []):
        got = ledger.section_first_item(case["lines"], case["start"])
        counts["sections"] += 1
        if got != case["expect"]:
            failures.append(
                "a section read wrong (%s)\n    want: %r\n    got : %r"
                % (case.get("why", "?"), case["expect"], got))

    aliases = markers.normalise(cases.get("aliases", []))
    for text in cases.get("owner_claims", []):
        counts["owner"] += 1
        if not ledger.waits_on_owner(text, vocabulary.owner_markers, aliases,
                                     vocabulary.markers):
            failures.append("should be read as naming the owner: %r" % text)
    for text in cases.get("not_owner_claims", []):
        counts["owner"] += 1
        if ledger.waits_on_owner(text, vocabulary.owner_markers, aliases,
                                     vocabulary.markers):
            failures.append(
                "must not claim the owner is the blocker: %r\n"
                "    a generic blocker is real and is still not your move" % text)

    # The refusal cases, against every shipped pack. Step 1's line has said
    # "the three refusals hold" since it was written, and this counter was
    # initialised to zero and never touched: nothing ran the refusals
    # against the full vocabulary anywhere. Step 2 runs them against the
    # *user's* resolved three layers, which is a different question - it
    # protects somebody who edited their own config, not the shipped packs.
    # Feeding a fixture of pure false positives left step 1 green.
    for case in cases.get("refusals", []):
        counts["refusals"] += 1
        found = ledger.blocker_line(case["line"], vocabulary.markers)
        if found is not None:
            failures.append(
                "a refused shape was read as a declaration (%s)\n"
                "    line          : %r\n"
                "    matched marker: %r"
                % (case.get("why", "prose"), case["line"], found[1]))

    return failures, counts


def check_your_vocabulary(vocabulary, cases):
    """Does *your* vocabulary fire on prose? The half that protects users.

    Only the refusal cases, and only against the resolved three layers.
    Adding "and" to extra_markers is a mistake nothing else in the tool
    will tell you about: the board will simply start reporting blockers
    on projects that are fine, and by the time that is noticeable the
    connection to the config edit is gone.
    """
    failures = []
    for case in cases.get("refusals", []):
        found = ledger.blocker_line(case["line"], vocabulary.markers)
        if found is not None:
            failures.append(
                "FALSE POSITIVE - this line is %s, not a declaration\n"
                "    line          : %r\n"
                "    matched marker: %r\n"
                "    reported as   : %r\n"
                "    switch it off : disable_markers = [%r]"
                % (case.get("why", "prose"), case["line"], found[1], found[0],
                   found[1]))
    return failures, len(cases.get("refusals", []))


CANARY_DIR = Path(__file__).resolve().parent / "fixtures" / "canary"
CANARY = "MURSCOPE-SENSITIVE-CANARY-MUST-NOT-BE-EMITTED"

# A repository, fabricated file by file. `git init` is not on Rule 5's
# read-only allowlist and will not be added for a test, so the layout is
# written directly: HEAD, a minimal config, and the two directories git
# insists on. `git status --porcelain` then really runs and really reports
# the untracked decoy file.
FABRICATED_REPO = (
    (".git/HEAD", "ref: refs/heads/main\n"),
    (".git/config", "[core]\n\trepositoryformatversion = 0\n\tbare = false\n"),
    (".git/refs/heads/.keep", ""),
    (".git/objects/info/.keep", ""),
    ("NOTES.md", "# Canary\n\nBLOCKED: %s\n\n- [ ] one\n- [ ] two\n" % CANARY),
    ("README.md", "# Canary\n\n%s\n" % CANARY),
)

# A second fabricated repository, carrying no decoy and marked ordinary.
# It is what keeps the outbound assertion from being satisfied by an empty
# payload: with only sensitive entries in the roster, "the decoy is not in
# the payload" would hold for a builder that produced no rows at all, and
# the withheld-count assertion below would be the only thing running.
ORDINARY_REPO = (
    (".git/HEAD", "ref: refs/heads/main\n"),
    (".git/config", "[core]\n\trepositoryformatversion = 0\n\tbare = false\n"),
    (".git/refs/heads/.keep", ""),
    (".git/objects/info/.keep", ""),
    ("NOTES.md", "# Ordinary\n\n- [ ] one\n"),
    ("README.md", "# Ordinary\n\nNothing withheld about this one.\n"),
)


class ReadRecorder(object):
    """Every path opened while this is installed, recorded not refused.

    DP69's instrument. Rule 7's static pass does not examine this module,
    on the stated grounds that the selftest builds a sensitive project
    under a throwaway home and reads the artifacts back - it is the
    verifier of the boundary, not a collector. That is a scope entry, and a
    scope entry is exactly the shape two audits warned about, so it does
    not get to rest on the argument: this measures it.

    Same move as DP65, one level down. Rather than prove the selftest
    cannot read outside its own sandbox, record what it opened and check.

    **The window, stated exactly, because two earlier versions were
    narrower than their own sentence.** The hook goes on at the top of
    `main()` and the assertion runs as step 10, after every step that
    opens a file, so the window is the whole run. It is not the last
    step and does not need to be: steps 11 and 12 are placed after it
    precisely because they open nothing, and each says so where it is
    called. The first version watched only from partway
    into step 3, and two
    injected reads under the user's home came back green - never in view
    rather than missed. The second closed the window at the end of step 3,
    which sounds complete and is not: step 3 collects *sensitive* entries,
    and the gate stops their readers, so a read planted in the tree walk
    was still green. Both times the guard measured a stretch of code where
    the thing it guards against does not happen.

    **The window now covers the whole run**, step 4 included. It did not
    at first, for a reason that sounded solid: `check_offline` collects the
    user's real roster, so it opens files inside their projects on purpose,
    and flagging those would fire for every user who has one. The
    consequence was that the one step which actually reads a project was
    the one step nobody measured - a read planted in the tree walk came
    back green, because for a *sensitive* entry step 3 never walks a tree.
    The window excluded exactly the code most worth watching.

    The answer was not a wider exemption but a named boundary that already
    exists: reads inside a **listed** project are permitted, because Rule
    17 permits them and has its own check. So the roots step 4 collects
    join the permitted set, and a read outside every sandbox and every
    listed project is a finding - which is the sentence this was always
    meant to enforce.

    It records rather than raising because the hook cannot be uninstalled:
    refusing here would break every later read in the process.
    """

    def __init__(self):
        self.paths = []
        self.installed = False

    def install(self):
        if not self.installed:
            sys.addaudithook(self._hook)
            self.installed = True

    def _hook(self, event, args):
        if event == "open" and args and isinstance(args[0], str):
            self.paths.append(args[0])

    def mark(self):
        return len(self.paths)

    def since(self, mark):
        return self.paths[mark:]


class NetworkWatch(object):
    """Every network event this run reached for, recorded *and* refused.

    The window is the same window `ReadRecorder` has and for the same
    reason: it opens on the first line of `main()` and never closes. It
    used to open inside step 4, which left a full collection, a full render
    and two explains outside it - so a network call planted in
    `render.build_document` was never in view, and the run still printed
    that it had made none.

    It records before it raises. The raise is what makes this a refusal
    rather than a log, and the record is what makes the verdict survive a
    caller that swallows exceptions: `cli.collect_records` catches
    everything per project so that one bad repository cannot end a round,
    which would otherwise turn a network attempt into a problem line on a
    green board.
    """

    def __init__(self):
        self.tripped = []
        self.installed = False

    def install(self):
        if not self.installed:
            sys.addaudithook(self._hook)
            self.installed = True

    def _hook(self, event, args):
        if event in NETWORK_EVENTS:
            self.tripped.append(event)
            raise RuntimeError("murscope selftest: network event %r during a "
                               "run that must not reach the network" % event)


READS = ReadRecorder()
NETWORK = NetworkWatch()

# Directories the operating system owns. Platform detection opens a version
# file under one of these and nobody keeps a project there.
OS_OWNED = ("/System", "/usr", "/Library", "/etc", "/proc", "/sys",
            "/private/etc", "/private/var/db")


class ReadWindow(object):
    """The window and the set of roots permitted inside it, in one object.

    **DP114, and the fourth appearance of one shape.** Three times a guard
    in this file measured a stretch of code narrower than the sentence it
    printed, and each fix widened the *window* - to the whole run, opened
    on the first line of `main()`. The fourth appearance is the mirror
    image and it lived in the code that fixed the third: step 7 asserted
    over `READS.since(0)`, the whole run, against a permitted set it
    assembled by hand out of the sandboxes; step 10 asserted over the same
    whole run against that set **plus** the project roots step 4 was asked
    to collect. Two sentences about the same window, disagreeing, twenty
    lines apart. So on any machine whose roster is not empty - which is
    every machine that has run `murscope init` - step 4 read a project on
    purpose and step 7 called it a stray. `selftest` was red for every
    user, and the gate never saw it because the gate ran the selftest
    against a throwaway home with no roster in it.

    The repair is not a third argument at the second call site. It is that
    **there is one window and one permitted set, and they are the same
    object's two halves**, so a step cannot state one without the other:

    * the window is `self._recorder.since(0)` - the whole run - and it is
      written down in exactly one place, inside `opened()`;
    * the permitted set is whatever has been handed to `permit()` by the
      time `strays()` is asked, and `permit()` is called at the moment a
      root is *acquired*, before the read it permits happens;
    * every assertion calls `strays()` with no arguments, so there is no
      parameter through which a caller could narrow either half.

    Narrowing the permitted set now means deleting a `permit()` call, and
    what goes red when somebody does is **one thing, not two: a `murscope
    selftest` run**, because the roots that call permitted are then read
    and unpermitted. Every `permit()` call site in this file was deleted in
    turn and the runs measured. The ones registering a sandbox this run
    built redden both of the gate's runs; the ones registering a root the
    roster named - `MURSCOPE_HOME` and the projects step 4 collects - are
    green on the empty roster and red only on the non-empty one, which is
    DP114 in one line and the reason the gate runs this command twice.

    **Rule 24 stays green through all of them, and that is its subject
    rather than a gap in it (DP122).** This docstring used to say the
    check was a second, independent red; it is not, and the claim was
    measured wrong. Rule 24's permit assertion is a *floor* - at least two
    call sites - so what it catches is an accumulator that has gone
    decorative, not the loss of any one root; deleting a single site moves
    its printed count down by one and it still exits 0. What it does hold
    is the shape this class is: one window, written in one place; one
    permitted set, read in one place; and no call site able to narrow
    either half. The guard against a *particular* root going unpermitted
    is the selftest run itself, which is what the sentence above says now.
    """

    def __init__(self, recorder):
        self._recorder = recorder
        self._permits = []

    def permit(self, path, why):
        """Register a root this run may read inside, and say why.

        Called where the root is acquired rather than where it is asserted
        over. A root that travels to the assertion as a return value can be
        picked up by one caller and missed by another, which is the whole
        of DP114.
        """
        if not path:
            return
        self._permits.append((Path(path), str(why)))

    def permits(self):
        return list(self._permits)

    def summary(self):
        """The permitted set counted by reason, for the line that reports it.

        Generated from the same list `strays()` reads, because a
        hand-written summary beside a computed assertion is how a sentence
        starts describing a set nobody is measuring.
        """
        order = []
        counts = {}
        for _path, why in self._permits:
            if why not in counts:
                order.append(why)
                counts[why] = 0
            counts[why] += 1
        return ", ".join("%d %s" % (counts[why], why) for why in order)

    def opened(self):
        """Every path this window covers. **The window is written here.**

        `since(0)` - from the first line of `main()` - appears in this one
        method and in no other place in this file, so there is no second
        expression of the window that could quietly be a shorter one. The
        three defects this class records all began as a second, narrower
        statement of a window that a docstring elsewhere described as whole.
        """
        return self._recorder.since(0)

    def counted(self):
        """How many reads the window holds, for the line that reports it."""
        return len(self.opened())

    def strays(self):
        """Every path opened in this window that is outside every permit.

        No arguments, deliberately. The window and the permitted set are
        both read off `self` here and nowhere else, so the two cannot be
        stated separately - and a step that wants a wider permission has to
        widen it for the whole run, in front of every other assertion.
        """
        return _stray_reads(self.opened(),
                            [path for path, _why in self._permits])


# The permitted set the steps register into. It outlives every sandbox on
# purpose: the final assertion runs after the steps have torn theirs down,
# and a path recorded inside a directory that no longer exists is still a
# path this run was allowed to open.
WINDOW = ReadWindow(READS)


def _permitted_read_roots():
    """The classes permitted for every run, whatever that run does.

    Three, each for a reason a reader can check, and none of them
    run-specific - what a *particular* run acquired goes through
    `ReadWindow.permit` instead, so that the roots and the window they are
    permitted inside cannot drift apart (DP114):

    * the installed package - its own fixtures, locales, marker packs and
      board template;
    * the interpreter's own directories - including the installation a
      virtual environment was created from, because `sys.prefix` is the
      venv and the stdlib zip lives beside the base installation's lib
      directory - since importing a module opens a file and the hook
      cannot tell that from anything else;
    * the directories the operating system owns, because platform detection
      opens a version file under one of them.

    Plus two narrowed permissions, both stated as one file rather than one
    tree, and both in `_stray_reads` where the narrowing can be written:

    * one file *directly* inside the system temporary directory:
      `tempfile` opens a randomly named probe there the first time it is
      used, which was the first thing this assertion caught. Deliberately
      not the whole temporary tree - permitting that was the first attempt,
      and the reverse verification then passed while reading a project
      planted under `/tmp`. The test was wrong and the permission was too
      wide, and one exposed the other;
    * `.pyc` files under `sys.pycache_prefix`, and nothing else under it.
      Apple's `/usr/bin/python3` sets that prefix to a directory under the
      user's home, which is under none of the three classes above - so on
      the interpreter DP3 pins the owner's own instance to, this assertion
      called the interpreter's own cached bytecode a stray read of a
      project.
    """
    roots = [Path(__file__).resolve().parent]
    roots.extend(Path(prefix) for prefix in OS_OWNED if Path(prefix).is_dir())
    for key in ("stdlib", "platstdlib", "purelib", "platlib"):
        path = sysconfig.get_paths().get(key)
        if path:
            roots.append(Path(path))
    roots.append(Path(sys.prefix))
    # And the installation a virtual environment was created *from*.
    # `sys.prefix` is the venv; the interpreter's own stdlib zip sits
    # beside the base installation's lib directory and is under neither
    # `sys.prefix` nor any sysconfig path, so a run inside a venv that
    # touches the zip reported it as a stray read of a project. It is the
    # same permitted class as the four above - the interpreter's own
    # files - and it was missing rather than excluded. Found by step 9,
    # whose distribution lookup is the first thing here to make the
    # import system scan its path entries.
    roots.append(Path(sys.base_prefix))
    return roots


# A bytecode cache entry, both of the names one of them passes through.
# CPython writes a `.pyc` atomically: `_write_atomic` opens
# `<name>.pyc.<id(path)>`, writes it, and renames it into place - so the
# name the audit hook actually sees on a **cold cache** is the one that
# does *not* end in `.pyc`, and the one it sees ever afterwards is the one
# that does. A rule written for the second name only is green on every run
# but the first, which is the run right after every code change.
BYTECODE_NAME = re.compile(r"\.pyc(\.[0-9]+)?$")


def _is_cached_bytecode(resolved, pycache_root):
    """One bytecode cache entry under this interpreter's cache prefix.

    Narrow on both axes on purpose, and each half is reverse-verified:
    a file under the prefix whose name is not a `.pyc` (a planted
    `README.md`) is still a stray, and a `.pyc` outside the prefix is
    still measured against the roots like anything else. The temptation
    here is to permit the prefix as a tree, and that is the shape whose
    first version passed while reading a project planted inside it.
    """
    if pycache_root is None:
        return False
    if not BYTECODE_NAME.search(resolved.name):
        return False
    return inside_root(pycache_root, resolved)


def _stray_reads(paths, permitted_roots):
    """Paths the selftest opened outside every permitted root.

    Called from `ReadWindow.strays` and from nowhere else - Rule 24 refuses
    a second caller, because a second caller is a second permitted set for
    one window and that is DP114 word for word.
    """
    roots = _permitted_read_roots()
    roots.extend(Path(root) for root in permitted_roots if root)
    temp_root = Path(tempfile.gettempdir()).resolve()
    # Where this interpreter keeps cached bytecode, when it keeps it
    # somewhere other than beside the source. `sys.pycache_prefix` is None
    # on most builds and is set on Apple's `/usr/bin/python3` - to a
    # directory under the *user's home*, which is not under `sys.prefix`,
    # not under any sysconfig path, and not under any root this assertion
    # permitted. So on the one interpreter DP3 says the owner's own
    # instance is pinned to, `murscope selftest` reported nine to twelve
    # of the interpreter's own `.pyc` files as stray reads of a project,
    # on an empty roster, and did so before this branch existed.
    #
    # It is the fifth instance of one shape and the smallest: the docstring
    # above has always listed "the interpreter's own directories" as a
    # permitted class, and this is one of them that the code did not name.
    # Narrowed to bytecode entries rather than permitting the tree, for the
    # reason the temporary-directory rule is narrowed to a direct child: a
    # permission wider than the thing it exists for is how the first
    # version of that rule passed while reading a project planted in it.
    #
    # **The first version of *this* rule was narrower than the thing it
    # exists for, which is the same failure from the other side.** It
    # permitted names ending in `.pyc`, and CPython writes a `.pyc` by
    # opening `<name>.pyc.<id>` and renaming - so the name seen on a cold
    # cache is the one that does not match. The result was a guard that
    # went red on the first run after any code change and green on the
    # second, which teaches a reader to run it twice rather than to read
    # it. Caught by the management window on the interpreter this exists
    # for; `BYTECODE_NAME` now covers both names and nothing else.
    pycache_root = getattr(sys, "pycache_prefix", None)
    pycache_root = Path(pycache_root).resolve() if pycache_root else None
    stray = []
    for raw in paths:
        # A pseudo-filename, not a path. `<unknown>`, `<string>` and
        # friends name a code object that was never on disk, and nothing
        # was opened. Found by step 7: from 3.11 onward
        # `traceback.format_exception` parses the offending source line to
        # place its carets, and that parse raises an audit event carrying
        # `<unknown>` - which resolved against the working directory and
        # was reported as a project read in a directory nobody listed.
        if raw.startswith("<") and raw.endswith(">"):
            continue
        try:
            resolved = Path(raw).resolve()
        except OSError:
            continue
        if any(inside_root(root, resolved) for root in roots):
            continue
        # A direct child of the temporary directory, and nothing deeper.
        if resolved.parent == temp_root:
            continue
        # Cached bytecode under this interpreter's cache prefix, and
        # nothing else under it.
        if _is_cached_bytecode(resolved, pycache_root):
            continue
        if resolved in stray:
            continue
        stray.append(resolved)
    return stray


def _build_repo(home, name, layout):
    """Write a git-shaped sensitive project under the throwaway home.

    **Why this exists at all.** The first canary pointed at a directory
    with two markdown files and no `.git`, and for a `sensitive` entry the
    collector disables exactly the readers that touch files - todos, code
    markers, the tree walk, the stack probe, maturity, the ledger - leaving
    only the git branch. So the assertion ran over a collection in which
    **no reader executed at all**, and an audit proved the consequence: a
    reader injected into the git branch leaked the decoy into `data.json`
    with the gate green, while the same reader in the non-git branch was
    caught. The canary was measuring a path nothing takes.

    A repository is therefore fabricated, so the branch a sensitive entry
    actually runs is the branch under test.
    """
    root = home / name
    for rel, body in layout:
        guard_write_path(root / rel, body)
    return root


def check_sensitive_canary(settings, catalog, vocabulary):
    """Sensitive entries, real collection, and every surface read as text.

    DP65. Static analysis kept failing to prove absence, so this asks the
    question from the other end: put a decoy in a sensitive project's
    files, run the paths a real command runs, and look for the decoy in
    what came out. It cannot be walked past by writing a reader
    differently, because it never looks at the reader.

    Two entries, because a sensitive entry's git branch and its non-git
    branch are different code: a fabricated repository, and the plain
    directory that ships with the package.

    Commit subjects are covered too, because DP68 withholds
    `last_subject` from a sensitive entry. Two assertions rather than a
    decoy, because a commit cannot be fabricated here - `git commit` is
    not on Rule 5's read-only allowlist and is not going on it for a test
    - so this checks that the key is absent from every sensitive record
    *and* absent from the whitelist. Put it back in either place and this
    step goes red, which is what makes "measured" a true word in the line
    it prints.
    """
    # The user's real MURSCOPE_HOME is not captured here any more. It used
    # to be, and it had to be captured *before* the redirect: `TemporaryHome`
    # below repoints the environment, so `murscope_home()` asked inside the
    # block returns the sandbox, the real home stops being permitted, and
    # the user's own `roster.json` gets reported as a stray read. That trap
    # is gone rather than avoided - `main()` registers the real home once,
    # before any sandbox exists, and every step reads the same permitted set
    # (DP114).
    surfaces = []
    findings = []
    from . import cli  # noqa: PLC0415 - cli imports this module too
    from .preview import TemporaryHome  # noqa: PLC0415 - same reason

    with TemporaryHome() as home:
        WINDOW.permit(home.path, "throwaway home(s) this run built")
        root = _build_repo(home.path, "canary-project", FABRICATED_REPO)
        ordinary = _build_repo(home.path, "ordinary-project", ORDINARY_REPO)
        entries = [config.Entry(0, {"id": "canary-git", "name": "canary-git",
                                    "root": str(root), "sensitive": True})]
        if CANARY_DIR.is_dir():
            entries.append(config.Entry(
                1, {"id": "canary-plain", "name": "canary-plain",
                    "root": str(CANARY_DIR), "sensitive": True}))
        else:
            findings.append(
                "the shipped canary directory is missing from this build, so "
                "the non-git branch was not exercised")
        entries.append(config.Entry(
            len(entries), {"id": "ordinary", "name": "ordinary",
                           "root": str(ordinary)}))

        roster = config.Roster(entries, home.path, True, [])
        # Rule 1 says this covers "everything printed". It covered stdout,
        # so a decoy written to stderr went through green. Both streams into
        # one buffer now, which is also how a reader would see them.
        captured = io.StringIO()
        with contextlib.redirect_stdout(captured), \
                contextlib.redirect_stderr(captured):
            records, problems = cli.collect_records(
                roster, settings, catalog, vocabulary)
            document, _written = render.render(
                records, settings, catalog, "en",
                problems + ["a problem line, so the list is not empty"],
                {}, home.path)
            for entry in entries:
                explain.explain(entry, settings, vocabulary, catalog)

        surfaces.append(("the payload data.json and data.js carry",
                         json.dumps(document, ensure_ascii=True)))
        surfaces.append(("everything the run printed", captured.getvalue()))

        # The outbound payload, examined directly and not as a board file.
        # Red line four holds on every surface, and this is the only one
        # where being wrong cannot be undone: a board file that says too
        # much can be deleted, a request that has left cannot. M2 planted
        # its decoy on what was written to disk; that is a different
        # question from what would be sent, and the second one has to be
        # asked here rather than inferred from the first.
        try:
            payload = outbound.build(records)
        except Exception as exc:
            payload = None
            findings.append(
                "the outbound payload could not be built (%s: %s), so the "
                "decoy was never looked for on the one surface that cannot "
                "be undone." % (type(exc).__name__, exc))
        if payload is not None:
            surfaces.append(("the outbound payload",
                             outbound.canonical(payload).decode("ascii")))
            # Both directions, because either one alone is satisfiable by a
            # builder that produced nothing (DP87). Two sensitive entries
            # have to have been dropped, and the ordinary one has to have
            # survived - otherwise "no sensitive content in the payload" is
            # true of an empty payload.
            sensitive_count = sum(1 for e in entries if e.sensitive)
            if payload.get("withheld_sensitive") != sensitive_count:
                findings.append(
                    "%d sensitive entry(s) were collected and the outbound "
                    "payload reports %r withheld. The count is what tells the "
                    "user something was left out; a wrong one is a wrong "
                    "account of what left."
                    % (sensitive_count, payload.get("withheld_sensitive")))
            carried = [row.get("id") for row in payload.get("projects") or []]
            if carried != ["ordinary"]:
                findings.append(
                    "the outbound payload describes %r. It must describe the "
                    "one entry that is not sensitive and no other: a payload "
                    "that describes nothing would satisfy every absence "
                    "assertion above by never containing anything." % carried)
        # Every file under the throwaway home, rather than the five this
        # block remembered to name. CONTRIBUTING described the surfaces as
        # "the payload, everything printed, and every file written", and the
        # list version was the three files `render` returned plus the roster
        # and the config - so a fourth artifact written under MURSCOPE_HOME
        # was never opened while the sentence describing this stayed green.
        # `written` is not consulted any more: it is a subset of what the
        # walk finds, and reading it as well would double every board file.
        #
        # The two fabricated projects are pruned. They are where the decoy
        # was planted and the input this run read, not surfaces this run
        # produced, and walking into the canary would report the fixture as
        # a leak of itself.
        sealed_from_surfaces = {root.name, ordinary.name}
        for dirpath, dirnames, filenames in os.walk(str(home.path)):
            dirnames[:] = sorted(name for name in dirnames
                                 if name not in sealed_from_surfaces)
            for name in sorted(filenames):
                path = Path(dirpath) / name
                try:
                    body = path.read_text(encoding="utf-8", errors="replace")
                except OSError as exc:
                    findings.append("a file this run wrote under the throwaway "
                                    "home could not be read back (%s), so it "
                                    "was not checked for the decoy" % exc)
                    continue
                surfaces.append((str(path.relative_to(home.path)), body))

        for what, text in surfaces:
            if CANARY in text:
                findings.append(
                    "the decoy from a sensitive project's files appears in %s. "
                    "Rule 7 permits method only, and this is content." % what)
        # DP68: a commit subject is content, so a sensitive row may not
        # carry one. A fabricated repository has no commits to hide a decoy
        # in, so this checks the two states that would let one through.
        #
        # The whitelist is the load-bearing one. Deriving the value again in
        # the collector without whitelisting it changes nothing - the filter
        # drops it and it never reaches an artifact - so the record check
        # below is a second net that only fires when both have happened,
        # rather than an independent one. Said plainly because a check that
        # sounds like two assertions and is really one is the shape this
        # project keeps finding.
        # The constant itself, first. Everything below iterates it, so
        # emptying it - or dropping the one key DP68 is about - would turn
        # two assertions into zero assertions and leave the step green
        # while the ruling was reversed. That is the hollow-check shape
        # this repository has found four times; it does not get to exist
        # here just because the list has one element today.
        if "last_subject" not in config.SENSITIVE_WITHHELD_KEYS:
            findings.append(
                "SENSITIVE_WITHHELD_KEYS no longer names 'last_subject', so "
                "nothing below asserts that a commit subject stays off a "
                "sensitive row. DP68 is settled: a sensitive project's "
                "contents do not go on the board, and a commit message is "
                "contents.")
        for key in config.SENSITIVE_WITHHELD_KEYS:
            if key in config.SENSITIVE_ALLOWED_KEYS:
                findings.append(
                    "%r is withheld from sensitive entries (DP68, settled) and "
                    "is back in SENSITIVE_ALLOWED_KEYS. A commit subject is "
                    "contents, and a sensitive project's contents do not go on "
                    "the board." % key)
            carried = sorted(r.get("id") for r in records if key in r)
            if carried:
                findings.append(
                    "sensitive record(s) %s carry %r, which is content: a "
                    "commit subject is the line most likely to name a client "
                    "or a person." % (", ".join(carried), key))

        # The git branch has to have actually run, or this proves nothing -
        # which is the whole reason the canary was rewritten.
        if not any(r.get("id") == "canary-git"
                   and r.get("uncommitted") is not None for r in records):
            findings.append(
                "the fabricated repository did not produce a git signal, so "
                "the branch a sensitive entry actually runs was not exercised")

        # DP69, and it goes **last** in this block on purpose. It used to sit
        # fifteen lines higher, so a read added below it was outside the
        # window while the docstring said the window covered the step - the
        # same "narrower than its own sentence" shape, a third time, in the
        # guard written to answer the second one. Placed at the end so the
        # window closes where the step does.
        for path in WINDOW.strays():
            findings.append(
                "the selftest opened %s, which is outside the throwaway home "
                "it built and outside this package. Rule 7's static pass "
                "skips this module on the grounds that it only reads its own "
                "sandbox; that is measured here, and it just stopped being "
                "true." % path)
    return findings, len(surfaces)


# Obviously fabricated, and deliberately not shaped like any vendor's
# credential: no real prefix, no real length, and the word "decoy" in the
# middle of it. A decoy that looked like a working key would be a working
# key the day somebody pasted this file into a search box.
DECOY_KEY = "murscope-decoy-key-not-a-real-credential-0000"


def check_key_never_reaches_an_artifact(settings, catalog, vocabulary):
    """DP18, and the half of it that only shows up on a bad day.

    Same instrument as the sensitive canary, pointed at a different
    secret: store a key through the real store, run the paths a real
    command runs, and look for the key in what came out. It cannot be
    walked past by writing a reader differently, because it never looks at
    a reader.

    **Four surfaces, and the fourth is the one that needed building.**

    * every file this run wrote under the throwaway home - the board's
      three files and anything beside them;
    * the outbound payload, which is the surface that cannot be undone;
    * everything the run printed, both streams, including `key list`,
      which is the command whose whole job is to talk about keys;
    * **the traceback of a failed request.** A URL with a key in its query
      string, handed to `urllib`, comes back as `ValueError: unknown url
      type: '...?key=<the key>'` - the standard library builds that
      string, and it lands in an exception message, which becomes a
      traceback, which is an artifact. The transport therefore leaves
      every failure through `keys.reraise_masked`, which redacts and
      raises `from None` so the original does not follow it into the
      traceback under "During handling of the above exception". That is
      the shape asserted here, on the shipped function, in a base install
      that has no transport at all.

    **What walks into each of them (DP87).** The key file has to contain
    the decoy, or the store wrote nothing and every absence below is
    vacuous. The masked failure has to carry the mask, or the redaction
    never ran and the traceback is clean because the message was empty.
    The board files have to exist. All three are asserted, not assumed.
    """
    findings = []
    surfaces = []
    from . import cli  # noqa: PLC0415 - cli imports this module too
    from .preview import TemporaryHome  # noqa: PLC0415 - same reason

    with TemporaryHome() as home:
        WINDOW.permit(home.path, "throwaway home(s) this run built")
        where, problems = keys.store("selftest-decoy", DECOY_KEY, home.path)
        for line in problems:
            findings.append("the key store refused the decoy: %s" % line)
        if where is None:
            return findings + ["nothing was stored, so nothing below was "
                               "measured"], 0, None

        stored = Path(where)
        mode = os.stat(str(stored)).st_mode & 0o777
        if mode != keys.FILE_MODE:
            findings.append(
                "the key was written at mode %04o and DP18 says %04o. A key "
                "file is protected by the filesystem and by nothing else."
                % (mode, keys.FILE_MODE))
        directory_mode = os.stat(str(stored.parent)).st_mode & 0o777
        if directory_mode != keys.DIR_MODE:
            findings.append(
                "the key directory is at mode %04o and %04o was intended. A "
                "0600 file in a listable directory still publishes which "
                "providers you hold a key for."
                % (directory_mode, keys.DIR_MODE))
        if not inside_root(home.path, stored):
            findings.append(
                "the key was written to %s, which is outside MURSCOPE_HOME."
                % stored)
        if DECOY_KEY not in stored.read_text(encoding="utf-8"):
            findings.append(
                "the decoy is not in %s, so the store wrote something else - "
                "and every absence asserted below would be an absence of "
                "nothing." % stored)

        secret, problems = keys.read("selftest-decoy", home.path)
        for line in problems:
            findings.append("reading the decoy back: %s" % line)
        if secret is None:
            findings.append("the decoy could not be read back through the "
                            "store, so the masking below was not exercised")
        else:
            if secret.value != DECOY_KEY:
                findings.append("the store handed back a different value than "
                                "it was given")
            surfaces.append(("str() of a key", str(secret)))
            surfaces.append(("repr() of a key", repr(secret)))
            surfaces.append(("a key in a format string", "{}".format(secret)))
            surfaces.append(("a key in a percent format", "%s" % secret))
            surfaces.append(("a key in a padded format",
                             "{:>60}".format(secret)))
            try:
                surfaces.append(("a key handed to json.dumps",
                                 json.dumps(secret)))
                findings.append(
                    "json.dumps() serialised a key instead of refusing it. "
                    "The refusal is what keeps a key out of any payload "
                    "written by code that never thought about keys.")
            except TypeError:
                pass

        # A real run, with the key sitting in the home the board is written
        # into. Nothing here reads a key on purpose, which is the point: a
        # reader added later - to the collector, to the renderer, to a
        # problem line - has to walk past this.
        ordinary = _build_repo(home.path, "ordinary-project", ORDINARY_REPO)
        entries = [config.Entry(0, {"id": "ordinary", "name": "ordinary",
                                    "root": str(ordinary)})]
        roster = config.Roster(entries, home.path, True, [])
        captured = io.StringIO()
        with contextlib.redirect_stdout(captured), \
                contextlib.redirect_stderr(captured):
            records, problems = cli.collect_records(
                roster, settings, catalog, vocabulary)
            document, written = render.render(
                records, settings, catalog, "en", problems, {}, home.path)
            cli.key_command(["list"])
        surfaces.append(("everything the run printed, `key list` included",
                         captured.getvalue()))
        surfaces.append(("the board payload",
                         json.dumps(document, ensure_ascii=True)))
        try:
            surfaces.append(("the outbound payload",
                             outbound.canonical(outbound.build(records))
                             .decode("ascii")))
        except Exception as exc:
            findings.append("the outbound payload could not be built (%s: %s)"
                            % (type(exc).__name__, exc))
        if not written:
            findings.append("no board file was written, so the board files "
                            "were not among the surfaces examined")

        masked_text = ""
        try:
            try:
                # The exact shape `urllib.request.Request` produces for a
                # URL it cannot parse. Constructed rather than provoked,
                # because provoking it means importing urllib, which Rule
                # 11 refuses the core - and the message is the artifact,
                # not the module that built it.
                raise ValueError("unknown url type: %r"
                                 % ("nonsense?key=%s" % DECOY_KEY))
            except ValueError as exc:
                keys.reraise_masked(exc, "the request could not be completed")
        except keys.Masked as masked:
            masked_text = "".join(traceback.format_exception(
                type(masked), masked, masked.__traceback__))
            if not masked.__suppress_context__:
                findings.append(
                    "the masked failure did not suppress its context, so the "
                    "original exception - the one whose message holds the key "
                    "- follows it into every traceback under \"During "
                    "handling of the above exception\".")
            if keys.MASK not in masked_text:
                findings.append(
                    "the masked failure carries no %r, so redaction did not "
                    "run and this traceback is clean for the wrong reason."
                    % keys.MASK)
        except Exception as exc:
            findings.append("the masked failure path raised %s instead of "
                            "keys.Masked, so it was not exercised"
                            % type(exc).__name__)
        surfaces.append(("the traceback of a failed request", masked_text))

        sealed_from_surfaces = {ordinary.name, keys.KEYS_DIRNAME}
        for dirpath, dirnames, filenames in os.walk(str(home.path)):
            dirnames[:] = sorted(name for name in dirnames
                                 if name not in sealed_from_surfaces)
            for name in sorted(filenames):
                path = Path(dirpath) / name
                try:
                    body = path.read_text(encoding="utf-8", errors="replace")
                except OSError as exc:
                    findings.append("a file this run wrote under the throwaway "
                                    "home could not be read back (%s)" % exc)
                    continue
                surfaces.append((str(path.relative_to(home.path)), body))

        for what, text in surfaces:
            if DECOY_KEY in text:
                findings.append(
                    "the stored key appears in %s. A key belongs in one file "
                    "at mode 0600 and in the request it authenticates, and "
                    "nowhere else - an exception traceback included." % what)

        # The whole run, against the whole permitted set - the same call
        # step 10 makes, because there is only one of them now. This site
        # used to assemble its own list of roots and left the projects step
        # 4 collects off it, so on any machine with a roster it reported a
        # legitimate read as a stray and `selftest` was red for every user
        # who had run `init` (DP114). `ordinary` is not registered here: it
        # is built inside the throwaway home above, which already is.
        for path in WINDOW.strays():
            findings.append(
                "the selftest opened %s, which is outside every throwaway "
                "home it built and outside this package." % path)
    return findings, len(surfaces), stored


def check_consent_binds_to_its_disclosure():
    """The ruling of this stage, measured rather than described.

    A boolean consent fails quietly in one specific way: the payload
    grows, and the old agreement silently covers the new, larger one.
    Nobody is asked again and nothing goes red. So a `Grant` is bound to a
    fingerprint of the disclosure it was granted against, and this asserts
    the four behaviours that makes true - **including the two that have to
    keep working**, because a binding that refused everything would pass
    the refusals and be useless:

    1. a grant recorded against today's disclosure covers today's request;
    2. a disclosure with one more field does **not** carry that grant
       over, and the refusal names the field;
    3. the same disclosure to a different destination does not either -
       agreeing to send eleven numbers to a model on your own machine is
       not agreeing to send them to a vendor (DP90);
    4. nothing is recorded means nothing is covered, and the message says
       what to run.

    The widened disclosure is a longer field list handed to the same
    function, not a patched module: the fingerprint takes the fields as an
    argument precisely so that this case can be constructed without
    reaching inside anything.
    """
    from .preview import TemporaryHome  # noqa: PLC0415 - as elsewhere here
    findings = []
    fields = outbound.fields()
    if len(fields) < 2:
        return ["the disclosure declares %d field(s); with fewer than two "
                "there is nothing for a widened case to widen."
                % len(fields)], 0
    widened = tuple(fields) + ("projects[].last_subject",)
    provider, destination = "selftest", "https://example.invalid"
    checked = 0

    with TemporaryHome() as home:
        WINDOW.permit(home.path, "throwaway home(s) this run built")
        try:
            consent.require(provider, destination, fields, home.path)
            findings.append(
                "an unrecorded consent was accepted. Nothing may be sent "
                "before the user has been shown what leaves and agreed.")
        except consent.ConsentRequired:
            checked += 1

        grant, _path = consent.record(provider, destination, fields, home.path)
        try:
            covered = consent.require(provider, destination, fields, home.path)
            checked += 1
            if covered.digest != grant.digest:
                findings.append("the grant written and the grant read back "
                                "carry different fingerprints")
        except Exception as exc:
            findings.append(
                "a consent recorded a moment ago did not cover the request it "
                "was recorded for (%s: %s). A binding that refuses everything "
                "passes every refusal below and is useless."
                % (type(exc).__name__, exc))

        try:
            consent.require(provider, destination, widened, home.path)
            findings.append(
                "a consent recorded against %d field(s) was accepted for a "
                "disclosure of %d. This is the whole ruling of this stage: "
                "the user agreed to what they were shown, so a payload that "
                "grew has to ask again rather than inherit the answer."
                % (len(fields), len(widened)))
        except consent.ConsentStale as exc:
            checked += 1
            if "last_subject" not in str(exc):
                findings.append(
                    "the refusal does not name the field that was added, so "
                    "the user is sent to read a diff: %s" % exc)

        try:
            consent.require(provider, "https://elsewhere.invalid", fields,
                            home.path)
            findings.append(
                "a consent recorded for %s was accepted for another "
                "destination. Where the data goes is part of what was "
                "disclosed (DP90)." % destination)
        except consent.ConsentStale:
            checked += 1

    return findings, checked


def state_of(record, entry, catalog):
    # The local import this used to carry said "kept local to this one
    # use", and step 5 is a second use with a module-level case table, so
    # the module imports it like everything else. `render` already pulls
    # `state` in at import time, so nothing new is loaded.
    return state.resolve(record, entry, catalog)


def check_offline(settings, roster, vocabulary):
    """Collect and scan for real, under the hook `main()` already installed.

    This step does not install anything. `NETWORK` went on before step 1,
    so the verdict it reports covers every step rather than this one - the
    version that installed the hook here measured only the last quarter of
    a run whose closing line spoke for all of it.

    What is left here is the *exercise*: the collection and the scan are
    the code paths whose silence is worth proving, because `init` walks
    directories nobody listed and shells out to git in each repository it
    meets. The hook cannot be removed once installed, which is why the
    process exits after this command and nothing else.
    """
    targets = [entry for entry in roster if entry.usable]
    stand_in = None
    if not targets:
        stand_in = Path(__file__).resolve().parent
        targets = [_StandIn(stand_in)]

    read_roots = [entry.path for entry in targets if entry.path]
    # Registered here, before the first collection, rather than handed back
    # for a caller to register. This is the step that acquires the roots and
    # the step whose reads need them, and the version that returned them for
    # `main()` to pass along is the version in which step 7 never got them
    # (DP114). Rule 17 is what permits these: a read inside a listed project
    # is that rule's business and has its own check.
    #
    # The reason is not the same sentence in both branches, because they are
    # not the same permission: a listed project is Rule 17's, and the
    # package directory collected for an empty roster is this package's own.
    # A run whose roster is empty must not print a line claiming it read a
    # project the roster listed - that is a smaller version of exactly the
    # failure this window keeps finding.
    why = ("stand-in root(s) collected for an empty roster"
           if stand_in is not None else
           "project root(s) the roster listed (Rule 17)")
    for root in read_roots:
        WINDOW.permit(root, why)
    collected = 0
    errors = []
    for entry in targets:
        try:
            collect.collect_project(entry, settings, vocabulary)
            collected += 1
        except RuntimeError as exc:
            errors.append(str(exc))
        except Exception as exc:  # a collection bug is not a network finding
            errors.append("%s: %s" % (type(exc).__name__, exc))

    # M2's promise is about `init` as much as `run`, and `init` reaches
    # further: it walks directories nobody listed and shells out to git
    # in each repository it finds. The task book asked for this to join
    # the permanent test rather than be measured once and forgotten, so
    # the scan and the permission probe run under the same hook.
    scanned = 0
    # The target itself, not its parent: scanning a project root finds
    # that project and therefore shells out to git under the hook, which
    # is the part worth watching. Scanning the parent can legitimately
    # find nothing - inside a git worktree the checkout is excluded by
    # DP57 - and a test that silently discovers nothing proves nothing.
    root = Path(targets[0].path) if targets else Path(__file__).parent
    try:
        sealed = config.sealed_dirs(settings.section("scan").get("sealed_dirs", []))
        doctor.check([root], sealed)
        found = scan.discover([root], sealed, budget_seconds=10)
        scanned = len(found.candidates)
    except RuntimeError as exc:
        errors.append(str(exc))
    except Exception as exc:
        errors.append("%s: %s" % (type(exc).__name__, exc))
    # The roots are not returned. They were, and `main()` passed them to one
    # of the two read-location assertions and not the other - which is the
    # whole of DP114. They now leave this function the only way they can be
    # used: registered on the window, in front of the read they permit.
    return collected, stand_in, errors, scanned


class _Case(object):
    """A roster entry with only what `state.resolve` reads off one."""

    def __init__(self, note=None):
        self.id = "case"
        self.note = note


# A declaration in the shape `read_ledger` hands to the state layer. Its
# text is deliberately about something other than work in hand, because
# that is the whole case: the headline is a quotation, and what the row is
# holding has to arrive some other way.
_CASE_DECLARATION = {
    "text": "BLOCKED: the vendor has not replied.",
    "source": "STATUS.md", "line_no": 3, "marker": "blocked",
    "at": None, "age_days": 1.0, "stale": False, "owner": False,
    "names_somebody": False,
}


def _case_signals(uncommitted=0, unpushed=0, stash=0, wip=False,
                  declared=False):
    signals = {
        "uncommitted": {"quality": "ok", "signal": "uncommitted",
                        "files": uncommitted},
        "unpushed": {"quality": "ok", "signal": "unpushed",
                     "commits": unpushed},
        "stash": {"quality": "ok", "signal": "stash", "entries": stash,
                  "oldest_age_days": 1.0 if stash else None},
        "last_commit": {"quality": "ok", "signal": "last_commit", "wip": wip,
                        "subject": "wip: half of it" if wip else "a commit"},
        "ledger": {"quality": "ok", "read": ["STATUS.md"], "hits": 1},
    }
    if declared:
        signals["ledger"]["declaration"] = dict(_CASE_DECLARATION)
    return signals


# label, kind expected, signals, roster note.
#
# The expected kind is asserted as well as the sentence. Without it a case
# that quietly stopped reaching the branch it was written for would pass
# by never being the thing it claims to test - the hollow shape this
# repository has now found more than once.
_STATE_CASES = (
    ("declared, holding all four", state.DECLARED,
     dict(uncommitted=21, unpushed=2, stash=1, wip=True, declared=True), None),
    ("declared, holding files only", state.DECLARED,
     dict(uncommitted=1, declared=True), None),
    ("declared, nothing in hand", state.DECLARED, dict(declared=True), None),
    ("curated, holding files", state.CURATED, dict(uncommitted=3),
     {"text": "Mid-rewrite.", "since": "2026-08-13"}),
    ("curated, nothing in hand", state.CURATED, dict(),
     {"text": "Parked.", "since": "2026-08-13"}),
    ("inferred, holding files and a stash", state.INFERRED,
     dict(uncommitted=4, stash=1), None),
    ("inferred, nothing in hand", state.INFERRED, dict(), None),
)


def check_state_accounts_for_what_it_counts(catalog):
    """DP80: what the tiles count, the row it counts says.

    The summary line and the board tiles take DP73's literal reading - a
    row with uncommitted files is holding uncommitted work, whatever its
    headline is about. That reading is only honest if the row can be
    reconciled with the number, and a declaration or a note outranks the
    whole inference table, so those rows used to print the quotation and
    nothing else.

    The invariant asserted here is the one sentence that has to hold:
    **every in-hand rule that matched appears on the row**, as the
    headline or in its sub-text. It is stated in terms of rule keys rather
    than English, so it holds in every locale, and it is checked across
    the three kinds that can outrank each other rather than only the one
    that changed.

    Pinned the other way too, because a state layer that attached every
    fact to every row would satisfy the sentence above and be useless: a
    row with nothing in hand must carry an empty sub-text, so the screen
    and the board show no bullet at all.

    Both surfaces, not just the payload. `wizard._row` is where the
    terminal screen turns a state into lines, and an assertion about the
    data alone would have passed with the screen printing nothing - which
    is exactly the half F6 was opened about.
    """
    from . import wizard  # noqa: PLC0415 - only this step renders a row
    failures = []
    rules_seen = 0
    wrapped = 0
    for label, want_kind, spec, note in _STATE_CASES:
        signals = _case_signals(**spec)
        record = {"id": "case", "name": "case", "recency_days": 1.0,
                  "signals": signals}
        resolved = state.resolve(record, _Case(note), catalog)
        if resolved.get("kind") != want_kind:
            failures.append("%s: resolved to %r, so this case no longer "
                            "exercises the %r branch it was written for"
                            % (label, resolved.get("kind"), want_kind))
            continue
        shown = [resolved.get("text") or ""] + list(resolved.get("also") or [])
        for item in state.rules_that_matched(record, signals, catalog):
            if item["rule"] not in state.IN_HAND_RULES:
                continue
            rules_seen += 1
            if item["text"] not in shown:
                failures.append(
                    "%s: rule %r matched and its sentence is on neither the "
                    "headline nor the sub-text, so the row cannot be "
                    "reconciled with the count that includes it"
                    % (label, item["rule"]))
        in_hand = any(spec.get(key) for key in
                      ("uncommitted", "unpushed", "stash", "wip"))
        also = resolved.get("also") or []
        if not in_hand and also:
            failures.append("%s: nothing is in hand and the sub-text is %r; a "
                            "row with nothing to add must add nothing"
                            % (label, also))

        record_with_state = dict(record, state=resolved)
        lines = wizard._row(1, record_with_state, None).split("\n")
        printed = "\n".join(lines[1:])
        if also and len(lines) < 2:
            failures.append("%s: the state carries %d sub-text sentence(s) and "
                            "the summary screen printed %d line(s) for the row"
                            % (label, len(also), len(lines)))
        elif not also and len(lines) != 1:
            failures.append("%s: nothing is in hand and the summary screen "
                            "still printed %d line(s)" % (label, len(lines)))
        # The sentence itself, not a bullet character standing in for it.
        # This assertion used to ask whether the sub-text line existed and
        # whether a `\u00b7` was on it - both of which a clipped line still
        # satisfies. It was green while the row printed "stopped halfway -
        # 2 commits finished but..." beside a tile counting the uncommitted
        # work the clip had removed (DP82). A check that names the thing it
        # watches and then measures something adjacent to it is the shape
        # this milestone has now found five times.
        for sentence in also:
            if sentence not in printed:
                failures.append(
                    "%s: the state carries the sub-text %r and the summary "
                    "screen printed %r, which does not contain it - the row "
                    "cannot be reconciled with a count that includes it"
                    % (label, sentence, printed))
        if len(lines) > 2:
            wrapped += 1
    return failures, len(_STATE_CASES), rules_seen, wrapped


# The rows the locale table is rendered from, one per width class. The
# names are invented and none of them is read off this machine.
#
# name, signals
_WIDTH_ROWS = (
    ("orchestrator", dict(uncommitted=3)),
    # Accented Latin: one cell per letter and two UTF-8 bytes per accent,
    # which is the case that separates a cell count from a byte count.
    ("r\u00e9f\u00e9rentiel-des-donn\u00e9es-partag\u00e9es",
     dict(unpushed=2, uncommitted=1)),
    # Wide: two cells per character. Holding all four things, so the row
    # produces a sub-text long enough to wrap.
    ("\u8bfe\u7a0b\u8bbe\u8ba1\u5e73\u53f0",
     dict(uncommitted=4, unpushed=2, stash=1, wip=True)),
)
_SOURCE = "- none"


def _own_cells(text):
    """This step's own cell count, so `width` is not marking its own work.

    Deliberately a second implementation of the same rule. Measuring
    `width`'s output with `width` would make every assertion below true by
    construction - the shape this product has found more than once.
    """
    total = 0
    for char in text:
        if unicodedata.category(char) in ("Mn", "Me"):
            continue
        total += 2 if unicodedata.east_asian_width(char) in ("W", "F") else 1
    return total


def _locales_the_status_doc_names(i18n):
    """Locale names from the shipped TRANSLATION_STATUS.md table.

    Read out of the document rather than off the directory, on purpose.
    `i18n.available()` globs whatever landed in site-packages, so a locale
    file left out of the wheel would simply stop being available and every
    assertion about "every locale" would pass over the ones that remain.
    The status document ships under a different package-data entry, so the
    two are unlikely to go missing together - and that disagreement is the
    finding. Both went missing once already, along with the fixtures and
    the marker packs, in the first wheel this product built.
    """
    path = Path(i18n.__file__).resolve().parent / "TRANSLATION_STATUS.md"
    if not path.exists():
        return None
    names = []
    for line in path.read_text(encoding="utf-8").splitlines():
        found = re.match(r"^\|\s*([a-z]{2}(?:[-_][A-Za-z]+)?)\s*\|\s*\d+\s*\|",
                         line)
        if found:
            names.append(found.group(1))
    return names or None


def check_the_table_lines_up_in_every_locale(catalog_unused=None):
    """(failures, locales, rows, offsets) - DP86, on the build that is installed.

    The gate's own Rule 29 measures this against the source tree. This
    step measures it against site-packages, which is a different question
    with a different failure: a locale file that never made it into the
    wheel renders every string on somebody's board as a missing-key marker
    while every check in the repository stays green, and that is not a
    hypothetical - the marker packs and the selftest fixtures were both
    missing from the first wheel this product built.

    Three things, per locale:

      * the summary screen's table puts its last column at one cell offset
        across the heading and every row;
      * no cell of it is a `[[MISSING:` marker, which is what a locale
        that shipped empty or short would print;
      * the rendering contains a wide character and an accented one, or
        this step says it measured nothing rather than reporting green.
    """
    from . import i18n, wizard  # noqa: PLC0415 - only this step renders one
    failures = []
    available = i18n.available()
    named = _locales_the_status_doc_names(i18n)
    if named is None:
        failures.append("TRANSLATION_STATUS.md did not ship with this build, "
                        "so there is nothing to compare the installed locales "
                        "against and 'every locale' means 'whichever ones "
                        "happen to be here'.")
    else:
        for locale in named:
            if locale not in available:
                failures.append(
                    "this build's TRANSLATION_STATUS.md names the %r locale "
                    "and no %s.json is installed. Every string of that "
                    "locale's board would render as a missing-key marker."
                    % (locale, locale))

    offsets = {}
    rows = 0
    for locale in available:
        catalog, problems = i18n.load(locale)
        for line in problems:
            failures.append("locale %s: %s" % (locale, line))
        lines = [wizard._header(catalog)]
        anchors = [i18n.translate(catalog, "col.ledger")]
        for index, (name, spec) in enumerate(_WIDTH_ROWS, start=1):
            signals = _case_signals(**spec)
            record = {"id": name, "name": name, "recency_days": 1.0,
                      "signals": signals}
            resolved = state.resolve(record, _Case(None), catalog)
            rendered = wizard._row(index, dict(record, state=resolved), None)
            for number, line in enumerate(rendered.split("\n")):
                lines.append(line)
                anchors.append(_SOURCE if number == 0 else None)
        text = "\n".join(lines)
        if i18n.MISSING_PREFIX in text:
            failures.append(
                "locale %s: the table rendered a %s marker, so this locale "
                "file is short of the keys the screen asks it for."
                % (locale, i18n.MISSING_PREFIX))
        if not any(unicodedata.east_asian_width(c) in ("W", "F") for c in text):
            failures.append(
                "locale %s: the rendered table holds no wide character, so "
                "the alignment below would be equally true of a screen that "
                "counted characters. Nothing was measured." % locale)
        if not any(ord(c) > 127 and unicodedata.category(c) in ("Ll", "Lu")
                   and unicodedata.east_asian_width(c) not in ("W", "F")
                   for c in text):
            failures.append(
                "locale %s: the rendered table holds no accented Latin "
                "letter, so a screen counting UTF-8 bytes would pass here."
                % locale)
        here = set()
        for line, anchor in zip(lines, anchors):
            if anchor is None or anchor not in line:
                continue
            rows += 1
            here.add(_own_cells(line[:line.rindex(anchor)]))
        offsets[locale] = here
        if len(here) > 1:
            failures.append(
                "locale %s: the table's last column starts at %d different "
                "cell offsets (%s). A column that starts in more than one "
                "place is not a column (DP86)."
                % (locale, len(here), ", ".join(str(n) for n in sorted(here))))
        elif not here:
            failures.append("locale %s: no row carried a last column, so "
                            "nothing was compared." % locale)
    if not available:
        failures.append("no locale files are installed at all, so this step "
                        "rendered nothing.")
    return failures, len(available), rows, offsets


# The two footer sentences and the install each one describes, as a
# table. Both branches are exercised on every install rather than only
# the one that happens to be installed - a promise that is only checked
# on the machine where it is already true is not checked (DP87).
_PROMISE_CASES = (
    ("a base install", (), boundary.BASE_PROMISE_KEY),
    ("an install carrying a socket-capable provider",
     (("network.py", "murscope-ai", ["urllib.request"]),),
     boundary.NETWORK_PROMISE_KEY),
)


def check_provider_boundary(catalog):
    """DP88: nothing a base install can load is able to open a socket.

    **What this measures, and why it is here rather than in the gate.**
    The claim is about what is on the user's disk after `pip install
    murscope` - not about what is in the repository, which is a different
    question with a different answer. M1's one real defect was a fixture
    that was in the source tree and missing from the wheel, invisible from
    a checkout; this is the same class, read from the other end. So the
    assertion ships inside the command, where it runs against the build
    the user actually installed. CI runs `murscope selftest` from a built
    wheel in a fresh environment outside every checkout, which is the
    configuration this step exists to be run in.

    The reading itself lives in `murscope.boundary`, because a second
    surface needs the same answer: the board's footer. It said "Makes no
    network call" on both installs, and that was true only while the
    transport refused to send - so stage two, which supplies the consent
    it was waiting for, is exactly when that sentence expired.

    **What walks into each finding (DP87).** The three cases `boundary`
    documents, plus two more here:

    * the footer table above, whose two rows fix the sentence each
      install is entitled to. The `[ai]` row runs on a base install too,
      because it is a fabricated survey answer rather than a real one;
    * the sentence the network row selects must exist in this locale. A
      key present in `en.json` and missing from the catalog being
      rendered would put `[[MISSING:board.promise.network]]` on somebody's
      board footer, which is a worse outcome than the stale promise.

    Returns (findings, rows, base_count, reaching).
    """
    survey = boundary.survey()
    findings = list(survey.findings)
    for label, reaching, want in _PROMISE_CASES:
        got = boundary.promise_key(reaching)
        if got != want:
            findings.append(
                "the board footer would print %r on %s, and %r is the "
                "sentence that install is entitled to." % (got, label, want))
    for _label, _reaching, key in _PROMISE_CASES:
        if not catalog.get(key):
            findings.append(
                "the catalog has no %r, so a board footer that needs it would "
                "print the missing-key marker." % key)
    return findings, survey.rows, survey.base_count, survey.reaching


class _StandIn(object):
    """A roster entry for a machine with no roster yet.

    The package's own directory is a real directory full of real files
    and no git history, so collecting it exercises the same code paths
    the hook needs to watch without inventing anything on disk - and
    inventing anything on disk is not available to this package anyway.
    """

    def __init__(self, path):
        self.id = "murscope-package"
        self.name = "murscope package directory"
        self.root = str(path)
        self.path = str(path)
        self.branch = ""
        self.sensitive = False
        self.ledgers = []
        self.note = None
        self.problems = []
        self.usable = True


def check_schedule_boundary():
    """(findings, refusals, permitted) - the second write boundary, live.

    Rule 26's check reads the guard's shape out of the parse tree. This
    reads its behaviour, and the two are not the same evidence: a guard
    can be shaped correctly and compare the wrong thing. The pairing is
    Rule 17's - structural *and* behavioural - and it is here rather than
    in the gate because this is where the user's own home directory is.

    **Nothing is written.** Every probe below is a path the guard must
    refuse, and a refusal happens before the guard touches anything, so a
    step that wrote something would be a step that failed. The permitted
    paths themselves are never handed to the writer here: proving that a
    guard permits what it should is `murscope timer install`'s job, and a
    selftest that installed a launch agent on somebody who typed one
    command would be a worse thing than the one it was checking.

    The sharpest of the probes is the last: **the two boundaries must not
    leak into each other.** `guard_write_path()` has to refuse the
    scheduling paths, or "murscope writes nothing outside MURSCOPE_HOME
    except its own job description" quietly becomes "except whatever is
    next to it".
    """
    findings = []
    permitted = permitted_schedule_paths()
    expected = len(SCHEDULE_FILES.get(sys.platform, ()))
    if len(permitted) != expected:
        findings.append(
            "permitted_schedule_paths() returned %d path(s) and the table "
            "for %s declares %d. The set of places this package may write "
            "outside MURSCOPE_HOME is the whole of DP126, so the two "
            "disagreeing is the finding."
            % (len(permitted), sys.platform, expected))

    home = Path(os.path.expanduser("~"))
    # Fabricated names, every one of them. A probe that named a real file
    # would be asserting a refusal on somebody's actual launch agent, and
    # the guard is supposed to be unable to tell the difference - which is
    # the point, and also the reason not to aim it at one.
    probes = [
        home / "Library" / "LaunchAgents" / "com.murscope.core.selftest.plist",
        home / ".config" / "systemd" / "user" / "murscope-core-selftest.timer",
        home / ".murscope-selftest-decoy",
        Path("/tmp") / "murscope-selftest-decoy.plist",
        Path("murscope-selftest-decoy.plist"),
    ]
    # A neighbour of each permitted path: same directory, one letter
    # different. This is the probe a prefix test passes and an equality
    # test refuses, and a prefix test is what "permit the directory"
    # would have been.
    probes.extend(path.parent / ("selftest-decoy-" + path.name)
                  for path in permitted)

    refusals = 0
    for probe in probes:
        for name, guard in (("guard_schedule_write",
                             lambda target: guard_schedule_write(target, "")),
                            ("guard_schedule_remove", guard_schedule_remove)):
            try:
                guard(probe)
            except RuntimeError:
                refusals += 1
            except Exception as exc:
                findings.append(
                    "%s(%s) raised %s rather than refusing cleanly."
                    % (name, probe, type(exc).__name__))
            else:
                findings.append(
                    "%s accepted %s, which is not in its permitted set of "
                    "%d path(s). The permission DP126 grants is for a path."
                    % (name, probe, len(permitted)))
        if probe.exists() and probe.name.startswith(
                ("com.murscope.core.selftest", "murscope-core-selftest",
                 ".murscope-selftest-decoy", "murscope-selftest-decoy",
                 "selftest-decoy-")):
            findings.append(
                "%s exists after the probes ran. A refusal that writes "
                "first is not a refusal." % probe)

    # The other direction, and the one that would rot quietly: the home
    # guard must not have grown a taste for these paths.
    for path in permitted:
        try:
            guard_write_path(path, "")
        except RuntimeError:
            refusals += 1
        else:
            findings.append(
                "guard_write_path() accepted %s. The two boundaries are "
                "separate on purpose - the home guard knows one root and "
                "the scheduling guard knows a fixed list - and a home guard "
                "that accepts a launch agent has stopped being either."
                % path)

    return findings, refusals, permitted


def check_alert_boundary(home):
    """(findings, asserted) - what an alert can and cannot carry, live.

    Two properties, and they fail in opposite directions, which is why
    both are here rather than one of them being inferred from the other.

    **A sensitive project cannot appear in an alert** (red line four, on a
    surface that pushes rather than one you pull). The decoy below is a
    project whose id *is* the canary string and whose previous snapshot
    would fire both rules on it - it is the loudest possible input, and it
    must produce nothing: no event, no entry in the snapshot that is kept
    between runs, and no occurrence of the string in any payload or in
    anything the local delivery printed. **And no count of it either**:
    the note carries `withheld_sensitive` and an alert deliberately does
    not, so the payloads are searched for the skipped count as well as for
    the name.

    **A delivery that fails is recorded as failed.** This is the failure
    this surface could not afford to be quiet about: nobody is at the
    machine, the alert did not arrive, and an absence of any trace reads
    from every angle like a quiet week. So a provider whose `alerts`
    callable raises is driven through the real delivery path, and what is
    asserted is that a record comes back, that its status is FAILED, and
    that `failures_since_last_success` counts it afterwards. No socket is
    involved: the stub raises before anything opens one, which is also why
    this can run under the network hook.

    What walks into it (DP87): the decoy is a real record handed to the
    real `evaluate()`, and the failure is the real `cli._send_one_alert`.
    Both halves assert a count as well as an absence, because an absence
    asserted over an empty set is the shape this file has found more than
    once - if nothing fired, nothing was withheld either.
    """
    from . import cli  # noqa: PLC0415 - only this step drives the command

    findings = []
    asserted = 0

    ordinary = {"id": "selftest-ordinary", "tier": "COLD",
                "recency_days": 40.0, "owner_queue": True, "sensitive": False}
    decoy = {"id": CANARY, "tier": "COLD", "recency_days": 99.0,
             "owner_queue": True, "sensitive": True}
    previous = {"selftest-ordinary": {"tier": "ACTIVE", "on_you": False},
                CANARY: {"tier": "ACTIVE", "on_you": False}}

    events, skipped, taken = alerts.evaluate([ordinary, decoy], previous)
    if not events:
        findings.append(
            "the alert evaluation fired nothing on a case built to fire two "
            "rules, so this step asserted an absence over an empty set - "
            "which asserts nothing (DP87).")
        return findings, asserted
    asserted += 1
    if skipped != 1:
        findings.append(
            "one sensitive project was collected and evaluate() reported %d "
            "skipped. The count is what tells the user on their own machine "
            "that something was held back." % skipped)
    asserted += 1

    for event in events:
        if event.project == CANARY:
            findings.append(
                "an alert fired for a project marked sensitive. A sensitive "
                "entry is not evaluated at all on this surface - not "
                "withheld after the fact, not counted, not named.")
    if CANARY in taken:
        findings.append(
            "the snapshot kept between runs holds a sensitive project's "
            "tier. Remembering when a sensitive project was last active is a "
            "record of that project's activity, kept by a feature that may "
            "not read it.")
    asserted += 1

    surfaces = []
    for event in events:
        try:
            payload = alerts.build(event, unattended=True)
        except alerts.DisclosureMismatch as exc:
            findings.append("an alert that fired did not become a payload "
                            "(%s), so nothing about it was searched." % exc)
            continue
        surfaces.append(alerts.canonical(payload).decode("utf-8"))
    stream = io.StringIO()
    with contextlib.redirect_stdout(stream):
        cli._deliver_locally(events, skipped, home)
    local = stream.getvalue()
    if not surfaces:
        findings.append("no alert payload was produced, so the decoy was "
                        "never looked for.")
    for text in surfaces:
        if CANARY in text:
            findings.append(
                "a sensitive project's id appears in an alert payload.")
        if "withheld" in text or "skipped" in text:
            findings.append(
                "an alert payload carries a count of what was withheld. "
                "Alerts go one at a time to a place other people may read, "
                "and a number that moves across that stream is a way of "
                "saying that something happened (murscope.alerts).")
    if CANARY in local:
        findings.append("a sensitive project's id was printed by the local "
                        "delivery.")
    if str(skipped) not in local:
        findings.append(
            "the local delivery did not print the number of sensitive "
            "projects it skipped. That count is what the alert payload gives "
            "up, so the surface that keeps it has to actually print it.")
    asserted += 1

    # **The sentence is the one prose row in the table**, so it is the one
    # place a future edit could put a project's own words on the wire under
    # a heading saying it cannot happen. `build()` recomputes it from the
    # declared fields and refuses a payload where the two differ, and the
    # only honest way to test that is to make them differ: `sentence_for`
    # is replaced by one that carries a ledger line into the first call and
    # tells the truth on the recompute, which is exactly the shape the
    # guard exists for. Restored in a `finally`, so a failure here cannot
    # leave the module patched for the steps below.
    original = alerts.sentence_for
    calls = []

    def _leaking(rule, values):
        calls.append(rule)
        text = original(rule, values)
        return text + " BLOCKED: waiting on Bob" if len(calls) == 1 else text

    alerts.sentence_for = _leaking
    try:
        alerts.build(events[0], unattended=True)
        findings.append(
            "an alert whose sentence carried a line the declared fields do "
            "not produce was built rather than refused. That row is the only "
            "prose in the table and the recompute is the only thing standing "
            "between it and a project's own words.")
    except alerts.DisclosureMismatch:
        pass
    finally:
        alerts.sentence_for = original
    if len(calls) < 2:
        findings.append(
            "murscope.alerts.build() called sentence_for %d time(s). It has "
            "to compose the sentence and then recompose it from the payload's "
            "own fields, or the injection above proved nothing (DP87)."
            % len(calls))
    asserted += 1

    class _Failing(object):
        name = "selftest-failing-alerter"

        @staticmethod
        def alerts(payload, **kwargs):
            raise RuntimeError("the receiver refused the connection")

    stream = io.StringIO()
    with contextlib.redirect_stdout(stream):
        record = cli._send_one_alert(_Failing, events[0], object(),
                                     "https://example.invalid", home, "file",
                                     True)
    if record.get("status") != alerts.FAILED:
        findings.append(
            "a delivery that raised produced a record with status %r. An "
            "alert that did not arrive and left no trace saying so is the "
            "one failure this surface cannot afford." % record.get("status"))
    if not record.get("detail"):
        findings.append("a failed delivery was recorded with no reason, so "
                        "the user is told that something failed and not what.")
    if alerts.failures_since_last_success([record]) != 1:
        findings.append(
            "a failed delivery is not counted by failures_since_last_success, "
            "which is what every later run prints to say the channel is "
            "broken.")
    if CANARY in stream.getvalue():
        findings.append("a sensitive project's id appears in the output of a "
                        "failed delivery.")
    asserted += 1
    return findings, asserted


def main(argv=None):
    # Both runtime windows open here, on the first two lines, before any
    # step - DP69's read recorder and the network refusal. Installed once
    # and never removed: an audit hook cannot be uninstalled, which is also
    # why the read side records rather than raising.
    #
    # Together rather than one here and one four steps down. The network
    # hook used to go on inside step 4, so steps 1-3 - a full collection, a
    # full render, two explains - ran outside it while the closing line
    # said "the run". What neither window can cover is this package's own
    # imports, which are finished before this function is entered; step 4
    # and step 10 both say so rather than implying otherwise.
    READS.install()
    NETWORK.install()

    home = config.murscope_home()
    # The window opened two lines up; the permitted set opens here, on the
    # line after the home is known and before the first file is read out of
    # it. The two halves are one object for the reason DP114 records - they
    # were two, and they disagreed.
    WINDOW.permit(home, "MURSCOPE_HOME")
    settings = config.load_config(home)
    roster = config.load_roster(home)
    vocabulary = markers.resolve(settings.locale, settings.section("blockers"))

    cases, problems = load_cases()
    if cases is None:
        for line in problems:
            print("FAILED: %s" % line)
        return 1

    print("murscope selftest")
    print("  home    : %s" % home)
    print("  locale  : %s" % settings.locale)
    print("  packs   : %s" % ", ".join(vocabulary.layers["packs"]))
    print("  markers : %d resolved (%d from packs, %d added, %d disabled)"
          % (len(vocabulary.markers), len(vocabulary.layers["from_packs"]),
             len(vocabulary.layers["extra"]), len(vocabulary.layers["disabled"])))
    print("  aliases : %s" % (", ".join(vocabulary.aliases) or "none configured"))

    bad = 0
    for line in vocabulary.problems:
        print("\n  vocabulary: %s" % line)
        bad += 1

    every_pack = markers.resolve(settings.locale, {"packs": markers.available()})
    failures, counts = check_shapes(every_pack, cases)
    total = sum(counts.values())
    print("\n[1/12] the parser still reads the shipped shapes (%d case(s), "
          "all %d pack(s))" % (total, len(markers.available())))
    if failures:
        for failure in failures:
            print("  FAIL %s" % failure)
        bad += len(failures)
    else:
        print("  OK  %d declaration(s) read, %d section(s), %d owner case(s), "
              "%d refusal(s) held" % (counts["declarations"],
                                      counts["sections"], counts["owner"],
                                      counts["refusals"]))

    yours, refusal_count = check_your_vocabulary(vocabulary, cases)
    print("\n[2/12] your vocabulary does not fire on prose (%d refusal case(s), "
          "%d marker(s))" % (refusal_count, len(vocabulary.markers)))
    if yours:
        for failure in yours:
            print("  FAIL %s" % failure)
        bad += len(yours)
    else:
        print("  OK  no configured marker matched a line that is prose, a "
              "legend, or an empty heading")

    from . import i18n  # noqa: PLC0415 - only this step needs a catalog
    catalog, _ = i18n.load("en")
    # Wrapped, because the network hook now covers this step too. A refusal
    # raised inside `render.render` here would otherwise leave the process
    # on a traceback with no step ever reported - red, and unreadable.
    try:
        canary_findings, surfaces = check_sensitive_canary(
            settings, catalog, vocabulary)
    except Exception as exc:
        canary_findings, surfaces = ["step 3 did not finish (%s: %s), so the "
                                     "decoy was never looked for"
                                     % (type(exc).__name__, exc)], 0
    print("\n[3/12] a sensitive entry emits method only, measured")
    if canary_findings:
        for line in canary_findings:
            print("  FAIL  %s" % line)
        bad += len(canary_findings)
    else:
        print("  OK  the decoy in two sensitive projects' files appears in "
              "none of the %d surface(s) this run produced, and no "
              "sensitive row carries a commit subject (DP68)"
              % surfaces)
        # What the two halves are made of, because the line above states
        # them in one breath and they are not the same kind of evidence.
        # The sentence that stood here said the opposite of the code: it
        # claimed `last_subject` reaches the board by design and is not
        # tested, eight lines below the two assertions that test it, and
        # directly under an OK line saying no sensitive row carries one.
        print("      the decoy half is a real injection; the commit-subject "
              "half is two absence assertions, because no commit can be "
              "fabricated here (git commit is not on Rule 5's read-only "
              "allowlist). What is proved is that last_subject is off the "
              "whitelist and on no sensitive record.")
        print("      DP68 is settled: a sensitive project's contents do not "
              "go on the board and a commit message is contents. Putting the "
              "key back in either place turns this step red.")
        # What each half of the outbound assertion actually catches, said
        # here rather than left for an audit to work out. The decoy on the
        # outbound payload catches a rogue reader whose value lands in one
        # of the eight fields that payload carries - the same class the
        # board canary catches, over a much narrower surface. What carries
        # red line four on this surface today is the *count*: two sensitive
        # entries collected, two withheld, one ordinary row kept. Stop
        # withholding and this step goes red on the count, not on the decoy.
        print("      On the outbound payload the two halves catch different "
              "things: the decoy catches a reader whose value reaches one of "
              "the fields that payload carries, and the counts - 2 sensitive "
              "withheld, 1 ordinary kept - are what carry red line four "
              "there, because a payload of numbers has nowhere to put a "
              "sentence.")

    (collected, stand_in, errors, scanned) = check_offline(
        settings, roster, vocabulary)
    counted_network = len(NETWORK.tripped)
    print("\n[4/12] offline: a real collection and a real scan, under the "
          "network hook installed at the top of this run")
    if stand_in is not None:
        print("  note: the roster is empty, so the package's own directory was "
              "collected as a stand-in")
    # Counted, not merely printed. These lines used to scroll past above an
    # OK reading "0 network event(s) attempted" - and an audit made every
    # collection throw, which produced exactly that: a silence reported from
    # a step in which nothing ran.
    for line in errors:
        print("  FAIL  a step-4 collection or scan did not finish: %s" % line)
    bad += len(errors)
    if NETWORK.tripped:
        print("  FAIL the run reached for the network: %s"
              % ", ".join(NETWORK.tripped))
        bad += len(NETWORK.tripped)
    elif not errors and not collected:
        print("  FAIL  nothing was collected, so no code ran under the hook "
              "in this step and its silence means nothing.")
        bad += 1
    elif not errors:
        print("  OK  %d project(s) collected and %d scan candidate(s) "
              "discovered; %d network event(s) attempted anywhere between the "
              "first line of this run and here, imports excepted"
              % (collected, scanned, len(NETWORK.tripped)))

    # Before the read-location step, not after it. Step 6 asserts over every
    # read *this run* made, and a step placed below it would sit outside the
    # window that is supposed to contain the whole run - the shape DP69 and
    # DP71 each found once already.
    try:
        state_failures, state_cases, state_rules, state_wrapped = (
            check_state_accounts_for_what_it_counts(catalog))
    except Exception as exc:
        state_failures, state_cases, state_rules, state_wrapped = (
            ["step 5 did not finish (%s: %s), so nothing was asserted"
             % (type(exc).__name__, exc)], 0, 0, 0)
    print("\n[5/12] every fact the tiles count is on the row they count, "
          "measured (DP80)")
    if state_failures:
        for line in state_failures:
            print("  FAIL  %s" % line)
        bad += len(state_failures)
    elif not state_rules:
        # A table that stopped producing in-hand matches would satisfy the
        # loop by having nothing to check, and print OK. The count is the
        # part that makes "measured" a true word here.
        print("  FAIL  %d case(s) ran and no in-hand rule matched in any of "
              "them, so this step asserted nothing." % state_cases)
        bad += 1
    elif not state_wrapped:
        # The same argument one level down. Every sentence surviving to the
        # screen is only worth asserting if some case carries more of them
        # than one line holds - that is the row the old clip destroyed. A
        # table trimmed to short rows would satisfy the assertion above by
        # never reaching the path it was written for.
        print("  FAIL  %d case(s) ran and none of them carried more sub-text "
              "than a single line holds, so the wrapping this step exists to "
              "assert was never exercised." % state_cases)
        bad += 1
    else:
        print("  OK  %d case(s) across declared, curated and inferred; %d "
              "in-hand rule match(es), every one of them on its row - as the "
              "headline or verbatim in its sub-text - on the board payload "
              "and on the summary screen; %d row(s) needed more than one "
              "sub-text line and got it rather than a clip"
              % (state_cases, state_rules, state_wrapped))
        print("      DP73 is settled on the literal reading: a row holding "
              "uncommitted files is counted whatever its headline says. This "
              "is what keeps that count reconcilable from the row. A row with "
              "nothing in hand is asserted to add nothing, so the two "
              "directions are both pinned.")

    # Before the read-location step for the same reason step 5 is: this one
    # opens every locale file the build shipped, and a step placed below
    # step 10 would make those reads happen outside the window step 10
    # asserts over.
    try:
        table_failures, table_locales, table_rows, table_offsets = (
            check_the_table_lines_up_in_every_locale())
    except Exception as exc:
        table_failures, table_locales, table_rows, table_offsets = (
            ["step 6 did not finish (%s: %s), so no table was measured"
             % (type(exc).__name__, exc)], 0, 0, {})
    print("\n[6/12] the summary screen's columns line up, measured in "
          "terminal cells on this build's own locales (DP86)")
    if table_failures:
        for line in table_failures:
            print("  FAIL  %s" % line)
        bad += len(table_failures)
    elif not table_rows:
        print("  FAIL  %d locale(s) rendered and not one line carried a "
              "column, so this step asserted nothing." % table_locales)
        bad += 1
    else:
        print("  OK  %d line(s) measured across %d locale(s) (%s), and in "
              "every one of them the table's last column - the heading "
              "counted in with the rows - starts at a single cell offset"
              % (table_rows, table_locales,
                 ", ".join("%s at %d" % (locale, sorted(here)[0])
                           for locale, here in sorted(table_offsets.items())
                           if here)))
        print("      The rows are rendered from names carrying all three "
              "width classes - ASCII, accented Latin, East Asian wide - "
              "because a byte count is right about the first and a "
              "character count about the first two, and only a table "
              "holding all three tells the three apart.")
        print("      This is the same property the gate's Rule 29 asserts "
              "against the source tree, asked of the build you installed. "
              "The locales this step expects are read out of the shipped "
              "TRANSLATION_STATUS.md rather than off the directory: a "
              "locale left out of a wheel stops being listed, and 'every "
              "locale lines up' would then be true of whichever ones "
              "arrived.")

    try:
        key_findings, key_surfaces, key_file = (
            check_key_never_reaches_an_artifact(settings, catalog, vocabulary))
    except Exception as exc:
        key_findings, key_surfaces, key_file = (
            ["step 7 did not finish (%s: %s), so the decoy key was never "
             "looked for" % (type(exc).__name__, exc)], 0, None)
    print("\n[7/12] a stored key reaches no artifact, not even a traceback, "
          "measured (DP18)")
    if key_findings:
        for line in key_findings:
            print("  FAIL  %s" % line)
        bad += len(key_findings)
    else:
        print("  OK  a decoy key was stored at mode %04o under a throwaway "
              "home and appears in none of the %d surface(s) this run "
              "produced." % (keys.FILE_MODE, key_surfaces))
        print("      Those surfaces include the board files, the outbound "
              "payload, everything both streams printed - `key list` "
              "included - and the traceback of a failed request, which is "
              "where a key gets carried out inside somebody else's error "
              "message. `str()`, `repr()`, two format spellings and "
              "`json.dumps` were each asked for the value and each refused.")

    try:
        consent_findings, consent_checked = check_consent_binds_to_its_disclosure()
    except Exception as exc:
        consent_findings, consent_checked = (
            ["step 8 did not finish (%s: %s), so nothing was asserted"
             % (type(exc).__name__, exc)], 0)
    print("\n[8/12] a consent covers the disclosure it was shown, and only "
          "that one")
    if consent_findings:
        for line in consent_findings:
            print("  FAIL  %s" % line)
        bad += len(consent_findings)
    elif consent_checked < 4:
        print("  FAIL  only %d of the 4 consent behaviours were reached, so "
              "this step asserted less than it claims." % consent_checked)
        bad += 1
    else:
        print("  OK  %d field(s) disclosed; an unrecorded consent covers "
              "nothing, a recorded one covers the request it was recorded "
              "for, and it stops covering it when one field is added or when "
              "the destination changes." % len(outbound.fields()))
        print("      That is the point of the fingerprint. A boolean consent "
              "would let a payload grow under an answer given about a smaller "
              "one, and nothing would go red; here the refusal names the "
              "field that appeared.")

    # Before the read-location step for the reason step 5 is: step 10 asserts
    # over every read this run made, and anything below it would sit outside
    # the window that is supposed to contain the whole run. This step reads
    # the provider directory, which is inside this package and therefore a
    # permitted root - so it is in the window and it stays inside it.
    try:
        boundary_findings, boundary_rows, base_modules, boundary_reaching = (
            check_provider_boundary(catalog))
    except Exception as exc:
        boundary_findings, boundary_rows, base_modules, boundary_reaching = (
            ["step 9 did not finish (%s: %s), so the provider layer was never "
             "examined" % (type(exc).__name__, exc)], [], 0, [])
    print("\n[9/12] nothing this install can load is able to open a socket, "
          "measured (DP88)")
    if boundary_findings:
        for line in boundary_findings:
            print("  FAIL  %s" % line)
        bad += len(boundary_findings)
    elif not boundary_rows:
        print("  OK  %d provider module(s) are installed, all of them from the "
              "base package, and not one imports anything that can open a "
              "socket." % base_modules)
        print("      This is promise two as a fact about your disk rather than "
              "a setting: the code that would reach out is not installed. It "
              "arrives only if you ask for it, with `pip install "
              "'murscope[ai]'`, and it is a separate distribution that `pip "
              "list` will show you (DP88).")
        print("      The board this build renders carries the footer that "
              "says so. Both footer sentences were checked against the "
              "install each describes, so the one you are not on was "
              "measured too.")
    else:
        # Not a failure. The user typed `[ai]`, and what they are owed here is
        # a plain statement of what that put on their disk - naming the
        # distribution that owns each module, because "it came with murscope"
        # is exactly the sentence this arrangement exists to make false.
        print("  OK  %d provider module(s) from the base package, plus %d "
              "installed by an extra you asked for; %d module(s) here can "
              "open a socket."
              % (base_modules, len(boundary_rows), len(boundary_reaching)))
        for name, owner, hits in boundary_rows:
            print("      %-16s from %-16s %s"
                  % (name, owner,
                     ("can reach the network via %s" % ", ".join(hits))
                     if hits else "opens nothing"))
        print("      The base package's second promise describes a base "
              "install and does not describe this one, and the board's footer "
              "on this install says so rather than repeating it. Being "
              "installed is still not being enabled: nothing above runs "
              "unless config.toml names it, and nothing sends without a "
              "consent recorded against the exact fields it would send.")

    # The same call step 7 makes, on the same object, over the same window.
    # It used to be a second hand-assembled permitted set, and the two sets
    # disagreed for four milestones (DP114).
    strays = WINDOW.strays()
    print("\n[10/12] every file this run opened is inside a permitted root, "
          "measured")
    if strays:
        for path in strays:
            print("  FAIL  this run opened %s, which is outside every "
                  "throwaway home it built, outside this package, and "
                  "outside every project the roster lists." % path)
        bad += len(strays)
    else:
        # Every permitted class named, because the count is a total over all
        # of them. The line used to attach the whole number to three of the
        # seven - "a sandbox, this package, or one of the listed roots" -
        # and an audit found six of 172 reads that belonged to the four it
        # did not name. They were all permitted on purpose; the sentence
        # simply did not describe the set it was counting.
        print("  OK  %d read(s) recorded from the first line of this run "
              "onward - this package's own imports finish before the hook "
              "goes on and are the one gap." % WINDOW.counted())
        # The breakdown is generated from the permitted set this assertion
        # actually used, not written out beside it. The line it replaced
        # attached its total to three of seven classes it named by hand, and
        # an audit found six reads belonging to the four it did not - they
        # were permitted on purpose and the sentence simply described a
        # different set. A summary computed from the set cannot do that.
        print("      Every one of them was inside %s registered by this run, "
              "this package, the interpreter's own directories, or a "
              "directory the operating system owns - plus two permissions "
              "narrowed to a file rather than a tree: the single probe "
              "`tempfile` opens directly in the temporary directory, and a "
              "`.pyc` under this interpreter's cache prefix."
              % WINDOW.summary())

    schedule_findings, schedule_refusals, schedule_permitted = \
        check_schedule_boundary()
    print("\n[11/12] the one place this package writes outside "
          "MURSCOPE_HOME is a list of paths, measured")
    if schedule_findings:
        for line in schedule_findings:
            print("  FAIL  %s" % line)
        bad += len(schedule_findings)
    else:
        print("  OK  %d path(s) may be written outside MURSCOPE_HOME on this "
              "platform (%s); %d refusal(s) held against everything else, "
              "including a neighbour of each permitted path in the same "
              "directory. Nothing was written."
              % (len(schedule_permitted), sys.platform, schedule_refusals))
        # Which of the two failures this step actually catches, said
        # rather than implied. The static half is in the gate and reads
        # the guard's shape; this half reads what it does, and a guard
        # can be the right shape around the wrong comparison.
        print("      The neighbour probe is the one that matters: it is "
              "what a prefix test on ~/Library/LaunchAgents would have "
              "accepted, and a prefix test is what \"permit the "
              "directory\" means in practice. Equality refuses it.")
        print("      The reverse is asserted too - guard_write_path() "
              "refuses %d scheduling path(s). Two boundaries that leak "
              "into each other are one boundary with a longer sentence."
              % len(schedule_permitted))

    # After step 10 for the same reason step 11 is: it opens no file. Every
    # input below is built in memory - records, a snapshot, a stub whose
    # `alerts` callable raises before anything could open a socket - so
    # nothing here belongs inside the read window, and nothing here reaches
    # the network hook either.
    try:
        alert_findings, alert_asserted = check_alert_boundary(home)
    except Exception as exc:
        alert_findings, alert_asserted = (
            ["step 12 did not finish (%s: %s), so neither the sensitive decoy "
             "nor the failed delivery was ever looked for"
             % (type(exc).__name__, exc)], 0)
    print("\n[12/12] a sensitive project cannot reach an alert, and a "
          "delivery that fails is recorded as failed, measured (DP125)")
    if alert_findings:
        for line in alert_findings:
            print("  FAIL  %s" % line)
        bad += len(alert_findings)
    elif alert_asserted < 6:
        print("  FAIL  only %d of the 6 alert behaviours were reached, so "
              "this step asserted less than it claims." % alert_asserted)
        bad += 1
    else:
        print("  OK  a decoy project whose id is the canary and whose "
              "previous tier would fire both rules produced no alert, no "
              "entry in the snapshot kept between runs, and no occurrence "
              "anywhere in the payloads or in what the local delivery "
              "printed.")
        print("      The payloads were also searched for a *count* of what "
              "was withheld, which the daily note carries and an alert "
              "deliberately does not: alerts leave one at a time to a place "
              "other people may read, and a number that moves across that "
              "stream is a way of saying something happened. The count is "
              "printed locally instead, and that was asserted too.")
        print("      Two injections, not one absence: a sentence carrying a "
              "ledger line the declared fields do not produce was refused "
              "rather than built, and a provider whose delivery raised came "
              "back as a recorded failure with a reason - because an alert "
              "that did not arrive and left no trace reads, from every angle "
              "afterwards, like a quiet week.")

    # Nothing below step 4 reaches for a socket, and "nothing below" is the
    # kind of sentence this project keeps finding to be false, so it is
    # measured rather than assumed.
    late = NETWORK.tripped[counted_network:]
    if late:
        print("\n  FAIL  the run reached for the network after step 4 "
              "reported: %s" % ", ".join(late))
        bad += len(late)

    print()
    if bad:
        print("FAILED: %d problem(s). A false positive above is the one that "
              "matters most: it sends you to a project that is fine." % bad)
        return 1
    # Two claims, and only the second one has no shelf life.
    #
    # The first is about **the code paths this run walked**. It is scoped
    # to them on purpose: this command never loads a provider and never
    # calls one - `providers.load()` and `contribute()` live in
    # `cli.run` - so it would stay true word for word on an install
    # carrying a provider that sends every night. A sentence that is true
    # for the wrong reason is exactly how M2's network hook ended up
    # installed in step 4 while the closing line generalised its silence
    # to "the run", and an injected call in `render.build_document` came
    # back green. The lesson is not "widen the window" - it is "say what
    # the window contains", so this line no longer says "everything".
    #
    # The second is about **what is on this disk**, which is the claim
    # DP88 bought and the one that survives an extra being installed,
    # because it describes the installation rather than the run.
    print("OK: the parser holds on %d shipped case(s), your %d-marker "
          "vocabulary fires on none of the %d prose cases, and the code "
          "paths this run walked after its own imports - two collections, "
          "two renders, two explains, a scan and a `key list` - made no "
          "network attempt."
          % (total, len(vocabulary.markers), refusal_count))
    # **What this window does not contain**, named rather than left for a
    # reader to work out from what is missing (DP93). Three commands in
    # this product open a socket on purpose - `murscope contributions`,
    # `murscope daily --send` and `murscope alert --send`, the last of
    # which the scheduled `murscope-alert` runs with nobody present - and
    # none of them is run here or by anything here. Step 12 above drives
    # the alert path deliberately short of its transport: the stub it
    # hands the delivery to raises before a socket could exist, which is
    # what lets that step run inside this window at all. That is the whole resolution of the conflict the
    # network hook created: the hook refuses every socket event for this
    # process, a sending provider needs one, and rather than weakening the
    # hook - which DP90 ruled out in advance in its most tempting form -
    # the sending lives in commands this process does not enter. The price
    # is that their sockets are outside this measurement, and the price is
    # stated here because the failure this line has found seven times is a
    # guard whose sentence is wider than its window.
    print("    What that sentence does not cover: `murscope contributions`, "
          "`murscope daily --send` and `murscope alert --send` - which the "
          "scheduled `murscope-alert` runs with nobody present. All three "
          "open a socket by design and none is run by this command. Nothing "
          "here loads a provider or calls one, so their silence is not being "
          "claimed - what is claimed above is that collecting, rendering, "
          "explaining and scanning reach for nothing. Step 12 does drive the "
          "alert path, with a stub that raises where a transport would be.")
    if boundary_reaching:
        print("    That is a statement about this run, not about this "
              "install. Step 9 found %d module(s) here that can open a "
              "socket (%s), installed by an extra you asked for. Nothing "
              "runs unless config.toml names it and nothing sends without a "
              "consent recorded against the exact fields it would send - but "
              "\"murscope makes no network call\" describes a base install, "
              "and this is not one. The board's footer says so too."
              % (len(boundary_reaching),
                 ", ".join(name for name, _owner, _hits in boundary_reaching)))
    elif not boundary_findings:
        print("    And nothing installed here could have reached the "
              "network whatever it had been asked to do - which is the "
              "claim that keeps (step 9). The line above is about the code "
              "paths this run walked; that one is about what is on this "
              "disk, and an extra cannot be installed without changing it.")
    if key_file is not None:
        print("    Your keys, if you store any, live beside that board at "
              "mode %04o and go into no artifact this command could find "
              "(step 7)." % keys.FILE_MODE)
    return 0
