"""Is a given tree the extraction of a commit of this repository?

`PUBLICATION.md` claims that every file in the published repository
arrived there by derivation. Nothing measured that claim. From the
published repository's second commit onward the only thing standing
between its `main` and a hand edit pushed straight to it was a check
that had just been ruled not to apply inside a derivation, and the
ruling said so rather than leaving it to be found (DP182).

**This is not a check, and it is not a network tool.** Rule 11 forbids
every module under `scripts/` from reaching the network, so the fetch
belongs to the CI workflow and the comparison belongs here. What this
file takes is two directories: a checkout of this repository, and a tree
somebody else fetched. Anybody can therefore run it offline against a
clone they made themselves, which is the point rather than a constraint
worked around. The repository argument is resolved to a directory on
disk before git is asked anything, so that parameter cannot become a
network location however it is spelled - a permission for a path and not
for a command (DP126).

**It searches, because the answer is never `HEAD`.** The published tree
is behind this one for as long as a push is held, which is the ordinary
condition and not the exception. So it walks history newest first, and
**it says how far it looked**. "No match in the last N commits" and "no
match in any commit that declares a derivation" are different sentences
and only one of them is a finding about the published repository; a
bound that answers the same way whether it read four commits or four
hundred is a step that looks like it works and measures nothing.

**It proves it can say no before anybody believes it saying yes**, on
every run rather than on the day somebody demonstrates it. One real
extraction is made twice and compared, so the comparator is seen
accepting a tree that genuinely is an extraction; then four plausible
hand edits - one file added, one file removed, one byte changed, one
permission bit flipped - are put to the same comparator, which has to
reject all four and name what it rejected each for. A comparator that has
quietly stopped comparing reports a clean match exactly as loudly as one
that looked (DP87).

**The fourth case exists because the first three were a proof of three
branches rather than of the comparator**, and acceptance demonstrated the
difference rather than describing it. `differences()` has four arms and
those mutations fired three; deleting the fourth - the one comparing the
executable bit - left every line of the proof block printing *it is
comparing*, and a published tree with one permission bit flipped was
certified as an extraction. **A proof that prints a claim it did not test
is worse than no proof**, because the sentence it prints is the one a
reader trusts. Every arm now has a case, and an arm whose case stops
firing takes the whole block red.

**And the proof is over the comparison, not over the sheet it compares.**
Rejecting four shapes says nothing about whether the sheet enumerates
every file: a walk narrowed to skip a directory drops the same paths from
both sides and every case stays green, with a falling file count as the
only trace. So each extraction is cross-checked against the count the
derivation spec reports for itself - two readers of the same tree,
asserted equal - which is the move Rule 35 made after a total that read
clean turned out to be one nobody had compared to anything (DP184).

Each commit is extracted by **its own** copy of the derivation spec,
checked out with it. The tree the published repository holds was produced
by the spec as it stood at the commit that produced it, and asking a
later spec what an earlier commit extracts to is a different question
with a similar-looking answer.

Pure stdlib. Makes no network call. Writes only into a throwaway
directory it creates, or the one it is given.

Usage:
  extraction_match.py --search <candidate-tree> [--limit N] [--ref REF]
                      [--repository DIR] [--work DIR]
  extraction_match.py --compare <checkout> <candidate-tree> [--work DIR]
  extraction_match.py --destination
"""
from __future__ import annotations

import hashlib
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import public_tree as spec

REPO_ROOT = Path(__file__).resolve().parent.parent

# Generous on purpose. The bound exists so that a search cannot run
# unboundedly, not to keep the answer cheap: an unmatched run is the
# alarm, and an alarm is allowed to be slow. Whatever it is, the run
# says which of the two sentences it earned.
DEFAULT_LIMIT = 500

# A fetched candidate is a clone and carries the directory git owns. It
# is in no tree this spec produces, and comparing it would make every run
# red for a reason that has nothing to do with the question asked.
GIT_DIR_NAME = ".git"

