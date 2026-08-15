"""Rule 5: monitored projects are read only.

Static AST scan of the murscope/ package. This is the paired check
(DP31): for every git invocation it must hold that

  1. the subcommand is on the read-only allowlist, AND
  2. the environment handed to that specific call sets
     GIT_OPTIONAL_LOCKS=0.

Either half alone is not enough. Measured on a real repository, the same
subcommand rewrites .git/index without the variable and leaves it alone
with it, so allowlisting the subcommand name only would license a write.

The environment is matched structurally, not by grepping the source
text, and both idioms are accepted:

    env = os.environ.copy()
    env["GIT_OPTIONAL_LOCKS"] = "0"

    env = dict(os.environ, GIT_OPTIONAL_LOCKS="0")

Names are resolved in the call's own function scope plus module level,
so an unrelated `env` in a different function cannot launder a call. A
string that merely mentions the variable - env={"NOTE": 'GIT_OPTIONAL_
LOCKS="0"'} - is not a match, because the key and the value are compared
as AST constants.

It also holds the write boundary: every write must sit inside
guard_write_path(), the single entry point that refuses targets outside
MURSCOPE_HOME. Writes are detected by the method being called rather
than by the receiver being a bare name, so Path(p).write_text(...) and
open(p, "w") and `from os import remove` then remove(p) are all caught.
And it refuses unreadable invocations - shell=True, os.system(),
os.popen(), a non-literal argument list, a non-literal open() mode -
because a promise that cannot be verified by reading the source is not a
promise.

**M4 adds a second, narrower boundary, and it is not an exception.**
launchd reads its job description from ~/Library/LaunchAgents and systemd
from ~/.config/systemd/user, so `murscope timer install` cannot happen
inside MURSCOPE_HOME however anybody feels about it (DP126). The reply is
guard_schedule_write() and guard_schedule_remove(), which hold a table of
the exact paths they will ever touch and compare by equality. Their
bodies are exempt only after schedule_guard_spans() below has confirmed
four things - they raise, they ask permitted_schedule_paths() and hand it
nothing, that function declares no parameters, and the target is printed
*before* the write, measured by line number. The last of those is the
ruling itself: a permission for a path is a permission the user can read
in advance, and a permission for a command is one they cannot.

**And a fifth thing, about the table rather than the guards (DP154).**
The four above are all about the *shape* of the machinery, and for four
stages that was the whole of what any check knew about this boundary -
the contents of the table were reviewed by eye. Adding `.zshrc` to
SCHEDULE_JOBS left this check green, the gate green and the selftest
green, and `guard_schedule_write()` then overwrote a user's shell
configuration with every mechanism working exactly as designed: the path
was announced before it was written, because it was in the permitted set.
The selftest's own sentence moved with the table - "2 path(s)" became
"4 path(s)" - which is why it caught nothing. **A number measured from
the thing it describes reports; it does not constrain.** The reverse
mistake, a written-down count, pins the number and nothing else: a second
launch agent and a dotfile are the same arithmetic.

So what schedule_table_findings() asserts is not how many entries there
are but what an entry *is* - a job description belonging to this product,
in the one directory that platform's supervisor reads job descriptions
from, with a suffix that supervisor loads. By category, never by name
list: a new murscope job passes without this file being touched, and a
dotfile in the user's home does not, and neither does another program's
launch agent. permitted_set_findings() then asks the guard for the set it
actually computes, because a correct table and a function that turns it
into something else are two different facts.

The scope is the shipped package. Repository tooling under scripts/ is
not the product and is not scanned here.

Passes on the facts while the package has no git calls and no writes
(M0); becomes binding the moment either lands. It is never skipped: it
reports how many call sites it inspected.

Fails when: a git invocation uses an allowlisted subcommand but its call
site does not receive an environment that structurally sets
GIT_OPTIONAL_LOCKS to "0"; or uses a subcommand outside the allowlist;
or any write call happens outside guard_write_path() or the scheduling
guards; or a scheduling guard does not raise, or takes its permitted set
from its caller, or writes a path it has not printed first; or
permitted_schedule_paths() declares a parameter; or a subprocess
invocation, or an open() mode, cannot be read statically; or the table of
paths this package may write outside MURSCOPE_HOME cannot be read as
literals, names a platform this check has no supervisor description for,
or permits anything that is not a job description of this product's own
in that supervisor's directory - measured on the table and again on the
set the guard computes from it, which must agree.
"""
from __future__ import annotations

import ast
import os
import re
import sys
from pathlib import Path, PurePosixPath

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
PACKAGE = REPO_ROOT / "murscope"

GUARD = "guard_write_path"
# The scheduling guards (DP126). They are not exceptions to the write
# boundary; they are a second, much narrower one, and schedule_guard_spans()
# below states the four things each has to be before its body is exempt.
SCHEDULE_GUARDS = ("guard_schedule_write", "guard_schedule_remove")
PERMITTED_SET = "permitted_schedule_paths"
# The two tables the permission is made of: the one written as literals,
# and the flat view everything downstream reads.
SCHEDULE_TABLE = "SCHEDULE_JOBS"
DERIVED_TABLE = "SCHEDULE_FILES"

