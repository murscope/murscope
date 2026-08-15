"""Run every check in scripts/checks/ and aggregate the exit codes.

CI calls this. Contributors run it before opening a pull request.

A check is any Python file in scripts/checks/. It must print its own
findings to stdout and exit 0 on success, non-zero on failure. There is
deliberately no "skip" exit code: a check whose target does not exist yet
inspects what is present and passes on the facts, so the skipped count is
structurally zero and is printed to prove it.

The number of checks is not a matter of opinion. It is recorded in
scripts/checks_manifest.json and asserted here, because deleting a check
along with its rule and regenerating the manifest otherwise produces a
green gate with a smaller number in it - and a number that only a human
reading the summary would notice is a claim, not a check (DP25).

Pure stdlib. Reads nothing outside this repository. Makes no network
call.

The selftest runs **twice**, on an empty roster and on a roster holding a
fabricated project, because for five milestones it only ever ran on the
first and the two are different code paths (DP114).

Fails when: either `murscope selftest` run exits non-zero; any check exits
non-zero; scripts/checks/ is empty or
missing; the manifest is missing or unreadable; the number of check
scripts present differs from the expected_check_count the manifest
records; or the fabricated roster project cannot be written outside the
throwaway home, which would make the second run measure nothing the first
one did not.
"""
from __future__ import annotations

import json
import os
import subprocess
import tempfile
import sys
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent
CHECKS_DIR = SCRIPTS_DIR / "checks"
MANIFEST = SCRIPTS_DIR / "checks_manifest.json"


# A project, fabricated file by file, for the second selftest run. Same
# shape and same reason as the selftest's own fixtures: `git init` is not
# on Rule 5's read-only allowlist and will not be added for a test, so the
# layout is written directly and `git status --porcelain` really runs in
# it. The names are invented; nothing here touches the owner's workspace.
FIXTURE_PROJECT = (
    (".git/HEAD", "ref: refs/heads/main\n"),
    (".git/config", "[core]\n\trepositoryformatversion = 0\n\tbare = false\n"),
    (".git/refs/heads/.keep", ""),
    (".git/objects/info/.keep", ""),
    ("NOTES.md", "# Gate fixture\n\n- [ ] one\n- [ ] two\n"),
    ("README.md", "# Gate fixture\n\nA synthetic project, listed so that the "
                  "selftest has a roster to read.\n"),
)


def build_fixture_roster(home, work):
    """Write a roster naming one fabricated project. Returns (root, error).

    **The project goes outside the throwaway home on purpose, and that is
    asserted rather than arranged and trusted.** Every path under
    `MURSCOPE_HOME` is a permitted read root for the selftest, so a fixture
    written inside the home would be permitted for a reason that has
    nothing to do with the roster - the second run would pass without ever
    exercising the permission it exists to exercise, and would report a
    green result for a measurement that did not happen (DP87).
    """
    root = Path(work) / "gate-fixture-project"
    if root.resolve() == Path(home).resolve() or _inside(root, home):
        return None, ("the fixture project would be written inside "
                      "MURSCOPE_HOME, where it is permitted whatever the "
                      "roster says. The second run would assert nothing.")
    for rel, body in FIXTURE_PROJECT:
        target = root / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(body, encoding="utf-8")
    roster = {"projects": [{"id": "gate-fixture", "name": "gate fixture",
                            "root": str(root)}]}
    (Path(home) / "roster.json").write_text(
        json.dumps(roster, indent=2) + "\n", encoding="utf-8")
    return root, None


def _inside(candidate, root):
    try:
        candidate.resolve().relative_to(Path(root).resolve())
    except ValueError:
        return False
    return True


def run_selftest(label, home):
    """One `murscope selftest`, from the source tree, against `home`."""
    print("\n--- murscope selftest (%s) ---" % label)
    sys.stdout.flush()
    result = subprocess.run(
        [sys.executable, "-m", "murscope.cli", "selftest"],
        cwd=str(SCRIPTS_DIR.parent),
        env=dict(os.environ, MURSCOPE_HOME=str(home)))
    sys.stdout.flush()
    return result.returncode != 0


def expected_count():
    """(count, error). The gate's own size, recorded where a script reads it."""
    if not MANIFEST.exists():
        return None, "scripts/checks_manifest.json is missing."
    try:
        payload = json.loads(MANIFEST.read_text(encoding="utf-8"))
    except ValueError as exc:
        return None, "scripts/checks_manifest.json is unreadable (%s)." % exc
    value = payload.get("expected_check_count")
    if not isinstance(value, int):
        return None, "scripts/checks_manifest.json records no expected_check_count."
    return value, None


def untracked_files():
    """Files on the disk that the index does not hold, or None.

    Ignored files are not among them: `.gitignore` is a statement that
    the build does not ship this, and `dist/` would otherwise make every
    run of the gate red. What is left is the genuinely unmeasured - a
    file somebody wrote, that no check reads, that a build would package.
    """
    env = dict(os.environ)
    env["GIT_OPTIONAL_LOCKS"] = "0"
    try:
        proc = subprocess.run(
            ["git", "-C", str(SCRIPTS_DIR.parent), "ls-files", "--others",
             "--exclude-standard", "-z"],
            capture_output=True, text=True, timeout=60, env=env)
    except (subprocess.TimeoutExpired, OSError):
        return None
    if proc.returncode != 0:
        return None
    return sorted(rel for rel in proc.stdout.split("\0") if rel)


