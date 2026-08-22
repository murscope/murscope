"""The DeepSeek adapter: the payload, a key, and a chat completion.

Same three gates as every other transport in this distribution -
installed, enabled, consented - and the same failure discipline: every
exception leaves through `keys.reraise_masked()`, redacted and with the
chain dropped, because a request whose URL or header carries a credential
comes back inside a message the standard library built.

## What is different from the local adapter, in one sentence

The destination. That is what the fingerprint is over (DP90): agreeing to
send fifteen declared things to a model on your own machine is not
agreeing to send them to a vendor on the open internet, and the consent
records which one.

## Evidence

`EVIDENCE` states what this adapter has done rather than what it is
supposed to do, and it is data so that the table which prints it cannot
quietly put a tested and an untested provider in one column (DP89).
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

ENDPOINT = "https://api.deepseek.com/chat/completions"

# The key name this adapter looks for in the store. The provider owns its
# credential: the core never writes this string.
KEY_NAME = "deepseek"

# Read off the vendor's own `GET /models` rather than copied from a
# tutorial: the account this was measured on answers with
# `deepseek-v4-flash` and `deepseek-v4-pro`, and a stale model id is a 400
# that looks like every other 400.
DEFAULT_MODEL = "deepseek-v4-flash"

PROVIDER = "deepseek"
USER_AGENT = "murscope"

# Generous rather than tight. A vendor endpoint under load is slower than
# the same endpoint on a quiet afternoon, and a daily note that times out
# is a degraded slot the user has to notice.
TIMEOUT = 120

# The keys this adapter may put around the payload, and the whole of what
# `request.envelope` describes in the disclosure. A check compares this
# tuple with the body this module builds.
ENVELOPE_KEYS = ("model", "messages", "stream")

EVIDENCE = "live"
EVIDENCE_NOTE = (
    "A real round trip against the vendor, recorded in M3 stage four's "
    "acceptance report: deepseek-v4-flash, one note written from a real "
    "payload. It took two keys to get there, and the first one is the more "
    "useful record: it was corrupted on the way into the store - 38 "
    "characters where the vendor's console showed 35 - so the Authorization "
    "header carried a value the gateway rejected before authentication ran, "
    "and every endpoint answered 400 with an empty body. `murscope key list` "
    "now prints each key's length for exactly that reason."
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
    """The note out of one response, or raise. Never an empty string."""
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
    """Turn one payload into a note. This is what the registry hands the core.

    The key is read here rather than passed in, because the provider owns
    its credential. It is read as a `Secret` and reaches exactly one place:
    the Authorization header of the request it authenticates.
    """
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
    "deepseek",
    summary=("Writes the daily note with DeepSeek, on a key you stored. Sends "
             "the declared payload and nothing else."),
    contribute=None,
    stage="M3",
    writes=write,
    destination=ENDPOINT,
    evidence=EVIDENCE,
    evidence_note=EVIDENCE_NOTE,
)
