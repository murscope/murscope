---
title: Document title in one line
type: mgmt | decisions | boot | task | adr | template
captured: YYYY-MM-DD
status: active | draft | done | superseded
---

# Title

Every markdown file under `design/` and `templates/`
starts with the four frontmatter keys above (Rule 4). `CLAUDE.md`,
`README.md`, `CONTRIBUTING.md` and `BRAND.md` are exempt.

`captured` is the date the document was written, never a relative
phrase. `status` moves forward only: draft -> active -> done, or
-> superseded when a later document replaces this one.

Body is English (Rule 3). Discussion happens in Chinese; what lands in
the repository is English.
