"""Rule 8: i18n keys stay complete.

Locale files are maintained independently, with no runtime default
fallback: a missing key renders a loud [[MISSING:key]] marker so the gap
is visible instead of silently resolving to English. This check holds:

  1. At least two locale files exist once murscope/i18n/locales/ does.
  2. Their key sets match exactly, compared across every locale rather
     than against a designated source of truth.
  3. Every value is a non-empty string.
  4. The i18n module *returns* the [[MISSING: marker from its lookup,
     and offers no silent fallback of any shape.
  5. TRANSLATION_STATUS.md states the real key count per locale. Left
     unverified in the reference implementation, that number drifted from
     45 to 111 without anyone noticing - a hand-written number is a claim
     until something counts it.
  5b. Every locale file is pure ASCII on disk, with its non-English
     characters written as \\uXXXX escapes. TRANSLATION_STATUS.md has
     required that since the first locale landed and nothing checked it,
     which held for exactly as long as the only non-English locale was
     Chinese: Rule 3's scanner names CJK ranges, so a raw `zh` value was
     caught by a different rule for a different reason. `fr` is the first
     locale whose natural spelling is Latin, and a raw `\\u00e9` passes
     Rule 3 without comment - measured, on a French locale written
     unescaped: 322 non-ASCII bytes in a tracked file, both checks green.
     The third locale is what made this reachable, and the rule it
     violates is red line five.
  6. The summary screen's column heading is built from catalog keys, and
     those keys exist in every locale. `wizard._header` may hold its
     format template and nothing else in the way of string constants;
     every other string in it must be a key, passed to `translate`.

Passes on the facts while the locale directory does not exist (M0) and
becomes binding the moment it lands. It is never skipped.

M0 recorded a hole here and M1 closed it. The marker used to be matched
as a string present anywhere in the module, so a dead constant sitting
beside a live silent fallback passed both tests. Two structural checks
close it: the marker has to be reachable from a `return` - directly, or
through a module constant the return names - and a two-argument
`.get(key, default)` anywhere in the i18n module is refused outright,
because that second argument is a silent fallback whatever it is called.

Known open, recorded rather than rediscovered: a fallback reached by
catching KeyError and returning another catalog's value would pass. It
needs the lookup traced through exception flow, and no such code exists
here; the shapes that do exist are all refused.

Also known open, and the reason point 6 is anchored to one function
instead of written as a rule about the codebase: comparing key *sets*
across locales cannot see a user-facing string that never became a key
at all. The summary screen's heading was three such strings, printed in
English over rows the catalog had already answered in Chinese, and every
locale agreed with every other locale the whole time (DP83). The wide
version of this check - find English literals that ought to be keys -
needs a static reading of which string constants are rendered values
rather than format templates, log lines, paths or identifiers, and DP67
already priced that proxy at negative: Rule 12's scanner failed a README
link and a function named `fetch`. So the widening is done one surface
at a time, by lifting a heading into a function like `_header` and
adding it here, which costs three lines and has no false positive. The
terminal screen's remaining prose is English on purpose and is not
claimed by this check (DP84).

Fails when: a locale is missing a key another locale has; a value is
empty or not a string; the loud missing-key marker is absent from the
i18n module; a defaultValue-style fallback exists; TRANSLATION_STATUS.md
states a key count that does not match the file; a locale file holds a
raw non-ASCII byte instead of an escape; or the summary screen's heading
holds a hand-written word instead of a key every locale carries.
"""
from __future__ import annotations

import ast
import json
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
I18N_DIR = REPO_ROOT / "murscope" / "i18n"
LOCALES_DIR = I18N_DIR / "locales"
STATUS_DOC = I18N_DIR / "TRANSLATION_STATUS.md"
WIZARD = REPO_ROOT / "murscope" / "wizard.py"
HEADER_FUNCTION = "_header"
MISSING_MARKER = "[[MISSING:"
FALLBACK_SHAPES = (
    re.compile(r"defaultValue"),
    re.compile(r"default_value"),
    re.compile(r"FALLBACK_LOCALE"),
    re.compile(r"fallback_catalog"),
)


