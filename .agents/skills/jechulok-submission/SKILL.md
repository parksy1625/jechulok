---
name: jechulok-submission
description: Parse Korean technical submission criteria, prepare JPG images or selected PDF pages on local disk, and recheck output requirements. Use when users ask to resize a photo to exact pixels, limit a JPG file to a KB threshold, inspect image/PDF format and dimensions/pages, or prepare a locally verifiable submission file. Do not use for document content review, passport-photo compliance, OCR, legally binding signatures, Office conversions, or automatic uploads.
license: MIT
compatibility: Python 3.11+ with Pillow and pypdf installed. Local filesystem read/write permission required; no network access used during processing.
metadata:
  author: jechulok
  version: "1.4.0"
---

# JeChulOK Submission Agent Skill

## v1.4 — Crash-safe local job records and explicit recovery

The local MCP now exposes **19 tools**. Approved background jobs
(`start_submission_job` with two execution flags *after real user approval*)
write a **private, local, atomic job journal** in
`JECHULOK_ALLOWED_DIRS`'s first configured root under
`.jechulok-jobs/`. On POSIX the directory and files are created with
restrictive permissions. Records contain a job ID, state, staged and final
output paths and progress counts, but **no notice text, source file paths,
document contents, upload tokens or reusable approval**.

New jobs prepare JPG/PDF into a random, exclusive, same-directory
`.*.jechulok-<job-id>-<item-id>.jpg/pdf` staging name. Every item is
technically checked before publishing. Published files use an exclusive
hard link to prevent overwriting another process's final filename.
The original files remain unchanged. A cancelled/failed normal batch
cleans up its private staging files. Publishing is **not a single atomic
multi-file transaction**: an OS crash in the publishing phase may leave
some approved final outputs. Those outputs are never automatically deleted.

After a crash or forced restart, call `list_interrupted_submission_jobs`
to inspect **recorded** unfinished jobs, temp filename presence and
possible final outputs. An old job is **never restarted automatically**;
starting a new approved job is blocked until interrupted records are reviewed.

To resolve, call `resolve_interrupted_submission_job(job_id)` first
(read-only preview). ONLY after the user checks final output paths and
authorizes private temp cleanup, call it with
`cleanup_staging=true`, `confirm_cleanup=true`, and
`checked_final_outputs=true`. The tool verifies the stored random stage
name, scope and symlink safety, refuses cleanup if the old PID may be alive,
and deletes **only** verified staging files; it leaves all final output
files intact. It then marks the journal as reviewed, never as reapproved.

The journal itself may contain sensitive **output paths**. Never upload it
or commit it to Git. Job history isn't a verified receipt. The current
user and operating system are still responsible for protecting local
folders; interrupted writes have residual race and crash risks.


## v1.3 — Real per-item polling and cooperative cancel

The local stdio MCP server now exposes **17 tools**. For a long-running batch,
call `start_submission_job(notice_text, assignments, execute=false,
confirm_execution=false)` to perform an ordinary **read-only dry run**. It
starts no background job by default and shows the exact paths, PDF pages and
crop choice. After the user explicitly approves that specific plan, call with
**both** `execute=true` and `confirm_execution=true` to start a worker.

The response includes a random `job_id`. Call
`get_submission_job(job_id)` to poll the *real, current* per-item state.
This is **polling**, not server-push subscriptions or streaming from a
single blocking tool. At most **one batch job** can execute at once in the
local MCP process.

Call `cancel_submission_job(job_id)` to *request* cancellation. The worker
is not forcibly interrupted while processing an individual image/PDF; it
honors the flag at safe item boundaries, then removes **new files created
by the current batch**. Poll until the terminal state is `cancelled`,
`failed` or `completed`; `cancel_requested` alone is not final.
The original inputs remain untouched. Previously existing outputs are never
overwritten.

