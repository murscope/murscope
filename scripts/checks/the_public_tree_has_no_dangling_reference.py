"""Rule 35: the public tree has no dangling reference.

`scripts/public_tree.py` says what the public repository is made of.
This check runs that derivation and reads what comes out, which is the
only way the spec can be worth anything: a written manifest nobody
executes is the same wall art Rule 1 refuses, one level up.

**What walks to this check is the extracted tree itself (DP87).** It is
not a static reading of the manifest, and it is not a grep over this
repository. The extraction runs, into a throwaway directory, and every
reference in the result is resolved against the result.

**What counts as a reference.** A path a reader or the interpreter is
asked to resolve **against the repository root** - by category, never by
a list of files:

* in markdown, a path inside an inline code span or a link target;
* in Python, a string that is joined onto the tree root - `ROOT / "x"`,
  `ROOT / "x" / "y"` - where `ROOT` is a module-level name bound to an
  ancestor of `__file__`, or another module-level name bound to such a
  join. The operand may be a literal or a module-level string constant,
  including one reached through `for name in CONSTANT_TUPLE:`, which is
  how `governed_docs_carry_frontmatter` names the directories it walks.

**And what does not.** `murscope/fingerprints.py` holds `mgmt/MGMT.md`,
`tasks/PROGRESS.md` and a dozen more. Those are **product data** - the
table by which murscope recognises a ledger in *somebody else's*
project - and they must ship exactly as they are. Nothing about them is
a reference to this repository, and the criterion separates them
without naming them: they are strings in a tuple, never joined onto this
tree's root. The same holds for the toy repositories
`scripts/make_toy_repos.py` writes, whose paths are joined onto a
fixture directory.

**A dangling reference** is one that names a path present in the source
tree and absent from the extracted tree. That is the defect this rule is
about: the derivation took something away and left a sentence pointing
at it.

**A path is not the only thing a reader is asked to resolve**, and the
audit before publication found the blind spot: both halves above read
*paths*, and `scripts/checks/all_changes_via_pr.py` carried eight commit
hashes and two pull request numbers of this repository straight into the
extracted tree without either half noticing. None of them exists in a
repository founded from a clean tree, so the check was red on its first
run there - and the same class covers the numbered coordinates the
docstrings used to carry into an unpublished design document. So there
is a third half, and it reads **coordinates**:

* a hex token that resolves to a commit *in this repository* - it will
  resolve nowhere else, and a check script naming one is the sharper
  case because it is not prose and goes red rather than merely
  misleading;
* `PR #N` and `pull request #N`, which name this repository's pull
  requests;
* `report <n>.<n>` and `task book <n>.<n>`, which read like something a
  reader could look up and name documents that are published nowhere
  (see "What the citations point at" in CONTRIBUTING.md).

A path that is in neither tree is still a different defect and is not
claimed here - it would be wrong in this repository too.

**Three halves read two file types, and that was the whole of it.** The
first half read `.md`, the second read `.py`, the third ran over
whatever those two had already opened. Everything else in the published
tree - the ignore file, the workflow, the packaging metadata, the
locales, the board - was never read by anything, and the second
pre-publication audit found what had been sitting in that gap: a comment
block describing the owner's private material by category and naming a
second private repository and a file inside a withheld directory, a CI
step that fails the job on any repository that is not private, and a
link to the development repository itself. None of it was hidden. Two
constants, `{".md"}` and `{".py"}`, were the entire reason no half
looked (DP169).

So the file-type restriction is gone. **Every file in the extracted tree
that decodes as text is read**, and the reader is chosen by what the
file is rather than the scan being skipped for want of one:

* `.md` gets the markdown reader, `.py` gets the AST walker, as before;
* everything else gets a **plain-text** reader, which has no code spans
  and no syntax to lean on and therefore looks for the one shape that
  needs none: a path-shaped token whose leading component is a directory
  the derivation withholds. The prefixes are generated from the
  exclusion table, never listed here - a list in this file would be a
  second place to keep in step with the spec, and the one that fell
  behind would be the one that stayed green;
* the coordinate half now runs over all of them, for the same reason.

**And a fifth half, which reads repositories rather than paths.** A URL
resolves against the internet and not against this tree, so no path half
can see it, and `normalise()` throws away every token containing `://`
by design. The category is stated positively: **a published file may
name the repository it is in, and no other repository on its host.**
Which repository that is comes from the derivation spec's `DESTINATION`,
and the host from `git remote get-url origin` rather than from a
constant.

**This used to be two rules wearing one sentence.** Run from the
published repository the tree being scanned *was* this repository, so
`origin` answered it; run from the development repository the tree was
bound for somewhere the spec never named, so the honest answer was
*none* and every URL on the host was a finding - including the one
naming the destination, which is correct and was reported anyway. The
spec names its destination now, so both modes ask one question of one
table and get one answer. A rule whose two modes collapse into one has
usually found its real shape; the two directions are still separable and
still tested, but they are no longer two criteria.

The mode is still read, for one thing rather than for the criterion:
when the tree already *is* the derivation, `origin` and `DESTINATION`
are two statements about the same repository and must agree. That
disagreement is reported on its own, because it means a name has gone
stale rather than that a document is wrong.

The host comes from `origin` too, which is what keeps a provider
endpoint and a DTD out of it: `api.example.com/v1/chat` has the shape of
an owner and a repository and is not on the hosting domain, and the
criterion never has to guess. What it does not cover is a repository
named in prose without a URL - a bare `owner/name` is a shape ordinary
sentences have, and a matcher that fired on one would be loosened within
a week. The rule states that limit rather than implying coverage it does
not have.

**Every half must resolve something, or prove itself another way.** A
markdown scanner that found nothing and an AST walker that resolved
nothing would report a clean tree with equal confidence, which is the
empty-graph pass DP87 names. The two path halves therefore have to come
back with at least one reference that resolved, and the counts are
printed rather than pinned (DP159). The plain-text, coordinate and
repository halves are expected to find nothing at all once the tree is
clean, so they prove themselves differently and they are the interesting
case: their matchers are run against known positives **assembled at run
time**, never written into this file, so that "found nothing" is a
result rather than a broken pattern. That is the discipline the audit
itself demonstrated, having once reported a spelling covered because it
had misspelled the probe.

Run the derivation by hand with:

    python3 scripts/public_tree.py --list
    python3 scripts/public_tree.py --extract <directory>

Fails when: a file in the extracted tree points at a path the extraction
withheld, in markdown, in Python, or in the clear in any other text
file; a file in the extracted tree carries a commit hash of this
repository, a pull request number, or a numbered coordinate into an
unpublished document; a file in the extracted tree carries a URL naming
a repository on the hosting domain other than the one that tree is; the
extraction reports a problem - a tracked file it cannot classify, or a
rewrite that matches neither the text it removes nor the text it leaves;
the extracted tree is empty; either path half of the reference scan
resolves nothing at all; a coordinate, withheld-prefix or repository
matcher fails to fire on a known positive; or `origin` cannot be read,
so the repository half has no idea which repository a file is allowed to
name.
"""
from __future__ import annotations

