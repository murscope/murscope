"""Rule 14: the activity source reads mtime, never content.

The MVP adapter walks the user's own work tree, so the difference
between "when did this change" and "what does it say" looks academic
today. It stops being academic at M4, when the adapter that reads an
external AI tool's session directory arrives and the files in question
are transcripts of somebody's conversations. The boundary has to exist
before the thing it protects against does, or it will be written by
whoever is in a hurry that day.

Two halves, both structural:

  1. **No content read anywhere in the activity layer.** No `open()`, no
     `read_text()`, no `read_bytes()`, no `json.load`. The adapter is
     allowed `os.stat` and `os.walk` and that is the whole permitted
     vocabulary.
  2. **`last_touch` and its source path stay out of any outbound
     payload.** No provider may name them, and they may not appear in
     the whitelist a sensitive entry emits - a project marked sensitive
     exposes method only (Rule 7), and the path of the newest file in it
     is content, not method.

The second half is trivially satisfied today because nothing leaves this
machine (Rule 11, and there are no providers at all). It is checked now
anyway: the day a provider exists is the day this stops being free, and
a rule that arrives after the capability it governs arrives too late.

Fails when: the activity module opens or reads a file rather than
stat-ing it; or an activity key appears in SENSITIVE_ALLOWED_KEYS; or a
provider module names last_touch or the activity source path; or the
rendered payload carries that path.
"""
from __future__ import annotations

import ast
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
PACKAGE = REPO_ROOT / "murscope"
ACTIVITY = PACKAGE / "activity.py"
PROVIDERS = PACKAGE / "providers"
# The optional distribution's providers (DP88). An outbound payload is
# where naming the activity clock would matter most, so the one directory
# that can actually send must be inside this walk.
EXTRAS_ROOT = REPO_ROOT / "extras"
CONFIG = PACKAGE / "config.py"

# Everything that turns a stat into a read.
CONTENT_READERS = ("open", "read_text", "read_bytes", "read", "readlines",
                   "load", "loads")
# Names that must not cross an outbound boundary. Matched exactly, not
# as substrings: `last_activity` is M1's commit clock - a timestamp
# derived from git history, which is method and which a sensitive entry
# is allowed to emit. The first version of this list matched substrings
# and flagged it, which would have taught the next author that this
# check cries wolf.
LEAKY_NAMES = ("last_touch", "activity", "activity_source", "touch_path")


def detect(payload):
    """Findings for one activity-layer module: any content read."""
    src = payload.decode("utf-8", errors="replace")
    try:
        tree = ast.parse(src)
    except SyntaxError as exc:
        return ["cannot parse (%s)." % exc]

    findings = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        name = getattr(node.func, "attr", None) or getattr(node.func, "id", None)
        if name in CONTENT_READERS:
            findings.append(
                "%d: %s() in the activity layer. This layer may stat a file "
                "and may not read one - at M4 these files are somebody's "
                "conversations, and 'when did it change' is the only "
                "question it is allowed to ask." % (node.lineno, name))
    return findings


def check_whitelist():
    """No activity key may sit in what a sensitive entry emits (Rule 7)."""
    findings = []
    if not CONFIG.exists():
        return findings
    src = CONFIG.read_text(encoding="utf-8")
    tree = ast.parse(src)
    for node in ast.walk(tree):
        if not isinstance(node, ast.Assign):
            continue
        for target in node.targets:
            if not (isinstance(target, ast.Name)
                    and target.id == "SENSITIVE_ALLOWED_KEYS"):
                continue
            for sub in ast.walk(node.value):
                if not (isinstance(sub, ast.Constant)
                        and isinstance(sub.value, str)):
                    continue
                if sub.value in LEAKY_NAMES:
                    findings.append(
                        "murscope/config.py:%d: SENSITIVE_ALLOWED_KEYS carries "
                        "%r. A sensitive entry exposes method only, and the "
                        "path of the newest file in it is content."
                        % (sub.lineno, sub.value))
    return findings