# The four hand edits the comparator is made to reject on every run, one
# per arm of the comparison. Plausible rather than absurd: what DP182
# leaves unmeasured is somebody pushing a small edit straight to the
# published `main`, so the proof is shaped like that and not like a tree
# with nothing in common.
PROOF_ADDED = "NOTICE.md"
PROOF_ADDED_BODY = "murscope is published under the MIT license.\n"
PROOF_CHANGE_PREFERRED = "README.md"
# A `chmod +x` on a script is the least visible hand edit of the four and
# the one no case exercised until acceptance flipped it and watched the
# tree be certified anyway.
PROOF_PERMISSION_PREFERRED = "scripts/public_tree.py"

# The count the derivation spec reports for the tree it just wrote. Read
# back and asserted against the sheet's own size, so a walk that has
# quietly narrowed is a finding rather than a smaller number nobody
# compares to anything.
SPEC_WROTE = re.compile(r"^(\d+) file\(s\) written to ", re.MULTILINE)


def git(args, cwd):
    """(returncode, stdout, stderr) from one git call. Never raises."""
    env = dict(os.environ)
    env["GIT_OPTIONAL_LOCKS"] = "0"
    try:
        proc = subprocess.run(
            ["git"] + args, cwd=str(cwd), env=env,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=300)
    except (subprocess.TimeoutExpired, OSError) as exc:
        return 1, "", str(exc)
    return (proc.returncode,
            proc.stdout.decode("utf-8", "replace"),
            proc.stderr.decode("utf-8", "replace"))


def tree_sheet(root):
    """{path: (digest, executable)} for every file in a tree.

    Flat and pure, so the comparison below is a comparison of two sheets
    and of nothing else - the same split Rule 36's check makes for the
    same reason: every verdict is then reachable from a sheet somebody
    wrote by hand, without a repository having to be in a state.
    """
    root = Path(root).resolve()
    sheet = {}
    for parent, dirnames, filenames in os.walk(str(root)):
        dirnames[:] = sorted(d for d in dirnames if d != GIT_DIR_NAME)
        for name in sorted(filenames):
            path = Path(parent) / name
            rel = path.relative_to(root).as_posix()
            if path.is_symlink():
                sheet[rel] = ("symlink -> %s" % os.readlink(str(path)), False)
            elif path.is_file():
                sheet[rel] = (
                    hashlib.sha256(path.read_bytes()).hexdigest(),
                    bool(path.stat().st_mode & 0o100))
    return sheet


def differences(extraction, candidate):
    """What separates a candidate tree from an extraction. Empty is equal.

    Pure: two sheets in, sentences out. Nothing here reads a disk, a
    repository or a clock.
    """
    findings = []
    for rel in sorted(set(extraction) - set(candidate)):
        findings.append("missing from the candidate: %s" % rel)
    for rel in sorted(set(candidate) - set(extraction)):
        findings.append(
            "in the candidate and in no extraction: %s" % rel)
    for rel in sorted(set(extraction) & set(candidate)):
        mine, theirs = extraction[rel], candidate[rel]
        if mine[0] != theirs[0]:
            findings.append(
                "contents differ: %s (extraction %s, candidate %s)"
                % (rel, mine[0][:12], theirs[0][:12]))
        elif mine[1] != theirs[1]:
            findings.append(
                "the executable bit differs: %s (extraction %s, candidate %s)"
                % (rel, "yes" if mine[1] else "no",
                   "yes" if theirs[1] else "no"))
    return findings