def _string_constants(tree):
    """Module-level names bound to a string literal."""
    found = {}
    for node in tree.body:
        if not isinstance(node, ast.Assign):
            continue
        value = node.value
        if isinstance(value, ast.Constant) and isinstance(value.value, str):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    found[target.id] = value.value
    return found


def _returns_marker(tree):
    """Is the loud marker reachable from a return, or only defined?"""
    constants = _string_constants(tree)
    for node in ast.walk(tree):
        if not isinstance(node, ast.Return) or node.value is None:
            continue
        for sub in ast.walk(node.value):
            if isinstance(sub, ast.Constant) and isinstance(sub.value, str):
                if MISSING_MARKER in sub.value:
                    return True
            elif isinstance(sub, ast.Name):
                if MISSING_MARKER in constants.get(sub.id, ""):
                    return True
    return False


def _silent_defaults(tree):
    """`.get(key, something)` - the second argument is a quiet fallback."""
    found = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        if getattr(node.func, "attr", None) != "get":
            continue
        if len(node.args) >= 2:
            found.append(node.lineno)
    return found


def detect(payload):
    """Findings for the i18n module source: a fallback, or a dead marker."""
    text = payload.decode("utf-8", errors="replace")
    findings = []
    if MISSING_MARKER not in text:
        findings.append("no %s marker; a missing key must render loudly, not "
                        "resolve to another locale." % MISSING_MARKER)
    for shape in FALLBACK_SHAPES:
        if shape.search(text):
            findings.append("runtime fallback '%s' present; locales are "
                            "maintained independently." % shape.pattern)
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return findings
    if MISSING_MARKER in text and not _returns_marker(tree):
        findings.append(
            "%s appears in the module but no return produces it. A marker "
            "defined and never returned is decoration sitting beside whatever "
            "the lookup really does." % MISSING_MARKER)
    for lineno in _silent_defaults(tree):
        findings.append(
            "%d: `.get(key, default)` - the second argument is a silent "
            "fallback, and a half-translated board that looks finished is "
            "exactly what Rule 8 exists to prevent." % lineno)
    return findings


def _translated_constants(func):
    """String constants inside `func` that are arguments to `translate`."""
    keys = set()
    for node in ast.walk(func):
        if not isinstance(node, ast.Call):
            continue
        if getattr(node.func, "attr", None) != "translate" and \
                getattr(node.func, "id", None) != "translate":
            continue
        for arg in node.args:
            if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                keys.add(arg.value)
    return keys


def header_keys(path, name=HEADER_FUNCTION):
    """(keys, findings) - the catalog keys the summary screen's heading names.

    Narrow on purpose, and the narrowness is the point: this reads one
    function and asks that every string constant in it is either the
    format template or a key handed to `translate`. A heading typed in
    English fails on the word itself, without a scanner that has to guess
    which English is user-facing.
    """
    findings = []
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
    except (OSError, SyntaxError) as exc:
        return set(), ["%s: could not be read (%s)." % (path.name, exc)]

    func = None
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name == name:
            func = node
    if func is None:
        return set(), [
            "%s: no module-level `%s`; the summary screen's heading is the "
            "one surface point 6 anchors on, and a heading inlined back into "
            "its caller leaves nothing holding it to the catalog."
            % (path.name, name)]

    keys = _translated_constants(func)
    docstring = ast.get_docstring(func, clean=False)
    for node in ast.walk(func):
        if not isinstance(node, ast.Constant) or not isinstance(node.value, str):
            continue
        value = node.value
        if value == docstring or "%" in value or value in keys:
            continue
        findings.append(
            "%s: `%s` holds the literal %r. A column heading is a rendered "
            "string, so it is a catalog key or it is a screen that answers "
            "in one language and labels in another." % (path.name, name, value))
    if not keys:
        findings.append(
            "%s: `%s` names no catalog key, so this point asserts nothing "
            "about it." % (path.name, name))
    return keys, findings


