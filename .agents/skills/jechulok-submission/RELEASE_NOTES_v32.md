# JeChulOK Agent Skill v3.2.0 — Read-only conversion risk preview

Scope: deterministic, local, single-file preflight **before** conversion.
Existing 20 MCP tools, Vercel web service, conversion behavior and explicit
execution approvals are unchanged.

## Added

- `python scripts/preview_prepare_v32.py --input FILE --rules TEXT` to
  inspect only an operator-selected local image or PDF. Optional `--output`
  validates a proposed new output filename without creating it; `--pages`
  selects PDF pages for preview; `--mode contain|cover` shows photo geometry.
- Parse requirements **before** inspecting the file. Ambiguous,
  contradictory, unsupported or missing format conditions stop early.
- Predict deterministic JPG pixel dimensions, honor EXIF orientation,
  estimate white-padding or center-crop area, and flag enlargements,
  metadata/transparency removal and JPEG size uncertainty.
- For PDF, require explicit page selection when exceeding the allowed
  limit, preserve selection order, and warn about potential impacts on
  signatures, bookmarks, attachments and interactive forms.
- Return an accessible Korean text result or machine-readable JSON with
  fixed action/risk codes and sanitized technical metadata. No absolute
  paths, filenames, raw error strings or notice text are returned.
- Explicit status separation: `already_compliant`, `needs_review`,
  `blocked`, `ready_for_review`. **None** authorizes conversion.
- New unit tests and six entirely synthetic regression scenarios validate
  no-write, no-path-leak, output collisions, cropping gate and PDF handling.

## Boundaries

This is a local file **read**, so always get explicit permission to inspect
the chosen input. It never writes user files, changes MCP client settings,
uploads data, chooses files automatically or approves a crop/conversion.
Previews do not encode JPG or extract PDF, thus they cannot guarantee output
file size, quality, font/metadata fidelity, identity, real submission rules
or institutional acceptance. For actual preparation, keep the existing
human approval and independent post-write verification workflow.

Published Git tags and Releases still require separate, deliberate action.
