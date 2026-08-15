"""Rule 13, second half: a base install has nothing to enable.

The other half of Rule 13 asks whether a provider runs unasked. This one
asks a question that half cannot reach: **is there anything there to
ask for?** They fail differently - a loader can be correct while the
wheel ships a provider it should not, and a wheel can be clean while the
loader imports at module scope - so they are two checks rather than one.

**This is measured on a built wheel, never on the source tree.** M1's
only real defect was a fixture present in the checkout and missing from
the wheel, and no amount of reading `murscope/` could have seen it. The
same gap runs the other way here: what is in the repository is not what
`pip install murscope` puts on a user's disk. So this check builds the
wheel with the backend `pyproject.toml` declares - the same backend `pip`
uses - and reads the artifact. Nothing below inspects a source file to
answer a question about what shipped.

The complementary half, an installed wheel in a fresh environment, is
`murscope selftest` step 6. It ships inside the command on purpose, so it
runs on the user's machine against the build they installed; CI runs it
from a built wheel outside every checkout. Between them: this check reads
the artifact, that step reads the installation.

**What walks into this check (DP87).** Both wheels are built and both
are read, and the extras wheel is what keeps this from being an assertion
over an empty set:

* the **base** wheel must carry exactly the provider modules the loader's
  `BASE` tuple names, plus the loader itself, and not one of them may
  import anything that can open a socket;
* the **extras** wheel must carry at least one provider module the base
  wheel does not have, and **at least one of them must be socket-capable**.
  Without that, "the base wheel has nothing that can reach out" would be
  true of a product where nothing anywhere can reach out, and the
  boundary this milestone is built on would be untested;
* the two wheels must not both carry the same file, because they install
  into one directory and a collision is a distribution quietly owning
  another's module;
* the extra must be declared and pinned: `Provides-Extra: ai` and a
  `Requires-Dist` naming the extras distribution at the exact version the
  extras distribution actually is, which is also `murscope.__version__`.
  Two halves of one product cut along a boundary must not drift apart.

If the build backend is not importable this check goes **red**, not
green. It cannot answer its question without a wheel, and a check that
reports success when its instrument is missing is the failure this
repository has spent two milestones removing.

Fails when: the base wheel carries a provider module beyond the loader
and `BASE`; any provider module in the base wheel imports a networking
module or shells out to a network tool; the extras wheel carries no
provider module, or carries none that is socket-capable; a file appears
in both wheels; the base wheel's metadata does not declare the `ai`
extra, or pins it to a version that is not the extras distribution's own
version and `murscope.__version__`; or the wheel cannot be built.
"""
from __future__ import annotations

import ast
import re
import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
EXTRAS_ROOT = REPO_ROOT / "extras" / "murscope-ai"
EXTRA_NAME = "ai"
EXTRAS_DIST = "murscope-ai"

# What the base distribution copies into a build sandbox. The build reads
# nothing else, and building in a copy is why the repository is left
# without a build/ directory or an .egg-info after the gate runs.
BASE_SOURCES = ("murscope", "pyproject.toml", "README.md", "LICENSE")

PROVIDER_PREFIX = "murscope/providers/"

# Roots that can open a socket. Named as strings and compared against a
# parse tree, so this file can list them without importing one (Rule 11).
NETWORK_ROOTS = {
    "urllib", "socket", "socketserver", "http", "ssl", "ftplib", "smtplib",
    "poplib", "imaplib", "nntplib", "telnetlib", "xmlrpc", "asyncio",
    "wsgiref", "requests", "httpx", "urllib3", "aiohttp", "websockets",
    "grpc", "boto3", "botocore", "paramiko", "anthropic", "openai",
    "_socket", "_ssl",
}
NETWORK_TOOLS = {
    "curl", "wget", "httpie", "xh", "nc", "ncat", "netcat", "socat",
    "telnet", "ftp", "ssh", "scp", "sftp", "rsync", "rclone", "pip", "pip3",
}
SUBPROCESS_FUNCS = {"run", "check_output", "check_call", "call", "Popen",
                    "getoutput", "getstatusoutput"}


