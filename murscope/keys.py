"""Key storage, and the masking that keeps a key out of the artifacts.

DP18 settled the storage: **0600 files under `MURSCOPE_HOME` first**,
because that needs no dependency and keeps ADR-0001 intact, with the
system keychain available as the `keyring` extra. README states the
security difference plainly rather than implying the file is as good, and
so does `murscope key list`: a file is protected by the filesystem and by
nothing else, so anything running as you can read it, and a backup that
copies your home copies your keys with it. The keychain is protected by
the operating system and asks before it hands a secret over. The file is
the default because it always works; it is not the safer of the two.

**This module lives in the core, and a base install has it.** That is
deliberate and it does not touch DP88. Promise two is about sockets, and
nothing here opens one - what is on the far side of the `[ai]` boundary
is the transport, not the cupboard. The gain is that the guard below runs
on every install rather than only on the ones that could leak: the decoy
in `murscope selftest` plants a key and looks for it in every artifact,
and a guard that only existed once the extra was installed would be a
guard the boundary crossed before it arrived.

## The three things a key must survive

**One: being printed.** `read()` never returns a string. It returns a
`Secret`, whose `__str__`, `__repr__` and `__format__` all say the same
withheld sentence, so `"%s" % key`, `f"{key}"`, `print(key)`, `repr` in a
debugger and `json.dumps` (which refuses it outright) cannot spell it.
Reaching the value takes `.value`, which is one visible word at the call
site and greppable.

**Two: being carried out inside somebody else's message.** This is the
one that only happens on the day something goes wrong, which is why it is
built here rather than noticed later. A URL with a key in its query
string, handed to `urllib`, comes back as
`ValueError: unknown url type: 'nonsense?key=<the actual key>'` - the
library builds that string, not us, and no amount of care at our call
sites prevents it. So a failing transport does not re-raise what it
caught: it calls `reraise_masked()`, which redacts the text and raises
`from None`. **The `from None` is the load-bearing half.** Without it the
original exception stays on `__context__`, and `traceback.print_exc()`
prints it under "During handling of the above exception" with the key
intact. An exception traceback is an artifact.

**Three: being redacted where it should not be.** `redact()` is applied
to error text and to nothing else. It is deliberately *not* applied to
the board payload on the way out, tempting as that is: a payload scrubber
would mean a key that reached the payload got masked instead of noticed,
and the canary that is supposed to go red would go green forever. The
board's protection is that no reader ever touches a key; the canary
measures that, and a scrubber would remove the measurement.

Values shorter than `MINIMUM_LENGTH` are refused at `store()` and are not
redacted, because a three-character secret would mask every occurrence of
three characters in any text it was applied to. Said out loud rather than
left as a surprise: no real API key is that short, and the refusal is
where a user learns it.
"""
from __future__ import annotations

import os
import re
from pathlib import Path

from .guard import guard_write_path, murscope_home

KEYS_DIRNAME = "keys"
FILE_MODE = 0o600
DIR_MODE = 0o700

# Long enough that redaction cannot turn into a text mangler, short enough
# that no real credential is refused. A key below this is a typo or a
# placeholder, and both are better refused at the door.
MINIMUM_LENGTH = 8

MASK = "[withheld]"

# `?key=...`, `&token=...`, and every other value in a URL's query string.
# **This is the half that catches a key the store never saw.** `redact()`
# below can only mask values this process read through `Secret`, and the
# transport is handed a URL by its caller - who may have built it from an
# environment variable, or from a literal. The gate's own check found
# exactly that: a decoy the store had never seen went straight into the
# traceback with `redact()` reporting nothing to do.
#
# A query string is where a credential ends up, so in a *failure message*
# every query value is treated as one. That is deliberately blunt: this
# runs on the error path, where being unable to read the exact value of
# `?stream=true` costs a debugging session and being able to read the
# exact value of `?key=` costs the key.
QUERY_VALUE = re.compile(r"([?&][A-Za-z0-9_.\-]{1,64}=)([^\s'\"&]+)")

NAME_CHARS = set("abcdefghijklmnopqrstuvwxyz"
                 "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-.")

KEYRING_SERVICE = "murscope"

