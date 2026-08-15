"""Rule 13, first half: a provider runs only when configuration names it.

Rule 13 is about data leaving the machine, and it is measured as two
separate things because they fail in two different ways. This is the
half that governs the loader: **being installed is not being enabled.**
The other half - that a base install has nothing to enable - lives in
`the_base_distribution_ships_no_provider_that_can_reach_out.py`, and it
is a different check because a green result here says nothing about it.

**What walks into this check (DP87).** Three instruments, and the second
is the one with teeth:

* the loader's own source, read as a parse tree, for the three shapes
  that would make configuration irrelevant;
* **three live `load()` calls**, run against the real loader and the real
  registry. An empty configuration must leave the registry empty; naming
  `noop` must put exactly `noop` in it; and three names that are not
  installed - a traversal string, a stdlib module, and one that simply
  does not exist - must all be refused with the registry unchanged. The
  static half alone would pass on a loader whose membership test compared
  against the wrong set, which is the shape this repository keeps finding;
* **a run of the shipped command**, `murscope daily --providers`, in a
  fresh interpreter with `noop` enabled. The two above ask whether a
  provider ran unasked. This asks the mirror question, and it was added
  because the answer was wrong for a stage: the table's accounting line
  called an enabled, imported module "installed and not enabled, so they
  were not imported", and miscounted by one saying it. "Being installed is
  not being enabled" is a sentence the user can only check by reading this
  output, so an output that misstates it is this rule failing, not a
  cosmetic defect (DP115).

The live half also asserts that `available()` found `noop` before it
concludes anything. A loader that resolved to an empty set would satisfy
"nothing was imported for a name nobody gave" by never being able to
import anything at all, and would report a green result for a broken
scan.

Three static shapes, each of which makes configuration irrelevant:

1. **a provider imported statically by the loader** - `from . import
   noop` runs the module the moment the loader is imported, which is
   every run;
2. **a dynamic import at module scope** - same consequence, reached a
   different way;
3. **a dynamic import inside a function with no membership test** - the
   string from `config.toml` reaching `import_module` unfiltered, which
   is an arbitrary-import hole with a written excuse. The membership test
   against what is on disk is what closes it: `pkgutil` yields plain
   module names, so a traversal string can never be in the answer.

Fails when: the loader imports a provider module statically; the loader
performs a dynamic import at module scope; the loader reaches
`import_module` without testing the requested name for membership; an
empty configuration leaves anything in the registry; a name that is not
installed is imported anyway; naming an installed provider fails to
register it; `available()` reports nothing at all; `murscope daily
--providers` exits non-zero with a provider enabled; or its output
describes an enabled, imported provider as not enabled, as not imported,
or does not mention it at all.
"""
from __future__ import annotations

import ast
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
LOADER = REPO_ROOT / "murscope" / "providers" / "__init__.py"

PROVIDERS_MODULE = "murscope.providers"
DYNAMIC_IMPORTERS = ("importlib.import_module", "__import__")


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


def _is_dynamic_import(node):
    if not isinstance(node, ast.Call):
        return False
    name = dotted(node.func)
    return name in DYNAMIC_IMPORTERS or name.endswith("import_module")


def _has_membership_test(node):
    """Does this function test something for membership in a set?

    Deliberately shallow. It asks whether the function that reaches
    `import_module` contains an `in` / `not in` comparison at all, not
    whether that comparison is the right one - a static check cannot
    establish the second, and claiming it would be claiming more than
    this executes. What establishes the second is the live half in
    `main()`, which asks the loader to import three names that are not
    installed and watches it refuse.
    """
    for sub in ast.walk(node):
        if isinstance(sub, ast.Compare):
            for op in sub.ops:
                if isinstance(op, (ast.In, ast.NotIn)):
                    return True
    return False


def detect(payload):
    """Findings for a loader: any path that imports a provider unasked."""
    source = payload.decode("utf-8", errors="replace")
    try:
        tree = ast.parse(source)
    except SyntaxError as exc:
        return ["cannot parse (%s)." % exc]

    findings = []
    advice = ("Configuration decides what is imported. A provider reached "
              "any other way runs on every run, which is what Rule 13 "
              "refuses.")

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.startswith(PROVIDERS_MODULE + "."):
                    findings.append(
                        "%d: statically imports the provider module '%s'. %s"
                        % (node.lineno, alias.name, advice))
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            names = [a.name for a in node.names]
            static = (
                (node.level == 0 and module.startswith(PROVIDERS_MODULE + "."))
                or (node.level == 1 and not module))
            if static and names:
                findings.append(
                    "%d: statically imports provider module(s) %s. %s"
                    % (node.lineno, ", ".join(repr(n) for n in names), advice))

    functions = [n for n in ast.walk(tree)
                 if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]
    inside = set()
    for function in functions:
        for sub in ast.walk(function):
            if _is_dynamic_import(sub):
                inside.add(sub.lineno)
                if not _has_membership_test(function):
                    findings.append(
                        "%d: reaches a dynamic import inside %s(), which tests "
                        "nothing for membership. The name arrives from "
                        "config.toml; without a membership test against what "
                        "is installed, that is an arbitrary import with a "
                        "written excuse." % (sub.lineno, function.name))
    for node in ast.walk(tree):
        if _is_dynamic_import(node) and node.lineno not in inside:
            findings.append(
                "%d: performs a dynamic import at module scope, so it runs "
                "when the loader is imported - which is every run, whatever "
                "configuration says." % node.lineno)
    return findings


