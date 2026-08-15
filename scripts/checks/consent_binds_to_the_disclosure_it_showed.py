"""Rule 19: consent binds to the disclosure it showed.

A boolean consent goes wrong in one specific, quiet way: **the payload
grows, and the old agreement silently covers the new, larger one.** The
user is never asked again, nothing goes red, and an answer given about
eleven fields is applied to twelve. Every part of that is invisible from
outside, which is why it needs a check rather than a comment.

So a consent is recorded against a fingerprint of the disclosure it was
granted for - the ordered table **as the user read it, path and sentence
together** - the provider, and the destination, and this rule holds the
properties that make it real.

**The sentence is in the digest, and it was not.** M3's fourth stage found
the fingerprint covering the paths alone, which is the shape this whole
file exists to refuse wearing different clothes: `projects[].id` described
as "the id you gave the project" and `projects[].id` described as "the
directory name the scan set, unless you changed it" declare the same path
and two different things leaving the machine, and the second inherited
every consent recorded against the first. The live half below rewrites one
sentence and asserts the grant stops covering the request.

**The static half** reads `murscope/consent.py`, `murscope/outbound.py`
and every provider module in the `extras/` distributions:

1. **the fingerprint uses everything it was given.** A `fingerprint()`
   that ignores its `destination` argument would make one consent cover
   every endpoint, and would still be a fingerprint.
2. **the payload is checked against the table it was disclosed from.**
   `build()` has to compare what it produced against the declared fields
   and raise, or the fingerprint is a promise about a document rather
   than about what leaves (DP87: the guard has to contain the thing it
   watches).
3. **the transport type-tests its consent.** Without an `isinstance`
   against the grant class, `consent=True` and `consent="yes"` are
   consents.
4. **the refusal comes before the wire.** The first `urllib` call in
   `send()` must sit *below* the consent check, measured by line number
   from the parse tree. A refusal that runs after the request has been
   built is a refusal that arrives late.
5. **the route is the destination that was disclosed.**
   `urllib.request.urlopen` reads `https_proxy` from the environment, so a
   transport that calls it sends the payload through a machine the consent
   screen never named while that screen said the vendor's host. DP90
   refused "localhost is not the network"; "a proxy is not a destination"
   is the same sentence. A transport must open through an opener it built
   with `ProxyHandler({})`, and this was found on a machine that has a
   proxy set - it is not hypothetical. **The proxy map is looked for in
   the functions `send()` can reach, not in the module it lives in
   (DP121)**: the first version asked the whole parse tree, so six
   openers changed to a bare `build_opener()` plus one never-called
   function per module holding a proxy map left this rule green while the
   opener that runs read `https_proxy`.

**The live half** is where the teeth are, and it runs the real modules:

* a grant recorded against today's disclosure covers today's request -
  the positive case, without which every refusal below is satisfied by a
  binding that refuses everything;
* one added field, and the same grant stops covering it, naming the
  field;
* **one field described differently**, every path unchanged, and it stops
  covering it, naming that field. A path-only digest passes this case
  silently, which is why it is asserted rather than left to follow from
  the one above;
* the same disclosure to another destination, and it stops covering it
  (DP90: where the data goes is part of what was disclosed);
* nothing recorded covers nothing;
* **the declared payload rows and the built payload are the same set**, in
  both directions. A field emitted and not declared is a field nobody was
  shown; a field declared and not emitted is a disclosure that overstates
  what leaves. The comparison is against the `PAYLOAD` rows because the
  rest of the table describes what the transport wraps around the body -
  a credential in a header, the vendor's envelope - and those leave
  without being leaves of this document;
* **the scope column cannot hide a field.** Moving a real payload row to
  request scope would take it off both sides of the comparison above, so
  the check does it and asserts `build()` refuses to send the result;
  a payload leaf no row declares is a stray, whatever the reason;
* **the transport refuses every non-grant** - `True`, `1`, `"yes"`, the
  old sentinel string, `None` - and a grant recorded for a wider
  disclosure, each in a subprocess under an audit hook that refuses
  socket events, so "before a socket is opened" is measured rather than
  read off the source.

**Every transport, not the first one to ship (DP103).** The probe used to
hard-code the provider name `network` and `outbound.fields()`, which was
right for exactly as long as there was one transport in `extras/`. A
second arrived at M3's third stage with its own name and its own, shorter
disclosure - and a probe that hands every module the first module's grant
is not testing the others, it is failing them. So a transport declares
`PROVIDER` and `consent_fields()`, and the probe builds each module's
grant from that module's own declaration.

**What walks into each finding (DP87).** The static shapes ship as cases
in this check's own fixture. The live half asserts a positive case beside
every refusal, and asserts that the correct grant gets *past* the consent
gate - proved by the transport then failing on the transport's own
terms - so a transport that refused everything would go red here rather
than passing five refusals. **If the transport module cannot be loaded
this check is red, not green**, for the same reason Rule 13b is red
without a build backend.

Fails when: fingerprint() ignores a parameter; build() does not check its
result against the declared fields; the transport does not type-test its
consent, touches urllib before checking it, calls urlopen() directly, or
opens a request without building a ProxyHandler; a recorded consent does
not cover the request it was recorded for; a consent survives a field
being added to the disclosure, a field's sentence being rewritten, or the
destination changing; an unrecorded
consent covers anything; the declared payload rows and the built payload
differ in either direction; the disclosure has no payload rows or no
request rows; a payload field moved to request scope is still sent;
the transport accepts a non-grant or a stale grant;
the transport opens a socket while refusing; or the transport cannot be
loaded at all.
"""
from __future__ import annotations

