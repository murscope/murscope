"""The public repository is a derivation of this one, and this is its spec.

DP160 ruled that the release is a **second repository**, founded from a
clean tree, and DP161's owner ruling took two directories out of it:
`mgmt/` and `tasks/` are the owner's own working files and are not
published. What that turns the public repository into is the thing this
file exists to say out loud:

    the public tree is not a subset of this one. It is a transform.

A subset would be a copy with two directories missing, and it would ship
with ten sentences pointing at directories that are not there - a table
row naming the management console, a rule naming four governed
directories when the tree has two, a check whose `GOVERNED_DIRS`
enumerates a path nothing walks. Those sentences are correct here and
wrong there, and "documentation that points at something absent" is the
exact class of defect this line has spent five milestones catching in
its own prose.

So the derivation is written down, executable, and repeatable, in one
place:

* **EXCLUDED** - what does not go, each with the reason it does not;
* **REWRITES** - what is rewritten on the way out, each with the reason;
* **REGEX_REWRITES** - the same, where a literal would be the problem;
* **DERIVED** - what is regenerated afterwards rather than copied.

The fourth table has one reason to exist and it is worth stating up
here. A rewrite that removes a commit hash has to **quote** that hash,
so a literal table publishes exactly what its rewrite takes out - and
this file, not its target, is where Rule 35's coordinate half found the
development repository's history. Making this file rewrite itself only
moves the quotation up a level. A pattern names the shape without naming
the history, which is the move Rule 34 already makes for the brand. It
has now happened twice, for a URL rather than a hash and found by a
different half of the same rule, which is the argument for that table
made a second time by something other than an author's judgment.

**What the rewrites are for has widened, and it is worth naming.** The
first round answered *references*: a sentence pointing at a path the
derivation takes away. The round after answered *assertions*: a sentence
stating something true of the repository it is written in and false of
the repository it is published into. A check finds the first kind. The
second kind is found by reading the extracted tree as a stranger, which
is a step in the pre-publication audit and not a thing any scanner does
(DP170) - and the reason each of those rewrites exists is written beside
it, because a reader who disagrees with one should be able to.

Everything tracked that is not excluded is included. That direction
matters: a manifest that listed what to *include* would silently drop
every file added after it was written, and the drop would look like a
decision. `extract()` therefore refuses a tracked file it cannot
classify, and no count of files appears anywhere in this file - the
numbers are measured and printed (DP159).

**The rewrites are idempotent on purpose.** Each one is satisfied either
by the text it removes being present, or by the text it leaves being
present already. That is what lets the public tree run this extraction
on itself and stay green, which is what lets Rule 35's check ship in the
public repository rather than being one more thing that only works here.
The failure it still catches is the one worth catching: a document
edited until neither form is there any more, so a rewrite that used to
fire now quietly does nothing.

**What this file does not do.** It does not create a repository, push
anything, or tag anything - DP160 puts all three behind an owner ruling
and a full pre-publication audit. It writes a tree into a directory you
name, and Rule 35 reads that tree.

Usage:

    python3 scripts/public_tree.py --list
    python3 scripts/public_tree.py --extract <directory>
"""
from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

# Where this derivation goes. `owner/name` and no host: the host is a
# fact about the clone in front of you and is read from `origin`, so
# writing one here would be a second copy of it, correct in one place and
# quietly wrong in the other.
#
# DP168 named this repository and this file did not contain the name,
# which is a gap in the spec rather than strictness in the check that
# reads it. Rule 35's repository half asks "which repository may a
# published file name", answers it with "the one it is in", and had no
# way to know which one that was going to be: run from here, the tree
# being scanned is bound for somewhere this file never said, so the
# honest answer was *none*, and every URL on the host - including one
# naming this very destination - was a finding.
#
# Naming it **narrows** the criterion rather than relaxing it. The
# allowed set goes from empty to exactly one repository, so a link to the
# development repository is still a finding, and so is any third
# repository on the host. What stops being a finding is the one link that
# was always going to be correct.
#
# It also collapses the rule's two modes into one. It used to answer
# differently depending on which repository the check ran in; now both
# modes ask the same question of the same table, and when the tree
# already *is* the derivation, `origin` and this line have to agree -
# a disagreement means either this name is stale or the clone is not the
# repository it claims to be, and Rule 35 says so rather than picking one.
DESTINATION = "murscope/murscope"

# Path prefixes that stay in the development repository, with the reason
# each one does. A prefix ending in "/" is a directory and covers
# everything under it.
EXCLUDED = (
    ("mgmt/",
     "the owner's management console - BOOT, MGMT and the decision ledger. "
     "It is how this line is run, not what it ships (owner ruling, DP161)"),
    ("tasks/",
     "the milestone task books. Same reason: they are the instrument the "
     "work was commissioned with, and they name windows, stages and "
     "acceptance rounds that mean nothing outside this repository"),
)

