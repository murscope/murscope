"""Consent: an act the user performs, bound to what it disclosed.

Three gates guard the network layer and being past one is not being past
the next (README says the same, in the same order):

1. **installed** - the module is on disk, because the user typed `[ai]`;
2. **enabled** - `config.toml` names it, or the loader never imports it;
3. **consented** - this module. The user was shown what a request
   contains and said yes.

## Why this is not a boolean

A boolean consent is wrong in a specific, quiet way. It records *that*
somebody agreed and not *what to*, so the day the payload grows the old
agreement silently covers the new, larger one. Nobody is asked again,
nothing goes red, and the user's answer is applied to a question they
were never shown. Every part of that is invisible from the outside, which
is exactly the class of failure this line keeps finding.

So a `Grant` carries a **fingerprint of the disclosure it was granted
against**: the ordered list of rows in `outbound.DISCLOSURE` **as the user
read them - the path and the sentence beside it** - the provider it names,
and the destination those fields go to. `require()` recomputes that
fingerprint from the code as it stands now and refuses the grant if it
differs, naming the fields that were added, removed, or **reworded**.
Changing what leaves therefore costs one re-consent, and it cannot cost
nothing.

## The sentence is in the digest, and it was not

The first version fingerprinted the paths alone, and that was a hole with
the shape this line keeps finding: the guard's sentence was wider than its
window. `projects[].id` described as "the id you gave the project" and
`projects[].id` described as "the directory name the scan set, unless you
changed it" are the same path and two different disclosures, and the
second was silently covered by every consent recorded against the first.
The owner found it by reading his own real payload - the field he had been
told was not a name was, on the default path, exactly the name.

`murscope.disclosure.normalise` decides what counts as a change: the
digest runs over whitespace-collapsed text, so re-wrapping a paragraph
costs nothing and rewriting a word costs a re-consent. That price is
accepted knowingly. A typo fix asks every user again, which is a real
cost; the alternative is a product that can change what it says it sends
while holding an agreement to the older sentence, on the one surface where
being wrong cannot be taken back.

The destination is in the fingerprint for the same reason the fields are.
Agreeing to send eleven numbers to a model on your own machine is not
agreeing to send them to a vendor on the open internet, and DP90 already
settled that the difference belongs in the consent text rather than in a
carve-out in the rule: a local model is on the network, and what differs
is where the data goes.

## What is *not* claimed

This is a record of an agreement, not an authorisation system. The file
under `MURSCOPE_HOME` is as protected as the home is, and anything
running as the user can write one. It exists so the product cannot send
without having asked, which is a promise about the product's behaviour -
the only kind of promise a local-first tool is in a position to make.
"""
from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime, timezone

from .guard import guard_write_path, murscope_home

CONSENT_DIRNAME = "consent"

# 2 since the digest covers the sentences as well as the paths. The bump
# is what lets a refusal say *why* a grant recorded last week no longer
# matches, instead of sending its holder to diff two tables: a schema-1
# document records paths and no sentences, so it cannot match and the
# reason is the change itself rather than anything the user did.
SCHEMA = 2
LEGACY_SCHEMA = 1


class ConsentRequired(RuntimeError):
    """Nothing was recorded: the user has not been asked, or said no."""


class ConsentStale(RuntimeError):
    """Something was recorded, and it is not about this request."""


def destination_of(url):
    """The scheme and host of a URL, which is what a user agrees to.

    Parsed here rather than with `urllib.parse`, which Rule 11 refuses to
    let the core import at all - the rule is about the module root, not
    about which submodule happens to open a socket, and narrowing it for
    one convenience is how an exemption list starts. Four lines of string
    work costs less than that precedent.

    The path and the query are deliberately dropped. A query string is
    where an API key ends up, and a destination is a place rather than a
    request.
    """
    if not isinstance(url, str) or not url.strip():
        return ""
    rest = url.strip()
    scheme = ""
    if "://" in rest:
        scheme, rest = rest.split("://", 1)
    host = rest.split("/", 1)[0].split("?", 1)[0].split("#", 1)[0]
    # Credentials in the authority section are a key by another route.
    if "@" in host:
        host = host.rsplit("@", 1)[1]
    return "%s://%s" % (scheme.lower(), host.lower()) if scheme else host.lower()


