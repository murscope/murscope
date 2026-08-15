"""Locales, maintained independently, with no runtime key fallback (DP10).

Two rules meet here and both are kept.

Rule 8: a key that is missing from the locale being rendered produces a
loud [[MISSING:key]] marker on the page. It does not quietly resolve to
English. A silent fallback means a half-translated board looks finished,
and the person who could fix it is the only person who will never see
the gap.

Rule 3: every tracked file is English, so the Chinese locale is stored
with \\uXXXX escapes. json.loads decodes those natively, so the escaping
costs nothing at runtime and keeps the whole repository ASCII-greppable.
The locale directory is deliberately *not* exempted from Rule 3 - an
exemption is how a directory stops being checked at all.

Choosing which locale to render is a separate question from resolving a
key inside it. An unknown locale name falls back to English and says so
in the run's problem list; a missing key inside a known locale does not
fall back to anything.
"""
from __future__ import annotations

import json
from pathlib import Path

from ..guard import inside_root

LOCALES_DIR = Path(__file__).resolve().parent / "locales"
DEFAULT_LOCALE = "en"
MISSING_PREFIX = "[[MISSING:"


def available():
    """Locale names that ship with this build."""
    if not LOCALES_DIR.is_dir():
        return []
    return sorted(path.stem for path in LOCALES_DIR.glob("*.json"))


def resolve(name):
    """(locale, problems) - which locale to render, and why not the asked-for one."""
    names = available()
    if name in names:
        return name, []
    if DEFAULT_LOCALE in names:
        return DEFAULT_LOCALE, [
            "locale %r is not one of the locales this build ships (%s); "
            "rendering in %s." % (name, ", ".join(names) or "none", DEFAULT_LOCALE)]
    return name, ["no locale files are installed; every string on the board "
                  "will render as a missing-key marker."]


def load(name):
    """(catalog, problems). A catalog is flat: dotted key -> string.

    The locale name comes from the user's configuration, so it is confined
    to the locales directory before it is opened (Rule 17). `locale =
    "../../../../etc/passwd"` is a string a config file can hold, and
    appending it to a directory is how a reader leaves the tree it was
    meant to stay in.
    """
    path = LOCALES_DIR / ("%s.json" % name)
    if not inside_root(LOCALES_DIR, path):
        return {}, ["locale %r is not a name, it is a path; nothing was read."
                    % name]
    if not path.exists():
        return {}, ["locale file %s is missing." % path]
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        return {}, ["locale file %s: %s" % (path, exc)]
    if not isinstance(document, dict):
        return {}, ["locale file %s: the top level must be an object." % path]
    return {k: v for k, v in document.items() if isinstance(v, str)}, []


def translate(catalog, key):
    """The string for `key`, or a marker nobody can mistake for a string."""
    value = catalog.get(key)
    if isinstance(value, str) and value:
        return value
    return MISSING_PREFIX + key + "]]"
