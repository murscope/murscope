"""The provider layer, and the boundary the network lives behind.

This package is the one place allowed to import a provider module, and
it does so only for the names configuration has enabled. That is the
whole mechanism behind DP5: the core imports `murscope.providers`, this
file imports what the user asked for, and each provider registers itself
with `murscope.registry` on the way in. No core module ever names a
provider, so Rule 16 has something real to enforce.

**What changed at M3, and why it is a packaging decision rather than a
code one (DP88).** Promise two reads "It makes no network call at all.
Not 'off by default' - absent", and the second half is a stance. A
provider gated on a configuration key would make that promise mean "off
by default", which is the exact reading the sentence exists to refuse -
the design would have been refuted by the product's own front page. So
network capability is not a flag and not a module that checks whether an
extra is installed. **It is a separate distribution.** `pip install
murscope` puts the modules below on disk and nothing else; `pip install
murscope[ai]` additionally installs `murscope-ai`, which writes its own
provider modules into this same directory. A user who never typed `[ai]`
does not have to audit a config file to know that nothing can reach out,
because the code that would reach out is not on their disk. `pip list`
answers the question. Same move as DP65: stop proving absence by
argument, arrange for the absence to be observable.

**The name list used to be a literal tuple and cannot be one any more.**
That literal was doing a real job - importing whatever string arrived
from a config file would be an arbitrary-import hole with a written
excuse - so replacing it needs the job to be done some other way rather
than dropped. The reason it has to go is that the base distribution does
not know the names of modules it does not ship, and writing them here
anyway would be the core naming a provider, which is the one thing Rule
16 exists to refuse.

What replaces it is a **directory listing, not an import**:
`available()` asks `pkgutil` what modules are on disk under this one
package, and `load()` refuses any name that is not in that answer. The
hole stays shut for a reason worth stating rather than assuming -
`pkgutil.iter_modules` yields plain module names, so a traversal string
or a dotted path is not something it can ever return, and a name that
does not appear in it is refused before `import_module` is reached.

`BASE` is the literal that survives, and it is the one this file is
measured against: it names what the **base distribution** ships, so that
`murscope selftest` and Rule 13b can both ask "is anything here that the
base wheel did not put here, and did an installed distribution put it
there?" without either of them having to guess.

Rule 11 exempts this directory, because a provider is where a network
call would legitimately live. Nothing the base distribution ships here
reaches the network: `noop` imports the registry and nothing else. That
is not a claim about this directory being empty - it is not - but about
which files are in the base wheel, which is a fact a check can read out
of the built artifact rather than out of a promise.
"""
from __future__ import annotations

import importlib
import pkgutil

# What the **base distribution** ships. `noop` exists to prove the
# wiring: without one registered module, "providers self-register" is a
# claim with no code path behind it, and it opens nothing.
#
# Anything found on disk beside these arrived from another distribution -
# `murscope-ai`, via `pip install murscope[ai]`. This tuple is what makes
# that sentence checkable, so it is a literal and stays one.
BASE = ("noop",)


def available():
    """Provider module names on disk under this package.

    A directory listing, not an import. Names beginning with an
    underscore are not providers and are skipped; everything else is a
    candidate that configuration may name.
    """
    return tuple(sorted(module.name
                        for module in pkgutil.iter_modules(__path__)
                        if not module.name.startswith("_")))


def load(names):
    """Import the enabled providers. Returns (loaded, problems).

    Nothing is imported for a name configuration did not give, and
    nothing is imported for a name that is not on disk. The membership
    test is what keeps this from being an arbitrary-import hole: the
    string from `config.toml` has to match something `pkgutil` found
    under this package before it reaches `import_module`.
    """
    loaded = []
    problems = []
    present = available()
    for name in names or ():
        if not isinstance(name, str) or name not in present:
            problems.append(
                "provider %r is not one of the modules installed under "
                "murscope.providers (%s); nothing was imported for it. If you "
                "expected a network provider here, it ships in a separate "
                "distribution: pip install 'murscope[ai]'."
                % (name, ", ".join(present) or "none"))
            continue
        try:
            importlib.import_module("%s.%s" % (__name__, name))
        except Exception as exc:  # a broken provider must not kill the board
            problems.append("provider %r failed to import (%s: %s)."
                            % (name, type(exc).__name__, exc))
            continue
        loaded.append(name)
    return loaded, problems
