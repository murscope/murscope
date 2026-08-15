## What changed

<!-- One paragraph. What is different after this merges, and why. -->

## Which rule covers it

<!-- Name the rule from CONTRIBUTING.md this change lives under, and the
check that enforces it. If this change introduces a new rule, it also
introduces the script that enforces it - Rule 1 has no exceptions.
If it touches scripts/checks/, say so explicitly: that is a frozen zone. -->

- Rule:
- Check:

## Gate output

<!-- Paste the real output of the command below. "Verified" means the
command was run and its output shown; otherwise write "unverified" and
say why. -->

```
$ python3 scripts/run_checks.py

```

## Red lines

- [ ] Writes nothing outside `MURSCOPE_HOME`
- [ ] Adds no network call and no third-party runtime dependency
- [ ] Adds no telemetry of any kind
- [ ] Every tracked file is English; display CJK is escaped
- [ ] No owner-private material enters the commit (`archive/`, `memory-mirror/`, `BRIEF.md`)
- [ ] No real person's name anywhere the derivation publishes (DP19).
      `LICENSE` carries the copyright
      holder, which is correct and out of scope for this one.
      **This box was ticked on every pull request this repository has
      merged, while the ledger module carried the owner's name in four
      lines** - `the_shipped_package_names_no_real_person` is what answers
      it now, and this box only records that you read the answer
- [ ] The repository is still private, and publication is still a
      derivation into a second repository (`PUBLICATION.md`, Rule 36).
      The one irreversible thing here is a setting, not a file
