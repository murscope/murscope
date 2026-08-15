"""Rule 7: sensitive entries expose method only.

A roster entry marked `sensitive` is read through a frozen key
whitelist, and the collector must not read the rest at all. That makes
this a collection-time boundary, not a rendering-time filter: a filter
applied on the way out has already read the thing it is hiding.

This check holds four things:

  1. SENSITIVE_ALLOWED_KEYS, once it exists, is a non-empty immutable
     collection of string literals.
  2. It is referenced somewhere other than its own definition, so the
     whitelist is applied rather than merely declared.
  3. Any JSON fixture in the repository holding an entry with
     "sensitive": true carries no key outside the whitelist.
  4. **The collection-time gate exists and covers every reader**, and
     **every reader is reached only from a gate**.

Point 4 is the half M0 wrote down as unenforced, and it is the stronger
half: a filter applied on the way out has already read the thing it is
hiding, so "expose method only" has to mean "never opened it".

It is checked structurally. A *reader* is a function in the package
whose body opens, stats, globs or walks something, or calls another
reader - computed to a fixpoint, so a reader three calls deep is still a
reader. A *gate* is a function that **tests** `sensitive` - an `if`, a
conditional expression, a comprehension filter. Not a function that
merely contains the word: a body contains its comments, so under the
older model a comment explaining why a reader was safe turned that
reader into a gate and its read into a finding. Documenting the boundary
was punished by the check defending it, twice - `wizard.run()`, then
`walk_tree()`. `check_model_precision()` pins both directions, because
narrowing this until nothing is a gate would also pass. Inside a gate,
every call to a reader must sit under an `if` whose test mentions
`sensitive`; a reader called unconditionally in the function that knows
about sensitivity is exactly the bug this rule exists to prevent. And
once the whitelist exists, at least one gate must exist, so the boundary
cannot quietly be nowhere.

Two holes an audit found here, both closed rather than documented away:
an **inline** `open()` inside a gate had no callee name to match, so an
ungated read was counted as a gate; and a reader called from a function
that never mentions sensitivity was not examined at all, because point 4
only ever looked inside gates. A reader must now be reached from a gate,
and the chain may pass through other readers on the way.

Known open, recorded rather than rediscovered, with the milestone that
owns each:

  - The **scan and the permission probe are out of scope**, stated above
    the `PRE_ROSTER` constant: they run before a roster exists and cannot
    be handed a sensitive entry. If that ever changes the line has to go.
  - The caller rule is **scoped to `murscope/collect.py`**, the module
    that reads a roster entry's project and the one where the audit
    demonstrated the leak. A wider version needs taint rooted at the
    roster path rather than at a function parameter: without that, a
    write through `guard_write_path()`, a metadata walk in the scanner,
    and a read of the board template are all indistinguishable from a
    read of somebody's project, and the version that tried reported
    sixteen findings that were all correct code. Widening it is M3's,
    with the provider layer that makes the stakes real. Propping the
    narrow version up with a list of exempt modules was the alternative
    and is refused - an exemption list is where every hole two audits
    found began.
  - A reader reached through a variable holding a function, or through a
    provider, is not traced. Neither shape exists in this package and
    Rule 16 keeps providers out of the core.

Fails when: SENSITIVE_ALLOWED_KEYS exists but is empty, mutable, or
never used; a JSON entry marked sensitive carries a key outside the
whitelist; a function that knows about sensitivity calls a file reader -
named or inline - without gating it; a content reader is called from a
function that never mentions sensitivity; or the whitelist exists and no
gate does.
"""
from __future__ import annotations

import ast
import json
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
PACKAGE = REPO_ROOT / "murscope"
WHITELIST = "SENSITIVE_ALLOWED_KEYS"
IMMUTABLE_FACTORIES = ("frozenset", "tuple")
JSON_ROOTS = ("murscope", "tests", "data")
GATE_WORD = "sensitive"
# Calls that read what is *inside* a path. Deliberately excludes stat,
# exists and is_file: those are metadata, and metadata is precisely what
# Rule 7 allows a sensitive entry to expose. Excludes subprocess too -
# git metadata is method, not content, and the git allowlist is Rule 5's
# job rather than this one's.
CONTENT_CALLS = frozenset((
    "open", "read_text", "read_bytes", "readlines", "walk",
    "scandir", "listdir", "glob", "rglob", "iterdir",
))


