"""Read-only signal collection over the roster.

Thirteen signals, ranked by how universal they are rather than by how
interesting they are. That ranking is the product decision: measured on
the reference implementation an explicit "blocked" marker fires on one
project in thirteen, so a board that leans on markers is empty for a
stranger. Signals 3 to 6 - uncommitted changes, unpushed commits, a
WIP-shaped last commit, a stash - exist in every git repository, need no
convention and no writing habit, and they are where coverage comes from.

Every git invocation satisfies both halves of Rule 5 (DP31): an
allowlisted read-only subcommand, and GIT_OPTIONAL_LOCKS=0 in the
environment handed to that specific call. Measured on a real repository,
`git status` rewrites .git/index without that variable and leaves it
alone with it, so the subcommand allowlist alone would license a write
into a monitored project.

Each git call spells out its own argument list. Factoring them into one
helper that takes `args` would read better and would make the invocation
unverifiable - Rule 5's check refuses a subprocess call whose argv it
cannot read statically, and it is right to. The repetition is the proof.

Degradation is honest. A signal that timed out, failed, or was skipped
says so and is listed in `degraded`; it never renders as a zero. "We
looked and found none" and "we could not look" are different facts and
the board must be able to tell them apart.
"""
from __future__ import annotations

import os
import re
import subprocess
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

from . import activity, ledger, markers
from .config import SENSITIVE_ALLOWED_KEYS, sealed_dirs

# Rule 5, half two. Built once, handed to every git call below.
GIT_ENV = dict(os.environ, GIT_OPTIONAL_LOCKS="0")

WIP_MARKERS = ("wip", "fixup!", "squash!", "tmp", "temp:", "amend!")
TODO_LINE = re.compile(r"^[\s>*+-]*-\s\[\s\]\s")
CODE_MARKER = re.compile(r"\b(TODO|FIXME|XXX|HACK)\b")
CODE_MARKER_KINDS = ("TODO", "FIXME", "XXX", "HACK")

# Files worth reading for signals 8 and 9. Everything else in the tree
# contributes its mtime to signal 10 and nothing more.
MARKDOWN_SUFFIXES = frozenset((".md", ".markdown", ".mdx"))
SOURCE_SUFFIXES = frozenset((
    ".py", ".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs", ".rb", ".go",
    ".rs", ".java", ".kt", ".swift", ".m", ".mm", ".c", ".h", ".cc",
    ".cpp", ".hpp", ".cs", ".php", ".sh", ".bash", ".zsh", ".fish",
    ".sql", ".vue", ".svelte", ".scala", ".ex", ".exs", ".lua", ".pl",
    ".r", ".jl", ".dart", ".clj", ".hs", ".ml", ".zig", ".nim",
))
READ_MAX_BYTES = 512 * 1024

# Signal 11: what the project is built out of, from files that only
# exist when a toolchain put them there.
STACK_MARKERS = (
    ("python", ("pyproject.toml", "setup.py", "setup.cfg", "requirements.txt",
                "Pipfile", "environment.yml")),
    ("node", ("package.json",)),
    ("rust", ("Cargo.toml",)),
    ("go", ("go.mod",)),
    ("ruby", ("Gemfile",)),
    ("java", ("pom.xml", "build.gradle", "build.gradle.kts")),
    ("swift", ("Package.swift",)),
    ("php", ("composer.json",)),
    ("elixir", ("mix.exs",)),
    ("dotnet", ("global.json",)),
    ("docker", ("Dockerfile", "compose.yaml", "docker-compose.yml")),
)
# Signal 12: toy -> documented -> tested -> continuously built.
README_NAMES = ("README.md", "README.rst", "README.txt", "README")
LICENSE_NAMES = ("LICENSE", "LICENSE.md", "LICENSE.txt", "COPYING", "LICENCE")
CI_PATHS = (".github/workflows", ".gitlab-ci.yml", ".circleci/config.yml",
            "azure-pipelines.yml", ".travis.yml", "Jenkinsfile",
            ".drone.yml", ".woodpecker.yml")
