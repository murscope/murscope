"""Rule 18: keys are stored 0600 and never rendered.

DP18 settled where a key lives. This is the rule that keeps it there, and
it has two instruments because the two failures are not the same failure.

**The static half** reads the modules that hold or transmit a secret -
`murscope/keys.py`, every provider module in the base package, and every
provider module in the `extras/` distributions - and refuses four shapes:

1. **a key written without a mode.** `guard_write_path(key_path(...), v)`
   writes 0644, and the file is the whole of the protection.
2. **a masking method that unmasks.** `Secret.__str__`, `__repr__` and
   `__format__` exist so that a key cannot be printed by accident;
   one that returns the value is worse than none, because the call sites
   have stopped being careful on the strength of it.
3. **a `raise` inside an `except` that does not say `from None`.** This is
   the implicit one: `raise Whatever(...)` inside a handler chains the
   original on `__context__`, and `traceback.print_exc()` prints it under
   "During handling of the above exception" - with whatever the original
   message held.
4. **the caught exception used for anything but redaction.** `print(exc)`,
   `"%s" % exc` and `raise X(str(exc))` all carry the original text out,
   and the original text is where a key ends up: `urllib` answers a URL it
   cannot parse with `ValueError: unknown url type: '...?key=<the key>'`,
   which the standard library built and no care at our call sites
   prevents. So inside these modules the bound name may appear only
   inside a `redact()` or `reraise_masked()` argument, or inside
   `type()`, which reaches the class and never the message.

**A value that cannot travel in a header is refused at the door (DP112).**
A key reached this store 38 characters long where the vendor's console
showed 35 - an interactive paste - and it stored cleanly, read back
cleanly, and was rejected by the gateway *before* authentication ran. So
every endpoint answered `400` with an empty body, and the failure read as
an account problem rather than a mangled value. `store()` now refuses a
value carrying a space, a control character or a character outside
printable ASCII, and `audit()` reports each key's **length** - the one
number a user can hold against what their console shows them, and the one
that would have caught this.

Neither is a claim that a key is *valid*: that needs the network, which
this module does not have, and the rule says so rather than implying more.
The refusals name positions and categories and never characters - a
diagnostic that echoed what it objected to would have put part of a key
into a terminal and an issue report.

**The live half** is what a parse tree cannot do, and it is where the
teeth are. It stores a decoy through the real store and measures the
mode; it refuses three mangled values - a space in the middle, a trailing
carriage return, a typographic lookalike - and asserts none of those
refusals echoes the value; it reads back the length the audit reports; it
asks the real `Secret` for its value five ways and checks that none of
them answers; and then it **exercises the transport's failure path for
real** - the extras module loaded from disk, handed a URL with
the decoy in its query string, in a subprocess under an audit hook that
refuses socket events. The failure is provoked by a URL `urllib` cannot
parse, so the leak happens where it happens in the field and no socket is
ever opened.

**Every transport, and each with its own grant (DP103).** The probe built
one grant, for the provider name and field list the first transport
happened to use. The second transport to ship refused it on consent - as
it should - and therefore never reached the failure path this check
exists to exercise, which surfaced here as "the traceback carries no
mask". That finding was true and its cause was this probe: nothing had
been masked because nothing had failed. A transport now declares
`PROVIDER` and `consent_fields()`, and each is handed a grant built from
its own declaration.

The keychain backend is exercised too, against a **stub** `keyring`
module: it must name a service, hand back a `Secret`, write no file, and
refuse rather than fall back to a file when the package is missing. That
proves the wiring and nothing more, and the summary line says so - a real
exercise writes into the machine's own keychain and prompts its owner,
which a gate may not do to somebody who typed one command. DP89's
discipline, applied a stage early.

**What walks into each finding (DP87).** Every static shape above ships
as a case in this check's own fixture, so a branch that stopped working
cannot pass by never being reached. The live half asserts three things
that make the absences mean something: the traceback must be non-empty,
it must carry the mask (or redaction never ran and it is clean for the
wrong reason), and the child must report that the transport really was
the code that raised. **If the extras module cannot be loaded this check
goes red rather than green**, for the reason Rule 13b goes red without a
build backend: a check that reports success when its instrument is
missing is not a check.

Fails when: a provider or the key store writes a key without a file mode;
a masking method returns the value; a `raise` inside an `except` in those
modules keeps its context; a caught exception is used for anything but
redaction there; the stored key file is not 0600 or its directory not
0700; the store accepts a value carrying a space, a control character or a
character outside printable ASCII; a refusal echoes the value it objected
to; the audit does not report a stored key's length;
`str`, `repr`, `format` or `json.dumps` yields a key's value;
`redact()` leaves a known value in place; the keychain backend writes a
file, loses the value, or falls back silently when `keyring` is missing;
a masked failure keeps its context or carries no mask; the transport's
failure path puts the key in its traceback; the transport opens a socket
while failing; or the transport module cannot be loaded at all.
"""
from __future__ import annotations

