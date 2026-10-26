# JeChulOK Agent Skill v3.0.0 — One-screen first-run checkup

Scope: consolidated, local-only installation status and guided next step.
The existing web service and all 20 MCP tools remain unchanged.

## Added

- `python scripts/setup_mcp.py checkup --allowed-dir WORK_FOLDER` combines
  existing environment checks into a short text report showing current
  stage and one recommended next manual action. It is safe to run without
  first installing the optional MCP packages.
- Optional `--language ko|en --format text|json --client CLIENT` output.
- **Explicit `--probe` only:** test local stdio server availability and
  20 tool names. Without this flag, do not spawn an MCP server.
- **Explicit `--config-file FILE` only:** audit an operator-selected Codex,
  Cursor or Claude settings file (which may contain secrets), using the
  v2.9 strict redacted parser. Do not discover or scan settings files.
- A failing local installation (especially mismatched packaged source
  integrity) blocks both optional tests, even when requested, rather
  than launching an unverified local server.
- Fixed four-stage, screen-reader-compatible plain-text output and
  stable categorized JSON; no paths, tokens, exception text or documents
  copied into results.
- 19 new deterministic unit tests and six synthetic-only audit cases.

## Safety and limits

`checkup` does not install, repair, upload, send telemetry, change settings,
select files, or approve file conversions. `--probe` can intentionally
start a **local** subprocess; `--config-file` can intentionally read an
existing local configuration file. Running both yields at most
`ready_for_manual_host_check`, not a claim that an MCP host loaded the
server or that an institution accepted any submission. The user must
separately inspect the MCP host status and test a synthetic invocation.

An explicit version tag and GitHub Release remain separate operations.
