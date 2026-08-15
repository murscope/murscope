"""The OpenAI adapter: the payload, a key, and a chat completion.

Written, and **never run against the vendor**. `EVIDENCE` below says so
and `murscope daily --providers` prints it in its own column, because DP89
is specific about the alternative: four adapters listed without that
column read as four working providers, and a provider whose only evidence
is that the code looks right is a rule without a check wearing a different
hat.

What that means concretely: the consent gate, the redaction on the failure
path and the request body are exercised by the gate on every run - Rules
18, 19 and 22 drive this module the same way they drive the others - and
the part nobody has seen is the vendor's answer. The parser below is
written from the published response shape and has never met one.

Everything else is the DeepSeek adapter's arrangement, for the plain
reason that the two APIs are the same shape.
"""
from __future__ import annotations

import json
import urllib.error
import urllib.request

from .. import consent as consent_module
from .. import keys, outbound
from ..registry import register

ENDPOINT = "https://api.openai.com/v1/chat/completions"

KEY_NAME = "openai"

DEFAULT_MODEL = "gpt-4o-mini"

PROVIDER = "openai"
USER_AGENT = "murscope"

TIMEOUT = 120

ENVELOPE_KEYS = ("model", "messages", "stream")

EVIDENCE = "unproven"
EVIDENCE_NOTE = (
    "No round trip has been made. No OpenAI key was available at M3 stage "
    "four and the owner ruled that none would be created for it, so what "
    "ships is written and unproven: the request shape and the parser have "
    "never met the vendor's answer."
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
            "consent was given as %s, which is not a recorded consent. "
            "murscope will not send anything until you have been shown what "
            "leaves this machine and have agreed to it. Being installed is "
            "not being enabled, and being enabled is not consent."
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
    """POST `payload` to `url`. Refuses unless consent covers this request."""
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
    """The declared envelope around the declared payload, byte for byte."""
    return json.dumps({
        "model": model,
        "messages": [{"role": "user",
                      "content": outbound.canonical(payload).decode("utf-8")}],
        "stream": False,
    }).encode("utf-8")


def answer(raw):
    """The note out of one response, or raise. Never an empty string.

    Written from the published response shape. It has not been run against
    a real answer, which is what `EVIDENCE` above says out loud.
    """
    try:
        document = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, ValueError) as exc:
        keys.reraise_masked(exc, "the provider answered with something that "
                                 "is not JSON")
    choices = document.get("choices") or []
    text = ""
    if choices:
        text = ((choices[0].get("message") or {}).get("content") or "").strip()
    if not text:
        raise TransportRefused(
            "the provider answered with no text (keys: %s). Nothing is "
            "recorded as a note: an empty note is a note that looks written."
            % (", ".join(sorted(document)) or "an empty document"))
    return text


def write(payload, home=None, grant=None, timeout=None, backend="file",
          model=None, endpoint=None):
    """Turn one payload into a note. This is what the registry hands the core."""
    secret, problems = keys.read(KEY_NAME, home, backend=backend)
    if secret is None:
        raise TransportRefused(
            "no key named %r is stored%s. `murscope key set %s` reads one "
            "from stdin - never from argv, because a key in argv is a key in "
            "your shell history."
            % (KEY_NAME, (": " + "; ".join(problems)) if problems else "",
               KEY_NAME))
    url = endpoint or ENDPOINT
    status, raw = send(
        url, body(payload, model or DEFAULT_MODEL),
        headers={"Authorization": "Bearer %s" % secret.value},
        timeout=timeout or TIMEOUT, consent=grant)
    return {"text": answer(raw), "model": model or DEFAULT_MODEL,
            "status": status, "destination": url}


register(
    "openai",
    summary=("Writes the daily note with OpenAI, on a key you stored. Written "
             "and never run against the vendor - see its evidence line."),
    contribute=None,
    stage="M3",
    writes=write,
    destination=ENDPOINT,
    evidence=EVIDENCE,
    evidence_note=EVIDENCE_NOTE,
)