import ast
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
KEY_STORE = REPO_ROOT / "murscope" / "keys.py"
PROVIDERS = REPO_ROOT / "murscope" / "providers"
EXTRAS_ROOT = REPO_ROOT / "extras"

WRITER = "guard_write_path"
MODE_KEYWORD = "mode"
# The mask the core writes over a redacted value. Held here as a literal
# rather than imported, so a check that runs before the package is
# importable still reads the right thing; the live half asserts the two
# agree.
MASK = "[withheld]"
MASKING_METHODS = ("__str__", "__repr__", "__format__")
VALUE_ATTRS = ("value", "_value")
REDACTING = ("redact", "reraise_masked")

# Obviously fabricated and deliberately not shaped like any vendor's
# credential. A decoy that looked like a working key would be one.
DECOY = "murscope-decoy-key-not-a-real-credential-0000"

# The child that exercises the transport. It runs in a subprocess for two
# reasons: the gate's own process then never imports `urllib` (Rule 11
# holds `scripts/` to the same bar as the core), and the audit hook it
# installs can refuse a socket outright without having to be uninstalled
# afterwards.
PROBE = r'''
import importlib.util, json, sys, traceback

REPO, MODULE, DECOY = sys.argv[1], sys.argv[2], sys.argv[3]
sys.path.insert(0, REPO)
report = {"loaded": False, "raised": "", "text": "", "sockets": []}

EVENTS = ("socket.connect", "socket.getaddrinfo", "socket.gethostbyname",
          "socket.sendto", "socket.bind", "urllib.Request")

def hook(event, args):
    if event in EVENTS:
        report["sockets"].append(event)
        raise RuntimeError("a socket was reached for")

try:
    from murscope import consent, outbound
    spec = importlib.util.spec_from_file_location(
        "murscope.providers.network", MODULE)
    network = importlib.util.module_from_spec(spec)
    sys.modules["murscope.providers.network"] = network
    spec.loader.exec_module(network)
    report["loaded"] = True
except Exception as exc:
    report["error"] = "%s: %s" % (type(exc).__name__, exc)
    print(json.dumps(report))
    raise SystemExit(0)

# A URL urllib cannot parse, carrying the decoy where an API key goes.
url = "nonsense?key=%s" % DECOY

# Which consent this transport requires, asked rather than assumed
# (DP103). Handing every module the first module's grant does not test
# the others: the second transport to ship refused on consent, never
# reached its failure path, and this check reported a traceback with no
# mask in it - correctly, because nothing had been masked, and for
# entirely the wrong reason.
provider = getattr(network, "PROVIDER", "network")
declared = getattr(network, "consent_fields", None)
fields = tuple(declared()) if callable(declared) else outbound.fields()
report["provider"] = provider

grant = consent.Grant(provider, consent.destination_of(url),
                      consent.fingerprint(fields, provider,
                                          consent.destination_of(url)),
                      fields, "now")
sys.addaudithook(hook)
try:
    network.send(url, b"{}", consent=grant)
    report["raised"] = "nothing"
except BaseException as exc:
    report["raised"] = type(exc).__name__
    report["text"] = "".join(
        traceback.format_exception(type(exc), exc, exc.__traceback__))
print(json.dumps(report))
'''