import ast
import importlib.util
import itertools
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
SPEC_PATH = REPO_ROOT / "scripts" / "public_tree.py"

CODE_SPAN = re.compile(r"`([^`\n]+)`")
LINK_TARGET = re.compile(r"\]\(([^)\s]+)\)")

MARKDOWN_SUFFIXES = {".md"}
PYTHON_SUFFIXES = {".py"}

# The third half. Assembled from parts where a literal would be a
# self-hit, and proved against positives built at run time so that a
# silent scan is a result rather than a typo (see the docstring).
PULL_REQUEST = re.compile(r"\b(?:PR|pull request)\s+#\d+", re.IGNORECASE)
COORDINATE = re.compile(
    r"\b(?:report(?:\s+section)?|task\s+book)\s+\d+\.\d+", re.IGNORECASE)
# Git's own abbreviation floor is 7. Forty is a full object name.
HEX_TOKEN = re.compile(r"\b[0-9a-f]{7,40}\b")

# The fifth half. A URL is thrown away by `normalise()` on purpose - it
# resolves against the internet rather than against this tree - so this
# is the only thing that reads one.
URL = re.compile(r"https?://[^\s<>()\[\]{}\"'`\\|]+", re.IGNORECASE)
# The owner and repository a URL names, if it names one. Loose on shape
# deliberately: the host is compared against `origin`'s, so a provider
# endpoint that happens to have two path segments never gets this far.
REPO_IN_URL = re.compile(
    r"^https?://(?P<host>[A-Za-z0-9.-]+)(?::\d+)?/"
    r"(?P<owner>[A-Za-z0-9][A-Za-z0-9._-]*)/"
    r"(?P<name>[A-Za-z0-9][A-Za-z0-9._-]*?)(?:\.git)?(?=[/?#]|$)",
    re.IGNORECASE)