TEST_PATHS = ("tests", "test", "spec", "__tests__", "src/test")

TIER_ACTIVE_DAYS = 2
TIER_WARM_DAYS = 7
TIER_QUIET_DAYS = 21

# Signal 2. The window is 90 days; the split compares the
# most recent 30 against the 60 before it, rate-normalised, because a
# raw count would call every project with a long tail "slowing". The
# report names the three outcomes and leaves the cut points open - these
# are the product's, written here so they can be argued with rather than
# rediscovered.
TREND_RECENT_DAYS = 30
TREND_ACCELERATING_PERCENT = 150
TREND_SLOWING_PERCENT = 50
# Below this many commits in the whole window, a ratio is arithmetic
# rather than evidence: one commit last month against one the month
# before is a 2x "acceleration" and means nothing. Say so instead.
TREND_MIN_COMMITS = 4


class Budget(object):
    """Wall-clock allowance for one repository (15s, DP30).

    A repository that cannot answer in time still gets its row. What it
    does not get is a fabricated zero, which is why every reader asks
    `remaining()` and every caller records what ran out.
    """

    def __init__(self, seconds):
        self.total = float(seconds)
        self.started = time.monotonic()

    def remaining(self):
        left = self.total - (time.monotonic() - self.started)
        return left if left > 0 else 0.0

    def spent(self):
        return round(time.monotonic() - self.started, 2)

    def exhausted(self):
        return self.remaining() <= 0.0


def _now():
    return datetime.now(timezone.utc)


def _iso(stamp):
    return datetime.fromtimestamp(stamp, timezone.utc).astimezone().isoformat(
        timespec="seconds")


def _days_since(stamp):
    return round((_now().timestamp() - stamp) / 86400.0, 1)


def _out_of_time(name):
    return {"quality": "budget-exceeded", "signal": name}


def _failed(name, proc):
    detail = (proc.stderr or "").strip().splitlines()
    return {"quality": "degraded", "signal": name,
            "detail": detail[0][:200] if detail else "git exited %d" % proc.returncode}


def head_branch(root, budget):
    """Which branch HEAD is on, so the log readers do not assume `main`."""
    if budget.exhausted():
        return _out_of_time("branch")
    try:
        proc = subprocess.run(
            ["git", "-C", str(root), "rev-parse", "--abbrev-ref", "HEAD"],
            capture_output=True, text=True, timeout=budget.remaining(), env=GIT_ENV)
    except subprocess.TimeoutExpired:
        return {"quality": "timeout", "signal": "branch"}
    except OSError as exc:
        return {"quality": "degraded", "signal": "branch", "detail": str(exc)[:200]}
    if proc.returncode != 0:
        return _failed("branch", proc)
    name = proc.stdout.strip()
    return {"quality": "ok", "signal": "branch", "name": name or "HEAD"}


def last_commit(root, branch, budget):
    """Signal 1: when the last commit landed and what it said.

    Signal 5 rides along: a subject shaped like `wip`, `fixup!`,
    `squash!` or `tmp` is the cheapest evidence there is that somebody
    stopped in the middle of something.
    """
    if budget.exhausted():
        return _out_of_time("last_commit")
    try:
        proc = subprocess.run(
            ["git", "-C", str(root), "log", branch, "-1", "--format=%ct%x09%s"],
            capture_output=True, text=True, timeout=budget.remaining(), env=GIT_ENV)
    except subprocess.TimeoutExpired:
        return {"quality": "timeout", "signal": "last_commit"}
    except OSError as exc:
        return {"quality": "degraded", "signal": "last_commit", "detail": str(exc)[:200]}
    if proc.returncode != 0:
        return _failed("last_commit", proc)
    raw = proc.stdout.strip()
    if not raw:
        return {"quality": "none", "signal": "last_commit",
                "detail": "the branch has no commits yet"}
    stamp, _, subject = raw.partition("\t")
    try:
        seconds = int(stamp)
    except ValueError:
        return {"quality": "degraded", "signal": "last_commit",
                "detail": "unreadable log format"}
    lowered = subject.strip().lower()
    return {
        "quality": "ok", "signal": "last_commit", "ts": seconds,
        "at": _iso(seconds), "age_days": _days_since(seconds),
        "subject": subject.strip()[:200],
        "wip": any(lowered.startswith(m) for m in WIP_MARKERS),
    }