import ast
import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
CONSENT = REPO_ROOT / "murscope" / "consent.py"
OUTBOUND = REPO_ROOT / "murscope" / "outbound.py"
EXTRAS_ROOT = REPO_ROOT / "extras"

GRANT_CLASS = "Grant"
FINGERPRINT = "fingerprint"
BUILDER = "build"
SENDER = "send"
DECLARED = ("DISCLOSURE", "fields")
URLLIB_CALLS = ("Request", "urlopen")

# What a transport must build so that the route is a decision rather than
# whatever the environment decided. See the branch in `detect()`.
PROXY_HANDLER = "ProxyHandler"

# Values that are not a consent and have been mistaken for one. The old
# sentinel is in the list on purpose: stage one's `send()` took a magic
# string, and a transport that still accepted it would be accepting a
# consent that says nothing about what is being sent.
NOT_CONSENTS = ("True", "1", "'yes'", "'murscope-consent-recorded'", "None")

PROBE = r'''
import importlib.util, json, sys

REPO, MODULE = sys.argv[1], sys.argv[2]
sys.path.insert(0, REPO)
report = {"loaded": False, "refused": {}, "accepted": "", "sockets": [],
          "reached_wire_when_accepted": False}
phase = ["refusing"]

EVENTS = ("socket.connect", "socket.getaddrinfo", "socket.gethostbyname",
          "socket.sendto", "socket.bind", "urllib.Request")

def hook(event, args):
    # Recorded per phase, because the two phases want opposite answers. A
    # refusal that reaches the wire is the finding; the accepted case
    # reaching the wire is the *proof* that it got past the gate, and a
    # single list would have reported the second as the first.
    if event in EVENTS:
        if phase[0] == "refusing":
            report["sockets"].append(event)
        else:
            report["reached_wire_when_accepted"] = True
        raise RuntimeError("a socket was reached for")

try:
    from murscope import consent, keys, outbound
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

# Which consent this particular transport requires, asked rather than
# assumed. Hard-coding "network" and outbound.fields() tested one
# transport and would have *failed* the second one to ship - a probe that
# hands every module the first module's grant is not testing the others.
provider = getattr(network, "PROVIDER", "network")
declared = getattr(network, "consent_fields", None)
fields = tuple(declared()) if callable(declared) else outbound.fields()
report["provider"] = provider
report["field_count"] = len(fields)

url = "nonsense://example.invalid/v1"
destination = consent.destination_of(url)
good = consent.Grant(provider, destination,
                     consent.fingerprint(fields, provider, destination),
                     fields, "now")
widened = tuple(fields) + ("an.added.field",)
stale = consent.Grant(provider, destination,
                      consent.fingerprint(widened, provider, destination),
                      widened, "now")

sys.addaudithook(hook)
candidates = [("True", True), ("1", 1), ("'yes'", "yes"),
              ("'murscope-consent-recorded'", "murscope-consent-recorded"),
              ("None", None), ("a grant for a wider disclosure", stale)]
for label, value in candidates:
    try:
        network.send(url, b"{}", consent=value)
        report["refused"][label] = "accepted"
    except BaseException as exc:
        report["refused"][label] = type(exc).__name__

# The positive case. A correct grant has to get *past* the consent gate,
# or every refusal above is satisfied by a transport that refuses
# everything. Past the gate it fails on the transport's own terms - the
# scheme is one urllib cannot open - which is a different exception.
phase[0] = "accepting"
try:
    network.send(url, b"{}", consent=good)
    report["accepted"] = "returned"
except keys.Masked as exc:
    report["accepted"] = "Masked"
except BaseException as exc:
    report["accepted"] = type(exc).__name__
print(json.dumps(report))
'''


