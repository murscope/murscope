"""Rule 1: all rules have checks.

Four jobs, all of them meta.

**Mapping.** Every "## Rule <id>: title" heading in CONTRIBUTING.md must
resolve either to scripts/checks/<slugified title>.py or to an explicit
"Enforcement:" line in the rule body, and every script must map back to
a heading, so an orphan script is a rule nobody wrote down. The heading
id is not required to be numeric: "## Rule 10b:" is a rule, and a check
that only understood digits would be blind to it while `grep -c '^## Rule
'` counted it. The check asserts its own parsed count equals that grep
count, so the two can never drift apart.

**Freeze.** The gate has to defend itself. Without this, a check can be
replaced by six lines that print OK, and the runner will report that
every rule passed. scripts/checks_manifest.json records the content hash
of every Python file under scripts/, recursively, plus every fixture,
plus the number of checks that are supposed to exist. Editing any of
them means updating the manifest in the same change, where a reviewer
sees it in the diff. This is a tripwire, not a vault - anything in the
working tree can be edited, the manifest included - but nothing can be
hollowed out *silently*.

**Binding.** This is the part that matters, and the part that was
missing while eleven hand-written reverse-verification cases stood in
for it. Eleven imagined violations caught eleven imagined violations;
nothing required a check to be capable of failing at all. So every check
now exposes a pure detector - detect(payload: bytes) -> list of findings
- and ships the violating shape from its own "Fails when:" line as data
at scripts/checks/fixtures/<slug>.txt. This script imports each check,
feeds it its own fixture, and fails if the detector stays quiet. A check
that cannot fail is now a check that cannot pass.

Fixtures are base64 inside a commented header, deliberately. A fixture
holding live violating source would trip the other checks, and the fix
for that is always an exempt directory - which is the beginning of every
hole both audits found. Data cannot be mistaken for code, and an exempt
directory never has to exist.

**Runner substance.** The runner is held to the same bar it applies:
"Fails when:" line, main(), sys.exit, and - structurally, from its parse
tree - it must glob the checks directory, execute them with the current
interpreter, and inspect their return codes. A runner that prints a
green summary having executed nothing is the same failure as a hollow
check, and CI runs that same command.

Regenerating the manifest, after a deliberate change:

    python3 scripts/checks/all_rules_have_checks.py --update-manifest

Fails when: a rule heading has neither a matching script nor an
"Enforcement:" line; a script maps to no heading; the parsed rule count
disagrees with the number of "## Rule " lines; a frozen file's hash
differs from the manifest, or a file is added or removed without
updating it; the recorded check count is wrong, or a regeneration tries
to lower it without --allow-shrink; a check runs at import time instead
of behind an __main__ guard; a check lacks detect(),
lacks a fixture, lacks a "Fails when:" line, or returns no findings when
fed its own fixture; or the runner does not structurally execute the
checks.
"""
from __future__ import annotations

import ast
import base64
import binascii
import hashlib
import importlib.util
import json
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
CONTRIBUTING = REPO_ROOT / "CONTRIBUTING.md"
SCRIPTS_DIR = REPO_ROOT / "scripts"
CHECKS_DIR = SCRIPTS_DIR / "checks"
FIXTURES_DIR = CHECKS_DIR / "fixtures"
# The cases that ship with the package (DP21). They are not under
# scripts/, so the freeze did not cover them, and an audit pointed out
# what that meant: weaken one of Rule 10's shipped cases and the gate
# stays green, because Rule 10 verifies that the cases pass rather than
# that they still say what they said. Same family as a hollowed-out
# check, which is what this whole file exists to refuse.
#
# Freezing them constrains this repository, not the user. The copy in
# site-packages is read-only and nobody edits it; what a user edits is
# the marker vocabulary, and DP19 and DP21 leave that alone.
PACKAGE_FIXTURES_DIR = REPO_ROOT / "murscope" / "fixtures"
RUNNER = SCRIPTS_DIR / "run_checks.py"
MANIFEST = SCRIPTS_DIR / "checks_manifest.json"

RULE_HEADING = re.compile(r"^##[ \t]+Rule[ \t]+([^:\s]+):[ \t]*(.+?)[ \t]*$", re.MULTILINE)
RULE_LINE = re.compile(r"^## Rule ", re.MULTILINE)
DEEP_HEADING = re.compile(r"^#{3,}[ \t]+Rule[ \t]", re.MULTILINE)
ENFORCEMENT_LINE = re.compile(r"^Enforcement:\s*\S+", re.MULTILINE)
FAILS_WHEN = re.compile(r"^Fails when:", re.MULTILINE)


