# Contributing

Discussion happens in Chinese; everything that lands in this repository
is English (Rule 3). The rules below are enforced by
`scripts/run_checks.py` - a rule without a check is wall art, so Rule 1
makes the mapping itself a check.

Run the gate before you claim anything:

```
python3 scripts/run_checks.py
```

The gate needs `setuptools` importable - not as a runtime dependency,
which the core still does not have (ADR-0001), but because Rule 13b
measures the *built wheels* and builds them with the backend
`pyproject.toml` already declares. Python 3.12 and later no longer seed
it into a virtual environment, so on a fresh one:

```
pip install setuptools
```

Without it Rule 13b goes red and says so. That is deliberate: it cannot
answer its question without a wheel, and a check that reports success
when its instrument is missing is the failure this file spends a rule
refusing.

The gate also needs a **JavaScript engine on PATH** - `node`, `deno` or
`bun`, whichever you have. Rule 30 executes the board template's own
script, because until M4 nothing here did: the whole project table could
be deleted from the template with the gate 29/29 green and `murscope
selftest` green on both roster shapes (DP149). **The engine is a
requirement of the gate and never of murscope** - ADR-0001 stands, the
package has zero runtime dependencies, ships no toolchain, and the board
opens in a user's own browser exactly as before. With no engine present
Rule 30 is red rather than skipped, for the same reason Rule 13b is.

Only one check needs the `keyring` package (Rule 18's real-keychain half,
DP150) and it does not go red without it - CI installs it and passes
`--require-keyring`, which does. Everything else is stdlib.

## What the citations point at

Four names recur in the prose here and throughout `murscope/`, and not
one of them is a citation you can follow. Two of the four are real
files in the repository where the work happens - the decision ledger
and the task books - and neither of those is published; the other two
are not files at all. Saying so once is the
whole of the fix; leaving a reader to discover it is how a document
teaches people that its references are decoration.

- **`DP<n>`** cites the decision ledger of the development repository -
  the numbered ruling that settled a question, kept beside the changes
  it caused. The ledger is not published (DP160, DP161). The reasoning
  that survives publication is in this file and in the docstrings the
  numbers sit in, so a `DP<n>` is a provenance mark rather than a
  pointer: it says *this was decided, and when*, not *go and read it*.
- **The task book** is the milestone commission an execution window
  works against. Task books are not published either, for the same
  reason. Where the phrase appears it is narrative - "the task book
  asked for X" - and X is always stated in the same sentence.
- **The design authority** is the product specification this line was
  built from. It is written in Chinese, it is deliberately not in this
  repository, and it is not published. It is named rather than cited:
  until M5 the docstrings carried section numbers into it - a report
  section here, a numbered task book item there - which read like
  something a reader could look up and were not. The numbers are gone;
  the attribution stays, because erasing it would make reasoning that
  came from somewhere look invented here.
- **`M<n>`** is a milestone: one of the numbered stages this line was
  built in, counted from `M0`. The prose uses them the way a history
  uses dates - *until M4 this check read two file types*, *since M5's
  second stage the rule is stated in this file* - so the number is
  telling you **when, relative to the other numbers**, and nothing
  else. It is **not a version**: the package's version says what a
  release contains and a milestone says which stage of construction
  something happened in, and the two are unrelated on purpose. A
  milestone is also not a thing you can open here; the commissions that
  drove them are the task books above.

Rule 35's check enforces the third of those: a numbered coordinate into
an unpublished document is a dangling reference, and it is caught in the
extracted tree before publication rather than after.

## Numbering, and the two deliberate gaps

Numbering follows the reference implementation for rules 1-10 so that
ported code keeps its rule references. Product-only rules start at 11.
The gaps below are deliberate - do not renumber:

- **Rule 9 (sanitized public feed) is not introduced.** There is no
  publisher yet, so the rule would have nothing to enforce, and Rule 1
  forbids a rule with no check. It lands with the publisher (DP15).
- **Rule 10 (blocker extraction stays precise) arrived with M1**, with
  the state layer it protects.

Rule 14 (activity source reads mtime only) arrived with M2. Rule 13
arrived with M3's first stage and became **two** rules on the way in -
13 and 13b - because "explicit consent before data leaves the machine"
turned out to be two things that fail differently: a provider running
without configuration naming it, and a base install having a provider to
name at all. One check for both would have been green whenever either
half held. Rule 15 is numbered past them because it was written last, not
because it matters least - it is the one rule here whose violation cannot
be undone.

Rules 18 and 19 arrive with M3's second stage, and they are two for the
same reason 13 and 13b are two. Rule 18 is about a **key**, which must
not reach an artifact; Rule 19 is about a **consent**, which must not
cover more than it disclosed. A key store can be perfect while a boolean
consent quietly authorises a larger payload, and a consent can be
precisely bound while the transport prints the key in a traceback. One
check would have been green whenever either half held.

Rule 16 (dependencies point one way) lands with M1, when the module
registry it protects is written. DP5 called for its script at the
architecture stage and no task book carried it, so for the whole of M0
it was a decision with no rule and no check - exactly the wall art Rule
1 exists to refuse.

## Rules

## Rule 1: all rules have checks

Every rule in this file must map to a script in `scripts/checks/` named
after the slugified rule title, or carry an explicit `Enforcement:` line
naming a non-code mechanism. Every script in `scripts/checks/` must map
back to a rule; an orphan script is a rule nobody wrote down. Rule ids
need not be numeric - `Rule 10b` is a rule - and the check asserts that
the number of headings it parsed equals the number of lines starting
`## Rule `, so a heading it cannot read can never go unnoticed.

The rule count and the script count are stated separately and both are
verified by the check. They are not the same number and never will be.

**The gate defends itself.** `scripts/checks_manifest.json` records the
content hash of every Python file under `scripts/`, recursively, plus
every fixture in `scripts/checks/fixtures/` **and in
`murscope/fixtures/`**, plus the number of checks that must exist. The
second fixture directory was outside the freeze until an audit asked what
that meant: those cases ship with the package so a user can run them
(DP21), and Rule 10 verifies that they pass rather than that they still
say what they said - so weakening one left the gate green. Freezing them
constrains this repository and not the user, whose copy in site-packages
is read-only; what a user edits is the marker vocabulary, and DP19 leaves
that alone. Recursively and
including `__init__.py`, because a support module tucked under
`scripts/checks/support/` is exactly where a check's real logic would go
if the freeze had a blind spot, and it would sit there with a
permanently stable hash. Change any of it and the gate goes red until the
manifest is regenerated in the same change:

```
python3 scripts/checks/all_rules_have_checks.py --update-manifest
```

That is the freeze. It is a tripwire, not a vault - anything in the
working tree can be edited, manifest included - but no check can be
hollowed out *silently*, and the manifest diff is what review looks at.

**Every check must be capable of failing, and must prove it.** A length
floor did not do that - forty lines of comment clear one. So each check
exposes a pure detector, `detect(payload: bytes) -> list of findings`,
with `main()` a thin wrapper over it, and ships the violating shape from
its own `Fails when:` line as data at
`scripts/checks/fixtures/<slug>.txt`. Rule 1 imports each check, feeds it
its own fixture, and goes red if the detector stays quiet.

**One finding is not proof.** A third audit hollowed out Rule 7's point
4 and the gate stayed green, because the fixture exercised a different
branch and "at least one finding" was satisfied. So a fixture carries
**several cases**, each under a `# case: <label>` marker, and **every case
must fire**. That is the whole of what this check enforces about
detectors, stated at its real strength.

Two stronger-sounding bars were tried and both are refused, on the same
grounds this file applies to every other rule:

- *one case per clause in the `Fails when:` line* - most clauses are
  verified in `main()` against a git history or a live probe, and no
  payload can reach them;
- *every place `detect()` can report from must have been reported from* -
  it counts `.append` on variables named `findings`, so renaming the
  accumulator walks past it. It is still computed and can be printed, but
  it is not a bar, because **a check may not claim more than it executes**
  and this file is not exempt from that.

What covers the gap is not a cleverer static rule. It is a **runtime
canary** in `murscope selftest`: sensitive entries with a decoy string in
their files, the real collection and render paths, and an assertion that
the decoy appears in none of the surfaces a run produces - the payload,
everything printed on either stream, and every file found under the
throwaway home afterwards. The last one is a walk rather than a list of
five remembered names, so a fourth artifact written under `MURSCOPE_HOME`
joins the surfaces instead of going unread.

**Its first version proved nothing, and the way it failed is the lesson.**
The canary pointed at a directory with no `.git`, and a `sensitive` entry
disables every reader that touches files, leaving only the git branch - so
the assertion ran over a collection in which no reader executed. A reader
injected into the git branch leaked the decoy with the gate green. A
runtime measurement is only worth the path it walks, and "it cannot be
walked past" was written about a canary that had been. It now fabricates a
repository so the branch a sensitive entry actually runs is the branch
under test, and covers the plain directory as a second entry.

