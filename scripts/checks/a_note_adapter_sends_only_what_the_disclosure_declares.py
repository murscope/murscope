"""Rule 22: a note adapter sends only what the disclosure declares.

`outbound.DISCLOSURE` is the document a consent is fingerprinted over, and
`outbound.build()` already refuses a payload leaf the table does not
declare. That covers the body murscope builds. **It does not cover what an
adapter wraps around it**, and the wrapper is a request the user is
equally entitled to have been told about: a vendor envelope is where a
`user` identifier, a session id or a system prompt nobody read would go,
and none of them would ever reach `build()`.

So the table has a row for the envelope, and this rule holds the adapters
to it. What `request.envelope` says the wrapper contains is:

> the model name you put in config.toml, the role labels and length limit
> its API requires, and a flag asking for one complete answer rather than
> a stream. Nothing of yours is in it

`ENVELOPE_VOCABULARY` below is that sentence as a set. An adapter that
puts a key in its body which is not in it is sending something the user
was not shown, and it goes red here rather than at the point somebody
reads a vendor's access log.

**Both directions, because each has a degenerate form.** An adapter that
declares five envelope keys and sends three is describing a request it
does not make; an adapter that declares three and sends five is making a
request it does not describe. And the payload has to actually be in the
body: an adapter that declared nothing and sent nothing would satisfy
every subset assertion here perfectly.

**What walks into this (DP87).** The live half builds a real payload
carrying a **decoy project id**, calls each adapter's own `body()`, and
asserts three things about the result: the decoy is in it, it appears
exactly where `outbound.canonical()` put it, and it appears nowhere else.
Without the first of those, "no key outside the vocabulary" would be
equally true of an adapter that sends an empty document - which is to say
the check would be green and the feature absent.

**No socket is opened here.** `body()` is a pure function by design, which
is why it is a named function in each adapter rather than an expression
inside `write()`: a request shape that can only be inspected by making the
request is a request shape nothing can check. The transports themselves
are Rules 18 and 19's; the live round trips are the acceptance report's.

Fails when: an adapter that registers a note writer declares no
`ENVELOPE_KEYS`; its declared keys and the keys its `body()` actually
emits differ in either direction; it emits or declares a key outside the
vocabulary the disclosure describes; the canonical payload is not in the
body exactly once; a decoy planted in the payload appears anywhere in the
body outside that content; `body()` is missing or cannot be called; or no
adapter could be loaded at all.
"""
from __future__ import annotations

import ast
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
EXTRAS_ROOT = REPO_ROOT / "extras"

DECLARATION = "ENVELOPE_KEYS"
BUILDER = "body"

# `request.envelope`, as a set. Every word of it maps to one entry:
# "the model name you put in config.toml"        -> model
# "the role labels ... its API requires"         -> messages
# "and length limit"                             -> max_tokens
# "a flag asking for one complete answer"        -> stream
#
# A new adapter that needs a fifth key needs a fifth clause in that
# sentence, and adding one invalidates every recorded consent - which is
# the cost of widening a request, charged where it is incurred.
ENVELOPE_VOCABULARY = ("model", "messages", "stream", "max_tokens")

# Obviously fabricated. A decoy shaped like a real project name would be
# indistinguishable from one in the body it is looked for in.
DECOY = "murscope-decoy-project-id-0000"


def _assigned(tree, name):
    """The literal assigned to `name` at module scope, or None."""
    for node in tree.body:
        if not isinstance(node, ast.Assign):
            continue
        for target in node.targets:
            if isinstance(target, ast.Name) and target.id == name:
                try:
                    return ast.literal_eval(node.value)
                except (ValueError, SyntaxError):
                    return None
    return None


def _registers_writer(tree):
    """Does this module register itself as something that writes a note?"""
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        callee = getattr(node.func, "id", None) or getattr(node.func, "attr",
                                                           None)
        if callee != "register":
            continue
        for keyword in node.keywords:
            if keyword.arg == "writes":
                return True
    return False


def detect(payload):
    """Findings about one adapter's source. Pure, so Rule 1 can feed it."""
    findings = []
    try:
        tree = ast.parse(payload)
    except SyntaxError as exc:
        return ["cannot be parsed (%s)" % exc]
    if not _registers_writer(tree):
        return []

    declared = _assigned(tree, DECLARATION)
    if not declared:
        findings.append(
            "registers a note writer and declares no %s. The envelope it "
            "wraps around the payload is then undescribed, and an undescribed "
            "wrapper is where a `user` identifier or a system prompt nobody "
            "read would sit." % DECLARATION)
        declared = ()
    for key in sorted(set(declared) - set(ENVELOPE_VOCABULARY)):
        findings.append(
            "declares envelope key %r, which the disclosure's "
            "`request.envelope` row does not describe. Sending it means "
            "sending something nobody was shown; describing it means one "
            "more clause in that sentence, and a re-consent." % key)

    functions = {node.name for node in ast.walk(tree)
                 if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))}
    if BUILDER not in functions:
        findings.append(
            "registers a note writer and has no %s(). A request shape that "
            "can only be inspected by making the request is a request shape "
            "nothing can check." % BUILDER)
    return findings


def adapter_modules():
    """Provider modules in the extras distributions that write a note."""
    if not EXTRAS_ROOT.is_dir():
        return []
    found = []
    for path in sorted(EXTRAS_ROOT.glob("*/murscope/providers/*.py")):
        if path.name == "__init__.py":
            continue
        try:
            tree = ast.parse(path.read_bytes())
        except SyntaxError:
            found.append(path)
            continue
        if _registers_writer(tree):
            found.append(path)
    return found