def slugify(title):
    return re.sub(r"[^a-zA-Z0-9]+", "_", title.strip().lower()).strip("_")


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def check_scripts():
    """Every check the runner would execute."""
    return sorted(CHECKS_DIR.glob("*.py"))


def fixture_case_counts():
    """How many cases each check's fixture carries, by slug.

    Recorded in the manifest so it cannot shrink quietly. A fourth audit
    hollowed out a detector branch *and deleted the case that covered it*,
    in one change with the manifest regenerated - every hash matched,
    every remaining case fired, and a remote image beacon sat in the
    shipped HTML template on a green gate.

    `murscope/fixtures/` got category floors in the same round this
    directory did not. Same doctrine as DP44: the baseline only goes up.
    """
    counts = {}
    if not FIXTURES_DIR.is_dir():
        return counts
    for path in sorted(FIXTURES_DIR.glob("*.txt")):
        try:
            counts[path.stem] = len(decode_fixture(path))
        except (binascii.Error, ValueError):
            counts[path.stem] = 0
    return counts


def frozen_files():
    """Every file the freeze covers, keyed by repo-relative path.

    Recursive over scripts/, and __init__.py is included: a support
    module tucked under scripts/checks/support/ is where a check's real
    logic would go if the freeze had a blind spot, and it would sit
    there with a permanently stable hash.

    `murscope/fixtures/` is covered too. Those cases ship with the package
    so a user can run them (DP21), which put them outside scripts/ and
    outside the freeze - and Rule 10 checks that they pass, not that they
    still say what they said, so weakening one left the gate green.
    """
    files = {}
    for path in sorted(SCRIPTS_DIR.rglob("*.py")):
        if "__pycache__" in path.parts:
            continue
        files[path.relative_to(REPO_ROOT).as_posix()] = path
    for directory in (FIXTURES_DIR, PACKAGE_FIXTURES_DIR):
        if not directory.is_dir():
            continue
        for path in sorted(directory.rglob("*")):
            if path.is_file():
                files[path.relative_to(REPO_ROOT).as_posix()] = path
    return files


CASE_MARK = "# case:"


def decode_fixture(path):
    """Every case in a fixture, as [(label, payload)].

    A fixture used to be one base64 body, and an audit showed what that
    bought: this check only ever asked whether `detect()` returned at
    least one finding, so a fixture exercising one branch certified a
    detector with five. Point 4 of Rule 7 was hollowed out, the manifest
    regenerated in the same change, and the gate stayed green with the
    violation still sitting in the package - the third time the gate's
    self-certification proved weaker than it reads.

    So a fixture may now carry several cases, each introduced by a
    `# case: <label>` line, and every one of them has to fire. A file with
    no case markers is a single case named "default", which keeps the
    older fixtures valid.
    """
    cases = []
    label = "default"
    body = []
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if stripped.startswith(CASE_MARK):
            if body:
                cases.append((label, "".join(body)))
                body = []
            label = stripped[len(CASE_MARK):].strip() or "unnamed"
            continue
        if not stripped or stripped.startswith("#"):
            continue
        body.append(stripped)
    if body:
        cases.append((label, "".join(body)))
    return [(name, base64.b64decode(text, validate=True))
            for name, text in cases]


def append_sites(path):
    """Line numbers of every `findings.append(...)` reachable from detect().

    **Kept as a report, not as a bar.** It was briefly enforced, and a
    fourth audit was right about what that claim was worth: it only counts
    `.append` on a variable whose name ends in `findings`, so renaming the
    accumulator to `extra` and concatenating it at the end walks straight
    past. A rule may not promise more than it executes, and that applies
    to this file before it applies to any other.

    What replaced it is not a stronger static bar - it is a runtime
    canary in `murscope selftest`, which looks at the artifact instead of
    at the shape of the code. The same move this project already made once,
    when "no network" stopped being an import scan and became an audit
    hook.
    """
    src = path.read_text(encoding="utf-8")
    try:
        tree = ast.parse(src)
    except SyntaxError:
        return set()

    functions = {n.name: n for n in ast.walk(tree)
                 if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))}
    if "detect" not in functions:
        return set()

    reachable = {"detect"}
    frontier = ["detect"]
    while frontier:
        node = functions.get(frontier.pop())
        if node is None:
            continue
        for sub in ast.walk(node):
            if not isinstance(sub, ast.Call):
                continue
            name = getattr(sub.func, "id", None)
            if name in functions and name not in reachable:
                reachable.add(name)
                frontier.append(name)

    sites = set()
    for name in reachable:
        for sub in ast.walk(functions[name]):
            if (isinstance(sub, ast.Call)
                    and getattr(sub.func, "attr", None) in ("append", "extend")
                    and isinstance(sub.func.value, ast.Name)
                    and sub.func.value.id.endswith("findings")):
                sites.add(sub.lineno)
    return sites


