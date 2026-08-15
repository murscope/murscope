"""The outbound payload, and the disclosure a consent is bound to.

**This is the one surface where a mistake cannot be undone.** A board
file that says too much can be deleted; a request that has already left
cannot. So the payload is not "the board, serialised" - it is its own,
much smaller thing, built from a declared table and checked against that
table on the way out.

## What leaves, and what does not

Method, and only method: how many projects, which tier each is in, which
state the layer resolved, how many days since the last commit, and the
in-hand counts. **No name, no path, no branch, no commit subject, no
declaration text, no ledger line, no file name.** A project's own words
never cross this boundary at this stage.

**A project marked sensitive does not appear at all.** Red line four says
a sensitive entry exposes method only, and on every other surface that is
what happens - the collector never opens its files and the board carries
the whitelisted keys. Here the answer is stronger, because "method only"
is a judgement about what a shape reveals and this is the one place where
being wrong about that judgement is permanent. So the row is dropped and
the payload carries the *count* of what was dropped, which is method
about the portfolio rather than method about the project.

## The disclosure, and why consent is bound to it

`DISCLOSURE` below is the list the user is shown before they agree, in
their own reading order, each field with a sentence saying what it is. It
is also the thing `consent` fingerprints.

That is the whole ruling of this stage, and it exists because a boolean
consent has a specific way of going wrong: **the payload grows, and the
old agreement silently covers the new, larger thing.** A user agreed to
what they were shown, not to a field name that later acquired a bigger
neighbour. So the fingerprint runs over the table and the destination, and
adding a field to it invalidates every recorded consent - loudly, naming
the field that changed. The cost is one re-consent per payload change. The
alternative is a product that can widen what it sends without asking
again, which is the failure this line would not be able to take back.

**The table and the payload are checked against each other**, in the
direction that matters: `build()` walks what it produced and refuses any
leaf path the table does not declare. Without that the fingerprint would
be over a document rather than over the payload - a promise about a list,
not about what leaves - and the two would drift the first time somebody
added a key without touching the table (DP87: a guard has to contain the
thing it is written to watch).

## What stage four changed, and why each change is a correction

**One: `projects[].id` was described in a way that is false on the default
path.** It read "the id you gave the project in roster.json - not its
name, not its path", and `scan.py` sets `id` to the directory name at
roster time, so on every install where the user never edited that file the
id is exactly the name and the user gave it nothing. The owner read the
real payload of his own workspace and found directory names in it under a
sentence saying they were not names. The wording below is his, and it does
the one thing the old sentence did not: it names the lever - rename it in
`roster.json` and this sends what you renamed it to.

**Two: the request is declared, not only the body.** The reading's table
has always declared the token and the user agent it sends. This one
declared eleven body fields and said nothing about the key that
authenticates them, which is the same omission the other table did not
make. `scope` distinguishes the two: `build()` measures itself against the
`PAYLOAD` rows, and the `REQUEST` rows are what the transport puts around
them. Both are shown, because both leave.

**Three: `instruction` is a field rather than something a transport adds
quietly.** A note needs a sentence telling the model what to do with the
numbers, and that sentence leaves the machine. Putting it in the request
envelope where the disclosure could not see it would have been the exact
failure this table exists to prevent - a payload wider than the document
that was agreed to - so it is declared, it is in the digested bytes, and
it is the same fixed string in every install.

**Four: the counts are one type.** `stash` left as the string `"0"` while
`uncommitted` left as the integer `0`, because `state.counted()` formats
for an evidence line on the board and was reused here. `kind` in the table
below is now checked at build time, so the next reuse of a formatter is a
finding rather than a payload.
"""
from __future__ import annotations

import hashlib
import json

from . import __version__, disclosure, state
from .disclosure import COUNT, FLAG, PAYLOAD, REQUEST, SECRET, TEXT

