"""Configuration and roster: what the user owns (DP4).

Three boundaries. The code is replaced wholesale on every upgrade and
owns nothing; `config.toml` and `roster.json` belong to the user and
live under MURSCOPE_HOME, where no upgrade ever reaches them; the board
is a rebuildable artifact beside them. The reference implementation kept
all three in one git repository, which works exactly until the user runs
`pip install --upgrade` once.

Two habits run through this module.

**A missing file is not an error.** A first run on a machine that has
never seen this tool has no config and no roster, and the right answer
is an empty configuration plus a sentence saying where the file would
go - not a stack trace, and not a silent default that leaves the user
guessing which file was read.

**A bad entry is named and kept.** One malformed roster entry must not
take the board down with it: the entry is marked bad, carries the key
and the reason, and still occupies a row. Aborting the run would hide
the twelve projects that were fine in order to complain about the one
that was not.
"""
from __future__ import annotations

import json
import os
import sys

from . import _toml
from .guard import murscope_home

CONFIG_NAME = "config.toml"
ROSTER_NAME = "roster.json"

# Directories a scan never enters (Rule 6). Dependency trees, build
# output, editor and tool caches, and the names people give to material
# they have already decided is private. Conservative on purpose: a name
# is added here when descending into it can only ever cost time or
# surprise the user, never when it is merely uninteresting.
DEFAULT_SEALED_DIRS = frozenset((
    ".git", ".hg", ".svn", ".bzr",
    "node_modules", "bower_components", "vendor", "Pods", "Carthage",
    ".venv", "venv", "env", "virtualenv", "site-packages", "__pycache__",
    ".mypy_cache", ".pytest_cache", ".ruff_cache", ".tox", ".nox", ".eggs",
    "target", "build", "dist", "out", "bin", "obj", "DerivedData",
    ".next", ".nuxt", ".svelte-kit", ".parcel-cache", ".turbo", ".sass-cache",
    ".gradle", ".terraform", ".serverless", ".cache", ".ccache",
    "coverage", "htmlcov", ".nyc_output",
    ".idea", ".vscode", ".fleet", ".DS_Store",
    "secrets", "sealed", "memory-mirror",
))

# What a roster entry marked `sensitive` is allowed to emit (Rule 7).
# This is a collection-time boundary, not a rendering filter: collect.py
# never opens a file inside a sensitive project, so the keys outside this
# set are not hidden on the way out - they are never read.
SENSITIVE_ALLOWED_KEYS = frozenset((
    "id", "name", "root", "sensitive", "tier", "recency_days",
    "last_activity", "trend", "uncommitted", "unpushed",
    "wip", "stash", "branches", "tag", "state", "signal_quality",
    "degraded", "collected_at", "problems",
    # Facts about how this row was produced, not about what is in the
    # project: which queue it joined and whether its directory overlaps
    # the write boundary (DP47). Method, which is what Rule 7 permits.
    "owner_queue", "owner_queue_source", "home_overlap",
    # The same number as recency_days, rounded once so the board and the
    # state sentence cannot disagree. Method, like the value it rounds.
    "recency_days_display",
))

# Withheld from a sensitive entry, and this is settled (DP68, ruled
# 2026-08-13). `last_subject` - the subject line of the newest commit -
# used to sit in the set above, so a full commit message reached the board
# for a sensitive entry with nothing injected and nothing gone wrong. An
# audit's example was a subject carrying a company name and an email
# address.
#
# The reason is one sentence and it decides the case: **marking a project
# sensitive means "the contents of this project do not go on the board",
# and a commit message is contents** - a commit subject being the line
# most likely to name a client, a figure or a person. Red line four says a
# sensitive entry exposes method only, and this is not method.
#
# Named separately from SENSITIVE_ALLOWED_KEYS rather than just left out
# of it, because absence proves nothing on its own: `selftest` asserts
# that every key here is off the whitelist and on no sensitive record, so
# putting one back turns the run red instead of turning it into a leak,
# and emptying this tuple turns the run red too.
SENSITIVE_WITHHELD_KEYS = ("last_subject",)

