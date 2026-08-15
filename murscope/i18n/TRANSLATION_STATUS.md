# Translation status

Locales are maintained independently (DP10). There is no runtime
fallback between them: a key missing from the locale being rendered
shows up on the board as `[[MISSING:key]]`, loudly, where the person who
can fix it will see it. A quiet fall back to English would make a
half-translated board look finished.

The counts below are not decoration. Rule 8's check reads this table,
counts the keys in each locale file, and goes red when the two disagree
- a hand-written number is a claim until something counts it (DP25). In
the reference implementation this same number drifted from 45 to 111
with nobody noticing, which is why it is checked here.

| Locale | Keys | State | Notes |
|---|---|---|---|
| en | 112 | complete | Source language. New keys land here first. |
| zh | 112 | complete | Stored with `\uXXXX` escapes so the file stays ASCII (Rule 3). |
| fr | 112 | complete, **machine-translated, unreviewed** | Escaped the same way. Produced by a language model in one pass and read by nobody who speaks French. See below. |

## What `fr` is, and what it is not

**No native or fluent speaker has read this locale.** It was produced in
one pass by the language model that wrote the rest of that change, checked
mechanically for key coverage and for placeholder survival - a `{days}`
that became `{jours}` renders as `[[UNFILLED:...]]` on somebody's screen -
and not checked at all for whether a French reader would recognise the
register, the terminology, or the idiom.

That is written here rather than left to be inferred, because DP89's rule
is that a thing with no evidence behind it is named unverified and never
put in the same column as a thing that has some. `en` was written by the
people who wrote the product. `zh` was written by somebody who speaks it.
`fr` is neither, and a table that listed all three as "complete" with no
further word would be saying they are the same kind of thing.

The row above says `complete` about the **key coverage**, which is
counted, and `unreviewed` about the **translation**, which is not. If
somebody reviews it, that word changes and this section says who and
when. Until then it does not change, and nobody may change it on the
grounds that a review is expected.

## Escapes, and why a check counts them now

Every locale file is pure ASCII on disk. That has been the rule here
since the first locale landed and nothing enforced it until `fr` arrived,
for a reason worth keeping: Rule 3's scanner names CJK and emoji ranges,
so a raw Chinese value was caught by a different rule for a different
reason and the escape rule was never the thing doing the work. A raw
French accent is in none of those ranges. Measured, on a French locale
written unescaped: 322 non-ASCII bytes in a tracked file, and both Rule 3
and Rule 8 green. Rule 8 now counts the bytes.

The **French marker pack** is a different file and shipped earlier -
`markers/fr.json` is in the wheel and `blockers.packs = ["en", "fr"]`
resolves it. What arrived at M4 is the French **locale**, the board's own
strings.

## Adding a key

1. Add it to every file in `locales/`. All of them, in the same change -
   the check compares the locales against each other rather than against
   a designated source of truth, so a key added to one is a failure.
2. Update the counts in the table above.
3. Run `python3 scripts/run_checks.py`.

## Adding a locale

Copy `en.json`, translate the values, keep the keys byte-identical, add
a row here. Non-ASCII values must be written as `\uXXXX` escapes;
`json.loads` decodes them natively, so the escaping costs nothing at
runtime and keeps the repository greppable in ASCII.
