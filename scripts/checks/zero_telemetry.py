"""Rule 12: zero telemetry.

Scans every tracked text file for analytics, crash-reporting,
version-phone-home and usage-beacon shapes. The patterns match call
sites and endpoint hosts rather than the English word, so README.md and
CONTRIBUTING.md can state the promise in prose without tripping the
check that enforces it - a rule whose enforcement forbids describing the
rule would get its exemption list widened until it meant nothing.

The scan covers the whole repository, not just the core: a beacon in the
dashboard template or in a CI workflow would leak just as well as one in
the collector. Matching is case-insensitive, because a crash reporter's
initializer is the same beacon whichever way its vendor capitalises it.

The vendor patterns are not enough on their own. The M2 deliverable is a
static HTML dashboard, so the shape telemetry would actually take in
this repository is a browser request - the fetch API, XMLHttpRequest, a
socket constructor, an image whose src is an http URL. All of those sat
in a tracked .html file on a fully green gate, because the check knew
about Python SDKs and named vendors. They are matched now, everywhere,
since a beacon is no more welcome in a Python file than in a template.

Exempt: this script, which names the forbidden shapes.

Fails when: any tracked, non-exempt file contains an analytics or
crash-reporting call site, a known beacon endpoint, or a phone-home
function shape.
"""
from __future__ import annotations

import os
import re
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent

FORBIDDEN_SHAPES = [
    ("Google Analytics tag", r"\bgtag\s*\("),
    ("Google Analytics legacy", r"\bga\s*\(\s*['\"]send['\"]"),
    ("Google Analytics loader", r"dataLayer\s*\.\s*push\s*\("),
    ("Segment / analytics client", r"\banalytics\s*\.\s*(track|identify|page|group|alias)\s*\("),
    ("Mixpanel", r"\bmixpanel\s*\.\s*\w+\s*\("),
    ("PostHog", r"\bposthog\s*\.\s*\w+\s*\("),
    ("Amplitude", r"\bamplitude\s*\.\s*\w+\s*\("),
    ("Sentry", r"\b[Ss]entry(_sdk)?\s*\.\s*init\s*\("),
    ("Bugsnag", r"\b[Bb]ugsnag\s*\.\s*\w+\s*\("),
    ("Crash reporting", r"\b(crashlytics|rollbar|airbrake|raygun)\b"),
    ("Usage beacon", r"\b(send|post|report|emit|log)_?(telemetry|usage|metrics|beacon|analytics)\s*\("),
    ("Phone home", r"\b(phone_home|check_for_updates|version_ping|report_install)\s*\("),
    ("Beacon API", r"navigator\s*\.\s*sendBeacon\s*\("),
    # The M2 deliverable is an HTML dashboard, so the shape telemetry
    # would actually take here is a browser request, not a Python
    # vendor SDK. All four of these passed a green gate.
    # `fetch(` alone reddened a plain Python function named `fetch` - an
    # audit found it, and by this file's own argument a check that cries
    # wolf gets deleted. So the browser API has to look like the browser
    # API: a URL, a scheme-relative address, or `window.fetch`.
    ("Browser request API",
     r"\bwindow\s*\.\s*fetch\s*\(|\bfetch\s*\(\s*[\"'`](https?:)?//"),
    ("Browser request API", r"\bnew\s+XMLHttpRequest\b"),
    ("Browser socket", r"\bnew\s+(WebSocket|EventSource)\s*\("),
    # Same treatment: an image object is only a beacon once something
    # remote is assigned to it, and the assignment pattern below catches
    # that. `new Image(` on its own is how any page sizes a local asset.
    ("Image beacon",
     r"\bnew\s+Image\s*\([^)]{0,80}\)\s*\.\s*src\s*=\s*[\"'`]?\s*https?://"),
    ("Remote asset assignment", r"\.\s*(src|href|action)\s*=\s*[\"'`]?\s*https?://"),
    # The plainest beacon there is, and the pattern above did not match
    # it: that one requires a dot before the attribute, which is the
    # shape of a JavaScript property assignment. An HTML attribute has no
    # dot, so `<img src="https://...">` walked through - and this
    # product's deliverable is an 18KB HTML page shipped inside the
    # wheel, so one remote <script src> in the template would reach every
    # user with the gate green. Anchored inside a tag so that prose and
    # markdown links do not trip it.
    # Only tags the browser fetches on its own. `<a href="https://...">` is
    # a hyperlink a reader chooses to follow, and an audit was right that
    # reddening an ordinary documentation link in README is how a check
    # gets deleted - what this line publishes has links in it.
    ("Remote asset fetched by markup",
     r"<\s*(img|script|iframe|embed|source|track|audio|video|object|link|form)"
     r"\b[^>]{0,300}?\b(src|href|action|data)\s*=\s*[\"']?\s*https?://"),
    # Three more shapes an audit walked through. The first two are why the
    # markup pattern alone was not enough: `detect()` reads line by line,
    # and an attribute wrapped onto the next line puts the URL out of
    # reach of any single-line regex. The third needs no attribute at all.
    ("Remote asset in CSS", r"url\(\s*[\"']?\s*https?://"),
    ("Remote CSS import", r"@import\s+[\"']?\s*https?://"),
    ("Meta refresh to a remote address",
     r"http-equiv\s*=\s*[\"']?refresh[^>]{0,200}?url\s*=\s*https?://"),
    ("HTTP client library", r"\baxios\s*\.\s*\w+\s*\("),
    ("HTTP client library", r"\$\s*\.\s*(ajax|getJSON|post)\s*\("),
    ("Analytics endpoint", r"(google-analytics\.com|googletagmanager\.com|analytics\.google\.com"
                           r"|segment\.(io|com)/v1|api\.mixpanel\.com|app\.posthog\.com"
                           r"|api\.amplitude\.com|sentry\.io/api|plausible\.io/api|matomo\.php)"),
]
# Case-insensitive: Rollbar.init(...) and Crashlytics.log(...) are the
# same beacon as their lowercase spellings, and a check that only reads
# one casing is a check an autocomplete can walk past.
COMPILED = [(label, re.compile(pattern, re.IGNORECASE)) for label, pattern in FORBIDDEN_SHAPES]

