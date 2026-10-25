# JeChulOK Agent Skill v2.1.0

Scope: local Python Agent Skill and local stdio MCP. The web service is
unchanged. All 20 existing MCP tools and approval requirements are retained.

## What's new

- User-triggered, opt-in GitHub stable release check:
  setup_mcp.py updates --allowed-dir WORK_FOLDER --online
- The same command WITHOUT --online is entirely offline. The online
  check uses a fixed HTTPS GitHub Releases API endpoint with a timeout
  and bounded JSON response; it NEVER downloads or installs software.
- Doctor now checks the installed VERSION and SKILL.md frontmatter.
  Versioned ZIP extracts now retain MANIFEST.json, enabling a local
  checksum consistency check for extracted files.
- Git source checkouts lacking a package manifest clearly report that
  file hash verification did NOT happen.
- Privacy-safe beta-check prints a compact read-only status and expected
  MCP tool count, without disclosing the local work folder.
- BETA_GUIDE.md provides an opt-in external test protocol and sanitized
  issue feedback instructions; no external testers or human outcomes are
  claimed to have participated.
- The versioned ZIP and SHA-256 artifact build plus six-platform CI
  matrix continue. The separate v2.1.0 tag release workflow is
  configured; it does not publish until the tag is actually created.

## Quick start

  python scripts/setup_mcp.py doctor --allowed-dir YOUR_WORK_FOLDER
  python scripts/setup_mcp.py probe --allowed-dir YOUR_WORK_FOLDER
  python scripts/setup_mcp.py beta-check --allowed-dir YOUR_WORK_FOLDER
  python scripts/setup_mcp.py updates --allowed-dir YOUR_WORK_FOLDER
  python scripts/setup_mcp.py updates --allowed-dir YOUR_WORK_FOLDER --online

The last command transmits a GitHub API request only; it does not send
documents, grant approvals, download archives, modify MCP configuration,
or install any updates.

For side-by-side offline upgrade, use the new v2.1 scripts to preview
the trusted ZIP and extract to a NEW folder with --execute only after
human confirmation. Verify, install dependencies, check MCP transport,
review client config, and keep the previous installation for rollback.

## Limitations

A checksum manifest detects inconsistent files but is not a signed
release or proof of publisher identity. The manifest and source could
both be replaced by a malicious party. Remote release metadata may be
unavailable (including when no stable GitHub Release exists).
Checking latest does not inspect prereleases. The local version can be
ahead of published releases. Python dependencies remain version-ranged.
The beta-check cannot prove real user usability, host IDE registration,
independent security review, or acceptance by an institution.

No telemetry or automatic updates were introduced. No real submitted
documents are included in the public test suite.

See QUICKSTART.md, BETA_GUIDE.md, SECURITY.md and MCP.md.
