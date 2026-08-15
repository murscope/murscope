"""Rule 24: one read window, one permitted set, and no way to have two.

**The shape this exists for, stated before the mechanics.** Three times a
guard in `murscope/selftest.py` measured a stretch of code narrower than
the sentence it printed, and each fix widened the *window* until it was
the whole run. The fourth time was the mirror image and it lived inside
the fix for the third: two assertions over the same whole-run window, each
assembling its own permitted set by hand, and the two sets differed by
exactly the project roots step 4 is asked to collect. On any machine whose
roster is not empty - every machine that has run `murscope init` - step 4
read a listed project on purpose and step 6 called it a stray read.
`murscope selftest` exited 1 for every such user while the gate stayed
green, because the gate only ever ran the selftest against a throwaway
home with no roster in it (DP114).

Patching the second call site would have made it green and left the shape
intact. What this check enforces instead is that the shape cannot be
written down:

1. **the window is stated once.** `since(...)` is called in exactly one
   place, inside `ReadWindow.opened`, and its argument is the literal `0`.
   A narrowed window - `since(mark)`, `since(3)` - is a finding, and so is
   a second caller stating a window of its own;
2. **the permitted set is stated once.** `_stray_reads` is called in
   exactly one place, inside `ReadWindow.strays`. A second caller is a
   second permitted set for one window, which is DP114 word for word;
3. **no assertion may narrow either half.** Every `strays()` call takes no
   arguments, so there is no parameter through which a step could pass a
   different window or a shorter list of roots;
4. **the permitted set is registered where roots are acquired.** `permit()`
   has to be called from at least two places - the sandboxes and the roots
   step 4 collects - or the accumulator is decorative and the roots are
   travelling by some other route again. **A floor, and only a floor**: it
   catches `permit()` going out of use, not the loss of any one root, and
   the sentence at the bottom of this docstring once claimed otherwise.

**What walks into this check (DP87), and what makes it red rather than
green when it cannot reach.** Two instruments:

* the static half above, over `murscope/selftest.py` read as a parse tree.
  If the file holds no `ReadWindow` class, no `strays` method, no
  `since(0)` call, no `_stray_reads` call or fewer than two `strays()`
  call sites, this check says so and **fails**. Those counts are the
  subject; a check that certifies a file it could not find anything in is
  the failure this repository has spent three milestones removing;
* **a live sensitivity probe** on the shipped `ReadWindow`. A path is
  recorded under a directory, the directory is permitted, and the window
  must report no stray; the same window built without that permit must
  report exactly that path. The static half alone would pass on a
  `strays()` that ignored its permitted set entirely and returned nothing,
  which is precisely a guard whose window is wider than its sentence,
  arrived at from the other end;
* **a simulated `sys.pycache_prefix`**, because the interpreter this half
  is about is not in the matrix. Apple's `/usr/bin/python3` sets that
  prefix to a directory under the user's home, and the assertion called
  the interpreter's own cache entries stray reads of a project there and
  nowhere else - red on `origin/main`, invisible to CI (DP117). Six shapes
  are asserted in both directions: a cached `.pyc` and the `<name>.pyc.<id>`
  CPython opens before renaming it must be permitted, and a README, a
  source file, a `.pyc.<not digits>` and a `.pyc` outside the prefix must
  still be strays. The first repair permitted only names ending in `.pyc`,
  so it was green on every run but the first after a code change - which is
  the run right after every edit, and a guard that is red only then teaches
  a reader to run it twice.

Between them they answer the reverse question the acceptance window asked:
narrow any step's permitted set and something goes red. **That something
is one thing and it is not this check (DP122).** Deleting a `permit()`
call turns a `murscope selftest` run red - the roots it permitted are then
read and unpermitted - while point 4 above is a floor with room under it,
so this check keeps exiting 0 with its printed call-site count one lower.
Every `permit()` site in `murscope/selftest.py` was deleted in turn and
both gate runs measured: the sandbox permits redden both, and the two that
register a root the roster named are green on the empty roster and red
only on the non-empty one - which is why the gate runs the selftest twice.

This docstring used to claim two independent reds. It was wrong in the way
this repository keeps finding: **a sentence stating what a check covers,
with nobody having run the case it describes.** What this check covers is
the shape - one window, one permitted set, no narrowing at a call site -
and that is a different guarantee from "this particular root is
permitted", which belongs to the selftest run and is stated there.

Fails when: `murscope/selftest.py` calls `since()` with anything but the
literal 0; calls `since()` from outside `ReadWindow.opened`; calls
`_stray_reads()` from outside `ReadWindow.strays`; passes any argument to
a `strays()` call; defines no `ReadWindow` class or no `strays` method on
it; registers permits from fewer than two call sites; holds fewer than two
`strays()` call sites; the shipped `ReadWindow` reports the same strays
whether or not a root is permitted; or, with `sys.pycache_prefix`
simulated, a cached `.pyc` or the name CPython writes before renaming it
is reported as a stray, or a README, a source file, a `.pyc.<not digits>`
or a `.pyc` outside the prefix is permitted.
"""
from __future__ import annotations

