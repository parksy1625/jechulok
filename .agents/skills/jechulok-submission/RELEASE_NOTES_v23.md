# JeChulOK Agent Skill v2.3.0 — installation/recovery lifecycle

Scope: the local Python Agent Skill, portable ZIP and stdio MCP.
Existing 20 MCP tools, file-creation approval gates and website remain unchanged.

## What ships

- New **read-only recovery-plan** CLI: checks a manually provided,
  trusted local release ZIP and a NEW destination, and reads current
  installation metadata/manifest status.
- Manual staged recovery protocol: old source diagnosis -> verify offline
  ZIP -> check new destination -> separately approve extraction ->
  explicitly install dependencies -> doctor/probe -> manually switch
  MCP client configuration.
- Fourteen deterministic disposable lifecycle cases, including real
  20-tool MCP stdio handshake to a newly extracted skill after simulated
  corruption of the previous install.
- Regression tests for corrupt ZIP, occupied targets, source manifest
  tampering, and preservation of synthetic user-file/client-config sentinels.
- Machine-readable sanitized JSON with scenario IDs and pass/fail flags.
- Portable v2.3 ZIP+SHA-256, six-platform CI, and synthetic recovery
  report uploaded as a GitHub Actions artifact.

## Preview and manual recovery

Run ONLY from a trusted skill installation, not potentially tampered
scripts. A checksum is NOT proof of publisher identity.

    python scripts/setup_mcp.py recovery-plan --allowed-dir YOUR_WORK_FOLDER \
      --archive TRUSTED_V2_3_ZIP --destination NEW_SKILL_FOLDER

This is read-only. Planned output does not create folders, install
dependencies, change the client config or remove the old installation.
Once verified and explicitly approved:

    python scripts/setup_mcp.py upgrade --allowed-dir YOUR_WORK_FOLDER \
      --archive TRUSTED_V2_3_ZIP --destination NEW_SKILL_FOLDER --execute

Then, from NEW_SKILL_FOLDER, separately run install (pip may require
network), doctor, probe, beta-check and config. Review and manually apply
the new client entry. Keep the old copy and old client entry to
revert manually. The tool never performs an automatic rollback.

## Synthetic local recovery audit

From the skill directory:

    python scripts/recovery_scenarios_v23.py --check

The harness creates only temporary invented fixtures: a fake user file,
fake client config, portable ZIP, old/new extracted installs and a broken
old source. It checks safe blocking and verifies a real MCP handshake
under the already installed test interpreter. It **does not** install
dependencies into the recovered copy. CI separately tests first-time
virtualenv installation on Linux.

A nonzero result means a scenario failed; no sensitive paths or document
content appear in the JSON report.

## Limitations

- No real users participated, so no independent user satisfaction data.
- No third-party security audit, signed artifact, authenticated publisher,
  automatic host-app registration or automatic rollback.
- Do not run suspect scripts when local source integrity checks fail.
- The new copy is not ready until dependencies are installed and its
  own doctor/probe succeed. Synthetic interpreter handshake is only a
  component smoke test.
- No actual institutional uploads or acceptance are tested, and file
  generation still requires independent human consent.
