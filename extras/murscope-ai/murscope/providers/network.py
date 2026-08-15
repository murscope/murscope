"""The outbound transport. The only code in this product that can open a
socket, and it ships in a distribution a base install does not have.

**Why this module is the deliverable of M3's first stage.** The stage was
about the boundary, not about any particular model, and a boundary is
only real if something is demonstrably on the far side of it. A base
install must have nothing here that could reach out; an `[ai]` install
must have something that could. This module is that something. It imports
`urllib.request` at module scope, deliberately and visibly, so that a
check reading the installed file can classify it as socket-capable
without importing it and without trusting a comment.

**What stage two changed: it can now actually send.** Stage one's
`send()` refused everything, because there was no honest way to decide
that a user had agreed to a request. `murscope.consent` supplies that
decision, so the refusal is now conditional - and the three sentences
below are what stands between a payload and the wire.

Three gates, and being past one is not being past the next:

1. **installed** - the module is on disk, because the user typed `[ai]`;
2. **enabled** - `config.toml` names it, or `load()` never imports it;
3. **consented** - a `consent.Grant` whose fingerprint still matches the
   disclosure this build would show. Not a boolean, not a string, not a
   flag: `consent=True`, `consent=1`, `consent="yes"` and a hopeful
   sentinel all fail below, **before a socket is anywhere in the
   picture**, and so does a real grant recorded against a smaller payload
   than the one being handed over.

A local model is on the far side of this boundary too (DP90). It speaks
HTTP to a socket, and "localhost does not count as the network" is how an
exemption becomes a hole. What differs is where the data goes, and that
is in the consent text the user reads - the destination is part of the
fingerprint, so agreeing to send to a model on your own machine is not
agreeing to send to a vendor.

## The failure path is a surface, and it is guarded here

The last thing this module does before the wire, and the first thing it
does when the wire fails, is the same thing: make sure nothing carries a
key out.

A URL with a key in its query string, handed to `urllib`, comes back as
`ValueError: unknown url type: 'nonsense?key=<the actual key>'`. That
string is built by the standard library, not by us, and it lands in an
exception message - which becomes a traceback, which is an artifact.
`traceback.print_exc()` prints it, a caller's `print(exc)` prints it, and
a log file keeps it.

So every failure below leaves through `keys.reraise_masked()`, which
redacts and raises **`from None`**. The `from None` is the load-bearing
half: without it the original stays on `__context__` and the traceback
prints it under "During handling of the above exception" with the key
intact. That is not a theoretical shape - it is the default behaviour of
`raise` inside an `except` block, which is to say it is what this file
would do if nobody had thought about it.
"""
from __future__ import annotations

import urllib.error
import urllib.request

from .. import consent as consent_module
from .. import keys, outbound
from ..registry import register

# The user agent this transport identifies itself as. Named rather than
# defaulted, because `Python-urllib/3.x` on a vendor's access log is a
# request nobody can attribute afterwards - including the user reading
# their own provider dashboard to check what murscope actually sent.
USER_AGENT = "murscope"

# Which consent this transport requires, declared rather than inferred.
# Rule 19's live probe used to hard-code "network" and `outbound.fields()`,
# which was correct for exactly as long as this was the only transport in
# the extras distribution. A second one arrived at M3's third stage with a
# different provider name and a different disclosure, and a probe that
# assumes the first one's answers does not test the second - it fails it.
# So a transport says what it wants and the check asks.
PROVIDER = "network"


def consent_fields():
    """The disclosure a grant for this transport must be fingerprinted on.

    The rows as the user read them - path and sentence - not the paths.
    A path-only digest let a field keep its name and change its meaning,
    which is what happened to `projects[].id`.
    """
    return outbound.shown()


class TransportRefused(RuntimeError):
    """The request was refused here, and no socket was opened."""


def _refuse(reason):
    raise TransportRefused(
        "%s murscope will not send anything until you have been shown what "
        "leaves this machine and have agreed to it. Being installed is not "
        "being enabled, and being enabled is not consent." % reason)


def check_consent(url, grant, provider=PROVIDER, fields=None):
    """Refuse unless `grant` covers this exact request. Opens nothing.

    Split out from `send()` so that the refusal can be exercised without
    a transport anywhere near it, and so that the order is legible: every
    line of this function runs before the first line of `send()` that
    touches `urllib`.
    """
    if not isinstance(grant, consent_module.Grant):
        _refuse("consent was given as %s, which is not a recorded consent."
                % type(grant).__name__)
    destination = consent_module.destination_of(url)
    wanted = consent_fields() if fields is None else tuple(fields)
    if not grant.matches(wanted, provider, destination):
        _refuse(
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

    Returns (status, body). Every failure - refusal, protocol error,
    unreachable host, a malformed URL - leaves as a `keys.Masked` with the
    key redacted and the original exception chain dropped.
    """
    check_consent(url, consent, provider=provider, fields=fields)
    try:
        request = urllib.request.Request(
            url, data=payload,
            headers=dict({"User-Agent": USER_AGENT}, **dict(headers or {})),
            method="POST")
        with _opener().open(request, timeout=timeout) as response:
            return response.getcode(), response.read()
    except Exception as exc:
        keys.reraise_masked(
            exc, "the request to %s could not be completed"
                 % consent_module.destination_of(url))


register(
    "network",
    summary=("The outbound transport the [ai] extra installs. Present only "
             "if you asked for it; sends nothing without a recorded consent "
             "that still matches what would be sent."),
    # Nothing is added to a project's record by the transport itself. The
    # registry permits this: a provider may exist purely to announce that
    # it is installed, which at this stage is exactly what it is for.
    contribute=None,
    stage="M3",
)
