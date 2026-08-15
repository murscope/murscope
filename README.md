# murscope

Read-only portfolio observability. Tell it where your projects are; it
scans them and hands you a one-page dashboard: what is moving, what
stalled, what is stuck on you.

## Three promises

These are the headline, and they are checkable by reading the source
rather than by trusting this page.

1. **It writes nothing into your projects.** Not a byte. The write path
   in the code refuses any target outside `MURSCOPE_HOME`, and every git
   call is a read-only subcommand run with `GIT_OPTIONAL_LOCKS=0`. The
   paths outside that home this tool can write are named here rather than
   discovered later: `murscope timer install` writes your scheduler's job
   description, because launchd and systemd will not read one from
   anywhere else, and `--alerts` adds a second job file beside it. It
   writes **those paths and no others** - the list is a literal in the
   source, compared by equality rather than by directory - the command
   prints every path before writing it, and `murscope timer uninstall`
   removes them.
2. **It makes no network call at all.** Not "off by default" - absent.
   There is no networking import in the core, and a check fails the build
   if one appears.
3. **It reads nothing outside the projects you listed.** No background
   indexing, no history file - running git consults your git
   configuration, as git always does, and `init` with no path looks in
   the conventional project directories that exist under your home to
   propose a roster, then tells you which roots it chose.

And a fourth, which is the same promise from the other side: **zero
telemetry.** No analytics, no crash reporting, no version phone-home, no
usage beacon. Nothing to opt out of, because there is nothing there.

## What this is not

**This is not a task manager.** No gantt charts, no collaboration, no
assignees, and not a place where you edit tasks. It is a read-only view
of work that already exists somewhere else. "Continuous tracking" here
means it tells you when something has gone stale, not that it manages it
for you.

It is also not a SaaS, and it does not publish anything to a public
address. The one artifact is a local HTML file.

## Two installs, and the second one is opt-in

    pip install murscope          the three promises above, unchanged
    pip install 'murscope[ai]'    adds the network layer

The three promises describe the first line. They are not "on by default"
settings that the second line switches off - **the code that could reach
the network is not installed by the first line at all**, because it lives
in a separate distribution. `pip list` will tell you which one you have.
That is the point of splitting them: promise two says "no network call at
all - not 'off by default' - absent", and a feature gated on a
configuration key would have made it mean the thing it refuses.

### What `[ai]` adds, and what it costs you

**What leaves your machine.** Summaries of the projects you have listed -
their state, not their contents - and nothing else. **Where it goes.**
Whichever provider you name: a vendor's API on the open internet, or a
model running on your own machine. A local model still counts as the
network here; a socket is a socket, and what differs is where the data
goes, not whether it left. **On whose key.** Yours. There is no account,
no proxy and no server belonging to this product, so a request is
between you and the provider you chose, billed to you.

Only then, what it is for: a daily note that reads your board and tells
you what changed, and a GitHub reader that pulls your own contribution
data with your own token.

Three separate gates, and passing one is not passing the next. Installed
is not enabled: nothing runs unless `config.toml` names it. Enabled is
not consent: nothing is sent until you have been shown what a request
contains and agreed to it.

**On an `[ai]` install, the board's footer says so.** The promise on a
base install still reads "makes no network call"; on an install that
carries the extra it says what the extra can do instead. A promise
printed on the artifact is the last place to leave a sentence that has
stopped being true.

### Where your keys live, and which of the two is safer

    murscope key set deepseek        reads the value from stdin, never argv
    murscope key list                names, location and mode - never a value

The default is a **0600 file** under `MURSCOPE_HOME`, in a `keys/`
directory at 0700. That needs no dependency at all, which is why it is
the default - **it is not the safer of the two**, and this page is not
going to imply that it is. A file is protected by the filesystem and by
nothing else: anything running as you can read it, and a backup that
copies your home copies your keys with it.

The **system keychain** is protected by the operating system and asks
before it hands a secret over:

    pip install 'murscope[keyring]'

then, in `config.toml`:

    [keys]
    backend = "keyring"

There is no fallback between them. If you choose the keychain and the
package is missing, murscope refuses and says so rather than quietly
writing a file - a tool that gives you something weaker than what you
asked for, without mentioning it, is worse than one that stops.

`murscope key list` prints each key's **length** beside its mode, and
`murscope key set` refuses a value carrying a space, a control character
or a character outside printable ASCII. Neither says whether a key is the
*right* key - that needs the network and this command has none. Both exist
because a key once arrived here three characters longer than the vendor's
console showed it, stored cleanly, read back cleanly, and was refused at
the far end with a status code that explained nothing. Compare the length
with what your provider shows you; a key of the wrong length was mangled
on the way in.

A key never reaches an artifact. Not the board, not a payload, not a log
line, and **not a traceback** - the last one is the reason there is any
machinery here at all, because a failing HTTP library reports the URL it
could not parse, and a URL is where an API key ends up. `murscope
selftest` plants a decoy key on your own machine and looks for it in
every one of those places.