def literal_members(value):
    if isinstance(value, ast.Call):
        if getattr(value.func, "id", None) not in IMMUTABLE_FACTORIES:
            return None
        if not value.args:
            return []
        value = value.args[0]
    if not isinstance(value, ast.Tuple):
        return None
    return [e.value for e in value.elts if isinstance(e, ast.Constant) and isinstance(e.value, str)]


def detect(payload):
    """Findings for one module: a broken whitelist, or an ungated read.

    Both halves, deliberately. An audit found that Rule 1's proof for this
    check was satisfied by a fixture holding
    `SENSITIVE_ALLOWED_KEYS = frozenset(())` - the empty-whitelist branch
    and nothing else - while point 4, which this file's own docstring
    calls the stronger half, lived only in `main()` and was never fed a
    violating shape. So the gate analysis runs here too, and the fixture
    carries the shape the audit constructed.
    """
    src = payload.decode("utf-8", errors="replace")
    try:
        tree = ast.parse(src)
    except SyntaxError as exc:
        return ["cannot parse (%s)." % exc]
    findings = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Assign):
            continue
        for target in node.targets:
            if not (isinstance(target, ast.Name) and target.id == WHITELIST):
                continue
            members = literal_members(node.value)
            if members is None:
                findings.append(
                    "%d: %s must be an immutable frozenset(...) or tuple of "
                    "string literals." % (node.lineno, WHITELIST))
            elif not members:
                findings.append(
                    "%d: %s is empty; a sensitive entry would expose nothing at "
                    "all, which means the whitelist is not the thing doing the "
                    "work." % (node.lineno, WHITELIST))

    readers = readers_below_gates([("<payload>", src, tree)], set())
    gate_only, _gates = gate_findings(tree, src, readers)
    findings.extend(gate_only)
    return findings


def _params(funcdef):
    """Every parameter name this function binds."""
    args = funcdef.args
    names = set()
    for group in (getattr(args, "posonlyargs", []), args.args, args.kwonlyargs):
        names.update(a.arg for a in group)
    if args.vararg:
        names.add(args.vararg.arg)
    if args.kwarg:
        names.add(args.kwarg.arg)
    return names


def _mentions(src, node, names):
    """Does this expression mention one of these names?

    Crude on purpose: a source-segment match rather than dataflow. It is
    the difference between a rule that can be read and one that needs a
    type checker, and every path in this package that reaches a
    monitored project reaches it through a parameter that is still
    spelled the same in the expression.
    """
    text = ast.get_source_segment(src, node) or ""
    return any(re.search(r"\b%s\b" % re.escape(name), text) for name in names)


def _module_constants(tree):
    """ALL-CAPS names bound at module level: this package's own paths."""
    names = set()
    for node in tree.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id.isupper():
                    names.add(target.id)
    return names


def tainted_names(funcdef, src, constants=()):
    """Names inside this function that carry a caller-supplied path.

    Starts at the parameters and follows assignments and loop targets to
    a fixpoint, because the path is almost never used under the name it
    arrived with - `root_str = str(root)`, then `os.walk(root_str)`,
    then `path = Path(dirpath) / filename`. Matching parameter names
    alone missed every one of those and called the package's only real
    tree walk metadata-free.
    """
    names = _params(funcdef)
    # A path built from one of this package's own directory constants is
    # package-internal however much of its tail came from a parameter:
    # markers.load_pack() does PACKS_DIR / ("%s.json" % name) and reads
    # it every time, and calling that a read of the user's project would
    # make this rule fire on the tool reading itself.
    internal = set(constants)
    changed = True
    while changed:
        changed = False
        for sub in ast.walk(funcdef):
            targets = []
            value = None
            if isinstance(sub, ast.Assign):
                targets, value = sub.targets, sub.value
            elif isinstance(sub, (ast.For, ast.AsyncFor)):
                targets, value = [sub.target], sub.iter
            elif isinstance(sub, ast.withitem) and sub.optional_vars is not None:
                targets, value = [sub.optional_vars], sub.context_expr
            if value is None:
                continue
            from_internal = _mentions(src, value, internal)
            from_params = _mentions(src, value, names)
            if not (from_internal or from_params):
                continue
            for target in targets:
                for leaf in ast.walk(target):
                    if not isinstance(leaf, ast.Name):
                        continue
                    bucket = internal if from_internal else names
                    if leaf.id not in bucket:
                        bucket.add(leaf.id)
                        changed = True
    return names - internal