def flatten(doc, prefix=""):
    flat = {}
    for key, value in doc.items():
        path = "%s.%s" % (prefix, key) if prefix else key
        if isinstance(value, dict):
            flat.update(flatten(value, path))
        else:
            flat[path] = value
    return flat


def main():
    if not LOCALES_DIR.is_dir():
        print("OK: murscope/i18n/locales/ not present yet; the rule binds the "
              "moment the first locale file lands.")
        return 0

    paths = sorted(LOCALES_DIR.glob("*.json"))
    if len(paths) < 2:
        print("FAILED: %d locale file(s) in murscope/i18n/locales/; Rule 8 "
              "compares locales against each other and needs at least two."
              % len(paths))
        return 1

    bad = 0
    data = {}
    for path in paths:
        try:
            data[path.stem] = flatten(json.loads(path.read_text(encoding="utf-8")))
        except ValueError as exc:
            print("murscope/i18n/locales/%s: invalid JSON (%s)." % (path.name, exc))
            bad += 1
        raw = sum(1 for byte in path.read_bytes() if byte > 127)
        if raw:
            print("murscope/i18n/locales/%s: %d raw non-ASCII byte(s). Values "
                  "are written as \\uXXXX escapes - json.loads decodes them "
                  "natively, so it costs nothing at runtime and keeps the "
                  "repository greppable in ASCII (red line five). Rule 3's "
                  "scanner names CJK and emoji ranges and will not catch a "
                  "French accent, which is why this is counted here."
                  % (path.name, raw))
            bad += 1
    if bad:
        print("\nFAILED: %d i18n problem(s)." % bad)
        return 1

    all_keys = set()
    for keys in data.values():
        all_keys |= set(keys)
    for locale in sorted(data):
        for key in sorted(all_keys - set(data[locale])):
            print("%s.json: missing key: %s" % (locale, key))
            bad += 1
        for key, value in sorted(data[locale].items()):
            if not isinstance(value, str) or not value.strip():
                print("%s.json: empty or non-string value: %s" % (locale, key))
                bad += 1

    module_text = "\n".join(
        p.read_text(encoding="utf-8") for p in sorted(I18N_DIR.rglob("*.py"))
    )
    for finding in detect(module_text.encode("utf-8")):
        print("murscope/i18n/: %s" % finding)
        bad += 1

    heading, heading_findings = header_keys(WIZARD)
    for finding in heading_findings:
        print("murscope/%s" % finding)
        bad += 1
    for locale in sorted(data):
        for key in sorted(heading - set(data[locale])):
            print("%s.json: the summary screen's heading names %s and this "
                  "locale has no such key, so the column would render as a "
                  "%s%s]] marker." % (locale, key, MISSING_MARKER, key))
            bad += 1

    if not STATUS_DOC.exists():
        print("murscope/i18n/TRANSLATION_STATUS.md: missing; the key count has "
              "to be written down somewhere a check can read it.")
        bad += 1
    else:
        status = STATUS_DOC.read_text(encoding="utf-8")
        for locale in sorted(data):
            row = re.search(r"^\|\s*%s\b[^|]*\|\s*(\d+)\s*\|" % re.escape(locale),
                            status, re.MULTILINE)
            if not row:
                print("TRANSLATION_STATUS.md: no key-count row for '%s'." % locale)
                bad += 1
            elif int(row.group(1)) != len(data[locale]):
                print("TRANSLATION_STATUS.md: says %s has %s key(s); the file has %d."
                      % (locale, row.group(1), len(data[locale])))
                bad += 1

    if bad:
        print("\nFAILED: %d i18n problem(s)." % bad)
        return 1
    print("OK: %d key(s) present and non-empty in %d locale(s) (%s), all of "
          "them pure ASCII on disk, loud missing-key marker in place, "
          "TRANSLATION_STATUS.md states the real counts, and the summary "
          "screen's heading is %d catalog key(s) (%s) rather than English."
          % (len(all_keys), len(data), ", ".join(sorted(data)),
             len(heading), ", ".join(sorted(heading))))
    return 0


if __name__ == "__main__":
    sys.exit(main())