def _string_leaves(value):
    """Every string in a decoded JSON document, at any depth."""
    if isinstance(value, str):
        return [value]
    found = []
    if isinstance(value, dict):
        for key in value:
            found.extend(_string_leaves(value[key]))
    elif isinstance(value, (list, tuple)):
        for item in value:
            found.extend(_string_leaves(item))
    return found


def live_findings(modules):
    """Call each adapter's own body() on a real payload. Returns (findings, n)."""
    import importlib.util  # noqa: PLC0415 - only this half loads by path

    sys.path.insert(0, str(REPO_ROOT))
    try:
        from murscope import outbound, registry
    except Exception as exc:
        return ["the payload builder could not be imported (%s: %s), so no "
                "adapter was driven." % (type(exc).__name__, exc)], 0

    findings = []
    checked = 0

    # A payload with a project in it, and the project carries the decoy.
    # An empty payload would satisfy every containment assertion below by
    # having nothing to contain.
    payload = outbound.build([
        {"id": DECOY, "tier": "ACTIVE", "recency_days": 1.0,
         "state": {"kind": "inferred"},
         "signals": {"uncommitted": {"quality": "ok", "files": 2},
                     "unpushed": {"quality": "ok", "commits": 1},
                     "stash": {"quality": "ok", "entries": 1},
                     "last_commit": {"quality": "ok", "wip": True}}}])
    content = outbound.canonical(payload).decode("utf-8")
    if DECOY not in content:
        return ["the decoy never reached the payload, so every assertion "
                "below would have been made about a document that does not "
                "carry a project at all."], 0

    for path in modules:
        rel = path.relative_to(REPO_ROOT).as_posix()
        registry.reset()
        spec = importlib.util.spec_from_file_location(
            "murscope.providers._gate_%s" % path.stem, path)
        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module
        try:
            spec.loader.exec_module(module)
        except Exception as exc:
            findings.append("%s: could not be loaded (%s: %s), so its request "
                            "shape was never inspected."
                            % (rel, type(exc).__name__, exc))
            continue

        declared = set(getattr(module, DECLARATION, ()) or ())
        builder = getattr(module, BUILDER, None)
        if not callable(builder):
            findings.append("%s: has no callable %s()." % (rel, BUILDER))
            continue
        try:
            raw = builder(payload, "a-model")
            document = json.loads(raw.decode("utf-8"))
        except Exception as exc:
            findings.append("%s: %s() did not produce a readable body (%s: %s)"
                            % (rel, BUILDER, type(exc).__name__, exc))
            continue
        checked += 1

        emitted = set(document)
        for key in sorted(emitted - declared):
            findings.append(
                "%s: sends %r and declares it nowhere. The user was shown an "
                "envelope this request does not match." % (rel, key))
        for key in sorted(declared - emitted):
            findings.append(
                "%s: declares %r and does not send it. A disclosure that "
                "overstates a request teaches its reader that the table is "
                "approximate." % (rel, key))
        for key in sorted(emitted - set(ENVELOPE_VOCABULARY)):
            findings.append(
                "%s: sends %r, which `request.envelope` does not describe."
                % (rel, key))

        # The payload has to be in there, whole, and nowhere else.
        #
        # Compared against the *decoded* string leaves rather than against
        # the body's bytes, because the body is JSON and the payload is a
        # JSON string inside it - the quotes are escaped on the way in, so
        # a substring test on the raw bytes would report every correct
        # adapter as broken. Walking the leaves is also what makes the
        # second half possible: a decoy in a leaf that is *not* the payload
        # is this adapter putting something of the user's in its envelope.
        leaves = _string_leaves(document)
        carrying = [leaf for leaf in leaves if leaf == content]
        elsewhere = [leaf for leaf in leaves
                     if leaf != content and DECOY in leaf]
        if len(carrying) != 1:
            findings.append(
                "%s: the canonical payload appears %d time(s) in the body it "
                "built, not once. What was digested and what left are then "
                "two documents that resemble each other."
                % (rel, len(carrying)))
        elif elsewhere:
            findings.append(
                "%s: the decoy appears in the body outside the payload "
                "content (%d place(s)) - so this adapter puts something of "
                "the user's in its envelope as well." % (rel, len(elsewhere)))
        else:
            checked += 1
    registry.reset()
    return findings, checked


def main():
    modules = adapter_modules()
    if not modules:
        print("FAILED: no note adapter was found under %s, so this check "
              "asserted nothing about what one sends. Red rather than green: "
              "it cannot answer its question without one."
              % EXTRAS_ROOT.relative_to(REPO_ROOT).as_posix())
        return 1

    bad = 0
    for path in modules:
        rel = path.relative_to(REPO_ROOT).as_posix()
        for finding in detect(path.read_bytes()):
            print("%s: %s" % (rel, finding))
            bad += 1

    live, checked = live_findings(modules)
    for finding in live:
        print("live: %s" % finding)
        bad += 1

    if bad:
        print("\nFAILED: %d way(s) in which an adapter could send something "
              "the disclosure does not describe." % bad)
        return 1
    print("OK: %d note adapter(s) inspected and driven. Every one declares "
          "its envelope, sends exactly what it declares, uses no key outside "
          "the four the `request.envelope` row describes, and carries the "
          "canonical payload whole - %d live assertion(s), with a decoy "
          "project id proving the payload was in the body rather than the "
          "body being empty. No socket was opened: body() is a pure function "
          "on purpose." % (len(modules), checked))
    return 0


if __name__ == "__main__":
    sys.exit(main())