def _callee(call):
    if not isinstance(call, ast.Call):
        return None
    return getattr(call.func, "id", None) or getattr(call.func, "attr", None)


def _reaches_value(node):
    """Does this expression reach `.value` or `._value` on anything?"""
    for sub in ast.walk(node):
        if isinstance(sub, ast.Attribute) and sub.attr in VALUE_ATTRS:
            return True
    return False


def _bare_exception_uses(handler):
    """Uses of the caught exception that carry its message somewhere.

    Every mention of the bound name is a finding **except** two, and the
    two exceptions are what keep this from being a rule nobody can follow:

    * `type(exc)` reaches the class, never the message. `"%s: %s" %
      (type(exc).__name__, exc)` is therefore half permitted and half not,
      which is exactly right - the second `%s` is the message;
    * a direct argument to `redact()` or `reraise_masked()`, which is the
      whole point of those two functions existing.

    Anything else - `print(exc)`, `"%s" % exc`, `raise X(str(exc))`,
    `logger.warning(exc)` - puts the original text somewhere it can be
    read, and the original text is where a key ends up.
    """
    allowed = set()
    for sub in ast.walk(handler):
        if not isinstance(sub, ast.Call):
            continue
        callee = _callee(sub)
        if callee == "type":
            for arg in sub.args:
                if isinstance(arg, ast.Name) and arg.id == handler.name:
                    allowed.add(id(arg))
        elif callee in REDACTING:
            # Anywhere inside the argument, not only as the argument
            # itself: `redact("%s: %s" % (type(exc).__name__, exc))` is
            # the ordinary spelling, and the message really is redacted.
            for arg in list(sub.args) + [kw.value for kw in sub.keywords]:
                for inner in ast.walk(arg):
                    if isinstance(inner, ast.Name) and inner.id == handler.name:
                        allowed.add(id(inner))
    findings = []
    for sub in ast.walk(handler):
        if (isinstance(sub, ast.Name) and sub.id == handler.name
                and id(sub) not in allowed):
            findings.append(
                "%d: the caught exception %r is used unredacted. The message "
                "of a failed request is where a key gets carried out - urllib "
                "answers an unparseable URL with the URL. In these modules it "
                "may reach %s, or `type()` for its class name, and nothing "
                "else." % (sub.lineno, handler.name,
                           " or ".join("%s()" % name for name in REDACTING)))
    return findings


def detect(payload):
    """Findings for one module that holds or transmits a secret."""
    source = payload.decode("utf-8", errors="replace")
    try:
        tree = ast.parse(source)
    except SyntaxError as exc:
        return ["cannot parse (%s)." % exc]

    findings = []

    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and _callee(node) == WRITER:
            named = set(kw.arg for kw in node.keywords)
            writes_key = any(
                isinstance(sub, ast.Call) and _callee(sub) in (
                    "key_path", "keys_dir")
                for arg in node.args for sub in ast.walk(arg))
            if writes_key and MODE_KEYWORD not in named:
                findings.append(
                    "%d: writes a key through %s() with no mode=, so it lands "
                    "at whatever the umask says. A key file is protected by "
                    "the filesystem and by nothing else (DP18)."
                    % (node.lineno, WRITER))

        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if node.name in MASKING_METHODS:
                for sub in ast.walk(node):
                    if isinstance(sub, ast.Return) and sub.value is not None \
                            and _reaches_value(sub.value):
                        findings.append(
                            "%d: %s() returns the key value. These methods "
                            "exist so a key cannot be printed by accident; "
                            "one that unmasks is worse than none, because "
                            "every call site has stopped being careful on the "
                            "strength of it." % (sub.lineno, node.name))

        if isinstance(node, ast.ExceptHandler):
            for sub in ast.walk(node):
                if isinstance(sub, ast.Raise) and sub.exc is not None:
                    cause = sub.cause
                    if not (isinstance(cause, ast.Constant)
                            and cause.value is None):
                        findings.append(
                            "%d: raises inside an `except` without `from "
                            "None`, so the original exception stays on "
                            "__context__ and every traceback prints it under "
                            "\"During handling of the above exception\" - "
                            "message and all." % sub.lineno)
            if node.name:
                findings.extend(_bare_exception_uses(node))
    return findings


