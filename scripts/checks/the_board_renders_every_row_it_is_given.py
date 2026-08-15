"""Rule 30: the board renders every row it is given.

**This closes DP85, and what it closes is much larger than DP85 recorded.**
DP85 was filed about one loop: re-gating `state.also` behind
`st.kind === "inferred"` - the exact regression DP80 exists to prevent -
left the gate fully green, because nothing in this repository executed
`board.html`. Re-measured at M4 stage four, with the gate at 29 checks and
the selftest at twelve steps, that is still true. It is also the small
half. Delete the `rows()` call from the template's entry point, so the
board renders **no project rows at all**, and the gate is 29/29 green with
`murscope selftest` green on both roster shapes. The product's one
deliverable can be empty and nothing in this repository notices.

Three hundred and thirty lines of JavaScript decide what a reader sees:
which sub-text lines appear under which kind of state, whether a sensitive
project's chip is drawn, whether the owed tile prints a number or a dash,
whether the activity clock's second line exists. Every one of those has
been a defect at least once - the comments in the template are the record
- and none of them was ever checked. `render.py` was checked; the thing
that turns `render.py`'s payload into a page was not.

**So the page is executed here, and the engine is a development
requirement of the gate** - never of the product. ADR-0001 is untouched:
`murscope` still has zero runtime dependencies and ships no JavaScript
toolchain, and a user runs the board in their own browser as they always
did. What changed is that the gate now needs one of `node`, `deno` or
`bun` on PATH. **Absent, this check is red, not skipped** (DP87): a check
that quietly stops running is the failure this whole gate is built
against, and "zero skipped" is an acceptance criterion rather than a
preference.

**The DOM is a shim, and its narrowness is deliberate.** The template uses
nine DOM operations - `createElement`, `getElementById`, `appendChild`,
`textContent`, `className`, `hidden`, `title`, `colSpan`, and reading
`window.MURSCOPE_BOARD` - so the shim implements those and nothing else.
Anything the template reaches for that is not there raises inside the
engine and this check goes red naming it, which is the correct outcome: a
board that needs a tenth DOM operation is a board this shim no longer
models, and finding that out from a red gate is the point. The element ids
are not invented either - they are parsed out of the shipped HTML, so a
`<div id="tiles">` deleted from the template makes `getElementById`
return null and the page throw, which is template-and-script drift caught
as itself.

**What walks into this check (DP87).** A fixture of eight projects,
rendered in every locale the package ships, and the floors are asserted
before the assertions are believed:

* all four state kinds must be present - `declared`, `curated`,
  `inferred`, `no-source` - because each one is a separate branch of
  `cellState` and a fixture missing one certifies nothing about it;
* **a `declared` row and a `curated` row must each carry a non-empty
  `also`**, which is DP85's own case: those are the two kinds whose
  headline is a quotation, and they are the rows the injection removes;
* one project must be sensitive and one must not, so the withheld-content
  assertion is not an absence measured over an empty page;
* one project must carry `home_overlap`, one must be `MISSING`, and the
  payload must carry at least one problem line;
* the rendered page must reach a floor of nodes, so a shim that silently
  produced nothing cannot report that everything it produced was correct.

Fails when: no JavaScript engine is on PATH; the template's inline script
cannot be located or raises while running; the rendered page carries fewer
project rows than the payload carries projects; any `state.also` sentence
is missing from its own row; a `declared`, `curated`, `inferred` or
`no-source` row is missing the line its branch is supposed to draw; a
sensitive project's withheld content reaches the page, or its chip does
not; a `[[MISSING:` marker appears in any locale; a stat tile's number
disagrees with the payload; the problems section stays hidden while
problems exist; or the fixture stops meeting any floor above.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

TEMPLATE = REPO_ROOT / "murscope" / "templates" / "board.html"

# In preference order, each with the arguments that run a plain script and
# print to stdout. None of them is given file or network access it does not
# already have: the harness reads nothing and opens nothing.
ENGINES = (
    ("node", []),
    ("bun", []),
    ("deno", ["run", "--quiet"]),
)

# The decoy a sensitive project's newest commit subject carries, planted
# in `last_subject` - the one key DP68 withholds by name.
#
# **It is not asserted absent from the page, and that is the finding.**
# The obvious assertion - "this string is nowhere on the rendered board" -
# cannot fire at this layer and would be exactly the shape DP143 names: a
# floor standing on something else's work. `render.build_document` runs
# `collect.shield(..., strict=True)` on every record before the template
# is ever handed one, and it *raises* on a sensitive record carrying a
# non-whitelisted key rather than filtering it. Writing this fixture is
# how that was measured: the first version handed the decoy straight to
# `build_document` and got `RuntimeError: sensitive entry 'foxtrot'
# carries non-whitelisted key(s) at the boundary: last_subject, note,
# signals`. So what is asserted here is the thing that can fail - that the
# strict boundary still refuses - and the page-level absence is a
# consequence of it rather than a second, unfireable claim.
DECOY = "murscope-board-canary-8fd1c2"

# Below this the shim produced a page too small to have rendered anything,
# and every absence assertion below it would be satisfied by emptiness.
MINIMUM_NODES = 60


def engine():
    """(name, argv) for the first engine on PATH, or (None, [])."""
    for name, prefix in ENGINES:
        found = shutil.which(name)
        if found:
            return name, [found] + prefix
    return None, []


def inline_script(html):
    """The template's own `<script>` body. Returns (source, problem).

    The `<script src="data.js">` tag is skipped by matching `<script>` with
    no attributes, which is what the template writes for its inline block.
    """
    match = re.search(r"<script>\n(.*?)\n</script>", html, re.S)
    if not match:
        return None, ("no inline <script> block found in the template, so "
                      "there is nothing to execute. The board's behaviour "
                      "lives in that block; a template without one renders a "
                      "blank page.")
    return match.group(1), ""


def element_ids(html):
    """Every `id="..."` the template declares, in document order."""
    return [m.group(1) for m in re.finditer(r'\bid="([^"]+)"', html)]


HARNESS = r"""
// A DOM narrow enough to read. Nine operations, which is what the board
// template uses; anything else throws, and a throw here is this check
// going red rather than a gap in it.
function El(tag) {
  this.tagName = tag;
  this.className = "";
  this.textContent = "";
  this.children = [];
  this.hidden = undefined;
  this.title = "";
  this.colSpan = undefined;
}
El.prototype.appendChild = function (child) {
  this.children.push(child);
  return child;
};
var __ids = {};
__ID_LIST__.forEach(function (id) { __ids[id] = new El("div"); });
var document = {
  createElement: function (tag) { return new El(tag); },
  getElementById: function (id) { return Object.prototype.hasOwnProperty.call(__ids, id) ? __ids[id] : null; }
};
var window = {};

