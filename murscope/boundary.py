"""What this install can reach, read off the disk it was installed onto.

DP88 made promise two a fact about which files `pip` put on the user's
machine rather than a fact about what a run happened to do. This module
is the one place that reads that fact, and two surfaces ask it:

* `murscope selftest` step 9 - nothing this install can load is able to
  open a socket - which reports it to the user in words;
* `render`, which picks the sentence the **board footer** carries.

The second one is why this stopped being a private helper inside the
selftest. The footer said "Makes no network call" in every locale, and
that sentence was true on both installs for exactly as long as the
transport refused to send anything. Stage two supplies the consent it was
waiting for, so the sentence acquired a shelf life the same day the
capability did - and a promise printed on the artifact is not a place to
discover that later. The board now says which install produced it.

**Read, never imported.** The question is what a module *could* do, and
importing it to find out would be asking a suspected network client to
run so that its silence can be admired. Reading is also the only method
available inside `selftest`, which runs under an audit hook that refuses
socket events: an import that did reach out would surface as a traceback
rather than as a verdict.

The module roots below are named as strings and compared against a parse
tree, never grepped, so this file can list them without importing one
(Rule 11) and so a name inside a comment or a docstring is not a hit.
"""
from __future__ import annotations

import ast
from pathlib import Path

# The board footer's two sentences. Both keys exist in every locale, and
# the choice between them is made here rather than in the template - the
# board's JavaScript is not executed by anything in this repository
# (DP85), so a decision taken in Python is a decision something can
# measure.
BASE_PROMISE_KEY = "board.promise"
NETWORK_PROMISE_KEY = "board.promise.network"

# Module roots that can open a socket.
SOCKET_CAPABLE_ROOTS = (
    "urllib", "socket", "socketserver", "http", "ssl", "ftplib", "smtplib",
    "poplib", "imaplib", "telnetlib", "xmlrpc", "asyncio", "wsgiref",
    "requests", "httpx", "urllib3", "aiohttp", "websockets", "grpc",
    "boto3", "botocore", "paramiko", "anthropic", "openai", "_socket", "_ssl",
)

# The provider layer's own directory, as a module constant rather than a
# path computed inside a function. Rule 6 asks for that and is right to: a
# traversal whose root is a local variable is one refactor away from being
# pointed somewhere else. Package-internal by construction - this file's
# own sibling - so it is the directory `murscope.providers.__path__`
# resolves to, in a checkout and in site-packages alike.
PROVIDERS_DIR = Path(__file__).resolve().parent / "providers"


def socket_capable(source):
    """Networking imports in one provider module's source."""
    try:
        tree = ast.parse(source)
    except SyntaxError as exc:
        return ["<unparseable: %s>" % exc]
    hits = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.split(".")[0] in SOCKET_CAPABLE_ROOTS:
                    hits.add(alias.name)
        elif isinstance(node, ast.ImportFrom) and not node.level:
            if (node.module or "").split(".")[0] in SOCKET_CAPABLE_ROOTS:
                hits.add(node.module)
    return sorted(hits)


def providers_owned_by_distributions(directory):
    """{filename: distribution name} for provider files a package owns.

    One pass over the installed distributions, keeping only the entries
    that land in this directory. Called **only** when a module is present
    that the base distribution does not ship, because that is the only
    question it answers and the pass is not free.
    """
    owners = {}
    try:
        from importlib import metadata  # noqa: PLC0415 - only this path needs it
    except ImportError:  # pragma: no cover - 3.8 and older, which we do not ship for
        return owners
    try:
        distributions = list(metadata.distributions())
    except Exception:
        return owners
    for dist in distributions:
        try:
            name = dist.metadata["Name"]
            files = dist.files or ()
        except Exception:
            continue
        for entry in files:
            if entry.name.endswith(".py") and "providers" in entry.parts:
                try:
                    located = Path(dist.locate_file(entry)).resolve()
                except Exception:
                    continue
                if located.parent == directory:
                    owners[located.name] = name
    return owners


class Survey(object):
    """What the provider directory holds, and what each module can do.

    `rows` are the modules the base distribution does **not** ship, each
    with the distribution that owns it. `reaching` is every module that
    can open a socket whichever distribution it came from - the base
    package's included, because a base module that could reach out is a
    defect and the board footer still has to tell the truth about it
    while the defect is being fixed.
    """

    def __init__(self, findings, rows, base_count, reaching):
        self.findings = findings
        self.rows = rows
        self.base_count = base_count
        self.reaching = reaching


def survey():
    """Read every provider module on this disk. Never imports one.

    **The three findings, and what walks into each (DP87).**

    * *Nothing found at all* is a failure, not a pass. A step that asserts
      an absence over an empty set asserts nothing, and this package has
      found that shape more than once. `noop` ships, so a scan reaching
      zero modules means the scan is broken.
    * *A module the base distribution ships is socket-capable.* Reverse
      verification is a networking import added to `noop.py`.
    * *A module is present that the base distribution does not ship and no
      installed distribution owns.* The planted-module case, and the one
      that makes "absent" mean absent: a file dropped into
      `site-packages/murscope/providers/` by hand belongs to nobody. A
      module owned by `murscope-ai` is reported rather than failed - the
      user asked for it by typing `[ai]`.
    """
    from . import providers  # noqa: PLC0415 - only this reads the layer

    findings = []
    rows = []
    reaching = []
    modules = sorted(PROVIDERS_DIR.glob("*.py"))
    if not modules:
        return Survey(
            ["no provider module was found under %s at all, so this step "
             "asserted nothing. `noop` ships with the base package: a scan "
             "that reaches zero modules is a broken scan, not an empty "
             "provider layer." % PROVIDERS_DIR], [], 0, [])

    shipped = {"__init__.py"} | set("%s.py" % name for name in providers.BASE)
    strangers = [path for path in modules if path.name not in shipped]
    owners = providers_owned_by_distributions(PROVIDERS_DIR) if strangers else {}

    base_count = 0
    for path in modules:
        try:
            source = path.read_text(encoding="utf-8", errors="replace")
        except OSError as exc:
            findings.append("a provider module (%s) could not be read back "
                            "(%s), so its capability was not established"
                            % (path.name, exc))
            continue
        hits = socket_capable(source)
        if path.name in shipped:
            base_count += 1
            if hits:
                reaching.append((path.name, "the base package", hits))
                findings.append(
                    "%s is shipped by the base package and imports %s. Promise "
                    "two says there is no network call at all, not one that is "
                    "off by default - a base install must not carry a module "
                    "that could open a socket." % (path.name, ", ".join(hits)))
            continue
        owner = owners.get(path.name)
        if not owner:
            findings.append(
                "%s is installed under %s and no installed distribution owns "
                "it. The base package does not ship it and `pip` did not put "
                "it there, so it was placed by hand - which is exactly the "
                "case this step exists to catch."
                % (path.name, PROVIDERS_DIR))
            continue
        rows.append((path.name, owner, hits))
        if hits:
            reaching.append((path.name, owner, hits))
    return Survey(findings, rows, base_count, reaching)


def promise_key(reaching):
    """Which footer sentence this install is entitled to print.

    A pure function over the survey's answer, so both branches can be
    exercised on any install rather than only on the one that happens to
    be installed - which is the whole of DP87. A base install has an empty
    `reaching` and prints the promise unchanged; an install carrying
    anything socket-capable prints the sentence that says so.
    """
    return NETWORK_PROMISE_KEY if reaching else BASE_PROMISE_KEY