def commit_trend(root, branch, budget, window_days, cuts=None):
    """Signal 2: commit distribution over the window, reduced to a direction.

    `cuts` is the [trend] config table (DP46). The numbers are the
    product's own - the design authority names accelerating, slowing
    and stalled and fixes no thresholds - so they are overridable and
    the board publishes them rather than handing down an unexplained
    verdict.
    """
    if budget.exhausted():
        return _out_of_time("trend")
    cuts = cuts or {}
    recent_days = cuts.get("recent_days", TREND_RECENT_DAYS)
    up = cuts.get("accelerating_percent", TREND_ACCELERATING_PERCENT) / 100.0
    down = cuts.get("slowing_percent", TREND_SLOWING_PERCENT) / 100.0
    floor = cuts.get("min_commits", TREND_MIN_COMMITS)
    since = (_now() - timedelta(days=window_days)).date().isoformat()
    try:
        proc = subprocess.run(
            ["git", "-C", str(root), "log", branch, "--since", since, "--format=%ct"],
            capture_output=True, text=True, timeout=budget.remaining(), env=GIT_ENV)
    except subprocess.TimeoutExpired:
        return {"quality": "timeout", "signal": "trend"}
    except OSError as exc:
        return {"quality": "degraded", "signal": "trend", "detail": str(exc)[:200]}
    if proc.returncode != 0:
        return _failed("trend", proc)

    now = _now().timestamp()
    cutoff = now - recent_days * 86400
    recent = prior = 0
    for line in proc.stdout.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            stamp = int(line)
        except ValueError:
            continue
        if stamp >= cutoff:
            recent += 1
        else:
            prior += 1

    total = recent + prior
    prior_rate = prior / float(max(1, window_days - recent_days))
    recent_rate = recent / float(recent_days)
    if total == 0:
        direction = "dormant"
    elif recent == 0:
        direction = "stalled"
    elif total < floor:
        direction = "sparse"
    elif prior == 0:
        # Split out of the `accelerating` arm, which read
        # `prior == 0 or recent_rate >= prior_rate * up` - and with no
        # earlier commits the rate to beat is zero, so every repository
        # whose history begins inside the window was called accelerating.
        # Thirteen rows in twenty read that way on one board, six of them
        # next to "quiet for N days" in the state column. The arithmetic is
        # unchanged; what changes is that a row with nothing to compare
        # against now says so instead of returning a comparison's verdict.
        direction = "started"
    elif recent_rate >= prior_rate * up:
        direction = "accelerating"
    elif recent_rate <= prior_rate * down:
        direction = "slowing"
    else:
        direction = "steady"
    return {"quality": "ok", "signal": "trend", "window_days": window_days,
            "recent_days": recent_days, "commits": total, "recent": recent,
            "prior": prior, "direction": direction}


def uncommitted(root, budget):
    """Signal 3: files changed but not committed.

    Measured safe: with GIT_OPTIONAL_LOCKS=0 this call does not write
    .git/index. Without it, it does. That measurement is the whole
    reason Rule 5 is a paired check (DP31).
    """
    if budget.exhausted():
        return _out_of_time("uncommitted")
    try:
        proc = subprocess.run(
            ["git", "-C", str(root), "status", "--porcelain"],
            capture_output=True, text=True, timeout=budget.remaining(), env=GIT_ENV)
    except subprocess.TimeoutExpired:
        return {"quality": "timeout", "signal": "uncommitted"}
    except OSError as exc:
        return {"quality": "degraded", "signal": "uncommitted", "detail": str(exc)[:200]}
    if proc.returncode != 0:
        return _failed("uncommitted", proc)
    lines = [ln for ln in proc.stdout.splitlines() if ln.strip()]
    tracked = [ln for ln in lines if not ln.startswith("??")]
    return {"quality": "ok", "signal": "uncommitted", "files": len(lines),
            "tracked": len(tracked), "untracked": len(lines) - len(tracked)}


