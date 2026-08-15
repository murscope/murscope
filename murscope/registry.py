"""The module registry: dependencies point one way (DP5, Rule 16).

The core knows that providers exist as a concept and knows nothing about
any particular one. A provider imports the core, calls register() at
import time, and configuration decides whether it is ever imported at
all. There is no line anywhere under murscope/ outside providers/ that
names a provider module, and Rule 16 is the check that keeps it that
way.

This is worth a module of its own for a reason that only shows up later:
the MVP ships with the provider layer empty, which is what makes the
three promises in the README facts rather than settings. "No network
call" is verifiable by reading the source precisely because there is no
provider to reach the network from. The registry is the seam that lets
that stay true while still leaving room for M3 - the seam has to exist
before it is needed, or the first provider gets bolted onto the core and
the direction is lost.
"""
from __future__ import annotations

_REGISTRY = {}


class Provider(object):
    """One registered module. `contribute` may be None: a provider is
    allowed to exist purely to announce that it is installed.

    `reads` and `destination` arrive with M3's third stage, and they are
    what let the core drive a network reader **without naming one**. Rule
    16 forbids any module under `murscope/` outside `providers/` from
    naming a provider module, and the contributions command would have
    broken that the moment it wrote `github` anywhere - so it does not
    look for a name. It asks the registry which registered providers offer
    a reading, and one that offers none is invisible to it.

    `destination` is the scheme and host the reader talks to. The provider
    declares it because the provider owns the endpoint, and the *core*
    needs it because consent is fingerprinted against where the data goes
    (DP90). A reader whose destination is empty cannot be consented to,
    which is the correct outcome rather than an inconvenience.

    `writes` arrives with M3's fourth stage and is the daily note's half of
    the same arrangement: a provider that can turn a payload into a
    sentence registers a callable, and the core finds it by asking rather
    than by naming it.

    `alerts` arrives with M4's second stage and is the third capability,
    deliberately separate from `writes` rather than folded into it. They
    carry different payloads under different disclosures, and - the part
    that is not tidiness - **a provider that can deliver an alert is a
    provider a machine may drive with nobody present** (DP125). Rule 26
    treats `registry.alerters()` as a transport doorway, so the timer
    cannot reach one; Rule 27 permits the alert entry point exactly this
    lookup and no other. Two capabilities that shared one field could not
    be told apart on a call graph, and both of those rules read the call
    graph.

    `evidence` and `evidence_note` are DP89 held in the data instead of in
    a paragraph. Four adapters ship and only some of them have ever
    completed a live round trip, so each one says which it is and why. A
    table that printed four rows with no such column would read as four
    working providers, which is exactly the claim DP89 refuses to let this
    line make for free.
    """

    def __init__(self, name, summary, contribute=None, stage="MVP",
                 reads=None, destination="", writes=None, evidence="unproven",
                 evidence_note="", alerts=None):
        self.name = name
        self.summary = summary
        self.contribute = contribute
        self.stage = stage
        self.reads = reads
        self.destination = destination
        self.writes = writes
        self.evidence = evidence
        self.evidence_note = evidence_note
        self.alerts = alerts

    def describe(self):
        return {"name": self.name, "summary": self.summary, "stage": self.stage,
                "contributes": self.contribute is not None,
                "reads": self.reads is not None,
                "writes": self.writes is not None,
                "alerts": self.alerts is not None,
                "evidence": self.evidence,
                "evidence_note": self.evidence_note,
                "destination": self.destination}


def register(name, summary, contribute=None, stage="MVP", reads=None,
             destination="", writes=None, evidence="unproven",
             evidence_note="", alerts=None):
    """Called by a provider at import time. Re-registration is refused."""
    if not isinstance(name, str) or not name.strip():
        raise ValueError("a provider must register under a non-empty name")
    if name in _REGISTRY:
        raise RuntimeError("provider %r is already registered" % name)
    _REGISTRY[name] = Provider(name, summary, contribute, stage, reads,
                               destination, writes, evidence, evidence_note,
                               alerts)
    return _REGISTRY[name]


def readers():
    """Registered providers that offer a reading, in registration order.

    The core's only way to find a network reader. It returns objects, not
    names, so a caller can drive one without ever writing a provider's
    name down - which is Rule 16 held by construction rather than by
    discipline.
    """
    return [provider for provider in _REGISTRY.values()
            if provider.reads is not None]


def writers():
    """Registered providers that can turn a payload into a note.

    The daily note's only way to find an adapter, and the same shape
    `readers()` has for the same reason: it returns objects, so the command
    drives one without ever writing a provider's name down.
    """
    return [provider for provider in _REGISTRY.values()
            if provider.writes is not None]


def alerters():
    """Registered providers that can deliver one alert off this machine.

    The third capability lookup, and the only one whose result a machine
    is allowed to drive with nobody present (DP125). Same shape as the
    other two - objects, never names - so `cli` can hand an alert to a
    transport without Rule 16 having anything to complain about.

    It is a function of its own rather than a filter written at the call
    site because two rules read the call graph for it: Rule 26 counts a
    call to this as a transport doorway, which is what keeps the timer
    away from it, and Rule 27 permits the alert entry point this one and
    refuses it `readers()` and `writers()`.
    """
    return [provider for provider in _REGISTRY.values()
            if provider.alerts is not None]


def registered():
    """Every provider that has been imported, in registration order."""
    return dict(_REGISTRY)


def describe_all():
    return [provider.describe() for provider in _REGISTRY.values()]


def reset():
    """Drop the registry. Exists for selftest and for nothing else."""
    _REGISTRY.clear()
