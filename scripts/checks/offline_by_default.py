"""Rule 11: offline by default.

AST scan of the core package and of the repository tooling. The core may
not import a networking module at all - not "imports it but does not call
it", not "calls it only when a flag is set". Network access is allowed
only inside murscope/providers/, which configuration has to enable
explicitly.

That directory is exempt and it is not empty: `providers/noop.py` ships,
to prove the registration wiring. It imports nothing forbidden, opens no
socket, and is loaded only if the user puts its name in `config.toml`,
where `enabled` is empty by default. This docstring said the directory
"does not exist yet" while the module was in the wheel and Rule 16's own
check was printing "1 provider module(s)" - the exemption is real, so the
reason given for it has to be too.

Imports are read from the parse tree rather than grepped, so this file
can name the forbidden modules without tripping itself, and so an import
hidden inside a function or a try block is still found. __import__() and
importlib.import_module() with a literal module name are caught too;
with a non-literal name they are refused outright, because a dynamic
import is exactly how this rule would be evaded.

The import list alone leaves a shell-shaped hole: subprocess.run(["curl",
"-X", "POST", "https://..."]) imports nothing forbidden and reaches the
network anyway. So subprocess argument lists are inspected too, and a
network tool as the program is refused wherever it appears. README
promises "no network call at all"; the check keeps that promise rather
than narrowing it to "no networking import".

Fails when: any module under murscope/ (outside murscope/providers/) or
under scripts/ imports urllib, socket, http, ssl, ftplib, smtplib,
telnetlib, xmlrpc, asyncio, or a third-party HTTP client; or performs a
dynamic import whose target cannot be read statically; or shells out to
curl, wget, nc, ssh, scp, rsync or another network tool.
"""
from __future__ import annotations

import ast
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
CORE = REPO_ROOT / "murscope"
TOOLING = REPO_ROOT / "scripts"
PROVIDERS = CORE / "providers"

FORBIDDEN_ROOTS = {
    "urllib", "socket", "socketserver", "http", "ssl", "ftplib", "smtplib",
    "poplib", "imaplib", "nntplib", "telnetlib", "xmlrpc", "asyncio",
    "wsgiref", "requests", "httpx", "urllib3", "aiohttp", "websockets",
    "grpc", "boto3", "botocore", "paramiko", "anthropic", "openai",
    # The C accelerators sit one underscore away from the names above
    # and open real sockets. _socket in particular is a working bypass
    # of this entire rule for the price of one character.
    "_socket", "_ssl", "ctypes", "multiprocessing",
}
# webbrowser is not forbidden outright: `murscope open` hands a local
# file:// path to the desktop browser at M2, and that opens no socket.
# But it is not free either - webbrowser.open() takes a URL, so an
# unconstrained exemption is an exfiltration channel with a written
# excuse. Every call is checked below.
BROWSER_MODULE = "webbrowser"
BROWSER_OPENERS = {"open", "open_new", "open_new_tab"}
DYNAMIC_IMPORTERS = {"__import__", "importlib.import_module"}

# Programs that reach the network. Shelling out to one of these is a
# network call whatever the import list says.
NETWORK_TOOLS = {
    "curl", "wget", "wget2", "aria2c", "httpie", "http", "https", "xh",
    "nc", "ncat", "netcat", "socat", "telnet", "ftp", "lftp", "tftp",
    "ssh", "scp", "sftp", "rsync", "rclone",
    "ping", "dig", "nslookup", "host", "traceroute", "whois",
    "pip", "pip3", "npm", "npx", "yarn", "pnpm", "brew", "apt", "apt-get",
    "docker", "kubectl", "gh", "hub", "aws", "gcloud", "az", "openssl",
}
SUBPROCESS_FUNCS = {
    "run", "check_output", "check_call", "call", "Popen",
    "getoutput", "getstatusoutput",
}


def dotted(node):
    parts = []
    cur = node
    while isinstance(cur, ast.Attribute):
        parts.append(cur.attr)
        cur = cur.value
    if isinstance(cur, ast.Name):
        parts.append(cur.id)
    else:
        return None
    return ".".join(reversed(parts))


def subprocess_aliases(tree):
    """Names bound by `from subprocess import run` and friends."""
    aliases = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module == "subprocess":
            for alias in node.names:
                if alias.name in SUBPROCESS_FUNCS:
                    aliases.add(alias.asname or alias.name)
    return aliases


def leading_string(node):
    """The constant prefix of a string expression, or None.

    Handles the three ways a command line gets built: a plain literal, a
    percent-format ("nc -z %s 443" % host), and an f-string. Only the
    leading constant matters, because that is where the program name is.
    """
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Mod):
        return leading_string(node.left)
    if isinstance(node, ast.JoinedStr) and node.values:
        return leading_string(node.values[0])
    return None


