# JeChulOK Agent Skill v3.3.0 — bound preview + read-only postflight

**Scope:** Local CLI workflow for one explicitly selected source and one explicitly named NEW output. No new MCP tools, telemetry, uploads, conversion approvals or background tasks.

## What changed

- `scripts/conversion_guard_v33.py preview` starts with the existing v3.2 rules/geometry/risk preview, then attaches randomized, salted hashes of the source bytes and proposed target location. The JSON includes neither path nor original notice. The operator chooses whether and where to save the JSON report.
- After a separate explicit conversion approval and the ordinary `jechulok.py prepare-image` / `prepare-pdf` invocation, `scripts/conversion_guard_v33.py verify` reads that preview, the specified original, and the specified output. It checks preview integrity, source bytes, destination binding, file format and extension, JPG dimensions and size threshold, PDF page count and chosen-page geometry/order, and samples the predicted white padding where the border is wide enough for a reliable check.
- Differences **block** a technical pass; very narrow padding is **unverified**, not silently accepted. This postflight command creates, edits, deletes and uploads no files. It does **not** roll back a converter-produced file, or grant permission to create/upload one.
- 23 new synthetic tests and eight synthetic audit scenarios; a dedicated GitHub Actions job checks the no-path and no-user-data aggregate.

## Example

From `.agents/skills/jechulok-submission`:

```bash
python scripts/conversion_guard_v33.py preview \
  --input "/absolute/path/example.png" \
  --output "/absolute/path/result.jpg" \
  --rules "JPG 가로 300픽셀 세로 400픽셀 500KB 이하" > preview.json

# Stop here. Operator must independently review the plan and approve conversion.
python scripts/jechulok.py prepare-image \
  --input "/absolute/path/example.png" --output "/absolute/path/result.jpg" \
  --width 300 --height 400 --max-kb 500

python scripts/conversion_guard_v33.py verify \
  --preview-json preview.json --input "/absolute/path/example.png" \
  --output "/absolute/path/result.jpg"
```

If the preview has `status != ready_for_review`, do not treat it as a convertible plan or save it for postflight. The v3.2-only preview JSON is not accepted as a bound v3.3 plan. Keep plan JSON under user control: a checksum is not a signature or access control.

## Explicit limits

- Output file bytes, photograph identity/composition, visual equivalence in cropped areas, PDF text/content identity, digital signatures, form behavior, bookmarks and actual institutional acceptance remain **unverified**.
- For a PDF, different pages with identical geometry can pass geometry checks; page content/order must still be checked visually. For JPG, white-border sampling is not a guarantee the correct photograph was used.
- A source file changing during inspection is rejected when detected by bounded filesystem signatures and salted bytes; concurrent adversarial tampering is outside this guarantee. Original file size remains capped at 50 MiB, PDF inspection at 20 MiB and image dimensions at 24 million pixels.
- No recorded human approval is inferred from existence of a plan or an output. Postflight success is a limited technical signal, not permission to send the output anywhere.

The existing v3.2 preview, converter entrypoints and **20 MCP tools** are unchanged.