__DATA__

__SCRIPT__

function serialise(node) {
  return {
    tag: node.tagName,
    cls: node.className,
    text: node.textContent,
    hidden: node.hidden,
    title: node.title,
    children: node.children.map(serialise)
  };
}
var out = {};
Object.keys(__ids).forEach(function (id) { out[id] = serialise(__ids[id]); });
console.log(JSON.stringify(out));
"""


def render_page(name, argv, html, document, workdir):
    """Run the template's script over one payload. (tree, problem)."""
    script, problem = inline_script(html)
    if problem:
        return None, problem
    data = ("window.MURSCOPE_BOARD = %s;"
            % json.dumps(document, sort_keys=True, ensure_ascii=True))
    program = (HARNESS
               .replace("__ID_LIST__", json.dumps(element_ids(html)))
               .replace("__DATA__", data)
               .replace("__SCRIPT__", script))
    path = workdir / "harness.js"
    path.write_text(program, encoding="utf-8")
    try:
        result = subprocess.run(argv + [str(path)], cwd=str(workdir),
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                timeout=120)
    except (OSError, subprocess.TimeoutExpired) as exc:
        return None, "%s could not run the page (%s)." % (name, exc)
    if result.returncode != 0:
        return None, ("%s refused the page (exit %d): %s. The template's "
                      "script raised while rendering, which is this rule "
                      "failing rather than this rule being unable to look."
                      % (name, result.returncode,
                         result.stderr.decode("utf-8", "replace").strip()[:400]))
    try:
        return json.loads(result.stdout.decode("utf-8")), ""
    except ValueError as exc:
        return None, ("%s produced no readable page (%s)." % (name, exc))


def flatten(node, out=None):
    """Every node in one subtree, the root included."""
    out = [] if out is None else out
    out.append(node)
    for child in node.get("children") or ():
        flatten(child, out)
    return out


def text_of(node):
    """All text in one subtree, joined - what a reader would see."""
    return " ".join(item.get("text") or "" for item in flatten(node))


def rows_of(tree):
    """The `<tr>` nodes under the projects table body, in order."""
    body = tree.get("rows")
    if not body:
        return []
    return [n for n in flatten(body) if n.get("tag") == "tr"]


