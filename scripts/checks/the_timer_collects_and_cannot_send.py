"""Rule 26: the timer collects and cannot send.

DP124 ruled that the first thing this product runs with nobody present
collects and renders, and never sends - **structurally, not by
configuration**. DP88 settled why the configured form will not do: a
capability the user has to go and audit a setting to rule out is a
capability that is on. So "the timer cannot send" has to be a property of
the call graph, and this is the check that reads it.

It starts at the scheduled entry point - `murscope.timer:main`, the
function the console script `murscope-timer` runs - walks every call it
can resolve inside the shipped package, and fails if the walk reaches a
transport doorway.

**A doorway is computed, not listed.** Three kinds:

  1. every function defined in a module that imports something able to
     open a socket, which on this product means the six adapters in the
     `[ai]` distribution;
  2. `registry.readers()`, `registry.writers()` and `registry.alerters()`,
     the core's only three ways to lay hands on a transport without naming
     one (Rule 16 is why they exist, and it is also why a name-based rule
     here would find nothing);
  3. any function that calls `.reads(...)`, `.writes(...)`, `.send(...)`
     or `.alerts(...)` on a value - the shape a resolved provider is
     driven through, which no static walk can follow to its target and
     which therefore has to be treated as arrival rather than as another
     edge.

**M4's second stage added the third lookup and the fourth attribute, and
that is this check widening rather than relaxing.** `registry.alerters()`
is how an alert reaches a wire, so a timer that could call it would be a
timer that could send - DP125's exception is for a *different entry point*
(`murscope-alert`, held by Rule 27), never for this one.

`provider.contribute(...)` is the one dynamic dispatch the timer's own
path really does make, and it is not left as a hole: every provider
module in the base package and in the extras distribution is read for
its `register(...)` call, and whatever it passes as `contribute` is added
to the walk as a root. Today all six extras adapters register
`contribute=None` and only `noop` registers a callable - which is a fact
this check re-derives on every run rather than a sentence somebody wrote
down once.

**The way this check could be worthless is by walking nowhere**, and that
is the failure DP87 exists to name: a guard whose window does not contain
the thing it watches reports green for the same reason an empty room
reports quiet. Three floors are asserted before any verdict is printed -
the walk must reach the collection and the render, the doorway set must
contain the three registry lookups and at least three functions from the
core, and the entry point must exist at all. Any of them failing is red,
not a skip and not a pass.

What exercises it: the walk runs over the real package on every gate run,
so `murscope/timer.py` and `murscope/cli.py` are its live inputs. Its
detector's own cases are in scripts/checks/fixtures/, and the reverse
verification is a send path spliced into the timer module, which this
check has been made to go red on rather than argued about.

Fails when: a transport doorway is reachable from the scheduled entry
point; or the entry point does not exist; or the walk cannot reach the
collection and render functions it is supposed to pass through; or the
doorway set loses the registry lookups or every core doorway; or a
provider registers a `contribute` this check cannot resolve.
"""
from __future__ import annotations

import ast
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
PACKAGE = REPO_ROOT / "murscope"
EXTRAS_ROOT = REPO_ROOT / "extras"
PACKAGE_NAME = "murscope"

# The scheduled entry point, as `pyproject.toml` declares it.
ENTRY = "murscope.timer:main"

# Module roots that can open a socket. The same list boundary.py carries,
# duplicated here on purpose: this check must be readable without
# importing the package it is checking, and a check that imports its
# subject can be fooled by its subject.
SOCKET_CAPABLE_ROOTS = {
    "urllib", "socket", "socketserver", "http", "ssl", "ftplib", "smtplib",
    "poplib", "imaplib", "telnetlib", "xmlrpc", "asyncio", "wsgiref",
    "requests", "httpx", "urllib3", "aiohttp", "websockets", "grpc",
    "boto3", "botocore", "paramiko", "anthropic", "openai", "_socket", "_ssl",
}