# `git@host:owner/name.git`, which is the other form a remote takes.
SCP_REMOTE = re.compile(
    r"^(?:[A-Za-z0-9._-]+@)?(?P<host>[A-Za-z0-9.-]+):(?P<path>[^/].*)$")


def load_spec():
    spec = importlib.util.spec_from_file_location(
        "murscope_public_tree", str(SPEC_PATH))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def normalise(token):
    """A reference token as a repo-relative path, or None.

    Deliberately strict. A token has to look like a path before it is
    treated as one, because a code span is also how this repository
    writes commands, environment variables and identifiers.
    """
    token = token.strip().strip("`")
    if not token or token.startswith("#") or "://" in token:
        return None
    if token.startswith("<") or token.endswith(">"):
        return None
    token = token.split("#", 1)[0].strip()
    if token.startswith("./"):
        token = token[2:]
    token = token.rstrip("/")
    if not token or token.startswith("/") or token.startswith("~"):
        return None
    if ".." in token.split("/"):
        return None
    return token


def detect(payload):
    """Findings for one markdown document: pointers into withheld paths.

    Pure with respect to the payload; the only outside knowledge is the
    exclusion table in `scripts/public_tree.py`, which is the spec this
    rule enforces.
    """
    spec = load_spec()
    text = payload.decode("utf-8", errors="replace")
    findings = []
    for lineno, line in enumerate(text.splitlines(), start=1):
        for match in itertools.chain(CODE_SPAN.finditer(line),
                                     LINK_TARGET.finditer(line)):
            ref = normalise(match.group(1))
            if ref is None:
                continue
            reason = spec.excluded_reason(ref + "/") or spec.excluded_reason(ref)
            if reason:
                findings.append(
                    "%d: points at `%s`, which the public tree withholds: %s"
                    % (lineno, ref, reason))
    findings.extend(coordinate_findings(text))
    findings.extend(plain_text_findings(text, withheld_prefix_matchers(spec)))
    host, own = origin_repository()
    findings.extend(repository_findings(
        text, host, {own} if own and is_derivation(spec) else set()))
    return findings


def coordinate_findings(text):
    """Findings for the coordinates in a document.

    The hash half is not here: resolving a hex token needs the source
    repository, and this function is the pure one. What is here is what
    a regular expression can settle on its own.
    """
    findings = []
    for lineno, line in enumerate(text.splitlines(), start=1):
        for match in PULL_REQUEST.finditer(line):
            findings.append(
                "%d: cites `%s`, which is a pull request of the development "
                "repository. The public repository is founded from a clean "
                "tree and has no such number; a reader following it lands "
                "somewhere else or nowhere." % (lineno, match.group(0)))
        for match in COORDINATE.finditer(line):
            findings.append(
                "%d: cites `%s`, a numbered coordinate into a document that "
                "is published nowhere. It reads like something a reader can "
                "look up and is not - name the thing instead (see 'What the "
                "citations point at' in CONTRIBUTING.md)."
                % (lineno, match.group(0)))
    return findings


def withheld_prefix_matchers(spec):
    """(name, pattern, reason) for every path prefix the tree withholds.

    Generated from the exclusion table rather than listed here. A list
    in this file would be a second place to keep in step with the spec,
    and the one that fell behind would be the one that stayed green -
    which is the shape of every hole this repository has found.
    """
    matchers = []
    for prefix, reason in spec.EXCLUDED:
        name = prefix.rstrip("/")
        if not name:
            continue
        matchers.append((
            name,
            re.compile(r"(?<![A-Za-z0-9_.\-/])" + re.escape(name)
                       + r"/[A-Za-z0-9._\-/]*"),
            reason))
    return matchers