def content_readers(sources, module_names):
    """Package functions that read the *contents* of a caller-supplied path.

    Not `stat`, `exists` or `is_file`: those are metadata, and Rule 7
    permits metadata for a sensitive entry - that is what "expose method
    only" means. Not a read of a package-internal path either, which is
    why the path has to be tainted by one of the function's own
    parameters: markers.load_pack() reads a file on every call and the
    file is always inside this package.

    Graph edges are only drawn to functions this package could actually
    be calling - a bare name, or an attribute on one of the package's own
    modules. Without that restriction `subprocess.run` resolved to
    `cli.run`, and every git reader in the package was reported as a
    content reader because the call graph had walked out of the package
    and back in through a name collision.
    """
    direct = set()
    edges = {}
    for _, src, tree in sources:
        constants = _module_constants(tree)
        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            params = _params(node)
            if not params:
                continue
            tainted = tainted_names(node, src, constants)
            if not tainted:
                continue
            calls = set()
            for sub in ast.walk(node):
                if not isinstance(sub, ast.Call):
                    continue
                attr = getattr(sub.func, "attr", None)
                bare = getattr(sub.func, "id", None)
                name = attr or bare
                if name in CONTENT_CALLS:
                    target = (sub.func.value if isinstance(sub.func, ast.Attribute)
                              else (sub.args[0] if sub.args else None))
                    if target is not None and _mentions(src, target, tainted):
                        direct.add(node.name)
                in_package = bool(bare) or (
                    isinstance(sub.func, ast.Attribute)
                    and isinstance(sub.func.value, ast.Name)
                    and sub.func.value.id in module_names)
                if name and in_package and any(
                        _mentions(src, arg, tainted) for arg in sub.args):
                    calls.add(name)
            edges.setdefault(node.name, set()).update(calls)

    readers = set(direct)
    changed = True
    while changed:
        changed = False
        for name, called in edges.items():
            if name not in readers and called & readers:
                readers.add(name)
                changed = True
    return readers


# Reading a file without going through a named package function. An
# audit constructed exactly this and the check called it a gate: the
# callee has no name in the package, so nothing matched `readers`, and
# the ungated read was counted as the fifth gate.
INLINE_READS = ("open", "read_text", "read_bytes", "readlines")


# A read of MURSCOPE_HOME is not a read of a monitored project. The
# config, the roster and the board live there and Rule 7 is about the
# projects; keyed on the boundary itself rather than on a list of exempt
# modules, so it stays true when the code moves.
HOME_WORDS = ("home", "murscope_home", "MURSCOPE_HOME")


def _reads_the_home(src, call):
    text = ast.get_source_segment(src, call) or ""
    return any(re.search(r"\b%s\b" % re.escape(word), text)
               for word in HOME_WORDS)


def _inline_reads(node, src, constants):
    """Calls that read a caller-supplied path without a package callee."""
    tainted = tainted_names(node, src, constants)
    out = []
    for sub in ast.walk(node):
        if not isinstance(sub, ast.Call):
            continue
        called = (getattr(sub.func, "attr", None)
                  or getattr(sub.func, "id", None))
        if called not in INLINE_READS:
            continue
        holder = sub.func.value if isinstance(sub.func, ast.Attribute) else None
        parts = list(sub.args) + ([holder] if holder is not None else [])
        if _reads_the_home(src, sub):
            continue
        if any(_mentions(src, part, tainted) for part in parts if part is not None):
            out.append((sub, called))
    return out


# The scan and the permission probe read **existence and metadata only** -
# `os.walk`, `os.stat`, and one fixed `.git` pointer file that says whether
# a directory is a linked checkout. They never open a project's own files,
# so they cannot emit its contents, and that is the load-bearing reason
# rather than a fact about who calls them.
#
# The reason used to be "the scan runs before a roster exists, so nothing
# hands it a roster row", and it said in its own words that the line had to
# go if that changed. It had changed: a bare `murscope init` derives its
# roots from the existing roster, sensitive entries included, so the scanner
# was being handed exactly that. Two things followed - the reason is now the
# one that does not depend on the caller, and the wizard no longer rescans a
# sensitive entry's root, because walking inside one would put its
# subdirectory names on the summary screen.
#
# `is_worktree()` reading that pointer file is what made every caller of
# `scan.discover()` a reader and reported `selftest.main()` for running the
# selftest.
PRE_ROSTER = ("murscope/scan.py", "murscope/doctor.py",
              # The selftest is the runtime verifier of this very boundary
              # (DP65). It builds a sensitive project under a throwaway
              # MURSCOPE_HOME, collects it, and reads back the artifacts to
              # assert the decoy is absent - so every read it makes is of a
              # home it created, never of a user's project. Scoped out with
              # the reason rather than by renaming variables until the
              # home-read heuristic recognised them, which is the kind of
              # naming trick this file refuses elsewhere.
              #
              # It is the one entry here that is worth arguing with: if the
              # selftest ever reads a real roster project, this line is
              # wrong and has to go.
              "murscope/selftest.py")


