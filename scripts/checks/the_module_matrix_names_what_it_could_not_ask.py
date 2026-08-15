"""Rule 31: the module matrix names what it could not ask.

The matrix is the surface that makes `registry.register()`'s declaration
legible - what is installed, what is enabled, what each module reads and
where each one sends. **Its sentences are as much of the deliverable as
its rows**, because the one accounting sentence this product has shipped
about provider modules was wrong (DP115): `daily --providers` computed
"N other provider module(s) are installed and not enabled, so they were
not imported" as installed-minus-writers, so with the contributions
reader switched on it named `github` - a module that *is* enabled, *is*
in `sys.modules`, and *is* returned by `registry.readers()`. Its real
reason for having no row was that it registers `reads` and not `writes`,
and the count was wrong by one in the same breath.

**The property this rule holds is that the matrix distinguishes three
states and never collapses them:**

1. **enabled, imported, and does not do this** - the module declared
   itself and the capability is genuinely absent. `no`.
2. **not imported** - `register()` never ran, so nothing here knows what
   the module does. `unknown`. Not `no`, and not a dash: a dash is a
   statement, and the statement would be the one DP115 got wrong.
3. **named by configuration and not on disk** - not a module that does
   nothing, a configuration line pointing at nothing.

The `socket` column is deliberately outside that scheme and the matrix
says so: `boundary.survey()` **reads** each module's source rather than
importing it, so that column is known for every module on the disk
including the ones nothing ran.

**What walks into this check (DP87).** The shipped `matrix` module is
driven in a fresh interpreter against a synthetic provider directory,
never against whatever happens to be installed on the machine running the
gate - a base install has one module and could not exercise a single one
of the three states above. The directory holds four modules: one enabled
that registers a **reader and no writer** (DP115's own module), one
enabled that registers a writer, one that is socket-capable and is *not*
enabled, and one that is neither. Configuration also names a fifth that
is not there. The case table is asserted to cover all three states before
any row is read, so a fixture that lost the reader case would go red
rather than certify the sentence that case exists for.

The command itself is driven too, in the same interpreter, because a
correct `matrix.rows()` printed by a broken command is DP115 again one
layer out.

Fails when: an imported module's capability is reported as `unknown`, or
an un-imported module's is reported as anything but `unknown`; the
accounting sentences miscount any of the three groups, or name a module
in the wrong one; a module that is enabled and imported is described as
not imported; the socket column is `unknown` for a module on disk; the
sentences are suppressed when nothing is enabled; `murscope modules`
prints no row for a module the matrix returned; or the case table stops
covering all three states.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

# The synthetic provider directory. Written into a throwaway home, never
# beside the real ones: a check that plants a module in
# `murscope/providers/` would be caught by the very survey it is driving.
#
# name, source, enabled
PROVIDER_SOURCES = (
    # DP115's own module: enabled, imported, registers a reading and no
    # writer. The sentence that used to call this "installed and not
    # enabled, so it was not imported" was wrong about all three.
    ("reader", '''from murscope import registry

registry.register("reader", "reads a calendar", stage="M3",
                  reads=lambda **kw: None,
                  destination="https://example.invalid",
                  evidence="live", evidence_note="a real exchange is recorded")
''', True),
    ("writer", '''from murscope import registry

registry.register("writer", "turns a payload into a note", stage="M3",
                  writes=lambda **kw: None,
                  destination="https://example.invalid",
                  evidence="unproven", evidence_note="no round trip yet")
''', True),
    # Socket-capable and never imported. Its row must still say `yes` in
    # the socket column, because that column is read off the file.
    ("dormant", '''import urllib.request

from murscope import registry

registry.register("dormant", "would open a socket if anything ran it")
''', False),
    ("quiet", '''from murscope import registry

registry.register("quiet", "opens nothing, and nothing imported it")
''', False),
)

# Named by configuration and not on disk.
ABSENT = "phantom"

PROBE = r'''
import json, sys, io, contextlib
from pathlib import Path

sys.path.insert(0, %(repo)r)
home = Path(%(home)r)
fake = Path(%(providers)r)

from murscope import boundary, cli, config, matrix, providers, registry

# Point the shipped loader and the shipped survey at the synthetic
# directory. Both are read through module attributes on purpose, so a
# probe can move them without either one growing a parameter nobody else
# passes.
providers.__path__ = [str(fake)]
# The synthetic modules stand in as what the base distribution ships, so
# `survey()` reads their capability instead of reporting four files no
# installed distribution owns. Distribution attribution is Rule 13b's
# subject and step 9's; what this probe is about is the three states.
providers.BASE = tuple(%(names)s)
boundary.PROVIDERS_DIR = fake

settings = config.load_config(home)
loaded, problems = providers.load(
    settings.section("providers").get("enabled", []))

rows = matrix.rows(home, settings)
sentences = matrix.sentences(rows)

printed = io.StringIO()
with contextlib.redirect_stdout(printed):
    code = cli.modules_command([])

print(json.dumps({
    "rows": rows,
    "sentences": sentences,
    "loaded": sorted(loaded),
    "problems": problems,
    "registered": sorted(registry.registered()),
    "printed": printed.getvalue(),
    "exit": code,
}))
'''


def detect(payload):
    """Findings for one matrix, handed in as JSON.

    Pure: what the shipped module returned, plus what the command printed,
    plus the expectations the synthetic directory sets up. Everything that
    needs an interpreter of its own happens in `main()`.
    """
    try:
        case = json.loads(payload.decode("utf-8"))
    except ValueError as exc:
        return ["the probe produced no readable answer (%s)." % exc]

    rows = {row["name"]: row for row in case.get("rows") or ()}
    sentences = " ".join(case.get("sentences") or ())
    printed = case.get("printed") or ""
    expected = case.get("expected") or {}
    findings = []

    for name, want in sorted(expected.items()):
        row = rows.get(name)
        if row is None:
            findings.append("the matrix returned no row for %r." % name)
            continue
        for column, value in sorted(want.items()):
            if row.get(column) != value:
                findings.append(
                    "%s: the %s column reads %r and should read %r. %s"
                    % (name, column, row.get(column), value,
                       "An un-imported module's capability is `unknown`, "
                       "never `no`: nothing asked it (DP115)."
                       if value == "unknown" else
                       "This module declared itself, so the matrix knows."))
        if name in rows and row.get("known") != (want.get("reads") != "unknown"):
            findings.append(
                "%s: `known` is %r while its capability columns say %r, so "
                "the row and the flag the sentences count from disagree."
                % (name, row.get("known"), want.get("reads")))

    # The module's own table line, not "the name appears somewhere in the
    # output". The looser form was green with the command dropping every
    # un-imported row, because the accounting sentences below the table
    # name those modules too - an assertion answered by a neighbour, which
    # is the shape DP143 records four times over.
    first_words = {line.strip().split(" ", 1)[0]
                   for line in printed.splitlines() if line.startswith("  ")}
    for name in expected:
        if name not in first_words:
            findings.append(
                "murscope modules printed no table row for %r. The matrix "
                "returned it; the screen dropped it, which is DP115 one layer "
                "out - a correct table behind a command that prints something "
                "else." % name)

    described = sorted(n for n, r in rows.items() if r.get("known"))
    silent = sorted(n for n, r in rows.items()
                    if not r.get("known") and r.get("distribution") != "not installed")
    absent = sorted(n for n, r in rows.items()
                    if r.get("distribution") == "not installed")

    if "%d of them" % len(described) not in sentences \
            and str(len(described)) not in sentences:
        findings.append("the sentences do not count the %d described "
                        "module(s)." % len(described))
    for name in silent:
        if name not in sentences:
            findings.append(
                "%r was not imported and no sentence names it. The reader is "
                "left to work out why its row is all `unknown`, which is the "
                "half DP115 was about." % name)
    for name in absent:
        if name not in sentences:
            findings.append(
                "%r is named by configuration and is not installed, and no "
                "sentence says so." % name)
    for name in described:
        if name in silent or name in absent:
            continue
        if "not enabled" in sentences and name in sentences.split("not enabled")[-1]:
            findings.append(
                "%r is enabled and imported, and a sentence about modules "
                "that were not imported names it (DP115 exactly)." % name)
    if not sentences.strip():
        findings.append("the matrix printed no accounting sentences at all. "
                        "The install that most needs them is the one whose "
                        "table is all `unknown`.")
    if case.get("exit") not in (0, None):
        findings.append("murscope modules exited %r." % case.get("exit"))
    return findings


def case_floors(expected):
    """The three states this check exists to tell apart must all be here."""
    findings = []
    if not any(want.get("reads") == "yes" and want.get("writes") == "no"
               for want in expected.values()):
        findings.append(
            "no case is enabled, imported, and registers a reading with no "
            "writer. That is DP115's own module - the one the old sentence "
            "called 'not enabled, not imported' - and without it this check "
            "certifies the repair without reaching it.")
    if not any(want.get("reads") == "unknown" for want in expected.values()):
        findings.append("no case is an installed module nothing imported, so "
                        "`unknown` is never exercised.")
    if not any(want.get("distribution") == "not installed"
               for want in expected.values()):
        findings.append("no case is a configured name that is not on disk.")
    if not any(want.get("socket") == "yes" and want.get("reads") == "unknown"
               for want in expected.values()):
        findings.append(
            "no case is socket-capable *and* un-imported, so nothing proves "
            "the socket column is read off the file rather than asked of the "
            "registry.")
    return findings


def build(tmp, label, enabled):
    """Write one synthetic home and provider directory. Returns paths."""
    home = tmp / ("home-%s" % label)
    home.mkdir(parents=True)
    fake = tmp / ("providers-%s" % label)
    fake.mkdir(parents=True)
    for name, source, _enabled in PROVIDER_SOURCES:
        (fake / ("%s.py" % name)).write_text(source, encoding="utf-8")
    (home / "config.toml").write_text(
        "[providers]\nenabled = [%s]\n"
        % ", ".join('"%s"' % name for name in enabled), encoding="utf-8")
    return home, fake


EXPECTED = {
    "reader": {"enabled": "yes", "imported": "yes", "socket": "no",
               "reads": "yes", "writes": "no", "alerts": "no",
               "evidence": "live"},
    "writer": {"enabled": "yes", "imported": "yes", "socket": "no",
               "reads": "no", "writes": "yes", "alerts": "no",
               "evidence": "unproven"},
    "dormant": {"enabled": "no", "imported": "no", "socket": "yes",
                "reads": "unknown", "writes": "unknown",
                "alerts": "unknown", "evidence": "unknown"},
    "quiet": {"enabled": "no", "imported": "no", "socket": "no",
              "reads": "unknown", "writes": "unknown",
              "alerts": "unknown", "evidence": "unknown"},
    ABSENT: {"enabled": "yes", "imported": "no", "distribution": "not installed",
             "reads": "unknown", "writes": "unknown", "alerts": "unknown"},
}

# The second install, and it is the one DP115's defect lived on. With
# nothing enabled there is no module to describe, and the old accounting
# sat behind an early return - so the install whose whole table is
# `unknown`, the one whose reader most needs the explanation, printed one
# bare line and stopped. Every row here is un-imported on purpose.
EXPECTED_NOTHING_ENABLED = {
    name: {"enabled": "no", "imported": "no",
           "socket": "yes" if name == "dormant" else "no",
           "reads": "unknown", "writes": "unknown", "alerts": "unknown",
           "evidence": "unknown"}
    for name, _source, _on in PROVIDER_SOURCES
}

# label, enabled names, expectations
INSTALLS = (
    ("configured", [name for name, _s, on in PROVIDER_SOURCES if on] + [ABSENT],
     EXPECTED),
    ("nothing-enabled", [], EXPECTED_NOTHING_ENABLED),
)


def main():
    import shutil  # noqa: PLC0415 - only the harness needs it
    import tempfile  # noqa: PLC0415

    findings = case_floors(EXPECTED)
    if not any(not enabled for _label, enabled, _want in INSTALLS):
        findings.append(
            "no install with an empty `enabled` list is driven, so the "
            "accounting is never asked to speak on the one configuration "
            "whose table is entirely `unknown` - which is the configuration "
            "the old sentence returned early on (DP115).")
    tmp = Path(tempfile.mkdtemp(prefix="murscope-matrix-"))
    try:
        for label, enabled, want in INSTALLS:
            home, fake = build(tmp, label, enabled)
            program = PROBE % {
                "repo": str(REPO_ROOT), "home": str(home),
                "providers": str(fake),
                "names": repr([name for name, _s, _on in PROVIDER_SOURCES])}
            result = subprocess.run(
                [sys.executable, "-c", program], cwd=str(tmp),
                env={"PATH": "/usr/bin:/bin", "MURSCOPE_HOME": str(home),
                     "HOME": str(home)},
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=120)
            if result.returncode != 0:
                print("%s: the probe interpreter exited %d: %s"
                      % (label, result.returncode,
                         result.stderr.decode("utf-8", "replace").strip()[:600]))
                print("\nFAILED: the matrix could not be driven at all.")
                return 1
            answer = json.loads(result.stdout.decode("utf-8"))
            answer["expected"] = want
            findings.extend("%s: %s" % (label, finding) for finding in
                            detect(json.dumps(answer).encode("utf-8")))
    finally:
        shutil.rmtree(str(tmp), ignore_errors=True)

    if findings:
        for finding in findings:
            print(finding)
        print("\nFAILED: %d finding(s) against the module matrix."
              % len(findings))
        return 1

    print("OK: the shipped matrix was driven in %d fresh interpreter(s) "
          "against a synthetic provider directory of %d module(s) plus one "
          "configured name that is not installed, and it tells the three "
          "states apart: "
          "%d imported module(s) describe themselves, %d installed module(s) "
          "nothing imported read `unknown` in every capability column rather "
          "than `no`, and a name pointing at nothing gets a row saying that "
          "rather than a row saying it does nothing."
          % (len(INSTALLS), len(PROVIDER_SOURCES),
             sum(1 for w in EXPECTED.values() if w.get("reads") == "yes"
                 or w.get("writes") == "yes"),
             sum(1 for w in EXPECTED.values() if w.get("reads") == "unknown"
                 and w.get("distribution") != "not installed")))
    print("    The case that carries this is `reader`: enabled, imported, "
          "registering a reading and no writer. That is the module the old "
          "sentence called 'installed and not enabled, so it was not "
          "imported' - true of nothing, and off by one (DP115). The socket "
          "column is asserted `yes` on a module nothing imported, which is "
          "what proves it is read off the file rather than asked of the "
          "registry.")
    print("    `murscope modules` was driven in the same interpreter and "
          "every module the matrix returned appears on the screen it printed: "
          "a correct table behind a command that prints something else is the "
          "same defect one layer out.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