def _callee(call):
    if not isinstance(call, ast.Call):
        return None
    return getattr(call.func, "id", None) or getattr(call.func, "attr", None)


def _functions(tree):
    return {node.name: node for node in ast.walk(tree)
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))}


def _reachable(tree, start):
    """The functions `start` can actually run, by name, `start` included.

    **DP121: the criterion was a module, and the proposition is a call.**
    The route assertion below used to ask `ast.walk(tree)` whether anyone
    anywhere in the file called `ProxyHandler` - which answers "does this
    module contain a proxy map", not "does the opener that `send()` uses
    build one". With all six openers changed to a bare `build_opener()` and a
    never-called function appended to each module carrying one
    `build_opener(ProxyHandler({}))`, this rule and Rule 25 both went
    green while the live opener read `https_proxy`. That takes somebody
    deliberately adding code that never runs; it is not a slip anyone
    makes editing an opener, and the ordinary regression - break the
    opener, add nothing - was caught then and is caught now. Recorded at
    that size, and closed anyway because the closure costs a call graph.

    One level would be enough for the shape that ships (`send()` calls
    `_opener()`). This walks the whole module-local call graph instead, so
    an opener obtained through a helper is still reached rather than
    reported red for being one hop further away.
    """
    functions = _functions(tree)
    seen, queue = set(), [start]
    while queue:
        name = queue.pop()
        if name in seen or name not in functions:
            continue
        seen.add(name)
        for sub in ast.walk(functions[name]):
            callee = _callee(sub)
            if callee in functions and callee not in seen:
                queue.append(callee)
    return [functions[name] for name in sorted(seen)]


def detect(payload):
    """Findings for a consent, disclosure or transport module."""
    source = payload.decode("utf-8", errors="replace")
    try:
        tree = ast.parse(source)
    except SyntaxError as exc:
        return ["cannot parse (%s)." % exc]

    findings = []
    functions = _functions(tree)

    node = functions.get(FINGERPRINT)
    if node is not None:
        used = set(sub.id for sub in ast.walk(node)
                   if isinstance(sub, ast.Name))
        for arg in node.args.args:
            if arg.arg not in used:
                findings.append(
                    "%d: %s() never uses its %r argument, so it fingerprints "
                    "less than it was given - and one consent would cover "
                    "every value of it."
                    % (node.lineno, FINGERPRINT, arg.arg))

    node = functions.get(BUILDER)
    if node is not None:
        names = set()
        for sub in ast.walk(node):
            if isinstance(sub, ast.Name):
                names.add(sub.id)
            elif isinstance(sub, ast.Call):
                names.add(_callee(sub) or "")
        raises = any(isinstance(sub, ast.Raise) for sub in ast.walk(node))
        if not (names & set(DECLARED)) or not raises:
            findings.append(
                "%d: %s() does not check what it produced against %s and "
                "raise. Without that the fingerprint is a promise about a "
                "document rather than about what leaves, and the two drift "
                "the first time a key is added to the payload."
                % (node.lineno, BUILDER, " or ".join(DECLARED)))

    node = functions.get(SENDER)
    if node is not None:
        checks = [sub.lineno for sub in ast.walk(node)
                  if isinstance(sub, ast.Call)
                  and _callee(sub) in ("check_consent", "require", "matches")]
        wire = [sub.lineno for sub in ast.walk(node)
                if isinstance(sub, ast.Call) and _callee(sub) in URLLIB_CALLS]
        if not checks:
            findings.append(
                "%d: %s() reaches the wire without checking a consent at all."
                % (node.lineno, SENDER))
        elif wire and min(wire) < min(checks):
            findings.append(
                "%d: %s() touches urllib at line %d, above its consent check "
                "at line %d. A refusal that runs after the request has been "
                "built is a refusal that arrives late."
                % (node.lineno, SENDER, min(wire), min(checks)))

        # **The route is part of the destination.** `urlopen` reads
        # `https_proxy` from the environment, so a transport that calls it
        # sends the payload through a machine the consent screen never
        # named - while that screen said "destination: <the vendor>" and
        # meant something else. DP90 refused "localhost is not the
        # network"; "a proxy is not a destination" is the same sentence,
        # and it was found on a machine that has one set.
        #
        # **Scoped to what `send()` can reach, not to the file it sits
        # in (DP121).** `ast.walk(tree)` answered "is there a proxy map
        # somewhere in this module", and a never-called function holding
        # one satisfied that while the live opener read `https_proxy`.
        bare = [sub.lineno for sub in ast.walk(node)
                if isinstance(sub, ast.Call) and _callee(sub) == "urlopen"]
        routed = any(_callee(sub) == PROXY_HANDLER
                     for fn in _reachable(tree, SENDER)
                     for sub in ast.walk(fn))
        if bare:
            findings.append(
                "%d: %s() calls urlopen(), which reads https_proxy from the "
                "environment. The payload would then pass through a machine "
                "the disclosure never named, and the consent screen would "
                "have said the vendor's host and meant something else. Open "
                "through an opener built with %s({})."
                % (min(bare), SENDER, PROXY_HANDLER))
        elif not routed:
            findings.append(
                "%d: %s() opens a request and nothing it can reach builds a "
                "%s, so the route it takes is whatever the environment "
                "decided. A destination that is in the fingerprint has to be "
                "the destination the request actually reaches. A %s built in "
                "a function %s() never calls answers for nothing (DP121)."
                % (node.lineno, SENDER, PROXY_HANDLER, PROXY_HANDLER, SENDER))

    if functions.get(SENDER) is not None or "check_consent" in functions:
        tested = any(
            isinstance(sub, ast.Call) and _callee(sub) == "isinstance"
            and any(GRANT_CLASS == getattr(inner, "attr", None)
                    or GRANT_CLASS == getattr(inner, "id", None)
                    for arg in sub.args for inner in ast.walk(arg))
            for sub in ast.walk(tree))
        if not tested:
            findings.append(
                "this module sends and never tests its consent against %s. "
                "Without that test `consent=True`, `consent=1` and "
                "`consent='yes'` are all consents, and none of them says "
                "anything about what is being sent." % GRANT_CLASS)
    return findings


