"""The module matrix: what is installed, what is enabled, what each does.

`registry.register()` has carried `name`, `summary`, `stage`, `reads`,
`writes`, `alerts`, `destination`, `evidence` and `evidence_note` since
M3, and until now the only surface that showed any of it was
`daily --providers`, which shows the note writers. This is the surface
that makes the whole declaration legible in one place.

**The matrix's sentences are as much of it as its rows (DP115).** The
one accounting sentence this product has shipped about provider modules
was wrong the first time: `daily --providers` computed "installed and not
enabled, so they were not imported" as installed-minus-writers, so with
the contributions reader switched on it named `github` - a module that is
enabled, is in `sys.modules`, and is returned by `registry.readers()`.
Its real reason for having no row was that it registers `reads` and not
`writes`. The count was wrong by one in the same breath.

So this module is built around the distinction that defect was made of:

* **What can be read off the disk** - the module's file is there, and its
  source imports something that can open a socket, or does not. True for
  every module, enabled or not, because `boundary.survey()` reads and
  never imports.
* **What only the registry knows** - what a module reads, writes, alerts
  to, and where it sends. A provider declares those by calling
  `register()`, which happens at *import* time, which happens only when
  `config.toml` names it (Rule 13). For a module nothing imported, this
  is not "nothing": it is **unknown**, and the row says so in that word.

A matrix that printed a dash in those columns for an un-imported module
would be making DP115's mistake again in a wider table - and the fix is
not a better guess, it is a column that can say "not asked".

Nothing here imports a provider to describe it. Describing a module is
not a reason to run it, and Rule 13 does not carry an exception for
curiosity.
"""
from __future__ import annotations

from . import boundary, config, providers, registry

# What a row says about a capability nobody asked the module about.
UNKNOWN = "unknown"
YES = "yes"
NO = "no"


def _capability(provider, attribute):
    return YES if getattr(provider, attribute, None) is not None else NO


def rows(home=None, settings=None):
    """One row per provider module on this disk. Imports nothing new.

    The caller is expected to have loaded whatever `config.toml` names
    already - that is `providers.load()`'s job and the command's - so this
    reads the registry as it stands rather than changing it.
    """
    settings = settings if settings is not None else config.load_config(home)
    enabled = [name for name in settings.section("providers").get("enabled", [])
               if isinstance(name, str)]
    imported = registry.registered()
    survey = boundary.survey()
    owners = {name: owner for name, owner, _hits in survey.rows}
    reaching = {name: hits for name, _owner, hits in survey.reaching}

    out = []
    for name in providers.available():
        filename = "%s.py" % name
        provider = imported.get(name)
        row = {
            "name": name,
            # Read off the installed distributions, never guessed from the
            # name. A module the base package ships says so; a module no
            # distribution owns is the planted-file case and `survey()`
            # has already turned it into a finding.
            "distribution": ("murscope" if name in providers.BASE
                             else owners.get(filename, UNKNOWN)),
            "enabled": YES if name in enabled else NO,
            "imported": YES if provider is not None else NO,
            # Known for every module, because this one is read rather than
            # asked: `boundary.socket_capable` parses the source.
            "socket": YES if filename in reaching else NO,
            "socket_imports": ", ".join(reaching.get(filename, ())),
        }
        if provider is None:
            row.update({
                "summary": UNKNOWN, "stage": UNKNOWN, "reads": UNKNOWN,
                "writes": UNKNOWN, "alerts": UNKNOWN, "destination": UNKNOWN,
                "evidence": UNKNOWN, "evidence_note": "",
                "known": False,
            })
        else:
            row.update({
                "summary": provider.summary,
                "stage": provider.stage,
                "reads": _capability(provider, "reads"),
                "writes": _capability(provider, "writes"),
                "alerts": _capability(provider, "alerts"),
                "destination": provider.destination or "-",
                "evidence": provider.evidence,
                "evidence_note": provider.evidence_note or "",
                "known": True,
            })
        out.append(row)

    # A name in `enabled` that is not on disk has no row above, and saying
    # nothing about it would be the same silence DP115 was about. It is not
    # a module the matrix can describe; it is a configuration line pointing
    # at nothing, and it gets a row of its own that says exactly that.
    for name in enabled:
        if name not in providers.available():
            out.append({
                "name": name, "distribution": "not installed",
                "enabled": YES, "imported": NO, "socket": UNKNOWN,
                "socket_imports": "", "summary": UNKNOWN, "stage": UNKNOWN,
                "reads": UNKNOWN, "writes": UNKNOWN, "alerts": UNKNOWN,
                "destination": UNKNOWN, "evidence": UNKNOWN,
                "evidence_note": "", "known": False,
            })
    return out


def sentences(matrix):
    """The accounting under the table, sourced from the table itself.

    Every number below is counted off `matrix`, never inferred from which
    other table a name is missing from - which is the arithmetic DP115
    found wrong. The sentences are emitted whether or not anything is
    enabled: the install that most needs the explanation is the one whose
    table is all `unknown`, and that was the install the old accounting
    returned early on.
    """
    installed = [row for row in matrix if row["distribution"] != "not installed"]
    described = [row for row in matrix if row["known"]]
    silent = [row for row in matrix if not row["known"]
              and row["distribution"] != "not installed"]
    missing = [row for row in matrix if row["distribution"] == "not installed"]
    reaching = [row for row in installed if row["socket"] == YES]

    lines = ["%d provider module(s) are installed under murscope.providers, "
             "and %d of them %s described below. A module is described when "
             "it has been imported, and it is imported when config.toml names "
             "it (Rule 13)."
             % (len(installed), len(described),
                "is" if len(described) == 1 else "are")]
    if silent:
        lines.append(
            "%d module(s) - %s - were not imported, so every capability "
            "column for them reads `unknown` rather than `no`. Nothing here "
            "asked them what they do: a provider declares that by calling "
            "register() at import time, and importing a module in order to "
            "describe it would be running it without configuration naming it. "
            "`unknown` is the honest answer and `-` would not be (DP115)."
            % (len(silent), ", ".join(row["name"] for row in silent)))
    if missing:
        lines.append(
            "%d name(s) under [providers] enabled are not installed: %s. That "
            "is a configuration line pointing at nothing, not a module that "
            "does nothing. If you expected a network provider here, it ships "
            "in a separate distribution: pip install 'murscope[ai]'."
            % (len(missing), ", ".join(row["name"] for row in missing)))
    lines.append(
        "The `socket` column is read rather than asked, so it is known for "
        "every installed module including the ones nothing imported: "
        "boundary.survey() parses each file's own imports and never runs one. "
        "%s"
        % ("%d module(s) could open a socket (%s). Whether one ever does is a "
           "question about configuration and consent, not about this column."
           % (len(reaching), ", ".join(row["name"] for row in reaching))
           if reaching else
           "Nothing installed here can open a socket at all - promise two as "
           "a fact about your disk rather than a setting (DP88)."))
    unproven = [row for row in described if row["evidence"] != "live"]
    if described:
        lines.append(
            "The `evidence` column is DP89: %d of the %d described module(s) "
            "%s never completed a live round trip, and each one says why in "
            "the line under its row. A table without that column would read "
            "as a list of working providers."
            % (len(unproven), len(described),
               "has" if len(unproven) == 1 else "have"))
    return lines
