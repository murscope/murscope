"""Recognise the tool, then guess the filename.

Ledgers are not grown, they are planted. Measured across real projects,
the file a project writes about itself is almost always the file some
tool created for it - a management console, a scaffolding script, an
agent convention - so recognising the *tool* matches a whole class of
users at once, where guessing filenames matches one project at a time.

This table is the one place that knowledge lives. `ledger.LEDGER_SHAPES`
is **derived from it** rather than maintained beside it: M1 shipped a
fixed-path subset and the note it left for M2 was to reconcile the two
and not to grow a second list, because two lists of filenames drift
within one milestone and nobody notices until a ledger stops being read.

**A fingerprint is not the same as a ledger, and the difference matters
more than it looks.** Every row below identifies a project and the tool
that shaped it. Only some rows carry files worth *reading for state*:

* a `CLAUDE.md`, an `AGENTS.md`, a `.cursorrules` is a **brief for an
  agent** - instructions about how to work, not a statement of where the
  work stands. Parsing one for state reports the instructions as the
  project's condition, which is worse than reporting nothing;
* the design authority's own column calls these *candidates*, and a
  candidate is something to offer the user on the summary screen, not
  something to read behind their back. They are marked `offer` here.
  Nothing reads them until somebody chooses them.

That is the reconciliation between the design authority and M1's
narrower list: the authority decides what is recognised, M1's argument
decides what is read without being asked, and the summary screen is
where the two meet.
"""
from __future__ import annotations

import fnmatch
import os

# (tool, markers, ledgers, offers)
#
#   markers   files or directories whose presence names the tool
#   ledgers   read for state without being asked
#   offers    recognised, listed on the summary screen, never auto-read
FINGERPRINTS = (
    ("mgmt console",
     ("mgmt/MGMT.md", "mgmt/DECISIONS.md"),
     ("mgmt/MGMT.md", "mgmt/DECISIONS.md"),
     ()),
    ("project-init",
     ("tasks/PROGRESS.md", "tasks/TASKS.md", "BRIEF.md"),
     ("tasks/PROGRESS.md", "tasks/TASKS.md", "BRIEF.md",
      "PROGRESS.md", "TASKS.md"),
     ()),
    ("superpowers SDD",
     (".superpowers/sdd",),
     (),
     ()),
    ("Claude Code",
     ("CLAUDE.md", ".claude"),
     (),
     ("CLAUDE.md",)),
    ("agent convention",
     ("AGENTS.md",),
     (),
     ("AGENTS.md",)),
    ("Cursor",
     (".cursorrules", ".cursor/rules"),
     (),
     (".cursorrules",)),
    ("Windsurf or Copilot",
     (".windsurfrules", ".github/copilot-instructions.md"),
     (),
     (".windsurfrules", ".github/copilot-instructions.md")),
    ("task-master",
     (".taskmaster", "tasks.json"),
     (),
     ("tasks.json",)),
    ("spec-kit",
     (".specify", "specs"),
     (),
     ()),
    ("ADR convention",
     ("docs/adr", "design"),
     (),
     ()),
    ("plans directory",
     ("docs/plans", "plans"),
     (),
     ()),
    ("general habit",
     ("TODO.md", "ROADMAP.md", "STATUS.md", "CHANGELOG.md", "NOTES.md"),
     ("TODO.md", "ROADMAP.md", "STATUS.md", "NOTES.md"),
     ("CHANGELOG.md",)),
)

# Rows whose ledger is "the newest file in this directory" rather than a
# fixed path: (directory, filename pattern, descend). The design
# authority writes them with a `*`; they are resolved by a pruning walk
# rather than a glob, because Rule 6 refuses glob on anything but a
# module constant and a scanner points at directories it has never seen.
WILDCARD_LEDGERS = (
    (".superpowers/sdd", "progress.md", True),
    (".superpowers/sdd", "plan.md", True),
    ("specs", "*.md", False),
    ("docs/adr", "*.md", False),
    ("design", "ADR-*.md", False),
    ("docs/plans", "*.md", False),
    ("plans", "*.md", False),
)

# How deep a wildcard row is allowed to look, and how many files it may
# consider. A ledger directory with ten thousand files in it is not a
# ledger directory.
WILDCARD_MAX_DEPTH = 3
WILDCARD_MAX_FILES = 400


def _flatten(index):
    out = []
    seen = set()
    for row in FINGERPRINTS:
        for path in row[index]:
            if path not in seen:
                seen.add(path)
                out.append(path)
    return tuple(out)


# Read for state without being asked. `ledger.LEDGER_SHAPES` is this.
LEDGER_SHAPES = _flatten(2)
# Recognised and shown, never read until chosen.
OFFERED_SHAPES = _flatten(3)
# Every path that says "a tool made this a project".
MARKER_SHAPES = _flatten(1)


def tools(root):
    """Which tools left their mark on this directory, in table order.

    Existence checks on fixed paths only - no traversal, so this is cheap
    enough to run on every candidate the scan turns up.
    """
    found = []
    for tool, markers, _ledgers, _offers in FINGERPRINTS:
        for rel in markers:
            if (root / rel).exists():
                found.append(tool)
                break
    return found


def fixed_ledgers(root):
    """Ledger files that exist here, by fixed path."""
    return [rel for rel in LEDGER_SHAPES
            if (root / rel).is_file() and not (root / rel).is_symlink()]


def offered(root):
    """Files a tool planted that we recognise but will not read.

    These belong on the summary screen beside the project, so that a
    user whose only written record is a `CLAUDE.md` can point us at it
    deliberately. Until they do, it stays unread (the design authority's
    *candidate* column, read as an offer rather than a licence).
    """
    return [rel for rel in OFFERED_SHAPES
            if (root / rel).is_file() and not (root / rel).is_symlink()]


def wildcard_ledgers(root, sealed):
    """Ledgers named by a pattern: the newest match for each row.

    One pruning `os.walk` per candidate directory that actually exists.
    Rule 6 forbids `glob`/`rglob` on a caller-supplied path and is right
    to - a scanner walks directories nobody has vetted - so the pattern
    is matched against names the walk hands over.
    """
    found = []
    for rel_dir, pattern, descend in WILDCARD_LEDGERS:
        base = root / rel_dir
        if not base.is_dir() or base.is_symlink():
            continue
        base_str = str(base)
        best = None
        seen = 0
        for dirpath, dirnames, filenames in os.walk(base_str):
            dirnames[:] = sorted(
                name for name in dirnames
                if name not in sealed and not name.startswith("."))
            depth = dirpath[len(base_str):].count(os.sep)
            if not descend or depth >= WILDCARD_MAX_DEPTH:
                dirnames[:] = []
            for name in sorted(filenames):
                seen += 1
                if seen > WILDCARD_MAX_FILES:
                    break
                if not fnmatch.fnmatch(name, pattern):
                    continue
                full = os.path.join(dirpath, name)
                try:
                    stamp = os.stat(full).st_mtime
                except OSError:
                    continue
                if best is None or stamp > best[0]:
                    best = (stamp, os.path.relpath(full, str(root)))
            if seen > WILDCARD_MAX_FILES:
                break
        if best is not None and best[1] not in found:
            found.append(best[1])
    return found
