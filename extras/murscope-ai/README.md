# murscope-ai

The network layer for [murscope](../../README.md).

**What leaves your machine, where it goes, and on whose key.** Nothing
leaves until you have named a provider and supplied your own key, and
this distribution states what a request contains before the first one is
sent. The destination is whichever provider you named - a vendor's API on
the open internet, or a model on your own machine. A local model is still
the network for this product's purposes: a socket is a socket, and what
differs is where the data goes, which is what the consent text is for
(DP90). The key is yours; this product has no account, no proxy and no
server of its own.

Install it through the base package's extra, not on its own:

    pip install 'murscope[ai]'

Installing it puts provider modules on disk under `murscope/providers/`.
That is the point. `pip install murscope` does not, which is what keeps
the base package's second promise - "It makes no network call at all. Not
'off by default' - absent" - a fact about which files exist rather than a
setting (DP88).

Nothing here runs unless `config.toml` names it. Being installed is not
being enabled, and being enabled is not consent to send: those are three
separate gates and Rule 13 governs all three.

## The third gate, and why it is not a yes

`send()` refuses anything that is not a `murscope.consent.Grant`, and it
refuses it **before a socket is anywhere in the picture**. `consent=True`,
`consent=1`, `consent="yes"` and the sentinel string this transport took
in its first stage are all refused; so is a real grant recorded against a
different set of fields, or against a different destination.

A grant carries a fingerprint of the disclosure it was granted for. That
is the whole design and it exists because the alternative fails quietly:
if a consent were a boolean, then the day the payload grows, the old
agreement silently covers the new, larger one - nobody is asked again and
nothing goes red. So changing what leaves costs one re-consent, and it
cannot cost nothing.

    murscope consent show  network --to https://api.example.com/v1
    murscope consent grant network --to https://api.example.com/v1

## Your key is not in what this prints when it fails

A failing request is a surface. Hand `urllib` a URL with a key in its
query string and it answers `ValueError: unknown url type:
'...?key=<the key>'` - a string the standard library built, which lands
in an exception message, which becomes a traceback, which is an artifact.

So every failure here leaves through `murscope.keys.reraise_masked()`,
which redacts the text and raises `from None` - the second half being the
load-bearing one, because without it the original stays on `__context__`
and every traceback prints it under "During handling of the above
exception" with the key intact. The base package's gate makes this
transport fail with a decoy key in the URL and reads the whole traceback
back, on every run.

MIT, same as the base package.