def plain_text_findings(text, matchers):
    """Findings for a file neither path half reads.

    An ignore file, a workflow, a packaging table: no code spans, no
    imports, nothing to parse. So the shape looked for is the one that
    needs no syntax at all - a path-shaped token whose leading component
    is a directory the derivation withholds. That is weaker than the two
    readers it stands in for and it is not trying to be them; it is the
    difference between reading those files and not reading them, which
    is what the file-type restriction used to cost (DP169).
    """
    findings = []
    for lineno, line in enumerate(text.splitlines(), start=1):
        for _, pattern, reason in matchers:
            for match in pattern.finditer(line):
                findings.append(
                    "%d: names `%s` in the clear, which is under a path the "
                    "public tree withholds: %s"
                    % (lineno, match.group(0), reason))
    return findings


def url_repository(url, host):
    """The `owner/name` a URL names on `host`, or None."""
    if not host:
        return None
    match = REPO_IN_URL.match(url.rstrip(".,;:"))
    if not match or match.group("host").lower() != host.lower():
        return None
    return "%s/%s" % (match.group("owner"), match.group("name"))


def repository_findings(text, host, allowed):
    """Findings for the repositories a document's URLs name.

    Stated positively: a published file may name the repository it is
    in, and no other repository on its host. `allowed` is that one
    repository, taken from the derivation spec's declared destination -
    the same answer whichever repository this check runs in. It is empty
    only when the spec declares no destination, which `main()` reports
    as a refusal to answer rather than letting it read as a clean scan.
    """
    findings = []
    for lineno, line in enumerate(text.splitlines(), start=1):
        for match in URL.finditer(line):
            named = url_repository(match.group(0), host)
            if named is None or named in allowed:
                continue
            findings.append(
                "%d: links to `%s`, which names the repository `%s` on this "
                "repository's own host. A published file may name the "
                "repository it is in and no other: %s"
                % (lineno, match.group(0), named,
                   "this tree names none, because its spec declares no "
                   "destination for the derivation"
                   if not allowed else
                   "this tree is `%s`" % ", ".join(sorted(allowed))))
    return findings


def markdown_references(text):
    """(lineno, reference) for every path-shaped token in a document."""
    out = []
    for lineno, line in enumerate(text.splitlines(), start=1):
        for match in itertools.chain(CODE_SPAN.finditer(line),
                                     LINK_TARGET.finditer(line)):
            ref = normalise(match.group(1))
            if ref is not None:
                out.append((lineno, ref))
    return out


def _parent_levels(node):
    """Levels above `__file__` this expression names, or None.

    `Path(__file__).resolve().parent` is 1, `.parent.parent` is 2, and
    `.parents[1]` is 2. Anything else is not a tree anchor and is left
    alone rather than guessed at.
    """
    levels = 0
    current = node
    while True:
        if isinstance(current, ast.Attribute):
            if current.attr == "parent":
                levels += 1
                current = current.value
                continue
            return None
        if isinstance(current, ast.Subscript):
            value = current.value
            index = current.slice
            if isinstance(index, ast.Index):  # Python 3.8 and earlier
                index = index.value
            if (isinstance(value, ast.Attribute) and value.attr == "parents"
                    and isinstance(index, ast.Constant)
                    and isinstance(index.value, int)):
                levels += index.value + 1
                current = value.value
                continue
            return None
        if isinstance(current, ast.Call):
            func = current.func
            if isinstance(func, ast.Attribute) and func.attr in ("resolve",
                                                                 "absolute"):
                current = func.value
                continue
            if (isinstance(func, ast.Name) and func.id == "Path"
                    and len(current.args) == 1):
                only = current.args[0]
                if isinstance(only, ast.Name) and only.id == "__file__":
                    return levels
            return None
        return None


def _flatten_division(node):
    """(base, [operands]) for a chain of `/`."""
    operands = []
    current = node
    while isinstance(current, ast.BinOp) and isinstance(current.op, ast.Div):
        operands.append(current.right)
        current = current.left
    operands.reverse()
    return current, operands


def _string_constants(tree):
    """Module-level names bound to a string or a tuple/list of strings."""
    env = {}
    for node in tree.body:
        if not isinstance(node, ast.Assign) or len(node.targets) != 1:
            continue
        target = node.targets[0]
        if not isinstance(target, ast.Name):
            continue
        value = node.value
        if isinstance(value, ast.Constant) and isinstance(value.value, str):
            env[target.id] = (value.value,)
        elif isinstance(value, (ast.Tuple, ast.List)):
            items = [e.value for e in value.elts
                     if isinstance(e, ast.Constant) and isinstance(e.value, str)]
            if items and len(items) == len(value.elts):
                env[target.id] = tuple(items)
    for node in ast.walk(tree):
        iterable = target = None
        if isinstance(node, (ast.For, ast.AsyncFor)):
            target, iterable = node.target, node.iter
        elif isinstance(node, ast.comprehension):
            target, iterable = node.target, node.iter
        if (isinstance(target, ast.Name) and isinstance(iterable, ast.Name)
                and iterable.id in env):
            env[target.id] = env[iterable.id]
    return env