# Every value this process has read, so `redact` can mask it without
# opening the key files again on every error. A set of raw values in
# memory is exactly as sensitive as the process already is - it read them
# on purpose - and it means redaction costs nothing on the happy path.
_KNOWN = set()


class Secret(object):
    """A key value that cannot be printed by accident.

    Not a security boundary - anything in the process can reach `.value`,
    and `_value` below is a convention rather than a lock. It is an
    accident boundary, which is the failure that actually happens: a key
    interpolated into a log line, a problem line, or an exception message
    by code that was thinking about something else.
    """

    __slots__ = ("name", "_value")

    def __init__(self, name, value):
        self.name = name
        self._value = value
        if isinstance(value, str) and len(value) >= MINIMUM_LENGTH:
            _KNOWN.add(value)

    @property
    def value(self):
        """The key itself. One visible word at the call site, greppable."""
        return self._value

    def __str__(self):
        return "<murscope key %r: withheld>" % self.name

    def __repr__(self):
        return self.__str__()

    def __format__(self, spec):
        # Without this, `"{:>20}".format(secret)` goes through
        # `object.__format__`, which raises for a non-empty spec - and an
        # empty spec would still take `str()`. Both answers are the mask.
        return self.__str__()

    def __bool__(self):
        return bool(self._value)


class Masked(RuntimeError):
    """A failure whose message has been through `redact()`."""


def redact(text, extra=()):
    """Every known key value in `text`, replaced by the mask.

    Two passes, because one of them cannot be complete on its own. The
    first masks values this process actually read - which is every key
    murscope itself uses, and nothing a caller built elsewhere. The second
    masks the values of a URL query string, which is where a credential
    ends up whether or not this process ever saw it.

    `extra` is for a value this process holds but never wrapped in a
    `Secret`. Values shorter than `MINIMUM_LENGTH` are ignored on purpose;
    see the module docstring.
    """
    if not isinstance(text, str):
        text = str(text)
    for value in sorted(set(_KNOWN) | set(extra), key=len, reverse=True):
        if isinstance(value, str) and len(value) >= MINIMUM_LENGTH:
            text = text.replace(value, MASK)
    return QUERY_VALUE.sub(lambda m: m.group(1) + MASK, text)


# How much of a rejected request's body is worth carrying into the error.
# Enough for a vendor's `{"error": {"message": ...}}`, short enough that a
# provider answering with a page of HTML does not become the message.
DETAIL_LIMIT = 400


def _detail(exc):
    """A vendor's own explanation, if the failure carries one.

    `urllib` raises `HTTPError`, which is also a readable response - and
    the readable half is where the vendor says *why*. Without this the
    message is "HTTP Error 400: Bad Request" and the user is told the
    status code they could already see, while the sentence naming the
    expired key or the exhausted balance is thrown away unread.

    It goes through `redact()` with everything else. A body is a place a
    credential can be echoed back, and a vendor that includes the key it
    rejected has put it somewhere this product would otherwise print.
    """
    reader = getattr(exc, "read", None)
    if not callable(reader):
        return ""
    try:
        raw = reader()
    except Exception:  # a body that cannot be read is not a second failure
        return ""
    if not raw:
        return " The provider sent no explanation with it."
    if isinstance(raw, bytes):
        raw = raw.decode("utf-8", errors="replace")
    text = " ".join(str(raw).split())[:DETAIL_LIMIT]
    return (" The provider said: %s" % text) if text else ""


def reraise_masked(exc, context):
    """Raise a redacted `Masked` in place of `exc`, dropping the chain.

    Called from inside an `except` block. Two things happen and both are
    necessary: the message is redacted, and `from None` suppresses
    `__context__` so the original - whose text is where the key was - does
    not follow the new exception into the traceback.

    The whole reason this is a function in the core rather than three
    lines in the transport: the transport ships in a distribution most
    users do not have, and this shape has to be exercisable by
    `murscope selftest` on a base install.

    It also pulls the vendor's own explanation out of the failure when
    there is one - see `_detail`. That happens here rather than at the
    call site because Rule 18 permits a transport to hand its caught
    exception to exactly this function and nothing else, which is the
    right constraint: reading a response body is the sort of thing that
    would otherwise be written four times, once per adapter, and be
    unredacted in one of them.
    """
    raise Masked(redact("%s (%s: %s)%s" % (context, type(exc).__name__, exc,
                                           _detail(exc)))) from None