def guarded_modules():
    """Every module that holds or transmits a secret, in scope order."""
    found = [KEY_STORE] if KEY_STORE.exists() else []
    if PROVIDERS.is_dir():
        found.extend(sorted(p for p in PROVIDERS.glob("*.py")
                            if p.name != "__init__.py"))
    if EXTRAS_ROOT.is_dir():
        for path in sorted(EXTRAS_ROOT.glob("*/murscope/providers/*.py")):
            if path.name != "__init__.py":
                found.append(path)
    return found


def transport_modules():
    """Provider modules in the extras distributions: the ones that send."""
    if not EXTRAS_ROOT.is_dir():
        return []
    return sorted(path for path in EXTRAS_ROOT.glob("*/murscope/providers/*.py")
                  if path.name != "__init__.py")


def live_store_findings():
    """Store a decoy for real, and ask the store for it five ways."""
    sys.path.insert(0, str(REPO_ROOT))
    try:
        from murscope import keys
    except Exception as exc:
        return ["the key store could not be imported (%s: %s), so nothing "
                "was exercised." % (type(exc).__name__, exc)], 0

    findings = []
    checked = 0
    with tempfile.TemporaryDirectory() as work:
        previous = os.environ.get("MURSCOPE_HOME")
        os.environ["MURSCOPE_HOME"] = work
        try:
            home = Path(work)
            where, problems = keys.store("gate-decoy", DECOY, home)
            findings.extend("the store refused the decoy: %s" % p
                            for p in problems)
            if where is None:
                return findings + ["nothing was stored"], checked
            stored = Path(where)
            mode = os.stat(str(stored)).st_mode & 0o777
            checked += 1
            if mode != keys.FILE_MODE:
                findings.append("the key file is at mode %04o, not %04o"
                                % (mode, keys.FILE_MODE))
            directory_mode = os.stat(str(stored.parent)).st_mode & 0o777
            checked += 1
            if directory_mode != keys.DIR_MODE:
                findings.append("the key directory is at mode %04o, not %04o"
                                % (directory_mode, keys.DIR_MODE))
            if DECOY not in stored.read_text(encoding="utf-8"):
                findings.append(
                    "the decoy is not in the file the store wrote, so every "
                    "assertion below is about the wrong value")

            # **A value that cannot travel in a header is refused here, not
            # by the far end (DP112).** A key reached this store 38
            # characters long where the vendor's console showed 35, stored
            # cleanly, read back cleanly, and was rejected by the gateway
            # before authentication ran - so every endpoint answered 400
            # with an empty body and the failure read as an account
            # problem. Three shapes, each the way an interactive paste
            # actually mangles a value.
            for label, mangled in (
                    ("a space in the middle", DECOY[:12] + " " + DECOY[12:]),
                    ("a trailing carriage return", DECOY + "\r"),
                    ("a typographic lookalike", DECOY[:-1] + "…")):
                where_bad, complaints = keys.store("gate-mangled", mangled,
                                                   home)
                if where_bad is not None:
                    findings.append(
                        "the store accepted a value with %s. It cannot go in "
                        "an HTTP header, so the far end refuses it with a "
                        "status code that explains nothing - which is a "
                        "remote unexplainable failure standing in for a "
                        "local explainable refusal." % label)
                    continue
                checked += 1
                text = " ".join(complaints)
                if mangled in text or DECOY in text:
                    findings.append(
                        "the refusal for %s printed the value it objected "
                        "to. A diagnostic that echoes part of a key has put "
                        "a key in a terminal and an issue report." % label)
            # The positive case, or every refusal above is satisfied by a
            # store that refuses everything - and the decoy above already
            # went in, which is what proves it does not.
            checked += 1

            # The length is reported and the value is not. This is the
            # number that would have caught the corruption, because the
            # vendor's console shows the length the key should be.
            rows = {row[0]: row for row in keys.audit(home)}
            row = rows.get("gate-decoy")
            if row is None:
                findings.append("the audit does not list the key it just "
                                "stored, so its length is not reportable.")
            elif row[2] != len(DECOY):
                findings.append(
                    "the audit reports length %r for a key of %d character(s)."
                    % (row[2], len(DECOY)))
            else:
                checked += 1

            secret, problems = keys.read("gate-decoy", home)
            findings.extend("reading it back: %s" % p for p in problems)
            if secret is None:
                return findings + ["the decoy could not be read back"], checked
            checked += 1
            if secret.value != DECOY:
                findings.append("the store handed back a different value")
            for label, rendered in (
                    ("str()", str(secret)), ("repr()", repr(secret)),
                    ("format()", "{}".format(secret)),
                    ("percent", "%s" % secret),
                    ("padded format", "{:>50}".format(secret))):
                checked += 1
                if DECOY in rendered:
                    findings.append("%s renders the key value" % label)
            checked += 1
            try:
                dumped = json.dumps(secret)
                findings.append(
                    "json.dumps() serialised a key (%s) instead of refusing "
                    "it. The refusal is what keeps a key out of a payload "
                    "written by code that never thought about keys." % dumped)
            except TypeError:
                pass
            checked += 1
            if DECOY in keys.redact("a line holding %s in the middle" % DECOY):
                findings.append("redact() left a known key value in place")
        finally:
            if previous is None:
                os.environ.pop("MURSCOPE_HOME", None)
            else:
                os.environ["MURSCOPE_HOME"] = previous
    return findings, checked


