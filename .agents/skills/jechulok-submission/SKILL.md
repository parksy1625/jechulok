---
name: jechulok-submission
description: Prepare a JPG image or extract PDF pages to satisfy submission requirements. Use when users ask to resize a photo to exact pixels, limit a JPG file to a KB threshold, inspect image/PDF format and dimensions/pages, or prepare a locally verifiable submission file. Do not use for document content review, passport-photo compliance, OCR, legally binding signatures, Office conversions, or automatic uploads.
license: MIT
compatibility: Python 3.11+ with Pillow and pypdf installed. Local filesystem read/write permission required; no network access used during processing.
metadata:
  author: jechulok
  version: "0.1.0"
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
