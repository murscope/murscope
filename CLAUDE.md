# murscope constitution

murscope is a read-only portfolio observability tool: a deterministic
Python collector scans the projects you point it at and renders a
one-page static dashboard. It answers one question - which of my
projects are moving, which stalled, which are stuck on me - without
writing anything into those projects, without a network call, and
without an account. This repository is the product line, not any one
person's instance.

## Layout

| Path | What |
|---|---|
| `murscope/` | The package. Core is pure stdlib, offline, write-guarded |
| `murscope/cli.py` | Entry point. `init` / `try` / `doctor` / `note` / `open` / `run` / `status --explain` / `modules` / `selftest` |
| `skill/` | The Claude Code skill. Instructions only; renders nothing (DP151) |
| `scripts/run_checks.py` | The gate. Runs every script in `scripts/checks/` |
| `scripts/checks/` | One script per enforced rule. Frozen zone |
| `scripts/public_tree.py` | What the public repository is made of: withheld, rewritten, regenerated (Rule 35) |
| `PUBLICATION.md` | The one irreversible thing here is a setting, not a file (Rule 36) |
| `design/` | ADRs. `templates/doc.md` frontmatter template |
| `.github/` | CI matrix (3.9 / 3.12 / 3.13) and the pull request template |
| `CONTRIBUTING.md` | The rules in full, each mapped to its check |

## Five red lines (checks enforce; details in CONTRIBUTING.md)

1. **Absolutely read-only toward monitored projects.** The tool never
   writes outside `MURSCOPE_HOME` - no caches, no lock files - with one
   named exception since M4: `murscope timer install` writes the
   scheduler's job description, because launchd and systemd read one from
   nowhere else. That is a permission for **a path**, not for a command
   (DP126): the permitted list is computed with no parameter, compared by
   equality, and printed before the write. Those are properties of the
   machinery, and for four stages they were all any check knew - what was
   *in* the list was reviewed by eye, so `.zshrc` in it left the gate 32/32
   green and the guard overwrote a shell configuration with everything
   working as designed (DP154). The contents are now asserted by category:
   a relative path, in the directory that platform's supervisor reads job
   descriptions from, with a suffix it loads, in this product's namespace.
   Every git call uses a read-only subcommand *and* `GIT_OPTIONAL_LOCKS=0`.
2. **Never scan sealed directories.** A conservative built-in list,
   extendable by the user, pruned during every walk.
3. **The user's data stays on the user's machine.** No telemetry, no
   network by default, nothing published without an explicit act.
4. **Sensitive entries expose method only.** A project marked sensitive
   is read through a whitelist of keys; the rest is never read.
5. **Born English.** Every tracked file is **ASCII**, apart from three
   named typographic marks the check asserts are punctuation rather than
   letters. Brand CJK appears only escaped. This said "no CJK and no
   emoji" until M4 and that is a different rule: a French accent was in
   none of the twenty-seven named ranges, so an unescaped `fr.json` with
   161 raw non-ASCII characters in it scanned clean (DP147). The Chinese
   brand name is never romanized and never translated - `murscope` is
   the Latin name and there is no third one. Since M5's first stage that
   is Rule 34 in `CONTRIBUTING.md`, which is the file a contributor
   reads, and a check that **generates** the spelling space from the
   brand's syllables rather than listing spellings (DP161).

## Pre-flight

Before claiming any work done:

```
python3 scripts/run_checks.py
```

It needs Python 3.9+, `setuptools`, and a **JavaScript engine on PATH** -
`node`, `deno` or `bun`. The engine arrived at M4 because the board's
behaviour is three hundred lines of JavaScript that nothing here executed:
the whole project table could be deleted from the template with the gate
29/29 green and the selftest green on both roster shapes (DP149). It is a
requirement of the gate and never of the product - ADR-0001 stands, the
package has zero runtime dependencies and ships no toolchain. With no
engine present that check is red rather than skipped, deliberately.

Still one command, deliberately - a discipline with two commands is a
discipline where somebody runs one of them. It now runs `murscope selftest`
as its last step, because the runtime guards live there (the sensitive
canary, the network audit hook, the read-location assertion) and for five
milestones they sat on a path neither CI nor this instruction walked:
putting a withheld key back into the whitelist left the gate green with
only the selftest red.

It runs the selftest **twice** - once against an empty throwaway home and
once against a roster naming a fabricated project outside it. The
empty-roster run was the only one for five milestones, which meant the
gate never ran the shape every user is in: `murscope init` writes a
roster, and a defect that made `selftest` exit 1 on every machine with one
sat behind a green gate the whole time (DP114). The fixture project is
synthetic and written to a temporary directory; nothing here reads the
owner's workspace.

CI runs the same command, and then runs `murscope selftest` again from a
built and installed wheel outside the checkout - a different class of
defect, because a fixture missing from the wheel cannot be seen from the
source tree. That second run is CI's because it needs a build and a fresh
environment.

Green gate or it did not happen. "Verified" means the command was run
and its output shown; otherwise write "unverified".

## Working rules

- Zero third-party runtime dependencies. Extras exist for that (ADR-0001).
- A rule without a check is wall art: add the script in the same change,
  or write an `Enforcement:` line naming the non-code mechanism.
- Any countable claim in the docs needs a check behind it, or is not
  written. A hand-written number is a claim, not a fact.
- Governed docs (`design/`, `templates/`) carry
  `title / type / captured / status` frontmatter.
- `DP<n>` cites the decision ledger of the development repository
  this tree is derived from (DP160). That ledger is not published;
  the reasoning that survives publication is in `CONTRIBUTING.md`.
- The public repository is a **derivation**, not a copy (DP162).
  `scripts/public_tree.py` holds the whole of it - what is withheld, what
  is rewritten and why, what is regenerated - and Rule 35 runs that
  derivation and reads the tree it produces. Adding a document that
  points into a withheld directory turns the gate red here, before
  publication rather than after - and since M5's second stage, so does
  naming a commit of this repository, a pull request, or a section
  number into a document nobody can open (DP165). That half caught the
  spec itself first: a rewrite removing a hash has to quote it. For
  three stages all of that read `.md` and `.py` and nothing else, so an
  ignore file disclosing the owner's private material by category, a CI
  step red on its first public run, and a link to this repository went
  out under a green gate (DP169). Every file that decodes as text is
  read now, and a link naming a repository other than the one a tree is
  is a finding too - measured against the clone's own `origin`, never
  against a name written down. What no check settles is a sentence true
  here and false there; that is what the reading before publication is
  for (DP170).
- **No repository in this line is published by being made public**
  (DP164). Publication is the derivation above, and this tree is its
  result; `PUBLICATION.md` declares the rule and Rule 36 checks it.
  Whether a development repository's visibility is still shut is asked
  where that repository is and cannot be asked here - a derivation
  carries no evidence about its source. Rule 36's check reads the
  derivation spec to work out which tree it is in, and says which on
  every run.
- **No real person's name reaches what is published** (DP19, Rule 37).
  `LICENSE` carries the copyright holder and is the check's own seed:
  the spellings are generated from it, and removing the name there turns
  the rule red rather than switching it off.
- The maker does not declare done. A change is judged by somebody
  other than the person who made it.