import ast
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
SELFTEST = REPO_ROOT / "murscope" / "selftest.py"

WINDOW_CLASS = "ReadWindow"
WINDOW_METHOD = "strays"
WINDOW_OPENER = "opened"
RECORDER_METHOD = "since"
PERMIT_METHOD = "permit"
RAW_ASSERTION = "_stray_reads"

# The two call sites the assertion is made from. Fewer than this and the
# static half is certifying a file that stopped doing the thing.
MINIMUM_ASSERTIONS = 2
# The sandboxes and the roots step 4 collects, at the least.
MINIMUM_PERMIT_SITES = 2


def _enclosing(tree):
    """{node: (class name or '', function name or '')} for every node."""
    where = {}

    def walk(node, cls, fn):
        for child in ast.iter_child_nodes(node):
            if isinstance(child, ast.ClassDef):
                walk(child, child.name, fn)
            elif isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                walk(child, cls, child.name)
            else:
                where[child] = (cls, fn)
                walk(child, cls, fn)
        where[node] = (cls, fn)

    walk(tree, "", "")
    return where


def _attr_calls(tree, name):
    """Every `<something>.name(...)` call in the tree."""
    return [node for node in ast.walk(tree)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == name]


def _plain_calls(tree, name):
    """Every `name(...)` call in the tree."""
    return [node for node in ast.walk(tree)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == name]


def _source_of(node):
    """The argument as it was written, for a message a reader can act on."""
    if node is None:
        return ""
    unparse = getattr(ast, "unparse", None)
    if unparse is not None:
        try:
            return unparse(node)
        except Exception:
            pass
    return type(node).__name__


def _assertion_sites(tree, where):
    """Every `.strays()` call made from outside the window object itself."""
    return [call for call in _attr_calls(tree, WINDOW_METHOD)
            if where.get(call, ("", "")) != (WINDOW_CLASS, WINDOW_METHOD)]


def _permit_sites(tree, where):
    """Every `.permit()` call made from outside the window object itself."""
    return [call for call in _attr_calls(tree, PERMIT_METHOD)
            if where.get(call, ("", ""))[0] != WINDOW_CLASS]