def unpushed(root, budget):
    """Signal 4: commits that exist here and nowhere else."""
    if budget.exhausted():
        return _out_of_time("unpushed")
    try:
        proc = subprocess.run(
            ["git", "-C", str(root), "rev-list", "--count", "@{u}..HEAD"],
            capture_output=True, text=True, timeout=budget.remaining(), env=GIT_ENV)
    except subprocess.TimeoutExpired:
        return {"quality": "timeout", "signal": "unpushed"}
    except OSError as exc:
        return {"quality": "degraded", "signal": "unpushed", "detail": str(exc)[:200]}
    if proc.returncode != 0:
        return {"quality": "not-applicable", "signal": "unpushed",
                "detail": "no upstream branch is configured"}
    try:
        return {"quality": "ok", "signal": "unpushed",
                "commits": int(proc.stdout.strip() or "0")}
    except ValueError:
        return {"quality": "degraded", "signal": "unpushed",
                "detail": "unreadable rev-list output"}


def stashes(root, budget):
    """Signal 6: work parked and, usually, forgotten.

    The timestamps matter as much as the count. The design authority's
    rule is "a stash and thirty days", and thirty days of *what* is the
    whole question - a stash made yesterday on a project that has been
    quiet for a month is not the same thing as a stash made a month ago.
    """
    if budget.exhausted():
        return _out_of_time("stash")
    try:
        proc = subprocess.run(
            ["git", "-C", str(root), "stash", "list", "--format=%ct"],
            capture_output=True, text=True, timeout=budget.remaining(), env=GIT_ENV)
    except subprocess.TimeoutExpired:
        return {"quality": "timeout", "signal": "stash"}
    except OSError as exc:
        return {"quality": "degraded", "signal": "stash", "detail": str(exc)[:200]}
    if proc.returncode != 0:
        return _failed("stash", proc)
    stamps = []
    for line in proc.stdout.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            stamps.append(int(line))
        except ValueError:
            continue
    out = {"quality": "ok", "signal": "stash", "entries": len(stamps)}
    if stamps:
        out["oldest_age_days"] = _days_since(min(stamps))
        out["newest_age_days"] = _days_since(max(stamps))
    return out


def branches(root, budget):
    """Signal 7: how many branches, how many unmerged, how many behind."""
    if budget.exhausted():
        return _out_of_time("branches")
    try:
        proc = subprocess.run(
            ["git", "-C", str(root), "for-each-ref",
             "--format=%(refname:short)%09%(upstream:short)%09%(upstream:track)",
             "refs/heads"],
            capture_output=True, text=True, timeout=budget.remaining(), env=GIT_ENV)
    except subprocess.TimeoutExpired:
        return {"quality": "timeout", "signal": "branches"}
    except OSError as exc:
        return {"quality": "degraded", "signal": "branches", "detail": str(exc)[:200]}
    if proc.returncode != 0:
        return _failed("branches", proc)
    count = dangling = behind = 0
    for line in proc.stdout.splitlines():
        if not line.strip():
            continue
        count += 1
        parts = line.split("\t")
        upstream = parts[1] if len(parts) > 1 else ""
        track = parts[2] if len(parts) > 2 else ""
        if not upstream:
            dangling += 1
        if "behind" in track:
            behind += 1
    return {"quality": "ok", "signal": "branches", "count": count,
            "dangling": dangling, "behind": behind}


