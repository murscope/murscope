"""murscope - read-only portfolio observability.

Scan the projects you point it at and render a one-page static
dashboard: what is moving, what stalled, what is stuck on you.

The package is pure standard library. It writes nothing outside
MURSCOPE_HOME, makes no network call, and reports nothing to anyone.

Layout, as of M2 - the MVP command surface is complete:

    guard      the single write path; refuses any target outside HOME
    config     MURSCOPE_HOME, config.toml, roster.json, the sealed table
    _toml      a small TOML reader for 3.9 and 3.10, where tomllib is not
    collect    thirteen read-only signals per project
    render     the board: data.json, data.js and one static page
    i18n       locales, maintained independently, no key fallback
    registry   providers self-register; the core imports none of them
    providers  empty by design until M3

The scanner, the state layer and the rest of the command surface arrive
with stage two of M1 and with M2.
"""

__version__ = "0.1.0"

__all__ = ["__version__"]
