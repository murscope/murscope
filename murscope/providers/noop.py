"""A provider that does nothing, so that the wiring can be proved.

There is no real provider until M3. Without at least one registered
module the registry is untested plumbing, and the first genuine provider
would arrive at the same time as the first evidence that registration
works at all - which is the moment when a shortcut into the core is most
tempting. This module removes that moment: `providers.enabled = ["noop"]`
in config.toml puts a row in the registry and changes nothing else.

It also documents the shape a provider takes: import the core registry,
register a name and a summary at import time, expose a callable that
receives one collected project record and returns extra fields. Nothing
imports this file except murscope/providers/__init__.py.
"""
from __future__ import annotations

from ..registry import register


def contribute(record):
    """Add nothing. A provider that has nothing to say returns an empty map."""
    return {}


register(
    "noop",
    summary="Registers and contributes nothing; proves the provider wiring.",
    contribute=contribute,
    stage="MVP",
)