def traced_detect(module, path, detect, payload):
    """Run detect(payload) and return (findings, lines executed in `path`).

    `sys.settrace` rather than a coverage dependency: DP2 forbids one, and
    a line trace over one function call is cheap enough that nobody will
    be tempted to switch it off.
    """
    target = str(path)
    seen = set()

    def local(frame, event, arg):
        if event == "line":
            seen.add(frame.f_lineno)
        return local

    def dispatch(frame, event, arg):
        if frame.f_code.co_filename == target:
            seen.add(frame.f_lineno)
            return local
        return None

    previous = sys.gettrace()
    sys.settrace(dispatch)
    try:
        findings = detect(payload)
    finally:
        sys.settrace(previous)
    return findings, seen


def load_detector(path):
    """Import a check for inspection, without letting it run.

    SystemExit is caught deliberately. A check whose sys.exit(main())
    sits at module level, unguarded, kills this process on import - and
    if it exits 0, the harness dies reporting success having verified
    nothing. That was a live hole: a stub check written exactly that way
    made Rule 1 exit green while printing its own freeze complaint.
    """
    name = "murscope_check_%s" % path.stem
    spec = importlib.util.spec_from_file_location(name, str(path))
    module = importlib.util.module_from_spec(spec)
    # **An inspection import must leave nothing behind.** Executing a
    # module writes `__pycache__/*.pyc` beside it, and this function is
    # called from inside the extracted public tree when the freeze is
    # regenerated there - so the derivation wrote 156 files and the tree
    # on disk held 157, with every check counting what the spec *said* it
    # wrote and none of them counting the disk. DP176's shape, one tree
    # over, and it was found by the comparator's own two-reader assertion
    # within minutes of being introduced.
    previously = sys.dont_write_bytecode
    sys.dont_write_bytecode = True
    try:
        spec.loader.exec_module(module)
    except SystemExit:
        raise RuntimeError(
            "runs at import time: sys.exit() is called at module level "
            "instead of behind `if __name__ == \"__main__\":`")
    finally:
        sys.dont_write_bytecode = previously
    return module


def recorded_fixture_counts():
    """The per-fixture case counts the manifest records, or None."""
    if not MANIFEST.exists():
        return None
    try:
        return json.loads(MANIFEST.read_text(encoding="utf-8")).get("fixture_cases")
    except ValueError:
        return None


# Rule 40's register is a tuple in a check, and a set whose size is
# recorded nowhere shrinks by one edit with no trace but a smaller number
# in its own output. Same answer as `expected_check_count` one level up,
# and the same counter-argument accepted for the same reason: a declared
# constant can be edited in the same commit, but doing so takes a second,
# legible edit instead of none. Named rather than discovered - rename the
# check without updating this and the count goes undeclared, which Rule 40
# reports as a finding rather than as a smaller set.
CI_GUARD_CHECK = "a_guard_that_lives_in_ci_stays_installed.py"


def ci_guard_count():
    """How many CI-resident guards Rule 40's register holds, or None."""
    path = CHECKS_DIR / CI_GUARD_CHECK
    if not path.is_file():
        return None
    try:
        module = load_detector(path)
    except BaseException:
        return None
    guards = getattr(module, "GUARDS", None)
    return len(guards) if guards is not None else None


def recorded_ci_guard_count():
    if not MANIFEST.exists():
        return None
    try:
        return json.loads(MANIFEST.read_text(encoding="utf-8")).get(
            "expected_ci_guard_count")
    except ValueError:
        return None


def recorded_count():
    if not MANIFEST.exists():
        return None
    try:
        return json.loads(MANIFEST.read_text(encoding="utf-8")).get("expected_check_count")
    except ValueError:
        return None


