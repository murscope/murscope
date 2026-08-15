"""Rule 17: reads stay inside the listed project.

The third promise on the front page - "it reads nothing outside the
projects you listed" - had no check, and an audit showed it was false.
`ledger_paths()` joined a roster-supplied string onto the project root
and read whatever came out:

    ledgers: ["../secret/OUTSIDE.md"]   read, and the ../ showed
    ledgers: ["/abs/OUTSIDE.md"]        read - `root / rel` on an
                                       absolute rel *is* rel, so the
                                       root was ignored entirely

The second was worse, because the caller renamed what it could not place:
`except ValueError: rel = path.name`. The code had foreseen the
out-of-root case and hidden it rather than refusing it, so a file from
outside the project appeared on the board under a bare filename with no
provenance at all.

A promise on the front page cannot rest on whoever edits the joiner next.
This check holds two things:

  1. **Structural.** A containment helper exists, resolves both sides and
     compares them; and any function that joins a caller-supplied name
     onto a root and then reads the result mentions containment
     (`inside_root`, or a `relative_to` test of its own). Crude, and
     checkable, which beats a rule about intent.
  2. **Behavioural.** The real `ledger_paths()` is handed the two shapes
     above and must refuse both. A structural check can be satisfied by a
     function that mentions the helper and ignores its answer; this
     cannot.

The second half is the one that would have caught the original defect, so
it is not decoration. It is also why this check imports the package
rather than only parsing it.

Fails when: the containment helper is missing, or does not resolve, or
does not compare; or a function joins a caller-supplied path onto a root,
reads it, and never tests containment; or `ledger_paths()` accepts a
relative escape or an absolute path outside the root.
"""
from __future__ import annotations

import ast
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
PACKAGE = REPO_ROOT / "murscope"

HELPER = "inside_root"
CONTAINMENT_HINT = (HELPER, "relative_to")
# Calls that turn a joined path into a read.
READS = ("open", "read_text", "read_bytes", "is_file", "stat", "iterdir",
         "walk", "scan_file")


def _tainted_names(node):
    """Names in this function that carry something a caller supplied.

    Parameters, plus any loop or comprehension target whose iterable
    traces back to one. That second half is the whole point: the defect
    this rule exists for was `for rel in list(configured) + ...`, where
    `rel` is not a parameter and is caller-supplied all the same. A
    detector that only looked at parameters would have called the
    offending function clean.

    The distinction it draws is the useful one. `root / rel` where `rel`
    iterates a module constant - the fingerprint table, the locale
    directory - cannot leave the project, and flagging it would push the
    next author to loosen this check rather than obey it.
    """
    tainted = {a.arg for a in node.args.args}
    tainted |= {a.arg for a in getattr(node.args, "kwonlyargs", [])}
    for _ in range(4):  # a fixed point; four is deeper than this package goes
        grew = False
        for sub in ast.walk(node):
            targets = []
            if isinstance(sub, (ast.For, ast.AsyncFor)):
                targets = [(sub.target, sub.iter)]
            elif isinstance(sub, (ast.ListComp, ast.SetComp, ast.GeneratorExp,
                                  ast.DictComp)):
                targets = [(gen.target, gen.iter) for gen in sub.generators]
            for target, source in targets:
                names = {n.id for n in ast.walk(source) if isinstance(n, ast.Name)}
                if not (names & tainted):
                    continue
                for bound in ast.walk(target):
                    if isinstance(bound, ast.Name) and bound.id not in tainted:
                        tainted.add(bound.id)
                        grew = True
        if not grew:
            break
    return tainted


def _joins_a_path(node):
    """Does this function append a caller-supplied name onto a root?

    The *appended* side is what matters. `root / ".git"` is a literal and
    can never escape; `root / rel` where `rel` came from the roster is the
    shape that read a file outside the project.
    """
    tainted = _tainted_names(node)
    for sub in ast.walk(node):
        if not (isinstance(sub, ast.BinOp) and isinstance(sub.op, ast.Div)):
            continue
        appended = {n.id for n in ast.walk(sub.right) if isinstance(n, ast.Name)}
        if appended & tainted:
            return True
    return False