### What you agree to, and what happens when it changes

    murscope consent show  <provider> --to <url>     read the whole disclosure
    murscope consent grant <provider> --to <url>     record that you agreed
    murscope consent status                          is it still current?

The disclosure is the literal list of fields a request would contain,
each with a sentence saying what it is. What is on that list is method
and nothing else: how many projects, which tier, which state kind, days
since the last commit, and the in-hand counts. **No name, no path, no
branch, no commit message, no declaration text, no file contents.** A
project you marked sensitive is not described at all - only counted, so
you can see that it was left out.

It also lists what the transport puts *around* that document - your key in
an authentication header, the user agent, and the provider's own envelope
- because those leave too. A disclosure that described only the body would
be silent about the credential that authenticates it.

**And it names the route.** `urllib` reads `https_proxy` from your
environment by default; murscope does not. Every request goes to the
destination the disclosure names and through nothing else, because a
destination in the fingerprint has to be the one the request reaches - "a
proxy is not a destination" is the same exemption as "localhost is not the
network". If your environment sets a proxy, murscope says so on screen and
tells you it is not using it. If your network requires one, the request
fails and says that, which is the honest outcome; routing through a proxy
on purpose would be a second destination to disclose and agree to, and
that is not built.

Before you agree, the screen also **lists the ids that request would
carry, one per line**, out of the roster you have now. "It sends project
ids" is a description; the names themselves are the thing you are being
asked about, and one of them may not be what you expected: the id is
whatever is in `roster.json`, which the scan set to the directory's own
name unless you changed it. Rename it there and murscope sends what you
renamed it to. That list is not part of the fingerprint - adding a project
does not expire your consent, because what you agreed to is that ids
leave, not which ones.

Your consent is recorded against a fingerprint of that list plus the
destination, **not against the provider's name** - and the fingerprint
covers the *sentences*, not just the field names. If a later version of
murscope would send one more field, send it somewhere else, or describe an
existing field as something other than what you were told it was, the
fingerprint changes, the old consent stops covering it, and you are asked
again - naming what changed. That has a price and it is worth saying: a
build that only fixes a wording will ask you again. The alternative is a
field that keeps its name, changes its meaning, and keeps your answer. A
consent that were merely a "yes" would let the payload grow under an
answer you gave about a smaller one, and nothing anywhere would go red.

**There is more than one disclosure, and one consent never covers two.**
The list above is the board summary. A provider that *reads* rather than
sends has its own, much shorter one, an alert has a third, and `murscope
consent show` prints whichever applies. Which one applies is decided by
what the provider *is*, so a provider you have not enabled yet is one
murscope cannot ask - and it says so and prints no table, rather than
showing you the wrong one. Enable it in `config.toml` first, then read
this screen.

### The daily note

    murscope daily            print the payload, byte for byte. Sends nothing
    murscope daily --send     write today's note, if the slot is open
    murscope daily --providers  which adapters exist, and which have been run

With no `--send` it prints the exact bytes a request would carry and stops.
That is the default because the smallest payload that produces a useful
note is your decision, and you cannot make it from a description of the
payload - only from the payload.

**Four adapters, and they have not all been run.** DeepSeek, Anthropic,
OpenAI and a local model (Ollama). Two of them have completed a live round
trip; the other two are written, and `--providers` says so in a column of
its own with the reason. A list of four under one heading with no such
column would read as four working providers, and that is a claim this
project has not earned for two of them.

**A failed note does not hold the day.** If the request fails, murscope
records a degraded slot with the reason and a moment it becomes worth
asking again, and the next round retries rather than treating "something
is recorded for today" as "today is done". That distinction is the whole
of it: a degraded result that is never re-checked looks exactly like a
successful one from outside. `retry_after_seconds` under `[providers]`
sets the wait, and it is capped at an hour - a backoff is a hold with a
timer on it, and an unbounded one would rebuild the failure while looking
like a preference.

### Reading your own contribution calendar

    murscope contributions             the corrected figure
    murscope contributions --measure   reproduce the platform's known defects

Your own account, your own token, and **nothing about your projects goes
out at all** - not a name, not a path, not a count. The query asks about
`viewer`, so the platform resolves the account from the token and even
your username stays here. What leaves is a credential, two timestamps and
the word `murscope`.

It is still consented to. "It only reads, so it needs no consent" is the
same exemption as "localhost is not the network", and this page refuses
both for the same reason: your key leaves this machine to authenticate
the request, and the platform learns that you asked and when.

Three corrections are built in, because the figure is wrong without them
and wrong in ways that look right (`design/ADR-0003`, Rule 20):

- a range never ends later than the moment you asked, because a future
  endpoint is answered with a snapshot frozen part way through today;
- the cache is a **failure fallback and never a freshness shortcut** - a
  second run re-fetches whatever the age, and a figure served after a
  failed request is stamped with when it was gathered, not with now;
- the year range is corrected by a second live window and the total is
  summed from the corrected days, never read from the platform's own
  stated total.

