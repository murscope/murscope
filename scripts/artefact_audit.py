"""Read what a stranger downloads (DP171).

Rule 35 reads the tree `scripts/public_tree.py` produces. The wheels and
sdists that go to the index are built from *this* tree, so **not one of
the derivation's rewrites is applied to them**, and the index is a third
publication channel no check governs. M5 produced one instance of the
gap: a licence file was inside the wheel while being invisible to every
check, because every check lists the tree with `git ls-files` and the
build reads the disk (DP176).

**This is the same machinery, pointed at the artefact.** It opens each
built distribution, reads every member that decodes as text, and applies
the halves of Rule 35 that mean something for an upload - a path under a
directory the derivation withholds, a coordinate into a history nobody
can open, a link naming another repository on this host - plus Rule 37's
generated spelling space for a real person's name. Nothing here inspects
a source file to answer a question about what shipped.

**Why this is a script and a CI step rather than a check.** It needs a
build, which is too slow to put in front of every commit, and the same
reason `extraction_match.py` is one. Its step is registered in Rule 40,
which is what keeps a step in a workflow from being deleted in silence.
And there is no network anywhere in it: it takes a directory, so anybody
with a clone and an artefact can put the same question to it offline.

**The reader is chosen by what the member is**, which is not a detail.
`murscope/fingerprints.py` ships in the wheel and holds a dozen ledger
paths, two of them named `mgmt/` and two `tasks/` - the table by which
murscope recognises a ledger in somebody else's project. They are
product data, and a plain-text scan of that file would report six
findings about the product working correctly. So markdown members get
Rule 35's markdown reader, Python members its Python reader - which
reads only strings joined onto a tree root and therefore never sees a
tuple of product data - and everything else the plain-text reader, whose
one shape needs no syntax: a path-shaped token whose leading component
is a withheld directory.

**The name half's exemption is a place, and everything about it has to
be narrow.** MIT asks for the copyright notice in every substantial
portion, so each distribution ships a `LICENSE` and the packaging
metadata embeds its text - which means the holder's name is inside
`METADATA` and `PKG-INFO` by construction, indented as a folded field
value. Exempting those two paths whole would exempt the summary, the
author fields and the description with them, so what is subtracted from
them is the artefact's own licence lines and nothing else. **And the
licence member is identified by where the packaging tools put it** -
`<name>-<version>.dist-info/licenses/LICENSE` in a wheel,
`<name>-<version>/LICENSE` in an sdist - never by its basename. Asked as
a basename, this exempted any member called `LICENSE` anywhere inside an
artefact, which is a lid a stranger writes for themselves; and the
exemption belongs to the name scan alone, because written as an early
`continue` it also dropped that member out of the commit-resolving half.
An artefact carrying no licence in that place gets no exemption at all,
and any name in it is a finding.

**The intersection is measured here and never carried.** DP171 bounded
the exposure for 0.1.0 at exactly one rewrite target inside an upload
and said in as many words that the number is a property of that version.
So this reports the intersection it measures, every run: which of the
derivation's rewrite targets have text reaching an artefact, and where.
That is a report rather than a finding - the derivation's rewrites are
preferences as often as they are repairs, and a guard red on day one
teaches a reader to ignore it - and the halves above are what turn an
actual leak red.

**Every silent matcher proves itself before its silence is believed**,
which is the discipline Rule 35 arrived at the hard way: a scan that
finds nothing and a scan looking for the wrong thing print identically.
Each matcher is fired on a known positive assembled at run time, never
written here as a literal - a literal would be found by this file's own
readers when the published tree is scanned, and the fix for that is an
exemption, which is where every hole in this repository's history began.
The commit resolver is proved on this repository's own HEAD, and the
name matcher on the licence each artefact carries, before either is
believed about anything else.

**One half is the exception, and it is written down rather than left to
be found** (DP205). The name matcher's positive is that licence, and a
licence names the **copyright holder** - so the spellings the proof
exercises are always holder-derived. Rule 37 seeds the same matcher from
this repository's authorship as well, because that is where a *second*
person's name would come from, and no artefact carries a second person's
name for it to fire on. That half is therefore proved by nothing. It is
a limit and not a defect: it is inherited from Rule 37's seeding rather
than introduced here, and the same gap exists anywhere the rule's known
positive is a licence. What this file does about it is measure it - the
report prints how many generated spellings come from the authorship
seeds alone, which is the number that would have to be non-zero for the
gap to be doing any harm.

Usage:

    python3 scripts/artefact_audit.py --build DIR    # build, then read
    python3 scripts/artefact_audit.py --audit DIR    # read what is there

Exit 0 when every artefact was opened, every member read, and no half
found anything. Exit 1 on a finding or on a refusal to answer - no
artefact, no matcher, no seed, no rewrite table, no directory that
builds a distribution, a member nothing could decode, a member that is
not a regular file, or a matcher that failed its own known positive.
"""
from __future__ import annotations