def _rows(shown):
    """`shown` as a list of (path, sentence), whatever it arrived as.

    A caller that still hands over bare paths - a probe, an older grant -
    gets rows with an empty sentence rather than a crash, and those rows
    fingerprint differently from the real table, which is the correct
    outcome: a grant that recorded no sentence did not record one.
    """
    rows = []
    for item in shown or ():
        if isinstance(item, (list, tuple)) and len(item) == 2:
            rows.append([str(item[0]), str(item[1])])
        else:
            rows.append([str(item), ""])
    return rows


def paths_of(shown):
    """Just the paths out of a shown table, for a message."""
    return [row[0] for row in _rows(shown)]


# The environment variables `urllib` reads to decide where a request
# actually goes. Named as strings and read with `os.environ`: this is a
# question about configuration, not about networking, and the core still
# imports nothing that can open a socket (Rule 11).
PROXY_VARIABLES = ("https_proxy", "HTTPS_PROXY", "http_proxy", "HTTP_PROXY",
                   "all_proxy", "ALL_PROXY")


def proxy_in_environment():
    """[(variable, host)] for every proxy this environment names.

    **This exists because a disclosure that names a destination is not
    true if something else is between here and it.** `urllib` reads these
    variables by default, so a payload agreed to for `api.example.com`
    would pass through a machine the user was never shown, and the consent
    screen would have said "destination: api.example.com" while meaning
    something else. DP90 refused "localhost is not the network"; "a proxy
    is not a destination" is the same sentence.

    The transports do not use them - they build an opener with proxies
    switched off, so the route is the declared one - and this function is
    what lets the commands *say* that to somebody whose environment sets
    one, rather than leaving them to wonder.

    The host only. A proxy URL can carry credentials in its authority
    section, and those are no more printable than any other key.
    """
    found = []
    for name in PROXY_VARIABLES:
        value = os.environ.get(name)
        if value and value.strip():
            found.append((name, destination_of(value) or "an unreadable value"))
    return found


