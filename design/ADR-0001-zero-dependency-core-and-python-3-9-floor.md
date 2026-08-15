---
title: Zero-dependency core and a Python 3.9 floor
type: adr
captured: 2026-08-11
status: active
---

# ADR-0001: zero-dependency core and a Python 3.9 floor

Implements DP2 and DP3.

## Status

Accepted. Both constraints are enforced: the dependency list in
`pyproject.toml` is empty and stays empty, and CI runs the gate on 3.9,
3.12 and 3.13 so a 3.10-only construct fails the build rather than
failing a user.

## Context

Two decisions that will be questioned by anyone who reads the code, for
the same reason: both look like gratuitous self-punishment. Writing down
why is cheaper than re-litigating them in every pull request.

**Why they get questioned.** A dependency-free core means writing
argument parsing, config validation, table rendering and date handling
by hand when good libraries exist. A 3.9 floor means no `match`, no
`X | Y` unions at runtime, no `dict | dict`, no `str.removeprefix` in
some paths, no `zoneinfo` assumptions, no `functools.cache`. Neither
constraint buys a feature. Both cost real time.

## Decision

### Zero third-party runtime dependencies in the core

The core is pure standard library. Anything that genuinely needs a
package goes into an optional extra and lives behind a provider module
that configuration must enable.

The reason is the product, not the engineering. This tool asks a user to
point it at every project they have and promises three things: it writes
nothing, it calls nothing, it reads nothing beyond what was listed. A
user can verify those promises by reading a few thousand lines of one
package. They cannot verify them across a transitive dependency tree,
and neither can we - a promise that depends on auditing somebody else's
release is not a promise, it is a hope with good intentions.

Two consequences follow, both wanted:

- Installation is one download and works offline. The tool that tells
  you about your local projects should not need the network to install.
- The supply-chain surface is the standard library. For a program that
  is deliberately pointed at everything a developer owns, that is the
  correct surface.

The cost is real and accepted: some wheels get reinvented. They are
small wheels, and they are the parts nobody would audit anyway.

### Python >= 3.9

The floor is not conservatism. It is a measured platform constraint.

On macOS, granting a background process permission to read directories
like `~/Documents` means granting Full Disk Access to a **specific
interpreter binary**, chosen by path in System Settings. The interpreter
that ships with macOS - and therefore the one a user can most plausibly
be walked through granting - is 3.9. A tool that requires 3.11 asks the
user to find and authorise an interpreter inside a virtual environment
they did not create and cannot easily name, and the failure mode when
they get it wrong is the worst one available: the scan returns zero
results and looks like an empty portfolio rather than a permission
error.

So 3.9 is not "the oldest thing we tolerate". It is the version the
platform makes reachable.

The CI matrix is 3.9, 3.12 and 3.13: the floor, plus a current release,
plus the newest. The middle entry catches deprecations before the newest
entry turns them into errors.

## Consequences

- No `match` statements, no PEP 604 unions evaluated at runtime, no
  3.10+ standard-library additions. Use `from __future__ import
  annotations` and keep annotations lazy.
- New code that wants a package is a design conversation, not a commit.
  The answer is usually "write the small version" and occasionally "make
  it an extra behind a provider".
- The `keyring` extra in `pyproject.toml` is declared and empty. Keys
  start life as 0600 files under `MURSCOPE_HOME`, which needs nothing
  (DP18); the system keychain becomes an option at M3, and the extra
  gets its dependency then, alongside the code that imports it.
- If a future milestone genuinely cannot be built inside these
  constraints, that is a decision for the ledger, not a patch. Both of
  these are load-bearing for the trust story, and the trust story is the
  differentiator.
