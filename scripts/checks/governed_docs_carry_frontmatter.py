"""Rule 4: governed docs carry frontmatter.

Every .md under design/ and templates/ must open with a
YAML frontmatter block carrying title, type, captured and status, and
`captured` must be an ISO date rather than a relative phrase. CLAUDE.md,
README.md, CONTRIBUTING.md and BRAND.md live at the repository root and
are exempt by construction.

Fails when: a .md file under a governed directory has no frontmatter
block, is missing one of the four keys, or writes `captured` as anything
other than YYYY-MM-DD.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
GOVERNED_DIRS = ("design", "templates")
REQUIRED_KEYS = ("title", "type", "captured", "status")
KEY_LINE = re.compile(r"^([A-Za-z_][A-Za-z0-9_-]*)\s*:\s*(.*)$")
ISO_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
PLACEHOLDER_DATE = "YYYY-MM-DD"


def frontmatter(text):
    if not text.startswith("---\n"):
        return None
    end = text.find("\n---", 4)
    if end == -1:
        return None
    values = {}
    for line in text[4:end].splitlines():
        m = KEY_LINE.match(line)
        if m:
            values[m.group(1)] = m.group(2).strip()
    return values


def detect(payload):
    """Findings for one governed markdown document."""
    text = payload.decode("utf-8", errors="replace")
    values = frontmatter(text)
    if values is None:
        return ["missing YAML frontmatter block."]
    missing = [k for k in REQUIRED_KEYS if k not in values]
    if missing:
        return ["frontmatter missing key(s): %s" % ", ".join(missing)]
    captured = values["captured"]
    if captured == PLACEHOLDER_DATE:
        return ["'captured: %s' is the template placeholder, not a date."
                % PLACEHOLDER_DATE]
    if not ISO_DATE.match(captured):
        return ["'captured: %s' is not an ISO date (YYYY-MM-DD)." % captured]
    return []


def main():
    bad = 0
    inspected = 0
    for directory in GOVERNED_DIRS:
        root = REPO_ROOT / directory
        if not root.is_dir():
            continue
        for path in sorted(root.rglob("*.md")):
            rel = path.relative_to(REPO_ROOT).as_posix()
            inspected += 1
            findings = detect(path.read_bytes())
            if rel == "templates/doc.md":
                # The template exists to show the shape, so it carries
                # the placeholder. This is the only path exemption, and
                # it covers the placeholder finding only.
                findings = [f for f in findings if PLACEHOLDER_DATE not in f]
            for finding in findings:
                print("%s: %s" % (rel, finding))
                bad += 1

    if bad:
        print("\nFAILED: %d governed doc(s) without proper frontmatter." % bad)
        return 1
    print("OK: %d governed doc(s) carry title / type / captured / status." % inspected)
    return 0


if __name__ == "__main__":
    sys.exit(main())
