"""Rule 27: the alert entry point sends only the alert.

DP125 ruled that an alert may leave the machine while nobody is present.
That is an exception to DP124, and the whole difference between an
exception and a hole is whether anything measures its edges. Rule 26
measures one edge - `murscope-timer` reaches no transport at all. This
check measures the other one: **`murscope-alert` reaches the alert's
transport and no other payload's.**

It starts at `murscope.alert:main`, the function the console script
`murscope-alert` runs, walks every call it can resolve inside the shipped
package, and fails if the walk reaches anything on the forbidden list.

**What is permitted, and it is exactly one thing.**
`registry.alerters()` and a `.alerts(...)` call on a value are how an
alert reaches a wire, and delivering an alert is what this entry point is
for. Everything else that could put bytes on a socket is forbidden:

  * `registry.readers()` and `registry.writers()` - the core's other two
    capability lookups. Reaching either would mean this entry point could
    drive the contributions reader or a daily-note adapter, which are
    payloads nobody consented to on the alert's disclosure;
  * `outbound.build`, `outbound.canonical` and `outbound.payload_digest` -
    the daily note's payload, by name, because the note's eight numbers
    per project are a different document under a different fingerprint;
  * `contributions.reading_documents` and
    `contributions.measurement_documents` - the reading's payload, for the
    same reason;
  * any function calling `.reads(...)`, `.writes(...)` or `.send(...)` on
    a value. `.alerts(...)` is the one attribute call permitted, so the
    difference between "can deliver an alert" and "can drive any resolved
    provider" is a difference this walk can see.

**The way this check could be worthless is by walking nowhere** (DP87),
and the failure would be quiet in the most convenient direction: an entry
point that resolves to nothing reaches no forbidden target either, and
this file would print a green line about a graph with one node in it. So
four floors are asserted before any verdict:

  1. the entry point exists;
  2. the walk passes through `murscope.cli:alert_command`,
    `murscope.cli:collect_records`, `murscope.alerts:evaluate` and
    `murscope.alerts:build` - an alert entry point that never reaches the
    evaluation or the payload builder is not walking the thing this rule
    is about;
  3. the walk reaches the permitted doorway `murscope.registry:alerters`.
    A graph that cannot even deliver would satisfy every prohibition here
    by being unable to do anything, and would certify a product where
    alerts silently never leave;
  4. the forbidden set resolves to functions that actually exist. A
    forbidden name that has been renamed away is a prohibition over
    nothing, so each one is looked up in the parse tree and a miss is red.

What exercises it: the walk runs over the real package on every gate run,
so `murscope/alert.py`, `murscope/cli.py` and `murscope/alerts.py` are its
live inputs. The detector's own cases are in
scripts/checks/fixtures/the_alert_entry_point_sends_only_the_alert.txt -
a module reaching `registry.writers()`, one calling `outbound.build`, and
one driving a provider through `.writes(...)`. The reverse verification is
each of those spliced into `murscope/alert.py` and `murscope/cli.py` for
real, which this check has been made to go red on rather than argued
about.

Fails when: a forbidden target is reachable from the alert entry point;
or the entry point does not exist; or the walk cannot reach the alert
evaluation and payload builder it is supposed to pass through; or the
walk cannot reach the one doorway it is permitted; or a forbidden name no
longer resolves to a function in the package.
"""
from __future__ import annotations

import ast
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
PACKAGE = REPO_ROOT / "murscope"
PACKAGE_NAME = "murscope"

# The scheduled alert entry point, as `pyproject.toml` declares it.
ENTRY = "murscope.alert:main"

# The one capability lookup this entry point may reach, and the one
# attribute call that drives it. Named rather than discovered, because
# they are the permission and a permission that widens by itself is not
# one (the same argument DP128 makes about the scheduling paths).
PERMITTED_DOORWAY = "murscope.registry:alerters"
PERMITTED_ATTR = "alerts"

# Every core function reaching one of these means the alert entry point
# can put a payload other than an alert on a wire.
FORBIDDEN = (
    "murscope.registry:readers",
    "murscope.registry:writers",
    "murscope.outbound:build",
    "murscope.outbound:canonical",
    "murscope.outbound:payload_digest",
    "murscope.contributions:reading_documents",
    "murscope.contributions:measurement_documents",
)