def write_manifest(allow_shrink=False):
    """Regenerate the freeze. The baseline only goes up.

    Recording the count is useless if regenerating the manifest silently
    lowers it: delete a check, delete its rule, regenerate, and the gate
    reports a smaller number in green. So a regeneration that would
    shrink the gate is refused, and shrinking it needs --allow-shrink -
    a deliberate word that appears in the diff and that nobody types by
    reflex.
    """
    recorded_cases = recorded_fixture_counts()
    live_cases = fixture_case_counts()
    dropped = sorted(
        "%s (%d -> %d)" % (slug, floor, live_cases.get(slug, 0))
        for slug, floor in (recorded_cases or {}).items()
        if live_cases.get(slug, 0) < floor)
    if dropped and not allow_shrink:
        print("REFUSED: fixture case count(s) fell: %s." % ", ".join(dropped))
        print("Deleting a case is how a detector branch gets emptied on a "
              "green gate - an audit did exactly that, in one change, with "
              "every hash matching. If a case really should go, say so:")
        print("  python3 scripts/checks/all_rules_have_checks.py "
              "--update-manifest --allow-shrink")
        return 1

    previous = recorded_count()
    current = len(check_scripts())
    if previous is not None and current < previous and not allow_shrink:
        print("REFUSED: scripts/checks/ holds %d check(s); the manifest records "
              "%d. The baseline only goes up." % (current, previous))
        print("A gate that shrinks quietly is the failure this count exists to "
              "catch, and regenerating past it would make the count decorative. "
              "If a rule really was retired, say so explicitly:")
        print("  python3 scripts/checks/all_rules_have_checks.py "
              "--update-manifest --allow-shrink")
        return 1
    guards_previous = recorded_ci_guard_count()
    guards_current = ci_guard_count()
    if (guards_previous is not None and guards_current is not None
            and guards_current < guards_previous and not allow_shrink):
        print("REFUSED: Rule 40's register holds %d CI-resident guard(s); the "
              "manifest records %d. The baseline only goes up."
              % (guards_current, guards_previous))
        print("A guard dropped from that register is an assertion that stops "
              "being watched, and its own output would report the smaller "
              "number in green. If one really was retired, say so explicitly:")
        print("  python3 scripts/checks/all_rules_have_checks.py "
              "--update-manifest --allow-shrink")
        return 1

    payload = {
        "note": (
            "Content hashes of the gate: every Python file under scripts/ and "
            "every fixture. Rule 1 refuses a file whose hash it does not "
            "recognise, so no check can be hollowed out without the change "
            "showing in this file's diff. expected_check_count is asserted by "
            "the runner, so a gate that silently shrinks is caught too. The "
            "expected_ci_guard_count is asserted by Rule 40, so its register "
            "cannot be narrowed without an edit here either. The counts only "
            "go up: lowering one needs --allow-shrink. Regenerate "
            "with: python3 scripts/checks/all_rules_have_checks.py "
            "--update-manifest"
        ),
        "algorithm": "sha256",
        "expected_check_count": len(check_scripts()),
        "expected_ci_guard_count": guards_current,
        "fixture_cases": fixture_case_counts(),
        "files": {rel: digest(path) for rel, path in sorted(frozen_files().items())},
    }
    MANIFEST.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print("Wrote %s: %d frozen file(s), expected_check_count=%d, "
          "expected_ci_guard_count=%s."
          % (MANIFEST.relative_to(REPO_ROOT).as_posix(),
             len(payload["files"]), payload["expected_check_count"],
             payload["expected_ci_guard_count"]))
    print("This is the freeze. The diff on this file is the record that the "
          "gate changed - make sure the review sees it.")
    return 0


def check_fixture_counts(recorded):
    """No fixture may carry fewer cases than the manifest records."""
    findings = []
    counts = fixture_case_counts()
    for slug, floor in sorted((recorded or {}).items()):
        found = counts.get(slug, 0)
        if found < floor:
            findings.append(
                "scripts/checks/fixtures/%s.txt carries %d case(s); the "
                "manifest records %d. Deleting a case is how a branch gets "
                "emptied on a green gate - regenerate with --shrink only if "
                "the case really should go." % (slug, found, floor))
    return findings