def _reads(node):
    for sub in ast.walk(node):
        if isinstance(sub, ast.Call):
            name = (getattr(sub.func, "attr", None)
                    or getattr(sub.func, "id", None))
            if name in READS:
                return True
    return False


def detect(payload):
    """Findings for one module: a join that is read without a containment test."""
    src = payload.decode("utf-8", errors="replace")
    try:
        tree = ast.parse(src)
    except SyntaxError as exc:
        return ["cannot parse (%s)." % exc]

    findings = []
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        if node.name == HELPER:
            continue
        if not (_joins_a_path(node) and _reads(node)):
            continue
        body = ast.get_source_segment(src, node) or ""
        if any(hint in body for hint in CONTAINMENT_HINT):
            continue
        findings.append(
            "%d: %s() joins a caller-supplied name onto a root and reads the "
            "result without testing containment. `root / rel` on an absolute "
            "rel is rel, so this reads outside the project the user listed - "
            "the third promise on the front page." % (node.lineno, node.name))
    return findings


def check_helper():
    """The containment helper exists, resolves, and compares."""
    findings = []
    source = None
    for path in sorted(PACKAGE.rglob("*.py")):
        src = path.read_text(encoding="utf-8")
        if "def %s(" % HELPER in src:
            source = (path, src)
            break
    if source is None:
        return ["no %s() anywhere in murscope/; the containment test this rule "
                "depends on does not exist." % HELPER]
    path, src = source
    tree = ast.parse(src, filename=str(path))
    for node in ast.walk(tree):
        if not (isinstance(node, ast.FunctionDef) and node.name == HELPER):
            continue
        body = ast.get_source_segment(src, node) or ""
        if "resolve()" not in body:
            findings.append(
                "%s(): does not resolve its arguments, so a symlink out of the "
                "project passes a string comparison."
                % HELPER)
        if "relative_to" not in body:
            findings.append(
                "%s(): does not compare the resolved path against the root."
                % HELPER)
    return findings


def check_behaviour():
    """Hand the real joiner the two shapes an audit found it accepting."""
    sys.path.insert(0, str(REPO_ROOT))
    try:
        from murscope import ledger  # noqa: PLC0415 - probing the real module
    except Exception as exc:  # pragma: no cover - an import failure is a finding
        return ["cannot import murscope.ledger (%s: %s)"
                % (type(exc).__name__, exc)]

    findings = []
    base = Path(tempfile.mkdtemp(prefix="rule17-"))
    root = base / "proj"
    root.mkdir()
    outside = base / "secret"
    outside.mkdir()
    decoy = outside / "OUTSIDE.md"
    decoy.write_text("BLOCKED: outside the root\n", encoding="utf-8")

    for label, rel in (("a relative escape", "../secret/OUTSIDE.md"),
                       ("an absolute path", str(decoy))):
        result = ledger.ledger_paths(root, [rel])
        if not isinstance(result, tuple) or len(result) != 2:
            findings.append(
                "ledger_paths() no longer returns (paths, refusals); this "
                "check cannot see what it refused.")
            break
        paths, refused = result
        if any(str(decoy) == str(Path(p).resolve()) for p in paths):
            findings.append(
                "ledger_paths() accepted %s (%r) and would have read a file "
                "outside the project root." % (label, rel))
        elif not refused:
            findings.append(
                "ledger_paths() dropped %s (%r) without reporting it. A "
                "silent drop and a refusal look identical to the user, and "
                "the point of this rule is that they must not."
                % (label, rel))
    return findings


def main():
    bad = 0
    modules = 0
    for path in sorted(PACKAGE.rglob("*.py")):
        modules += 1
        rel = path.relative_to(REPO_ROOT).as_posix()
        for finding in detect(path.read_bytes()):
            print("%s:%s" % (rel, finding))
            bad += 1
    for finding in check_helper() + check_behaviour():
        print(finding)
        bad += 1

    if bad:
        print("FAILED: %d read(s) that could leave the listed project." % bad)
        return 1
    print("OK: %d module(s) inspected, %s() resolves and compares, and "
          "ledger_paths() refuses both a relative escape and an absolute path "
          "outside the root - reported, not silently dropped."
          % (modules, HELPER))
    return 0


if __name__ == "__main__":
    sys.exit(main())
