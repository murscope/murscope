"""Rule 2: all changes via pull request, verified offline from history.

Branch protection is the mechanism this rule named, and this check is
the offline replacement for it. A protection rule is a setting on a
hosting account; this reads the history that is in front of you, which
is the same evidence a reviewer has and needs no account at all.

Every commit on `main` after the founding phase must carry a pull
request reference. A squash merge leaves `(#N)` in the subject; the
GitHub merge commit says `Merge pull request #N`. Either satisfies this.

**It catches the accidental direct push and nothing more.** A determined
author can type `(#99)` into a commit subject, and no offline check can
tell that from a real merge - the reference is a convention, not a
receipt. That limit is the honest description of what this buys, and it
is worth forty lines because the failure that actually happens is
somebody pushing to main at eleven at night, not somebody forging a
reference.

**The baseline is this repository's own root commit.** This tree was
founded clean, so there is no founding phase to exempt and no
pre-existing violation to enumerate: the frozen list below is empty and
the boundary is empty, which means "start at this ref's own root". An
empty boundary is not a fallback for a named one that does not resolve -
that stays a finding, because a hash gone from history is a stale list,
and a stale list is the failure this rule refuses.

Fails when: a commit on main after the founding boundary carries neither
a `(#N)` reference nor a merge-commit reference and is not one of the
enumerated pre-existing exceptions; an enumerated exception is no longer
present in history, which means the list has gone stale; or the boundary
is empty and the ref has no single root commit to start from.
"""
from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent

# Empty: this ref's own root commit. This repository was founded from a
# clean tree, so there is no founding phase to exempt and no commit to
# name here - the first commit is the founding one and everything after
# it went through review like anything else.
FOUNDING_BOUNDARY = ""

# Pre-existing violations, frozen and empty. There are none in this
# repository: it was founded from a clean tree, so the first commit is
# the founding one and everything after it went through review. The
# table stays because the rule it belongs to does - an exception is
# written down rather than absorbed into the boundary.
GRANDFATHERED = {}

# A parenthesised reference, or a GitHub merge commit. Deliberately NOT a
# bare `#N` anywhere in the subject: this repository's commit messages
# routinely cite decision and rule numbers, so an audit walked a direct
# push through with the subject "Fix crash reported in #3". A convention
# that any sentence can satisfy by accident is not a convention.
REFERENCE = re.compile(r"\(#\d+\)$|\(#\d+\)\s|Merge pull request #\d+")

# The rule is about `main`, so the check reads `main` - not HEAD. On a
# feature branch HEAD carries commits that have not been merged yet and
# legitimately have no reference: they get one when they are squashed.
# Reading HEAD would turn every branch red for doing the right thing,
# which is how a check gets deleted. `origin/main` first because a local
# `main` can lag.
MAIN_REFS = ("origin/main", "main")

# Rule 5's environment pairing applies to repository tooling too: this
# reads history and must not write an index while doing it (DP31).
GIT_ENV_KEY = "GIT_OPTIONAL_LOCKS"


def main_refs():
    """Every ref that stands for `main` here, both if both exist.

    It used to return the first of `origin/main`, `main` - and an audit
    committed straight to local `main` in a clone, where `origin/main` was
    one commit behind and clean, so the check read the clean one and passed.
    **The check was blind at the only moment it was still free**: before
    the push.

    So both are read and a violation on either is a finding. DP62's
    concern was `HEAD`, which carries un-merged branch commits that
    legitimately have no reference yet; local `main` carries commits that
    are on main, which is exactly what this rule is about.
    """
    import os  # noqa: PLC0415 - kept beside the call that needs the env
    env = dict(os.environ, GIT_OPTIONAL_LOCKS="0")
    found = []
    for ref in MAIN_REFS:
        try:
            proc = subprocess.run(
                ["git", "-C", str(REPO_ROOT), "rev-parse", "--verify",
                 "--quiet", ref],
                capture_output=True, text=True, timeout=15, env=env)
        except (subprocess.TimeoutExpired, OSError):
            return []
        if proc.returncode == 0 and proc.stdout.strip():
            found.append(ref)
    return found


