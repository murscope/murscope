"""The shape of a disclosure row, shared by every table that has one.

Three tables exist - `outbound.DISCLOSURE` for the daily note,
`contributions.DISCLOSURE` for the reading, and `alerts.DISCLOSURE` for an
alert - and they are deliberately separate documents. What they share is
this shape, and sharing it is not tidiness: `consent.fingerprint` has to be
handed the same kind of thing by all of them, or one is fingerprinted over
something the others are not.

**M4's third table is why the payload walk moved down here.** `leaf_paths`,
`values_at` and `kind_findings` below were private to `outbound`, and the
alert payload needs exactly the same three - it is a different document
checked against its table in the same direction. Copying them would have
been the shape DP116 is a standing complaint about: two copies agree until
somebody edits one, and the thing they would silently stop agreeing about
is which leaves of a payload count as declared.

## A row is four things, and only two of them are shown

    (path, scope, kind, what)

* **path** - where the value sits in the request, with `[]` for "every
  item of this list".
* **scope** - `PAYLOAD` for a leaf of the JSON body murscope builds,
  `REQUEST` for something the transport adds around it. The split exists
  because `outbound.build()` walks what it produced and refuses any leaf
  the table does not declare - and it can only do that against the rows
  that describe the body. A row for an `Authorization` header would look,
  to that walk, like a declared field that never arrives.
* **kind** - what type the value is. Checked on the way out, so a count
  that arrives as the string `"0"` is a finding rather than a surprise in
  somebody's prompt.
* **what** - the sentence the user reads.

**The fingerprint covers `path` and `what`, and nothing else.** That is
the whole reason this module exists rather than a fourth column bolted
onto a tuple, and it is a correction rather than a design: the fingerprint
used to cover the paths alone. A path is not what anybody agreed to. The
line

    projects[].id    the id you gave the project in roster.json

and the line

    projects[].id    the id in roster.json - which the scan set to the
                     directory name unless you changed it

declare the same path and describe two different things leaving the
machine, and under a path-only fingerprint the second silently inherits
every consent recorded against the first. "You agreed to what you were
shown" was true of the code's intent and false of its arithmetic.

`scope` and `kind` are not fingerprinted, because they are not shown -
they are how `build()` checks itself, and a user cannot agree to or refuse
a validation rule they never read.

**The cost, stated rather than discovered.** Editing the wording of any
row now invalidates every consent recorded against that table, and the
user is asked again. A typo fix costs a re-consent. That is the wrong side
of the trade only if re-asking is worse than sending under an agreement to
different words, and on the one surface that cannot be taken back it is
not. `NORMALISE` below buys back the harmless half: the fingerprint runs
over whitespace-collapsed text, so re-wrapping a paragraph to fit a column
changes nothing and changing a word changes everything.
"""
from __future__ import annotations

# Where a declared value sits. `PAYLOAD` rows are leaves of the JSON body
# and are what `outbound.build()` measures itself against; `REQUEST` rows
# are what the transport puts around that body.
PAYLOAD = "payload"
REQUEST = "request"
SCOPES = (PAYLOAD, REQUEST)

# What a declared value is. Checked at build time for `PAYLOAD` rows.
TEXT = "text"
COUNT = "count"
FLAG = "flag"
SECRET = "secret"
KINDS = (TEXT, COUNT, FLAG, SECRET)


def normalise(text):
    """The sentence as it is fingerprinted: one space between words.

    So that re-wrapping a paragraph is free and rewriting it is not. The
    two failures are not alike and only one of them is worth a re-consent.
    """
    return " ".join(str(text).split())


def shown(table):
    """((path, what), ...) - exactly what the user reads, in table order.

    What `consent.fingerprint` is handed. Not the paths: a path with a
    different sentence beside it is a different disclosure.
    """
    return tuple((path, normalise(what)) for path, _scope, _kind, what in table)


def paths(table):
    """Just the paths, in table order. For messages, never for a digest."""
    return tuple(path for path, _scope, _kind, _what in table)


def payload_paths(table):
    """The paths that describe leaves of the JSON body murscope builds."""
    return tuple(path for path, scope, _kind, _what in table
                 if scope == PAYLOAD)


def kinds(table):
    """{path: kind} for the payload rows. What `build()` type-checks."""
    return {path: kind for path, scope, kind, _what in table
            if scope == PAYLOAD}