# **What a job description is, per platform, as a category (DP154).** Not
# a second copy of guard.py's table - a description of the class every
# entry in it has to belong to, so that adding a job needs no edit here
# and adding a dotfile is refused with a reason.
#
# Each value is (the one per-user directory that supervisor reads job
# descriptions from, the suffixes it will load out of it). Both halves are
# facts about launchd and systemd rather than preferences: launchd loads
# per-user agents from ~/Library/LaunchAgents and reads property lists,
# systemd loads user units from ~/.config/systemd/user and reads .service
# and .timer. A platform absent from here is refused rather than waved
# through, because a supervisor nobody described is a supervisor whose
# entries nothing can judge.
JOB_DESCRIPTION = {
    "darwin": ("Library/LaunchAgents", (".plist",)),
    "linux": (".config/systemd/user", (".service", ".timer")),
}
# The namespace a permitted job has to be in, read off the package
# directory rather than typed, so it is this product's own name by
# construction. Without it the table could name another program's launch
# agent, which is in the right directory with the right suffix and is
# still somebody else's.
NAMESPACE = PACKAGE.name
WORD = re.compile(r"[^a-z0-9]+")
LOCKS_KEY = "GIT_OPTIONAL_LOCKS"
LOCKS_VALUE = "0"
HOME_VAR = "MURSCOPE_HOME"

# Read-only git subcommands. Conservative on purpose: a subcommand is
# added here only when it cannot mutate the repository it is pointed at.
ALLOWED_SUBCOMMANDS = {
    "log", "show", "status", "diff", "rev-parse", "rev-list",
    "for-each-ref", "ls-files", "ls-tree", "cat-file", "shortlog",
    "describe", "symbolic-ref", "count-objects", "var",
}
# Subcommands that are read-only only in a specific form.
ALLOWED_PAIRS = {
    ("stash", "list"),
    ("branch", "--list"),
    ("config", "--get"),
    ("config", "--get-all"),
    ("config", "--list"),
    ("remote", "-v"),
    ("remote", "get-url"),
    ("tag", "--list"),
    ("worktree", "list"),
}

SUBPROCESS_FUNCS = {
    "run", "check_output", "check_call", "call", "Popen",
    "getoutput", "getstatusoutput",
}
# The package shells out to exactly one program. Skipping non-git
# programs let rm -rf and /bin/sh -c through a green gate.
ALLOWED_PROGRAMS = {"git"}

# Method names that write, whatever the receiver is. Every one of these
# is unambiguous: no common non-writing object exposes them.
ALWAYS_WRITE_ATTRS = {
    "write_text", "write_bytes", "writelines", "truncate",
    "mkdir", "makedirs", "touch", "unlink", "rmdir", "removedirs",
    "rmtree", "copytree", "copyfile", "copy2", "copystat", "make_archive",
    "symlink_to", "hardlink_to", "chmod", "lchmod", "chown",
}
# Ambiguous names, matched only through a module prefix or an imported
# alias: os.remove(p) and `from os import remove` both write, but
# some_list.remove(x) does not.
OS_WRITE_FUNCS = {
    "makedirs", "mkdir", "remove", "unlink", "rmdir", "removedirs",
    "rename", "renames", "replace", "symlink", "link", "chmod", "chown",
    "truncate", "mkfifo", "mknod", "utime", "write",
}
SHUTIL_WRITE_FUNCS = {
    "copy", "copy2", "copyfile", "copytree", "copystat", "move",
    "rmtree", "make_archive", "unpack_archive", "chown",
}
# Ambiguous names disambiguated by call shape. Path.replace(target) and
# Path.rename(target) take one positional argument; str.replace takes
# two and datetime.replace takes keywords. shutil.copy/move take two.
ARITY_WRITE_ATTRS = {"replace": 1, "rename": 1, "copy": 2, "move": 2}

# "+" is the one that gets missed: open(p, "r+") writes and contains
# none of w, a or x.
WRITE_MODES = set("wax+")


def attr_of(func):
    """Method name for an attribute call, whatever the receiver is."""
    if isinstance(func, ast.Attribute):
        return func.attr
    return None


def dotted(func):
    """Dotted name for a call target, or None when the base is not a Name."""
    parts = []
    cur = func
    while isinstance(cur, ast.Attribute):
        parts.append(cur.attr)
        cur = cur.value
    if isinstance(cur, ast.Name):
        parts.append(cur.id)
        return ".".join(reversed(parts))
    return None


def const_str(node):
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    return None


def import_aliases(tree):
    """Names bound by `from <module> import <name>`, per module."""
    found = {"subprocess": set(), "os": set(), "shutil": set()}
    for node in ast.walk(tree):
        if not isinstance(node, ast.ImportFrom) or node.module not in found:
            continue
        for alias in node.names:
            found[node.module].add((alias.asname or alias.name, alias.name))
    return found


def module_aliases(tree):
    """Local names for whole modules: `import os as o` binds o -> os."""
    found = {}
    for node in ast.walk(tree):
        if not isinstance(node, ast.Import):
            continue
        for alias in node.names:
            if alias.name in ("os", "shutil", "subprocess"):
                found[alias.asname or alias.name] = alias.name
    return found


