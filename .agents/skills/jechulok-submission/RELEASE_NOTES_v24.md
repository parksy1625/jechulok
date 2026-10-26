# JeChulOK Agent Skill v2.4.0 — First-run user experience

Scope: the local Agent Skill / stdio MCP assistant and its installation
artifact. The public website is unchanged; the 20 MCP tools and explicit
human file-generation approval requirements are preserved.

## What changed

- All responses from the existing assist_submission guided workflow
  now include a new top-level **experience** summary containing five-step
  progress, the next human action, a curated next-action explanation,
  the number of missing original files, safe item IDs/expected formats
  and unresolved notice/plan blocker counts where available.
- The new summary is designed to avoid repeating original notice text,
  absolute filenames and local paths. The original detailed response
  remains present to support deliberate inspection of exact file plans.
- Progress percentage is strictly **stage progress**, never actual
  processing completion or institutional acceptance.
- No tool auto-selects source files, guesses ambiguous requirements,
  reuses human approval, or automatically uploads any information.
- Added a **24-state synthetic first-run evaluation**. Six invented
  two-document technical notices each pass through four workflow
  states (both files missing, one missing, full plan awaiting approval,
  and ambiguous rules). It asserts one grouped missing-files question,
  stage correctness, no unwanted file writes, no job starts, and
  privacy-safe experience metadata.
- The synthetic audit additionally reports one grouped prompt per
  two-missing-file case versus a *hypothetical* one-question-per-file
  baseline. This is a mathematical counterfactual, **not measured user
  behavior, observed reduction in prompts, or customer satisfaction**.
- Versioned v2.4.0 source ZIP+SHA256 and matrix CI continue to verify
  the existing 20-tool stdio MCP handshake, v2.3 recovery cases and
  earlier synthetic notice evaluations.

## Run evaluation locally

From the skill directory (dependencies already installed):

    python scripts/first_run_audit_v24.py --check

The output is structured JSON with a summary, fixed scenario identifiers
and pass/fail status. Nonzero exit means a regression. GitHub Actions
runs the same evaluation and uploads a sanitized JSON artifact. The
synthetic audit does **not** open personal documents, use user notices,
read home directories, contact external APIs, or submit to institutions.

## First use

Open your MCP-compatible client, call the existing assist_submission
tool with the **explicit notice text**, then read experience.next_action
and experience.next_step_help. When source files are missing, request
every file in experience.file_choices together. A filename suggestion is
a hint only; the user decides which source is correct.

When experience.requires_separate_human_approval is true, inspect the
original full preflight plan including paths, page ranges and image
crop choices. Consent is NOT implied by reading the progress metadata.
Files are created only by separately requesting the existing approved
execution path. Technical verification is NOT proof an institution has
received the submission.

## Limitations

- This is a deterministic UX regression, not a real usability study.
  No externally recruited beta testers or real user session timings.
- One grouped prompt does not mean all user questions are resolved in
  one interaction. Actual confusion/abandonment have not been measured.
- The original submission workflow can still contain source-derived
  evidence and exact local paths when needed for a user's review;
  only the new experience summary is purposely path-free.
- Checksums are not developer signatures and no third-party security
  audit has taken place.

See QUICKSTART.md, SECURITY.md and BETA_GUIDE.md.
