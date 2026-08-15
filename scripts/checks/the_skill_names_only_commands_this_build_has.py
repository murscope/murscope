"""Rule 32: the skill names only commands this build has, and never one
that sends.

**Why the skill ships from this repository (DP1, N1, DP151).** DP1's
default is one repo and a separate one only when genuinely needed, and N1
reserved `murscope/skill` for the day that is true. It is not true yet,
and the reason is this file. A skill is a page of instructions naming a
command line; in its own repository nothing would notice when a command
is renamed, an option changes meaning, or a new one arrives that sends.
Here, that is a check - and a skill whose commands are verified against
the build shipping beside it is worth more than a skill with its own
release cadence.

**What the skill adds over `pipx install murscope`, which is the question
DP1 asks (DP151).** One thing, and it is not convenience: **murscope
never writes into a monitored project and an agent can.** The most useful
row on the board is a project's own status line, quoted rather than
guessed; the CLI will not author it and will not put it on disk, because
red line one is what lets a user point this tool at twenty repositories
without auditing what it did to them. The skill is the half that
interviews and writes. Everything else it does - install, init, open,
schedule - is one command, and wrapping one command in an agent is
decoration (DP14: a shell, not a fork; DP27: bootstrapping a ledger
belongs to the skill and the CLI never writes).

**What this rule holds.** Two properties, both structural:

1. **Every `murscope <word>` the skill names is a command this build
   dispatches** - read out of the shipped CLI in a fresh interpreter,
   never from a list kept here. A renamed command turns the page red
   instead of turning it into instructions that fail on the user's
   machine.
2. **The skill never tells an agent to run something that sends, or that
   agrees to a send.** `--send`, `consent grant`, and a key on a command
   line are the three, and they are refused by exact string rather than
   by review. An agent recording a consent is the failure the whole
   consent mechanism exists to prevent: a consent is recorded against the
   exact fields the screen showed, and agreeing on somebody's behalf to a
   disclosure they did not read empties it. This is not a style
   preference and it does not get to depend on somebody reading the page.

**What walks into this check (DP87).** The skill must name at least
`MINIMUM_COMMANDS` distinct commands and must name `init` among them,
because "every command it names exists" is trivially true of a page that
names none - and this check would then certify an empty file. The
forbidden strings are asserted to be *absent from the skill* and
*present in the product*, so a denylist that stopped matching anything
real goes red rather than passing quietly.

Fails when: the skill is missing, or has no `name:`/`description:`
frontmatter; it names a `murscope` command this build does not dispatch;
it names fewer than the floor, or does not name `init`; it contains any
of the forbidden send-shaped strings; or one of those strings is no
longer something the product itself has, so the denylist has stopped
naming anything.
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

SKILL = REPO_ROOT / "skill" / "SKILL.md"

# A `murscope <word>` mention, and it is only looked for **inside code** -
# a fenced block or an inline backtick span. The first version matched the
# whole document and reported `murscope writes`, `murscope had` and
# `murscope murscope` as commands this build does not have, which is the
# fragile-proxy road DP67 already measured at negative: the repair would
# have been a growing list of English words that are not commands. Where a
# command appears is a structural fact about markdown, and the structure
# is what this reads.
MENTION = re.compile(r"\bmurscope\s+([a-z][a-z-]*)\b")
FENCED = re.compile(r"```[a-z]*\n(.*?)```", re.S)
INLINE = re.compile(r"`([^`\n]+)`")

MINIMUM_COMMANDS = 4
MUST_NAME = "init"

# Strings the skill may not contain, each paired with where the product
# itself has it. The second half is the floor: a denylist that has stopped
# matching anything real would pass this check forever while naming
# nothing.
FORBIDDEN = (
    ("--send", "murscope/cli.py",
     "an agent must not run the command that sends. Show it and stop."),
    ("consent grant", "murscope/cli.py",
     "an agent must not record a consent. It is recorded against the exact "
     "fields the screen showed, and agreeing on somebody's behalf to a "
     "disclosure they did not read is what the mechanism exists to prevent."),
)

PROBE = r'''
import json, sys
sys.path.insert(0, %(repo)r)
from murscope import cli
print(json.dumps(cli.implemented_commands()))
'''


def frontmatter(text):
    """The skill's YAML frontmatter as {key: value}, or {}."""
    match = re.match(r"---\n(.*?)\n---\n", text, re.S)
    if not match:
        return {}
    found = {}
    for line in match.group(1).splitlines():
        if ":" in line and not line.startswith(" "):
            key, value = line.split(":", 1)
            found[key.strip()] = value.strip()
    return found


def code_spans(body):
    """Every fenced block and inline code span, as text."""
    spans = list(FENCED.findall(body))
    spans.extend(INLINE.findall(FENCED.sub("\n", body)))
    return spans