def canonical(name, modules):
    """Rewrite a dotted call name through its module alias."""
    if not name or "." not in name:
        return name
    head, rest = name.split(".", 1)
    return "%s.%s" % (modules.get(head, head), rest)


def dict_sets_locks(node, constants=None):
    """True for an expression that structurally sets the variable.

    Covers a dict literal, dict(os.environ, GIT_OPTIONAL_LOCKS="0"), and
    the 3.9 merge operator os.environ.copy() | {...}. Keys held in a
    module constant are resolved through `constants`, so naming the key
    once - LOCKS = "GIT_OPTIONAL_LOCKS" - is not punished.
    """
    constants = constants or {}
    if isinstance(node, ast.Dict):
        for key, value in zip(node.keys, node.values):
            if key_is_locks(key, constants) and const_str(value) == LOCKS_VALUE:
                return True
        return False
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.BitOr):
        return (dict_sets_locks(node.left, constants)
                or dict_sets_locks(node.right, constants))
    if isinstance(node, ast.Call) and getattr(node.func, "id", None) == "dict":
        for kw in node.keywords:
            if kw.arg == LOCKS_KEY and const_str(kw.value) == LOCKS_VALUE:
                return True
        for arg in node.args:
            if dict_sets_locks(arg, constants):
                return True
    return False


def key_is_locks(node, constants):
    """The key is the variable, whether spelled literally or via a name."""
    if const_str(node) == LOCKS_KEY:
        return True
    if isinstance(node, ast.Name) and constants.get(node.id) == LOCKS_KEY:
        return True
    return False


def string_constants(tree):
    """Names bound anywhere in the module to a plain string literal."""
    found = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign) and const_str(node.value) is not None:
            for target in node.targets:
                if isinstance(target, ast.Name):
                    found[target.id] = const_str(node.value)
    return found


SCOPE_NODES = (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Lambda)


def iter_scope(body_nodes):
    """Walk these statements without descending into a nested scope.

    ast.walk would happily cross a `def` boundary, which is how a locked
    env in one function ends up vouching for a bare call in another.
    """
    stack = [n for n in body_nodes if not isinstance(n, SCOPE_NODES)]
    while stack:
        node = stack.pop()
        yield node
        for child in ast.iter_child_nodes(node):
            if not isinstance(child, SCOPE_NODES):
                stack.append(child)


def locked_names(body_nodes, constants=None):
    """Names proven, inside this one scope, to carry the variable.

    Recognises the three real idioms and nothing else:
      X = {"GIT_OPTIONAL_LOCKS": "0", ...}   / dict(..., GIT_OPTIONAL_LOCKS="0")
      X["GIT_OPTIONAL_LOCKS"] = "0"
      X.update({"GIT_OPTIONAL_LOCKS": "0"})
    """
    constants = constants or {}
    good = set()
    for sub in iter_scope(body_nodes):
        if isinstance(sub, ast.Assign):
            if dict_sets_locks(sub.value, constants):
                for target in sub.targets:
                    if isinstance(target, ast.Name):
                        good.add(target.id)
            if const_str(sub.value) == LOCKS_VALUE:
                for target in sub.targets:
                    if (isinstance(target, ast.Subscript)
                            and isinstance(target.value, ast.Name)
                            and key_is_locks(_index(target), constants)):
                        good.add(target.value.id)
        elif isinstance(sub, ast.Call):
            if attr_of(sub.func) == "update" and sub.args:
                base = dotted(sub.func)
                if base and dict_sets_locks(sub.args[0], constants):
                    good.add(base.rsplit(".", 1)[0])
    return good


def _index(subscript):
    """Subscript key, across the 3.8 and 3.9+ AST shapes."""
    node = subscript.slice
    if isinstance(node, ast.Index):  # pragma: no cover - Python 3.8
        node = node.value
    return node


def scope_index(tree):
    """Map every node to the statement body of its enclosing function."""
    module_body = tree.body
    owner = {}
    # ast.walk is breadth-first, so nested functions are visited after
    # their parents and the innermost scope wins the assignment.
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            for child in ast.walk(node):
                owner[child] = node.body
    return module_body, owner


def function_index(tree):
    """Map every node to its enclosing FunctionDef, innermost winning."""
    owner = {}
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            for child in ast.walk(node):
                owner[child] = node
    return owner


def bound_names(funcdef, body_nodes):
    """Every name this scope binds: parameters, assignments, loop targets.

    Closing M0's known-open on this check. The old version asked "is the
    name locked here, or locked at module level" as a union, so a
    function with its own unlocked `env` was vouched for by an unrelated
    locked `env` somewhere else in the file. Shadowing has to be visible
    before that can be refused, and this is what makes it visible.
    """
    names = set()
    if funcdef is not None:
        args = funcdef.args
        for group in (getattr(args, "posonlyargs", []), args.args, args.kwonlyargs):
            names.update(a.arg for a in group)
        if args.vararg:
            names.add(args.vararg.arg)
        if args.kwarg:
            names.add(args.kwarg.arg)
    for sub in iter_scope(body_nodes):
        if isinstance(sub, ast.Assign):
            for target in sub.targets:
                if isinstance(target, ast.Name):
                    names.add(target.id)
        elif isinstance(sub, (ast.AugAssign, ast.AnnAssign)):
            if isinstance(sub.target, ast.Name):
                names.add(sub.target.id)
        elif isinstance(sub, (ast.For, ast.AsyncFor)):
            if isinstance(sub.target, ast.Name):
                names.add(sub.target.id)
        elif isinstance(sub, ast.withitem) and isinstance(sub.optional_vars, ast.Name):
            names.add(sub.optional_vars.id)
    return names