def check_freeze():
    files = frozen_files()
    if not MANIFEST.exists():
        print("scripts/checks_manifest.json: missing. The gate cannot vouch for "
              "itself without it; regenerate with --update-manifest.")
        return 1, 0
    try:
        payload = json.loads(MANIFEST.read_text(encoding="utf-8"))
        recorded = payload["files"]
        expected = payload["expected_check_count"]
    except (ValueError, KeyError, TypeError) as exc:
        print("scripts/checks_manifest.json: unreadable (%s)." % exc)
        return 1, 0

    bad = 0
    actual_checks = len(check_scripts())
    if actual_checks != expected:
        print("scripts/checks_manifest.json: records expected_check_count=%s but "
              "scripts/checks/ holds %d check(s). A gate that shrinks quietly is "
              "the failure the count exists to catch." % (expected, actual_checks))
        bad += 1
    for rel in sorted(set(recorded) - set(files)):
        print("%s: in the manifest but no longer on disk." % rel)
        bad += 1
    for rel in sorted(set(files) - set(recorded)):
        print("%s: on disk but not in the manifest." % rel)
        bad += 1
    for rel in sorted(set(files) & set(recorded)):
        actual = digest(files[rel])
        if actual != recorded[rel]:
            print("%s: content hash %s does not match the manifest (%s). Either "
                  "this edit was not meant to happen, or the manifest needs "
                  "regenerating in the same change."
                  % (rel, actual[:12], str(recorded[rel])[:12]))
            bad += 1
    return bad, len(files)


def check_binding():
    """Feed every check the violating shape it documents. Quiet is red."""
    bad = 0
    proven = 0
    for path in check_scripts():
        rel = path.relative_to(REPO_ROOT).as_posix()
        text = path.read_text(encoding="utf-8")

        if not FAILS_WHEN.search(text):
            print("%s: module docstring has no 'Fails when:' line stating the "
                  "violating shape." % rel)
            bad += 1
        if "def main(" not in text:
            print("%s: defines no main()." % rel)
            bad += 1
        if "sys.exit" not in text:
            print("%s: never calls sys.exit; the runner reads exit codes." % rel)
            bad += 1

        fixture = FIXTURES_DIR / ("%s.txt" % path.stem)
        if not fixture.exists():
            print("%s: no fixture at scripts/checks/fixtures/%s.txt holding the "
                  "shape from its 'Fails when:' line." % (rel, path.stem))
            bad += 1
            continue

        try:
            cases = decode_fixture(fixture)
        except (binascii.Error, ValueError) as exc:
            print("scripts/checks/fixtures/%s.txt: not decodable base64 (%s)."
                  % (path.stem, exc))
            bad += 1
            continue

        try:
            module = load_detector(path)
        except BaseException as exc:  # a check that cannot be imported cannot run
            print("%s: cannot be imported (%s: %s)." % (rel, type(exc).__name__, exc))
            bad += 1
            continue

        detect = getattr(module, "detect", None)
        if not callable(detect):
            print("%s: exposes no detect(payload) function, so nothing can prove "
                  "it is capable of failing." % rel)
            bad += 1
            continue

        if not cases:
            print("%s: its fixture holds no cases." % rel)
            bad += 1
            continue

        executed = set()
        quiet = []
        broke = False
        for label, payload in cases:
            try:
                findings, lines = traced_detect(module, path, detect, payload)
            except BaseException as exc:
                print("%s: detect() raised on fixture case %r (%s: %s)."
                      % (rel, label, type(exc).__name__, exc))
                bad += 1
                broke = True
                break
            executed |= lines
            if not findings:
                quiet.append(label)
        if broke:
            continue

        if quiet:
            print("%s: detect() returned no findings for fixture case(s) %s. A "
                  "case that fires on nothing certifies nothing."
                  % (rel, ", ".join(repr(q) for q in quiet)))
            bad += 1
            continue

        proven += 1

    return bad, proven


def check_runner():
    """The runner must structurally do what it claims, not just say it."""
    bad = 0
    if not RUNNER.exists():
        print("scripts/run_checks.py: missing.")
        return 1

    text = RUNNER.read_text(encoding="utf-8")
    if not FAILS_WHEN.search(text):
        print("scripts/run_checks.py: no 'Fails when:' line; the runner is held "
              "to the bar it applies to the checks.")
        bad += 1
    if "def main(" not in text or "sys.exit" not in text:
        print("scripts/run_checks.py: no main() or no sys.exit.")
        bad += 1

    try:
        tree = ast.parse(text, filename=str(RUNNER))
    except SyntaxError as exc:
        print("scripts/run_checks.py: cannot parse (%s)." % exc)
        return bad + 1

    source = ast.dump(tree)
    executes = "'run'" in source or "'check_call'" in source or "'Popen'" in source
    if not executes:
        print("scripts/run_checks.py: never invokes a subprocess; a runner that "
              "prints a green summary having executed nothing is the same "
              "failure as a hollow check.")
        bad += 1
    if "executable" not in source:
        print("scripts/run_checks.py: does not run the checks with the current "
              "interpreter (sys.executable).")
        bad += 1
    if "returncode" not in source:
        print("scripts/run_checks.py: never inspects a return code, so every "
              "check could be failing silently.")
        bad += 1
    if "glob" not in source:
        print("scripts/run_checks.py: does not enumerate scripts/checks/.")
        bad += 1
    return bad