def lines(table, width=72):
    """The table as the lines a user reads before agreeing.

    Wrapped here rather than left to the terminal, because a row whose
    sentence is three lines long is a row somebody wrote three lines for.
    """
    out = []
    for path, _scope, _kind, what in table:
        out.append(path)
        words = normalise(what).split()
        line = ""
        for word in words:
            candidate = (line + " " + word) if line else word
            if len(candidate) > width:
                out.append("    " + line)
                line = word
            else:
                line = candidate
        if line:
            out.append("    " + line)
    return out


def leaf_paths(value, prefix=""):
    """Every leaf path in a payload, with `[]` for a list's items.

    A list contributes one set of paths for all of its items rather than
    one per index, so a payload describing three projects declares the
    same shape as one describing thirty.

    This is the half of the arrangement that makes a fingerprint a promise
    about what leaves rather than about a document: a table nobody measures
    the payload against drifts the first time a key is added without the
    table being touched (DP87).
    """
    found = set()
    if isinstance(value, dict):
        for key in value:
            found |= leaf_paths(value[key],
                                "%s.%s" % (prefix, key) if prefix else key)
    elif isinstance(value, (list, tuple)):
        for item in value:
            found |= leaf_paths(item, "%s[]" % prefix)
    else:
        found.add(prefix)
    return found


def values_at(value, parts):
    """Every value a leaf path names. A `[]` step visits every item."""
    if not parts:
        return [value]
    head, rest = parts[0], parts[1:]
    if head.endswith("[]"):
        block = (value or {}).get(head[:-2]) if isinstance(value, dict) else None
        found = []
        for item in block or ():
            found.extend(values_at(item, rest))
        return found
    if not isinstance(value, dict) or head not in value:
        return []
    return values_at(value[head], rest)


def kind_findings(table, payload):
    """Every leaf whose value is not the kind its row declares.

    Walked from the payload rather than from the table, so a list of thirty
    projects is thirty checks and not one.
    """
    declared = kinds(table)
    findings = []
    for path in sorted(leaf_paths(payload)):
        kind = declared.get(path)
        if kind is None:
            continue  # a stray; the builder names it on its own terms
        for value in values_at(payload, path.split(".")):
            problem = kind_problem(path, kind, value)
            if problem and problem not in findings:
                findings.append(problem)
    return findings


def kind_problem(path, kind, value):
    """A sentence naming a value that is not the kind declared, or None.

    Written as a returned sentence rather than a raise so that `build()`
    can collect every mismatch and name them together. One at a time is
    how a caller fixes four things in four runs.
    """
    if kind == COUNT:
        # `bool` is an `int` in Python and a count that arrives as `True`
        # is a bug wearing the right type.
        if value is None or (isinstance(value, int)
                             and not isinstance(value, bool)):
            return None
        return ("%s is declared a count and carries %r (%s). A count that "
                "leaves as a string is a count somebody has to parse, and the "
                "two shapes travelled in one payload: `stash` went out as "
                "\"0\" beside `uncommitted` as 0." % (path, value,
                                                      type(value).__name__))
    if kind == FLAG:
        if isinstance(value, bool):
            return None
        return "%s is declared a flag and carries %r." % (path, value)
    if kind == TEXT:
        if value is None or isinstance(value, str):
            return None
        return "%s is declared text and carries %r." % (path, value)
    if kind == SECRET:
        return ("%s is declared a secret and appears in the payload body. A "
                "secret belongs in a header the transport adds, never in the "
                "document murscope builds and digests." % path)
    return "%s declares kind %r, which is not one of %s." % (
        path, kind, ", ".join(KINDS))


def table_problems(table):
    """Findings about the table itself. A malformed row is not a disclosure.

    This is here because the table is data and data is what drifts. A row
    with four columns in the wrong order parses as a row.
    """
    findings = []
    seen = set()
    for index, row in enumerate(table):
        if not isinstance(row, tuple) or len(row) != 4:
            findings.append("row %d is not (path, scope, kind, what)." % index)
            continue
        path, scope, kind, what = row
        if not isinstance(path, str) or not path.strip():
            findings.append("row %d declares no path." % index)
        if path in seen:
            findings.append("%s is declared twice; a fingerprint over a "
                            "table with a repeated path is a fingerprint "
                            "over an ambiguity." % path)
        seen.add(path)
        if scope not in SCOPES:
            findings.append("%s declares scope %r, not one of %s."
                            % (path, scope, ", ".join(SCOPES)))
        if kind not in KINDS:
            findings.append("%s declares kind %r, not one of %s."
                            % (path, kind, ", ".join(KINDS)))
        if not isinstance(what, str) or not normalise(what):
            findings.append("%s carries no sentence. A path nobody explained "
                            "is a path nobody agreed to." % path)
    return findings
