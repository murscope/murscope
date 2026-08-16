"""Rule 40: a guard that lives in CI stays installed.

Some assertions cannot be made from a check under `scripts/`. Rule 11
forbids a network tool there, so the two questions that need one - is
this repository still private, and is the published tree still the
extraction of a commit here - live in the workflow. Others could live
under `scripts/` and do not, because they need a build, a fresh
environment or a clean checkout, which is too slow to put in front of
every commit.

**What every one of them has in common is the failure this rule is
for.** A step in a workflow is invisible to the gate. Delete it and the
gate is still green, every check still passes, and the assertion is
simply gone - no diff a reviewer reads as a loss, no red anywhere. Rule
36 already refuses that for exactly one member, the visibility probe.
This rule refuses it for the set.

**The register is here rather than in the workflow, and that is the
whole mechanism.** A declaration living inside the thing it declares
cannot notice the thing being deleted: removing the step would remove
its own marker, and the keeper would enumerate nothing and pass. So the
members are named in this file, and the workflow is read against them.

**Four questions per member**, all offline:

1. **Is it there?** A step with that name, in a workflow file.
2. **Does it still have what it needs?** Its token, its subject, the
   inputs the assertion is made of. A probe with no token answers
   nothing on every run, which reads in a log exactly like an answer.
3. **Can it still fail the job?** Not `continue-on-error`, not turning
   errexit back off, and its asserting command not swallowed by
   `|| true`. A step that reports and continues is a log line, not a
   gate. **For a step that `uses:` somebody else's action this question
   is weaker and is reported as weaker**: there is no command of ours in
   it to read, so all that can be said is that the step is not exempted
   from failing, and its inputs carry the weight instead.
4. **Does anything run it?** A workflow with no trigger is a watcher
   nobody starts.

**And two questions about the set rather than about a member.** Every
step in every workflow must be either a registered member or named
infrastructure, so a new step is classified by whoever adds it rather
than by whoever notices later. **A step is matched to a register row by
its exact name**, expression and all: prefix matching was introduced for
one title carrying a matrix expression and started doing the classifying
by name collision instead, swallowing an unregistered `Run the gate on
the docs` into the member `Run the gate`. Narrowing the prefix to
`declared + " "` does not fix that - the collision name begins with the
member name and a space - so the register carries full names and this is
equality. And **the register's own size is declared
in the freeze** and asserted here: a set whose size is recorded nowhere
shrinks by one edit with no trace but a smaller number in its own
output, which is exactly the shape `expected_check_count` has refused
since M0. The counter-argument - that a declared constant can be edited
in the same commit - is equally true there and was accepted for the same
reason: the point is not that it cannot be defeated, it is that
defeating it takes a second, legible edit instead of none.

**Infrastructure is the class whose absence announces itself**, because
the steps after it stop working: delete the checkout and there are no
files, delete the install and the first command naming the package
fails. **It was twice this size and acceptance was right about both.**
Setting up the interpreter and setting up the board's engine are absent
in exactly the way this rule exists to catch - the runner ships both
already, so deleting either leaves the job green while the three-version
matrix collapses onto whatever the image carries. A criterion applied
wrongly is not a criterion written wrongly; both are members now.

**What this costs, written here because it is the argument against this
rule and it lost rather than being absent.** A keeper that covers a
class can be loosened for the class: one edit here narrows what is
watched for every member at once, where a guard per member would have to
be defeated one at a time. That is real. It was ruled for anyway,
because the alternative was a third copy of a thing this line had
already written twice - and had already promised itself, in DP182, that
it would look at the arrangement before there was a third. Nothing read
that sentence, which is how the third came to be built.

**One member this rule cannot catch from inside CI, named rather than
discovered.** `Run the gate` is a member, because the assertion that
only the workflow makes is that the gate runs on a *clean checkout* on
every interpreter in the matrix - the one runner that saw an untracked
file five local green gates could not (DP176). But this check runs
inside that step. Delete it, and nothing here runs in CI at all, so the
red arrives only from a contributor's own pre-flight. That is a guard
whose window does not contain the thing it watches, in this rule, on
purpose and with no version of it that does not have the property.

**What is left uncovered, stated rather than discovered.** A row, its
step and the declared size, edited together in one commit. That is three
legible edits where a per-member guard would have taken one deletion,
and it is the same floor `expected_check_count` has stood on since M0.

**Rule 36 is not delegated to this rule and is not weakened by it.** It
keeps its own three assertions about the probe - a token, `exit 1` on a
repository that is not private, and `GITHUB_REPOSITORY` rather than a
name somebody typed - plus the declaration and the blast radius, which
are not this rule's business. The overlap is presence, inputs and
can-fail on one member. What that costs is that an edit to the probe
turns two checks red and a reader may repair one and assume the other;
both name the step and their own rule, so the second red is a direction
rather than a puzzle. What it buys is that a red line's keeper stays
self-contained: Rule 36 does not stop working if this rule is loosened,
and cannot be loosened by loosening the class.

**Measured, then judged.** `main()` reads the workflow files into a flat
sheet of `Key: value` lines; `detect()` judges the sheet and nothing
else. Every branch is then reachable from a fixture without a repository
in a particular state, and a sheet that has *lost* a key is a finding
rather than a silent pass (DP87).

**In a derived tree two of the members do not apply**, and the rule says which
rather than skipping quietly. The visibility probe watches a setting on
the repository the derivation came from, and the extraction assertion
searches a history that tree does not have; both are rewritten out of
the published workflow with their reasons. Which tree this is comes from
the derivation spec, the way Rules 35 and 36 ask the same question.

Fails when: no workflow file exists, or none holds a step; a registered
member that applies to this tree is absent, has lost an input, cannot
fail the job, or sits in a workflow nothing triggers; a step is present
that is neither a registered member nor named infrastructure; the
register's size disagrees with the size the freeze declares, or the
freeze declares none; or the measured sheet is missing a key the
judgment needs.
"""
from __future__ import annotations

