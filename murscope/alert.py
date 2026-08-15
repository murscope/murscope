"""The entry point a scheduler runs when an alert may leave the machine.

This is the second thing this product does with nobody present, and it is
the first thing it does that **sends** with nobody present. DP125 is the
ruling behind it, and the ruling is about a collision rather than about a
feature: DP124 says the scheduled collection has no send path reachable
from its entry point, the owner also ruled that an alert may leave -
because an alert that only reaches the Mac you are sitting at is not an
alert - and the resolution is an exception that is *stated* rather than a
hole that is silent.

**The shape of that exception is a second console script, and the reason
is DP127's, arrived at from the other end.** The timer got its own script
because `murscope` is an argv dispatcher and `daily --send` was one word
away in a job description nothing re-reads. The same argument says an
alert job cannot be a flag on the timer: a flag would put both capabilities
on one call graph, and then neither Rule 26 nor Rule 27 could say anything
about either. So there are two entry points and two rules:

* **Rule 26** walks from `murscope.timer:main` and fails if the walk
  reaches *any* transport doorway - `registry.readers()`,
  `registry.writers()`, `registry.alerters()`, a `.reads`/`.writes`/
  `.send`/`.alerts` call on a value, or any function in a module that
  imports something socket-capable.
* **Rule 27** walks from `main()` below and fails if it reaches anything
  except the alert's own doorway. `registry.alerters()` and `.alerts(...)`
  are permitted, because delivering an alert is what this is for.
  `registry.readers()`, `registry.writers()`, `outbound.build`,
  `outbound.canonical` and every `.reads`/`.writes`/`.send` call are
  forbidden, so **the only payload this entry point can put on a wire is
  the alert's**. That sentence is a property of the call graph, measured
  on every gate run, rather than a paragraph anybody has to believe.

It takes no arguments, and refuses them rather than ignoring them, for the
reason the timer does: a job description that grew an argument should fail
loudly rather than quietly do the old thing.

**What being scheduled means here, and what it does not.** Running does
not make anything leave. Three gates still stand between this process and
a socket, and they are the same three the daily note has: the network
layer has to be installed, `config.toml` has to name a delivery provider,
and a consent has to be recorded against the alert's own disclosure. With
any of them missing this delivers locally - to stdout, which the job
description points at `MURSCOPE_HOME/alerts.log` - and says which one was
missing. What the recorded consent buys is that murscope does not ask
again; that is the whole difference between the two consents this product
now has, and the consent screen says so in the owner's words.
"""
from __future__ import annotations

import sys

from . import cli


def main(argv=None):
    """Evaluate the alert rules and deliver. Takes no arguments.

    Returns `cli.alert_command`'s exit code, which is non-zero when an
    outbound delivery was attempted and did not complete - because the
    failure that matters on this surface is the quiet one, where a user
    believes an alert went out and it did not.
    """
    args = list(sys.argv[1:] if argv is None else argv)
    if args:
        sys.stderr.write(
            "murscope-alert takes no arguments; got %s.\n"
            "This is the scheduled alert entry point and it does exactly one "
            "thing: evaluate the alert rules against a fresh collection and "
            "deliver what fired. It has no options because an option is a "
            "way for a job description written once to mean something else "
            "later (DP124, and DP125 for what this one may send).\n"
            % " ".join(repr(arg) for arg in args))
        return 2
    return cli.alert_command([], unattended=True)


if __name__ == "__main__":
    sys.exit(main())