def root_commits(ref):
    """Every parentless commit reachable from `ref`, or None on failure."""
    import os  # noqa: PLC0415 - kept beside the call that needs the env
    env = dict(os.environ, GIT_OPTIONAL_LOCKS="0")
    try:
        proc = subprocess.run(
            ["git", "-C", str(REPO_ROOT), "rev-list", "--max-parents=0", ref],
            capture_output=True, text=True, timeout=30, env=env)
    except (subprocess.TimeoutExpired, OSError):
        return None
    if proc.returncode != 0:
        return None
    return [line.strip() for line in proc.stdout.splitlines() if line.strip()]


def boundary_for(ref):
    """(boundary, problem) - where this rule starts counting on `ref`.

    A named boundary is returned as written; resolving it is `git log`'s
    job, and a name that no longer resolves is the stale-list finding
    this rule already makes rather than something to route around.

    An empty boundary is the clean-tree case and is resolved here to the
    ref's own root commit. Two roots is a finding rather than a guess: a
    grafted history has no single founding, and picking one of them
    would silently exempt everything on the other.
    """
    if FOUNDING_BOUNDARY:
        return FOUNDING_BOUNDARY, ""
    roots = root_commits(ref)
    if roots is None:
        return None, ("git could not list the root commit(s) of %s" % ref)
    if len(roots) != 1:
        return None, ("%s has %d root commit(s); an empty founding boundary "
                      "means 'this ref's own root', and that is not a single "
                      "commit here" % (ref, len(roots)))
    return roots[0], ""


def git_log(boundary, ref):
    """`<boundary>..<ref>` as `<short sha>\\t<subject>` lines, or None."""
    import os  # noqa: PLC0415 - kept beside the call that needs the env
    env = dict(os.environ, GIT_OPTIONAL_LOCKS="0")
    try:
        proc = subprocess.run(
            ["git", "-C", str(REPO_ROOT), "log", "--format=%h%x09%s",
             "%s..%s" % (boundary, ref)],
            capture_output=True, text=True, timeout=30, env=env)
    except (subprocess.TimeoutExpired, OSError) as exc:
        return None, str(exc)[:200]
    if proc.returncode != 0:
        return None, (proc.stderr or "").strip()[:200]
    return proc.stdout, ""


def detect(payload):
    """Findings for a `<sha>\\t<subject>` log: commits with no reference.

    Pure, so the fixture can hand it a log rather than a repository. The
    grandfathered set is applied by the caller, not here: a detector that
    knows about exceptions cannot be handed its own violating shape and
    be expected to fire.
    """
    findings = []
    for line in payload.decode("utf-8", errors="replace").splitlines():
        line = line.rstrip()
        if not line:
            continue
        sha, _, subject = line.partition("\t")
        if not subject:
            continue
        if REFERENCE.search(subject):
            continue
        findings.append(
            "%s carries no pull request reference: %r. Work lands on main "
            "through a pull request, and a squash merge leaves (#N) in the "
            "subject - if this was merged, the subject was edited."
            % (sha.strip(), subject[:80]))
    return findings