# What gets rewritten on the way out. One entry per file, each a tuple
# of (find, replace, why). `find` must appear verbatim, or `replace`
# must already be there - see the note on idempotence above.
REWRITES = {
    "CLAUDE.md": (
        (
            "| `mgmt/` | Management console (`BOOT` / `MGMT` / `DECISIONS`) |\n"
            "| `design/` | ADRs. `tasks/` task books. `templates/doc.md` "
            "frontmatter template |\n",
            "| `design/` | ADRs. `templates/doc.md` frontmatter template |\n",
            "the layout table describes the tree the reader has in front of "
            "them, and two of its rows describe directories the public tree "
            "does not carry",
        ),
        (
            "- Governed docs (`mgmt/`, `design/`, `tasks/`, `templates/`) carry\n"
            "  `title / type / captured / status` frontmatter.\n"
            "- Decisions land in `mgmt/DECISIONS.md`, append-only.\n",
            "- Governed docs (`design/`, `templates/`) carry\n"
            "  `title / type / captured / status` frontmatter.\n"
            "- `DP<n>` cites the decision ledger of the development repository\n"
            "  this tree is derived from (DP160). That ledger is not published;\n"
            "  the reasoning that survives publication is in `CONTRIBUTING.md`.\n",
            "the governed-directory list has to match the tree, and the "
            "ledger line is the one place a reader is told where a DP number "
            "goes - turning it into an honest sentence is better than "
            "deleting it and leaving the numbers unexplained",
        ),
        (
            "- **This repository is never published by being made public** "
            "(DP164).\n  Publication is the derivation above, into a second "
            "repository;\n  `PUBLICATION.md` declares it and Rule 36 checks "
            "it. The gate cannot\n  ask the host - Rule 11 forbids a network "
            "tool anywhere under\n  `scripts/` - so the probe is a CI step "
            "and Rule 36's job is to keep\n  that step honest. It prints what "
            "a flipped switch would release,\n  measured, and says out loud "
            "that between two CI runs nothing is\n  watching.\n",
            "- **No repository in this line is published by being made "
            "public**\n  (DP164). Publication is the derivation above, and "
            "this tree is its\n  result; `PUBLICATION.md` declares the rule "
            "and Rule 36 checks it.\n  Whether a development repository's "
            "visibility is still shut is asked\n  where that repository is "
            "and cannot be asked here - a derivation\n  carries no evidence "
            "about its source. Rule 36's check reads the\n  derivation spec "
            "to work out which tree it is in, and says which on\n  every "
            "run.\n",
            "the constitution's own statement of DP164 reads as a claim about "
            "the repository the file is in, and in the published one it is "
            "the opposite of true. The ruling is about the line; the sentence "
            "has to say so where a stranger reads it",
        ),
        (
            "- The maker does not declare done. Acceptance runs in a fresh "
            "context\n  against the task book.\n",
            "- The maker does not declare done. A change is judged by "
            "somebody\n  other than the person who made it.\n",
            "the rule survives publication and the machinery it names does "
            "not. In this tree acceptance runs in a second window against a "
            "task book, and both of those are withheld - a reader of the "
            "public tree has no task book, no execution window and no "
            "acceptance window, so the sentence sends them to look for three "
            "things that are not there. What is left when those are removed "
            "is the part that was doing the work: the person who made a "
            "change is not the person who judges it done. That is actionable "
            "by a stranger with a pull request and a reviewer, which is the "
            "test for whether a rule belongs in a contributor-facing file at "
            "all. **The published form says what is true where it lands and "
            "makes no claim about how this line runs** - not `a fresh "
            "context`, which is a fact about the machinery here rather than "
            "an instruction anybody can follow, and not the task book, which "
            "is named and explained in CONTRIBUTING.md and deliberately not "
            "pointed at",
        ),
    ),
    "CONTRIBUTING.md": (
        (
            "Every `.md` under `mgmt/`, `design/`, `tasks/` and `templates/` "
            "starts",
            "Every `.md` under `design/` and `templates/` starts",
            "Rule 4 names the directories it governs, and it may not name one "
            "that is not there",
        ),
        (
            "| b | An `.md` under `mgmt/` missing the `captured` key |",
            "| b | An `.md` under `design/` missing the `captured` key |",
            "a reverse-verification case is an instruction to construct "
            "something; it has to be constructible in the tree it is written "
            "in",
        ),
        (
            "Every other irreversible thing in this repository is a file, and "
            "files\nhave a diff, a review and a gate. **This one is a "
            "setting.** DP160 ruled\nthat the release is a second repository "
            "founded from a clean tree, and\nfor five milestones that ruling "
            "was the only thing standing between the\nsettings page and "
            "everything here being readable in one click. No check,\nno CI "
            "step, no repository configuration. A decision, not a gate - "
            "the\nwall art Rule 1 has refused since the first commit, hanging "
            "on this\nrepository's own wall the whole time.\n",
            "Every other irreversible thing in this line is a file, and files "
            "have a\ndiff, a review and a gate. **This one is a setting.** "
            "DP160 ruled that\nthe release is a second repository founded "
            "from a clean tree - the one\nyou are reading - and for five "
            "milestones that ruling was the only thing\nstanding between a "
            "settings page and a development repository's whole\nhistory "
            "being readable in one click. No check, no CI step, no "
            "repository\nconfiguration. A decision, not a gate - the wall art "
            "Rule 1 has refused\nsince the first commit, hanging on the wall "
            "of the repository that\nrefused it.\n",
            "Rule 36's opening says everything here would become readable in "
            "one click, in a repository where everything is readable already "
            "and by decision. The rule is right and its subject is the other "
            "repository",
        ),
        (
            "Work lands on `main` through pull requests. The M0 scaffol"
            "d commits are\nexempt: they create the branch protection's "
            "own preconditions.\n\nBranch protection was attempted at M1 "
            "acceptance and refused:\n\n    403 Upgrade to GitHub Pro or "
            "make this repository public\n        to enable this feature"
            ".\n\nProtection on a private repository needs a paid plan; t"
            "his one is\nprivate until M5 by design (DP40), so the mecha"
            "nism this rule originally\nnamed is not available and will "
            "not be until the repository goes public.\n\nThe replacement "
            "landed at M2 and is a check rather than a promise: every\nc"
            "ommit on `main` after the founding phase carries a pull-re"
            "quest\nreference, verified offline from git history. The fo"
            "unding boundary is\nthe last M0 scaffold commit, named in a"
            " constant in the check, because\nthose commits created the "
            "preconditions review depends on and could not\nthemselves h"
            "ave been reviewed.\n\nIt will not stop a determined author -"
            " `(#99)` can be typed into a\nsubject and no offline check "
            "can tell that from a merge. It catches the\naccidental dire"
            "ct push, which is the failure that actually happens.\n\n**It"
            "s first run found seven.** Five were genuine direct pushes"
            " during\nthe M1 and M2 rounds; two were real squash merges "
            "whose `(#N)` was lost\nwhen the subject was edited at merge"
            " time. History on a shared branch is\nnot rewritten to make"
            " a check pass, so those seven are enumerated in the\ncheck "
            "by hash with a reason each, and the list is frozen: a new\n"
            "violation is a finding. Moving the boundary until they fel"
            "l outside it\nwould have been fitting the line to the data,"
            " which is the one habit\nthis repository refuses (DP52).\n",
            "Work lands on `main` through pull requests.\n\nBranch "
            "protection is the mechanism this rule originally named, and "
            "it\nis a setting on a hosting account rather than a fact "
            "about a tree.\nThis check needs no account at all: it reads "
            "the history in front of\nyou, which is the same evidence a "
            "reviewer has and is available\noffline. That is the "
            "replacement, and it is a check rather than a\npromise - "
            "every commit on `main` after the founding phase carries a\n"
            "pull-request reference, verified from git history.\n\n**The "
            "founding boundary here is empty**, which means this ref's "
            "own\nroot commit. A tree founded from a clean start has no "
            "founding phase\nto exempt, because its first commit is the "
            "founding one and everything\nafter it went through review "
            "like anything else. An empty boundary is\nnot a fallback "
            "for a named one that failed to resolve: that stays a\n"
            "finding, because a hash gone from history is a stale list, "
            "and a stale\nlist is the failure this rule refuses.\n\nIt "
            "will not stop a determined author - `(#99)` can be typed "
            "into a\nsubject and no offline check can tell that from a "
            "merge. It catches the\naccidental direct push, which is the "
            "failure that actually happens.\n\n**The frozen table of "
            "pre-existing violations is empty here**, for the\nsame "
            "reason the boundary is. It stays in the check because the "
            "rule it\nbelongs to does: an exception is written down "
            "rather than absorbed into\nthe boundary, which would be "
            "fitting the line to the data - the one\nhabit this line "
            "refuses (DP52).\n",
            "the whole of Rule 2's explanation is a set of facts about "
            "the development repository: a 403 from a hosting account, a "
            "plan tier, a repository that is private by design, a "
            "founding boundary naming a scaffold commit, and seven "
            "enumerated violations of a history this tree does not have. "
            "The check itself is already rewritten - the boundary and "
            "the table are emptied by pattern - so without this the file "
            "a contributor reads would describe a constant the shipped "
            "check no longer holds, and would tell a reader of a public "
            "repository that it is private. Found by reading the "
            "extracted tree, not by any half of Rule 35 (DP170)",
        ),
        (
            "probe is a step in the CI workflow, where the network is "
            "expected and\nthe repository is already identified, and it fails "
            "the job when the\nanswer is not `private`. This check reads that "
            "step and refuses to pass\nif it has been removed, has lost its "
            "token, has stopped naming the\nrepository being built, or has "
            "stopped being able to fail the job.",
            "probe is a step in the **development** repository's CI workflow, "
            "where\nthe network is expected and the repository is already "
            "identified, and\nit fails the job when the answer is not "
            "`private`. There is no such\nstep in a derived tree and the "
            "check does not look for one there. Where\nthere is one, the "
            "check reads it and refuses to pass if it has been\nremoved, has "
            "lost its token, has stopped naming the repository being\nbuilt, "
            "or has stopped being able to fail the job.",
            "the paragraph tells a reader the probe is a step in the CI "
            "workflow, and the derivation takes that step out of the "
            "published one - so the sentence would point at a step nobody "
            "holding this tree can find",
        ),
    ),
    "design/ADR-0003-port-baseline-from-the-reference-implementation.md": (
        (
            "appears anywhere under `murscope/`, `scripts/`, `tasks/` or "
            "`design/`.",
            "appears anywhere under `murscope/`, `scripts/` or `design/`.",
            "a measurement over four directories is still true over three of "
            "them; naming the fourth here would be pointing a reader at a "
            "directory they cannot open",
        ),
    ),
    "templates/doc.md": (
        (
            "Every markdown file under `mgmt/`, `design/`, `tasks/` and "
            "`templates/`",
            "Every markdown file under `design/` and `templates/`",
            "the template states the scope of Rule 4 and has to state the "
            "same scope the rule does",
        ),
    ),
    ".github/pull_request_template.md": (
        (
            "`LICENSE` carries the copyright holder and\n"
            "      `mgmt/` names roles; both are correct and out of scope for "
            "this one",
            "`LICENSE` carries the copyright\n"
            "      holder, which is correct and out of scope for this one",
            "the checklist item explains where a real name is allowed to "
            "appear, and one of the two places it names is not published",
        ),
    ),
    "scripts/checks/all_changes_via_pr.py": (
        (
            "Branch protection is the mechanism this rule named and it is not\n"
            "available: protection on a private organisation repository needs "
            "a paid\ntier, and this repository is private until M5 by design "
            "(DP50). So the\nrule pointed at nothing, which is the wall art "
            "Rule 1 forbids, and this\nis the replacement.\n",
            "Branch protection is the mechanism this rule named, and this "
            "check is\nthe offline replacement for it. A protection rule is a "
            "setting on a\nhosting account; this reads the history that is in "
            "front of you, which\nis the same evidence a reviewer has and "
            "needs no account at all.\n",
            "the paragraph explains why the rule is enforced this way by "
            "citing a fact about the development repository - that it is "
            "private, on a tier without protection - and neither half of that "
            "is true of the repository the reader is holding",
        ),
        (
            "**The baseline is enumerated, dated, and frozen.** When this "
            "check was\nfirst run it found seven pre-existing commits with no "
            "reference: five\ngenuine direct pushes from the M1 and M2 rounds, "
            "and two squash merges\nwhose subject was edited at merge time so "
            "the `(#N)` GitHub would have\nadded was lost. History on a shared "
            "branch is not rewritten to make a\ncheck pass, so those seven are "
            "listed below by hash, with the reason,\nand the list may not grow "
            "- a new violation is a new finding, and that\nis the whole point "
            "of writing the old ones down instead of moving the\nboundary "
            "until they disappeared. Moving the boundary would have been\n"
            "fitting the line to the data, which is the one thing this "
            "repository has\nconsistently refused to do (DP52).\n\n"
            "**The boundary is a hash here and is empty in a tree founded "
            "clean.**\n`scripts/public_tree.py` rewrites both tables on the "
            "way out, because a\nrepository created from a clean tree has none "
            "of these eight commits and\nthis check would be red on its first "
            "run - a gate that is red on day one\nteaches a reader to ignore "
            "it, which costs more than the rule buys. An\nempty boundary means "
            '"start at this ref\'s own root commit": there is no\nfounding '
            "phase to exempt when the first commit *is* the founding. An\n"
            "empty boundary is not a fallback for a named one that does not "
            "resolve -\nthat stays a finding, because a hash gone from history "
            "is the stale list\nthis rule already refuses.\n",
            "**The baseline is this repository's own root commit.** This tree "
            "was\nfounded clean, so there is no founding phase to exempt and "
            "no\npre-existing violation to enumerate: the frozen list below is "
            "empty and\nthe boundary is empty, which means \"start at this "
            "ref's own root\". An\nempty boundary is not a fallback for a "
            "named one that does not resolve -\nthat stays a finding, because "
            "a hash gone from history is a stale list,\nand a stale list is "
            "the failure this rule refuses.\n",
            "the two paragraphs describe eight commits of another "
            "repository's history, none of which exists here, and they are "
            "the prose half of the four rewrites that follow",
        ),
        (
            "# The last M0 scaffold commit. Everything up to and including it "
            "created\n# the preconditions this rule depends on - the "
            "repository, the gate, the\n# console - and could not itself have "
            "gone through review. Named here\n# rather than computed so that "
            "the exemption is a line somebody can read\n# and argue with, "
            "rather than a window that moves on its own.\n#\n"
            "# Empty means \"this ref's own root commit\", which is what a "
            "repository\n# founded from a clean tree needs: no founding "
            "phase, nothing to exempt.\n",
            "# Empty: this ref's own root commit. This repository was founded "
            "from a\n# clean tree, so there is no founding phase to exempt and "
            "no commit to\n# name here - the first commit is the founding one "
            "and everything after\n# it went through review like anything "
            "else.\n",
            "the comment explains a named boundary, and the line below it "
            "stops naming one",
        ),
        (
            "# Pre-existing violations, frozen. Each is a fact about history "
            "rather\n# than a licence: they are the reason this check was "
            "written.\n#\n#   direct pushes to main, M1 and M2 rounds\n"
            "#   squash merges whose (#N) was removed when the subject was "
            "edited\n",
            "# Pre-existing violations, frozen and empty. There are none in "
            "this\n# repository: it was founded from a clean tree, so the "
            "first commit is\n# the founding one and everything after it went "
            "through review. The\n# table stays because the rule it belongs "
            "to does - an exception is\n# written down rather than absorbed "
            "into the boundary.\n",
            "same again for the table below it, which stops having rows",
        ),
    ),
    # The six rewrites below came out of the second pre-publication
    # audit, and what they have in common is worth saying once here.
    # Every one of them is in a file that says something **true of the
    # repository it is written in and false of the repository it is
    # published into** - not a path pointing at something absent, which
    # is what the first round of rewrites was about, but a sentence
    # asserting a fact about a different repository. Four of the six sit
    # in files no half of Rule 35 read at all until DP169; the other two
    # would have passed every half even then, because no scanner settles
    # whether a sentence is true somewhere else. That is why the audit is
    # a reading and not only a run (DP170).
    ".gitignore": (
        (
            "# Owner-private material. NEVER track these. This repository is "
            "never\n# published by being made public (DP164) - the release is "
            "a derivation\n# into a second repository - and that is not a "
            "reason to relax: git\n# history is permanent, a file committed "
            "once is exposed forever unless\n# the history is rewritten, and "
            "who may read this repository is a\n# setting rather than a fact. "
            "Everything listed here stays on disk in\n# the working directory "
            "(windows still read it) but must not enter a\n# single commit.\n"
            "#\n# 1. The AI memory mirror: the owner's identity, profile, "
            "goals, habits.\nmemory-mirror/\n#\n"
            "# 2. Pre-repo founding material, written in Chinese and full of "
            "the\n#    owner's real project roster, coverage statistics and "
            "personal\n#    handles. It now lives in the separate private "
            "murscope-vault repo\n#    (see mgmt/BOOT.md for the path). These "
            "two lines stay as defence\n#    in depth: if a copy is ever "
            "dropped back in here by hand, it is\n#    ignored rather than "
            "staged.\nBRIEF.md\narchive/\n",
            "# Working files that are never committed. The reason is the same "
            "for\n# every entry: git history is permanent, so a file "
            "committed once is\n# exposed for as long as the repository is, "
            "and an ignore pattern costs\n# nothing while an unstaged mistake "
            "cannot be taken back. What these\n# name is local to whoever is "
            "working in the tree. None of it is part of\n# the product, and "
            "nothing that is part of the product is ignored.\n"
            "memory-mirror/\nBRIEF.md\narchive/\n",
            "the comment describes the owner's private material by category - "
            "identity, profile, goals, habits, a real project roster, "
            "coverage statistics, personal handles - names a second private "
            "repository, and points at a file inside a withheld directory. "
            "The patterns themselves disclose nothing and stay; the paragraph "
            "explaining them is a disclosure with no reader it was written "
            "for. It reached the extracted tree because nothing read a file "
            "with no suffix (DP169)",
        ),
    ),
    ".github/workflows/checks.yml": (
        (
            "      # Rule 36's probe. The one thing in this repository that "
            "cannot be\n      # undone is not in a file - it is the "
            "visibility toggle, and a\n      # toggle has no diff, no review "
            "and no gate. PUBLICATION.md holds\n      # the ruling; this step "
            "is the only thing in the whole line that\n      # can observe "
            "whether the ruling still holds.\n      #\n"
            "      # It is here rather than in a check script because Rule 11 "
            "forbids\n      # every module under scripts/ from shelling out "
            "to a network tool,\n      # `gh` among them, and buying one "
            "probe with an exemption to that\n      # rule is the trade every "
            "hole in this repository's history began\n      # with. So the "
            "probe lives where the network is expected, and\n"
            "      # `publication_is_a_derivation_never_a_switch` reads this "
            "file and\n      # goes red if the step is removed, loses its "
            "token, or stops being\n      # able to fail the job.\n      #\n"
            "      # `GITHUB_REPOSITORY` rather than a literal, so the step "
            "is about\n      # the repository actually being built. A failed "
            "`gh` leaves the\n      # variable empty and the comparison fails "
            "- a probe that could not\n      # answer is not an answer.\n"
            "      - name: Refuse to be public\n        env:\n"
            "          GH_TOKEN: ${{ secrets.GITHUB_TOKEN }}\n"
            "        run: |\n          set -eu\n"
            "          visibility=$(gh api \"repos/${GITHUB_REPOSITORY}\" "
            "--jq .visibility || true)\n"
            "          echo \"visibility: '${visibility}'\"\n"
            "          if [ \"${visibility}\" != \"private\" ]; then\n"
            "            echo \"FAILED: Rule 36. PUBLICATION.md declares "
            "Switch: never, and\"\n"
            "            echo \"this repository's visibility is "
            "'${visibility}'. Publication\"\n"
            "            echo \"is a derivation into a second repository "
            "(DP160, DP162); it\"\n"
            "            echo \"is never this repository's toggle. Make it "
            "private again,\"\n"
            "            echo \"then read scripts/checks/"
            "publication_is_a_derivation_never_a_switch.py\"\n"
            "            echo \"for what a flip releases.\"\n"
            "            exit 1\n          fi\n",
            "      # **No visibility probe here, and that is the ruling "
            "rather than an\n      # omission.** Rule 36 watches a setting "
            "rather than a file, and the\n      # setting it watches belongs "
            "to the development repository this tree\n      # was derived "
            "from - which this tree cannot ask after and carries no\n"
            "      # evidence about. What this tree is, is the publication: "
            "everything\n      # in it arrived by derivation, so there is no "
            "switch here whose flip\n      # would release anything that is "
            "not released already.\n      #\n"
            "      # The gate below still runs Rule 36's check. It reads the "
            "derivation\n      # spec to work out which tree it is in, says "
            "which on every run, and\n      # asks the probe question only "
            "where there is a probe to ask about.\n",
            "the step fails the job on any repository whose visibility is not "
            "`private`, and the published repository is public by "
            "construction - so it is red on its first run there and on every "
            "run after, which is the day-one-red gate this line refuses. It "
            "reached the extracted tree because nothing read `.yml` (DP169). "
            "Rule 36's check needs no step here: it detects a derived tree "
            "from the exclusion table and does not ask the probe question of "
            "one",
        ),
    ),
    "PUBLICATION.md": (
        (
            "This repository is the development line. **It does not become "
            "public by\nbeing made public.** Publication has exactly one "
            "mechanism, and that\nmechanism is a derivation into a separate "
            "repository (DP160, DP162).\n",
            "This repository is the published derivation. **Nothing here was "
            "released\nby being made public.** Every file in this tree was "
            "produced from a\ndevelopment repository by the one mechanism "
            "this line has for publishing\nanything, and that mechanism is "
            "named below (DP160, DP162).\n",
            "the opening sentence says this repository is the development "
            "line and does not become public by being made public. In the "
            "published repository both halves are false, and they are the "
            "first thing a stranger reads",
        ),
        (
            "`Switch: never` is the ruling: this repository's visibility is "
            "not a\nrelease channel and flipping it is not a way to publish. "
            "`Mechanism:`\nnames the file that holds the whole derivation - "
            "what is withheld, what\nis rewritten, what is regenerated - and "
            "Rule 36's check refuses a\nmechanism that is not really one, so "
            "this cannot decay into a filename\nthat stopped meaning "
            "anything.\n",
            "`Switch: never` is the ruling, and it is a ruling about every "
            "repository\nin this line rather than about one of them: no "
            "repository here is\npublished by having its visibility flipped. "
            "A flip releases a history\nand derives nothing - it withholds "
            "nothing, rewrites nothing and\nregenerates nothing. `Mechanism:` "
            "names the file that does all three,\nand Rule 36's check refuses "
            "a mechanism that is not really one, so this\ncannot decay into a "
            "filename that stopped meaning anything.\n",
            "the paragraph reads `Switch: never` as a statement about this "
            "repository's own visibility, which in a repository that is "
            "public reads as a plain contradiction. The ruling is about the "
            "line rather than about one repository in it, and that is what it "
            "has to say where it can be read by anybody",
        ),
        (
            "Every other irreversible thing in this line is a file, and files "
            "have\nchecks. This one is a **setting**, and until Rule 36 it "
            "had nothing: no\ncheck, no CI, no repository configuration stood "
            "between somebody opening\nthe settings page and everything in "
            "this repository becoming readable in\none click. DP160 ruled "
            "that the release is a second repository, which is\nthe decision "
            "that prevents it - and a decision without a check is the\nwall "
            "art Rule 1 has refused since the first commit. It took until M5 "
            "for\nthat argument to be turned on this repository itself.\n",
            "Every other irreversible thing in this line is a file, and files "
            "have\nchecks. This one is a **setting**, and until Rule 36 it "
            "had nothing: no\ncheck, no CI, no repository configuration stood "
            "between somebody opening\na settings page and a development "
            "repository's whole history becoming\nreadable in one click. "
            "DP160 ruled that the release is a second\nrepository - the one "
            "you are reading - and a decision without a check is\nthe wall "
            "art Rule 1 has refused since the first commit. It took until "
            "M5\nfor that argument to be turned on the repository making "
            "it.\n",
            "\"everything in this repository becoming readable in one click\" "
            "describes a risk that has already been taken deliberately here: "
            "everything in this repository is readable, on purpose, because "
            "this is the publication",
        ),
        (
            "## What the switch would release, and why it is more than you "
            "think\n\nNot the working tree. The whole history, and history is "
            "wider than any\nbranch:\n\n- every commit on `main`, and every "
            "commit on every other ref;\n- **every pull request head, "
            "permanently.** GitHub keeps `refs/pull/N/head`\n  for each pull "
            "request ever opened, and anyone with read access fetches\n  them "
            "with one refspec. Those carry the pre-squash commits - the "
            "drafts,\n  the reverted attempts, the messages nobody edited - "
            "and `git log --all`\n  in a normal clone does not show them, so "
            "an audit that reads the local\n  history alone will undercount "
            "what a stranger receives;\n- every workflow run's logs, which "
            "quote command output verbatim.\n\nRule 36's check measures what "
            "it can measure offline and prints it, so\nthe number is in front "
            "of whoever is deciding. No count is written down\nhere: a "
            "hand-written number is a claim, not a fact (DP159), and this "
            "is\nexactly the file where a stale number would be worst.\n\n"
            "## What the check can and cannot do\n\nIt cannot ask GitHub. "
            "Rule 11 forbids every module under `murscope/` and\nunder "
            "`scripts/` from shelling out to a network tool, `gh` included, "
            "and\nbuying this one probe with an exemption to that rule would "
            "trade a live\nred line for a watcher - which is the trade every "
            "hole in this\nrepository's history began with.\n\nSo the probe "
            "runs where the network is expected and the repository is\nalready "
            "identified: **a step in CI, on every push and every pull\n"
            "request, that asks GitHub for this repository's visibility and "
            "fails the\njob when the answer is not `private`.** Rule 36's "
            "check is what keeps\nthat step honest - it reads the workflow "
            "and refuses to pass if the\nprobe has been removed, has lost its "
            "token, or has stopped being able to\nfail the job.\n\nThat "
            "leaves one real gap, named rather than papered over: **between "
            "two\nCI runs, nothing is watching.** A repository made public "
            "and made\nprivate again inside that window leaves no trace here. "
            "Closing it needs\na mechanism this repository does not own - an "
            "organisation policy, or a\nbranch of GitHub's own settings - and "
            "the honest record is that the\nwatcher is a detector with a "
            "latency, not a lock.\n\n## If it ever comes back red\n\nMake the "
            "repository private again first, then read the check's own\noutput "
            "for what was exposed and for how long. The public release is\n"
            "unaffected either way: it is a different repository, derived by\n"
            "`scripts/public_tree.py`, and nothing about it depends on this "
            "one's\nvisibility.\n",
            "## What this tree can say, and what it cannot\n\n"
            "`scripts/public_tree.py` is in this tree and runs in it. The "
            "derivation\nis idempotent, so extracting this tree yields this "
            "tree and Rule 35\nreads the result - which is what makes the "
            "derivation auditable by\nanybody holding this repository rather "
            "than only by whoever ran it:\n\n    python3 "
            "scripts/public_tree.py --list\n    python3 "
            "scripts/public_tree.py --extract <directory>\n\nRule 36's check "
            "asks a third question in a development tree - whether\nthe probe "
            "watching that repository's visibility is still installed, "
            "still\nhas a token, and can still fail the job - and it does not "
            "ask it here.\nIt works out which tree it is in by reading the "
            "derivation spec, and\nsays which on every run rather than "
            "skipping quietly.\n\nThat leaves something worth stating plainly "
            "rather than leaving a reader\nto assume its opposite: **this "
            "tree carries no evidence about the\nrepository it came from.** A "
            "derivation is not a window onto its source.\nWhat is in front of "
            "you is what was published; what was withheld is\nlisted, with "
            "the reason for each, in the spec named above.\n",
            "three sections about the blast radius of a switch, the CI probe "
            "that watches it, and what to do when that probe goes red. None "
            "of the three has a referent in the published repository: there "
            "is no switch left to flip, the probe is not in that tree, and "
            "the instruction \"make the repository private again\" would "
            "un-publish the release",
        ),
    ),
    "scripts/checks/governed_docs_carry_frontmatter.py": (
        (
            "Every .md under mgmt/, design/, tasks/ and templates/ must open "
            "with a",
            "Every .md under design/ and templates/ must open with a",
            "the check's own docstring is its rule statement",
        ),
        (
            'GOVERNED_DIRS = ("mgmt", "design", "tasks", "templates")',
            'GOVERNED_DIRS = ("design", "templates")',
            "this is the one rewrite that is not prose: the check walks these "
            "names against the repository root, so two of them would resolve "
            "to nothing on every run and the walk would report a scope it "
            "does not have",
        ),
    ),
}