def readers_below_gates(sources, module_names):
    """Direct readers that are not reached through a gate.

    Used by both passes now. `gate_findings` used to take the unrestricted
    transitive reader set, which made `cli.collect_records` a reader
    because it calls the gate - so a gate calling it was reported, and the
    selftest canary, whose whole job is to run the real collection path
    and prove nothing escapes, was flagged as the violation it exists to
    detect. Readerness stops at the gate (DP64) in both directions: below
    it the chain is ordinary, above it a reader is the finding.
    """
    functions = {}
    for name, src, tree in sources:
        constants = _module_constants(tree)
        holders = set(module_names) | set(_import_aliases(tree, module_names))
        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            body = ast.get_source_segment(src, node) or ""
            functions[node.name] = {
                "module": name,
                "gate": is_gate(node, src),
                "direct": bool(_inline_reads(node, src, constants)),
                "calls": {c for c in
                          (_callee(sub, holders) for sub in ast.walk(node)
                           if isinstance(sub, ast.Call)) if c},
            }
    below = {n for n, f in functions.items()
             if f["direct"] and not f["gate"]
             and f["module"] not in PRE_ROSTER}
    for _ in range(len(functions) + 1):
        grew = False
        for name, info in functions.items():
            if name in below or info["gate"] or info["module"] in PRE_ROSTER:
                continue
            if info["calls"] & below:
                below.add(name)
                grew = True
        if not grew:
            break
    return below


def gate_findings(tree, src, readers):
    """Readers called by a sensitivity-aware function must be gated.

    Calling a *gate* is exempt, and not as a convenience: a function that
    tests sensitivity is where the decision is made, so delegating to it is
    the correct thing to do rather than a way around the rule.
    `collect_project()` is both the gate and, transitively, a reader, and
    without this the selftest canary - whose entire job is to collect a
    sensitive entry and prove nothing escapes - was reported as the
    violation it exists to detect.
    """
    functions = {n.name: n for n in ast.walk(tree)
                 if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))}
    # Named apart from the `gates` counter below on purpose: the first
    # version of this collided with it and every call turned into
    # `str in int`.
    gate_names = {name for name, node in functions.items()
                  if is_gate(node, src)}
    constants = _module_constants(tree)
    findings = []
    gates = 0
    for name, node in sorted(functions.items()):
        if not is_gate(node, src):
            continue
        gates += 1
        guarded = set()
        for sub in ast.walk(node):
            if not isinstance(sub, ast.If):
                continue
            test = ast.get_source_segment(src, sub.test) or ""
            if GATE_WORD not in test:
                continue
            for branch in (sub.body, sub.orelse):
                for stmt in branch:
                    for inner in ast.walk(stmt):
                        guarded.add(id(inner))
        for sub in ast.walk(node):
            if not isinstance(sub, ast.Call):
                continue
            called = (getattr(sub.func, "id", None)
                      or getattr(sub.func, "attr", None))
            if called not in readers or called == name or called in gate_names:
                continue
            if id(sub) not in guarded:
                findings.append(
                    "%d: %s() calls the content reader %s() outside any `if` "
                    "testing %s. A sensitive entry must never be read, not "
                    "read and then filtered."
                    % (sub.lineno, name, called, GATE_WORD))
        for sub, called in _inline_reads(node, src, constants):
            if id(sub) in guarded:
                continue
            findings.append(
                "%d: %s() reads a caller-supplied path with %s() outside any "
                "`if` testing %s. An inline read has no callee name in this "
                "package, which is exactly why it has to be matched on its "
                "own - a gate that reads unconditionally is not a gate."
                % (sub.lineno, name, called, GATE_WORD))
    return findings, gates