import argparse
import importlib.util
import os
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
import zipfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SPEC_PATH = REPO_ROOT / "scripts" / "public_tree.py"
CHECKS_DIR = REPO_ROOT / "scripts" / "checks"
RULE_35 = CHECKS_DIR / "the_public_tree_has_no_dangling_reference.py"
RULE_37 = CHECKS_DIR / "the_shipped_package_names_no_real_person.py"

# What a stranger downloads. `.zip` is here because an sdist may be one
# on a platform that cannot write a tarball, and a member of it would
# otherwise be read by nothing at all.
WHEEL_SUFFIX = ".whl"
TAR_SUFFIXES = (".tar.gz", ".tgz")
ZIP_SUFFIXES = (".zip",)

# **A sandbox rather than the checkout**, because the backend writes an
# egg-info and a build tree beside the sources it is given and this must
# leave the working tree exactly as it found it.
#
# **What is copied is the directory, and this list has now been wrong
# twice in the same direction.** It began as four names - `murscope`,
# `pyproject.toml`, `README.md`, `LICENSE` - and a `NOTICE` at the
# repository root shipped into `dist-info/licenses/` past it, because
# setuptools globs its licence files rather than taking the one the
# packaging table names. Widened to the directory, it still called
# `build/` residue, and **setuptools' `build_py` is additive and prunes
# nothing**: a file left in `build/lib/murscope/` is copied into a real
# `pip wheel .` and was invisible to a sandbox that skipped it. Both times
# the shape was DP176's, inside the guard written to close DP176's class -
# the build reads the disk, this read a list, and the file in the gap was
# invisible to the one and shipped by the other.
#
# **So the criterion stopped being "what a build packages" and became
# "what a build could read", which is a question with one answer.** Only
# two things are left behind, and neither is an input to any build: the
# git object store, and the directory holding this repository's own
# worktrees. Copying either would copy a repository into itself. Anything
# a backend regenerates - `build/`, `dist/`, an egg-info, a `__pycache__`
# - is copied and let alone, because *regenerated* and *ignored* are not
# the same word and the difference is exactly what shipped.
NOT_A_BUILD_INPUT = (".git", ".claude")

# The metadata document that embeds the licence: `METADATA` in a wheel,
# `PKG-INFO` in an sdist.
METADATA_NAMES = ("METADATA", "PKG-INFO")

# **The licence exemption is a location, not a name, and it was a name.**
# Rule 37 states its exemption as the file named `LICENSE` at the root of
# a directory that builds a distribution - a *place*. Read here as a
# basename, it exempted any member called `LICENSE` anywhere in an
# artefact, which is a lid a stranger writes for themselves: the same
# bytes in `murscope/vendor/READ.md` were reported and in
# `murscope/vendor/LICENSE` were silent. So the shape is the place the
# packaging tools put it, and it differs by artefact kind: a wheel writes
# `<name>-<version>.dist-info/licenses/LICENSE` and an sdist writes
# `<name>-<version>/LICENSE`. A `LICENSE` anywhere else is an ordinary
# member and is read like one.
WHEEL_LICENCE = re.compile(r"^[^/]+\.dist-info/licenses/LICENSE$")
SDIST_LICENCE = re.compile(r"^[^/]+/LICENSE$")

MARKDOWN_SUFFIXES = {".md"}
PYTHON_SUFFIXES = {".py"}