# The characters a credential may hold. Visible ASCII, no space: exactly
# what can travel in an HTTP header without the standard library or the
# far end having to decide what was meant.
#
# **This exists because a key was corrupted on the way in and nothing said
# so until the far end refused it.** A value arrived 38 characters long
# where the vendor's console showed 35, went into an `Authorization`
# header, and was rejected by the gateway *before* authentication ran - so
# every endpoint answered `400` with an empty body, on every route, and the
# obvious reading ("it authenticates, so the account is refusing") was
# wrong. An interactive paste is the ordinary way this happens.
#
# The honest limit of this check, stated rather than implied: **it cannot
# tell whether a key is the right key.** That needs the network and this
# module does not have it. What it can do is refuse a value that could not
# work as a header at all, and turn a remote unexplainable failure into a
# local explainable refusal.
HEADER_SAFE_LOW, HEADER_SAFE_HIGH = 0x21, 0x7E


def shape_problems(value):
    """Findings about a value's characters. Never echoes the value.

    Positions and categories only. The whole point of this module is that a
    key does not reach a message, and a diagnostic that printed the two
    characters it objected to would be a diagnostic that printed part of a
    key into somebody's terminal and their issue report.
    """
    findings = []
    if not isinstance(value, str):
        return ["a key must be text"]
    spaces = [i for i, char in enumerate(value) if char in " \t"]
    controls = [i for i, char in enumerate(value) if ord(char) < 0x20
                or ord(char) == 0x7F]
    wide = [i for i, char in enumerate(value) if ord(char) > HEADER_SAFE_HIGH]
    if spaces:
        findings.append(
            "%d character(s) at position(s) %s are a space or a tab. A "
            "credential does not contain one, and a paste that picked up "
            "surrounding text is the usual way it acquires one."
            % (len(spaces), ", ".join(str(i + 1) for i in spaces[:8])))
    if controls:
        findings.append(
            "%d control character(s) at position(s) %s. These cannot travel "
            "in an HTTP header, and a value carrying one is refused by the "
            "far end before anything reads it."
            % (len(controls), ", ".join(str(i + 1) for i in controls[:8])))
    if wide:
        findings.append(
            "%d character(s) at position(s) %s are outside printable ASCII. "
            "A terminal or an editor that replaced a character with a "
            "typographic lookalike leaves exactly this."
            % (len(wide), ", ".join(str(i + 1) for i in wide[:8])))
    return findings


def keys_dir(home=None):
    return (home or murscope_home()) / KEYS_DIRNAME


def key_path(name, home=None):
    return keys_dir(home) / name


def valid_name(name):
    """(ok, reason). A key name becomes a filename, so it is constrained."""
    if not isinstance(name, str) or not name.strip():
        return False, "a key name cannot be empty"
    if name != name.strip():
        return False, "a key name cannot begin or end with whitespace"
    if any(char not in NAME_CHARS for char in name):
        return False, ("a key name may hold letters, digits, dot, dash and "
                       "underscore only; %r does not" % name)
    if name in (".", "..") or name.startswith("."):
        return False, "a key name may not begin with a dot"
    return True, ""


def store(name, value, home=None, backend="file"):
    """Put a key away. Returns (where, problems).

    `where` is a human-readable location - a path for the file backend,
    the service name for the keychain - and is never the value.
    """
    ok, reason = valid_name(name)
    if not ok:
        return None, [reason]
    if not isinstance(value, str) or len(value) < MINIMUM_LENGTH:
        return None, ["a key must be at least %d characters; nothing was "
                      "stored. murscope refuses a short one rather than "
                      "storing it, because redaction cannot mask a value "
                      "short enough to occur in ordinary text."
                      % MINIMUM_LENGTH]
    shape = shape_problems(value)
    if shape:
        return None, [
            "that value cannot travel in an HTTP header, so nothing was "
            "stored: %s Compare its length with the one your provider's "
            "console shows - a key that is the wrong length is a key that "
            "was mangled on the way here, and the far end will refuse it "
            "with a status code that explains nothing." % " ".join(shape)]
    if backend == "keyring":
        module, problem = _keyring()
        if module is None:
            return None, [problem]
        try:
            module.set_password(KEYRING_SERVICE, name, value)
        except Exception as exc:  # a keychain refusal is not a crash
            return None, [redact("the system keychain refused to store %r "
                                 "(%s: %s)."
                                 % (name, type(exc).__name__, exc))]
        _KNOWN.add(value)
        return "system keychain, service %r" % KEYRING_SERVICE, []
    target = guard_write_path(key_path(name, home), value + "\n",
                              mode=FILE_MODE)
    _KNOWN.add(value)
    return str(target), []


