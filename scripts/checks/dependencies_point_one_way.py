"""Rule 16: dependencies point one way.

DP5 settled this at the architecture stage: the core imports no
provider, providers import the core, and a CI script scans the
direction. The script is the half that never got written. For the whole
of M0 the decision sat in the ledger with no rule and no check behind
it, which under Rule 1 is the definition of wall art - and the moment
the first provider lands, one convenient import from the core is all it
takes for the direction to be lost quietly and permanently.

Two facts are held here.

**The core does not name a provider.** Anything under murscope/ outside
murscope/providers/ may import the provider *package* - that is the
seam, and murscope/cli.py uses it - but may not import a provider
module. `from . import providers` is fine; `from .providers import
github` is not. The distinction matters because the package's __init__
imports only what configuration enabled, which is what keeps "the MVP
has no network path" true by construction rather than by discipline.

**A provider does not import a provider.** Sideways imports turn a set
of independent modules into a graph, and the first one makes the second
one cheap. This covers the providers that ship in the optional
`murscope-ai` distribution under `extras/` as well: they install into the
same directory, so they are one set at runtime whatever wheel each came
from. murscope/providers/__init__.py is exempt and is the only
exemption: it is the loader, importing enabled modules by name is its
entire job, and it is one small file a reviewer can read.

Passes on the facts today - `noop` ships in the base package and
`network` in the optional one, and nothing imports either except the
loader. It is never skipped: it reports how many
modules it inspected on each side of the line.

Fails when: a module under murscope/ outside murscope/providers/
imports a provider module, by absolute or relative path or through a
literal dynamic import; or a provider module imports another provider.
"""
from __future__ import annotations

import ast
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
PACKAGE = REPO_ROOT / "murscope"
PROVIDERS = PACKAGE / "providers"
# Provider modules that ship in the optional distribution (DP88). They
# install into the same directory as the base package's, so they are the
# same set for this rule's purposes.
EXTRAS_ROOT = REPO_ROOT / "extras"

PACKAGE_NAME = "murscope"
PROVIDERS_MODULE = "murscope.providers"
LOADER = "__init__.py"
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


def _literal_targets(tree):
    """Module names passed to a dynamic importer as a string literal."""
    found = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        name = dotted(node.func)
        if name not in DYNAMIC_IMPORTERS and not name.endswith("import_module"):
            continue
        if node.args and isinstance(node.args[0], ast.Constant) \
                and isinstance(node.args[0].value, str):
            found.append((node.lineno, node.args[0].value))
    return found


def detect(payload):
    """Findings for a core module: any import that names a provider.

    Pure: source in, list of findings out. The rule for a provider
    module is different - it may not import a *sibling* - and lives in
    detect_provider(), which needs to know which siblings exist.
    """
    source = payload.decode("utf-8", errors="replace")
    try:
        tree = ast.parse(source)
    except SyntaxError as exc:
        return ["cannot parse (%s)." % exc]

    findings = []
    advice = ("The core imports the provider package, never a provider: "
              "`from murscope import providers` and let configuration decide "
              "what gets imported (DP5).")
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.startswith(PROVIDERS_MODULE + "."):
                    findings.append("%d: imports the provider module '%s'. %s"
                                    % (node.lineno, alias.name, advice))
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            if node.level == 0:
                hit = (module == PROVIDERS_MODULE
                       or module.startswith(PROVIDERS_MODULE + "."))
                label = module
            else:
                hit = module == "providers" or module.startswith("providers.")
                label = "." * node.level + module
            if hit:
                findings.append(
                    "%d: `from %s import %s` reaches into the provider layer. %s"
                    % (node.lineno, label,
                       ", ".join(a.name for a in node.names), advice))
    for lineno, target in _literal_targets(tree):
        if target.startswith(PROVIDERS_MODULE + "."):
            findings.append("%d: dynamically imports the provider module '%s'. %s"
                            % (lineno, target, advice))
    return findings


def detect_provider(payload, stem, siblings):
    """Findings for one provider module: any import of another provider."""
    source = payload.decode("utf-8", errors="replace")
    try:
        tree = ast.parse(source)
    except SyntaxError as exc:
        return ["cannot parse (%s)." % exc]

    advice = ("Providers are independent of each other; shared code belongs "
              "in the core, where both can import it.")
    findings = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                tail = alias.name[len(PROVIDERS_MODULE) + 1:] \
                    if alias.name.startswith(PROVIDERS_MODULE + ".") else ""
                if tail and tail.split(".")[0] in siblings - {stem}:
                    findings.append("%d: imports sibling provider '%s'. %s"
                                    % (node.lineno, alias.name, advice))
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            targets = set()
            if node.level == 1 and not module:
                targets = {alias.name for alias in node.names}
            elif node.level == 1 and module:
                targets = {module.split(".")[0]}
            elif node.level == 0 and module.startswith(PROVIDERS_MODULE + "."):
                targets = {module[len(PROVIDERS_MODULE) + 1:].split(".")[0]}
            elif node.level == 2 and module.startswith("providers."):
                targets = {module.split(".")[1]}
            for target in sorted(targets & (siblings - {stem})):
                findings.append("%d: imports sibling provider '%s'. %s"
                                % (node.lineno, target, advice))
    for lineno, target in _literal_targets(tree):
        if target.startswith(PROVIDERS_MODULE + "."):
            name = target[len(PROVIDERS_MODULE) + 1:].split(".")[0]
            if name in siblings - {stem}:
                findings.append("%d: dynamically imports sibling provider '%s'. %s"
                                % (lineno, name, advice))
    return findings


def main():
    if not PACKAGE.is_dir():
        print("OK: murscope/ not present yet; nothing to inspect.")
        return 0

    core_files = []
    provider_files = []
    for path in sorted(PACKAGE.rglob("*.py")):
        if PROVIDERS in path.parents:
            provider_files.append(path)
        else:
            core_files.append(path)
    # Providers that ship in a separate distribution (DP88) are still
    # providers, and "a provider does not import a provider" is about the
    # set that lands in one directory at install time - not about which
    # wheel each arrived in. They were outside this walk for exactly as
    # long as it took to notice: a guard whose window does not contain the
    # thing it guards is the shape this milestone was warned about four
    # times.
    for path in sorted(EXTRAS_ROOT.rglob("*.py")):
        if path.parent.name == "providers":
            provider_files.append(path)

    siblings = {p.stem for p in provider_files if p.name != LOADER}
    bad = 0

    for path in core_files:
        rel = path.relative_to(REPO_ROOT).as_posix()
        for finding in detect(path.read_bytes()):
            print("%s:%s" % (rel, finding))
            bad += 1

    inspected_providers = 0
    for path in provider_files:
        if path.name == LOADER:
            # The loader is the seam. Importing enabled providers by name
            # is the whole reason it exists, and it is one short file.
            continue
        inspected_providers += 1
        rel = path.relative_to(REPO_ROOT).as_posix()
        for finding in detect_provider(path.read_bytes(), path.stem, siblings):
            print("%s:%s" % (rel, finding))
            bad += 1

    if bad:
        print("\nFAILED: %d dependency-direction violation(s)." % bad)
        return 1
    print("OK: %d core module(s) name no provider; %d provider module(s) - "
          "base package and extras distribution together - import no sibling; "
          "murscope/providers/__init__.py is the one loader."
          % (len(core_files), inspected_providers))
    return 0


if __name__ == "__main__":
    sys.exit(main())