# Config keys this version understands, with the type each must carry.
# An unknown key is reported rather than ignored: a typo in a marker
# table is indistinguishable from a marker that quietly never applied.
CONFIG_SCHEMA = {
    "": {"locale": str},
    "collect": {"timeout_seconds": int, "trend_window_days": int,
                "walk_max_depth": int, "walk_max_files": int},
    "blockers": {"extra_markers": list, "disable_markers": list,
                 "owner_aliases": list, "packs": list},
    "scan": {"sealed_dirs": list},
    # `model` and `retry_after_seconds` arrive with the daily note.
    # `model` is passed to whichever adapter is enabled and each has its
    # own default, so an empty value is not a missing setting. The backoff
    # is clamped in `murscope.daily` rather than validated here, because
    # its ceiling is a rule about the retry and not about the file: an
    # unbounded backoff is a degraded result holding a day, wearing a
    # preference (DP49).
    "providers": {"enabled": list, "model": str, "retry_after_seconds": int},
    # DP18. "file" is a 0600 file under MURSCOPE_HOME and needs no
    # dependency; "keyring" is the system keychain and needs the extra.
    # There is no third value and no automatic fallback between the two:
    # a user who chose the keychain and silently got a file would have
    # been told nothing, which is DP49's shape one layer down.
    "keys": {"backend": str},
    # DP22: off unless the user says otherwise, and the default below is
    # the whole of that promise. DP23 keeps it from colouring the tier.
    "activity": {"enabled": bool, "source": str},
    # DP46: the trend cut points are the product's own, not the report's.
    # They live in one named place, they are overridable here, and the
    # board states them - an unexplained verdict about somebody's own
    # work is the opposite of what this tool is for. Ratios are whole
    # percents because the 3.9 fallback parser refuses floats on purpose.
    "trend": {"recent_days": int, "accelerating_percent": int,
              "slowing_percent": int, "min_commits": int},
    # DP125. `destination` is the scheme and host an alert would be
    # delivered to, and it is here rather than in the key store because
    # the core has to be able to print it on a consent screen and put it
    # in a fingerprint without knowing which provider it is talking to
    # (Rule 16). The delivery URL itself is a credential and lives in the
    # key store; the provider refuses to deliver if the two do not resolve
    # to the same place. Empty by default, which is what "outbound
    # alerting is off" means as a fact about a fresh install rather than
    # as a setting somebody has to find.
    "alerts": {"destination": str},
}

CONFIG_DEFAULTS = {
    "locale": "en",
    "collect": {"timeout_seconds": 15, "trend_window_days": 90,
                "walk_max_depth": 8, "walk_max_files": 20000},
    "blockers": {"extra_markers": [], "disable_markers": [],
                 "owner_aliases": [], "packs": []},
    "scan": {"sealed_dirs": []},
    "providers": {"enabled": [], "model": "",
                  "retry_after_seconds": 900},
    "keys": {"backend": "file"},
    "activity": {"enabled": False, "source": "worktree-mtime"},
    "trend": {"recent_days": 30, "accelerating_percent": 150,
              "slowing_percent": 50, "min_commits": 4},
    "alerts": {"destination": ""},
}

ENTRY_SCHEMA = {
    "id": str, "name": str, "root": str, "branch": str,
    "sensitive": bool, "ledgers": list, "note": dict,
}
REQUIRED_ENTRY_KEYS = ("id", "root")
ID_CHARS = set("abcdefghijklmnopqrstuvwxyz"
               "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-.")


def sealed_dirs(extra=()):
    """The resolved exclusion table: the built-in default plus the user's.

    Rule 6 asks for three things and this is the second of them - the
    default table exists, the user can extend it, and every walk prunes
    on the resolved answer before descending rather than filtering after.
    """
    names = set(DEFAULT_SEALED_DIRS)
    for name in extra or ():
        if isinstance(name, str) and name.strip():
            names.add(name.strip())
    return frozenset(names)