class _StubKeyring(object):
    """A keychain that is not the operating system's.

    **What this proves and what it does not.** It proves the wiring: that
    the keychain backend calls `set_password` and `get_password` with the
    service name and the key name, hands back a `Secret` rather than a
    string, and writes no file while doing it. It does not prove that the
    real `keyring` package behaves this way, and nothing here claims it
    does - a real exercise writes into the machine's own keychain and
    prompts its owner for a password, which is not something a gate may
    do to somebody who typed `python3 scripts/run_checks.py`.

    So the honest statement, which the summary line makes: the file
    backend is measured, the keychain backend's wiring is measured, and
    the keychain backend has never completed a round trip against a real
    system keychain. DP89's discipline, applied one milestone early.
    """

    def __init__(self):
        self.calls = []
        self.store = {}

    def set_password(self, service, name, value):
        self.calls.append(("set", service, name))
        self.store[(service, name)] = value

    def get_password(self, service, name):
        self.calls.append(("get", service, name))
        return self.store.get((service, name))


def live_keyring_findings():
    """The keychain backend, against a stub. Wiring only, and it says so."""
    import tempfile  # noqa: PLC0415 - only this half needs a throwaway home

    sys.path.insert(0, str(REPO_ROOT))
    try:
        from murscope import keys
    except Exception as exc:
        return ["the key store could not be imported (%s: %s)."
                % (type(exc).__name__, exc)], 0

    findings = []
    checked = 0
    stub = _StubKeyring()
    previous = sys.modules.get("keyring")
    sys.modules["keyring"] = stub
    try:
        with tempfile.TemporaryDirectory() as work:
            home = Path(work)
            where, problems = keys.store("gate-keychain", DECOY, home,
                                         backend="keyring")
            findings.extend("keychain store: %s" % p for p in problems)
            checked += 1
            if where is None:
                findings.append("the keychain backend stored nothing")
            elif keys.keys_dir(home).exists():
                findings.append(
                    "the keychain backend wrote a file under %s as well. The "
                    "point of choosing the keychain is that the value is not "
                    "in a file." % keys.keys_dir(home))
            secret, problems = keys.read("gate-keychain", home,
                                         backend="keyring")
            findings.extend("keychain read: %s" % p for p in problems)
            checked += 1
            if secret is None or secret.value != DECOY:
                findings.append("the keychain backend did not hand back what "
                                "it was given")
            elif DECOY in str(secret):
                findings.append("a keychain-backed key renders its value")
            checked += 1
            if not any(call[1] == keys.KEYRING_SERVICE for call in stub.calls):
                findings.append(
                    "the keychain backend never named a service, so nothing "
                    "establishes which keychain entry it would use")
    finally:
        if previous is None:
            sys.modules.pop("keyring", None)
        else:
            sys.modules["keyring"] = previous

    # And the refusal, which is the behaviour a user is most likely to
    # meet: the backend is configured and the package is not installed.
    # No silent fallback to a file - that is DP49's shape one layer down.
    sys.modules["keyring"] = None
    try:
        with tempfile.TemporaryDirectory() as work:
            where, problems = keys.store("gate-missing", DECOY, Path(work),
                                         backend="keyring")
            checked += 1
            if where is not None:
                findings.append(
                    "with no keyring package importable the backend stored "
                    "something anyway - which means it fell back to a file "
                    "and told the user nothing.")
            elif not problems:
                findings.append("the missing keychain was refused silently")
    finally:
        sys.modules.pop("keyring", None)
    return findings, checked


