"""Rule 38: the published history carries no personal address.

Rule 37 reads every file a stranger receives and asks whether it names a
real person. It found nothing in the founding derivation and it was
right about the files - and the root commit of the public repository
carried the owner's personal email address in its author and committer
fields, where no file did. `git log` disagreed with `git ls-files` and
only one of them was being read.

**A commit is not a file, and that is the whole of the gap.** Rule 37's
window is `git ls-files`; the address lived in object metadata, which is
published, cloned, and served by the host's API to anyone who asks. The
same shape as DP176 one level over: there the gate read the index while
the build read the disk, here the gate reads files while a clone carries
history. Every guard in this line has a window, and this is the third
time the window was the defect (DP179).

**The criterion is positive and needs no seed.** It asserts what every
published commit *must* be - an address at the host's noreply domain -
rather than listing addresses that must not appear. A list would be the
worse of two designs for a reason this repository has already paid for
once: a rewrite that removes a URL has to quote the URL, so a check that
forbade a particular address would publish that address in its own
source (DP169, and DP161 for the brand before it). Nothing here knows
the owner's address and nothing here needs to.

**The domain is constructed, not written down.** The host comes from
`git remote get-url origin` the way Rule 35 reads it, and the noreply
domain is `users.noreply.<host>`. A constant here would be a second copy
of a fact about the clone, correct in one place and quietly wrong in
another.

**The mode is stated and never skipped.** The development repository's
own history carries real addresses in nearly every commit and always
will - it is where the work happens and its history is not published.
Run there, this check says which tree it is in, says what it therefore
did not assert, and passes. It does not skip: a skipped check is one
this line has spent five milestones learning not to trust, because a
skip and a pass are the same green to everybody reading the summary.
Which tree it is in comes from the derivation spec, the same question
Rule 35 and Rule 36 both ask.

**The criterion is proved on a known positive, every run and in both
modes.** A fabricated address at a domain that is not the noreply one is
assembled at run time and the criterion has to reject it; if it does
not, this check is red before it reads a single commit. The address is
invented here and belongs to nobody, and the real one is never written
into this file for the same reason the criterion is positive.

The positive is an address rather than a repository, deliberately.
Building one would mean `git init` and `git commit` inside the gate, and
this repository has already decided against that: `run_checks.py` writes
its fixture project's layout out by hand precisely because `git init` is
not a read-only subcommand and will not be added for a test. So what is
proved here is the predicate every commit is judged by, and what is not
proved here is the plumbing that hands commits to it - which is stated
rather than implied.

What this does not cover, stated rather than implied: it reads the
commits reachable from this clone's refs. An object that is unreachable
but not yet garbage collected is not a commit this can see, and after a
history rewrite the host keeps serving the old object by sha for a
while. The honest sentence about such a rewrite is "no longer reachable
from any ref", never "removed".

Fails when: a commit reachable in the published derivation carries an
author or committer address outside the host's noreply domain; `origin`
cannot be read, so the domain cannot be constructed; the history cannot
be read or holds no commits, so the scan would report clean having
looked at nothing (DP87); or the criterion fails to reject the
fabricated positive, which would make its silence meaningless.
"""
from __future__ import annotations

import importlib.util
import os
import re
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
SPEC_PATH = REPO_ROOT / "scripts" / "public_tree.py"

# `owner/name` on a host, the shape Rule 35 reads an origin URL with.
REPO_IN_URL = re.compile(
    r"^https?://(?P<host>[A-Za-z0-9.-]+)(?::\d+)?/"
    r"(?P<owner>[A-Za-z0-9._-]+)/(?P<name>[A-Za-z0-9._-]+?)(?:\.git)?/?$")
SCP_REMOTE = re.compile(
    r"^[A-Za-z0-9._-]+@(?P<host>[A-Za-z0-9.-]+):(?P<path>.+?)(?:\.git)?/?$")

RECORD = "%H%x1f%an%x1f%ae%x1f%cn%x1f%ce"

DOMAIN_MARK = "domain:"
SEPARATOR = "--"


