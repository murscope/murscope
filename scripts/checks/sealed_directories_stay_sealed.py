"""Rule 6: sealed directories stay sealed.

The scanner ships a built-in default exclusion table, the user may extend
it, and every directory walk prunes on the resolved table before
descending. This check holds all three:

  1. DEFAULT_SEALED_DIRS, once it exists, is a non-empty immutable
     collection of string literals - an empty table is the same as no
     table.
  2. A resolver named sealed_dirs() exists, references the default table
     and takes user additions, so "extendable" is a fact and not a plan.
  3. Every tree traversal in the package prunes before descending. A
     walk that collects and filters afterwards has already entered the
     directory.

Point 3 is wider than it was. M0 recorded a hole: only `os.walk()` used
as the iterator of a `for` was inspected, so `Path(root).rglob("*")` and
a comprehension over `os.walk()` both walked a sealed directory on a
green gate - and `rglob` is the more likely thing an author reaches for.
Both are caught now:

  - every call to `walk()` anywhere is checked, and one that is not the
    iterator of a pruning `for` is a finding. A comprehension cannot
    contain `dirnames[:] = ...`, so a comprehension over a walk can
    never be pruned and is refused by construction.
  - `rglob()`, `glob()` and `iterdir()` are refused unless the receiver
    is an ALL-CAPS module-level constant. Package-internal directories
    are constants (`LOCALES_DIR`, `PACKS_DIR`); a monitored project's
    root always arrives as a local variable or a parameter. The rule is
    crude and it is checkable, which beats a rule about intent.

**A third permitted shape arrived with M3's key store, and it is a
loosening, so here is what it is and what it is not.** A key list and a
consent list enumerate directories under `MURSCOPE_HOME`, whose path is
resolved at runtime and can therefore never be an ALL-CAPS constant. The
first two shapes had no room for them, and a rule that refuses the
correct idiom gets worked around rather than obeyed - the note on cases j
and u in CONTRIBUTING is about exactly this.

So a traversal is also permitted when its receiver is a local name
assigned from a call to a **home-rooted function in the same module**:
one whose body reaches `murscope_home()`, directly or through another
function here that does. `keys.keys_dir()` and `consent.consent_dir()`
are the two, and both are two lines long.

What that buys, precisely: MURSCOPE_HOME is the one directory this tool
owns and the only one it writes into (Rule 5, from the other side), so a
listing of it is not a scan of anybody's project. What it does not buy:
if the user points MURSCOPE_HOME *inside* a monitored project, the two
overlap - which DP47 already treats as a fact to report rather than to
prevent, and `cli.collect_records` puts on the board per entry. The
resolution is deliberately same-module: a glob written elsewhere, on a
directory some other module resolved, arrives here as an expression
nothing can vouch for and stays refused.

Known open, recorded rather than rediscovered: a module constant that
pointed at a monitored project would pass. Module constants in this
package are package-internal by construction and the freeze puts any
change to one in front of a reviewer, so the residual risk is a
reviewed line rather than an unnoticed one.

Fails when: DEFAULT_SEALED_DIRS exists but is empty or mutable; or the
sealed_dirs() resolver is missing or ignores the default table or takes
no user additions; or a traversal in murscope/ descends without pruning
against the sealed names - an unpruned os.walk(), a walk inside a
comprehension, or rglob/glob/iterdir on a receiver that is neither a
module constant nor a directory this module resolved from
murscope_home().
"""
from __future__ import annotations

import ast
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
PACKAGE = REPO_ROOT / "murscope"

TABLE = "DEFAULT_SEALED_DIRS"
RESOLVER = "sealed_dirs"
IMMUTABLE_FACTORIES = ("frozenset", "tuple")
PRUNE_HINT = re.compile(r"%s|%s|sealed" % (TABLE, RESOLVER))
# Traversals that enumerate a directory tree. Each one either prunes or
# is pointed at something that provably is not a monitored project.
TRAVERSALS = ("rglob", "glob", "iterdir", "scandir", "listdir")
# The one function that answers "where is the directory this tool owns".
# A traversal rooted at its result is a listing of murscope's own home,
# not a scan of anybody's project.
HOME_RESOLVER = "murscope_home"


def find_table(files):
    for path in files:
        src = path.read_text(encoding="utf-8")
        if TABLE not in src:
            continue
        tree = ast.parse(src, filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name) and target.id == TABLE:
                        return path, src, tree, node
    return None, None, None, None


def table_members(value):
    """String literals in a frozenset(...)/tuple(...)/(...)/{...} literal."""
    if isinstance(value, ast.Call):
        name = getattr(value.func, "id", None)
        if name not in IMMUTABLE_FACTORIES:
            return None
        if not value.args:
            return []
        value = value.args[0]
    if isinstance(value, ast.Tuple):
        pass
    elif isinstance(value, (ast.List, ast.Set)):
        # A list or set literal is mutable; the table must be frozen.
        return None
    else:
        return None
    return [e.value for e in value.elts if isinstance(e, ast.Constant) and isinstance(e.value, str)]