def load(path, name):
    """Import a module by path, so one reader has one home."""
    spec = importlib.util.spec_from_file_location(name, str(path))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def git(args):
    """A read-only git call under Rule 5's locked environment, or None."""
    env = dict(os.environ)
    env["GIT_OPTIONAL_LOCKS"] = "0"
    try:
        proc = subprocess.run(
            ["git", "-C", str(REPO_ROOT)] + args,
            capture_output=True, text=True, timeout=60, env=env)
    except (subprocess.TimeoutExpired, OSError):
        return None
    if proc.returncode != 0:
        return None
    return proc.stdout


# ----------------------------------------------------------------- build


def _copy_sources(source_dir, sandbox):
    """Copy a distribution's whole directory into a throwaway one.

    Everything the backend could read, rather than a list of what it was
    thought to read. `build/` is copied and not skipped: setuptools'
    `build_py` is additive and prunes nothing, so a file left there is
    packaged by a real build, and calling it residue was the second
    version of the same mistake.
    """
    shutil.copytree(str(source_dir), str(sandbox),
                    ignore=shutil.ignore_patterns(*NOT_A_BUILD_INPUT))
    return sorted(p.name for p in sandbox.iterdir())


def packaging_roots():
    """Every directory here that builds a distribution, discovered.

    Walked rather than listed, the way Rule 37 finds the same
    directories: a `pyproject.toml` holding a `[project]` table. A
    two-tuple written here would build the two distributions this
    repository has today and be silent about a third the day it arrives,
    which is the shape of everything else this file has had to correct.
    """
    rule37 = load(RULE_37, "murscope_rule37_packaging")
    found = []
    for current, directories, names in os.walk(str(REPO_ROOT)):
        directories[:] = [d for d in sorted(directories)
                          if d not in NOT_A_BUILD_INPUT and d != "build"
                          and d != "dist" and d != "__pycache__"]
        if rule37.PACKAGING_MANIFEST not in names:
            continue
        path = Path(current) / rule37.PACKAGING_MANIFEST
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        if rule37.PROJECT_TABLE.search(text):
            found.append(Path(current))
    return found