def _read_toml(text):
    """tomllib where it exists, the small fallback where it does not."""
    if sys.version_info >= (3, 11):
        import tomllib  # noqa: PLC0415 - 3.11+ only, cannot be a top import
        return tomllib.loads(text)
    return _toml.loads(text)


class Config(object):
    """Tool settings, plus every complaint raised while reading them."""

    def __init__(self, values, path, exists, problems):
        self.values = values
        self.path = path
        self.exists = exists
        self.problems = problems

    def __getitem__(self, key):
        return self.values[key]

    def section(self, name):
        return self.values.get(name, {})

    @property
    def locale(self):
        return self.values.get("locale", "en")


def _merged_defaults():
    merged = {}
    for key, value in CONFIG_DEFAULTS.items():
        merged[key] = dict(value) if isinstance(value, dict) else value
    return merged


def _check_section(section_name, table, values, problems):
    known = CONFIG_SCHEMA[section_name]
    label = "[%s]" % section_name if section_name else "top level"
    for key, value in sorted(table.items()):
        if isinstance(value, dict):
            continue
        if key not in known:
            problems.append(
                "%s: unknown key %r (this version understands %s). It was "
                "read and ignored - if it is a typo, nothing you configured "
                "there is in effect." % (label, key, ", ".join(sorted(known))))
            continue
        wanted = known[key]
        if not isinstance(value, wanted) or isinstance(value, bool) != (wanted is bool):
            problems.append("%s: %r must be %s, got %s."
                            % (label, key, wanted.__name__, type(value).__name__))
            continue
        if wanted is list:
            bad = [item for item in value if not isinstance(item, str)]
            if bad:
                problems.append("%s: %r must be a list of strings; %r is not."
                                % (label, key, bad[0]))
                continue
        values[key] = value


def load_config(home=None):
    """Read config.toml. A missing file is an empty configuration."""
    root = home or murscope_home()
    path = root / CONFIG_NAME
    values = _merged_defaults()
    problems = []

    if not path.exists():
        return Config(values, path, False, [
            "no %s yet; running on defaults. It would go at %s."
            % (CONFIG_NAME, path)])

    try:
        raw = path.read_text(encoding="utf-8")
    except OSError as exc:
        problems.append("%s: cannot be read (%s); running on defaults."
                        % (path, exc))
        return Config(values, path, True, problems)

    try:
        document = _read_toml(raw)
    except Exception as exc:  # tomllib and the fallback raise different types
        problems.append("%s: %s. The whole file was skipped and defaults "
                        "apply; nothing in it is in effect." % (path, exc))
        return Config(values, path, True, problems)

    top = {k: v for k, v in document.items() if not isinstance(v, dict)}
    _check_section("", top, values, problems)
    for name, table in sorted(document.items()):
        if not isinstance(table, dict):
            continue
        if name not in CONFIG_SCHEMA:
            problems.append("[%s]: unknown table (this version understands %s)."
                            % (name, ", ".join(sorted(n for n in CONFIG_SCHEMA if n))))
            continue
        section = dict(CONFIG_DEFAULTS[name])
        _check_section(name, table, section, problems)
        values[name] = section
    return Config(values, path, True, problems)