def _import_aliases(tree, module_names):
    """Local name -> package module it refers to.

    `from . import collect as _c` then `_c.peek_notes(...)` escaped every
    earlier version of this pass, because the holder was `_c` and `_c` is
    not a module name. An audit walked content out of a sensitive project
    through exactly that, inside the module this rule claims to cover.
    """
    aliases = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                tail = alias.name.split(".")[-1]
                if tail in module_names:
                    aliases[alias.asname or tail] = tail
        elif isinstance(node, ast.ImportFrom):
            for alias in node.names:
                if alias.name in module_names:
                    aliases[alias.asname or alias.name] = alias.name
    return aliases


def _reader_variables(node, readers, holders):
    """Names bound to a reader: `probe = collect.peek_notes`.

    A function held in a variable was recorded as Known open and then
    demonstrated, so it stops being Known open. Only the plain shapes are
    traced - a direct assignment from a bare name or from a package module
    attribute - which is what an author writes when they are not trying to
    hide.
    """
    bound = set()
    for sub in ast.walk(node):
        if not isinstance(sub, ast.Assign):
            continue
        value = sub.value
        name = None
        if isinstance(value, ast.Name) and value.id in readers:
            name = value.id
        elif (isinstance(value, ast.Attribute)
              and isinstance(value.value, ast.Name)
              and value.value.id in holders
              and value.attr in readers):
            name = value.attr
        if name is None:
            continue
        for target in sub.targets:
            if isinstance(target, ast.Name):
                bound.add(target.id)
    return bound


def is_gate(node, src):
    """Does this function *test* sensitivity, rather than mention it?

    The model used to be "the body contains the word", and a body contains
    its comments: writing a comment that explains why a reader is safe made
    the reader a gate, and a gate that reads unconditionally is a finding -
    so documenting the boundary was punished by the check defending it. It
    happened twice, to the wizard and to `walk_tree`.

    A gate is a function that branches on sensitivity, which is what this
    check's own message has always said: "outside any `if` testing
    sensitive". Tests only - `if`, a conditional expression, a
    comprehension's filter.
    """
    for sub in ast.walk(node):
        tests = []
        if isinstance(sub, (ast.If, ast.IfExp)):
            tests.append(sub.test)
        elif isinstance(sub, (ast.ListComp, ast.SetComp, ast.GeneratorExp,
                              ast.DictComp)):
            for gen in sub.generators:
                tests.extend(gen.ifs)
        elif isinstance(sub, ast.While):
            tests.append(sub.test)
        for test in tests:
            if GATE_WORD in (ast.get_source_segment(src, test) or ""):
                return True
    return False


def _callee(call, module_names):
    """The package function this call names, or None.

    A bare name, or an attribute on one of the package's own modules.
    Without that restriction `subprocess.run` resolves to `cli.run` by
    name collision - a trap `content_readers()` documents above and one
    the first version of this pass walked straight into, reporting nine
    findings that were all the same collision.
    """
    if isinstance(call.func, ast.Attribute):
        holder = call.func.value
        if isinstance(holder, ast.Name) and holder.id in module_names:
            return call.func.attr
        return None
    if isinstance(call.func, ast.Name):
        return call.func.id
    return None


# The collector is the module that reads a roster entry's project, and it
# is where the audit demonstrated the leak. The caller rule is scoped to
# it deliberately - see the Known open note in this file's docstring for
# what that leaves uncovered and why a wider version needs taint rooted
# at the roster rather than at a function parameter.
COLLECTORS = ("murscope/collect.py", "murscope/ledger.py",
              "murscope/fingerprints.py", "murscope/activity.py")