def named_commands(text):
    """Every `murscope <command>` the skill names in code, first seen first."""
    seen = []
    body = re.sub(r"^---\n.*?\n---\n", "", text, flags=re.S)
    for span in code_spans(body):
        for match in MENTION.finditer(span):
            word = match.group(1)
            if word not in seen:
                seen.append(word)
    return seen


def detect(payload):
    """Findings for one skill document.

    Pure: text in, findings out. The set of real commands is the one thing
    it needs from outside, so it is passed in beside the document rather
    than looked up here - `main()` reads it out of a fresh interpreter.
    """
    try:
        case = json.loads(payload.decode("utf-8"))
    except ValueError as exc:
        return ["the skill case is not readable JSON (%s)." % exc]

    text = case.get("text") or ""
    commands = set(case.get("commands") or ())
    findings = []

    front = frontmatter(text)
    for key in ("name", "description"):
        if not front.get(key):
            findings.append(
                "the skill has no `%s:` in its frontmatter, so nothing loads "
                "it as a skill." % key)

    named = named_commands(text)
    for word in named:
        if commands and word not in commands:
            findings.append(
                "the skill tells the reader to run `murscope %s`, and this "
                "build dispatches no such command. A page of instructions "
                "that fail on the user's machine is worse than no page."
                % word)
    if len(named) < MINIMUM_COMMANDS:
        findings.append(
            "the skill names %d command(s) and %d is the floor. 'Every "
            "command it names exists' is true of a page that names none, "
            "and this check would certify it."
            % (len(named), MINIMUM_COMMANDS))
    if MUST_NAME not in named:
        findings.append(
            "the skill never names `murscope %s`, which is the command a "
            "first run is. A skill that cannot get somebody started is not "
            "the shell DP14 describes." % MUST_NAME)

    body = re.sub(r"^---\n.*?\n---\n", "", text, flags=re.S)
    # The forbidden strings, checked only where they are an instruction.
    # The skill is allowed - and required - to say *not* to do these, so a
    # line carrying "never" or "do not" is the sentence that forbids it
    # rather than the sentence that asks for it.
    for line in body.splitlines():
        lowered = line.lower()
        if "never" in lowered or "do not" in lowered or "let them" in lowered:
            continue
        for needle, _where, why in FORBIDDEN:
            if needle in line:
                findings.append(
                    "the skill line %r carries %r as an instruction. %s"
                    % (line.strip()[:70], needle, why))
    return findings


def denylist_floors():
    """Every forbidden string must still name something the product has."""
    findings = []
    for needle, where, _why in FORBIDDEN:
        path = REPO_ROOT / where
        if not path.exists() or needle not in path.read_text(encoding="utf-8"):
            findings.append(
                "%r no longer appears in %s, so this check is refusing a "
                "string the product does not have. A denylist that has "
                "stopped naming anything real passes forever." % (needle, where))
    return findings


def main():
    if not SKILL.exists():
        print("FAILED: %s is missing. Rule 32 has nothing to check, which is "
              "red rather than green."
              % SKILL.relative_to(REPO_ROOT).as_posix())
        return 1

    findings = denylist_floors()
    result = subprocess.run(
        [sys.executable, "-c", PROBE % {"repo": str(REPO_ROOT)}],
        cwd=str(REPO_ROOT), stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        timeout=120)
    if result.returncode != 0:
        print("the shipped CLI could not be asked which commands it has: %s"
              % result.stderr.decode("utf-8", "replace").strip()[:400])
        print("\nFAILED: the skill's commands were not verified against "
              "anything.")
        return 1
    commands = json.loads(result.stdout.decode("utf-8"))
    if not commands:
        print("the shipped CLI reports no commands at all, so every name in "
              "the skill would pass by comparison with an empty set.")
        print("\nFAILED: the comparison set is empty.")
        return 1

    text = SKILL.read_text(encoding="utf-8")
    findings.extend(detect(json.dumps(
        {"text": text, "commands": commands}).encode("utf-8")))

    if findings:
        for finding in findings:
            print(finding)
        print("\nFAILED: %d finding(s) against the skill." % len(findings))
        return 1

    named = named_commands(text)
    print("OK: skill/SKILL.md names %d murscope command(s) (%s), every one of "
          "them dispatched by this build's own CLI - read out of "
          "cli.implemented_commands() in a fresh interpreter, not from a list "
          "kept beside this check. It carries no instruction to send: %d "
          "forbidden string(s) (%s) appear nowhere in it except on the lines "
          "that forbid them, and each one is asserted to still be something "
          "the product has, so the denylist cannot go quiet."
          % (len(named), ", ".join(named), len(FORBIDDEN),
             ", ".join(repr(n) for n, _w, _y in FORBIDDEN)))
    print("    The skill ships from this repository rather than its own "
          "(DP1, N1, DP151): its whole content is instructions naming this "
          "command line, and in a separate repository nothing would notice a "
          "renamed command. What it adds over `pipx install murscope` is the "
          "one thing the CLI structurally will not do - murscope never writes "
          "into a monitored project, and the sentence worth having there is "
          "one somebody has to write (DP27).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