def python_references(rel, text):
    """(lineno, reference) for every root-anchored path join in a module."""
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return []

    here = tuple(Path(rel).parts[:-1])
    strings = _string_constants(tree)

    def anchor(node):
        levels = _parent_levels(node)
        if levels is None:
            return None
        if levels - 1 > len(here):
            return None
        return here[:len(here) - (levels - 1)]

    dirs = {}
    for node in tree.body:
        if not isinstance(node, ast.Assign) or len(node.targets) != 1:
            continue
        target = node.targets[0]
        if not isinstance(target, ast.Name):
            continue
        resolved = _resolve_join(node.value, anchor, dirs, strings)
        if resolved and len(resolved) == 1:
            dirs[target.id] = tuple(resolved[0].split("/")) if resolved[0] else ()

    out = []
    for node in ast.walk(tree):
        if not (isinstance(node, ast.BinOp) and isinstance(node.op, ast.Div)):
            continue
        for ref in _resolve_join(node, anchor, dirs, strings) or []:
            if ref:
                out.append((getattr(node, "lineno", 0), ref))
    return out


def _resolve_join(node, anchor, dirs, strings):
    """Every repo-relative path a `/` chain can denote, or None."""
    base, operands = _flatten_division(node)
    prefix = anchor(base)
    if prefix is None:
        if isinstance(base, ast.Name) and base.id in dirs:
            prefix = dirs[base.id]
        else:
            return None
    if not operands:
        return ["/".join(prefix)]
    choices = []
    for operand in operands:
        if isinstance(operand, ast.Constant) and isinstance(operand.value, str):
            choices.append((operand.value,))
        elif isinstance(operand, ast.Name) and operand.id in strings:
            choices.append(strings[operand.id])
        else:
            return None
    return ["/".join([p for p in list(prefix) + list(combo) if p])
            for combo in itertools.product(*choices)]


def tracked_paths(root):
    """Every tracked path in a tree, plus every directory containing one."""
    env = dict(os.environ)
    env["GIT_OPTIONAL_LOCKS"] = "0"
    out = subprocess.check_output(
        ["git", "ls-files", "-z"], cwd=str(root), env=env).decode("utf-8")
    paths = set()
    for rel in out.split("\0"):
        if not rel:
            continue
        parts = rel.split("/")
        for index in range(1, len(parts) + 1):
            paths.add("/".join(parts[:index]))
    return paths


def present_paths(root):
    """Every path in an extracted tree, files and directories alike."""
    root = Path(root)
    paths = set()
    for current, directories, files in os.walk(str(root)):
        base = Path(current).relative_to(root)
        for name in itertools.chain(directories, files):
            paths.add((base / name).as_posix())
    return paths


def git_head():
    """This repository's HEAD, abbreviated - the resolver's known positive."""
    env = dict(os.environ)
    env["GIT_OPTIONAL_LOCKS"] = "0"
    try:
        proc = subprocess.run(
            ["git", "-C", str(REPO_ROOT), "rev-parse", "--short=10", "HEAD"],
            capture_output=True, text=True, timeout=30, env=env)
    except (subprocess.TimeoutExpired, OSError):
        return ""
    return proc.stdout.strip() if proc.returncode == 0 else ""


def origin_repository():
    """(host, `owner/name`) of this repository's own remote, or (None, None).

    Read rather than written down. Which repository this is is a fact
    about the clone in front of the check, and a constant here would be
    a second copy of it - correct in one repository and quietly wrong in
    the other, which is the whole class of defect this rule is about.
    """
    env = dict(os.environ)
    env["GIT_OPTIONAL_LOCKS"] = "0"
    try:
        proc = subprocess.run(
            ["git", "-C", str(REPO_ROOT), "remote", "get-url", "origin"],
            capture_output=True, text=True, timeout=30, env=env)
    except (subprocess.TimeoutExpired, OSError):
        return None, None
    if proc.returncode != 0:
        return None, None
    url = proc.stdout.strip()
    if not url:
        return None, None
    scp = SCP_REMOTE.match(url)
    if scp and "://" not in url:
        url = "https://%s/%s" % (scp.group("host"), scp.group("path"))
    match = REPO_IN_URL.match(url)
    if not match:
        return None, None
    return (match.group("host"),
            "%s/%s" % (match.group("owner"), match.group("name")))