def detect(payload):
    """Findings for one rendered page, handed in as JSON.

    Pure: page in, findings out. What it cannot answer is whether the page
    came from the shipped template - that is `main()`'s job, and it is why
    the fixture floors live there too. What it answers is the question the
    whole rule is about: is everything the payload carries actually on the
    page.
    """
    try:
        case = json.loads(payload.decode("utf-8"))
    except ValueError as exc:
        return ["the rendered page is not readable JSON (%s)." % exc]

    tree = case.get("page") or {}
    document = case.get("document") or {}
    catalog = document.get("i18n") or {}
    locale = case.get("locale") or "?"
    findings = []

    projects = document.get("projects") or []
    rows = rows_of(tree)
    if len(rows) < len(projects):
        findings.append(
            "%s: the payload carries %d project(s) and the page rendered %d "
            "row(s). A board that drops rows is a board that says a project "
            "is fine by not mentioning it."
            % (locale, len(projects), len(rows)))
        return findings

    for index, project in enumerate(projects):
        row = text_of(rows[index])
        name = project.get("name") or project.get("id") or ""
        if name and name not in row:
            findings.append("%s: project %r has no name on its own row."
                            % (locale, name))
        st = project.get("state") or {}
        kind = st.get("kind")
        for sentence in st.get("also") or ():
            if sentence not in row:
                findings.append(
                    "%s: row %r is a %r state carrying the sub-text %r, and "
                    "the rendered row does not contain it. That is DP80's "
                    "board half: the tiles count what this row is holding and "
                    "the row does not say so."
                    % (locale, name, kind, sentence))
        if kind == "declared" and st.get("source") and st["source"] not in row:
            findings.append("%s: declared row %r does not show its source %r."
                            % (locale, name, st["source"]))
        if kind == "curated" and st.get("byline") and st["byline"] not in row:
            findings.append("%s: curated row %r does not show its byline."
                            % (locale, name))
        # The badge is asserted as an *element*, not as text. Asserting the
        # text left this green when the badge was dropped: `st.badge` is
        # the translation of `state.inferred`, and the state chip two lines
        # above renders `state.<kind>` - which for an inferred row is the
        # same word. The assertion was answered by something the renderer
        # had already put on the row, which is DP143's fourth injection
        # exactly, met here on the first run of this battery.
        badges = [n for n in flatten(rows[index])
                  if "badge" in (n.get("cls") or "").split()]
        if kind == "inferred":
            if st.get("promote") and st["promote"] not in row:
                findings.append("%s: inferred row %r does not show how to "
                                "promote it." % (locale, name))
            if not badges:
                findings.append("%s: inferred row %r carries no badge element, "
                                "so a guess reads as a fact." % (locale, name))
            elif st.get("badge") and badges[0].get("text") != st["badge"]:
                findings.append("%s: inferred row %r has a badge reading %r "
                                "and the payload says %r."
                                % (locale, name, badges[0].get("text"),
                                   st["badge"]))
        elif badges:
            findings.append(
                "%s: row %r is a %r state and carries a badge. The badge says "
                "'this is a guess' and belongs on an inference only."
                % (locale, name, kind))
        if kind == "no-source" and st.get("next_command") \
                and st["next_command"] not in row:
            findings.append("%s: no-source row %r offers no next command."
                            % (locale, name))
        # The sensitive chip is asserted by its own label, in the project
        # cell, not by "the row has some chip on it". The looser form was
        # green with the chip deleted, because the state cell renders
        # `t("state." + kind)` with the same `chip` class - a second case of
        # an assertion answered by a neighbour (DP143).
        if project.get("sensitive"):
            wanted = catalog.get("label.sensitive")
            texts = [n.get("text") or "" for n in flatten(rows[index])]
            if wanted and wanted not in texts:
                findings.append(
                    "%s: sensitive row %r does not carry the %r chip, so "
                    "nothing on the page says this project is read through a "
                    "whitelist." % (locale, name, wanted))
        if project.get("home_overlap"):
            classes = [n.get("cls") or "" for n in flatten(rows[index])]
            if not any("q-degraded" in cls for cls in classes):
                findings.append(
                    "%s: row %r overlaps MURSCOPE_HOME and the page does not "
                    "say so (DP47). The write guard's boundary and this "
                    "project's directory overlap, so the guard alone no longer "
                    "proves the red line." % (locale, name))

    whole = " ".join(text_of(node) for node in tree.values())
    if "[[MISSING:" in whole:
        markers = sorted({m for m in re.findall(r"\[\[MISSING:[^\]]+\]\]", whole)})
        findings.append(
            "%s: the page renders %d missing-key marker(s): %s. The board's "
            "own keys are not in this locale's pack."
            % (locale, len(markers), ", ".join(markers[:6])))

    stats = document.get("stats") or {}
    tiles = tree.get("tiles") or {}
    tile_texts = [text_of(node) for node in (tiles.get("children") or ())]
    if len(tile_texts) != 6:
        findings.append("%s: the page drew %d stat tile(s) and the board has "
                        "six." % (locale, len(tile_texts)))
    else:
        # The owed tile prints a dash rather than a number when nothing
        # matched, which is deliberate (a blind zero is worse than no
        # answer), so it is asserted only where it prints one.
        for key, tile in zip(("projects", "active", "in_hand", "unsent",
                              "owed", "degraded"), tile_texts):
            value = stats.get(key)
            if key == "owed" and "\u2013" in tile:
                continue
            if str(value) not in tile:
                findings.append(
                    "%s: the %s tile reads %r and the payload says %r."
                    % (locale, key, tile.strip()[:40], value))

    problems = list(document.get("problems") or ())
    for project in projects:
        for line in project.get("problems") or ():
            problems.append("%s: %s" % (project.get("name"), line))
    if problems:
        section = tree.get("notes-section") or {}
        if section.get("hidden") is not False:
            findings.append(
                "%s: the payload carries %d problem line(s) and the notes "
                "section stayed hidden." % (locale, len(problems)))
        listed = text_of(tree.get("notes") or {})
        for line in problems:
            if line not in listed:
                findings.append("%s: problem line %r is on no rendered page."
                                % (locale, line[:60]))

    if len(flatten({"children": list(tree.values()), "text": ""})) < MINIMUM_NODES:
        findings.append(
            "%s: the rendered page holds fewer than %d nodes, so every "
            "absence asserted above was asserted over an empty page."
            % (locale, MINIMUM_NODES))
    return findings