# Attribute calls that mean a resolved provider is being driven for
# something other than an alert. A static walk cannot follow
# `writer.writes(...)` to its target, so it stops there and calls it
# arrival - the same treatment Rule 26 gives the same shape.
FORBIDDEN_ATTRS = {"reads", "writes", "send"}

# The walk has to pass through these or it is not walking the thing it
# claims to walk (DP87). Stated as module:function so a rename is a red
# check rather than a silent narrowing.
MUST_REACH = (
    "murscope.cli:alert_command",
    "murscope.cli:collect_records",
    "murscope.alerts:evaluate",
    "murscope.alerts:build",
)


def module_name(path):
    parts = list(path.with_suffix("").parts)
    if PACKAGE_NAME not in parts:
        return ""
    index = len(parts) - 1 - parts[::-1].index(PACKAGE_NAME)
    return ".".join(parts[index:])


def source_files():
    """Every module this walk may enter. The core only.

    The extras adapters are deliberately not read here, and that is the
    difference between this rule and Rule 26. Rule 26 has to know which
    modules can open a socket because it forbids reaching any of them;
    this one forbids reaching *the core functions that build somebody
    else's payload*, and those are all under murscope/. An adapter is
    reached through `.alerts(...)`, which is arrival rather than an edge.
    """
    return {module_name(path): path for path in sorted(PACKAGE.rglob("*.py"))}


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


def bindings(tree, name, known_modules):
    """({alias: module}, {alias: 'module:symbol'}) for one module's imports."""
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
    found = {}
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            found[node.name] = node
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            found.setdefault(node.name, node)
    return found


def owners(tree):
    owner = {}
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            for sub in ast.walk(node):
                owner.setdefault(id(sub), node.name)
    return owner


def detect(payload):
    """Findings for one module: every non-alert transport shape it holds.

    Pure - source in, list of strings out. Fed `murscope/alert.py` or any
    module the alert entry point reaches, a finding here is the whole of
    Rule 27; fed the daily note's command it is simply a description of
    what that command legitimately does, and `main()` below is where the
    difference between the two readings lives, because that is where the
    graph is.
    """
    try:
        tree = ast.parse(payload.decode("utf-8", errors="replace"))
    except SyntaxError as exc:
        return ["cannot parse (%s)." % exc]

    owner = owners(tree)
    findings = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        where = owner.get(id(node), "<module>")
        name = dotted(node.func)
        tail = name.split(".")[-1] if name else ""
        if tail in ("readers", "writers") and name in (
                "registry.readers", "registry.writers", "readers", "writers"):
            findings.append(
                "%d: `%s` calls %s(), a capability lookup that resolves a "
                "provider for a payload other than an alert."
                % (node.lineno, where, name))
        elif name.startswith("outbound.") and tail in (
                "build", "canonical", "payload_digest"):
            findings.append(
                "%d: `%s` calls %s(), which is the daily note's payload."
                % (node.lineno, where, name))
        elif isinstance(node.func, ast.Attribute) \
                and node.func.attr in FORBIDDEN_ATTRS:
            findings.append(
                "%d: `%s` calls .%s(...) on a value, which is how a resolved "
                "provider is driven for something that is not an alert."
                % (node.lineno, where, node.func.attr))
    return findings


