# JeChulOK Agent Skill v2.8.0 — Opt-in beta-study protocol preparation

Scope: standalone local Agent Skill support scripts and documentation.
The web service and all 20 existing MCP tools remain unchanged.

## Added

- `scripts/beta_protocol_v28.py protocol` supplies five fixed tasks using
  **invented** installation/notice/file/approval/verification scenarios,
  plus Korean or English participation and withdrawal information.
- `template --cohort baseline|current` outputs a strictly categorized,
  **default-unchecked** local study manifest JSON to copy manually.
- `audit --manifest LOCAL_JSON` checks only an explicitly provided
  manifest with booleans for consent notice presentation, voluntary
  participation, synthetic files, identifier exclusion and optional
  feedback. It never verifies any real participant's consent.
- `compare-preflight --baseline-manifest A --current-manifest B` checks
  matching fixed task set, questionnaire, recruitment category and
  moderation category, plus operator attestations. Matching entries
  do NOT prove participants, recruitment or application versions are
  actually comparable.
- Input hardening: strict allowlisted keys/values, no free text or IDs,
  at most 2 KiB JSON, no duplicate keys, symlink rejection and descriptor
  checks for regular files. Reports omit input paths and manifest contents.
- 19 new unit tests and six synthetic regression scenarios. No humans
  were recruited and no user feedback or documents were collected.

## Usage

From `.agents/skills/jechulok-submission`:

    python scripts/beta_protocol_v28.py protocol --language ko
    python scripts/beta_protocol_v28.py template --cohort baseline
    python scripts/beta_protocol_v28.py audit --manifest YOUR_LOCAL_JSON
    python scripts/beta_protocol_v28.py compare-preflight \
      --baseline-manifest BASELINE_JSON --current-manifest CURRENT_JSON
    python scripts/beta_protocol_audit_v28.py --check

All commands are read-only and print JSON. No network traffic, telemetry,
automatic participant invitations, file creation, participant information
storage, remote analysis or uploads. The organizer must separately obtain
and document informed consent according to applicable requirements,
provide withdrawal contact/procedure and conduct any beta testing.

This release prepares a controlled protocol but **does not conduct a
human study**, validate user satisfaction, demonstrate causality or
independently audit security. See BETA_GUIDE.md for the operator boundary.
