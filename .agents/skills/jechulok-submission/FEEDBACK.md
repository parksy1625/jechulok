# JeChulOK v2.6 — Private opt-in feedback and offline insights

The new offline feedback tool is deliberately **not telemetry**.
It does not monitor MCP sessions, infer user behavior, or send feedback to
a server. The only allowed fields are three human-selected categories:

- Stage: notice, files, plan, prepare, check, installation
- Issue: unclear_next_step, unclear_technical_rule,
  file_selection_confusing, approval_confusing, error_message_unhelpful,
  operation_too_slow, installation_trouble, other_usability_issue,
  worked_well
- Impact: none, minor, blocked

No freeform notes, notice text, document paths, client IDs, environment
fingerprints, timestamps, names, IP addresses, or machine identifiers are
recorded. This avoids storing sensitive material but limits diagnostic
detail. The tool does not have access to the actual failed operation.

## Run entirely offline

From .agents/skills/jechulok-submission:

First, **preview without saving**:

    python scripts/feedback_v25.py preview --stage files \
      --issue file_selection_confusing --impact minor

Save only if explicitly desired. Create and select your own dedicated
feedback directory outside the repository, preferably not under a
sensitive document folder:

    python scripts/feedback_v25.py save --stage files \
      --issue file_selection_confusing --impact minor \
      --output-dir YOUR_EXISTING_FEEDBACK_FOLDER

The save command creates a unique, never-overwritten JSON file with
owner-only permissions on POSIX (0600). It never uploads anything.
Delete that file manually to withdraw the local feedback.

To see local aggregate counts:

    python scripts/feedback_v25.py summary \
      --directory YOUR_EXISTING_FEEDBACK_FOLDER

Summaries hide ALL category counts for fewer than five entries, and
suppress a whole category dimension if ANY nonzero category count is
smaller than three. This is intentionally conservative, though small
cohort privacy cannot be guaranteed across multiple different reports.
Summary results are **not automatically shareable** and should not be
published without additional human privacy review and consent.
Never share raw feedback files, directory contents, or private data.

## Safety and validation

- All strings are allowlisted. Arbitrary comments, filenames and extra
  fields are rejected.
- Both save and summary require an explicit existing canonical local
  directory. Symlinks and invalid records are rejected; occupied files
  are never overwritten.
- No background collection, remote API, network access, auto-installs,
  institutional uploads, MCP tool additions or changes in approval.
- Existing 20 stdio MCP tools are unchanged.
- Unit tests and a 31-case synthetic regression exercise preview,
  local file save, malformed inputs, symlink safety, small-cohort
  suppression, aggregated categories and source-file preservation.
- The public GitHub CI reports only **synthetic** findings. It never
  collects actual users' private feedback.

## Measuring improvements responsibly

Actual feedback must be collected separately from consenting people.
Because participants choose whether to respond, the data is
self-selected and **cannot estimate all-user satisfaction or prevalence
of confusion without appropriate sampling**. The local aggregated
categories can help prioritize fixes, but compare versions only after
controlling for who responded and how the questions were asked.

The v2.5 synthetic suite contains 30 generated responses plus one
aggregate safety check. No real user responded; its pass rate is only
a software-regression result, not measured user satisfaction.

## v2.6 — Rank issues and compare voluntary report cohorts locally

The separate, read-only v2.6 command accepts **only** the original local
four-field `.feedback-v25.json` records, with no new identifiers. It never
creates files, queries web services, reads submitted documents, or uploads
feedback. Run these commands from the skill directory:

    python scripts/feedback_insights_v26.py prioritize \
      --directory YOUR_EXISTING_FEEDBACK_FOLDER

The ranking is deliberately withheld below 20 records or if **any**
nonempty issue category has fewer than five records. When permitted, rank
reflects only the frequency of self-selected reports, not population
prevalence or how seriously people were affected. Suggestions are static
follow-up experiments, not automatic changes to the product.

For a descriptive side-by-side view, the user must manually keep records
for different versions in **two existing, disjoint folders**. The records
have no version or participant identifiers, so directory assignment and
repeat participation cannot be verified. First review the questionnaire,
participant recruiting, time window, and support-channel changes. Only if
you judge the conditions comparable, explicitly opt in:

    python scripts/feedback_insights_v26.py compare \
      --baseline-dir YOUR_OLD_VERSION_FEEDBACK_FOLDER \
      --candidate-dir YOUR_NEW_VERSION_FEEDBACK_FOLDER \
      --conditions-comparable

Without the last flag, the command returns no differences. With it, both
folders must contain at least 30 records and every nonzero issue count must
be at least five; otherwise all differences are hidden. The returned shares
and percentage-point differences describe only **voluntarily submitted**
records. They cannot establish independent users, statistical significance,
product causality, or representative satisfaction. Repeated queries across
different groups can reveal private information: never publish these
outputs without separate review and consent. Public CI uses synthetic
records exclusively (`python scripts/feedback_audit_v26.py --check`).