def env_ok(call, module_body, owner, functions, constants, fn_owner=None):
    """True when this call site hands git an env that sets the variable.

    Accepts the three things a careful author actually writes:
      a literal dict, or dict(os.environ, ...), or the 3.9 merge form
      a local or module-level name that was locked in this scope
      a call to a helper whose body provably locks the environment

    The helper form matters most. Factoring the locked environment into
    one function is how the invariant stops being forgeable, and the
    check refusing it would have pushed the next author to loosen the
    check instead of writing the helper.
    """
    for kw in call.keywords:
        if kw.arg != "env":
            continue
        if dict_sets_locks(kw.value, constants):
            return True
        if isinstance(kw.value, ast.Name):
            scope = owner.get(call, [])
            funcdef = (fn_owner or {}).get(call)
            # Resolve in this scope first. A local binding of the same
            # name shadows the module-level one, so a locked module
            # constant must not vouch for a local `env` that was never
            # locked - the hole this check documented as open at M0.
            if kw.value.id in bound_names(funcdef, scope):
                return kw.value.id in locked_names(scope, constants)
            return kw.value.id in locked_names(module_body, constants)
        if isinstance(kw.value, ast.Call):
            name = dotted(kw.value.func)
            target = functions.get(name) if name else None
            if target is not None and function_locks_env(target, constants):
                return True
        return False
    return False


def function_locks_env(funcdef, constants=None):
    """True when this function body provably produces a locked env."""
    if locked_names(funcdef.body, constants):
        return True
    for node in ast.walk(funcdef):
        if isinstance(node, ast.Return) and node.value is not None:
            if dict_sets_locks(node.value, constants):
                return True
    return False


def argv_of(call):
    if not call.args:
        return None
    first = call.args[0]
    if isinstance(first, (ast.List, ast.Tuple)):
        return [const_str(e) for e in first.elts]
    return None


def git_subcommand(argv):
    i = 1
    while i < len(argv):
        token = argv[i]
        if token is None:
            return None
        if token in ("-C", "-c", "--git-dir", "--work-tree", "--namespace"):
            i += 2
            continue
        if token.startswith("-"):
            i += 1
            continue
        return token
    return None


def guard_spans(tree, src):
    """Line ranges of guard_write_path(), and complaints about fakes.

    The exemption used to be granted on the function's name alone, which
    means any writer could be waved through by being called
    guard_write_path. A guard that neither knows about MURSCOPE_HOME nor
    raises is not a guard, and its body does not get the exemption.
    """
    spans = []
    problems = []
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        if node.name != GUARD:
            continue
        body = ast.get_source_segment(src, node) or ""
        raises = any(isinstance(sub, ast.Raise) for sub in ast.walk(node))
        knows_home = HOME_VAR in body
        if raises and knows_home:
            spans.append((node.lineno, getattr(node, "end_lineno", node.lineno)))
            continue
        missing = []
        if not knows_home:
            missing.append("never mentions %s" % HOME_VAR)
        if not raises:
            missing.append("never raises")
        problems.append((node.lineno, ", ".join(missing)))
    return spans, problems


def _write_calls_in(node):
    """[(lineno, {names touched})] for the write calls inside one function."""
    found = []
    for sub in ast.walk(node):
        if not isinstance(sub, ast.Call):
            continue
        name = dotted(sub.func) or ""
        attr = sub.func.attr if isinstance(sub.func, ast.Attribute) else ""
        writes = False
        if name == "open" or attr == "open":
            mode, readable = open_mode(sub)
            writes = (not readable) or bool(set(mode or "") & WRITE_MODES)
        elif name.startswith("os.") and name.rsplit(".", 1)[-1] in OS_WRITE_FUNCS:
            writes = True
        elif attr in ALWAYS_WRITE_ATTRS:
            writes = True
        if writes:
            names = {n.id for n in ast.walk(sub) if isinstance(n, ast.Name)}
            found.append((sub.lineno, names))
    return found