SKIP_SUFFIXES = {
    ".png", ".jpg", ".jpeg", ".gif", ".webp", ".pdf", ".zip", ".gz",
    ".woff", ".woff2", ".ttf", ".eot", ".ico", ".mp3", ".mp4", ".wav",
}

EXEMPT_PATHS = {
    "scripts/checks/zero_telemetry.py",
}


def scanned_files():
    env = dict(os.environ)
    env["GIT_OPTIONAL_LOCKS"] = "0"
    out = subprocess.check_output(
        ["git", "ls-files", "-z", "--cached", "--others", "--exclude-standard"],
        cwd=str(REPO_ROOT),
        env=env,
    ).decode("utf-8")
    seen = set()
    paths = []
    for rel in out.split("\0"):
        if rel and rel not in seen:
            seen.add(rel)
            paths.append(rel)
    return paths


MULTILINE_SHAPES = ("Remote asset fetched by markup", "Remote asset in CSS",
                    "Remote CSS import", "Meta refresh to a remote address")


def detect(payload):
    """Findings for one file's contents. Pure: bytes in, findings out."""
    text = payload.decode("utf-8", errors="replace")
    findings = []
    seen = set()
    for lineno, line in enumerate(text.splitlines(), start=1):
        for label, regex in COMPILED:
            if regex.search(line):
                findings.append("%d: %s: %s" % (lineno, label, line.strip()[:120]))
                seen.add(label)
                break

    # A second pass over the whole text, because a line-by-line scan
    # cannot see an attribute that was wrapped onto the next line - and an
    # audit put a one-pixel beacon through by doing exactly that. The
    # deliverable is an 18KB HTML page shipped inside the wheel, so a
    # markup shape that only matches when the author keeps it on one line
    # is not a check, it is a formatting preference.
    flat = " ".join(text.split())
    for label, regex in COMPILED:
        if label not in MULTILINE_SHAPES or label in seen:
            continue
        match = regex.search(flat)
        if match:
            findings.append(
                "across lines: %s: %s"
                % (label, flat[max(0, match.start() - 20):match.end() + 40]))
    return findings


def main():
    bad = 0
    inspected = 0
    for rel in scanned_files():
        if rel in EXEMPT_PATHS:
            continue
        path = REPO_ROOT / rel
        if path.suffix.lower() in SKIP_SUFFIXES or not path.is_file():
            continue
        try:
            payload = path.read_bytes()
        except OSError:
            continue
        inspected += 1
        for finding in detect(payload):
            print("%s:%s" % (rel, finding))
            bad += 1

    if bad:
        print("\nFAILED: %d telemetry shape(s) found." % bad)
        print("Rule 12 is a promise in README.md; it has no exceptions.")
        return 1
    print("OK: %d tracked file(s) inspected, no analytics, crash reporting, "
          "phone-home or usage beacon." % inspected)
    return 0


if __name__ == "__main__":
    sys.exit(main())
