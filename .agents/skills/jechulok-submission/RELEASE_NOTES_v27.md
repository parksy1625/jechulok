# JeChulOK Agent Skill v2.7.0 — Explicit comparison and privacy guardrails

Scope: offline Python Agent Skill and separate feedback utility only.
Website, user documents and the existing 20 stdio MCP tools are unchanged.

## New recommended analysis command

The v2.6 `feedback_insights_v26.py` remains available for compatibility.
Use `scripts/feedback_insights_v27.py` for new local analyses:

    python scripts/feedback_insights_v27.py prioritize \
      --directory EXISTING_LOCAL_FEEDBACK_FOLDER

    python scripts/feedback_insights_v27.py compare \
      --baseline-directory EXISTING_BASELINE_FOLDER \
      --current-directory EXISTING_CURRENT_FOLDER \
      --conditions-comparable

`prioritize` requires at least **20** opt-in categorical records, and
`compare` requires at least **30 in each** separately chosen folder.
Any nonzero issue category containing fewer than **five** records
suppresses the entire ranking or comparison. There is no per-person,
per-version or per-issue severity estimation. These thresholds are
conservative disclosure guards, not a guarantee against differencing
multiple overlapping reports.

## Explicit comparison gate

Without `--conditions-comparable`, comparison returns no differences
and **does not read feedback entries**. Operators should first examine
whether the same question wording, recruitment, reporting window and
support conditions apply. Supplying the flag is a human assertion only;
it is never independently verified. Counts may include repeated reports
from one individual, and user-partitioned folders cannot prove version
membership. Percentages are descriptive, **not** evidence of product
causality or statistical significance.

## Local file safety and validation

- Strengthened v2.5 summary input reading: regular-file file-descriptor
  checks, byte limits and `O_NOFOLLOW` where available, reducing the
  symlink-replacement race between path check and file read.
- New dedicated v2.7 tests for small samples, sparse cells, comparison
  opt-in, path sanitization, nonregular entries and unchanged files.
- Synthetic-only v2.7 privacy evaluation; no actual respondents, user
  documents, product-improvement measurements or network telemetry.
- Portable source ZIP and checksum remain reproducible. SHA-256 only
  checks integrity, not publisher identity. No automatic tag/release.

No new network calls, automatic collection, shared reports, institutional
uploads, exact-plan approvals or new MCP tools are introduced. Review
any aggregate report manually before sharing with others.