def git(args, cwd=None):
    """A read-only git call under Rule 5's locked environment, or None."""
    env = dict(os.environ)
    env["GIT_OPTIONAL_LOCKS"] = "0"
    try:
        proc = subprocess.run(
            ["git", "-C", str(cwd or REPO_ROOT)] + args,
            capture_output=True, text=True, timeout=60, env=env)
    except (subprocess.TimeoutExpired, OSError):
        return None
    if proc.returncode != 0:
        return None
    return proc.stdout


def origin_host():
    """The host this clone's `origin` points at, or None."""
    url = git(["remote", "get-url", "origin"])
    if not url:
        return None
    url = url.strip()
    scp = SCP_REMOTE.match(url)
    if scp and "://" not in url:
        url = "https://%s/%s" % (scp.group("host"), scp.group("path"))
    match = REPO_IN_URL.match(url)
    return match.group("host").lower() if match else None


def noreply_domain(host):
    """The host's own no-reply domain, constructed from the host."""
    return "users.noreply.%s" % host


def permitted(address, domain):
    """Is this an address at the host's no-reply domain?"""
    return address.lower().endswith("@" + domain)


def detect(payload):
    """Findings for a seeded document: addresses that are not at the domain.

    Pure, and seeded from the payload rather than from `origin`, so a
    fixture can hand it a fabricated host and fabricated commits. The
    payload is a `domain: <host no-reply domain>` line, a `--` line,
    then one commit per line as `<sha> <author> <committer>`.

    `main()` builds exactly this payload from `git log` and calls this
    function, so the fixture drives the code the real run uses rather
    than a parallel copy of it.

    A payload with no domain, or with no commit in it, is a finding
    rather than a clean result: a criterion with nothing to compare
    against and a scan with nothing to scan both report every commit
    clean (DP87).
    """
    text = payload.decode("utf-8", errors="replace")
    lines = text.splitlines()
    domain = None
    body = []
    for index, line in enumerate(lines):
        stripped = line.strip()
        if stripped.lower().startswith(DOMAIN_MARK):
            domain = stripped[len(DOMAIN_MARK):].strip().lower()
            continue
        if stripped == SEPARATOR:
            body = lines[index + 1:]
            break
        body = lines[index:]
        break

    findings = []
    if not domain:
        findings.append(
            "the payload declares no no-reply domain, so every address in "
            "it would be judged against nothing and pass (DP87)")
        return findings

    seen = 0
    for line in body:
        stripped = line.strip()
        if not stripped:
            continue
        parts = stripped.split()
        if len(parts) != 3:
            findings.append(
                "%r is not a commit record of `<sha> <author> <committer>`, "
                "so it was read by nothing" % stripped)
            continue
        sha, author, committer = parts
        seen += 1
        for role, address in (("author", author), ("committer", committer)):
            if not permitted(address, domain):
                findings.append(
                    "%s: %s address is not at %s. A published history is "
                    "cloned, mirrored and served by the host's API, so an "
                    "address here reaches at least as far as the same "
                    "address in a file would - and Rule 37 reads files."
                    % (sha[:12], role, domain))
    if not seen:
        findings.append(
            "the payload holds no commit record, so nothing was examined "
            "and a clean result would mean nothing (DP87)")
    return findings


def load_spec():
    if not SPEC_PATH.is_file():
        return None
    spec = importlib.util.spec_from_file_location(
        "murscope_public_tree_addresses", str(SPEC_PATH))
    module = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(module)
    except BaseException:
        return None
    return module


def is_derivation(spec):
    """Is the tree this check runs in already the published derivation?

    Read off the exclusion table rather than from a constant of its own,
    the way Rules 35 and 36 ask the same question: the development tree
    is the one that still holds what the derivation withholds.
    """
    return not any((REPO_ROOT / prefix.rstrip("/")).is_dir()
                   for prefix, _ in spec.EXCLUDED)