import importlib.util
import json
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
WORKFLOWS = REPO_ROOT / ".github" / "workflows"
SPEC_PATH = REPO_ROOT / "scripts" / "public_tree.py"
MANIFEST = REPO_ROOT / "scripts" / "checks_manifest.json"

DEVELOPMENT = "development"
DERIVATION = "derivation"
BOTH = "both"

# How a step does its work, which decides what "can fail the job" can
# mean. A `run:` step carries a command of ours and the question is
# whether that command's exit code still reaches the job. A `uses:` step
# carries somebody else's action: there is no command of ours to inspect,
# so the only thing readable here is that the step is not exempted from
# failing. That is weaker and is reported as weaker rather than dressed up.
RUN = "run"
USES = "uses"

# A step begins at `- name:`. Split rather than parsed as YAML: there is
# no YAML parser in the standard library and ADR-0001 forbids adding
# one, so the shape is read the way a reviewer reads it.
STEP_HEAD = re.compile(r"^[ \t]*-[ \t]+name:[ \t]*(.+?)[ \t]*$", re.MULTILINE)

# **Errexit is not the criterion, and the first version of this check
# said it was.** The host runs a `run:` body under `bash -e` already, so
# asking whether the step says `set -e` is a test almost every step
# passes for free while saying nothing about any of them - and it went
# red on `Run the gate`, a one-line step that fails the job exactly as
# it should. What can actually stop a failure from reaching the job is
# somebody turning errexit back off, or swallowing the exit code of the
# command that does the asserting. Those are what is read.
SET_PLUS_E = re.compile(r"^\s*set\s+\+[a-z]*e", re.MULTILINE)
RUNS_A_COMMAND = "run:"

# What turns an assertion into a report. A line ending this way exits 0
# whatever the command before it did.
NEUTRALISED = re.compile(r"(\|\|\s*(true|:)|;\s*true)\s*$")
CONTINUE_ON_ERROR = "continue-on-error: true"

TRIGGERS = ("push:", "pull_request:", "schedule:", "workflow_dispatch:")