def live_findings():
    """Run the real loader three ways. The half a parse tree cannot do."""
    sys.path.insert(0, str(REPO_ROOT))
    try:
        from murscope import providers, registry
    except Exception as exc:
        return ["the loader could not be imported (%s: %s), so nothing was "
                "exercised." % (type(exc).__name__, exc)], 0

    findings = []
    installed = providers.available()
    if not installed:
        return (["providers.available() reported no module at all. `noop` "
                 "ships with the base package, so an empty answer is a broken "
                 "scan - and every refusal below would then be satisfied by a "
                 "loader that can import nothing."], 0)
    if "noop" not in installed:
        findings.append(
            "providers.available() did not report 'noop' (%s). It is what "
            "proves the wiring; without it the positive case below cannot run."
            % ", ".join(installed))
        return findings, len(installed)

    registry.reset()
    loaded, problems = providers.load([])
    if loaded or registry.registered():
        findings.append(
            "an empty `enabled` list loaded %s and left %d provider(s) in the "
            "registry. Nothing may run unless configuration names it."
            % (loaded or "nothing", len(registry.registered())))

    registry.reset()
    refused = ["../../etc/passwd", "os", "definitely_not_installed"]
    loaded, problems = providers.load(refused)
    if loaded:
        findings.append(
            "the loader imported %s for name(s) that are not installed under "
            "murscope.providers. A name from config.toml that matches nothing "
            "on disk must be refused before it reaches import_module."
            % ", ".join(loaded))
    if registry.registered():
        findings.append(
            "%d provider(s) registered while loading names that are not "
            "installed." % len(registry.registered()))
    if len(problems) != len(refused):
        findings.append(
            "%d name(s) were refused and %d problem line(s) were reported. A "
            "refusal the user is not told about is a silent one."
            % (len(refused), len(problems)))

    registry.reset()
    loaded, problems = providers.load(["noop"])
    if loaded != ["noop"] or "noop" not in registry.registered():
        findings.append(
            "naming 'noop' in configuration loaded %r and registered %s. The "
            "positive case has to work, or the refusals above are satisfied by "
            "a loader that never imports anything."
            % (loaded, sorted(registry.registered())))
    registry.reset()
    findings.extend(reported_state_findings())
    return findings, len(installed)


def reported_state_findings():
    """The other direction of Rule 13: what the product *says* is enabled.

    The loader above is asked whether a provider ran unasked. This asks
    whether the command tells the truth about which ones did, and it exists
    because the answer was no for a stage. `murscope daily --providers`
    printed one accounting sentence covering everything without a row, and
    it read "installed and not enabled, so they were not imported" - so a
    reader who had enabled the contributions reader was told their enabled,
    imported module was neither, and the count was wrong by one. It sent
    nothing anywhere; a table that misreports which modules configuration
    turned on is still this rule's business, because "being installed is not
    being enabled" is a sentence a user can only check by reading this line.

    **Driven as a subprocess, and that is not a stylistic choice.** In this
    process the loader has already run three times above, so
    `murscope.providers.noop` is in `sys.modules`; importing it again
    returns the cached module without re-executing `register()`, and the
    probe would read an empty registry and conclude the table was silent
    about a module it had in fact described. A fresh interpreter is the only
    way to ask this question of the real command - and it is what a user
    runs anyway. `noop` is the instrument: it ships with the base package,
    it registers no note writer, and enabling it is exactly the case the old
    sentence got wrong.
    """
    import subprocess  # noqa: PLC0415 - only this probe runs the command
    import tempfile  # noqa: PLC0415 - same reason
    import os  # noqa: PLC0415 - same reason

    findings = []
    with tempfile.TemporaryDirectory() as home:
        (Path(home) / "config.toml").write_text(
            '[providers]\nenabled = ["noop"]\n', encoding="utf-8")
        result = subprocess.run(
            [sys.executable, "-m", "murscope.cli", "daily", "--providers"],
            cwd=str(REPO_ROOT), stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            env=dict(os.environ, MURSCOPE_HOME=home))
    text = result.stdout.decode("utf-8", errors="replace")
    if result.returncode != 0:
        return ["`murscope daily --providers` exited %d with 'noop' enabled, "
                "so what it reports about an enabled provider was not "
                "measured. Output: %s"
                % (result.returncode, text.strip()[:400])]

    if "noop" not in text:
        findings.append(
            "'noop' is enabled and imported and the provider table does not "
            "mention it at all. A module the user turned on and that has no "
            "row is owed a reason; silence is the version of this defect that "
            "cannot even be read as wrong.")
        return findings
    for line in text.splitlines():
        if "noop" in line and "not enabled" in line:
            findings.append(
                "the provider table calls 'noop' not enabled while "
                "configuration names it: %r. Whether a module was imported is "
                "a question for the registry, not an inference from which "
                "table it is missing from." % line.strip())
        if "noop" in line and "not imported" in line:
            findings.append(
                "the provider table calls 'noop' not imported while "
                "configuration names it and it registered: %r."
                % line.strip())
    return findings


def main():
    if not LOADER.exists():
        print("FAILED: %s is missing; there is no loader to inspect."
              % LOADER.relative_to(REPO_ROOT).as_posix())
        return 1

    bad = 0
    rel = LOADER.relative_to(REPO_ROOT).as_posix()
    for finding in detect(LOADER.read_bytes()):
        print("%s:%s" % (rel, finding))
        bad += 1

    live, installed = live_findings()
    for finding in live:
        print("live: %s" % finding)
        bad += 1

    if bad:
        print("\nFAILED: %d way(s) in which a provider could run without "
              "configuration naming it." % bad)
        return 1
    print("OK: the loader imports no provider statically and none at module "
          "scope; %d installed provider module(s) found; an empty `enabled` "
          "list registered nothing, three uninstalled names were refused with "
          "a problem line each, and naming 'noop' registered exactly it."
          % installed)
    return 0


if __name__ == "__main__":
    sys.exit(main())