def _build_one(sandbox, out_dir, hook):
    """Run one backend hook in a sandbox. Returns (path, error).

    A subprocess rather than an in-process call, for the reason Rule 13b
    gives: the backend changes the working directory and writes a build
    tree beside the sources, and the copy it does that in is thrown away
    with the temporary directory. `sys.executable` rather than a program
    name, so nothing here names a tool Rule 11 forbids.
    """
    program = (
        "import sys, warnings, contextlib, io\n"
        "warnings.simplefilter('ignore')\n"
        "import setuptools.build_meta as backend\n"
        "buf = io.StringIO()\n"
        "with contextlib.redirect_stdout(buf), "
        "contextlib.redirect_stderr(buf):\n"
        "    name = getattr(backend, sys.argv[2])(sys.argv[1])\n"
        "sys.stdout.write(name)\n"
    )
    result = subprocess.run(
        [sys.executable, "-c", program, str(out_dir), hook],
        cwd=str(sandbox), stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if result.returncode != 0:
        detail = result.stderr.decode("utf-8", errors="replace").strip()
        tail = detail.splitlines()[-3:] if detail else ["no output"]
        return None, " / ".join(tail)
    built = Path(out_dir) / result.stdout.decode(
        "utf-8", errors="replace").strip()
    if not built.exists():
        return None, "the backend reported %s and it is not there" % built
    return built, None


def build_artefacts(out_dir):
    """Build every distribution this repository publishes. (built, errors).

    Both wheels *and* both sdists, because an sdist carries what a wheel
    does not - the readme as a file of its own, the packaging metadata's
    source listing - and a stranger can download either.
    """
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    sandboxes = Path(tempfile.mkdtemp(prefix="murscope-artefact-build-"))
    built = []
    errors = []
    try:
        roots = packaging_roots()
        if not roots:
            errors.append(
                "no directory here holds a pyproject.toml with a [project] "
                "table, so there is no distribution to build and an audit "
                "over nothing would print the same green as a clean one "
                "(DP87).")
            return built, errors
        for index, source_dir in enumerate(roots):
            label = source_dir.name if source_dir != REPO_ROOT else "root"
            sandbox = sandboxes / ("%d-%s" % (index, label))
            copied = _copy_sources(source_dir, sandbox)
            if not copied:
                errors.append("%s: nothing to build; its source directory "
                              "copied empty" % label)
                continue
            for hook in ("build_wheel", "build_sdist"):
                path, error = _build_one(sandbox, out_dir, hook)
                if error:
                    errors.append(
                        "%s: %s could not be built (%s). This cannot answer "
                        "its question without the artefact, so it is red "
                        "rather than green. If setuptools is missing from "
                        "this interpreter, `python3 -m pip install "
                        "setuptools` - it is this project's declared build "
                        "backend." % (label, hook, error))
                    continue
                built.append(path)
    finally:
        shutil.rmtree(str(sandboxes), ignore_errors=True)
    return built, errors


# ------------------------------------------------------------------ read


def artefact_paths(directory):
    """Every built distribution in a directory, sorted."""
    directory = Path(directory)
    if not directory.is_dir():
        return []
    out = []
    for path in sorted(directory.iterdir()):
        if not path.is_file():
            continue
        name = path.name.lower()
        if name.endswith(WHEEL_SUFFIX) or name.endswith(TAR_SUFFIXES) \
                or name.endswith(ZIP_SUFFIXES):
            out.append(path)
    return out


def members_of(path):
    """(members, unread) for one artefact, or (None, None) if it will not open.

    `unread` is what an archive holds that is not a regular file - a
    symlink, a device node, a hard link. Named rather than skipped: a
    build here writes none of them, but `--audit` is documented as taking
    an artefact somebody downloaded, and a member dropped in silence
    would be counted in neither the read total nor the undecodable one.
    """
    name = path.name.lower()
    try:
        if name.endswith(WHEEL_SUFFIX) or name.endswith(ZIP_SUFFIXES):
            with zipfile.ZipFile(str(path)) as archive:
                return [(entry, archive.read(entry))
                        for entry in archive.namelist()
                        if not entry.endswith("/")], []
        with tarfile.open(str(path)) as archive:
            out = []
            unread = []
            for entry in archive.getmembers():
                if entry.isdir():
                    continue
                if not entry.isfile():
                    unread.append(entry.name)
                    continue
                handle = archive.extractfile(entry)
                if handle is None:
                    unread.append(entry.name)
                    continue
                out.append((entry.name, handle.read()))
            return out, unread
    except (zipfile.BadZipFile, tarfile.TarError, OSError, EOFError):
        return None, None


def _basename(member):
    return member.rsplit("/", 1)[-1]


def is_licence_member(artefact_name, member):
    """Is this member the licence notice the distribution is required to carry?

    **A location, not a name.** The packaging tools put it in exactly one
    place per artefact kind, and asking after the basename instead made
    any member called `LICENSE` exempt wherever it sat.
    """
    if artefact_name.lower().endswith(WHEEL_SUFFIX):
        return bool(WHEEL_LICENCE.match(member))
    return bool(SDIST_LICENCE.match(member))


def licence_lines(artefact_name, members):
    """(the licence text's lines, the members that are the licence itself).

    The exemption Rule 37 states as a category, read off the artefact:
    the copyright notice a distribution is required to carry. Lines
    rather than the whole text, because packaging metadata folds the
    notice into a field value with every line indented.
    """
    lines = set()
    documents = []
    for member, data in members:
        if not is_licence_member(artefact_name, member):
            continue
        try:
            text = data.decode("utf-8")
        except UnicodeDecodeError:
            continue
        documents.append(member)
        for line in text.splitlines():
            stripped = line.strip()
            if stripped:
                lines.add(stripped)
    return lines, documents


def without_licence(text, lines):
    """A member's text with the artefact's own licence lines removed."""
    if not lines:
        return text
    kept = [line for line in text.splitlines()
            if line.strip() not in lines]
    return "\n".join(kept)


def name_findings(text, space):
    """Findings for the whole names written in a text."""
    findings = []
    for lineno, line in enumerate(text.splitlines(), start=1):
        low = line.lower()
        for spelling in sorted(space):
            if spelling in low:
                findings.append(
                    "%d: writes a real person's whole name as %r. DP19 has "
                    "said since M0 that no real person's name appears in "
                    "what ships, and an upload is the widest thing that "
                    "ships. The licence notice each distribution carries is "
                    "the exemption and it was subtracted before this line "
                    "was read." % (lineno, spelling))
                break
    return findings


# --------------------------------------------------------- intersection


def rewrite_targets(spec):
    """{path: [(kind, find)]} for every rewrite the derivation applies."""
    targets = {}
    for path, rules in getattr(spec, "REWRITES", {}).items():
        for find, _, _ in rules:
            targets.setdefault(path, []).append(("literal", find))
    for path, rules in getattr(spec, "REGEX_REWRITES", {}).items():
        for find, _, _ in rules:
            targets.setdefault(path, []).append(("pattern", find))
    return targets


def intersection(targets, corpus):
    """{rewrite target: [member sites]} - what reaches an upload unrewritten.

    The text a rewrite *removes* is what is looked for, rather than the
    file it removes it from: a readme reaches an artefact under three
    different names and inside the packaging metadata, and asking after
    the file would miss all four.
    """
    hits = {}
    for path, rules in sorted(targets.items()):
        for kind, find in rules:
            for site, text in corpus:
                found = (find in text) if kind == "literal" \
                    else bool(find.search(text))
                if found and site not in hits.setdefault(path, []):
                    hits[path].append(site)
    return hits


# ----------------------------------------------------------------- main


def audit(directory):
    """Read every artefact in a directory. Returns (findings, report)."""
    findings = []
    report = {}

    if not SPEC_PATH.is_file():
        return (["scripts/public_tree.py is missing, so there is no "
                 "exclusion table, no rewrite table and nothing to measure "
                 "an artefact against."], report)
    spec = load(SPEC_PATH, "murscope_public_tree_artefacts")
    rule35 = load(RULE_35, "murscope_rule35_readers")
    rule37 = load(RULE_37, "murscope_rule37_readers")

    paths = artefact_paths(directory)
    report["artefacts"] = [p.name for p in paths]
    if not paths:
        findings.append(
            "no built artefact in %s. An audit over no artefact finds "
            "nothing and reports the same green as an audit over a clean "
            "one, which is the empty-graph pass (DP87)." % directory)
        return findings, report

    matchers = rule35.withheld_prefix_matchers(spec)
    if not matchers:
        findings.append(
            "the exclusion table yields no withheld prefix, so the "
            "plain-text half has nothing to look for and every member "
            "neither path reader opens passes unexamined (DP87).")
    host, _ = rule35.origin_repository()
    destination = getattr(spec, "DESTINATION", "")
    allowed = {destination} if destination else set()
    if not host:
        findings.append(
            "`origin` could not be read, so the repository half does not "
            "know which repository a shipped file may name, and it would "
            "report every link on the hosting domain as harmless (DP87).")
    if not destination:
        findings.append(
            "scripts/public_tree.py declares no DESTINATION, so the "
            "repository half would allow nothing and call the one correct "
            "link a finding, or allow everything and call none of them one "
            "(DP87).")
    targets = rewrite_targets(spec)
    if not targets:
        findings.append(
            "the derivation declares no rewrite at all, so the intersection "
            "below is zero for a reason that has nothing to do with what "
            "shipped (DP87).")

    seeds = []
    holders = rule37.copyright_holders(
        (REPO_ROOT / "LICENSE").read_text(encoding="utf-8")) \
        if (REPO_ROOT / "LICENSE").is_file() else []
    seeds.extend(holders)
    authors = rule37.authorship()
    if authors is None:
        findings.append(
            "this repository's authorship could not be read, so a second "
            "person's name has no seed and the name half is narrower than "
            "it says (DP87).")
    else:
        seeds.extend(authors)
    space = set()
    for seed in seeds:
        space |= rule37.spellings(seed)
    # **The composition of the seed set is recorded, not just its size.**
    # An authorship that cannot be read at all is the finding above; an
    # authorship that comes back *shorter* - a shallow clone, a
    # single-branch fetch, a rewritten history - is silent, and the space
    # narrows by exactly as much while every member still reads clean.
    # Nothing here holds a baseline to compare against, and a baseline
    # would be a check; what it can do is print the two numbers so the
    # narrowing is on the page rather than only in the total.
    holder_space = set()
    for seed in holders:
        holder_space |= rule37.spellings(seed)
    report["seeds"] = len(seeds)
    report["spellings"] = len(space)
    report["holder_seeds"] = len(holders)
    report["authorship_seeds"] = None if authors is None else len(authors)
    report["barren_seeds"] = sum(
        1 for seed in seeds if not rule37.spellings(seed))
    # Which spellings the known positive below can never exercise. A
    # licence names the copyright holder, so the authorship-derived half -
    # the one whose whole job is a *second* person's name - has no subject
    # inside an artefact to fire on. Measured every run rather than
    # asserted, because it is a property of this tree's seeds.
    report["unproved_spellings"] = len(space - holder_space)
    if not space:
        findings.append(
            "no usable seed for the name half - `LICENSE` names no "
            "copyright holder this could generate a spelling from, and the "
            "history offers none either. A matcher generated from nothing "
            "reports every member clean (DP87).")

    read = {"markdown": 0, "python": 0, "plain": 0}
    exempt_documents = []
    unreadable = []
    irregular = []
    hex_sites = []
    corpus = []
    licences_seen = 0

    for path in paths:
        members, unread = members_of(path)
        if members is None:
            findings.append(
                "%s could not be opened as an archive, so nothing in it was "
                "read - and it is what a stranger downloads." % path.name)
            continue
        irregular.extend("%s::%s" % (path.name, m) for m in unread)
        lines, documents = licence_lines(path.name, members)
        if lines:
            licences_seen += 1
            if space and not name_findings("\n".join(sorted(lines)), space):
                findings.append(
                    "%s: the generated spellings do not fire on the licence "
                    "this artefact carries, where the copyright holder "
                    "certainly is. Their silence over the rest of it "
                    "therefore means nothing (DP87)." % path.name)
        exempt_documents.extend("%s::%s" % (path.name, m) for m in documents)

        for member, data in members:
            site = "%s::%s" % (path.name, member)
            try:
                text = data.decode("utf-8")
            except UnicodeDecodeError:
                unreadable.append(site)
                continue
            corpus.append((site, text))
            suffix = ("." + member.rsplit(".", 1)[-1].lower()) \
                if "." in _basename(member) else ""

            if suffix in MARKDOWN_SUFFIXES:
                read["markdown"] += 1
                references = rule35.markdown_references(text)
            elif suffix in PYTHON_SUFFIXES:
                read["python"] += 1
                references = rule35.python_references(member, text)
            else:
                read["plain"] += 1
                references = ()
                for finding in rule35.plain_text_findings(text, matchers):
                    findings.append("%s:%s" % (site, finding))
            for lineno, ref in references:
                reason = spec.excluded_reason(ref + "/") \
                    or spec.excluded_reason(ref)
                if reason:
                    findings.append(
                        "%s:%d: points at `%s`, which the derivation "
                        "withholds: %s. It is inside an artefact, where no "
                        "rewrite of the derivation is applied."
                        % (site, lineno, ref, reason))
            for finding in rule35.coordinate_findings(text):
                findings.append("%s:%s" % (site, finding))
            for finding in rule35.repository_findings(text, host, allowed):
                findings.append("%s:%s" % (site, finding))

            # **The exemption is the name scan's and nothing else's.**
            # Written as a `continue`, it dropped a licence member out of
            # the hex-token loop below as well, so a commit of this
            # repository written into a member called `LICENSE` was never
            # put to the resolver - an exemption for one half quietly
            # spending for two.
            if space and not is_licence_member(path.name, member):
                body = without_licence(text, lines) \
                    if _basename(member) in METADATA_NAMES else text
                for finding in name_findings(body, space):
                    findings.append("%s:%s" % (site, finding))

            for lineno, line in enumerate(text.splitlines(), start=1):
                for match in rule35.HEX_TOKEN.finditer(line):
                    hex_sites.append((site, lineno, match.group(0)))

    report["read"] = read
    report["unreadable"] = unreadable
    report["irregular"] = irregular

    for site in irregular:
        findings.append(
            "%s: is a member that is not a regular file - a link or a "
            "special file - so nothing read it, and it is inside what a "
            "stranger downloads. Nothing built here writes one; an "
            "artefact somebody else built can, and a member dropped in "
            "silence is counted in neither total above." % site)
    report["licences"] = licences_seen
    report["exempt"] = exempt_documents

    for site in unreadable:
        findings.append(
            "%s: could not be decoded as text, so no half of this audit "
            "read it - and it is inside what a stranger downloads. A member "
            "this cannot read is not a member that did not need reading; it "
            "is a hole in the coverage the summary claims (DP184)." % site)

    for name, probe, positive in rule35.matcher_proofs(matchers, host, allowed):
        if not probe(positive):
            findings.append(
                "the %s matcher does not fire on %r, a known positive "
                "assembled at run time for exactly this question. Its "
                "silence over these artefacts therefore means nothing "
                "(DP87)." % (name, positive))
    # The name half's own assembled positive, so that a run over artefacts
    # carrying no licence at all still knows its matcher works.
    if space:
        fabricated = sorted(space)[0]
        if not name_findings("a line naming " + fabricated + " in it", space):
            findings.append(
                "the name matcher does not fire on a spelling it generated "
                "itself, so it would report every member clean (DP87).")

    head = rule35.git_head()
    tokens = {token for _, _, token in hex_sites}
    commits = rule35.resolve_commits(tokens | ({head} if head else set()))
    if commits is None:
        findings.append(
            "git could not be asked which of %d hex token(s) name a commit "
            "here, so the coordinate half resolved nothing (DP87)."
            % len(tokens))
        commits = set()
    elif not head:
        findings.append(
            "this repository has no HEAD to prove the commit resolver "
            "against, so a token that resolves and one that does not are "
            "indistinguishable here (DP87).")
    elif head not in commits:
        findings.append(
            "the commit resolver does not recognise this repository's own "
            "HEAD (%s), so it would report every hash inside these "
            "artefacts as harmless (DP87)." % head)
    report["hex"] = len(tokens)
    report["commits"] = len(commits - {head})

    for site, lineno, token in hex_sites:
        if token in commits and token != head:
            findings.append(
                "%s:%d: names `%s`, a commit of the development repository. "
                "Whoever downloads this artefact has no such object and no "
                "way to get one." % (site, lineno, token))

    report["targets"] = len(targets)
    report["intersection"] = intersection(targets, corpus)
    return findings, report


def print_report(directory, report):
    print("    Read %d artefact(s) in %s: %s."
          % (len(report.get("artefacts", [])), directory,
             ", ".join(report.get("artefacts", [])) or "none"))
    read = report.get("read", {})
    print("    %d member(s) opened and read - %d markdown, %d Python, %d "
          "neither, which get the plain-text reader. %d could not be decoded "
          "as text, which is printed rather than counted as clean."
          % (sum(read.values()), read.get("markdown", 0),
             read.get("python", 0), read.get("plain", 0),
             len(report.get("unreadable", []))))
    authorship = report.get("authorship_seeds")
    print("    The name half generated %d spelling(s) from %d seed(s) - %d "
          "from the copyright holder `LICENSE` names and %s from this "
          "tree's authorship, %d of them carrying a single word token and "
          "so generating nothing, because Rule 37 never matches one - and "
          "was proved on the licence %d artefact(s) carry before anything "
          "else was scanned. Its exemption is those %d licence document(s) "
          "and the licence lines folded into the packaging metadata beside "
          "them, computed off each artefact rather than listed."
          % (report.get("spellings", 0), report.get("seeds", 0),
             report.get("holder_seeds", 0),
             "none, because it could not be read" if authorship is None
             else "%d" % authorship,
             report.get("barren_seeds", 0),
             report.get("licences", 0), len(report.get("exempt", []))))
    print("    **An authorship that cannot be read at all is a finding "
          "above; an authorship that comes back shorter is not**, and that "
          "asymmetry is why the two counts are printed rather than only "
          "their total. A shallow clone, a single-branch fetch or a "
          "rewritten history yields fewer names, the space narrows by "
          "exactly as much, and every member still reads clean. Nothing "
          "here compares the numbers against a baseline - there is none, "
          "and a baseline would be a check.")
    print("    **And the half whose subject never appears in an artefact is "
          "the one matcher in this file that no known positive proves.** "
          "The name half's positive is the licence each artefact carries, "
          "and a licence names the copyright holder, so only "
          "holder-derived spellings are ever exercised: %d of the %d "
          "generated exist because of the authorship seeds alone, and "
          "nothing fires on those. That is a stated limit rather than a "
          "defect - a second person's name has no subject inside an "
          "artefact to be a positive, and the limit is inherited from Rule "
          "37's seeding rather than introduced here. It is written down "
          "for the reason Rule 38 states its mode: a limit nobody wrote "
          "down reads as a green (DP205)."
          % (report.get("unproved_spellings", 0),
             report.get("spellings", 0)))
    print("    The coordinate half put %d distinct hex token(s) to this "
          "repository, %d of which resolve to a commit here, after the "
          "resolver was proved on this repository's own HEAD."
          % (report.get("hex", 0), report.get("commits", 0)))

    hits = report.get("intersection", {})
    print("    **The intersection, measured on this tree and not carried "
          "from DP171** (DP171 bounded it at one for 0.1.0 and said in as "
          "many words that the number is a property of that version): %d of "
          "%d rewrite target(s) have text reaching an artefact."
          % (len(hits), report.get("targets", 0)))
    for path in sorted(hits):
        print("        %s" % path)
        for site in hits[path]:
            print("            %s" % site)
    print("    That is a report and not a finding: a rewrite is as often a "
          "preference for the published tree as a repair, and a guard red on "
          "day one teaches a reader to ignore it. What turns an actual leak "
          "red is the halves above, which read every member of every "
          "artefact whether a rewrite names it or not.")


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Read what a stranger downloads (DP171).")
    parser.add_argument("--build", metavar="DIR",
                        help="build every distribution into DIR, then read it")
    parser.add_argument("--audit", metavar="DIR",
                        help="read the artefacts already in DIR")
    args = parser.parse_args(argv)

    if bool(args.build) == bool(args.audit):
        parser.error("exactly one of --build DIR or --audit DIR")

    directory = args.build or args.audit
    if args.build:
        built, errors = build_artefacts(directory)
        for error in errors:
            print(error)
        print("Built %d artefact(s) into %s: %s"
              % (len(built), directory,
                 ", ".join(sorted(p.name for p in built)) or "none"))
        print("    Each was built by the declared backend from a copy of "
              "its whole source directory - **what the backend could read, "
              "rather than what it was thought to package**, which is the "
              "distinction a NOTICE at the root and a file left in build/ "
              "each cost one round. `build/` is copied rather than skipped: "
              "setuptools' build_py is additive and prunes nothing, so a "
              "file left there is packaged by a real `pip wheel .`. Left "
              "behind: %s - neither is an input to any build, and copying "
              "either would copy a repository into itself. The directories "
              "that build a distribution are discovered by walking for a "
              "pyproject.toml with a [project] table, the way Rule 37 finds "
              "the same ones, so a third distribution is built the day it "
              "arrives." % ", ".join(NOT_A_BUILD_INPUT))
        if errors:
            print("\nFAILED: the artefacts this reads could not all be built.")
            return 1

    findings, report = audit(directory)
    if findings:
        for finding in findings:
            print(finding)
        print_report(directory, report)
        print("\nFAILED: %d finding(s) in what a stranger downloads."
              % len(findings))
        print("Fix: the rewrites in scripts/public_tree.py are not applied "
              "to an artefact, so a sentence repaired for the published tree "
              "is still wrong here. Repair it at the source.")
        return 1

    print("OK: every member of every built artefact was opened and read, and "
          "no half found a path under a withheld directory, a coordinate "
          "into a history nobody can open, a link naming another repository "
          "on this host, or a real person's name outside the licence notice "
          "- where the names it is able to find are the ones it is seeded "
          "with: the copyright holder `LICENSE` names, plus every author "
          "and committer in this tree's history. A second person who has "
          "never committed here is outside that space, whatever tree "
          "`here` is.")
    print_report(directory, report)
    return 0


if __name__ == "__main__":
    sys.exit(main())