def newest_tag(root, budget):
    """Signal 13: the most recent version this project claims."""
    if budget.exhausted():
        return _out_of_time("tag")
    try:
        proc = subprocess.run(
            ["git", "-C", str(root), "for-each-ref", "--sort=-v:refname",
             "--count=1", "--format=%(refname:short)", "refs/tags"],
            capture_output=True, text=True, timeout=budget.remaining(), env=GIT_ENV)
    except subprocess.TimeoutExpired:
        return {"quality": "timeout", "signal": "tag"}
    except OSError as exc:
        return {"quality": "degraded", "signal": "tag", "detail": str(exc)[:200]}
    if proc.returncode != 0:
        return _failed("tag", proc)
    name = proc.stdout.strip()
    if not name:
        return {"quality": "none", "signal": "tag", "detail": "no tags"}
    return {"quality": "ok", "signal": "tag", "name": name}


def stack(root):
    """Signal 11: toolchain fingerprints, read as file existence."""
    found = []
    for label, names in STACK_MARKERS:
        for name in names:
            if (root / name).exists():
                found.append(label)
                break
    return {"quality": "ok", "signal": "stack", "labels": found}


def maturity(root):
    """Signal 12: toy -> documented -> tested -> continuously built."""
    def any_of(names):
        return any((root / name).exists() for name in names)

    found = {
        "readme": any_of(README_NAMES),
        "license": any_of(LICENSE_NAMES),
        "ci": any_of(CI_PATHS),
        "tests": any_of(TEST_PATHS),
    }
    found["score"] = sum(1 for key in ("readme", "license", "ci", "tests") if found[key])
    found["quality"] = "ok"
    found["signal"] = "maturity"
    return found


def walk_tree(root, sealed, max_depth, max_files, budget):
    """Signals 8, 9 and 10 in one pruned walk.

    One walk, because three separate ones would triple the cost of the
    most expensive thing this collector does. Sealed directories are
    pruned before descending (Rule 6) rather than filtered afterwards -
    filtering afterwards has already entered the directory.
    """
    root_str = str(root)
    todo_items = 0
    todo_files = 0
    marker_counts = {kind: 0 for kind in CODE_MARKER_KINDS}
    marker_files = 0
    newest_ts = None
    newest_rel = ""
    files_seen = 0
    capped = ""

    for dirpath, dirnames, filenames in os.walk(root_str):
        dirnames[:] = sorted(
            name for name in dirnames
            if name not in sealed and not name.startswith("."))
        depth = dirpath[len(root_str):].count(os.sep)
        if depth >= max_depth:
            dirnames[:] = []
            capped = capped or "depth"
        for filename in sorted(filenames):
            if filename.startswith("."):
                continue
            if files_seen >= max_files:
                capped = capped or "file-count"
                break
            if budget.exhausted():
                capped = capped or "budget"
                break
            files_seen += 1
            path = Path(dirpath) / filename
            if path.is_symlink():
                continue
            try:
                stamp = path.stat().st_mtime
                size = path.stat().st_size
            except OSError:
                continue
            if newest_ts is None or stamp > newest_ts:
                newest_ts = stamp
                newest_rel = os.path.relpath(str(path), root_str)
            suffix = path.suffix.lower()
            reads_markdown = suffix in MARKDOWN_SUFFIXES
            reads_source = suffix in SOURCE_SUFFIXES
            if not (reads_markdown or reads_source) or size > READ_MAX_BYTES:
                continue
            try:
                with open(str(path), encoding="utf-8", errors="replace") as handle:
                    body = handle.read()
            except OSError:
                continue
            if reads_markdown:
                hits = sum(1 for line in body.splitlines() if TODO_LINE.match(line))
                if hits:
                    todo_items += hits
                    todo_files += 1
            if reads_source:
                hit_here = False
                for match in CODE_MARKER.finditer(body):
                    marker_counts[match.group(1)] += 1
                    hit_here = True
                if hit_here:
                    marker_files += 1
        if capped in ("file-count", "budget"):
            break

    todos = {"quality": "degraded" if capped else "ok", "signal": "todos",
             "unchecked": todo_items, "files": todo_files}
    markers = {"quality": "degraded" if capped else "ok", "signal": "code_markers",
               "total": sum(marker_counts.values()), "files": marker_files,
               "by_kind": marker_counts}
    # Signal 10 keeps the path of the newest file, and keeps it in the
    # payload - unlike the activity clock's, which is stripped at the
    # boundary (see `_without_activity_path` in render.py). Three reasons,
    # written here because an audit asked why two paths of the same shape
    # are treated differently:
    #
    #   it is inside a project the user listed, not inside another tool's
    #   directory, which is what Rule 14 is about;
    #   the board renders it - "newest file: X" is the only recency answer a
    #   project with no commits has, and dropping it would take a real line
    #   off the page;
    #   a sensitive entry never has it at all, because this walk does not
    #   run for one.
    if newest_ts is None:
        tree = {"quality": "none", "signal": "tree",
                "detail": "no readable file in the tree"}
    else:
        tree = {"quality": "degraded" if capped else "ok", "signal": "tree",
                "at": _iso(newest_ts), "ts": newest_ts,
                "age_days": _days_since(newest_ts), "path": newest_rel}
    if capped:
        note = {"depth": "walk stopped at the depth limit",
                "file-count": "walk stopped at the file limit",
                "budget": "walk stopped when the time budget ran out"}[capped]
        for block in (todos, markers, tree):
            block["detail"] = note
            block["files_seen"] = files_seen
    return todos, markers, tree