def build_graph(files):
    """(edges, forbidden_hits, permitted_hits, problems, unresolved).

    `forbidden_hits` maps 'module:function' to the reason it counts, for
    every function holding a forbidden shape. It is a superset of
    FORBIDDEN: a named function is forbidden by name, and any function
    driving a provider through `.writes(...)` is forbidden by shape.
    """
    trees = {}
    for name, path in files.items():
        try:
            trees[name] = ast.parse(path.read_bytes().decode("utf-8", "replace"))
        except SyntaxError as exc:
            return {}, {}, set(), ["%s: cannot parse (%s)." % (name, exc)], 0

    known = set(trees)
    edges = {}
    forbidden = {}
    permitted = set()
    problems = []
    unresolved = 0

    for name in FORBIDDEN:
        forbidden[name] = "is on this rule's forbidden list by name"

    for name, tree in trees.items():
        modules, symbols = bindings(tree, name, known)
        functions = function_index(tree)
        owner = owners(tree)

        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            where = owner.get(id(node))
            if where is None:
                continue
            source = "%s:%s" % (name, where)
            called = dotted(node.func)
            tail = called.split(".")[-1] if called else ""

            if called in ("registry.alerters", "alerters") \
                    or (isinstance(node.func, ast.Attribute)
                        and node.func.attr == PERMITTED_ATTR):
                permitted.add(source)
            if called in ("registry.readers", "registry.writers",
                          "readers", "writers") and tail in ("readers",
                                                             "writers"):
                forbidden.setdefault(
                    source, "calls %s(), a capability lookup for a payload "
                            "that is not an alert" % called)
            elif isinstance(node.func, ast.Attribute) \
                    and node.func.attr in FORBIDDEN_ATTRS:
                forbidden.setdefault(
                    source, "calls .%s(...) on a value, which drives a "
                            "resolved provider for something that is not an "
                            "alert" % node.func.attr)

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

    return edges, forbidden, permitted, problems, unresolved


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
    edges, forbidden, permitted, problems, unresolved = build_graph(files)
    for line in problems:
        print(line)
    bad = len(problems)

    # Floor one: the entry point exists.
    entry_module, entry_function = ENTRY.split(":")
    entry_ok = False
    if entry_module in files:
        tree = ast.parse(
            files[entry_module].read_bytes().decode("utf-8", "replace"))
        entry_ok = entry_function in function_index(tree)
    if not entry_ok:
        print("%s does not exist. Rule 27 is a statement about what is "
              "reachable from the alert entry point, and there is nothing to "
              "walk from." % ENTRY)
        return 1

    reached = reachable_from(edges, [ENTRY])

    # Floor two: the walk passes through the evaluation and the builder.
    missing = [name for name in MUST_REACH if name not in reached]
    if missing:
        print("the walk from %s never reaches %s. That is this check "
              "reporting on itself: the alert entry point is supposed to "
              "evaluate the rules and build an alert payload, so a graph "
              "that does not contain those is a graph this check cannot "
              "draw a conclusion from (DP87)."
              % (ENTRY, ", ".join(missing)))
        bad += 1

    # Floor three: it can still reach the one doorway it is allowed. A
    # product where an alert can never leave would pass every prohibition
    # in this file by being unable to do anything at all.
    if PERMITTED_DOORWAY not in reached:
        print("the walk from %s never reaches %s, the one transport doorway "
              "this rule permits. An alert entry point that cannot deliver "
              "satisfies every prohibition here for the wrong reason - DP125 "
              "asked for an exception that works, not for one that is "
              "unreachable." % (ENTRY, PERMITTED_DOORWAY))
        bad += 1
    if not permitted & reached:
        print("no function reachable from %s drives a provider through "
              ".%s(...). The permitted shape is what distinguishes this rule "
              "from a rule forbidding everything, and a walk that never "
              "sees it is not measuring the distinction."
              % (ENTRY, PERMITTED_ATTR))
        bad += 1

    # Floor four: each forbidden name still resolves to a real function. A
    # prohibition over a name nothing defines forbids nothing.
    for name in FORBIDDEN:
        module, function = name.split(":")
        tree = ast.parse(files[module].read_bytes().decode("utf-8", "replace")) \
            if module in files else None
        if tree is None or function not in function_index(tree):
            print("%s is on the forbidden list and does not exist. A rule "
                  "that forbids a name nothing defines forbids nothing; "
                  "update the list deliberately." % name)
            bad += 1

    hits = sorted(reached & set(forbidden))
    for hit in hits:
        print("%s is reachable from %s and %s. The alert entry point may "
              "send an alert and may send nothing else - DP125's exception "
              "is for one payload, and an exception nobody measures the "
              "edges of is a hole." % (hit, ENTRY, forbidden[hit]))
        bad += 1

    if bad:
        print("\nFAILED: %d finding(s) against Rule 27." % bad)
        return 1
    print("OK: %d function(s) reachable from %s, none of them among the %d "
          "forbidden target(s). The walk passes through %s, and it does "
          "reach %s - the one doorway this rule permits, driven through "
          ".%s(...) by %d function(s). %d call(s) could not be resolved to a "
          "function in the package and are attribute calls on values, which "
          "the forbidden-attribute rule covers by name rather than by edge."
          % (len(reached), ENTRY, len(forbidden), ", ".join(MUST_REACH),
             PERMITTED_DOORWAY, PERMITTED_ATTR, len(permitted & reached),
             unresolved))
    return 0


if __name__ == "__main__":
    sys.exit(main())