def detect(payload):
    """Findings for a CONTRIBUTING-shaped document: unenforced rules.

    Pure: the only outside knowledge is which check scripts exist.
    """
    text = payload.decode("utf-8", errors="replace")
    scripts = {p.stem for p in check_scripts()}
    findings = []
    matches = list(RULE_HEADING.finditer(text))
    for i, m in enumerate(matches):
        rule_id, title = m.group(1), m.group(2)
        body = text[m.end(): matches[i + 1].start() if i + 1 < len(matches) else len(text)]
        if slugify(title) in scripts or ENFORCEMENT_LINE.search(body):
            continue
        findings.append(
            "Rule %s ('%s'): unenforced - expected scripts/checks/%s.py, or an "
            "'Enforcement: <non-code mechanism>' line in the rule body."
            % (rule_id, title, slugify(title)))
    return findings


def check_mapping():
    text = CONTRIBUTING.read_text(encoding="utf-8")
    matches = list(RULE_HEADING.finditer(text))
    if not matches:
        print("FAILED: no '## Rule <id>: title' headings found in CONTRIBUTING.md.")
        return 1, 0, 0, 0

    bad = 0
    grep_count = len(RULE_LINE.findall(text))
    if grep_count != len(matches):
        print("CONTRIBUTING.md: %d line(s) start with '## Rule ' but %d parsed as "
              "'## Rule <id>: title'. A heading this check cannot read is a rule "
              "nothing enforces." % (grep_count, len(matches)))
        bad += 1
    for m in DEEP_HEADING.finditer(text):
        line = text.count("\n", 0, m.start()) + 1
        print("CONTRIBUTING.md:%d: rule heading below level 2; rules are '## Rule "
              "<id>: title' so the count is greppable." % line)
        bad += 1

    for finding in detect(text.encode("utf-8")):
        print(finding)
        bad += 1

    scripts = {p.stem for p in check_scripts()}
    claimed = set()
    by_script = 0
    by_enforcement = 0
    for i, m in enumerate(matches):
        title = m.group(2)
        body = text[m.end(): matches[i + 1].start() if i + 1 < len(matches) else len(text)]
        slug = slugify(title)
        if slug in scripts:
            claimed.add(slug)
            by_script += 1
        elif ENFORCEMENT_LINE.search(body):
            by_enforcement += 1

    for orphan in sorted(scripts - claimed):
        print("scripts/checks/%s.py: orphan - no '## Rule <id>: %s' heading in "
              "CONTRIBUTING.md maps to it." % (orphan, orphan.replace("_", " ")))
        bad += 1

    return bad, len(matches), by_script, by_enforcement


def main(argv=None):
    args = list(sys.argv[1:] if argv is None else argv)
    if args and args[0] == "--update-manifest":
        rest = args[1:]
        if rest and rest != ["--allow-shrink"]:
            print("usage: all_rules_have_checks.py [--update-manifest "
                  "[--allow-shrink]]")
            return 2
        return write_manifest(allow_shrink=bool(rest))
    if args:
        print("usage: all_rules_have_checks.py [--update-manifest "
              "[--allow-shrink]]")
        return 2

    if not CONTRIBUTING.exists():
        print("FAILED: CONTRIBUTING.md is missing.")
        return 1
    if not CHECKS_DIR.is_dir():
        print("FAILED: scripts/checks/ is missing.")
        return 1

    bad, rules, by_script, by_enforcement = check_mapping()
    frozen_bad, frozen_count = check_freeze()
    for finding in check_fixture_counts(recorded_fixture_counts()):
        print(finding)
        frozen_bad += 1
    binding_bad, proven = check_binding()
    bad += frozen_bad + binding_bad + check_runner()

    if bad:
        print("\nFAILED: %d mapping, freeze, binding or runner violation(s)." % bad)
        return 1

    print("OK: %d rule(s) - %d backed by a check script, %d by an Enforcement "
          "line - matching the %d '## Rule ' heading line(s); %d frozen file(s) "
          "match the manifest; %d check(s) proved to fire on their own fixture; "
          "the runner executes them."
          % (rules, by_script, by_enforcement, rules, frozen_count, proven))
    return 0


if __name__ == "__main__":
    sys.exit(main())
