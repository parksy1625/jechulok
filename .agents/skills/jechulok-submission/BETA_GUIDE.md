# JeChulOK Agent Skill v2.8 — Voluntary Beta Study Preparation

## v2.8: Prepare without collecting personal data

The new optional tool prepares a fixed, synthetic-only study protocol:

    python scripts/beta_protocol_v28.py protocol --language ko

Use `--language en` for the same five task stages in English. The output
includes a voluntary participation/withdrawal notice, but **does not send
it to anyone**. An actual organizer must independently explain consent,
provide withdrawal instructions and arrange the study. Do not copy real
notices or participant files into this protocol.

Print a preflight JSON template (all sensitive attestations default to
`false`); if needed, copy it into a manually chosen local `.json` file:

    python scripts/beta_protocol_v28.py template --cohort baseline
    python scripts/beta_protocol_v28.py template --cohort current

The only allowed fields describe the cohort role, a fixed task set and
questionnaire, recruitment and moderation *categories*, and five boolean
operator checkboxes. No names, emails, timestamps, participant IDs, text
notes, file paths or document contents are accepted. Use these read-only
checks after creating the JSON files explicitly yourself:

    python scripts/beta_protocol_v28.py audit --manifest BASELINE_JSON
    python scripts/beta_protocol_v28.py compare-preflight \
      --baseline-manifest BASELINE_JSON --current-manifest CURRENT_JSON

`self_attested_checklist_complete` or `self_attested_protocols_match`
means **only** that operator-entered categories pass structural checks.
It does NOT verify that any person consented, that respondents are unique,
that conditions truly matched, or that the product improved. The tool
never writes a study record, contacts participants, reads application
documents, transmits telemetry or changes the MCP client's permissions.

Run the synthetic-only contract check locally:

    python scripts/beta_protocol_audit_v28.py --check

The older beta checklist below remains a historical reference. Never
publish actual participant information or consent evidence through the
public GitHub CI or repository.

## Historical v2.1 external beta checklist

Beta is opt-in. No telemetry, background updates, user-file uploads or
remote MCP services are added. This is a test protocol, NOT evidence that
external users participated or that an independent security audit occurred.

## Privacy and setup

Use a dedicated disposable folder containing invented JPG/PDF samples,
never personal application documents. Obtain the ZIP from a trusted
repository Actions artifact. The SHA-256 sidecar confirms consistency only,
not publisher identity. Extract into a NEW folder; do not merge
versions. Never publish logs, configuration, screenshots, document bytes,
work paths, email addresses or job journal files.

## Tester steps

1. Run setup_mcp.py doctor --allowed-dir YOUR_TEST_FOLDER. A verified
   packaged manifest proves files agree with their local hashes; it
   cannot prove who published those hashes. A Git checkout has no manifest
   and is reported as not verified by a packaged manifest.
2. Run setup_mcp.py probe --allowed-dir YOUR_TEST_FOLDER to exercise
   local stdio handshake and check the 20 MCP tools.
3. Run setup_mcp.py beta-check --allowed-dir YOUR_TEST_FOLDER for a
   concise privacy-safe status report and actionable failure codes.
4. Run setup_mcp.py updates --allowed-dir YOUR_TEST_FOLDER without
   --online and confirm no network request is made.
5. Opt in to the fixed GitHub Releases API only with
   setup_mcp.py updates --allowed-dir YOUR_TEST_FOLDER --online.
   The read-only query never downloads or installs an update.
6. Test a synthetic unambiguous JPG rule, verify that the preview creates
   no files, then explicitly approve a reviewed plan before creation.
7. Cancel a long synthetic batch and confirm no unexpected staging files
   remain. Final user outputs are never deleted automatically.
8. Crash/recovery tests must use disposable files. Confirm orphan cleanup
   requires human confirmation.

## Feedback template

Report only:
- Platform: Windows/macOS/Linux; Python major.minor;
- Distribution: Git checkout or trusted portable ZIP;
- Step: doctor, probe, beta-check, updates, preview or execution;
- Sanitized error code and reproduction using invented sample files;
- Expected behavior vs observed behavior.

Never share personal paths, inputs, identifiers or application documents.
A passing beta-check does not prove that the host IDE loaded its config,
that an institution accepted documents, or that external users tested it.

## Future independent beta acceptance

Actual external validation would require at least three independently
tested environments, documented revert/rollback confirmation, explicit
approval protections and a reviewed, sanitized issue log. No such human
study is claimed in the v2.1 release.
