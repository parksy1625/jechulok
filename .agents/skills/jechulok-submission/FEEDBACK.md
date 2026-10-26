# JeChulOK v2.5 — Private, opt-in feedback

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