# Steps that are not guards: their absence announces itself, because the
# steps after them stop working. Delete the checkout and there are no
# files; delete the install and the first command that names the package
# fails. **The out-list was twice this long and acceptance was right about
# both.** `Set up Python` and `Set up a JavaScript engine` are absent in
# exactly the way this rule exists to catch: the runner ships a Python and
# a node already, so deleting either leaves everything green while the
# three-interpreter matrix collapses into three identical legs on whatever
# the image happens to carry, and the board check runs on an engine nobody
# pinned. Both are registered guards now. What the criterion says is what
# it always said - it was applied wrongly, not written wrongly.
INFRASTRUCTURE = (
    "Checkout",
    "Install the package",
)

# The register. One entry per assertion whose only home is the workflow.
#
# `requires` is what the assertion is made of - a token, a subject, an
# input - and every one of them has to still be in the step. `asserts` is
# the command that can say no, and it has to be there on a line that does
# not swallow its exit code.
GUARDS = (
    {
        "key": "interpreter-matrix",
        "step": "Set up Python ${{ matrix.python-version }}",
        "trees": BOTH,
        "kind": USES,
        "requires": ("actions/setup-python", "matrix.python-version"),
        "asserts": (),
        "why": "the gate runs on every interpreter in the matrix rather than "
               "on whatever the runner ships. **A matrix cannot exist under "
               "scripts/ at all**, so this is as CI-resident as an assertion "
               "gets - and deleting the step is silent, because a runner has "
               "a Python already and three legs then measure one version "
               "three times (DP3)",
    },
    {
        "key": "board-engine",
        "step": "Set up a JavaScript engine for the board check",
        "trees": BOTH,
        "kind": USES,
        "requires": ("actions/setup-node", "node-version"),
        "asserts": (),
        "why": "the board's own script is executed on a pinned engine. Its "
               "own comment makes the case - the engine is pinned rather "
               "than inherited because `it happened to be there` is not a "
               "thing to discover from a red run six months later - and "
               "deleting the step is silent for the same reason: the runner "
               "ships one (DP149)",
    },
    {
        "key": "console-scripts",
        "step": "Prove the console scripts run",
        "trees": BOTH,
        "requires": ("murscope --version", "murscope-timer", "murscope-alert"),
        "asserts": ('test "$code" -eq 2',),
        "why": "the three console entry points are wired up. The gate runs "
               "the CLI as a module and never through an installed entry "
               "point, so a scheduler with nobody present would be the first "
               "reader of a broken one (DP124, DP127)",
    },
    {
        "key": "visibility-probe",
        "step": "Refuse to be public",
        "trees": DEVELOPMENT,
        "requires": ("GH_TOKEN", "GITHUB_REPOSITORY", "visibility"),
        "asserts": ("exit 1",),
        "why": "the one irreversible thing here is a setting rather than a "
               "file, and this is the only thing in the line that can observe "
               "it. Rule 11 keeps it out of scripts/, and Rule 36 keeps its "
               "own separate watch on it (DP164)",
    },
    {
        "key": "gate-on-a-clean-checkout",
        "step": "Run the gate",
        "trees": BOTH,
        "requires": ("python3 scripts/run_checks.py",),
        "asserts": ("python3 scripts/run_checks.py",),
        "why": "the gate runs on a clean checkout, on every interpreter in "
               "the matrix. The gate itself is not CI's - it runs anywhere - "
               "but that it runs where nothing has been left on the disk is, "
               "and a clean checkout is the only runner that has ever caught "
               "an untracked file (DP176). **This is the member this rule "
               "cannot catch from inside CI**, because this check runs inside "
               "the step: with it gone, the red arrives from a contributor's "
               "own pre-flight and from nowhere else",
    },
    {
        "key": "extraction-assertion",
        "step": "Prove the published tree is an extraction of this history",
        "trees": DEVELOPMENT,
        "requires": ("--destination", "github.server_url"),
        "asserts": ("extraction_match.py --search",),
        "why": "nothing else measures the claim that every file in the "
               "published repository arrived there by derivation. Rule 2 does "
               "not apply inside a derivation, and its check had accidentally "
               "been the only thing between that branch and a hand edit "
               "(DP182, DP194)",
    },
    {
        "key": "keychain-round-trip",
        "step": "Prove the keychain round trip against the real keyring "
                "package",
        "trees": BOTH,
        "requires": ("keys_are_stored_0600_and_never_rendered.py",
                     "[keyring]"),
        "asserts": ("--require-keyring",),
        "why": "the keychain path is driven through the real package rather "
               "than a stub. Without the flag this step passes, that whole "
               "path is skipped silently on any machine without the extra, "
               "which is a skip wearing a pass (DP99, DP150)",
    },
    {
        "key": "wheel-and-fresh-install",
        "step": "Prove the shipped command works from a built wheel",
        "trees": BOTH,
        "requires": ("pip wheel", "MURSCOPE_HOME="),
        "asserts": ("murscope selftest",),
        "why": "the shipped command works from a *built* wheel, outside the "
               "checkout, on both roster shapes. A fixture missing from the "
               "wheel is invisible from the source tree, and the empty-roster "
               "shape is the one no user is ever in (DP114)",
    },
    {
        "key": "network-boundary-installs",
        "step": "Prove the network boundary from two fresh installs",
        "trees": BOTH,
        "requires": ("--no-index", "murscope[ai]"),
        "asserts": ("murscope.providers.network",),
        "why": "the boundary is measured in two *installed environments*, "
               "which is the dimension a wheel inspection cannot reach - a "
               "file that arrives on disk without a distribution owning it "
               "looks fine in a zip (DP88)",
    },
)

