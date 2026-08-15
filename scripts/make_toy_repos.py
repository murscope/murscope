"""Build five toy repositories and a roster that points at them.

Acceptance for this milestone is "on a machine that has never run this
tool, pointing it at five toy repositories produces a real board". That
sentence is only checkable if the five repositories are reproducible, so
they are built by a script rather than described in prose. Each one is
shaped to land in a different cell of the five-state ladder (DP33) and,
between them, to make every one of the thirteen signals fire at least
once.

Nothing here is part of the shipped package. It writes only inside the
directory it is given - MURSCOPE_HOME, or a temp directory - and it
never touches this repository. Toy repositories must not live in the
repository and must never become nested git repositories inside it.

    python3 scripts/make_toy_repos.py --home "$(mktemp -d)"

It prints the home it used, so the next command can be pasted straight
after it.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

AUTHOR = "murscope toy"
EMAIL = "toy@example.invalid"


def run(args, cwd, days_ago=None):
    """One git command inside a toy repository, optionally backdated."""
    env = dict(os.environ)
    env["GIT_OPTIONAL_LOCKS"] = "0"
    env["GIT_AUTHOR_NAME"] = AUTHOR
    env["GIT_COMMITTER_NAME"] = AUTHOR
    env["GIT_AUTHOR_EMAIL"] = EMAIL
    env["GIT_COMMITTER_EMAIL"] = EMAIL
    if days_ago is not None:
        stamp = (datetime.now(timezone.utc) - timedelta(days=days_ago)).isoformat()
        env["GIT_AUTHOR_DATE"] = stamp
        env["GIT_COMMITTER_DATE"] = stamp
    result = subprocess.run(["git"] + args, cwd=str(cwd), env=env,
                            capture_output=True, text=True)
    if result.returncode != 0:
        raise SystemExit("git %s failed in %s:\n%s"
                         % (" ".join(args), cwd, result.stderr.strip()))
    return result.stdout


def write(root, rel, text):
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def init(root):
    root.mkdir(parents=True, exist_ok=True)
    run(["init", "--quiet", "--initial-branch=main"], root)
    run(["config", "user.name", AUTHOR], root)
    run(["config", "user.email", EMAIL], root)


def commit(root, message, days_ago):
    run(["add", "-A"], root)
    run(["commit", "--quiet", "-m", message], root, days_ago=days_ago)


def toy_declared(base):
    """Its own ledger says it is blocked, and names the owner. -> declared."""
    root = base / "toy-atlas"
    init(root)
    write(root, "README.md", "# toy-atlas\n\nA toy repository.\n")
    write(root, "LICENSE", "MIT\n")
    write(root, "pyproject.toml", "[project]\nname = \"toy-atlas\"\n")
    write(root, "tests/test_atlas.py", "def test_nothing():\n    assert True\n")
    write(root, ".github/workflows/ci.yml", "name: ci\non: [push]\n")
    write(root, "src/atlas.py",
          "# TODO: name the thing\n# FIXME: and then rename it\n"
          "def atlas():\n    return 1\n")
    commit(root, "Bring atlas up to a shape worth reading", 6)
    # Two declarations, deliberately. The generic one comes first and the
    # owner-naming one last, because ledgers are append-ordered and the
    # last marker is the current claim - and because B11 needs both
    # kinds present to show that only the second takes the badge.
    write(root, "mgmt/MGMT.md",
          "# MGMT\n\n## Current state\n\n"
          "BLOCKED: the signing key has not been minted yet.\n\n"
          "Notation: a line starting `blocked` declares a state.\n\n"
          "## Blocked\n\n"
          "<!-- move stuck items here -->\n\n"
          "## Next\n\n"
          "needs decision: whether the export stays in scope\n\n"
          "- [ ] decide the export question\n"
          "- [ ] then cut the release\n")
    commit(root, "Write down where atlas is stuck", 3)
    run(["tag", "v0.3.1"], root)
    run(["branch", "spike/export"], root)

    # A bare upstream two commits behind, so signal 4 has something to
    # count without any network anywhere.
    remote = base / "toy-atlas-upstream.git"
    run(["init", "--bare", "--quiet", str(remote)], base)
    run(["remote", "add", "origin", str(remote)], root)
    run(["push", "--quiet", "-u", "origin", "main"], root)
    write(root, "src/atlas.py",
          "# TODO: name the thing\ndef atlas():\n    return 2\n")
    commit(root, "Rework the atlas return value", 3)
    write(root, "src/atlas.py",
          "# TODO: name the thing\ndef atlas():\n    return 3\n")
    commit(root, "Rework it again", 2)
    return {"id": "toy-atlas", "name": "toy-atlas", "root": str(root)}


def toy_inferred(base):
    """Uncommitted work, untouched for ten days. -> inferred, set aside."""
    root = base / "toy-beacon"
    init(root)
    write(root, "README.md", "# toy-beacon\n")
    write(root, "package.json", "{\n  \"name\": \"toy-beacon\"\n}\n")
    write(root, "src/beacon.js", "// HACK: this is the third rewrite\n"
                                 "export const beacon = () => 1;\n")
    commit(root, "First cut of the beacon", 24)
    # A WIP-shaped subject, so signal 5 has something to detect. This toy
    # therefore trips two inference rules at once - uncommitted work gone
    # quiet, and a commit that stopped mid-thought - which is exactly the
    # case the state layer has to order rather than guess at.
    write(root, "src/beacon.js", "export const beacon = () => 2;\n")
    commit(root, "wip: half of the retry policy", 10)

    write(root, "src/parked.js", "// XXX: half of an idea\n")
    run(["add", "-A"], root)
    run(["stash", "push", "--quiet", "-m", "parked idea"], root)

    write(root, "src/beacon.js", "export const beacon = () => 3;\n")
    write(root, "src/beacon.test.js", "// nothing yet\n")
    write(root, "NOTES.md", "# Notes\n\n- [ ] decide on the retry policy\n"
                            "- [ ] write the test\n- [x] pick a name\n")
    return {"id": "toy-beacon", "name": "toy-beacon", "root": str(root)}


def toy_curated(base):
    """Clean and cold; the user wrote the reason in the roster. -> curated."""
    root = base / "toy-cinder"
    init(root)
    write(root, "README.md", "# toy-cinder\n")
    write(root, "Cargo.toml", "[package]\nname = \"toy-cinder\"\n")
    write(root, "src/main.rs", "fn main() {}\n")
    commit(root, "Start cinder", 90)
    write(root, "src/main.rs", "fn main() { println!(\"cinder\"); }\n")
    commit(root, "Print something", 41)
    return {"id": "toy-cinder", "name": "toy-cinder", "root": str(root),
            "note": {"text": "Parked until the hardware arrives.",
                     "since": (datetime.now(timezone.utc)
                               - timedelta(days=20)).date().isoformat()}}


def toy_no_source(base):
    """Not a repository, no ledger. Nothing was readable. -> no-source."""
    root = base / "toy-drift"
    root.mkdir(parents=True, exist_ok=True)
    write(root, "outline.txt", "A folder of writing, not a code project.\n")
    write(root, "draft/chapter-one.txt", "Once, there was a directory.\n")
    return {"id": "toy-drift", "name": "toy-drift", "root": str(root)}


def toy_none(base):
    """Read, computed, nothing worth saying. -> none, confidently.

    This used to be a clean git repository whose last commit was twelve
    days old. DP51 took that case away and was right to: a clean tree
    quiet for twelve days now earns rule 7 and reads "quiet 12 days,
    nothing outstanding", which is a judgment where `none` was a shrug.

    So `none` keeps the case it always described best, and the pair with
    toy-drift gets sharper rather than weaker. Both are directories
    rather than repositories; the only difference between them is whether
    there was a ledger to read. That is exactly the distinction DP20
    draws and B3 tests - "we did not look" against "we looked and found
    nothing" - and now the two toys differ by that one fact alone.
    """
    root = base / "toy-ember"
    root.mkdir(parents=True, exist_ok=True)
    write(root, "README.md", "# toy-ember\n\nSmall and finished.\n")
    # A real ledger, deliberately declaring nothing: no marker line for
    # the parser to find and no unchecked item for signal 8. It is read,
    # in full, and it says the project is fine.
    write(root, "STATUS.md",
          "# Status\n\n"
          "Shipped in March and stable since. Nothing outstanding, and\n"
          "nobody is waiting on anybody.\n\n"
          "## History\n\n"
          "- Shipped 1.0\n"
          "- Fixed the one reported defect\n")
    return {"id": "toy-ember", "name": "toy-ember", "root": str(root)}


BUILDERS = (toy_declared, toy_inferred, toy_curated, toy_no_source, toy_none)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--home", required=True,
                        help="MURSCOPE_HOME to populate with config and roster")
    parser.add_argument("--toys", default="",
                        help="where the repositories go; default <home>-toys")
    parser.add_argument("--force", action="store_true",
                        help="delete an existing toy directory first")
    args = parser.parse_args()

    home = Path(os.path.expanduser(args.home)).resolve()
    # B1 is "a machine that has never run this tool", so the home this
    # script is handed will routinely not exist yet. It only ever did in
    # testing because $(mktemp -d) creates it.
    home.mkdir(parents=True, exist_ok=True)
    # Beside the home, not inside it. The read-only proof is cleanest
    # when the write boundary and the monitored projects are disjoint
    # sets of directories - if the toys sit under MURSCOPE_HOME, "the
    # guard refused it" and "it was a monitored project" stop being the
    # same statement, and murscope says so at every run.
    base = (Path(os.path.expanduser(args.toys)).resolve() if args.toys
            else home.parent / (home.name + "-toys"))
    if base.exists():
        if not args.force:
            raise SystemExit("%s already exists; pass --force to rebuild it." % base)
        shutil.rmtree(str(base))
    base.mkdir(parents=True)

    entries = [builder(base) for builder in BUILDERS]
    (home / "roster.json").write_text(
        json.dumps({"projects": entries}, indent=2) + "\n", encoding="utf-8")
    (home / "config.toml").write_text(
        "# Written by scripts/make_toy_repos.py.\n"
        "locale = \"en\"\n\n"
        "[providers]\n"
        "enabled = [\"noop\"]\n", encoding="utf-8")

    print("MURSCOPE_HOME=%s" % home)
    print("%d toy repositories under %s" % (len(entries), base))
    for entry in entries:
        print("  %-12s %s" % (entry["id"], entry["root"]))
    print("\nNext:\n  MURSCOPE_HOME=%s python3 -m murscope.cli run" % home)
    return 0


if __name__ == "__main__":
    sys.exit(main())