def extract_checkout(checkout, dest):
    """Extract a checkout with its own spec. Returns (sheet, note, problem).

    `note` is what the spec said about itself and is carried into the
    report even on success: an extraction whose spec exited non-zero
    still writes a tree, and a match against one of those is a fact a
    reader has to be told rather than one this file gets to swallow.
    """
    checkout = Path(checkout).resolve()
    dest = Path(dest).resolve()
    spec_path = checkout / "scripts" / "public_tree.py"
    if not spec_path.is_file():
        return None, None, ("carries no derivation spec, so there is no "
                            "extraction of it to compare against")
    try:
        proc = subprocess.run(
            [sys.executable, str(spec_path), "--extract", str(dest)],
            cwd=str(checkout), stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT, timeout=600)
    except (subprocess.TimeoutExpired, OSError) as exc:
        return None, None, "its derivation spec could not be run (%s)" % exc
    note = None
    if proc.returncode != 0:
        note = ("its derivation spec exited %d; the tree below was still "
                "written and is still compared, because a match against a "
                "spec that complained is a finding and not a pass"
                % proc.returncode)
    if not dest.is_dir():
        return None, note, "its derivation spec wrote no tree"

    sheet = tree_sheet(dest)
    # Two readers of the same tree. The spec counts what it wrote;
    # `tree_sheet` counts what it found. A walk that has been narrowed
    # reports a smaller number in both sheets and every comparison stays
    # green, so the only thing that catches it is a second count taken by
    # somebody else (DP184).
    stated = SPEC_WROTE.search(proc.stdout.decode("utf-8", "replace"))
    if stated is None:
        # **A cross-check that could not run is a finding, not a note.**
        # This regex couples to another file's wording, and the first
        # version treated a wording change as a note and carried on - so
        # a narrowed walk sailed through on the same screen as the note
        # saying the cross-check had not happened, under a closing line
        # that said it had. That is the defect this very assertion was
        # added to catch, reintroduced by the assertion. The availability
        # of the second reader is asserted rather than assumed, which is
        # what `--require-keyring` settled one rule over (DP150).
        return None, note, ("its derivation spec reported no file count in a "
                            "shape this can read, so there is no second "
                            "reader of the tree and nothing to assert the "
                            "walk against")
    if int(stated.group(1)) != len(sheet):
        return None, note, ("its derivation spec says it wrote %s file(s) and "
                            "this walk found %d. Two readers of one tree "
                            "disagree, so neither count is evidence about it"
                            % (stated.group(1), len(sheet)))
    return sheet, note, None


def prove_comparator(checkout, work, out):
    """Make the comparator accept a true extraction and reject three edits.

    Returns True when all four cases went the way they have to. Every
    line is printed, on every run: this is the half of DP182's condition
    that a step delivered green does not have, and a proof that only ran
    on the day of the demonstration is a proof of that day.
    """
    out("--- proving the comparator before anything it says is believed ---")
    first = Path(work) / "proof-extraction-a"
    second = Path(work) / "proof-extraction-b"
    sheet, note, problem = extract_checkout(checkout, first)
    if problem:
        out("  REFUSED: the tree being proved against %s." % problem)
        return False
    if note:
        out("  note: %s" % note)
    twin, _, problem = extract_checkout(checkout, second)
    if problem:
        out("  REFUSED: the second extraction %s." % problem)
        return False

    identical = differences(sheet, twin)
    if identical:
        out("  FAILED: extracting the same commit twice produced %d "
            "difference(s), so the derivation is not deterministic and no "
            "answer below means anything:" % len(identical))
        for line in identical[:10]:
            out("      %s" % line)
        return False
    out("  extracted twice, %d file(s) each, 0 difference(s) - the "
        "comparator accepts a tree that is an extraction" % len(sheet))

    ok = True
    for label, mutate in (("one file added", _mutate_added),
                          ("one file removed", _mutate_removed),
                          ("one byte changed", _mutate_changed),
                          ("one permission bit flipped", _mutate_permission)):
        target = Path(work) / ("proof-" + label.replace(" ", "-"))
        if target.exists():
            shutil.rmtree(str(target))
        shutil.copytree(str(first), str(target))
        described, error = mutate(target)
        if error:
            out("  REFUSED: %s could not be arranged (%s)." % (label, error))
            ok = False
            continue
        found = differences(sheet, tree_sheet(target))
        if not found:
            out("  FAILED: %s (%s) and the comparator called it an "
                "extraction. It is not comparing." % (label, described))
            ok = False
            continue
        out("  %s (%s): rejected - %s"
            % (label, described, found[0]))
    if ok:
        out("  the comparator accepted the extraction and rejected all four "
            "hand edits, naming each - one per arm of the comparison, "
            "including the permission bit that no case reached until a tree "
            "carrying one was certified as an extraction.")
        # Reached only because `extract_checkout` refuses when the second
        # reader is unavailable, so this sentence cannot be printed by a
        # run that did not do it. It names the number to say so.
        out("  and the %d file(s) above are the derivation spec's own count "
            "for the tree it wrote as well as this walk's - two readers, "
            "asserted equal, so a walk that has narrowed is a finding rather "
            "than a smaller number." % len(sheet))
    return ok