def caller_findings(sources, module_names):
    """Every project reader must be reached from a gate.

    The hole this closes: an audit added a reader to collect.py, called it
    from `cli.collect_records` - a function that never mentions
    sensitivity - and collected the contents of a sensitive entry with
    point 4 green. Point 4 only looked *inside* gates, so a read that
    never entered one was invisible.

    **Readerness stops at the gate**, and that is the load-bearing detail.
    A first attempt allowed "a reader may be called by another reader",
    and it passed the constructed leak: `collect_records` counts as a
    reader because it calls the gate, so it conferred a permission it had
    borrowed from the gate itself. Propagation therefore does not cross a
    gate. Below the gate a reader may call a reader - that is the ordinary
    chain, `read_ledger` to `find_declaration` to `_read`. Above it,
    calling a reader means the gate is not on the path a sensitive entry
    takes.
    """
    functions = {}
    for name, src, tree in sources:
        constants = _module_constants(tree)
        # Module names plus whatever this file calls them locally.
        holders = set(module_names) | set(_import_aliases(tree, module_names))
        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            body = ast.get_source_segment(src, node) or ""
            functions[node.name] = {
                "module": name, "node": node, "src": src,
                "gate": GATE_WORD in body,
                "direct": bool(_inline_reads(node, src, constants)),
                "calls": {c for c in
                          (_callee(sub, holders) for sub in ast.walk(node)
                           if isinstance(sub, ast.Call)) if c},
                "holders": holders,
            }

    # What must be protected: functions that read a project. Propagation
    # stops at a gate, because a gate is the boundary rather than another
    # link in the chain.
    # One rule, stated once, after three layered attempts each of which
    # exempted the very thing it was meant to catch:
    #
    #   a *project reader* is a function in a collection module that itself
    #   opens a caller-supplied path;
    #   a call to one is allowed only from a gate, or from another project
    #   reader - the ordinary chain, `read_ledger` to `find_declaration` to
    #   `_read`;
    #   anything else calling one is a finding.
    #
    # What went wrong before is worth keeping: the set of permitted callers
    # was grown by a fixpoint that had no module filter, so `cli`'s
    # collector-caller joined the readers and exempted itself; and a
    # separate "anything a gate can reach" set exempted it a second way,
    # including through the selftest canary - the function whose job is to
    # prove a leak cannot happen was quietly licensing the function a leak
    # was demonstrated in. No fixpoint and no reachability now: membership
    # is decided by where a function is defined and what it does, which
    # cannot drift.
    readers = {n for n, f in functions.items()
               if f["direct"] and not f["gate"]
               and f["module"] in COLLECTORS}
    chain = {n for n, f in functions.items()
             if f["module"] in COLLECTORS and not f["gate"]}

    findings = []
    for name, info in sorted(functions.items()):
        if info["gate"] or name in chain or info["module"] in PRE_ROSTER:
            continue
        aliased = _reader_variables(info["node"], readers, info["holders"])
        for sub in ast.walk(info["node"]):
            if not isinstance(sub, ast.Call):
                continue
            called = _callee(sub, info["holders"])
            if called in aliased:
                called = "a reader held in %s" % called
                findings.append(
                    "%s:%d: %s() calls %s and never mentions %s."
                    % (info["module"], sub.lineno, name, called, GATE_WORD))
                continue
            if called is None or called not in readers or called == name:
                continue
            findings.append(
                "%s:%d: %s() calls the project reader %s() and never mentions "
                "%s. A reader has to be reached from a gate, or the gate is "
                "not on the path a sensitive entry takes."
                % (info["module"], sub.lineno, name, called, GATE_WORD))
    return findings


def entries(node):
    """Yield every dict inside an arbitrarily nested JSON document."""
    if isinstance(node, dict):
        yield node
        for value in node.values():
            for found in entries(value):
                yield found
    elif isinstance(node, list):
        for value in node:
            for found in entries(value):
                yield found


# Two payloads differing only in where the word sits. Prose must not make
# a gate; a test must. A probe rather than a `# case:` fixture because
# half of it is an expected *absence*, and Rule 1 requires every case in a
# pack to fire.
PROSE_ONLY = (b"def walk(entry, root):\n"
              b"    # a %s entry never reaches this reader\n"
              b"    return len(str(root))\n") % GATE_WORD.encode()
TEST_PRESENT = (b"def walk(entry, root):\n"
                b"    if entry.%s:\n"
                b"        pass\n"
                b"    return len(str(root))\n") % GATE_WORD.encode()


def check_model_precision():
    """A gate tests, it does not merely mention. Verified, not asserted."""
    findings = []
    src = PROSE_ONLY.decode()
    if is_gate(ast.parse(src).body[0], src):
        findings.append(
            "is_gate() calls a function a gate because its *comment* names "
            "sensitivity. That model punishes documenting the boundary: it "
            "made gates out of the wizard, and later out of walk_tree, and "
            "then reported their reads as ungated.")
    src = TEST_PRESENT.decode()
    if not is_gate(ast.parse(src).body[0], src):
        findings.append(
            "is_gate() no longer recognises `if entry.%s:` as a gate. "
            "Narrowing the model until nothing is a gate passes this file "
            "and deletes the rule." % GATE_WORD)
    return findings


