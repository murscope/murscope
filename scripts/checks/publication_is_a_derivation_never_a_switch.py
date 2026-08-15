"""Rule 36: publication is a derivation, never a switch.

Every other irreversible thing in this repository is a file, and files
have checks. **This one is a setting.** DP160 ruled that the release is
a second repository founded from a clean tree, and for five milestones
that ruling was the only thing standing between the settings page and
everything here being readable in one click - a decision, not a gate,
which is the wall art Rule 1 has refused since the first commit.

`PUBLICATION.md` is the ruling written down. This is the check that
reads it.

**What this check can do, exactly.** Three things, all offline:

1. **The declaration is there and is not a fiction.** `Switch: never`
   and a `Mechanism:` that resolves to the real derivation machinery -
   a module exposing `EXCLUDED`, `REWRITES` and `extract()`. A
   declaration naming a filename that stopped meaning anything is how
   this decays.
2. **The blast radius is measured and printed**, from history rather
   than from a sentence, so the number is in front of whoever is
   deciding. No count is written into `PUBLICATION.md` (DP159); they are
   all measured here.
3. **The probe that watches the switch is still installed in CI**, still
   has a token, still asks about *this* repository, and can still fail
   the job.

**What it cannot do, and why the probe is in CI.** It cannot ask GitHub.
Rule 11 forbids every module under `murscope/` and under `scripts/` from
shelling out to a network tool, `gh` included, and buying one probe with
an exemption to that rule would trade a live red line for a watcher -
the trade every hole this repository has found began with. So the probe
is a step in `.github/workflows/`, where the network is expected and the
repository is already identified, and this check's job is to make sure
that step is still capable of firing. That is the same move Rule 2 made
when branch protection was unavailable, one level up: verify the
mechanism you have rather than name one you do not.

The gap that leaves is named rather than papered over: between two CI
runs nothing is watching, so this is a detector with a latency and not a
lock. `PUBLICATION.md` says so in the same words.

**Measured, then judged.** `main()` reads the world - the declaration,
git, the workflow files - into a flat sheet of `Key: value` lines, and
`detect()` judges the sheet and nothing else. That split is deliberate:
every branch of the judgment is then reachable from a fixture without
needing a repository in a particular state, and a sheet that has *lost*
a key is a finding rather than a silent pass, which is the shape DP87 is
about.

**The blast radius is wider than any branch.** `git log --all` in a
normal clone does not see `refs/pull/N/head`, which GitHub keeps for
every pull request ever opened and which any reader fetches with one
refspec. So the local counts here are a floor and say so; the pull
request references on `main` are counted because each one names a head
that is still on the remote.

Fails when: `PUBLICATION.md` is missing or carries no declaration block;
`Switch` is absent or is anything other than `never`; `Mechanism` is
absent or does not resolve to the derivation machinery; git cannot be
read, or the history measures nothing at all; or - in the development
tree - no workflow step probes this repository's visibility, the probe
has no token in scope, or it cannot fail the job.
"""
from __future__ import annotations

import importlib.util
import os
import re
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
DECLARATION = REPO_ROOT / "PUBLICATION.md"
SPEC_PATH = REPO_ROOT / "scripts" / "public_tree.py"
WORKFLOWS = REPO_ROOT / ".github" / "workflows"

# The declaration is the first fenced block in the document. Fenced
# rather than "any Key: value line anywhere", because the prose around
# it discusses the same keys and a scanner that read the prose would
# take an explanation for a ruling.
FENCE = re.compile(r"^```", re.MULTILINE)
FIELD = re.compile(r"^([A-Za-z][A-Za-z0-9_-]*):\s*(.*?)\s*$")

# What the mechanism has to actually be. Naming a path is not enough:
# a `Mechanism:` pointing at an empty file would satisfy any check that
# only asked whether the file existed.
MECHANISM_SURFACE = ("EXCLUDED", "REWRITES", "extract")

# A step in a workflow. Split on the step marker rather than parsed as
# YAML - there is no YAML parser in the standard library and ADR-0001
# forbids adding one, so the shape is read the way a reviewer reads it.
STEP_SPLIT = re.compile(r"^\s*-\s+name:", re.MULTILINE)

# What makes a step the visibility probe, by category rather than by its
# name: it asks the hosting account about a repository, it names the
# thing it is asking about, and it can say no.
PROBE_ASKS = ("gh api", "gh repo view")
PROBE_SUBJECT = "visibility"
PROBE_THIS_REPOSITORY = "GITHUB_REPOSITORY"
PROBE_TOKENS = ("GH_TOKEN", "GITHUB_TOKEN")
PROBE_REFUSES = "exit 1"
TRIGGERS = ("push:", "pull_request:")