def _mutate_added(root):
    """Add one file a maintainer might plausibly have pushed by hand."""
    target = Path(root) / PROOF_ADDED
    if target.exists():
        return None, "%s is already in the tree" % PROOF_ADDED
    target.write_text(PROOF_ADDED_BODY, encoding="utf-8")
    return PROOF_ADDED, None


def _mutate_removed(root):
    """Delete one file, the way a hand edit deletes one."""
    sheet = tree_sheet(root)
    if not sheet:
        return None, "the tree is empty"
    victim = sorted(sheet)[0]
    (Path(root) / victim).unlink()
    return victim, None


def _mutate_changed(root):
    """Change exactly one byte, the way a typo fix changes one."""
    sheet = tree_sheet(root)
    candidates = [rel for rel in sorted(sheet)
                  if (Path(root) / rel).is_file()
                  and (Path(root) / rel).stat().st_size >= 64]
    if not candidates:
        return None, "no file in the tree is long enough to edit"
    rel = (PROOF_CHANGE_PREFERRED if PROOF_CHANGE_PREFERRED in candidates
           else candidates[0])
    path = Path(root) / rel
    payload = bytearray(path.read_bytes())
    offset = len(payload) // 2
    payload[offset] = 0x62 if payload[offset] != 0x62 else 0x63
    path.write_bytes(bytes(payload))
    return "%s at byte %d" % (rel, offset), None


def _mutate_permission(root):
    """Flip one executable bit, the way `chmod +x` flips one.

    The contents are untouched on purpose: this is the only shape that
    reaches the arm of the comparison that runs when two files have the
    same hash, and it is the arm that had no case until a tree carrying
    exactly this was certified as an extraction.
    """
    sheet = tree_sheet(root)
    if not sheet:
        return None, "the tree is empty"
    rel = (PROOF_PERMISSION_PREFERRED if PROOF_PERMISSION_PREFERRED in sheet
           else sorted(sheet)[0])
    path = Path(root) / rel
    mode = path.stat().st_mode
    was = bool(mode & 0o111)
    path.chmod(mode & ~0o111 if was else mode | 0o111)
    return "%s, %s" % (rel, "-x" if was else "+x"), None


def commits(source, ref, limit):
    """(shas, total, problem). Newest first, bounded, and the bound is said."""
    rc, out, err = git(["rev-list", ref], source)
    if rc != 0:
        return None, 0, ("`git rev-list %s` failed in %s: %s"
                         % (ref, source, err.strip() or out.strip()))
    shas = [line.strip() for line in out.splitlines() if line.strip()]
    return shas[:limit], len(shas), None


def is_shallow(source):
    """Does this clone hold only part of its own history?

    `git rev-list` on a shallow clone answers about what was fetched and
    says so nowhere, so the strongest sentence this file can print - no
    match in *any* commit - would be a statement about a history the run
    never had. Asked of git rather than inferred, with the marker file as
    the fallback for a git too old to answer.
    """
    rc, out, _ = git(["rev-parse", "--is-shallow-repository"], source)
    if rc == 0 and out.strip() in ("true", "false"):
        return out.strip() == "true"
    return (Path(source) / ".git" / "shallow").exists()


def subject(source, sha):
    rc, out, _ = git(["log", "-1", "--format=%s", sha], source)
    return out.strip() if rc == 0 else ""