def main():
    if not PACKAGE.is_dir():
        print("OK: murscope/ not present yet; nothing to inspect.")
        return 0

    files = sorted(PACKAGE.rglob("*.py"))
    definition = None
    uses = 0
    for path in files:
        src = path.read_text(encoding="utf-8")
        if WHITELIST not in src:
            continue
        tree = ast.parse(src, filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name) and target.id == WHITELIST:
                        definition = (path, node)
            elif isinstance(node, ast.Name) and node.id == WHITELIST and isinstance(node.ctx, ast.Load):
                uses += 1

    if definition is None:
        print("OK: %d file(s) inspected, no %s whitelist yet; the rule binds "
              "the moment the collector lands." % (len(files), WHITELIST))
        return 0

    path, assign = definition
    rel = path.relative_to(REPO_ROOT).as_posix()
    bad = 0

    gates = 0
    sources = []
    for candidate in files:
        candidate_src = candidate.read_text(encoding="utf-8")
        sources.append((candidate, candidate_src,
                        ast.parse(candidate_src, filename=str(candidate))))
    module_names = {path.stem for path in files}
    named_for_readers = [(c.relative_to(REPO_ROOT).as_posix(), src, tree)
                         for c, src, tree in sources]
    readers = readers_below_gates(named_for_readers, module_names)
    for candidate, candidate_src, candidate_tree in sources:
        # The scope statement above PRE_ROSTER applies to both passes. It
        # only reached the reader set at first, so the modules it names
        # were still examined as gates and the selftest was reported for
        # verifying the boundary it verifies.
        rel_name = candidate.relative_to(REPO_ROOT).as_posix()
        if rel_name in PRE_ROSTER:
            continue
        # Rule 7's subject is **collection**: the gate exists so that a
        # sensitive project's files are never opened while its row is being
        # built. A function elsewhere that merely branches on sensitivity is
        # not a collection gate, and treating it as one reported
        # `wizard.run()` for calling `guard_write_path()` the moment the
        # wizard learned to stop rescanning a sensitive root - a fix being
        # punished by the rule it was serving. The alternative was to keep
        # the word out of the wizard, which is the naming trick this file
        # refuses elsewhere.
        if rel_name not in COLLECTORS:
            continue
        findings, found = gate_findings(candidate_tree, candidate_src, readers)
        gates += found
        for finding in findings:
            print("%s:%s" % (candidate.relative_to(REPO_ROOT).as_posix(), finding))
            bad += 1
    named_sources = [(c.relative_to(REPO_ROOT).as_posix(), src, tree)
                     for c, src, tree in sources]
    for finding in caller_findings(named_sources, module_names):
        print(finding)
        bad += 1
    for finding in check_model_precision():
        print(finding)
        bad += 1

    if gates == 0:
        print("%s: %s is defined but nothing in the package gates collection "
              "on it. The whitelist filters output; the rule requires the "
              "reads not to happen." % (rel, WHITELIST))
        bad += 1

    for finding in detect(path.read_bytes()):
        print("%s:%s" % (rel, finding))
        bad += 1
    members = literal_members(assign.value) or []
    if uses == 0:
        print("%s: %s is declared but never read; a whitelist that is not "
              "applied is a comment." % (rel, WHITELIST))
        bad += 1

    allowed = set(members) | {"sensitive"}
    documents = 0
    for root_name in JSON_ROOTS:
        root = REPO_ROOT / root_name
        if not root.is_dir():
            continue
        for json_path in sorted(root.rglob("*.json")):
            try:
                doc = json.loads(json_path.read_text(encoding="utf-8"))
            except (ValueError, OSError):
                continue
            documents += 1
            json_rel = json_path.relative_to(REPO_ROOT).as_posix()
            for entry in entries(doc):
                if entry.get("sensitive") is not True:
                    continue
                extra = sorted(set(entry.keys()) - allowed)
                if extra:
                    print("%s: sensitive entry carries non-whitelisted key(s): %s"
                          % (json_rel, ", ".join(extra)))
                    bad += 1

    if bad:
        print("\nFAILED: %d sensitive-exposure violation(s)." % bad)
        return 1
    print("OK: %s holds %d key(s), is read at %d site(s), %d collection gate(s) "
          "keep every file reader behind a sensitivity test, and %d JSON "
          "document(s) stay inside it."
          % (WHITELIST, len(members), uses, gates, documents))
    return 0


if __name__ == "__main__":
    sys.exit(main())