# Rewrites whose `find` is a **category** rather than a literal, and the
# only reason this second table exists: a rewrite that removes a commit
# hash has to quote that hash, so the literal table would carry into the
# extracted tree exactly what the rewrite takes out of its target. Rule
# 35's coordinate half found this file rather than `all_changes_via_pr`
# when the first attempt was written that way, and the attempt after it
# - this file rewriting itself - only moved the quotation one level up.
# A pattern names the shape without naming the history, which is the
# move Rule 34 already made for the brand's spellings.
#
# Same tuple as above and the same idempotence: a rewrite is satisfied
# by its pattern matching, or by its replacement already being there.
REGEX_REWRITES = {
    "extras/murscope-ai/README.md": (
        (
            re.compile(r"\(https?://[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)+"
                       r"/[A-Za-z0-9._-]+/[A-Za-z0-9._-]+/?\)"),
            "(../../README.md)",
            "the link points at the repository this tree is, and a relative "
            "link needs no host to be right: it survives a fork, a clone "
            "under another owner, a mirror, and reading the file offline, "
            "none of which an absolute URL does. **This is a preference for "
            "the published tree and not a requirement of the gate, and the "
            "difference is stated because it changed.** The rewrite was "
            "load-bearing when it was written: the link named the development "
            "repository, which is private and stays private (DP164), and the "
            "spec had not yet said where the derivation goes, so every URL on "
            "the host was a finding whatever it named. Both halves of that "
            "are now false - the link names the public repository, and "
            "DESTINATION above tells Rule 35 that this is the one repository "
            "a published file here may name. **Measured rather than reasoned "
            "about: with this entry removed the extraction is green**, the "
            "absolute form survives into the published README and the "
            "repository half does not object. Keeping it is therefore a "
            "choice, and the surviving reason is the one sentence above it - "
            "written down because a rewrite whose reason has quietly expired "
            "is removed by the next reader with nothing going red, which is "
            "the wall art Rule 1 refuses. **A pattern "
            "rather than "
            "a literal, for the second time and the same reason:** written as "
            "a literal, this table quoted the very URL its rewrite removes, "
            "and the repository half found this file instead of its target - "
            "which is how the coordinate half found it in M5's second stage "
            "(DP169). The shape is named; the repository is not",
        ),
    ),
    "scripts/checks/all_changes_via_pr.py": (
        (
            re.compile(r'^FOUNDING_BOUNDARY = "[0-9a-f]{7,40}"$', re.MULTILINE),
            'FOUNDING_BOUNDARY = ""',
            "the founding boundary is a commit of the development "
            "repository. A tree founded clean has no such object, so the "
            "check would be red on its first run there - and a gate that is "
            "red on day one teaches a reader to ignore it",
        ),
        (
            re.compile(r"^GRANDFATHERED = \{[^{}]*\}$", re.MULTILINE),
            "GRANDFATHERED = {}",
            "the enumerated exceptions are seven more commits of this "
            "repository and the only two pull request numbers left anywhere "
            "in the published tree. Every one of them would be reported "
            "there as a stale exception, which is this rule's own way of "
            "saying the list describes somebody else's history",
        ),
    ),
}

