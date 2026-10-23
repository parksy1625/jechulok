---
name: jechulok-submission
description: Parse Korean technical submission criteria, prepare JPG images or selected PDF pages on local disk, and recheck output requirements. Use when users ask to resize a photo to exact pixels, limit a JPG file to a KB threshold, inspect image/PDF format and dimensions/pages, or prepare a locally verifiable submission file. Do not use for document content review, passport-photo compliance, OCR, legally binding signatures, Office conversions, or automatic uploads.
license: MIT
compatibility: Python 3.11+ with Pillow and pypdf installed. Local filesystem read/write permission required; no network access used during processing.
metadata:
  author: jechulok
  version: "0.5.0"
---

# JeChulOK Submission Agent Skill

Use the bundled Python CLI to prepare **local** submission files. Read the user's file paths and institution's exact requirements before executing. The tool never uploads files and never replaces an existing file.

## Setup

From this skill directory (`.agents/skills/jechulok-submission/`):

```bash
python -m pip install -r requirements.txt
python scripts/jechulok.py --help
```

If dependencies are unavailable, explain that setup failed; do not claim that a file was processed. Processing works offline after installation.

## MCP integration (v0.5, optional)

An MCP-capable agent may call nine local stdio tools. The original tools include `parse_submission_rules`, `prepare_from_requirements`, `check_file`,
`prepare_image`, `extract_pdf_pages`, `verify_submission`; multi-file tools are described below. If the JeChulOK MCP
server is connected, prefer these tools over shell commands. See [MCP.md](MCP.md)
for installation, allowed-directory settings and the security boundary.

```bash
python -m pip install -r requirements-mcp.txt
python scripts/mcp_server.py  # launched by your MCP host; not a network server
```

If the MCP server is unavailable, continue using the existing CLI. Do **not**
claim that simply cloning GitHub attaches the MCP server to ChatGPT or Codex.
The MCP server only accepts local paths within the configured allowed folders,
never overwrites files, and requires `crop_approved=true` for center-crop jobs.
Always run `verify_submission` on the produced file. A `pass` checks only the
user's explicitly provided technical requirements.

## v0.4: Long notices and multiple files

Use `analyze_submission_notice` when a recruitment announcement names separate
file items such as “증명사진: JPG 300×400px 500KB 이하” and
“이력서: PDF 5MB 이하, 최대 3페이지”. The deterministic parser returns
`item_01`, `item_02` etc., original line numbers and text evidence.

If any item is ambiguous, any common/unassigned format or numeric rule exists,
or the announcement does not label items explicitly, **stop and ask for review**.
No automatic matching of source files to labels. This is not semantic document
understanding, OCR, or an institutional policy lookup.

Then call `prepare_submission_batch` with one **explicit**
`{item_id,input_path,output_path,pages_to_extract}` mapping per recognized item.
First call with `execute=false` (the default) to see the full plan. Only after
the user explicitly approves the mapped plan should an agent call it with
`execute=true, confirm_execution=true`.

- JPG operations always create a separate JPG, preserving the original.
- PDF operations need user-chosen pages for extraction. If the existing PDF
  already meets its limits, omit `pages_to_extract` **and** `output_path` to
  verify it unchanged. A maximum-page limit never selects pages automatically.
- Central cropping needs `crop_approved=true` and real user permission.
- All paths must be under `JECHULOK_ALLOWED_DIRS`; outputs cannot overwrite
  originals, existing files, or each other.
- On a batch processing failure, newly completed batch outputs are rolled back.
  Do not claim partial completion as a success.
- Always report technical limitations, check files before sending, and never
  claim actual institutional acceptance.

CLI read-only analysis is also available:

```bash
python scripts/jechulok.py parse-notice --text '- 증명사진: JPG 300×400px 500KB 이하'
```

## v0.5: Suggest local candidate files, never auto-assign

When the user provides an authorized local directory containing possible
submission files, call `suggest_submission_files(notice_text, directory_path)`.
This tool is **read only** and scans only immediate files, up to 250 directory
entries. It ranks compatible filename/extension hints for each named item but
never inspects document contents, determines suitability, selects the file or
executes conversions.