REQUIRED_KEYS = ("Tree", "Workflows", "Steps-seen", "Steps-infrastructure",
                 "Steps-unclassified", "Registered", "Registered-applicable",
                 "Registered-declared")

FIELD = re.compile(r"^([A-Za-z][A-Za-z0-9_-]*):\s*(.*?)\s*$")


def declared_size():
    """The register's size as recorded in the freeze, or a reason it is not.

    A falling integer that nothing compares to anything is the shape this
    line already refused for the check count: delete a check, delete its
    rule, regenerate, and the gate reports a smaller number in green. The
    register has the same shape and gets the same answer - the size is
    declared in `scripts/checks_manifest.json`, inside the freeze, and
    lowering it there needs `--allow-shrink`. **It can still be defeated
    by editing both in one commit**, exactly as the check count can; the
    point is not that it cannot be defeated, it is that defeating it takes
    a second, legible edit instead of none.
    """
    if not MANIFEST.is_file():
        return "absent (scripts/checks_manifest.json is missing)"
    try:
        value = json.loads(MANIFEST.read_text(encoding="utf-8")).get(
            "expected_ci_guard_count")
    except ValueError as exc:
        return "unreadable (%s)" % exc
    if not isinstance(value, int):
        return "absent (scripts/checks_manifest.json records no " \
               "expected_ci_guard_count)"
    return str(value)


def guard_keys(guard):
    """The four sheet keys one member contributes."""
    return ("Guard-%s" % guard["key"],
            "Guard-%s-inputs" % guard["key"],
            "Guard-%s-fails-job" % guard["key"],
            "Guard-%s-triggered" % guard["key"])


def named(step_name, declared):
    """Does a step name match a declared one? **Exactly, and only.**

    Prefix matching was introduced for one reason - a step whose title
    carries a matrix expression - and it did the classifying by name
    collision instead: `Run the gate on the docs` was swallowed by the
    member `Run the gate`, so an unregistered step slipped past the one
    question that exists to make a new step be classified by whoever
    adds it. **Narrowing it to `declared + " "` does not fix that**, and
    the reproduction is the proof: the collision name begins with the
    member name and a space. So the register carries each step's full
    name, expression included, and this is equality. A step renamed by
    one character is then absent *and* unclassified, which is two reds
    saying the same true thing rather than one silence.
    """
    return step_name == declared


def applies(guard, tree):
    return guard["trees"] == BOTH or guard["trees"] == tree