def dotted(node):
    parts = []
    current = node
    while isinstance(current, ast.Attribute):
        parts.append(current.attr)
        current = current.value
    if isinstance(current, ast.Name):
        parts.append(current.id)
        return ".".join(reversed(parts))
    return ""


def _program_of(call):
    if not call.args:
        return None
    first = call.args[0]
    if isinstance(first, (ast.List, ast.Tuple)) and first.elts:
        first = first.elts[0]
    if isinstance(first, ast.Constant) and isinstance(first.value, str):
        text = first.value.strip()
        return text.split()[0].rsplit("/", 1)[-1] if text else None
    return None


def detect(payload):
    """Findings for one provider module's source: can it reach out?

    Pure: source in, findings out. Fed the source read **out of a wheel**,
    never off the source tree.
    """
    source = payload.decode("utf-8", errors="replace")
    try:
        tree = ast.parse(source)
    except SyntaxError as exc:
        return ["cannot parse (%s), so its capability cannot be read." % exc]

    findings = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.split(".")[0] in NETWORK_ROOTS:
                    findings.append(
                        "%d: imports '%s', which can open a socket."
                        % (node.lineno, alias.name))
        elif isinstance(node, ast.ImportFrom):
            if not node.level and (node.module or "").split(".")[0] in NETWORK_ROOTS:
                findings.append(
                    "%d: imports 'from %s import ...', which can open a socket."
                    % (node.lineno, node.module))
        elif isinstance(node, ast.Call):
            name = dotted(node.func)
            tail = name.rsplit(".", 1)[-1]
            if tail not in SUBPROCESS_FUNCS and name not in ("os.system", "os.popen"):
                continue
            program = _program_of(node)
            if program in NETWORK_TOOLS:
                findings.append(
                    "%d: shells out to '%s', which reaches the network however "
                    "empty the import list is." % (node.lineno, program))
    return findings