def real_keyring_findings(require):
    """The keychain backend against the **real** `keyring` package (DP99).

    DP99 recorded that the keychain's success path had never run against
    anything but a stub, and gave the reason: a genuine exercise writes
    into the machine's own keychain and prompts its owner for a password,
    which a gate may not do to somebody who typed one command. That reason
    is still right, and it turns out to rule out less than it looked like.

    `keyring` is a dispatcher. The platform keychain is one backend behind
    it, and `keyring.set_keyring()` replaces which one - so the real
    package can be driven end to end, with the real `set_password` and
    `get_password`, the real import path and the real exception types,
    while the value goes into a backend this check owns and the operating
    system is never asked for anything. What stays unproven afterwards is
    exactly one layer: the platform backend itself. That is named in the
    summary rather than left to be assumed, and the manual procedure for
    closing it is in CONTRIBUTING under Rule 18 - a human runs it and
    records the evidence, because it is the one thing a gate genuinely
    may not do.

    The stub half above is kept rather than replaced. It runs on every
    machine and proves the wiring; this runs where the extra is installed
    and proves the wiring was written against the real interface. With
    `--require-keyring` an absent package is a finding, which is how CI
    keeps this from becoming a path nobody is ever on (DP81's shape).
    """
    import tempfile  # noqa: PLC0415 - only this half needs a throwaway home

    try:
        import keyring  # noqa: PLC0415 - the extra, and only this path needs it
        from keyring.backend import KeyringBackend  # noqa: PLC0415
    except ImportError as exc:
        if require:
            return ["--require-keyring was given and the `keyring` package "
                    "is not importable (%s). This flag exists so the real "
                    "round trip is enforced somewhere rather than being a "
                    "branch that quietly stops running; CI installs "
                    "murscope[keyring] before passing it." % exc], 0, "absent"
        return [], 0, "absent"

    sys.path.insert(0, str(REPO_ROOT))
    from murscope import keys  # noqa: PLC0415

    class _OwnedByThisCheck(KeyringBackend):
        """A real `keyring` backend that is not the operating system's.

        Registered with `set_keyring()` before anything is stored, so the
        platform keychain is never initialised and nobody is prompted.
        """

        priority = 1

        def __init__(self):
            super(_OwnedByThisCheck, self).__init__()
            self.entries = {}
            self.calls = []

        def set_password(self, service, username, password):
            self.calls.append(("set", service, username))
            self.entries[(service, username)] = password

        def get_password(self, service, username):
            self.calls.append(("get", service, username))
            return self.entries.get((service, username))

        def delete_password(self, service, username):
            self.entries.pop((service, username), None)

    findings = []
    checked = 0
    backend = _OwnedByThisCheck()
    previous = None
    try:
        previous = keyring.get_keyring()
    except Exception:  # never initialised; nothing to put back
        previous = None
    keyring.set_keyring(backend)
    try:
        with tempfile.TemporaryDirectory() as work:
            home = Path(work)
            where, problems = keys.store("gate-real-keychain", DECOY, home,
                                         backend="keyring")
            findings.extend("real keychain store: %s" % p for p in problems)
            checked += 1
            if where is None:
                findings.append("the real `keyring` package stored nothing.")
            elif keys.keys_dir(home).exists():
                findings.append(
                    "a file was written under %s as well, so the value is on "
                    "disk after the user chose the keychain."
                    % keys.keys_dir(home))
            checked += 1
            if keyring.get_keyring() is not backend:
                findings.append(
                    "the value did not go through `keyring`'s own dispatch: "
                    "the registered backend is %r. Without that this measures "
                    "a stub with a longer import path."
                    % type(keyring.get_keyring()).__name__)
            checked += 1
            if backend.entries.get((keys.KEYRING_SERVICE,
                                    "gate-real-keychain")) != DECOY:
                findings.append(
                    "the real package holds nothing under service %r for this "
                    "key name, so `set_password` was not reached with the "
                    "arguments the backend claims to use."
                    % keys.KEYRING_SERVICE)
            secret, problems = keys.read("gate-real-keychain", home,
                                         backend="keyring")
            findings.extend("real keychain read: %s" % p for p in problems)
            checked += 1
            if secret is None or secret.value != DECOY:
                findings.append("the real round trip did not hand back what it "
                                "was given.")
            elif DECOY in str(secret) or DECOY in repr(secret):
                findings.append("a keychain-backed key renders its own value.")
            checked += 1
            missing, problems = keys.read("gate-real-absent", home,
                                          backend="keyring")
            if missing is not None:
                findings.append("a key that was never stored came back as a "
                                "secret.")
            if problems:
                findings.append("reading an absent key reported a problem "
                                "where the honest answer is 'not there': %s"
                                % "; ".join(problems))
    finally:
        if previous is not None:
            keyring.set_keyring(previous)
    return findings, checked, _installed_version("keyring")