def fingerprint(shown, provider, destination):
    """A digest over exactly what the user was shown.

    `shown` is the ordered `(path, sentence)` table, not the paths: the
    sentence is the disclosure and the path is where it lives. See the
    module docstring for what that costs and why it is the right side of
    the trade.

    Canonical JSON rather than a concatenation, so a field named
    `a.b` and two fields named `a` and `b` cannot produce the same digest.
    """
    document = {"schema": SCHEMA, "provider": provider,
                "destination": destination, "shown": _rows(shown)}
    payload = json.dumps(document, ensure_ascii=True, sort_keys=True,
                         separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


class Grant(object):
    """One recorded agreement. Constructed by `record()` and by `load()`.

    It is a class rather than a `True` on purpose, and `send()` refuses
    anything that is not one - so `consent=True`, `consent=1`,
    `consent="yes"` and a hopeful string all fail at the door, before a
    socket is anywhere in the picture.
    """

    __slots__ = ("provider", "destination", "digest", "shown", "recorded_at",
                 "schema")

    def __init__(self, provider, destination, digest, shown, recorded_at,
                 schema=SCHEMA):
        self.provider = provider
        self.destination = destination
        self.digest = digest
        self.shown = tuple(tuple(row) for row in _rows(shown))
        self.recorded_at = recorded_at
        self.schema = schema

    @property
    def fields(self):
        """The paths this grant recorded. Kept for the messages that name
        a field; the digest is over `shown` and always was meant to be."""
        return tuple(path for path, _what in self.shown)

    def matches(self, shown, provider, destination):
        return self.digest == fingerprint(shown, provider, destination)

    def as_document(self):
        return {"schema": SCHEMA, "provider": self.provider,
                "destination": self.destination, "fingerprint": self.digest,
                "shown": [list(row) for row in self.shown],
                "recorded_at": self.recorded_at}

    def __str__(self):
        return ("consent for %r to %s, %d field(s), recorded %s (%s)"
                % (self.provider, self.destination, len(self.shown),
                   self.recorded_at, self.digest[:12]))


def consent_dir(home=None):
    return (home or murscope_home()) / CONSENT_DIRNAME


def consent_path(provider, home=None):
    return consent_dir(home) / ("%s.json" % provider)


def record(provider, destination, shown, home=None):
    """Write the agreement. Returns (grant, path).

    The rows are stored as well as fingerprinted. The digest is what
    `require()` compares, and the stored table is what lets a refusal say
    *which* field appeared, vanished or was rewritten - a refusal that only
    says "this no longer matches" sends the user to read a diff.
    """
    destination = destination_of(destination) or destination
    grant = Grant(provider, destination,
                  fingerprint(shown, provider, destination), shown,
                  datetime.now(timezone.utc).astimezone().isoformat(
                      timespec="seconds"))
    path = guard_write_path(
        consent_path(provider, home),
        json.dumps(grant.as_document(), indent=2, sort_keys=True) + "\n")
    return grant, path


def recorded(home=None):
    """Provider names with a consent on file, sorted. Names only.

    The listing lives here rather than in `cli` for Rule 6's sake and for
    the reason behind it: a traversal is permitted when it is provably
    rooted at MURSCOPE_HOME, and that is only provable in the module where
    the root is resolved. `consent_dir()` reaches `murscope_home()` two
    lines up; a glob written in `cli` would arrive at the check as an
    expression nothing can vouch for.
    """
    directory = consent_dir(home)
    if not directory.is_dir():
        return []
    return sorted(path.stem for path in directory.glob("*.json")
                  if path.is_file())


def load(provider, home=None):
    """(grant, problems). A missing file is no consent, not an error."""
    path = consent_path(provider, home)
    if not path.is_file():
        return None, []
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        return None, ["%s cannot be read (%s); treat it as no consent at "
                      "all." % (path, exc)]
    if not isinstance(document, dict):
        return None, ["%s does not hold an object; treat it as no consent."
                      % path]
    digest = document.get("fingerprint")
    schema = document.get("schema")
    rows = document.get("shown")
    if not isinstance(rows, list):
        # A schema-1 document records paths and no sentences. It is read
        # rather than refused, so `require()` can say what changed instead
        # of reporting an unreadable file - the grant is genuine, it is
        # simply about a disclosure this build no longer describes the
        # same way.
        rows = document.get("fields")
    if not isinstance(digest, str) or not isinstance(rows, list):
        return None, ["%s records no fingerprint and disclosure table, so "
                      "there is nothing to check a request against." % path]
    return Grant(document.get("provider") or provider,
                 document.get("destination") or "", digest, rows,
                 document.get("recorded_at") or "unknown",
                 schema if isinstance(schema, int) else LEGACY_SCHEMA), []


def _what_changed(grant, shown, destination):
    """One sentence naming the difference, in the order that matters."""
    if grant.destination != destination:
        return ("the destination is now %s and you agreed to %s"
                % (destination, grant.destination or "nothing recorded"))
    wanted = dict(_rows(shown))
    had = dict(_rows(grant.shown))
    added = [path for path in paths_of(shown) if path not in had]
    dropped = [path for path in grant.fields if path not in wanted]
    # A path that stayed and whose sentence did not. This is the case the
    # path-only fingerprint could not see at all, and it is the one the
    # owner found: the same field, described as something else.
    reworded = [path for path in paths_of(shown)
                if path in had and had[path] and had[path] != wanted[path]]
    if grant.schema < SCHEMA and not (added or dropped):
        return ("it was recorded before murscope bound a consent to the "
                "sentences it showed rather than to the field names alone, so "
                "there is no record of what you were told these fields were")
    parts = [part for part in (
        "now also sends %s" % ", ".join(added) if added else "",
        "no longer sends %s" % ", ".join(dropped) if dropped else "",
        "describes %s differently than it did when you agreed"
        % ", ".join(reworded) if reworded else "") if part]
    if parts:
        return "; ".join(parts)
    return ("the disclosure it was granted against no longer fingerprints "
            "the same way")


def require(provider, destination, shown, home=None):
    """The grant for this exact request, or raise.

    `ConsentRequired` when nothing is recorded, `ConsentStale` when
    something is and it is about a different disclosure. Two exceptions
    rather than one because the user's next action differs: the first is
    "you have not been asked", the second is "what murscope sends has
    changed since you agreed, here is what changed".
    """
    destination = destination_of(destination) or destination
    grant, problems = load(provider, home)
    if grant is None:
        raise ConsentRequired(
            "murscope has recorded no consent for provider %r.%s Nothing is "
            "sent until you have been shown what leaves this machine and "
            "have agreed to it: run `murscope consent grant %s --to %s`."
            % (provider, (" " + " ".join(problems)) if problems else "",
               provider, destination))
    if grant.matches(shown, provider, destination):
        return grant
    changed = _what_changed(grant, shown, destination)
    raise ConsentStale(
        "the consent recorded for %r on %s does not cover this request: %s. "
        "You agreed to what you were shown, not to a field name - so this "
        "asks again rather than assuming. Run `murscope consent show %s "
        "--to %s` to read the new disclosure, then `murscope consent grant`."
        % (provider, grant.recorded_at, changed, provider, destination))