def detect(payload):
    """Findings for a selftest-shaped source: window and permits apart.

    Pure - source in, findings out. Fed the real `murscope/selftest.py` by
    `main()` and each fixture case by Rule 1's binding check.
    """
    source = payload.decode("utf-8", errors="replace")
    try:
        tree = ast.parse(source)
    except SyntaxError as exc:
        return ["cannot parse (%s), so the window and its permits cannot be "
                "read at all." % exc]

    findings = []
    where = _enclosing(tree)

    window_class = None
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and node.name == WINDOW_CLASS:
            window_class = node
    if window_class is None:
        findings.append(
            "no class %s. The window and the permitted set are one object on "
            "purpose; without it they are two things that can disagree, which "
            "is what left `selftest` red for every user with a roster."
            % WINDOW_CLASS)
        strays_method = None
    else:
        strays_method = next(
            (n for n in window_class.body
             if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
             and n.name == WINDOW_METHOD), None)
        if strays_method is None:
            findings.append(
                "%s defines no %s(). That method is the only place a window "
                "and a permitted set are allowed to meet."
                % (WINDOW_CLASS, WINDOW_METHOD))

    def inside_opener(node):
        return where.get(node, ("", "")) == (WINDOW_CLASS, WINDOW_OPENER)

    def inside_strays(node):
        return where.get(node, ("", "")) == (WINDOW_CLASS, WINDOW_METHOD)

    # 1. The window is the whole run, and it is opened in one place.
    since_calls = _attr_calls(tree, RECORDER_METHOD)
    for call in since_calls:
        argument = call.args[0] if call.args else None
        whole_run = (isinstance(argument, ast.Constant)
                     and argument.value == 0
                     and not isinstance(argument.value, bool))
        if not whole_run:
            findings.append(
                "%d: the read window is opened with .%s(%s). The window is the "
                "whole run and the literal 0 is how that is written down; a "
                "mark narrows it to a stretch of code where the thing being "
                "guarded against may not happen, which this file has found "
                "three times."
                % (call.lineno, RECORDER_METHOD, _source_of(argument)))
        elif not inside_opener(call):
            findings.append(
                "%d: .%s() is called outside %s.%s. A second caller is a "
                "second statement of the window, and a second statement is "
                "free to be a shorter one than the permitted set was measured "
                "against."
                % (call.lineno, RECORDER_METHOD, WINDOW_CLASS, WINDOW_OPENER))

    # 2. The permitted set is assembled in one place.
    for call in _plain_calls(tree, RAW_ASSERTION):
        if not inside_strays(call):
            findings.append(
                "%d: %s() is called outside %s.%s, so this call site states a "
                "permitted set of its own. Two hand-assembled sets over one "
                "window is DP114 exactly: they differed by the projects the "
                "roster lists, and `murscope selftest` exited 1 on every "
                "machine that had run `init`."
                % (call.lineno, RAW_ASSERTION, WINDOW_CLASS, WINDOW_METHOD))

    # 3. No assertion may narrow either half through an argument.
    assertions = _assertion_sites(tree, where)
    for call in assertions:
        if call.args or call.keywords:
            findings.append(
                "%d: .%s() is called with argument(s). It takes none on "
                "purpose - an argument is a way for one step to assert over a "
                "window or a root list that the next step's assertion never "
                "sees." % (call.lineno, WINDOW_METHOD))

    # 4. Permits are registered where roots are acquired, from more than one
    #    place, or the accumulator is decorative.
    permit_sites = _permit_sites(tree, where)

    # Reachability, and each of these is a finding rather than a silent pass
    # (DP87): a file this check found nothing in is a file it cannot certify.
    if not since_calls:
        findings.append(
            "no .%s() call anywhere, so this file opens no read window and "
            "every absence below would be an absence of nothing."
            % RECORDER_METHOD)
    if not _plain_calls(tree, RAW_ASSERTION):
        findings.append(
            "no %s() call anywhere, so nothing compares what was opened "
            "against what was permitted." % RAW_ASSERTION)
    if len(assertions) < MINIMUM_ASSERTIONS:
        findings.append(
            "%d read-location assertion(s) - .%s() called from outside the "
            "window object - and %d is the floor. The defect this rule exists "
            "for was two assertions disagreeing; with fewer than two there is "
            "nothing here to hold together."
            % (len(assertions), WINDOW_METHOD, MINIMUM_ASSERTIONS))
    if len(permit_sites) < MINIMUM_PERMIT_SITES:
        findings.append(
            "%d call site(s) register a permitted root with .%s(), and %d is "
            "the floor: the throwaway homes and the roots step 4 is asked to "
            "collect. Fewer means a class of legitimate read is reaching the "
            "assertion by some other route again, or is not permitted at all."
            % (len(permit_sites), PERMIT_METHOD, MINIMUM_PERMIT_SITES))

    return findings


