# Canary project

This directory ships with the package and exists for one assertion in
`murscope selftest`: a roster entry marked `sensitive` must never emit the
contents of its files, whatever shape the reader that would have read them
is written in.

The string below is the decoy. If it ever appears in a rendered board,
in data.json, in data.js, in the run's problem list or anywhere else a
sensitive entry's output can reach, Rule 7 has been broken and the
selftest says so.

BLOCKED: MURSCOPE-SENSITIVE-CANARY-MUST-NOT-BE-EMITTED

- [ ] an unchecked item, so signal 8 would have something to count
- [ ] a second one

TODO: a code marker, so signal 9 would have something to count