def commits(cwd=None):
    """(sha, author name, author email, committer name, committer email)."""
    out = git(["log", "--all", "--format=" + RECORD], cwd=cwd)
    if out is None:
        return None
    rows = []
    for line in out.splitlines():
        if not line.strip():
            continue
        parts = line.split("\x1f")
        if len(parts) == 5:
            rows.append(tuple(parts))
    return rows


def known_positive(domain):
    """An address the criterion must reject, assembled at run time.

    Assembled from pieces rather than written as a literal, the way Rule
    37 builds its probes: a literal address in a published check is an
    address in the published tree. It is fabricated and belongs to
    nobody - the only property that matters is that it is not at the
    no-reply domain, which is what the criterion is about.
    """
    bad = "%s@%s" % ("a-person", "example.com")
    if permitted(bad, domain):
        return None, "the fabricated positive is itself at the no-reply domain"
    return bad, None


def main():
    spec = load_spec()
    if spec is None:
        print("scripts/public_tree.py is missing or does not import, so this "
              "check cannot tell which tree it is in - and the two modes are "
              "opposite. Refusing rather than guessing.")
        return 1

    host = origin_host()
    if not host:
        print("`origin` could not be read, so the host's no-reply domain "
              "cannot be constructed. Every address would then be judged "
              "against a domain this check invented, which is not a "
              "measurement (DP87).")
        return 1
    domain = noreply_domain(host)

    bad_address, problem = known_positive(domain)
    if problem:
        print("the known positive is unusable: %s. Its rejection would prove "
              "nothing (DP87)." % problem)
        return 1
    if permitted(bad_address, domain):
        print("the criterion accepts %r, which is not at %s. It is not "
              "measuring what it says it measures." % (bad_address, domain))
        return 1

    rows = commits()
    if rows is None:
        print("the history could not be read, so no commit was examined. A "
              "scan that looked at nothing reports every commit clean "
              "(DP87).")
        return 1
    if not rows:
        print("this tree holds no commit, so there is nothing to assert and "
              "a clean result would mean nothing (DP87).")
        return 1

    derivation = is_derivation(spec)
    if not derivation:
        print("OK: this is the development repository, and its history is "
              "not published - %d commit(s) here were counted and none was "
              "asserted against %s."
              % (len(rows), domain))
        print("    What that means, said out loud rather than skipped: the "
              "addresses in this history are the ones the work was done "
              "under, and they are correct here. The assertion below runs "
              "against the derivation, which is the tree a stranger clones. "
              "The criterion was still proved on a fabricated address at a "
              "domain that is not %s, so this run knows its matcher works "
              "even where it does not apply." % domain)
        return 0

    payload = ("%s %s\n%s\n" % (DOMAIN_MARK, domain, SEPARATOR)) + "".join(
        "%s %s %s\n" % (sha, ae, ce) for sha, _an, ae, _cn, ce in rows)
    findings = detect(payload.encode("utf-8"))
    if findings:
        for finding in findings:
            print(finding)
        print("\nFAILED: %d finding(s) over %d published commit(s)."
              % (len(findings), len(rows)))
        print("Fix: set the commit identity to the host's no-reply address "
              "and rewrite the affected commits. Note that a rewrite stops "
              "the loss rather than erasing it - the old object stays "
              "fetchable by sha for a while, so the true sentence is 'no "
              "longer reachable from any ref'.")
        return 1

    print("OK: %d published commit(s), %d address(es) - every author and "
          "committer at %s, which was constructed from this clone's own "
          "`origin` rather than written down."
          % (len(rows), 2 * len(rows), domain))
    print("    The criterion is positive and carries no seed: it asserts "
          "what an address must be, never a list of addresses it must not "
          "be. A list would publish the very address it exists to keep out "
          "of the tree, which is the shape DP169 found in a rewrite that "
          "had to quote its own target. Proved this run on a fabricated "
          "address at a domain that is not %s, and rejected." % domain)
    print("    What this does not cover: commits reachable from this "
          "clone's refs are what it read. An object that is unreachable "
          "and not yet collected is not visible here, and a host keeps "
          "serving one by sha after a rewrite - which is why a rewrite is "
          "reported as 'no longer reachable from any ref' and never as "
          "'removed'.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