# Regenerated in the extracted tree rather than copied, because a
# rewritten file has a different content hash and the freeze records
# hashes. Regenerating is not weakening it: the manifest is derived data
# in both trees, and Rule 1 in the public tree freezes the public tree.
DERIVED = ("scripts/checks_manifest.json",)


def git(args, cwd=None):
    env = dict(os.environ)
    env["GIT_OPTIONAL_LOCKS"] = "0"
    return subprocess.check_output(
        ["git"] + args, cwd=str(cwd or REPO_ROOT), env=env).decode("utf-8")


def tracked_files(root=None):
    """Every tracked path in a tree, repo-relative, sorted."""
    out = git(["ls-files", "-z"], cwd=root)
    return sorted(rel for rel in out.split("\0") if rel)


def excluded_reason(rel):
    """Why this path stays private, or None if it is published."""
    for prefix, reason in EXCLUDED:
        if rel == prefix.rstrip("/") or rel.startswith(prefix):
            return reason
    return None


def classify(rel):
    """('exclude', reason) or ('include', None). Total, by construction.

    Inclusion is the default and exclusion is the enumerated case. The
    other direction - enumerate what ships - drops every file added
    after the list was written, and the drop reads as a decision
    somebody took.
    """
    reason = excluded_reason(rel)
    return ("exclude", reason) if reason else ("include", None)