# The sentence murscope sends with the numbers. It is data - it goes into
# the payload, it is digested with everything else, and it is declared -
# rather than a string the transport wraps around the body where nobody
# reading the disclosure would find it.
#
# Deliberately dull, and deliberately about the numbers rather than about
# the person. A prompt that asks a model to be encouraging produces a note
# that is encouraging whatever the figures say, which is the one thing this
# product exists not to do.
INSTRUCTION = (
    "You are reading one day's summary of a developer's own project "
    "portfolio, as numbers. Write at most six sentences: which projects are "
    "moving, which have gone quiet, and which are waiting on the person "
    "reading this. Use the ids exactly as given. Say only what the numbers "
    "support - if something is not in the data, it is not in the note - and "
    "do not encourage, congratulate or advise."
)

# (path, scope, kind, what it is). The path uses `[]` for "every item of
# this list", which is how `_leaf_paths` below spells the same thing - so
# the two are comparable without either of them knowing about a particular
# project. `shown()` is what a consent is fingerprinted over: the path and
# the sentence, never the scope or the kind, because those are how this
# module checks itself and are not things a user was asked about.
DISCLOSURE = (
    ("auth.token", REQUEST, SECRET,
     "your key for that provider, in the request's authentication header - "
     "`Authorization`, or `x-api-key` where the vendor requires that "
     "instead - which is how the provider knows whose account to bill. It "
     "is read from the key store for the request and goes into no "
     "artifact. A model running on your own machine needs no key and is "
     "sent none"),
    ("headers.user_agent", REQUEST, TEXT,
     "the word `murscope`, so a request on your own provider dashboard is "
     "one you can attribute"),
    ("request.envelope", REQUEST, TEXT,
     "the provider's own wrapper around the document below: the model name "
     "you put in config.toml, the role labels and length limit its API "
     "requires, and a flag asking for one complete answer rather than a "
     "stream. Nothing of yours is in it"),
    ("request.route", REQUEST, TEXT,
     "nothing between here and the destination named above. murscope builds "
     "its own opener with proxies switched off, so an `https_proxy` in your "
     "environment is not used and does not become a second machine your "
     "payload passes through. If your network requires one, the request "
     "fails and says so rather than taking an exit you were never shown"),
    ("instruction", PAYLOAD, TEXT,
     "one fixed sentence murscope wrote, asking the model to summarise the "
     "numbers below and to say only what they support. It ships inside the "
     "package, it is identical on every install, and it carries nothing of "
     "yours"),
    ("generator", PAYLOAD, TEXT,
     "which version of murscope produced this"),
    ("project_count", PAYLOAD, COUNT,
     "how many projects are described below"),
    ("withheld_sensitive", PAYLOAD, COUNT,
     "how many projects were left out because you marked them sensitive - "
     "the number only; nothing else about them leaves"),
    ("projects[].id", PAYLOAD, TEXT,
     "the id in roster.json - which the scan set to the directory name "
     "unless you changed it. Rename it there and this sends what you "
     "renamed it to"),
    ("projects[].tier", PAYLOAD, TEXT,
     "which activity tier it fell into: ACTIVE, WARM, COLD and so on"),
    ("projects[].state", PAYLOAD, TEXT,
     "which kind of state the layer resolved: declared, curated or "
     "inferred - the kind, never the sentence"),
    ("projects[].idle_days", PAYLOAD, COUNT,
     "whole days since its last commit"),
    ("projects[].uncommitted", PAYLOAD, COUNT,
     "how many files are uncommitted"),
    ("projects[].unpushed", PAYLOAD, COUNT,
     "how many commits are unpushed"),
    ("projects[].stash", PAYLOAD, COUNT,
     "how many stash entries it holds"),
    ("projects[].wip", PAYLOAD, FLAG,
     "whether its last commit looks like work in progress"),
)


class DisclosureMismatch(RuntimeError):
    """The payload carries something the disclosure does not declare."""


def shown():
    """((path, sentence), ...). What `consent` fingerprints.

    The sentence is in it because the sentence is what was read. See
    `murscope.disclosure` for the whole argument and for what it costs.
    """
    return disclosure.shown(DISCLOSURE)


def fields():
    """Just the paths, in table order. For messages, never for a digest.

    Kept because a refusal that says "the disclosure changed" sends the
    user to read a diff, and one that names `projects[].id` does not.
    """
    return disclosure.paths(DISCLOSURE)


def disclosure_lines():
    """The table as the lines a user reads before agreeing."""
    return disclosure.lines(DISCLOSURE)