def search(candidate, source, ref, limit, work, out):
    """Walk history for a commit whose extraction is `candidate`.

    Returns an exit code. 0 is a match, 1 is a search that ran and found
    none, 2 is a run that asserts nothing - a bound of zero, a broken
    comparator, a repository that could not be read. The three are kept
    apart because a run that made no assertion must never read as a run
    that found nothing wrong.
    """
    candidate = Path(candidate).resolve()
    source = Path(source).resolve()
    if not candidate.is_dir():
        out("REFUSED: %s is not a directory, so there is no candidate tree "
            "to compare." % candidate)
        return 2
    if not (source / ".git").exists():
        out("REFUSED: %s holds no git repository, so there is no history to "
            "search." % source)
        return 2

    candidate_sheet = tree_sheet(candidate)
    out("Candidate tree: %s" % candidate)
    out("                %d file(s), the directory git owns excluded"
        % len(candidate_sheet))
    out("Repository:     %s" % source)

    rc, resolved, err = git(["rev-parse", ref], source)
    if rc != 0:
        out("REFUSED: `%s` does not resolve in %s: %s"
            % (ref, source, err.strip()))
        return 2
    resolved = resolved.strip()
    out("Ref:            %s -> %s" % (ref, resolved[:7]))
    shallow = is_shallow(source)
    if shallow:
        out("History:        **shallow** - this clone holds only part of its "
            "own history, so `rev-list` answers about what was fetched and "
            "nothing here can see what was not.")

    if limit <= 0:
        out("Bound:          %d commit(s)." % limit)
        out("")
        out("REFUSED: a bound of %d reads no commits at all, so this run "
            "made no statement about the candidate tree. It is not a "
            "search that found nothing - it is a search that did not "
            "happen, and the two are reported differently on purpose."
            % limit)
        return 2

    shas, total, problem = commits(source, ref, limit)
    if problem:
        out("REFUSED: %s" % problem)
        return 2
    if not shas:
        out("REFUSED: no commit is reachable from `%s`." % ref)
        return 2
    out("Bound:          %d commit(s); %d reachable from `%s`, so this run "
        "%s." % (limit, total, ref,
                 "reads all of them" if total <= limit
                 else "reads the newest %d and leaves %d unread"
                      % (limit, total - limit)))
    out("")

    clone = Path(work) / "history"
    rc, _, err = git(["clone", "--quiet", "--shared", "--no-checkout",
                      "--", str(source), str(clone)], work)
    if rc != 0:
        out("REFUSED: could not make a working copy of %s to check commits "
            "out into: %s" % (source, err.strip()))
        return 2

    rc, _, err = git(["checkout", "--detach", "--force", "--quiet", resolved],
                     clone)
    if rc != 0:
        out("REFUSED: could not check out %s: %s" % (resolved[:7], err.strip()))
        return 2
    if not prove_comparator(clone, work, out):
        out("")
        out("REFUSED: the comparator did not prove itself, so nothing it "
            "would have said about the candidate tree is evidence.")
        return 2
    out("")

    out("--- searching, newest first ---")
    dest = Path(work) / "extraction"
    match = None
    compared = 0
    # Two reasons a commit is not compared, kept apart because they say
    # different things. A commit with no derivation spec has no extraction
    # for the candidate to be; a commit whose extraction this run could not
    # trust - its spec complained, or its two readers disagreed about how
    # many files it wrote - *has* one, and the run simply cannot speak for
    # it. Folding them together produced the sentence `1 did not declare a
    # derivation` about a commit that declared one perfectly well.
    no_spec = 0
    unusable = 0
    pending = []
    newest_findings = None
    newest_sha = None

    def flush():
        if not pending:
            return
        out("  %s  %d commit(s) carry no derivation spec and are not "
            "comparable" % (
                pending[0][:7] if len(pending) == 1
                else "%s..%s" % (pending[0][:7], pending[-1][:7]),
                len(pending)))
        del pending[:]

    for sha in shas:
        rc, _, err = git(["checkout", "--detach", "--force", "--quiet", sha],
                         clone)
        if rc != 0:
            flush()
            out("  %s  could not be checked out: %s" % (sha[:7], err.strip()))
            unusable += 1
            continue
        sheet, note, problem = extract_checkout(clone, dest)
        if problem:
            if "carries no derivation spec" in problem:
                pending.append(sha)
                no_spec += 1
            else:
                flush()
                out("  %s  %s" % (sha[:7], problem))
                unusable += 1
            continue
        flush()
        compared += 1
        found = differences(sheet, candidate_sheet)
        if newest_findings is None:
            newest_findings, newest_sha = found, sha
        if note:
            out("  %s  note: %s" % (sha[:7], note))
        if not found:
            out("  %s  %d file(s)  MATCH" % (sha[:7], len(sheet)))
            match = sha
            break
        out("  %s  %d file(s)  %d difference(s)"
            % (sha[:7], len(sheet), len(found)))
    flush()
    read = shas.index(match) + 1 if match else len(shas)
    out("")

    if match:
        out("MATCH: the candidate tree is the extraction of %s (%s)."
            % (match[:7], subject(source, match) or "no subject"))
        out("Read %d of the %d commit(s) reachable from `%s`, newest first, "
            "and stopped at the match. %s"
            % (read, total, ref, accounted(compared, no_spec, unusable)))
        if shallow:
            out("The %s above is what this shallow clone holds rather than "
                "the length of that history - a match is a positive fact and "
                "survives that, which is why this is a result and not the "
                "refusal an unmatched search on a shallow clone gets." % total)
        out("This names the newest commit that extracts to the candidate and "
            "not the only one: a commit that changed nothing outside what the "
            "derivation withholds extracts to the same tree as its parent, so "
            "the answer is `an extraction of` rather than `the extraction "
            "of`. Which of a tied run was pushed is not a question this tree "
            "can settle.")
        return 0

    if shallow:
        # The third sentence, and it is a refusal rather than a finding.
        # On a shallow clone `total` is what was fetched, so the exhausted
        # branch below would print "all N were read, back to X, which is
        # where that history ends" about a history that does not end
        # there - the strongest sentence this file has, reserved for a
        # finding about the published repository, printed by a search
        # that did not happen. Same principle as a bound of zero.
        out("REFUSED: no match in the %d commit(s) this shallow clone holds, "
            "from %s back to %s - and a shallow clone cannot say what it does "
            "not have. This is neither `no match in the last N` nor `no match "
            "in any`: it is a search over a history that was never fetched, "
            "and calling it either would be a claim about the published "
            "repository that nothing here measured."
            % (len(shas), shas[0][:7], shas[-1][:7]))
        out("Fetch the rest and ask again:")
        out("    git -C %s fetch --unshallow" % source)
        if newest_findings:
            out("")
            out("The newest commit that could be compared was %s, and it "
                "differs from the candidate in %d place(s):"
                % (newest_sha[:7], len(newest_findings)))
            for line in newest_findings[:20]:
                out("    %s" % line)
        return 2

    if len(shas) < total:
        out("NO MATCH in the last %d commit(s) reachable from `%s`, from %s "
            "back to %s. The bound stopped this run with %d commit(s) "
            "unread, so whether an older commit matches is a question this "
            "run did not ask."
            % (len(shas), ref, shas[0][:7], shas[-1][:7], total - len(shas)))
    else:
        out("NO MATCH in any commit reachable from `%s`: all %d were read, "
            "back to %s, which is where that history ends."
            % (ref, total, shas[-1][:7]))
    out(accounted(compared, no_spec, unusable))
    if newest_findings:
        out("")
        out("The newest commit that could be compared was %s, and it differs "
            "from the candidate in %d place(s):"
            % (newest_sha[:7], len(newest_findings)))
        for line in newest_findings[:20]:
            out("    %s" % line)
        if len(newest_findings) > 20:
            out("    ... and %d more" % (len(newest_findings) - 20))
    return 1