# The core's three capability lookups. Named here rather than discovered
# because they are the floor: if a rename empties this, the check must go
# red and be updated deliberately, not quietly certify a graph with no
# doorways in it.
REGISTRY_DOORWAYS = ("murscope.registry:readers", "murscope.registry:writers",
                     "murscope.registry:alerters")

# Attribute calls that mean a resolved provider is being driven. A static
# walk cannot follow `writer.writes(...)` to its target, so it stops there
# and calls it arrival.
TRANSPORT_ATTRS = {"reads", "writes", "send", "alerts"}

# The walk has to pass through these or it is not walking the thing it
# claims to walk (DP87). Stated as module:function so a rename is a red
# check rather than a silent narrowing.
MUST_REACH = (
    "murscope.cli:run",
    "murscope.cli:collect_records",
    "murscope.collect:collect_project",
    "murscope.render:render",
)


def module_name(path):
    """Dotted module name for a file in the package or in the extras tree."""
    parts = list(path.with_suffix("").parts)
    if PACKAGE_NAME not in parts:
        return ""
    index = len(parts) - 1 - parts[::-1].index(PACKAGE_NAME)
    return ".".join(parts[index:])


def source_files():
    """Every module this walk may enter: the package and the extras adapters."""
    files = {}
    for path in sorted(PACKAGE.rglob("*.py")):
        files[module_name(path)] = path
    for path in sorted(EXTRAS_ROOT.rglob("*.py")):
        if path.parent.name == "providers":
            files.setdefault(module_name(path), path)
    return files


def dotted(node):
    parts = []
    current = node
    while isinstance(current, ast.Attribute):
        parts.append(current.attr)
        current = current.value
    if isinstance(current, ast.Name):
        parts.append(current.id)
        return ".".join(reversed(parts))
    return ""


def socket_capable(tree):
    """Networking imports in one module. Same question boundary.py asks."""
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.split(".")[0] in SOCKET_CAPABLE_ROOTS:
                    return True
        elif isinstance(node, ast.ImportFrom) and not node.level:
            if (node.module or "").split(".")[0] in SOCKET_CAPABLE_ROOTS:
                return True
    return False


def bindings(tree, name, known_modules):
    """({alias: module}, {alias: 'module:symbol'}) for one module's imports.

    Relative imports are resolved against this module's own package, which
    is what makes `from . import cli` and `from .guard import murscope_home`
    two different kinds of answer: the first binds a module, the second
    binds a symbol inside one, and a call resolver that confused them would
    resolve `murscope_home()` to a module.
    """
    package = name.rsplit(".", 1)[0] if "." in name else name
    modules = {}
    symbols = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                modules[alias.asname or alias.name.split(".")[0]] = alias.name
        elif isinstance(node, ast.ImportFrom):
            if node.level:
                base = package
                for _ in range(node.level - 1):
                    base = base.rsplit(".", 1)[0] if "." in base else base
                base = "%s.%s" % (base, node.module) if node.module else base
            else:
                base = node.module or ""
            for alias in node.names:
                bound = alias.asname or alias.name
                candidate = "%s.%s" % (base, alias.name)
                if candidate in known_modules:
                    modules[bound] = candidate
                else:
                    symbols[bound] = "%s:%s" % (base, alias.name)
    return modules, symbols


def function_index(tree):
    """{name: node} for every function in a module, top level winning ties."""
    found = {}
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            found[node.name] = node
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            found.setdefault(node.name, node)
    return found


def doorways(tree):
    """[(lineno, function, why)] - the transport doorways in one module.

    The findings are facts about a module rather than accusations against
    it: in the timer's own file a doorway *is* the violation, and in
    `cli.py` the same fact is a node on the map main() walks against. The
    detector is one function because two would drift, and the difference
    between the two readings belongs in main() where the graph is.
    """
    owner = {}
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            for sub in ast.walk(node):
                owner.setdefault(id(sub), node.name)

    found = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        where = owner.get(id(node), "<module>")
        name = dotted(node.func)
        if name in ("registry.readers", "registry.writers",
                    "registry.alerters"):
            found.append((node.lineno, where, "calls %s()" % name))
        elif name in ("readers", "writers", "alerters"):
            found.append((node.lineno, where,
                          "calls %s(), the registry's capability lookup" % name))
        elif isinstance(node.func, ast.Attribute) \
                and node.func.attr in TRANSPORT_ATTRS:
            found.append((node.lineno, where,
                          "calls .%s(...) on a value, which is how a resolved "
                          "provider is driven" % node.func.attr))
    return found