def is_derivation(spec):
    """Is the tree this check runs in already a derivation?

    Read off the exclusion table rather than from a constant of its own,
    the way Rule 36 asks the same question: the development tree is the
    one that still holds what the derivation withholds.
    """
    return not any((REPO_ROOT / prefix.rstrip("/")).is_dir()
                   for prefix, _ in spec.EXCLUDED)


def resolve_commits(tokens):
    """Which of these hex tokens name a commit in *this* repository.

    One `cat-file --batch-check` rather than a process per token: an
    English word of seven hex letters is common enough that a subprocess
    each would make this half expensive enough to switch off.
    """
    tokens = sorted(tokens)
    if not tokens:
        return set()
    env = dict(os.environ)
    env["GIT_OPTIONAL_LOCKS"] = "0"
    try:
        proc = subprocess.run(
            ["git", "-C", str(REPO_ROOT), "cat-file", "--batch-check"],
            input="\n".join(tokens) + "\n", capture_output=True, text=True,
            timeout=60, env=env)
    except (subprocess.TimeoutExpired, OSError):
        return None
    if proc.returncode != 0:
        return None
    hits = set()
    for token, line in zip(tokens, proc.stdout.splitlines()):
        if " commit " in line:
            hits.add(token)
    return hits


def matcher_proofs(matchers, host, allowed):
    """Known positives for the silent matchers, built at run time.

    Never written into this file as a literal: a literal here would be
    found by this check's own scan of the extracted tree, and the fix
    for that is an exemption - which is where every hole this repository
    has found began. Assembling them from pieces keeps the proof and
    leaves nothing to exempt (DP87 for Rule 34, same shape).

    The withheld-prefix and repository positives are assembled from the
    live seeds rather than from pieces of a spelling: a prefix that has
    left the exclusion table, or a host that has moved, then stops being
    proved here rather than being proved against something stale.
    """
    proofs = [
        ("pull request", lambda t: PULL_REQUEST.search(t), "PR" + " #" + "9"),
        ("pull request", lambda t: PULL_REQUEST.search(t),
         "pull" + " request " + "#" + "11"),
        ("coordinate", lambda t: COORDINATE.search(t),
         "report" + " " + "7" + "." + "4"),
        ("coordinate", lambda t: COORDINATE.search(t),
         "task" + " book " + "1" + "." + "1"),
    ]
    def prefix_probe(text):
        return plain_text_findings(text, matchers)

    def repository_probe(text):
        return repository_findings(text, host, allowed)

    for name, _, _ in matchers:
        proofs.append(("withheld prefix", prefix_probe,
                       name + "/" + "PROBE" + ".md"))
    if host:
        # An owner and a repository that are not this one, whatever this
        # one is: the seed is negated rather than guessed at.
        elsewhere = "%s/%s" % ("not" + "-an-owner", "not" + "-a-repository")
        proofs.append(("repository", repository_probe,
                       "https" + "://" + host + "/" + elsewhere))
    return proofs