def read(name, home=None, backend="file"):
    """A `Secret`, or None. Returns (secret, problems) - never a string."""
    ok, reason = valid_name(name)
    if not ok:
        return None, [reason]
    if backend == "keyring":
        module, problem = _keyring()
        if module is None:
            return None, [problem]
        try:
            value = module.get_password(KEYRING_SERVICE, name)
        except Exception as exc:
            return None, [redact("the system keychain refused to hand over "
                                 "%r (%s: %s)."
                                 % (name, type(exc).__name__, exc))]
        if not value:
            return None, []
        return Secret(name, value), []
    path = key_path(name, home)
    if not path.is_file():
        return None, []
    try:
        value = path.read_text(encoding="utf-8").strip()
    except OSError as exc:
        return None, [redact("%s cannot be read (%s)." % (path, exc))]
    if not value:
        return None, []
    return Secret(name, value), []


def names(home=None):
    """Key names on disk, for the file backend. Names only, never values."""
    directory = keys_dir(home)
    if not directory.is_dir():
        return []
    found = []
    for path in sorted(directory.iterdir()):
        if path.is_file() and valid_name(path.name)[0]:
            found.append(path.name)
    return found


def audit(home=None):
    """[(name, mode, length, findings)] for every stored key file.

    The mode is one point. A key file that has been widened - copied by a
    backup, restored by an installer, or written by an earlier version -
    is still a key file, and the user is entitled to be told rather than
    to assume the tool fixed it silently.

    **The length is the other, and it was learned the hard way.** A key
    reached this store 38 characters long where the vendor's console showed
    35, and nothing anywhere said so: it stored cleanly, read back cleanly,
    and failed only at the far end with a `400` carrying no body - on every
    endpoint, which is what made the failure read as an account problem
    rather than a mangled value. A length is not the value and it does not
    weaken Rule 18's promise; it is the one number a user can compare
    against what their provider shows them, and comparing it is what found
    this.

    A stored value is examined and never returned. The findings name
    positions and categories, never characters.
    """
    rows = []
    for name in names(home):
        path = key_path(name, home)
        findings = []
        try:
            mode = os.stat(str(path)).st_mode & 0o777
        except OSError as exc:
            rows.append((name, None, None,
                         [redact("cannot be examined (%s)" % exc)]))
            continue
        if mode != FILE_MODE:
            findings.append(
                "mode is %04o, not %04o: anything running as another user "
                "on this machine can read it. `chmod %04o %s` closes it."
                % (mode, FILE_MODE, FILE_MODE, path))
        length = None
        try:
            value = path.read_text(encoding="utf-8").strip()
        except (OSError, UnicodeDecodeError) as exc:
            findings.append(redact("cannot be read (%s)" % exc))
        else:
            length = len(value)
            findings.extend(shape_problems(value))
        rows.append((name, mode, length, findings))
    return rows


def _keyring():
    """(module, problem). The system keychain, if the extra is installed.

    No silent fallback to the file backend. Falling back would mean a user
    who chose the keychain gets a 0600 file and is told nothing - which is
    the whole shape DP49 is about, one layer down: a degraded result that
    looks exactly like the thing that was asked for.
    """
    try:
        import keyring  # noqa: PLC0415 - optional, and only this path needs it
    except Exception as exc:
        return None, redact(
            "the keychain backend is configured and the `keyring` package is "
            "not importable (%s: %s). Nothing was read or written, and "
            "murscope did not quietly use a file instead - install it with "
            "`pip install 'murscope[keyring]'`, or set backend = \"file\" in "
            "[keys]." % (type(exc).__name__, exc))
    return keyring, ""