def schedule_guard_spans(tree, src):
    """Line ranges of the scheduling guards, and complaints about fakes.

    DP126: installing a timer is the first deliberate write outside
    MURSCOPE_HOME in this product's life, because a scheduler will not
    read its job description from anywhere but its own directory. The
    permission granted is **for a path, on an explicit command, printed
    before it is written** - and the difference between that and a
    permission for a command is the whole ruling, so it is measured here
    rather than trusted.

    Four things earn the exemption, and the shape of each one is chosen so
    that the obvious way to cheat it fails:

    - it raises, exactly as guard_write_path() must;
    - it asks permitted_schedule_paths() which targets it may touch, and
      **passes it nothing**. A permitted set the caller can influence is
      not a permitted set, and an argument is the only way to influence a
      function that takes none;
    - permitted_schedule_paths() itself declares no parameters, checked
      below, so the table cannot be widened from a call site either;
    - the target is printed **before** the write, measured by line number
      from the parse tree, and the print names the same variable the write
      acts on. Reading the source for the word "print" would pass a guard
      that logs the path afterwards, and a path named after the fact is a
      receipt rather than a chance to say no. This is case ck's method -
      a refusal after the request is built is a refusal that arrives late.
    """
    spans = []
    problems = []
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        if node.name == PERMITTED_SET:
            arguments = node.args
            declared = (len(arguments.posonlyargs) if hasattr(
                arguments, "posonlyargs") else 0) + len(arguments.args) \
                + len(arguments.kwonlyargs) \
                + (1 if arguments.vararg else 0) + (1 if arguments.kwarg else 0)
            if declared:
                problems.append(
                    (node.lineno,
                     "%s() takes %d parameter(s), so the complete set of "
                     "paths this package may write outside MURSCOPE_HOME can "
                     "be widened from a call site. It must take none: DP126 "
                     "grants a path, and a table any caller can extend is not "
                     "a table of paths."
                     % (PERMITTED_SET, declared)))
            continue
        if node.name not in SCHEDULE_GUARDS:
            continue

        missing = []
        if not any(isinstance(sub, ast.Raise) for sub in ast.walk(node)):
            missing.append("never raises")
        asks = [sub for sub in ast.walk(node)
                if isinstance(sub, ast.Call)
                and (dotted(sub.func) or "").split(".")[-1] == PERMITTED_SET]
        if not asks:
            missing.append("never asks %s() which paths it may touch"
                           % PERMITTED_SET)
        elif any(call.args or call.keywords for call in asks):
            missing.append("hands %s() an argument, so its permitted set is "
                           "whatever its caller says it is" % PERMITTED_SET)

        writes = _write_calls_in(node)
        if writes:
            announced = False
            for sub in ast.walk(node):
                if not isinstance(sub, ast.Call) or dotted(sub.func) != "print":
                    continue
                said = {n.id for n in ast.walk(sub) if isinstance(n, ast.Name)}
                if all(sub.lineno < lineno and (said & names)
                       for lineno, names in writes):
                    announced = True
                    break
            if not announced:
                missing.append(
                    "touches the filesystem at line(s) %s without printing "
                    "that same target first. DP126 grants a path, named "
                    "before it is written"
                    % ", ".join(str(lineno) for lineno, _n in writes))

        if missing:
            problems.append((node.lineno,
                             "%s() %s, so it is not a scheduling guard and "
                             "its body gets no exemption. This is the one "
                             "place murscope writes outside MURSCOPE_HOME, "
                             "and DP126 grants a path rather than a command."
                             % (node.name, ", ".join(missing))))
        else:
            spans.append((node.lineno,
                          getattr(node, "end_lineno", node.lineno)))
    return spans, problems


def job_description_findings(relative, platform):
    """Why this relative path is not a job description on `platform`, or [].

    Three questions, and each one is a category rather than a name:

    - **is it a plain relative path under the user's home?** `home / rel`
      on an absolute or climbing `rel` is not under the home at all, which
      is the Rule 17 shape - the join reads as contained and is not;
    - **is it in the directory that supervisor reads?** launchd will not
      load an agent out of the user's home directory and systemd will not
      load a unit out of `~/Documents`. A path somewhere else is not a job
      description that failed to work; it is a file this product would be
      writing for some other reason;
    - **is it a file that supervisor loads, in this product's namespace?**
      The suffix is what the scheduler reads; the namespace is what makes
      it *ours*. `~/Library/LaunchAgents/com.apple.something.plist` passes
      the first two and is another program's job.

    None of the three mentions an entry that exists today, which is the
    point: the table may grow a job without this function changing, and it
    may not grow a shell configuration file.
    """
    directory, suffixes = JOB_DESCRIPTION[platform]
    text = str(relative)
    path = PurePosixPath(text)
    if (not text or path.is_absolute() or ".." in path.parts
            or text.startswith("~") or "\\" in text):
        return ["%r is not a plain relative path under the user's home "
                "directory, so what it joins to is not something this file "
                "can read" % text]

    problems = []
    if path.parent.as_posix() != directory:
        problems.append(
            "it sits in %r, and the supervisor on %s reads job descriptions "
            "out of %r and out of nowhere else"
            % (path.parent.as_posix(), platform, directory))
    if path.suffix not in suffixes:
        problems.append(
            "its suffix is %r, and that supervisor loads %s"
            % (path.suffix, " or ".join(repr(s) for s in suffixes)))
    if NAMESPACE not in WORD.split(path.name.lower()):
        problems.append(
            "%r is not in this product's own namespace, so the table would be "
            "granting a write to a file belonging to something else"
            % path.name)
    return problems


def _module_assignments(tree, name):
    """Every module-level `name = ...`, as Assign nodes.

    Module level rather than anywhere: this is a constant, and a binding
    inside a function is not the table the guard reads.
    """
    return [node for node in tree.body
            if isinstance(node, ast.Assign)
            and any(isinstance(target, ast.Name) and target.id == name
                    for target in node.targets)]