def module_constants(tree):
    """ALL-CAPS names bound at module level: the package's own directories."""
    names = set()
    for node in tree.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id.isupper():
                    names.add(target.id)
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            if node.target.id.isupper():
                names.add(node.target.id)
    return names


def pruned_walk_calls(tree, src):
    """Walk calls that sit in a `for` whose body prunes before descending."""
    good = set()
    for node in ast.walk(tree):
        if not isinstance(node, (ast.For, ast.AsyncFor)):
            continue
        iter_src = ast.get_source_segment(src, node.iter) or ""
        if "walk(" not in iter_src:
            continue
        body_src = "\n".join(
            ast.get_source_segment(src, stmt) or "" for stmt in node.body)
        if re.search(r"\w+\[:\]\s*=", body_src) and PRUNE_HINT.search(body_src):
            for sub in ast.walk(node.iter):
                if isinstance(sub, ast.Call):
                    good.add(id(sub))
    return good


def receiver_name(func):
    """The name a method is called on, when it is a plain name."""
    if isinstance(func, ast.Attribute) and isinstance(func.value, ast.Name):
        return func.value.id
    return None


def _callee(call):
    """The bare name of what a call calls: `f()` and `mod.f()` both give f."""
    if not isinstance(call, ast.Call):
        return None
    return getattr(call.func, "id", None) or getattr(call.func, "attr", None)


def home_rooted_functions(tree):
    """Functions here that provably resolve a path from murscope_home().

    A fixed point rather than one hop, so `key_path()` calling
    `keys_dir()` calling `murscope_home()` is recognised without anybody
    having to remember to keep the chain one deep. Same module only: a
    directory another module resolved arrives at the traversal as an
    expression this file cannot vouch for, and stays refused.
    """
    functions = {node.name: node for node in ast.walk(tree)
                 if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))}
    rooted = set()
    changed = True
    while changed:
        changed = False
        for name, node in functions.items():
            if name in rooted:
                continue
            for sub in ast.walk(node):
                if _callee(sub) in (HOME_RESOLVER,) or _callee(sub) in rooted:
                    rooted.add(name)
                    changed = True
                    break
    return rooted


def home_rooted_names(tree, rooted):
    """Variables that can only ever hold a directory rooted at the home.

    Deliberately unanimous rather than last-wins. The permission is
    granted per *name* across a whole module, so a name meaning
    `keys_dir()` in one function and a project root in another would
    launder the second through the first - which is the collision a
    per-name rule invites. A name therefore qualifies only when **every**
    binding of it in this module is a call to a rooted function, and any
    appearance as a parameter or as a loop target disqualifies it
    outright: both arrive from somewhere this file cannot see.
    """
    callees = {}
    refused = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            args = node.args
            named = list(args.args) + list(args.kwonlyargs)
            named += list(getattr(args, "posonlyargs", []))
            named += [a for a in (args.vararg, args.kwarg) if a]
            refused.update(arg.arg for arg in named)
            continue
        if isinstance(node, (ast.For, ast.AsyncFor, ast.comprehension)):
            refused.update(sub.id for sub in ast.walk(node.target)
                           if isinstance(sub, ast.Name))
            continue
        if not isinstance(node, ast.Assign):
            continue
        for target in node.targets:
            if not isinstance(target, ast.Name):
                continue
            callee = _callee(node.value)
            if callee is None:
                refused.add(target.id)
            else:
                callees.setdefault(target.id, set()).add(callee)
    return set(name for name, seen in callees.items()
               if name not in refused and seen and seen <= rooted)