def _case_signals(uncommitted=0, unpushed=0, stash=0, wip=False,
                  declaration=None, ledger=True):
    """One project's signals, in the shape `collect` hands the state layer."""
    signals = {
        "uncommitted": {"quality": "ok", "signal": "uncommitted",
                        "files": uncommitted},
        "unpushed": {"quality": "ok", "signal": "unpushed",
                     "commits": unpushed},
        "stash": {"quality": "ok", "signal": "stash", "entries": stash,
                  "oldest_age_days": 1.0 if stash else None},
        "last_commit": {"quality": "ok", "signal": "last_commit", "wip": wip,
                        "subject": "a commit"},
        "branches": {"quality": "ok", "signal": "branches", "count": 2,
                     "behind": 1},
        "todos": {"quality": "ok", "signal": "todos", "unchecked": 3},
        "code_markers": {"quality": "ok", "signal": "code_markers", "total": 2},
        "maturity": {"quality": "ok", "signal": "maturity", "readme": True,
                     "license": True, "ci": False, "tests": True},
    }
    if ledger:
        signals["ledger"] = {"quality": "ok", "read": ["STATUS.md"], "hits": 1}
        if declaration:
            signals["ledger"]["declaration"] = dict(declaration)
    return signals


DECLARATION = {
    "text": "BLOCKED: the vendor has not replied.",
    "source": "STATUS.md", "line_no": 3, "marker": "blocked",
    "at": None, "age_days": 1.0, "stale": False, "owner": False,
    "names_somebody": False,
}


class _Entry(object):
    """A roster entry with only what `state.resolve` reads off one."""

    def __init__(self, project_id, note=None):
        self.id = project_id
        self.note = note


# The fixture. Every name is invented; nothing here is read off this
# machine, and no path in it exists.
#
# id, name, note, signal spec, extra record keys
FIXTURE = (
    # DP85's own case, twice: the two kinds whose headline is a quotation
    # and whose in-hand facts can only arrive as sub-text.
    ("alpha", "orchestrator", None,
     dict(uncommitted=21, unpushed=2, stash=1, wip=True,
          declaration=DECLARATION), {}),
    ("bravo", "reference-shelf", {"text": "Mid-rewrite.", "since": "2026-08-13"},
     dict(uncommitted=3, stash=1), {}),
    ("charlie", "signal-relay", None, dict(uncommitted=4, unpushed=1), {}),
    # Nothing readable and no weak signal either, which is `no-source` -
    # a different fact from "read it, found nothing" and a different code
    # path (DP20). Its own row on the board offers the next command.
    ("delta", "quiet-corner", None, dict(ledger=False),
     {"signals_empty": True, "recency_days": None, "tier": "UNKNOWN",
      "signal_quality": "bad"}),
    ("echo", "ledger-keeper", None, dict(declaration=DECLARATION),
     {"home_overlap": True}),
    ("foxtrot", "sealed-drawer", None, dict(uncommitted=2),
     {"sensitive": True, "last_subject": DECOY, "note": DECOY}),
    ("golf", "absent-one", None, dict(), {"tier": "MISSING", "git": False}),
    ("hotel", "steady-state", None, dict(), {}),
)