def read_ledger(root, configured, vocabulary):
    """Signal 14: what the project says about itself.

    Least universal, most trustworthy. Three qualities, and the
    difference between the last two is the one DP20 is about:

      ok              a declaration was found
      none            ledger files were read and none declared anything
      not-applicable  there was no ledger file to read

    "not-applicable" rather than "missing" on purpose: a project with no
    ledger has not failed at anything, and listing it as a degraded
    signal would put a complaint on twelve rows out of thirteen.
    """
    declaration, evidence = ledger.find_declaration(root, configured, vocabulary)
    out = {"signal": "ledger", "read": evidence["read"],
           "unreadable": evidence["unreadable"], "hits": evidence["hits"],
           "refused": evidence.get("refused") or [],
           "refused_lines": evidence.get("refused_lines", 0)}
    if declaration is not None:
        out["quality"] = "ok"
        out["declaration"] = declaration
    elif evidence["read"]:
        out["quality"] = "none"
        out["detail"] = ("%d ledger file(s) read, no declaration in any of them"
                         % len(evidence["read"]))
    else:
        out["quality"] = "not-applicable"
        out["detail"] = "no ledger file among the shapes this build reads"
    return out


def tier(recency_days):
    """The colour band, from one number: how long since anything moved."""
    if recency_days is None:
        return "UNKNOWN"
    if recency_days <= TIER_ACTIVE_DAYS:
        return "ACTIVE"
    if recency_days <= TIER_WARM_DAYS:
        return "WARM"
    if recency_days <= TIER_QUIET_DAYS:
        return "QUIET"
    return "COLD"


def _degraded_list(signals):
    """Every signal that did not answer cleanly, with the reason.

    "not-applicable" is not in the list. A repository with no upstream
    has no unpushed count and that is a fact about the repository, not a
    failure of the collector - listing it as a problem would bury the
    signals that really did fail under a column of shrugs.
    """
    out = []
    for name, block in sorted(signals.items()):
        if not isinstance(block, dict):
            continue
        quality = block.get("quality")
        # `sealed-skipped` joins the exclusions for the reason stated
        # above: a sensitive entry whose file readers were deliberately not
        # run has not failed at anything, and reporting it as a partial
        # signal put a red alert on the board for the privacy setting
        # working exactly as designed.
        if quality in ("ok", "none", "not-applicable", "sealed-skipped", None):
            continue
        out.append({"signal": name, "quality": quality,
                    "detail": block.get("detail", "")})
    return out