# Rule 5's environment pairing applies to repository tooling too (DP31).
GIT_ENV_KEY = "GIT_OPTIONAL_LOCKS"

REQUIRED_KEYS = (
    "Tree", "Declaration", "Switch", "Mechanism", "Mechanism-resolves",
    "History-readable", "Commits-all-refs", "Commits-main",
    "Pull-request-refs",
)
PROBE_KEYS = (
    "Workflow-probe", "Workflow-probe-token", "Workflow-probe-fails-job",
    "Workflow-probe-asks-this-repository", "Workflow-probe-triggered",
)

DEVELOPMENT = "development"


def git(args):
    """A read-only git call under Rule 5's locked environment, or None."""
    env = dict(os.environ)
    env[GIT_ENV_KEY] = "0"
    try:
        proc = subprocess.run(
            ["git", "-C", str(REPO_ROOT)] + args,
            capture_output=True, text=True, timeout=60, env=env)
    except (subprocess.TimeoutExpired, OSError):
        return None
    if proc.returncode != 0:
        return None
    return proc.stdout


def declaration_fields(text):
    """The `Key: value` pairs of the first fenced block, as a dict."""
    fences = list(FENCE.finditer(text))
    if len(fences) < 2:
        return {}
    body = text[fences[0].end():fences[1].start()]
    fields = {}
    for line in body.splitlines():
        match = FIELD.match(line)
        if match:
            fields[match.group(1)] = match.group(2)
    return fields


def mechanism_resolves(value):
    """(ok, reason) - does `value` name the real derivation machinery?"""
    if not value:
        return False, "no Mechanism is declared"
    candidate = (REPO_ROOT / value).resolve()
    try:
        candidate.relative_to(REPO_ROOT)
    except ValueError:
        return False, "%s is outside this tree" % value
    if candidate.suffix != ".py" or not candidate.is_file():
        return False, "%s is not a Python file in this tree" % value
    spec = importlib.util.spec_from_file_location(
        "murscope_declared_mechanism", str(candidate))
    module = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(module)
    except BaseException as exc:  # a mechanism that cannot load is not one
        return False, "%s does not import (%s)" % (value, type(exc).__name__)
    missing = [name for name in MECHANISM_SURFACE
               if not hasattr(module, name)]
    if missing:
        return False, ("%s exposes no %s, so it is a filename rather than a "
                       "derivation" % (value, ", ".join(missing)))
    return True, ""


def is_development_tree():
    """Is this the source tree, or a tree derived from it?

    Read off the derivation spec rather than from a constant of its own:
    the development tree is the one that still holds what the derivation
    withholds. A derived tree answers no, and Rule 36's third question -
    which is about the development repository's visibility - does not
    apply to it.
    """
    if not SPEC_PATH.is_file():
        return True, "scripts/public_tree.py is absent; assuming the source"
    spec = importlib.util.spec_from_file_location(
        "murscope_public_tree_probe", str(SPEC_PATH))
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


def workflow_probe():
    """The visibility probe's properties, read out of the workflow files."""
    facts = dict.fromkeys(PROBE_KEYS, "no")
    facts["Workflow-probe"] = "absent"
    facts["Workflow-probe-token"] = "absent"
    if not WORKFLOWS.is_dir():
        return facts
    for path in sorted(WORKFLOWS.glob("*.y*ml")):
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        triggered = any(trigger in text for trigger in TRIGGERS)
        for step in STEP_SPLIT.split(text)[1:]:
            asks = any(token in step for token in PROBE_ASKS)
            if not (asks and PROBE_SUBJECT in step):
                continue
            facts["Workflow-probe"] = "present"
            if any(token in step for token in PROBE_TOKENS):
                facts["Workflow-probe-token"] = "present"
            if PROBE_REFUSES in step:
                facts["Workflow-probe-fails-job"] = "yes"
            if PROBE_THIS_REPOSITORY in step:
                facts["Workflow-probe-asks-this-repository"] = "yes"
            if triggered:
                facts["Workflow-probe-triggered"] = "yes"
            return facts
    return facts


