# JeChulOK Agent Skill v2.2.0

Scope: Python Agent Skill, local stdio MCP and setup CLI only.
The JeChulOK web service and all existing 20 MCP tools are unchanged.

## New: accessible, read-only onboarding and recovery guide

Run:

    python scripts/setup_mcp.py guide --allowed-dir YOUR_FOLDER

By default, the guide prints clean, Korean, screen-reader-friendly text
without ANSI colors, interactive questions, personal file names or absolute
paths. English and machine-readable formats are available:

    python scripts/setup_mcp.py guide --allowed-dir YOUR_FOLDER --language en
    python scripts/setup_mcp.py guide --allowed-dir YOUR_FOLDER --format json
    python scripts/setup_mcp.py guide --allowed-dir YOUR_FOLDER --client cursor

The guide turns the local doctor result into one prioritized action:
1. Safety-critical source VERSION/manifest mismatch -> stop and reinstall
   from a trusted archive into a NEW folder; never auto-delete old files.
2. Python or isolated work-folder permission problems -> manually fix.
3. Missing virtual environment/dependencies -> review suggested install;
   pip may require network access, so installation is NEVER automatic.
4. A healthy environment -> explicitly run local MCP connection probe.

Only if the user adds --probe does the guide start the local stdio
handshake. A successful probe shows a suggested client config command;
the user must manually register the server with Codex/Cursor/Claude Desktop.
The guide does not edit any app config and cannot confirm host registration.

## Diagnostics and accessibility

- Korean/English curated instructions, stage numbers, stable error codes;
- Priority on unsafe/untrusted source conditions before dependency fixes;
- Plain text or JSON output, both free of document data and user paths;
- No network access, auto-installs, auto-repair, permission changes, client
  config writes, source modifications or uploaded telemetry;
- README/QUICKSTART include a simplified installation and rollback route.

## Release and safety

A versioned v2.2.0 ZIP + SHA-256 sidecar is built and checked on GitHub
Actions. CI runs the complete regression suite on Windows, macOS and Ubuntu
with Python 3.11/3.13; real extracted MCP handshake and the guide's
read-only behavior are included. A separately created v2.2.0 tag would
trigger the gated GitHub Release workflow: workflow configuration alone
does NOT create or publish such a release.

Checksums/manifest confirm consistency, not developer authenticity.
No independent security audit or actual external user study is claimed.
Existing explicit file approval, offline processing and scope restrictions
remain in place. Never run repair instructions on untrusted code.

References: QUICKSTART.md, SECURITY.md, BETA_GUIDE.md.