def detect(payload):
    """Findings for one module: every transport doorway it contains.

    Pure - source in, list of strings out. Fed the timer's own module this
    is the whole of Rule 26; fed any other module it is the map.
    """
    try:
        tree = ast.parse(payload.decode("utf-8", errors="replace"))
    except SyntaxError as exc:
        return ["cannot parse (%s)." % exc]
    return ["%d: `%s` %s." % (lineno, where, why)
            for lineno, where, why in doorways(tree)]


def registered_contributors(tree, name):
    """('module:function', problem) for this module's registered contribute.

    A provider hands the core a callable and the core calls it during a
    run, which is the one edge in the timer's path no static walk can
    follow. Reading it out of the `register(...)` call is how the edge
    stops being a hole. `None` is an answer; a name this module does not
    define is a problem, because a contribute the check cannot resolve is
    a contribute it cannot certify.
    """
    roots = []
    problems = []
    functions = function_index(tree)
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call) or dotted(node.func).split(".")[-1] \
                != "register":
            continue
        for keyword in node.keywords:
            if keyword.arg != "contribute":
                continue
            value = keyword.value
            if isinstance(value, ast.Constant) and value.value is None:
                continue
            if isinstance(value, ast.Name) and value.id in functions:
                roots.append("%s:%s" % (name, value.id))
                continue
            problems.append(
                "%s:%d registers a `contribute` this check cannot resolve to "
                "a function in the same module, so it cannot say whether the "
                "timer's run reaches a transport through it."
                % (name, node.lineno))
    return roots, problems


def build_graph(files):
    """(edges, doorway_set, contributors, problems, unresolved).

    edges maps 'module:function' to the set of targets it calls that this
    resolver could name. An attribute call on a value is not an edge - it
    is either a doorway, above, or an unresolved call counted and
    reported, because a resolver that quietly drops what it cannot read is
    a resolver whose green means nothing.
    """
    trees = {}
    for name, path in files.items():
        try:
            trees[name] = ast.parse(path.read_bytes().decode("utf-8", "replace"))
        except SyntaxError as exc:
            return {}, set(), [], ["%s: cannot parse (%s)." % (name, exc)], 0

    known = set(trees)
    edges = {}
    doorway = set()
    contributors = []
    problems = []
    unresolved = 0

    for name, tree in trees.items():
        modules, symbols = bindings(tree, name, known)
        functions = function_index(tree)
        transport_module = socket_capable(tree)
        if transport_module:
            for function in functions:
                doorway.add("%s:%s" % (name, function))
        for lineno, where, _why in doorways(tree):
            if where != "<module>":
                doorway.add("%s:%s" % (name, where))
        if "providers" in name.split("."):
            roots, trouble = registered_contributors(tree, name)
            contributors.extend(roots)
            problems.extend(trouble)

        owner = {}
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                for sub in ast.walk(node):
                    owner.setdefault(id(sub), node.name)

        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            where = owner.get(id(node))
            if where is None:
                continue
            source = "%s:%s" % (name, where)
            target = None
            if isinstance(node.func, ast.Name):
                if node.func.id in symbols:
                    target = symbols[node.func.id]
                elif node.func.id in functions:
                    target = "%s:%s" % (name, node.func.id)
            elif isinstance(node.func, ast.Attribute) \
                    and isinstance(node.func.value, ast.Name):
                module = modules.get(node.func.value.id)
                if module in known:
                    target = "%s:%s" % (module, node.func.attr)
            if target is None:
                unresolved += 1
                continue
            edges.setdefault(source, set()).add(target)

    return edges, doorway, contributors, problems, unresolved