def _overall_quality(signals):
    qualities = {b.get("quality") for b in signals.values() if isinstance(b, dict)}
    if qualities <= {"ok", "none", "not-applicable", "sealed-skipped"}:
        return "ok"
    if "ok" in qualities:
        return "degraded"
    return "bad"


def collect_project(entry, config, vocabulary=None):
    """Every signal for one roster entry. Never raises for one bad project."""
    settings = config.section("collect")
    if vocabulary is None:
        vocabulary = markers.resolve(config.locale, config.section("blockers"))
    budget = Budget(settings.get("timeout_seconds", 15))
    root = Path(entry.path) if entry.path else None
    record = {
        "id": entry.id,
        "name": entry.name,
        "root": entry.root,
        "sensitive": entry.sensitive,
        "problems": list(entry.problems),
        "collected_at": _now().astimezone().isoformat(timespec="seconds"),
    }

    if root is None or not root.is_dir():
        record.update({
            "tier": "MISSING", "signals": {},
            "degraded": [{"signal": "root", "quality": "missing",
                          "detail": "no directory at %s" % (entry.root or "(unset)")}],
            "signal_quality": "bad",
        })
        return shield(record)

    is_git = (root / ".git").exists()
    signals = {}

    if is_git:
        branch_info = head_branch(root, budget)
        branch = entry.branch or branch_info.get("name") or "HEAD"
        signals["branch"] = branch_info
        signals["last_commit"] = last_commit(root, branch, budget)
        signals["trend"] = commit_trend(
            root, branch, budget, settings.get("trend_window_days", 90),
            config.section("trend"))
        signals["uncommitted"] = uncommitted(root, budget)
        signals["unpushed"] = unpushed(root, budget)
        signals["stash"] = stashes(root, budget)
        signals["branches"] = branches(root, budget)
        signals["tag"] = newest_tag(root, budget)
    else:
        for name in ("branch", "last_commit", "trend", "uncommitted", "unpushed",
                     "stash", "branches", "tag"):
            signals[name] = {"quality": "not-applicable", "signal": name,
                             "detail": "not a git repository"}

    if entry.sensitive:
        # Rule 7, the strong half: a sensitive entry is not filtered on
        # the way out, it is never read. The walk and the stack and
        # maturity probes all open or stat files inside the project, so
        # for a sensitive entry they do not run at all.
        for name in ("todos", "code_markers", "tree", "stack", "maturity",
                     "ledger"):
            signals[name] = {"quality": "sealed-skipped", "signal": name,
                             "detail": "entry is marked sensitive; "
                                       "collection reads git metadata only"}
    else:
        sealed = sealed_dirs(config.section("scan").get("sealed_dirs", []))
        todos, markers, tree = walk_tree(
            root, sealed,
            settings.get("walk_max_depth", 8),
            settings.get("walk_max_files", 20000),
            budget)
        signals["todos"] = todos
        signals["code_markers"] = markers
        signals["tree"] = tree
        signals["stack"] = stack(root)
        signals["maturity"] = maturity(root)
        signals["ledger"] = read_ledger(root, entry.ledgers, vocabulary)
        # DP22: the activity clock runs only if the user turned it on,
        # and the gate is here, at the call site, rather than inside the
        # adapter - "off by default" should be visible where somebody
        # reads what collection does.
        clock_on, clock_source, clock_problems = activity.configured(config)
        if clock_on:
            signals["activity"] = activity.last_touch(root, sealed,
                                                      clock_source)
        record["activity_problems"] = clock_problems

    # DP23: the file clock never colours the tier. For a git project the
    # answer to "how long since this moved" is the last commit; the
    # newest mtime is a second, weaker answer and showing both as one
    # number means a build artifact or an editor swap file can paint a
    # dead project green. Only a project with no git history falls back
    # to mtime, because there it is the only answer there is.
    primary = signals.get("last_commit") or {}
    newest = primary.get("ts") if primary.get("quality") == "ok" else None
    if newest is None and not is_git:
        tree_block = signals.get("tree") or {}
        newest = tree_block.get("ts") if tree_block.get("quality") in ("ok", "degraded") else None

    record.update({
        "git": is_git,
        "signals": signals,
        "last_activity": _iso(newest) if newest else None,
        "recency_days": _days_since(newest) if newest else None,
        "budget_seconds": budget.spent(),
    })
    record["tier"] = tier(record["recency_days"])
    record["degraded"] = _degraded_list(signals)
    record["signal_quality"] = _overall_quality(signals)
    return shield(record)