def detect(payload):
    """Findings for one module: an unpruned traversal, or a broken table."""
    src = payload.decode("utf-8", errors="replace")
    try:
        tree = ast.parse(src)
    except SyntaxError as exc:
        return ["cannot parse (%s)." % exc]

    findings = []
    constants = module_constants(tree)
    safe_walks = pruned_walk_calls(tree, src)
    rooted = home_rooted_functions(tree)
    home_names = home_rooted_names(tree, rooted)

    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            attr = getattr(node.func, "attr", None) or getattr(node.func, "id", None)
            # `ast.walk` walks a parse tree, not a directory, and cannot
            # reach a sealed directory or any other one. The test here is
            # by name, so it caught it - narrowed to the receiver rather
            # than to the name, which keeps a bare `walk(...)` from `from
            # os import walk` firing exactly as before. Nothing else is
            # exempted: the receiver has to be literally `ast`.
            if attr == "walk" and receiver_name(node.func) == "ast":
                continue
            if attr == "walk" and id(node) not in safe_walks:
                findings.append(
                    "%d: a directory walk that is not the iterator of a `for` "
                    "whose body prunes against the sealed table. A "
                    "comprehension cannot prune, so it descends into every "
                    "sealed directory it meets." % node.lineno)
            elif attr in TRAVERSALS:
                who = receiver_name(node.func)
                if who not in constants and who not in home_names:
                    findings.append(
                        "%d: %s() on %s. A tree traversal must either prune "
                        "(os.walk with `dirnames[:] = ...`), be pointed at a "
                        "package-internal directory held in an ALL-CAPS module "
                        "constant, or be pointed at a directory this module "
                        "resolved from %s(); %s is none of the three."
                        % (node.lineno, attr, who or "an expression",
                           HOME_RESOLVER, who or "this receiver"))
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if not (isinstance(target, ast.Name) and target.id == TABLE):
                    continue
                members = table_members(node.value)
                if members is None:
                    findings.append(
                        "%d: %s must be an immutable frozenset(...) or tuple of "
                        "string literals; a mutable table is not a frozen default."
                        % (node.lineno, TABLE))
                elif not members:
                    findings.append(
                        "%d: %s is empty; an empty exclusion table is the same as "
                        "no table." % (node.lineno, TABLE))
    return findings


def check_walks(files):
    bad = 0
    walks = 0
    # Traversals permitted by the third shape, counted rather than merely
    # allowed. A loosening that turns out to cover nothing is a loosening
    # that should be taken back out, and one that quietly grows to cover
    # nine call sites is worth seeing in the gate's own output - neither
    # is visible if the permission only ever suppresses a finding.
    home_rooted = 0
    for path in files:
        rel = path.relative_to(REPO_ROOT).as_posix()
        src = path.read_text(encoding="utf-8")
        tree = ast.parse(src, filename=str(path))
        home_names = home_rooted_names(tree, home_rooted_functions(tree))
        for node in ast.walk(tree):
            if isinstance(node, ast.For):
                iter_src = ast.get_source_segment(src, node.iter) or ""
                if "os.walk(" in iter_src or ".walk(" in iter_src:
                    walks += 1
            if (isinstance(node, ast.Call)
                    and getattr(node.func, "attr", None) in TRAVERSALS
                    and receiver_name(node.func) in home_names):
                home_rooted += 1
        for finding in detect(path.read_bytes()):
            print("%s:%s" % (rel, finding))
            bad += 1
    return bad, walks, home_rooted


def main():
    if not PACKAGE.is_dir():
        print("OK: murscope/ not present yet; nothing to inspect.")
        return 0

    files = sorted(PACKAGE.rglob("*.py"))
    bad, walks, home_rooted = check_walks(files)

    path, src, tree, assign = find_table(files)
    if assign is None:
        if bad:
            print("\nFAILED: %d unpruned directory walk(s)." % bad)
            return 1
        print("OK: %d file(s) inspected, %d directory walk(s), no %s table yet; "
              "the rule binds the moment the scanner lands."
              % (len(files), walks, TABLE))
        return 0

    rel = path.relative_to(REPO_ROOT).as_posix()
    members = table_members(assign.value) or []

    resolver = None
    for candidate in files:
        candidate_src = candidate.read_text(encoding="utf-8")
        if RESOLVER not in candidate_src:
            continue
        candidate_tree = ast.parse(candidate_src, filename=str(candidate))
        for node in ast.walk(candidate_tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == RESOLVER:
                resolver = (candidate, ast.get_source_segment(candidate_src, node) or "", node)
    if resolver is None:
        print("%s: no %s() resolver; the built-in table exists but users "
              "cannot extend it." % (rel, RESOLVER))
        bad += 1
    else:
        _, resolver_src, node = resolver
        if TABLE not in resolver_src:
            print("%s(): does not reference %s; the default table is not "
                  "actually applied." % (RESOLVER, TABLE))
            bad += 1
        if not node.args.args and not node.args.kwonlyargs:
            print("%s(): takes no user additions; Rule 6 requires the built-in "
                  "table to be extendable." % RESOLVER)
            bad += 1

    if bad:
        print("\nFAILED: %d sealed-directory violation(s)." % bad)
        return 1
    print("OK: %s holds %d sealed name(s), %s() resolves user additions on top, "
          "and all %d directory walk(s) prune before descending. %d listing(s) "
          "are permitted by the third shape - a directory the same module "
          "resolved from %s() - and every other traversal is on an ALL-CAPS "
          "package-internal constant."
          % (TABLE, len(members), RESOLVER, walks, home_rooted, HOME_RESOLVER))
    return 0


if __name__ == "__main__":
    sys.exit(main())