Re-measured on 2026-08-13, the first and third did not reproduce: a
future endpoint and a clamped one agreed on every day, and six start
dates returned identical recent tails. The corrections stay - a range
ending later than now is wrong whether or not it is currently answered
wrongly - and Rule 20 now holds them against synthetic cases rather than
against the platform's current behaviour.

## Status

Pre-alpha, and the MVP is in: the commands below run, and the three
promises are measured rather than asserted. The enhancement layer is
being built now, behind the boundary above - the first stage was the
boundary itself, which is why the two installs exist before anything uses
them, and the second is the key store and the consent that governs it. A
base install still has no GitHub reader and no daily note, and can still
send nothing: it has no transport to send with.

    pipx install murscope
    murscope init

Two commands to a board. `murscope try <path>` shows you one first and
writes nothing to your home; `murscope doctor` says whether this
interpreter can read what you pointed it at; `murscope modules` prints
the module matrix - every provider module on your disk, which
distribution put it there, whether configuration enabled it, whether it
could open a socket, and, for the ones that were imported, what each
reads and writes and where each sends. **A module nothing imported reads
`unknown` there, never `no`**: being asked what it does is being
imported, and importing a module configuration did not name in order to
describe it is running it. `murscope selftest` proves,
on your machine, that the parser is still precise and that a real
collection, a real render and a real scan reach no network - under a
socket-refusing audit hook installed before its first step. What that
hook cannot cover is the package's own imports, which finish before it
goes on, and the selftest says so where it says the rest. It also reads
every provider module installed on your machine and tells you whether any
of them could open a socket, naming the distribution each came from - so
"nothing here can reach out" is something your own copy reports rather
than something this page asserts.

`murscope timer install` schedules the board to refresh with nobody
there - a launchd agent on macOS, a systemd user timer on Linux. **The
scheduled job collects and renders, and it cannot send.** Not "does not":
it runs its own command, `murscope-timer`, which takes no arguments, and
a check walks the call graph from that entry point on every build and
fails if a transport becomes reachable from it. murscope writes the job
file, prints the one command that turns it on, and stops there - it does
not talk to your scheduler, so `murscope timer status` tells you which
files exist rather than pretending to know what launchd is doing.
Demonstrated on macOS; the Linux unit is generated and has never been
loaded on a real system, which is said here rather than left for you to
find out. Windows has no timer: Task Scheduler takes its job from a
command rather than from a file, and that is a decision not yet taken.

`murscope alert` is the other half, and it is the one place this product
sends anything without you there. A rule fires when a project that was
moving goes quiet, or when a project's own ledger starts naming you as
the one it is waiting for; the alert is delivered locally by default and
that is all that happens on a fresh install. Sending it somewhere - a
webhook you can reach from your phone - takes three separate acts: the
network layer installed, a provider named in `config.toml`, and a consent
recorded **against the alert's own disclosure**, which is a different
table and a different fingerprint from the daily note's. Agreeing to one
has never agreed to the other.

**That consent is a different kind of thing and its screen says so.** The
daily note's consent authorises the request you are about to watch
happen; the alert's authorises murscope to send on its own, at moments
you are not present, until you say otherwise. The screen puts that in one
line near the top - *this one leaves while you are not here* - and a
check renders both screens on every build and fails if a reader could not
tell them apart.

What an alert carries is one sentence and four fields: which rule fired,
the project's id, the tier it moved between, and how many days since its
last commit. The sentence is composed from a template inside the package
and those four fields, and murscope refuses to send one that does not
recompose from exactly them - so nothing your project wrote can ride
along. **A project you marked sensitive is never evaluated by an alert
rule at all**, and unlike the daily note there is no count of what was
skipped in the message either: alerts leave one at a time, timestamped,
to somewhere other people may read, and a number that moves across that
stream is a way of saying something happened. You still see the count -
it is printed on your own machine.

A delivery that fails is recorded as failed, said on the next run and on
`murscope alert --status`, and the scheduled job exits non-zero. An alert
that did not arrive and left no trace saying so reads, from every angle
afterwards, like a quiet week.

## Rules and contributing

Every rule this product depends on is enforced by a script in
`scripts/checks/`, run by `python3 scripts/run_checks.py`. See
`CONTRIBUTING.md` for the rules and `CLAUDE.md` for the constitution.

Running that gate needs Python 3.9 or newer, `setuptools`, and a
JavaScript engine on PATH - `node`, `deno` or `bun`, whichever you have.
The engine is there because the board's behaviour is three hundred lines
of JavaScript and Rule 30 executes them; **it is a requirement of the
gate and never of murscope**. The package has zero runtime dependencies,
ships no toolchain, and the board opens in your own browser exactly as it
always did.

`skill/SKILL.md` is a Claude Code skill for driving murscope. It exists
for the one thing the command line will not do: murscope never writes
into a project it watches, and the sentence most worth having on the
board is the one a project's own status file carries. An agent can
interview you and write that line. Rule 32 checks that every command the
skill names is one this build has, and that it never tells an agent to
send anything or to agree to a send on your behalf.

## License and brand

MIT - see `LICENSE`. The name and palette are not covered by it; see
`BRAND.md` for what a fork is asked (not required) to do.