def schedule_table_findings(tree):
    """(findings, entries) for the table of paths permitted outside the home.

    `entries` is [(platform, relative)] for everything the table declares,
    so the caller can say how many walked into this rather than printing a
    green line about a table it never found (DP87).
    """
    findings = []
    entries = []
    for node in _module_assignments(tree, SCHEDULE_TABLE):
        try:
            table = ast.literal_eval(node.value)
        except (ValueError, SyntaxError, TypeError, MemoryError):
            findings.append(
                "%d: %s is not written as literals, so the complete set of "
                "paths this package may write outside MURSCOPE_HOME cannot be "
                "read here at all. DP126 grants a set of paths, and a set "
                "nobody can read before the write is not one."
                % (node.lineno, SCHEDULE_TABLE))
            continue
        if not isinstance(table, dict) or not table:
            findings.append(
                "%d: %s is %s rather than a non-empty table of platform to "
                "jobs." % (node.lineno, SCHEDULE_TABLE, type(table).__name__))
            continue
        for platform, jobs in sorted(table.items()):
            if platform not in JOB_DESCRIPTION:
                findings.append(
                    "%d: %s declares platform %r, and this check knows what a "
                    "job description is on %s only. An entry judged by nobody "
                    "is the state this assertion exists to end."
                    % (node.lineno, SCHEDULE_TABLE, platform,
                       " and ".join(sorted(JOB_DESCRIPTION))))
                continue
            for entry in jobs or ():
                if not (isinstance(entry, (tuple, list)) and len(entry) == 2
                        and isinstance(entry[1], (tuple, list))):
                    findings.append(
                        "%d: %s[%r] holds %r, which is not a (job, paths) "
                        "pair. An entry this file cannot take apart is an "
                        "entry it cannot judge."
                        % (node.lineno, SCHEDULE_TABLE, platform, entry))
                    continue
                job, relatives = entry
                for relative in relatives:
                    if not isinstance(relative, str):
                        findings.append(
                            "%d: %s[%r] job %r permits %r, which is not a "
                            "path." % (node.lineno, SCHEDULE_TABLE, platform,
                                       job, relative))
                        continue
                    entries.append((platform, relative))
                    for why in job_description_findings(relative, platform):
                        findings.append(
                            "%d: %s[%r] job %r permits %r, and %s. This table "
                            "is the whole of what murscope may write outside "
                            "MURSCOPE_HOME; every mechanism around it - the "
                            "equality test, the announcement before the write "
                            "- works exactly as designed on whatever is in "
                            "here, which is why what is in here is asserted "
                            "rather than reviewed (DP154)."
                            % (node.lineno, SCHEDULE_TABLE, platform, job,
                               relative, why))
    return findings, entries


def derived_table_findings(tree):
    """The flat table has to be derived from the job table, never rewritten.

    Everything that asks "what may this package write outside
    MURSCOPE_HOME" reads the flat one. A second table written out by hand
    would be a second answer, and the categorical assertion above would
    then be made against the copy nobody uses.
    """
    findings = []
    for node in _module_assignments(tree, DERIVED_TABLE):
        names = {sub.id for sub in ast.walk(node.value)
                 if isinstance(sub, ast.Name)}
        literals = [sub.value for sub in ast.walk(node.value)
                    if isinstance(sub, ast.Constant)
                    and isinstance(sub.value, str)]
        if SCHEDULE_TABLE not in names or literals:
            findings.append(
                "%d: %s is not derived from %s - %s. The two are one fact, "
                "and the moment they are two the assertion on %s is being "
                "made against a table nothing reads."
                % (node.lineno, DERIVED_TABLE, SCHEDULE_TABLE,
                   "it carries %d string literal(s) of its own" % len(literals)
                   if literals else "it never mentions it", SCHEDULE_TABLE))
    return findings


def permitted_set_findings():
    """(findings, paths) - the set the guard computes, on this platform.

    The static half reads the table; this asks the module the product
    asks. They are not the same evidence - a table can be correct while
    the function that turns it into absolute paths reads something else -
    and the pairing is the one Rule 17 already uses, pointed at the one
    write this product makes outside its own home.

    Nothing is written and nothing is removed here: `permitted_schedule_
    paths()` computes names. Red rather than quiet when the module cannot
    be imported, because a check that cannot reach its own subject reports
    on nothing and would print a green line about it (DP87).
    """
    sys.path.insert(0, str(REPO_ROOT))
    try:
        from murscope import guard  # noqa: PLC0415 - the live half only
    except Exception as exc:
        return ["the guard could not be imported (%s: %s), so the set it "
                "computes was never measured. This half is red rather than "
                "silent." % (type(exc).__name__, exc)], []

    findings = []
    home = Path(os.path.expanduser("~")).resolve()
    paths = tuple(guard.permitted_schedule_paths())
    known = sys.platform in JOB_DESCRIPTION
    if not known:
        if paths:
            findings.append(
                "%d path(s) are permitted outside MURSCOPE_HOME on %s and "
                "this check has no supervisor description for that platform, "
                "so none of them was judged."
                % (len(paths), sys.platform))
        return findings, paths

    live = []
    for path in paths:
        try:
            relative = path.relative_to(home).as_posix()
        except ValueError:
            findings.append(
                "%s is in the permitted set and does not resolve inside the "
                "user's home directory at all. The set is computed as `home / "
                "relative`, so a path that left the home did not come from a "
                "relative name." % path)
            continue
        live.append(relative)
        for why in job_description_findings(relative, sys.platform):
            findings.append(
                "%s is in the live permitted set and %s. This is the set "
                "`guard_schedule_write()` compares against, so it is the one "
                "that decides what gets written." % (path, why))

    declared = sorted({relative
                       for _job, relatives in guard.SCHEDULE_JOBS.get(
                           sys.platform, ())
                       for relative in relatives})
    if sorted(set(live)) != declared:
        findings.append(
            "the live permitted set holds %s and %s declares %s for this "
            "platform. Everything downstream compares against the first and "
            "the categorical assertion is made against the second; two "
            "answers means one of them is not being checked."
            % (", ".join(sorted(set(live))) or "(nothing)", SCHEDULE_TABLE,
               ", ".join(declared) or "(nothing)"))
    return findings, paths