**The two halves are not the same evidence, stated rather than implied**:
the decoy is a real injection, and the commit-subject half is two absence
assertions - `last_subject` is off Rule 7's whitelist and on no sensitive
record - because no commit can be fabricated here (`git commit` is not on
Rule 5's read-only allowlist and is not going on it for a test). Whether a
commit message is method or content is settled (DP68): it is contents, and
a sensitive project's contents do not go on the board. This paragraph used
to say the opposite - that `last_subject` is on the whitelist and reaches
the board by design - which contradicted Rule 7's own section below it,
the `az` row in the table, the constant in `config.py`, and the two
assertions that have been testing it since DP68.

Fixtures are base64 under a commented header on purpose. A fixture
holding live violating source would trip the other checks, and the fix
for that is always an exempt directory - which is where every hole two
audits found began. Data cannot be mistaken for code, and no directory
has to be exempted.

The runner is held to the same bar. It must carry a `Fails when:` line,
define `main()`, call `sys.exit`, and - checked structurally, from its
parse tree - enumerate the checks directory, execute them with the
current interpreter, and inspect their return codes. A runner that
prints a green summary having executed nothing is the same failure as a
hollow check, and CI runs that same command. The manifest also records
how many checks are supposed to exist, and the runner asserts it, so
deleting a check along with its rule cannot produce a smaller green
number that only a human would notice (DP25).

## Rule 2: all changes via pr

Work lands on `main` through pull requests.

Branch protection is the mechanism this rule originally named, and it
is a setting on a hosting account rather than a fact about a tree.
This check needs no account at all: it reads the history in front of
you, which is the same evidence a reviewer has and is available
offline. That is the replacement, and it is a check rather than a
promise - every commit on `main` after the founding phase carries a
pull-request reference, verified from git history.

**The founding boundary here is empty**, which means this ref's own
root commit. A tree founded from a clean start has no founding phase
to exempt, because its first commit is the founding one and everything
after it went through review like anything else. An empty boundary is
not a fallback for a named one that failed to resolve: that stays a
finding, because a hash gone from history is a stale list, and a stale
list is the failure this rule refuses.

It will not stop a determined author - `(#99)` can be typed into a
subject and no offline check can tell that from a merge. It catches the
accidental direct push, which is the failure that actually happens.

**The frozen table of pre-existing violations is empty here**, for the
same reason the boundary is. It stays in the check because the rule it
belongs to does: an exception is written down rather than absorbed into
the boundary, which would be fitting the line to the data - the one
habit this line refuses (DP52).

Practical consequence: **do not edit the subject line when squash
merging.** Let the `(#N)` stand.

## Rule 3: english only

Tracked files are ASCII. Every non-ASCII character is a finding unless it
is one of three permitted typographic marks - `U+00B7`, `U+2192`,
`U+2026` - each of which the check asserts is punctuation or a symbol
rather than a letter, so the permitted list cannot grow a language.
Brand or display CJK must be escaped (`\uXXXX` in code and JSON, HTML
entities in pages) so that sources stay ASCII-grep-able. Tracked text
files must decode as UTF-8: a file the scan cannot read is a finding, not
a pass, because a GBK-encoded Chinese file would otherwise scan clean.

**This rule used to name twenty-seven CJK and emoji ranges, and that is
not the same rule** (DP147). A raw character outside all of them was
invisible: rewrite the shipped `fr.json` with its accents unescaped on
`origin/main` and the check printed *136 tracked file(s) are
English-only* over 161 raw non-ASCII characters in a tracked file. What
the rule enforced was "no Chinese", and it looked like "born English"
only because Chinese was the only other language in the repository. The
ranges are still named so a CJK hit says which script it is in; they are
a label, not the test. The test is `ord(ch) > 127`.

Exempt: nothing. The check names the ranges and the permitted marks as
escape sequences, so it is pure ASCII and is scanned like every other
file - it used to exempt itself and never needed to. Note that
`archive/` is **not** an exemption here either - it is untracked
entirely (DP40). The reason given at the time was that the repository
would one day be made public, and DP164 later ruled that making a
repository public is never how anything here is published. The reason
that survives that ruling is the durable one: git history is permanent,
and who may read a repository is a setting rather than a fact.

## Rule 4: governed docs carry frontmatter

Every `.md` under `design/` and `templates/` starts
with YAML frontmatter carrying `title`, `type`, `captured` and `status`.
`captured` is a date, never a relative phrase.

Exempt: `CLAUDE.md`, `README.md`, `CONTRIBUTING.md`, `BRAND.md`.

## Rule 5: monitored projects are read only

Inside the `murscope/` package:

- Every git invocation must satisfy **both** halves of the pair: an
  allowlisted read-only subcommand **and** `GIT_OPTIONAL_LOCKS=0` in the
  environment passed to that call. Measured on a real repository, the
  same subcommand writes `.git/index` without the variable and does not
  write it with (DP31). Pinning the subcommand name alone is not enough.
  Every idiom a careful author would reach for is accepted:
  `env = os.environ.copy()` then `env["GIT_OPTIONAL_LOCKS"] = "0"`,
  `dict(os.environ, GIT_OPTIONAL_LOCKS="0")`, the 3.9 merge form
  `os.environ.copy() | {...}`, a key held in a module constant, and a
  call to a helper whose body provably locks the environment. That last
  one matters most: factoring the locked environment into one function is
  how the invariant stops being forgeable, and a check that refused it
  would push the next author to loosen the check instead of writing the
  helper. The environment is matched structurally, in the call's own
  scope, so a string that merely mentions the variable does not count and
  a locked `env` in another function cannot vouch for a bare call here.
- Every write goes through `guard_write_path()`, which raises unless the
  target resolves inside `MURSCOPE_HOME`.
- No write outside that guard, in any spelling: write-mode `open()`,
  `Path(p).write_text()`, `Path(p).mkdir()`, `os.remove()`,
  `shutil.rmtree()`, or the same functions reached through
  `from os import remove` / `from shutil import rmtree`. The check
  matches the method being called, not the shape of the receiver.
- Write-capable `open()` modes include `r+`, which contains none of `w`,
  `a` or `x` and writes anyway.
- The package shells out to `git` and to nothing else. Skipping every
  non-git program let `rm -rf` and `/bin/sh -c` write into a monitored
  project on a green gate.
- Subprocess invocations must be statically readable argument lists.
  `shell=True`, `os.system()` and `os.popen()` are refused outright: a
  promise that cannot be verified by reading the source is not a promise.
- `guard_write_path()` earns its exemption by content, not by name: it
  must mention `MURSCOPE_HOME` and it must `raise`. Otherwise any writer
  could be waved through by renaming itself.

**The scheduling exception, which is not an exception (DP126).** launchd
reads a job description from `~/Library/LaunchAgents` and systemd from
`~/.config/systemd/user`. Neither will read one from `MURSCOPE_HOME`, so
`murscope timer install` is the first deliberate write outside the home
in this product's life. The reply is a second pair of guards -
`guard_schedule_write()` and `guard_schedule_remove()` - and what makes
them a boundary rather than a hole is that **the permission is for a
path, on an explicit command, printed before it is written**. Four things
are checked, and each is chosen against the obvious way to fake it:

- the guard `raise`s, exactly as `guard_write_path()` must;
- it asks `permitted_schedule_paths()` which targets it may touch, and
  **hands it nothing**. A permitted set the caller can influence is not a
  permitted set;
- `permitted_schedule_paths()` itself declares **no parameters**, so the
  table cannot be widened from a call site either. It is computed from
  literals and the user's home directory, and it is compared by
  **equality** - a prefix test on `~/Library/LaunchAgents` would license
  every launch agent on the machine, which is a permission for a
  directory wearing a permission for a path;
- the target is printed **before** the write, measured by line number
  from the parse tree. Reading the source for the word `print` would pass
  a guard that logs the path afterwards, and a path named after the fact
  is a receipt rather than a chance to say no. This is case `ck`'s
  method: a refusal that arrives after the request is built arrives late.

A guard failing any of the four gets no exemption and its writes are
reported like anybody else's. The activation of the job is **not** part
of this: `launchctl` and `systemctl` are not on the one-program
allowlist above and are not going on it, so murscope writes the file,
prints the command, and stops.

**A fifth thing, and it is about the table rather than the guards
(DP154).** The four above are all properties of the machinery, and for
four stages that was everything any check knew about this boundary - what
was actually *in* the permitted table was reviewed by eye. Adding
`.zshrc` to `SCHEDULE_JOBS` left the whole gate green and `murscope
selftest` green, and `guard_schedule_write()` then overwrote a user's
shell configuration with every mechanism working exactly as designed: the
target was announced before the write, because it was in the permitted
set. The selftest's own sentence moved with the table - "2 path(s) may be
written outside MURSCOPE_HOME" became "4 path(s)", the refusal count 16
became 22 - which is precisely why it caught nothing. **A number measured
off the thing it describes reports; it does not constrain.** The opposite
mistake is a written-down count, which pins the number and nothing else:
a second launch agent and a dotfile are the same arithmetic.

So the table's entries are asserted by **category, never by name list**.
Every path it permits has to be

- a plain relative path under the user's home - not absolute, not
  climbing. `home / rel` on an absolute `rel` is `rel`, which is Rule
  17's shape: the join reads as contained and is not;
- in the one directory that platform's supervisor reads job descriptions
  from - `Library/LaunchAgents` on darwin, `.config/systemd/user` on
  linux - because a file anywhere else is not a job description that
  failed to work, it is this product writing somewhere for another
  reason;
- with a suffix that supervisor loads (`.plist`; `.service` or `.timer`),
  and with a name in **this product's own namespace**, read off the
  package directory rather than typed. The last one is what separates our
  launch agent from `com.apple.something.plist`, which is in the right
  directory with the right suffix and is somebody else's.

A platform the check has no supervisor description for is refused rather
than waved through, `SCHEDULE_FILES` must be *derived* from
`SCHEDULE_JOBS` rather than written out a second time, and the whole
assertion is made twice: once on the table as literals, and once on the
set `permitted_schedule_paths()` actually computes, which must agree with
it. A new murscope job passes both without the check being touched; that
is what makes this a category and not a list.

**The table holds two jobs since M4's second stage, and the count is the
only thing that changed.** DP124 keeps the collecting job away from every
transport and DP125 lets an alert leave, so an alert cannot be something
the collecting job does - it needs a scheduled entry point of its own
(`murscope-alert`, held by Rule 27). Two unattended entry points are two
job descriptions on disk, and the permitted set is the union. It is still
computed with no parameter, still compared by equality, still printed
before the write; `murscope timer install` writes the collecting job and
`--alerts` adds the other, and the screen says in as many words which of
the two can send. The same reasoning refuses the notification centre for
local delivery: `osascript` and `notify-send` are not `git` either, so an
unattended alert's local half is stdout, which the job description points
at `MURSCOPE_HOME/alerts.log`.

## Rule 6: sealed directories stay sealed

The scanner ships a non-empty built-in default exclusion table, users may
extend it, and every directory walk prunes on the resolved table before
descending.

Check scripts are a frozen zone: changing one has to pass the checks, and
has to update `scripts/checks_manifest.json` in the same change. Rule 1
enforces that half.

## Rule 7: sensitive entries expose method only

A roster entry marked `sensitive` is read through a frozen key
whitelist. The check verifies that the whitelist exists, is frozen, is
actually applied, and that no data file escapes it.

*The stronger half, and where it now stands.* "The collector must not
read the rest at all" is why this is a collection-time boundary rather
than a rendering-time filter: a filter applied on the way out has already
read the thing it hides. That half **is** enforced - `collect.py` exists,
ships, and the check reports the gates it found - and the sentence that
used to stand here, saying nothing enforced it because the collector did
not exist, was left unrevised from M0 through four audits while the file
grew to seven hundred lines. It contradicted Rule 17 a hundred lines
further down.

**`last_subject` is withheld, and that is settled (DP68).** A commit
subject was on the whitelist, so a sensitive entry put a full commit
message on the board with nothing injected - and a commit subject is the
line most likely to name a client or a person. The ruling is one
sentence: marking a project sensitive means its **contents** do not go on
the board, and a commit message is contents. The key lives in
`SENSITIVE_WITHHELD_KEYS`, named rather than merely left out of the
whitelist, because absence proves nothing on its own - `murscope
selftest` asserts it is off the whitelist and on no sensitive record, so
putting it back turns the run red instead of turning it into a leak.

What the check actually does is **statically resolvable readers in the
collection modules**, and its docstring records the five shapes it cannot
see - a reader in an unlisted module, a class attribute, a dict of
callables, `getattr`, a module-level lambda. Those are the boundary of
static analysis rather than a backlog, and what covers them is the runtime
canary in `murscope selftest` (DP65).

## Rule 8: i18n keys stay complete

Locale files are maintained independently. There is no runtime default
fallback: a missing key renders a loud `[[MISSING:key]]` marker. Key sets
must match exactly across locales, every value must be a non-empty
string, and `TRANSLATION_STATUS.md` must state the real key count.

Comparing key *sets* cannot see a string that never became a key at all.
The summary screen's heading was three of those - English words printed
over rows the catalog had already answered in Chinese - and every locale
agreed with every other one throughout (DP83). So the check also reads
`wizard._header` and requires every string constant in it, other than
the format template, to be a catalog key passed to `translate` and
present in every locale.

That guard is deliberately one function wide. The wide version - find
the English literals that ought to be keys - needs a static reading of
which constants are rendered values rather than templates, log lines,
paths or identifiers, and DP67 already priced that proxy at negative.
The terminal screen's remaining prose is English on purpose and this
rule does not claim it; the widening happens one surface at a time, by
lifting a heading into its own function and naming it in the check
(DP84). **Adding a third locale did not close that gap and the record
must not imply it did**: `fr` makes the key-set comparison span three
files, which is the first time it can disagree at all, and it still
cannot see a user-facing string that never became a key.

**Every locale file is pure ASCII on disk**, with its non-English
characters written as `\uXXXX` escapes. `TRANSLATION_STATUS.md` has said
so since the first locale landed and nothing counted it, which held for
as long as the only non-English locale was Chinese: Rule 3's scanner
names CJK and emoji ranges, so a raw `zh` value was caught by a different
rule for a different reason and the escape rule was never doing the work.
A French accent is in none of those ranges. Measured, on a French locale
written unescaped: 322 non-ASCII bytes in a tracked file, Rule 3 green
and Rule 8 green. Rule 8 now counts them.

## Rule 10: blocker extraction stays precise

A declaration must lead its line, or lead one of the line's table cells,
and satisfy one of four shapes: a multi-word marker, a marker followed by
punctuation, a short status cell, or a non-ASCII marker. Three shapes are
refused outright:

1. **prose** that merely mentions a marker mid-sentence;
2. **notation legends** inside a code span or an HTML comment;
3. **an empty "Blocked" heading** - a heading is a bucket, and reporting
   the bucket invents a blocker out of a section title.

The precedence rule is pinned with them: a declaration that names the
owner overrules the roster's next-move badge and joins the owner queue;
a generic blocker never does, because that is not the owner's move.

The fixtures split in two (DP21). The shape cases are **synthetic** and
**ship with the package** at `murscope/fixtures/ledger_cases.json`, so
`murscope selftest` runs them on the user's machine against the user's
own vocabulary - that is what turns this rule from something protecting
the maintainer into something protecting the user who just edited
`extra_markers`. The reference implementation's fixtures are quoted from
the owner's real ledgers and are not copied here, at any point.

The frozen-vocabulary pin stays in repo CI and pins the default packs
only. The marker lists are literals in the check rather than a hash: a
reviewer should see which word changed.

A false positive here costs more than a miss. It sends someone to a
project that is fine, and the second time that happens the column has
lost them.

## Rule 11: offline by default

The core may not import `urllib`, `socket`, `http`, `ssl`, `ftplib`,
`smtplib`, `xmlrpc`, `asyncio`, or any third-party HTTP client. Network
access is allowed only inside `murscope/providers/`. Repository tooling
under `scripts/` is held to the same bar.

*This became binding at M3, and it took two rules rather than one.* The
sentence "which configuration must explicitly enable" had nothing behind
it: the enforcement was that no code path in the build reached the
network, not that a provider was gated on config, and the directory was
described as empty in three places while `noop` was in the wheel and this
gate's own Rule 16 line was printing "1 provider module(s)". Rule 13 now
enforces the gating and Rule 13b enforces that a base install has nothing
to gate - two checks, because a loader can be correct while the wheel
ships a provider it should not, and a wheel can be clean while the loader
imports at module scope.

What ships under `murscope/providers/` in the base distribution is the
loader and `noop`, which registers a name, contributes an empty map,
opens no socket and imports nothing forbidden. Everything that can reach
the network lives in `murscope-ai`, a separate distribution (DP88), and a
base install does not have it.

`webbrowser` is not forbidden - `murscope open` hands the local board to
the desktop browser, and landed at M2 - but every call to it must pass a `file://`
literal, a string with no scheme, or `Path(...).as_uri()`. An
unconstrained browser call takes a URL, which makes it an exfiltration
channel with a written exemption.

Nor may it shell out to one. `subprocess.run(["curl", ...])` imports
nothing forbidden and reaches the network anyway, so `curl`, `wget`,
`nc`, `ssh`, `scp`, `rsync` and their relatives are refused as
subprocess programs outside a provider.

"This command will not reach the network" has to be a fact a reader can
verify, not a setting they have to trust.

## Rule 12: zero telemetry

No analytics, crash reporting, version phone-home or usage beacon
anywhere in the repository. The check matches call and endpoint shapes,
not the English word, so the promise can be written in prose without
tripping it, and it matches them case-insensitively, because a crash
reporter's initializer is the same beacon whichever way its vendor
capitalises it. `README.md` states it as a promise.

Note that the vendor names themselves are matched as bare words, so this
file cannot name them either. That is the intended trade: a repository
promising zero telemetry has no reason to mention a telemetry vendor,
and the alternative - an exemption for the documentation - is how an
exemption list starts growing until it means nothing.

Exempt: the check script itself, which names the forbidden shapes.

## Rule 13: providers run only when configuration names them

A provider is imported when, and only when, `config.toml` names it in
`providers.enabled`. Being installed is not being enabled.

The loader is the whole mechanism and it is one short file,
`murscope/providers/__init__.py`. It may not import a provider
statically, may not import one at module scope, and may not hand a
string from configuration to `import_module` without first testing it
for membership in the set of modules actually present on disk. That
membership test is what keeps the loader from being an arbitrary-import
hole: `pkgutil.iter_modules` yields plain module names, so a traversal
string or a dotted path can never be in its answer.

The name list used to be a literal tuple, which did the same job. It
could not survive DP88: the base distribution does not know the names of
modules it does not ship, and writing them down anyway would be the core
naming a provider, which Rule 16 refuses. What replaced it is a
directory listing rather than an import, and `BASE` - the tuple that
remains - names what the *base distribution* ships, so Rule 13b below has
something to measure against.

The check has two instruments, because the static one alone would pass a
loader whose membership test compared against the wrong set: the loader's
parse tree, and **three live `load()` calls** against the real registry -
an empty configuration must register nothing, three uninstalled names
(a traversal string, a stdlib module, one that does not exist) must each
be refused with a problem line, and naming `noop` must register exactly
`noop`. The positive case is not decoration: without it every refusal
would be satisfied by a loader that can import nothing at all.

## Rule 13b: the base distribution ships no provider that can reach out

The other half of Rule 13, and a separate check because it fails
differently. Rule 13 asks whether a provider runs unasked; this asks
whether there is anything there to ask for.

**Ruled at DP88: network capability ships as an optional package, not as
a configuration flag.** Promise two reads "It makes no network call at
all. Not 'off by default' - absent", and the second half is a stance
rather than a flourish - a provider gated only on a config key would make
the promise mean the exact thing it exists to refuse. So `pip install
murscope` puts no module on disk that could open a socket, and `pip
install 'murscope[ai]'` additionally installs `murscope-ai`, a separate
distribution whose sources live under `extras/murscope-ai/` and whose
modules land beside the base package's in `murscope/providers/`.

The gain is that the promise is measurable rather than trusted. `pip
list` answers it. A user who never typed `[ai]` does not audit a config
file to know nothing can reach out, because the code that would reach out
is not on their disk.

**Measured on a built wheel, never on the source tree.** M1's one real
defect was a fixture present in the checkout and missing from the wheel,
invisible from a source tree; this is the same class read from the other
end, and what is in the repository is not what `pip` puts on a user's
disk. The check builds both wheels with the backend `pyproject.toml`
declares - the same one `pip` uses - and reads the artifacts. If the
backend is not importable it goes **red**, because a check that reports
success when its instrument is missing is not a check.

Both wheels are read, and the extras wheel is what stops this being an
assertion over an empty set: the base wheel must carry exactly the loader
and the modules `BASE` names with nothing socket-capable among them, and
the extras wheel must carry at least one provider module that *is*
socket-capable. Otherwise "the base wheel has nothing that can reach out"
would be equally true of a product where nothing anywhere can. The two
wheels must share no file, since they install into one directory, and the
extra must be declared in the base wheel's own METADATA and pinned to the
version the extras distribution actually is - one product, one version.

The complementary half - an installed wheel in a fresh environment - is
`murscope selftest` step 9 - nothing this install can load is able to
open a socket - which ships inside the command so it runs on
the user's machine against the build they installed. CI runs it from a
built wheel outside every checkout. Between them: this check reads the
artifact, that step reads the installation, and a file dropped into
`site-packages` by hand belongs to no distribution and turns the step red.

**If this is the only red check on your machine, read this before
debugging your change (DP119).** This check builds both wheels with the
declared backend, and a `setuptools` older than 61 cannot read project
metadata out of `pyproject.toml` - it produces `UNKNOWN-0.0.0` wheels with
no package in them, and nine findings follow from that one fact. Apple's
`/usr/bin/python3` ships setuptools 58.0.4, so a gate run on the system
interpreter is 24/25 with this check red on `main` as well as on your
branch. CI does `pip install setuptools` before the gate for exactly this
reason. The fix is the same locally:

```
python3 -m pip install --upgrade setuptools
```

Recorded here rather than left to be rediscovered: a check that is red
only on some machines is a check the next person assumes they broke.

## Rule 18: keys are stored 0600 and never rendered

DP18 settled where a key lives: a 0600 file under `MURSCOPE_HOME`, which
needs no dependency, with the system keychain as the `keyring` extra.
This rule keeps it there, and it is two instruments because the two
failures are not alike.

**The static half** reads the modules that hold or transmit a secret -
`murscope/keys.py`, the base package's provider modules, and every
provider module under `extras/` - and refuses four shapes: a key written
through the guard with no mode; a `Secret.__str__` / `__repr__` /
`__format__` that returns the value; a `raise` inside an `except` without
`from None`; and the caught exception used for anything but `redact()`,
`reraise_masked()` or `type()`.

The third and fourth are the ones worth spelling out, because they are
about **the day something goes wrong rather than the day it works**. A
URL with a key in its query string, handed to `urllib`, comes back as
`ValueError: unknown url type: '...?key=<the key>'` - a string the
standard library built, which no care at our call sites prevents. It
lands in an exception message, which becomes a traceback, which is an
artifact: `traceback.print_exc()` prints it, a caller's `print()` prints
it, and a log file keeps it. A bare `raise` inside a handler chains the
original on `__context__`, so the traceback prints it under "During
handling of the above exception" even when nobody named it.

**The live half** stores a decoy through the real store and measures the
mode; asks the real `Secret` for its value five ways and checks that none
answers; and **makes the real transport fail with the decoy in the URL**,
in a subprocess under an audit hook that refuses socket events, then
reads the whole traceback back. The failure is provoked by a URL `urllib`
cannot parse, so it happens where it happens in the field and no socket
is ever opened.

Redaction has two passes and needs both: known values, which covers every
key murscope itself read, and URL query values, which covers a key the
store never saw. **The second pass exists because this check found the
gap** - a decoy handed straight to the transport went into the traceback
with `redact()` reporting nothing to do.

Redaction is applied to error text and to nothing else. Not to the board
payload: a payload scrubber would mask a key that reached the payload
instead of the canary catching it, and the guard that is supposed to go
red would go green forever.

**Every transport is made to fail, each with its own grant (DP103).** The
probe built one grant, for whichever provider name and field list the
first transport used. The second transport to ship refused it on consent -
correctly - and so never reached the failure path this rule exists to
exercise, which surfaced as "the traceback carries no mask": a true
finding whose cause was the probe, because nothing had been masked since
nothing had failed. A transport declares `PROVIDER` and
`consent_fields()`, and each is handed a grant built from its own.

**If the transport module cannot be loaded, this check goes red**, for
the reason Rule 13b goes red without a build backend.

### The keychain, and how much of it is proven (DP99, DP150)

DP99 recorded that the keychain backend's success path had only ever run
against a stub, and gave the reason: a genuine exercise writes into the
machine's own keychain and prompts its owner for a password, which a gate
may not do to somebody who typed one command. That reason is still right.
It turns out to rule out **one layer** rather than the whole path.

`keyring` is a dispatcher. The platform keychain is one backend behind it,
and `keyring.set_keyring()` replaces which one - so the real package is
now driven end to end: the real `set_password` and `get_password`, the
real import path, the real exception types, with the value going into a
backend the check owns and the operating system never asked for anything.
Three things are asserted that the stub could not: that dispatch really
went through `keyring` (`get_keyring()` is the registered backend), that
`set_password` was reached with the service name the backend claims, and
that an absent key comes back absent rather than as a problem.

The stub half is kept rather than replaced. It runs on every machine; the
real half runs where the extra is installed, and **CI installs
`murscope[keyring]` and passes `--require-keyring`**, which turns an
absent package into a finding. Without that flag the stronger path would
be a branch nobody is ever on, which is DP81's shape.

**What is still unproven, and it is not scheduled** - because scheduling
it would be the "M5 will do it" that DP81 exists to make visible, and
because it genuinely cannot become a gate's job:

> No operating system keychain has ever been written to or read from by
> this code.

The procedure that would close it is manual, and here it is, so that
"unproven" does not quietly age into "fine":

```
pip install 'murscope[keyring]'
printf 'keys-backend-probe-value-0001' | murscope key set probe
murscope key list
```

with `backend = "keyring"` under `[keys]` in `config.toml`. The machine
will prompt for a password; that prompt is the thing a gate may not
cause. `key list` must name the service and no value, and the platform's
own keychain application must show one entry under service `murscope`.
Whoever runs it records the platform, the version and the outcome in the
acceptance report for the milestone they run it in, and this section says
so instead of a check pretending to.

## Rule 19: consent binds to the disclosure it showed

**A boolean consent fails in one specific, quiet way: the payload grows,
and the old agreement silently covers the new, larger one.** The user is
never asked again, nothing goes red, and an answer given about eleven
fields is applied to twelve. Every part of that is invisible from the
outside, which is why it is a rule and not a comment.

So a `consent.Grant` carries a fingerprint of the disclosure it was
granted against - the ordered table from `outbound.DISCLOSURE` **as the
user read it, each path together with the sentence beside it** - the
provider, and the destination. The destination is in it for the reason
DP90 gives: agreeing to send eleven numbers to a model on your own
machine is not agreeing to send them to a vendor on the open internet.
Changing what leaves therefore costs one re-consent, and it cannot cost
nothing.

**The sentence is in the digest, and it was not (DP105).** The first
version fingerprinted the paths alone, which is this same failure wearing
different clothes: `projects[].id` described as "the id you gave the
project" and `projects[].id` described as "the directory name the scan
set, unless you changed it" are one path and two disclosures, and the
second inherited every consent recorded against the first. The digest runs
over whitespace-collapsed text, so re-wrapping a paragraph is free and
rewriting a word costs a re-consent - a price this file states rather than
hides, because it is paid by every user of a build that fixes a typo.

**The table declares scope, and `build()` measures itself against the
payload rows only.** A row describing a credential in a header is not a
leaf of the document murscope builds, and comparing it against that
document would report every request-scoped row as a disclosure that
overstates what leaves. The scope column cannot be used to take a field
off the screen: a payload leaf no `PAYLOAD` row declares is a stray and
nothing is sent, and the check moves a real field to request scope and
asserts exactly that.

The static half holds five things: `fingerprint()` uses every argument it
takes; `build()` checks what it produced against the declared table and
raises; the transport type-tests its consent against `Grant`; its first
`urllib` call sits below its consent check, by line number; and **the
route it takes is the destination it disclosed**.

That last one is DP111 and it was found on a machine that has a proxy set.
`urllib.request.urlopen` reads `https_proxy` from the environment, so a
transport that calls it sends the payload through a machine the consent
screen never named while that screen said the vendor's host - the
fingerprint would be over a destination the request does not reach. DP90
refused "localhost is not the network"; "a proxy is not a destination" is
the same sentence. Every transport therefore opens through an opener it
built with `ProxyHandler({})`, the disclosure carries a `request.route`
row saying so, and the commands tell a user whose environment names a
proxy that it is being ignored - because the alternative to a silent
detour is a connection failure nobody can explain.

**The proxy map is looked for in what `send()` can reach, not in the file
it lives in (DP121).** The first version of that assertion walked the
whole module, which answers "does this file contain a proxy map" and not
"does the opener that runs build one". Six openers changed to a bare
`build_opener()` plus one never-called function per module holding a
`ProxyHandler({})` left this rule green while the live opener read
`https_proxy`. It takes deliberately-added dead code to reach - the
ordinary regression, an opener changed and nothing added, was caught
before and is caught now - and the criterion is a call graph from
`send()` instead, which costs nothing and does not need the caveat.

The live half runs the real modules: a recorded consent covers its own
request, stops covering it when one field is added - naming the field -
**stops covering it when one field's sentence is rewritten and every path
stays the same**, and stops covering it when the destination changes; an
unrecorded consent covers nothing; **the declared payload rows and the
built payload are the same set in both directions**, because a field
emitted and not declared is a field nobody was shown and a field declared
and not emitted is a disclosure that overstates what leaves; and the
transport refuses `True`,
`1`, `"yes"`, stage one's old sentinel string, `None` and a grant
recorded for a wider disclosure, each under an audit hook that refuses
socket events.

**The positive cases are not decoration.** A binding that refused
everything would satisfy every refusal above, so the current grant is
asserted to be accepted *and* to reach the wire - which is the only
evidence that it got past the gate rather than falling over before it.

Rule 19 covers **every** transport in `extras/`, not the first one to
ship. A transport declares the provider name and field list its consent
is about (`PROVIDER`, `consent_fields()`) and the probe asks; a probe
that handed every module the first module's grant would not be testing
the others, it would be failing them.

## Rule 20: the contributions reader corrects three known platform defects

`design/ADR-0003` records four defects found upstream **after** the port
baseline was pinned. Three of them are the contributions reader's, and
they are not hypotheses: each produced a wrong number on a page that
looked right, and each was expensive to find. Porting the reader without
them re-introduces them, which is what makes this a rule rather than a
comment in the module.

| | The defect | What the rule holds |
|---|---|---|
| E1 | A range endpoint in the future is answered with a snapshot frozen part way through the current day | no range ends later than the moment it is asked |
| E2 | A 25-minute cache TTL published 11:22 figures under a masthead reading 11:44 | the cache answers only after a failed request, never instead of one (DP48) |
| E3 | "1 January to today" is the range the platform precomputes for its own annual view, so it is served from cache while any other range is computed live | the year range is corrected by a second, live window, and the total is summed from the corrected series - never read from `totalContributions` |

**The corrections live in the core and only the socket is behind the
`[ai]` boundary** (DP95, applied a second time). Nothing in
`murscope/contributions.py` opens one: it clamps a range, lays one day
series over another, and adds up the result. That is why this rule can be
checked on every install rather than only on the ones that could reach
out.

The static half refuses four shapes: a December endpoint with no clamp
anywhere in the module; a time-to-live that lets a cache answer instead
of a request; a total lifted from the platform's own figure; and a reader
that builds one range and nothing live to correct it with.

The live half runs the real module and pins **each correction in both
directions**, because each has a degenerate form that would pass a
one-sided assertion: a clamp that always returns `now` satisfies "no
endpoint is in the future" and destroys every historical range; a
`resolve()` that ignores its cache satisfies "the cache is never a
shortcut" and has no fallback at all; an `overlay()` that returns its
base unchanged satisfies "the total is not the platform's" whenever the
two happen to agree.

**Two assertions exist only to prove the others were reachable (DP87).**
The measurement plan must still carry one range ending later than `now` -
without a request that still has the defect, E1 is measured against
nothing - and the reading plan must carry two genuinely different ranges,
or the overlay lays the year range over itself and corrects nothing by
construction.

**The corrections are held whether or not the platform still misbehaves.**
Re-measured here on 2026-08-13, E1 and E3 did not reproduce (DP101). That
is recorded as a finding about the platform, not as grounds for dropping
the corrections: a range ending later than now is wrong whether or not it
is currently answered wrongly, and E3's whole lesson is that this
behaviour was not predictable from first principles in either direction.

## Rule 21: a degraded note is retried, never held

DP49, stated as the thing that happened rather than as a principle:

> An honest fallback that is never re-checked is a failure that has been
> silently timestamped.

Upstream, a provider's quota ran out, the run wrote a degraded result into
the day's slot, and the scheduler compared **dates**. The quota came back
an hour later and the degraded result held the day, because something was
already recorded for today. From the outside that is indistinguishable
from success: a file exists, it is stamped with today, and the only way to
learn it is wrong is to open it.

The static half refuses four shapes in `murscope/daily.py`: a scheduler
that never reads what is *in* the slot; one that never consults the moment
a degraded result becomes worth asking about again; one that cannot answer
both ways; and a degraded record written with no retry moment, or a
backoff with no ceiling.

**A backoff is a hold with a timer on it**, which is why the ceiling is a
rule and not a default. `retry_after_seconds` is a real setting - a user on
a flaky link may want a longer one - and without `MAX_RETRY_AFTER_SECONDS`
a config file could rebuild the upstream failure exactly, holding the day
with a degraded result, and it would look like a preference.

The live half drives the whole loop and **it drives it on the product's
own state**: a degraded slot produced by `record_degraded()`, written by
`write_slot()` and read back by `read_slot()`, asserted to have come back
degraded and carrying a moment *before* anything is concluded from it
(DP87 - a hand-built dict would satisfy "a degraded slot is retried"
without the scheduler having a degraded slot to look at). Then: it is not
attempted before its moment, it is attempted after, an ok slot is not
attempted at all - without which a scheduler that always says yes passes
everything else - and an empty slot is not a hold.

**What this rule does not cover, said rather than assumed.** It measures
when a request happens, never what the request does. No socket is opened
by the check and no adapter is driven: the transports are Rules 18, 19 and
22's, and the live round trips are the acceptance report's.

## Rule 22: a note adapter sends only what the disclosure declares

`outbound.build()` refuses a payload leaf the table does not declare, and
that covers the document murscope builds. **It does not cover what an
adapter wraps around it.** A vendor envelope is exactly where a `user`
identifier, a session id or a second system prompt would sit, and none of
them would ever reach `build()`.

So the table has a `request.envelope` row, and this rule holds the
adapters to the sentence in it: the model name, the role labels and length
limit the API requires, and a flag asking for one complete answer rather
than a stream. That sentence is a set of four keys in the check, and an
adapter that emits or declares a fifth goes red - the cost of widening a
request charged where it is incurred, because adding a clause to that
sentence invalidates every recorded consent.

Both directions, because each has a degenerate form: declaring five keys
and sending three describes a request nobody makes, and declaring three
and sending five makes one nobody was shown.

**The payload has to actually be in the body (DP87).** The live half
builds a real payload carrying a decoy project id, calls each adapter's own
`body()`, and asserts the canonical payload appears in it exactly once and
the decoy appears nowhere else. Without the first, "no key outside the
vocabulary" would be equally true of an adapter that sends an empty
document. `body()` is a named pure function in every adapter for this
reason: a request shape that can only be inspected by making the request
is a request shape nothing can check.

## Rule 23: an untested provider is reported as untested

DP89, and it is a rule rather than a convention because of what breaking
it costs:

> A provider that has never completed a live round trip is not delivered.
> It is written and it is honestly labelled as untested, with the reason.

Four adapters ship for the daily note and at M3's fourth stage one of them
had ever spoken to a model. **Four rows under one heading with no evidence
column read as four working providers** - a reader supplies the missing
claim themselves and is not wrong to, because a list of four things under
one heading is a list of four things of one kind.

So evidence is data on the provider rather than prose in a commit message:
each adapter declares `EVIDENCE` and `EVIDENCE_NOTE`, passes both to
`register()` rather than inheriting a default, and the listing prints the
value in a column of its own. A note that repeats the label is refused -
"unproven" and "unproven, because no key for this vendor was available and
DP89 refuses a stub standing in for one" send a reader to two different
places.

The live half loads the real adapters, drives the real listing, and
asserts every provider's name *and* its evidence value appear, then counts
the distinct values declared against the distinct values printed. That
count is the assertion this rule is named after: every row can be present
while the distinction between them is not.

**What it cannot do, stated rather than implied.** Nothing static can
verify that a provider labelled `live` really completed a round trip. What
is enforced is that the claim is explicit, per provider, with a reason.
The round trip belongs in the acceptance report, which is where DP89 put
it.

## Rule 24: a read window and its permits stay paired

DP114. `murscope selftest` records every file it opens and asserts that
each one is inside a permitted root. That assertion has been wrong four
times, and the first three were all the same shape: **the window was
narrower than the sentence describing it**, so a read planted where the
window did not reach came back green. Each fix widened the window, until
it was the whole run - opened on the first line of `main()` and never
closed.

The fourth was the mirror image, and it lived inside the fix for the
third. Two steps asserted over that same whole-run window, each assembling
its own list of permitted roots by hand, and the two lists differed by
exactly the projects the roster names. So on any machine that had run
`murscope init`, step 4 read a listed project on purpose and step 7 called
it a stray read:

> `MURSCOPE_HOME=<empty roster>` → exit 0.
> `MURSCOPE_HOME=<roster of 1>` → exit 1, and one FAIL line per file read.

`selftest` was red for every user with a roster and the gate never saw it,
because the gate ran the selftest against a throwaway home with no roster
in it. **A guard nobody's discipline walks past is not a guard**, and this
one had been off that path for five milestones.

> The window and the permitted set are one object's two halves, and no
> step may state either half on its own.

`ReadWindow` holds both. `opened()` is the only place `since(0)` is
written; `strays()` is the only caller of `_stray_reads`; every assertion
calls `strays()` with no arguments; and a root joins the permitted set
through `permit()` **where it is acquired**, in front of the read it
permits, rather than travelling to one assertion as a return value and
missing the other.

The check refuses every other shape statically and then probes the shipped
object live - a read inside a permitted root must produce no stray, and
the same read with the permit withdrawn must produce exactly that stray,
because a `strays()` that ignored its permitted set would satisfy every
static rule and report a clean run for a process reading anything.

**What this check does not cover, measured rather than assumed (DP122).**
Its permit assertion is a floor - two call sites at least - so deleting
one of the roots the selftest permits leaves it printing OK with a count
one lower. The guard against that deletion is the selftest run itself:
every `permit()` site in `murscope/selftest.py` was removed in turn and
both gate runs measured, and each removal turns one red. The sites
registering a sandbox this run built redden both runs; the two registering
a root the roster named - `MURSCOPE_HOME`, and the projects step 4
collects - are green on the empty roster and red only on the non-empty
one, which is DP114 restated and is why the gate runs the selftest twice.
This paragraph replaces a sentence claiming two independent reds, which
nobody had run the case for.

**The narrowed half is probed with a simulated prefix, because the
interpreter it is about is not in the matrix (DP117, DP118).** Apple's
`/usr/bin/python3` sets `sys.pycache_prefix` under the user's home, which
is under no permitted root, so the assertion called the interpreter's own
bytecode cache entries stray reads of a project *there and nowhere else*.
Permission is by name, never by tree: a cached `.pyc` and the
`<name>.pyc.<id>` CPython opens before renaming it are permitted, and a
README, a source file, a `.pyc.<not digits>` and a `.pyc` outside the
prefix are not. Both names matter - the first repair permitted only the
one ending in `.pyc`, which made the guard red on the first run after any
code change and green on the second. **A guard that is red only on the run
right after an edit teaches the reader to run it twice**, and that is how
somebody learns to ignore a real one.

`scripts/run_checks.py` also runs the selftest **twice**, the second time
against a roster naming a fabricated project written outside
`MURSCOPE_HOME` - asserted to be outside it, because a fixture inside the
home is permitted whatever the roster says and the second run would then
measure nothing the first did not.

## Rule 25: every transport bypasses the proxy the same way

DP111 made the network route a decision: each transport builds its own
opener with `ProxyHandler({})`, so a payload consented to for a named
destination cannot travel through a machine the consent screen never
showed. Rule 19 refuses a *new* transport that ships without the bypass.
This rule is about the six that have it.

The bypass is written out once per transport, six times, byte for byte the
same. M3's acceptance window hit the consequence directly: it edited
`network.py` to change the route and `murscope contributions` did not
change, because `github.py` carries its own copy. **Five copies can be
corrected while the sixth is not**, and the sixth still opens a socket
under a consent taken over a destination it does not reach - and none of
that appears in a diff of the file somebody did edit.

> The copies stay, and they may not drift.

The duplication is a decision, not an oversight (DP116): a shared
`_transport` module would take `urllib` out of each adapter's own imports,
and `boundary.socket_capable` reads exactly those - the selftest's
provider-boundary step and the board's promise footer would then report
every one of those adapters as opening nothing. That is a promise-level
surface, and trading it for tidiness is the wrong way round.

**The retirement condition is re-measured on every run, not remembered**
(DP148). It was written down - consolidate when `boundary.socket_capable`
can follow a relative import one level, so a shared module is still
reported as socket-capable on every adapter that uses it - and a condition
living in a paragraph is a condition whose arrival nobody notices, which
is DP81's shape. The check now hands the shipped survey two synthetic
modules: one importing `urllib.request` absolutely, one importing a
sibling with `from ._transport import opener`. **Both answers are
assertions.** The absolute probe finding nothing is red, because the
retirement probe would then be measuring a broken instrument rather than
an unmet condition. The relative probe finding *something* is red too:
that is the condition arriving, and the copies are due for consolidation
the same day.

Until then the check pins every copy to one digest and requires each
`_opener` to **call** `ProxyHandler` in code that runs, with a floor of
six so that a run finding no copies goes red rather than reporting that
all zero of them agree. Seven ship today; the floor is a floor.

**"Call", because the first version accepted a paragraph (DP120).** It
asked `ast.dump()` whether the string `ProxyHandler` appeared anywhere in
the function, and `ast.dump()` renders the docstring - in which
`` `ProxyHandler({})` is an explicitly empty proxy map `` is written out.
All six openers were changed to a bare `build_opener()`, the docstrings
left alone, and this check printed OK over six identical copies of code
that has no proxy map in it at all; delete only that sentence and it went
red. **The third time a check here has mentioned the thing instead of
testing it**, after Rule 7 reading a word out of a comment and M2's
truncation assertion counting dots instead of sentences - and this one was
inside the check written to stop exactly that. Every route assertion in
both rules now reads `ast.Call` nodes, which a docstring cannot contain.

## Rule 26: the timer collects and cannot send

M4 introduces the first thing this product does with nobody present.
Every network call M3 shipped had a person in front of it: a consent
screen read, a `yes` typed, and the send in the next second. A timer
removes that adjacency, so DP124 ruled what may be on the other side of
it - **the scheduled job collects and renders, and it cannot send.**

Not "does not send". *Cannot*, and not by configuration: DP88 settled
that a capability the user has to go and audit a setting to rule out is a
capability that is on. So the statement is about the call graph, and this
is what makes it checkable:

- the scheduled job runs its **own console script**, `murscope-timer`,
  which takes no arguments and refuses them. `murscope run` would not do:
  `murscope` is an argv dispatcher and `daily --send` is one word away,
  in a job description written once and re-read by nobody;
- from `murscope.timer:main` there is **no resolvable call path in the
  package that reaches a transport doorway**.

A doorway is computed rather than listed, which matters because Rule 16
forbids the core from naming a provider at all - a name-based rule here
would find nothing to name. Three kinds count: every function in a module
that imports something able to open a socket (the six `[ai]` adapters);
`registry.readers()` and `registry.writers()`, the core's only two ways
to lay hands on a transport; and any call of `.reads(...)`,
`.writes(...)` or `.send(...)` on a value, which is how a resolved
provider is driven and is where a static walk has to stop and call it
arrival.

**M4's second stage added a third lookup, `registry.alerters()`, and a
fourth attribute, `.alerts(...)`.** That is this rule widening rather than
relaxing: an alert is the one payload this product will send with nobody
present (DP125), and the exception for it is a *different entry point*
held by Rule 27 - never a loosening of this one. A timer that could call
`registry.alerters()` would be a timer that could send.

`provider.contribute(...)` is the one dynamic dispatch the timer's path
really makes, and it is not left as a hole: every provider module is read
for its `register(...)` call and whatever it passes as `contribute` joins
the walk as a root. A `contribute` the check cannot resolve to a function
is a finding, not a shrug.

**The way this check could be worthless is by walking nowhere** (DP87),
so three floors are asserted before any verdict: the entry point exists,
the walk passes through `cli.run`, `cli.collect_records`,
`collect.collect_project` and `render.render`, and the doorway set still
holds the three registry lookups and at least three core doorways. Any of
them failing is red.

## Rule 27: the alert entry point sends only the alert

DP125 ruled that an alert **may** leave the machine while nobody is
present, because an alert that only reaches the Mac you are sitting at is
not an alert. That collides with DP124 head on, and the resolution is an
exception that is stated rather than a hole that is silent. **The
difference between an exception and a hole is whether anything measures
its edges.** Rule 26 measures one edge; this rule measures the other.

The shape is DP127's, arrived at from the other end. The timer got its own
console script because a flag on `murscope` is one word away from `daily
--send`; the alert job gets its own for the mirror-image reason - a flag
would put both capabilities on one call graph, and then neither rule could
say anything about either. So `murscope-alert` runs `murscope.alert:main`,
takes no arguments and refuses them, and from it:

- `registry.alerters()` and a `.alerts(...)` call on a value are
  **permitted**. Delivering an alert is what this entry point is for;
- `registry.readers()`, `registry.writers()`, `outbound.build`,
  `outbound.canonical`, `outbound.payload_digest`,
  `contributions.reading_documents`, `contributions.measurement_documents`
  and every `.reads(...)`, `.writes(...)` or `.send(...)` call on a value
  are **forbidden**. Each of them is a payload agreed to on a different
  disclosure under a different fingerprint.

So "the only thing this entry point can put on a wire is an alert" is a
property of the call graph, read on every gate run, rather than a
paragraph anybody has to believe.

**The way this check could be worthless is by walking nowhere** (DP87),
and here the quiet failure runs in the convenient direction: an entry
point that resolves to nothing reaches no forbidden target either. Four
floors are asserted before any verdict - the entry point exists; the walk
passes through `cli.alert_command`, `cli.collect_records`,
`alerts.evaluate` and `alerts.build`; the walk **does** reach
`registry.alerters()`, because a product where an alert can never leave
satisfies every prohibition here for the wrong reason; and every forbidden
name still resolves to a function that exists, because a prohibition over
a renamed name forbids nothing.

## Rule 28: a machine acting consent says so on screen

This product now records **two consents of different strength** (DP125).
The daily note's and the reading's are completed by a person on each send:
a screen is read, `yes` is typed, and the request happens in the next
second while that person is looking at the answer. The alert's authorises
a machine to act alone, from then on, at moments nobody is present. Both
are recorded by the same command, into the same directory, in the same
format.

**A user has to be able to see which one they are giving.** That is a
claim about printed text, so the check renders the screens and reads them
the way a person would - `murscope consent show`, not the shape of the
module behind it. Four things are asserted:

- every disclosure this build can show carries a `who sends` line, printed
  directly under `this is` and above the field table;
- the alert's line differs from every other one. Two screens describing
  the same act are two screens a reader cannot tell apart;
- the alert's line says murscope sends it on its own **and carries the
  owner's own phrasing, `this one leaves while you are not here`**. DP125
  records that wording as the requirement rather than as an example, and a
  check that accepted any sentence would assert that some words are
  printed rather than that these are;
- the person-completed screens say the person sends, and do not claim
  otherwise. The distinction has two ends, and a rule that read only the
  alert's screen would stay green through an edit that made the daily note
  claim to send itself.

The screens are rendered against a throwaway home holding a fabricated
roster with one sensitive entry, so the alert screen's id listing is
exercised rather than skipped, and the number of screens read is asserted
against `cli.known_disclosures()` - a render that produced nothing would
otherwise report green about nothing (DP87).

## Rule 29: the terminal table is measured in cells

A column is a promise about where the next column starts. `%-38s` pads to
38 **characters**, and a terminal draws a CJK ideograph in two cells, so a
`zh` table padded that way begins its next column somewhere different on
every row. Measured before the fix, on four `zh` rows of `murscope init`'s
summary screen: the ledger column at one *character* offset of 70 and at
three *cell* offsets - 75, 76 and 80 - with the rows 81, 82 and 86 cells
wide (DP86). Through `murscope.width` the same four rows give one cell
offset, 70, from three character offsets - 60, 64, 65 - and every row
exactly 76 cells. Nothing on that screen was untrue, which is why it was
filed rather than blocking a gate, and it stayed crooked for two
milestones.

Every cell of that table now goes through `murscope.width`, which counts
`unicodedata.east_asian_width` rather than characters, and clips and pads
in the same unit. The pairing is the rule: the original defect was a clip
measuring one thing beside a `%-*s` measuring another, so a sentence
trimmed correctly was still padded to the wrong place.

The check is judged on **rendered text**, not on the shape of the code:
`wizard._header` and `._row` are called for real, once per locale the
build ships, and three things are measured - the last column starts at one
cell offset across the heading and every row, rows sharing a last column
are one width, and the sub-text hangs at the cell offset of the state
column above it rather than at a character count.

**The fixture has to reach the code, and the floors are per locale.** Each
locale's own rendering must contain a wide name, an accented Latin name,
an ASCII name, a clip, and a row whose sub-text wraps; a table of ASCII
cases satisfies every assertion above while exercising nothing (DP87).
Pooled across locales those floors were answered by `zh` and `fr` on
`en`'s behalf, and taking the wide name out of the fixture entirely left
the check green - which is the same failure one level up.

What this rule does **not** claim: that no other column anywhere is padded
by character count. Deciding that statically means deciding which `%-*s`
carries a rendered value and which carries an identifier - `expand()` pads
a tier name to eight and is right to - and DP67 priced that class of
scanner at negative. The guard is behavioural and anchored to the one
table that renders locale strings; a second such table is added to the
check by name, the way Rule 8's heading was.

## Rule 30: the board renders every row it is given

The board is the product's one deliverable and, until this rule, nothing
in this repository ever executed it. DP85 recorded the small half: re-gate
the `state.also` loop behind `st.kind === "inferred"` - the exact
regression DP80 exists to prevent - and the gate stays green. Re-measured
at M4 stage four, with the gate at 29 checks and the selftest at twelve
steps, that was still true. **The large half is worse.** Delete the
`rows()` call from the template's entry point, so the board draws no
project rows at all, and the gate was 29/29 green with `murscope selftest`
green on both roster shapes.

> Three hundred and thirty lines of JavaScript decided what a reader saw,
> and `render.py`'s payload was the only half anything checked.

**So the page is executed, and a JavaScript engine is a development
requirement of the gate** - `node`, `deno` or `bun`, whichever is on
PATH. It is never a requirement of murscope: ADR-0001 stands, the package
has zero runtime dependencies, ships no toolchain, and a user opens the
board in their own browser exactly as before. With no engine present this
check is **red, not skipped**: a check that quietly stops running is the
failure the whole gate is built against, and "zero skipped" is an
acceptance criterion.

The DOM is a shim implementing the nine operations the template actually
uses. Anything it reaches for that is not there raises, and the check goes
red naming it - which is the right answer, because a board needing a tenth
operation is a board the shim no longer models. The element ids are parsed
out of the shipped HTML rather than invented, so a `<div id="tiles">`
renamed in the template makes `getElementById` return null and the page
throw: template-and-script drift caught as itself.

**The fixture's floors, because a page renders whatever it is given
(DP87).** Eight projects in every locale the package ships, and the check
refuses to believe its own answer unless all four state kinds are present,
**two rows carry a quotation headline *and* a non-empty sub-text** (DP85's
own case - a fixture whose declared and curated rows hold nothing cannot
see that injection), one project is sensitive and one is not, one overlaps
`MURSCOPE_HOME`, one is `MISSING`, and the payload carries a problem line.

**Red line four is carried here by the assertion that can fail.** The
obvious one - "a sensitive project's withheld content is nowhere on the
page" - cannot fire at this layer and would be DP143's shape exactly:
`render.build_document` runs `collect.shield(..., strict=True)` before the
template is handed anything, and that *raises* on a non-whitelisted key
rather than filtering it. So what is asserted is the boundary still
refusing, and the page-level absence is its consequence rather than a
second unfireable claim.

Fifteen injections were built and run before this check was believed, and
**two of them were green on the first pass**: the badge asserted by text
was answered by the state chip rendering the same word, and "the sensitive
row has some chip on it" was answered by that same chip. Both are DP143's
fourth injection again - a floor standing on something the renderer had
already put there - and both are now asserted as elements.

## Rule 31: the module matrix names what it could not ask

`murscope modules` prints what `registry.register()` has carried since M3:
what is installed, what configuration enabled, what each module reads,
writes and alerts to, where it sends and whether it has ever completed a
round trip. **Its sentences are as much of the deliverable as its rows**,
because the one accounting sentence this product had shipped about
provider modules was wrong (DP115).

The rule is that three states are told apart and never collapsed:

| the module | the column says | because |
|---|---|---|
| enabled, imported, and does not do this | `no` | it declared itself |
| not imported | `unknown` | nothing asked it, and importing it to find out would be running a provider configuration did not name (Rule 13) |
| named by configuration, not on disk | its own row | it is a configuration line pointing at nothing, not a module that does nothing |

A dash in the second row would be a statement, and the statement is the
one DP115 got wrong. The `socket` column is deliberately outside the
scheme and the matrix says so: `boundary.survey()` **reads** each module's
source instead of importing it, so it is known for every module on the
disk including the ones nothing ran.

**What walks into this check (DP87).** The shipped matrix is driven in a
fresh interpreter against a synthetic provider directory, never against
whatever is installed on the machine running the gate - a base install has
one module and could not exercise a single state. Four modules: one
enabled registering **a reader and no writer** (DP115's own module), one
enabled registering a writer, one socket-capable and not enabled, one
neither; plus a fifth name in `enabled` that is not there. It is driven
**twice** - once configured, once with `enabled = []` - because the
install whose whole table is `unknown` is the one the old accounting
returned early on, and a single configured run never reaches that branch.
The command is driven in the same interpreter and each module must appear
as its own table row, not merely somewhere in the output: the looser form
was green with every un-imported row dropped, because the sentences below
the table name those modules too.

## Rule 32: the skill names only commands this build has

`skill/SKILL.md` ships from this repository rather than its own (DP1, N1,
DP151). Its whole content is instructions naming this command line, and
in a separate repository nothing would notice a renamed command; here that
is a check, and a skill verified against the build beside it is worth more
than one with its own release cadence.

**What it adds over `pipx install murscope`** is one thing and it is not
convenience: **murscope never writes into a monitored project and an agent
can.** The most useful row on the board is a project's own status line,
quoted rather than guessed; the CLI will not author it and will not put it
on disk, because red line one is what lets somebody point this tool at
twenty repositories without auditing what it did to them. The skill is the
half that interviews and writes (DP14: a shell, not a fork; DP27:
bootstrapping a ledger belongs to the skill and the CLI never writes).

Two properties, both structural:

1. Every `murscope <command>` the skill names **in code** - a fenced block
   or an inline span - is dispatched by this build, read out of
   `cli.implemented_commands()` in a fresh interpreter rather than from a
   list kept beside the check. Scanning the whole document instead was the
   first version and it reported `murscope writes` and `murscope had` as
   missing commands; the repair would have been a growing list of English
   words that are not commands, which is the proxy DP67 priced at negative.
   Where a command appears is a structural fact about markdown.
2. The skill contains no instruction to send. `--send` and `consent grant`
   are refused by exact string, except on the lines that forbid them. **An
   agent recording a consent is the failure the whole consent mechanism
   exists to prevent**: a consent is recorded against the exact fields the
   screen showed, and agreeing on somebody's behalf to a disclosure they
   did not read empties it.

Floors: at least four distinct commands and `init` among them, because
"every command it names exists" is true of a page naming none; and each
forbidden string must still appear in the product, so a denylist that
stopped matching anything real goes red rather than passing forever.

## Rule 33: no command acts on an argument it could not read

**A question about a command was answered by running it (DP155).**
`murscope open --help` opened a browser. `murscope alert --help` collected the roster and
wrote an alert snapshot; `murscope run --help` built the board; `murscope
init --help` began scanning the user's home directory for projects. Only
`murscope timer` recognised the word - every other command took `--help`
as an argument it had no use for, ignored it, and did the thing. The
window that found this made a file in the owner's real `~/.murscope` while
doing nothing but asking what a command was.

**The quiet half is every other unrecognised flag.** `murscope alert
--sendd` collected, delivered locally, and never said that the word it was
handed was not `--send`. The failure direction was safe - a misspelling
could only ever send less - but a command that silently does something
other than what was typed leaves no line anybody can read back to what
they asked for, and the next flag to be misspelled need not fail in the
safe direction. The two entry points that run unattended already refuse an
argument loudly and exit 2; the dispatcher was the surface that did not.

So an argument this build cannot read is **answered, never acted on**, and
one place decides that for every command rather than fifteen commands
each deciding for themselves:

- every command answers `-h` and `--help` with its own usage, exits 0, and
  writes nothing. The usage text is read out of the help screen, for the
  reason `implemented_commands()` is - two copies of a fact drift, and the
  copy nobody prints is the one that goes stale;
- every command that takes flags refuses one it does not recognise, exits
  2, names the flag, and writes nothing;
- `note` is the one command not asked to refuse a word, and that is a
  category rather than a favour: everything after the project name is a
  sentence the user writes about their own project, and "- waiting on the
  vendor" is not a flag.

Measured by **running** the commands, not by reading the dispatcher. Each
goes into a subprocess with `HOME` and `MURSCOPE_HOME` both pointed at
throwaway directories, hashed before and after: what a command *wrote* is
the evidence that it acted, and a source scan cannot produce it. Pointing
`HOME` at the throwaway matters as much as `MURSCOPE_HOME` - the shape
being refused is `init` with no path, which walks the conventional project
directories under the user's home, and a check that reproduced the defect
by scanning somebody's workspace would be worse than the thing it checks.
The command list is `cli.implemented_commands()`, so a command that lands
in this build is exercised without anybody remembering to add it here, and
a run covering fewer commands than the build declares is red.

## Rule 34: the brand name is never transliterated

The product has **two** names. In Latin letters it is `murscope`. In
Chinese it is two characters, written as themselves and escaped, because
Rule 3 keeps every tracked file ASCII. Neither of them is ever replaced
by the other, and neither is ever spelled out: no romanization, in any
system, and no translation into English words.

**A romanization is a third name, and a product with three names has
none.** A reader who meets the spelled-out form cannot get from it to
the Chinese one, cannot get from it to `murscope`, and has no reason to
believe the three are the same thing. This is the argument `BRAND.md`
makes to a fork - one name, one product, or the promises on the front
page stop meaning anything - turned inward and applied to us.

This rule was in `CLAUDE.md` and nowhere else until now, and `CLAUDE.md`
is the file an agent window reads. A contributor reads this one.

**The check generates the forbidden spellings; it does not list them
(DP154).** A list would name the ordinary Hanyu Pinyin form, hyphenated,
spaced and camel-cased, and would be green until somebody typed the next
spelling - and there are at least four romanization systems in ordinary
use, two tone notations, and a handful of joiners. That is the
reviewed-by-eye table DP154 was about. So the seed is the brand's
**syllables**, one entry per brand character in a neutral (initial,
final) key, and each system is a mapping from those keys to letters.
The spelling space is computed: systems x tone notations x joiners x
case, and the cross terms fall out, so a form that mixes two systems is
caught without being enumerated. Teaching it a fifth system is one table
row; a brand that gained a third character needs that character's
syllable and nothing else.

The seed gets the treatment Rule 5's permitted-path table gets, for the
same reason: a syllable table that has stopped describing the brand, or
that names a key some system cannot spell, would generate a smaller
space in silence. Both are findings. And the brand's own escaped code
points have to be **somewhere in the product** - not in the check, which
declares them and would otherwise vouch for itself - or the rule is
guarding a name the repository no longer carries and every scan below it
is vacuously clean (DP87).

**The mechanism has a floor, and it is measured rather than assumed.** A
single Mandarin syllable romanizes to two or three letters and a few of
those spellings are ordinary English words; two syllables joined are not
English by accident, and that is the whole reason this works. Trimming
the syllable table to one entry and re-running was the measurement: two
shipped fixtures matched. So a brand of fewer than two syllables is
itself a finding - it would need a different criterion, and a check that
started reporting prose would be loosened rather than obeyed.

**Two things it does not do, stated rather than implied.** A
*translation* is ordinary English on the page and no mechanism this
repository could carry would recognise it; that half is this paragraph
and is not claimed by the check. Gwoyeu Romatzyh spells tone into the
syllable rather than marking it, and is not generated - named here so
the gap is a known one rather than a surprise.

**Commit messages are scanned too**, because a public repository carries
its history and a name spelled out in a subject line is as permanent as
one in a file. What is *not* checked over history is the English-only
half: this line's history carries one subject written in Chinese, and it
is not being rewritten. DP160 founds the public repository from a clean
tree, so it inherits none of those subjects, and rewriting a shared
branch to make a check pass is the habit Rule 2 already refuses.

**This section cannot show you an example of what it forbids**, for the
reason Rule 12 cannot name a telemetry vendor: the check scans every
tracked file, and this is one.

## Rule 35: the public tree has no dangling reference

DP160 ruled that the release is a **second repository**, founded from a
clean tree. The owner's ruling that the management console and the
milestone task books do not go into it turns that repository into
something this one has to be able to state precisely, because it is not
a copy with two directories missing:

> The public tree is not a subset of this one. It is a transform.

Sentences here point into those two directories, and every one of them
is **correct here**. A layout table row names the console. Rule 4 names
four governed directories where the published tree has two. A check
walks a tuple of directory names against the repository root and two of
them would resolve to nothing. Published as-is, each becomes a pointer
to something absent - the exact class of defect this file has spent five
milestones catching in its own prose, arriving from the one direction
nobody was watching.

**This section names neither directory**, for the reason Rule 12 cannot
name a telemetry vendor and Rule 34 cannot print a spelling: it is
published, it is scanned, and a rule that violated itself in its own
statement would have to be exempted from itself. They are named once, in
the exclusion table, which is Python and is read as data.

So the derivation is written down in `scripts/public_tree.py`, in three
tables: **what does not go**, each with the reason; **what is rewritten
on the way out**, each with the reason; and **what is regenerated**
rather than copied, which is the freeze manifest, because a rewritten
file has a different hash.

Inclusion is the default and exclusion is the enumerated case. A
manifest that listed what to *publish* would silently drop every file
added after it was written, and the drop would read as a decision
somebody took; so the extraction refuses a tracked file it cannot
classify. No count of files appears in the spec - the numbers are
measured off the extraction and printed (DP159).

**The check runs the derivation and reads the result** (DP87). It is not
a static reading of the tables and not a grep over this repository: the
tree is extracted into a throwaway directory, and every reference in it
is resolved against it. A **dangling reference** is one naming a path
that is in this tree and not in that one.

What counts as a reference is a category, never a list of files: in
markdown, a path inside a code span or a link target; in Python, a
string joined onto the tree root - `ROOT / "x"` - where `ROOT` is a
module-level name bound to an ancestor of `__file__`, or to another such
join. The operand may be a literal or a module-level string constant,
including one reached through `for name in CONSTANT:`, which is how the
governed-docs check names the directories it walks. That last shape is
the one that makes the Python half worth having: the only non-prose
rewrite in the spec is the tuple it reads.

**And what the category deliberately excludes.**
`murscope/fingerprints.py` holds a dozen ledger paths, two of which name
directories this repository has. Those are **product data** - the table
by which murscope recognises a ledger in somebody else's project - and
they ship exactly as they are. The criterion separates them without
naming them: they are strings in a tuple, never joined onto this tree's
root. The same holds for the toy repositories `scripts/make_toy_repos.py`
writes.

**The rewrites are idempotent, and that is load-bearing.** Each is
satisfied either by the text it removes being present or by the text it
leaves being present already, so the public tree can run this extraction
on itself and stay green - which is what lets this rule ship in the
public repository instead of being one more thing that only works here.
What it still catches is the failure worth catching: a document edited
until neither form is there, so a rewrite that used to fire now quietly
does nothing.

**A path is not the only thing a reader is asked to resolve**, and the
pre-publication audit found the blind spot: both halves above read
*paths*, so eight commit hashes and two pull request numbers sat in a
check script and went straight into the extracted tree with neither half
noticing. None of them exists in a repository founded from a clean tree,
so the gate was red on its first run there - and a gate that is red on
day one teaches a reader to ignore it, which is worse than the thing it
was guarding.

So there is a third half, and it reads **coordinates**: a hex token that
resolves to a commit in this repository; a pull request citation; and a
section number into a document that is published nowhere, which is the
form the docstrings used until M5 (see "What the citations point at").

That half is the interesting one, because when the tree is clean it is
*expected* to find nothing, and "found nothing" and "was looking for the
wrong thing" print identically. It therefore proves itself instead: each
matcher is fired on a known positive **assembled at run time**, never
written into the file - a literal there would be found by the scan and
the fix for that is an exemption - and the commit resolver is proved
against this repository's own HEAD before any token from the extracted
tree is put to it. That is the discipline the audit itself demonstrated,
having once reported a spelling covered because it had misspelled the
probe.

**Three halves read two file types, and that was the whole of it.** The
first read `.md`, the second read `.py`, the third ran over whatever
those two had already opened. Everything else in the published tree -
the ignore file, the workflow, the packaging table, the locales, the
board - was read by nothing at all, and the second pre-publication audit
found what had been sitting in that gap. A comment block describing the
owner's private material by category, naming a second private repository
and a file inside a withheld directory. A step that fails the job on any
repository whose visibility is not `private`, in the repository that is
public by construction. A link to the development repository itself.
None of it was hidden and none of it was subtle: two constants, one
holding `.md` and one holding `.py`, were the entire reason no half
looked (DP169).

So the file-type restriction is gone. **Every file in the extracted tree
that decodes as text is read**, and the reader is chosen by what the file
is rather than the file being skipped for want of one. Markdown and
Python keep the readers they had. Everything else gets a **plain-text**
reader, which has no code spans and no syntax to lean on and therefore
looks for the one shape that needs neither: a path-shaped token whose
leading component is a directory the derivation withholds. That is
weaker than the two readers it stands in for and is not trying to be
them - it is the difference between reading those files and not reading
them. The prefixes are generated from the exclusion table, never listed
in the check, so the two cannot drift apart with the copy that fell
behind staying green.

**And a half that reads repositories rather than paths.** A URL resolves
against the internet and not against this tree, so no path half can see
one - normalisation throws away every token carrying a scheme, by
design. The category is stated positively: **a published file may name
the repository it is in, and no other repository on its host.** Which
repository that is comes from the clone's own `origin` rather than from a
constant; which tree this is comes from the derivation spec, the way Rule
36 asks the same question. Run from the development repository, the tree
being scanned is a derivation destined for somewhere else, so the set of
repositories a file in it may name is empty and every link on the
hosting domain is a finding - including the one naming the development
repository, which is what the audit found. Run from the published
repository, the derivation is idempotent, the tree being scanned *is*
that repository, and a link naming it is the one link that is fine.

Taking the host from `origin` too is what keeps a provider endpoint and a
document type definition out of it: both have the shape of an owner and a
repository, neither is on the hosting domain, and the criterion never has
to guess. **What it does not cover**, stated rather than implied: a
repository named in prose without a URL. A bare `owner/name` is a shape
ordinary sentences have, and a matcher that fired on one would be
loosened within a week - the same limit Rule 37 states about a given name
on its own.

**What a check can hold here, and what only a reading can.** Two of the
six findings in that audit were references - a path and a link, both
now caught. The other four were sentences **true of the repository they
are written in and false of the repository they are published into**: a
declaration that this repository is never made public, sitting in the one
that is. No scanner settles that, because it is not a fact about the file
in front of it. Those are found by reading the extracted tree as a
stranger before anything is published, and the rewrites answering them
are in the spec with the reason attached. The check is why the audit no
longer has to find the path-shaped ones by eye; it is not a reason to
stop reading (DP170).

**The first two halves must resolve something**, or a scanner that found
nothing would report a clean tree with the same confidence as one that
found everything. Each has to come back with at least one reference that
resolved. The plain-text and repository halves are silent ones and prove
themselves the way the coordinate half does - fired on a known positive
assembled at run time, here from the live seeds, so that a prefix which
has left the exclusion table or a host which has moved stops being proved
rather than being proved against something stale.

**One table exists only because of the third half.** A rewrite that
removes a commit hash has to quote it, so the literal rewrite table
publishes exactly what its own rewrite takes out - and the check found
the spec rather than the check script it targets. Making the spec
rewrite itself only moves the quotation up a level. `REGEX_REWRITES`
holds the rewrites whose `find` is a **category** instead: the shape of
a founding boundary, the shape of an enumerated table. Same tuple, same
idempotence, and no history named anywhere.

**What this rule does not cover, so nobody reads it as more.** It says
nothing about a path that is in neither tree - that would be wrong here
too, and this rule is about what the derivation does. And it does not
run the extracted tree's own gate: that is the pre-publication audit
DP160 puts before the repository is created. That audit has now been run
once, and what it found is in this rule and in Rules 36 and 37.

Nothing here creates a repository, pushes anything or tags anything.
DP160 puts all three behind an owner ruling and that audit.

## Rule 36: publication is a derivation, never a switch

Every other irreversible thing in this line is a file, and files have a
diff, a review and a gate. **This one is a setting.** DP160 ruled that
the release is a second repository founded from a clean tree - the one
you are reading - and for five milestones that ruling was the only thing
standing between a settings page and a development repository's whole
history being readable in one click. No check, no CI step, no repository
configuration. A decision, not a gate - the wall art Rule 1 has refused
since the first commit, hanging on the wall of the repository that
refused it.

`PUBLICATION.md` is the ruling written down, in a block a machine reads:
`Switch: never`, and a `Mechanism:` naming the file that holds the whole
derivation.

The check asks three questions, all of them offline.

**Is the declaration there, and is it a fiction?** A `Mechanism:` naming
a file that exists is not enough - the named module has to expose the
derivation itself, `EXCLUDED`, `REWRITES` and `extract()`, or the
declaration is true in wording and empty in fact.

**What would the switch release?** Measured from history and printed, so
the number is in front of whoever is deciding. Not the working tree: the
whole history, and history is wider than any branch. GitHub keeps a head
ref for every pull request ever opened and a reader fetches all of them
with one refspec, carrying the pre-squash commits that a normal clone's
`git log --all` cannot see - so the local counts are a **floor**, they
say so, and the check prints the fetch that raises them. No count is
written into `PUBLICATION.md`; a hand-written number is a claim, not a
fact (DP159).

**Is the thing that watches the switch still installed?** And here is
the honest part, which is the reason this rule is shaped the way it is.

**The check cannot ask GitHub.** Rule 11 forbids every module under
`murscope/` and under `scripts/` from shelling out to a network tool,
and the hosting client is on that list. Buying one probe with an
exemption to Rule 11 would trade a live red line for a watcher, which is
the trade every hole this repository has ever found began with. So the
probe is a step in the **development** repository's CI workflow, where
the network is expected and the repository is already identified, and
it fails the job when the answer is not `private`. There is no such
step in a derived tree and the check does not look for one there. Where
there is one, the check reads it and refuses to pass if it has been
removed, has lost its token, has stopped naming the repository being
built, or has stopped being able to fail the job. That
is the same move Rule 2 made when branch protection was unavailable, one
level up: verify the mechanism you have rather than name one you do not.

**The gap that leaves, named rather than papered over.** Between two CI
runs nothing is watching. A repository made public and made private
again inside that window leaves no trace here. Closing it needs a
mechanism this repository does not own - an organisation policy, or a
branch of the host's own settings - and the honest record is that this
is a detector with a latency, not a lock.

**In a derived tree the third question does not apply**, and the check
says so rather than skipping quietly. It knows which tree it is in by
reading the derivation spec: the development tree is the one that still
holds what the derivation withholds.

`main()` measures the world into a flat sheet; `detect()` judges the
sheet and nothing else. That split is why every branch above is
reachable from a fixture without a repository in a particular state -
including the one nobody can arrange locally - and why a sheet that has
*lost* a key is a finding rather than a silent pass.

## Rule 37: the shipped package names no real person

DP19 said it in M0 - no real person's name may appear anywhere in the
shipped package - and until M5 its entire enforcement was a checkbox in
the pull request template. It was ticked on every pull request this
repository merged, and it was wrong the whole time: the ledger module carried the owner's name in four
lines of two docstrings, one of them introduced by "Measured on real
data", which tells a reader the example came out of the owner's own
records. That shipped in every wheel.

This rule is Rule 1 turned on this repository's own oldest promise.

**The spelling space is generated, not listed**, for the reason DP161
gives for the brand: a list covers what somebody thought of. The seed is
the copyright holder in `LICENSE` - the one place a real name is correct
and deliberately out of scope - plus every author and committer name in
this repository's history, which is where a *second* person's name would
come from. From each seed's word tokens the check generates every
ordering and every common joiner, so a family name written first and one
written last are the same finding, and so are the hyphenated,
underscored, dotted and run-together forms.

**A single token is never matched, deliberately.** A given name alone is
an ordinary word in some language, and a matcher that fired on one would
be loosened within a week - a loosened red line is worse than none. What
is matched is a whole name. The cost is stated rather than hidden: a
given name on its own walks past this rule.

**The matcher proves itself on a known positive, every run.** The
generated spellings are run over `LICENSE`, where the holder's name
certainly is, and the rule is red if they find nothing there. A scan
reporting "no name anywhere" is worth exactly what the proof that it can
find one is worth, and this line has been caught twice by a guard
searching for the wrong shape (DP147, DP161).

**Scope is what a stranger receives**, which is wider than the wheel:
every tracked file the derivation publishes.

**The exemption is a category, not a path.** It is the file named
`LICENSE` at the root of a directory that builds a distribution - one
holding a `pyproject.toml` with a `[project]` table - and those
directories are discovered by walking the published tree rather than
listed. Written as the single path `LICENSE`, this rule made the second
distribution choose between shipping the copyright notice MIT asks for
and a green gate: `murscope-ai` shipped seven modules and no notice, and
adding one turned the check red. That is Rule 5's "a permission for a
path, not a command" failing in the other direction, too narrow rather
than too wide. A `NOTICE` beside a `pyproject.toml` is not exempt, and
neither is a `LICENSE` in a directory that builds nothing.

The root `LICENSE` is still the seed, so removing the name from it does
not disarm the rule - it turns the known positive red. Both ways of
breaking the seed are refusals rather than passes: take the holder line
out and the rule has no seed at all; leave `Copyright (c) 2026` and
remove only the name, and the generated spellings stop firing on the one
file they certainly should.

Two limits worth writing down. A name inside a base64 fixture is data by
construction and is not read. And the seed is only as good as `LICENSE`:
a holder written there in one script and used in the package in another
is a gap this cannot close.

A third limit was found the hard way and is now Rule 38's: this rule
reads files, and a commit is not a file.

## Rule 38: the published history carries no personal address

Rule 37 read every file the founding derivation publishes and reported
no real person. It was right about the files. The root commit of the
public repository carried a personal email address in its author and
committer fields, where no file carried it - `git log` and `git
ls-files` disagreed and only one of them was being read.

**A published history is not a published file, and it travels further
than one.** It is cloned, mirrored, and served by the host's API to
anyone who asks, so an address in commit metadata reaches at least as
far as the same address in a tracked file. Rule 37's window could not
contain it, which is the third time a guard in this line has been wrong
not about its rule but about the shape of the thing it was watching.

**The criterion is positive and carries no seed.** It asserts what a
published commit's addresses must be - at the host's own no-reply
domain - rather than listing addresses that must not appear. That
direction is forced rather than chosen: a check that named a particular
address would publish that address in its own source, which is exactly
the trap a rewrite falls into when it has to quote the thing it removes
(Rule 35's pattern-not-literal, and Rule 34 for the brand before it).
Nothing in the check knows whose address it is keeping out.

**The domain is constructed from `origin`, not written down**, so a
constant cannot rot into a second, wrong copy of a fact about the clone.

**The mode is stated and never skipped.** The development repository's
history carries the addresses the work was done under, it always will,
and it is not published. Run there, the check names the tree it is in,
says what it therefore did not assert, and passes - it does not skip,
because a skip and a pass are the same green to anybody reading a
summary. The criterion is proved on a fabricated address in both modes,
so a run that cannot apply the rule still knows its matcher works.

What it does not cover, and this matters after any rewrite: it reads
commits reachable from the clone's refs. A host goes on serving an
unreachable object by sha for some time, so the honest sentence about a
rewritten history is **"no longer reachable from any ref"** and never
"removed".

## Rule 39: the numbers the console states are measured

"Any countable claim in the docs needs a check behind it, or is not
written. A hand-written number is a claim, not a fact" - DP25, restated
at DP141 and DP159. Every document in this tree honours it. **The rule
below is about documents this tree does not carry:** a development
repository keeps its own state and its own decision ledger in working
directories the derivation withholds, and the counts those documents
state are what this rule measures. Where those directories are, it
reads them and compares; here it names the mode it is in and asserts
nothing, which is the shape Rule 2, Rule 36 and Rule 38 already have.

Four numbers, each measured and compared with what the state document
says:

- **how many rules there are**, read off the same `## Rule ` heading
  line Rule 1 greps rather than counted a second way. It arrived last,
  after an acceptance window pointed out that the console writes this
  count three words from the check count and only one of the two was
  measured (DP191);
- **how many checks there are**, counted off the directory the runner
  globs and the freeze records;
- **how far the decision ledger has run**, taken from the ledger's own
  highest numbered row;
- **how many files publication produces**, classified through the
  derivation spec, which is the same answer this prints:

```
python3 scripts/public_tree.py --list
```

**Nothing the check compares is named inside it**, and that constraint
shaped the whole file. Every file under `scripts/` is published, and
Rule 35 reads every file in the extracted tree that decodes as text
(DP169), so a check written the obvious way - with the state document's
path in it - turns this gate red before publication rather than after.
That is Rule 35 working, not Rule 35 in the way. So the directories come
from the derivation spec's exclusion table; the state document is **the
one carrying its own directory's name**; and the ledger is **the
document with the most numbered decision rows**. A record is recognised
by being one, and a path is derived rather than written down - the idiom
Rule 35's own generated prefixes already explain.

**What counts as a claim, and what does not.** A document rewritten in
place carries history as well as state, and a number inside a sentence
about a measurement somebody took once is not a claim about today. The
check count and the ledger mark are anchored by their own vocabulary.
**The file count is anchored to the instrument that produces it:** a
count of files in the same paragraph, or the same table row, as the
derivation spec. Naming the instrument is the console declaring whose
number it is, and a subject is the one thing a matcher cannot read on
its own.

**A count of files beside the name of the repository the derivation
goes to is the third outcome, and it is a refusal rather than a
comparison.** What that repository holds is a fact about that
repository; nothing here measures one, and a number that names it is in
the same position as its commit count. If a paragraph names both the
instrument and the repository, the instrument wins - the console has
said whose number it is.

**That anchor used to be the repository, and moving it is DP190.** The
old one was right about the problem it solved and required the number
to stand beside the repository's name, which is what makes a reader
take it for a fact about that repository. It became one: the change
that added this rule also added two published files, so the extraction
moved and the published repository did not, and the console was
corrected to a number that was wrong about its own subject with a green
check under it. **Adding the guard made the sentence less true**, which
is this line's own recurring shape - a guard correct about its
criterion and wrong about its window - arriving this time inside the
guard written to catch it.

**The cost is stated rather than left to be found.** The anchor is a
vocabulary, so a passing sentence in the state document that counts
checks is read as a claim and goes red. The answer is the one DP141
already gives: a number in prose that nothing measures is not written.

**A category that matches nothing at all is itself a finding**, and this
is the half the rule exists for. Two of its first three assertions were
green the day it was written; a number that is right today with nothing
reading it is the same object as one that is wrong today, and a matcher
that has quietly stopped firing reports a clean console with exactly the
confidence of one that looked (DP87).

**That branch covers less than it looks, and the check says so on every
run rather than leaving it here.** It fires where a category has *no*
claim, so a second count in a category that still holds a correct one -
phrased outside the vocabulary, `paths` where the console said `files` -
is neither read nor missed. Each category is safe today only by
appearing exactly once. The general repair widens a matcher that reads
the console on every run, which on this line's own precedent is a round
of its own rather than a patch, so it is carried as an open item with
its shape written down (DP191).

**The file anchor is the spec's filename, wherever it is named.** It was
briefly narrowed to the repo-relative path on the argument that the wide
form fails quietly, and that argument inverts: an over-wide matcher's
failure is a **false positive**, which is red and so loud by
construction, and an over-narrow one's is a **false negative**, which is
silent by construction. Measured over four shapes, wide is right on
three; narrow is wrong on two, and one of those is a correct count
anchored here beside a second, wrong one written with the short name -
green, and nobody would know. **What wide costs is the fourth shape**: a
passing sentence about that file which happens to count files is read as
this claim and goes red. Owner ruling, 2026-08-15 (DP192). A false
positive argues with you; a false negative does not.

**In a derived tree there is no console to read.** The mode is named,
what is therefore not asserted is named, the matcher is proved on
positives *and* negatives assembled at run time, and the check
**passes** - it does not skip, because a skip and a pass are the same
green in a summary (DP182). It is not the first rule to work this way,
and naming the family at its newest member is half the point: Rule 2's
published copy, Rule 36's third question and Rule 38's whole criterion
all turn on which tree they are in, and every one of them reads the mode
off the exclusion table rather than off a constant of its own.

`main()` measures the world into a flat sheet and `detect()` judges the
sheet and nothing else, the split Rule 36 uses and for the same reason:
every branch is then reachable from a fixture without needing a
repository in a particular state, and a sheet that has *lost* a key is a
finding rather than a silent pass.

## Rule 40: a guard that lives in ci stays installed

Some assertions this repository makes cannot be made from a check under
`scripts/`. Rule 11 forbids a network tool there, so the two that need
one - is this repository still private, and is the published tree still
the extraction of a commit here - live in the workflow. Others could
live under `scripts/` and do not, because they need a build, a fresh
environment or a clean checkout, which is too slow to put in front of
every commit.

**What all of them share is the failure this rule is for.** A step in a
workflow is invisible to the gate. Delete it and the gate is still
green, every check still passes, and the assertion is simply gone -
there is no diff a reviewer reads as a loss and no red anywhere. Rule 36
already refuses that for exactly one member, the visibility probe. What
was missing is that it was written **for one member rather than for a
set**, and this line noticed that before there was a second and then
built a third anyway, because noticing is not a mechanism.

**The register lives in the check and not in the workflow**, and that is
the whole of it. A declaration living inside the thing it declares
cannot notice that thing being deleted: removing the step removes its
own marker, and a keeper reading markers would enumerate nothing and
pass. So the members are named in the check, and the workflow is read
against them.

Four questions per member, all offline. **Is it there** - a step with
that name. **Does it still have what it needs** - its token, its
subject, the inputs its assertion is made of; a probe with no token
answers nothing on every run and that reads in a log exactly like an
answer. **Can it still fail the job** - not `continue-on-error`, not
switching errexit back off, and its asserting command not swallowed by a
trailing `|| true`. **Does anything run it** - a workflow with no
trigger is a watcher nobody starts.

**For a member that `uses:` somebody else's action the third question is
weaker, and is reported as weaker rather than dressed up.** There is no
command of ours inside such a step to read, so all that can be said is
that it is not exempted from failing; its inputs carry the weight
instead - which is why the interpreter member requires the matrix
binding and not merely the action's name.

**Errexit is deliberately not one of the four**, and the first version
of this rule had it. The host runs a `run:` body under `bash -e`
already, so asking whether a step says `set -e` is a question almost
every step passes for free while saying nothing about any of them - and
it went red on the step that runs the gate, a single command that fails
the job exactly as it should. What can actually stop a failure from
reaching the job is somebody turning errexit off or swallowing an exit
code, and those are what is read.

**And two questions about the set rather than about a member.** Every
step in every workflow must be either a registered member or named
infrastructure, so deleting a member's row leaves its step running,
unclassified and red, and a new step is classified by whoever adds it
rather than by whoever notices later. **A step matches a register row by
its exact name**, expression and all. Matching by prefix was introduced
for a single title carrying a matrix expression, and it promptly did the
classifying by name collision - an unregistered step called `Run the
gate on the docs` was swallowed by the member called `Run the gate`.
Narrowing the prefix to the name plus a space does not fix it, since the
collision begins that way too, so the register carries whole names and
the test is equality. And **the register's own size is
declared in the freeze** and asserted by the check: a set whose size is
recorded nowhere shrinks by one edit with no trace but a smaller number
in its own output, which is the gate-shrinks-quietly shape Rule 1
refuses one level up with `expected_check_count`. The counter-argument -
that a declared constant can be edited in the same commit - is equally
true there, and was accepted for the same reason: the point is not that
it cannot be defeated, it is that defeating it takes a second, legible
edit instead of none.

**Infrastructure is the class whose absence announces itself**, because
the steps after it stop working - delete the checkout and there are no
files, delete the install and the first command naming the package
fails. **That list was twice this long and both extra entries were
wrong.** Setting up the interpreter and setting up the board's engine
are absent in exactly the way this rule exists to catch: the runner
ships both already, so deleting either leaves the job green while the
three-version matrix quietly collapses onto whatever the image carries
and the board runs on an engine nobody pinned. A matrix cannot exist
under `scripts/` at all, which makes it about as CI-resident as an
assertion gets. Both are members. The criterion did not change; it had
been applied wrongly.

**What this rule costs, stated here rather than found later.** A keeper
that covers a class can be loosened for the class: one edit to the
register narrows what is watched for every member at once, where a guard
written per member has to be defeated one at a time. That is real, and
it is the argument the alternative had. It was ruled for anyway, because
the alternative was a third copy of a thing already written twice. The
two questions about the set are what keep the cost bounded: drop a row
and its step goes unclassified and this rule is red; drop the row and
the step together and the declared size disagrees and it is red again.
**The residue is three legible edits in one commit** - the row, the
step, and the size in the freeze - which is exactly the floor
`expected_check_count` has stood on since M0. Measured rather than
reasoned about, and written down rather than left as a property somebody
discovers.

**One member is watched from inside itself.** The step that runs the
gate is a member, because the assertion only the workflow makes is that
the gate runs on a *clean checkout* on every interpreter in the matrix -
the one runner that has ever caught a file on the disk that the index
did not hold. But this check runs inside that step. Delete it and
nothing here runs in CI at all, so the red arrives from a contributor's
own pre-flight and from no CI run. That is a guard whose window does not
contain the thing it watches, in this rule, on purpose, with no version
of it that does not have the property.

**Rule 36 is not delegated to this rule and is not weakened by it.** It
keeps its own assertions about the probe - a token, a refusal on a
repository that is not private, and the repository being built rather
than one somebody typed - along with the declaration and the blast
radius, which are not this rule's business. The overlap is presence,
inputs and can-fail on one member. The cost is that an edit to that step
turns two checks red and a reader may repair one and assume the other;
both name the step and their own rule, so the second red is a direction
rather than a puzzle. What it buys is that a red line's keeper stays
self-contained - it does not stop working if this rule is loosened, and
cannot be loosened by loosening the class.

**In a derived tree two members do not apply**, and the rule says which
rather than skipping quietly, the way Rules 2, 36, 38 and 39 all do.
Both watch the repository the derivation came from, which a derived tree
cannot ask after and carries no evidence about; both are rewritten out
of the published workflow with their reasons attached. Which tree this
is comes from the derivation spec's exclusion table rather than from a
constant.

`main()` measures the workflow files into a flat sheet and `detect()`
judges the sheet and nothing else - the same split, for the same reason:
every branch is reachable from a fixture without a repository in a
particular state, and a sheet that has lost a key is a finding rather
than a silent pass.

## Rule 14: activity source reads mtime only

The activity clock (DP22) is a pluggable source, **off by default**, and
the MVP adapter reads mtimes inside the work tree only. This rule is
what keeps it from becoming something else.

- The activity layer may call `os.stat` and `os.walk`. It may not call
  `open()`, `read_text()`, `read_bytes()` or a JSON loader. Today it
  walks the user's own project; at M4 the adapter points at an external
  AI tool's session directory, and the difference between "when did this
  change" and "what does it say" is the entire boundary.
- `last_touch` and **its source path** may not enter an outbound payload:
  no provider names them, and they stay out of the whitelist a sensitive
  entry emits, because the path of the newest file in a sensitive
  project is content and Rule 7 permits only method.
- The **age** is a different thing from the path, and the board does show
  it - that is the secondary line DP22 and DP23 ask for. It reaches the
  page as a duration under its own key and carries no path, and it is
  absent from a sensitive row entirely, because a sensitive entry's file
  readers never run. Said here because the rule reading "may not enter an
  outbound payload" has to be readable beside a board that displays
  something the clock produced.
- **This rule is about the activity source, not about paths.** Signal 10
  keeps the path of the newest file in the tree and puts it on the board -
  "newest file: X", the only recency answer a project with no commits has -
  and that is not a violation of anything. The distinction is not which
  rule was written first: an activity source becomes, at M4, an adapter
  pointed at **another tool's** directory, so a path from it names data the
  user never listed, while signal 10's path names a file inside a project
  they did. The reason is recorded at both sites, because an audit asked why
  two paths of the same shape are treated differently and the answer had
  been left to inference.

The second half is free today - nothing leaves this machine, and the one
provider that ships (`noop`) contributes an empty map and is not loaded
unless the user enables it. It is checked now because the day a provider
with something to send exists is the day it stops being free, and a rule
that arrives after the capability it governs has arrived too late.

**DP23**: the clock never colours the tier. The tier answers "how long
since this moved" from the commit history; this is a second, weaker
answer on a second line. Two answers competing for one question is how a
build artifact paints a dead project green.

## Rule 17: reads stay inside the listed project

The third promise on the front page is that murscope reads nothing
outside the projects you listed. It had no check, and an audit showed it
was false: `ledger_paths()` joined a roster-supplied string onto the
project root and read the result, so `ledgers: ["../secret/x.md"]` was
read, and an absolute path was read too - `root / rel` on an absolute
`rel` **is** `rel`, so the root was ignored entirely.

The renaming was the worse half. The caller did
`except ValueError: rel = path.name`, so a file from outside the project
appeared on the board under a bare filename with no provenance. The code
had foreseen the out-of-root case and hidden it instead of refusing it.

- A containment helper resolves both sides and compares them, so a
  symlink out of the project cannot pass a string test.
- Any function that joins a caller-supplied name onto a root and reads
  the result must test containment.
- A path that escapes is **refused and reported**, per entry and on the
  board. A silent drop and a refusal look identical to the user.

Checked structurally *and* behaviourally: the check hands the real
`ledger_paths()` both shapes above and fails if either is accepted, or
dropped without a report. A structural test alone can be satisfied by a
function that mentions the helper and ignores its answer.

`sensitive: true` already prevented this, because Rule 7's strong half is
really implemented - but a promise that holds only under a non-default
setting is not the promise that was made.

## Rule 15: owner private material never enters history

No path under `archive/` or `memory-mirror/`, and not `BRIEF.md`, may be
tracked, staged, or present in any commit reachable from any ref - and
its content may not be resting in the object database unreachable from
anything. The check asks all four questions. Staging is the last moment
this is still free to fix and the only moment a human is likely to be
looking; the fourth question exists because `git add` writes the blob
whether or not the commit happens, unstaging does not remove it, and the
first three questions all ask about names while an unreachable blob has
none.

The fourth is deliberately not dressed up as a leak. `git push` sends
only objects reachable from the refs being pushed, so an unreachable
blob does not reach the remote; this is local hygiene and defence in
depth, with a one-line remedy the check prints. A rule that overstates
its own stakes teaches people to discount it.

Git history is permanent, and who may read a repository is a setting
rather than a fact - DP164 rules that no repository in this line is
published by having that setting flipped, and the rule below assumes it
happens anyway. Every other rule here guards against a bug; this one
guards against a disclosure, and it is the only failure in the
repository that cannot be undone by a follow-up commit.

It exists because until an audit went looking, private material was
caught only incidentally - by Rule 3 noticing Chinese inside it. The
English-only private files walked through a fully green gate. A rule that
works only when the secret happens to be in the wrong alphabet is a
coincidence, not enforcement.

The private set is a literal in the check, not a read of `.gitignore`.
`.gitignore` can be edited in the same commit that leaks the file; the
check is covered by the freeze.

## Rule 16: dependencies point one way

The core imports no provider. Providers import the core. No provider
imports another provider.

Anything under `murscope/` outside `murscope/providers/` may import the
provider *package* - that is the seam, and `murscope/cli.py` uses it -
but may not name a provider module, by absolute import, by relative
import, or through a dynamic import with a literal name.
`murscope/providers/__init__.py` is the one exemption: importing the
enabled modules by name is its entire job, it is short, and every
provider it can reach is a literal in its own allowlist.

This is what keeps the MVP's second promise structural. "No network
call" is verifiable by reading the source precisely because the provider
layer is empty and nothing in the core reaches for it; one convenient
import from the core is all it would take to lose that quietly.

## Verification discipline

- The pre-flight is **one command**, and it runs the checks *and*
  `murscope selftest`. That is not tidiness: the runtime guards - the
  sensitive canary (DP65), the socket-refusing audit hook, the DP69
  read-location assertion, the parser's shape cases - all live in the
  selftest, and until this landed neither CI nor the documented pre-flight
  ran it. Putting a withheld key back into `SENSITIVE_ALLOWED_KEYS` left
  the gate 15/15 green with only the selftest red, so a contributor
  following the discipline exactly would never have reached that guard.
  A guard on a path nobody walks is the same failure as a canary that
  measures a path nothing takes, one level up.
- CI runs that command and then runs `murscope selftest` again **from a
  built and installed wheel, outside the checkout**. That is a different
  class of defect: the canary fixture was once missing from the wheel, and
  no source-tree run could have seen it. It stays in CI because it needs a
  build and a fresh environment.
- "Verified" means the command was run and its output shown. Otherwise
  write "unverified".
- The baseline only goes up. Skipped checks stay at zero, always: a check
  whose target does not exist yet inspects what is present and passes on
  the facts, it is never skipped.
- A check that cannot fail is not a check. Every check's docstring
  carries a `Fails when:` line, and acceptance constructs that exact
  shape and confirms it goes red.
- The person who writes a change does not declare it done. It is
  judged by somebody else.

### Reverse verification cases

Standing set. Every one of these is constructed in the working tree,
confirmed, and reverted before committing. A milestone that cannot
reproduce this table has regressed, whatever the gate prints.

Cases g to k came from the first audit, l to w from the second. Each was
found passing green. They are kept because they are cheap to re-run and
because the failures they describe are specific, but they are no longer
what makes the gate trustworthy - Rule 1's fixture harness is. Eleven
hand-written cases caught eleven imagined violations and the second
audit walked about twenty more straight through. A list of remembered
mistakes is a ritual; a mechanism that requires every check to fire on
its own documented violation is enforcement.

| # | Construct | Check | Expect |
|---|---|---|---|
| a | A tracked file containing a CJK character | `english_only` | red |
| b | An `.md` under `design/` missing the `captured` key | `governed_docs_carry_frontmatter` | red |
| c | An allowlisted git subcommand with no `GIT_OPTIONAL_LOCKS=0` | `monitored_projects_are_read_only` | red |
| d | `import urllib.request` inside the core package | `offline_by_default` | red |
| e | An analytics client's event call in any tracked file | `zero_telemetry` | red |
| f | A rule with neither a script nor an `Enforcement:` line | `all_rules_have_checks` | red |
| g | `Path(p).write_text(x)` in the package | `monitored_projects_are_read_only` | red |
| h | `from os import remove`, then `remove(p)` | `monitored_projects_are_read_only` | red |
| i | A check script replaced by a stub that prints OK | `all_rules_have_checks` | red |
| j | `env = os.environ.copy()`, `env["GIT_OPTIONAL_LOCKS"] = "0"`, then a git call | `monitored_projects_are_read_only` | **green** |
| k | A shelled-out network tool pointed at an https URL | `offline_by_default` | red |
| l | A check's `detect()` edited to return nothing, manifest regenerated | `all_rules_have_checks` | red |
| m | A check with no `detect()` at all | `all_rules_have_checks` | red |
| n | Delete a check and its rule, then regenerate the manifest | regeneration refused; runner red | red |
| o | A runner replaced by one that prints a green summary | `all_rules_have_checks` | red |
| o2 | A check whose `sys.exit()` sits at module level, unguarded | `all_rules_have_checks` | red |
| p | Stage an owner-private file that contains no CJK | `owner_private_material_never_enters_history` | red |
| p2 | Stage an owner-private file, unstage it, leave the blob in the object database | `owner_private_material_never_enters_history` | red |
| q | `open(p, "r+")` outside the guard | `monitored_projects_are_read_only` | red |
| r | `subprocess.run(["rm", "-rf", p])` in the package | `monitored_projects_are_read_only` | red |
| s | A `guard_write_path()` that neither mentions `MURSCOPE_HOME` nor raises | `monitored_projects_are_read_only` | red |
| t | `import os as o`, then `o.remove(p)` | `monitored_projects_are_read_only` | red |
| u | A git call taking its env from a helper that provably locks it | `monitored_projects_are_read_only` | **green** |
| v | `import _socket`, the C accelerator | `offline_by_default` | red |
| w | `webbrowser.open()` handed an https URL | `offline_by_default` | red |
| x | A browser image beacon in a tracked `.html` | `zero_telemetry` | red |
| y | `from .providers import noop` in a core module | `dependencies_point_one_way` | red |
| y2 | One provider importing another | `dependencies_point_one_way` | red |
| y3 | `from . import providers` in a core module | `dependencies_point_one_way` | **green** |
| z | Prose mentioning a marker mid-sentence | `blocker_extraction_stays_precise` | red |
| z2 | A marker legend inside a code span | `blocker_extraction_stays_precise` | red |
| z3 | An empty "Blocked" heading | `blocker_extraction_stays_precise` | red |
| z4 | A default marker changed without touching the fixtures | `blocker_extraction_stays_precise` | red |
| aa | `from . import noop` in the provider loader | `providers_run_only_when_configuration_names_them` | red |
| ab | The loader's membership test removed, so a config string reaches `import_module` | `providers_run_only_when_configuration_names_them` | red |
| ac | A dynamic import of a provider at the loader's module scope | `providers_run_only_when_configuration_names_them` | red |
| ad | A provider module added under `murscope/providers/` beyond `BASE` | `the_base_distribution_ships_no_provider_that_can_reach_out` | red |
| ae | `import urllib.request` added to `noop.py`, so the base wheel ships it | `the_base_distribution_ships_no_provider_that_can_reach_out` | red |
| af | The extras distribution's only socket-capable import removed | `the_base_distribution_ships_no_provider_that_can_reach_out` | red |
| ag | The `[ai]` pin changed to a version the extras distribution is not | `the_base_distribution_ships_no_provider_that_can_reach_out` | red |
| ah | The `[ai]` extra emptied, so it declares no distribution | `the_base_distribution_ships_no_provider_that_can_reach_out` | red |
| ai | A networking import added to a provider the base package ships | `murscope selftest` step 9 | red |
| aj | A provider module dropped into `site-packages/murscope/providers/` by hand | `murscope selftest` step 9 | red |
| ak | `murscope[ai]` installed, so a socket-capable module is present and owned | `murscope selftest` step 9 | **green**, and it names the distribution |
| z5 | A generic blocker claiming the owner queue | `blocker_extraction_stays_precise` | red |
| z6 | A section written as a table, reported as its column names | `blocker_extraction_stays_precise` | red |
| z7 | A table under a heading carrying only a header row | `blocker_extraction_stays_precise` | red |
| aa | `ledgers: ["../outside/x.md"]` on a roster entry | `reads_stay_inside_the_listed_project` | red |
| ab | `ledgers` holding an absolute path outside the root | `reads_stay_inside_the_listed_project` | red |
| ac | Weaken one shipped case in `murscope/fixtures/` | `all_rules_have_checks` | red |
| ad | An inline `open()` inside a function that tests `sensitive` and reads anyway | `sensitive_entries_expose_method_only` | red |
| ae | A reader added to `collect.py`, called from a function that never mentions sensitivity | `sensitive_entries_expose_method_only` | red |
| af | A reader in `ledger.py`, called unconditionally from `cli` | `sensitive_entries_expose_method_only` | red |
| ag | `from . import collect as _c`, then `_c.peek(...)` | `sensitive_entries_expose_method_only` | red |
| ah | `reader = collect.peek; reader(...)` | `sensitive_entries_expose_method_only` | red |
| ai | A key added to a sensitive record after collection | `render` raises at the boundary | red |
| aj | Point 4 hollowed out, manifest regenerated in the same change | `all_rules_have_checks` | red |
| ak | A direct commit to **local** `main`, `origin/main` clean | `all_changes_via_pr` | red |
| al | A wrapped `<img>` beacon, CSS `url()`, `@import`, `meta refresh` | `zero_telemetry` | red |
| am | All six false-positive refusals deleted, other categories padded | `blocker_extraction_stays_precise` | red |
| an | Two authors level on a two-project scan | nothing seeded, and it says so |
| ao | A reader in the **git** branch of `collect_project`, written as a dict of callables | `murscope selftest` canary | red |
| ao2 | The same reader in the non-git branch | `murscope selftest` canary | red |
| ap | Hollow a detector branch **and** delete the case covering it | `all_rules_have_checks` | regeneration refused |
| aq | `<a href="https://...">` in README, a Python function named `fetch` | `zero_telemetry` | **green** |
| ar | `BLOCKED: waiting on <alias>` | counts as waiting on you | green |
| as | `BLOCKED: waiting on a human` | does **not** count, and does not inflate the unmatched counter |
| at | Drop a row, rename another, then change owner names | both survive the recollection |
| au | A sensitive entry with two uncommitted files | tile and row agree |
| av | `status --explain` on a sensitive entry | says it was sealed; prints no table of nulls |
| aw | A board with one matched and one unmatched owner name | the tile keeps the number and names the shortfall |
| ax | A sensitive entry whose file readers were sealed | no `partial signals` alert |
| ay | An indented HTML comment after a declaration | not joined |
| az | `last_subject` put back into `SENSITIVE_ALLOWED_KEYS` | `murscope selftest` canary | red |
| az2 | `SENSITIVE_WITHHELD_KEYS` emptied, or `last_subject` dropped from it | `murscope selftest` step 3 | red - emptying the list would otherwise turn two assertions into zero and leave the step green while the ruling was reversed |
| ba | A read outside the sandbox, added at the top of step 3 | `murscope selftest` canary | red |
| ba2 | The same read added inside step 1 | `murscope selftest` canary | red |
| ba3 | A real roster whose projects step 4 collects | **green** - those are paths the user listed |
| bc | The activity clock on, and the board's hint claiming it is off | conditional hint | red before, gone now |
| bd | `signals.activity.path` reaching `data.json` | `activity_source_reads_mtime_only` | red |
| be | `status --explain` on a project with no ledger file | says so; does not claim a refusal |
| bf | A shipped fixture of pure false positives | selftest step 1 | red |
| bg | A read at the very end of the canary step | `murscope selftest` | red |
| bh | The decoy written to `sys.stderr` inside the run | `murscope selftest` | red |
| bi | A bare `init` with a sensitive entry in the roster | its root is not rescanned |
| bj | A read planted in the tree walk, which only a **non**-sensitive entry reaches | `murscope selftest` step 10 | **green before, red now** - the window ended where step 3 did, and step 3 collects sensitive entries only |
| bk | A comment naming sensitivity above an unconditional read | `sensitive_entries_expose_method_only` | **red before, green now** - a gate is a function that tests, not one that mentions |
| bl | `is_gate()` narrowed until nothing is a gate | same check's `check_model_precision` | red |
| bm | A `socket.getaddrinfo` planted in `render.build_document`, which step 3 runs | `murscope selftest` | **green before, red now** - the network hook went on inside step 4, and the closing line spoke for the whole run. Built both wheels and ran the same injection against each: previous build exit 0 printing "the run made no network attempt", this one exit 1 |
| bn | The same injection wrapped in `try/except Exception: pass`, so nothing propagates | `murscope selftest` step 4 | red - the hook records before it raises, which is what survives `collect_records` swallowing per-project exceptions |
| bo | Every step-4 collection raises, step 3's canary entries left alone | `murscope selftest` step 4 | **green before, red now** - errors were printed and never counted, so "0 network event(s) attempted" was reported from a step in which nothing ran |
| bp | A root that does not exist, handed to `doctor` | `murscope doctor` | **"Every root returned entries" before, refused now** - `blocked()` counts only BLIND, and the health sentence asked it instead of counting OK |
| bq | Twenty-three repositories all committed to seconds ago, cap 20 | `murscope init` | **"3 older or non-git ones" and `tier2` before; "3 recent ones past the cap of 20" and `capped` now** |
| br | A sensitive entry on a repository with eight commits | board evidence | **`recent_commits=0` before, `recent_commits=no-source` now** - `_shielded_signals` rebuilds four blocks and `trend` is not one |
| bs | Twenty repositories, ten holding uncommitted work, three of those carrying a ledger declaration | `init` summary vs board tile | **8 vs 10 before, 10 and 10 now** |
| bt | A home holding one directory reachable as both `Projects` and `projects` | `init` proposal list | **one project proposed twice before, once now** |
| bu | `_in_hand_also` made to return an empty list, so a declared or curated row carries no sub-text | `murscope selftest` step 5 | **green before, red now** - the whole of DP80 switched off left `run_checks.py` at 15/15 with the selftest green, because nothing exercised a declared row |
| bv | The sub-text dropped in `wizard._row` only, leaving the payload correct | `murscope selftest` step 5 | red - the step renders a row rather than trusting the data, which is the half F6 is about |
| bw | The board template's `st.also` loop put back behind `st.kind === "inferred"` | nothing | **green** - no check in this repository executes `board.html`. Recorded as DP81, not papered over. The board half of DP80 was verified by rendering the shipped template and reading the state cell of every row out of the live DOM |
| bx | The one-line clip put back in `wizard._row`, the payload left correct | `murscope selftest` step 5 | **green before, red now** - the step asked whether a sub-text line existed and carried a `·`, both of which a clipped line satisfies, so DP80 shipped with its own screen dropping three of four sentences on the row that needed them (DP82) |
| by | A heading in `wizard._header` typed in English instead of `translate(catalog, key)` | `i18n_keys_stay_complete` | **green before, red now** - key sets matched across locales the whole time, because the word was never a key (DP83) |
| bz | The four-thing case deleted from `_STATE_CASES`, so no row wraps | `murscope selftest` step 5 | red - every sentence surviving is only worth asserting if some case carries more than one line holds; a table trimmed to short rows would satisfy the assertion by never reaching it |
| ca | `reraise_masked` changed from `from None` to `from exc` | `keys_are_stored_0600_and_never_rendered`, `murscope selftest` step 7 | red - the original exception follows the masked one into the traceback under "During handling of the above exception", key and all |
| cb | The query-string pass removed from `redact()`, leaving only known values | `keys_are_stored_0600_and_never_rendered` | red - a key the store never saw goes into the traceback. **This is how the pass was found**: the check was written first and the transport failed it |
| cc | `Secret.__repr__` changed to return the value | `keys_are_stored_0600_and_never_rendered`, `murscope selftest` step 7 | red on both halves - the static one reads the return, the live one prints it |
| cd | `mode=` dropped from the key store's `guard_write_path` call | `keys_are_stored_0600_and_never_rendered` | red - static on the call, live on the 0644 file it produces |
| ce | The `isinstance(..., Grant)` test removed from the transport | `consent_binds_to_the_disclosure_it_showed` | red - `True`, `1`, `'yes'` and the old sentinel string are all accepted as consents |
| cf | A field added to `outbound.DISCLOSURE` and the payload left alone | `consent_binds_to_the_disclosure_it_showed` | red - the declared table and the built payload stop being the same set, in the direction that means the user is shown more than leaves |
| cg | A key added to the outbound payload and `DISCLOSURE` left alone | `outbound.build` raises; `consent_binds_to_the_disclosure_it_showed` | red - a field nobody was shown |
| ch | `consent.require()` reduced to "a file exists" | `consent_binds_to_the_disclosure_it_showed`, `murscope selftest` step 8 | red - a consent recorded for eleven fields covers twelve, which is the whole of DP94 |
| ci | The destination dropped from `fingerprint()`'s inputs | `consent_binds_to_the_disclosure_it_showed` | red twice - statically for the unused argument, live because one consent then covers every endpoint (DP90) |
| cj | A grant recorded against today's disclosure, handed to `send()` | `consent_binds_to_the_disclosure_it_showed` | **green, and it must reach the wire** - a transport that refuses everything satisfies all six refusals and sends nothing anybody agreed to |
| ck | The consent check moved below `Request(...)` in `send()` | `consent_binds_to_the_disclosure_it_showed` | red - measured by line number from the parse tree, because a refusal after the request is built is a refusal that arrives late |
| cl | `board.promise.network` deleted from one locale | `i18n_keys_stay_complete`, `murscope selftest` step 9 | red - the footer would print the missing-key marker on an `[ai]` install |
| cm | `boundary.promise_key` made to return the base key always | `murscope selftest` step 9 | red - the two-row table asserts both branches on every install, including the one this machine is not |
| cn | A decoy planted in a sensitive entry's files, the outbound payload examined | `murscope selftest` step 3 | red if it appears - and the step also asserts the non-sensitive row *did* survive, or the absence is an absence in an empty payload |
| co | `keys.names()` rewritten as a `glob` on a parameter | `sealed_directories_stay_sealed` | red - the third shape resolves same-module bindings only, and a parameter disqualifies a name outright |
| cp | `cli.daily_command(["--send"])` spliced into `murscope.timer:main` | `the_timer_collects_and_cannot_send` | red - three findings, because the walk arrives at `daily_command`, at `_resolve_writer` and at `registry.writers` |
| cq | The same command reached through `from .cli import daily_command as _d` | same | red - the resolver binds from-imported symbols, so an alias is not a way out |
| cr | `registry.writers()` called from the timer module itself | same | red on `murscope.timer:main`, which is reachable from itself. A doorway in the entry point is the shortest possible violation and was the one most likely to be missed |
| cs | `_resolve_writer(home)` spliced into `cli.run`, the timer left alone | same | red - the violation is anywhere on the path, not only in the timer's own file |
| ct | The timer's call to `cli.run` removed | same | red - **the walk reaching nothing is a finding, not a pass**. This is DP87 in one row: a check that certifies an empty graph certifies nothing |
| cu | The scheduled entry point renamed | same | red - there is nothing to walk from, and the check says so rather than reporting a clean graph |
| cv | A provider registering a `contribute` the check cannot resolve to a function | same | red - the one dynamic edge on the timer's path is read out of `register()`, and an unreadable one is a finding |
| cw | The announcement in `guard_schedule_write()` moved below the write | `monitored_projects_are_read_only` | red - measured by line number, so a path named afterwards is a receipt and not a permission |
| cx | `permitted_schedule_paths()` given a parameter | same | red - the complete set of paths writable outside the home stops being complete the moment a call site can extend it |
| cy | A scheduling guard that refuses by returning `None` instead of raising | same | red - and its body loses the exemption, so its `open()` is reported like anybody else's |
| cz | A scheduling guard handed its permitted set by its caller | same | red - this is the whole of DP126: a guard that trusts the caller is a permission for a command |
| da | The brand's Chinese name spelled out in a tracked file, joined and lower case | `the_brand_name_is_never_transliterated` | red |
| db | The same name in a romanization system nobody would have thought to list | same | red - the spelling space is generated from the syllables, so a system is covered the moment its table row exists |
| dc | Tone marks instead of digits, composed rather than decomposed, camel-cased onto another word | same | red |
| dd | The syllable table trimmed to one entry, so half the brand generates nothing | same | red - the seed is asserted against the name it claims to describe, the way Rule 5's permitted table is |
| de | The brand's escaped code points removed from every locale | same | red - the check would otherwise be guarding a name the repository no longer carries, and this file's own declaration does not count towards it (DP87) |
| df | The same name spelled out in a commit subject | same | red - a public repository carries its history |
| dg | A code span pointing into a withheld directory, added to a published file | `the_public_tree_has_no_dangling_reference` | red |
| dh | One rewrite deleted from the spec, the document left as it stands | same | red - the reference that rewrite existed to remove reaches the extracted tree |
| di | A rewrite's `find` text edited until it matches neither the text it removes nor the text it leaves | same | red - a rewrite that quietly does nothing is the drift the idempotence is there to expose |
| dj | The governed-directories tuple rewrite removed, prose rewrites left alone | same | red on the **Python** half, which is the half a markdown-only scan would not have |
| dk | Everything excluded, so the extraction produces an empty tree | same | red - an empty tree carries no dangling reference and proves nothing (DP87) |
| dl | The withheld directories' ledger filenames left exactly as they are in `murscope/fingerprints.py`'s table | same | **green** - product data, never joined onto this tree's root. This is the false positive the category exists to avoid, and getting it wrong would mean shipping a scanner that cannot recognise a management console |
| dm | A commit hash of this repository left in a check script, its prose rewritten around it | same | red - the coordinate half resolves the token against this repository's own object database, and a tree founded clean has no such object |
| dn | The same hash written into the spec's rewrite table, which is the only way a literal rewrite can quote what it removes | same | red, and on the spec rather than on its target. This is the whole reason `REGEX_REWRITES` exists: the answer is a pattern, not an exemption for the one file that decides what is published |
| do | A section number into the unpublished design document, added to a docstring | same | red |
| dp | A pull request citation added to a published file | same | red |
| dq | The coordinate matchers' known positives written into the check as literals | same | red on the check's own file - which is why they are assembled at run time: a literal there would need an exemption, and the file would have nothing left to prove |
| dr | The commit resolver made to answer "no" to every token | same | red - it is fired on this repository's own HEAD before any token from the extracted tree is put to it |
| ds | `Switch: never` changed to anything else in `PUBLICATION.md` | `publication_is_a_derivation_never_a_switch` | red |
| dt | `Mechanism:` pointed at a file that exists and is not the derivation | same | red - the named module has to expose the derivation, not merely be openable |
| du | The visibility probe deleted from the CI workflow | same | red - nothing anywhere then observes the one change here that cannot be undone |
| dv | The probe's token removed from its step | same | red - it would answer nothing on every run, which reads in the log exactly like a repository that is fine |
| dw | The probe's refusal softened from an exit to an echo | same | red - a probe that reports and continues is a log line, not a gate |
| dx | The probe pointed at a repository name somebody typed rather than the one being built | same | red - it would stay green while this one went public |
| dy | A key deleted from the measured sheet before it reaches `detect()` | same | red - a judgment over a sheet with a key missing is a judgment about nothing (DP87) |
| dz | The repository actually made public, the probe left intact | the CI step | **red in CI and green here**, and that split is this rule's honest limit rather than a defect in it: the gate is offline by construction, the watcher has a latency, and both say so in as many words |
| ea | The owner's name put back into a docstring under `murscope/` | `the_shipped_package_names_no_real_person` | red - this is the defect the rule was written for, and it had been shipping in every wheel for five milestones behind a ticked checkbox |
| eb | The same name with the family name first, run together, hyphenated, dotted, or upper case | same | red - the spellings are generated from the seed's tokens, so ordering and joiner are covered rather than enumerated |
| ec | The copyright holder removed from `LICENSE` | same | red - the seed is gone, and a matcher generated from nothing reports every file clean |
| ed | The holder left in `LICENSE` and the matcher changed so it no longer finds it there | same | red - the known positive is asserted every run, before any other file is read |
| ee | A contributor's name in a docstring, that person never having been the copyright holder | same | red - authorship seeds the space too, which is where a second person's name arrives from |
| ef | A given name on its own, in a comment | same | **green, and deliberately** - a matcher that fired on one ordinary word would be loosened within a week, and a loosened red line is worse than none. The rule states this limit rather than implying coverage it does not have |
| eg | A withheld directory named in the clear in the ignore file, the workflow, or the packaging table | `the_public_tree_has_no_dangling_reference` | red - every file that decodes as text is read now, and a file with no markdown and no syntax in it gets the plain-text reader rather than no reader (DP169) |
| eh | The same defect in a file type nobody has added to this repository yet | same | red - the plain-text reader is the default rather than one more listed suffix, so a file type arrives covered instead of arriving unread |
| ei | The withheld prefixes written into the check instead of generated from the exclusion table | same | red - an exclusion table that yields no prefix means the plain-text half is looking for nothing, and that is asserted before the scan rather than inferred from its silence |
| ej | A link to the development repository, in any published file | same | red - the repository half compares against the clone's own `origin`, so no repository name is written down anywhere for it to be right about |
| ek | That link written as a literal in the spec's rewrite table, which is the only way a literal rewrite can quote what it removes | same | red, and on the spec rather than on its target. Second time, same answer: a pattern in `REGEX_REWRITES`, not an exemption for the file that decides what is published |
| el | A service or unit name that happens to contain the development repository's name | same | **green** - the category is a URL naming an owner and a repository on the hosting domain, never a word. This is the false positive the shape exists to avoid, and getting it wrong would mean a rule nobody could keep |
| em | A sentence true of the repository it is written in and false of the one it is published into, carrying no path and no URL | same | **green, and this is the rule's honest limit.** No scanner settles whether a sentence is true in a repository it cannot see. Four of the six findings in the second pre-publication audit had this shape, which is why that audit is a reading and not only a run (DP170) |

Case p2 has to be cleaned up after. Staging a file writes its blob
whether or not the commit happens, and unstaging does not remove it, so
running case p - or case p2 - leaves owner-private content sitting in
`.git/objects` reachable from nothing. That is not a leak: `git push`
sends only objects reachable from the refs being pushed. It is local
hygiene, and **testing this rule is itself a way to create what the rule
forbids**, so purge afterwards, every time:

```
git reflog expire --expire=now --all && git gc --prune=now
```

Case o2 was found by running case i, not by imagining it: a stub check
with an unguarded module-level `sys.exit(0)` killed the harness on
import, and the harness died reporting success having verified nothing.
That is the argument for the fixture mechanism in one line - the ritual
produced the case, the mechanism produced the bug.

Cases j, u, dl and ef are the ones that must stay **green**. A red line that
rejects the correct idiom gets loosened rather than obeyed, and a
loosened red line is worse than none - so the check being *usable* is
part of the check being right. Case u is the sharper of the two:
factoring the locked environment into one helper is how "every git call
is locked" stops being something each author has to remember.
