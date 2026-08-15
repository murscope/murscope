"""A model on your own machine, over HTTP, through the same gate as a vendor.

**This is the adapter DP90 was written about.** It talks to
`http://localhost:11434`, and "localhost does not count as the network" is
a comfortable sentence that is how an exemption becomes a hole. A socket
is a socket: this module ships behind the `[ai]` boundary exactly like the
vendor adapters, a base install does not have it, Rule 13 governs it
identically, and it will not send without a recorded consent.

What differs is **where the data goes**, and that difference lives where
DP90 put it - in the consent text. The destination is part of the
fingerprint, so agreeing to send to `http://localhost:11434` is not
agreeing to send to a vendor, and a user who later points this at a
machine on their network is asked again.

## The timeout is not set from a warm figure

The window that installed the model measured it and DP93 recorded the
numbers so nobody has to re-measure: about 960ms cold against about 132ms
warm, and the model is unloaded after roughly five minutes idle. **A
provider's first call therefore always pays the cold start**, and a daily
note is by construction a once-a-day call - which is to say the cold start
is not the exceptional case here, it is the case. Those figures are for a
bare round trip; generating six sentences on a small model on a CPU is
seconds more, and a first-run load of the weights is more again.

`TIMEOUT` below is therefore generous rather than tight. A timeout tuned
to the warm figure would pass every test written by somebody who had just
run it twice and fail on the machine of somebody who runs it once a day,
which is every user of this feature.

## Evidence

`EVIDENCE` says what this adapter has actually done, not what it should
do. Read DP89: a provider whose only evidence is that the code looks right
is a rule without a check wearing a different hat.
"""
from __future__ import annotations

import json
import urllib.error
import urllib.request

from .. import consent as consent_module
from .. import keys, outbound
from ..registry import register

# The default Ollama address. Overridable in config.toml under
# `[providers.local]`, and a change to it changes the destination the
# consent is fingerprinted against - so pointing this at another machine
# asks again rather than inheriting the agreement to talk to this one.
BASE_URL = "http://localhost:11434"
ENDPOINT = BASE_URL + "/api/chat"

DEFAULT_MODEL = "llama3.2:1b"

PROVIDER = "local"
USER_AGENT = "murscope"

# See the module docstring. Cold start, then weights, then generation, on
# a machine that may be doing something else.
TIMEOUT = 180

# The keys this adapter is allowed to put around the payload, and the whole
# of what `request.envelope` in the disclosure describes. A check reads
# this tuple and the body this module builds, and refuses a key that is in
# one and not the other - which is how "nothing of yours is in it" stays a
# fact rather than a sentence in a table.
ENVELOPE_KEYS = ("model", "messages", "stream")

# DP89, in the data rather than in a paragraph.
EVIDENCE = "live"
EVIDENCE_NOTE = (
    "A real round trip against Ollama on this machine, recorded in M3 "
    "stage four's acceptance report: llama3.2:1b at http://localhost:11434, "
    "one note written from a real payload."
)


class TransportRefused(RuntimeError):
    """The request was refused here, and no socket was opened."""


def consent_fields():
    """The disclosure a grant for this transport must be fingerprinted on."""
    return outbound.shown()


def check_consent(url, grant, provider=PROVIDER, fields=None):
    """Refuse unless `grant` covers this exact request. Opens nothing."""
    if not isinstance(grant, consent_module.Grant):
        raise TransportRefused(
            "consent was given as %s, which is not a recorded consent. A "
            "model on your own machine is still on the far side of a socket, "
            "and murscope will not send anything through one until you have "
            "been shown what leaves and have agreed to it."
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

def send(url, payload, headers=None, timeout=TIMEOUT, consent=None,
         provider=PROVIDER, fields=None):
    """POST `payload` to `url`. Refuses unless consent covers this request.

    The same signature as every other transport in this distribution, so
    that Rule 18's and Rule 19's probes drive all of them through one code
    path rather than through a special case per module.
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


def body(payload, model):
    """The request body: the declared envelope around the declared payload.

    `outbound.canonical` is what goes in as the message content, byte for
    byte - the same bytes `outbound.payload_digest` records - so what the
    user was shown, what was digested and what left are one document
    rather than three that resemble each other.
    """
    return json.dumps({
        "model": model,
        "messages": [{"role": "user",
                      "content": outbound.canonical(payload).decode("utf-8")}],
        "stream": False,
    }).encode("utf-8")


def answer(raw):
    """The note out of one response, or raise. Never an empty string.

    An empty note is a note that looks written. `NoAnswer` here becomes a
    degraded slot with a reason, which is retried (DP49); a blank string
    would become an `ok` slot holding nothing.
    """
    try:
        document = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, ValueError) as exc:
        # Through `reraise_masked` like every other failure here, and for
        # the same reason: a body murscope could not parse is a body that
        # goes into the message, and a request body is where a key ends up
        # when somebody puts one there.
        keys.reraise_masked(exc, "the model answered with something that is "
                                 "not JSON")
    text = ((document.get("message") or {}).get("content") or "").strip()
    if not text:
        raise TransportRefused(
            "the model answered with no text (keys: %s). Nothing is recorded "
            "as a note: an empty note is a note that looks written."
            % (", ".join(sorted(document)) or "an empty document"))
    return text


def write(payload, home=None, grant=None, timeout=None, backend="file",
          model=None, endpoint=None):
    """Turn one payload into a note. This is what the registry hands the core.

    No key is read and none is sent. A model on your own machine has no
    account to bill, and asking the key store for one would have put a
    credential on a code path that has no use for it.
    """
    url = endpoint or ENDPOINT
    status, raw = send(url, body(payload, model or DEFAULT_MODEL),
                       timeout=timeout or TIMEOUT, consent=grant)
    return {"text": answer(raw), "model": model or DEFAULT_MODEL,
            "status": status, "destination": url}


register(
    "local",
    summary=("Writes the daily note with a model running on your own machine "
             "(Ollama). Still a socket, still consented to, still absent from "
             "a base install: DP90 refuses the localhost exemption."),
    contribute=None,
    stage="M3",
    writes=write,
    destination=ENDPOINT,
    evidence=EVIDENCE,
    evidence_note=EVIDENCE_NOTE,
)