Show the suggestions and unresolved items. Ask the user to review each
`item_id` → `input_path` selection before constructing an assignment. If a
filename suggests a resume, this is not proof the file is a resume.
`needs_review`, `no_candidates`, or `truncated=true` must be stated.
Symlinks and paths outside `JECHULOK_ALLOWED_DIRS` are not accepted. Do not
treat suggestions as permission to upload, edit, or submit data.

Then retain the v0.4 rule: obtain the dry-run plan from
`prepare_submission_batch(execute=false)` and require real user approval of
the exact paths and PDF page selections before the double-confirmed execution.
Never call execution immediately after suggestion without this separate review.

## Decision flow

1. **Understand the specification.** Ask for or use explicit pixel dimensions, max size, allowed file type, and PDF page limits. Don't invent rules from the user's institution. `--max-kb` uses KiB (1 KiB = 1,024 bytes).
2. **Inspect first.** Run `check` and parse JSON stdout. `pass` means **specified machine-checkable conditions** matched; it does not mean admission or submission success. `info` means no limits were requested. `fail` means a condition was violated. `unverified` means a requested property could not be checked.
3. **Select a supported operation:** `prepare-image` produces JPG from JPG/PNG/WebP, or `prepare-pdf` extracts requested pages from an unencrypted PDF <=20 MiB. HEIC, AVIF, OCR, office files, signable PDFs, PDF recompression, and edits to existing PDF text are not supported by this skill version.
4. **Keep content intact unless permitted.** Use `--mode contain` by default (white padding, no cropping). Only use `--mode cover` if the user explicitly authorizes center cropping. Explain that converting transparent images to JPG replaces transparency with white.
5. **Generate a new output.** The CLI refuses to overwrite existing files or output onto the input. If the destination exists, choose another new name.
6. **Recheck and inspect result JSON.** Both preparation commands internally re-parse and verify the new output. For the final response, report the returned output path, exact measured bytes/pixels/pages, and what remains unverified. Never report completion when exit code != 0 or `status` is not `pass`.
7. **Warn about limitations.** Original PDF signatures, attachments, interactive forms and bookmarks may not survive page extraction. A matching file format/pixel size/KB limit does not validate an applicant photo's background, face positioning, or institution-specific requirements.

## Commands

```bash
# Check a candidate photo (does not modify it).
python scripts/jechulok.py check --input /path/photo.png --format jpg --width 300 --height 400 --max-kb 500

# Create a separate JPG, preserving the whole photo with white padding by default.
python scripts/jechulok.py prepare-image --input /path/photo.png --output /path/photo-ready.jpg --width 300 --height 400 --max-kb 500 --mode contain

# Crop the center only after explicit authorization.
python scripts/jechulok.py prepare-image --input /path/photo.png --output /path/photo-cropped.jpg --width 300 --height 400 --max-kb 500 --mode cover

# Verify original PDF length and a size limit.
python scripts/jechulok.py check --input /path/portfolio.pdf --format pdf --max-kb 10240 --max-pages 8

# Extract pages 2-4 and 7, in that order. Output is new, not overwritten.
python scripts/jechulok.py prepare-pdf --input /path/portfolio.pdf --output /path/portfolio-selected.pdf --pages 2-4,7 --max-pages 4
```

## Tool contract

- **JSON on stdout.** The CLI emits one JSON object. `check` returns `status`, `file`, `checks`, `limitations`. `prepare-*` returns `status`, `input`, `output`, `report`, `warning`.
- **Exit codes:** `0` = success or informational check; `1` = processing error; `2` = failed rule; `3` = unverified required property.
- **Paths:** Use user-approved local paths; quote any shell paths and do not pass untrusted text as a shell program. Default output is `<stem>-jechulok.jpg` or `<stem>-jechulok.pdf` next to the input. Never silently overwrite.
- **Resource limits:** input up to 50 MiB, PDFs read/modified up to 20 MiB, output up to 50 MiB, image output <=24 million pixels, PDF extract up to 300 pages.
- **Security:** Process third-party images/PDFs as untrusted. Dependencies must be installed from trusted repositories, and local path access should stay inside the user-authorized workspace.

