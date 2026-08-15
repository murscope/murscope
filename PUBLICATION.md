# Publication

This repository is the published derivation. **Nothing here was released
by being made public.** Every file in this tree was produced from a
development repository by the one mechanism this line has for publishing
anything, and that mechanism is named below (DP160, DP162).

## The declaration

```
Switch:    never
Mechanism: scripts/public_tree.py
```

`Switch: never` is the ruling, and it is a ruling about every repository
in this line rather than about one of them: no repository here is
published by having its visibility flipped. A flip releases a history
and derives nothing - it withholds nothing, rewrites nothing and
regenerates nothing. `Mechanism:` names the file that does all three,
and Rule 36's check refuses a mechanism that is not really one, so this
cannot decay into a filename that stopped meaning anything.

## Why a file, and why a check

Every other irreversible thing in this line is a file, and files have
checks. This one is a **setting**, and until Rule 36 it had nothing: no
check, no CI, no repository configuration stood between somebody opening
a settings page and a development repository's whole history becoming
readable in one click. DP160 ruled that the release is a second
repository - the one you are reading - and a decision without a check is
the wall art Rule 1 has refused since the first commit. It took until M5
for that argument to be turned on the repository making it.

## What this tree can say, and what it cannot

`scripts/public_tree.py` is in this tree and runs in it. The derivation
is idempotent, so extracting this tree yields this tree and Rule 35
reads the result - which is what makes the derivation auditable by
anybody holding this repository rather than only by whoever ran it:

    python3 scripts/public_tree.py --list
    python3 scripts/public_tree.py --extract <directory>

Rule 36's check asks a third question in a development tree - whether
the probe watching that repository's visibility is still installed, still
has a token, and can still fail the job - and it does not ask it here.
It works out which tree it is in by reading the derivation spec, and
says which on every run rather than skipping quietly.

That leaves something worth stating plainly rather than leaving a reader
to assume its opposite: **this tree carries no evidence about the
repository it came from.** A derivation is not a window onto its source.
What is in front of you is what was published; what was withheld is
listed, with the reason for each, in the spec named above.