def is_development_tree():
    """Is this the source tree, or a tree derived from it?

    Read off the derivation spec rather than from a constant of its own,
    the way Rules 35 and 36 ask it: the development tree is the one that
    still holds what the derivation withholds.
    """
    if not SPEC_PATH.is_file():
        return True, "scripts/public_tree.py is absent; assuming the source"
    spec = importlib.util.spec_from_file_location(
        "murscope_public_tree_guards", str(SPEC_PATH))
    module = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(module)
    except BaseException:
        return True, "scripts/public_tree.py does not import; assuming source"
    held = [prefix for prefix, _ in module.EXCLUDED
            if (REPO_ROOT / prefix.rstrip("/")).is_dir()]
    if held:
        return True, "holds %s, which the derivation withholds" % ", ".join(held)
    return False, "holds none of the withheld paths, so it is a derivation"


def steps_in(text):
    """[(name, body)] for one workflow file, with the body after the name.

    **The name is not part of the body, and that is load-bearing.** One
    step is called `Set up Python ${{ matrix.python-version }}`, so a
    body that included its own name satisfied the requirement for the
    matrix binding out of the title while the input underneath had been
    pinned to a single version - the step was no longer bound to the
    matrix and this check said it was. An assertion satisfied by the
    wrong text is the shape this whole rule is about, and it was found by
    trying to make the rule go red rather than by reading it.
    """
    heads = list(STEP_HEAD.finditer(text))
    out = []
    for index, head in enumerate(heads):
        end = heads[index + 1].start() if index + 1 < len(heads) else len(text)
        out.append((head.group(1).strip(), text[head.end():end]))
    return out


def can_fail_the_job(body, asserts, kind=RUN):
    """(ok, reason). Would a failure inside this step stop the run?"""
    if CONTINUE_ON_ERROR in body:
        return False, "it carries `continue-on-error: true`"
    if kind == USES:
        # An action fails its step by failing; there is nothing of ours
        # in it to read. `requires` carries the weight for these, and the
        # OK line says which members are read this way.
        return True, ""
    if RUNS_A_COMMAND not in body:
        return False, ("it runs no command of its own, so there is nothing in "
                       "it that could exit non-zero")
    if SET_PLUS_E.search(body):
        return False, ("it turns errexit back off with `set +e`, so a command "
                       "in it can fail without the step doing so")
    for token in asserts:
        carrying = [line for line in body.splitlines() if token in line]
        if not carrying:
            return False, "its asserting command `%s` is no longer in it" % token
        if all(NEUTRALISED.search(line) for line in carrying):
            return False, ("every line carrying `%s` swallows its exit code"
                           % token)
    return True, ""


def read_workflows():
    """The measured world: what the workflow files hold, as facts."""
    facts = {}
    tree_is_development, reason = is_development_tree()
    tree = DEVELOPMENT if tree_is_development else DERIVATION
    facts["Tree"] = tree
    facts["Tree-reason"] = reason
    facts["Registered"] = str(len(GUARDS))
    facts["Registered-declared"] = declared_size()
    applicable = [g for g in GUARDS if applies(g, tree)]
    facts["Registered-applicable"] = str(len(applicable))

    for guard in applicable:
        present, inputs, fails, triggered = guard_keys(guard)
        facts[present] = "absent"
        facts[inputs] = "unread"
        facts[fails] = "no (the step is absent)"
        facts[triggered] = "no"

    paths = sorted(WORKFLOWS.glob("*.y*ml")) if WORKFLOWS.is_dir() else []
    facts["Workflows"] = str(len(paths))
    facts["Workflow-files"] = ", ".join(
        p.relative_to(REPO_ROOT).as_posix() for p in paths) or "none"

    seen = 0
    infrastructure = 0
    unclassified = []
    by_name = {}
    for path in paths:
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        triggered = any(trigger in text for trigger in TRIGGERS)
        for name, body in steps_in(text):
            seen += 1
            by_name.setdefault(name, (body, triggered))
            if any(named(name, prefix) for prefix in INFRASTRUCTURE):
                infrastructure += 1
                continue
            if any(named(name, g["step"]) for g in GUARDS):
                continue
            unclassified.append(name)

    facts["Steps-seen"] = str(seen)
    # **Counted, not subtracted.** This number was `Steps-seen` minus the
    # applicable members, which is right by arithmetic exactly while
    # nothing slips through - and it printed `the other 3 are named
    # infrastructure` when there were two, in the output of a rule about
    # numbers nobody compares to anything.
    facts["Steps-infrastructure"] = str(infrastructure)
    facts["Steps-unclassified"] = str(len(unclassified))
    if unclassified:
        facts["Unclassified-steps"] = "; ".join(unclassified)

    for guard in applicable:
        found = next((v for k, v in by_name.items()
                      if named(k, guard["step"])), None)
        if not found:
            continue
        body, triggered = found
        present, inputs, fails, trig = guard_keys(guard)
        facts[present] = "present"
        missing = [token for token in guard["requires"] if token not in body]
        facts[inputs] = ("complete" if not missing
                         else "missing " + ", ".join("`%s`" % m for m in missing))
        ok, why = can_fail_the_job(body, guard["asserts"],
                                   guard.get("kind", RUN))
        facts[fails] = "yes" if ok else "no (%s)" % why
        facts[trig] = "yes" if triggered else "no"
    return facts