def program_of(call):
    """The literal program a subprocess call runs, or None."""
    if not call.args:
        return None
    first = call.args[0]
    if isinstance(first, (ast.List, ast.Tuple)) and first.elts:
        first = first.elts[0]
    text = leading_string(first)
    if text is None or not text.strip():
        return None
    # A shell string ("curl -s https://...") reduces to its first word.
    return text.strip().split()[0]


def network_tool_of(call, name, aliases):
    """Network tool name when this call shells out to one, else None."""
    tail = name.rsplit(".", 1)[-1]
    is_subprocess = (
        (tail in SUBPROCESS_FUNCS and name.startswith("subprocess."))
        or name in aliases
        or name in ("os.system", "os.popen")
    )
    if not is_subprocess:
        return None
    program = program_of(call)
    if program is None:
        return None
    base = program.rsplit("/", 1)[-1]
    return base if base in NETWORK_TOOLS else None


def browser_problem(call, name):
    """A finding when webbrowser is handed something that is not local.

    Accepts a file:// literal, a literal with no scheme, and the one
    expression that is provably local - Path(...).as_uri(). Anything
    else, including a bare variable, is refused: the point of the
    exemption is opening a file on disk, and a check that cannot tell
    that from a URL is not enforcing anything.
    """
    tail = name.rsplit(".", 1)[-1]
    if not (name.startswith(BROWSER_MODULE + ".") or tail in BROWSER_OPENERS):
        return None
    if not name.startswith(BROWSER_MODULE + ".") or tail not in BROWSER_OPENERS:
        return None
    if not call.args:
        return None
    target = call.args[0]
    if isinstance(target, ast.Constant) and isinstance(target.value, str):
        value = target.value
        if value.startswith("file://") or "://" not in value:
            return None
        return ("%s(%r) opens a URL, not a local file. Rule 11 allows the "
                "browser only for the local board." % (name, value))
    if isinstance(target, ast.Call) and getattr(target.func, "attr", None) == "as_uri":
        return None
    return ("%s() is handed an expression this check cannot prove is local. "
            "Pass a file:// literal or Path(...).as_uri(); an unconstrained "
            "browser call is an exfiltration channel with a written exemption."
            % name)


def detect(payload):
    """Findings for one module. Pure: source in, list of findings out."""
    src = payload.decode("utf-8", errors="replace")
    try:
        tree = ast.parse(src)
    except SyntaxError as exc:
        return ["cannot parse (%s)." % exc]

    aliases = subprocess_aliases(tree)
    findings = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.split(".")[0] in FORBIDDEN_ROOTS:
                    findings.append("%d: forbidden import '%s' (Rule 11: the core "
                                    "does not reach the network)."
                                    % (node.lineno, alias.name))
        elif isinstance(node, ast.ImportFrom):
            if node.level:
                continue
            if (node.module or "").split(".")[0] in FORBIDDEN_ROOTS:
                findings.append("%d: forbidden import 'from %s import ...' (Rule 11)."
                                % (node.lineno, node.module))
        elif isinstance(node, ast.Call):
            name = dotted(node.func) or ""
            browser = browser_problem(node, name)
            if browser:
                findings.append("%d: %s" % (node.lineno, browser))
                continue
            tool = network_tool_of(node, name, aliases)
            if tool:
                findings.append("%d: shells out to '%s', which reaches the network "
                                "(Rule 11: no network call at all, not one that is "
                                "off by default)." % (node.lineno, tool))
                continue
            if name not in DYNAMIC_IMPORTERS and not name.endswith("import_module"):
                continue
            target = node.args[0] if node.args else None
            if isinstance(target, ast.Constant) and isinstance(target.value, str):
                if target.value.split(".")[0] in FORBIDDEN_ROOTS:
                    findings.append("%d: forbidden dynamic import of '%s' (Rule 11)."
                                    % (node.lineno, target.value))
            else:
                findings.append("%d: dynamic import with a non-literal module name; "
                                "Rule 11 cannot be verified by reading the source."
                                % node.lineno)
    return findings


def scan(path, rel):
    bad = 0
    for finding in detect(path.read_bytes()):
        print("%s:%s" % (rel, finding))
        bad += 1
    return bad


def targets():
    found = []
    for root in (CORE, TOOLING):
        if not root.is_dir():
            continue
        for path in sorted(root.rglob("*.py")):
            if PROVIDERS in path.parents:
                continue
            found.append(path)
    return found


def main():
    files = targets()
    if not files:
        print("OK: no core or tooling modules present yet; nothing to inspect.")
        return 0

    bad = 0
    for path in files:
        bad += scan(path, path.relative_to(REPO_ROOT).as_posix())

    if bad:
        print("\nFAILED: %d networking import(s) or network tool invocation(s) "
              "outside a provider." % bad)
        return 1
    provider_note = "murscope/providers/ does not exist yet"
    if PROVIDERS.is_dir():
        provider_note = "murscope/providers/ is exempt and config-gated"
    print("OK: %d module(s) inspected, none imports a networking module and none "
          "shells out to a network tool (%s)." % (len(files), provider_note))
    return 0


if __name__ == "__main__":
    sys.exit(main())