def probe_sensitivity():
    """The shipped window, asked the same question with and without a permit.

    The static half cannot see this: a `strays()` that ignored its permitted
    set and returned an empty list would satisfy every rule above and report
    a clean run for a process reading anything it liked.
    """
    sys.path.insert(0, str(REPO_ROOT))
    try:
        from murscope import selftest  # noqa: PLC0415 - probing the real module
    except Exception as exc:
        return ["cannot import murscope.selftest (%s: %s), so the window "
                "could not be probed." % (type(exc).__name__, exc)]

    window_class = getattr(selftest, WINDOW_CLASS, None)
    if window_class is None:
        return ["murscope.selftest exposes no %s, so there is no window to "
                "probe." % WINDOW_CLASS]

    class _Recorder(object):
        def __init__(self, paths):
            self.paths = list(paths)

        def since(self, mark):
            return self.paths[mark:]

    findings = []
    with tempfile.TemporaryDirectory() as work:
        root = Path(work) / "a-listed-project"
        root.mkdir()
        read = root / "README.md"
        read.write_text("# probe\n", encoding="utf-8")
        recorder = _Recorder([str(read)])

        permitted = window_class(recorder)
        # Every call guarded, because a window that raises is a window that
        # answered nothing - and an uncaught traceback here would take the
        # static findings above off the screen with it.
        try:
            permitted.permit(str(root), "a probe root")
            with_permit = list(permitted.strays())
            withheld = window_class(recorder)
            without_permit = list(withheld.strays())
        except Exception as exc:
            return ["the window raised %s: %s when asked for its strays, so it "
                    "reported nothing and certified nothing."
                    % (type(exc).__name__, exc)]

        if with_permit:
            findings.append(
                "a read inside a permitted root was reported as a stray, so "
                "the window does not honour its own permitted set and every "
                "legitimate read would be a finding: %s"
                % ", ".join(str(p) for p in with_permit))

        if not without_permit:
            findings.append(
                "the same read was reported as no stray with the root NOT "
                "permitted. The window is insensitive to its permitted set, "
                "so a green result from it means nothing - which is the "
                "vacuous-guard shape this file's own history is made of.")
    return findings