def apply_rewrites(rel, text):
    """Rewrite one file's text. Returns (text, applied, problems).

    A rewrite is satisfied by either form being present, so running this
    on an already-extracted tree changes nothing and reports nothing.
    What it will not accept is neither form being there: that is a
    document that has drifted out from under its rewrite, and it is the
    failure this whole mechanism exists to notice before publication
    rather than after.
    """
    applied = []
    problems = []
    index = 0
    for find, replace, why in REWRITES.get(rel, ()):
        index += 1
        hits = text.count(find)
        if hits:
            text = text.replace(find, replace)
            applied.append("%s rewrite %d: %d occurrence(s) - %s"
                           % (rel, index, hits, why))
        elif replace in text:
            applied.append("%s rewrite %d: already applied - %s"
                           % (rel, index, why))
        else:
            problems.append(
                "%s rewrite %d matches nothing: neither the text it removes "
                "nor the text it leaves is in the file. The document has "
                "drifted, and a rewrite that quietly does nothing is how the "
                "public tree gets a sentence nobody meant to publish. Reason "
                "it exists: %s" % (rel, index, why))
    for pattern, replace, why in REGEX_REWRITES.get(rel, ()):
        index += 1
        text, hits = pattern.subn(replace, text)
        if hits:
            applied.append("%s rewrite %d: %d match(es) of /%s/ - %s"
                           % (rel, index, hits, pattern.pattern, why))
        elif replace in text:
            applied.append("%s rewrite %d: already applied - %s"
                           % (rel, index, why))
        else:
            problems.append(
                "%s rewrite %d matches nothing: /%s/ finds nothing and the "
                "text it leaves is not there either. A pattern that has "
                "stopped matching is the same drift a literal has, and it is "
                "quieter. Reason it exists: %s"
                % (rel, index, pattern.pattern, why))
    return text, applied, problems


