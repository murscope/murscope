"""The alert delivery adapter: one alert, one POST, to a URL you stored.

This is the only module in this product that a machine may drive with
nobody present (DP125), and everything odd about its shape comes from that
sentence.

**The URL is the credential, so it is in the key store and not in
config.toml.** A webhook address is a bearer token with a scheme in front
of it: anybody holding it can post into your channel. So `murscope key set
alert-webhook` is where the whole URL lives - 0600, never echoed, never in
an artifact, never in argv - and `config.toml` carries only the scheme and
host under `[alerts] destination`.

**Those two are stated separately on purpose, and they have to agree.**
The core needs a destination it can print on a consent screen and put in a
fingerprint (DP90: a consent is bound to where the data goes), and it
cannot read a provider's key because Rule 16 forbids it any knowledge of
which provider is which. So the core reads the host from configuration and
hands it down, this module reads the URL and refuses to deliver if the two
do not resolve to the same place. Changing your webhook to a different host
therefore invalidates the consent rather than silently redirecting the
alerts you agreed to send somewhere else.

**Written and unproven against any real vendor.** `EVIDENCE` below says so
and every table that lists this adapter prints it (DP89). What it *has*
been run against is a webhook receiver on this machine - a real socket, a
real request, a real answer parsed - which is what makes the send path
something other than a hopeful paragraph. A localhost destination is still
the network (DP90); what differs is where the data goes, and that is in the
consent text.
"""
from __future__ import annotations

import importlib.util
import urllib.error
import urllib.request

# **The first thing a stranger meets when this distribution is installed on
# its own** (DP172). `murscope-ai` declares no dependency on `murscope` -
# deliberately, because the base package's `ai` extra points this way and
# declaring both would close a cycle - so `pip install murscope-ai` puts
# these seven modules on a disk with nothing under them. `import murscope`
# then *succeeds*: DP88 requires this distribution to own no `__init__.py`,
# so the directory resolves as a namespace package and tells the reader
# nothing is wrong. The failure used to arrive one line below this one, as
# `ImportError: cannot import name 'consent' from 'murscope' (unknown
# location)` - an internal name, a location that does not exist, and no
# remedy anywhere in it.
#
# **Duplicated in all seven adapters deliberately, and asserted rather than
# trusted.** There is nowhere in this distribution for a shared copy to
# live: a module beside these would be a sibling import, which Rule 16
# refuses and is right to, and the core is the very thing that is absent.
# It is the same trade `_opener()` already makes here (DP116). The seven
# copies are byte for byte identical - `__name__` is what varies at run
# time and not the text - and CI imports every one of them in an
# environment with no base package and reads what each one says.
#
# `find_spec` rather than an import: the question is whether the base
# distribution is on the disk, and importing would answer a different one -
# a `consent` that is present and raises for a reason of its own would be
# reported here as an absent base, which is a wrong sentence delivered
# confidently.
if importlib.util.find_spec("murscope.consent") is None:
    raise ImportError(
        "%s needs the murscope base package and it is not installed: this "
        "is murscope-ai, which carries murscope's network providers and not "
        "murscope itself, so run `pip install 'murscope[ai]'` - one command "
        "that installs both halves at the pinned version." % __name__)

from .. import alerts
from .. import consent as consent_module
from .. import keys
from ..registry import register

# Where the whole delivery URL is stored. A name rather than a path: the
# key store decides where a key lives and at what mode, and this module
# has no business knowing either.
KEY_NAME = "alert-webhook"

PROVIDER = "webhook"
USER_AGENT = "murscope"

# Shorter than the note's. An alert that takes two minutes to deliver has
# already failed at being an alert, and a scheduled job that hangs is a
# scheduled job somebody eventually kills.
TIMEOUT = 20

EVIDENCE = "demonstrated-locally"
EVIDENCE_NOTE = (
    "No round trip against a hosted webhook service has been made. The send "
    "path, the refusal path and the failure path were each run against a "
    "receiver on this machine - a real socket, a real POST, a real body "
    "read back, and a real connection refused - which is more than "
    "'written' and less than 'proven against the vendor you will point it "
    "at'."
)