**Safety boundaries:** job state is in-memory and exists only in the currently
running MCP server process. If the process exits/crashes, job state and
cancel controls are lost and the user must manually inspect the local folder
before retrying. The worker is not a preemptive OS sandbox. Approval flags
cannot cryptographically prove human consent; the agent must obtain real
user permission. Restarting or retrying a completed/cancelled job never
reuses the old approval or automatically re-runs an operation.

Use `prepare_submission_batch` for traditional synchronous execution when
polling/cancellation is unnecessary. Only the local Skill/MCP implementation
is affected; no institutional upload is implemented.


## v1.2: Fast JPEG pass, timing and safe retry

When a photo has an explicit maximum KB size, the encoder first tries its
highest supported JPEG quality (95). If that **already meets** the size limit,
it needs only one encode. Otherwise it retains the lower-quality binary
search and verifies the resulting output from disk. `prepare_image` returns
`encoding_attempts` and `duration_ms`; `prepare_pdf` returns
`duration_ms`. Avoid promising a percentage performance increase from a
single timing.

`prepare_submission_batch` retains its default dry-run and double-confirmation.
Its result now includes a **completed-response snapshot**, `progress`, with
`phase`, `completed_items`, `total_items`, `percent` and
`live_streaming=false`, plus `duration_ms` and per-item durations for
successful items. This is not a live progress event subscription; an MCP caller
receives it only once the request finishes.

On blocked or failed batch results, show `retry_guidance`. Never automatically
retry, reuse former user consent, overwrite previous files or guess PDF pages.
After failure, inspect the filesystem for unexpected outputs, repair the
cause, run a new dry-run and obtain user approval for the revised exact plan.

For reproducible, **synthetic-only** local measurements, run
`python scripts/benchmark_v12.py`. Its temporary fixtures are deleted;
real user files are never measured by this script.



**v1.0 안정화:** The 14 MCP tools remain compatible with v0.9. File paths must
be canonical and may not pass through symlinked intermediate directories or
`..` aliases. A file with an unrecognized extension or unreadable image/PDF
structure must **never** be treated as technically compliant. After preparing a
batch, independently re-inspect final files; keep all institutional/content
checks manual. The new `tests/test_release_v10.py` exercises a real stdio MCP
session from notice parsing to offline reporting using synthetic files.
Read `SECURITY.md` at repository root for the explicit threat boundaries.


Use the bundled Python CLI to prepare **local** submission files. Read the user's file paths and institution's exact requirements before executing. The tool never uploads files and never replaces an existing file.

## v1.1: Confirm real local MCP connectivity

After local installation, run the `probe` command to connect to the actual
stdio MCP server and call only `parse_submission_rules` on synthetic example
text. The diagnostic **does not open the user's documents** and never changes
a client configuration. To inspect both installation and handshake in one
command, run:

```bash
python3 scripts/setup_mcp.py status --allowed-dir "/absolute/path/to/submission-files"
```

For separate checks use `doctor` for Python/dependency diagnostics and
`probe` for live local MCP handshake. `status=pass` proves that this
computer can start the MCP subprocess, *not* that the user's Codex/Cursor/Claude
client has connected. If `needs_attention`, show the returned `code`,
`fix` and any failing `doctor.checks`; do not guess, auto-write client
settings, or ask the user to share real documents as a diagnostic.

## v0.9: Guided local installation

For first-time installation, prefer the standard-library setup helper (Python
3.11+) rather than installing packages into the system Python:

```bash
python3 scripts/setup_mcp.py install --allowed-dir "/absolute/path/to/submission-files"
python3 scripts/setup_mcp.py doctor --allowed-dir "/absolute/path/to/submission-files"
python3 scripts/setup_mcp.py config --client codex --allowed-dir "/absolute/path/to/submission-files"
```