def scan(dest, source_paths, extracted_paths, matchers, host, allowed):
    """(findings, resolved, hex sites, read, unreadable) for one tree.

    Every file is opened. Which reader it gets depends on what it is;
    that no reader at all was the answer for anything other than `.md`
    and `.py` is the defect DP169 records.
    """
    findings = []
    resolved = {"markdown": 0, "python": 0}
    hex_sites = []
    unreadable = []
    read = {"markdown": 0, "python": 0, "plain": 0}
    dest = Path(dest)
    for current, directories, files in os.walk(str(dest)):
        directories[:] = [d for d in directories if d not in ("__pycache__",)]
        for name in sorted(files):
            path = Path(current) / name
            rel = path.relative_to(dest).as_posix()
            try:
                text = path.read_text(encoding="utf-8")
            except (UnicodeDecodeError, OSError):
                unreadable.append(rel)
                continue
            suffix = path.suffix.lower()
            references = ()
            half = None
            if suffix in MARKDOWN_SUFFIXES:
                half = "markdown"
                references = markdown_references(text)
                read["markdown"] += 1
            elif suffix in PYTHON_SUFFIXES:
                half = "python"
                references = python_references(rel, text)
                read["python"] += 1
            else:
                read["plain"] += 1
                for finding in plain_text_findings(text, matchers):
                    findings.append("%s:%s" % (rel, finding))
            for lineno, ref in references:
                if ref in extracted_paths:
                    resolved[half] += 1
                elif ref in source_paths:
                    findings.append(
                        "%s:%d: points at `%s`, which is in this repository "
                        "and not in the public tree. The derivation took it "
                        "away and this sentence still asks a reader to open "
                        "it." % (rel, lineno, ref))
            for finding in coordinate_findings(text):
                findings.append("%s:%s" % (rel, finding))
            for finding in repository_findings(text, host, allowed):
                findings.append("%s:%s" % (rel, finding))
            for lineno, line in enumerate(text.splitlines(), start=1):
                for match in HEX_TOKEN.finditer(line):
                    hex_sites.append((rel, lineno, match.group(0)))
    return findings, resolved, hex_sites, read, unreadable