def blast_radius():
    """What a flipped switch would release, measured from local history."""
    facts = {"History-readable": "yes"}
    refs = []
    for ref in ("origin/main", "main", "HEAD"):
        if git(["rev-parse", "--verify", "--quiet", ref]):
            refs.append(ref)
    if not refs:
        facts["History-readable"] = "no (no main and no HEAD resolves here)"
        for key in ("Commits-all-refs", "Commits-main", "Pull-request-refs",
                    "Commits-off-main", "Pull-request-heads-local"):
            facts[key] = "0"
        return facts
    main_ref = refs[0]
    everything = git(["rev-list", "--count", "--all"])
    on_main = git(["rev-list", "--count", main_ref])
    off_main = git(["rev-list", "--count", "--all", "--not", main_ref])
    subjects = git(["log", "--format=%s", main_ref])
    heads = git(["for-each-ref", "--format=%(refname)", "refs/pull/"])
    if everything is None or on_main is None or subjects is None:
        facts["History-readable"] = "no (git refused to read %s)" % main_ref
        for key in ("Commits-all-refs", "Commits-main", "Pull-request-refs",
                    "Commits-off-main", "Pull-request-heads-local"):
            facts.setdefault(key, "0")
        return facts
    references = set(re.findall(r"\(#(\d+)\)", subjects))
    facts["Main-ref"] = main_ref
    facts["Commits-all-refs"] = everything.strip() or "0"
    facts["Commits-main"] = on_main.strip() or "0"
    facts["Commits-off-main"] = (off_main or "0").strip() or "0"
    facts["Pull-request-refs"] = str(len(references))
    facts["Pull-request-heads-local"] = str(
        len([line for line in (heads or "").splitlines() if line.strip()]))
    return facts


def sheet(facts):
    """The measured world as a document, which is what detect() judges."""
    order = ["Tree", "Tree-reason", "Declaration", "Switch", "Mechanism",
             "Mechanism-resolves", "History-readable", "Main-ref",
             "Commits-all-refs", "Commits-main", "Commits-off-main",
             "Pull-request-refs", "Pull-request-heads-local"]
    order.extend(PROBE_KEYS)
    lines = ["%s: %s" % (key, facts[key]) for key in order if key in facts]
    lines.extend("%s: %s" % (key, value) for key, value in sorted(facts.items())
                 if key not in order)
    return "\n".join(lines) + "\n"