def accounted(compared, no_spec, unusable):
    """Every commit read, in the bucket it actually belongs to."""
    parts = ["%d were extracted and compared" % compared]
    if no_spec:
        parts.append("%d declare no derivation, so there is no extraction of "
                     "them for the candidate to be" % no_spec)
    if unusable:
        parts.append("%d declared one this run could not use and named the "
                     "reason above - those are commits this run does not "
                     "speak for either way" % unusable)
    if len(parts) == 1:
        return "All %d of them were extracted and compared." % compared
    return "Of those, " + "; ".join(parts) + "."


def compare(checkout, candidate, work, out):
    """The two-directory question, with no history in it."""
    checkout = Path(checkout).resolve()
    candidate = Path(candidate).resolve()
    if not checkout.is_dir():
        out("REFUSED: %s is not a directory." % checkout)
        return 2
    if not candidate.is_dir():
        out("REFUSED: %s is not a directory." % candidate)
        return 2
    out("Checkout:       %s" % checkout)
    out("Candidate tree: %s" % candidate)
    out("")
    if not prove_comparator(checkout, work, out):
        out("")
        out("REFUSED: the comparator did not prove itself, so nothing it "
            "would have said about the candidate tree is evidence.")
        return 2
    out("")
    sheet, note, problem = extract_checkout(checkout, Path(work) / "extraction")
    if problem:
        out("REFUSED: %s %s" % (checkout, problem))
        return 2
    if note:
        out("note: %s" % note)
    found = differences(sheet, tree_sheet(candidate))
    if not found:
        out("MATCH: %s is the extraction of %s (%d file(s))."
            % (candidate, checkout, len(sheet)))
        return 0
    out("NO MATCH: %s is not the extraction of %s. %d difference(s):"
        % (candidate, checkout, len(found)))
    for line in found[:50]:
        out("    %s" % line)
    if len(found) > 50:
        out("    ... and %d more" % (len(found) - 50))
    return 1


