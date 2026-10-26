# JeChulOK Agent Skill v2.9.0 — Explicit client configuration audit

Scope: local installation usability. The web service and 20 existing MCP
tools remain unchanged; no new automatic permissions or file transformations.

## Added

- `python scripts/setup_mcp.py config-check --client codex|cursor|claude-desktop
  --allowed-dir EXISTING_FOLDER --config-file ACTUAL_CONFIG_PATH`
  inspects **only** the explicitly named local config file.
- Parse Codex TOML or Cursor / Claude Desktop JSON and compare the
  `jechulok` command, args and allowed-folder setting against the local
  installation. Additional unrelated MCP server entries are not reported.
- Provide curated mismatch reason codes and a manual repair instruction.
  Never copy source paths, secrets, raw config text or exception text to
  output. Do not discover config files automatically.
- Reject aliases, symbolic links, nonregular files, oversized inputs
  (>128 KiB), malformed TOML/JSON and repeated JSON keys.
- Add 18 configuration regression tests and six fully synthetic audit cases
  with a dedicated CI workflow. No real client settings were inspected.

## Limitations

The command reads sensitive configuration **only with explicit operator
direction**. It does not install packages, access submission documents,
change any setting, use the network, start the server or measure actual
host registration. A matching config file is **not evidence** the client
loaded it. Use `doctor` and explicit `probe` separately, restart the app
and check its own MCP status.

Local release ZIP consistency via SHA-256 does not authenticate the
publisher. A version-tagged public release requires a separate deliberate
tag creation and CI gate; the tag is not created by this change.