def _installed_version(name):
    """The distribution's version, asked of the installed metadata.

    Not `module.__version__`: `keyring` 25 does not define one, and asking
    for it raises `AttributeError` - which is how a first reading of this
    concluded the package was not installed at all when it was.
    """
    try:
        from importlib import metadata  # noqa: PLC0415 - only this line needs it
        return metadata.version(name)
    except Exception:
        return "an unknown version"


def live_transport_findings():
    """Make the transport fail with a key in the URL, and read the traceback."""
    modules = transport_modules()
    if not modules:
        return ["no transport module was found under %s, so the failure path "
                "- the one surface where a key leaves inside somebody else's "
                "message - was never exercised. This check is red rather than "
                "green: it cannot answer its question without one."
                % EXTRAS_ROOT.relative_to(REPO_ROOT).as_posix()], 0

    findings = []
    exercised = 0
    for module in modules:
        rel = module.relative_to(REPO_ROOT).as_posix()
        result = subprocess.run(
            [sys.executable, "-c", PROBE, str(REPO_ROOT), str(module), DECOY],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        raw = result.stdout.decode("utf-8", errors="replace").strip()
        if not raw:
            findings.append(
                "%s: the probe printed nothing (%s). The failure path was not "
                "exercised and this check asserted nothing about it."
                % (rel, result.stderr.decode("utf-8", errors="replace")
                   .strip().splitlines()[-1:] or ["no output"]))
            continue
        try:
            report = json.loads(raw.splitlines()[-1])
        except ValueError as exc:
            findings.append("%s: the probe's report is unreadable (%s)."
                            % (rel, exc))
            continue
        if not report.get("loaded"):
            findings.append(
                "%s: could not be loaded (%s), so its failure path was never "
                "walked." % (rel, report.get("error", "no reason given")))
            continue
        if report.get("sockets"):
            findings.append(
                "%s: reached for the network (%s) while failing on a URL that "
                "cannot be parsed. Nothing should have got that far."
                % (rel, ", ".join(report["sockets"])))
        text = report.get("text") or ""
        if report.get("raised") in ("", "nothing"):
            findings.append(
                "%s: send() returned instead of raising on an unparseable "
                "URL, so no traceback was produced and the surface this "
                "check exists for was not examined." % rel)
            continue
        exercised += 1
        if DECOY in text:
            findings.append(
                "%s: the key in the URL appears in the traceback of the "
                "failed request. An exception traceback is an artifact - it "
                "is printed by `traceback.print_exc()`, by a caller's "
                "print(), and into every log file that catches this." % rel)
        if MASK not in text:
            findings.append(
                "%s: the traceback carries no mask, so redaction did not run "
                "and the absence above is an absence for the wrong reason."
                % rel)
    return findings, exercised


def main(argv=None):
    args = list(sys.argv[1:] if argv is None else argv)
    require = "--require-keyring" in args
    for arg in args:
        if arg != "--require-keyring":
            print("usage: keys_are_stored_0600_and_never_rendered.py "
                  "[--require-keyring]")
            return 2

    modules = guarded_modules()
    if not modules:
        print("FAILED: no key store and no provider module were found, so "
              "this check inspected nothing. It is red rather than green: an "
              "absence asserted over an empty set is not an assertion.")
        return 1

    bad = 0
    for path in modules:
        rel = path.relative_to(REPO_ROOT).as_posix()
        for finding in detect(path.read_bytes()):
            print("%s:%s" % (rel, finding))
            bad += 1

    store_findings, store_checked = live_store_findings()
    for finding in store_findings:
        print("live store: %s" % finding)
        bad += 1

    keyring_findings, keyring_checked = live_keyring_findings()
    for finding in keyring_findings:
        print("live keychain: %s" % finding)
        bad += 1

    real_findings, real_checked, real_version = real_keyring_findings(require)
    for finding in real_findings:
        print("real keychain: %s" % finding)
        bad += 1

    transport_findings, transport_exercised = live_transport_findings()
    for finding in transport_findings:
        print("live transport: %s" % finding)
        bad += 1

    if bad:
        print("\nFAILED: %d way(s) in which a key could reach something that "
              "is not the file it lives in." % bad)
        return 1
    print("OK: %d module(s) that hold or transmit a secret carry no unmasked "
          "render, no unmoded key write, and no `except` that re-raises with "
          "its context or hands the caught exception to anything but "
          "redaction. Live: a decoy stored at 0600 in a 0700 directory, %d "
          "assertion(s) against the real store - str, repr, two formats and "
          "json.dumps all refused it - and %d transport(s) made to fail on a "
          "URL carrying the decoy, each raising a masked error whose full "
          "traceback holds the mask and not the key, with no socket reached "
          "for." % (len(modules), store_checked, transport_exercised))
    print("    The keychain backend is measured against a stub, %d "
          "assertion(s): it names a service, hands back a Secret, writes no "
          "file, and refuses rather than falling back to one when the "
          "`keyring` package is missing."
          % keyring_checked)
    if real_version == "absent":
        print("    The **real** `keyring` package is not importable here, so "
              "the round trip through it did not run on this machine. It is "
              "not optional: CI installs murscope[keyring] and passes "
              "--require-keyring, which turns this line red rather than "
              "letting the stronger path become one nobody is ever on "
              "(DP150). Install it with `pip install 'murscope[keyring]'` to "
              "run it here.")
    else:
        print("    The **real** `keyring` package (%s) was driven end to end, "
              "%d assertion(s): a backend this check owns is registered with "
              "`keyring.set_keyring()`, the value goes in through the real "
              "`set_password` under service %r, comes back through the real "
              "`get_password` as a Secret that refuses to render itself, an "
              "absent key comes back as absent rather than as a problem, and "
              "no file is written. DP99's reason for the stub was that a gate "
              "may not write into the machine's own keychain and prompt its "
              "owner - true, and it rules out one layer rather than the whole "
              "path: `keyring` is a dispatcher, and only the platform backend "
              "behind it is out of reach (DP150)."
              % (real_version, real_checked, "murscope"))
    print("    **What is still unproven, stated rather than assumed (DP89):** "
          "no operating system keychain has ever been written to or read from "
          "by this code. That cannot become a gate's job, so it is not "
          "scheduled - CONTRIBUTING's Rule 18 carries the manual procedure "
          "and the place its evidence is recorded, and until somebody runs it "
          "the platform backend is untested and says so.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
