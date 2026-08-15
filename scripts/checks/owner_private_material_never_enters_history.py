"""Rule 15: owner private material never enters history.

The one failure in this repository that cannot be undone. Git history is
permanent and who may read a repository is a setting rather than a fact,
so a private file committed once is exposed for as long as the
repository is, unless the history is rewritten. DP164 rules that no
repository in this line is published by flipping that setting; this rule
assumes it happens anyway, because a rule that rests on a setting is not
one. Everything else here is a bug; this is a disclosure.

Four questions, because a file can be private at four different
distances from the point of no return:

  1. Is it tracked right now?
  2. Is it staged for the next commit? Staging is where this is still
     free to fix, and it is the only moment a human is likely to be
     watching.
  3. Is it in any commit on any ref? A file deleted in the tip commit is
     still in the history anybody with read access receives.
  4. Is its content sitting in the object database, reachable from
     nothing? `git add` writes a blob whether or not the commit ever
     happens, and unstaging does not remove it. The first three
     questions all ask about names; an unreachable blob has no name.

**On the severity of question 4, precisely.** `git push` transmits only
objects reachable from the refs being pushed, so an unreachable blob
does not reach the remote and this is not a live exfiltration path. It
is local hygiene and defence in depth: private content resting in
`.git/objects` on the machine, one `git commit` or one careless
`--allow-unrelated` recovery away from becoming reachable. The remedy is
a one-liner and the check reports it. A rule that overstates its own
stakes teaches people to discount it, so this one does not.

**Testing this rule creates what it forbids.** Running the acceptance
case - stage an owner-private file, confirm red, unstage - leaves that
file's blob in the object database, and question 4 will report it on the
next run. That is correct behaviour, not a bug in the test. Purge
afterwards, every time:

    git reflog expire --expire=now --all && git gc --prune=now

Question 4 matches on content rather than path, since an unreachable
blob has none. Two ways, reported as one finding:

  - Exact: the blob's own hash equals `git hash-object` of a private
    file currently on disk. No false positives, and it catches the
    acceptance case exactly.
  - Heuristic: the blob holds CJK. No tracked file in this repository
    may (Rule 3), and the owner-private material is largely Chinese, so
    a CJK blob in the object database is at minimum junk to purge. This
    one can misfire on a discarded translation fixture; the remedy is
    the same either way.

The private set is written here as a literal rather than read from
.gitignore. .gitignore is a convenience that can be edited in the same
commit that leaks the file; this list is covered by the freeze.

Cost: `git fsck --connectivity-only` walks the object database, which on
this repository takes about 40 ms. On a repository with a large history
it is proportionally slower, and if it ever makes the pre-flight
unusable the honest move is to scope question 4 to a separate command
rather than to drop it. Blob reads are capped (see MAX_BLOBS,
MAX_BLOB_BYTES) so a large loose-object pile cannot stall the gate.

Fails when: any path under archive/ or memory-mirror/, or BRIEF.md, is
tracked in the index, staged for the next commit, or present in any
commit reachable from any ref; or an unreachable or dangling object in
the database carries the content of a private file, or carries CJK.
"""
from __future__ import annotations

import os
import re
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent

PRIVATE_PREFIXES = ("archive/", "memory-mirror/")
PRIVATE_EXACT = ("BRIEF.md",)

PURGE = "git reflog expire --expire=now --all && git gc --prune=now"

# Bounds, so a repository with a large pile of loose objects cannot turn
# the pre-flight gate into a coffee break.
MAX_BLOBS = 500
MAX_BLOB_BYTES = 1 << 20

CJK = re.compile("[\u4e00-\u9fff\u3400-\u4dbf\u3000-\u303f\uff00-\uffef]")
FSCK_LINE = re.compile(r"^(?:unreachable|dangling)\s+(blob|commit|tree|tag)\s+([0-9a-f]{40,64})\s*$")


def is_private(path):
    if path in PRIVATE_EXACT:
        return True
    return any(path.startswith(prefix) for prefix in PRIVATE_PREFIXES)


def detect(payload):
    """Findings for a chunk of repository data: private by name or by content.

    Pure. The caller decides what the payload is - a list of paths from
    the index, the staging area or the history, or the bytes of a single
    object - and this answers the one question either way: is there
    owner-private material in here.
    """
    findings = []
    text = payload.decode("utf-8", errors="replace")

    seen = set()
    for line in text.splitlines():
        path = line.strip()
        if not path or path in seen:
            continue
        seen.add(path)
        if is_private(path):
            findings.append(
                "%s: owner-private material. Git history is permanent and "
                "read access is a setting, so this is exposed for as long "
                "as the repository is (DP40, DP164)." % path)

    match = CJK.search(text)
    if match:
        findings.append(
            "carries CJK (U+%04X); no tracked file in this repository may, and "
            "the owner-private material is largely Chinese."
            % ord(match.group(0)))
    return findings