def probe_bytecode_cache():
    """The narrowed half of the permitted set, on every interpreter.

    **This exists because the interpreter it is about is not in the
    matrix.** `sys.pycache_prefix` is None on almost every build and is set
    on Apple's `/usr/bin/python3` - to a directory under the user's home,
    which is under no permitted root - so the read-location assertion
    reported the interpreter's own cache entries as stray reads of a
    project there and nowhere else. It was red on `origin/main` and CI
    could not have seen it (DP117).

    The first repair was narrower than the thing it exists for, which is
    the same failure from the other side: it permitted names ending in
    `.pyc`, and CPython writes a `.pyc` by opening `<name>.pyc.<id>` and
    renaming, so the name seen on a **cold cache** does not match. The
    guard went red on the first run after any code change and green on the
    second - a guard that teaches a reader to run it twice.

    So the prefix is simulated rather than waited for: `sys.pycache_prefix`
    is pointed at a temporary directory, and six shapes are asserted in
    both directions. Two must be permitted and four must not, because a
    permission wider than the thing it exists for is how the temporary
    directory rule once passed while reading a project planted inside it.
    """
    sys.path.insert(0, str(REPO_ROOT))
    try:
        from murscope import selftest  # noqa: PLC0415 - probing the real module
    except Exception as exc:
        return ["cannot import murscope.selftest (%s: %s), so the bytecode "
                "cache permission was not probed." % (type(exc).__name__, exc)]

    findings = []
    original = getattr(sys, "pycache_prefix", None)
    with tempfile.TemporaryDirectory() as work:
        prefix = Path(work) / "cache-prefix"
        outside = Path(work) / "not-the-prefix"
        (prefix / "pkg").mkdir(parents=True)
        outside.mkdir(parents=True)
        cases = [
            ("a cached .pyc", prefix / "pkg" / "mod.cpython-39.pyc", True),
            ("the name CPython writes before renaming",
             prefix / "pkg" / "mod.cpython-39.pyc.4339850560", True),
            ("a project file planted under the prefix",
             prefix / "pkg" / "README.md", False),
            ("a .pyc suffix followed by something that is not digits",
             prefix / "pkg" / "mod.cpython-39.pyc.evil", False),
            ("a source file planted under the prefix",
             prefix / "pkg" / "main.py", False),
            ("a .pyc outside the prefix",
             outside / "mod.cpython-39.pyc", False),
        ]
        try:
            sys.pycache_prefix = str(prefix)
            for label, path, permitted in cases:
                path.write_text("x", encoding="utf-8")
                strays = selftest._stray_reads([str(path)], [])
                if permitted and strays:
                    findings.append(
                        "%s was reported as a stray read. It is this "
                        "interpreter's own cache entry, and calling it a "
                        "project read makes the whole assertion red on a "
                        "machine where nothing is wrong." % label)
                if not permitted and not strays:
                    findings.append(
                        "%s was permitted. The cache prefix is permitted as a "
                        "set of bytecode names, never as a tree - a permission "
                        "wider than the thing it exists for is how the "
                        "temporary-directory rule once passed while reading a "
                        "project planted inside it." % label)
        except Exception as exc:
            findings.append("the probe raised %s: %s, so the bytecode cache "
                            "permission was not measured."
                            % (type(exc).__name__, exc))
        finally:
            sys.pycache_prefix = original
    return findings


def main():
    if not SELFTEST.exists():
        print("FAILED: %s is missing, so the read window this rule governs "
              "cannot be read." % SELFTEST.relative_to(REPO_ROOT).as_posix())
        return 1

    findings = detect(SELFTEST.read_bytes())
    for finding in findings:
        print("murscope/selftest.py:%s" % finding)
    live = probe_sensitivity()
    for finding in live:
        print("the shipped ReadWindow: %s" % finding)
    cached = probe_bytecode_cache()
    for finding in cached:
        print("the bytecode cache permission: %s" % finding)

    bad = len(findings) + len(live) + len(cached)
    if bad:
        print("\nFAILED: %d finding(s). One window, one permitted set - and "
              "they are only one thing while nothing else can state either "
              "half on its own." % bad)
        return 1

    tree = ast.parse(SELFTEST.read_text(encoding="utf-8"))
    where = _enclosing(tree)
    assertions = len(_assertion_sites(tree, where))
    permits = len(_permit_sites(tree, where))
    print("OK: the read window is stated once, with the literal 0, inside "
          "%s.%s(), and %s.%s() is the only caller of %s(). %d read-location "
          "assertion(s) call .%s() with no arguments, so neither half can be "
          "narrowed at a call site, and %d call site(s) register a permitted "
          "root where the root is acquired. Probed live: the shipped window "
          "reports no stray for a read inside a permitted root and reports "
          "that same read when the permit is withdrawn; and with "
          "sys.pycache_prefix simulated, it permits a cached `.pyc` and the "
          "name CPython writes before renaming it, while still calling a "
          "README, a source file, a `.pyc.<not digits>` and a `.pyc` outside "
          "the prefix strays."
          % (WINDOW_CLASS, WINDOW_OPENER, WINDOW_CLASS, WINDOW_METHOD,
             RAW_ASSERTION, assertions, WINDOW_METHOD, permits))
    return 0


if __name__ == "__main__":
    sys.exit(main())