def main():
    if not SPEC_PATH.is_file():
        print("scripts/public_tree.py is missing; the public tree has no spec, "
              "so there is nothing to derive and nothing to read.")
        return 1

    spec = load_spec()
    dest = Path(tempfile.mkdtemp(prefix="murscope-public-tree-")) / "tree"
    bad = 0
    try:
        report = spec.extract(dest)
        for problem in report["problems"]:
            print("scripts/public_tree.py: %s" % problem)
            bad += 1

        if not report["included"]:
            print("scripts/public_tree.py: the extraction produced no files. "
                  "An empty tree carries no dangling reference and proves "
                  "nothing (DP87).")
            bad += 1

        source_paths = tracked_paths(REPO_ROOT)
        extracted_paths = present_paths(dest)
        matchers = withheld_prefix_matchers(spec)
        derivation = is_derivation(spec)
        host, own = origin_repository()
        destination = getattr(spec, "DESTINATION", "")
        allowed = {destination} if destination else set()
        if not host:
            print("`origin` could not be read, so the repository half does "
                  "not know which repository a published file is allowed to "
                  "name - and it would report every link on the hosting "
                  "domain as harmless (DP87).")
            bad += 1
        if not destination:
            print("scripts/public_tree.py declares no DESTINATION, so the "
                  "repository half does not know which repository this "
                  "derivation is bound for. It would then allow nothing and "
                  "call the one correct link a finding, or allow everything "
                  "and call none of them one - neither is a measurement "
                  "(DP87).")
            bad += 1
        # When the tree this check runs in *is* the derivation, the spec's
        # destination and the clone's own `origin` are two statements about
        # the same repository, and they have to agree. A mismatch is not a
        # link problem, so it is reported here rather than as a finding: it
        # means the name above has gone stale, or this clone is not the
        # repository the spec is describing. Naming which one is wrong is
        # not this check's to guess.
        if derivation and own and destination and own != destination:
            print("scripts/public_tree.py declares DESTINATION `%s`, but this "
                  "tree is already the derivation and its `origin` is `%s`. "
                  "Two names for one repository that do not match: either the "
                  "spec is stale or this clone is not the repository it "
                  "describes." % (destination, own))
            bad += 1
        if not matchers:
            print("the exclusion table yields no withheld prefix, so the "
                  "plain-text half has nothing to look for and every file "
                  "neither path half reads passes unexamined (DP87).")
            bad += 1
        findings, resolved, hex_sites, read, unreadable = scan(
            dest, source_paths, extracted_paths, matchers, host, allowed)

        for name, probe, positive in matcher_proofs(matchers, host, allowed):
            if not probe(positive):
                print("the %s matcher does not fire on %r, a known positive "
                      "assembled here for exactly this question. Its silence "
                      "over the extracted tree therefore means nothing "
                      "(DP87)." % (name, positive))
                bad += 1

        head = git_head()
        commits = resolve_commits({token for _, _, token in hex_sites} | ({head}
                                                                          if head else set()))
        if commits is None:
            print("git could not be asked which of %d hex token(s) name a "
                  "commit here, so the history half resolved nothing (DP87)."
                  % len({t for _, _, t in hex_sites}))
            bad += 1
            commits = set()
        elif not head:
            print("this repository has no HEAD to prove the commit resolver "
                  "against, so a token that resolves and one that does not "
                  "are indistinguishable here (DP87).")
            bad += 1
        elif head not in commits:
            print("the commit resolver does not recognise this repository's "
                  "own HEAD (%s), so it would report every hash in the "
                  "extracted tree as harmless (DP87)." % head)
            bad += 1

        for rel, lineno, token in hex_sites:
            if token in commits and token != head:
                findings.append(
                    "%s:%d: names `%s`, a commit of the development "
                    "repository. The public repository is founded from a "
                    "clean tree and has no such object, so this is red on its "
                    "first run there - and a gate that is red on day one "
                    "teaches a reader to ignore it." % (rel, lineno, token))

        # A file nothing could decode is not a file nothing needed to be
        # read. Until now these were counted and never named, and the
        # count was printed beside a claim that the read total equals the
        # tree - both of which were true only because the number had
        # always been zero. One tracked binary made the extraction report
        # 152 published and 151 read, and pass (DP184).
        for rel in unreadable:
            findings.append(
                "%s: could not be decoded as text, so no half of this rule "
                "read it - and it is published. A file this check cannot "
                "read is not a file that does not need reading; it is a "
                "hole in the coverage the summary claims." % rel)

        # The structural half of the same defect, and it catches more than
        # its cause: whatever the reason, every published file is either
        # read or it is a finding. Stated as an equality rather than as a
        # printed number, because a number nobody compares is a number
        # that can drift.
        total_read = sum(read.values())
        if total_read != len(report["included"]):
            findings.append(
                "the extraction published %d file(s) and this rule read %d "
                "of them. The difference is files no half examined, so the "
                "clean result covers less than the tree it claims to "
                "(DP87)." % (len(report["included"]), total_read))

        for finding in findings:
            print(finding)
            bad += 1

        for half in sorted(resolved):
            if not resolved[half]:
                print("the %s half of the reference scan resolved nothing, so "
                      "it would report a clean tree whether or not one was "
                      "there (DP87)." % half)
                bad += 1

        if bad:
            print("\nFAILED: %d finding(s) deriving the public tree." % bad)
            print("Fix: rewrite the sentence in scripts/public_tree.py's "
                  "REWRITES, or publish the path it points at.")
            return 1
        print("OK: the public tree derives cleanly - %d file(s) published, %d "
              "withheld under %d exclusion(s), %d rewrite(s) reported over %d "
              "file(s); %d markdown and %d Python reference(s) resolved inside "
              "the extracted tree and none pointed back at a withheld path. "
              "Every number here is measured off the extraction (DP159)."
              % (len(report["included"]), len(report["excluded"]),
                 len(spec.EXCLUDED), len(report["applied"]),
                 len(spec.REWRITES), resolved["markdown"], resolved["python"]))
        print("    The silent halves - coordinate, withheld prefix, "
              "repository - found none of the shapes they look for, and that "
              "is a result rather than a silence: all %d matcher(s) were "
              "fired on a known positive assembled at run time, and the "
              "commit resolver was proved on this repository's own HEAD "
              "before %d hex token(s) in the extracted tree were put to it - "
              "%d of which resolve to a commit here."
              % (len(matcher_proofs(matchers, host, allowed)),
                 len({t for _, _, t in hex_sites}), len(commits - {head})))
        print("    %d file(s) in the extracted tree were opened and read: %d "
              "markdown, %d Python, and %d that are neither and were read by "
              "nothing at all until DP169. %d could not be decoded as text "
              "and were skipped, which is printed rather than counted as "
              "clean. The repository half allowed %s, which is where the "
              "spec says this derivation goes; %s."
              % (sum(read.values()), read["markdown"], read["python"],
                 read["plain"], len(unreadable),
                 ", ".join(sorted(allowed)) or "no repository at all",
                 "this tree is already that derivation, and its `origin` "
                 "agrees with the spec" if derivation
                 else "this tree is the development repository, and the same "
                      "name will be the right answer once the extraction "
                      "lands - the criterion no longer changes with the "
                      "repository the check runs in"))
        return 0
    finally:
        shutil.rmtree(str(dest.parent), ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