def parse(args):
    """(mode, options) or (None, message). Hand-rolled, like the spec's."""
    options = {"limit": DEFAULT_LIMIT, "ref": "HEAD",
               "repository": str(REPO_ROOT), "work": None}
    mode = None
    positional = []
    index = 0
    while index < len(args):
        token = args[index]
        if token in ("--search", "--compare", "--destination"):
            if mode:
                return None, "give exactly one of --search, --compare, " \
                             "--destination."
            mode = token[2:]
        elif token in ("--limit", "--ref", "--repository", "--work"):
            if index + 1 >= len(args):
                return None, "%s takes a value." % token
            index += 1
            if token == "--limit":
                try:
                    options["limit"] = int(args[index])
                except ValueError:
                    return None, "--limit takes a whole number."
            else:
                options[token[2:]] = args[index]
        elif token.startswith("-"):
            return None, "unknown option %s." % token
        else:
            positional.append(token)
        index += 1
    if mode is None:
        return None, "give one of --search, --compare, --destination."
    if mode == "destination" and positional:
        return None, "--destination takes no arguments."
    if mode == "search" and len(positional) != 1:
        return None, "--search takes exactly one candidate directory."
    if mode == "compare" and len(positional) != 2:
        return None, "--compare takes a checkout and a candidate directory."
    options["positional"] = positional
    return mode, options


def main(argv=None):
    args = list(sys.argv[1:] if argv is None else argv)
    mode, options = parse(args)
    if mode is None:
        print("usage: extraction_match.py --search <candidate> [--limit N] "
              "[--ref REF] [--repository DIR] [--work DIR]")
        print("       extraction_match.py --compare <checkout> <candidate> "
              "[--work DIR]")
        print("       extraction_match.py --destination")
        print("%s" % options)
        return 2
    if mode == "destination":
        # Where the derivation goes, read off the spec rather than written
        # down a second time. The workflow that fetches the published tree
        # asks this rather than naming a repository of its own, so the two
        # cannot drift apart with the copy that fell behind staying green.
        print(spec.DESTINATION)
        return 0

    def out(line):
        print(line)
        sys.stdout.flush()

    given = options["work"]
    if given:
        work = Path(given).resolve()
        work.mkdir(parents=True, exist_ok=True)
        if mode == "search":
            return search(options["positional"][0], options["repository"],
                          options["ref"], options["limit"], work, out)
        return compare(options["positional"][0], options["positional"][1],
                       work, out)
    with tempfile.TemporaryDirectory() as work:
        if mode == "search":
            return search(options["positional"][0], options["repository"],
                          options["ref"], options["limit"], work, out)
        return compare(options["positional"][0], options["positional"][1],
                       work, out)


if __name__ == "__main__":
    sys.exit(main())