# The payload walk lives in `murscope.disclosure` since M4, because the
# alert table needs the same three functions and a second copy of "which
# leaves of this document are declared" is a copy that will differ once
# (DP116's standing complaint, applied before rather than after). The name
# is kept because it is what this module's own vocabulary calls it.
_leaf_paths = disclosure.leaf_paths


def _count(value):
    """A count as a count, or the fact that nothing counted it.

    Not `state.counted()`, which formats for an evidence line on the board
    and returns a string - `"0"`, or the words for "no source". That is
    right for a board cell and wrong here, and it travelled: `stash` left
    as `"0"` in the same payload where `uncommitted` left as `0`, so the
    document declaring four counts carried three integers and a string.
    Absence stays absence rather than becoming zero, for the reason
    `state.counted` has it: a reader that did not run and a repository with
    nothing to report are not the same fact.
    """
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _row(record):
    resolved = record.get("state") or {}
    return {
        "id": record.get("id"),
        "tier": record.get("tier"),
        "state": resolved.get("kind"),
        "idle_days": state.whole_days(
            record.get("recency_days")
            if isinstance(record.get("recency_days"), (int, float)) else None),
        "uncommitted": _count(state.uncommitted_files(record)),
        "unpushed": _count(state.unpushed_commits(record)),
        "stash": _count(
            ((record.get("signals") or {}).get("stash") or {}).get("entries")),
        "wip": bool(((record.get("signals") or {}).get("last_commit") or {})
                    .get("wip")),
    }


def preview(roster):
    """(ids, withheld) - the rows `build()` would keep, from the roster alone.

    What the consent screen prints, and the reason it can print it without
    a collection: whether a row leaves is decided by `sensitive`, which is
    in `roster.json`, and nothing a collector learns changes it.

    It exists because "it sends project ids" is a description and a list of
    twenty names is the thing itself. The owner read his own real payload
    and found working directory names in it under a sentence saying they
    were not names; a screen that had printed them would have said so
    before the first request rather than after.

    Deliberately the same decision `build()` makes rather than a second one
    that resembles it - a check drives both and asserts they agree, because
    a preview that drifts from the payload is worse than no preview.
    """
    kept = [entry.id for entry in roster if not entry.sensitive]
    return kept, sum(1 for entry in roster if entry.sensitive)


def build(records):
    """The payload, or raise. Method only, sensitive entries withheld.

    Raises `DisclosureMismatch` when the result carries a leaf the
    `DISCLOSURE` table does not declare, or a leaf whose value is not the
    kind that row declares. That is deliberately fatal rather than a
    problem line: a payload nobody consented to must not be sent, and the
    caller's correct response is to stop, not to send a smaller one it
    invented.
    """
    kept = [record for record in records if not record.get("sensitive")]
    withheld = len(records) - len(kept)
    payload = {
        "instruction": INSTRUCTION,
        "generator": "murscope %s" % __version__,
        "project_count": len(kept),
        "withheld_sensitive": withheld,
        "projects": [_row(record) for record in kept],
    }
    declared = set(disclosure.payload_paths(DISCLOSURE))
    strays = sorted(_leaf_paths(payload) - declared)
    if strays:
        raise DisclosureMismatch(
            "the outbound payload carries %s, which the disclosure does not "
            "declare. Nothing is sent: the user agreed to the fields in "
            "murscope.outbound.DISCLOSURE, and a field that is not on that "
            "list is a field nobody was shown. Add it to the table - which "
            "invalidates every recorded consent and asks again - or take it "
            "out of the payload." % ", ".join(strays))
    mistyped = disclosure.kind_findings(DISCLOSURE, payload)
    if mistyped:
        raise DisclosureMismatch(
            "the outbound payload carries a value that is not the kind its "
            "row declares, so nothing is sent: %s" % " ".join(mistyped))
    return payload


def canonical(payload):
    """The payload as the bytes that actually go over the wire."""
    return json.dumps(payload, ensure_ascii=True, sort_keys=True,
                      separators=(",", ":")).encode("utf-8")


def payload_digest(payload):
    """A digest of one payload's bytes, for a record of what was sent."""
    return hashlib.sha256(canonical(payload)).hexdigest()