def build_wheel(source_dir, sources, out_dir):
    """Build one wheel with the declared backend. Returns (path, error).

    A subprocess rather than an in-process call: the backend changes the
    working directory and writes a build tree beside the sources, and the
    copy it does that in is thrown away with the temporary directory.
    """
    sandbox = out_dir / ("src-" + source_dir.name)
    sandbox.mkdir(parents=True)
    for name in sources:
        origin = source_dir / name
        if not origin.exists():
            return None, "%s is missing from %s" % (name, source_dir)
        if origin.is_dir():
            shutil.copytree(str(origin), str(sandbox / name))
        else:
            shutil.copy2(str(origin), str(sandbox / name))

    wheels = out_dir / ("wheel-" + source_dir.name)
    wheels.mkdir(parents=True)
    program = (
        "import sys, warnings, contextlib, io\n"
        "warnings.simplefilter('ignore')\n"
        "import setuptools.build_meta as backend\n"
        "buf = io.StringIO()\n"
        "with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):\n"
        "    name = backend.build_wheel(sys.argv[1])\n"
        "sys.stdout.write(name)\n"
    )
    result = subprocess.run(
        [sys.executable, "-c", program, str(wheels)],
        cwd=str(sandbox), stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if result.returncode != 0:
        detail = result.stderr.decode("utf-8", errors="replace").strip()
        tail = detail.splitlines()[-3:] if detail else ["no output"]
        return None, ("the wheel could not be built (%s). This check cannot "
                      "answer its question without one, so it is red rather "
                      "than green. If setuptools is missing from this "
                      "interpreter, `pip install setuptools` - it is already "
                      "this project's declared build backend."
                      % " / ".join(tail))
    built = wheels / result.stdout.decode("utf-8", errors="replace").strip()
    if not built.exists():
        return None, "the backend reported %s and it is not there" % built
    return built, None


def provider_members(wheel):
    """{filename: source bytes} for provider modules inside a wheel."""
    members = {}
    with zipfile.ZipFile(str(wheel)) as archive:
        for name in archive.namelist():
            if name.startswith(PROVIDER_PREFIX) and name.endswith(".py"):
                members[name[len(PROVIDER_PREFIX):]] = archive.read(name)
    return members


def wheel_files(wheel):
    with zipfile.ZipFile(str(wheel)) as archive:
        return set(n for n in archive.namelist() if not n.endswith("/"))


def wheel_metadata(wheel):
    with zipfile.ZipFile(str(wheel)) as archive:
        for name in archive.namelist():
            if name.endswith(".dist-info/METADATA"):
                return archive.read(name).decode("utf-8", errors="replace")
    return ""


def base_module_names():
    """The loader's own BASE tuple, read rather than assumed."""
    source = (REPO_ROOT / "murscope" / "providers" / "__init__.py").read_text(
        encoding="utf-8")
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if getattr(target, "id", None) == "BASE":
                    try:
                        return set(ast.literal_eval(node.value))
                    except ValueError:
                        return None
    return None


def declared_versions():
    """(package version, extras version, pinned version) as written down."""
    package = re.search(
        r'^__version__\s*=\s*"([^"]+)"',
        (REPO_ROOT / "murscope" / "__init__.py").read_text(encoding="utf-8"),
        re.MULTILINE)
    extras = re.search(
        r'^version\s*=\s*"([^"]+)"',
        (EXTRAS_ROOT / "pyproject.toml").read_text(encoding="utf-8"),
        re.MULTILINE)
    pinned = re.search(
        r'%s\s*==\s*([0-9A-Za-z.\-]+)' % re.escape(EXTRAS_DIST),
        (REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    return (package.group(1) if package else None,
            extras.group(1) if extras else None,
            pinned.group(1) if pinned else None)


def check_metadata(metadata, pinned):
    findings = []
    if ("Provides-Extra: %s" % EXTRA_NAME) not in metadata:
        findings.append(
            "the base wheel's METADATA declares no `Provides-Extra: %s`, so "
            "`pip install 'murscope[%s]'` would install nothing extra and the "
            "boundary would exist only in the documentation."
            % (EXTRA_NAME, EXTRA_NAME))
    wanted = re.compile(
        r"^Requires-Dist:\s*%s\s*==\s*%s\s*;.*extra\s*==\s*[\"']%s[\"']"
        % (re.escape(EXTRAS_DIST), re.escape(pinned or ""), EXTRA_NAME),
        re.MULTILINE)
    if pinned and not wanted.search(metadata):
        findings.append(
            "the base wheel's METADATA carries no `Requires-Dist: %s==%s ; "
            "extra == \"%s\"`. The wheel is what `pip` reads; a pin that "
            "exists only in pyproject.toml is a pin nothing enforces."
            % (EXTRAS_DIST, pinned, EXTRA_NAME))
    return findings


def main():
    if not EXTRAS_ROOT.is_dir():
        print("FAILED: %s is missing. The network layer is a separate "
              "distribution (DP88); without it there is no boundary to "
              "measure and the `ai` extra points at nothing."
              % EXTRAS_ROOT.relative_to(REPO_ROOT).as_posix())
        return 1

    base_names = base_module_names()
    if base_names is None:
        print("FAILED: murscope/providers/__init__.py declares no readable "
              "BASE tuple, so what the base wheel is allowed to carry is not "
              "written down anywhere this check can read.")
        return 1

    findings = []
    with tempfile.TemporaryDirectory() as work:
        out = Path(work)
        base_wheel, error = build_wheel(REPO_ROOT, BASE_SOURCES, out)
        if error:
            print("FAILED: base distribution: %s" % error)
            return 1
        extras_wheel, error = build_wheel(
            EXTRAS_ROOT, tuple(p.name for p in sorted(EXTRAS_ROOT.iterdir())
                               if p.name not in ("build", "dist")), out)
        if error:
            print("FAILED: %s: %s" % (EXTRAS_DIST, error))
            return 1

        base_providers = provider_members(base_wheel)
        extras_providers = provider_members(extras_wheel)

        allowed = {"__init__.py"} | set("%s.py" % n for n in base_names)
        for name in sorted(set(base_providers) - allowed):
            findings.append(
                "the base wheel carries murscope/providers/%s, which is "
                "neither the loader nor one of the modules BASE names (%s). A "
                "base install must have nothing to enable - not a disabled "
                "provider, an absent one."
                % (name, ", ".join(sorted(base_names))))
        for name in sorted(allowed - set(base_providers)):
            findings.append(
                "the base wheel does not carry murscope/providers/%s, which "
                "BASE names. `noop` is what proves the wiring; a wheel without "
                "it makes every absence below vacuous." % name)

        for name, source in sorted(base_providers.items()):
            for finding in detect(source):
                findings.append(
                    "the base wheel's murscope/providers/%s:%s Promise two is "
                    "that there is no network call at all, not one that is off "
                    "by default." % (name, finding))

        if not extras_providers:
            findings.append(
                "the %s wheel carries no provider module at all, so the base "
                "wheel's emptiness is being asserted against a product in "
                "which nothing anywhere can reach out. That is not this "
                "boundary passing; it is this boundary never being tested."
                % EXTRAS_DIST)
        else:
            reaching = {name: detect(source)
                        for name, source in extras_providers.items()}
            if not any(reaching.values()):
                findings.append(
                    "the %s wheel carries %d provider module(s) and not one of "
                    "them can open a socket. The extra is the far side of the "
                    "boundary; if nothing there reaches the network, this "
                    "check proves nothing about the near side."
                    % (EXTRAS_DIST, len(extras_providers)))
            shared = sorted(set(base_providers) & set(extras_providers))
            for name in shared:
                findings.append(
                    "murscope/providers/%s is in both wheels. They install "
                    "into one directory: a file in both means one distribution "
                    "silently owns the other's module, and which one wins "
                    "depends on install order." % name)

        collisions = sorted(wheel_files(base_wheel) & wheel_files(extras_wheel))
        for name in collisions:
            if not name.startswith(PROVIDER_PREFIX):
                findings.append(
                    "%s is in both wheels. The extras distribution adds modules "
                    "beside the base package's and owns nothing of it." % name)

        package_version, extras_version, pinned = declared_versions()
        if not pinned:
            findings.append(
                "pyproject.toml does not pin %s to an exact version. The two "
                "distributions are one product cut along a boundary, and an "
                "open pin lets the halves drift apart quietly." % EXTRAS_DIST)
        elif not (pinned == extras_version == package_version):
            findings.append(
                "the versions disagree: murscope.__version__ is %r, %s is %r, "
                "and the extra pins %r. One product, one version."
                % (package_version, EXTRAS_DIST, extras_version, pinned))

        findings.extend(check_metadata(wheel_metadata(base_wheel), pinned))

        base_count = len(base_providers)
        extras_count = len(extras_providers)
        reaching_count = sum(1 for source in extras_providers.values()
                             if detect(source))

    if findings:
        for finding in findings:
            print(finding)
        print("\nFAILED: %d finding(s) against the built wheels." % len(findings))
        return 1
    print("OK: measured on two freshly built wheels, not on the source tree. "
          "The base wheel carries %d provider file(s) - the loader and %s - "
          "and none of them imports anything that can open a socket. The %s "
          "wheel carries %d provider module(s), %d of which can, and shares no "
          "file with the base wheel. The `%s` extra is declared in the base "
          "wheel's own METADATA and pinned to %s, which is also "
          "murscope.__version__."
          % (base_count, ", ".join(sorted(base_names)), EXTRAS_DIST,
             extras_count, reaching_count, EXTRA_NAME, pinned))
    return 0


if __name__ == "__main__":
    sys.exit(main())