class Entry(object):
    """One roster entry: the user's claim about a project, validated.

    `problems` is the point of this object. A bad entry keeps its row and
    carries the reason, because a board that silently drops a project the
    user listed is lying about the size of the portfolio.
    """

    def __init__(self, index, raw):
        self.raw = raw if isinstance(raw, dict) else {}
        self.problems = []
        self.index = index
        self.id = self._string("id") or "entry-%d" % index
        self.name = self._string("name") or self.id
        self.root = self._string("root") or ""
        self.branch = self._string("branch") or ""
        self.sensitive = self._bool("sensitive")
        self.ledgers = self._string_list("ledgers")
        self.note = self._note()
        self._validate(raw)

    def _string(self, key):
        value = self.raw.get(key)
        if value is None:
            return ""
        if not isinstance(value, str):
            self.problems.append("key %r must be a string, got %s."
                                 % (key, type(value).__name__))
            return ""
        return value.strip()

    def _bool(self, key):
        value = self.raw.get(key)
        if value is None:
            return False
        if not isinstance(value, bool):
            self.problems.append("key %r must be true or false, got %r."
                                 % (key, value))
            return False
        return value

    def _string_list(self, key):
        value = self.raw.get(key)
        if value is None:
            return []
        if not isinstance(value, list) or any(not isinstance(v, str) for v in value):
            self.problems.append("key %r must be a list of strings." % key)
            return []
        return [v.strip() for v in value if v.strip()]

    def _note(self):
        value = self.raw.get("note")
        if value is None:
            return None
        if isinstance(value, str):
            return {"text": value.strip(), "since": None}
        if not isinstance(value, dict):
            self.problems.append(
                "key 'note' must be a string or an object with 'text' and an "
                "optional 'since' date, got %s." % type(value).__name__)
            return None
        text = value.get("text")
        if not isinstance(text, str) or not text.strip():
            self.problems.append("key 'note' has no readable 'text'.")
            return None
        since = value.get("since")
        if since is not None and not isinstance(since, str):
            self.problems.append("key 'note.since' must be an ISO date string.")
            since = None
        return {"text": text.strip(), "since": since}

    def _validate(self, raw):
        if not isinstance(raw, dict):
            self.problems.append("entry is %s, not an object."
                                 % type(raw).__name__)
            return
        for key in sorted(raw):
            if key not in ENTRY_SCHEMA:
                self.problems.append(
                    "unknown key %r (this version reads %s). It was ignored."
                    % (key, ", ".join(sorted(ENTRY_SCHEMA))))
        for key in REQUIRED_ENTRY_KEYS:
            if not getattr(self, key):
                self.problems.append("required key %r is missing or empty." % key)
        if self.id and any(c not in ID_CHARS for c in self.id):
            self.problems.append(
                "id %r contains characters outside letters, digits, dot, dash "
                "and underscore; it is used as an HTML anchor." % self.id)

    @property
    def path(self):
        return os.path.expanduser(self.root) if self.root else ""

    @property
    def usable(self):
        return bool(self.root) and not any(
            p.startswith("required key") for p in self.problems)


class Roster(object):
    """The projects the user pointed at, plus what was wrong with the list."""

    def __init__(self, entries, path, exists, problems):
        self.entries = entries
        self.path = path
        self.exists = exists
        self.problems = problems

    def __len__(self):
        return len(self.entries)

    def __iter__(self):
        return iter(self.entries)


def load_roster(home=None):
    """Read roster.json. A missing file is an empty roster, loudly."""
    root = home or murscope_home()
    path = root / ROSTER_NAME
    problems = []

    if not path.exists():
        return Roster([], path, False, [
            "no %s yet, so there is nothing to look at. It would go at %s, "
            "holding {\"projects\": [{\"id\": \"...\", \"root\": \"~/code/...\"}]}."
            % (ROSTER_NAME, path)])

    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        return Roster([], path, True, ["%s: %s" % (path, exc)])

    if not isinstance(document, dict):
        return Roster([], path, True, [
            "%s: the top level must be an object holding \"projects\"." % path])

    raw_entries = document.get("projects")
    if raw_entries is None:
        return Roster([], path, True, [
            "%s: no \"projects\" list." % path])
    if not isinstance(raw_entries, list):
        return Roster([], path, True, [
            "%s: \"projects\" must be a list, got %s."
            % (path, type(raw_entries).__name__)])

    for key in sorted(document):
        if key != "projects":
            problems.append("%s: unknown top-level key %r; it was ignored."
                            % (ROSTER_NAME, key))

    entries = []
    seen = {}
    for index, raw in enumerate(raw_entries):
        entry = Entry(index, raw)
        if entry.id in seen:
            entry.problems.append(
                "id %r is already used by entry %d; both rows are shown, but "
                "only one of them can own the anchor." % (entry.id, seen[entry.id]))
        else:
            seen[entry.id] = index
        entries.append(entry)
    return Roster(entries, path, True, problems)