def check_providers():
    """No provider may name the activity clock or its path."""
    findings = []
    candidates = sorted(PROVIDERS.glob("*.py")) if PROVIDERS.is_dir() else []
    if EXTRAS_ROOT.is_dir():
        candidates += sorted(path for path in EXTRAS_ROOT.rglob("*.py")
                             if path.parent.name == "providers")
    for path in candidates:
        src = path.read_text(encoding="utf-8")
        tree = ast.parse(src, filename=str(path))
        rel = path.relative_to(REPO_ROOT).as_posix()
        for node in ast.walk(tree):
            if isinstance(node, ast.Constant) and isinstance(node.value, str):
                if node.value in LEAKY_NAMES:
                    findings.append(
                        "%s:%d: a provider names %r. last_touch and its source "
                        "path may not enter an outbound payload."
                        % (rel, node.lineno, node.value))
            if isinstance(node, ast.Attribute) and node.attr in LEAKY_NAMES:
                findings.append(
                    "%s:%d: a provider reaches for .%s."
                    % (rel, node.lineno, node.attr))
    return findings


def check_board_payload():
    """The rendered payload must not carry the activity signal's path.

    Behavioural, because the two static halves could not see this: the
    whitelist governs a *sensitive* row, and the leak was on an ordinary
    one - `signals.activity.path` held a filename from inside the project
    and went into data.json in full. Rule 14 says the source path may not
    enter an outbound payload, and a board file is outbound the moment it
    is sent to anybody.
    """
    sys.path.insert(0, str(REPO_ROOT))
    try:
        from murscope import render  # noqa: PLC0415 - probing the real module
    except Exception as exc:  # pragma: no cover
        return ["cannot import murscope.render (%s: %s)"
                % (type(exc).__name__, exc)]
    # Through `build_document`, not through the helper it calls. The first
    # version probed `_without_activity_path` directly, and a reverse
    # verification then unwired the call site and the check stayed green:
    # a check aimed at a helper cannot see the helper stop being used.
    try:
        from murscope import config, i18n  # noqa: PLC0415 - probing for real
        settings = config.load_config(REPO_ROOT / "no-such-home")
        catalog, _problems = i18n.load("en")
    except Exception as exc:  # pragma: no cover
        return ["cannot build a probe payload (%s: %s)"
                % (type(exc).__name__, exc)]
    record = {"id": "probe", "signals": {"activity": {
        "quality": "ok", "signal": "activity", "age_days": 1.0,
        "path": "a-filename-inside-the-project.md"}}}
    document = render.build_document(
        [record], settings, "en", catalog, [], {})
    rendered = document["projects"][0]
    block = (rendered.get("signals") or {}).get("activity") or {}
    if "path" in block:
        return ["render does not strip the activity signal's source path; it "
                "reaches data.json, which Rule 14 forbids in its own words."]
    if block.get("age_days") != 1.0:
        return ["render dropped the activity age along with the path; the age "
                "is method and the board is meant to show it (DP22, DP23)."]
    return []


def main():
    bad = 0
    modules = 0
    if not ACTIVITY.exists():
        print("murscope/activity.py is missing; Rule 14 has nothing to "
              "protect and the activity clock is specified for M2.")
        print("FAILED: the activity layer does not exist.")
        return 1
    for path in (ACTIVITY,):
        modules += 1
        rel = path.relative_to(REPO_ROOT).as_posix()
        for finding in detect(path.read_bytes()):
            print("%s:%s" % (rel, finding))
            bad += 1
    for finding in check_whitelist() + check_providers() + check_board_payload():
        print(finding)
        bad += 1

    if bad:
        print("FAILED: %d Rule 14 violation(s)." % bad)
        return 1
    print("OK: %d activity module(s) stat and never read; no activity key in "
          "SENSITIVE_ALLOWED_KEYS; no provider names last_touch." % modules)
    return 0


if __name__ == "__main__":
    sys.exit(main())