Use an existing, real, canonical directory. The installer creates a private
`.venv` in the skill folder and installs pinned-range dependencies there. It
does **not** modify the Codex, Cursor, or Claude Desktop MCP configuration.
The `config` command prints an escaped snippet to copy into the appropriate
client settings; choose `--client cursor` or `--client claude-desktop` for
JSON. Never automatically copy/edit another application's existing config,
expose all of the user's home directory or launch the server as a remote
network endpoint. `doctor` performs read-only local environment checks and
reports specific remediation items. A successful doctor cannot guarantee that
a particular AI client has connected to the MCP server.

For installation walkthrough and troubleshooting see `QUICKSTART.md`.
The installer may access the internet only when an individual user
explicitly runs the `install` command to obtain Python dependencies.

## CLI-only setup (alternative)

From this skill directory (`.agents/skills/jechulok-submission/`):

```bash
python -m pip install -r requirements.txt
python scripts/jechulok.py --help
```

If dependencies are unavailable, explain that setup failed; do not claim that a file was processed. Processing works offline after installation.

## MCP integration (v0.9, optional)

An MCP-capable agent may call fourteen local stdio tools. The original tools include `parse_submission_rules`, `prepare_from_requirements`, `check_file`,
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

## v0.6: Read-only output naming and technical status tracking

Once the user **manually confirms** each item-to-input mapping, call
`suggest_submission_output_paths(notice_text, assignments, output_directory)`
to propose new output filenames. This tool does not generate, reserve, or
approve files. Report any missing PDF page selection as a manual decision.
Existing compliant PDFs can be checked without generating copies.

Present the suggested paths to the user for review. The human-approved mapping
must then pass `prepare_submission_batch(execute=false)` preflight.
Only after separately approving that exact plan may the agent execute with
both `execute=true` and `confirm_execution=true`.

Read `summary.items[].technical_status` to report per-item progress:
`planned`, `awaiting_confirmation`, `blocked`, `rolled_back`,
`not_executed`, or `verified`. A `verified` result checks **only technical
file constraints**. Never equate this with a real submission or an institution's
acceptance. Do not treat preview proposals as approved final paths.

## v0.7: Separate review from technical success

Use `review_submission_plan` to show an exact, read-only preflight and
specific unresolved approvals or repair actions. Never infer permission from
`awaiting_human_approval`: this means the work is NOT approved yet. Confirm
the source files, output paths, PDF page range and crop permission with the
actual user, then obtain a separate explicit instruction to run
`prepare_submission_batch(execute=true, confirm_execution=true)`.

After files are produced, use `verify_submission_package` with the original
notice and each final `{item_id, file_path}` to independently re-open and
recheck them. A previous `pass` result or matching filename is not evidence
that a now-modified file will still pass. If any `remediation` item appears,
show the repair guidance and stop before actual submission.

Even `technical_pass` leaves every manual checklist item unchecked.
Never claim `ready_to_submit`, accepted/received by an institution, correct
photo composition, digital signature preservation, or validated document
content. No actual form submission is implemented.

## v0.8: Prioritized next question and private offline report

Prefer `guide_submission_workflow` when the user needs a conversational
walkthrough rather than a raw MCP tool protocol. It returns a single,
prioritized `question` and `next_action` using only the current notice,
the user-confirmed file mapping and (when supplied) the final files.
Never treat `awaiting_human_approval` as approval, and never select source
files or PDF pages without human input. Only after real approval of the
**exact** dry-run may you execute with the previous double-confirmed batch
call. The guided tool **never changes files**.

When the user wants an offline record, call
`create_submission_html_report(notice_text, files, output_path)` to preview
the current final-file inspection without writing. Show that preview and the
planned `.html` output path to the user. Only with explicit permission save
via `execute=true, confirm_execution=true`. The new HTML is local-only and
cannot overwrite an existing file. It includes basenames, technical statuses,
repair hints and unchecked human review steps, never file contents, full
filesystem paths or upload links. It may contain personal information inside
filenames. Do not send it to a server.

Even if `technical_pass` is reported, do not claim submitted/accepted.
Institution policies, applicant identity, image composition, PDF signature
validity and receipt remain manually checked.

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
