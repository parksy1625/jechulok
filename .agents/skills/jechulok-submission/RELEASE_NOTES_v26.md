# JeChulOK Agent Skill v2.6.0 — Local feedback insights

Scope: optional local feedback analysis utility, existing offline Agent
Skill and unchanged 20 stdio MCP tools. No website change or telemetry.

## Improvements

- **Prioritize**: reads an explicitly selected v2.5 feedback directory.
  Ranks only independently disclosed categories by frequency and supplies
  a human-review suggestion for each. Ranking does NOT measure incident
  severity or real population impact.
- **Compare**: reads two explicitly selected feedback directories as
  baseline/current descriptive cohorts. Compares proportions to avoid
  comparing counts directly for different sample sizes, but never
  asserts that a new software version caused a change.
- Stronger minimum: each directory must contain at least **10**
  categorical records and have a nonsuppressed issue breakdown from the
  existing v2.5 privacy filter. Otherwise no individual issue results
  are provided.
- Directories must be distinct; raw records are never returned.
  Results contain only aggregate categorical counts and suggestions.
- No files are created, logs uploaded, network requests made, source
  documents read, MCP permissions changed or client telemetry collected.
- Synthetic regression: **20 checks** for two fabricated local
  20-entry cohorts, plus unit tests for sparse cells, missing samples,
  file preservation and unsupported inferences.
- Portable ZIP+SHA256 build and full existing Windows/macOS/Ubuntu
  Python 3.11/3.13 CI matrix remain.

## Local commands

From the skill directory with an already installed Python:

    python scripts/feedback_insights_v26.py prioritize       --directory PRIVATE_BASELINE_FEEDBACK_FOLDER

    python scripts/feedback_insights_v26.py compare       --baseline-directory PRIVATE_BASELINE_FEEDBACK_FOLDER       --current-directory PRIVATE_CURRENT_FEEDBACK_FOLDER

    python scripts/feedback_insights_audit_v26.py --check

The folders must already exist, be canonical and not symlinks.
The local CLI prints descriptive JSON and does not save reports by
default. If you use shell redirection to save a report, that is a
separate explicit user operation. Do not publish raw data or output
without an independent privacy/permission check.

## Interpreting the outputs

- A top-ranked response category is simply the **most frequently
  selected category** among the voluntarily recorded responses, not
  necessarily the most important or costly user issue.
- Counts may reflect a single person submitting multiple times.
  No user IDs, time periods, or product versions are automatically
  collected. The data cannot prove two directories contain independent
  cohorts from two actual application versions.
- Descriptive proportion differences are not causal evidence of
  an improvement. Sampling bias, different respondents, changing
  prompts and duplicate participation can explain any difference.
- No confidence interval or significance claim is calculated, and
  additional external human evaluation is required.
- Suppression of small cohorts/issue categories reduces disclosure
  risk but cannot guarantee privacy against differencing multiple
  overlapping reports. Output is NEVER automatically shareable.

No actual user feedback or real observed effectiveness measurements
are included in this release. See FEEDBACK.md and SECURITY.md.