def git(args, binary=False):
    env = os.environ.copy()
    env["GIT_OPTIONAL_LOCKS"] = "0"
    out = subprocess.run(
        ["git"] + args, cwd=str(REPO_ROOT), env=env,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if out.returncode != 0 and not out.stdout:
        raise subprocess.CalledProcessError(out.returncode, args, out.stdout, out.stderr)
    return out.stdout if binary else out.stdout + out.stderr


def private_blob_hashes():
    """git hash-object of every private file currently on disk."""
    paths = []
    for prefix in PRIVATE_PREFIXES:
        root = REPO_ROOT / prefix.rstrip("/")
        if root.is_dir():
            paths.extend(sorted(p for p in root.rglob("*") if p.is_file()))
    for name in PRIVATE_EXACT:
        candidate = REPO_ROOT / name
        if candidate.is_file():
            paths.append(candidate)
    if not paths:
        return {}
    out = git(["hash-object", "--"] + [str(p) for p in paths], binary=True)
    hashes = out.decode("utf-8", errors="replace").split()
    return dict(zip(hashes, (p.relative_to(REPO_ROOT).as_posix() for p in paths)))


def unreachable_objects():
    """(kind, sha) for every object the refs cannot reach."""
    text = git(["fsck", "--unreachable", "--dangling", "--connectivity-only",
                "--no-progress"]).decode("utf-8", errors="replace")
    found = []
    for line in text.splitlines():
        m = FSCK_LINE.match(line.strip())
        if m:
            found.append((m.group(1), m.group(2)))
    return found


def check_object_database():
    """Question 4. Reported apart from the three that ask about names."""
    bad = 0
    try:
        objects = unreachable_objects()
    except (subprocess.CalledProcessError, OSError) as exc:
        print("could not inspect the object database (%s); Rule 15 cannot be "
              "fully verified, which is a failure and not a pass." % exc)
        return 1, 0

    known = private_blob_hashes()
    inspected = 0
    for kind, sha in objects[:MAX_BLOBS]:
        if kind != "blob":
            continue
        inspected += 1
        if sha in known:
            print("unreachable blob %s is the current content of %s. `git add` "
                  "writes the blob whether or not the commit happens, and "
                  "unstaging does not remove it. [object database]"
                  % (sha[:12], known[sha]))
            print("    Not a leak: `git push` sends only objects reachable from "
                  "the refs being pushed. Purge it anyway: %s" % PURGE)
            bad += 1
            continue
        try:
            payload = git(["cat-file", "blob", sha], binary=True)[:MAX_BLOB_BYTES]
        except (subprocess.CalledProcessError, OSError):
            continue
        for finding in detect(payload):
            print("unreachable blob %s %s [object database]" % (sha[:12], finding))
            print("    Not a leak: `git push` sends only objects reachable from "
                  "the refs being pushed. Purge it anyway: %s" % PURGE)
            bad += 1
            break

    if len(objects) > MAX_BLOBS:
        print("note: %d unreachable object(s) present, only the first %d "
              "inspected. Purge them: %s" % (len(objects), MAX_BLOBS, PURGE))
    return bad, inspected


def main():
    sources = (
        ("tracked in the index", ["ls-files"]),
        ("staged for the next commit", ["diff", "--cached", "--name-only"]),
        ("in a commit on some ref", ["log", "--all", "--name-only", "--pretty=format:"]),
    )

    bad = 0
    for label, args in sources:
        try:
            payload = git(args, binary=True)
        except (subprocess.CalledProcessError, OSError) as exc:
            print("could not read paths %s (%s); Rule 15 cannot be verified, "
                  "which is a failure and not a pass." % (label, exc))
            bad += 1
            continue
        for finding in detect(payload):
            print("%s [%s]" % (finding, label))
            bad += 1

    object_bad, inspected = check_object_database()
    bad += object_bad

    if bad:
        print("\nFAILED: %d owner-private finding(s)." % bad)
        print("Fix: `git rm --cached <path>` if it is staged or tracked. If it "
              "is already in a commit, stop and rewrite the history before the "
              "repository is pushed anywhere. For unreachable objects: %s" % PURGE)
        return 1
    print("OK: no owner-private path is tracked, staged, or present in any "
          "commit on any ref, and none of the %d unreachable blob(s) in the "
          "object database carries private content." % inspected)
    return 0


if __name__ == "__main__":
    sys.exit(main())