def inside(spans, lineno):
    return any(start <= lineno <= end for start, end in spans)


def open_mode(call):
    """(mode, readable) for an open() call in either builtin or Path form."""
    is_method = isinstance(call.func, ast.Attribute)
    positional = 0 if is_method else 1
    node = None
    if len(call.args) > positional:
        node = call.args[positional]
    for kw in call.keywords:
        if kw.arg == "mode":
            node = kw.value
    if node is None:
        return "r", True
    mode = const_str(node)
    if mode is None:
        return None, False
    return mode, True


def report_writes(node, name, attr, aliases):
    """Return a message when this call writes outside the guard."""
    os_alias = {bound: real for bound, real in aliases["os"] if real in OS_WRITE_FUNCS}
    shutil_alias = {bound: real for bound, real in aliases["shutil"] if real in SHUTIL_WRITE_FUNCS}

    if name in os_alias:
        return "os.%s() via `from os import %s`" % (os_alias[name], name)
    if name in shutil_alias:
        return "shutil.%s() via `from shutil import %s`" % (shutil_alias[name], name)
    if name and name.startswith("os.") and name.rsplit(".", 1)[-1] in OS_WRITE_FUNCS:
        return "%s()" % name
    if name and name.startswith("shutil.") and name.rsplit(".", 1)[-1] in SHUTIL_WRITE_FUNCS:
        return "%s()" % name
    if attr in ALWAYS_WRITE_ATTRS:
        return ".%s()" % attr
    if attr in ARITY_WRITE_ATTRS and not node.keywords:
        if len(node.args) == ARITY_WRITE_ATTRS[attr]:
            return ".%s() with %d argument(s), the filesystem form" % (attr, len(node.args))
    return None