def sheet(facts):
    """The measured world as a document, which is what detect() judges."""
    order = ["Tree", "Tree-reason", "Workflows", "Workflow-files",
             "Steps-seen", "Steps-infrastructure", "Steps-unclassified",
             "Unclassified-steps",
             "Registered", "Registered-declared", "Registered-applicable"]
    for guard in GUARDS:
        order.extend(guard_keys(guard))
    lines = ["%s: %s" % (key, facts[key]) for key in order if key in facts]
    lines.extend("%s: %s" % (key, value) for key, value in sorted(facts.items())
                 if key not in order)
    return "\n".join(lines) + "\n"


def detect(payload):
    """Findings for a measured sheet: a guard that stopped being installed.

    Pure. Everything judged here was measured by `main()` and written
    into the payload, so every branch is reachable from a fixture - a
    step deleted, a token dropped, an assertion swallowed, a workflow
    nothing triggers - without any of them having to be arranged in the
    tree this happens to run in.
    """
    text = payload.decode("utf-8", errors="replace")
    facts = {}
    for line in text.splitlines():
        match = FIELD.match(line)
        if match:
            facts[match.group(1)] = match.group(2)

    findings = []
    for key in REQUIRED_KEYS:
        if key not in facts:
            findings.append(
                "the measured sheet carries no `%s`. A judgment made over a "
                "sheet with a key missing is a judgment about nothing (DP87)."
                % key)
    if findings:
        return findings

    declared = facts["Registered-declared"]
    if declared != facts["Registered"]:
        findings.append(
            "this register holds %s guard(s) and the freeze declares %s. A "
            "set whose size is recorded nowhere shrinks by one edit with no "
            "trace but a smaller number in its own output, which is why the "
            "size is declared in scripts/checks_manifest.json and why "
            "lowering it there needs --allow-shrink. Regenerate the freeze if "
            "the register really changed, and let the diff carry it."
            % (facts["Registered"], declared))

    tree = facts["Tree"]
    if facts["Workflows"] in ("0", ""):
        findings.append(
            "there is no workflow file at all, so every assertion in the "
            "register below has no home. Rule 11 keeps two of them out of "
            "scripts/ on purpose; with no workflow they are nowhere.")
        return findings
    if facts["Steps-seen"] in ("0", ""):
        findings.append(
            "the workflow files hold no step this check could read. Either "
            "they are empty or the shape a step is written in has changed, "
            "and a keeper that reads no steps reports every guard absent or "
            "none - neither of which is a measurement.")
        return findings

    unclassified = facts["Steps-unclassified"]
    if unclassified not in ("0", ""):
        findings.append(
            "%s workflow step(s) are neither a registered guard nor named "
            "infrastructure: %s. Every step is one or the other on purpose - "
            "otherwise deleting a row from the register leaves its step "
            "running and unwatched, and this check reports a smaller set in "
            "green. Add it to the register with what it asserts, or to the "
            "infrastructure list if its absence would announce itself."
            % (unclassified, facts.get("Unclassified-steps", "unnamed")))

    for guard in GUARDS:
        present, inputs, fails, triggered = guard_keys(guard)
        if not applies(guard, tree):
            continue
        missing = [key for key in (present, inputs, fails, triggered)
                   if key not in facts]
        if missing:
            findings.append(
                "the measured sheet carries no %s, so `%s` was not measured "
                "in a tree where it applies."
                % (", ".join("`%s`" % key for key in missing), guard["step"]))
            continue
        if facts[present] != "present":
            findings.append(
                "no workflow step is named `%s`. What goes with it: %s. A step "
                "deleted from a workflow leaves the gate green and every check "
                "passing, which is the whole reason this rule exists."
                % (guard["step"], guard["why"]))
            continue
        if facts[inputs] != "complete":
            findings.append(
                "`%s` has lost part of what its assertion is made of: %s. It "
                "will keep running and keep reporting, and what it reports "
                "will be about less than it says."
                % (guard["step"], facts[inputs]))
        if facts[fails] != "yes":
            findings.append(
                "`%s` cannot fail the job: %s. A step that reports and "
                "continues is a log line, not a gate - and a green job beside "
                "it is a statement nobody made."
                % (guard["step"], facts[fails][4:].rstrip(")")
                   if facts[fails].startswith("no (") else facts[fails]))
        if facts[triggered] != "yes":
            findings.append(
                "`%s` sits in a workflow with no trigger, so nothing starts "
                "it. A watcher nobody runs has the same latency as no watcher."
                % guard["step"])
    return findings


