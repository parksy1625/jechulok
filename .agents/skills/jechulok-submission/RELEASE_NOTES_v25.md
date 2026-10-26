# JeChulOK Agent Skill v2.5.0 — Opt-in feedback without telemetry

Scope: the local Python Agent Skill and its offline feedback utility.
The web product and all 20 existing local stdio MCP tools are unchanged.

## Added

- A new **optional, offline** `scripts/feedback_v25.py` command. Users
  choose only (stage, issue category, impact category). Freeform comments,
  files, paths, timestamps, OS/IDE identifiers and notice content are not
  accepted or retained.
- `preview` prints proposed categorical feedback without saving.
- `save` requires explicit choice of an existing destination directory;
  each local entry is created with a unique name and never overwrites an
  existing file. Owner-only POSIX permissions are requested.
- `summary` reads ONLY the chosen directory's .feedback-v25.json files,
  returns category counts but suppresses ALL breakdowns below five
  entries, and hides a category dimension if any cell contains fewer
  than three entries. Aggregate output is never automatically shared.
- No network calls, tracking SDK, background collection, outgoing API,
  auto-update, job start or change to exact-plan approval.
- New unit tests and a **31-case synthetic feedback regression** covering
  preview, local saving, invalid input, symlink protections and sparse
  aggregate suppression. GitHub CI publishes the synthetic JSON only,
  never actual user responses.

## Example

From the local skill directory:

    python scripts/feedback_v25.py preview --stage files \
      --issue file_selection_confusing --impact minor

To intentionally save, choose a dedicated already existing directory:

    python scripts/feedback_v25.py save --stage files \
      --issue file_selection_confusing --impact minor \
      --output-dir YOUR_PRIVATE_FEEDBACK_FOLDER

To summarize locally (never uploaded by the tool):

    python scripts/feedback_v25.py summary \
      --directory YOUR_PRIVATE_FEEDBACK_FOLDER

No freeform evidence is included. Delete your local entry manually to
withdraw it. Independently review any summary before sharing it.

## Methodology and limitations

The synthetic regression creates 30 fake responses plus an aggregation
check; no real people were asked and no usable satisfaction estimate was
obtained. Feedback responses are entirely voluntary and self-selected,
so they cannot estimate all-user confusion/satisfaction without a proper
sampling plan. Even a report with sufficient counts can carry disclosure
risk across repeated queries and must not be published automatically.

Checksums are not signatures. No independent security audit or human
beta study is implied by CI passes. For details, see FEEDBACK.md and
SECURITY.md. Existing manual file approval and no-institution-upload
boundaries continue to apply.