def reachable_from(edges, roots):
    seen = set()
    queue = list(roots)
    while queue:
        node = queue.pop()
        if node in seen:
            continue
        seen.add(node)
        queue.extend(edges.get(node, ()))
    return seen


def main():
    if not PACKAGE.is_dir():
        print("OK: murscope/ not present yet; nothing to inspect.")
        return 0

    files = source_files()
    edges, doorway, contributors, problems, unresolved = build_graph(files)
    for line in problems:
        print(line)

    bad = len(problems)

    # Floor one: the entry point exists. A walk from a function that is
    # not there reaches nothing and would otherwise report the strongest
    # possible result for the weakest possible reason.
    entry_module, entry_function = ENTRY.split(":")
    entry_tree_ok = False
    if entry_module in files:
        entry_tree = ast.parse(
            files[entry_module].read_bytes().decode("utf-8", "replace"))
        entry_tree_ok = entry_function in function_index(entry_tree)
    if not entry_tree_ok:
        print("%s does not exist. Rule 26 is a statement about what is "
              "reachable from the scheduled entry point, and there is nothing "
              "to walk from." % ENTRY)
        return 1

    reached = reachable_from(edges, [ENTRY] + contributors)

    # Floor two: the walk passes through the collection and the render.
    # This is the whole of DP87 for this check - a resolver that stopped
    # resolving would report an empty graph as a clean one.
    missing = [name for name in MUST_REACH if name not in reached]
    if missing:
        print("the walk from %s never reaches %s. That is this check "
              "reporting on itself: the timer is supposed to collect and "
              "render, so a graph that does not contain those is a graph "
              "this check cannot draw a conclusion from (DP87)."
              % (ENTRY, ", ".join(missing)))
        bad += 1

    # Floor three: the doorway set still has doorways in it, in the core as
    # well as in the extras tree. Extras adapters are doorways wholesale
    # because their modules import urllib; the core's two are the ones a
    # rename could quietly remove.
    for name in REGISTRY_DOORWAYS:
        if name not in doorway:
            module, function = name.split(":")
            tree = ast.parse(files[module].read_bytes().decode("utf-8", "replace")) \
                if module in files else None
            if tree is None or function not in function_index(tree):
                print("%s is gone. It is one of the two ways the core lays "
                      "hands on a transport without naming one, and this "
                      "check's doorway set is built around it." % name)
                bad += 1
            else:
                doorway.add(name)
    core_doorways = sorted(d for d in doorway
                           if d.startswith("murscope.")
                           and ".providers." not in d)
    if len(core_doorways) < 3:
        print("only %d transport doorway(s) found in the core (%s). The core "
              "drives every send through a resolved provider, so a doorway "
              "set this small means the detector stopped recognising the "
              "shape rather than that the shape stopped existing."
              % (len(core_doorways), ", ".join(core_doorways) or "none"))
        bad += 1

    hits = sorted(reached & doorway)
    for hit in hits:
        print("%s is reachable from %s. The timer collects and renders; it "
              "does not send, and DP124 asks for that structurally rather "
              "than as a setting somebody could change." % (hit, ENTRY))
        bad += 1

    if bad:
        print("\nFAILED: %d finding(s) against Rule 26." % bad)
        return 1
    print("OK: %d function(s) reachable from %s, none of them among the %d "
          "transport doorway(s) - %d in the core, %d in the extras adapters. "
          "The walk passes through %s. %d call(s) could not be resolved to a "
          "function in the package and are attribute calls on values, which "
          "the doorway rule covers by name rather than by edge; %d provider "
          "contribute callable(s) were read out of register() and walked."
          % (len(reached), ENTRY, len(doorway), len(core_doorways),
             len(doorway) - len(core_doorways), ", ".join(MUST_REACH),
             unresolved, len(contributors)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
