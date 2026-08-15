"""The entry point a scheduler runs, and the only thing this product does
with nobody present.

Everything M3 shipped that left the machine had a person in front of it:
a consent screen read, a `yes` typed, and the send in the next second.
This module breaks that adjacency, and DP124 is the ruling about what may
therefore be on the other side of it - **it collects and renders, and it
cannot send.**

That is why this is a module and a console script of its own rather than
a flag on `murscope`. `murscope` is an argv dispatcher: `daily --send` is
one word away from `run`, and a scheduler's job description is a string
in a file that nothing re-reads. `murscope-timer` takes no arguments at
all - it refuses them rather than ignoring them, because a job description
that grew an argument should fail loudly rather than quietly do the old
thing - and from `main()` below there is no call path in the package that
reaches a transport. That claim is not a comment: Rule 26's check walks
the call graph from this function and goes red if one appears, and it goes
red just as fast if its own walk stops being able to reach the collection
it is supposed to be walking through.

**Gating it on a setting was refused, and DP88 is why.** A capability the
user has to go and audit a configuration file to rule out is a capability
that is on. The honest form of "this cannot send" is that the send is not
reachable from here, and the honest way to say it is a check that fails
when it becomes reachable.
"""
from __future__ import annotations

import sys

from . import cli


def main(argv=None):
    """Collect the roster and write the board. Takes no arguments.

    Returns `cli.run`'s exit code, which a scheduler will record and
    almost nobody will read; the board and MURSCOPE_HOME/timer.log are
    what a person actually looks at afterwards.
    """
    args = list(sys.argv[1:] if argv is None else argv)
    if args:
        sys.stderr.write(
            "murscope-timer takes no arguments; got %s.\n"
            "This is the scheduled entry point and it does exactly one "
            "thing: collect the roster and render the board. It has no "
            "options because an option is a way for a job description "
            "written once to mean something else later (DP124).\n"
            % " ".join(repr(arg) for arg in args))
        return 2
    return cli.run([])


if __name__ == "__main__":
    sys.exit(main())