def shield(record, strict=False):
    """Rule 7 at the boundary: the last moment before the artifact.

    This used to run inside `collect_project`'s return, and an audit
    pointed out what that meant: three writers add keys *after* that
    point - `cli.collect_records` adds `home_overlap` and `state`,
    `cli.run` merges whatever a provider contributes - so the docstring's
    promise to "fail loudly here instead of quietly appearing on the
    board" did not hold for the last three chances to break it.

    So it is called again from `render.build_document()`, which is the
    last place a record exists before it is written to disk. Collection
    remains the primary gate - a sensitive project's files are never
    opened at all - and this is the net under it.
    """
    if not record.get("sensitive"):
        return record
    entry_id = record.get("id", "?")
    # `strict` is the boundary call, and it is the half that makes the
    # docstring true. At collection this function filters: the raw record
    # legitimately carries `signals`, `git` and a budget, none of which a
    # sensitive entry may emit. At the boundary the record has already
    # been filtered once, so anything outside the whitelist arrived
    # *after* collection - which is precisely the case the first version
    # dropped in silence, leaving the author to add the next signal the
    # same way. Clean artifact either way; only raising teaches.
    arrived = sorted(set(record) - set(SENSITIVE_ALLOWED_KEYS)) if strict else []
    if arrived:
        raise RuntimeError(
            "sensitive entry %r carries non-whitelisted key(s) at the "
            "boundary: %s. Rule 7 permits method only, and a key added to a "
            "record after collection has not been through the gate."
            % (entry_id, ", ".join(arrived)))
    kept = {k: v for k, v in record.items() if k in SENSITIVE_ALLOWED_KEYS}
    signals = record.get("signals") or {}
    if not signals:
        # Already shielded once. The derived counts below come from
        # `signals`, which the first pass removed, so re-deriving them
        # replaced real numbers with `None` - the board then showed
        # `0 with uncommitted work` at the top and `2 files uncommitted`
        # on the row directly underneath. Idempotent now: with nothing
        # left to derive from, what survived the first pass stands.
        return kept
    kept.update({
        "tier": record.get("tier"),
        "recency_days": record.get("recency_days"),
        "last_activity": record.get("last_activity"),
        # `last_subject` is deliberately absent: see
        # SENSITIVE_WITHHELD_KEYS in config.py. Deriving it here and
        # relying on the whitelist to drop it would work, and would also
        # mean the value existed on the record - so it is not derived.
        "trend": (signals.get("trend") or {}).get("direction"),
        "uncommitted": (signals.get("uncommitted") or {}).get("files"),
        "unpushed": (signals.get("unpushed") or {}).get("commits"),
        "wip": (signals.get("last_commit") or {}).get("wip"),
        "stash": (signals.get("stash") or {}).get("entries"),
        "branches": (signals.get("branches") or {}).get("count"),
        "tag": (signals.get("tag") or {}).get("name"),
    })
    escaped = sorted(set(kept) - set(SENSITIVE_ALLOWED_KEYS))
    if escaped:
        raise RuntimeError(
            "sensitive entry %r would emit non-whitelisted key(s): %s"
            % (entry_id, ", ".join(escaped)))
    return kept