def main():
    # **Rule 2 is about work landing on `main`, and nothing lands in a
    # derivation.** What arrives here is extraction output, and the review
    # this rule exists to guarantee happened in the repository this tree
    # was derived from, before the commit that was extracted. So the mode
    # is named and the assertion is not made - and it is not skipped,
    # because a skipped check and a passed one are the same green in a
    # summary, which is a distinction this line settled long ago.
    #
    # **What that costs is stated rather than left to be found.** Between
    # the founding commit and this branch, this check was the only thing
    # standing between this `main` and a hand edit pushed straight to it -
    # accidentally, and only from the second commit onward. Nothing here
    # measures the claim PUBLICATION.md makes, that everything in this
    # tree arrived by derivation. The property that should hold is that
    # every commit is an extraction output, and **this tree cannot check
    # that about itself**: the evidence is in a repository it does not
    # have, so the assertion belongs where that repository is.
    import importlib.util
    spec_path = REPO_ROOT / "scripts" / "public_tree.py"
    spec = None
    if spec_path.is_file():
        loader = importlib.util.spec_from_file_location(
            "murscope_public_tree_pr", str(spec_path))
        module = importlib.util.module_from_spec(loader)
        try:
            loader.loader.exec_module(module)
            spec = module
        except BaseException:
            spec = None
    if spec is None:
        print("scripts/public_tree.py is missing or does not "
              "import, so this check cannot tell which tree it "
              "is in - and the two modes are opposite.")
        print("FAILED: Rule 2's check needs to know which tree "
              "it is in.")
        return 1
    if not any((REPO_ROOT / prefix.rstrip("/")).is_dir()
               for prefix, _ in spec.EXCLUDED):
        carrying = "a squash subject (#1)"
        bare = "a subject naming no pull request"
        if not REFERENCE.search(carrying) or REFERENCE.search(bare):
            print("the reference matcher cannot tell a subject "
                  "carrying `(#N)` from one that does not, so "
                  "its silence would mean nothing (DP87).")
            print("FAILED: Rule 2's check cannot prove its own "
                  "matcher.")
            return 1
        print("OK: this is the derivation, and no work lands "
              "here - what arrives is extraction output, so no "
              "commit on this branch was asserted to carry a "
              "pull request reference.")
        print("    The review this rule guarantees happened "
              "before extraction, in the repository this tree "
              "was derived from. A pull request opened and "
              "merged here would have one participant, and a "
              "review-shaped thing with no reviewer in it is "
              "what this rule's own history warns about - its "
              "first enforcement was a template checkbox, "
              "ticked every time and wrong the whole time.")
        print("    What is therefore not measured anywhere: "
              "that every commit here is an extraction output, "
              "which is what PUBLICATION.md claims. This tree "
              "cannot settle it - the evidence is the source "
              "repository, which this one does not have. The "
              "matcher was still proved on a subject carrying "
              "a reference and one that does not.")
        return 0
    refs = main_refs()
    if not refs:
        print("neither %s resolves here, so there is no main to inspect."
              % " nor ".join(MAIN_REFS))
        print("FAILED: Rule 2's check needs the branch it verifies.")
        return 1

    inspected = []
    findings = []
    present = set()
    boundaries = []
    for ref in refs:
        boundary, problem = boundary_for(ref)
        if boundary is None:
            print("cannot establish the founding boundary on %s: %s"
                  % (ref, problem))
            print("FAILED: Rule 2's check needs the boundary it counts from.")
            return 1
        boundaries.append(boundary)
        raw, problem = git_log(boundary, ref)
        if raw is None:
            print("cannot read history from %s on %s: %s"
                  % (boundary, ref, problem))
            print("FAILED: Rule 2's check needs the history it verifies. A "
                  "shallow clone must fetch with depth 0.")
            return 1
        lines = [ln for ln in raw.splitlines() if ln.strip()]
        inspected.extend(lines)
        present |= {ln.split("\t", 1)[0].strip() for ln in lines}
        for finding in detect(raw.encode("utf-8")):
            sha = finding.split(" ", 1)[0]
            if sha in GRANDFATHERED:
                continue
            entry = "%s: %s" % (ref, finding)
            if entry not in findings:
                findings.append(entry)
    named = FOUNDING_BOUNDARY or ", ".join(sorted(set(boundaries)))
    stale = sorted(sha for sha in GRANDFATHERED if sha not in present)
    for sha in stale:
        findings.append(
            "%s is listed as a pre-existing exception but is not in "
            "%s..%s any more; the frozen list has gone stale and must be "
            "trimmed in the same change that rewrote history."
            % (sha, named, ", ".join(refs)))

    for finding in findings:
        print(finding)
    if findings:
        print("FAILED: %d commit(s) on main with no pull request reference."
              % len(findings))
        return 1
    print("OK: %d commit(s) across %s since the founding boundary %s%s, every "
          "one carrying a pull request reference, plus %d enumerated "
          "pre-existing exception(s) that may not grow."
          % (len(inspected), " and ".join(refs), named,
             "" if FOUNDING_BOUNDARY else " (this ref's own root commit)",
             len(GRANDFATHERED)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
