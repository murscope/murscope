"""Marker vocabulary in three layers (DP19).

    default packs   markers/<locale>.json, shipped, enabled by locale
    extra_markers   what the user's team actually writes
    disable_markers the important one

The third layer is the important one and it is worth saying why. A false
positive here is worse than a miss: it sends someone to a project that is
fine, and after the second time they stop believing the column. Somebody
whose writing is full of "awaiting" has to be able to switch that word
off in one line of config, today, not wait for a release.

Owner aliases come from configuration only and default to empty. The
reference implementation hard-codes five, including a real name and a
real handle - the single hard-coded human identity in that collector -
and DP19 forbids any real person's name in the shipped package. The
feature still works without them: a marker like "needs decision" names
the owner by meaning rather than by spelling their name.

Which packs are enabled: the active locale's, plus English always.
The design authority says "enabled by locale", and taken literally a
Chinese user would stop matching `BLOCKED:` - a string that turns up in
ledgers of every language because it comes from the tooling, not from
the prose.
English is therefore always on, and `blockers.packs` overrides the whole
decision for anyone who disagrees.
"""
from __future__ import annotations

import json
from pathlib import Path

from ..guard import inside_root

PACKS_DIR = Path(__file__).resolve().parent
ALWAYS_ON = "en"

# A marker this short and this common is not a declaration, it is a
# word. Two-character CJK markers are words; four-character ASCII ones
# are the floor below which "on" and "wip" start matching sentences.
MIN_ASCII_MARKER = 4
STOP_WORDS = frozenset((
    "the", "and", "but", "for", "with", "this", "that", "then", "than",
    "from", "into", "over", "when", "what", "which", "will", "would",
    "have", "has", "had", "not", "yes", "no", "todo", "done", "next",
    "note", "notes", "task", "tasks", "item", "items", "work", "state",
))


class Vocabulary(object):
    """The resolved marker set, and a record of where each layer came from.

    `layers` exists for `murscope status --explain`. Once the vocabulary
    is editable, the user needs to see what it resolved to; without that,
    configurable becomes breakable.
    """

    def __init__(self, markers, owner_markers, aliases, layers, problems):
        self.markers = markers
        self.owner_markers = owner_markers
        self.aliases = aliases
        self.layers = layers
        self.problems = problems

    def describe(self):
        return {
            "markers": list(self.markers),
            "owner_markers": list(self.owner_markers),
            "aliases": list(self.aliases),
            "layers": self.layers,
            "problems": list(self.problems),
        }


def available():
    """Locale names with a default pack in this build."""
    if not PACKS_DIR.is_dir():
        return []
    return sorted(path.stem for path in PACKS_DIR.glob("*.json"))


def load_pack(name):
    """(markers, owner_markers, problems) for one shipped pack.

    `blockers.packs` is user configuration, so the name is confined to the
    packs directory before it is opened (Rule 17) - a pack name that is
    really a path would read a file this package was never meant to open.
    """
    path = PACKS_DIR / ("%s.json" % name)
    if not inside_root(PACKS_DIR, path):
        return [], [], ["marker pack %r is not a name, it is a path; nothing "
                        "was read." % name]
    if not path.exists():
        return [], [], ["marker pack %r is not one of the packs this build "
                        "ships (%s)." % (name, ", ".join(available()) or "none")]
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        return [], [], ["marker pack %s: %s" % (path.name, exc)]
    markers = [m for m in document.get("markers", []) if isinstance(m, str)]
    owners = [m for m in document.get("owner_markers", []) if isinstance(m, str)]
    return markers, owners, marker_problems(markers, "pack %s" % name)


def marker_problems(markers, where="markers"):
    """Findings for a marker list that cannot be matched precisely.

    Shared deliberately between the shipped packs, the user's
    `extra_markers`, and Rule 10's check. The same predicate that keeps a
    default pack honest is the one that tells a user their new marker
    will match half their prose - and a user who learns that at the
    moment they write it never files the bug.
    """
    findings = []
    seen = set()
    for raw in markers:
        if not isinstance(raw, str):
            findings.append("%s: %r is not a string." % (where, raw))
            continue
        marker = raw.strip().lower()
        if not marker:
            findings.append("%s: an empty marker matches the start of every "
                            "line." % where)
            continue
        if marker in seen:
            findings.append("%s: %r is listed twice." % (where, marker))
            continue
        seen.add(marker)
        if marker.isascii() and len(marker) < MIN_ASCII_MARKER:
            findings.append(
                "%s: %r is %d characters of ASCII; below %d a marker starts "
                "matching ordinary words rather than declarations."
                % (where, marker, len(marker), MIN_ASCII_MARKER))
        if marker in STOP_WORDS:
            findings.append(
                "%s: %r is a common word. It would report a blocker on every "
                "line that happens to start with it, and a false positive "
                "here costs more than a miss (DP19)." % (where, marker))
    return findings


def normalise(markers):
    """Lowercase, trimmed, de-duplicated, longest first.

    Longest first matters: "needs decision" and "blocked" can both open a
    line, and matching the longer one first is what lets the owner subset
    be recognised rather than swallowed by a shorter generic marker.
    """
    out = []
    seen = set()
    for raw in markers:
        if not isinstance(raw, str):
            continue
        marker = raw.strip().lower()
        if marker and marker not in seen:
            seen.add(marker)
            out.append(marker)
    return sorted(out, key=lambda m: (-len(m), m))


def enabled_packs(locale, override=()):
    """Which packs apply: the override, or this locale plus English."""
    if override:
        return [name for name in override if isinstance(name, str)]
    names = [locale] if locale in available() else []
    if ALWAYS_ON not in names and ALWAYS_ON in available():
        names.append(ALWAYS_ON)
    return names


def resolve(locale, settings=None):
    """Build the vocabulary from the three layers, loudly."""
    settings = settings or {}
    packs = enabled_packs(locale, settings.get("packs", ()))
    problems = []
    base = []
    owners = []
    layers = {"packs": packs, "from_packs": [], "extra": [], "disabled": [],
              "ignored_disable": []}

    for name in packs:
        pack_markers, pack_owners, pack_problems = load_pack(name)
        problems.extend(pack_problems)
        base.extend(pack_markers)
        owners.extend(pack_owners)
    layers["from_packs"] = normalise(base)

    extra = [m for m in settings.get("extra_markers", []) if isinstance(m, str)]
    problems.extend(marker_problems(extra, "blockers.extra_markers"))
    layers["extra"] = normalise(extra)

    disable = {m.strip().lower() for m in settings.get("disable_markers", [])
               if isinstance(m, str) and m.strip()}
    resolved = [m for m in normalise(base + extra) if m not in disable]
    layers["disabled"] = sorted(disable & set(normalise(base + extra)))
    layers["ignored_disable"] = sorted(disable - set(normalise(base + extra)))
    for name in layers["ignored_disable"]:
        problems.append(
            "blockers.disable_markers lists %r, which is not in the resolved "
            "vocabulary; nothing was switched off by it." % name)

    aliases = normalise(
        m for m in settings.get("owner_aliases", []) if isinstance(m, str))
    owner_set = [m for m in normalise(owners) if m not in disable]
    return Vocabulary(resolved, owner_set, aliases, layers, problems)
