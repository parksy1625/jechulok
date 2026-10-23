# JeChulOK Agent Skill v2.0.0

**Scope:** The local Python Agent Skill + stdio MCP only. The JeChulOK web
application is not part of this package and is not changed by this release.

## What changed

- Reproducible source ZIP containing offline MCP server, parsers,
  submission tools, setup assistant, and documentation.
- Per-file SHA-256 manifest inside the ZIP plus a full-archive checksum
  file. Checksums detect changes but are NOT digital signatures or
  proof of publisher identity.
- Explicit, side-by-side offline upgrade preparation. Preview first;
  extract only when --execute is given and the destination does not exist.
- Installer never edits Codex/Cursor/Claude Desktop configuration,
  overwrites an existing virtual environment, or downloads updates.
- Release-candidate archive is verified in CI; a separately created
  v2.0.0 tag triggers the gated GitHub Release publishing workflow.
- Full tests include a real MCP stdio handshake from the extracted ZIP.
  Existing 20 MCP tools are unchanged.

## Safe upgrade

1. Obtain the ZIP and checksum from a trusted GitHub repository release
   or the verified project's Actions artifact.
2. From an already installed skill directory preview the new installation:

       python scripts/setup_mcp.py upgrade --allowed-dir "/WORK/FOLDER" \
         --archive "/DOWNLOAD/jechulok-agent-skill-v2.0.0.zip" \
         --destination "/NEW/jechulok-skill-v2"

3. Review all paths, then repeat with --execute. A NEW folder is created.
   The prior environment and MCP client settings are untouched.
4. In the NEW folder run install, doctor, probe, and config in that order
   and manually merge the new MCP configuration entry into your client.
5. To roll back, reselect the previous client MCP entry pointing to the
   old installation. No automatic migration of user files is performed.

The work directory must already exist and be canonical. Python 3.11+
is required. PowerShell may use py -3.11 instead of python.

## Limits

- NOT independently security audited. Unit tests and GitHub CI are
  engineering safeguards, not a third-party penetration test.
- Unsigned release: SHA-256 proves consistency, not author identity.
  An attacker replacing both ZIP and checksum can bypass this protection.
- Version-ranged Python dependencies are not a fully reproducible,
  cryptographically locked third-party package supply chain.
- The initial pip install may require the network. Offline processing
  once dependencies are installed remains local only.
- File creation still needs human approval. No institutional upload is
  automated. Multi-file publishing is not power-failure atomic.
- No empirical real-notice accuracy is established by synthetic tests.

See QUICKSTART.md, EVALUATION.md, REAL_EVALUATION.md and SECURITY.md.