def extract(dest):
    """Write the public tree into `dest`. Returns a report dict.

    Every tracked file is classified, copied or skipped, and rewritten
    if the spec says so. Nothing here counts to a target: the numbers in
    the report are measured off what happened (DP159).
    """
    dest = Path(dest)
    if dest.exists():
        shutil.rmtree(str(dest))
    dest.mkdir(parents=True)

    report = {
        "included": [],
        "excluded": [],
        "applied": [],
        "problems": [],
        "derived": [],
    }

    for rel in tracked_files():
        source = REPO_ROOT / rel
        if not source.is_file():
            report["problems"].append(
                "%s is tracked but is not a readable file" % rel)
            continue
        verdict, reason = classify(rel)
        if verdict == "exclude":
            report["excluded"].append((rel, reason))
            continue
        target = dest / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        payload = source.read_bytes()
        if rel in REWRITES or rel in REGEX_REWRITES:
            try:
                text = payload.decode("utf-8")
            except UnicodeDecodeError:
                report["problems"].append(
                    "%s carries a rewrite but does not decode as UTF-8" % rel)
                shutil.copyfile(str(source), str(target))
                report["included"].append(rel)
                continue
            text, applied, problems = apply_rewrites(rel, text)
            report["applied"].extend(applied)
            report["problems"].extend(problems)
            target.write_text(text, encoding="utf-8")
            shutil.copymode(str(source), str(target))
        else:
            shutil.copyfile(str(source), str(target))
            shutil.copymode(str(source), str(target))
        report["included"].append(rel)

    for rel in sorted(set(REWRITES) | set(REGEX_REWRITES)):
        if rel not in report["included"]:
            report["problems"].append(
                "%s carries a rewrite but is not in the public tree; a "
                "rewrite for a file nobody publishes is a rule with nothing "
                "under it" % rel)

    report["problems"].extend(regenerate_derived(dest))
    return report