See [CONTRACT.md](references/CONTRACT.md) for detailed invariants and unsupported features.
- 증명사진: JPG 300×400px 500KB 이하\n- 이력서: PDF 5MB 이하, 최대 3페이지'
```

## v0.3 Korean requirements workflow

1. When the user provides submission instructions, call `parse_submission_rules` first (or run `python scripts/jechulok.py parse-rules --text 'JPG 300×400px 500KB 이하'`).
2. If status is `needs_review` or `no_rules`, do not edit automatically. Confirm ambiguous format choices, units, physical dimensions or unverified requirements with the user.
3. Call `prepare_from_requirements` only after obtaining unambiguous technical constraints. For PDF, require explicit user-selected `pages_to_extract`. Never infer pages from a maximum page count.
4. Use `contain` by default; do not use center crop without explicit approval. Keep original input unchanged.
5. Call `verify_submission` for the output; never confuse technical rule checks with institution acceptance.

## Decision flow

1. **Understand the specification.** Ask for or use explicit pixel dimensions, max size, allowed file type, and PDF page limits. Don't invent rules from the user's institution. `--max-kb` uses KiB (1 KiB = 1,024 bytes).
2. **Inspect first.** Run `check` and parse JSON stdout. `pass` means **specified machine-checkable conditions** matched; it does not mean admission or submission success. `info` means no limits were requested. `fail` means a condition was violated. `unverified` means a requested property could not be checked.
3. **Select a supported operation:** `prepare-image` produces JPG from JPG/PNG/WebP, or `prepare-pdf` extracts requested pages from an unencrypted PDF <=20 MiB. HEIC, AVIF, OCR, office files, signable PDFs, PDF recompression, and edits to existing PDF text are not supported by this skill version.
4. **Keep content intact unless permitted.** Use `--mode contain` by default (white padding, no cropping). Only use `--mode cover` if the user explicitly authorizes center cropping. Explain that converting transparent images to JPG replaces transparency with white.
5. **Generate a new output.** The CLI refuses to overwrite existing files or output onto the input. If the destination exists, choose another new name.
6. **Recheck and inspect result JSON.** Both preparation commands internally re-parse and verify the new output. For the final response, report the returned output path, exact measured bytes/pixels/pages, and what remains unverified. Never report completion when exit code != 0 or `status` is not `pass`.
7. **Warn about limitations.** Original PDF signatures, attachments, interactive forms and bookmarks may not survive page extraction. A matching file format/pixel size/KB limit does not validate an applicant photo's background, face positioning, or institution-specific requirements.

## Commands

```bash
# Check a candidate photo (does not modify it).
python scripts/jechulok.py check --input /path/photo.png --format jpg --width 300 --height 400 --max-kb 500

# Create a separate JPG, preserving the whole photo with white padding by default.
python scripts/jechulok.py prepare-image --input /path/photo.png --output /path/photo-ready.jpg --width 300 --height 400 --max-kb 500 --mode contain

# Crop the center only after explicit authorization.
python scripts/jechulok.py prepare-image --input /path/photo.png --output /path/photo-cropped.jpg --width 300 --height 400 --max-kb 500 --mode cover

# Verify original PDF length and a size limit.
python scripts/jechulok.py check --input /path/portfolio.pdf --format pdf --max-kb 10240 --max-pages 8

# Extract pages 2-4 and 7, in that order. Output is new, not overwritten.
python scripts/jechulok.py prepare-pdf --input /path/portfolio.pdf --output /path/portfolio-selected.pdf --pages 2-4,7 --max-pages 4
```

## Tool contract

- **JSON on stdout.** The CLI emits one JSON object. `check` returns `status`, `file`, `checks`, `limitations`. `prepare-*` returns `status`, `input`, `output`, `report`, `warning`.
- **Exit codes:** `0` = success or informational check; `1` = processing error; `2` = failed rule; `3` = unverified required property.
- **Paths:** Use user-approved local paths; quote any shell paths and do not pass untrusted text as a shell program. Default output is `<stem>-jechulok.jpg` or `<stem>-jechulok.pdf` next to the input. Never silently overwrite.
- **Resource limits:** input up to 50 MiB, PDFs read/modified up to 20 MiB, output up to 50 MiB, image output <=24 million pixels, PDF extract up to 300 pages.
- **Security:** Process third-party images/PDFs as untrusted. Dependencies must be installed from trusted repositories, and local path access should stay inside the user-authorized workspace.

See [CONTRACT.md](references/CONTRACT.md) for detailed invariants and unsupported features.