def transport_modules():
    if not EXTRAS_ROOT.is_dir():
        return []
    return sorted(path for path in EXTRAS_ROOT.glob("*/murscope/providers/*.py")
                  if path.name != "__init__.py")


def live_binding_findings():
    """Record, require, widen, move. The real modules, in a real home."""
    import os  # noqa: PLC0415 - only this half touches the environment
    import tempfile  # noqa: PLC0415 - same

    sys.path.insert(0, str(REPO_ROOT))
    try:
        from murscope import consent, disclosure, outbound
    except Exception as exc:
        return ["the consent layer could not be imported (%s: %s), so nothing "
                "was exercised." % (type(exc).__name__, exc)], 0

    findings = []
    checked = 0
    # The rows as the user read them - path *and* sentence. A digest over
    # the paths alone let a field keep its name and change its meaning,
    # which is what happened to `projects[].id`: "the id you gave the
    # project" and "the directory name the scan set" are the same path and
    # two different disclosures, and every consent recorded against the
    # first silently covered the second.
    shown = outbound.shown()
    widened = tuple(shown) + (("projects[].last_subject", "the subject line "
                               "of its most recent commit"),)
    # Same paths, one sentence rewritten. This case is the one a path-only
    # fingerprint could not see at all, so it is asserted rather than
    # assumed to follow from the case above.
    reworded = tuple((path, ("something else entirely" if path == "projects[].id"
                             else what)) for path, what in shown)
    provider, destination = "gate", "https://example.invalid"

    with tempfile.TemporaryDirectory() as work:
        previous = os.environ.get("MURSCOPE_HOME")
        os.environ["MURSCOPE_HOME"] = work
        try:
            home = Path(work)
            try:
                consent.require(provider, destination, shown, home)
                findings.append("an unrecorded consent was accepted")
            except consent.ConsentRequired:
                checked += 1

            consent.record(provider, destination, shown, home)
            try:
                consent.require(provider, destination, shown, home)
                checked += 1
            except Exception as exc:
                findings.append(
                    "a consent recorded a moment ago did not cover the request "
                    "it was recorded for (%s: %s). A binding that refuses "
                    "everything passes every refusal below."
                    % (type(exc).__name__, exc))

            try:
                consent.require(provider, destination, widened, home)
                findings.append(
                    "a consent recorded against %d field(s) was accepted for "
                    "a disclosure of %d. This is the rule: the user agreed to "
                    "what they were shown." % (len(shown), len(widened)))
            except consent.ConsentStale as exc:
                checked += 1
                if "last_subject" not in str(exc):
                    findings.append("the refusal does not name the field that "
                                    "was added: %s" % exc)

            # The same fields, one of them described as something else.
            try:
                consent.require(provider, destination, reworded, home)
                findings.append(
                    "a consent recorded against one wording was accepted for "
                    "another: `projects[].id` was rewritten and the grant "
                    "carried over. That is the hole this rule is named after "
                    "- the paths matched and the disclosure did not.")
            except consent.ConsentStale as exc:
                checked += 1
                if "projects[].id" not in str(exc):
                    findings.append(
                        "the refusal does not name the field whose sentence "
                        "changed, so a user is sent to diff two tables: %s"
                        % exc)

            try:
                consent.require(provider, "https://elsewhere.invalid", shown,
                                home)
                findings.append("a consent recorded for one destination was "
                                "accepted for another (DP90)")
            except consent.ConsentStale:
                checked += 1
        finally:
            if previous is None:
                os.environ.pop("MURSCOPE_HOME", None)
            else:
                os.environ["MURSCOPE_HOME"] = previous

    # The table and the payload, in both directions. Two records, one of
    # them sensitive, so the withheld count and a project row are both
    # produced - a payload built from nothing would declare nothing and
    # agree with an empty table.
    records = [
        {"id": "kept", "tier": "ACTIVE", "recency_days": 1.0,
         "state": {"kind": "inferred"},
         "signals": {"uncommitted": {"quality": "ok", "files": 2},
                     "unpushed": {"quality": "ok", "commits": 1},
                     "stash": {"quality": "ok", "entries": 1},
                     "last_commit": {"quality": "ok", "wip": True}}},
        {"id": "withheld", "sensitive": True, "tier": "COLD",
         "state": {"kind": "inferred"}, "signals": {}},
    ]
    # Only the rows that describe the body murscope builds. The rest of the
    # table describes what the transport puts around it - a credential in a
    # header, the user agent, the vendor's own envelope - and comparing
    # those against the payload would report every one of them as a
    # disclosure that overstates what leaves, which is the opposite of true:
    # they leave, they were simply not in this document.
    declared = set(disclosure.payload_paths(outbound.DISCLOSURE))
    requested = [path for path, scope, _kind, _what in outbound.DISCLOSURE
                 if scope == disclosure.REQUEST]
    if not declared or not requested:
        findings.append(
            "the disclosure has %d payload row(s) and %d request row(s). Both "
            "halves have to exist or this assertion is being made against an "
            "empty set: a table with no request rows would prove nothing "
            "about the split, and one with no payload rows would agree with "
            "any payload at all." % (len(declared), len(requested)))
    try:
        payload = outbound.build(records)
        produced = outbound._leaf_paths(payload)
        checked += 1
        for path in sorted(produced - declared):
            findings.append(
                "the payload carries %r and the disclosure does not declare "
                "it: a field nobody was shown." % path)
        for path in sorted(declared - produced):
            findings.append(
                "the disclosure declares %r and the payload does not carry "
                "it: the user is being shown more than leaves." % path)
        if payload.get("withheld_sensitive") != 1 or len(payload["projects"]) != 1:
            findings.append(
                "the payload kept %d project(s) and withheld %r from two "
                "records, one of them sensitive - so neither branch of the "
                "builder was exercised the way this case intends."
                % (len(payload["projects"]), payload.get("withheld_sensitive")))
    except Exception as exc:
        findings.append("the payload could not be built (%s: %s)"
                        % (type(exc).__name__, exc))

    # **The scope column must not be a way to hide a field.** Everything
    # above compares the payload with the `PAYLOAD` rows, so moving a real
    # payload field to `REQUEST` would remove it from both sides of that
    # comparison and the check would stay green while the user stopped
    # being shown it. What stops that is `build()` itself: a leaf that is
    # not a payload row is a stray and nothing is sent. Asserted here by
    # doing it, because DP87 is specific - a guard has to contain the thing
    # it is written to watch.
    original = outbound.DISCLOSURE
    hidden = tuple((path, disclosure.REQUEST if path == "projects[].id" else
                    scope, kind, what)
                   for path, scope, kind, what in original)
    try:
        outbound.DISCLOSURE = hidden
        try:
            outbound.build(records)
            findings.append(
                "a payload field moved to request scope was still sent. The "
                "scope column would then be a way to take a field off the "
                "screen without taking it out of the request.")
        except outbound.DisclosureMismatch as exc:
            checked += 1
            if "projects[].id" not in str(exc):
                findings.append("the refusal does not name the field that "
                                "stopped being declared: %s" % exc)
    finally:
        outbound.DISCLOSURE = original
    return findings, checked