def build_documents():
    """One payload per shipped locale. (documents, problems).

    The records are built through the shipped state layer rather than
    written out by hand, so a change to what `state.resolve` produces
    reaches this fixture instead of being described by it.
    """
    from murscope import collect, config, i18n, render, state  # noqa: PLC0415

    documents = {}
    home = Path(tempfile.mkdtemp(prefix="murscope-board-"))
    previous = os.environ.get("MURSCOPE_HOME")
    os.environ["MURSCOPE_HOME"] = str(home)
    try:
        settings = config.load_config(home)
        for locale in sorted(i18n.available()):
            catalog, _problems = i18n.load(locale)
            projects = []
            for project_id, name, note, spec, extra in FIXTURE:
                signals = ({} if extra.get("signals_empty")
                           else _case_signals(**spec))
                record = {"id": project_id, "name": name,
                          "root": "/nowhere/%s" % project_id,
                          "recency_days": 1.0, "tier": "ACTIVE",
                          "signal_quality": "ok", "degraded": [],
                          "signals": signals, "problems": []}
                record.update({k: v for k, v in extra.items()
                               if k != "signals_empty"})
                # The same order the product runs in: the collector
                # shields a sensitive record, and `cli.collect_records`
                # adds `state` and `home_overlap` afterwards. Running it
                # this way is what makes the decoy a real injection - it
                # is on the raw record, in the one field DP68 withholds,
                # and the shield is what has to remove it.
                if record.get("sensitive"):
                    record = collect.shield(record)
                resolved = state.resolve(record, _Entry(project_id, note),
                                         catalog)
                record["state"] = resolved
                state.apply_precedence(record, resolved)
                projects.append(record)
            documents[locale] = render.build_document(
                projects, settings, locale, catalog,
                ["a roster entry names a directory that is not there"],
                [{"name": "noop", "summary": "the wiring, and nothing else"}])
    finally:
        if previous is None:
            os.environ.pop("MURSCOPE_HOME", None)
        else:
            os.environ["MURSCOPE_HOME"] = previous
        shutil.rmtree(str(home), ignore_errors=True)
    return documents


def strict_boundary_problems():
    """The assertion that carries red line four at this layer.

    A withheld key cannot reach the template, and the reason is that
    `render.build_document` strict-shields every record first. That is a
    thing which can stop being true, so it is asserted here rather than
    assumed by an absence assertion over a page the key could never have
    reached (DP143).
    """
    from murscope import collect  # noqa: PLC0415

    record = {"id": "probe", "name": "sealed-drawer", "sensitive": True,
              "tier": "ACTIVE", "recency_days": 1.0, "state": {},
              "last_subject": DECOY}
    try:
        collect.shield(record, strict=True)
    except RuntimeError as exc:
        if DECOY in str(exc):
            return ["the strict boundary's refusal quotes the withheld "
                    "value itself (%r), so a sensitive project's content "
                    "travels inside the error that exists to stop it."
                    % DECOY]
        return []
    return ["collect.shield(..., strict=True) accepted a sensitive record "
            "carrying `last_subject`, the key DP68 withholds by name. The "
            "board's template is handed records after that call, so nothing "
            "downstream of here can hold red line four."]