def detect(payload, stats=None):
    """Findings for one module of the package. Pure: source in, list out.

    M0 recorded one hole here and M1 closed it: an `env` name bound at
    module level and shadowed by an unlocked local of the same name
    inside a function used to resolve against the module-level binding
    and pass. Names are now resolved in the call's own scope first, with
    parameters and loop targets counted as bindings, and only a name
    this scope never binds falls through to module level.

    Known open, recorded so the next reader does not rediscover it: an
    env dict built by mutating a locked copy through an alias
    (`other = env; other["X"] = "y"`) is not tracked, and a locked env
    passed through a function parameter is only accepted when the callee
    is named at the call site. Both need real dataflow; neither has any
    code in this package today.
    """
    stats = stats if stats is not None else {}
    for key in ("subprocess", "git", "open", "write", "permitted", "tables"):
        stats.setdefault(key, 0)
    src = payload.decode("utf-8", errors="replace")
    try:
        tree = ast.parse(src)
    except SyntaxError as exc:
        return ["cannot parse (%s)." % exc]

    aliases = import_aliases(tree)
    modules = module_aliases(tree)
    constants = string_constants(tree)
    subprocess_names = {bound for bound, real in aliases["subprocess"] if real in SUBPROCESS_FUNCS}
    module_body, owner = scope_index(tree)
    fn_owner = function_index(tree)
    functions = {n.name: n for n in ast.walk(tree)
                 if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))}
    spans, guard_problems = guard_spans(tree, src)
    schedule_spans, schedule_problems = schedule_guard_spans(tree, src)
    spans = spans + schedule_spans

    findings = []
    for lineno, why in guard_problems:
        findings.append(
            "%d: %s() %s, so it is not a write guard and its body gets no "
            "exemption. Verifying a guard by its name is how a writer walks "
            "through by renaming itself." % (lineno, GUARD, why))
    for lineno, why in schedule_problems:
        findings.append("%d: %s" % (lineno, why))

    # The contents of the permitted table, not the shape of the guards
    # around it (DP154). Counted, so main() can refuse to report on a table
    # it never found.
    table_findings, permitted = schedule_table_findings(tree)
    findings.extend(table_findings)
    findings.extend(derived_table_findings(tree))
    stats["permitted"] += len(permitted)
    stats["tables"] += len(_module_assignments(tree, SCHEDULE_TABLE))

    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        raw = dotted(node.func)
        name = canonical(raw, modules)
        attr = attr_of(node.func)
        tail = (name or "").rsplit(".", 1)[-1]

        if name in ("os.system", "os.popen"):
            findings.append("%d: %s() is refused: the command cannot be read "
                            "statically." % (node.lineno, name))
            continue

        is_subprocess = (
            (tail in SUBPROCESS_FUNCS and (name or "").startswith("subprocess."))
            or raw in subprocess_names
        )
        if is_subprocess:
            stats["subprocess"] += 1
            for kw in node.keywords:
                if kw.arg == "shell" and getattr(kw.value, "value", None) is True:
                    findings.append("%d: shell=True is refused: the command "
                                    "cannot be read statically." % node.lineno)
            argv = argv_of(node)
            if argv is None:
                findings.append("%d: subprocess call with a non-literal argument "
                                "list; the program cannot be verified read-only."
                                % node.lineno)
                continue
            if not argv or argv[0] is None:
                findings.append("%d: subprocess call whose program is not a "
                                "string literal." % node.lineno)
                continue

            program = argv[0].rsplit("/", 1)[-1]
            if program not in ALLOWED_PROGRAMS:
                findings.append(
                    "%d: subprocess program '%s' is not on the allowlist %s. The "
                    "package shells out to git and nothing else; skipping other "
                    "programs let `rm -rf` and `/bin/sh -c` write into a "
                    "monitored project on a green gate."
                    % (node.lineno, argv[0], sorted(ALLOWED_PROGRAMS)))
                continue

            stats["git"] += 1
            sub = git_subcommand(argv)
            second = None
            if sub is not None:
                idx = argv.index(sub)
                if idx + 1 < len(argv):
                    second = argv[idx + 1]
            if sub is None:
                findings.append("%d: git call with no readable subcommand." % node.lineno)
            elif sub not in ALLOWED_SUBCOMMANDS and (sub, second) not in ALLOWED_PAIRS:
                findings.append("%d: git subcommand '%s' is not on the read-only "
                                "allowlist %s."
                                % (node.lineno, sub, sorted(ALLOWED_SUBCOMMANDS)))
            if not env_ok(node, module_body, owner, functions, constants, fn_owner):
                findings.append(
                    '%d: git call does not receive an environment setting %s="%s" '
                    "(DP31: the subcommand allowlist is only half of Rule 5)."
                    % (node.lineno, LOCKS_KEY, LOCKS_VALUE))
            continue

        if inside(spans, node.lineno):
            continue

        if name == "open" or attr == "open" or name == "io.open":
            stats["open"] += 1
            mode, readable = open_mode(node)
            if not readable:
                findings.append("%d: open() with a non-literal mode outside %s(); "
                                "Rule 5 cannot be verified by reading the source."
                                % (node.lineno, GUARD))
            elif set(mode) & WRITE_MODES:
                findings.append("%d: write-mode open(mode=%r) outside %s()."
                                % (node.lineno, mode, GUARD))
            continue

        message = report_writes(node, name, attr, aliases)
        if message:
            stats["write"] += 1
            findings.append("%d: %s outside %s()." % (node.lineno, message, GUARD))

    return findings


def check_file(path, rel, stats):
    bad = 0
    for finding in detect(path.read_bytes(), stats):
        print("%s:%s" % (rel, finding))
        bad += 1
    return bad


def main():
    if not PACKAGE.is_dir():
        print("OK: murscope/ not present yet; nothing to inspect.")
        return 0

    files = sorted(PACKAGE.rglob("*.py"))
    stats = {"subprocess": 0, "git": 0, "open": 0, "write": 0,
             "permitted": 0, "tables": 0}
    bad = 0
    for path in files:
        bad += check_file(path, path.relative_to(REPO_ROOT).as_posix(), stats)

    # DP87, as a floor rather than an assumption: the categorical assertion
    # above judges whatever table it found, and a package where it found
    # none would produce no findings and a green line about a boundary
    # nothing looked at. There is exactly one table, in one module.
    if stats["tables"] != 1:
        print("murscope/: %d module(s) define %s. The set of places this "
              "package may write outside MURSCOPE_HOME is one table read in "
              "one place; %s, so the assertion about what may be in it "
              "inspected %d entry(ies)."
              % (stats["tables"], SCHEDULE_TABLE,
                 "none was found" if not stats["tables"]
                 else "this build has more than one", stats["permitted"]))
        bad += 1

    live, permitted = permitted_set_findings()
    for finding in live:
        print("murscope/guard.py: %s" % finding)
        bad += 1

    if bad:
        print("\nFAILED: %d read-only violation(s)." % bad)
        return 1
    print("OK: %d file(s) in murscope/ inspected, %d subprocess call site(s), "
          "%d git call site(s), %d open() call site(s); every git call read-only "
          "and locks-free, every write behind %s() or the %d scheduling "
          "guard(s) %s, which name a target before they write it. The %d "
          "path(s) %s permits outside MURSCOPE_HOME are each a job "
          "description of this product's own, in the directory that "
          "platform's supervisor reads them from and with a suffix it loads; "
          "the %d of them live on %s were measured off the guard itself, not "
          "off the table."
          % (len(files), stats["subprocess"], stats["git"], stats["open"],
             GUARD, len(SCHEDULE_GUARDS),
             " and ".join("%s()" % name for name in SCHEDULE_GUARDS),
             stats["permitted"], SCHEDULE_TABLE, len(permitted), sys.platform))
    return 0


if __name__ == "__main__":
    sys.exit(main())