def main():
    scripts = sorted(CHECKS_DIR.glob("*.py"))
    if not scripts:
        print("FAILED: no checks found in scripts/checks/.")
        return 1

    expected, error = expected_count()
    if error:
        print("FAILED: %s The gate cannot assert its own size." % error)
        return 1
    if expected != len(scripts):
        print("FAILED: scripts/checks/ holds %d check(s) but the manifest "
              "expects %d. A gate that shrinks quietly is exactly what this "
              "assertion exists to catch." % (len(scripts), expected))
        return 1

    failures = []
    for script in scripts:
        print("\n--- %s ---" % script.name)
        # Flush before handing the terminal to the child, otherwise this
        # process's buffered output lands after every child's.
        sys.stdout.flush()
        result = subprocess.run([sys.executable, str(script)])
        if result.returncode != 0:
            failures.append(script.name)
        sys.stdout.flush()

    # The runtime guards live in `murscope selftest` - the sensitive canary
    # (DP65), the socket-refusing audit hook, the DP69 read-location
    # assertion, the parser's shape cases. None of them were on the path
    # anybody walks: CI ran the gate and CLAUDE.md's pre-flight is the gate,
    # and neither ran the selftest. Putting `last_subject` back into the
    # whitelist left the gate 15/15 green with only the selftest red, so a
    # contributor following the documented discipline would never reach that
    # guard.
    #
    # It runs here rather than as a second pre-flight command because one
    # command is this repository's discipline, and a discipline with two
    # commands is a discipline where somebody runs one of them. The
    # installed-package dimension is real and is covered in CI, which builds
    # a wheel and runs the same command from outside the checkout - that
    # step needs a build and a virtual environment, which is too slow to put
    # in front of every commit, and its unique value is packaging rather
    # than behaviour. Both paths exist; neither is the only one.
    #
    # **Twice, and the second run is the one this paragraph is about.** For
    # five milestones the only selftest the gate ever ran had an empty
    # roster, because a throwaway home is the easy thing to hand it. That is
    # not the shape any user is in: `murscope init` writes a roster, step 4
    # then collects those projects, and step 6's read-location assertion did
    # not permit them - so `selftest` exited 1 on every machine that had run
    # `init`, and the gate could not see it because the gate never ran
    # `init`. A guard the discipline walks past is the failure this file was
    # written to remove, and an empty-roster-only run walked past this one
    # (DP114).
    #
    # Both runs are kept rather than the second replacing the first: with an
    # empty roster step 4 collects the package directory as a stand-in, and
    # that branch would otherwise stop being exercised anywhere but CI. One
    # run costs under a second.
    selftest_failed = False
    with tempfile.TemporaryDirectory() as home:
        selftest_failed |= run_selftest("empty roster", home)

    listed = 0
    with tempfile.TemporaryDirectory() as home, \
            tempfile.TemporaryDirectory() as work:
        root, error = build_fixture_roster(home, work)
        if error:
            print("\n--- murscope selftest (roster of 1) ---")
            print("FAILED: %s" % error)
            selftest_failed = True
        else:
            listed = 1
            selftest_failed |= run_selftest("roster of 1 fabricated project",
                                            home)

    passed = len(scripts) - len(failures)
    # The selftest is counted apart from the checks, because it is not one
    # of them: it is the shipped command, run here so the runtime guards sit
    # on the path the discipline actually walks. Folding it into the check
    # count would misreport both numbers - the first version of this did,
    # and printed "1 of 15 check(s) red - murscope selftest".
    if failures or selftest_failed:
        if failures:
            print("FAILED: %d of %d check(s) red - %s"
                  % (len(failures), len(scripts), ", ".join(failures)))
        if selftest_failed:
            print("FAILED: murscope selftest is red. The runtime guards live "
                  "there - the sensitive canary, the network audit hook, the "
                  "read-location assertion - and a green gate beside a red "
                  "selftest is not a green pre-flight.")
        print("Summary: %d of %d check(s) passed, 0 skipped; murscope "
              "selftest %s."
              % (passed, len(scripts), "red" if selftest_failed else "green"))
        return 1
    # Every check here measures `git ls-files`. The build measures the
    # disk. A file that is on the disk and not in the index sits in the
    # gap: invisible to all 37 of them and shipped by the wheel anyway.
    # That is not hypothetical - `extras/murscope-ai/LICENSE` was
    # untracked through five consecutive green gates while it was already
    # inside the built artifact, and the only runner that caught it was
    # CI, because CI is the only one that starts from a clean checkout
    # (DP176). So the gate says which tree it measured rather than
    # letting "OK" stand for the disk.
    unmeasured = untracked_files()
    if unmeasured is None:
        print("FAILED: git could not be asked which files are untracked, so "
              "this run cannot say whether the tree it measured is the tree "
              "on disk. Every check here reads `git ls-files` (DP176).")
        return 1
    if unmeasured:
        print("FAILED: %d file(s) are on the disk and not in the index, so no "
              "check here has read them - and a build reads the disk:"
              % len(unmeasured))
        for rel in unmeasured:
            print("    %s" % rel)
        print("Track them or ignore them, then run this again. A green line "
              "under an untracked file is a statement about the index worn as "
              "a statement about the disk, which is how a distribution shipped "
              "a file the gate had never seen (DP176).")
        return 1
    print("OK: %d check(s) passed, 0 failed, 0 skipped, and murscope "
          "selftest green on both an empty roster and a roster of %d "
          "fabricated project outside MURSCOPE_HOME." % (passed, listed))
    return 0


if __name__ == "__main__":
    sys.exit(main())