def main():
    facts = read_workflows()
    payload = sheet(facts)
    findings = detect(payload.encode("utf-8"))
    if findings:
        for finding in findings:
            print(finding)
        print("\nMeasured:")
        for line in payload.splitlines():
            print("  %s" % line)
        print("\nFAILED: %d finding(s) on guards that live where the gate "
              "cannot see them." % len(findings))
        return 1

    tree = facts["Tree"]
    applicable = [g for g in GUARDS if applies(g, tree)]
    withheld = [g for g in GUARDS if not applies(g, tree)]
    commanding = [g for g in applicable if g.get("kind", RUN) == RUN]
    delegated = [g for g in applicable if g.get("kind", RUN) == USES]
    print("OK: %s guard(s) of %s registered - and %s is what the freeze "
          "declares, so narrowing the register takes an edit in "
          "scripts/checks_manifest.json too - are installed in %s, each with "
          "the inputs its assertion is made of and each in a workflow "
          "something triggers. %s step(s) read in all, of which %s are named "
          "infrastructure, whose absence announces itself."
          % (len(applicable), facts["Registered"], facts["Registered-declared"],
             facts["Workflow-files"], facts["Steps-seen"],
             facts["Steps-infrastructure"]))
    print("    **Able to fail the job was read of %d of them**, the ones "
          "running a command of ours. The other %d `uses:` somebody else's "
          "action, where there is nothing of ours to read and all that was "
          "asserted is that the step is not exempted from failing - marked "
          "`uses` below rather than counted in a sentence that would then be "
          "about less than it says."
          % (len(commanding), len(delegated)))
    for guard in applicable:
        print("    %-26s %-5s %s"
              % (guard["key"], guard.get("kind", RUN), guard["step"]))
    if withheld:
        print("    This is a %s (%s), so %d member(s) do not apply and are not "
              "looked for: %s. Both watch the repository this tree came from, "
              "which this tree cannot ask after and carries no evidence about."
              % (tree, facts["Tree-reason"], len(withheld),
                 ", ".join(g["key"] for g in withheld)))
    print("    **What this does not cover, in the same breath as the result.** "
          "The register is in this file, so one edit here narrows what is "
          "watched for every member at once - that is what a keeper for a "
          "class costs, and it was ruled for over a third one-off anyway. Two "
          "things bound it. A dropped row leaves its step unclassified, which "
          "is red; and the register's size is declared in the freeze, so a "
          "row and its step going together is red as well until somebody "
          "regenerates with --allow-shrink. **The residue is three legible "
          "edits in one commit** - the row, the step, and the declared size - "
          "which is where `expected_check_count` has stood since M0, and it "
          "is written down rather than left to be discovered.")
    print("    And `Run the gate` is watched from inside itself: this check "
          "runs in that step, so if it is deleted the red comes from a "
          "contributor's own pre-flight and from no CI run at all.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
