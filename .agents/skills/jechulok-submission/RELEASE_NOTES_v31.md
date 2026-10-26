# JeChulOK Agent Skill v3.1.0 — Opt-in offline synthetic rehearsal

Scope: self-contained technical rehearsal with **invented** image and PDF
inputs. No changes to the 20 existing MCP tools or the Vercel web app.

## Added

- `python scripts/offline_demo_v31.py`: safe, no-write preview.
- `python scripts/offline_demo_v31.py --run`: explicitly run an end-to-end
  conversion and verification exercise in an automatically deleted OS temp
  directory. Optional `--format json` and `--language ko|en`.
- An illustrated PNG generated entirely in memory, then processed by the
  **existing** production JPG encoder into a 300×400 JPG below 500 KiB.
  A second independent check verifies file signature, extension, size and
  dimensions.
- An invented three-page blank PDF with distinguishable page dimensions,
  followed by actual production PDF extraction of pages 2–3. A second check
  verifies signature, page count, size and selected page order.
- Both original synthetic inputs are hash-checked for nonmodification.
  Outputs are only in the temporary directory and are removed before the
  terminal success report is returned.
- Six-stage fixed JSON report with no output paths, exception messages,
  contents, token data, timestamps, machine identifiers or telemetry.
- Dedicated regression tests and six synthetic audit cases covering the
  complete pipeline, cleanup, explicit opt-in, deterministic output and
  failure-safe reporting.

## Safety and limits

No personal documents, client configuration, manually configured allowed
directories or network APIs are accessed. The standalone rehearsal never
starts or registers an MCP server and does not upload anything. Unexpected
processing errors are reduced to a fixed stage identifier without exposing
local exception messages, and the temporary folder is cleaned up even on
failures. If the OS prevents cleanup, the result cannot claim cleanup passed.

The rehearsal verifies only **synthetic** file structures and explicit
technical checks. It cannot verify portrait composition, document meaning,
digital signatures, real-world usability, host integration or successful
acceptance by an organization. A Git tag / GitHub Release is an independent
publication step; this update does not create one automatically.