def regenerate_derived(dest):
    """Rebuild the files that are computed rather than copied."""
    problems = []
    regenerator = dest / "scripts" / "checks" / "all_rules_have_checks.py"
    if not regenerator.is_file():
        problems.append(
            "the extracted tree has no %s, so the freeze cannot be rebuilt "
            "and every rewritten file would fail its own gate on a hash"
            % regenerator.relative_to(dest).as_posix())
        return problems
    completed = subprocess.run(
        [sys.executable, str(regenerator), "--update-manifest"],
        cwd=str(dest), stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    if completed.returncode != 0:
        problems.append(
            "regenerating the freeze in the extracted tree exited %d: %s"
            % (completed.returncode,
               completed.stdout.decode("utf-8", "replace").strip()))
    for rel in DERIVED:
        if not (dest / rel).is_file():
            problems.append("%s was not produced in the extracted tree" % rel)
    return problems


def main(argv=None):
    args = list(sys.argv[1:] if argv is None else argv)
    if args[:1] == ["--list"] and len(args) == 1:
        print("Excluded from the public tree:")
        for prefix, reason in EXCLUDED:
            print("  %-10s %s" % (prefix, reason))
        print("\nRewritten on the way out:")
        for rel in sorted(set(REWRITES) | set(REGEX_REWRITES)):
            literal = REWRITES.get(rel, ())
            patterned = REGEX_REWRITES.get(rel, ())
            print("  %s (%d rewrite(s), %d of them by pattern)"
                  % (rel, len(literal) + len(patterned), len(patterned)))
            index = 0
            for _, _, why in literal:
                index += 1
                print("    %d. %s" % (index, why))
            for pattern, _, why in patterned:
                index += 1
                print("    %d. /%s/ - %s" % (index, pattern.pattern, why))
        print("\nRegenerated rather than copied:")
        for rel in DERIVED:
            print("  %s" % rel)
        included = [r for r in tracked_files() if classify(r)[0] == "include"]
        excluded = [r for r in tracked_files() if classify(r)[0] == "exclude"]
        print("\n%d tracked file(s): %d published, %d withheld."
              % (len(included) + len(excluded), len(included), len(excluded)))
        for rel in included:
            print("  + %s" % rel)
        for rel in excluded:
            print("  - %s" % rel)
        return 0
    if args[:1] == ["--extract"] and len(args) == 2:
        report = extract(args[1])
        for line in report["applied"]:
            print(line)
        for line in report["problems"]:
            print("PROBLEM: %s" % line)
        print("%d file(s) written to %s; %d withheld; %d rewrite(s) reported."
              % (len(report["included"]), args[1], len(report["excluded"]),
                 len(report["applied"])))
        return 1 if report["problems"] else 0
    print("usage: public_tree.py --list | --extract <directory>")
    return 2


if __name__ == "__main__":
    sys.exit(main())