class TransportRefused(RuntimeError):
    """The delivery was refused here, and no socket was opened."""


def consent_fields():
    """The disclosure a grant for this transport must be fingerprinted on.

    The alert's table, never the daily note's. They are different documents
    describing different payloads, and a grant recorded against one does
    not fingerprint the same way as the other - which is what makes "two
    consents of different strength" a fact rather than a phrase.
    """
    return alerts.shown()


def check_consent(url, grant, provider=PROVIDER, fields=None):
    """Refuse unless `grant` covers this exact delivery. Opens nothing.

    Split out so the refusal can be exercised with no transport anywhere
    near it, and so the order is legible: every line of this runs before
    the first line of `send()` that touches `urllib`.
    """
    if not isinstance(grant, consent_module.Grant):
        raise TransportRefused(
            "consent was given as %s, which is not a recorded consent. "
            "murscope will not send an alert until you have been shown what "
            "leaves this machine and have agreed to it - and this is the "
            "consent that authorises a send while you are not here, so it is "
            "checked at the door like every other one."
            % type(grant).__name__)
    destination = consent_module.destination_of(url)
    wanted = consent_fields() if fields is None else tuple(fields)
    if not grant.matches(wanted, provider, destination):
        raise TransportRefused(
            "the recorded consent does not cover this delivery: it was "
            "granted for %r to %s over %d field(s), and this carries %d "
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


def send(url, payload, headers=None, timeout=TIMEOUT, consent=None,
         provider=PROVIDER, fields=None):
    """POST `payload` to `url`. Refuses unless consent covers this delivery.

    Every failure leaves as a `keys.Masked` with the URL redacted and the
    original exception chain dropped - `from None`, which is the
    load-bearing half. Without it the original stays on `__context__` and a
    traceback prints it under "During handling of the above exception" with
    the whole webhook URL, which is the credential, in it.
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
            exc, "the alert to %s could not be delivered"
                 % consent_module.destination_of(url))


def deliver(payload, home=None, grant=None, timeout=None, backend="file",
            destination=None):
    """Deliver one alert. This is what the registry hands the core.

    `destination` is the scheme and host the core read out of config.toml
    and recorded the consent against. The URL here has to resolve to it, or
    this refuses: the core cannot check that itself without knowing which
    provider it is talking to, and a delivery that quietly went somewhere
    other than the place named on the consent screen is the one failure
    this whole arrangement exists to make impossible.
    """
    secret, problems = keys.read(KEY_NAME, home, backend=backend)
    if secret is None:
        raise TransportRefused(
            "no key named %r is stored%s. `murscope key set %s` reads one "
            "from stdin - never from argv, because a key in argv is a key in "
            "your shell history. For this provider the key is the whole "
            "delivery URL, because a webhook URL is what authenticates the "
            "request."
            % (KEY_NAME, (": " + "; ".join(problems)) if problems else "",
               KEY_NAME))
    url = secret.value
    reached = consent_module.destination_of(url)
    if destination and reached != destination:
        raise TransportRefused(
            "the stored delivery URL resolves to %s and config.toml names %s "
            "under [alerts] destination. Those are the two places this one "
            "fact is written, and a consent is bound to the second - so a "
            "URL pointing somewhere else is a delivery nobody agreed to. "
            "Nothing was sent." % (reached or "nothing readable", destination))
    status, raw = send(url, alerts.canonical(payload),
                       timeout=timeout or TIMEOUT, consent=grant)
    return {"status": status, "destination": reached,
            "body": raw[:200].decode("utf-8", errors="replace")}


register(
    "webhook",
    summary=("Delivers one alert to a webhook URL you stored. This is the "
             "only provider a scheduled job may drive with nobody present, "
             "and it sends nothing without a consent recorded against the "
             "alert's own disclosure."),
    contribute=None,
    stage="M4",
    alerts=deliver,
    destination="",
    evidence=EVIDENCE,
    evidence_note=EVIDENCE_NOTE,
)
