"""The Anthropic adapter: the payload, a key, and one message.

Written, and **never run against the vendor**. `EVIDENCE` below says so
and the provider table prints it in its own column (DP89). The owner ruled
that no key would be created for this adapter at M3 stage four, so what
ships is code that has never had an answer to parse - and the honest label
for that is "unproven", not a row that looks like the local model's.

## Two things here that the other vendor adapters do not have

**The credential travels in `x-api-key`, not in `Authorization`.** That is
this vendor's shape, and the disclosure says so rather than describing an
`Authorization` header the request does not carry - a disclosure that
describes a request murscope does not make is a disclosure about nothing.

**`max_tokens` is required by the API**, so it is in `ENVELOPE_KEYS` and
in the sentence `request.envelope` shows the user. A key that the body
carries and the envelope row does not name is a key nobody was shown, and
Rule 22's check compares the two.
"""
from __future__ import annotations

import importlib.util
import json
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

from .. import consent as consent_module
from .. import keys, outbound
from ..registry import register

ENDPOINT = "https://api.anthropic.com/v1/messages"

KEY_NAME = "anthropic"

DEFAULT_MODEL = "claude-sonnet-4-5"

# The API version header this vendor requires. A constant rather than a
# setting: it pins the response shape `answer()` below was written for.
API_VERSION = "2023-06-01"

PROVIDER = "anthropic"
USER_AGENT = "murscope"

TIMEOUT = 120

# Six sentences. Named rather than left to a default, because this API has
# no default - the request is rejected without it.
MAX_TOKENS = 1024

ENVELOPE_KEYS = ("model", "messages", "stream", "max_tokens")

EVIDENCE = "unproven"
EVIDENCE_NOTE = (
    "No round trip has been made. The owner ruled at M3 stage four that no "
    "Anthropic key would be created for this adapter, so what ships is "
    "written and unproven: the request shape and the parser have never met "
    "the vendor's answer."
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
                          "Content-Type": "application/json",
                          "anthropic-version": API_VERSION},
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
        "max_tokens": MAX_TOKENS,
        "messages": [{"role": "user",
                      "content": outbound.canonical(payload).decode("utf-8")}],
        "stream": False,
    }).encode("utf-8")


def answer(raw):
    """The note out of one response, or raise. Never an empty string.

    Written from the published response shape and never run against a real
    one, which is what `EVIDENCE` above says out loud.
    """
    try:
        document = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, ValueError) as exc:
        keys.reraise_masked(exc, "the provider answered with something that "
                                 "is not JSON")
    blocks = document.get("content") or []
    text = ""
    for block in blocks:
        if isinstance(block, dict) and block.get("type") == "text":
            text = (text + "\n" + (block.get("text") or "")).strip()
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
        headers={"x-api-key": secret.value},
        timeout=timeout or TIMEOUT, consent=grant)
    return {"text": answer(raw), "model": model or DEFAULT_MODEL,
            "status": status, "destination": url}


register(
    "anthropic",
    summary=("Writes the daily note with Anthropic, on a key you stored. "
             "Written and never run against the vendor - see its evidence "
             "line."),
    contribute=None,
    stage="M3",
    writes=write,
    destination=ENDPOINT,
    evidence=EVIDENCE,
    evidence_note=EVIDENCE_NOTE,
)
