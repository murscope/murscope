"""The contributions reader's transport. A socket, and nothing else.

**What is here and what is deliberately not.** Every correction this
reader exists for - the clamped range endpoint, the cache that only
answers after a failure, the overlaid recent series and the total summed
from it - lives in `murscope.contributions`, in the core, where a base
install has it and the gate can check it. What lives here is the one
thing that cannot: the call that opens a socket.

That split is DP95's, applied a second time. The rule it follows is not
"network-ish things go in the extra" but the narrower and checkable one:
**a module goes behind the `[ai]` boundary when it opens a socket.** The
arithmetic of a reading does not, and putting it here would have meant a
base install could not measure its own corrections.

## Read-only, and still consented

Nothing about the user's projects goes out. What goes out is a token, two
timestamps and the word `viewer` - the platform resolves the account from
the token, so not even the account name is in the request.

**That is an argument for a small disclosure, not for skipping one.**
"It only reads, so it needs no consent" is the same sentence as
"localhost is not the network", which DP90 refused, and it fails for the
same reason: the question a consent answers is whether a socket may be
opened to a named destination carrying a named list of things, and this
opens one. The user's credential leaves this machine. The fact that
murscope ran, at this minute, on this account, leaves with it. So the
reading is gated on a `Grant` fingerprinted against
`contributions.DISCLOSURE` - a **different** table from the board
summary's, because agreeing to send eleven facts about your projects to a
model is not agreeing to ask a code host what you did last month, and one
fingerprint must never cover both.

## The failure path

Same shape as the outbound transport and for the same reason: a URL or a
header carrying a credential comes back inside a message the standard
library built, and a message becomes a traceback, and a traceback is an
artifact. Every failure below leaves through `keys.reraise_masked()`,
which redacts and raises `from None` so the original does not follow it
in under "During handling of the above exception".
"""
from __future__ import annotations

import json
import urllib.error
import urllib.request

from .. import consent as consent_module
from .. import contributions, keys
from ..registry import register

ENDPOINT = "https://api.github.com/graphql"

# The key name this reader looks for in the store. Declared here because
# the provider owns its credential: the core never writes this string, and
# a second reader for some other host would bring its own.
KEY_NAME = "github"

# What this transport's consent is about, read by Rule 19's probe rather
# than assumed by it. A check that hard-codes one transport's provider
# name and field list tests one transport; these two names are how it
# tests every transport that ships.
PROVIDER = "github"

USER_AGENT = "murscope"


class TransportRefused(RuntimeError):
    """The request was refused here, and no socket was opened."""


def consent_fields():
    """The disclosure a grant for this transport must be fingerprinted on.

    The rows as the user read them - path and sentence - not the paths.
    """
    return contributions.shown()


def check_consent(url, grant, provider=PROVIDER, fields=None):
    """Refuse unless `grant` covers this exact request. Opens nothing.

    Split out from `send()` so the refusal can be exercised with no
    transport anywhere near it, and so the order is legible: every line
    here runs before the first line of `send()` that touches `urllib`.
    """
    if not isinstance(grant, consent_module.Grant):
        raise TransportRefused(
            "consent was given as %s, which is not a recorded consent. "
            "murscope will not ask the platform anything until you have been "
            "shown what leaves this machine and have agreed to it. Reading is "
            "still a request, and a request still carries your key."
            % type(grant).__name__)
    destination = consent_module.destination_of(url)
    wanted = consent_fields() if fields is None else tuple(fields)
    if not grant.matches(wanted, provider, destination):
        raise TransportRefused(
            "the recorded consent does not cover this request: it was granted "
            "for %r to %s over %d field(s), and this request carries %d "
            "field(s) to %s. You agreed to what you were shown."
            % (grant.provider, grant.destination or "an unrecorded "
               "destination", len(grant.fields), len(wanted), destination))
    return destination


def _opener():
    """An opener that goes where the disclosure says, and nowhere else.

    **`urllib.request.urlopen` reads `https_proxy` from the environment.**
    That is a convenience everywhere else and a hole here: a payload the
    user agreed to send to a named destination would pass through a machine
    they were never shown, while the consent screen said "destination:
    <the vendor>" and meant something else. DP90 refused "localhost is not
    the network"; "a proxy is not a destination" is that sentence again.

    So the route is a decision rather than a default. `ProxyHandler({})` is
    an explicitly empty proxy map, which switches proxying off for this
    opener - if the network requires one the request fails and the command
    says so, which is the honest outcome. Using a proxy on purpose would be
    a second destination and would have to be disclosed and consented to;
    that is not built, and it is recorded as not built rather than left
    working by accident (DP111).
    """
    return urllib.request.build_opener(urllib.request.ProxyHandler({}))


def send(url, payload, headers=None, timeout=30, consent=None,
         provider=PROVIDER, fields=None):
    """POST `payload` to `url`. Refuses unless consent covers this request.

    The same signature as the outbound transport's, so that Rule 19's live
    probe drives both through one code path rather than through a special
    case per module.

    Returns (status, body). Every failure leaves as a `keys.Masked` with
    the credential redacted and the exception chain dropped.
    """
    check_consent(url, consent, provider=provider, fields=fields)
    try:
        request = urllib.request.Request(
            url, data=payload,
            headers=dict({"User-Agent": USER_AGENT,
                          "Content-Type": "application/json"},
                         **dict(headers or {})),
            method="POST")
        with _opener().open(request, timeout=timeout) as response:
            return response.getcode(), response.read()
    except Exception as exc:
        keys.reraise_masked(
            exc, "the request to %s could not be completed"
                 % consent_module.destination_of(url))


def read(documents, home=None, grant=None, timeout=30, backend="file"):
    """Post each GraphQL document and return the parsed answers.

    This is what the registry hands the core as `reads`. The core builds
    the documents - it owns the ranges, the clamp and the overlay - and
    never learns which host answered them.

    The key is read here rather than passed in, because the provider owns
    its credential. It is read as a `Secret` and reaches exactly one
    place: the Authorization header of the request it authenticates.
    """
    secret, problems = keys.read(KEY_NAME, home, backend=backend)
    if secret is None:
        raise TransportRefused(
            "no key named %r is stored%s. `murscope key set %s` reads one "
            "from stdin - never from argv, because a key in argv is a key in "
            "your shell history."
            % (KEY_NAME, (": " + "; ".join(problems)) if problems else "",
               KEY_NAME))

    answers = []
    for document in documents:
        payload = json.dumps(document).encode("utf-8")
        status, body = send(
            ENDPOINT, payload,
            headers={"Authorization": "bearer %s" % secret.value},
            timeout=timeout, consent=grant)
        try:
            answers.append(json.loads(body.decode("utf-8")))
        except (UnicodeDecodeError, ValueError) as exc:
            keys.reraise_masked(
                exc, "the platform answered %s with something that is not "
                     "JSON" % status)
    return answers


register(
    "github",
    summary=("Reads your own contribution calendar from your own account, on "
             "a key you stored. Sends nothing about your projects: the "
             "request carries a token, two timestamps and the word `viewer`."),
    contribute=None,
    stage="M3",
    reads=read,
    destination=ENDPOINT,
)