def live_transport_findings():
    """Hand the transport five non-consents and one stale grant."""
    modules = transport_modules()
    if not modules:
        return ["no transport module was found under %s, so nothing was asked "
                "to refuse anything. This check is red rather than green."
                % EXTRAS_ROOT.relative_to(REPO_ROOT).as_posix()], 0

    findings = []
    refusals = 0
    for module in modules:
        rel = module.relative_to(REPO_ROOT).as_posix()
        result = subprocess.run(
            [sys.executable, "-c", PROBE, str(REPO_ROOT), str(module)],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        raw = result.stdout.decode("utf-8", errors="replace").strip()
        if not raw:
            findings.append("%s: the probe printed nothing (%s)."
                            % (rel, result.stderr.decode(
                                "utf-8", errors="replace").strip()[-300:]))
            continue
        try:
            report = json.loads(raw.splitlines()[-1])
        except ValueError as exc:
            findings.append("%s: unreadable report (%s)." % (rel, exc))
            continue
        if not report.get("loaded"):
            findings.append("%s: could not be loaded (%s)."
                            % (rel, report.get("error", "no reason given")))
            continue
        if report.get("sockets"):
            findings.append(
                "%s: reached for the network (%s) while refusing a consent. "
                "The refusal has to happen before the wire, not beside it."
                % (rel, ", ".join(report["sockets"])))
        for label, outcome in sorted(report.get("refused", {}).items()):
            if outcome == "accepted":
                findings.append(
                    "%s: accepted %s as a consent. It is not one - it records "
                    "no field list, no destination and no act." % (rel, label))
            else:
                refusals += 1
        accepted = report.get("accepted")
        if accepted in ("", "TransportRefused"):
            findings.append(
                "%s: a grant recorded against today's disclosure was refused "
                "as well (%s). A transport that refuses everything satisfies "
                "every refusal above and sends nothing anybody consented to."
                % (rel, accepted or "no result"))
        elif not report.get("reached_wire_when_accepted"):
            # The positive case has to get *past* the gate, and the only
            # evidence of that is the wire being reached. Without this the
            # case would be satisfied by a transport that failed early for
            # some entirely different reason.
            findings.append(
                "%s: the current grant did not reach the wire (%s), so "
                "nothing establishes that it got past the consent gate "
                "rather than falling over before it." % (rel, accepted))
    return findings, refusals


def main():
    sources = [path for path in (CONSENT, OUTBOUND) if path.exists()]
    sources.extend(transport_modules())
    if not sources:
        print("FAILED: no consent, disclosure or transport module was found, "
              "so this check inspected nothing.")
        return 1

    bad = 0
    for path in sources:
        rel = path.relative_to(REPO_ROOT).as_posix()
        for finding in detect(path.read_bytes()):
            print("%s: %s" % (rel, finding))
            bad += 1

    binding, checked = live_binding_findings()
    for finding in binding:
        print("live binding: %s" % finding)
        bad += 1

    transport, refusals = live_transport_findings()
    for finding in transport:
        print("live transport: %s" % finding)
        bad += 1

    if bad:
        print("\nFAILED: %d way(s) in which a consent could cover something it "
              "never disclosed." % bad)
        return 1
    from murscope import outbound  # noqa: PLC0415 - for the count only
    print("OK: %d module(s) inspected; the fingerprint uses every argument it "
          "takes, the builder checks its result against the declared table and "
          "raises, and the transport type-tests its consent above its first "
          "urllib call. Live: %d binding assertion(s) - an unrecorded consent "
          "covers nothing, a recorded one covers its own request, and it stops "
          "covering it when a field is added or the destination changes - the "
          "%d declared field(s) and the built payload are the same set in both "
          "directions, and the transport refused %d non-consent(s) without "
          "reaching for a socket while still accepting a current grant."
          % (len(sources), checked, len(outbound.fields()), refusals))
    return 0


if __name__ == "__main__":
    sys.exit(main())
