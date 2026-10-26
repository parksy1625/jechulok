# JeChulOK Agent Skill v2.6.0 — Local-only feedback insights

Scope: independent, read-only CLI addition. The web service and all 20
existing local MCP tools remain unchanged. v2.5's opt-in feedback format,
storage rules and manual workflow permissions remain unchanged.

## Added

- `scripts/feedback_insights_v26.py prioritize --directory FOLDER` ranks
  local v2.5 issue categories by *share of self-selected feedback reports*.
  It returns a fixed corresponding follow-up experiment, not an automated
  fix, inferred severity, or estimate of all users' experiences.
- Ranking requires at least 20 records; any issue cell containing 1–4
  records suppresses the **entire ranking** to prevent simple subtraction
  from a reported total.
- `compare --baseline-dir OLD --candidate-dir NEW --conditions-comparable`
  computes descriptive category-share differences (percentage points) in
  two user-partitioned folders. It requires 30 or more records **in each**
  cohort and at least five records in every nonempty category in each.
- `--conditions-comparable` is an explicit acknowledgement by the operator,
  never a verified condition. Without it, no category differences display.
- Hardened local file reading: bounded entry count and byte length,
  regular files only, no symlink following where supported. Malformed
  schema, missing folders, and identical comparison paths are rejected.
- 14 new automated unit tests plus a six-scenario synthetic read-only
  regression. No real people, documents or feedback participated in CI.

## How to run

From `.agents/skills/jechulok-submission`:

    python scripts/feedback_insights_v26.py prioritize --directory LOCAL_FOLDER

    python scripts/feedback_insights_v26.py compare \
      --baseline-dir BASELINE_FOLDER \
      --candidate-dir CANDIDATE_FOLDER \
      --conditions-comparable

    python scripts/feedback_audit_v26.py --check

## Methodological / privacy limits

No online telemetry, automatic sending, persistent identifiers, versions,
device info, free-text answers or private document paths are introduced.
Outputs contain no local paths, are NOT automatically shareable and must
be manually reviewed. Because users opt in and may respond multiple times,
the reported distribution is not a representative user metric. A change
in reported issue share does **not** prove a version improved, nor imply
statistical significance or valid matched cohorts. Folder assignment is
user-provided; sampling protocol cannot be independently verified.

Category suppression reduces direct disclosure, but repeated comparisons
of overlapping or selectively modified folders can still reveal counts.
Do not publish sensitive reports or repeatedly probe changing groups.
Existing manual approval, no-upload rules and offline processing continue.
