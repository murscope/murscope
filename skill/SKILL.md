---
name: murscope
description: Set up and drive murscope, a read-only portfolio dashboard. Use when the user wants to see which of their projects are moving, which have stalled and which are waiting on them; when they ask to install, configure or schedule murscope; or when they want help writing the one status line in a project that murscope reads and never writes.
---

# murscope

murscope scans the project directories it is pointed at and renders one
static page. It is read-only toward those projects, makes no network call
on a base install, and keeps everything under `MURSCOPE_HOME`
(`~/.murscope` by default).

## What this skill is for, and what it is not

`pipx install murscope` already gives the user every command below. This
skill exists for the one thing the command line will never do:

> **murscope never writes into a monitored project. You can.**

The most useful thing in murscope is a project's own status line - a
plain sentence in a `STATUS.md` or a `README.md` saying what is actually
going on. murscope reads it, quotes it on the board, and outranks its own
guesses with it. It will not author it, and it will not put it on disk:
that is red line one, and it is the reason a user can point this tool at
twenty repositories without auditing what it did to them.

So the division is: **murscope reads and renders; you interview and
write.** Everything in this skill is either running a murscope command or
writing a line into a file the user asked you to write into. It renders
nothing itself.

## Install

```
pipx install murscope
```

That install can reach no network at all - not a disabled provider, none
at all. The network layer is a separate distribution and arrives only if
the user asks for it by name (`pip install 'murscope[ai]'`).

## First run

```
murscope init
```

With no path it looks in the conventional project directories under the
user's home, names them on screen before it scans, and proposes what it
found. With a path it scans that path. Then:

```
murscope open
```

hands the board to the browser from disk. Nothing is served and nothing
is uploaded.

If the user wants to try it on one directory without agreeing to
anything, `murscope try <path>` writes a throwaway board and touches
their home not at all.

## The interview, which is the part worth doing

Read the board or run `murscope status --explain <project>` and ask about
the rows murscope had to guess at. A guessed row carries a badge saying
so; a quoted row does not. For each project the user cares about, ask
one question:

> What is actually going on with this one, in a sentence?

Then **write that sentence into the project yourself**, as a line the
parser reads - a `STATUS.md` heading, or a marked line such as
`BLOCKED: waiting on the vendor's reply`. Ask before you write, and write
into the project the user named and no other.

If the user would rather keep the sentence out of the repository, put it
in murscope's own roster instead:

```
murscope note <project> "..."
```

That writes under `MURSCOPE_HOME` and nowhere else. It is the same
sentence with a different home, and the board marks which of the two it
came from.

## Scheduling

```
murscope timer install
murscope timer status
murscope timer uninstall
```

The scheduled job collects and renders. It has no path to any transport
at all - that is structural, not a setting. Installing a timer is the one
thing murscope writes outside `MURSCOPE_HOME`: it names the exact file
before writing it, and `timer uninstall` removes it. Show the user the
path it prints.

## Do not do these

These are the user's acts and not yours. Show them the command and let
them run it:

- **Never** run a command that sends anything. If the user wants the
  daily note or an outbound alert, tell them the command and stop.
- **Never** record a consent for them. A consent is recorded against the
  exact list of fields the screen showed; agreeing on somebody's behalf
  to a disclosure they did not read is the one thing the whole consent
  mechanism exists to prevent.
- **Never** put a key in a shell command. `murscope key set <name>` reads
  it from stdin, never from argv, and never echoes it.

## Checking what is on the machine

```
murscope doctor
murscope modules
murscope selftest
```

`doctor` answers whether this interpreter can read what it was pointed
at. `modules` prints the module matrix: what is installed, what
configuration enabled, what each one reads and where each one sends - and
`unknown`, not `no`, for a module nothing imported. `selftest` proves the
marker vocabulary is still precise, that a collection and a render reach
no network, that no stored key reaches an artifact, and that nothing
installed could open a socket.