def detect(payload):
    """Findings for a measured sheet: a switch that is no longer shut.

    Pure. Everything it judges was measured by `main()` and written into
    the payload, so every branch below is reachable from a fixture -
    including the one nobody can arrange locally, which is a repository
    that has already been made public.

    A key it needs and cannot find is a finding, not a pass. A sheet that
    quietly lost `Switch` would otherwise certify a switch nobody looked
    at (DP87).
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

    if facts["Declaration"] != "present":
        findings.append(
            "PUBLICATION.md carries no declaration block. The ruling that "
            "this repository is never published by being made public is then "
            "nowhere in the tree, and Rule 36 has nothing to enforce.")
    switch = facts["Switch"]
    if switch != "never":
        findings.append(
            "PUBLICATION.md declares `Switch: %s`. The only value this rule "
            "recognises is `never`: publication is a derivation into a second "
            "repository (DP160, DP162), and this repository's visibility is "
            "not a release channel." % (switch or "<empty>"))
    if facts["Mechanism-resolves"] != "yes":
        findings.append(
            "the declared publication mechanism is not one: %s. A "
            "`Mechanism:` that names a file which stopped being the "
            "derivation leaves the declaration true in wording and empty in "
            "fact." % (facts.get("Mechanism-resolves-reason")
                       or facts["Mechanism-resolves"]))
    if facts["History-readable"] != "yes":
        findings.append(
            "the blast radius could not be measured: %s. This check reports "
            "what a flipped switch would release, and a report it could not "
            "produce is red rather than reassuring (DP87)."
            % facts["History-readable"])
    elif facts["Commits-all-refs"] in ("0", ""):
        findings.append(
            "the history measures 0 commit(s) across every ref. Nothing "
            "walked to this check, so its blast radius paragraph would be a "
            "reassuring sentence about an empty repository (DP87).")

    if facts["Tree"] != DEVELOPMENT:
        return findings

    for key in PROBE_KEYS:
        if key not in facts:
            findings.append(
                "the measured sheet carries no `%s`, and this is the "
                "development tree, where the probe is the only thing watching "
                "the switch." % key)
    if findings and any(key not in facts for key in PROBE_KEYS):
        return findings

    if facts["Workflow-probe"] != "present":
        findings.append(
            "no workflow step asks this repository's visibility. Rule 11 "
            "keeps that probe out of scripts/ - `gh` is a network tool - so "
            "CI is where it lives, and with the step gone nothing anywhere "
            "observes the one change in this repository that cannot be "
            "undone.")
        return findings
    if facts["Workflow-probe-token"] != "present":
        findings.append(
            "the visibility probe has no `GH_TOKEN` or `GITHUB_TOKEN` in "
            "scope. It will answer nothing on every run, which reads in the "
            "log exactly like a repository that is fine.")
    if facts["Workflow-probe-fails-job"] != "yes":
        findings.append(
            "the visibility probe cannot fail its job: no `exit 1` on the "
            "path that finds a non-private repository. A probe that reports "
            "and continues is a log line, not a gate.")
    if facts["Workflow-probe-asks-this-repository"] != "yes":
        findings.append(
            "the visibility probe does not name `GITHUB_REPOSITORY`, so it is "
            "asking about a repository somebody typed rather than the one "
            "being built - and it would stay green while this one went "
            "public.")
    if facts["Workflow-probe-triggered"] != "yes":
        findings.append(
            "the visibility probe is in a workflow with no `push` or "
            "`pull_request` trigger, so nothing runs it. A watcher nobody "
            "starts has the same latency as no watcher.")
    return findings


def main():
    facts = {}
    development, reason = is_development_tree()
    facts["Tree"] = DEVELOPMENT if development else "derivation"
    facts["Tree-reason"] = reason

    if DECLARATION.is_file():
        text = DECLARATION.read_text(encoding="utf-8")
        fields = declaration_fields(text)
        facts["Declaration"] = "present" if fields else "absent"
        facts["Switch"] = fields.get("Switch", "")
        facts["Mechanism"] = fields.get("Mechanism", "")
    else:
        facts["Declaration"] = "absent"
        facts["Switch"] = ""
        facts["Mechanism"] = ""

    resolves, why = mechanism_resolves(facts["Mechanism"])
    facts["Mechanism-resolves"] = "yes" if resolves else "no"
    if why:
        facts["Mechanism-resolves-reason"] = why

    facts.update(blast_radius())
    if development:
        facts.update(workflow_probe())

    payload = sheet(facts)
    findings = detect(payload.encode("utf-8"))
    if findings:
        for finding in findings:
            print(finding)
        print("\nMeasured:")
        for line in payload.splitlines():
            print("  %s" % line)
        print("\nFAILED: %d finding(s) on the one thing here that is a "
              "setting rather than a file." % len(findings))
        return 1

    if not development:
        print("OK: this tree is a derivation (%s), so the visibility question "
              "is not its own - it is asked of the repository this tree came "
              "from. The declaration holds: `Switch: never`, mechanism `%s`, "
              "which resolves to the real derivation. %s commit(s) across "
              "every ref here." % (reason, facts["Mechanism"],
                                   facts["Commits-all-refs"]))
        return 0

    print("OK: `Switch: never` is declared in PUBLICATION.md and `%s` resolves "
          "to the derivation itself (%s). The probe that watches the switch is "
          "installed in CI, has a token, names GITHUB_REPOSITORY, and exits 1 "
          "on a repository that is not private."
          % (facts["Mechanism"], ", ".join(MECHANISM_SURFACE)))
    print("    What that switch would release, measured from this clone and "
          "not written down anywhere (DP159): %s commit(s) reachable from "
          "every local ref, of which %s are on %s and %s are on no branch; %s "
          "pull request reference(s) on %s."
          % (facts["Commits-all-refs"], facts["Commits-main"],
             facts.get("Main-ref", "main"), facts["Commits-off-main"],
             facts["Pull-request-refs"], facts.get("Main-ref", "main")))
    print("    **Those are a floor.** GitHub keeps refs/pull/N/head for every "
          "pull request ever opened and a reader fetches all of them with one "
          "refspec; %s are in this clone. The rest carry pre-squash commits "
          "that `git log --all` here cannot see, and every workflow run's log "
          "goes out with them. To measure the real number rather than this "
          "floor:"
          % facts["Pull-request-heads-local"])
    print("      git fetch origin '+refs/pull/*/head:refs/pull/*/head'")
    print("    The gap this check does not close: between two CI runs nothing "
          "is watching, so the probe is a detector with a latency and not a "
          "lock. PUBLICATION.md says so in the same words.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