def fixture_floors(documents):
    """What this check's own cases must reach before their answer counts."""
    findings = []
    if not documents:
        return ["no locale produced a payload, so nothing was rendered."]
    any_locale = sorted(documents)[0]
    projects = documents[any_locale].get("projects") or []
    kinds = {(p.get("state") or {}).get("kind") for p in projects}
    for kind in ("declared", "curated", "inferred", "no-source"):
        if kind not in kinds:
            findings.append(
                "the fixture carries no %r row, and `cellState` draws a "
                "different set of lines for each kind - a kind that is absent "
                "is a branch this check certified without reaching." % kind)
    quotation_with_also = [
        p for p in projects
        if (p.get("state") or {}).get("kind") in ("declared", "curated")
        and (p.get("state") or {}).get("also")]
    if len(quotation_with_also) < 2:
        findings.append(
            "%d row(s) carry a quotation headline *and* a non-empty sub-text, "
            "and two is the floor. Those are DP85's own case: re-gating the "
            "`state.also` loop behind `st.kind === \"inferred\"` is invisible "
            "to a fixture whose declared and curated rows hold nothing."
            % len(quotation_with_also))
    if not any(p.get("sensitive") for p in projects):
        findings.append("no sensitive row, so the withheld-content assertion "
                        "would be an absence measured over nothing.")
    if not any(not p.get("sensitive") for p in projects):
        findings.append("every row is sensitive, so nothing proves the page "
                        "renders content at all.")
    if not any(p.get("home_overlap") for p in projects):
        findings.append("no row overlaps MURSCOPE_HOME, so DP47's chip is "
                        "never drawn.")
    if not any(p.get("tier") == "MISSING" for p in projects):
        findings.append("no MISSING row, so the tier that marks an absent "
                        "project is never rendered.")
    if not (documents[any_locale].get("problems") or []):
        findings.append("the payload carries no problem line, so the notes "
                        "section is never unhidden.")
    return findings


def main():
    if not TEMPLATE.exists():
        print("FAILED: %s is missing." % TEMPLATE.relative_to(REPO_ROOT))
        return 1

    name, argv = engine()
    if not name:
        print("FAILED: no JavaScript engine on PATH (looked for %s)."
              % ", ".join(spec[0] for spec in ENGINES))
        print("The board's behaviour is 330 lines of JavaScript, and until "
              "this check existed not one of them was executed by anything "
              "here: the whole project table could be deleted from the "
              "template with the gate green on 29 checks (DP149).")
        print("An engine is a development requirement of the gate and never a "
              "requirement of murscope - the package still has zero runtime "
              "dependencies and ships no toolchain (ADR-0001). This is red "
              "rather than skipped because a check that stops running quietly "
              "is the failure the whole gate is built against (DP87).")
        return 1

    html = TEMPLATE.read_text(encoding="utf-8")
    documents = build_documents()
    findings = fixture_floors(documents) + strict_boundary_problems()

    rendered = 0
    workdir = Path(tempfile.mkdtemp(prefix="murscope-harness-"))
    try:
        for locale in sorted(documents):
            tree, problem = render_page(name, argv, html, documents[locale],
                                        workdir)
            if problem:
                findings.append("%s: %s" % (locale, problem))
                continue
            rendered += 1
            findings.extend(detect(json.dumps(
                {"page": tree, "document": documents[locale],
                 "locale": locale}).encode("utf-8")))
    finally:
        shutil.rmtree(str(workdir), ignore_errors=True)

    if not rendered:
        findings.append("no locale rendered at all, so every assertion above "
                        "ran over nothing.")

    if findings:
        for finding in findings:
            print(finding)
        print("\nFAILED: %d finding(s) against the rendered board." % len(findings))
        return 1

    projects = documents[sorted(documents)[0]]["projects"]
    print("OK: the board template's script was executed by %s over %d "
          "locale(s) (%s) and %d project row(s) each, and every row carries "
          "what the payload put on it - name, every `state.also` sentence "
          "under all four kinds, the declared row's source, the curated row's "
          "byline, the inferred row's badge and promote line, the no-source "
          "row's next command, DP47's overlap chip, the six tile numbers and "
          "every problem line."
          % (name, len(documents), ", ".join(sorted(documents)), len(projects)))
    print("    Until this rule existed nothing here ran that script (DP85, "
          "DP149). Both of DP85's injections are now red: re-gating "
          "`state.also` behind `st.kind === \"inferred\"`, and dropping the "
          "`rows()` call so the board draws no project rows at all - the "
          "second of which was 29/29 green with the selftest green on both "
          "roster shapes.")
    print("    Red line four is carried here by the assertion that can fail: "
          "`collect.shield(..., strict=True)` still refuses a sensitive record "
          "holding `last_subject`, and `render.build_document` runs it before "
          "the template is handed anything - so a withheld key cannot reach "
          "the page rather than being asserted absent from it (DP143). The "
          "sensitive row is rendered and asserted to carry its chip. The "
          "engine is a development requirement of the gate, never of "
          "murscope: ADR-0001 stands and the package ships no toolchain.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
